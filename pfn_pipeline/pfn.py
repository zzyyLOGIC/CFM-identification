"""Train a named DGP model and load supported four-arm GMM checkpoints.

The bundled causalpfn_v0.pt is a BASELINE, not a trained checkpoint for this model.
Relative checkpoint names resolve under research/checkpoints. The ER estimation
demo is the default training prior; unknown releases are rejected.
"""
from dataclasses import dataclass, field
import hashlib
from pathlib import Path

import numpy as np

from .contracts import TaskSpec
from ._internal.paths import CHECKPOINTS_DIR, DEFAULT_CHECKPOINT, checkpoint_path
from ._internal.estimation.priors import DEFAULT_DGP, VERSIONS, checkpoint_dgp, validate_dgp

__all__ = ["PFNModel", "build_model", "load_checkpoint", "train_model", "predict"]


@dataclass
class PFNModel:
    model: object
    device: str
    provenance: dict = field(default_factory=dict)
    graph_record: dict | None = None
    trained: bool = False


def build_model(*, device="cpu", seed=0, dgp=DEFAULT_DGP, **model_options) -> PFNModel:
    """Construct an explicitly UNTRAINED model; does not install or select weights."""
    import torch
    from ._internal.estimation.train_local_network_interference import (
        LocalNetworkQueryTransformer, ModelConfig, resolve_device)
    from ._internal.estimation.cepo import PREDICTION_PROTOCOL, ARM_NAMES
    validate_dgp(dgp)
    resolved = resolve_device(device)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        model = LocalNetworkQueryTransformer(ModelConfig(**model_options)).to(resolved)
    return PFNModel(model, str(resolved), {
        "estimation_version": VERSIONS[dgp], "dgp": dgp, "prediction_protocol": PREDICTION_PROTOCOL,
        "upstream_arm_order": list(ARM_NAMES), "model_status": "untrained",
        "outcome_scale": "original", "exposure_definition": "strict_majority"})


def load_checkpoint(path=None, *, device="cpu") -> PFNModel:
    """Load supported weights strictly; default: the bundled ER estimation demo.

    Loading never trains or updates parameters. An explicit path overrides the
    default, retaining the checkpoint's own version, graph and provenance.
    """
    from ._internal.estimation.causalfm_experiment.training import load_model
    from ._internal.estimation.train_local_network_interference import resolve_device
    from ._internal.estimation.cepo import ARM_NAMES
    path = checkpoint_path(DEFAULT_CHECKPOINT if path is None else path)
    resolved = resolve_device(device)
    model, state = load_model(path, device=resolved)
    if "graph_record" not in state:
        raise ValueError("Current checkpoint must retain its training graph_record")
    from .simulation import load_graph
    load_graph(state["graph_record"])  # Verify the graph before accepting weights.
    model.eval()
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    digest = hasher.hexdigest()
    return PFNModel(model, str(resolved), {
        "checkpoint_path": str(path), "checkpoint_sha256": digest,
        "estimation_version": state["version"], "prediction_protocol": state["prediction_protocol"],
        "upstream_arm_order": list(ARM_NAMES), "model_status": "trained_checkpoint",
        "epoch": state.get("epoch"), "outcome_scale": "original",
        "best_epoch": state.get("best_epoch"),
        "best_validation_nll": state.get("best_validation_nll"),
        "training_data_identity": state.get("data_identity"),
        "dgp": checkpoint_dgp(state), "training_noise_sd": state["config"]["noise_sd"],
        "training_graph_sha256": state["graph_record"]["adjacency_sha256"],
        "model_config": dict(state["model_config"]),
        "exposure_definition": "strict_majority", "mu01_training_status": "directly_supervised",
    }, state["graph_record"], True)


def train_model(output_dir=None, *, resume=False, **options) -> Path:
    """Run the migrated training implementation; outputs go to an explicit run folder.

    Default output is checkpoints/linear_b_random_a, default device is CPU. Production
    task counts/architecture retain upstream defaults; use small explicit values
    for a smoke test. Training caches default to research/.cache/pfn_pipeline.
    """
    from ._internal.estimation.causalfm_experiment.training import RunConfig, train
    options.setdefault("device", "cpu")
    config = RunConfig(**options)
    output = CHECKPOINTS_DIR / config.dgp if output_dir is None else Path(output_dir).resolve()
    return train(config, output, resume=resume)


def predict(model: PFNModel, task: TaskSpec, *, allow_untrained=False, allow_new_graph=False) -> dict:
    """Forward-only prediction from factual data; no oracle or candidate allocations.

    Returns four named mean vectors plus their marginal GMMs. Marginals are not a
    joint posterior and no calibrated intervals are manufactured. New topologies
    require explicit opt-in and carry a graph-generalization diagnostic.
    """
    import torch
    from dataclasses import replace
    from ._internal.estimation.cepo import ARM_COORDINATES, ARM_NAMES, cepo_queries
    from ._internal.estimation.fixed_er_graph import _decode_graph
    if not isinstance(model, PFNModel):
        raise TypeError("model must come from build_model or load_checkpoint")
    replace(task)
    if not model.trained and not allow_untrained:
        raise ValueError("Model is untrained; supply a current checkpoint or explicitly allow_untrained")
    if task.outcome_kind != "continuous" or task.exposure_definition != "strict_majority":
        raise ValueError("Current learned backend requires continuous outcomes and strict-majority arms")
    if task.assignment_design.get("assignment_probability") != 0.5:
        raise ValueError("Current training target uses Bernoulli(1/2); a different p changes the estimand")
    same_graph = None
    if model.graph_record is not None:
        record = model.graph_record
        trained_graph = _decode_graph(record["n_units"], record["upper_hex"]).numpy()
        same_graph = np.array_equal(trained_graph, task.adjacency)
        if not same_graph and not allow_new_graph:
            raise ValueError("Task graph differs from the training graph; set allow_new_graph explicitly")
    batch = {"tokens": torch.tensor(task.factual_tokens(), dtype=torch.float32,
                                     device=model.device).unsqueeze(0),
             "adjacency": torch.tensor(task.adjacency, dtype=torch.float32,
                                        device=model.device).unsqueeze(0)}
    was_training = model.model.training
    model.model.eval()
    try:
        with torch.inference_mode():
            output = model.model(batch["tokens"], cepo_queries(batch), batch["adjacency"])
    finally:
        model.model.train(was_training)
    marginal = {key: output[key][0].detach().cpu().numpy().copy()
                for key in ("gmm_pi", "gmm_mu", "gmm_sigma")}
    pi, means, sigma = (marginal[key] for key in ("gmm_pi", "gmm_mu", "gmm_sigma"))
    if (pi.ndim != 3 or pi.shape[:2] != (task.n_nodes, 4)
            or means.shape != pi.shape or sigma.shape != pi.shape
            or not all(np.isfinite(value).all() for value in marginal.values())
            or np.any(pi < 0) or np.any(sigma <= 0)
            or not np.allclose(pi.sum(-1), 1, rtol=1e-5, atol=1e-6)):
        raise ValueError("Invalid four-arm marginal GMM output")
    mu = np.sum(pi * means, axis=-1)
    return {"node_ids": task.node_ids,
        "mu_by_state": {tuple(map(int, state)): mu[:, index].copy()
                        for index, state in enumerate(ARM_COORDINATES)},
        "marginals": {**marginal, "arm_order": tuple(ARM_NAMES)},
        "provenance": {**model.provenance, "graph_matches_training": same_graph,
                       "finite_sample_guarantee": "none"}}
