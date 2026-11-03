"""Task 07 的识别规则：D3 × E1。

在给定假设下，有 support 的 arm mean 被 POINT 识别为可观测的条件总体均值：

    mu_i(t, s) = E[ Y_obs_i | A, X, T_i = t, S_i = s ],      (t, s) ∈ {0,1}^2.

结果字段与共享仓库的词汇保持一致
（``pfn_pipeline`` 中的 ``IdentificationResult``）：

* ``status`` ∈ {POINT, UNSUPPORTED}；
* ``verification_status`` ∈ {VERIFIED, REJECTED}；
* ``diagnostics["workflow_status"]`` ∈ {COMPLETE, NEEDS_INPUT, UNSUPPORTED}；
* ``estimation_request`` 仅在目标可执行时非 None。

满足以下两条时，规则返回 POINT 泛函：

* 五个因果假设被显式承认；
* 查询的 arm 具有严格正的总体 support ``pi_i(t, s) > 0``。

若某个 arm 的总体 support 为 0，规则拒绝该 query：
任务中的式(3)不能用于空设计单元。有限样本里恰好没出现某个 arm，在这里
*不会* 被当成总体 support 为 0 —— support 只来自已知分配律，绝不来自观测数据。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, Iterable, Optional, Tuple

from support import TwoGroupQuotaDesign
from support import support as _support

REQUIRED_ASSUMPTIONS: Tuple[str, ...] = (
    "known_assignment_law",
    "full_vector_randomization",
    "consistency",
    "fixed_pretreatment_network",
    "finite_conditional_first_moments",
)

#: 便捷常量：当调用方确实声明全部五个假设时使用。
#: 它仍需 *显式* 传给 ``identify_arm``，以免省略参数时静默承认假设。
EXPERIMENTAL_ASSUMPTIONS: Tuple[str, ...] = REQUIRED_ASSUMPTIONS

# --- 识别 / 验证状态（与共享仓库词汇一致）--------------------------------
POINT = "POINT"
UNSUPPORTED = "UNSUPPORTED"
VERIFIED = "VERIFIED"
REJECTED = "REJECTED"

# --- 工作流状态 -----------------------------------------------------------
COMPLETE = "COMPLETE"
NEEDS_INPUT = "NEEDS_INPUT"

#: 对比名称 -> 定义该对比的两个 arm。
CONTRAST_ARMS: Dict[str, Tuple[Tuple[int, int], Tuple[int, int]]] = {
    "Direct": ((1, 0), (0, 0)),
    "Spillover": ((1, 1), (1, 0)),
    "Total": ((1, 1), (0, 0)),
}


@dataclass(frozen=True)
class IdentificationResult:
    status: str
    reason_code: str
    node: str
    #: 单个 arm 时为 ``(t, s)``；对比时为 ``((t_hi, s_hi), (t_lo, s_lo))``。
    arm: tuple
    support: Optional[Fraction]
    functional: str
    assumptions_used: Tuple[str, ...]
    verification_status: str = UNSUPPORTED
    diagnostics: Dict[str, object] = field(default_factory=dict)
    estimation_request: Optional[Dict[str, object]] = None
    message: str = ""

    @property
    def identified(self) -> bool:
        return self.status == POINT and self.verification_status == VERIFIED

    @property
    def workflow_status(self) -> str:
        return str(self.diagnostics.get("workflow_status", UNSUPPORTED))


def _arm_functional(node: str, t: int, s: int) -> str:
    return (
        f"mu_{node}(t={t},s={s}) = "
        f"E[Y_obs_{node} | A,X,T_{node}={t},S_{node}={s}]"
    )


def _refusal(
    reason_code: str,
    node: str,
    arm: tuple,
    message: str,
    assumptions_used: Iterable[str],
    workflow: str,
    missing: Iterable[str] = (),
) -> IdentificationResult:
    # 统一的“拒绝”结果：UNSUPPORTED，无泛函，无 estimation_request
    return IdentificationResult(
        status=UNSUPPORTED,
        reason_code=reason_code,
        node=node,
        arm=arm,
        support=Fraction(0),
        functional="",
        assumptions_used=tuple(assumptions_used),
        verification_status=UNSUPPORTED,
        diagnostics={
            "workflow_status": workflow,
            "reason_code": reason_code,
            "missing_assumptions": list(missing),
        },
        estimation_request=None,
        message=message,
    )


def identify_arm(
    design: TwoGroupQuotaDesign,
    node: str,
    t: int,
    s: int,
    *,
    assumptions: Optional[Iterable[str]] = None,
) -> IdentificationResult:
    """识别 ``node`` 的单个 arm ``(t, s)``，或在无法识别时说明原因。

    ``assumptions`` 必须显式传入。省略它 *不* 会被当作"全部承认"：
    规则会以 ``ASSUMPTIONS_NOT_SPECIFIED`` 拒绝，且 ``workflow_status = NEEDS_INPUT``，
    这样调用方无法在省略参数时静默地认证一套假设。
    """
    if assumptions is None:
        return _refusal(
            "ASSUMPTIONS_NOT_SPECIFIED", node, (t, s),
            "no admitted assumptions supplied; pass the confirmed assumption names "
            "explicitly (see rule.EXPERIMENTAL_ASSUMPTIONS for the full set).",
            (), NEEDS_INPUT,
        )
    assumed = tuple(assumptions)
    missing = tuple(name for name in REQUIRED_ASSUMPTIONS if name not in set(assumed))
    if missing:
        return _refusal(
            "REQUIRED_ASSUMPTIONS_NOT_ADMITTED", node, (t, s),
            f"missing admitted assumptions: {', '.join(missing)}",
            assumed, UNSUPPORTED, missing,
        )

    try:
        probability = _support(design, node, t, s)
    except ValueError as exc:
        return _refusal("INVALID_QUERY", node, (t, s), str(exc), assumed, UNSUPPORTED)

    if probability <= 0:
        # 空设计单元：pi=0 时式(3)的权重 w=q/pi 无定义，必须拒绝
        return _refusal(
            "ZERO_POPULATION_SUPPORT", node, (t, s),
            f"pi_{node}{t, s} = 0 under the declared D3 design; the arm is an empty "
            "design cell and equation (3) does not apply.",
            assumed, UNSUPPORTED,
        )

    functional = _arm_functional(node, t, s)
    return IdentificationResult(
        status=POINT,
        reason_code="POINT_IDENTIFIED",
        node=node,
        arm=(t, s),
        support=probability,
        functional=functional,
        assumptions_used=assumed,
        verification_status=VERIFIED,
        diagnostics={"workflow_status": COMPLETE, "reason_code": "POINT_IDENTIFIED"},
        estimation_request={
            "request_type": "design_standardized_arm_mean",
            "target": functional,
            "node": node,
            "own_treatment": t,
            "exposure": s,
            "population_support": str(probability),
            "assumptions_used": list(REQUIRED_ASSUMPTIONS),
        },
        message=(
            "randomization + consistency + positive population support identify "
            "the design-standardized arm mean as an observable conditional mean."
        ),
    )


def identify_contrast(
    design: TwoGroupQuotaDesign,
    node: str,
    kind: str,
    *,
    assumptions: Optional[Iterable[str]] = None,
) -> IdentificationResult:
    """识别 ``node`` 的一个 ``Direct`` / ``Spillover`` / ``Total`` 对比。"""
    if kind not in CONTRAST_ARMS:
        raise ValueError(f"unknown contrast {kind!r}; expected one of {sorted(CONTRAST_ARMS)}")
    high_arm, low_arm = CONTRAST_ARMS[kind]
    high = identify_arm(design, node, high_arm[0], high_arm[1], assumptions=assumptions)
    low = identify_arm(design, node, low_arm[0], low_arm[1], assumptions=assumptions)

    label = f"tau_{kind}_{node}"
    expression = (
        f"{label} = mu_{node}{high_arm} - mu_{node}{low_arm} = "
        f"({_arm_functional(node, *high_arm).split(' = ', 1)[1]}) - "
        f"({_arm_functional(node, *low_arm).split(' = ', 1)[1]})"
    )
    failed = [result for result in (high, low) if not result.identified]
    if failed:
        # 只要有任意一个 arm 不可识别，整个对比就不可识别
        workflow = (
            NEEDS_INPUT
            if any(result.reason_code == "ASSUMPTIONS_NOT_SPECIFIED" for result in failed)
            else UNSUPPORTED
        )
        return _refusal(
            "ARM_NOT_IDENTIFIED", node, (high_arm, low_arm),
            "contrast not identified because "
            + ", ".join(result.reason_code for result in failed),
            high.assumptions_used, workflow,
        )
    return IdentificationResult(
        status=POINT,
        reason_code="POINT_IDENTIFIED",
        node=node,
        arm=(high_arm, low_arm),
        support=None,
        functional=expression,
        assumptions_used=high.assumptions_used,
        verification_status=VERIFIED,
        diagnostics={"workflow_status": COMPLETE, "reason_code": "POINT_IDENTIFIED"},
        estimation_request={
            "request_type": "design_standardized_contrast",
            "kind": kind,
            "target": expression,
            "node": node,
            "high_arm": list(high_arm),
            "low_arm": list(low_arm),
            "assumptions_used": list(REQUIRED_ASSUMPTIONS),
        },
        message="both contrast arms are point identified.",
    )


def supported_arms(
    design: TwoGroupQuotaDesign,
    node: str,
    *,
    assumptions: Optional[Iterable[str]] = None,
) -> Tuple[Tuple[int, int], ...]:
    """便捷函数：返回规则会判定为 POINT 的那些 arm。"""
    return tuple(
        arm
        for arm in ((t, s) for t in (0, 1) for s in (0, 1))
        if identify_arm(design, node, arm[0], arm[1], assumptions=assumptions).identified
    )
