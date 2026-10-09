"""Greedy heuristics and simple allocation baselines, independent of evaluation."""

import math

import numpy as np

from .exposure import degree, majority_exposure, majority_threshold, treated_neighbor_count
from .objective import majority_surrogate_value, marginal_gain_reference
from .types import BudgetMode, GreedyStep, PolicyProblem, PolicyResult, PolicyState
from .validation import (validate_candidate, validate_greedy_options, validate_problem,
                         validate_treatment)


def _scaled_difference(after: float, before: float, N: int) -> float:
    """Subtract before dividing to retain small contrasts on a common baseline."""
    difference = float(after) - float(before)
    if math.isfinite(difference):
        return difference / N
    # Opposite extreme signs can overflow subtraction even when /N is finite.
    return float(after) / N - float(before) / N


def _choose_candidate(gains: dict[int, float], tie_tolerance: float) -> tuple[int, float]:
    """Choose the smallest index within absolute tolerance of the actual max."""
    if not all(np.isfinite(gain) for gain in gains.values()):
        raise ValueError("marginal gains overflowed; rescale outcome units before optimization")
    best_gain = max(gains.values())
    node = min(node for node, gain in gains.items() if best_gain - gain <= tie_tolerance)
    return node, best_gain


def _result(problem: PolicyProblem, treatment: np.ndarray, trace: list[GreedyStep],
            initial_value: float, final_value: float, budget_mode: BudgetMode,
            stop_reason: str) -> PolicyResult:
    return PolicyResult(
        treatment=treatment.copy(), selected_nodes=tuple(item.selected_node for item in trace),
        initial_value=initial_value, final_value=final_value, budget=int(problem.budget),
        budget_used=int(np.sum(treatment)), budget_mode=budget_mode,
        trace=tuple(trace), stop_reason=stop_reason,
    )


def greedy_reference(problem: PolicyProblem, *, budget_mode: BudgetMode,
                     gain_tolerance: float = 1e-12, tie_tolerance: float = 1e-12) -> PolicyResult:
    """Simple correctness implementation: recompute every candidate objective.

    exact uses B additions even for negative gains; at_most stops if the maximum
    remaining candidate gain is <= gain_tolerance. Ties use absolute objective
    units and the smallest node index within tie_tolerance of the maximum.
    """
    validate_problem(problem)
    validate_greedy_options(budget_mode, gain_tolerance, tie_tolerance)
    N = problem.adjacency.shape[0]
    treatment = np.zeros(N, dtype=np.int64)
    initial_value = current_value = majority_surrogate_value(problem, treatment)
    trace: list[GreedyStep] = []
    stop_reason = "budget_reached"
    for step in range(1, int(problem.budget) + 1):
        gains = {
            int(node): marginal_gain_reference(problem, treatment, int(node))
            for node in np.flatnonzero(treatment == 0)
        }
        node, best_gain = _choose_candidate(gains, tie_tolerance)
        if budget_mode == "at_most" and best_gain <= gain_tolerance:
            stop_reason = "no_positive_single_node_gain"
            break
        old_exposure = majority_exposure(problem.adjacency, treatment)
        candidate = treatment.copy()
        candidate[node] = 1
        new_exposure = majority_exposure(problem.adjacency, candidate)
        # Independent contribution differences; do not use the optimized formula.
        own_gain = _scaled_difference(problem.mu[node, 1, new_exposure[node]],
                                      problem.mu[node, 0, old_exposure[node]], N)
        neighbor_gain = math.fsum(
            _scaled_difference(problem.mu[i, int(candidate[i]), new_exposure[i]],
                               problem.mu[i, int(treatment[i]), old_exposure[i]], N)
            for i in range(N) if i != node
        )
        after = majority_surrogate_value(problem, candidate)
        newly_high = tuple(int(i) for i in np.flatnonzero(new_exposure > old_exposure))
        trace.append(GreedyStep(step, node, own_gain, neighbor_gain,
                                own_gain + neighbor_gain, current_value, after, newly_high, step))
        treatment = candidate
        current_value = after
    return _result(problem, treatment, trace, initial_value, current_value, budget_mode, stop_reason)


def _gain_components(problem: PolicyProblem, state: PolicyState, node: int,
                     neighbors: np.ndarray, thresholds: np.ndarray
                     ) -> tuple[float, float, tuple[int, ...]]:
    """Local gain formula for this MVP's untreated candidate and 0 -> 1 move."""
    N = state.treatment.size
    exposure = int(state.exposure[node])
    own_gain = _scaled_difference(problem.mu[node, 1, exposure],
                                  problem.mu[node, 0, exposure], N)
    crossing = tuple(int(i) for i in neighbors
                     if state.treated_neighbor_count[i] == thresholds[i])
    neighbor_gain = math.fsum(
        _scaled_difference(problem.mu[i, int(state.treatment[i]), 1],
                           problem.mu[i, int(state.treatment[i]), 0], N)
        for i in crossing
    )
    return own_gain, neighbor_gain, crossing


