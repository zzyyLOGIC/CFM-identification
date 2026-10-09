from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from pydantic import ValidationError
from fractions import Fraction
from . import network_mixture_exact as exact
from .rational_arithmetic import fraction, display, dot, matvec, transpose

from .schemas import (
    CandidateMixtureIdentificationCertificateV1,
    ClosedIntervalV1,
    FarkasIncompatibilityCertificateV1,
    FiniteCategoricalNetworkExposureSpec,
    FiniteExposureCandidateSetSpec,
    FiniteLocalExposureMappingSpec,
    FiniteUnionClosedIntervalsV1,
    IdentificationResult,
    IdentificationSpec,
    IdentificationStatus,
    LPDualWitnessV1,
    LPPrimalWitnessV1,
    NetworkPolicyBinaryMeanPopulationTruthV1,
    NetworkPolicyFiniteMixtureSetProgram,
    NetworkPolicyMixtureProofBundleV1,
    RowSpacePointCertificateV1,
    TraceStep,
    VerificationStatus,
)


THEOREM_RULE_ID = "NETWORK_POLICY_FINITE_MIXTURE_ID_V1"
BACKEND_ID = "finite_local_exposure_policy_value_v1"
NUMERIC_POLICY_VERSION = "p1-rational-v2"
RESIDUAL_ATOL = 1e-8
RESIDUAL_RTOL = 1e-8
TOPOLOGY_AMBIGUITY_BAND = 1e-7


class NetworkPolicyMixtureUnsupported(RuntimeError):
    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


@dataclass(frozen=True)
class CanonicalMixtureLPV1:
    candidate_id: str
    A: np.ndarray
    b: np.ndarray
    q: np.ndarray
    variable_order: tuple[str, ...]
    matrix_fingerprint: str
    rhs_fingerprint: str
    query_fingerprint: str
    variable_order_fingerprint: str
    exact_lp: exact.RationalLP | None = None


@dataclass(frozen=True)
class NetworkPolicyMixtureOracleRunV1:
    proposed: IdentificationResult
    verified: IdentificationResult


def _fingerprint_payload(value: object) -> str:
    if isinstance(value, np.ndarray):
        payload = value.tolist()
    else:
        payload = value
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _spec_fingerprint(spec: IdentificationSpec) -> str:
    # Keep the frozen v0.2.19 P1 proof identity when unrelated optional v0.2.20
    # fields are absent. Non-null new semantics are NEVER dropped from the hash.
    payload = spec.model_dump(mode="json")
    if payload.get("majority_response_theorem_contract") is None:
        payload.pop("majority_response_theorem_contract", None)
    if payload["query"].get("response_target_fingerprint") is None:
        payload["query"].pop("response_target_fingerprint", None)
    return _fingerprint_payload(payload)


def _exact_set_fingerprint(exact: FiniteUnionClosedIntervalsV1 | None) -> str | None:
    return None if exact is None else _fingerprint_payload(exact.model_dump(mode="json"))


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= RESIDUAL_ATOL + RESIDUAL_RTOL * max(abs(a), abs(b))


def _candidate_family(spec: IdentificationSpec) -> tuple[FiniteCategoricalNetworkExposureSpec, FiniteExposureCandidateSetSpec]:
    network = spec.network_exposure
    uncertainty = spec.exposure_uncertainty
    if not isinstance(network, FiniteCategoricalNetworkExposureSpec):
        raise NetworkPolicyMixtureUnsupported(
            "UNSUPPORTED_NETWORK_EXPOSURE",
            "P1 exact oracle requires FiniteCategoricalNetworkExposureSpec.",
        )
    if not isinstance(uncertainty, FiniteExposureCandidateSetSpec):
        raise NetworkPolicyMixtureUnsupported(
            "UNSUPPORTED_EXPOSURE_UNCERTAINTY",
            "P1 exact oracle requires a finite enumerated candidate exposure family.",
        )
    return network, uncertainty


