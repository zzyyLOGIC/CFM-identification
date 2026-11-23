"""D1 x E1/E2 production tests against a *separate* full-design oracle.

The oracle enumerates 2**N treatment vectors on small graphs and computes
q(t|W) directly from the p_i values. It does not use the production neighbor
count DP, SupportEngine, or the independent generating-polynomial verifier.
"""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from itertools import product
from unittest.mock import patch
import copy
import random
import unittest

from pfn_pipeline import (
    identify, make_heterogeneous_bernoulli_arm_task,
    replay_population_identification, replay_handoff,
)
from pfn_pipeline._internal.identification.schemas import (
    HeterogeneousBernoulliDesignV1, NetworkExposureSpec, IdentificationSpec,
)
from pfn_pipeline._internal.identification.randomized_arm_family import (
    AssignmentSpec, ExposureSpec, SupportEngine, ArmSupportEvidence,
)
from pfn_pipeline._internal.identification.randomized_network_arm import (
    RandomizedNetworkArmBackend, make_heterogeneous_bernoulli_arm_spec,
    _verify_heterogeneous_joint_support_independently,
)
from pfn_pipeline._internal.identification.verifier import IdentificationVerifier


def net(n: int, edges: list[tuple[int,int]], name='d1-oracle') -> NetworkExposureSpec:
    return NetworkExposureSpec(
        network_id=name, node_ids=[str(i) for i in range(n)],
        undirected_edges=[(str(i), str(j)) for i,j in edges],
    )


def oracle_all_arms(network: NetworkExposureSpec, p_raw: dict[str,str],
                    node_id: str, grouping: str):
    """Independently integrate the original full design q(t) over arm events."""
    ids = list(network.node_ids)
    p = {node: Fraction(p_raw[node]) for node in ids}
    neighbors = set()
    for u, v in network.undirected_edges:
        if u == node_id:
            neighbors.add(v)
        elif v == node_id:
            neighbors.add(u)
    degree = len(neighbors)
    if degree == 0 and grouping == 'three_level_treated_neighbor_fraction':
        return None
    states = (0,1) if grouping == 'strict_majority' else (0,1,2)
    joint = {(a,s): Fraction(0) for a in (0,1) for s in states}
    for bits in product((0,1), repeat=len(ids)):
        t = dict(zip(ids, bits))
        prob = Fraction(1)
        for node in ids:
            prob *= p[node] if t[node] else (1-p[node])
        k = sum(t[j] for j in neighbors)
        if grouping == 'strict_majority':
            s = int(2*k > degree)
        else:
            fraction = Fraction(k,degree)
            s = 0 if fraction < Fraction(1,3) else 1 if fraction < Fraction(2,3) else 2
        joint[(t[node_id],s)] += prob
    return joint


def task(network, p, *, node='0', a=1, s=0,
         grouping='strict_majority', admitted=True, authority='TRUSTED_FIXTURE'):
    return make_heterogeneous_bernoulli_arm_task(
        network, propensities=p, node_id=node, own_treatment_value=a,
        exposure_value=s, exposure_definition=grouping,
        source='known synthetic pretreatment probabilities',
        evidence='independent binary assignment protocol with fixed p_i',
        synthetic=True, admitted=admitted, query_authority=authority,
    )


