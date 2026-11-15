"""Independent small-graph enumeration oracle for Task 06.

Run from repo root: python -B -m pytest -q student_work/task06/test_rule.py
Or from this directory: python -B -m pytest -q test_rule.py
"""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations
from math import comb

import pytest

from rule import REQUIRED_ASSUMPTIONS, identify_all, identify_arm
from support import (
    Task06Setting, joint_arm_probability, positive_support_from_bounds,
    support_for_node, support_probabilities,
)

ADMITTED = {name: True for name in REQUIRED_ASSUMPTIONS}


def complete_graph(n: int) -> list[list[int]]:
    return [[int(i != j) for j in range(n)] for i in range(n)]


def cyclic_core_sets(n: int, h: int) -> dict[int, tuple[int, ...]]:
    return {i: tuple((i + j) % n for j in range(1, h+1)) for i in range(n)}


def exact_enumeration_oracle(setting: Task06Setting):
    """Independent oracle: enumerate every legal *full* assignment once.

    Does not call joint_arm_probability or the hypergeometric formula.
    """
    n = setting.n
    counts = {i: {(t, s): 0 for t in (0, 1) for s in (0, 1)}
              for i in range(n)}
    for treated_nodes in combinations(range(n), setting.m):
        treated = set(treated_nodes)
        for i in range(n):
            t = int(i in treated)
            k = len(set(setting.core_partners[i]) & treated)
            s = int(2*k > len(setting.core_partners[i]))
            counts[i][(t, s)] += 1
    denom = comb(n, setting.m)
    return {i: {arm: Fraction(c, denom) for arm, c in by_arm.items()}
            for i, by_arm in counts.items()}


def test_reference_N8_m3_h3_all_four_arms():
    setting = Task06Setting.create(complete_graph(8), cyclic_core_sets(8, 3), 3)
    expected = {(0, 0): Fraction(22, 56), (0, 1): Fraction(13, 56),
                (1, 0): Fraction(18, 56), (1, 1): Fraction(3, 56)}
    assert support_for_node(setting, 0) == expected
    assert all(support_for_node(setting, i) == expected for i in range(8))
    assert exact_enumeration_oracle(setting)[0] == expected


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7, 8])
def test_oracle_all_quotas_multiple_cores_and_all_nodes(n):
    graph = complete_graph(n)
    # Exercise odd/even core sizes, a one-partner core, and h=N-1.
    for h in sorted({1, min(2, n-1), n-1}):
        core = cyclic_core_sets(n, h)
        for m in range(n + 1):
            setting = Task06Setting.create(graph, core, m)
            exact = exact_enumeration_oracle(setting)
            formula = support_probabilities(graph, core, m)
            assert formula == exact
            for i in range(n):
                pi = formula[i]
                assert sum(pi.values(), Fraction(0)) == 1
                assert pi[(1, 0)] + pi[(1, 1)] == Fraction(m, n)
                assert pi[(0, 0)] + pi[(0, 1)] == Fraction(n-m, n)
                assert all((pi[t, s] > 0) == positive_support_from_bounds(
                    n, m, h, t, s) for t in (0, 1) for s in (0, 1))


def test_irregular_graph_different_core_sizes_and_which_partners():
    n = 6
    edges = [(0, 1), (0, 2), (0, 3), (1, 2), (2, 3),
             (3, 4), (4, 5), (5, 0)]
    graph = [[0]*n for _ in range(n)]
    for i, j in edges:
        graph[i][j] = graph[j][i] = 1
    core = {0: [1, 2, 3], 1: [0], 2: [0, 1], 3: [0, 2, 4],
            4: [3], 5: [0, 4]}
    for m in range(n + 1):
        setting = Task06Setting.create(graph, core, m)
        assert support_probabilities(graph, core, m) == exact_enumeration_oracle(setting)


def test_zero_support_refuses_one_query_but_allows_supported_queries():
    setting = Task06Setting.create(complete_graph(6), cyclic_core_sets(6, 3), 2)
    assert joint_arm_probability(6, 2, 3, 1, 1) == 0
    zero = identify_arm(setting, 0, 1, 1, assumptions=ADMITTED)
    assert zero.status == "UNSUPPORTED"
    assert zero.reason_code == "ZERO_POPULATION_SUPPORT"
    assert zero.identified_functional is None
    positive = identify_arm(setting, 0, 0, 0, assumptions=ADMITTED)
    assert positive.status == "POINT"
    assert positive.identified_functional is not None
    assert positive.support > 0


