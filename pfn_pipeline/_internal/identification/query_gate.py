from __future__ import annotations

from collections.abc import Sequence

from .schemas import (
    AssumptionConflict,
    IdentificationResult,
    IdentificationStatus,
    QuerySpec,
    TraceStep,
    VariableSemanticSpec,
    VerificationStatus,
)


TRUSTED_QUERY_AUTHORITIES = {"HUMAN_CONFIRMED", "TRUSTED_FIXTURE"}
BUSINESS_EXECUTABLE_QUERY_TYPES = {"ATE"}


def query_semantics_implementation_gaps(query: QuerySpec) -> list[str]:
    """List confirmed query slots the current theorem/estimator stack ignores.

    The current ATE program is an overall-population, unconditional contrast.
    A semantic field must never be fingerprinted as execution-relevant and then
    silently discarded downstream.
    """

    gaps: list[str] = []
    if query.type not in {"NETWORK_RESPONSE_SURFACE", "NETWORK_MAJORITY_RESPONSE_POLICY_SCORE"} and query.response_target_fingerprint is not None:
        gaps.append("response_target_fingerprint is only supported for NETWORK_RESPONSE_SURFACE")
    if query.type == "NETWORK_MAJORITY_RESPONSE_POLICY_SCORE":
        expected = {"target_population": "fixed_network_conditional_context",
                    "reference_exposure_definition": "treated_neighbor_count_1hop",
                    "target_exposure_semantics": "design_averaged_majority_response",
                    "policy_description": "all_budget_feasible_binary_allocations"}
        for key, value in expected.items():
            if getattr(query, key) != value:
                gaps.append(f"{key} must equal {value!r}")
        if query.conditioning_variables or query.exposure_value is not None or not query.response_target_fingerprint or not query.policy_fingerprint:
            gaps.append("Majority-score query requires bound response and policy-class fingerprints")
        return gaps
    if query.type == "NETWORK_RESPONSE_SURFACE":
        expected = {
            "target_population": "fixed_network_conditional_context",
            "reference_exposure_definition": "treated_neighbor_count_1hop",
            "target_exposure_semantics": "design_averaged_majority_response",
        }
        for key, value in expected.items():
            if getattr(query, key) != value:
                gaps.append(f"{key} must equal {value!r}")
        if (query.conditioning_variables or query.exposure_value is not None
            or query.policy_description is not None or query.policy_fingerprint is not None
            or not query.response_target_fingerprint):
            gaps.append("Response query requires all four arms, full-context conditioning and a bound target; it is not a policy or subgroup query")
        return gaps
    if query.type == "ATE":
        if query.target_population != "overall_population":
            gaps.append(
                f"target_population={query.target_population!r} (only 'overall_population' is implemented)"
            )
        if query.conditioning_variables:
            gaps.append(
                f"conditioning_variables={query.conditioning_variables!r} (conditional/subgroup ATE is not implemented)"
            )
        if query.reference_exposure_definition is not None:
            gaps.append("reference_exposure_definition is populated (exposure-specific ATE is not implemented)")
        if query.policy_description is not None:
            gaps.append("policy_description is populated (policy-specific ATE is not implemented)")
        return gaps

    if query.type == "POLICY_VALUE":
        if query.target_population != "overall_population":
            gaps.append(
                f"target_population={query.target_population!r} (the minimal policy-value fixture implements only the declared overall target-context population)"
            )
        if query.conditioning_variables:
            gaps.append(
                f"conditioning_variables={query.conditioning_variables!r} (the policy value is already indexed by pre-treatment context W; an additional conditional target is not implemented)"
            )
        if query.reference_exposure_definition == "finite_local_exposure_table_v1":
            if not query.policy_fingerprint:
                gaps.append("policy_fingerprint must bind the complete deterministic action table")
            if query.exposure_value is not None or query.target_exposure_semantics is not None:
                gaps.append("fixed-policy query must not also be a fixed-exposure-state query")
            if not query.policy_description:
                gaps.append("explicit policy description is required")
            return gaps
        if query.reference_exposure_definition != "treated_neighbor_count_1hop":
            gaps.append(
                "reference_exposure_definition must equal 'treated_neighbor_count_1hop' for the minimal network policy-value theorem"
            )
        if query.target_exposure_semantics is not None:
            gaps.append("target_exposure_semantics must be empty for the current POLICY_VALUE fixture")
        if query.policy_description != "deterministic_binary_network_policy":
            gaps.append(
                "policy_description must equal 'deterministic_binary_network_policy' for the minimal network policy-value theorem"
            )
        return gaps

    if query.type == "DIRECT_EFFECT":
        if query.target_population != "overall_population":
            gaps.append(
                f"target_population={query.target_population!r} (the current direct-effect fixture targets the observed overall context population)"
            )
        if query.conditioning_variables:
            gaps.append(
                f"conditioning_variables={query.conditioning_variables!r} (conditional direct effects are not executable in v0.2.9)"
            )
        if query.reference_exposure_definition != "treated_neighbor_share_threshold_1hop":
            gaps.append(
                "reference_exposure_definition must equal 'treated_neighbor_share_threshold_1hop' for the network direct-effect theorem"
            )
        if query.target_exposure_semantics != "true_sufficient_exposure_state":
            gaps.append(
                "target_exposure_semantics must equal 'true_sufficient_exposure_state' so POINT/PARTIAL preserve the same causal target"
            )
        if query.exposure_value not in {0, 1}:
            gaps.append("exposure_value must be 0 or 1 for the binary threshold-exposure direct effect")
        if query.policy_description is not None:
            gaps.append("policy_description must be empty for DIRECT_EFFECT")
        return gaps

    return gaps


