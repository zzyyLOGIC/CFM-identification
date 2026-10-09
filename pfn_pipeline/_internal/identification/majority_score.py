"""Identified-functional composition for an explicit majority-response score.

This identifies the function z -> Q_maj(z) on a predeclared allocation class.
It neither equates Q_maj with actual rollout welfare nor proves a unique argmax.
The response theorem is a named, replayed dependency, not a replacement target.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
from typing import Any

import numpy as np

from .schemas import (
    IdentificationResult, IdentificationSpec, IdentificationStatus,
    MajorityScorePolicyClassV1, NetworkMajorityPolicyScoreProgram,
    QuerySpec, TraceStep, VerificationStatus,
)
from .strict_json import canonical
from .query_gate import query_semantics_implementation_gaps
from .majority_response import (
    MajorityResponseBackend, verify_majority_response,
    _eligibility_error as response_eligibility, spec_fingerprint,
)

QUERY = "NETWORK_MAJORITY_RESPONSE_POLICY_SCORE"
TARGET = "network_majority_response_policy_score"
RULE_ID = "NETWORK_MAJORITY_SCORE_COMPOSITION_V1"
BACKEND = "network_majority_score_composition_v1"
CLASS_KEY = "majority_score_policy_class"


def _hash(obj: Any) -> str:
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def policy_class_fingerprint(policy_class: MajorityScorePolicyClassV1) -> str:
    return _hash(policy_class.model_dump(mode="json"))


def make_majority_score_spec(response_spec: IdentificationSpec, *, budget: int,
                             budget_mode: str) -> IdentificationSpec:
    """Compile a proposed score spec, preserving the response's causal assumptions.

    A response-only confirmation is deliberately NOT reused for a new score.
    The new query must be separately confirmed with its complete class fingerprint.
    """
    if response_spec.query.type != "NETWORK_RESPONSE_SURFACE":
        raise ValueError("RESPONSE_DEPENDENCY_REQUIRED")
    cls = MajorityScorePolicyClassV1(node_ids=response_spec.network_exposure.node_ids,
                                    budget=budget, budget_mode=budget_mode)
    data = response_spec.model_dump(mode="json")
    data["support_domain"][CLASS_KEY] = cls.model_dump(mode="json")
    data["query"].update(type=QUERY, authority="PROPOSED",
        policy_description="all_budget_feasible_binary_allocations",
        policy_fingerprint=policy_class_fingerprint(cls),
        interpretation_notes="Identify the majority-response score functional for every feasible allocation; not rollout welfare or an optimizer's answer.")
    return IdentificationSpec.model_validate(data)


def response_dependency(spec: IdentificationSpec) -> IdentificationSpec:
    """A subquery entailed by the approved composition; no new user intent inferred."""
    if spec.query.type != QUERY:
        raise ValueError("MAJORITY_SCORE_QUERY_REQUIRED")
    data = spec.model_dump(mode="json", warnings="error")
    if CLASS_KEY not in data["support_domain"]:
        raise ValueError("SCORE_POLICY_CLASS_REQUIRED")
    data["support_domain"].pop(CLASS_KEY)
    data["query"].update(type="NETWORK_RESPONSE_SURFACE", policy_description=None,
                         policy_fingerprint=None)
    return IdentificationSpec.model_validate(data)


def _validate(spec: IdentificationSpec) -> tuple[IdentificationSpec, MajorityScorePolicyClassV1]:
    normalized = IdentificationSpec.model_validate(spec.model_dump(mode="json", warnings="error"))
    if canonical(normalized.model_dump(mode="json")) != canonical(spec.model_dump(mode="json", warnings="error")):
        raise ValueError("NONCANONICAL_SCORE_SPEC")
    if spec.query.type != QUERY or query_semantics_implementation_gaps(spec.query):
        raise ValueError("MAJORITY_SCORE_QUERY_MISMATCH")
    cls = MajorityScorePolicyClassV1.model_validate(spec.support_domain.get(CLASS_KEY))
    if canonical(cls.model_dump(mode="json")) != canonical(spec.support_domain[CLASS_KEY]):
        raise ValueError("NONCANONICAL_SCORE_POLICY_CLASS")
    if (cls.node_ids != spec.network_exposure.node_ids
        or spec.query.policy_fingerprint != policy_class_fingerprint(cls)):
        raise ValueError("SCORE_POLICY_CLASS_BINDING_MISMATCH")
    base_spec = response_dependency(spec)
    error = response_eligibility(base_spec)
    if error:
        raise ValueError(error)
    return base_spec, cls


def _fields(spec: IdentificationSpec, cls: MajorityScorePolicyClassV1,
            base_result: IdentificationResult) -> dict:
    response = base_result.identified_functional
    target_hash = _hash({"rule": RULE_ID, "response": response.model_dump(mode="json"),
                        "policy_class": cls.model_dump(mode="json"),
                        "aggregation": "uniform_node_average"})
    program = NetworkMajorityPolicyScoreProgram(treatment=spec.query.treatment,
        outcome=spec.query.outcome, target_fingerprint=target_hash,
        response_program=response, policy_class=cls)
    return dict(status=IdentificationStatus.POINT, query=spec.query, backend=BACKEND,
        identified_functional=program, network_exposure=spec.network_exposure,
        required_population_objects=base_result.required_population_objects,
        known_design_objects=base_result.known_design_objects,
        assumptions_used=base_result.assumptions_used, guarantee="point_identified",
        validity_domain={"response_target_fingerprint": response.target_fingerprint,
            "score_target_fingerprint": target_hash, "policy_class_fingerprint": policy_class_fingerprint(cls),
            "context": response.context, "identification_scope": program.identification_scope,
            "deterministic_rollout_welfare_identified": False,
            "finite_sample_accuracy_verified": False, "optimizer_optimality_verified": False},
        certificate={"rule_id": RULE_ID, "version": "majority-score-proof-v1",
            "source_spec_sha256": spec_fingerprint(spec),
            "composition": "finite_uniform_sum_of_selected_identified_responses",
            "response_identification_result": base_result.model_dump(mode="json")})


@dataclass
class MajorityScoreBackend:
    name: str = BACKEND
    priority: int = 116
    is_fallback: bool = False

    def supports(self, spec: IdentificationSpec) -> bool:
        return spec.query.type == QUERY

    def solve(self, spec: IdentificationSpec) -> IdentificationResult:
        try:
            base_spec, cls = _validate(spec)
            base = verify_majority_response(base_spec, MajorityResponseBackend().solve(base_spec))
            if base.verification_status != VerificationStatus.VERIFIED:
                raise ValueError("RESPONSE_DEPENDENCY_NOT_VERIFIED")
            return IdentificationResult(**_fields(spec, cls, base),
                message="The requested majority-response policy score is point identified over the declared allocation class.",
                trace=[TraceStep(step="identified_functional_composition", outcome="PASS",
                    detail="For any fixed feasible z, G fixes S_i(z); a finite average of identified responses identifies Q_maj(z). No assumption that majority alone is sufficient is added.")])
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            return IdentificationResult(status=IdentificationStatus.UNSUPPORTED, query=spec.query,
                backend=BACKEND, reason_code=str(exc), message=str(exc))


def verify_majority_score(spec: IdentificationSpec, result: IdentificationResult) -> IdentificationResult:
    """No proposer/optimizer call: replay the response proof and composition bindings."""
    checked = result.model_copy(deep=True)
    try:
        base_spec, cls = _validate(spec)
        base_raw = result.certificate["response_identification_result"]
        base = IdentificationResult.model_validate(base_raw)
        base = verify_majority_response(base_spec, base)
        if base.verification_status != VerificationStatus.VERIFIED:
            raise ValueError("RESPONSE_DEPENDENCY_PROOF_REJECTED: " + base.verification_message)
        expected = IdentificationResult(**_fields(spec, cls, base))
        excluded = {"trace", "message", "verification_status", "verification_message"}
        if canonical(result.model_dump(mode="json", exclude=excluded, warnings="error")) != canonical(expected.model_dump(mode="json", exclude=excluded)):
            raise ValueError("SCORE_COMPOSITION_CERTIFICATE_MISMATCH")
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        checked.verification_status = VerificationStatus.REJECTED
        checked.verification_message = str(exc)
        return checked
    checked.verification_status = VerificationStatus.VERIFIED
    checked.verification_message = "Response dependency and score composition replayed. POINT applies to each score, not a unique policy, prediction accuracy, or true rollout welfare."
    return checked


def evaluate_score(program: NetworkMajorityPolicyScoreProgram, network, mu, allocation,
                   *, require_feasible: bool = True) -> dict:
    """Independent score calculation; neither invokes nor imports the policy runtime.

    Exact rational arithmetic is applied to supplied floating-point predictions,
    NOT to unknown population truth. Intermediate greedy states can be scored with
    require_feasible=False, but only a feasible final state may be recommended.
    """
    program = NetworkMajorityPolicyScoreProgram.model_validate(program.model_dump(mode="json", warnings="error"))
    expected_hash = _hash({"rule": RULE_ID, "response": program.response_program.model_dump(mode="json"),
        "policy_class": program.policy_class.model_dump(mode="json"), "aggregation": "uniform_node_average"})
    if program.target_fingerprint != expected_hash:
        raise ValueError("SCORE_PROGRAM_FINGERPRINT_MISMATCH")
    nodes = program.policy_class.node_ids
    if nodes != network.node_ids or program.response_program.network_fingerprint != network.semantic_fingerprint():
        raise ValueError("SCORE_NETWORK_BINDING_MISMATCH")
    values, z = np.asarray(mu), np.asarray(allocation)
    n = len(nodes)
    if (values.shape != (n, 2, 2) or values.dtype.kind not in "iuf" or not np.isfinite(values).all()
        or z.shape != (n,) or z.dtype.kind not in "biuf" or not np.isin(z, [0, 1]).all()):
        raise ValueError("INVALID_SCORE_INPUT")
    selected = int(z.sum()); cls = program.policy_class
    feasible = selected == cls.budget if cls.budget_mode == "exact" else selected <= cls.budget
    if require_feasible and not feasible:
        raise ValueError("SCORE_ALLOCATION_OUTSIDE_APPROVED_CLASS")
    index = {node: i for i, node in enumerate(nodes)}
    neighbors = [[] for _ in nodes]
    for left, right in network.undirected_edges:
        i, j = index[left], index[right]; neighbors[i].append(j); neighbors[j].append(i)
    arms = [int(sum(int(z[j]) for j in ns) > len(ns) // 2) for ns in neighbors]
    total = sum((Fraction(float(values[i, int(z[i]), arms[i]])) for i in range(n)), Fraction(0)) / n
    return {"score_target_fingerprint": program.target_fingerprint,
            "value": float(total), "prediction_score_rational": str(total),
            "majority_states": arms, "selected_count": selected, "allocation_feasible": bool(feasible),
            "value_source": "FINITE_SAMPLE_PREDICTIONS_NOT_POPULATION_TRUTH"}
