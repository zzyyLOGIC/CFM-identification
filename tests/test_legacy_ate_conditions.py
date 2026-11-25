"""Admission and independent replay regressions; no new identifying formula."""
from unittest.mock import patch

import pytest

from pfn_pipeline._internal.identification.schemas import Assumption, IdentificationSpec
from pfn_pipeline._internal.identification.identification import IdentificationEngine
from pfn_pipeline._internal.identification.verifier import IdentificationVerifier
from pfn_pipeline.identification_assumption_inventory import legacy_ate_condition_catalog


def assumption(name, *, status="ADMITTED", evidence="Explicit research declaration"):
    return Assumption(name=name, source="human_confirmation", status=status,
                      evidence=[evidence])


def spec(*, regime="experimental", p=0.5, domain=None, extras=()):
    names = ["consistency", "no_interference"]
    if regime == "experimental":
        names += ["random_assignment"] + (["positivity"] if 0 < p < 1 else [])
    return IdentificationSpec.model_validate(dict(
        structure=dict(representation_type="design_based_potential_outcomes",
                       variables=["T", "Y"], source="human_specified"),
        variable_domains={"T": {"kind": "binary"}, "Y": domain or {"kind": "binary"}},
        assumptions=[assumption(n) for n in names] + list(extras),
        information_signature={"objects": [dict(name="P(T,Y)", regime=regime, variables=["T", "Y"])]},
        query=dict(type="ATE", treatment="T", outcome="Y", authority="HUMAN_CONFIRMED"),
        support_domain={"assignment_probability": p},
    ))


def solve(s):
    return IdentificationEngine().solve_verified(s, IdentificationVerifier())


@pytest.mark.parametrize("domain", [
    {"kind": "binary"}, {"kind": "continuous", "lower": -5, "upper": 10},
    {"kind": "categorical", "values": [-2, 0, 7]},
])
def test_finite_numeric_support_entails_means_without_new_scientific_claim(domain):
    s = spec(domain=domain)
    before = s.model_dump(mode="json")
    out = solve(s)
    assert out.status == "POINT" and out.verification_status == "VERIFIED"
    assert out.validity_domain["mean_existence_basis"] == "FINITE_NUMERIC_OUTCOME_DOMAIN"
    assert "finite_conditional_first_moments" not in out.assumptions_used
    assert out.identified_functional.to_text() == "E[Y | T=1] - E[Y | T=0]"
    assert s.model_dump(mode="json") == before


@pytest.mark.parametrize("p", [0, 0.5, 1])
@pytest.mark.parametrize("domain", [
    {"kind": "continuous"}, {"kind": "continuous", "lower": 0},
    {"kind": "continuous", "upper": 100},
])
def test_missing_moments_blocks_two_arm_one_arm_and_unrestricted_claims(p, domain):
    out = solve(spec(p=p, domain=domain))
    assert out.status == "UNSUPPORTED" and out.verification_status != "VERIFIED"
    assert out.reason_code == "LEGACY_ATE_FINITE_MEANS_REQUIRED"
    assert out.identified_functional is None and out.bound_program is None


@pytest.mark.parametrize("status", ["PROPOSED", "UNRESOLVED", "NOT_ADMITTED"])
def test_pending_or_not_adopted_moments_cannot_authorize_unbounded_means(status):
    out = solve(spec(domain={"kind": "continuous"}, extras=[
        assumption("finite_conditional_first_moments", status=status)]))
    assert out.reason_code == "LEGACY_ATE_FINITE_MEANS_REQUIRED"


def test_nonblank_evidence_and_consistent_review_required_for_moments():
    a = assumption("finite_conditional_first_moments", evidence=" ")
    assert solve(spec(domain={"kind": "continuous"}, extras=[a])).status == "UNSUPPORTED"
    a = assumption("finite_conditional_first_moments", status="PROPOSED").model_copy(update={"confirmed": True})
    s = spec(domain={"kind": "continuous"})
    s.assumptions.append(a)  # Tamper after validation, as model_copy callers can.
    assert solve(s).reason_code == "LEGACY_ATE_INVALID_ASSUMPTION_RECORD"


@pytest.mark.parametrize("p,domain,status", [
    (0.5, {"kind": "continuous"}, "POINT"),
    (0, {"kind": "continuous", "lower": 0}, "PARTIAL"),
    (1, {"kind": "continuous", "upper": 100}, "PARTIAL"),
    (0, {"kind": "continuous"}, "NO_USEFUL_ID"),
    (1, {"kind": "continuous"}, "NO_USEFUL_ID"),
])
def test_explicit_moments_preserve_existing_formulas_and_support_results(p, domain, status):
    out = solve(spec(p=p, domain=domain, extras=[assumption("finite_conditional_first_moments")]))
    assert out.status == status and out.verification_status == "VERIFIED"
    assert "finite_conditional_first_moments" in out.assumptions_used
    if status == "NO_USEFUL_ID":
        assert out.identified_set == {"type": "unbounded_real_line", "lower": "-inf", "upper": "+inf"}


def test_classic_manski_preserves_formula_and_redundant_moments_are_allowed():
    base = solve(spec(regime="observational"))
    assert base.status == "PARTIAL" and base.verification_status == "VERIFIED"
    assert base.guarantee == "sharp"
    assert base.bound_program.to_text() == "[-P(Y=0,T=1)-P(Y=1,T=0), P(Y=1,T=1)+P(Y=0,T=0)]"
    out = solve(spec(regime="observational", extras=[assumption("finite_conditional_first_moments")]))
    assert out.verification_status == "VERIFIED" and out.bound_program == base.bound_program


