from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol

from .query_gate import (
    evaluate_query_before_identification,
    query_semantics_implementation_gaps,
)
from .schemas import (
    ConditionalMean,
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
    TraceStep,
    interference_structure_semantic_fingerprint,
    VerificationStatus,
)


class IdentificationBackend(Protocol):
    name: str
    priority: int
    is_fallback: bool

    def supports(self, spec: IdentificationSpec) -> bool: ...
    def solve(self, spec: IdentificationSpec) -> IdentificationResult: ...


class IdentificationVerifierProtocol(Protocol):
    def verify(self, spec: IdentificationSpec, result: IdentificationResult) -> IdentificationResult: ...


def _is_binary(spec: IdentificationSpec, variable: str) -> bool:
    domain = spec.domain(variable)
    return bool(domain is not None and domain.kind == "binary" and set(domain.values or []) == {0, 1})


def _assignment_probability(spec: IdentificationSpec) -> float | None:
    p = spec.support_domain.get("assignment_probability")
    return None if p is None else float(p)


def _is_executable_ate_query(spec: IdentificationSpec) -> bool:
    """Defense in depth; the engine also applies a central preflight gate."""
    return (
        spec.query.type == "ATE"
        and spec.query.resolution == "RESOLVED"
        and spec.query.authority in {"HUMAN_CONFIRMED", "TRUSTED_FIXTURE"}
        and not query_semantics_implementation_gaps(spec.query)
    )


def _is_executable_policy_value_query(spec: IdentificationSpec) -> bool:
    """Defense in depth for the minimal fixed-network POLICY_VALUE theorem."""
    return (
        spec.query.type == "POLICY_VALUE"
        and spec.query.resolution == "RESOLVED"
        and spec.query.authority in {"HUMAN_CONFIRMED", "TRUSTED_FIXTURE"}
        and not query_semantics_implementation_gaps(spec.query)
    )


def _is_executable_network_direct_effect_query(spec: IdentificationSpec) -> bool:
    """Defense in depth for the current fixed-network DIRECT_EFFECT theorem family."""
    return (
        spec.query.type == "DIRECT_EFFECT"
        and spec.query.resolution == "RESOLVED"
        and spec.query.authority in {"HUMAN_CONFIRMED", "TRUSTED_FIXTURE"}
        and not query_semantics_implementation_gaps(spec.query)
    )


def _has_authorized_interference_structure(spec: IdentificationSpec) -> bool:
    """Whether I1 supplied a fingerprint-matched structure admitted to analysis.

    This is deliberately an *analysis qualification* check, not a declaration that
    the structure is the unique true causal structure.
    """

    receipt = spec.interference_structure_receipt
    if (
        receipt is None
        or spec.network_exposure is None
        or spec.exposure_mapping_claim is None
    ):
        return False
    if not receipt.executable():
        return False
    expected = interference_structure_semantic_fingerprint(
        spec.network_exposure,
        spec.exposure_uncertainty,
        spec.exposure_mapping_claim,
    )
    return receipt.semantic_fingerprint == expected


def _interference_structure_preflight(spec: IdentificationSpec) -> IdentificationResult | None:
    """Return a structured abstention for unresolved/rejected I1 network input."""

    if spec.query.type not in {"DIRECT_EFFECT", "POLICY_VALUE", "SPILLOVER_EFFECT", "NETWORK_RESPONSE_SURFACE", "NETWORK_MAJORITY_RESPONSE_POLICY_SCORE"}:
        return None
    if spec.network_exposure is None:
        return None
    receipt = spec.interference_structure_receipt
    if receipt is None:
        return IdentificationResult(
            status=IdentificationStatus.UNSUPPORTED,
            query=spec.query,
            backend="pre_identification_i1_gate_v2",
            guarantee="none",
            reason_code="INTERFERENCE_STRUCTURE_RECEIPT_MISSING",
            message="Network Identification requires an auditable I1 structure receipt.",
            verification_status=VerificationStatus.UNSUPPORTED,
            verification_message="I1 structure qualification is missing.",
            trace=[TraceStep(step="i1_structure_gate", outcome="FAIL", detail="No I1 receipt was supplied.")],
        )
    if receipt.analysis_status == "UNRESOLVED":
        return IdentificationResult(
            status=IdentificationStatus.UNSUPPORTED,
            query=spec.query,
            backend="pre_identification_i1_gate_v2",
            guarantee="none",
            reason_code="INTERFERENCE_STRUCTURE_UNRESOLVED",
            message=(
                "The supplied interference structure is reviewable but has not been admitted to the current analysis. "
                "I1 does not treat a model proposal as causal truth."
            ),
            verification_status=VerificationStatus.UNSUPPORTED,
            verification_message="I1 analysis_status is UNRESOLVED.",
            trace=[TraceStep(step="i1_structure_gate", outcome="FAIL", detail=f"source_status={receipt.source_status}, analysis_status=UNRESOLVED")],
        )
    if receipt.analysis_status == "REJECTED":
        return IdentificationResult(
            status=IdentificationStatus.UNSUPPORTED,
            query=spec.query,
            backend="pre_identification_i1_gate_v2",
            guarantee="none",
            reason_code="INTERFERENCE_STRUCTURE_REJECTED",
            message="The supplied interference structure was rejected for this analysis.",
            verification_status=VerificationStatus.UNSUPPORTED,
            verification_message="I1 analysis_status is REJECTED.",
            trace=[TraceStep(step="i1_structure_gate", outcome="FAIL", detail=f"source_status={receipt.source_status}, analysis_status=REJECTED")],
        )
    expected = interference_structure_semantic_fingerprint(
        spec.network_exposure, spec.exposure_uncertainty, spec.exposure_mapping_claim
    )
    if receipt.semantic_fingerprint != expected:
        return IdentificationResult(
            status=IdentificationStatus.UNSUPPORTED,
            query=spec.query,
            backend="pre_identification_i1_gate_v2",
            guarantee="none",
            reason_code="INTERFERENCE_STRUCTURE_FINGERPRINT_MISMATCH",
            message="I1 receipt does not match the network/exposure semantics in the formal specification.",
            verification_status=VerificationStatus.UNSUPPORTED,
            verification_message="I1 semantic fingerprint mismatch.",
            trace=[TraceStep(step="i1_structure_gate", outcome="FAIL", detail="Receipt fingerprint mismatch.")],
        )
    return None


