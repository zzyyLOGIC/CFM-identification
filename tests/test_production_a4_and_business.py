"""v2.1 regression for real A4 gate and non-authoritative business router."""
from __future__ import annotations
import copy
from dataclasses import replace
from fractions import Fraction
import unittest

from pfn_pipeline import (
    identify, make_heterogeneous_bernoulli_arm_task, identify_randomized_network_batch,
    ArmInquiryV21, EffectsInquiryV21, FixedPolicyInquiryV21, FinitePolicyInquiryV21,
    identify_network_business_query, replay_verified_business_outcome,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec, Assumption
from pfn_pipeline.identification_composition import EffectQueryV18
from pfn_pipeline.identification_a4_shadow import declare_a4_source
from pfn_pipeline.identification_policy_r1b import identify_verified_fixed_policy
from pfn_pipeline.identification_policy_r2 import (
    declare_policy_signature, admit_mean_signature_sufficiency,
    declare_signature_population_source,
)
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_a4_source, fixed_policy_target_from_context,
)
from network_study_fixtures import make_study, assumptions
from network_study_fixtures import star_study


def small_task():
    net = NetworkExposureSpec(network_id='a4-v21-3',node_ids=['0','1','2'],
                             undirected_edges=[('0','1'),('0','2')])
    return make_heterogeneous_bernoulli_arm_task(net,
        propensities={'0':'1/2','1':'1/2','2':'1/2'},
        node_id='0',own_treatment_value=0,exposure_value=0,
        source='explicit synthetic protocol',evidence='randomized full vector and population operator',
        admitted=True, synthetic=True,query_authority='TRUSTED_FIXTURE')


def updated(t, **fields):
    raw=copy.deepcopy(t.identification_spec)
    info=raw['information_signature']['objects'][0]
    info.update(fields)
    return replace(t,identification_spec=raw)