@pytest.mark.parametrize("status", ["ADMITTED", "PROPOSED", "UNRESOLVED"])
@pytest.mark.parametrize("name", ["zero_individual_treatment_effect", "monotone_treatment_response"])
def test_manski_never_discards_adopted_or_pending_restrictions(name, status):
    out = solve(spec(regime="observational", extras=[assumption(name, status=status)]))
    assert out.reason_code == "LEGACY_ATE_UNSUPPORTED_EXTRA_ASSUMPTION"
    assert out.guarantee == "none" and out.bound_program is None


def test_explicitly_not_adopted_condition_is_not_silently_adopted_or_blocking():
    out = solve(spec(regime="observational", extras=[
        assumption("monotone_treatment_response", status="NOT_ADMITTED")]))
    assert out.status == "PARTIAL" and out.verification_status == "VERIFIED"
    assert "monotone_treatment_response" not in out.assumptions_used


@pytest.mark.parametrize("variable,lower,upper", [("Y", 0, 0), ("Y", 1, 1), ("T", 0, 0)])
def test_narrowed_binary_domains_cannot_reuse_unrestricted_completions(variable, lower, upper):
    s = spec(regime="observational")
    s.variable_domains[variable] = s.domain(variable).model_copy(update={"lower": lower, "upper": upper})
    out = solve(s)
    assert out.reason_code == "LEGACY_ATE_NARROWED_BINARY_DOMAIN"


@pytest.mark.parametrize("extra", ["support", "graph", "information"])
def test_other_structured_restrictions_are_not_dropped(extra):
    s = spec(regime="observational")
    if extra == "support":
        s.support_domain["effect_bounds"] = [0, 0]
    elif extra == "graph":
        s.structure = s.structure.model_copy(update={"representation_type": "graphical"})
    else:
        obj = s.information_signature.objects[0]
        s.information_signature.objects.append(obj.model_copy(update={"regime": "experimental"}))
    assert solve(s).status == "UNSUPPORTED"


def test_one_arm_cannot_bypass_extra_constraint_check():
    out = solve(spec(p=0, extras=[assumption("zero_individual_treatment_effect")]))
    assert out.reason_code == "LEGACY_ATE_UNSUPPORTED_EXTRA_ASSUMPTION"


@pytest.mark.parametrize("regime", ["experimental", "observational"])
def test_verifier_independently_rejects_bad_inputs_even_when_producer_gate_is_disabled(regime):
    s = (spec(domain={"kind": "continuous"}) if regime == "experimental" else
         spec(regime=regime, extras=[assumption("zero_individual_treatment_effect")]))
    with patch("pfn_pipeline._internal.identification.identification._legacy_ate_admission", return_value=None):
        raw = IdentificationEngine().solve(s)
    assert raw.status in {"POINT", "PARTIAL"}
    assert IdentificationVerifier().verify(s, raw).verification_status == "REJECTED"


def test_old_valid_certificate_cannot_be_replayed_after_adding_restrictions():
    s = spec(regime="observational")
    certificate = solve(s)
    s.assumptions.append(assumption("zero_individual_treatment_effect"))
    assert IdentificationVerifier().verify(s, certificate).verification_status == "REJECTED"


def test_moment_basis_tampering_is_rejected():
    s = spec()
    out = solve(s)
    out.validity_domain["mean_existence_basis"] = "REVIEWED_FINITE_CONDITIONAL_FIRST_MOMENTS"
    assert IdentificationVerifier().verify(s, out).verification_status == "REJECTED"


def test_catalog_explains_conditions_without_granting_admission():
    c = legacy_ate_condition_catalog()
    assert not c["formula_changed"] and not c["scientific_validity_certified_by_software"]
    assert c["mean_existence"]["one_sided_bound_is_not_sufficient"]
    assert c["closed_model"]["unhandled_adopted_or_pending_assumptions"] == "BLOCK"


@pytest.mark.parametrize("case,expected", [
    ("bounded_ate", "POINT"), ("unbounded_ate", "UNSUPPORTED"),
    ("moments_ate", "POINT"), ("manski", "PARTIAL"),
    ("extra_manski", "UNSUPPORTED"), ("narrowed_manski", "UNSUPPORTED"),
])
def test_website_research_interface_keeps_review_and_native_guards(case, expected):
    from demo.backend.math_library import run
    s = spec(regime="observational" if "manski" in case else "experimental")
    if case in {"unbounded_ate", "moments_ate"}:
        s = spec(domain={"kind": "continuous"}, extras=(
            [assumption("finite_conditional_first_moments")] if case == "moments_ate" else []))
    if case == "extra_manski":
        s.assumptions.append(assumption("zero_individual_treatment_effect"))
    if case == "narrowed_manski":
        s.variable_domains["Y"] = s.domain("Y").model_copy(update={"upper": 0})
    request = dict(operation="population", problem={"spec": s.model_dump(mode="json")})
    pending = run(request)
    assert pending["state"] == "REVIEW_REQUIRED" and not pending["backend_called"]
    sheet = pending["worksheet"]
    request["review"] = dict(binding=sheet["binding"], decisions=dict.fromkeys(sheet["items"], "ACCEPTED"),
                             reviewer="Synthetic acceptance", evidence="Frozen formal input, not an LLM reply")
    out = run(request)
    assert out["state"] == expected and not out["estimation_handoff_allowed"]
    assert (out["result"]["verification_status"] == "VERIFIED") == (expected != "UNSUPPORTED")


def test_website_condition_query_includes_legacy_catalog_without_admission():
    from demo.backend.math_library import run
    out = run(dict(operation="requirements", problem={}))
    assert out["state"] == "DIAGNOSTIC" and not out["estimation_handoff_allowed"]
    assert out["result"]["legacy_ate_catalog"] == legacy_ate_condition_catalog()