def _validate_applicability(spec: IdentificationSpec, truth: NetworkPolicyBinaryMeanPopulationTruthV1 | None) -> None:
    # None compiles the population program only. It never inserts a fake o.
    # Shape/value checks run separately when reference or estimated objects bind.
    if spec.query.type != "POLICY_VALUE":
        raise NetworkPolicyMixtureUnsupported("UNSUPPORTED_QUERY", "P1 exact oracle supports only POLICY_VALUE.")
    if spec.query.authority not in {"TRUSTED_FIXTURE", "HUMAN_CONFIRMED"}:
        raise NetworkPolicyMixtureUnsupported(
            "UNTRUSTED_QUERY_SEMANTICS", "POLICY_VALUE query must be trusted or human-confirmed."
        )
    if spec.network_policy_mixture_theorem_contract is None:
        raise NetworkPolicyMixtureUnsupported("MISSING_THEOREM_CONTRACT", "Missing frozen theorem contract.")
    if spec.query.resolution != "RESOLVED" or spec.query.alternatives:
        raise NetworkPolicyMixtureUnsupported("QUERY_NOT_RESOLVED", "Resolve all query alternatives before execution.")
    policy = spec.deterministic_policy_oracle
    if policy is None or spec.query.policy_fingerprint != policy.semantic_fingerprint():
        raise NetworkPolicyMixtureUnsupported("POLICY_QUERY_BINDING_MISMATCH", "The confirmed query must bind the complete policy table fingerprint.")
    if (spec.query.target_population != "overall_population" or spec.query.conditioning_variables
        or spec.query.exposure_value is not None or spec.query.target_exposure_semantics is not None
        or spec.query.reference_exposure_definition != "finite_local_exposure_table_v1"
        or spec.query.response_target_fingerprint is not None):
        raise NetworkPolicyMixtureUnsupported("UNSUPPORTED_QUERY_SEMANTICS", "P1 requires an overall-population fixed-policy query, not a fixed-exposure or subgroup target.")
    if spec.assumption_conflicts:
        raise NetworkPolicyMixtureUnsupported("ASSUMPTION_CONFLICT", "Resolve assumption conflicts before execution.")
    if spec.network_policy_mixture_population_facts is not None or spec.reference_exposure_propensity_upper_bound_fact is not None:
        raise NetworkPolicyMixtureUnsupported("UNMODELED_POPULATION_RESTRICTION", "Embedded legacy facts cannot be silently ignored by this exact oracle.")
    if spec.structure.directed_edges or spec.structure.bidirected_edges:
        raise NetworkPolicyMixtureUnsupported("UNMODELED_STRUCTURAL_RESTRICTION", "Variable-DAG restrictions are outside this marginal-only model class.")
    if any(a.confirmed and (a.source == "llm_candidate" or a.name not in {"random_assignment", "consistency"}) for a in spec.assumptions):
        raise NetworkPolicyMixtureUnsupported("UNSUPPORTED_ADDITIONAL_ASSUMPTION", "No extra response restrictions or LLM-approved assumptions may be ignored.")
    confirmed = spec.confirmed_assumptions()
    for required in ("random_assignment", "consistency"):
        if required not in confirmed:
            raise NetworkPolicyMixtureUnsupported(
                "MISSING_CONFIRMED_ASSUMPTION", f"P1 v1 requires confirmed assumption: {required}."
            )
    design = spec.network_policy_mixture_assignment_design
    if design is None or not (0 < fraction(design.p) < 1):
        raise NetworkPolicyMixtureUnsupported(
            "UNSUPPORTED_ASSIGNMENT_DESIGN", "P1 v1 requires homogeneous iid Bernoulli assignment with 0<p<1."
        )
    info = spec.network_policy_mixture_information_contract
    if info is None or info.basis != "NODE_CONTEXT_WORKING_EXPOSURE_BINARY_MEAN_V1":
        raise NetworkPolicyMixtureUnsupported("UNSUPPORTED_INFORMATION_BASIS", "Frozen node-local binary-mean basis is required.")
    has_typed_local_object = any(
        obj.regime == "experimental"
        and obj.basis == "NODE_CONTEXT_WORKING_EXPOSURE_BINARY_MEAN_V1"
        and obj.joint_scope == "node_local_marginals_only"
        and obj.outcome_representation == "binary_mean_complete"
        for obj in spec.information_signature.objects
    )
    if not has_typed_local_object:
        raise NetworkPolicyMixtureUnsupported(
            "UNSUPPORTED_INFORMATION_BASIS",
            "InformationSignature must explicitly declare the frozen node-local binary-mean basis.",
        )
    refined_full_info = any(
        obj.basis == "WHOLE_NETWORK_ASSIGNMENT_LAW_V1"
        or obj.joint_scope == "whole_network_assignment"
        or obj.whole_network_assignment_law_available is True
        for obj in spec.information_signature.objects
    )
    if refined_full_info:
        raise NetworkPolicyMixtureUnsupported(
            "REFINED_INFORMATION_ROUTE_DOMINATES",
            "Whole-network assignment-law information is declared available; the local coarsened route must not determine the final status.",
        )
    if any(not (obj.regime == "experimental" and obj.basis == "NODE_CONTEXT_WORKING_EXPOSURE_BINARY_MEAN_V1"
                    and obj.joint_scope == "node_local_marginals_only"
                    and obj.outcome_representation == "binary_mean_complete"
                    and obj.whole_network_assignment_law_available is False)
           for obj in spec.information_signature.objects):
        raise NetworkPolicyMixtureUnsupported("UNSUPPORTED_ADDITIONAL_INFORMATION", "Unmodeled information cannot be dropped when claiming the exact identified set.")
    if spec.variable_domains.get(spec.query.treatment) is None or spec.variable_domains[spec.query.treatment].kind != "binary":
        raise NetworkPolicyMixtureUnsupported("UNSUPPORTED_TREATMENT_DOMAIN", "Treatment must be binary.")
    if spec.variable_domains.get(spec.query.outcome) is None or spec.variable_domains[spec.query.outcome].kind != "binary":
        raise NetworkPolicyMixtureUnsupported("UNSUPPORTED_OUTCOME_DOMAIN", "Outcome must be binary.")
    policy = spec.deterministic_policy_oracle
    if policy is None:
        raise NetworkPolicyMixtureUnsupported("MISSING_POLICY_TABLE", "Deterministic context-indexed policy table is required.")
    network, uncertainty = _candidate_family(spec)
    if spec.structure.representation_type != "fixed_network_interference" or not network.fixed_network:
        raise NetworkPolicyMixtureUnsupported("UNSUPPORTED_STRUCTURAL_SEMANTICS", "The finite oracle requires an explicitly fixed interference graph.")
    if spec.exposure_mapping_claim != "REFERENCE_WITH_UNCERTAINTY":
        raise NetworkPolicyMixtureUnsupported("UNMODELED_EXPOSURE_CLAIM", "The finite candidate family, not an additional assertion that the working mapping is sufficient, defines the admitted structures.")
    expected_vars={"W", "C", spec.query.treatment, spec.query.outcome}
    if len(expected_vars) != 4 or set(spec.structure.variables) != expected_vars:
        raise NetworkPolicyMixtureUnsupported("VARIABLE_BINDING_MISMATCH", "W, C, treatment and outcome must be distinct and exhaust the frozen variable universe.")
    if any(set(obj.variables) != expected_vars for obj in spec.information_signature.objects):
        raise NetworkPolicyMixtureUnsupported("INFORMATION_VARIABLE_BINDING_MISMATCH", "Population information must bind W, working C, the queried treatment and outcome.")
    if set(spec.variable_domains) != {spec.query.treatment, spec.query.outcome}:
        raise NetworkPolicyMixtureUnsupported("UNMODELED_DOMAIN_RESTRICTION", "The frozen route supports explicit binary treatment/outcome domains only.")
    if any(d.lower != 0 or d.upper != 1 for d in spec.variable_domains.values()):
        raise NetworkPolicyMixtureUnsupported("UNMODELED_DOMAIN_RESTRICTION", "Binary domains must be exactly {0,1}; extra outcome restrictions must not be ignored.")
    if set(spec.support_domain) - {"analysis_unit", "business_entity_binding"}:
        raise NetworkPolicyMixtureUnsupported("UNMODELED_SUPPORT_RESTRICTION", "Additional support restrictions need a separately implemented theorem.")
    if spec.support_domain.get("analysis_unit", ["node"]) != ["node"]:
        raise NetworkPolicyMixtureUnsupported("ANALYSIS_UNIT_BINDING_MISMATCH", "P1 uses the fixed network node as analysis unit.")
    binding=spec.support_domain.get("business_entity_binding")
    if binding is not None and binding != {"business_analysis_unit":"node", "network_entity":"node_id", "binding":"fixed_snapshot_identity"}:
        raise NetworkPolicyMixtureUnsupported("ANALYSIS_UNIT_BINDING_MISMATCH", "Only the explicit fixed-snapshot node identity binding is supported.")
    if truth is not None and set(truth.context_weights) != set(policy.context_ids):
        raise NetworkPolicyMixtureUnsupported("POPULATION_TRUTH_CONTEXT_MISMATCH", "Population truth contexts do not match policy contexts.")
    if truth is not None and set(truth.conditional_means) != set(policy.context_ids):
        raise NetworkPolicyMixtureUnsupported("POPULATION_TRUTH_CONTEXT_MISMATCH", "Conditional-mean contexts do not match policy contexts.")
    if spec.interference_structure_receipt is None:
        raise NetworkPolicyMixtureUnsupported("MISSING_I1_RECEIPT", "P1 v1 requires a typed executable I1 structure receipt.")
    if not spec.interference_structure_receipt.executable():
        raise NetworkPolicyMixtureUnsupported("UNRESOLVED_I1_STRUCTURE", "I1 structure receipt is not executable.")
    if spec.network_policy_mixture_theorem_contract.cross_block_response_constraints != "none_beyond_declared_local_marginals":
        raise NetworkPolicyMixtureUnsupported(
            "CROSS_BLOCK_RESPONSE_CONSTRAINTS_UNSUPPORTED_V1",
            "Cross-block response restrictions are outside P1 v1.",
        )
    if len(network.node_ids) > 8 or len(policy.context_ids) > 4 or len(uncertainty.candidates) > 16:
        raise NetworkPolicyMixtureUnsupported("EXACT_ORACLE_RESOURCE_LIMIT", "Small-network v2 limits: 8 nodes, 4 contexts, 16 candidates.")
    working_tables = network.working_mapping.state_by_local_assignment
    if any(working_tables[w] != working_tables[policy.context_ids[0]] for w in policy.context_ids):
        raise NetworkPolicyMixtureUnsupported("CONTEXT_VARYING_WORKING_MAPPING_UNSUPPORTED", "Frozen v1 working mapping is context invariant.")
    for candidate in uncertainty.candidates:
        if len(candidate.state_labels)*len(network.node_ids)*len(policy.context_ids)*4 > 384:
            raise NetworkPolicyMixtureUnsupported("EXACT_ORACLE_RESOURCE_LIMIT", "Canonical LP exceeds 384 variables.")
        network.validate_candidate_mapping(candidate)
    if truth is not None:
        _validate_population_truth_shape(spec, truth)


