"""Read-only condition metadata; the v27 API retains its eight-route scope.

NOT a catalog of all scientifically possible assumptions, and NOT a source of
causal licences.  Never use this metadata to bypass a theorem's native checks.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

# A4 design information is intentionally distinguished from the scientific A5.
# The legacy model records known_assignment_law among accepted assumption
# records; the underlying known q is an independently required design object.
_EXPERIMENT = (
    'known_assignment_law', 'full_vector_randomization', 'consistency',
    'fixed_pretreatment_network', 'finite_conditional_first_moments',
)
_OBSERVATIONAL = (
    'full_vector_conditional_exchangeability', 'consistency',
    'fixed_pretreatment_network', 'finite_conditional_first_moments',
)
_D6 = 'first_stage_profile_no_direct_outcome_effect'
_SIGNATURE = 'mean_signature_sufficiency'

# Frozen v27 compatibility keys, not a complete inventory of current methods.
_ROUTES = {
    'R1A_RANDOMIZED_ARM': (
        'q_standardized_node_arm', _EXPERIMENT, 'positive_joint_arm_support',
        'typed population node-arm mean or legitimate full-law entailment'),
    'R1A_COMPOSITION': (
        'q_standardized_linear_effect_bundle', _EXPERIMENT, 'positive_support_for_every_nonzero_term',
        'typed population arm means for all constituent terms'),
    'R1B_FULL_ASSIGNMENT': (
        'fixed_full_assignment_policy_value', _EXPERIMENT, 'positive_q_of_full_target_assignment',
        'assignment-resolved node means for the target vector'),
    'R1B_FINITE_POLICY': (
        'finite_mixture_of_verified_fixed_policies', _EXPERIMENT, 'each_positive_weight_component_certified',
        'separate certified R1b population operator for every component'),
    'R2_MEAN_SIGNATURE': (
        'fixed_policy_with_q_signature_reduction', _EXPERIMENT + (_SIGNATURE,),
        'positive_target_signature_for_every_nonzero_weight_node',
        'typed population signature means matching the accepted signature'),
    'R3_FULL_ASSIGNMENT': (
        'observational_fixed_policy_value', _OBSERVATIONAL,
        'positive_pobs_of_full_target_assignment',
        'exact finite p_obs(T|W) and assignment-conditioned outcome means'),
    'R3_MEAN_SIGNATURE': (
        'observational_fixed_policy_with_signature_reduction', _OBSERVATIONAL + (_SIGNATURE,),
        'positive_pobs_target_signature_each_weighted_node',
        'exact finite p_obs and signature-node outcome means'),
    'R3_P_STANDARDIZED_EFFECTS': (
        'pobs_standardized_arm_linear_contrasts', _OBSERVATIONAL,
        'positive_pobs_arm_support_for_each_nonzero_term',
        'Exact finite p_obs, or a separately admitted factorized/finite-mixture observational law, with the matching typed population mean operators.'),
}

@dataclass(frozen=True)
class ImplementedAssumptionV27:
    name: str
    layer: str
    description: str
    scientific_scope: str
    machine_verifiability: str

_ASSUMPTIONS = (
    ImplementedAssumptionV27('known_assignment_law','A4_DESIGN',
        'Exact joint experimental treatment law q(T|W) is specified.',
        'Implemented randomized-design routes; the concrete design/probability adapter determines support. Legacy also records an admission.',
        'Exact protocol syntax and probabilities checkable; real adherence not automatically verifiable.'),
    ImplementedAssumptionV27('full_vector_randomization','A5',
        'The full realized randomized allocation is conditionally independent of all potential outcomes.',
        'R1a/R1b/R2, not an observational self-selection guarantee.',
        'Protocol declaration/replay only; not a test of implementation fidelity.'),
    ImplementedAssumptionV27('consistency','A5',
        'Observed outcome equals the potential outcome under the actually realized intervention version.',
        'All current R1/R2/R3 POINT mechanisms.',
        'Cannot establish real-world intervention-version consistency from a typed claim.'),
    ImplementedAssumptionV27('fixed_pretreatment_network','A3_A5',
        'Network and exposure reference sets are defined before the intervention.',
        'Current single-time, fixed, simple undirected network routes.',
        'Typed topology/timing record checkable; exogeneity is a scientific claim.'),
    ImplementedAssumptionV27('finite_conditional_first_moments','A5_ANALYTIC',
        'Required conditional expectations exist and are finite.',
        'Current mean-valued targets.',
        'Declared integrability, not universally testable from finite samples.'),
    ImplementedAssumptionV27('mean_signature_sufficiency','A5_STRUCTURAL',
        'For each covered node, E[Y_i(t)|W] is constant across full allocations with equal (t_i,g_i(t,W)).',
        'R2, R3-Signature and finite-network mean-based PARTIAL contracts; signature/node/study bindings required.',
        'Typed licence and provenance checks; cannot prove the structural restriction empirically.'),
    ImplementedAssumptionV27('full_vector_conditional_exchangeability','A5_OBSERVATIONAL',
        'Given W, observational allocation is independent of the full potential-outcome vector.',
        'R3-Full, R3-Signature and R3 p-standardized effects.',
        'Requires explicit reviewed admission; observational data cannot by itself establish it.'),
    ImplementedAssumptionV27(_D6,'A5_D6_EXTRA',
        'Holding final complete T fixed, stage-one quota/profile U has no additional direct outcome effect.',
        'D6 randomized-design routes in addition to the ordinary R1/R2 conditions.',
        'Dedicated explicit source/status gate; not implied by known D6 randomization.'),
)


def implemented_assumption_catalog_v27() -> dict:
    """Return documented assumptions, not an admission or a truth test."""
    return {
        'contract': 'CFM-ID-IMPLEMENTED-ASSUMPTIONS-v2.7-P0',
        'universal_finite_catalog': False,
        'scope': 'The eight v27 fixed-network POINT routes; not all current identification methods',
        'assumptions': [asdict(a) for a in _ASSUMPTIONS],
        'route_ids': list(_ROUTES),
        'additional_condition_sources': {
            'legacy_ate': 'legacy_ate_condition_catalog',
            'observational_exposure_adjustment': 'pfn_pipeline.identification_observational_exposure_adjustment',
            'observational_nodewise_adjustment': 'pfn_pipeline.identification_observational_nodewise_adjustment',
            'network_partial': 'cfm_id.bounded_policy_contract / bounded_finite_contract / mean_order_contract',
            'dag': 'cfm_id.dag_backdoor_contract / dag_id_contract',
            'iv': 'cfm_id.iv_route_contract',
        },
        'warning': 'Admitted/provenance/verified software does NOT certify scientific truth.',
    }


def requirements_for_route_v27(route: str, *, design_kind: str | None = None) -> dict:
    """Describe this route's premises, not globally necessary ID conditions."""
    if route not in _ROUTES:
        raise ValueError(f'Unknown implemented theorem route: {route!r}')
    target, base, support, information = _ROUTES[route]
    experimental = route.startswith(('R1A_', 'R1B_', 'R2_'))
    d6 = design_kind == 'two_stage_quota_mixture_binary_v2_7'
    if d6 and not experimental:
        raise ValueError('D6 is an experimental design, not an observational R3 assignment')
    return {
        'route': route, 'target_semantics': target,
        'required_names': list(base) + ([_D6] if d6 else []),
        'conditionally_required_if_D6': _D6 if experimental and not d6 else None,
        'A4_required': information, 'A6_required': support,
        'requires_mean_signature_sufficiency': _SIGNATURE in base,
        'exposure_mapping_does_not_certify_sufficiency': True,
        'premises_checked_by': 'ORIGINAL_ROUTE_THEOREM_AND_INDEPENDENT_REPLAY_ONLY',
        'scientific_validity_certified_by_software': False,
        'no_assumption_discovery': True,
    }


