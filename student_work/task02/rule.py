"""Task 02 identification rule: turn a supported design arm into a POINT functional.

Contract (the full argument is in ``setting.md``):

  * support > 0 and the three assumptions admitted
        -> return the functional  mu_i(t, s) = E[ Y_obs_i | A, X, T_i = t, S_i = s ]
  * support == 0
        -> refuse: the conditioning event has probability zero, the conditional expectation is
           undefined, and equation (3) of the task sheet may NOT be applied.
  * assumptions not admitted
        -> refuse: nothing is identified from the design alone.

The rule returns a *functional*, never a number: point identification is a statement about what the
population observable law determines, not an estimate. The simulator's outcome truth is never read.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from support import (
    E2_LEVELS,
    InvalidDesignError,
    UndefinedExposureError,
    degree,
    neighbours,
    support_D1_E2,
    validate_probabilities,
)

SETTING_ID = "Task02 = D1 (heterogeneous independent Bernoulli) x E2 (three-level exposure)"

IDENTIFIED_STATUS = "POINT"
REFUSED_STATUS = "REFUSED"

#: The assumptions the POINT argument consumes, exactly as stated in the task sheet.
ASSUMPTIONS = (
    "consistency: T = u implies Y_obs_i = Y_i(u)",
    "full-vector randomization: T independent of {Y_i(u)} given A, X (from the protocol)",
    "query-specific positive population support: pi_i(t, s) = P(T_i = t, S_i = s | A, X) > 0",
)

POINT_FUNCTIONAL_TEMPLATE = "mu_i(t, s) = E[ Y_obs_i | A, X, T_i = t, S_i = s ]"

SUPPORTED_REASON = "positive population support under D1 x E2"
ZERO_SUPPORT_REASON = (
    "pi_i({i}, {t}, {s}) = 0: arm (T_i = {t}, S_i = {s}) is unreachable for unit {i}, so the "
    "conditioning event has zero probability, the conditional expectation is undefined and "
    "equation (3) must not be applied."
)
UNRESOLVED_ASSUMPTION_REASON = (
    "the three design assumptions (consistency, full-vector randomization, positive population "
    "support) are not admitted yet, so no arm is identified"
)


class ZeroSupportRefusal(Exception):
    """The queried arm has zero population support, so no identification functional exists."""


class UnresolvedAssumptionsError(Exception):
    """At least one required assumption is not admitted, so the POINT route is unavailable."""


@dataclass(frozen=True)
class ArmResult:
    """Outcome of one ``(i, t, s)`` query.

    ``functional`` is a non-empty string exactly for identified arms. ``support`` is ``None`` only
    when E2 is undefined for the unit (d_i = 0), where the support cannot even be formed.
    """

    unit: int
    treatment: int
    exposure: int
    support: "float | None"
    status: str
    functional: str
    reason: str = ""

    @property
    def identified(self):
        return self.status == IDENTIFIED_STATUS


@dataclass(frozen=True)
class IdentificationResult:
    """All six arms of one unit, the assumption gate, and a status summary."""

    setting: str = SETTING_ID
    assumptions: tuple = ASSUMPTIONS
    assumptions_admitted: bool = True
    arms: tuple = ()
    diagnostics: dict = field(default_factory=dict)

    @property
    def supported_arms(self):
        return tuple(a for a in self.arms if a.identified)

    @property
    def refused_arms(self):
        return tuple(a for a in self.arms if not a.identified)

    @property
    def status(self):
        if not self.assumptions_admitted:
            return "NEEDS_INPUT"
        if not self.arms:
            return "EMPTY"
        if self.refused_arms and not self.supported_arms:
            return "UNSUPPORTED"
        return "COMPLETE"


def identify_arm(adj, ps, i, t, s, *, assumptions_admitted=True):
    """Identify mu_i(t, s) as a POINT functional.

    Raises ``ZeroSupportRefusal`` for zero-support arms and ``UnresolvedAssumptionsError`` when the
    assumptions have not been admitted. A value (0, NaN or otherwise) is never returned instead.
    """
    if t not in (0, 1) or s not in E2_LEVELS:
        raise InvalidDesignError(
            f"query must have t in (0, 1) and s in {E2_LEVELS}, got t = {t!r}, s = {s!r}."
        )
    if not assumptions_admitted:
        raise UnresolvedAssumptionsError(UNRESOLVED_ASSUMPTION_REASON)

    pi = support_D1_E2(adj, ps, i)[(t, s)]
    if pi <= 0.0:
        raise ZeroSupportRefusal(ZERO_SUPPORT_REASON.format(i=i, t=t, s=s))
    return ArmResult(int(i), int(t), int(s), float(pi), IDENTIFIED_STATUS,
                     POINT_FUNCTIONAL_TEMPLATE, SUPPORTED_REASON)


def try_identify_arm(adj, ps, i, t, s, *, assumptions_admitted=True):
    """Non-raising variant: a refusal comes back as an ``ArmResult`` with ``functional = ""``."""
    try:
        return identify_arm(adj, ps, i, t, s, assumptions_admitted=assumptions_admitted)
    except (ZeroSupportRefusal, UndefinedExposureError, UnresolvedAssumptionsError) as refusal:
        try:
            pi = float(support_D1_E2(adj, ps, i).get((int(t), int(s)), 0.0))
        except (UndefinedExposureError, InvalidDesignError):
            pi = None
        return ArmResult(int(i), int(t), int(s), pi, REFUSED_STATUS, "", str(refusal))


def identify_all_arms(adj, ps, i, *, assumptions_admitted=True):
    """Run the six arms of unit i and collect them into an ``IdentificationResult``.

    The population support is a design quantity, so it is computed even when the assumptions are
    not admitted; in that case every arm is reported as refused with status ``NEEDS_INPUT``.
    """
    validate_probabilities(ps, len(adj))
    try:
        pi = support_D1_E2(adj, ps, i)
        undefined_reason = ""
    except UndefinedExposureError as undefined:
        pi, undefined_reason = None, str(undefined)

    arms = []
    for t in (0, 1):
        for s in E2_LEVELS:
            if pi is None:
                arms.append(ArmResult(int(i), t, s, None, REFUSED_STATUS, "", undefined_reason))
            elif not assumptions_admitted:
                arms.append(ArmResult(int(i), t, s, float(pi[(t, s)]), REFUSED_STATUS, "",
                                     UNRESOLVED_ASSUMPTION_REASON))
            elif pi[(t, s)] > 0.0:
                arms.append(ArmResult(int(i), t, s, float(pi[(t, s)]), IDENTIFIED_STATUS,
                                     POINT_FUNCTIONAL_TEMPLATE, SUPPORTED_REASON))
            else:
                arms.append(ArmResult(int(i), t, s, 0.0, REFUSED_STATUS, "",
                                     ZERO_SUPPORT_REASON.format(i=i, t=t, s=s)))
    arms = tuple(arms)

    diagnostics = {
        "unit": int(i),
        "degree": degree(adj, i),
        "neighbourhood": [int(j) for j in neighbours(adj, i)],
        "supported": sum(1 for a in arms if a.identified),
        "refused": sum(1 for a in arms if not a.identified),
    }
    return IdentificationResult(assumptions_admitted=assumptions_admitted, arms=arms,
                                diagnostics=diagnostics)