def _bernoulli_local_state_probabilities(spec: IdentificationSpec, p: float) -> dict[str, dict[str, float]]:
    network = spec.network_exposure
    if network is None:
        raise ValueError("network exposure specification is required")
    result: dict[str, dict[str, float]] = {}
    for node, degree in network.degree_map().items():
        states: dict[str, float] = {}
        for a in (0, 1):
            own = p if a == 1 else 1.0 - p
            for k in range(degree + 1):
                neighbor = math.comb(degree, k) * (p ** k) * ((1.0 - p) ** (degree - k))
                states[f"a={a},k={k}"] = own * neighbor
        result[node] = states
    return result


@dataclass
class RandomizedATEBackend:
    """Point identification of a binary-treatment ATE with two-arm support."""

    name: str = "randomized_ate_v3"
    priority: int = 100
    is_fallback: bool = False

    def supports(self, spec: IdentificationSpec) -> bool:
        t, y = spec.query.treatment, spec.query.outcome
        p = _assignment_probability(spec)
        confirmed = spec.confirmed_assumptions()
        return (
            spec.causal_semantics == "potential_outcomes"
            and _is_executable_ate_query(spec)
            and _is_binary(spec, t)
            and spec.information_signature.contains_joint(t, y, regime="experimental")
            and "random_assignment" in confirmed
            and "positivity" in confirmed
            and p is not None
            and 0.0 < p < 1.0
        )

    def solve(self, spec: IdentificationSpec) -> IdentificationResult:
        t, y = spec.query.treatment, spec.query.outcome
        p = _assignment_probability(spec)
        confirmed = spec.confirmed_assumptions()
        trace: list[TraceStep] = [
            TraceStep(
                step="routing",
                outcome="PASS",
                detail="Specification matches the randomized two-arm binary-treatment ATE backend.",
            )
        ]

        required = ["random_assignment", "consistency", "positivity", "no_interference"]
        missing = [name for name in required if name not in confirmed]
        if missing or p is None or not (0.0 < p < 1.0):
            trace.append(
                TraceStep(
                    step="point_rule_conditions",
                    outcome="FAIL",
                    detail=f"Randomized point rule conditions not met; missing={missing}, p={p}.",
                )
            )
            return IdentificationResult(
                status=IdentificationStatus.UNSUPPORTED,
                query=spec.query,
                backend=self.name,
                guarantee="none",
                reason_code="POINT_RULE_NOT_APPLICABLE",
                message="The randomized point-identification rule is not applicable to this specification.",
                trace=trace,
            )

        trace.extend(
            [
                TraceStep(
                    step="identifying_assumptions",
                    outcome="PASS",
                    detail=f"Confirmed: {required}",
                ),
                TraceStep(
                    step="positivity",
                    outcome="PASS",
                    detail=f"Declared assignment probability p={p:.3f} lies strictly between 0 and 1.",
                ),
            ]
        )

        functional = DifferenceFunctional(
            left=ConditionalMean(outcome=y, treatment=t, treatment_value=1),
            right=ConditionalMean(outcome=y, treatment=t, treatment_value=0),
        )
        trace.append(
            TraceStep(
                step="identification_rule",
                outcome="PASS",
                detail=(
                    "By random assignment + consistency + positivity under unit-level no-interference semantics, "
                    "E[Y(t)] = E[Y | T=t] for t in {0,1}."
                ),
            )
        )

        return IdentificationResult(
            status=IdentificationStatus.POINT,
            query=spec.query,
            backend=self.name,
            identified_functional=functional,
            required_population_objects=functional.required_population_objects(),
            assumptions_used=required,
            validity_domain={
                "assignment_probability": p,
                "analysis_unit": spec.support_domain.get("analysis_unit", []),
                "regime": "randomized_experiment",
            },
            guarantee="point_identified",
            certificate={
                "type": "rule_replay",
                "rule_id": "RANDOMIZED_ATE_V3",
                "conditions": [
                    "binary treatment",
                    "experimental P(T,Y)",
                    "random_assignment",
                    "consistency",
                    "two-arm positivity",
                    "no_interference",
                ],
            },
            trace=trace,
            message="ATE is point identified by the randomized two-arm population mean difference.",
        )


