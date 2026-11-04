"""Task 06 only: D2 complete randomization + E3 core-partner majority.

Exact, graph-size-independent population support.  This module deliberately
uses neither observed outcomes nor simulation ground truth and has no PFN /
Estimation / Policy dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import comb
from numbers import Integral
from typing import Mapping, Sequence


def _integer(value: object, name: str, *, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    result = int(value)
    if not low <= result <= high:
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    return result


def _choose(n: int, k: int) -> int:
    """Binomial coefficient, zero outside the combinatorially valid range."""
    return comb(n, k) if 0 <= k <= n else 0


@dataclass(frozen=True)
class Task06Setting:
    """Validated fixed undirected graph, pretreatment core sets, and D2 quota.

    Node labels in this standalone task are integer indices 0,...,N-1,
    matching positions in the adjacency matrix.  `core_partners[i]` is a
    nonempty subset of node i's neighbors and is fixed before randomization.
    """

    adjacency: tuple[tuple[int, ...], ...]
    core_partners: tuple[tuple[int, ...], ...]
    m: int

    @property
    def n(self) -> int:
        return len(self.adjacency)

    @classmethod
    def create(
        cls,
        adjacency: Sequence[Sequence[int]],
        core_partners: Mapping[int, Sequence[int]] | Sequence[Sequence[int]],
        m: int,
    ) -> Task06Setting:
        try:
            n = len(adjacency)
        except TypeError as exc:
            raise ValueError("adjacency must be an N x N matrix") from exc
        if n < 2:
            raise ValueError("N must be >= 2 because every C_i must be nonempty")
        matrix: list[tuple[int, ...]] = []
        for i, row in enumerate(adjacency):
            if len(row) != n:
                raise ValueError(f"adjacency row {i} has length {len(row)}; expected {n}")
            current: list[int] = []
            for j, x in enumerate(row):
                if x not in (0, 1):
                    raise ValueError("adjacency must have binary entries (0 or 1)")
                current.append(int(x))
                if i == j and x != 0:
                    raise ValueError("self-loops are not allowed")
            matrix.append(tuple(current))
        for i in range(n):
            for j in range(i + 1, n):
                if matrix[i][j] != matrix[j][i]:
                    raise ValueError("adjacency must be symmetric (undirected graph)")

        quota = _integer(m, "m", low=0, high=n)
        if isinstance(core_partners, Mapping):
            if set(core_partners) != set(range(n)):
                raise ValueError("core_partners must define C_i for every node 0..N-1")
            core_rows = [core_partners[i] for i in range(n)]
        else:
            if len(core_partners) != n:
                raise ValueError("core_partners must define C_i for every node")
            core_rows = list(core_partners)

        core: list[tuple[int, ...]] = []
        for i, neighbors in enumerate(core_rows):
            if isinstance(neighbors, (str, bytes)):
                raise ValueError(f"C_{i} must be a sequence of node indices")
            try:
                raw = list(neighbors)
            except TypeError as exc:
                raise ValueError(f"C_{i} must be a sequence of node indices") from exc
            if not raw:
                raise ValueError(f"C_{i} must be nonempty (E3 requires h_i>0)")
            cleaned = [_integer(j, f"core partner of node {i}", low=0, high=n-1)
                       for j in raw]
            if len(set(cleaned)) != len(cleaned):
                raise ValueError(f"C_{i} contains duplicate partners")
            for j in cleaned:
                if j == i or matrix[i][j] != 1:
                    raise ValueError(f"C_{i} must be a subset of node {i}'s pretreatment neighbors")
            core.append(tuple(sorted(cleaned)))
        return cls(adjacency=tuple(matrix), core_partners=tuple(core), m=quota)


def joint_arm_probability(n: int, m: int, h: int, t: int, s: int) -> Fraction:
    """Exact pi_i(t,s), using only N, m, h_i under uniform complete randomization.

    Number of legal allocations with (T_i=t,K_i=k):
        C(h,k) C(N-1-h, m-t-k).
    Every one of the C(N,m) legal allocations is equally likely.
    """
    n = _integer(n, "N", low=2, high=10**9)
    m = _integer(m, "m", low=0, high=n)
    h = _integer(h, "h", low=1, high=n - 1)
    t = _integer(t, "t", low=0, high=1)
    s = _integer(s, "s", low=0, high=1)
    threshold = h // 2
    valid_ks = range(0, threshold + 1) if s == 0 else range(threshold + 1, h + 1)
    total = sum(_choose(h, k) * _choose(n - 1 - h, m - t - k)
                for k in valid_ks)
    return Fraction(total, comb(n, m))


def positive_support_from_bounds(n: int, m: int, h: int, t: int, s: int) -> bool:
    """Independent closed-form positivity check (no probability summation).

    Let R=m-t, L=N-1-h, b=floor(h/2), a=b+1.
    S=0 iff max(0,R-L) <= b, provided 0 <= R <= N-1.
    S=1 iff min(h,R) >= a, provided 0 <= R <= N-1.
    """
    n = _integer(n, "N", low=2, high=10**9)
    m = _integer(m, "m", low=0, high=n)
    h = _integer(h, "h", low=1, high=n - 1)
    t = _integer(t, "t", low=0, high=1)
    s = _integer(s, "s", low=0, high=1)
    r = m - t
    if not 0 <= r <= n - 1:
        return False
    if s == 0:
        return r <= n - 1 - (h + 1) // 2
    return r >= h // 2 + 1


def support_for_node(setting: Task06Setting, node: int) -> dict[tuple[int, int], Fraction]:
    """Return four exact joint probabilities keyed by (own treatment, exposure)."""
    i = _integer(node, "node", low=0, high=setting.n-1)
    h = len(setting.core_partners[i])
    result = {(t, s): joint_arm_probability(setting.n, setting.m, h, t, s)
              for t in (0, 1) for s in (0, 1)}
    for (t, s), probability in result.items():
        assert (probability > 0) == positive_support_from_bounds(
            setting.n, setting.m, h, t, s
        ), "support formula and independent feasibility bound disagree"
    assert sum(result.values(), Fraction(0)) == 1
    return result


def support_probabilities(
    adjacency: Sequence[Sequence[int]],
    core_partners: Mapping[int, Sequence[int]] | Sequence[Sequence[int]],
    m: int,
) -> dict[int, dict[tuple[int, int], Fraction]]:
    """Validate setting; return pi_i(t,s) for every node and each of four arms."""
    setting = Task06Setting.create(adjacency, core_partners, m)
    return {i: support_for_node(setting, i) for i in range(setting.n)}
