"""support.py —— 任务 01（D1 + E1）的 support 概率计算。

Setting（相对 shared baseline 只改了随机化设计，exposure 与 baseline 相同）：

    Assignment (D1):  T_i ~ Bernoulli(p_i)，跨个体独立，0 < p_i < 1，p_i 实验前已知
    Exposure   (E1):  K_i(t) = sum_{j in N(i)} t_j
                      S_i(t) = 1{K_i(t) > floor(d_i/2)}     （严格多数；正好一半归入 S=0）
    Target:           mu_i(t,s) = E[Y_i((t, T_{-i})) | S_i((t,T_{-i})) = s, A, X]

Support（式 (4) 的 pi）：

    pi_i(t,s) = P(T_i = t, S_i = s | A, X)
              = P(T_i = t) * P(S_i = s)                        （T_i 与 T_{-i} 独立）
              = p_i^t (1-p_i)^(1-t) * q_i(s)

    其中 K_i = sum_{j in N(i)} T_j ~ PoissonBinomial({p_j}_{j in N(i)})，
    即“每个邻居都是一次成功概率不同的 Bernoulli”：

        P(K_i = k) = sum_{A subseteq N(i), |A| = k} prod_{j in A} p_j * prod_{j not in A} (1 - p_j)

    q_i(1) = P(K_i > floor(d_i/2))，q_i(0) = 1 - q_i(1)。

Support 结构（哪些状态可能为 0）：
    * t = 0 / t = 1：因设计约束 0 < p_i < 1，恒有正概率（p_i 取 0 或 1 即违反设计）；
    * s = 1（严格多数）：每个 p_j in (0,1) 使 K_i 在 {0,...,d_i} 上全支撑，
      故 d_i >= 1 时 q_i(1) > 0；d_i = 0（孤立点）时 K_i 恒为 0，S_i 恒为 0，pi_i(t,1) = 0；
    * s = 0：恒有正概率（K_i = 0 的概率 prod_{j in N(i)} (1-p_j) > 0）。

图的表示：邻接表 neighbors[i] = 升序邻居索引列表（无向简单图，无自环）。
只依赖 Python 标准库；不针对任何单个 node 硬编码，也不含 N=300 之类的常量。
"""

from __future__ import annotations

import random
from typing import Dict, List, Sequence

__all__ = [
    "er_network",
    "check_probs",
    "own_treatment_prob",
    "poisson_binomial_pmf",
    "neighbor_treated_pmf",
    "majority_threshold",
    "exposure_state",
    "exposure_probs",
    "support_pi",
    "support_table",
    "zero_support_arms",
]

# ---------------------------------------------------------------------------
# 图 / 设计参数
# ---------------------------------------------------------------------------