@dataclass
class OneArmATESupportBackend:
    """Handle degenerate one-arm experimental support without overclaiming.

    A single finite lower or upper outcome support bound already restricts the
    missing potential-outcome mean and therefore yields a sharp half-infinite
    ATE identified set. Two finite bounds yield a finite interval. Only when
    neither side is finitely restricted is the ATE unrestricted over R.
    """

    name: str = "one_arm_ate_support_v2"
    priority: int = 90
    is_fallback: bool = False

    def supports(self, spec: IdentificationSpec) -> bool:
        t, y = spec.query.treatment, spec.query.outcome
        p = _assignment_probability(spec)
        return (
            spec.causal_semantics == "potential_outcomes"
            and _is_executable_ate_query(spec)
            and _is_binary(spec, t)
            and spec.information_signature.contains_joint(t, y, regime="experimental")
            and "random_assignment" in spec.confirmed_assumptions()
            and p in {0.0, 1.0}
        )

    def solve(self, spec: IdentificationSpec) -> IdentificationResult:
        t, y = spec.query.treatment, spec.query.outcome
        p = _assignment_probability(spec)
        assert p in {0.0, 1.0}
        observed_arm = int(p)
        confirmed = spec.confirmed_assumptions()
        trace = [
            TraceStep(
                step="routing",
                outcome="PASS",
                detail=f"Only treatment arm {observed_arm} has support under the declared design.",
            )
        ]
        required = ["random_assignment", "consistency", "no_interference"]
        missing = [name for name in required if name not in confirmed]
        if missing:
            return IdentificationResult(
                status=IdentificationStatus.UNSUPPORTED,
                query=spec.query,
                backend=self.name,
                guarantee="none",
                reason_code="BACKEND_APPLICABILITY_FAILURE",
                message=f"One-arm support rule lacks confirmed assumptions: {missing}.",
                trace=trace,
            )

        outcome_domain = spec.domain(y)
        lower_y, upper_y = (
            outcome_domain.finite_support_restrictions()
            if outcome_domain is not None
            else (None, None)
        )

        if lower_y is None and upper_y is None:
            trace.append(
                TraceStep(
                    step="missing_arm_domain",
                    outcome="FAIL",
                    detail=(
                        "The unobserved potential-outcome arm has no declared finite lower or upper support restriction; "
                        "its mean is unrestricted over the real line."
                    ),
                )
            )
            return IdentificationResult(
                status=IdentificationStatus.NO_USEFUL_ID,
                query=spec.query,
                backend=self.name,
                identified_set={"type": "unbounded_real_line", "lower": "-inf", "upper": "+inf"},
                assumptions_used=required,
                validity_domain={
                    "observed_treatment_arm": observed_arm,
                    "assignment_probability": p,
                    "regime": "one_arm_experimental",
                },
                guarantee="trivial",
                certificate={
                    "type": "rule_replay",
                    "rule_id": "ONE_ARM_NO_OUTCOME_RESTRICTION_V2",
                    "observed_treatment_arm": observed_arm,
                    "outcome_lower": None,
                    "outcome_upper": None,
                    "reason": "missing potential-outcome mean has no finite declared lower or upper support restriction",
                },
                reason_code="UNRESTRICTED_MISSING_ARM",
                message=(
                    "The randomized point rule fails because one treatment arm has zero support. "
                    "With no finite outcome support restriction on either side, the ATE identified set is the full real line."
                ),
                trace=trace,
            )

        program = OneArmATEBoundsProgram(
            treatment=t,
            outcome=y,
            observed_treatment_value=observed_arm,
            outcome_lower=lower_y,
            outcome_upper=upper_y,
        )
        support_description = []
        if lower_y is not None:
            support_description.append(f"Y >= {lower_y:g}")
        if upper_y is not None:
            support_description.append(f"Y <= {upper_y:g}")
        trace.append(
            TraceStep(
                step="partial_identification_rule",
                outcome="PASS",
                detail=(
                    f"Declared outcome support restriction(s) {', '.join(support_description)} constrain the missing "
                    "potential-outcome mean. The resulting one-arm ATE set is sharp and may be finite or half-infinite."
                ),
            )
        )
        return IdentificationResult(
            status=IdentificationStatus.PARTIAL,
            query=spec.query,
            backend=self.name,
            bound_program=program,
            identified_set={
                "type": "interval_functional_extended_real",
                "expression": program.to_text(),
                "allows_infinite_endpoint": True,
            },
            required_population_objects=program.required_population_objects(),
            assumptions_used=required,
            validity_domain={
                "observed_treatment_arm": observed_arm,
                "outcome_lower": lower_y,
                "outcome_upper": upper_y,
                "regime": "one_arm_experimental",
            },
            guarantee="sharp",
            certificate={
                "type": "support_completion_witness",
                "rule_id": "ONE_ARM_ATE_BOUNDS_V2",
                "observed_treatment_arm": observed_arm,
                "outcome_lower": lower_y,
                "outcome_upper": upper_y,
            },
            message=(
                "ATE is partially identified because one treatment arm is unobserved but the outcome domain supplies "
                "at least one finite support restriction."
            ),
            trace=trace,
        )