def _validate_population_truth_shape(spec: IdentificationSpec, truth: NetworkPolicyBinaryMeanPopulationTruthV1) -> None:
    network, _ = _candidate_family(spec)
    expected_contexts = network.working_mapping.context_ids
    if set(truth.context_weights) != set(expected_contexts):
        # Declared policy/mapping order is canonical; truth dictionary insertion order is not.
        raise NetworkPolicyMixtureUnsupported(
            "POPULATION_TRUTH_CONTEXT_MISMATCH",
            "Population truth context ids must match the frozen context universe.",
        )
    for w in expected_contexts:
        node_table = truth.conditional_means[w]
        if set(node_table) != set(network.node_ids):
            raise NetworkPolicyMixtureUnsupported(
                "POPULATION_TRUTH_NODE_MISMATCH", "Population truth must contain exactly all network nodes."
            )
        working_maps = network.working_mapping.state_by_local_assignment[w]
        for node in network.node_ids:
            reachable = set(working_maps[node].values())
            treatment_table = node_table[node]
            if set(treatment_table) != {"0", "1"}:
                raise NetworkPolicyMixtureUnsupported("POPULATION_TRUTH_TREATMENT_MISMATCH", "Population truth needs T=0 and T=1.")
            for a in ("0", "1"):
                if set(treatment_table[a]) != reachable:
                    raise NetworkPolicyMixtureUnsupported(
                        "POPULATION_TRUTH_EXPOSURE_MISMATCH",
                        "Population truth must contain exactly each reachable working exposure state.",
                    )


