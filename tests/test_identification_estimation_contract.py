"""v0.9 read-only target/adapter boundary regression tests.

Do not import/train a PFN or regard target-equivalence as an estimator adapter.
"""
import copy
from dataclasses import replace
import unittest

from pfn_pipeline import (
    compare_arm_with_legacy_response,
    identify,
    inspect_identification_estimation,
    make_complete_randomization_arm_task,
    make_heterogeneous_bernoulli_arm_task,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec
from fixed_network_fixture import FIXTURES, load_graph, make_score_task


class IdentificationEstimationContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        g = load_graph(FIXTURES / 'fixed_er_N20_p0.5_seed12345.json')
        cls.legacy_task = make_score_task(adjacency=g, budget=3)
        cls.legacy_result = identify(cls.legacy_task)
        cls.network = NetworkExposureSpec.model_validate(cls.legacy_task.identification_spec['network_exposure'])

    @classmethod
    def new_arm(cls, *, probability='1/2', grouping='strict_majority', a=1, s=1):
        probs = {node: probability for node in cls.network.node_ids}
        task = make_heterogeneous_bernoulli_arm_task(
            cls.network, propensities=probs, node_id=cls.network.node_ids[0],
            own_treatment_value=a, exposure_value=s, exposure_definition=grouping,
            source='synthetic known pre-treatment protocol', evidence='fixed graph and known p_i',
            admitted=True, synthetic=True, query_authority='TRUSTED_FIXTURE',
        )
        return identify(task)

    def test_legacy_score_uses_response_dependency_not_rollout_value(self):
        profile = inspect_identification_estimation(self.legacy_result)
        self.assertEqual(profile['query_type'], 'NETWORK_MAJORITY_RESPONSE_POLICY_SCORE')
        self.assertEqual(profile['query_scope'], 'policy_score_with_response_dependency')
        self.assertEqual(profile['estimation']['status'], 'REQUEST_DEFINED_RUNTIME_UNCHECKED')
        self.assertEqual(profile['estimation']['request_type'], 'NETWORK_MAJORITY_POLICY_SCORE')
        self.assertEqual(profile['estimation']['response_request_type'], 'NETWORK_MAJORITY_RESPONSE')
        self.assertEqual(profile['response_dependency']['response_shape'], [20, 2, 2])
        self.assertEqual(profile['response_dependency']['assignment_probability'], '1/2')
        self.assertFalse(profile['estimation']['trained_model_checked'])
        self.assertFalse(profile['estimation']['runtime_checked'])

    def test_new_family_verified_target_has_no_pfn_adapter_even_when_same_semantics(self):
        result = self.new_arm()
        profile = inspect_identification_estimation(result)
        self.assertEqual(profile['query_scope'], 'single_node_single_arm')
        self.assertEqual(profile['assignment']['kind'], 'heterogeneous_bernoulli_binary_v1')
        self.assertEqual(profile['exposure']['states'], [0, 1])
        self.assertEqual(profile['population_joint_arm_support'],
                         result.result['certificate']['joint_arm_support_probability'])
        self.assertEqual(profile['estimation']['status'], 'NO_ADAPTER')
        self.assertIsNone(profile['estimation']['request_type'])
        self.assertFalse(profile['full_surface_certified_by_this_single_arm'])
        alignment = compare_arm_with_legacy_response(result, self.legacy_result)
        self.assertTrue(alignment['aligned'], alignment)
        self.assertFalse(alignment['estimation_request_emitted'])

    def test_support_and_fingerprint_change_with_design(self):
        result = self.new_arm(probability='2/5')
        alignment = compare_arm_with_legacy_response(result, self.legacy_result)
        self.assertFalse(alignment['aligned'])
        self.assertIn('Different assignment laws', str(alignment['reasons']))

    def test_three_level_arm_has_six_candidate_arms_but_only_one_certified(self):
        result = self.new_arm(grouping='three_level_treated_neighbor_fraction', s=1)
        profile = inspect_identification_estimation(result)
        self.assertEqual(profile['exposure']['states'], [0, 1, 2])
        self.assertEqual(profile['potential_output_layout_if_all_arms_supported'], [20, 2, 3])
        self.assertFalse(profile['full_surface_certified_by_this_single_arm'])
        self.assertFalse(compare_arm_with_legacy_response(result, self.legacy_result)['aligned'])

    def test_complete_randomization_d2_not_a_bernoulli_half_target(self):
        task = make_complete_randomization_arm_task(
            self.network, m=10, node_id=self.network.node_ids[0],
            own_treatment_value=1, exposure_value=1, source='study quota',
            evidence='uniform complete randomization', admitted=True,
            synthetic=True, query_authority='TRUSTED_FIXTURE',
        )
        result = identify(task)
        self.assertEqual(inspect_identification_estimation(result)['estimation']['status'], 'NO_ADAPTER')
        self.assertFalse(compare_arm_with_legacy_response(result, self.legacy_result)['aligned'])

    def test_proposed_assumptions_not_laundered_into_readiness(self):
        task = make_heterogeneous_bernoulli_arm_task(
            self.network, propensities={node: '1/2' for node in self.network.node_ids},
            node_id=self.network.node_ids[0], own_treatment_value=1, exposure_value=1,
            source='unreviewed protocol', evidence='proposal', synthetic=True,
            admitted=False, query_authority='PROPOSED',
        )
        result = identify(task)
        profile = inspect_identification_estimation(result)
        self.assertEqual(profile['estimation']['status'], 'NOT_IDENTIFIED')
        self.assertFalse(profile['estimation']['trained_model_checked'])
        self.assertIsNone(result.estimation_request)

    def test_corrupted_verified_certificate_cannot_generate_a_capability_report(self):
        result = self.new_arm()
        corrupted = copy.deepcopy(result.result)
        corrupted['certificate']['joint_arm_support_probability'] = '1/999'
        tampered = replace(result, result=corrupted)
        with self.assertRaises(ValueError):
            inspect_identification_estimation(tampered)

    def test_outcome_kind_and_network_must_match_for_alignment(self):
        base = self.new_arm()
        # Creating a task over a differently ordered graph changes the target.
        ids = list(self.network.node_ids)
        new_network = NetworkExposureSpec(
            network_id='different-network', node_ids=ids,
            undirected_edges=[(ids[0],ids[1]), (ids[0],ids[2])],
        )
        altered = identify(make_heterogeneous_bernoulli_arm_task(
            new_network, propensities={i:'1/2' for i in ids}, node_id=ids[0],
            own_treatment_value=1, exposure_value=1, source='synthetic protocol',
            evidence='different graph', admitted=True, synthetic=True,
            query_authority='TRUSTED_FIXTURE',
        ))
        self.assertTrue(compare_arm_with_legacy_response(base, self.legacy_result)['aligned'])
        self.assertFalse(compare_arm_with_legacy_response(altered, self.legacy_result)['aligned'])


if __name__ == '__main__':
    unittest.main()
