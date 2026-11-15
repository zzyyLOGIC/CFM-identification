"""Tests for Task 02 (D1 x E2): population support, POINT functional and refusal behaviour.

Run from the repository root:

    python -B tools/run_student_tests.py
    python -B -m pytest -q student_work/task02/test_rule.py

Covers the three required cases -- a normal case, a zero-support / invalid-parameter case and an
n <= 8 brute-force oracle -- plus the E2 interval table, the Poisson-binomial dynamic program and
the assumption gate of ``rule.py``.
"""

from __future__ import annotations

import math
import sys
from itertools import product
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rule as rl
import support as sp


# helpers


def er_adjacency(n, edge_probability, seed):
    """Small Erdos-Renyi adjacency matrix, drawn once and then frozen."""
    rng = np.random.default_rng(seed)
    upper = np.triu(rng.random((n, n)) < edge_probability, k=1)
    return (upper | upper.T).astype(np.int8)


def path_adjacency(n):
    """Path graph 0 - 1 - ... - (n-1): both end units have degree 1."""
    adjacency = np.zeros((n, n), dtype=np.int8)
    for i in range(n - 1):
        adjacency[i, i + 1] = adjacency[i + 1, i] = 1
    return adjacency


def random_ps(n, seed):
    return np.random.default_rng(seed).uniform(0.2, 0.8, size=n)


def brute_force_support(adj, ps, i, t, s):
    """Enumerate all 2^n assignments and count P(T_i = t, S_i = s) exactly."""
    n = len(adj)
    nbrs = [j for j in range(n) if adj[i][j]]
    if not nbrs:
        raise sp.UndefinedExposureError("isolated unit")
    total = 0.0
    for assignment in product((0, 1), repeat=n):
        if assignment[i] != t:
            continue
        weight = 1.0
        for j in range(n):
            weight *= ps[j] if assignment[j] == 1 else (1.0 - ps[j])
        if sp.e2_state(sum(assignment[j] for j in nbrs), len(nbrs)) == s:
            total += weight
    return total


# 1. E2: real cut points -> integer intervals


@pytest.mark.parametrize(
    "d, expected",
    [
        (1, {0: (0, 0), 1: (1, 0), 2: (1, 1)}),
        (2, {0: (0, 0), 1: (1, 1), 2: (2, 2)}),
        (3, {0: (0, 0), 1: (1, 1), 2: (2, 3)}),
        (4, {0: (0, 1), 1: (2, 2), 2: (3, 4)}),
        (6, {0: (0, 1), 1: (2, 3), 2: (4, 6)}),
    ],
)
def test_e2_integer_ranges_table(d, expected):
    assert sp.e2_integer_ranges(d) == expected


@pytest.mark.parametrize("d", range(1, 13))
def test_e2_state_agrees_with_integer_ranges(d):
    ranges = sp.e2_integer_ranges(d)
    for k in range(d + 1):
        lo, hi = ranges[sp.e2_state(k, d)]
        assert lo <= k <= hi, (d, k)


def test_degree_one_has_no_medium_level():
    lo, hi = sp.e2_integer_ranges(1)[sp.E2_MEDIUM]
    assert hi < lo, "for d_i = 1 the medium interval must be empty"


# 2. Poisson-binomial dynamic program


@pytest.mark.parametrize("p", [0.25, 0.5, 0.8])
@pytest.mark.parametrize("m", [2, 5])
def test_poisson_binomial_equals_binomial(p, m):
    pmf = sp.poisson_binomial_pmf([p] * m)
    exact = np.array([math.comb(m, k) * p**k * (1 - p) ** (m - k) for k in range(m + 1)])
    assert np.allclose(pmf, exact, atol=1e-12)


def test_poisson_binomial_matches_subset_enumeration():
    ps = [0.3, 0.45, 0.8, 0.15]
    pmf = sp.poisson_binomial_pmf(ps)
    from itertools import combinations

    for k in range(len(ps) + 1):
        exact = 0.0
        for index in combinations(range(len(ps)), k):
            probability = 1.0
            for j, p in enumerate(ps):
                probability *= p if j in index else 1.0 - p
            exact += probability
        assert abs(pmf[k] - exact) < 1e-12


