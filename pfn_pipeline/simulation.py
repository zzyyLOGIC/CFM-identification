"""Named synthetic priors; oracle values leave through a separate evaluation return."""
import json
import hashlib
from collections.abc import Mapping
from fractions import Fraction

import numpy as np

from .contracts import TaskSpec
from ._internal.paths import DEFAULT_GRAPH
from ._internal.estimation.priors import DEFAULT_DGP, default_graph, prior_definition

__all__ = ["load_graph", "simulate_task"]


def load_graph(path=None) -> np.ndarray:
    """Verify/decode a graph JSON path or checkpoint graph_record; default: ER300."""
    from pathlib import Path
    from ._internal.estimation.fixed_er_graph import _decode_graph, adjacency_sha256
    record = path if isinstance(path, Mapping) else json.loads(
        Path(path or DEFAULT_GRAPH).read_text(encoding="utf-8"))
    graph = _decode_graph(record["n_units"], record["upper_hex"])
    if adjacency_sha256(graph) != record["adjacency_sha256"]:
        raise ValueError("Saved graph failed its SHA256 check")
    return graph.numpy().astype(np.int64)


def simulate_task(seed=2026, *, task_id=0, stream=None, adjacency=None,
                  noise_sd=4.0, treatment_prob=0.5, dgp=DEFAULT_DGP, outcome_family=None,
                  budget=5, budget_mode="at_most", return_reference=False):
    """Sample a synthetic score task; default: random-a linear B on saved ER300.

    Default return: TaskSpec. With return_reference=True: (TaskSpec, reference).
    Only the latter contains oracle mu and mechanism provenance. Synthetic
    assumptions are explicitly attributed to this generator; real-world tasks
    must supply their own identification_spec rather than reuse this declaration.
    dgp='random_functions' retains the legacy mixture prior and ER20 default.
    The random-a default stream is scaling_v1/test, matching batch evaluation.
    """
    from ._internal.identification.schemas import NetworkExposureSpec
    from ._internal.identification.majority_response import make_majority_response_spec
    from ._internal.identification.majority_score import make_majority_score_spec
    generate_task, _, _, _ = prior_definition(dgp)
    stream = ("scaling_v1/test" if dgp == DEFAULT_DGP else "test") if stream is None else stream
    graph = load_graph(default_graph(dgp)) if adjacency is None else np.array(adjacency, copy=True)
    options = {}
    if dgp == DEFAULT_DGP:
        if outcome_family is not None:
            raise ValueError("outcome_family applies only to dgp='random_functions'")
    else:
        options["outcome_family"] = outcome_family or "mixture"
    generated = generate_task(graph, task_id=task_id, seed=seed, stream=stream,
        noise_sd=noise_sd, treatment_prob=treatment_prob, **options)
    batch = generated.batch
    ids = tuple(f"node-{i}" for i in range(graph.shape[0]))
    edges = [(ids[i], ids[j]) for i, j in zip(*np.where(np.triu(graph, 1) == 1))]
    graph_hash = hashlib.sha256(np.asarray(graph, dtype=np.uint8).tobytes()).hexdigest()
    net = NetworkExposureSpec(network_id=f"shared-fixed-network-{graph.shape[0]}-{graph_hash[:12]}",
                              node_ids=list(ids), undirected_edges=edges)
    spec = make_majority_response_spec(net,
        assignment_probability=str(Fraction(str(treatment_prob))),
        source=f"pfn_pipeline.simulation {dgp} DGP",
        evidence=(
            "Known fixed pre-treatment network and documented iid Bernoulli assignment. "
            "The simulator outcome function is evaluation truth only and is not used by Identification."
        ),
        admitted=True, query_authority="TRUSTED_FIXTURE", synthetic=True)
    spec = make_majority_score_spec(spec, budget=budget, budget_mode=budget_mode)
    spec.query.authority = "TRUSTED_FIXTURE"
    task = TaskSpec(name=f"{dgp} network task", target_id=f"{dgp}/{stream}/{seed}/{task_id}",
        estimand=spec.query.type,
        target_semantics="design_averaged_majority_response_score_not_rollout_welfare",
        node_ids=ids, adjacency=graph, assignment_design={
            "design_type": "randomized_experiment", "assignment_probability": treatment_prob},
        exposure_definition="strict_majority", outcome_kind="continuous",
        x=batch["x"][0].numpy()[:, None], treatment=batch["observed_treatment"][0].numpy(),
        outcome=batch["y_obs"][0].numpy(), budget=budget, budget_mode=budget_mode,
        assumptions=tuple(a.model_dump(mode="python") for a in spec.assumptions),
        identification_spec=spec.model_dump(mode="python"),
        metadata={"source": "synthetic", "dgp": dgp, "graph_sha256": graph_hash,
                  "graph_n_nodes": int(graph.shape[0]),
                  "identification_route": "randomized_network_design_standardized_arm_mean"})
    if not return_reference:
        return task
    reference = {"target_id": task.target_id, "node_ids": task.node_ids,
        "target_semantics": task.target_semantics, "mu": batch["oracle_arm_means"][0].numpy().copy(),
        "metadata": dict(generated.metadata)}
    return task, reference
