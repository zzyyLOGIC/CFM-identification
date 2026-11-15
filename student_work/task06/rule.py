"""Task 06 theorem gate: point-ID of design-standardized core-majority arms.

This is an isolated student submission, NOT a registration of a new backend in
pfn_pipeline.  In particular, it does not assume iid Bernoulli assignment and
never reads observed/simulated outcomes or uses Estimation / Policy code.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from numbers import Integral
from typing import Mapping

if __package__:
    from .support import Task06Setting, support_for_node
else:
    from support import Task06Setting, support_for_node

# These facts must be explicitly admitted based on an experiment protocol;
# the solver cannot verify their real-world truth from observed outcomes.
REQUIRED_ASSUMPTIONS: tuple[str, ...] = (
    "fixed_pretreatment_network",
    "fixed_pretreatment_core_partners",
    "known_complete_randomization",
    "full_vector_randomization",
    "consistency",
    "finite_conditional_first_moments",
)


@dataclass(frozen=True)
class IdentificationResult:
    """A compact local result; distinct from pfn_pipeline's shared contract."""

    node: int
    treatment: int
    exposure: int
    support: Fraction
    status: str                         # POINT or UNSUPPORTED
    identified_functional: str | None   # None unless POINT
    reason_code: str | None            # explicit reason if UNSUPPORTED
    assumptions_used: tuple[str, ...]
    explanation: str


def identify_arm(
    setting: Task06Setting,
    node: int,
    treatment: int,
    exposure: int,
    *,
    assumptions: Mapping[str, bool] | None = None,
) -> IdentificationResult:
    """Identify an arm only with positive population support and admitted assumptions.

    POINT: mu_i(t,s) = E[Y_i^obs | A,X,C,T_i=t,S_i=s].
    Zero support: target as defined by design-standardization is undefined.
    Missing/false assumptions: UNSUPPORTED, *not* PARTIAL.
    """
    if not isinstance(treatment, Integral) or isinstance(treatment, bool) or treatment not in (0, 1):
        raise ValueError("treatment must be 0 or 1")
    if not isinstance(exposure, Integral) or isinstance(exposure, bool) or exposure not in (0, 1):
        raise ValueError("exposure must be 0 or 1")
    probs = support_for_node(setting, node)  # also validates node
    pi = probs[(int(treatment), int(exposure))]
    admitted = {} if assumptions is None else assumptions
    if not isinstance(admitted, Mapping):
        raise ValueError("assumptions must be a mapping of named boolean admissions")
    for name, state in admitted.items():
        if not isinstance(name, str) or type(state) is not bool:
            raise ValueError("assumption names must be strings and their values must be booleans")

    missing = tuple(name for name in REQUIRED_ASSUMPTIONS
                    if admitted.get(name) is not True)
    if pi == 0:
        return IdentificationResult(
            node, int(treatment), int(exposure), pi,
            "UNSUPPORTED", None, "ZERO_POPULATION_SUPPORT", (),
            "This (T_i,S_i) event is impossible under the fixed-m design; "
            "the design-standardized arm mean is not defined.",
        )
    if missing:
        return IdentificationResult(
            node, int(treatment), int(exposure), pi,
            "UNSUPPORTED", None, "REQUIRED_ASSUMPTIONS_NOT_ADMITTED", (),
            "Unconfirmed assumptions: " + ", ".join(missing)
            + ". An algorithm cannot certify these real-world facts.",
        )

    return IdentificationResult(
        node=node, treatment=int(treatment), exposure=int(exposure),
        support=pi, status="POINT", reason_code=None,
        identified_functional=(
            f"mu_{node}({treatment},{exposure}) = "
            f"E[Y_{node}^obs | A, X, C, T_{node}={treatment}, S_{node}={exposure}]"
        ),
        assumptions_used=REQUIRED_ASSUMPTIONS,
        explanation=(
            "Law of total expectation over legal full assignments + "
            "consistency + full-vector randomization + positive support. "
            "S_i is a design-standardized query grouping, not a sufficient "
            "causal exposure. No finite-sample estimate is asserted."
        ),
    )


def identify_all(
    setting: Task06Setting, *, assumptions: Mapping[str, bool] | None = None,
) -> dict[int, dict[tuple[int, int], IdentificationResult]]:
    """Evaluate all N x 4 queries; each arm has its own status and support."""
    return {
        i: {(t, s): identify_arm(setting, i, t, s, assumptions=assumptions)
            for t in (0, 1) for s in (0, 1)}
        for i in range(setting.n)
    }