def er_network(n: int, edge_prob: float, seed: int = 0) -> List[List[int]]:
    """Erdos-Renyi G(n, edge_prob) 随机图，返回邻接表（升序、无向、无自环）。

    仅作演示 / 测试用；识别逻辑本身不依赖图的生成方式。
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    if not (0.0 <= edge_prob <= 1.0):
        raise ValueError("edge_prob must be in [0, 1]")
    rng = random.Random(seed)
    neighbors: List[List[int]] = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < edge_prob:
                neighbors[i].append(j)
                neighbors[j].append(i)
    return neighbors


def check_probs(probs: Sequence[float]) -> Sequence[float]:
    """校验设计参数：D1 要求每个 p_i 严格落在 (0, 1) 内且实验前已知。"""
    if len(probs) == 0:
        raise ValueError("probs is empty")
    for i, p in enumerate(probs):
        if not isinstance(p, (int, float)) or isinstance(p, bool):
            raise ValueError(f"p_{i} = {p!r} is not a number")
        if not (0.0 < float(p) < 1.0):
            raise ValueError(
                f"p_{i} = {p} violates the D1 design constraint 0 < p_i < 1; "
                "an arm with p_i in {{0, 1}} would have zero support and the "
                "query is undefined"
            )
    return probs


def own_treatment_prob(probs: Sequence[float], i: int, t: int) -> float:
    """P(T_i = t) = p_i^t (1-p_i)^(1-t)。"""
    _check_node_index(probs, i)
    if t not in (0, 1):
        raise ValueError(f"own treatment t = {t} must be 0 or 1")
    p = probs[i]
    return float(p) if t == 1 else 1.0 - float(p)


def _check_node_index(neighbors_or_probs, i: int) -> None:
    if not isinstance(i, int) or isinstance(i, bool):
        raise ValueError(f"node index i = {i!r} must be an int")
    if not (0 <= i < len(neighbors_or_probs)):
        raise ValueError(f"node index i = {i} out of range [0, {len(neighbors_or_probs)})")


# ---------------------------------------------------------------------------
# Exposure（E1 严格多数，与 shared baseline 相同）
# ---------------------------------------------------------------------------


def majority_threshold(d: int) -> int:
    """floor(d/2)：K_i 必须严格超过该值才算严格多数。"""
    if d < 0:
        raise ValueError("degree must be >= 0")
    return d // 2


def exposure_state(k: int, d: int) -> int:
    """E1 暴露映射：S = 1{k > floor(d/2)}（正好一半归入 S = 0）。"""
    return 1 if k > majority_threshold(d) else 0


# ---------------------------------------------------------------------------
# K_i 的分布：Poisson Binomial（每个邻居成功概率不同的独立 Bernoulli 之和）
# ---------------------------------------------------------------------------


def poisson_binomial_pmf(ps: Sequence[float]) -> List[float]:
    """P(K = k), k = 0..len(ps)，其中 K = sum 独立 Bernoulli(p)，p 逐个不同。

    动态规划：dp[k] = 前 m 个邻居中恰有 k 个 treated 的概率，
    dp'[k] = dp[k]*(1-p) + dp[k-1]*p。复杂度 O(len(ps)^2)。
    """
    dp = [1.0]
    for p in ps:
        p = float(p)
        nxt = [0.0] * (len(dp) + 1)
        for k, v in enumerate(dp):
            if v == 0.0:
                continue
            nxt[k] += v * (1.0 - p)
            nxt[k + 1] += v * p
        dp = nxt
    return dp


def neighbor_treated_pmf(neighbors: Sequence[Sequence[int]], probs: Sequence[float], i: int) -> List[float]:
    """节点 i 的邻居 treated 数 K_i 的 PMF：P(K_i = k), k = 0..d_i。"""
    _check_node_index(neighbors, i)
    _check_node_index(probs, i)
    for j in neighbors[i]:
        _check_node_index(probs, j)
    return poisson_binomial_pmf([probs[j] for j in neighbors[i]])


def exposure_probs(neighbors: Sequence[Sequence[int]], probs: Sequence[float], i: int) -> Dict[int, float]:
    """{s: P(S_i = s | A, X)}，E1 严格多数暴露（s in {0, 1}）。"""
    pmf = neighbor_treated_pmf(neighbors, probs, i)
    thr = majority_threshold(len(neighbors[i]))
    q1 = sum(pmf[thr + 1 :])  # P(K_i > floor(d_i/2))
    return {0: 1.0 - q1, 1: q1}


# ---------------------------------------------------------------------------
# Support：pi_i(t, s) = P(T_i = t, S_i = s | A, X)
# ---------------------------------------------------------------------------


def support_pi(
    neighbors: Sequence[Sequence[int]],
    probs: Sequence[float],
    i: int,
    t: int,
    s: int,
) -> float:
    """pi_i(t,s) = P(T_i = t) * P(S_i = s) = p_i^t (1-p_i)^(1-t) * q_i(s)。"""
    check_probs(probs)
    _check_node_index(neighbors, i)
    _check_node_index(probs, i)
    if t not in (0, 1):
        raise ValueError(f"own treatment t = {t} must be 0 or 1")
    if s not in (0, 1):
        raise ValueError(f"exposure state s = {s} must be 0 or 1 (E1 is binary)")
    return own_treatment_prob(probs, i, t) * exposure_probs(neighbors, probs, i)[s]


def support_table(
    neighbors: Sequence[Sequence[int]],
    probs: Sequence[float],
    i: int,
) -> Dict[tuple, float]:
    """节点 i 的四个 arm 的 support：{(t, s): pi_i(t,s)}。"""
    return {(t, s): support_pi(neighbors, probs, i, t, s) for t in (0, 1) for s in (0, 1)}


def zero_support_arms(
    neighbors: Sequence[Sequence[int]],
    probs: Sequence[float],
) -> Dict[tuple, str]:
    """列出整个网络中 support = 0 的 (i, t, s) 及原因（本 setting 只有孤立点的 (t,1)）。"""
    check_probs(probs)
    out: Dict[tuple, str] = {}
    for i in range(len(neighbors)):
        if len(neighbors[i]) == 0:
            for t in (0, 1):
                out[(i, t, 1)] = "d_i = 0 (isolated): K_i == 0 always, so S_i == 1 never occurs"
    return out


if __name__ == "__main__":
    # 小演示：N=6 的图 + 异构 p_i
    nbrs = er_network(6, 0.5, seed=3)
    ps = [0.2, 0.35, 0.5, 0.65, 0.8, 0.95]
    for i in range(len(nbrs)):
        tab = support_table(nbrs, ps, i)
        print(f"node {i}: d_i={len(nbrs[i])}, " + ", ".join(f"pi{k[0]}{k[1]}={v:.4f}" for k, v in tab.items()))