# 3. Normal case: every arm of a unit with d_i >= 2 is supported


def test_support_sums_to_one_and_factorises():
    adjacency = er_adjacency(30, 0.25, seed=7)
    ps = random_ps(30, seed=11)
    for i in range(30):
        pi = sp.support_D1_E2(adjacency, ps, i)
        assert set(pi) == {(t, s) for t in (0, 1) for s in sp.E2_LEVELS}
        assert abs(sum(pi.values()) - 1.0) < 1e-12
        own = {t: ps[i] if t == 1 else 1.0 - ps[i] for t in (0, 1)}
        for (t, s), value in pi.items():
            assert pi[(1 - t, s)] == pytest.approx(value * own[1 - t] / own[t])


def test_all_six_arms_supported_when_degree_at_least_two():
    adjacency = er_adjacency(40, 0.3, seed=3)
    ps = random_ps(40, seed=5)
    checked = 0
    for i in range(40):
        if sp.degree(adjacency, i) < 2:
            continue
        assert all(value > 0.0 for value in sp.support_D1_E2(adjacency, ps, i).values())
        result = rl.identify_all_arms(adjacency, ps, i)
        assert result.status == "COMPLETE"
        assert len(result.supported_arms) == 6 and not result.refused_arms
        for arm in result.supported_arms:
            assert arm.functional == rl.POINT_FUNCTIONAL_TEMPLATE
        checked += 1
    assert checked > 20


# 4. Zero-support case: a degree-1 unit has no medium exposure


def test_degree_one_unit_has_zero_support_for_medium_arms():
    adjacency = path_adjacency(6)
    ps = random_ps(6, seed=31)
    assert sp.degree(adjacency, 0) == 1

    pi = sp.support_D1_E2(adjacency, ps, 0)
    assert pi[(0, 1)] == 0.0 and pi[(1, 1)] == 0.0
    for t in (0, 1):
        for s in (0, 2):
            assert pi[(t, s)] > 0.0
    assert abs(sum(pi.values()) - 1.0) < 1e-12

    result = rl.identify_all_arms(adjacency, ps, 0)
    assert result.status == "COMPLETE"
    assert len(result.supported_arms) == 4 and len(result.refused_arms) == 2
    assert {(a.treatment, a.exposure) for a in result.refused_arms} == {(0, 1), (1, 1)}


def test_zero_support_is_refused_and_never_returns_a_value():
    adjacency = path_adjacency(5)
    ps = random_ps(5, seed=41)
    with pytest.raises(rl.ZeroSupportRefusal) as error:
        rl.identify_arm(adjacency, ps, 0, 1, 1)
    assert "zero probability" in str(error.value)

    arm = rl.try_identify_arm(adjacency, ps, 0, 1, 1)
    assert arm.status == rl.REFUSED_STATUS and arm.functional == "" and not arm.identified
    assert arm.support == 0.0

    for t in (0, 1):
        for s in (0, 2):
            assert rl.try_identify_arm(adjacency, ps, 0, t, s).identified


# 5. Invalid parameters and undefined exposure



@pytest.mark.parametrize("bad_value", [0.0, 1.0, -0.2, 1.5])
def test_probabilities_outside_open_unit_interval_are_rejected(bad_value):
    adjacency = er_adjacency(6, 0.5, seed=51)
    ps = random_ps(6, seed=52)
    ps[2] = bad_value
    with pytest.raises(sp.InvalidDesignError):
        sp.validate_probabilities(ps, 6)
    with pytest.raises(sp.InvalidDesignError):
        sp.support_D1_E2(adjacency, ps, 0)


def test_probability_vector_length_must_match_graph():
    adjacency = er_adjacency(6, 0.5, seed=53)
    with pytest.raises(sp.InvalidDesignError):
        sp.support_D1_E2(adjacency, random_ps(5, seed=54), 0)


