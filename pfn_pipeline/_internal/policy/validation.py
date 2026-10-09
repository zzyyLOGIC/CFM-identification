"""Central validation for public policy inputs."""

from numbers import Integral, Real

import numpy as np

from .types import PolicyProblem


def _real_array(value: np.ndarray, name: str, *, allow_bool: bool = False) -> None:
    if not isinstance(value, np.ndarray):
        raise ValueError(f"{name} must be a NumPy array")
    numeric = value.dtype.kind in "iuf"
    boolean = allow_bool and value.dtype.kind == "b"
    if not (numeric or boolean):
        raise ValueError(f"{name} must contain real numeric values")
    if not np.all(np.isfinite(value)):
        raise ValueError(f"{name} must contain only finite values (no NaN or Inf)")


def validate_adjacency(adjacency: np.ndarray) -> None:
    """Require a nonempty, binary, undirected graph without loops or isolates."""
    _real_array(adjacency, "adjacency", allow_bool=True)
    if adjacency.ndim != 2 or adjacency.shape[0] != adjacency.shape[1]:
        raise ValueError("adjacency must be a square two-dimensional array")
    if adjacency.shape[0] < 1:
        raise ValueError("adjacency must have N >= 1")
    if not np.all((adjacency == 0) | (adjacency == 1)):
        raise ValueError("adjacency must be binary (0 or 1)")
    if not np.array_equal(adjacency, adjacency.T):
        raise ValueError("adjacency must be symmetric (undirected)")
    if np.any(np.diag(adjacency) != 0):
        raise ValueError("adjacency diagonal must be zero (no self-loop)")
    if np.any(np.sum(adjacency, axis=1, dtype=np.int64) == 0):
        raise ValueError("adjacency contains isolated nodes; degree must be >= 1")


def validate_mu(mu: np.ndarray, N: int) -> None:
    """Require all four finite real outcomes with explicit [node, t, s] axes."""
    _real_array(mu, "mu")
    if mu.shape != (N, 2, 2):
        raise ValueError(f"mu must have shape ({N}, 2, 2), with axes [node, treatment, exposure]")


def validate_node_ids(node_ids: tuple[str, ...] | None, N: int) -> None:
    if node_ids is None:
        return
    if not isinstance(node_ids, tuple) or not all(isinstance(item, str) for item in node_ids):
        raise ValueError("node_ids must be a tuple of strings or None")
    if len(node_ids) != N:
        raise ValueError(f"node_ids length must equal N={N}")
    if len(set(node_ids)) != N:
        raise ValueError("node_ids must be unique; duplicate node_ids are not allowed")


def validate_problem(problem: PolicyProblem) -> None:
    """Fail early on an invalid graph, outcome tensor, budget, or node ordering."""
    if not isinstance(problem, PolicyProblem):
        raise ValueError("problem must be a PolicyProblem")
    validate_adjacency(problem.adjacency)
    N = problem.adjacency.shape[0]
    validate_mu(problem.mu, N)
    if isinstance(problem.budget, (bool, np.bool_)) or not isinstance(problem.budget, Integral):
        raise ValueError("budget must be an integer; bool and float budgets are invalid")
    if not 0 <= problem.budget <= N:
        raise ValueError(f"budget must satisfy 0 <= budget <= N={N}")
    validate_node_ids(problem.node_ids, N)


def validate_treatment(treatment: np.ndarray, N: int) -> None:
    """Accept only an (N,) vector of finite, integer-compatible binary values."""
    if isinstance(N, (bool, np.bool_)) or not isinstance(N, Integral) or N < 1:
        raise ValueError("N must be a positive integer")
    _real_array(treatment, "treatment", allow_bool=True)
    if treatment.shape != (N,):
        raise ValueError(f"treatment must have shape ({N},)")
    if not np.all((treatment == 0) | (treatment == 1)):
        raise ValueError("treatment must be binary and integer-compatible (0 or 1)")


def validate_candidate(treatment: np.ndarray, node: int) -> None:
    if isinstance(node, (bool, np.bool_)) or not isinstance(node, Integral):
        raise ValueError("node must be an integer index")
    if not 0 <= node < treatment.size:
        raise ValueError("node index is out of range")
    if treatment[node] == 1:
        raise ValueError(f"node {node} is already treated")


def validate_greedy_options(budget_mode: str, gain_tolerance: float, tie_tolerance: float) -> None:
    if budget_mode not in ("exact", "at_most"):
        raise ValueError("budget_mode must be 'exact' or 'at_most'")
    for name, value in (("gain_tolerance", gain_tolerance), ("tie_tolerance", tie_tolerance)):
        if (isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
                or not np.isfinite(value) or value < 0):
            raise ValueError(f"{name} must be a finite nonnegative real number")