def _assignment_probability(bitstring: str, p: float) -> float:
    ones = bitstring.count("1")
    zeros = len(bitstring) - ones
    return (p ** ones) * ((1.0 - p) ** zeros)


def mixing_kernel_for_node(
    network: FiniteCategoricalNetworkExposureSpec,
    candidate: FiniteLocalExposureMappingSpec,
    context_id: str,
    node_id: str,
    p: float,
) -> dict[str, dict[str, float]]:
    working_table = network.working_mapping.state_by_local_assignment[context_id][node_id]
    candidate_table = candidate.state_by_local_assignment[context_id][node_id]
    working_states = network.working_mapping.state_labels
    candidate_states = candidate.state_labels
    kernel: dict[str, dict[str, float]] = {}
    for c in working_states:
        denominator = sum(
            _assignment_probability(bits, p)
            for bits, working_state in working_table.items()
            if working_state == c
        )
        if denominator <= 0.0:
            raise NetworkPolicyMixtureUnsupported("UNREACHABLE_WORKING_STATE", "A declared working exposure state has zero design probability.")
        row: dict[str, float] = {}
        for e in candidate_states:
            numerator = sum(
                _assignment_probability(bits, p)
                for bits, working_state in working_table.items()
                if working_state == c and candidate_table[bits] == e
            )
            row[e] = numerator / denominator
        if not _close(sum(row.values()), 1.0):
            raise NetworkPolicyMixtureUnsupported("MIXING_KERNEL_NORMALIZATION", "Replayed mixing kernel failed normalization.")
        kernel[c] = row
    return kernel


