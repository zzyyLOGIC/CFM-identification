from __future__ import annotations

from .schemas import (
    BoundEstimationRequest,
    NetworkPolicyMixtureEstimationRequestV2,
    EstimationRequest,
    IdentificationResult,
    IdentificationStatus,
    NetworkDirectEffectBoundEstimationRequest,
    NetworkDirectEffectPointEstimationRequest,
    NetworkDirectEffectPointProgram,
    NetworkDirectEffectSensitivityBoundsProgram,
    NetworkPolicyValueProgram,
    PointEstimationRequest,
    PolicyValueEstimationRequest,
    PolicyValueTensorContract,
    ThresholdNetworkExposureSpec,
    ExposurePropensityRatioSensitivitySpec,
    VerificationStatus,
)


def compile_estimation_request(result: IdentificationResult, *, spec=None, population_truth=None) -> EstimationRequest | None:
    """Compile only independently verified causal objects into estimation work."""
    if result.verification_status != VerificationStatus.VERIFIED:
        return None

    if result.query.type == "NETWORK_MAJORITY_RESPONSE_POLICY_SCORE":
        from .schemas import NetworkMajorityScoreEstimationRequestV1
        from .majority_score import response_dependency, verify_majority_score
        from .query_confirmation import query_confirmation_fingerprint
        if spec is None:
            raise ValueError("Majority score handoff requires source spec")
        checked = verify_majority_score(spec, result)
        if checked.verification_status != VerificationStatus.VERIFIED:
            raise ValueError("Majority score proof replay failed: " + checked.verification_message)
        dependency = response_dependency(spec)
        base = IdentificationResult.model_validate(checked.certificate["response_identification_result"])
        response_request = compile_estimation_request(base, spec=dependency)
        return NetworkMajorityScoreEstimationRequestV1(
            program=checked.identified_functional, source_spec=spec,
            reference_identification_result=checked, response_request=response_request,
            required_population_objects=checked.required_population_objects,
            known_design_objects=checked.known_design_objects,
            query_confirmation_fingerprint=query_confirmation_fingerprint(spec.query))

    if result.query.type == "NETWORK_RESPONSE_SURFACE":
        from .schemas import NetworkMajorityResponseEstimationRequestV1
        from .query_confirmation import query_confirmation_fingerprint
        if spec is None:
            raise ValueError("Majority response handoff requires source spec for independent replay")
        return NetworkMajorityResponseEstimationRequestV1(
            program=result.identified_functional, source_spec=spec,
            reference_identification_result=result,
            required_population_objects=result.required_population_objects,
            known_design_objects=result.known_design_objects,
            query_confirmation_fingerprint=query_confirmation_fingerprint(spec.query))

    # Reject even previously saved VERIFIED labels from the quarantined route.
    if isinstance(result.bound_program, NetworkDirectEffectSensitivityBoundsProgram):
        return None
    if result.network_policy_mixture_proof is not None:
        if result.status not in {IdentificationStatus.POINT, IdentificationStatus.PARTIAL}:
            return None
        if spec is None or population_truth is None:
            raise ValueError("Finite-mixture handoff requires source spec and separate population truth for replay")
        from .query_confirmation import query_confirmation_fingerprint
        return NetworkPolicyMixtureEstimationRequestV2(
            identification_status=result.status,program=result.set_program,
            required_population_objects=result.required_population_objects,known_design_objects=result.known_design_objects,
            validity_domain=result.validity_domain,assumptions=spec.assumptions,provenance=spec.provenance,
            guarantee=result.guarantee,query_confirmation_fingerprint=query_confirmation_fingerprint(spec.query),
            source_spec=spec,reference_population_truth=population_truth,reference_identification_result=result)

    if result.status == IdentificationStatus.POINT:
        if result.identified_functional is None:
            raise ValueError("Verified POINT result must contain an identified functional")

        if result.query.type == "ATE":
            return PointEstimationRequest(
                estimand="ATE",
                identification_status=IdentificationStatus.POINT,
                treatment=result.query.treatment,
                outcome=result.query.outcome,
                program=result.identified_functional,
                required_population_objects=result.required_population_objects,
                validity_domain=result.validity_domain,
                assumptions=result.assumptions_used,
                guarantee=result.guarantee,
                identification_backend=result.backend,
                verification_status=VerificationStatus.VERIFIED,
            )

        if result.query.type == "DIRECT_EFFECT":
            if not isinstance(result.identified_functional, NetworkDirectEffectPointProgram):
                raise ValueError("Verified DIRECT_EFFECT point result must carry NetworkDirectEffectPointProgram")
            if not isinstance(result.network_exposure, ThresholdNetworkExposureSpec):
                raise ValueError("Verified DIRECT_EFFECT point result must carry ThresholdNetworkExposureSpec")
            if result.exposure_uncertainty is not None:
                raise ValueError("Verified DIRECT_EFFECT point result must not carry exposure uncertainty")
            network = result.network_exposure
            return NetworkDirectEffectPointEstimationRequest(
                identification_status=IdentificationStatus.POINT,
                treatment=result.query.treatment,
                outcome=result.query.outcome,
                reference_exposure_definition=result.query.reference_exposure_definition,
                target_exposure_semantics=result.query.target_exposure_semantics,
                exposure_value=int(result.query.exposure_value),
                program=result.identified_functional,
                network=network,
                network_exposure_fingerprint=network.semantic_fingerprint(),
                required_population_objects=result.required_population_objects,
                validity_domain=result.validity_domain,
                assumptions=result.assumptions_used,
                guarantee=result.guarantee,
                identification_backend=result.backend,
                verification_status=VerificationStatus.VERIFIED,
            )

        if result.query.type == "POLICY_VALUE":
            if not isinstance(result.identified_functional, NetworkPolicyValueProgram):
                raise ValueError("Verified POLICY_VALUE result must carry NetworkPolicyValueProgram")
            if result.network_exposure is None:
                raise ValueError("Verified POLICY_VALUE result must carry the fixed network/exposure contract")
            local_g = result.certificate.get("local_state_probabilities")
            if not isinstance(local_g, dict):
                raise ValueError("Verified POLICY_VALUE result must carry known local-state design probabilities")
            network = result.network_exposure
            tensor_contract = PolicyValueTensorContract(
                node_ids=network.node_ids,
                reachable_neighbor_counts=network.reachable_neighbor_counts(),
                max_neighbor_count=network.max_degree(),
                outcome_mean_semantics=(
                    f"mu_hat[s,i,a,k] estimates E[{result.query.outcome}_i | W_s,A,"
                    f"{result.query.treatment}_i=a,K_i=k] for reachable local states"
                ),
                local_state_propensity_semantics=(
                    f"local_g[s,i,a,k] = P({result.query.treatment}_i=a,K_i=k | W_s,A,logging design); "
                    "in this fixture local_g is known exactly from the Bernoulli design and is constant across snapshots"
                ),
            )
            return PolicyValueEstimationRequest(
                identification_status=IdentificationStatus.POINT,
                treatment=result.query.treatment,
                outcome=result.query.outcome,
                program=result.identified_functional,
                network=network,
                network_exposure_fingerprint=network.semantic_fingerprint(),
                required_population_objects=result.required_population_objects,
                estimation_nuisance_objects=result.estimation_nuisance_objects,
                known_design_objects=result.known_design_objects,
                known_local_state_propensities=local_g,
                tensor_contract=tensor_contract,
                validity_domain=result.validity_domain,
                assumptions=result.assumptions_used,
                guarantee=result.guarantee,
                identification_backend=result.backend,
                verification_status=VerificationStatus.VERIFIED,
            )

        raise ValueError(f"Verified POINT query type is not supported by the handoff compiler: {result.query.type}")

    if result.status == IdentificationStatus.PARTIAL:
        if result.bound_program is None:
            raise ValueError("Verified PARTIAL result must contain a bound program")

        if result.query.type == "DIRECT_EFFECT":
            if not isinstance(result.bound_program, NetworkDirectEffectSensitivityBoundsProgram):
                raise ValueError("Verified DIRECT_EFFECT partial result must carry NetworkDirectEffectSensitivityBoundsProgram")
            if not isinstance(result.network_exposure, ThresholdNetworkExposureSpec):
                raise ValueError("Verified DIRECT_EFFECT partial result must carry ThresholdNetworkExposureSpec")
            if not isinstance(result.exposure_uncertainty, ExposurePropensityRatioSensitivitySpec):
                raise ValueError("Verified DIRECT_EFFECT partial result must carry the typed exposure uncertainty contract")
            network = result.network_exposure
            return NetworkDirectEffectBoundEstimationRequest(
                identification_status=IdentificationStatus.PARTIAL,
                treatment=result.query.treatment,
                outcome=result.query.outcome,
                reference_exposure_definition=result.query.reference_exposure_definition,
                target_exposure_semantics=result.query.target_exposure_semantics,
                exposure_value=int(result.query.exposure_value),
                program=result.bound_program,
                network=network,
                network_exposure_fingerprint=network.semantic_fingerprint(),
                exposure_uncertainty=result.exposure_uncertainty,
                required_population_objects=result.required_population_objects,
                validity_domain=result.validity_domain,
                assumptions=result.assumptions_used,
                guarantee=result.guarantee,
                identification_backend=result.backend,
                verification_status=VerificationStatus.VERIFIED,
            )

        if result.query.type == "ATE":
            return BoundEstimationRequest(
                estimand="ATE",
                identification_status=IdentificationStatus.PARTIAL,
                treatment=result.query.treatment,
                outcome=result.query.outcome,
                program=result.bound_program,
                required_population_objects=result.required_population_objects,
                validity_domain=result.validity_domain,
                assumptions=result.assumptions_used,
                guarantee=result.guarantee,
                identification_backend=result.backend,
                verification_status=VerificationStatus.VERIFIED,
            )

        raise ValueError(f"Verified PARTIAL query type is not supported by the handoff compiler: {result.query.type}")

    return None
