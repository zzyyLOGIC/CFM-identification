"""test_rule.py —— 任务 01（D1 + E1）的测试。

包含：
    1. 正常例子：非孤立点四个 arm 全部 POINT identified，support 表归一，
       且 DP 公式与“直接枚举邻居子集”的独立算法一致；
    2. zero-support / 非法参数例子：孤立点 (t,1) 被明确拒绝；p_i 取 0/1、
       t/s 越界等抛错；缺少关键假设时拒绝；
    3. N <= 8 小图 brute-force 对拍：枚举全部 2^N 个合法 assignment，按设计
       概率加权直数每个 (T_i, S_i) 状态出现的概率，与 support.py 的 DP 结果
       逐格比较。

运行：python test_rule.py   （或用 pytest 运行）
"""

from __future__ import annotations

import itertools
import math

from rule import ASSUMPTIONS, identify, identify_all
from support import (
    check_probs,
    er_network,
    exposure_probs,
    neighbor_treated_pmf,
    support_pi,
    support_table,
    zero_support_arms,
)

TOL = 1e-9


def brute_force_support(neighbors, probs):
    """标准答案：枚举所有 2^N 个 assignment，按设计概率 P(T=t) = prod p_i^{t_i}(1-p_i)^{1-t_i}
    加权，直数每个 (i, T_i, S_i) 状态出现的概率。

    只用于 N <= 8 的小图验证。
    """
    n = len(neighbors)
    check_probs(probs)
    cell = {}
    for mask in range(1 << n):
        t = [(mask >> i) & 1 for i in range(n)]
        w = 1.0
        for i in range(n):
            w *= probs[i] if t[i] == 1 else 1.0 - probs[i]
        for i in range(n):
            k = sum(t[j] for j in neighbors[i])
            s = 1 if k > len(neighbors[i]) // 2 else 0
            cell[(i, t[i], s)] = cell.get((i, t[i], s), 0.0) + w
    return cell


def subset_enumeration_pmf(neighbors, probs, i):
    """独立算法：直接枚举 N(i) 的全部子集计算 P(K_i = k)（度小时可用）。"""
    nb = neighbors[i]
    pmf = [0.0] * (len(nb) + 1)
    for r in range(len(nb) + 1):
        for subset in itertools.combinations(nb, r):
            p = 1.0
            for j in nb:
                p *= probs[j] if j in subset else 1.0 - probs[j]
            pmf[r] += p
    return pmf


# ---------------------------------------------------------------------------
# 1. 正常例子
# ---------------------------------------------------------------------------


def test_support_normal_case():
    """N=20 ER 图 + 异构 p_i：非孤立点四个 arm support 全正，support 表归一。"""
    nbrs = er_network(20, 0.30, seed=7)
    probs = [round(0.10 + 0.80 * i / 19, 4) for i in range(20)]  # 0.10 ~ 0.90 异构
    n_nonisolated = 0
    for i in range(20):
        tab = support_table(nbrs, probs, i)
        total = sum(tab.values())
        assert abs(total - 1.0) < TOL, f"node {i}: support table sums to {total}, not 1"
        if len(nbrs[i]) == 0:
            # 孤立点：S_i 恒为 0，(t,1) 零 support
            assert tab[(0, 1)] == 0.0 and tab[(1, 1)] == 0.0
            assert tab[(0, 0)] == 1.0 - probs[i] and tab[(1, 0)] == probs[i]
        else:
            n_nonisolated += 1
            for key, v in tab.items():
                assert v > 0.0, f"node {i}, arm {key}: support = {v} should be > 0"
    assert n_nonisolated > 0
    print(f"[ok] normal case: {n_nonisolated}/20 non-isolated nodes, all four arms positive")


def test_dp_matches_subset_enumeration():
    """DP 的 Poisson binomial PMF 与直接子集枚举一致（度 <= 10 的节点）。"""
    nbrs = er_network(20, 0.30, seed=7)
    probs = [round(0.10 + 0.80 * i / 19, 4) for i in range(20)]
    checked = 0
    for i in range(20):
        if len(nbrs[i]) <= 10:
            dp = neighbor_treated_pmf(nbrs, probs, i)
            exact = subset_enumeration_pmf(nbrs, probs, i)
            assert len(dp) == len(exact)
            for k, (a, b) in enumerate(zip(dp, exact)):
                assert abs(a - b) < TOL, f"node {i}, k={k}: dp={a} vs subset={b}"
            checked += 1
    assert checked > 0
    print(f"[ok] DP vs subset enumeration: {checked} nodes match")


def test_identify_returns_point_functional():
    """非孤立点的 arm：POINT identified，functional 是可观测条件均值。"""
    nbrs = er_network(20, 0.30, seed=7)
    probs = [round(0.10 + 0.80 * i / 19, 4) for i in range(20)]
    i = next(i for i in range(20) if len(nbrs[i]) > 0)
    for t in (0, 1):
        for s in (0, 1):
            res = identify(nbrs, probs, i, t, s)
            assert res.identified, res.reason
            assert res.support > 0.0
            assert res.functional == f"mu_{i}(t={t}, s={s}) = E[Y^obs_{i} | A, X, T_i = {t}, S_i = {s}]"
            assert set(res.assumptions) == set(ASSUMPTIONS)
    # support 数值 = own prob * q(s)
    for s in (0, 1):
        q = exposure_probs(nbrs, probs, i)[s]
        assert abs(support_pi(nbrs, probs, i, 1, s) - probs[i] * q) < TOL
        assert abs(support_pi(nbrs, probs, i, 0, s) - (1 - probs[i]) * q) < TOL
    print("[ok] identify() returns POINT functional with correct support values")