def _policy_neighbor_bitstring(network: FiniteCategoricalNetworkExposureSpec, policy_actions: list[int], node_id: str) -> str:
    action_by_node = dict(zip(network.node_ids, policy_actions, strict=True))
    return "".join(str(action_by_node[nbr]) for nbr in network.neighbor_order()[node_id])


def compile_candidate_lp(spec, truth, candidate) -> CanonicalMixtureLPV1:
    _validate_applicability(spec, truth)
    lp = exact.compile_exact(spec, truth, candidate)
    binding = lp.bindings()
    return CanonicalMixtureLPV1(
        A=np.array([[float(x) for x in row] for row in lp.A]),
        b=np.array([float(x) for x in lp.b]), q=np.array([float(x) for x in lp.q]),
        variable_order=lp.variable_order, exact_lp=lp, **binding,
    )


def _bindings(lp: CanonicalMixtureLPV1) -> dict[str, str]:
    return {
        "candidate_id": lp.candidate_id,
        "matrix_fingerprint": lp.matrix_fingerprint,
        "rhs_fingerprint": lp.rhs_fingerprint,
        "query_fingerprint": lp.query_fingerprint,
        "variable_order_fingerprint": lp.variable_order_fingerprint,
    }


def solve_candidate(lp: CanonicalMixtureLPV1) -> CandidateMixtureIdentificationCertificateV1:
    r = lp.exact_lp
    if r is None:
        raise NetworkPolicyMixtureUnsupported("EXACT_INPUT_REQUIRED", "Numeric-only matrices do not establish exact topology.")
    try:
        low,zl,yl = exact.optimize_endpoint(r,"LOWER")
    except exact.ExactInfeasibleError as exc:
        fy = exc.y
        return CandidateMixtureIdentificationCertificateV1(candidate_id=r.candidate_id,status="INCOMPATIBLE",
            farkas=FarkasIncompatibilityCertificateV1(**_bindings(lp), y=[display(x) for x in fy], exact_y=[str(x) for x in fy]))
    high,zu,yu = exact.optimize_endpoint(r,"UPPER")
    if low > high:
        raise NetworkPolicyMixtureUnsupported("ENDPOINT_ORDER_FAILURE", "Exact upper endpoint is below lower.")
    if low != high and display(low) == display(high):
        raise NetworkPolicyMixtureUnsupported("DISPLAY_TOPOLOGY_AMBIGUITY", "Distinct exact endpoints cannot be faithfully represented by this float display schema.")
    def primal(side,z,v):
        return LPPrimalWitnessV1(**_bindings(lp),side=side,z=[display(x) for x in z],objective_value=display(v),
                                exact_z=[str(x) for x in z],exact_objective=str(v))
    def dual(side,y,v):
        return LPDualWitnessV1(**_bindings(lp),side=side,y=[display(x) for x in y],objective_value=display(v),
                              exact_y=[str(x) for x in y],exact_objective=str(v))
    return CandidateMixtureIdentificationCertificateV1(candidate_id=r.candidate_id,
        status="POINT" if low==high else "PARTIAL", raw_interval=ClosedIntervalV1(lower=display(low),upper=display(high)),
        lower_primal=primal("LOWER",zl,low),lower_dual=dual("LOWER",yl,low),
        upper_primal=primal("UPPER",zu,high),upper_dual=dual("UPPER",yu,high))


def _canonical_union(intervals: Iterable[ClosedIntervalV1]) -> FiniteUnionClosedIntervalsV1:
    ordered = sorted(intervals, key=lambda x: (x.lower, x.upper))
    if not ordered:
        raise ValueError("cannot canonicalize empty compatible interval set")
    components: list[ClosedIntervalV1] = [ClosedIntervalV1(lower=ordered[0].lower, upper=ordered[0].upper)]
    for interval in ordered[1:]:
        previous = components[-1]
        gap = interval.lower - previous.upper
        if 0.0 < gap <= TOPOLOGY_AMBIGUITY_BAND:
            raise NetworkPolicyMixtureUnsupported(
                "NUMERIC_CERTIFICATE_AMBIGUITY",
                "Interval-component gap lies inside the numeric topology ambiguity band.",
            )
        if gap <= 0.0:
            previous.upper = max(previous.upper, interval.upper)
        else:
            components.append(ClosedIntervalV1(lower=interval.lower, upper=interval.upper))
    return FiniteUnionClosedIntervalsV1(components=components)