def test_isolated_unit_has_undefined_exposure():
    adjacency = er_adjacency(8, 0.4, seed=55)
    adjacency[3, :] = 0
    adjacency[:, 3] = 0
    ps = random_ps(8, seed=56)
    with pytest.raises(sp.UndefinedExposureError):
        sp.support_D1_E2(adjacency, ps, 3)
    with pytest.raises(sp.UndefinedExposureError):
        sp.e2_integer_ranges(0)
    result = rl.identify_all_arms(adjacency, ps, 3)
    assert result.status == "UNSUPPORTED"
    assert all(a.support is None and a.functional == "" for a in result.arms)


@pytest.mark.parametrize("t, s", [(2, 0), (-1, 0), (0, 3), (0, 1.5)])
def test_invalid_query_values_are_rejected(t, s):
    adjacency = er_adjacency(6, 0.5, seed=57)
    ps = random_ps(6, seed=58)
    with pytest.raises(sp.InvalidDesignError):
        rl.identify_arm(adjacency, ps, 0, t, s)


def test_unresolved_assumptions_block_identification():
    adjacency = er_adjacency(6, 0.5, seed=59)
    ps = random_ps(6, seed=60)
    with pytest.raises(rl.UnresolvedAssumptionsError):
        rl.identify_arm(adjacency, ps, 0, 1, 0, assumptions_admitted=False)
    result = rl.identify_all_arms(adjacency, ps, 0, assumptions_admitted=False)
    assert result.status == "NEEDS_INPUT" and not result.supported_arms


# 6. Small-N brute-force oracle (the required cross-check)


@pytest.mark.parametrize("n, edge_probability, seed", [(4, 0.5, 1), (6, 0.4, 2), (8, 0.35, 4)])
def test_brute_force_matches_closed_form(n, edge_probability, seed):
    adjacency = er_adjacency(n, edge_probability, seed=seed)
    ps = random_ps(n, seed=seed + 100)
    for i in range(n):
        if sp.degree(adjacency, i) == 0:
            continue
        pi = sp.support_D1_E2(adjacency, ps, i)
        for t in (0, 1):
            for s in sp.E2_LEVELS:
                oracle = brute_force_support(adjacency, ps, i, t, s)
                assert abs(oracle - pi[(t, s)]) < 1e-12, (n, i, t, s, oracle, pi[(t, s)])


def test_brute_force_oracle_reproduces_the_degree_one_zero_support():
    adjacency = path_adjacency(4)
    ps = random_ps(4, seed=61)
    assert brute_force_support(adjacency, ps, 0, 0, 1) == 0.0
    assert brute_force_support(adjacency, ps, 0, 1, 1) == 0.0
    assert abs(brute_force_support(adjacency, ps, 0, 1, 2)
               - sp.support_D1_E2(adjacency, ps, 0)[(1, 2)]) < 1e-12


# 7. Shared fixed ER300 network

ER300 = (Path(__file__).resolve().parents[2] / "pfn_pipeline" / "_internal" / "estimation"
         / "data" / "fixed_er_N300_p0.02_seed12345.json")


@pytest.mark.skipif(not ER300.exists(), reason="shared fixed ER300 record not present")
def test_shared_fixed_er300_network():
    adjacency = sp.load_fixed_er_adjacency(ER300)
    assert adjacency.shape == (300, 300)
    assert int(adjacency.sum()) // 2 == 905

    degrees = adjacency.sum(axis=1).astype(int)
    assert degrees.min() >= 1, "the shared record must contain no isolated node"

    ps = random_ps(300, seed=2026)
    for i in range(300):
        pi = sp.support_D1_E2(adjacency, ps, i)
        assert abs(sum(pi.values()) - 1.0) < 1e-12
        if degrees[i] == 1:
            assert pi[(0, 1)] == 0.0 and pi[(1, 1)] == 0.0
        else:
            assert all(value > 0.0 for value in pi.values())