def legacy_ate_condition_catalog() -> dict:
    """Describe the legacy contracts without granting admission or a proof."""
    return {
        'contract': 'CFM-ID-LEGACY-ATE-CONDITIONS-1',
        'scientific_validity_certified_by_software': False,
        'formula_changed': False,
        'mean_existence': {
            'required': 'The means used in the returned formula exist and are finite.',
            'automatic_basis': 'Validated finite numeric outcome support.',
            'otherwise': 'Explicitly admitted finite_conditional_first_moments with nonblank evidence.',
            'one_sided_bound_is_not_sufficient': True,
            'source_is_real_world_proof': False,
        },
        'rules': {
            'RANDOMIZED_ATE_V3': {
                'required_names': ['random_assignment', 'consistency', 'positivity', 'no_interference'],
                'support': '0 < assignment_probability < 1',
                'information': 'experimental population P(T,Y)',
                'mean_existence_required': True,
            },
            'ONE_ARM_ATE_BOUNDS_V2 / ONE_ARM_NO_OUTCOME_RESTRICTION_V2': {
                'required_names': ['random_assignment', 'consistency', 'no_interference'],
                'support': 'assignment_probability is 0 or 1',
                'information': 'experimental population P(T,Y)',
                'mean_existence_required': True,
                'closed_model_required': True,
            },
            'MANSKI_BINARY_ATE_V2': {
                'required_names': ['consistency', 'no_interference'],
                'domain': 'Both binary values 0 and 1 remain allowed for T and Y.',
                'information': 'observational population P(T,Y) only; duplicate equivalent declarations allowed',
                'mean_existence_basis': 'finite binary domain',
                'closed_model_required': True,
            },
        },
        'closed_model': {
            'unhandled_adopted_or_pending_assumptions': 'BLOCK',
            'explicitly_not_admitted_extra_assumptions': 'NOT_PART_OF_MODEL',
            'contradicted_or_inconsistent_records': 'BLOCK',
            'unhandled_graph_information_or_support_restrictions': 'BLOCK',
            'redundant_finite_moment_declaration': 'ALLOWED',
            'failure_is_nonidentification_proof': False,
        },
        'checks': {
            'producer': 'pfn_pipeline._internal.identification.legacy_ate_contract',
            'replay': 'pfn_pipeline._internal.identification.verifier.IdentificationVerifier',
        },
    }


__all__ = ['implemented_assumption_catalog_v27', 'requirements_for_route_v27', 'legacy_ate_condition_catalog']
