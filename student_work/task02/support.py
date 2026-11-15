"""Task 02 support: D1 (heterogeneous independent Bernoulli) x E2 (three-level exposure).

Only the design law is implemented here. No outcome data, no simulator truth and no Estimation or
Policy code is used or read.

    D1  T_i ~ Bernoulli(p_i), independent across units, 0 < p_i < 1, p_i known pretreatment
    E2  E_i = K_i / d_i with three levels: low (< 1/3) / medium ([1/3, 2/3)) / high (>= 2/3)

Computed quantity:  pi_i(t, s) = P( T_i = t, S_i = s | A, X ),  t in {0, 1}, s in {0, 1, 2}.

Two facts used throughout (both specific to D1):
  * T_i is independent of every T_j with j != i, and i is never its own neighbour, so
        pi_i(t, s) = P(T_i = t) * P(S_i = s);
  * K_i = sum_{j in N(i)} T_j is a sum of d_i independent Bernoulli variables with *different*
    probabilities -> Poisson-binomial, not binomial. Since 0 < p_j < 1 it puts positive mass on
    every k in {0, ..., d_i}, hence  pi_i(t, s) > 0  <=>  the interval of level s is non-empty.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np


class InvalidDesignError(ValueError):
    """Assignment parameters violate D1 (need 0 < p_i < 1) or the query is malformed."""


class UndefinedExposureError(ValueError):
    """E2 needs d_i >= 1; the treated-neighbour fraction is not defined for an isolated unit."""


# E2 exposure rule

E2_LOW, E2_MEDIUM, E2_HIGH = 0, 1, 2
E2_LEVELS = (E2_LOW, E2_MEDIUM, E2_HIGH)


def e2_thresholds(d):
    """(k1, k2) = (ceil(d/3), ceil(2d/3)): the two integer cut points behind E2."""
    if d < 1:
        raise UndefinedExposureError(f"E2 requires d_i >= 1, got d_i = {d}.")
    return math.ceil(d / 3), math.ceil(2 * d / 3)


def e2_integer_ranges(d):
    """Map each level to its inclusive K_i interval; ``hi < lo`` means that level is unreachable."""
    k1, k2 = e2_thresholds(d)
    return {E2_LOW: (0, k1 - 1), E2_MEDIUM: (k1, k2 - 1), E2_HIGH: (k2, d)}


def e2_state(k, d):
    """Forward E2 rule: level of a unit with k treated neighbours out of d."""
    k1, k2 = e2_thresholds(d)
    if not 0 <= k <= d:
        raise InvalidDesignError(f"K_i must lie in [0, {d}], got {k}.")
    return E2_LOW if k < k1 else (E2_MEDIUM if k < k2 else E2_HIGH)


# Poisson-binomial law of K_i


def poisson_binomial_pmf(ps):
    """Exact PMF of a sum of independent Bernoulli(ps) variables; entry k is P(sum = k)."""
    ps = np.asarray(list(ps), dtype=float)
    if ps.size and not np.all((ps > 0.0) & (ps < 1.0)):
        raise InvalidDesignError("Bernoulli probabilities must all lie strictly in (0, 1).")
    pmf = np.zeros(ps.size + 1)
    pmf[0] = 1.0
    for m, p in enumerate(ps, start=1):                      # O(d^2) dynamic program
        pmf[1:m + 1] = pmf[1:m + 1] * (1.0 - p) + pmf[:m] * p
        pmf[0] *= 1.0 - p
    return pmf


# Graph helpers


def _adjacency(adj):
    matrix = np.asarray(adj, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise InvalidDesignError("adjacency must be a square matrix.")
    return matrix


def neighbours(adj, i):
    """N(i), the neighbours of unit i."""
    return np.flatnonzero(_adjacency(adj)[i] != 0)


def degree(adj, i):
    """d_i = |N(i)|."""
    return int(neighbours(adj, i).size)


def validate_probabilities(ps, n_units):
    """Check the D1 vector: length n_units, finite, and 0 < p_i < 1 for every unit."""
    ps = np.asarray(ps, dtype=float).reshape(-1)
    if ps.size != n_units:
        raise InvalidDesignError(f"p must have length {n_units}, got {ps.size}.")
    if not np.all(np.isfinite(ps)) or not np.all((ps > 0.0) & (ps < 1.0)):
        raise InvalidDesignError("D1 requires 0 < p_i < 1 for every unit.")
    return ps


def load_fixed_er_adjacency(path):
    """Read the shared fixed ER record (upper triangle packed as ``upper_hex``) into adjacency."""
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    n_units = int(record["n_units"])
    count = n_units * (n_units - 1) // 2
    packed = bytes.fromhex(record["upper_hex"])
    if len(packed) != (count + 7) // 8:
        raise InvalidDesignError("fixed-graph hex length does not match n_units.")
    bits = np.unpackbits(np.frombuffer(packed, dtype=np.uint8))[:count]
    adjacency = np.zeros((n_units, n_units), dtype=np.int8)
    adjacency[np.triu_indices(n_units, k=1)] = bits
    return adjacency + adjacency.T

# Query-specific population support for Task 02


def support_D1_E2(adj, ps, i):
    """pi_i(t, s) for the six arms of unit i.

    All six keys ``(t, s)`` are always returned, including the ones whose value is exactly 0.0.
    Raises ``UndefinedExposureError`` when d_i == 0 (E2 has no meaning for an isolated unit).
    """
    ps = validate_probabilities(ps, _adjacency(adj).shape[0])
    nbrs = neighbours(adj, i)
    d = int(nbrs.size)
    if d == 0:
        raise UndefinedExposureError(f"unit {i} is isolated (d_i = 0); E2 is not defined for it.")

    pmf = poisson_binomial_pmf(ps[nbrs])                     # only neighbours' p_j enter
    support = {}
    for t in (0, 1):
        own = float(ps[i]) if t == 1 else 1.0 - float(ps[i])  # own p_i enters only here
        for s, (lo, hi) in e2_integer_ranges(d).items():
            support[(t, s)] = own * (float(pmf[lo:hi + 1].sum()) if hi >= lo else 0.0)
    return support
