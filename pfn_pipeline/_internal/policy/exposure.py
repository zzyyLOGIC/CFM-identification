"""Pure network exposure mathematics; this module never accesses outcomes."""

import numpy as np

from .validation import validate_adjacency, validate_treatment


def degree(adjacency: np.ndarray) -> np.ndarray:
    """Return d_i = sum_j A_ij as integer counts."""
    validate_adjacency(adjacency)
    return np.sum(adjacency, axis=1, dtype=np.int64)


def majority_threshold(degree: np.ndarray) -> np.ndarray:
    """Return floor(d_i / 2); isolated nodes have no definition in this MVP."""
    if (not isinstance(degree, np.ndarray) or degree.ndim != 1 or degree.size == 0
            or degree.dtype.kind not in "iuf"):
        raise ValueError("degree must be a nonempty one-dimensional real numeric array")
    if (not np.all(np.isfinite(degree)) or np.any(degree < 1)
            or np.any(degree >= 2**63) or np.any(degree != np.floor(degree))):
        raise ValueError("degree must contain finite positive integer counts; no isolated nodes")
    return np.floor_divide(degree, 2).astype(np.int64)


def treated_neighbor_count(adjacency: np.ndarray, treatment: np.ndarray) -> np.ndarray:
    """Return K(z) = A @ z; use int64 to avoid bool/uint8 dot-product errors."""
    validate_adjacency(adjacency)
    validate_treatment(treatment, adjacency.shape[0])
    return adjacency.astype(np.int64) @ treatment.astype(np.int64)


def majority_exposure(adjacency: np.ndarray, treatment: np.ndarray) -> np.ndarray:
    """Return S_i(z) = 1{K_i(z) > floor(d_i/2)} (strict majority)."""
    counts = treated_neighbor_count(adjacency, treatment)
    thresholds = majority_threshold(degree(adjacency))
    return (counts > thresholds).astype(np.int64)
