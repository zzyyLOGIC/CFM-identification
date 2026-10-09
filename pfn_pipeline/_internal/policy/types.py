"""Fixed data contracts. No algorithms or estimation-specific state live here."""

from dataclasses import dataclass
from typing import Literal

import numpy as np

BudgetMode = Literal["exact", "at_most"]


@dataclass(frozen=True)
class PolicyProblem:
    """Inputs (A, mu, B), with mu indexed strictly as mu[node, treatment, exposure].

    Frozen fields do not make the NumPy buffers immutable. Public algorithms never
    mutate them; callers must not change inputs during an optimization call.
    """

    adjacency: np.ndarray
    mu: np.ndarray
    budget: int
    node_ids: tuple[str, ...] | None = None


@dataclass
class PolicyState:
    """Internal dynamic state z, K(z), S(z) for treatment additions."""

    treatment: np.ndarray
    treated_neighbor_count: np.ndarray
    exposure: np.ndarray


@dataclass(frozen=True)
class GreedyStep:
    """One accepted move; all gains are in mean-objective units (divided by N)."""

    step: int
    selected_node: int
    own_gain: float
    neighbor_gain: float
    marginal_gain: float
    objective_before: float
    objective_after: float
    newly_high_exposure_nodes: tuple[int, ...]
    treatment_count: int


@dataclass(frozen=True)
class PolicyResult:
    """A greedy heuristic solution, without a global optimality certificate."""

    treatment: np.ndarray
    selected_nodes: tuple[int, ...]
    initial_value: float
    final_value: float
    budget: int
    budget_used: int
    budget_mode: BudgetMode
    trace: tuple[GreedyStep, ...]
    stop_reason: str

    @property
    def objective_gain(self) -> float:
        return self.final_value - self.initial_value


@dataclass(frozen=True)
class AssignmentEvaluation:
    """Descriptive statistics for a given assignment, without ground truth."""

    objective_value: float
    treated_count: int
    treated_fraction: float
    high_exposure_count: int
    high_exposure_fraction: float