@dataclass
class BinaryManskiATEBackend:
    """Sharp worst-case ATE bounds for binary T/Y observational data."""

    name: str = "manski_binary_ate_v2"
    priority: int = 80
    is_fallback: bool = False

    def supports(self, spec: IdentificationSpec) -> bool:
        t, y = spec.query.treatment, spec.query.outcome
        return (
            spec.causal_semantics == "potential_outcomes"
            and _is_executable_ate_query(spec)
            and _is_binary(spec, t)
            and _is_binary(spec, y)
            and spec.information_signature.contains_joint(t, y, regime="observational")
        )

    def solve(self, spec: IdentificationSpec) -> IdentificationResult:
        t, y = spec.query.treatment, spec.query.outcome
        confirmed = spec.confirmed_assumptions()
        trace = [
            TraceStep(
                step="routing",
                outcome="PASS",
                detail="Specification matches binary observational ATE bounds with P(T,Y).",
            )
        ]
        required = ["consistency", "no_interference"]
        missing = [name for name in required if name not in confirmed]
        if missing:
            trace.append(
                TraceStep(
                    step="identifying_assumptions",
                    outcome="FAIL",
                    detail=f"Missing assumptions needed to interpret unit-level potential outcomes: {missing}",
                )
            )
            return IdentificationResult(
                status=IdentificationStatus.UNSUPPORTED,
                query=spec.query,
                backend=self.name,
                guarantee="none",
                reason_code="BACKEND_APPLICABILITY_FAILURE",
                message="Binary Manski bounds backend cannot be certified under the declared semantics.",
                trace=trace,
            )

        program = ManskiBinaryATEBoundsProgram(treatment=t, outcome=y)
        trace.extend(
            [
                TraceStep(
                    step="information_regime",
                    outcome="PASS",
                    detail="Observational population joint P(T,Y) is available.",
                ),
                TraceStep(
                    step="partial_identification_rule",
                    outcome="PASS",
                    detail=(
                        "Unobserved binary counterfactual outcomes are allowed to range over {0,1}. "
                        "Worst/best-case completion yields sharp Manski ATE bounds."
                    ),
                ),
            ]
        )
        return IdentificationResult(
            status=IdentificationStatus.PARTIAL,
            query=spec.query,
            backend=self.name,
            bound_program=program,
            identified_set={
                "type": "interval_functional",
                "lower": f"-P({y}=0,{t}=1)-P({y}=1,{t}=0)",
                "upper": f"P({y}=1,{t}=1)+P({y}=0,{t}=0)",
            },
            required_population_objects=program.required_population_objects(),
            assumptions_used=required,
            validity_domain={
                "treatment_domain": [0, 1],
                "outcome_domain": [0, 1],
                "regime": "observational",
            },
            guarantee="sharp",
            certificate={
                "type": "endpoint_completion_witness",
                "rule_id": "MANSKI_BINARY_ATE_V2",
                "lower_completion": {
                    f"{t}=1,{y}=1": f"set missing {y}(0)=1",
                    f"{t}=1,{y}=0": f"set missing {y}(0)=1",
                    f"{t}=0,{y}=1": f"set missing {y}(1)=0",
                    f"{t}=0,{y}=0": f"set missing {y}(1)=0",
                },
                "upper_completion": {
                    f"{t}=1,{y}=1": f"set missing {y}(0)=0",
                    f"{t}=1,{y}=0": f"set missing {y}(0)=0",
                    f"{t}=0,{y}=1": f"set missing {y}(1)=1",
                    f"{t}=0,{y}=0": f"set missing {y}(1)=1",
                },
            },
            trace=trace,
            message=(
                "ATE is not point identified from observational P(T,Y) alone, but binary outcomes imply sharp worst-case bounds."
            ),
        )


@dataclass
class NetworkDirectEffectThresholdPointBackend:
    """Point-ID of an average direct effect when the threshold exposure mapping is correct.

    This is the strong-assumption member of the paired network benchmark.
    It uses the standard g-formula under network consistency, full-assignment
    unconfoundedness, positivity, a fixed known network, and a correctly specified
    binary one-hop threshold exposure mapping.
    """

    name: str = "network_direct_effect_threshold_point_v2"
    priority: int = 109
    is_fallback: bool = False

    def supports(self, spec: IdentificationSpec) -> bool:
        t, y = spec.query.treatment, spec.query.outcome
        network = spec.network_exposure
        return (
            spec.causal_semantics == "potential_outcomes"
            and _is_executable_network_direct_effect_query(spec)
            and _has_authorized_interference_structure(spec)
            and _is_binary(spec, t)
            and isinstance(network, ThresholdNetworkExposureSpec)
            and network.fixed_network
            and spec.exposure_uncertainty is None
            and spec.exposure_mapping_claim == "ASSERTED_SUFFICIENT"
            and spec.structure.representation_type == "fixed_network_interference"
            and {t, y, "neighbor_threshold_exposure", "context"}.issubset(
                set(spec.structure.variables)
            )
            and spec.support_domain.get("target_context_distribution") == "observational_regime"
            and spec.information_signature.contains_variables(
                ["context", t, "neighbor_threshold_exposure", y], regime="observational"
            )
        )

    def solve(self, spec: IdentificationSpec) -> IdentificationResult:
        t, y = spec.query.treatment, spec.query.outcome
        network = spec.network_exposure
        assert isinstance(network, ThresholdNetworkExposureSpec)
        z = int(spec.query.exposure_value)
        required = [
            "network_consistency",
            "network_interference_true_exposure_sufficiency",
            "network_unconfoundedness_full_assignment",
            "network_positivity",
            "fixed_known_network",
            "true_exposure_mapping_equals_reference",
        ]
        confirmed = spec.confirmed_assumptions()
        missing = [name for name in required if name not in confirmed]
        trace = [
            TraceStep(
                step="routing",
                outcome="PASS",
                detail=(
                    "Specification matches the explicit-reference/true-target network DIRECT_EFFECT point rule."
                ),
            )
        ]
        if missing:
            trace.append(
                TraceStep(
                    step="identifying_assumptions",
                    outcome="FAIL",
                    detail=f"Missing confirmed assumptions: {missing}.",
                )
            )
            return IdentificationResult(
                status=IdentificationStatus.UNSUPPORTED,
                query=spec.query,
                backend=self.name,
                guarantee="none",
                reason_code="NETWORK_DIRECT_EFFECT_POINT_RULE_NOT_APPLICABLE",
                message=(
                    "The correct-threshold network direct-effect point rule cannot be certified under the declared assumptions."
                ),
                trace=trace,
            )

        program = NetworkDirectEffectPointProgram(
            treatment=t,
            outcome=y,
            network_id=network.network_id,
            reference_exposure_mapping=spec.query.reference_exposure_definition,
            target_exposure_semantics=spec.query.target_exposure_semantics,
            exposure_value=z,
        )
        trace.extend(
            [
                TraceStep(
                    step="identifying_assumptions",
                    outcome="PASS",
                    detail=f"Confirmed: {required}.",
                ),
                TraceStep(
                    step="identification_rule",
                    outcome="PASS",
                    detail=(
                        "With the declared threshold exposure mapping correct, network consistency, full-assignment "
                        "unconfoundedness, and positivity identify the CAPO by E[Y|T=t,Z=z,X]; averaging the "
                        "T=1 versus T=0 contrast over P_obs(X) identifies the ADE at the fixed exposure level."
                    ),
                ),
            ]
        )
        return IdentificationResult(
            status=IdentificationStatus.POINT,
            query=spec.query,
            backend=self.name,
            identified_functional=program,
            network_exposure=network.model_copy(deep=True),
            required_population_objects=program.required_population_objects(),
            assumptions_used=required,
            validity_domain={
                "regime": "observational_fixed_network_interference",
                "network_id": network.network_id,
                "node_ids": network.node_ids,
                "reference_exposure_mapping": spec.query.reference_exposure_definition,
                "reference_threshold": network.threshold,
                "target_exposure_semantics": spec.query.target_exposure_semantics,
                "target_exposure_value": z,
                "target_context_distribution": "observational_regime",
                "network_exposure_fingerprint": network.semantic_fingerprint(),
            },
            guarantee="point_identified",
            certificate={
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
            },
            trace=trace,
            message=(
                "The average direct effect for the true sufficient exposure state is point identified because the declared point-world assumptions equate the true exposure mapping g* with the employed/reference mapping g."
            ),
        )