# ---------------------------------------------------------------------------
# 2. zero-support / 非法参数
# ---------------------------------------------------------------------------


def test_zero_support_rejected():
    """孤立点 (t, 1)：support = 0，必须明确拒绝，不能给 functional。"""
    # 手工构造：0-1-2 三角形 + 3-4 边 + 节点 5 孤立
    nbrs = [[1, 2], [0, 2], [0, 1], [4], [3], []]
    probs = [0.30, 0.55, 0.70, 0.20, 0.85, 0.45]
    iso = 5
    for t in (0, 1):
        assert support_pi(nbrs, probs, iso, t, 1) == 0.0
        res = identify(nbrs, probs, iso, t, 1)
        assert not res.identified
        assert res.support == 0.0
        assert res.functional == ""
        assert "zero support" in res.reason
    # (t, 0) 仍然 POINT
    for t in (0, 1):
        res = identify(nbrs, probs, iso, t, 0)
        assert res.identified and abs(res.support - (probs[iso] if t == 1 else 1 - probs[iso])) < TOL
    # zero_support_arms 恰好列出孤立点的两个 (t,1)
    zsa = zero_support_arms(nbrs, probs)
    assert set(zsa) == {(iso, 0, 1), (iso, 1, 1)}
    print("[ok] zero-support arms rejected with explicit reason")


def test_illegal_params_raise():
    """非法参数必须抛错（p_i 取 0/1 违反 D1 设计；t/s/i 越界）。"""
    nbrs = [[1], [0]]
    good = [0.3, 0.6]
    for bad_probs in ([0.0, 0.6], [0.3, 1.0], [0.3], [1.5, 0.6]):
        try:
            support_pi(nbrs, bad_probs, 0, 1, 0)
        except ValueError:
            pass
        else:
            raise AssertionError(f"probs={bad_probs} should violate D1 design")
    for t in (2, -1, 0.5):
        try:
            identify(nbrs, good, 0, t, 0)
        except ValueError:
            pass
        else:
            raise AssertionError(f"t={t} should raise")
    for s in (2, -1, 0.5):
        try:
            identify(nbrs, good, 0, 1, s)
        except ValueError:
            pass
        else:
            raise AssertionError(f"s={s} should raise")
    for i in (2, -1):
        try:
            identify(nbrs, good, i, 0, 0)
        except ValueError:
            pass
        else:
            raise AssertionError(f"i={i} should raise")
    print("[ok] illegal parameters raise ValueError")


def test_missing_assumption_rejected():
    """缺少 A1/A2/A3 中任何一个：不返回 POINT。"""
    nbrs = [[1], [0]]
    probs = [0.3, 0.6]
    for partial in (ASSUMPTIONS[:1], ASSUMPTIONS[:2], ()):
        res = identify(nbrs, probs, 0, 1, 0, assumptions=partial)
        assert not res.identified
        assert "assumption" in res.reason
    res = identify(nbrs, probs, 0, 1, 0, assumptions=ASSUMPTIONS)
    assert res.identified
    print("[ok] missing assumptions rejected")


# ---------------------------------------------------------------------------
# 3. N <= 8 brute-force 对拍
# ---------------------------------------------------------------------------


def test_brute_force_small_graph():
    """N=7 小图（含孤立点）枚举全部 2^7 个 assignment，与 support.py 对拍。"""
    # 0-1-2 路径 + 2-3 + 3-4 + 4-5 + 节点 6 孤立；异构 p
    nbrs = [[1], [0, 2], [1, 3], [2, 4], [3, 5], [4], []]
    probs = [0.15, 0.40, 0.55, 0.65, 0.80, 0.95, 0.50]
    n = len(nbrs)
    assert n <= 8
    cell = brute_force_support(nbrs, probs)

    # 每个 (i,t,s) 格子逐一比较；没出现过的格子两侧都必须是 0
    for i in range(n):
        for t in (0, 1):
            for s in (0, 1):
                bf = cell.get((i, t, s), 0.0)
                dp = support_pi(nbrs, probs, i, t, s)
                assert abs(bf - dp) < TOL, f"node {i}, arm ({t},{s}): brute={bf} vs support.py={dp}"
        # 归一性
        assert abs(sum(cell.get((i, t, s), 0.0) for t in (0, 1) for s in (0, 1)) - 1.0) < TOL

    # 孤立点 6 的 (t,1) 两侧都是严格的 0
    for t in (0, 1):
        assert cell.get((6, t, 1), 0.0) == 0.0
        assert support_pi(nbrs, probs, 6, t, 1) == 0.0
    print("[ok] brute-force vs support.py: all (i,t,s) cells match on N=7 graph")


def test_brute_force_all_isolated():
    """极端小图：两个孤立点，枚举验证只有 (t,0) 可达。"""
    nbrs = [[], []]
    probs = [0.25, 0.75]
    cell = brute_force_support(nbrs, probs)
    for i in range(2):
        for t in (0, 1):
            assert abs(cell.get((i, t, 0), 0.0) - (probs[i] if t == 1 else 1 - probs[i])) < TOL
            assert cell.get((i, t, 1), 0.0) == 0.0
            assert abs(support_pi(nbrs, probs, i, t, 0) - cell[(i, t, 0)]) < TOL
            assert support_pi(nbrs, probs, i, t, 1) == 0.0
    print("[ok] brute-force on fully isolated graph matches")


def main():
    test_support_normal_case()
    test_dp_matches_subset_enumeration()
    test_identify_returns_point_functional()
    test_zero_support_rejected()
    test_illegal_params_raise()
    test_missing_assumption_rejected()
    test_brute_force_small_graph()
    test_brute_force_all_isolated()
    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    main()