def evaluate_query_before_identification(
    query: QuerySpec,
    *,
    assumption_conflicts: Sequence[AssumptionConflict] = (),
    allow_policy_value_theory: bool = False,
    allow_network_direct_effect_theory: bool = False,
    allow_network_response_theory: bool = False,
) -> IdentificationResult | None:
    """Return a blocking result, or ``None`` when formal ID may proceed.

    This gate is deliberately outside the theorem-backend registry. It checks
    semantic resolution, trusted execution authority, and software capability;
    none of those checks is itself a causal identification theorem. Business Mode
    executes ATE only; direct Theory-Mode formal specs may additionally enable the
    narrow fixed-network POLICY_VALUE fixture or the current network DIRECT_EFFECT fixture.
    """

    executable_query_types = set(BUSINESS_EXECUTABLE_QUERY_TYPES)
    if allow_policy_value_theory:
        executable_query_types.add("POLICY_VALUE")
    if allow_network_response_theory:
        executable_query_types.update({"NETWORK_RESPONSE_SURFACE", "NETWORK_MAJORITY_RESPONSE_POLICY_SCORE"})
    if allow_network_direct_effect_theory:
        executable_query_types.add("DIRECT_EFFECT")

    if query.resolution != "RESOLVED":
        reason_code = "QUERY_INTERPRETATION_NOT_RESOLVED"
        message = (
            f"The semantic front-end proposed {query.type}, but its resolution is "
            f"{query.resolution}. Identification is blocked until the intended query is resolved."
        )
        failed_step = "query_resolution"
        failed_detail = (
            f"Candidate={query.type}; resolution={query.resolution}; "
            f"alternatives={[item.type for item in query.alternatives]}."
        )
    elif query.authority not in TRUSTED_QUERY_AUTHORITIES:
        reason_code = "QUERY_NOT_CONFIRMED"
        message = (
            f"The LLM proposed a resolved {query.type} query, but its authority is {query.authority}. "
            "An explicit human confirmation or trusted fixture is required before causal identification."
        )
        failed_step = "query_confirmation"
        failed_detail = (
            "LLM_RESOLVED is not execution authority. Allowed authorities are "
            f"{sorted(TRUSTED_QUERY_AUTHORITIES)}."
        )
    elif query.type not in executable_query_types:
        reason_code = "QUERY_TYPE_NOT_IMPLEMENTED"
        message = (
            f"The confirmed semantic query is {query.type}. The current minimal theorem library "
            f"executes only {sorted(executable_query_types)} in this mode and will not reinterpret one query family as another."
        )
        failed_step = "query_capability_check"
        failed_detail = (
            f"Executable query types in this mode={sorted(executable_query_types)}; received={query.type}."
        )
    elif semantic_gaps := query_semantics_implementation_gaps(query):
        reason_code = "QUERY_SEMANTICS_NOT_IMPLEMENTED"
        message = (
            f"The confirmed {query.type} query contains execution-relevant semantics that the current "
            "minimal theorem/estimation contract does not implement."
        )
        failed_step = "query_semantics_capability_check"
        failed_detail = "; ".join(semantic_gaps)
    else:
        return None

    trace = [
        TraceStep(
            step="pre_identification_gate",
            outcome="INFO",
            detail=(
                f"candidate={query.type}; resolution={query.resolution}; authority={query.authority}; "
                f"evidence={query.evidence}."
            ),
        )
    ]
    if assumption_conflicts:
        trace.append(
            TraceStep(
                step="assumption_compatibility",
                outcome="INFO",
                detail=str(
                    [
                        (item.code, item.assumption, item.severity)
                        for item in assumption_conflicts
                    ]
                ),
            )
        )
    trace.append(TraceStep(step=failed_step, outcome="FAIL", detail=failed_detail))

    return IdentificationResult(
        status=IdentificationStatus.UNSUPPORTED,
        query=query,
        backend="pre_identification_query_gate_v1",
        guarantee="none",
        reason_code=reason_code,
        message=message,
        verification_status=VerificationStatus.UNSUPPORTED,
        verification_message=(
            "No formal IdentificationSpec or causal theorem was executed because the pre-identification query gate blocked the request."
        ),
        trace=trace,
    )


def evaluate_semantic_spec_before_identification(
    semantics: VariableSemanticSpec,
) -> IdentificationResult | None:
    return evaluate_query_before_identification(
        semantics.query,
        assumption_conflicts=semantics.assumption_conflicts,
    )