@dataclass
class NetworkDirectEffectSensitivityBoundsBackend:
    """PARTIAL-ID bounds under exposure-mapping propensity-ratio sensitivity.

    This implements a deliberately narrow constant-Gamma special case of
    Schröder, Oprescu, Feuerriegel & Kallus (2026): Eq. (9) bounds the ratio
    between true and employed exposure propensities; Theorem 4.2 gives the CAPO
    bound functional and Supplement C.3 translates the endpoints to direct-effect
    bounds. For discrete exposure, a separate supplementary applicability condition
    is checked before the result is labeled sharp. Finite-sample orthogonal
    estimation from that paper is *not* implemented here.
    """

    name: str = "network_direct_effect_sensitivity_bounds_v2"
    priority: int = 110
    is_fallback: bool = False

    def supports(self, spec: IdentificationSpec) -> bool:
        t, y = spec.query.treatment, spec.query.outcome
        network = spec.network_exposure
        sensitivity = spec.exposure_uncertainty
        return (
            spec.causal_semantics == "potential_outcomes"
            and _is_executable_network_direct_effect_query(spec)
            and _has_authorized_interference_structure(spec)
            and _is_binary(spec, t)
            and isinstance(network, ThresholdNetworkExposureSpec)
            and network.fixed_network
            and isinstance(sensitivity, ExposurePropensityRatioSensitivitySpec)
            and sensitivity.gamma > 1.0
            and spec.exposure_mapping_claim == "REFERENCE_WITH_UNCERTAINTY"
            and spec.structure.representation_type == "fixed_network_interference"
            and {t, y, "neighbor_threshold_exposure", "context"}.issubset(
                set(spec.structure.variables)
            )
            and spec.support_domain.get("target_context_distribution") == "observational_regime"
            and spec.information_signature.contains_variables(
                ["context", t, "neighbor_threshold_exposure", y], regime="observational"
            )
        )

    def solve(self, spec: IdentificationSpec) -> IdentificationResult:
        return IdentificationResult(
            status=IdentificationStatus.UNSUPPORTED, query=spec.query, backend=self.name,
            guarantee="none", reason_code="LEGACY_EXPOSURE_RATIO_BRIDGE_UNPROVEN",
            message="Quarantined: an exposure-propensity ratio restriction alone does not establish the outcome-density-ratio bridge required by this bound program. No causal bounds or EstimationRequest are issued.",
            trace=[TraceStep(step="legacy_theorem_quarantine", outcome="FAIL", detail="Population coverage counterexample; see docs/V0_2_19_THEORY_REVIEW_ZH.md.")],
        )


@dataclass
class ConservativeDirectEffectFallbackBackend:
    """Coverage fallback for executable network DIRECT_EFFECT theory queries."""

    name: str = "conservative_network_direct_effect_fallback_v1"
    priority: int = 1
    is_fallback: bool = True

    def supports(self, spec: IdentificationSpec) -> bool:
        return (
            spec.causal_semantics == "potential_outcomes"
            and _is_executable_network_direct_effect_query(spec)
        )

    def solve(self, spec: IdentificationSpec) -> IdentificationResult:
        return IdentificationResult(
            status=IdentificationStatus.UNSUPPORTED,
            query=spec.query,
            backend=self.name,
            guarantee="none",
            reason_code="NO_SUPPORTED_IDENTIFICATION_BACKEND",
            message=(
                "No registered trusted network DIRECT_EFFECT backend covers this formal specification. "
                "This is a software-coverage limitation, not a proof of mathematical non-identification."
            ),
            trace=[
                TraceStep(
                    step="routing",
                    outcome="FAIL",
                    detail=(
                        "No trusted direct-effect theorem matches the declared network, exposure semantics, information regime, uncertainty model, and assumptions."
                    ),
                )
            ],
        )