def _overall_status(exact: FiniteUnionClosedIntervalsV1 | None) -> IdentificationStatus:
    if exact is None:
        return IdentificationStatus.INCOMPATIBLE
    if exact.is_singleton():
        return IdentificationStatus.POINT
    if (
        exact.is_connected
        and len(exact.components) == 1
        and exact.components[0].lower == 0.0
        and exact.components[0].upper == 1.0
    ):
        return IdentificationStatus.NO_USEFUL_ID
    return IdentificationStatus.PARTIAL


def _strict_copy(model, cls):
    raw = model.model_dump(mode="json")
    copy = cls.model_validate(raw)
    if raw != copy.model_dump(mode="json"):
        raise ValueError("NONCANONICAL_OR_STALE_PAYLOAD")
    return copy


def _display_set(components):
    if not components:
        return None
    display_intervals = [ClosedIntervalV1(lower=display(lo),upper=display(hi)) for lo,hi in components]
    for (lo,hi), d in zip(components, display_intervals):
        if lo!=hi and d.lower==d.upper:
            raise NetworkPolicyMixtureUnsupported("DISPLAY_TOPOLOGY_AMBIGUITY", "Non-singleton became a float singleton.")
    for left,right in zip(display_intervals,display_intervals[1:]):
        if left.upper >= right.lower:
            raise NetworkPolicyMixtureUnsupported("DISPLAY_TOPOLOGY_AMBIGUITY", "An exact gap is not representable in the float view.")
    return FiniteUnionClosedIntervalsV1(components=display_intervals)


def _assemble(spec, truth, certificates, components):
    network,uncertainty = _candidate_family(spec)
    policy=spec.deterministic_policy_oracle
    image=_display_set(components)
    status = (IdentificationStatus.INCOMPATIBLE if not components else
              IdentificationStatus.POINT if len(components)==1 and components[0][0]==components[0][1] else
              IdentificationStatus.NO_USEFUL_ID if components==((Fraction(0),Fraction(1)),) else
              IdentificationStatus.PARTIAL)
    scope="EMPTY_FIBER_CERTIFIED" if not components else "EXACT_IDENTIFIED_SET"
    guarantee={IdentificationStatus.POINT:"point_identified",IdentificationStatus.PARTIAL:"sharp",
               IdentificationStatus.NO_USEFUL_ID:"trivial",IdentificationStatus.INCOMPATIBLE:"none"}[status]
    proof=NetworkPolicyMixtureProofBundleV1(
        numeric_policy_version=NUMERIC_POLICY_VERSION,
        exact_components_rational=[(str(lo),str(hi)) for lo,hi in components],
        policy_fingerprint=policy.semantic_fingerprint(),spec_fingerprint=_spec_fingerprint(spec),
        population_truth_fingerprint=truth.semantic_fingerprint(),working_mapping_fingerprint=network.working_mapping.semantic_fingerprint(),
        candidate_set_fingerprint=uncertainty.semantic_fingerprint(),exact_set_fingerprint=_exact_set_fingerprint(image),
        sharpness_scope=scope,candidate_results=certificates,exact_identified_set=image)
    return IdentificationResult(status=status, query=spec.query,backend=BACKEND_ID,
        set_program=NetworkPolicyFiniteMixtureSetProgram(treatment=spec.query.treatment,outcome=spec.query.outcome,
            network_id=network.network_id,working_mapping_id=network.working_mapping.mapping_id,
            candidate_mapping_ids=[c.mapping_id for c in uncertainty.candidates],policy_id=policy.policy_id),
        identified_set=image,network_policy_mixture_proof=proof,network_exposure=network,exposure_uncertainty=uncertainty,
        assumptions_used=["random_assignment","consistency"],
        required_population_objects=["P_exp(W)", f"P({spec.query.outcome}_i=1 | W,{spec.query.treatment}_i,C_i,A)"],
        known_design_objects=["fixed network A","iid Bernoulli p","working exposure mapping",
                              "finite candidate true exposure mappings","deterministic policy"],
        validity_domain={"theorem_rule_id":THEOREM_RULE_ID,"ambiguity_semantics":"FINITE_EXACT_STRUCTURAL_FAMILY",
                         "sharpness_scope":scope,"information_basis":"NODE_CONTEXT_WORKING_EXPOSURE_BINARY_MEAN_V1",
                         "numeric_policy_version":NUMERIC_POLICY_VERSION,"identification_scope":"INSTANCE_AT_DECLARED_POPULATION_TRUTH",
                         "cross_block_response_constraints":"none_beyond_declared_local_marginals",
                         "conditional_coupling_semantics":"arbitrary_coupling_allowed",
                         "finite_sample_estimation":"NOT_RUN","policy_optimization":"NOT_RUN"},
        guarantee=guarantee,certificate={"population_truth_fingerprint":truth.semantic_fingerprint()},
        message="Exact population result conditional on the declared finite structural family and marginal-only information. Float endpoints are display values; rational endpoints are authoritative.",
        trace=[TraceStep(step="p1_exact_oracle_proposal",outcome="PASS",detail="Exact rational LP witnesses proposed.")],
        verification_status=VerificationStatus.UNSUPPORTED,verification_message="Awaiting certificate replay.")


