"""The single source of truth for the majority-surrogate objective."""

import math

import numpy as np

from .exposure import majority_exposure
from .types import PolicyProblem
from .validation import validate_candidate, validate_problem, validate_treatment


def majority_surrogate_value(problem: PolicyProblem, treatment: np.ndarray) -> float:
    """Compute mean_i mu[i, z_i, S_i(z)] using all four outcome states.

    This is an estimated majority-arm surrogate, not true policy welfare.
    Scaling each contribution before summation avoids overflowing a finite mean.
    """
    validate_problem(problem)
    N = problem.adjacency.shape[0]
    validate_treatment(treatment, N)
    exposure = majority_exposure(problem.adjacency, treatment)
    contributions = [
        float(problem.mu[i, int(treatment[i]), int(exposure[i])]) / N
        for i in range(N)
    ]
    return float(math.fsum(contributions))


def marginal_gain_reference(problem: PolicyProblem, treatment: np.ndarray, node: int) -> float:
    """Correctness oracle: fully recompute V(z + e_node) - V(z)."""
    validate_problem(problem)
    validate_treatment(treatment, problem.adjacency.shape[0])
    validate_candidate(treatment, node)
    candidate = treatment.copy()
    candidate[node] = 1
    return majority_surrogate_value(problem, candidate) - majority_surrogate_value(problem, treatment)

