"""E3 production tests independent of the count-DP and theorem verifier.

The oracle enumerates *complete* D1/D2/D3 treatment vectors and weights each
by its original design law, using core references only when classifying arms.
Neither the production SupportEngine nor the backend verifier is used by the
oracle.  This also checks zero-support and the lack of exposure sufficiency.
"""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from itertools import product
import copy
import random
import unittest

from pfn_pipeline import (
    identify, replay_population_identification, replay_handoff,
    make_complete_randomization_arm_task, make_two_group_quota_arm_task,
    make_heterogeneous_bernoulli_arm_task,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec
from pfn_pipeline._internal.identification.randomized_network_arm import (
    GROUP_E3, make_complete_randomization_arm_spec, RandomizedNetworkArmBackend,
)
from pfn_pipeline._internal.identification.verifier import IdentificationVerifier
from pfn_pipeline._internal.identification.randomized_arm_family import (
    AssignmentSpec, ExposureSpec, SupportEngine,
)
from pfn_pipeline._internal.identification.schemas import CompleteRandomizationDesignV1

EXPOSURE = 'pretreatment_core_collaborator_majority'


def net(n: int, edges: list[tuple[int, int]], name: str = 'e3-small') -> NetworkExposureSpec:
    return NetworkExposureSpec(
        network_id=name, node_ids=[str(i) for i in range(n)],
        undirected_edges=[(str(a), str(b)) for a, b in edges],
    )


def edges_and_core(n: int, rng: random.Random):
    # Cycle gives every node at least one neighbor; add independent extra edges.
    edges = {(min(i, (i+1) % n), max(i, (i+1) % n)) for i in range(n)}
    for i in range(n):
        for j in range(i+1, n):
            if rng.random() < 0.38:
                edges.add((i,j))
    graph = net(n, sorted(edges), name=f'e3-random-{n}')
    neighbor = {str(i): set() for i in range(n)}
    for left, right in graph.undirected_edges:
        neighbor[left].add(right)
        neighbor[right].add(left)
    core = {}
    for node, candidates in neighbor.items():
        subset = [other for other in sorted(candidates) if rng.random() < .65]
        if not subset:
            subset = [sorted(candidates)[0]]
        # Deliberately shuffle source input; stored contract must be canonical.
        rng.shuffle(subset)
        core[node] = subset
    return graph, core


def full_design_probability(t: dict[str, int], mode: str, opts: dict) -> Fraction:
    """Oracle uses only the *original* allocation probability q(t|W)."""
    if mode == 'D1':
        mass = Fraction(1)
        for node, treated in t.items():
            p = Fraction(opts['propensities'][node])
            mass *= p if treated else 1-p
        return mass
    if mode == 'D2':
        from math import comb
        return (Fraction(1, comb(len(t), opts['m']))
                if sum(t.values()) == opts['m'] else Fraction(0))
    from math import comb
    if any(sum(t[j] for j in members) != quota
           for members, quota in zip(opts['groups'], opts['treated_quotas'])):
        return Fraction(0)
    den = 1
    for members, quota in zip(opts['groups'], opts['treated_quotas']):
        den *= comb(len(members), quota)
    return Fraction(1, den)


def oracle_arms(graph, core, mode, opts, node):
    ids = graph.node_ids
    weights = {(a,s): Fraction(0) for a in (0,1) for s in (0,1)}
    # Deliberately non-exposure-sufficient potential-outcome schedule:
    # the outcome depends on noncore treated nodes and interaction terms.
    outcome_numerators = {(a,s): Fraction(0) for a in (0,1) for s in (0,1)}
    for bits in product((0,1), repeat=len(ids)):
        t = dict(zip(ids, bits))
        p = full_design_probability(t, mode, opts)
        if not p:
            continue
        k = sum(t[j] for j in core[node])
        exposure = int(k > len(core[node])//2)
        arm = (t[node],exposure)
        # All variables available only to the synthetic oracle, NOT to ID code.
        y = Fraction(sum((j+1)*t[str(j)] for j in range(len(ids))), 3)
        y += Fraction(t[ids[0]]*t[ids[-1]], 7)
        weights[arm] += p
        outcome_numerators[arm] += p*y
    assert sum(weights.values()) == 1
    return weights, outcome_numerators


def task(graph, core, mode, opts, a, s, node='0', admitted=True):
    keywords = dict(
        node_id=node, own_treatment_value=a, exposure_value=s,
        exposure_definition=EXPOSURE, core_collaborators=core,
        source='fixed pre-treatment design and collaborator nominations',
        evidence='signed synthetic network assignment protocol',
        admitted=admitted, synthetic=True, query_authority='TRUSTED_FIXTURE',
    )
    builders = {
        'D1': make_heterogeneous_bernoulli_arm_task,
        'D2': make_complete_randomization_arm_task,
        'D3': make_two_group_quota_arm_task,
    }
    return builders[mode](graph, **opts, **keywords)


class CoreCollaboratorProductionTests(unittest.TestCase):
    def test_cross_group_golden_case_and_zero_support(self):
        # Graph edges 0--4 exist, but 4 is NOT a core collaborator of 0.
        graph = net(5, [(0,1),(0,2),(0,3),(0,4)])
        core = {'0':['3','2','1'], '1':['0'], '2':['0'], '3':['0'], '4':['0']}
        opts = {'groups':(('0','1'),('2','3','4')), 'treated_quotas':(1,1)}
        expected = {(0,0):Fraction(1,6),(0,1):Fraction(1,3),
                    (1,0):Fraction(1,2),(1,1):Fraction(0)}
        got, _ = oracle_arms(graph, core, 'D3', opts, '0')
        self.assertEqual(got, expected)
        for (a,s), weight in expected.items():
            with self.subTest(a=a,s=s):
                ptask = task(graph,core,'D3',opts,a,s)
                self.assertEqual(ptask.metadata['setting'], 'D3xE3')
                self.assertEqual(ptask.exposure_definition, EXPOSURE)
                self.assertIn('-E3', ptask.target_id)
                self.assertEqual(ptask.identification_spec['randomized_network_arm_theorem_contract']['core_collaborators']['0'], ('1','2','3'))
                result = identify(ptask)
                if weight:
                    self.assertEqual((result.status,result.verification_status),('POINT','VERIFIED'))
                    self.assertEqual(result.result['certificate']['joint_arm_support_probability'],str(weight))
                    self.assertEqual(result.result['certificate']['core_neighbor_ids'],['1','2','3'])
                    self.assertEqual(result.result['certificate']['core_reference_size'],3)
                    self.assertEqual(result.result['identified_functional']['core_neighbor_ids'],('1','2','3'))
                    self.assertEqual(result.result['identified_functional']['grouping'],
                                     'K_i(C_i)>floor(|C_i|/2);ties=0;C_i fixed pretreatment')
                    self.assertEqual(replay_population_identification(result).verification_status,'VERIFIED')
                    self.assertIsNone(result.estimation_request)
                    self.assertEqual(result.diagnostics['workflow_status'],'IDENTIFIED_NO_ESTIMATION_ADAPTER')
                    with self.assertRaises(ValueError):
                        replay_handoff(result)
                else:
                    self.assertEqual(result.result['reason_code'], 'ZERO_ARM_SUPPORT')
                    self.assertEqual(result.status, 'UNSUPPORTED')

    def test_small_network_full_vector_design_oracle(self):
        rng = random.Random(20261014)
        check_count = 0
        for n in range(3,9):
            for trial in range(5):
                graph, core = edges_and_core(n,rng)
                n1 = n // 2
                designs = (
                    ('D1', {'propensities':{
                        node:rng.choice(('0','1','1/5','1/3','1/2','2/3','4/5'))
                        for node in graph.node_ids
                    }}),
                    ('D2', {'m':rng.randrange(n+1)}),
                    ('D3', {'groups':(tuple(str(i) for i in range(n1)),tuple(str(i) for i in range(n1,n))),
                            'treated_quotas':(rng.randrange(n1+1),rng.randrange(n-n1+1))}),
                )
                for mode, opts in designs:
                    for node in graph.node_ids:
                        truth, _ = oracle_arms(graph,core,mode,opts,node)
                        for a in (0,1):
                            for s in (0,1):
                                with self.subTest(n=n,trial=trial,mode=mode,node=node,a=a,s=s):
                                    ptask = task(graph,core,mode,opts,a,s,node=node)
                                    result = identify(ptask)
                                    mass = truth[(a,s)]
                                    if mass:
                                        self.assertEqual((result.status,result.verification_status),('POINT','VERIFIED'))
                                        self.assertEqual(Fraction(result.result['certificate']['joint_arm_support_probability']), mass)
                                    else:
                                        self.assertEqual(result.result['reason_code'],'ZERO_ARM_SUPPORT')
                                check_count+=1
        self.assertGreaterEqual(check_count, 1900)

    def test_component_support_matches_unconditional_original_q(self):
        graph = net(5, [(0,1),(0,2),(0,3),(0,4)])
        core={'0':['1','2','3'],'1':['0'],'2':['0'],'3':['0'],'4':['0']}
        assignment = AssignmentSpec(CompleteRandomizationDesignV1(m=2))
        exposure = ExposureSpec(GROUP_E3,{node: tuple(others) for node,others in core.items()})
        weights, _ = oracle_arms(graph,core,'D2',{'m':2},'0')
        for arm in weights:
            evidence = SupportEngine.evaluate(network=graph,assignment=assignment,exposure=exposure,
                                              node_id='0',own_treatment_value=arm[0],exposure_value=arm[1])
            self.assertEqual(evidence.joint_probability, weights[arm])
            self.assertEqual(evidence.own_probability * evidence.exposure_given_own_probability,
                             evidence.joint_probability)

    def test_invalid_core_mapping_rejected_without_guessing(self):
        graph=net(5,[(0,1),(0,2),(0,3),(0,4)])
        core={'0':['1','2','3'],'1':['0'],'2':['0'],'3':['0'],'4':['0']}
        opts={'m':2}
        variants=[
            {**core,'0':[]},
            {**core,'0':['1','1']},
            {**core,'0':['4','no-such-node']},
            {**core,'0':['0']},
            {**core,'1':['2']},
            {key:value for key,value in core.items() if key!='4'},
            {**core,'absent':['0']},
        ]
        for bad in variants:
            with self.subTest(bad=bad), self.assertRaises((ValueError,TypeError)):
                task(graph,bad,'D2',opts,1,0)
        with self.assertRaisesRegex(ValueError,'requires a pre-treatment core collaborator'):
            task(graph,None,'D2',opts,1,0)
        with self.assertRaisesRegex(ValueError,'only be supplied for E3'):
            make_complete_randomization_arm_task(graph,m=2,node_id='0',own_treatment_value=1,
                exposure_value=0,source='protocol',evidence='evidence',synthetic=True,
                admitted=True,query_authority='TRUSTED_FIXTURE',
                exposure_definition='strict_majority',core_collaborators=core)
        isolate=net(4,[(0,1),(1,2)])
        with self.assertRaises(ValueError):
            task(isolate,{'0':['1'],'1':['0'],'2':['1'],'3':[]},'D2',{'m':2},1,0)
        with self.assertRaises(ValueError):
            task(graph,core,'D2',opts,1,2)

    def test_change_core_target_and_tampered_certificates_rejected(self):
        graph=net(5,[(0,1),(0,2),(0,3),(0,4)])
        core={'0':['1','2','3'],'1':['0'],'2':['0'],'3':['0'],'4':['0']}
        changed={**core,'0':['1','2','4']}
        opts={'m':2}
        old=task(graph,core,'D2',opts,0,1)
        new=task(graph,changed,'D2',opts,0,1)
        self.assertNotEqual(old.target_fingerprint,new.target_fingerprint)
        self.assertNotEqual(old.identification_spec['query']['response_target_fingerprint'],
                            new.identification_spec['query']['response_target_fingerprint'])
        original=identify(old)
        self.assertEqual((original.status,original.verification_status),('POINT','VERIFIED'))
        for section,key,value in [
            ('certificate','core_neighbor_ids',['1','2','4']),
            ('certificate','joint_arm_support_probability','99/100'),
            ('identified_functional','core_neighbor_ids',['1','2','4']),
            ('identified_functional','target_fingerprint','tampered'),
        ]:
            with self.subTest(section=section,key=key):
                result=copy.deepcopy(original.result)
                result[section][key]=value
                with self.assertRaisesRegex(ValueError,'proof replay failed|identified target fingerprint differs'):
                    replay_population_identification(replace(original,result=result))
        spec=copy.deepcopy(old.identification_spec)
        spec['randomized_network_arm_theorem_contract']['core_collaborators']['0']=['1','2','4']
        forged=replace(old, identification_spec=spec)
        res=identify(forged)
        self.assertEqual(res.result['reason_code'],'DESIGN_DEPENDENT_TARGET_FINGERPRINT_MISMATCH')

    def test_unadmitted_assumptions_stop_without_point_claim(self):
        graph=net(4,[(0,1),(0,2),(0,3)])
        core={'0':['1'],'1':['0'],'2':['0'],'3':['0']}
        inp=task(graph,core,'D1',{'propensities':{str(i):'1/2' for i in range(4)}},1,0,admitted=False)
        out=identify(inp)
        self.assertEqual(out.diagnostics['workflow_status'],'NEEDS_INPUT')
        self.assertEqual(out.status,'UNSUPPORTED')
        self.assertIsNone(out.estimation_request)

    def test_proposer_and_independent_verifier_disagree_on_tamper(self):
        graph=net(5,[(0,1),(0,2),(0,3),(0,4)])
        core={'0':['1','2'],'1':['0'],'2':['0'],'3':['0'],'4':['0']}
        spec=make_complete_randomization_arm_spec(graph,m=2,node_id='0',
            own_treatment_value=1,exposure_value=0,source='fixture',evidence='fixture',
            admitted=True,synthetic=True,query_authority='TRUSTED_FIXTURE',
            exposure_definition=EXPOSURE,core_collaborators=core)
        engine=RandomizedNetworkArmBackend()
        raw=engine.solve(spec)
        self.assertEqual(IdentificationVerifier().verify(spec,raw).verification_status,'VERIFIED')
        altered=raw.model_copy(deep=True)
        altered.certificate['joint_arm_support_probability']='0'
        self.assertEqual(IdentificationVerifier().verify(spec,altered).verification_status,'REJECTED')

    def test_exposure_sufficiency_is_not_required(self):
        graph = net(6,[(0,j) for j in range(1,6)])
        core = {'0':['1','2'], **{str(j):['0'] for j in range(1,6)}}
        opts = {'m':2}
        # For a=0,s=0, several legal allocations have identical core exposure
        # but different treated noncore colleagues and potential outcomes.
        weight, numerator = oracle_arms(graph,core,'D2',opts,'0')
        self.assertGreater(weight[(0,0)],0)
        self.assertNotEqual(numerator[(0,0)],0)
        answer = identify(task(graph,core,'D2',opts,0,0))
        self.assertEqual((answer.status,answer.verification_status),('POINT','VERIFIED'))
        self.assertEqual(Fraction(answer.result['certificate']['joint_arm_support_probability']),weight[(0,0)])

    def test_shared_er300_fixed_graph_without_pfn_adapter(self):
        from fixed_network_fixture import DEFAULT_GRAPH, load_graph
        matrix = load_graph(DEFAULT_GRAPH)
        self.assertEqual(matrix.shape,(300,300))
        graph = NetworkExposureSpec(
            network_id='shared-er300-e3', node_ids=[str(i) for i in range(300)],
            undirected_edges=[(str(i),str(j)) for i in range(300)
                              for j in range(i+1,300) if matrix[i,j]],
        )
        neighbors = {node: [] for node in graph.node_ids}
        for left,right in graph.undirected_edges:
            neighbors[left].append(right)
            neighbors[right].append(left)
        # Deterministic, documented pre-treatment core *fixture*; no model
        # learns or invents the core sets from observed treatment/outcomes.
        core = {node: members[:3] for node,members in neighbors.items()}
        self.assertTrue(all(len(members)==3 for members in core.values()))
        designs = (
            ('D1',{'propensities':{node:'1/4' if int(node)%2 else '3/4' for node in graph.node_ids}}),
            ('D2',{'m':150}),
            ('D3',{'groups':(tuple(str(i) for i in range(150)),
                              tuple(str(i) for i in range(150,300))),
                   'treated_quotas':(75,75)}),
        )
        for design,opts in designs:
            with self.subTest(design=design):
                answer=identify(task(graph,core,design,opts,1,0,node='100'))
                self.assertEqual((answer.status,answer.verification_status),('POINT','VERIFIED'))
                self.assertGreater(Fraction(answer.result['certificate']['joint_arm_support_probability']),0)
                self.assertEqual(replay_population_identification(answer).verification_status,'VERIFIED')
                self.assertIsNone(answer.estimation_request)


if __name__=='__main__':
    unittest.main()
