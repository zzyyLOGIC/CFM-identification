"""Describe given assignments. Objective mathematics lives in objective.py."""

from collections.abc import Mapping

import numpy as np

from .exposure import majority_exposure
from .objective import majority_surrogate_value
from .types import AssignmentEvaluation, PolicyProblem


def evaluate_assignment(problem: PolicyProblem, treatment: np.ndarray) -> AssignmentEvaluation:
    """Describe an assignment without enforcing budget feasibility.

    This intentionally supports the No Treatment comparator under exact B > 0.
    The objective function validates the graph, outcomes, and assignment first.
    """
    value = majority_surrogate_value(problem, treatment)
    N = problem.adjacency.shape[0]
    treated_count = int(np.sum(treatment, dtype=np.int64))
    high_count = int(np.sum(majority_exposure(problem.adjacency, treatment)))
    return AssignmentEvaluation(value, treated_count, treated_count / N, high_count, high_count / N)


def compare_assignments(problem: PolicyProblem, assignments: Mapping[str, np.ndarray]
                        ) -> dict[str, AssignmentEvaluation]:
    """Evaluate every named assignment against the same surrogate objective."""
    return {name: evaluate_assignment(problem, treatment) for name, treatment in assignments.items()}

