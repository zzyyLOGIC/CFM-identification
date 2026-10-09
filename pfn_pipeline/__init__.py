"""Unified research pipeline; heavy backends are imported only when requested.

Typical use::

    model = load_checkpoint()
    task, reference = simulate_task(adjacency=load_graph(model.graph_record),
                                    return_reference=True)
    identified = identify(task)
    estimates = estimate_effects(task, identified, model)
    allocation = optimize_offline(task, estimates)
    metrics = evaluate_estimates(estimates, reference)

The imported ER demo checkpoint supports inference. Its training prior differs
from this simulation, so these metrics are a cross-prior functional check.
The causalPFN baseline and legacy weights cannot substitute for it.
"""
from importlib import import_module

from .contracts import TaskSpec, IdentificationResult, EstimateBundle, PolicyResult

_EXPORTS = {
    "identify": "identification", "replay_handoff": "identification",
    "PFNModel": "pfn", "build_model": "pfn", "load_checkpoint": "pfn",
    "train_model": "pfn", "predict": "pfn", "estimate_effects": "estimation",
    "optimize_offline": "policy", "simulate_task": "simulation", "load_graph": "simulation",
    "effect_table": "evaluation", "evaluate_estimates": "evaluation",
    "evaluate_policy": "evaluation", "evaluate_checkpoint": "evaluation",
    "plot_response_surface": "visualization", "plot_effects": "visualization",
    "plot_policy": "visualization",
}
__all__ = ["TaskSpec", "IdentificationResult", "EstimateBundle", "PolicyResult", *_EXPORTS]


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{_EXPORTS[name]}", __name__), name)
    globals()[name] = value
    return value
