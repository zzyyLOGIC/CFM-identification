"""Optimize an explicitly identified majority-response score under its budget."""
from dataclasses import asdict
import math

import numpy as np

from .contracts import TaskSpec, EstimateBundle, PolicyResult
from .identification import replay_handoff

__all__ = ["optimize_offline"]


def optimize_offline(task: TaskSpec, estimates: EstimateBundle, *, budget=None,
                     budget_mode=None, method="greedy", criterion="center") -> PolicyResult:
    """Run greedy/reference greedy and independently evaluate the identified score.

    A scalar ATE, partial set or unidentified task cannot silently become a
    four-arm allocation objective. Such inputs produce an explicit abstention.
    """
    if estimates.task is not task:
        raise ValueError("Pass the same TaskSpec instance throughout the pipeline")
    budget = task.budget if budget is None else budget
    if budget is None:
        raise ValueError("An explicit policy budget is required")
    mode = task.budget_mode if budget_mode is None else budget_mode
    common = dict(estimates=estimates, objective=task.estimand, criterion=criterion,
                  method=method, budget=budget, budget_mode=mode)
    def abstain(reason):
        return PolicyResult(**common, feasible=False, abstain=True, stop_reason=reason)
    if estimates.kind == "unavailable":
        return abstain(estimates.note)
    if (task.estimand != "NETWORK_MAJORITY_RESPONSE_POLICY_SCORE" or estimates.status != "POINT"
            or estimates.kind != "response_surface" or criterion != "center"):
        return abstain("This optimizer requires an identified point majority-response score; "
                       "scalar, set-valued and robust objectives require a different policy contract")
    if estimates.population_support is not None and not estimates.population_support.all():
        return abstain("This greedy optimizer has no general population-support constraints")
    request = replay_handoff(estimates.identification)
    policy_class = request.program.policy_class
    if (budget, mode) != (policy_class.budget, policy_class.budget_mode):
        raise ValueError("Budget and mode must match the identified policy class")
    from ._internal.policy.types import PolicyProblem
    from ._internal.policy.optimizers import greedy, greedy_reference
    from ._internal.identification.majority_score import evaluate_score
    optimizers = {"greedy": greedy, "greedy_reference": greedy_reference}
    if method not in optimizers:
        raise ValueError("Supported methods are greedy and greedy_reference")
    result = optimizers[method](PolicyProblem(task.adjacency, estimates.center, budget, task.node_ids),
                                budget_mode=mode)
    final = evaluate_score(request.program, request.source_spec.network_exposure,
                           estimates.center, result.treatment)
    initial = evaluate_score(request.program, request.source_spec.network_exposure,
        estimates.center, np.zeros(task.n_nodes, dtype=int), require_feasible=False)
    if not (math.isclose(final["value"], result.final_value, rel_tol=1e-10, abs_tol=1e-10)
            and math.isclose(initial["value"], result.initial_value, rel_tol=1e-10, abs_tol=1e-10)):
        raise ValueError("Optimizer values disagree with the independently identified score formula")
    return PolicyResult(**common, feasible=True, allocation=result.treatment,
        predicted_value=result.final_value, initial_value=result.initial_value,
        stop_reason=result.stop_reason, trace=tuple(asdict(step) for step in result.trace),
        diagnostics={"score_verification": "independent_formula_matches",
                     "global_optimality_verified": False,
                     "actual_rollout_welfare": "outside_this_target"})
