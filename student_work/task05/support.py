"""Exact D2 x E2 population support; no outcomes or fitted models are used.

Input: a nonempty, symmetric binary adjacency matrix without self-loops,
and an integer quota 0 <= m <= N. Node IDs are row indices.
Output: one {(t, s): Fraction} table per node; None denotes an isolate,
whose fraction-based exposure is undefined (not a zero-probability arm).
"""
from fractions import Fraction
from math import comb
from numbers import Integral


def integer(value, name, lower, upper):
    """Validate integer inputs before conversion; reject floats and bools."""
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer, not a bool or float")
    value = int(value)
    if not lower <= value <= upper:
        raise ValueError(f"{name} must be between {lower} and {upper}")
    return value


def validate_design(adjacency, m):
    """Copy/validate a simple undirected graph and its complete-randomization quota."""
    try:
        rows = tuple(tuple(row) for row in adjacency)
    except TypeError as exc:
        raise ValueError("adjacency must be a square matrix") from exc
    n = len(rows)
    if not n or any(len(row) != n for row in rows):
        raise ValueError("adjacency must be nonempty and square")
    if any(not isinstance(x, Integral) or x not in (0, 1) for row in rows for x in row):
        raise ValueError("adjacency must contain integer 0/1 entries")
    graph = tuple(tuple(int(x) for x in row) for row in rows)
    if any(graph[i][i] for i in range(n)):
        raise ValueError("self-loops are not supported")
    if any(graph[i][j] != graph[j][i] for i in range(n) for j in range(i)):
        raise ValueError("adjacency must be symmetric")
    return graph, integer(m, "m", 0, n)


def exposure_state(k, degree):
    """E2 uses [0,1/3), [1/3,2/3), [2/3,1]; integer comparisons are exact."""
    if isinstance(degree, bool) or not isinstance(degree, Integral) or degree < 1:
        raise ValueError("E2 is undefined for degree zero; degree must be a positive integer")
    degree = int(degree)
    k = integer(k, "k", 0, degree)
    return 0 if 3 * k < degree else (1 if 3 * k < 2 * degree else 2)


def support_by_degree(n, m, degree):
    """Count full assignments, preserving dependence between own and others' T.

    pi(t,s) = sum_{k in bin_s} C(d,k) C(N-1-d,m-t-k) / C(N,m).
    Feasible k bounds avoid invalid binomial coefficients, including m=0,N.
    """
    if isinstance(n, bool) or not isinstance(n, Integral) or n < 1:
        raise ValueError("n must be a positive integer")
    n = int(n)
    m = integer(m, "m", 0, n)
    degree = integer(degree, "degree", 0, n - 1)
    if degree == 0:
        return None
    counts = {(t, s): 0 for t in (0, 1) for s in (0, 1, 2)}
    outside = n - 1 - degree
    for t in (0, 1):
        lower = max(0, m - t - outside)
        upper = min(degree, m - t)
        for k in range(lower, upper + 1):
            counts[t, exposure_state(k, degree)] += comb(degree, k) * comb(outside, m - t - k)
    total = comb(n, m)
    return {arm: Fraction(count, total) for arm, count in counts.items()}


def compute_support(adjacency, m):
    """Return all six exact joint probabilities per nonisolated node.

    Under uniform complete randomization, support depends on N,m,d_i.
    Computing a table once per distinct degree is sufficient; each returned
    table is copied so callers cannot mutate another node's table.
    """
    graph, m = validate_design(adjacency, m)
    degrees = tuple(map(sum, graph))
    tables = {d: support_by_degree(len(graph), m, d) for d in set(degrees)}
    return {i: None if tables[d] is None else dict(tables[d]) for i, d in enumerate(degrees)}