def _failure(spec, code, message, *, rejected=False):
    return IdentificationResult(status=IdentificationStatus.UNSUPPORTED,query=spec.query,backend=BACKEND_ID,
        guarantee="none",reason_code=code,message=message,
        verification_status=VerificationStatus.REJECTED if rejected else VerificationStatus.UNSUPPORTED,
        verification_message=message,trace=[TraceStep(step="p1_exact_oracle",outcome="FAIL",detail=message)])


def propose_network_policy_mixture(spec, truth):
    try:
        spec=_strict_copy(spec,IdentificationSpec)
        truth=_strict_copy(truth,NetworkPolicyBinaryMeanPopulationTruthV1)
        _validate_applicability(spec,truth)
        _,family=_candidate_family(spec)
        certificates=[];intervals=[]
        for candidate in family.candidates:
            cert=solve_candidate(compile_candidate_lp(spec,truth,candidate));certificates.append(cert)
            if cert.status!="INCOMPATIBLE":
                intervals.append((fraction(cert.lower_primal.exact_objective),fraction(cert.upper_primal.exact_objective)))
        return _assemble(spec,truth,certificates,exact.union(intervals))
    except NetworkPolicyMixtureUnsupported as exc:
        return _failure(spec,exc.reason_code,exc.message)
    except (ValueError,TypeError,KeyError,AssertionError,ArithmeticError) as exc:
        return _failure(spec,"INVALID_OR_UNCERTIFIED_EXACT_INPUT",str(exc))
    except Exception as exc:
        # Optimizer failures are not proofs of incompatibility or non-identification.
        return _failure(spec,"EXACT_SOLVER_FAILURE",f"{type(exc).__name__}: {exc}")


def _read_vector(rational, view, length, error_code):
    if rational is None or len(rational)!=length or len(view)!=length:
        raise ValueError("CERTIFICATE_DIMENSION_MISMATCH")
    vec=tuple(fraction(x) for x in rational)
    if [display(x) for x in vec] != view:
        raise ValueError(error_code)
    return vec


def _check_bindings(cert, lp):
    return all(getattr(cert,k)==v for k,v in lp.bindings().items())


def _verify_candidate_certificate(lp, cert):
    if cert.candidate_id != lp.candidate_id:
        raise ValueError("CANDIDATE_BINDING_MISMATCH")
    if cert.status=="INCOMPATIBLE":
        f=cert.farkas
        if f is None or not _check_bindings(f,lp):
            raise ValueError("CERTIFICATE_BINDING_MISMATCH")
        if any(x is not None for x in [cert.lower_primal,cert.upper_primal,cert.lower_dual,cert.upper_dual,cert.row_space_point]):
            raise ValueError("EXTRANEOUS_COMPATIBLE_CERTIFICATES")
        y=_read_vector(f.exact_y,f.y,len(lp.b),"INVALID_FARKAS_CERTIFICATE")
        exact.check_farkas(lp,y)
        return None
    if cert.farkas is not None:
        raise ValueError("CONFLICTING_CERTIFICATES")
    endpoints=[]
    for side,p,d in [("LOWER",cert.lower_primal,cert.lower_dual),("UPPER",cert.upper_primal,cert.upper_dual)]:
        if p is None or d is None:
            raise ValueError("MISSING_EXACT_ENDPOINT_CERTIFICATES")
        if not _check_bindings(p,lp) or not _check_bindings(d,lp) or p.side!=side or d.side!=side:
            raise ValueError("CERTIFICATE_BINDING_MISMATCH")
        z=_read_vector(p.exact_z,p.z,len(lp.q),"INVALID_PRIMAL_CERTIFICATE")
        y=_read_vector(d.exact_y,d.y,len(lp.b),"INVALID_DUAL_CERTIFICATE")
        value=fraction(p.exact_objective)
        if fraction(d.exact_objective)!=value or p.objective_value!=display(value) or d.objective_value!=display(value):
            raise ValueError("CERTIFICATE_OBJECTIVE_MISMATCH")
        exact.check_endpoint(lp,z,y,value,side);endpoints.append(value)
    lo,hi=endpoints
    if cert.row_space_point is not None:
        row=cert.row_space_point
        if not _check_bindings(row,lp):
            raise ValueError("CERTIFICATE_BINDING_MISMATCH")
        z=_read_vector(row.exact_feasible_z,row.feasible_witness_z,len(lp.q),"INVALID_ROW_SPACE_CERTIFICATE")
        a=_read_vector(row.exact_alpha,row.alpha,len(lp.b),"INVALID_ROW_SPACE_CERTIFICATE")
        if matvec(lp.A,z)!=lp.b or any(x<0 for x in z) or matvec(transpose(lp.A),a)!=lp.q:
            raise ValueError("INVALID_ROW_SPACE_CERTIFICATE")
        if not dot(a,lp.b)==fraction(row.exact_value)==lo==hi or row.identified_value!=display(lo):
            raise ValueError("ROW_SPACE_VALUE_MISMATCH")
    if cert.raw_interval is None or cert.raw_interval.lower!=display(lo) or cert.raw_interval.upper!=display(hi):
        raise ValueError("CERTIFIED_INTERVAL_MISMATCH")
    if cert.status != ("POINT" if lo==hi else "PARTIAL"):
        raise ValueError("CANDIDATE_STATUS_MISMATCH")
    return lo,hi