def optimized_marginal_gain(problem: PolicyProblem, treatment: np.ndarray, node: int) -> float:
    """Evaluate the own + threshold-crossing neighbor formula, in objective units.

    This public helper validates and derives K/S from the supplied treatment.
    greedy() uses the same formula on its maintained state without recalculating
    K/S for every candidate. Already-treated candidates are rejected.
    """
    validate_problem(problem)
    validate_treatment(treatment, problem.adjacency.shape[0])
    validate_candidate(treatment, node)
    thresholds = majority_threshold(degree(problem.adjacency))
    counts = treated_neighbor_count(problem.adjacency, treatment)
    state = PolicyState(treatment, counts, (counts > thresholds).astype(np.int64))
    neighbors = np.flatnonzero(problem.adjacency[node])
    own_gain, neighbor_gain, _ = _gain_components(problem, state, node, neighbors, thresholds)
    gain = own_gain + neighbor_gain
    if not np.isfinite(gain):
        raise ValueError("marginal gain overflowed; rescale outcome units")
    return gain


def greedy(problem: PolicyProblem, *, budget_mode: BudgetMode,
           gain_tolerance: float = 1e-12, tie_tolerance: float = 1e-12) -> PolicyResult:
    """Greedy heuristic maintaining z, K, S, without candidate objective calls.

    Only the selected assignment's objective is recomputed once per step using
    the canonical objective function, to avoid accumulation drift in the trace.
    No monotonicity, submodularity, or global optimum is assumed.
    """
    validate_problem(problem)
    validate_greedy_options(budget_mode, gain_tolerance, tie_tolerance)
    N = problem.adjacency.shape[0]
    thresholds = majority_threshold(degree(problem.adjacency))
    neighbors = tuple(np.flatnonzero(problem.adjacency[node]) for node in range(N))
    state = PolicyState(np.zeros(N, dtype=np.int64), np.zeros(N, dtype=np.int64),
                        np.zeros(N, dtype=np.int64))
    initial_value = current_value = majority_surrogate_value(problem, state.treatment)
    trace: list[GreedyStep] = []
    stop_reason = "budget_reached"
    for step in range(1, int(problem.budget) + 1):
        components = {
            int(node): _gain_components(problem, state, int(node), neighbors[node], thresholds)
            for node in np.flatnonzero(state.treatment == 0)
        }
        gains = {node: own + neighbor for node, (own, neighbor, _) in components.items()}
        node, best_gain = _choose_candidate(gains, tie_tolerance)
        if budget_mode == "at_most" and best_gain <= gain_tolerance:
            stop_reason = "no_positive_single_node_gain"
            break
        own_gain, neighbor_gain, crossing = components[node]
        state.treatment[node] = 1
        state.treated_neighbor_count[neighbors[node]] += 1
        for i in crossing:
            state.exposure[i] = 1
        after = majority_surrogate_value(problem, state.treatment)
        trace.append(GreedyStep(step, node, own_gain, neighbor_gain,
                                own_gain + neighbor_gain, current_value, after, crossing, step))
        current_value = after
    return _result(problem, state.treatment, trace, initial_value, current_value, budget_mode, stop_reason)


def no_treatment(problem: PolicyProblem) -> np.ndarray:
    """All-zero descriptive baseline, potentially infeasible for an exact B > 0."""
    validate_problem(problem)
    return np.zeros(problem.adjacency.shape[0], dtype=np.int64)


def random_allocation(problem: PolicyProblem, *, seed: int) -> np.ndarray:
    """Select exactly B nodes uniformly without replacement with a local RNG."""
    validate_problem(problem)
    if isinstance(seed, (bool, np.bool_)) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    treatment = no_treatment(problem)
    treatment[np.random.default_rng(seed).choice(treatment.size, size=problem.budget, replace=False)] = 1
    return treatment


def _topk(problem: PolicyProblem, scores: np.ndarray) -> np.ndarray:
    treatment = no_treatment(problem)
    order = sorted(range(treatment.size), key=lambda i: (-float(scores[i]), i))
    treatment[order[:problem.budget]] = 1
    return treatment


def degree_topk(problem: PolicyProblem) -> np.ndarray:
    """Degree Top-B with smallest-index tie breaking."""
    validate_problem(problem)
    return _topk(problem, degree(problem.adjacency))


def direct_effect_topk(problem: PolicyProblem) -> np.ndarray:
    """Top-B by mu[i,1,0] - mu[i,0,0]; this ignores network exposure changes."""
    validate_problem(problem)
    scores = problem.mu[:, 1, 0].astype(float) - problem.mu[:, 0, 0].astype(float)
    if not np.all(np.isfinite(scores)):
        raise ValueError("direct effect scores overflowed; rescale outcome units")
    return _topk(problem, scores)