class V21ProductionA4Tests(unittest.TestCase):
    def test_official_constructor_preserves_point(self):
        t=small_task();result=identify(t)
        self.assertEqual(result.status,'POINT');self.assertEqual(result.verification_status,'VERIFIED')

    def test_legacy_variable_list_alone_not_a_population_operator(self):
        t=small_task()
        raw=copy.deepcopy(t.identification_spec)
        raw['information_signature']['objects'][0].pop('randomized_arm_observable')
        result=identify(replace(t,identification_spec=raw))
        self.assertEqual(result.status,'UNSUPPORTED')
        self.assertEqual(result.result['reason_code'],'CONDITIONAL_ARM_POPULATION_INFORMATION_REQUIRED')

    def test_weak_marginals_do_not_qualify(self):
        t=updated(small_task(),joint_scope='node_local_marginals_only',
                  whole_network_assignment_law_available=False)
        self.assertEqual(identify(t).status,'UNSUPPORTED')

    def test_strong_explicit_full_joint_entails_arm(self):
        t=small_task();raw=copy.deepcopy(t.identification_spec)
        o=raw['information_signature']['objects'][0]
        v=o['randomized_arm_observable'];v.update(
            operator='FULL_JOINT_LAW', exposure_fingerprint=None,
            arm_coverage=None,arm_cells=[])
        o.update(name='P(T_vector,Y_vector|W)',variables=['treatment','outcome','context'],
                 joint_scope='whole_network_assignment',
                 outcome_representation='full_joint_law',whole_network_assignment_law_available=True)
        modified=replace(t,identification_spec=raw)
        self.assertEqual(identify(modified).status,'POINT')
        self.assertEqual(identify(modified).verification_status,'VERIFIED')

    def test_wrong_law_order_exposure_and_source_status_fail(self):
        for field,value in [('assignment_law_fingerprint','wrong'),('node_order',['2','1','0']),
                            ('exposure_fingerprint','wrong'),('admission','PROPOSED'),
                            ('availability','FINITE_SAMPLE_ESTIMATE')]:
            with self.subTest(field=field):
                t=small_task();raw=copy.deepcopy(t.identification_spec)
                raw['information_signature']['objects'][0]['randomized_arm_observable'][field]=value
                self.assertEqual(identify(replace(t,identification_spec=raw)).status,'UNSUPPORTED')

    def test_only_one_arm_claim_cannot_authorize_entire_batch(self):
        t=small_task();raw=copy.deepcopy(t.identification_spec)
        r=raw['information_signature']['objects'][0]['randomized_arm_observable']
        r.update(arm_coverage='EXPLICIT_CELLS',arm_cells=[['0',0,0]])
        t=replace(t,identification_spec=raw)
        self.assertEqual(identify(t).status,'POINT')
        with self.assertRaisesRegex(ValueError,'BATCH_A4_ARM_COVERAGE_INCOMPLETE'):
            identify_randomized_network_batch(t)

    def test_conflicting_repeated_A4_source_identity_is_rejected(self):
        t=small_task();raw=copy.deepcopy(t.identification_spec)
        original=copy.deepcopy(raw['information_signature']['objects'][0])
        conflicting=copy.deepcopy(original)
        conflicting['randomized_arm_observable']['operator']='NODE_FULL_LAW'
        conflicting['randomized_arm_observable']['exposure_fingerprint']=None
        conflicting['randomized_arm_observable']['arm_coverage']=None
        conflicting['randomized_arm_observable']['arm_cells']=[]
        raw['information_signature']['objects'].append(conflicting)
        out=identify(replace(t,identification_spec=raw))
        self.assertEqual(out.status,'UNSUPPORTED')
        self.assertEqual(out.result['reason_code'],'CONFLICTING_A4_SOURCE_ID')

    def test_full_node_law_covers_only_declared_outcome_nodes(self):
        t=small_task();raw=copy.deepcopy(t.identification_spec)
        o=raw['information_signature']['objects'][0]
        o['randomized_arm_observable'].update(operator='NODE_FULL_LAW',
            exposure_fingerprint=None,arm_coverage=None,arm_cells=[],outcome_nodes=['1'])
        o['variables']=['treatment','outcome','context']
        self.assertEqual(identify(replace(t,identification_spec=raw)).status,'UNSUPPORTED')

    def test_replay_rejects_business_route_label_tampering(self):
        t=small_task();out=identify_network_business_query(ArmInquiryV21(t))
        self.assertEqual(out.status,'POINT')
        with self.assertRaisesRegex(ValueError,'route/result mismatch'):
            replay_verified_business_outcome(replace(out,route='R2_MEAN_SIGNATURE'))

    def test_no_inferred_exposure_sufficiency(self):
        study=star_study()
        target=fixed_policy_target_from_context(study,(1,)*5,authority='TRUSTED_FIXTURE')
        src=declare_network_a4_source(study,source_id='full',operator='NODE_FULL_LAW',
             provenance='hypothetical protocol',admission='ADMITTED',
             availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=study.node_order)
        from network_study_fixtures import r2_assumptions
        outcome=identify_network_business_query(FixedPolicyInquiryV21(
            study,target,r2_assumptions(),r1b_sources=(src,)))
        self.assertEqual(outcome.status,'UNSUPPORTED')
        self.assertEqual(outcome.reason_code,'OFF_SUPPORT_ALTERNATE_THEOREM')

    def test_a4_source_does_not_change_causal_assumptions(self):
        t=small_task();raw=copy.deepcopy(t.identification_spec)
        for assumption in raw['assumptions']:
            if assumption['name']=='full_vector_randomization':
                assumption['status']='UNRESOLVED';assumption['confirmed']=False
        self.assertNotEqual(identify(replace(t,identification_spec=raw)).status,'POINT')

    def test_r1a_arm_and_effect_route(self):
        t=small_task()
        a=identify_network_business_query(ArmInquiryV21(t))
        self.assertEqual((a.status,a.route),('POINT','R1A_RANDOMIZED_ARM'))
        self.assertTrue(replay_verified_business_outcome(a))
        b=identify_randomized_network_batch(t)
        cells=tuple((n,x,s) for n in b.node_ids for x in (0,1) for s in b.exposure_states
                   if b.cell(n,x,s)['status']=='POINT')
        source=declare_a4_source(t, source_id='reviewed arm information',
                 operator='NODE_ARM_MEANS', provenance='synthetic full arm population operator',
                 admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
                 outcome_nodes=b.node_ids,node_order=b.node_ids,arm_cells=cells)
        req=(EffectQueryV18(kind='DIRECT',node_weights=(('0','1'),),
                            reference_exposure=0,comparison_exposure=0),)
        effect=identify_network_business_query(EffectsInquiryV21(b,source,req))
        self.assertEqual((effect.status,effect.route),('POINT','R1A_COMPOSITION'))
        self.assertTrue(replay_verified_business_outcome(effect))

    def test_r1b_fixed_and_finite_mix(self):
        study=make_study(er300=False)
        targets=[fixed_policy_target_from_context(study,z,authority='TRUSTED_FIXTURE')
                 for z in ((0,0,0),(1,1,1))]
        s=declare_network_a4_source(study,source_id='reviewed full law',
             operator='NODE_FULL_LAW',provenance='explicit symbolic population full law',
             admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
             outcome_nodes=study.node_order)
        outcomes=[identify_network_business_query(FixedPolicyInquiryV21(
                 study,t,assumptions(),r1b_sources=(s,))) for t in targets]
        self.assertTrue(all(x.status=='POINT' and x.route=='R1B_FULL_ASSIGNMENT' for x in outcomes))
        mix=identify_network_business_query(FinitePolicyInquiryV21(
                 tuple(x.result for x in outcomes),('1/4','3/4')))
        self.assertEqual((mix.status,mix.route),('POINT','R1B_FINITE_POLICY'))
        self.assertTrue(replay_verified_business_outcome(mix))
        arm=declare_network_a4_source(study,source_id='arm only',operator='NODE_ARM_MEANS',
            provenance='insufficient arm mean info',admission='ADMITTED',
            availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=study.node_order,
            exposure_fingerprint='g:toy')
        blocked=identify_network_business_query(FixedPolicyInquiryV21(
            study,targets[0],assumptions(),r1b_sources=(arm,)))
        self.assertEqual(blocked.status,'NEEDS_INPUT')

    def test_offsupport_r2_fallback_and_assumption_gate(self):
        study=star_study();target=fixed_policy_target_from_context(study,(1,)*5,
                                              authority='TRUSTED_FIXTURE')
        source=declare_network_a4_source(study,source_id='symbolic full law',
             operator='NODE_FULL_LAW',provenance='fixture',admission='ADMITTED',
             availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=study.node_order)
        signature=declare_policy_signature(study,grouping='strict_majority_ties_low')
        cells=tuple((n,1,1) for n in study.node_order)
        r2src=declare_signature_population_source(study,signature,
             source_id='reviewed signatures',operator='NODE_SIGNATURE_MEANS',
             provenance='explicit synthetic population means',admission='ADMITTED',
             availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=study.node_order,
             signature_cells=cells)
        suff=admit_mean_signature_sufficiency(study,signature,
             assumption=Assumption(name='mean_signature_sufficiency',source='demo_specification',
                confirmed=True,status='ADMITTED',evidence=['synthetic world assumes equal mean by g']),
             covered_nodes=study.node_order)
        from network_study_fixtures import r2_assumptions
        req=FixedPolicyInquiryV21(study,target,r2_assumptions(),(source,),
                      signature,suff,(r2src,))
        good=identify_network_business_query(req)
        self.assertEqual((good.status,good.route),('POINT','R2_MEAN_SIGNATURE'))
        self.assertTrue(replay_verified_business_outcome(good))
        self.assertEqual(good.attempted_routes[0][1],'OFF_SUPPORT_ALTERNATE_THEOREM')
        missing=identify_network_business_query(FixedPolicyInquiryV21(
             study,target,r2_assumptions(),(source,)))
        self.assertNotEqual(missing.status,'POINT')


if __name__ == '__main__':
    unittest.main()
