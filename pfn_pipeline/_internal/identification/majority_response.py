"""Population identification of design-standardized network response arms.

The theorem does *not* assume that treated-neighbor count or the majority label is
a sufficient causal exposure.  The target itself is defined by standardizing over
the known assignment design within the majority grouping.  Under a fixed
pre-treatment network, known iid Bernoulli assignment, full-vector randomization,
consistency and positive arm support, each arm mean is a functional of the
experimental population law.

This module is graph-size agnostic: the current shared repository happens to ship
a default fixed ER graph, but the theorem is instantiated from the TaskSpec/network
that Estimation and Policy are already using.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from math import comb

from .schemas import (
    Assumption, AssumptionStatus, IdentificationResult, IdentificationSpec, IdentificationStatus,
    InformationObject, InformationSignature, InterferenceStructureReceipt,
    MajorityResponseTheoremContractV1, NetworkExposureSpec,
    NetworkMajorityResponseProgram, QuerySpec, StructureSpec, TraceStep,
    VariableDomain, VerificationStatus, interference_structure_semantic_fingerprint,
)
from .query_gate import query_semantics_implementation_gaps, TRUSTED_QUERY_AUTHORITIES
from .rational_arithmetic import fraction

RULE_ID = "NETWORK_MAJORITY_DESIGN_AVERAGE_V1"
BACKEND = "network_majority_design_average_v1"
# Exact count tables scale with degree, not with the 2**N full assignments.
# This bounded workload covers the shared dense ER300 graph and dense N=300.
MAX_MAJORITY_DEGREE = 512
REQUIRED = (
    "known_assignment_law",
    "full_vector_randomization",
    "consistency",
    "fixed_pretreatment_network",
    "finite_conditional_first_moments",
)
ASSUMPTION_DETAILS = (
    "The experiment uses a known iid Bernoulli(p) assignment law for all nodes in the declared fixed network.",
    "Conditional on the full pre-treatment network context W and fixed G, the complete assignment vector is independent of the complete potential-outcome schedule.",
    "For the realized full assignment vector T, the observed outcome equals the corresponding potential outcome Y_i(T). No exposure-sufficiency restriction is added.",
    "The supplied undirected network and node order are fixed before treatment and are used to define the target grouping S_i(T).",
    "Conditional first absolute moments of all potential outcomes entering the design-standardized target are finite.",
)


def _hash(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def response_target_fingerprint(network: NetworkExposureSpec,
                                contract: MajorityResponseTheoremContractV1) -> str:
    return _hash({"network": network.model_dump(mode="json", warnings="error"),
                  "contract": contract.model_dump(mode="json", warnings="error"),
                  "p_rational": str(fraction(contract.design.p)),
                  "arms": [[0, 0], [0, 1], [1, 0], [1, 1]]})


def spec_fingerprint(spec: IdentificationSpec) -> str:
    return _hash(spec.model_dump(mode="json", warnings="error"))


def make_majority_response_spec(
    network: NetworkExposureSpec, *, assignment_probability: str | float = "1/2",
    source: str, evidence: str, admitted: bool = False,
    query_authority: str = "PROPOSED", synthetic: bool = False,
    outcome_kind: str = "continuous",
) -> IdentificationSpec:
    """Construct an explicit spec, never infer design/causal assumptions from D_n.

    ``admitted=True`` is a caller's domain-assumption declaration, not empirical
    verification. Query confirmation remains a separate step. Synthetic=True must
    only be used for a documented simulator, never for arbitrary uploaded data.
    """
    if not source.strip() or not evidence.strip():
        raise ValueError("source and qualification evidence are required")
    if query_authority == "TRUSTED_FIXTURE" and not synthetic:
        raise ValueError("TRUSTED_FIXTURE is reserved for documented synthetic fixtures")
    contract = MajorityResponseTheoremContractV1(design={"p": assignment_probability})
    query = QuerySpec(
        type="NETWORK_RESPONSE_SURFACE", treatment="treatment", outcome="outcome",
        target_population="fixed_network_conditional_context",
        reference_exposure_definition="treated_neighbor_count_1hop",
        target_exposure_semantics="design_averaged_majority_response",
        response_target_fingerprint=response_target_fingerprint(network, contract),
        authority=query_authority, evidence=[evidence],
        interpretation_notes=(
            "Identify all four design-standardized majority-arm means. The majority label is a target grouping under the assignment design, not an asserted sufficient causal exposure."
        ),
    )
    receipt = InterferenceStructureReceipt(
        provider_id="declared_fixed_network_grouping_v1",
        source_status="SYNTHETIC_GROUND_TRUTH" if synthetic else "EXPERT_PROVIDED",
        analysis_status="ACCEPTED_AS_ASSUMPTION" if admitted else "UNRESOLVED",
        semantic_fingerprint=interference_structure_semantic_fingerprint(network, None, "UNSPECIFIED"),
        provenance={"source": source}, qualification_evidence=[evidence],
    )
    return IdentificationSpec(
        structure=StructureSpec(representation_type="fixed_network_interference",
                                variables=["treatment", "majority_exposure", "outcome", "context"],
                                source="human_specified",
                                notes="unit-level fixed network; no variable-level causal DAG required for the randomized route"),
        network_exposure=network, exposure_mapping_claim="UNSPECIFIED",
        interference_structure_receipt=receipt,
        majority_response_theorem_contract=contract,
        variable_domains={"treatment": VariableDomain(kind="binary", values=[0, 1]),
                          "outcome": VariableDomain(kind=outcome_kind, **({"values": [0, 1]} if outcome_kind == "binary" else {}))},
        assumptions=[Assumption(
            name=name,
            source=(
                "deterministic_derivation" if synthetic and name == "finite_conditional_first_moments"
                else "study_protocol" if synthetic and name in {"known_assignment_law", "full_vector_randomization", "fixed_pretreatment_network"}
                else "demo_specification" if synthetic
                else "domain_knowledge"
            ),
            status=(
                AssumptionStatus.UNRESOLVED if not admitted
                else AssumptionStatus.CERTIFIED if synthetic and name != "finite_conditional_first_moments"
                else AssumptionStatus.DERIVED if synthetic and name == "finite_conditional_first_moments"
                else AssumptionStatus.ADMITTED if admitted
                else AssumptionStatus.UNRESOLVED
            ),
            evidence=[evidence],
            details=detail + " Source: " + source,
        ) for name, detail in zip(REQUIRED, ASSUMPTION_DETAILS)],
        information_signature=InformationSignature(objects=[InformationObject(
            name="P_exp(Y_i,T_i,S_i|W,G)", regime="experimental",
            variables=["treatment", "majority_exposure", "outcome", "context"],
            description="Node-indexed conditional population laws in repeated experiments at fixed full network context; no numerical o is supplied.")]),
        query=query,
        support_domain={"analysis_unit": ["node"], "context_symbol": "W",
                        "context_semantics": "full_pretreatment_network_context",
                        "target_context_distribution": "conditional_not_transport"},
        provenance={"mode": "synthetic_source_contract" if synthetic else "expert_assumption_contract",
                    "source": source, "population_values": "not_supplied",
                    "finite_sample_status": "not_used_to_confirm_causal_assumptions"},
    )


def _eligibility_error(spec: IdentificationSpec) -> str | None:
    q, net, contract = spec.query, spec.network_exposure, spec.majority_response_theorem_contract
    if q.type != "NETWORK_RESPONSE_SURFACE" or contract is None:
        return "MAJORITY_RESPONSE_CONTRACT_REQUIRED"
    if q.resolution != "RESOLVED" or q.authority not in TRUSTED_QUERY_AUTHORITIES:
        return "QUERY_NOT_CONFIRMED"
    if query_semantics_implementation_gaps(q):
        return "MAJORITY_RESPONSE_QUERY_MISMATCH"
    if spec.structure.representation_type != "fixed_network_interference" or spec.structure.directed_edges or spec.structure.bidirected_edges:
        return "VARIABLE_GRAPH_CONSTRAINTS_NOT_SUPPORTED_BY_MAJORITY_RULE"
    if not isinstance(net, NetworkExposureSpec) or not net.fixed_network:
        return "FIXED_COUNT_NETWORK_REQUIRED"
    # The target is design-standardized within majority groups.  Therefore this
    # theorem does not require the majority/count mapping to be a sufficient
    # causal exposure.  Exposure-structure uncertainty is simply irrelevant to
    # this particular target rather than silently treated as resolved.
    if spec.exposure_uncertainty is not None:
        return "EXPOSURE_UNCERTAINTY_NOT_PART_OF_THIS_TARGET_CONTRACT"
    if (spec.network_policy_mixture_theorem_contract is not None
        or spec.network_policy_mixture_population_facts is not None
        or spec.deterministic_policy_oracle is not None
        or spec.reference_exposure_propensity_upper_bound_fact is not None):
        return "MIXED_THEOREM_CONTRACTS_NOT_SUPPORTED"
    if spec.assumption_conflicts:
        return "UNRESOLVED_ASSUMPTION_CONFLICT"
    if not set(REQUIRED) <= spec.confirmed_assumptions():
        return "REQUIRED_ASSUMPTIONS_NOT_ADMITTED"
    receipt = spec.interference_structure_receipt
    if receipt is None or not receipt.executable() or receipt.analysis_status != "ACCEPTED_AS_ASSUMPTION":
        return "I1_STRUCTURE_NOT_ADMITTED"
    if receipt.semantic_fingerprint != interference_structure_semantic_fingerprint(
            net, None, spec.exposure_mapping_claim or "UNSPECIFIED"):
        return "I1_FINGERPRINT_MISMATCH"
    if q.response_target_fingerprint != response_target_fingerprint(net, contract):
        return "DESIGN_DEPENDENT_TARGET_FINGERPRINT_MISMATCH"
    domain = spec.domain(q.treatment)
    if domain is None or domain.kind != "binary" or set(domain.values or ()) != {0, 1}:
        return "BINARY_TREATMENT_REQUIRED"
    if spec.domain(q.outcome) is None or spec.domain(q.outcome).kind not in {"continuous", "binary"}:
        return "INTEGRABLE_NUMERIC_OUTCOME_REQUIRED"
    if not spec.information_signature.contains_variables([q.treatment, q.outcome, "majority_exposure", "context"], regime="experimental"):
        return "CONDITIONAL_MAJORITY_POPULATION_INFORMATION_REQUIRED"
    expected_domain = {"analysis_unit": ["node"], "context_symbol": "W",
                       "context_semantics": "full_pretreatment_network_context",
                       "target_context_distribution": "conditional_not_transport"}
    if spec.support_domain != expected_domain:
        return "CONTEXT_DOMAIN_NOT_SUPPORTED"
    degrees = net.degree_map()
    p = fraction(contract.design.p)
    if (not 0 < p < 1 or min(degrees.values()) < 1):
        return "MAJORITY_ARMS_REQUIRE_POSITIVE_DESIGN_AND_NONISOLATED_NODES"
    if len(net.node_ids) > 4096 or max(degrees.values()) > MAX_MAJORITY_DEGREE or max(p.numerator.bit_length(), p.denominator.bit_length()) > 64:
        return "MAJORITY_RULE_RESOURCE_LIMIT"
    return None


def _count_weights(degree: int, p: Fraction, *, independent: bool) -> dict:
    # Two computational paths; verifier never calls proposer or a backend solver.
    if independent:
        # Adjacent binomial-mass ratios give an independent O(degree) replay.
        # All operations remain rational; no floating-point tolerance is used.
        mass = [(1 - p) ** degree]
        for k in range(degree):
            mass.append(mass[-1] * (degree - k) * p / ((k + 1) * (1 - p)))
    else:
        mass = [comb(degree, k) * p**k * (1-p)**(degree-k) for k in range(degree+1)]
    weights, joint = {}, {}
    for s in (0, 1):
        ks = [k for k in range(degree+1) if int(k > degree//2) == s]
        denom = sum((mass[k] for k in ks), Fraction(0))
        weights[str(s)] = [str(mass[k]/denom) if k in ks else "0" for k in range(degree+1)]
        for a in (0, 1):
            joint[f"{a},{s}"] = str((p if a else 1-p) * denom)
    return {"conditional_count_weights": weights, "joint_own_treatment_arm_probabilities": joint}


def expected_program(spec: IdentificationSpec) -> NetworkMajorityResponseProgram:
    return NetworkMajorityResponseProgram(
        treatment=spec.query.treatment, outcome=spec.query.outcome,
        target_fingerprint=spec.query.response_target_fingerprint,
        network_fingerprint=spec.network_exposure.semantic_fingerprint(),
        assignment_probability_rational=str(fraction(spec.majority_response_theorem_contract.design.p)),
    )


def _expected_fields(spec: IdentificationSpec, *, independent: bool) -> dict:
    program = expected_program(spec)
    unique_degrees = sorted(set(spec.network_exposure.degree_map().values()))
    p = fraction(spec.majority_response_theorem_contract.design.p)
    tables = {str(d): _count_weights(d, p, independent=independent) for d in unique_degrees}
    return dict(
        status=IdentificationStatus.POINT, query=spec.query, backend=BACKEND,
        identified_functional=program, network_exposure=spec.network_exposure,
        required_population_objects=[f"E_exp[{spec.query.outcome}_i|{spec.query.treatment}_i=a,S_i=s,W,G], all i,a,s"],
        known_design_objects=[f"iid_Bernoulli(p={p})", "P(K_i=k|S_i=s,G,p)", "P(T_i=a,S_i=s|G,p)"],
        assumptions_used=list(REQUIRED), guarantee="point_identified",
        validity_domain={"network_fingerprint": program.network_fingerprint,
                         "target_fingerprint": program.target_fingerprint,
                         "context": program.context, "grouping": program.grouping,
                         "causal_target": program.semantics,
                         "numerical_population_values_supplied": False,
                         "estimator_accuracy_verified": False,
                         "deterministic_policy_value_identified": False},
        certificate={"rule_id": RULE_ID, "version": "majority-response-proof-v1",
                     "source_spec_sha256": spec_fingerprint(spec), "design_by_degree": tables},
    )


def _failure(spec: IdentificationSpec, reason: str) -> IdentificationResult:
    return IdentificationResult(status=IdentificationStatus.UNSUPPORTED, query=spec.query,
                                backend=BACKEND, reason_code=reason, message=reason)


@dataclass
class MajorityResponseBackend:
    name: str = BACKEND
    priority: int = 115
    is_fallback: bool = False

    def supports(self, spec: IdentificationSpec) -> bool:
        return spec.query.type == "NETWORK_RESPONSE_SURFACE"

    def solve(self, spec: IdentificationSpec) -> IdentificationResult:
        error = _eligibility_error(spec)
        if error:
            return _failure(spec, error)
        return IdentificationResult(**_expected_fields(spec, independent=False),
            message=(
                "All four design-standardized local response arms are point identified under the declared randomized network experiment; no numerical estimate or actual fixed-allocation rollout welfare is certified."
            ),
            trace=[
                TraceStep(step="target_semantics", outcome="PASS",
                          detail="S_i is used only to define a design-standardized grouping; no count/majority exposure-sufficiency assumption is used."),
                TraceStep(step="randomization_identification", outcome="PASS",
                          detail="Known assignment law + full-vector randomization + consistency identify E[Y_i^obs | T_i=a,S_i=s,W,G] for every positive-support arm."),
            ])


def verify_majority_response(spec: IdentificationSpec, result: IdentificationResult) -> IdentificationResult:
    """Replay all semantic fields and exact weights; numeric estimates never enter."""
    checked = result.model_copy(deep=True)
    try:
        normalized = IdentificationSpec.model_validate(spec.model_dump(mode="python", warnings="error"))
        # Mutation cannot bypass pydantic validators or leave stale query expressions.
        if normalized.model_dump(mode="json", warnings="error") != spec.model_dump(mode="json", warnings="error"):
            raise ValueError("Non-canonical mutated specification")
        error = _eligibility_error(normalized)
        if error:
            raise ValueError(error)
        expected = IdentificationResult(**_expected_fields(normalized, independent=True))
        ignored = {"trace", "message", "verification_status", "verification_message"}
        if checked.model_dump(mode="json", exclude=ignored, warnings="error") != expected.model_dump(mode="json", exclude=ignored, warnings="error"):
            raise ValueError("Result/program/certificate differs from the independently replayed contract")
    except (ValueError, TypeError, KeyError, AttributeError, ZeroDivisionError) as exc:
        checked.verification_status = VerificationStatus.REJECTED
        checked.verification_message = str(exc)
        return checked
    checked.verification_status = VerificationStatus.VERIFIED
    checked.verification_message = (
        "Design-standardized randomized-network identification rule and exact design weights replayed; "
        "the replay verifies the declared contract, not the truth of domain assumptions or finite-sample estimator accuracy."
    )
    return checked


def confirm_response_query(spec: IdentificationSpec, fingerprint: str) -> IdentificationSpec:
    """Confirm only an exact reviewed proposal, never its causal assumptions."""
    import hmac
    from .query_confirmation import query_confirmation_fingerprint
    confirmed = IdentificationSpec.model_validate(spec.model_dump(mode="python", warnings="error"))
    q = confirmed.query
    if (q.type not in {"NETWORK_RESPONSE_SURFACE", "NETWORK_MAJORITY_RESPONSE_POLICY_SCORE"} or q.authority != "PROPOSED"
        or q.resolution != "RESOLVED" or not q.evidence or q.alternatives
        or not hmac.compare_digest(query_confirmation_fingerprint(q), fingerprint.strip().lower())):
        raise ValueError("QUERY_CONFIRMATION_MISMATCH: inspect the current formal query and fingerprint")
    q.authority = "HUMAN_CONFIRMED"
    confirmed.provenance["query_confirmation"] = "Explicit user-confirmed exact qf2; not confirmation of causal assumptions"
    return confirmed
