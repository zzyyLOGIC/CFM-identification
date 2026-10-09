"""Numerical evaluation with explicitly separate simulation references."""
import numpy as np

from .contracts import EstimateBundle, PolicyResult

__all__ = ["effect_table", "evaluate_estimates", "evaluate_policy", "evaluate_checkpoint"]


def effect_table(mu):
    """Return [node, direct/spillover/total] using 10-00, 11-10 and 11-00."""
    mu = np.asarray(mu, dtype=float)
    if mu.ndim != 3 or mu.shape[1:] != (2, 2) or not np.isfinite(mu).all():
        raise ValueError("mu must be a finite [N,2,2] response surface")
    return np.column_stack((mu[:, 1, 0] - mu[:, 0, 0],
                            mu[:, 1, 1] - mu[:, 1, 0], mu[:, 1, 1] - mu[:, 0, 0]))


def _reference(task, reference):
    if (reference.get("target_id") != task.target_id
            or tuple(reference.get("node_ids", ())) != task.node_ids
            or reference.get("target_semantics") != task.target_semantics):
        raise ValueError("Evaluation reference target, semantics or node order differs from the task")
    mu = np.asarray(reference["mu"], dtype=float)
    if mu.shape != (task.n_nodes, 2, 2) or not np.isfinite(mu).all():
        raise ValueError("Reference mu must be finite with shape [N,2,2]")
    return mu


def _metrics(estimate, truth):
    error = np.asarray(estimate) - np.asarray(truth)
    return {"mae": float(np.abs(error).mean()), "rmse": float(np.sqrt((error**2).mean())),
            "bias": float(error.mean())}


def evaluate_estimates(estimates: EstimateBundle, reference: dict) -> dict:
    """Evaluate four-arm and effect errors; reports no unsupported interval coverage."""
    if estimates.kind != "response_surface" or estimates.center is None:
        raise ValueError("This evaluator requires a point response surface")
    truth = _reference(estimates.task, reference)
    predicted_effects, true_effects = effect_table(estimates.center), effect_table(truth)
    return {"response_surface": _metrics(estimates.center, truth),
        "ite": {name: _metrics(predicted_effects[:, i], true_effects[:, i])
                for i, name in enumerate(("direct", "spillover", "total"))},
        "ate": {name: {"estimate": float(predicted_effects[:, i].mean()),
                       "reference": float(true_effects[:, i].mean())}
                for i, name in enumerate(("direct", "spillover", "total"))},
        "n_nodes": estimates.task.n_nodes}


def evaluate_policy(result: PolicyResult, reference: dict) -> dict:
    """Evaluate the selected allocation's oracle RESPONSE SCORE, not rollout welfare."""
    if result.abstain or result.allocation is None:
        return {"abstain": True, "reason": result.stop_reason}
    if result.task.estimand != "NETWORK_MAJORITY_RESPONSE_POLICY_SCORE":
        raise ValueError("This evaluator only supports the majority-response score")
    mu = _reference(result.task, reference)
    values = mu[np.arange(result.task.n_nodes), result.allocation, result.resulting_exposure]
    return {"predicted_score": result.predicted_value, "reference_score": float(values.mean()),
            "reference_score_gain": float(values.mean() - mu[:, 0, 0].mean()),
            "budget_used": result.budget_used, "feasible": result.feasible,
            "semantics": result.task.target_semantics,
            "actual_rollout_welfare": "not_evaluated", "global_optimality": "not_certified"}


def evaluate_checkpoint(checkpoint, output_dir, *, device="cpu", baselines=False, **options):
    """Run migrated multiseed research evaluation into a caller-selected directory.

    Optional baselines retain upstream dependencies (including torch-geometric
    for HyperSCI). This explicit experiment operation writes its normal outputs;
    the pure evaluate_estimates/evaluate_policy functions above write no files.
    """
    from importlib.util import find_spec
    from ._internal.paths import CACHE_DIR, checkpoint_path
    from ._internal.estimation.causalfm_experiment.evaluation import evaluate
    if baselines and find_spec("torch_geometric") is None:
        raise ModuleNotFoundError("Full baseline evaluation requires torch-geometric==2.6.1 (HyperSCI)")
    # The saved cache_dir may be an absolute training-server path.
    options.setdefault("cache_dir", str(CACHE_DIR / "evaluation"))
    return evaluate(checkpoint_path(checkpoint), output_dir, device=device,
                    baselines=baselines, **options)