@dataclass
class NetworkPolicyValueBernoulliBackend:
    """Point-ID of a deterministic network policy value under known Bernoulli design.

    This is intentionally narrow: one fixed known undirected network, binary node
    treatment, one-hop treated-neighbor-count exposure, and independent common-p
    Bernoulli randomization. It identifies the population response surface needed
    by a downstream policy-value estimator; it does not implement policy search.
    """

    name: str = "network_policy_value_bernoulli_v1"
    priority: int = 110
    is_fallback: bool = False

    def supports(self, spec: IdentificationSpec) -> bool:
        t, y = spec.query.treatment, spec.query.outcome
        p = _assignment_probability(spec)
        network = spec.network_exposure
        return (
            spec.causal_semantics == "potential_outcomes"
            and _is_executable_policy_value_query(spec)
            and _has_authorized_interference_structure(spec)
            and spec.exposure_mapping_claim == "ASSERTED_SUFFICIENT"
            and _is_binary(spec, t)
            and network is not None
            and network.fixed_network
            and network.exposure_mapping == "treated_neighbor_count_1hop"
            and spec.structure.representation_type == "fixed_network_interference"
            and {t, y, "neighbor_treatment_count", "context"}.issubset(set(spec.structure.variables))
            and spec.support_domain.get("assignment_mechanism") == "independent_bernoulli"
            and spec.support_domain.get("target_context_distribution") == "experimental_regime"
            and p is not None
            and 0.0 < p < 1.0
            and spec.information_signature.contains_variables(
                ["context", t, "neighbor_treatment_count", y], regime="experimental"
            )
        )

    def solve(self, spec: IdentificationSpec) -> IdentificationResult:
        t, y = spec.query.treatment, spec.query.outcome
        network = spec.network_exposure
        p = _assignment_probability(spec)
        assert network is not None and p is not None and 0.0 < p < 1.0

        trace: list[TraceStep] = [
            TraceStep(
                step="routing",
                outcome="PASS",
                detail=(
                    "Specification matches the minimal fixed-network POLICY_VALUE backend: "
                    "binary node treatment, one-hop treated-neighbor-count exposure, and known independent Bernoulli assignment."
                ),
            )
        ]
        required = [
            "random_assignment",
            "consistency",
            "fixed_known_network",
            "one_hop_treated_neighbor_count_sufficiency",
        ]
        confirmed = spec.confirmed_assumptions()
        missing = [name for name in required if name not in confirmed]
        if missing:
            trace.append(
                TraceStep(
                    step="identifying_assumptions",
                    outcome="FAIL",
                    detail=f"Missing confirmed assumptions: {missing}.",
                )
            )
            return IdentificationResult(
                status=IdentificationStatus.UNSUPPORTED,
                query=spec.query,
                backend=self.name,
                guarantee="none",
                reason_code="POLICY_VALUE_RULE_NOT_APPLICABLE",
                message=(
                    "The minimal network policy-value point-identification rule is not applicable because required assumptions are unconfirmed."
                ),
                trace=trace,
            )

        program = NetworkPolicyValueProgram(
            treatment=t,
            outcome=y,
            network_id=network.network_id,
        )
        local_g = _bernoulli_local_state_probabilities(spec, p)
        trace.extend(
            [
                TraceStep(
                    step="identifying_assumptions",
                    outcome="PASS",
                    detail=f"Confirmed: {required}.",
                ),
                TraceStep(
                    step="local_state_positivity",
                    outcome="PASS",
                    detail=(
                        f"Common Bernoulli p={p:.6g} lies strictly in (0,1); every reachable local state "
                        "(T_i=a, K_i=k) has positive design probability for the fixed finite network."
                    ),
                ),
                TraceStep(
                    step="identification_rule",
                    outcome="PASS",
                    detail=(
                        "Random assignment + consistency + the declared one-hop exposure mapping identify "
                        "mu_i(a,k,W,A)=E[Y_i | W,A,T_i=a,K_i=k]. For the same context population represented by "
                        "the experimental regime, substitution into a deterministic policy's induced local states identifies "
                        "V(pi)=E_{W~P_exp}[N^{-1} sum_i mu_i(pi_i(W),K_i(pi(W)),W,A)]."
                    ),
                ),
            ]
        )

        return IdentificationResult(
            status=IdentificationStatus.POINT,
            query=spec.query,
            backend=self.name,
            identified_functional=program,
            network_exposure=network.model_copy(deep=True),
            required_population_objects=program.required_population_objects(),
            estimation_nuisance_objects=[],
            known_design_objects=[
                f"A[{network.network_id}] fixed known network with node order {network.node_ids}",
                f"local_state_propensity_i(a,k|W,A)=P(T_i=a,K_i=k|W,A,design) exactly known from independent Bernoulli(p={p:.6g})",
            ],
            assumptions_used=required,
            validity_domain={
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
            },
            guarantee="point_identified",
            certificate={
                "type": "rule_replay",
                "rule_id": "NETWORK_POLICY_VALUE_BERNOULLI_V1",
                "network_id": network.network_id,
                "node_ids": network.node_ids,
                "undirected_edges": network.undirected_edges,
                "exposure_mapping": network.exposure_mapping,
                "assignment_mechanism": "independent_bernoulli",
                "assignment_probability": p,
                "target_context_distribution": "experimental_regime",
                "network_exposure_fingerprint": network.semantic_fingerprint(),
                "local_state_probabilities": local_g,
            },
            trace=trace,
            message=(
                "The deterministic network policy value is point identified under the declared fixed-network local-exposure Bernoulli design."
            ),
        )


