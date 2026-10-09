from __future__ import annotations

import math
import json

from .schemas import (
    DifferenceFunctional,
    IdentificationResult,
    IdentificationSpec,
    IdentificationStatus,
    ExposurePropensityRatioSensitivitySpec,
    ManskiBinaryATEBoundsProgram,
    NetworkDirectEffectPointProgram,
    NetworkDirectEffectSensitivityBoundsProgram,
    NetworkPolicyValueProgram,
    OneArmATEBoundsProgram,
    ThresholdNetworkExposureSpec,
    VerificationStatus,
    interference_structure_semantic_fingerprint,
)
from .query_gate import TRUSTED_QUERY_AUTHORITIES, query_semantics_implementation_gaps


class IdentificationVerifier:
    """Independent rule-replay verifier for the supported minimal backends.

    The verifier never calls IdentificationEngine. It re-checks the formal spec, certificate rule id, and program structure.
    v0.2.19 adds exact finite-mixture POLICY_VALUE replay, preserves older POINT
    routes, and rejects the quarantined Gamma DIRECT_EFFECT certificate family.
    It rejects NO_USEFUL_ID whenever even one finite support restriction remains.
    """

    def verify(self, spec: IdentificationSpec, result: IdentificationResult, *, population_truth=None) -> IdentificationResult:
        if (spec.query.type == "NETWORK_MAJORITY_RESPONSE_POLICY_SCORE"
            or result.query.type == "NETWORK_MAJORITY_RESPONSE_POLICY_SCORE"
            or result.certificate.get("rule_id") == "NETWORK_MAJORITY_SCORE_COMPOSITION_V1"):
            from .majority_score import verify_majority_score
            return verify_majority_score(spec, result)
        if (spec.majority_response_theorem_contract is not None
            or result.query.type == "NETWORK_RESPONSE_SURFACE"
            or result.certificate.get("rule_id") == "NETWORK_MAJORITY_DESIGN_AVERAGE_V1"):
            from .majority_response import verify_majority_response
            return verify_majority_response(spec, result)
        if spec.network_policy_mixture_theorem_contract is not None or result.network_policy_mixture_proof is not None:
            from .network_policy_mixture import verify_network_policy_mixture, _failure
            if population_truth is None:
                return _failure(spec,"MISSING_POPULATION_TRUTH","Certificate replay needs the original separate population truth.",rejected=True)
            return verify_network_policy_mixture(spec,population_truth,result)
        checked = result.model_copy(deep=True)

        if result.status == IdentificationStatus.POINT:
            rule_id = result.certificate.get("rule_id")
            if rule_id == "RANDOMIZED_ATE_V3":
                return self._verify_randomized_point(spec, checked)
            if rule_id == "NETWORK_POLICY_VALUE_BERNOULLI_V1":
                return self._verify_network_policy_value_point(spec, checked)
            if rule_id == "NETWORK_DIRECT_EFFECT_THRESHOLD_POINT_V2":
                return self._verify_network_direct_effect_point(spec, checked)
            return self._reject(checked, "Unknown POINT identification certificate rule id.")
        if result.status == IdentificationStatus.PARTIAL:
            if result.certificate.get("rule_id") == "MANSKI_BINARY_ATE_V2":
                return self._verify_manski_partial(spec, checked)
            if result.certificate.get("rule_id") == "ONE_ARM_ATE_BOUNDS_V2":
                return self._verify_one_arm_partial(spec, checked)
            if result.certificate.get("rule_id") == "NETWORK_DIRECT_EFFECT_PROPENSITY_RATIO_BOUNDS_V2":
                return self._verify_network_direct_effect_partial(spec, checked)
            return self._reject(checked, "Unknown PARTIAL identification certificate rule id.")
        if result.status == IdentificationStatus.NO_USEFUL_ID:
            if result.certificate.get("rule_id") == "ONE_ARM_NO_OUTCOME_RESTRICTION_V2":
                return self._verify_one_arm_no_restriction_no_useful(spec, checked)
            checked.verification_status = VerificationStatus.UNSUPPORTED
            checked.verification_message = (
                "NO_USEFUL_ID is a mathematical claim and this verifier does not support the supplied certificate."
            )
            return checked

        checked.verification_status = VerificationStatus.UNSUPPORTED
        checked.verification_message = (
            "This verifier preserves INCOMPATIBLE/UNSUPPORTED statuses but does not promote them to a causal theorem "
            "without a supported certificate."
        )
        return checked

    def _interference_structure_receipt_error(self, spec: IdentificationSpec) -> str | None:
        receipt = spec.interference_structure_receipt
        if receipt is None:
            return "Network theorem requires an auditable I1 interference-structure receipt."
        if not receipt.executable():
            return (
                "I1 interference structure is not admitted to the current analysis "
                f"(analysis_status={receipt.analysis_status})."
            )
        if spec.network_exposure is None:
            return "I1 receipt is present but the formal specification has no network/exposure object."
        if spec.exposure_mapping_claim is None:
            return "I1 receipt is present but exposure_mapping_claim is missing."
        expected = interference_structure_semantic_fingerprint(
            spec.network_exposure,
            spec.exposure_uncertainty,
            spec.exposure_mapping_claim,
        )
        if receipt.semantic_fingerprint != expected:
            return "I1 interference-structure receipt fingerprint does not match the formal network/exposure semantics."
        return None

    def _verify_randomized_point(self, spec: IdentificationSpec, result: IdentificationResult) -> IdentificationResult:
        if result.certificate.get("rule_id") != "RANDOMIZED_ATE_V3":
            return self._reject(result, "Unknown or missing randomized-ATE proof rule id.")

        t, y = spec.query.treatment, spec.query.outcome
        t_domain = spec.domain(t)
        if t_domain is None or t_domain.kind != "binary" or set(t_domain.values or []) != {0, 1}:
            return self._reject(result, "Randomized ATE rule requires binary treatment encoded as {0,1}.")

        confirmed = spec.confirmed_assumptions()
        for name in ("random_assignment", "consistency", "positivity", "no_interference"):
            if name not in confirmed:
                return self._reject(result, f"Required confirmed assumption missing: {name}")

        p = spec.support_domain.get("assignment_probability")
        if p is None or not 0.0 < float(p) < 1.0:
            return self._reject(result, f"Two-arm positivity fails under declared assignment probability p={p}")

        if not spec.information_signature.contains_joint(t, y, regime="experimental"):
            return self._reject(result, "Experimental joint P(T,Y) is not available in the information signature.")

        expected = DifferenceFunctional.model_validate(
            {
                "kind": "difference",
                "left": {"kind": "conditional_mean", "outcome": y, "treatment": t, "treatment_value": 1},
                "right": {"kind": "conditional_mean", "outcome": y, "treatment": t, "treatment_value": 0},
            }
        )
        if result.identified_functional != expected:
            return self._reject(result, "Identified functional does not match RANDOMIZED_ATE_V3.")
        if result.bound_program is not None:
            return self._reject(result, "POINT result must not carry a partial-ID bound program.")
        if result.required_population_objects != expected.required_population_objects():
            return self._reject(result, "Required population objects do not match the point functional AST.")

        result.verification_status = VerificationStatus.VERIFIED
        result.verification_message = "RANDOMIZED_ATE_V3 independent rule replay passed."
        return result

    def _verify_network_policy_value_point(
        self, spec: IdentificationSpec, result: IdentificationResult
    ) -> IdentificationResult:
        receipt_error = self._interference_structure_receipt_error(spec)
        if receipt_error is not None:
            return self._reject(result, receipt_error)
        if spec.query.type != "POLICY_VALUE":
            return self._reject(result, "Network policy-value rule requires a POLICY_VALUE query.")
        if result.query != spec.query:
            return self._reject(result, "IdentificationResult query does not exactly match the verified formal query.")
        if spec.query.resolution != "RESOLVED":
            return self._reject(result, "Network policy-value query must be semantically resolved before theorem verification.")
        if spec.query.authority not in TRUSTED_QUERY_AUTHORITIES:
            return self._reject(result, "Network policy-value query lacks trusted execution authority.")
        semantic_gaps = query_semantics_implementation_gaps(spec.query)
        if semantic_gaps:
            return self._reject(
                result,
                "Network policy-value query contains unsupported execution semantics: " + "; ".join(semantic_gaps),
            )

        network = spec.network_exposure
        if network is None:
            return self._reject(result, "Network policy-value rule requires a typed fixed-network exposure specification.")
        if not network.fixed_network or network.exposure_mapping != "treated_neighbor_count_1hop":
            return self._reject(result, "Unsupported network/exposure semantics for NETWORK_POLICY_VALUE_BERNOULLI_V1.")
        if spec.exposure_mapping_claim != "ASSERTED_SUFFICIENT":
            return self._reject(
                result,
                "Network policy-value rule requires I1 exposure_mapping_claim='ASSERTED_SUFFICIENT'.",
            )
        if spec.structure.representation_type != "fixed_network_interference":
            return self._reject(result, "Network policy-value rule requires structure.representation_type='fixed_network_interference'.")
        required_structure_variables = {
            spec.query.treatment, spec.query.outcome, "neighbor_treatment_count", "context"
        }
        if not required_structure_variables.issubset(set(spec.structure.variables)):
            return self._reject(
                result,
                "StructureSpec must contain treatment, outcome, context, and neighbor_treatment_count for this theorem.",
            )
        if result.network_exposure != network:
            return self._reject(result, "IdentificationResult network/exposure contract differs from the formal specification.")

        t, y = spec.query.treatment, spec.query.outcome
        t_domain = spec.domain(t)
        if t_domain is None or t_domain.kind != "binary" or set(t_domain.values or []) != {0, 1}:
            return self._reject(result, "Network policy-value rule requires binary node treatment encoded as {0,1}.")

        confirmed = spec.confirmed_assumptions()
        required = (
            "random_assignment",
            "consistency",
            "fixed_known_network",
            "one_hop_treated_neighbor_count_sufficiency",
        )
        for name in required:
            if name not in confirmed:
                return self._reject(result, f"Required confirmed assumption missing: {name}")

        if spec.support_domain.get("assignment_mechanism") != "independent_bernoulli":
            return self._reject(result, "Minimal network policy-value rule requires independent Bernoulli assignment.")
        if spec.support_domain.get("target_context_distribution") != "experimental_regime":
            return self._reject(
                result,
                "The v1 policy-value theorem identifies only the context population represented by the experimental regime.",
            )
        p = spec.support_domain.get("assignment_probability")
        if p is None or not 0.0 < float(p) < 1.0:
            return self._reject(result, f"Independent Bernoulli local-state positivity requires 0<p<1, got p={p}.")
        p = float(p)

        if not spec.information_signature.contains_variables(
            ["context", t, "neighbor_treatment_count", y], regime="experimental"
        ):
            return self._reject(
                result,
                "Experimental population information for context W, treatment, treated-neighbor count, and outcome is required.",
            )

        expected = NetworkPolicyValueProgram(
            treatment=t,
            outcome=y,
            network_id=network.network_id,
        )
        if result.identified_functional != expected:
            return self._reject(result, "Identified functional does not match NETWORK_POLICY_VALUE_BERNOULLI_V1.")
        if result.bound_program is not None:
            return self._reject(result, "POINT policy-value result must not carry a partial-ID bound program.")
        if result.required_population_objects != expected.required_population_objects():
            return self._reject(result, "Required population objects do not match the network policy-value program.")
        if result.estimation_nuisance_objects:
            return self._reject(
                result,
                "The current Bernoulli fixture treats local-state probabilities as known design objects, not estimated nuisances.",
            )
        if result.guarantee != "point_identified":
            return self._reject(result, "Network policy-value rule must be marked point_identified.")
        if result.assumptions_used != list(required):
            return self._reject(result, "assumptions_used does not exactly match the theorem's required assumptions.")
        expected_known_design_objects = [
            f"A[{network.network_id}] fixed known network with node order {network.node_ids}",
            f"local_state_propensity_i(a,k|W,A)=P(T_i=a,K_i=k|W,A,design) exactly known from independent Bernoulli(p={p:.6g})",
        ]
        if result.known_design_objects != expected_known_design_objects:
            return self._reject(result, "known_design_objects do not match the independently derived Bernoulli design contract.")
        expected_validity = {
            "regime": "randomized_fixed_network_interference",
            "assignment_mechanism": "independent_bernoulli",
            "assignment_probability": p,
            "network_id": network.network_id,
            "node_ids": network.node_ids,
            "exposure_mapping": network.exposure_mapping,
            "reachable_neighbor_counts": network.reachable_neighbor_counts(),
            "policy_class": "deterministic_binary_network_policy",
            "target_population": spec.query.target_population,
            "target_context_distribution": "experimental_regime",
            "network_exposure_fingerprint": network.semantic_fingerprint(),
        }
        if result.validity_domain != expected_validity:
            return self._reject(result, "validity_domain does not match the independently derived theorem domain.")

        certificate = result.certificate
        if certificate.get("network_id") != network.network_id:
            return self._reject(result, "Certificate network_id does not match the formal network.")
        if certificate.get("node_ids") != network.node_ids:
            return self._reject(result, "Certificate node order does not match the formal network.")
        if certificate.get("undirected_edges") != network.undirected_edges:
            return self._reject(result, "Certificate edges do not match the formal network.")
        if certificate.get("exposure_mapping") != network.exposure_mapping:
            return self._reject(result, "Certificate exposure mapping does not match the formal specification.")
        if certificate.get("assignment_mechanism") != "independent_bernoulli":
            return self._reject(result, "Certificate assignment mechanism is invalid.")
        cert_p = certificate.get("assignment_probability")
        if cert_p is None or not math.isclose(float(cert_p), p, rel_tol=0.0, abs_tol=1e-12):
            return self._reject(result, "Certificate assignment probability does not match the formal design.")
        if certificate.get("target_context_distribution") != "experimental_regime":
            return self._reject(result, "Certificate target-context distribution is invalid.")
        if certificate.get("network_exposure_fingerprint") != network.semantic_fingerprint():
            return self._reject(result, "Certificate network/exposure fingerprint does not match the formal specification.")

        observed_table = certificate.get("local_state_probabilities")
        if not isinstance(observed_table, dict):
            return self._reject(result, "Certificate local-state probability table is missing.")
        degrees = network.degree_map()
        for node in network.node_ids:
            row = observed_table.get(node)
            if not isinstance(row, dict):
                return self._reject(result, f"Missing local-state probabilities for node {node}.")
            expected_keys: set[str] = set()
            total = 0.0
            for a in (0, 1):
                own = p if a == 1 else 1.0 - p
                for k in range(degrees[node] + 1):
                    key = f"a={a},k={k}"
                    expected_keys.add(key)
                    expected_prob = own * math.comb(degrees[node], k) * (p ** k) * (
                        (1.0 - p) ** (degrees[node] - k)
                    )
                    if key not in row or not math.isclose(
                        float(row[key]), expected_prob, rel_tol=0.0, abs_tol=1e-12
                    ):
                        return self._reject(
                            result,
                            f"Local-state probability mismatch for node={node}, {key}.",
                        )
                    if expected_prob <= 0.0:
                        return self._reject(result, "Every reachable local state must have positive design probability.")
                    total += expected_prob
            if set(row) != expected_keys:
                return self._reject(result, f"Certificate contains missing or extra local states for node {node}.")
            if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-12):
                return self._reject(result, f"Local-state probabilities for node {node} do not sum to one.")

        result.verification_status = VerificationStatus.VERIFIED
        result.verification_message = (
            "NETWORK_POLICY_VALUE_BERNOULLI_V1 independent rule/program/design-probability replay passed."
        )
        return result


    def _verify_network_direct_effect_common(self, spec: IdentificationSpec, result: IdentificationResult) -> str | None:
        receipt_error = self._interference_structure_receipt_error(spec)
        if receipt_error is not None:
            return receipt_error
        if spec.query.type != "DIRECT_EFFECT":
            return "Network direct-effect rule requires a DIRECT_EFFECT query."
        if result.query != spec.query:
            return "IdentificationResult query does not exactly match the verified formal query."
        if spec.query.resolution != "RESOLVED":
            return "Network direct-effect query must be semantically resolved before theorem verification."
        if spec.query.authority not in TRUSTED_QUERY_AUTHORITIES:
            return "Network direct-effect query lacks trusted execution authority."
        semantic_gaps = query_semantics_implementation_gaps(spec.query)
        if semantic_gaps:
            return "Network direct-effect query contains unsupported execution semantics: " + "; ".join(semantic_gaps)

        network = spec.network_exposure
        if not isinstance(network, ThresholdNetworkExposureSpec):
            return "Network direct-effect rule requires ThresholdNetworkExposureSpec."
        if not network.fixed_network or network.exposure_mapping != "treated_neighbor_share_threshold_1hop":
            return "Unsupported network/exposure semantics for the current direct-effect theorem family."
        if spec.structure.representation_type != "fixed_network_interference":
            return "Network direct-effect theorem requires fixed_network_interference structure semantics."
        required_structure_variables = {
            spec.query.treatment, spec.query.outcome, "neighbor_threshold_exposure", "context"
        }
        if not required_structure_variables.issubset(set(spec.structure.variables)):
            return "StructureSpec must contain treatment, outcome, context, and neighbor_threshold_exposure."
        if result.network_exposure != network:
            return "IdentificationResult network/exposure contract differs from the formal specification."

        t, y = spec.query.treatment, spec.query.outcome
        t_domain = spec.domain(t)
        if t_domain is None or t_domain.kind != "binary" or set(t_domain.values or []) != {0, 1}:
            return "Network direct-effect rule requires binary treatment encoded as {0,1}."
        if spec.support_domain.get("target_context_distribution") != "observational_regime":
            return "The network direct-effect theorem targets the observed context population only."
        if spec.provenance.get("mode") == "business_llm_network_bridge":
            if spec.support_domain.get("analysis_unit") != ["node"]:
                return "Business-to-network bridge must preserve analysis_unit=['node']."
            expected_binding = {
                "business_analysis_unit": "node",
                "network_entity": "node_id",
                "binding": "identity_semantics_in_fixed_snapshot_theory_fixture",
                "date_time_abstracted": True,
            }
            if spec.support_domain.get("business_entity_binding") != expected_binding:
                return "Business-to-network entity binding is missing or inconsistent with the fixed-snapshot Theory-Mode contract."
            if spec.provenance.get("analysis_unit_binding") != "BusinessInput.node == I1.network_exposure.node_id":
                return "Business-to-network analysis-unit binding provenance is missing or inconsistent."
        if not spec.information_signature.contains_variables(
            ["context", t, "neighbor_threshold_exposure", y], regime="observational"
        ):
            return "Observational population information for X,T,Z,Y is required."
        return None

    def _verify_network_direct_effect_point(
        self, spec: IdentificationSpec, result: IdentificationResult
    ) -> IdentificationResult:
        common_error = self._verify_network_direct_effect_common(spec, result)
        if common_error:
            return self._reject(result, common_error)
        if spec.exposure_mapping_claim != "ASSERTED_SUFFICIENT":
            return self._reject(
                result,
                "Network direct-effect POINT rule requires I1 exposure_mapping_claim='ASSERTED_SUFFICIENT'.",
            )
        if spec.exposure_uncertainty is not None:
            return self._reject(result, "Correct-exposure point rule requires no exposure-uncertainty specification.")
        if result.exposure_uncertainty is not None:
            return self._reject(result, "POINT result must not carry exposure uncertainty for this rule.")

        network = spec.network_exposure
        assert isinstance(network, ThresholdNetworkExposureSpec)
        t, y, z = spec.query.treatment, spec.query.outcome, int(spec.query.exposure_value)
        required = [
            "network_consistency",
            "network_interference_true_exposure_sufficiency",
            "network_unconfoundedness_full_assignment",
            "network_positivity",
            "fixed_known_network",
            "true_exposure_mapping_equals_reference",
        ]
        confirmed = spec.confirmed_assumptions()
        for name in required:
            if name not in confirmed:
                return self._reject(result, f"Required confirmed assumption missing: {name}")

        expected = NetworkDirectEffectPointProgram(
            treatment=t,
            outcome=y,
            network_id=network.network_id,
            reference_exposure_mapping=spec.query.reference_exposure_definition,
            target_exposure_semantics=spec.query.target_exposure_semantics,
            exposure_value=z,
        )
        if result.identified_functional != expected:
            return self._reject(result, "Direct-effect point functional does not match the formal theorem program.")
        if result.bound_program is not None or result.identified_set is not None:
            return self._reject(result, "POINT direct-effect result must not carry a bound program or identified set.")
        if result.required_population_objects != expected.required_population_objects():
            return self._reject(result, "Required population objects do not match the direct-effect point program.")
        if result.assumptions_used != required:
            return self._reject(result, "assumptions_used does not exactly match the direct-effect point theorem.")
        if result.guarantee != "point_identified":
            return self._reject(result, "Correct-threshold direct-effect theorem must be marked point_identified.")

        expected_validity = {
            "regime": "observational_fixed_network_interference",
            "network_id": network.network_id,
            "node_ids": network.node_ids,
            "reference_exposure_mapping": spec.query.reference_exposure_definition,
            "reference_threshold": network.threshold,
            "target_exposure_semantics": spec.query.target_exposure_semantics,
            "target_exposure_value": z,
            "target_context_distribution": "observational_regime",
            "network_exposure_fingerprint": network.semantic_fingerprint(),
        }
        if result.validity_domain != expected_validity:
            return self._reject(result, "validity_domain does not match the direct-effect point theorem domain.")

        cert = result.certificate
        expected_cert = {
            "type": "rule_replay",
            "rule_id": "NETWORK_DIRECT_EFFECT_THRESHOLD_POINT_V2",
            "network_id": network.network_id,
            "node_ids": network.node_ids,
            "undirected_edges": network.undirected_edges,
            "reference_exposure_mapping": spec.query.reference_exposure_definition,
            "reference_threshold": network.threshold,
            "target_exposure_semantics": spec.query.target_exposure_semantics,
            "target_exposure_value": z,
            "target_context_distribution": "observational_regime",
            "network_exposure_fingerprint": network.semantic_fingerprint(),
        }
        if json.loads(json.dumps(cert, allow_nan=False)) != json.loads(json.dumps(expected_cert, allow_nan=False)):
            return self._reject(result, "Direct-effect point certificate does not exactly match the formal specification.")

        result.verification_status = VerificationStatus.VERIFIED
        result.verification_message = (
            "NETWORK_DIRECT_EFFECT_THRESHOLD_POINT_V2 independently coded rule replay passed; "
            "this checks the encoded theorem contract/certificate and is not an external formal proof."
        )
        return result

    def _verify_network_direct_effect_partial(
        self, spec: IdentificationSpec, result: IdentificationResult
    ) -> IdentificationResult:
        return self._reject(result, "LEGACY_EXPOSURE_RATIO_BRIDGE_UNPROVEN: archived Gamma certificates are not accepted as causal identification evidence.")

    def _verify_manski_partial(self, spec: IdentificationSpec, result: IdentificationResult) -> IdentificationResult:
        if result.certificate.get("rule_id") != "MANSKI_BINARY_ATE_V2":
            return self._reject(result, "Unknown or missing binary-Manski proof rule id.")

        t, y = spec.query.treatment, spec.query.outcome
        for variable in (t, y):
            domain = spec.domain(variable)
            if domain is None or domain.kind != "binary" or set(domain.values or []) != {0, 1}:
                return self._reject(result, f"Manski binary ATE rule requires {variable} to be binary {{0,1}}.")

        confirmed = spec.confirmed_assumptions()
        for name in ("consistency", "no_interference"):
            if name not in confirmed:
                return self._reject(result, f"Required confirmed assumption missing: {name}")

        if not spec.information_signature.contains_joint(t, y, regime="observational"):
            return self._reject(result, "Observational joint P(T,Y) is not available in the information signature.")

        expected = ManskiBinaryATEBoundsProgram(treatment=t, outcome=y)
        if result.bound_program != expected:
            return self._reject(result, "Bound program does not match MANSKI_BINARY_ATE_V2.")
        if result.identified_functional is not None:
            return self._reject(result, "PARTIAL result must not claim a point identified functional.")
        if result.required_population_objects != expected.required_population_objects():
            return self._reject(result, "Required population objects do not match the bound program.")
        if result.guarantee != "sharp":
            return self._reject(result, "Supported Manski binary ATE rule must be marked sharp at the population level.")

        expected_lower = {
            f"{t}=1,{y}=1": f"set missing {y}(0)=1",
            f"{t}=1,{y}=0": f"set missing {y}(0)=1",
            f"{t}=0,{y}=1": f"set missing {y}(1)=0",
            f"{t}=0,{y}=0": f"set missing {y}(1)=0",
        }
        expected_upper = {
            f"{t}=1,{y}=1": f"set missing {y}(0)=0",
            f"{t}=1,{y}=0": f"set missing {y}(0)=0",
            f"{t}=0,{y}=1": f"set missing {y}(1)=1",
            f"{t}=0,{y}=0": f"set missing {y}(1)=1",
        }
        if result.certificate.get("lower_completion") != expected_lower:
            return self._reject(result, "Lower-endpoint completion witness is invalid.")
        if result.certificate.get("upper_completion") != expected_upper:
            return self._reject(result, "Upper-endpoint completion witness is invalid.")

        result.verification_status = VerificationStatus.VERIFIED
        result.verification_message = "MANSKI_BINARY_ATE_V2 population sharp-bound rule/program replay passed."
        return result

    def _verify_one_arm_partial(self, spec: IdentificationSpec, result: IdentificationResult) -> IdentificationResult:
        if result.certificate.get("rule_id") != "ONE_ARM_ATE_BOUNDS_V2":
            return self._reject(result, "Unknown one-arm ATE bounds certificate.")
        t, y = spec.query.treatment, spec.query.outcome
        p = spec.support_domain.get("assignment_probability")
        if p not in {0.0, 1.0}:
            return self._reject(result, f"One-arm rule requires assignment_probability in {{0,1}}, got {p}.")
        confirmed = spec.confirmed_assumptions()
        for name in ("random_assignment", "consistency", "no_interference"):
            if name not in confirmed:
                return self._reject(result, f"Required confirmed assumption missing: {name}")
        if not spec.information_signature.contains_joint(t, y, regime="experimental"):
            return self._reject(result, "Experimental P(T,Y) is required for the observed arm.")
        domain = spec.domain(y)
        lower, upper = domain.finite_support_restrictions() if domain is not None else (None, None)
        if lower is None and upper is None:
            return self._reject(
                result,
                "One-arm PARTIAL rule requires at least one finite outcome support restriction; otherwise the ATE is unrestricted.",
            )
        expected = OneArmATEBoundsProgram(
            treatment=t,
            outcome=y,
            observed_treatment_value=int(p),
            outcome_lower=lower,
            outcome_upper=upper,
        )
        if result.bound_program != expected:
            return self._reject(result, "One-arm bound program does not match the declared one-/two-sided support restriction.")
        if result.guarantee != "sharp":
            return self._reject(result, "One-arm support rule must be marked sharp at the population level.")
        if result.required_population_objects != expected.required_population_objects():
            return self._reject(result, "Required population object does not match the one-arm program.")
        certificate = result.certificate
        if certificate.get("observed_treatment_arm") != int(p):
            return self._reject(result, "One-arm certificate records the wrong observed treatment arm.")
        if certificate.get("outcome_lower") != lower or certificate.get("outcome_upper") != upper:
            return self._reject(result, "One-arm certificate support endpoints do not match the formal outcome domain.")
        result.verification_status = VerificationStatus.VERIFIED
        result.verification_message = "ONE_ARM_ATE_BOUNDS_V2 population sharp-bound rule replay passed."
        return result

    def _verify_one_arm_no_restriction_no_useful(self, spec: IdentificationSpec, result: IdentificationResult) -> IdentificationResult:
        if result.certificate.get("rule_id") != "ONE_ARM_NO_OUTCOME_RESTRICTION_V2":
            return self._reject(result, "Unknown one-arm unrestricted ATE certificate.")
        t, y = spec.query.treatment, spec.query.outcome
        p = spec.support_domain.get("assignment_probability")
        if p not in {0.0, 1.0}:
            return self._reject(result, f"One-arm unrestricted rule requires p in {{0,1}}, got {p}.")
        confirmed = spec.confirmed_assumptions()
        for name in ("random_assignment", "consistency", "no_interference"):
            if name not in confirmed:
                return self._reject(result, f"Required confirmed assumption missing: {name}")
        if not spec.information_signature.contains_joint(t, y, regime="experimental"):
            return self._reject(result, "Experimental P(T,Y) is required for the observed arm.")
        domain = spec.domain(y)
        lower, upper = domain.finite_support_restrictions() if domain is not None else (None, None)
        if lower is not None or upper is not None:
            return self._reject(
                result,
                "At least one finite outcome support restriction exists, so the ATE is PARTIAL (possibly half-infinite), not NO_USEFUL_ID.",
            )
        if result.identified_set != {"type": "unbounded_real_line", "lower": "-inf", "upper": "+inf"}:
            return self._reject(result, "NO_USEFUL_ID claim must represent the full real line for this supported rule.")
        if result.guarantee != "trivial":
            return self._reject(result, "Unrestricted one-arm result must be marked trivial.")
        result.verification_status = VerificationStatus.VERIFIED
        result.verification_message = (
            "ONE_ARM_NO_OUTCOME_RESTRICTION_V2 replay passed: one treatment arm is absent and neither finite outcome support endpoint is declared."
        )
        return result

    @staticmethod
    def _reject(result: IdentificationResult, message: str) -> IdentificationResult:
        result.verification_status = VerificationStatus.REJECTED
        result.verification_message = message
        return result
