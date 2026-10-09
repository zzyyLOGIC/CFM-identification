import copy
import unittest
from dataclasses import replace
from fractions import Fraction
from itertools import product
from pathlib import Path

import numpy as np
import torch

from pfn_pipeline import identify, simulate_task
from pfn_pipeline.simulation import load_graph
from pfn_pipeline._internal.paths import DEFAULT_GRAPH
from pfn_pipeline._internal.estimation.causalfm_experiment.training import RunConfig
from pfn_pipeline._internal.estimation.estimands import arm_probability, conditional_count_weights
from pfn_pipeline._internal.identification.majority_response import (
    _count_weights, make_majority_response_spec, MajorityResponseBackend,
    verify_majority_response,
)
from pfn_pipeline._internal.identification.schemas import Assumption, NetworkExposureSpec


class IdentificationIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        previous_threads = torch.get_num_threads()
        cls.addClassCleanup(torch.set_num_threads, previous_threads)
        torch.set_num_threads(1)
        cls.task = simulate_task(seed=2026, budget=5)
        cls.result = identify(cls.task)
        graph20 = load_graph(DEFAULT_GRAPH.with_name('fixed_er_N20_p0.5_seed12345.json'))
        cls.small_task = simulate_task(adjacency=graph20, budget=5)

    def test_shared_default_graph_uses_design_standardized_route(self):
        task, result = self.task, self.result
        self.assertEqual(task.n_nodes, 300)
        self.assertEqual(task.adjacency.sum() // 2, 22455)
        self.assertGreater(task.adjacency.sum(axis=1).max(), 128)
        self.assertEqual(Path(RunConfig().graph_file), DEFAULT_GRAPH)
        self.assertEqual(result.status, "POINT")
        self.assertEqual(result.verification_status, "VERIFIED")
        self.assertEqual(result.diagnostics['workflow_status'], 'COMPLETE')
        used = set(result.result["assumptions_used"])
        self.assertEqual(used, {
            "known_assignment_law",
            "full_vector_randomization",
            "consistency",
            "fixed_pretreatment_network",
            "finite_conditional_first_moments",
        })
        self.assertFalse(any("sufficiency" in item for item in used))
        self.assertEqual(task.identification_spec["exposure_mapping_claim"], "UNSPECIFIED")
        self.assertIn("graph_sha256", task.metadata)

    def test_unresolved_and_rejected_randomization_stop_the_handoff(self):
        for status, source, workflow in (
            ('UNRESOLVED', 'unresolved_input', 'NEEDS_INPUT'),
            ('PROPOSED', 'llm_candidate', 'NEEDS_INPUT'),
            ('NOT_ADMITTED', 'human_confirmation', 'UNSUPPORTED'),
            ('CONTRADICTED', 'study_protocol', 'UNSUPPORTED'),
        ):
            with self.subTest(status=status):
                spec = copy.deepcopy(self.small_task.identification_spec)
                for item in spec['assumptions']:
                    if item['name'] == 'full_vector_randomization':
                        item.update(status=status, source=source, confirmed=False)
                task = replace(self.small_task, identification_spec=spec,
                               assumptions=tuple(copy.deepcopy(spec['assumptions'])))
                result = identify(task)
                self.assertEqual(result.status, 'UNSUPPORTED')
                self.assertEqual(result.result['reason_code'], 'REQUIRED_ASSUMPTIONS_NOT_ADMITTED')
                self.assertEqual(result.diagnostics['workflow_status'], workflow)
                self.assertIn('full_vector_randomization', result.diagnostics['missing_assumptions'])
                self.assertIsNone(result.estimation_request)

    def test_missing_assumption_requests_input(self):
        spec = copy.deepcopy(self.small_task.identification_spec)
        spec['assumptions'] = [a for a in spec['assumptions'] if a['name'] != 'consistency']
        task = replace(self.small_task, identification_spec=spec,
                       assumptions=tuple(copy.deepcopy(spec['assumptions'])))
        result = identify(task)
        self.assertEqual(result.diagnostics['workflow_status'], 'NEEDS_INPUT')
        self.assertEqual(result.diagnostics['missing_assumptions'], ['consistency'])
        self.assertIsNone(result.estimation_request)

    def test_proposal_cannot_silently_become_an_admitted_assumption(self):
        for source in ('llm_candidate', 'unresolved_input', 'withheld_metadata'):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    Assumption(name='full_vector_randomization', source=source, confirmed=True)
                with self.assertRaises(ValueError):
                    Assumption(name='full_vector_randomization', source=source, status='CERTIFIED')
        legacy = Assumption(name='consistency', source='human_confirmation', confirmed=True)
        self.assertEqual(legacy.status, 'ADMITTED')
        unresolved = Assumption(name='consistency', source='human_confirmation',
                                status='UNRESOLVED', confirmed=True)
        self.assertFalse(unresolved.confirmed)

    def test_synthetic_source_still_requires_explicit_admission(self):
        net = NetworkExposureSpec(network_id='triangle', node_ids=['a','b','c'],
                                  undirected_edges=[('a','b'),('b','c'),('a','c')])
        spec = make_majority_response_spec(net, source='test protocol', evidence='test fixture',
                                          synthetic=True, admitted=False, query_authority='TRUSTED_FIXTURE')
        self.assertFalse(spec.confirmed_assumptions())
        self.assertNotEqual(MajorityResponseBackend().solve(spec).status, 'POINT')

    def test_er300_design_weights_match_estimation(self):
        proof = self.result.result['certificate']['response_identification_result']['certificate']
        for degree, table in proof['design_by_degree'].items():
            degree = int(degree)
            probabilities = table['joint_own_treatment_arm_probabilities']
            self.assertEqual(sum(map(Fraction, probabilities.values())), 1)
            for arm in (0, 1):
                self.assertAlmostEqual(float(Fraction(probabilities[f'0,{arm}'])),
                                       0.5 * arm_probability(degree, 0.5, arm), places=14)
                exact = [Fraction(w) for w in table['conditional_count_weights'][str(arm)]]
                self.assertEqual(sum(exact), 1)
                np.testing.assert_allclose(np.array(exact, dtype=float),
                                           conditional_count_weights(degree, 0.5, arm),
                                           rtol=1e-10, atol=1e-15)

    def test_exact_replay_matches_enumerated_nonhalf_assignment(self):
        p, degree = Fraction(2, 5), 5
        mass = [Fraction(0)] * (degree + 1)
        for assignment in product((0, 1), repeat=degree):
            count = sum(assignment)
            mass[count] += p**count * (1-p)**(degree-count)
        table = _count_weights(degree, p, independent=True)
        for arm in (0, 1):
            arm_mass = sum(mass[k] for k in range(degree + 1) if int(k > degree//2) == arm)
            expected = [mass[k]/arm_mass if int(k > degree//2) == arm else Fraction(0)
                        for k in range(degree + 1)]
            self.assertEqual(list(map(Fraction, table['conditional_count_weights'][str(arm)])), expected)

    def test_empty_observed_cells_do_not_change_population_identification(self):
        task = replace(self.small_task, treatment=np.zeros(self.small_task.n_nodes),
                       outcome=np.full(self.small_task.n_nodes, 123.0))
        result = identify(task)
        self.assertEqual((result.status, result.verification_status), ('POINT', 'VERIFIED'))

    def test_count_insufficient_outcomes_are_compatible_with_the_target(self):
        # The two assignments (own=0,b=1,c=0) and (own=0,b=0,c=1)
        # have the same count but unequal outcomes. Only the target is grouped.
        net = NetworkExposureSpec(network_id='triangle', node_ids=['a','b','c'],
                                  undirected_edges=[('a','b'),('b','c'),('a','c')])
        spec = make_majority_response_spec(net, source='enumerated experiment',
            evidence='iid Bernoulli fixture', synthetic=True, admitted=True,
            query_authority='TRUSTED_FIXTURE')
        checked = verify_majority_response(spec, MajorityResponseBackend().solve(spec))
        self.assertEqual(checked.verification_status, 'VERIFIED')
        def outcome(a, b, c):
            return 2*a + 3*b - 5*c
        self.assertNotEqual(outcome(0,1,0), outcome(0,0,1))
        for own, arm in product((0, 1), repeat=2):
            observable = [outcome(a,b,c) for a,b,c in product((0,1), repeat=3)
                          if a == own and int(b+c > 1) == arm]
            standardized = [outcome(own,b,c) for b,c in product((0,1), repeat=2)
                            if int(b+c > 1) == arm]
            self.assertEqual(np.mean(observable), np.mean(standardized))

    def test_same_identification_route_accepts_other_saved_er_graph(self):
        root = Path(__file__).resolve().parents[1]
        for n_nodes, probability in ((20, '0.5'), (1000, '0.02')):
            with self.subTest(n_nodes=n_nodes):
                graph = load_graph(root / f'pfn_pipeline/_internal/estimation/data/fixed_er_N{n_nodes}_p{probability}_seed12345.json')
                task = simulate_task(seed=2026, budget=5, adjacency=graph)
                result = identify(task)
                self.assertEqual((result.status, result.verification_status), ('POINT', 'VERIFIED'))
                self.assertEqual(task.n_nodes, n_nodes)


if __name__ == "__main__":
    unittest.main()