def test_assumption_gate_explicit_and_never_silently_partial():
    setting = Task06Setting.create(complete_graph(8), cyclic_core_sets(8, 3), 3)
    no_admission = identify_arm(setting, 0, 1, 1)
    assert no_admission.status == "UNSUPPORTED"
    assert no_admission.reason_code == "REQUIRED_ASSUMPTIONS_NOT_ADMITTED"
    assert no_admission.identified_functional is None
    subset = dict(ADMITTED)
    subset["full_vector_randomization"] = False
    assert identify_arm(setting, 0, 0, 1, assumptions=subset).status == "UNSUPPORTED"
    assert identify_arm(setting, 0, 0, 1, assumptions=ADMITTED).status == "POINT"
    with pytest.raises(ValueError, match="booleans"):
        identify_arm(setting, 0, 0, 1, assumptions={"consistency": "yes"})


def test_all_results_and_no_estimation_content():
    setting = Task06Setting.create(complete_graph(8), cyclic_core_sets(8, 3), 3)
    results = identify_all(setting, assumptions=ADMITTED)
    assert len(results) == 8
    assert sum(result.status == "POINT" for arms in results.values()
               for result in arms.values()) == 32
    result = results[0][(1, 1)]
    assert "E[Y_0^obs" in result.identified_functional
    assert "fixed_pretreatment_core_partners" in result.assumptions_used
    assert result.support == Fraction(3, 56)
    assert not hasattr(result, "estimate")


@pytest.mark.parametrize("m", [0, 4])
def test_boundary_quotas_do_not_break_probability_or_query_handling(m):
    setting = Task06Setting.create(complete_graph(4), cyclic_core_sets(4, 1), m)
    oracle = exact_enumeration_oracle(setting)
    assert support_for_node(setting, 2) == oracle[2]
    result = identify_all(setting, assumptions=ADMITTED)[2]
    assert sum(r.support for r in result.values()) == 1
    assert sum(r.status == "POINT" for r in result.values()) == 1


def test_graph_size_agnostic_N300():
    n = 300
    graph = [[0]*n for _ in range(n)]
    core = {}
    for i in range(n):
        j = (i+1) % n
        k = (i-1) % n
        graph[i][j] = graph[j][i] = 1
        graph[i][k] = graph[k][i] = 1
        core[i] = [j, k]
    setting = Task06Setting.create(graph, core, 90)
    support = support_for_node(setting, 117)
    assert sum(support.values()) == 1
    assert all(0 < p < 1 for p in support.values())


def test_invalid_params_and_core_sets_are_rejected():
    graph = complete_graph(4)
    valid = cyclic_core_sets(4, 1)
    with pytest.raises(ValueError, match="m"):
        Task06Setting.create(graph, valid, -1)
    with pytest.raises(ValueError, match="m"):
        Task06Setting.create(graph, valid, 5)
    with pytest.raises(ValueError, match="m"):
        Task06Setting.create(graph, valid, 2.5)
    with pytest.raises(ValueError, match="nonempty"):
        Task06Setting.create(graph, {**valid, 2: []}, 2)
    with pytest.raises(ValueError, match="duplicate"):
        Task06Setting.create(graph, {**valid, 0: [1, 1]}, 2)
    with pytest.raises(ValueError, match="subset"):
        Task06Setting.create(graph, {**valid, 0: [0]}, 2)
    with pytest.raises(ValueError, match="every node"):
        Task06Setting.create(graph, {0: [1]}, 2)
    nonsymmetric = [row.copy() for row in graph]
    nonsymmetric[1][2] = 0
    with pytest.raises(ValueError, match="symmetric"):
        Task06Setting.create(nonsymmetric, valid, 2)
    selfloop = [row.copy() for row in graph]
    selfloop[0][0] = 1
    with pytest.raises(ValueError, match="self-loops"):
        Task06Setting.create(selfloop, valid, 2)
    sparse = [[0]*4 for _ in range(4)]
    sparse[0][1] = sparse[1][0] = 1
    with pytest.raises(ValueError, match="subset"):
        Task06Setting.create(sparse, valid, 2)
    with pytest.raises(ValueError, match="node"):
        support_for_node(Task06Setting.create(graph, valid, 2), 4)
    with pytest.raises(ValueError, match="treatment"):
        identify_arm(Task06Setting.create(graph, valid, 2), 0, 2, 1, assumptions=ADMITTED)
    with pytest.raises(ValueError, match="exposure"):
        identify_arm(Task06Setting.create(graph, valid, 2), 0, 1, 2, assumptions=ADMITTED)