class HeterogeneousBernoulliArmTests(unittest.TestCase):
    def test_golden_case_e1_e2_and_public_contract(self):
        network = net(4, [(0,1),(0,2),(0,3)])
        p={'0':'1/2','1':'1/4','2':'1/2','3':'3/4'}
        expected_e1 = {
            (0,0): Fraction(1,4),(0,1):Fraction(1,4),
            (1,0):Fraction(1,4),(1,1):Fraction(1,4),
        }
        expected_e2 = {
            (0,0): Fraction(3,64),(0,1):Fraction(13,64),(0,2):Fraction(1,4),
            (1,0): Fraction(3,64),(1,1):Fraction(13,64),(1,2):Fraction(1,4),
        }
        for grouping, expected in [('strict_majority', expected_e1),
                                   ('three_level_treated_neighbor_fraction', expected_e2)]:
            self.assertEqual(oracle_all_arms(network,p,'0',grouping), expected)
            for (a,s), mass in expected.items():
                with self.subTest(grouping=grouping, a=a, s=s):
                    inp = task(network,p,a=a,s=s,grouping=grouping)
                    self.assertEqual(inp.assignment_design['assignment_scheme'],
                                     'heterogeneous_independent_bernoulli')
                    result = identify(inp)
                    self.assertEqual((result.status,result.verification_status),('POINT','VERIFIED'))
                    self.assertEqual(result.result['certificate']['joint_arm_support_probability'],str(mass))
                    self.assertEqual(result.result['identified_functional']['assignment_kind'], 'heterogeneous_bernoulli')
                    self.assertEqual(result.result['identified_functional']['propensities'],p)
                    self.assertEqual(result.result['certificate']['propensities'],p)
                    self.assertIsNone(result.estimation_request)
                    self.assertEqual(result.diagnostics['workflow_status'],'IDENTIFIED_NO_ESTIMATION_ADAPTER')
                    self.assertEqual(replay_population_identification(result).verification_status,'VERIFIED')
                    with self.assertRaises(ValueError):
                        replay_handoff(result)

    def test_small_graph_independent_full_design_oracle(self):
        rng=random.Random(20261014)
        checked=0
        for n in range(2,9):
            ids=[str(i) for i in range(n)]
            for trial in range(8):
                edges=[(i,j) for i in range(n) for j in range(i+1,n)
                       if rng.random() < rng.choice((0.2,0.45,0.8,1.0))]
                network=net(n,edges,name=f'd1-oracle-{n}-{trial}')
                p={node:rng.choice(('0','1','1/5','1/2','2/3','3/4','4/5')) for node in ids}
                design=HeterogeneousBernoulliDesignV1(propensities=p)
                assignment=AssignmentSpec(design)
                for node in ids:
                    for grouping, internal in (
                        ('strict_majority','strict_majority_ties_low'),
                        ('three_level_treated_neighbor_fraction','three_level_treated_neighbor_fraction'),
                    ):
                        oracle=oracle_all_arms(network,p,node,grouping)
                        if oracle is None:
                            continue
                        self.assertEqual(sum(oracle.values()),1)
                        for (a,s), mass in oracle.items():
                            with self.subTest(n=n,trial=trial,node=node,grouping=grouping,a=a,s=s):
                                evidence=SupportEngine.evaluate(
                                    network=network, assignment=assignment,
                                    exposure=ExposureSpec(internal),
                                    node_id=node, own_treatment_value=a, exposure_value=s,
                                )
                                verifier=_verify_heterogeneous_joint_support_independently(
                                    network,design,node,a,s,internal,
                                )
                                self.assertEqual(evidence.joint_probability,mass)
                                self.assertEqual(verifier,mass)
                                checked+=1
        self.assertGreater(checked,2500)

    def test_q_t_normalized_and_weighted_counterfactual_target(self):
        network=net(4,[(0,1),(0,2),(0,3)])
        p={'0':'0.4','1':'0.2','2':'0.5','3':'0.8'}
        assignment=AssignmentSpec(HeterogeneousBernoulliDesignV1(propensities=p))
        mass=Fraction(0)
        joint_num=Fraction(0)
        for bits in product((0,1), repeat=4):
            t=dict(zip(network.node_ids,bits))
            q=assignment.full_assignment_probability(network,t)
            mass+=q
            k=sum(t[j] for j in ('1','2','3'))
            if t['0']==1 and k>=2:
                # A synthetic potential outcome that differs for full assignments
                # even when T_0=1 and exposure is the same.
                y=Fraction(11*t['1'] + 7*t['2'] - 3*t['3'] + t['0'],1)
                joint_num+=q*y
        self.assertEqual(mass,1)
        actual=identify(task(network,p,a=1,s=1))
        self.assertEqual((actual.status,actual.verification_status),('POINT','VERIFIED'))
        arm_mass=Fraction(actual.result['certificate']['joint_arm_support_probability'])
        self.assertEqual(arm_mass,oracle_all_arms(network,p,'0','strict_majority')[(1,1)])
        self.assertIsInstance(joint_num / arm_mass, Fraction)

    def test_zero_mass_is_unsupported_not_partial(self):
        network=net(4,[(0,1),(0,2),(0,3)])
        p={'0':'1','1':'0','2':'0','3':'0'}
        positive=identify(task(network,p,a=1,s=0))
        self.assertEqual((positive.status,positive.verification_status),('POINT','VERIFIED'))
        self.assertEqual(positive.result['certificate']['joint_arm_support_probability'],'1')
        for a,s in [(0,0),(1,1),(0,1)]:
            result=identify(task(network,p,a=a,s=s))
            self.assertEqual(result.result['reason_code'],'ZERO_ARM_SUPPORT')
            self.assertEqual(result.status,'UNSUPPORTED')
            self.assertIsNone(result.estimation_request)

    def test_e2_degree_zero_and_tie_boundaries(self):
        network=net(4,[(1,2),(1,3)])
        p={'0':'1/3','1':'1/3','2':'1/3','3':'1/3'}
        for a in (0,1):
            for s in (0,1,2):
                result=identify(task(network,p,node='0',a=a,s=s,
                                     grouping='three_level_treated_neighbor_fraction'))
                self.assertEqual(result.result['reason_code'],'EXPOSURE_UNDEFINED_FOR_ISOLATED_NODE')
        low=identify(task(network,p,node='0',a=0,s=0))
        self.assertEqual((low.status,low.verification_status),('POINT','VERIFIED'))
        with self.assertRaises(ValueError):
            ExposureSpec('three_level_treated_neighbor_fraction').classify(0,0)

    def test_invalid_or_missing_probabilities_fail_closed(self):
        network=net(3,[(0,1),(0,2)])
        for bad in ({'0':'1/2','1':'1/2'}, {'0':'1/2','1':'1/2','2':'1/2','9':'1'},
                    {'0':'1/2','1':'nan','2':'1/3'}, {'0':'1/2','1':'1.0001','2':'1/3'},
                    {'0':'1/2','1':'-0.1','2':'1/3'}, {'0':'1/2','1':'1/0','2':'1/3'},
                    {'0':0.5,'1':True,'2':0.3}):
            with self.subTest(bad=bad),self.assertRaises((ValueError,TypeError)):
                task(network,bad)
        for bad in (True,2,-1,0.5):
            with self.assertRaises((ValueError,TypeError)):
                task(network,{'0':'0.5','1':'0.5','2':'0.5'},a=bad)
        for bad in (-1,2,'high',True):
            with self.assertRaises((ValueError,TypeError)):
                task(network,{'0':'0.5','1':'0.5','2':'0.5'},s=bad)
        good=task(network,{'0':'0.50','1':'1/2','2':'0.5'})
        self.assertEqual(good.assignment_design['propensities'],{'0':'1/2','1':'1/2','2':'1/2'})
        self.assertEqual(identify(good).verification_status,'VERIFIED')

    def test_target_fingerprint_binds_all_propensities_even_non_neighbors(self):
        network=net(4,[(0,1)])
        p1={'0':'1/2','1':'1/2','2':'1/2','3':'1/2'}
        p2={**p1, '3':'1/3'}
        first=task(network,p1,a=1,s=0)
        second=task(network,p2,a=1,s=0)
        self.assertNotEqual(first.target_fingerprint,second.target_fingerprint)
        self.assertEqual(identify(first).result['certificate']['joint_arm_support_probability'],
                         identify(second).result['certificate']['joint_arm_support_probability'])
        with self.assertRaisesRegex(ValueError,'assignment/exposure/target differs'):
            replace(first, assignment_design={**first.assignment_design, 'propensities':p2})
        with self.assertRaisesRegex(ValueError,'assignment/exposure/target differs'):
            replace(first, exposure_definition='three_level_treated_neighbor_fraction')

    def test_unresolved_design_fails_and_no_proposal_promotion(self):
        network=net(3,[(0,1),(0,2)])
        p={'0':'1/2','1':'1/2','2':'1/2'}
        unresolved=identify(task(network,p,admitted=False))
        self.assertEqual(unresolved.diagnostics['workflow_status'],'NEEDS_INPUT')
        candidate=identify(task(network,p,admitted=True,authority='PROPOSED'))
        self.assertNotEqual(candidate.verification_status,'VERIFIED')
        known=task(network,p)
        payload=copy.deepcopy(known.identification_spec)
        for assumption in payload['assumptions']:
            if assumption['name']=='known_assignment_law':
                assumption.update(status='CONTRADICTED',confirmed=False,source='human_confirmation')
        rejected=identify(replace(known,identification_spec=payload))
        self.assertEqual(rejected.diagnostics['workflow_status'],'UNSUPPORTED')

    def test_verifier_catches_proposer_corruption_and_result_tampering(self):
        network=net(4,[(0,1),(0,2),(0,3)])
        p={'0':'1/2','1':'1/4','2':'1/2','3':'3/4'}
        query=task(network,p,a=1,s=1)
        spec=IdentificationSpec.model_validate(query.identification_spec)
        backend=RandomizedNetworkArmBackend()
        original=backend.solve(spec)
        self.assertEqual(IdentificationVerifier().verify(spec,original).verification_status,'VERIFIED')
        with patch.object(SupportEngine,'evaluate',return_value=ArmSupportEvidence(
            Fraction(1,2),Fraction(1,2),Fraction(99,100),
        )):
            corrupted=backend.solve(spec)
        self.assertEqual(IdentificationVerifier().verify(spec,corrupted).verification_status,'REJECTED')
        saved=identify(query)
        forged=copy.deepcopy(saved.result)
        forged['certificate']['joint_arm_support_probability']='1/7'
        self.assertEqual(IdentificationVerifier().verify(
            spec, type(original).model_validate(forged)).verification_status,'REJECTED')

    def test_network_of_300_is_population_only(self):
        # Use the actual shared fixed ER300 network, not a substitute chain.
        from fixed_network_fixture import DEFAULT_GRAPH, load_graph
        graph=load_graph(DEFAULT_GRAPH)
        self.assertEqual(graph.shape,(300,300))
        network=NetworkExposureSpec(
            network_id='shared-er300-d1', node_ids=[str(j) for j in range(300)],
            undirected_edges=[(str(i),str(j)) for i in range(300)
                              for j in range(i+1,300) if graph[i,j]],
        )
        p={str(j): ('1/4' if j % 3 == 0 else '1/2' if j % 3 == 1 else '3/4') for j in range(300)}
        for grouping,s in [('strict_majority',0),('three_level_treated_neighbor_fraction',1)]:
            result=identify(task(network,p,node='100',a=1,s=s,grouping=grouping))
            self.assertEqual((result.status,result.verification_status),('POINT','VERIFIED'))
            self.assertIsNone(result.estimation_request)
            self.assertEqual(replay_population_identification(result).verification_status,'VERIFIED')


if __name__=='__main__':
    unittest.main()
