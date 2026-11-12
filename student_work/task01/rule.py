"""rule.py —— 任务 01（D1 + E1）的识别规则。


    P_M = P_M'  =>  Q(M) = Q(M')

即：两个满足当前假设、总体观测分布相同的世界，必须给出同一个 causal answer。
本例中 A, X 处理前给定，可观测的总体信息是 P_M(T, Y^obs | A, X)。

POINT 论证：

    E[Y^obs_i | A, X, T_i = t, S_i = s]
        = sum_{t_{-i}: S_i((t,t_{-i})) = s} E[Y^obs_i | A, X, T = (t, t_{-i})] * w(t_{-i})
        = sum_{t_{-i}: S_i((t,t_{-i})) = s} E[Y_i((t, t_{-i})) | A, X] * w(t_{-i})
        = mu_i(t, s) = E[Y_i((t, T_{-i})) | S_i((t,T_{-i})) = s, A, X]

    第一行是全概率公式（在 T_{-i} 上分解）；第二行用 consistency + full-vector
    randomization；第三行就是 target 的定义。其中

        w(t_{-i}) = P(T_{-i} = t_{-i} | A, X, T_i = t, S_i = s)

    是由随机化设计唯一决定的权重（D1 下不再均摊，而按各 p_j 倾斜——这是本 setting
    与 baseline 的唯一实质差别，但它不改变识别结论）。右侧是总体可观测条件均值，
    所以 Q 由 P_M 唯一决定：POINT。

前提假设（缺一不可）：
    A1 处理前结构固定：A, X 在 treatment assignment 之前确定；
    A2 Consistency：T = t 时 Y^obs_i = Y_i(t)；
    A3 Full-vector randomization：T ⊥ {Y_i(t) : i, t} | A, X，来自实验协议，
       不从 outcome 数据中检验；
    A4 Query support：pi_i(t,s) = P(T_i = t, S_i = s | A, X) > 0。

若 pi_i(t,s) = 0：条件事件概率为零，观测分布不决定该条件均值（全概率公式中的
w 不再是合法条件分布，条件均值本身也未定义），此时必须明确拒绝该 query，
不能套用上面的 functional；这不是 PARTIAL，而是查询未定义。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Tuple

from support import check_probs, exposure_probs, own_treatment_prob, support_pi

__all__ = [
    "ASSUMPTIONS",
    "IdentificationResult",
    "identify",
    "identify_all",
]

# 三个关键假设（A4 support 由代码数值检查，不作为输入）
ASSUMPTIONS: Tuple[str, ...] = (
    "A1_pretreatment_structure_fixed",
    "A2_consistency",
    "A3_full_vector_randomization",
)


@dataclass(frozen=True)
class IdentificationResult:
    """一次识别查询的输出。

    identified : True 当且仅当假设齐备且 pi_i(t,s) > 0（POINT）。
    functional : POINT functional（可观测条件均值的表达式）；未识别时为拒绝原因。
    """

    node: int
    t: int
    s: int
    identified: bool
    support: Optional[float]
    functional: str
    assumptions: Tuple[str, ...] = field(default=())
    reason: str = ""

    def __str__(self) -> str:  # 便于 demo / 测试打印
        head = f"node {self.node}, arm (t={self.t}, s={self.s}): "
        if self.identified:
            return (
                head
                + f"POINT identified (support = {self.support:.6g})\n"
                + f"    functional: {self.functional}"
            )
        return head + f"REJECTED ({self.reason})"


def _validate_query(neighbors, probs, i, t, s) -> None:
    """查询本身的合法性：参数越界 / 违反设计 -> 抛错（非法参数不是零 support）。"""
    if not isinstance(i, int) or isinstance(i, bool):
        raise ValueError(f"node index i = {i!r} must be an int")
    if not (0 <= i < len(neighbors)):
        raise ValueError(f"node index i = {i} out of range [0, {len(neighbors)})")
    if t not in (0, 1):
        raise ValueError(f"own treatment t = {t} must be 0 or 1")
    if s not in (0, 1):
        raise ValueError(f"exposure state s = {s} must be 0 or 1 (E1 is binary)")
    check_probs(probs)  # D1 设计约束 0 < p_i < 1


def identify(
    neighbors: Sequence[Sequence[int]],
    probs: Sequence[float],
    i: int,
    t: int,
    s: int,
    assumptions: Sequence[str] = ASSUMPTIONS,
    support_tol: float = 0.0,
) -> IdentificationResult:
    """识别 mu_i(t,s)。

    support > 0 且 A1/A2/A3 齐备 -> 返回 POINT functional：
        mu_i(t,s) = E[Y^obs_i | A, X, T_i = t, S_i = s]
    support = 0 -> 明确拒绝（查询未定义）。
    """
    _validate_query(neighbors, probs, i, t, s)

    missing = [a for a in ASSUMPTIONS if a not in set(assumptions)]
    if missing:
        return IdentificationResult(
            node=i, t=t, s=s, identified=False, support=None,
            functional="",
            assumptions=tuple(assumptions),
            reason=f"key assumption(s) not confirmed: {', '.join(missing)}",
        )

    pi = support_pi(neighbors, probs, i, t, s)
    if pi <= support_tol:
        d_i = len(neighbors[i])
        if s == 1 and d_i == 0:
            why = "zero support: d_i = 0 (isolated node), K_i == 0 so S_i == 1 never occurs"
        else:
            why = "zero support: P(T_i = t, S_i = s | A, X) = 0"
        return IdentificationResult(
            node=i, t=t, s=s, identified=False, support=pi,
            functional="",
            assumptions=tuple(assumptions),
            reason=why,
        )

    functional = (
        f"mu_{i}(t={t}, s={s}) = E[Y^obs_{i} | A, X, T_i = {t}, S_i = {s}]"
    )
    return IdentificationResult(
        node=i, t=t, s=s, identified=True, support=pi,
        functional=functional,
        assumptions=tuple(assumptions),
        reason="",
    )


def identify_all(
    neighbors: Sequence[Sequence[int]],
    probs: Sequence[float],
    i: int,
    assumptions: Sequence[str] = ASSUMPTIONS,
) -> Dict[Tuple[int, int], IdentificationResult]:
    """节点 i 的四个 arm 一次性识别（demo 用）。"""
    return {
        (t, s): identify(neighbors, probs, i, t, s, assumptions)
        for t in (0, 1)
        for s in (0, 1)
    }


if __name__ == "__main__":
    from support import er_network

    nbrs = er_network(6, 0.5, seed=3)
    ps = [0.2, 0.35, 0.5, 0.65, 0.8, 0.95]
    for i in (1, 4):  # 一个非孤立点，一个孤立点
        print(f"--- node {i} (d_i = {len(nbrs[i])}) ---")
        for (t, s), res in identify_all(nbrs, ps, i).items():
            print(" ", res)