@dataclass
class ConservativePolicyValueFallbackBackend:
    """Coverage fallback for executable POLICY_VALUE queries not covered by a trusted theorem."""

    name: str = "conservative_policy_value_fallback_v1"
    priority: int = 1
    is_fallback: bool = True

    def supports(self, spec: IdentificationSpec) -> bool:
        return spec.causal_semantics == "potential_outcomes" and _is_executable_policy_value_query(spec)

    def solve(self, spec: IdentificationSpec) -> IdentificationResult:
        return IdentificationResult(
            status=IdentificationStatus.UNSUPPORTED,
            query=spec.query,
            backend=self.name,
            guarantee="none",
            reason_code="NO_SUPPORTED_IDENTIFICATION_BACKEND",
            message=(
                "No registered trusted POLICY_VALUE backend covers this formal specification. "
                "This is a system-coverage limitation, not a mathematical proof of non-identifiability."
            ),
            trace=[
                TraceStep(
                    step="routing",
                    outcome="FAIL",
                    detail=(
                        "No trusted policy-value backend matches the declared network, exposure mapping, assignment design, support, and assumptions."
                    ),
                )
            ],
        )


@dataclass
class ConservativeATEFallbackBackend:
    """Coverage fallback: unsupported is a system statement, not a causal theorem."""

    name: str = "conservative_ate_fallback_v2"
    priority: int = 1
    is_fallback: bool = True

    def supports(self, spec: IdentificationSpec) -> bool:
        return spec.causal_semantics == "potential_outcomes" and _is_executable_ate_query(spec)

    def solve(self, spec: IdentificationSpec) -> IdentificationResult:
        return IdentificationResult(
            status=IdentificationStatus.UNSUPPORTED,
            query=spec.query,
            backend=self.name,
            guarantee="none",
            reason_code="NO_SUPPORTED_IDENTIFICATION_BACKEND",
            message=(
                "No registered trusted backend covers this specification. This is a system-coverage limitation, "
                "not a mathematical proof that the causal query is non-identifiable."
            ),
            trace=[
                TraceStep(
                    step="routing",
                    outcome="FAIL",
                    detail="No trusted backend with matching causal semantics, information regime, support, and variable domains is implemented.",
                )
            ],
        )