def verify_network_policy_mixture(spec,truth,proposed):
    if proposed.status==IdentificationStatus.UNSUPPORTED:
        return _failure(spec,proposed.reason_code or "PROPOSER_ABSTAINED",proposed.message or "No certified claim.")
    try:
        spec=_strict_copy(spec,IdentificationSpec)
        truth=_strict_copy(truth,NetworkPolicyBinaryMeanPopulationTruthV1)
        proposed=_strict_copy(proposed,IdentificationResult)
        _validate_applicability(spec,truth)
        bundle=proposed.network_policy_mixture_proof
        if bundle is None or bundle.numeric_policy_version!=NUMERIC_POLICY_VERSION:
            raise ValueError("MISSING_OR_UNSUPPORTED_EXACT_PROOF_BUNDLE")
        network,family=_candidate_family(spec)
        ids=[c.mapping_id for c in family.candidates]
        if [c.candidate_id for c in bundle.candidate_results]!=ids:
            raise ValueError("CANDIDATE_SET_MISMATCH")
        intervals=[]
        for candidate,cert in zip(family.candidates,bundle.candidate_results):
            lp=exact.compile_exact(spec,truth,candidate,global_replay=True)
            interval=_verify_candidate_certificate(lp,cert)
            if interval is not None:intervals.append(interval)
        expected=_assemble(spec,truth,bundle.candidate_results,exact.union(intervals))
        # Bind EVERY claim/program/handoff field, not just LP objective/status.
        ignore={"trace","verification_status","verification_message"}
        lhs=proposed.model_dump(mode="json",exclude=ignore)
        rhs=expected.model_dump(mode="json",exclude=ignore)
        if lhs!=rhs:
            changed=sorted(k for k in lhs if lhs[k]!=rhs[k])
            raise ValueError("RESULT_PAYLOAD_MISMATCH: "+", ".join(changed))
        expected.verification_status=VerificationStatus.VERIFIED
        expected.verification_message="Whole-assignment kernel replay and exact rational primal/dual/Farkas identities passed. Conditional on the encoded theorem class; not an external formal proof."
        expected.trace.append(TraceStep(step="p1_exact_oracle_verifier",outcome="PASS",detail=expected.verification_message))
        return expected
    except NetworkPolicyMixtureUnsupported as exc:
        return _failure(spec,exc.reason_code,exc.message,rejected=True)
    except (ValueError,TypeError,KeyError,IndexError,AttributeError,AssertionError,ArithmeticError) as exc:
        code=str(exc).split(":",1)[0] if isinstance(exc,ValueError) and not isinstance(exc,ValidationError) else "MALFORMED_CERTIFICATE_OR_SPEC"
        return _failure(spec,code,str(exc),rejected=True)


def run_network_policy_mixture_oracle(spec,truth):
    proposed=propose_network_policy_mixture(spec,truth)
    return NetworkPolicyMixtureOracleRunV1(proposed,verify_network_policy_mixture(spec,truth,proposed))
