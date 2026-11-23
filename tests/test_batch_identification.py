"""Batch population theorem, independent enumeration, and safe old-PFN bridge."""
from dataclasses import replace
from fractions import Fraction
from itertools import product
import unittest

import numpy as np

from pfn_pipeline import identify
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec
from pfn_pipeline._internal.identification.randomized_arm_family import AssignmentSpec, ExposureSpec
from pfn_pipeline.identification import (
    make_complete_randomization_arm_task, make_two_group_quota_arm_task,
    make_heterogeneous_bernoulli_arm_task,
)
from pfn_pipeline.identification_batch import (
    identify_randomized_network_batch, replay_network_arm_batch,
    bind_legacy_response_batch, replay_legacy_response_batch_bridge,
    estimate_bound_legacy_response,
)
from fixed_network_fixture import FIXTURES, load_graph, make_score_task


class BatchIdentificationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = FIXTURES / 'fixed_er_N20_p0.5_seed12345.json'
        cls.legacy = identify(make_score_task(adjacency=load_graph(path), budget=3))
        cls.network = NetworkExposureSpec.model_validate(cls.legacy.task.identification_spec['network_exposure'])

    def _batch(self, kind='D1', grouping='strict_majority', **overrides):
        net = overrides.pop('network', self.network)
        kw = dict(network=net, node_id=net.node_ids[0], own_treatment_value=0,
                  exposure_value=0, exposure_definition=grouping,
                  source='test synthetic protocol', evidence='known randomized experiment',
                  synthetic=True, admitted=True, query_authority='TRUSTED_FIXTURE')
        if kind == 'D1':
            kw['propensities'] = {n: '1/2' for n in net.node_ids}
            maker = make_heterogeneous_bernoulli_arm_task
        elif kind == 'D2':
            kw['m'] = len(net.node_ids)//2
            maker = make_complete_randomization_arm_task
        else:
            mid = len(net.node_ids)//2
            kw['groups'] = (tuple(net.node_ids[:mid]), tuple(net.node_ids[mid:]))
            kw['treated_quotas'] = (max(1, mid//2), max(1, (len(net.node_ids)-mid)//2))
            maker = make_two_group_quota_arm_task
        kw.update(overrides)
        return identify_randomized_network_batch(maker(**kw))

    def _oracle(self, batch):
        formal = batch.template.identification_spec
        from pfn_pipeline._internal.identification.schemas import IdentificationSpec
        spec = IdentificationSpec.model_validate(formal)
        design = AssignmentSpec(spec.randomized_network_arm_theorem_contract.design)
        c = spec.randomized_network_arm_theorem_contract
        grouping = ExposureSpec(c.grouping, c.core_collaborators)
        net = spec.network_exposure
        n = len(net.node_ids)
        self.assertLessEqual(n, 8)
        for i, node in enumerate(net.node_ids):
            neighbors = {r for l, r in net.undirected_edges if l == node} | {l for l, r in net.undirected_edges if r == node}
            if c.core_collaborators is not None:
                neighbors = set(c.core_collaborators[node])
            if grouping.grouping == 'three_level_treated_neighbor_fraction' and not neighbors:
                for a in (0, 1):
                    for s in batch.exposure_states:
                        self.assertIsNone(batch.cell(node, a, s)['joint_support'])
                continue
            for a in (0, 1):
                for s in batch.exposure_states:
                    total = Fraction(0)
                    for state in product((0, 1), repeat=n):
                        t = dict(zip(net.node_ids, state))
                        if t[node] != a:
                            continue
                        k = sum(t[j] for j in neighbors)
                        if grouping.classify(k, len(neighbors)) == s:
                            total += design.full_assignment_probability(net, t)
                    self.assertEqual(Fraction(batch.cell(node,a,s)['joint_support']), total)

    def test_20_node_four_arm_output_and_single_arm_consistency(self):
        batch = self._batch()
        self.assertEqual(batch.shape, (20, 2, 2))
        self.assertEqual(batch.coverage_status, 'ALL_POINT_IDENTIFIED')
        self.assertEqual(batch.verification_status, 'VERIFIED')
        self.assertIsNone(batch.estimation_request)
        self.assertTrue(all(all(all(x for x in a) for a in n) for n in batch.population_support_mask))
        self.assertEqual(replay_network_arm_batch(batch).batch_sha256, batch.batch_sha256)
        from pfn_pipeline._internal.identification.randomized_network_arm import arm_target_fingerprint
        from pfn_pipeline._internal.identification.schemas import IdentificationSpec
        spec = IdentificationSpec.model_validate(batch.template.identification_spec)
        for a,s in ((0,0),(1,1)):
            cell = batch.cell(batch.node_ids[0], a, s)
            self.assertEqual(cell['target_fingerprint'], arm_target_fingerprint(
                spec.network_exposure, spec.randomized_network_arm_theorem_contract,
                batch.node_ids[0],a,s))
        self.assertEqual(sum(Fraction(x) for row in batch.population_joint_support[0] for x in row), 1)

    def test_D1_heterogeneous_E2_exact_oracle(self):
        net = NetworkExposureSpec(network_id='hetero-oracle', node_ids=['a','b','c','d'],
                  undirected_edges=[('a','b'),('a','c'),('b','d')])
        batch=self._batch('D1', 'three_level_treated_neighbor_fraction', network=net,
                          propensities={'a':'1/4','b':'1/3','c':'2/3','d':'1/2'}, exposure_value=1)
        self.assertEqual(batch.shape, (4,2,3))
        self._oracle(batch)

    def test_D2_fixed_quota_E2_zero_support_and_isolate(self):
        net=NetworkExposureSpec(network_id='five-with-isolate', node_ids=['a','b','c','d','e'],
                                undirected_edges=[('a','b'),('a','c'),('b','c')])
        batch=self._batch('D2', 'three_level_treated_neighbor_fraction', network=net,
                          m=2, exposure_value=1)
        self._oracle(batch)
        self.assertEqual(batch.cell('d', 0, 0)['reason_code'], 'EXPOSURE_UNDEFINED_FOR_ISOLATED_NODE')
        self.assertIsNone(batch.cell('d', 0, 0)['joint_support'])
        self.assertEqual(batch.coverage_status, 'SOME_ARMS_UNSUPPORTED')
        # An undefined exposure is distinct from a mathematically zero arm mass.
        self.assertIsNone(batch.cell('e', 1, 1)['joint_support'])

    def test_D2_no_treated_all_one_arms_zero(self):
        net=NetworkExposureSpec(network_id='quota-zero', node_ids=['a','b','c'],
                                undirected_edges=[('a','b'),('b','c')])
        batch=self._batch('D2', network=net, m=0, exposure_value=0)
        self._oracle(batch)
        self.assertEqual(batch.cell('a',1,0)['status'], 'UNSUPPORTED')
        self.assertEqual(batch.cell('a',1,0)['reason_code'], 'ZERO_ARM_SUPPORT')
        self.assertEqual(batch.cell('a',1,0)['joint_support'], '0')

    def test_D3_E3_cross_group_core_exact_oracle(self):
        net=NetworkExposureSpec(network_id='groups-and-core', node_ids=['a','b','c','d','e','f'],
                                undirected_edges=[('a','d'),('a','b'),('b','e'),('b','c'),
                                                 ('c','f'),('c','d'),('d','e'),('e','f')])
        cores={node: (next(other for left,right in net.undirected_edges
                            for other in ([right] if left==node else [left] if right==node else [])),)
               for node in net.node_ids}
        batch=self._batch('D3', 'pretreatment_core_collaborator_majority', network=net,
                          treated_quotas=(1,1),core_collaborators=cores)
        self._oracle(batch)
        self.assertIn('POINT', [c for node in batch.arm_status for arm in node for c in arm])

    def test_all_nine_design_exposure_combinations_against_full_assignment_oracle(self):
        net = NetworkExposureSpec(
            network_id='nine-way-oracle', node_ids=['a','b','c','d','e','f'],
            undirected_edges=[('a','b'),('b','c'),('c','d'),('d','e'),('e','f'),
                              ('f','a'),('a','d'),('b','e'),('c','f')],
        )
        cores = {node: (next(other for left, right in net.undirected_edges
                         for other in ([right] if left == node else
                                       [left] if right == node else [])),)
                 for node in net.node_ids}
        for design in ('D1','D2','D3'):
            for exposure in ('strict_majority', 'three_level_treated_neighbor_fraction',
                             'pretreatment_core_collaborator_majority'):
                with self.subTest(design=design, exposure=exposure):
                    extra = {}
                    if design == 'D1':
                        extra['propensities'] = {
                            node: str(Fraction(i+1,8)) for i,node in enumerate(net.node_ids)
                        }
                    if design == 'D2':
                        extra['m'] = 3
                    if design == 'D3':
                        extra['treated_quotas'] = (1,2)
                    if exposure == 'pretreatment_core_collaborator_majority':
                        extra['core_collaborators'] = cores
                    if exposure == 'three_level_treated_neighbor_fraction' and design in ('D2','D3'):
                        # Choose a supported seed arm; the full batch will still
                        # explicitly report any other structural zero support.
                        extra['exposure_value'] = 1
                    batch = self._batch(design,exposure,network=net,**extra)
                    self.assertEqual(batch.shape, (6,2,3 if 'three_level' in exposure else 2))
                    self._oracle(batch)
                    replay_network_arm_batch(batch)

    def test_zero_propensity_unadmitted_and_tamper(self):
        net=NetworkExposureSpec(network_id='chain', node_ids=['a','b','c'],
                                undirected_edges=[('a','b'),('b','c')])
        batch=self._batch('D1', network=net,
                          propensities={'a':'0','b':'1/2','c':'1'}, exposure_value=0)
        self._oracle(batch)
        self.assertEqual(batch.cell('a',1,0)['status'],'UNSUPPORTED')
        for attr,value in [('batch_sha256','0'*64), ('population_joint_support',((('0',),),)),
                           ('target_fingerprints',((('bad',),),)),
                           ('coverage_status','ALL_POINT_IDENTIFIED')]:
            with self.subTest(attr=attr):
                with self.assertRaises(ValueError):
                    replay_network_arm_batch(replace(batch,**{attr:value}))
        with self.assertRaisesRegex(ValueError,'not POINT/VERIFIED'):
            self._batch('D1',network=net, admitted=False, propensities={n:'1/2' for n in net.node_ids})

    def test_legacy_bridge_exact_target_and_population_support(self):
        link=bind_legacy_response_batch(self.legacy)
        self.assertEqual(link.batch.shape, (20,2,2))
        self.assertEqual(link.estimation_status, 'REQUEST_DEFINED_RUNTIME_UNCHECKED')
        self.assertIsNone(link.batch.estimation_request)
        self.assertIs(replay_legacy_response_batch_bridge(link),link)
        with self.assertRaises(ValueError):
            replay_legacy_response_batch_bridge(replace(link,binding_sha256='x'*64))
        from pfn_pipeline import inspect_identification_estimation
        self.assertEqual(inspect_identification_estimation(link.legacy_identification)['estimation']['status'],
                         'REQUEST_DEFINED_RUNTIME_UNCHECKED')

    def test_bridge_rejects_wrong_assignment_probability(self):
        graph = load_graph(FIXTURES / 'fixed_er_N20_p0.5_seed12345.json')
        result = identify(make_score_task(adjacency=graph, treatment_prob=.4, budget=3))
        with self.assertRaisesRegex(ValueError, 'Bernoulli'):
            bind_legacy_response_batch(result)

    def test_fitting_boundary_checks_binding_before_referral(self):
        link = bind_legacy_response_batch(self.legacy)
        with self.assertRaisesRegex(NotImplementedError, 'full autoCFM'):
            estimate_bound_legacy_response(link)
        with self.assertRaises(ValueError):
            estimate_bound_legacy_response(replace(link, binding_sha256='0'*64))


if __name__ == '__main__':
    unittest.main()