class IdentificationEngine:
    """Route candidate backends; production pipeline selects only after verification.

    v0.2.9 deliberately avoids a global status ranking such as POINT > PARTIAL >
    INCOMPATIBLE. `solve_verified` first verifies candidate claims, treats a
    verified INCOMPATIBLE result as terminal, checks for conflicting verified
    conclusions, and only then chooses the most informative compatible result.
    """

    def __init__(self, backends: list[IdentificationBackend] | None = None):
        from .majority_response import MajorityResponseBackend
        from .majority_score import MajorityScoreBackend
        self.backends = backends or [
            MajorityScoreBackend(),
            MajorityResponseBackend(),
            RandomizedATEBackend(),
            OneArmATESupportBackend(),
            BinaryManskiATEBackend(),
            NetworkDirectEffectSensitivityBoundsBackend(),
            NetworkDirectEffectThresholdPointBackend(),
            NetworkPolicyValueBernoulliBackend(),
            ConservativeATEFallbackBackend(),
            ConservativePolicyValueFallbackBackend(),
            ConservativeDirectEffectFallbackBackend(),
        ]

    def _candidate_backends(self, spec: IdentificationSpec) -> list[IdentificationBackend]:
        specialized = [b for b in self.backends if not b.is_fallback and b.supports(spec)]
        if specialized:
            return specialized
        return [b for b in self.backends if b.is_fallback and b.supports(spec)]

    def solve_candidates(self, spec: IdentificationSpec) -> list[tuple[IdentificationBackend, IdentificationResult]]:
        return [(backend, backend.solve(spec)) for backend in self._candidate_backends(spec)]

    def solve(self, spec: IdentificationSpec, *, population_truth=None) -> IdentificationResult:
        """Backward-compatible raw routing. Prefer solve_verified in the pipeline."""
        gate_result = evaluate_query_before_identification(
            spec.query,
            assumption_conflicts=spec.assumption_conflicts,
            allow_policy_value_theory=spec.network_exposure is not None,
            allow_network_response_theory=spec.majority_response_theorem_contract is not None,
            allow_network_direct_effect_theory=spec.query.type == "DIRECT_EFFECT" and spec.network_exposure is not None,
        )
        if gate_result is not None:
            return gate_result
        if spec.network_policy_mixture_theorem_contract is not None:
            from .network_policy_mixture import propose_network_policy_mixture, _failure
            if population_truth is None:
                return _failure(spec,"MISSING_POPULATION_TRUTH","Finite-mixture oracle needs separate typed population truth o; no empirical plug-in is promoted.")
            return propose_network_policy_mixture(spec,population_truth)
        i1_gate_result = _interference_structure_preflight(spec)
        if i1_gate_result is not None:
            return i1_gate_result
        candidates = self.solve_candidates(spec)
        if not candidates:
            return self._no_backend(spec)
        candidates.sort(key=lambda pair: pair[0].priority, reverse=True)
        selected = candidates[0][1]
        selected.trace.insert(
            0,
            TraceStep(
                step="engine_selection",
                outcome="INFO",
                detail=(
                    "Raw/unverified routing selected the highest-priority applicable backend. "
                    "The production pipeline uses solve_verified instead."
                ),
            ),
        )
        return selected

    def solve_verified(self, spec: IdentificationSpec, verifier: IdentificationVerifierProtocol, *, population_truth=None) -> IdentificationResult:
        gate_result = evaluate_query_before_identification(
            spec.query,
            assumption_conflicts=spec.assumption_conflicts,
            allow_policy_value_theory=spec.network_exposure is not None,
            allow_network_response_theory=spec.majority_response_theorem_contract is not None,
            allow_network_direct_effect_theory=spec.query.type == "DIRECT_EFFECT" and spec.network_exposure is not None,
        )
        if gate_result is not None:
            return gate_result
        if spec.network_policy_mixture_theorem_contract is not None:
            from .network_policy_mixture import propose_network_policy_mixture, _failure
            if population_truth is None:
                return _failure(spec,"MISSING_POPULATION_TRUTH","Finite-mixture oracle needs separate typed population truth o; no empirical plug-in is promoted.")
            raw=propose_network_policy_mixture(spec,population_truth)
            return verifier.verify(spec,raw,population_truth=population_truth)
        i1_gate_result = _interference_structure_preflight(spec)
        if i1_gate_result is not None:
            return i1_gate_result
        candidates = self.solve_candidates(spec)
        if not candidates:
            return self._no_backend(spec)

        checked: list[tuple[IdentificationBackend, IdentificationResult]] = [
            (backend, verifier.verify(spec, raw)) for backend, raw in candidates
        ]

        verified_incompatible = [
            (b, r) for b, r in checked
            if r.status == IdentificationStatus.INCOMPATIBLE and r.verification_status == VerificationStatus.VERIFIED
        ]
        if verified_incompatible:
            chosen = max(verified_incompatible, key=lambda pair: pair[0].priority)[1]
            chosen.trace.insert(
                0,
                TraceStep(
                    step="engine_selection",
                    outcome="INFO",
                    detail="A verified specification incompatibility is terminal; no causal solution is selected.",
                ),
            )
            return chosen

        verified = [
            (b, r) for b, r in checked
            if r.verification_status == VerificationStatus.VERIFIED
            and r.status in {IdentificationStatus.POINT, IdentificationStatus.PARTIAL, IdentificationStatus.NO_USEFUL_ID}
        ]
        conflict = self._detect_verified_conflict(spec, verified)
        if conflict is not None:
            return conflict

        if verified:
            informativeness = {
                IdentificationStatus.POINT: 3,
                IdentificationStatus.PARTIAL: 2,
                IdentificationStatus.NO_USEFUL_ID: 1,
            }
            verified.sort(key=lambda pair: (informativeness[pair[1].status], pair[0].priority), reverse=True)
            chosen = verified[0][1]
            chosen.trace.insert(
                0,
                TraceStep(
                    step="engine_selection",
                    outcome="INFO",
                    detail=(
                        "Selected among independently verified compatible results; informativeness is compared only after verification."
                    ),
                ),
            )
            return chosen

        # No verified causal claim. Preserve the most specific checked failure/abstention.
        checked.sort(key=lambda pair: pair[0].priority, reverse=True)
        chosen = checked[0][1]
        chosen.trace.insert(
            0,
            TraceStep(
                step="engine_selection",
                outcome="INFO",
                detail="No verified causal solution was available; returning the highest-priority checked abstention/failure.",
            ),
        )
        return chosen

    @staticmethod
    def _detect_verified_conflict(
        spec: IdentificationSpec,
        verified: list[tuple[IdentificationBackend, IdentificationResult]],
    ) -> IdentificationResult | None:
        if len(verified) <= 1:
            return None

        results = [r for _, r in verified]
        statuses = {r.status for r in results}

        # A verified NO_USEFUL_ID cannot coexist with a verified informative result.
        if IdentificationStatus.NO_USEFUL_ID in statuses and len(statuses) > 1:
            return IdentificationEngine._conflict_result(spec, results, "Verified NO_USEFUL_ID conflicts with a verified informative result.")

        # A sharp PARTIAL result cannot coexist with a verified POINT result under the same formal spec.
        if IdentificationStatus.POINT in statuses and IdentificationStatus.PARTIAL in statuses:
            if any(r.status == IdentificationStatus.PARTIAL and r.guarantee == "sharp" for r in results):
                return IdentificationEngine._conflict_result(spec, results, "Verified POINT conflicts with a verified sharp PARTIAL result.")

        point_programs = {
            r.identified_functional.model_dump_json() for r in results
            if r.status == IdentificationStatus.POINT and r.identified_functional is not None
        }
        if len(point_programs) > 1:
            return IdentificationEngine._conflict_result(spec, results, "Verified POINT backends produced different canonical programs.")

        partial_programs = {
            r.bound_program.model_dump_json() for r in results
            if r.status == IdentificationStatus.PARTIAL and r.bound_program is not None and r.guarantee == "sharp"
        }
        if len(partial_programs) > 1:
            return IdentificationEngine._conflict_result(spec, results, "Verified sharp PARTIAL backends produced different canonical bound programs.")

        return None

    @staticmethod
    def _conflict_result(spec: IdentificationSpec, results: list[IdentificationResult], detail: str) -> IdentificationResult:
        return IdentificationResult(
            status=IdentificationStatus.UNSUPPORTED,
            query=spec.query,
            backend="engine_consistency_guard_v1",
            guarantee="none",
            reason_code="INTERNAL_BACKEND_CONFLICT",
            message=(
                "Multiple independently verified backend outputs are logically inconsistent under the same formal specification. "
                "The system abstains instead of silently ranking them."
            ),
            verification_status=VerificationStatus.UNSUPPORTED,
            verification_message="Internal backend conflict requires developer review.",
            trace=[
                TraceStep(step="engine_consistency", outcome="FAIL", detail=detail),
                TraceStep(
                    step="conflicting_backends",
                    outcome="INFO",
                    detail=str([(r.backend, r.status.value, r.guarantee) for r in results]),
                ),
            ],
        )

    @staticmethod
    def _no_backend(spec: IdentificationSpec) -> IdentificationResult:
        return IdentificationResult(
            status=IdentificationStatus.UNSUPPORTED,
            query=spec.query,
            backend="none",
            guarantee="none",
            reason_code="NO_BACKEND",
            message="No registered identification backend supports this specification.",
            trace=[TraceStep(step="routing", outcome="FAIL", detail="No backend declared support for this formal specification.")],
        )
