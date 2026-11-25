"""Admission checks for the three legacy unit-level ATE rules.

No identifying formula lives here. A sharp completion rule must not discard
unhandled restrictions. The verifier implements its own checks independently.
"""
import math

from .schemas import Assumption, AssumptionStatus


MOMENTS = "finite_conditional_first_moments"
BASE_ATE = frozenset({"consistency", "no_interference"})
SHARP_SUPPORT_FIELDS = frozenset({"assignment_probability", "analysis_unit"})


def assumption_error(spec):
    if spec.assumption_conflicts:
        return "LEGACY_ATE_ASSUMPTION_CONFLICT"
    seen = {}
    for a in spec.assumptions:
        try:
            restored = Assumption.model_validate(a.model_dump(mode="json"))
        except (TypeError, ValueError):
            return "LEGACY_ATE_INVALID_ASSUMPTION_RECORD"
        if restored != a:
            return "LEGACY_ATE_INVALID_ASSUMPTION_RECORD"
        if a.status == AssumptionStatus.CONTRADICTED:
            return "LEGACY_ATE_ASSUMPTION_CONFLICT"
        state = ("ACCEPTED" if a.confirmed else a.status, a.confirmed)
        if a.name in seen and seen[a.name] != state:
            return "LEGACY_ATE_ASSUMPTION_CONFLICT"
        seen[a.name] = state
    return None


def moment_basis(spec):
    """Finite numeric support entails integrability; one-sided support does not."""
    domain = spec.domain(spec.query.outcome)
    if domain is None:
        return None
    bounds = (domain.lower, domain.upper)
    if any(v is not None and math.isnan(float(v)) for v in bounds):
        return None
    if domain.lower == math.inf or domain.upper == -math.inf:
        return None
    if all(v is not None for v in bounds) and domain.lower > domain.upper:
        return None
    if domain.kind == "binary" and set(domain.values or []) == {0, 1}:
        return "FINITE_NUMERIC_OUTCOME_DOMAIN"
    if domain.kind == "categorical":
        values = domain.values or []
        if values and all(type(v) in (int, float) and math.isfinite(v) for v in values):
            return "FINITE_NUMERIC_OUTCOME_DOMAIN"
        return None
    if domain.kind != "continuous":
        return None
    if all(v is not None and math.isfinite(float(v)) for v in bounds):
        return "FINITE_NUMERIC_OUTCOME_DOMAIN"
    if any(a.name == MOMENTS and a.confirmed and any(e.strip() for e in a.evidence)
           for a in spec.assumptions):
        return "REVIEWED_FINITE_CONDITIONAL_FIRST_MOMENTS"
    return None


def sharp_model_error(spec, *, regime):
    """Closed model used by classical endpoint completions, not general bounds."""
    allowed = BASE_ATE | {MOMENTS}
    if regime == "experimental":
        allowed |= {"random_assignment"}
    for a in spec.assumptions:
        # A rejected proposal is not an adopted model restriction. Pending
        # restrictions, in contrast, cannot silently disappear from a model.
        if a.name not in allowed and a.status != AssumptionStatus.NOT_ADMITTED:
            return "LEGACY_ATE_UNSUPPORTED_EXTRA_ASSUMPTION: " + a.name
    if set(spec.support_domain) - SHARP_SUPPORT_FIELDS:
        return "LEGACY_ATE_UNSUPPORTED_SUPPORT_RESTRICTION"
    if (spec.structure.representation_type not in {"design_based_potential_outcomes", "unspecified"}
            or spec.structure.directed_edges or spec.structure.bidirected_edges
            or spec.network_exposure is not None):
        return "LEGACY_ATE_UNSUPPORTED_STRUCTURAL_RESTRICTION"
    expected = {spec.query.treatment, spec.query.outcome}
    for obj in spec.information_signature.objects:
        if (obj.regime != regime or set(obj.variables) != expected
                or any(v is not None for v in (obj.basis, obj.joint_scope,
                    obj.outcome_representation, obj.whole_network_assignment_law_available,
                    obj.randomized_arm_observable))):
            return "LEGACY_ATE_UNSUPPORTED_EXTRA_INFORMATION"
    for variable in expected:
        domain = spec.domain(variable)
        if domain is None:
            return "LEGACY_ATE_OUTCOME_DOMAIN_REQUIRED"
        if domain.kind == "binary":
            if (set(domain.values or []) != {0, 1}
                    or domain.lower is not None and not domain.lower <= 0
                    or domain.upper is not None and not domain.upper >= 1):
                return "LEGACY_ATE_NARROWED_BINARY_DOMAIN"
        elif variable == spec.query.outcome:
            # One-arm interval completion does not implement discrete supports.
            if domain.kind != "continuous" or domain.values is not None:
                return "LEGACY_ATE_UNSUPPORTED_OUTCOME_SUPPORT"
    return None
