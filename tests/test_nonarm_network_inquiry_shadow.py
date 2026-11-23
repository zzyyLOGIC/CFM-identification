"""Boundary tests for independent non-arm input; no new identification theorem.

These tests intentionally exercise the exact object identities, provenance and
information granularity that the old arm-bound route could not represent.
"""
from __future__ import annotations
import json
from dataclasses import replace
import unittest

from pfn_pipeline._internal.identification.schemas import Assumption, IdentificationSpec
from pfn_pipeline.identification_route_shadow import FIXED_POLICY_CANDIDATE
from pfn_pipeline.network_inquiry_shadow import (
    NetworkStudyContextV17, NetworkA4SourceV17, OBSERVATIONAL_CANDIDATE,
    declare_network_study, study_from_legacy_arm,
    fixed_policy_target_from_context, declare_network_a4_source,
    assess_nonarm_network_inquiry, replay_nonarm_network_inquiry,
)
from network_study_fixtures import legacy_task


def study(regime='experimental', law=True, W='W:fixed', network_id='policy-toy3',
          nodes=('0','1','2'), outcome='Y', graph='DECLARED_PRETREATMENT_FIXED'):
    design={'kind':'heterogeneous_bernoulli_binary_v1',
            'propensities':{n:'1/2' for n in nodes}} if law and regime=='experimental' else None
    return declare_network_study(
        network_id=network_id,node_order=nodes,
        undirected_edges=((nodes[0],nodes[1]),(nodes[0],nodes[2])),
        treatment_variable='T',outcome_variable=outcome,outcome_kind='continuous',
        context_reference=W,observation_regime=regime,assignment_design=design,
        protocol_provenance='reviewed experimental/observational fixture',
        network_provenance='reviewed network fixture',graph_timing_claim=graph)


def target(ctx,z=None,authority='TRUSTED_FIXTURE'):
    return fixed_policy_target_from_context(ctx, z or (0,)*len(ctx.node_order),
                                           authority=authority)


def source(ctx, kind='ASSIGNMENT_NODE_MEANS', z=None, admission='ADMITTED',
           availability='SYMBOLIC_POPULATION_OPERATOR', nodes=None, source_id='source:reviewed'):
    return declare_network_a4_source(ctx,source_id=source_id,operator=kind,
        provenance='reviewed population-operator declaration', admission=admission,
        availability=availability,
        outcome_nodes=tuple(ctx.node_order if nodes is None else nodes),
        assignment_cells=((0,)*len(ctx.node_order),) if kind=='ASSIGNMENT_NODE_MEANS' and z is None else ((z,) if kind=='ASSIGNMENT_NODE_MEANS' else ()),
        exposure_fingerprint='g:unrelated' if kind=='NODE_ARM_MEANS' else None)


def assumptions():
    return tuple(Assumption(name=name, source='demo_specification', confirmed=True,
                            evidence=['reviewed assumption fixture']) for name in (
        'known_assignment_law','full_vector_randomization','consistency',
        'fixed_pretreatment_network','finite_conditional_first_moments'))


def run(ctx=None, srcs=None, ass=None, family=None, tgt=None):
    ctx=ctx or study()
    tgt=tgt or target(ctx)
    return assess_nonarm_network_inquiry(ctx,tgt,tuple(srcs) if srcs is not None else (source(ctx),),
        family_id=family or (FIXED_POLICY_CANDIDATE if ctx.observation_regime=='experimental' else OBSERVATIONAL_CANDIDATE),
        assumptions=assumptions() if ass is None else tuple(ass))


class StudyContextAndTargetV17(unittest.TestCase):
    def test_exact_baseline_fixed_policy_no_arm(self):
        c=study(); t=target(c); s=source(c)
        r=run(c,tgt=t)
        self.assertEqual(r.route_status,'THEOREM_BACKEND_UNAVAILABLE')
        self.assertEqual(r.information_status,'SATISFIED')
        self.assertEqual(r.validity_status,'POSITIVE_UNDER_DECLARED_Q')
        self.assertEqual(r.policy_assignment_probability,'1/8')
        self.assertEqual(r.assumption_status,'ADMITTED')
        self.assertEqual(r.backend_capability,'CANDIDATE_NOT_REGISTERED')
        self.assertIsNone(r.mathematical_identification_from_router)
        self.assertEqual(r.required_observable.assignment_cell,(0,0,0))
        self.assertTrue(replay_nonarm_network_inquiry(c,t,(s,),r,assumptions=assumptions()))

    def test_observational_without_dummy_arm_or_randomized_q(self):
        c=study('observational',law=False); t=target(c); s=source(c)
        r=run(c,(s,),(),tgt=t)
        self.assertEqual(r.route_status,'THEOREM_BACKEND_UNAVAILABLE')
        self.assertEqual(r.information_status,'SATISFIED')
        self.assertEqual(r.assumption_status,'NO_REGISTERED_OBSERVATIONAL_THEOREM')
        self.assertEqual(r.validity_status,'UNRESOLVED')
        self.assertIn('NO_REGISTERED_OBSERVATIONAL_POLICY_THEOREM',r.blockers)
        self.assertIsNone(c.assignment_design_json)
        self.assertNotIn('exposure_definition',c.__dataclass_fields__)
        self.assertNotIn('identification_status',c.__dataclass_fields__)
        self.assertNotIn('assumptions',c.__dataclass_fields__)
        self.assertTrue(replay_nonarm_network_inquiry(c,t,(s,),r,assumptions=()))

    def test_observational_full_joint_without_support_is_unresolved(self):
        c=study('observational'); r=run(c,(source(c,'FULL_JOINT_LAW'),),())
        self.assertEqual(r.information_status,'UNRESOLVED')
        self.assertEqual(r.source_results[0].reason,'FULL_JOINT_CONDITIONING_SUPPORT_UNRESOLVED')
        self.assertNotEqual(r.route_status,'CANDIDATE_READY')

    def test_observational_cannot_declare_randomized_q(self):
        args={'kind':'heterogeneous_bernoulli_binary_v1','propensities':{'0':'1/2','1':'1/2','2':'1/2'}}
        with self.assertRaisesRegex(ValueError,'experimental assignment law'):
            declare_network_study(network_id='n',node_order=('0','1','2'),
              undirected_edges=(('0','1'),('0','2')),treatment_variable='T',outcome_variable='Y',
              outcome_kind='continuous',context_reference='W',observation_regime='observational',
              assignment_design=args,protocol_provenance='source',network_provenance='graph')

    def test_same_study_different_policy_targets_share_context(self):
        c=study()
        a=target(c,(0,0,0))
        b=target(c,(1,1,1))
        self.assertNotEqual(a.target_digest,b.target_digest)
        self.assertEqual(c.study_digest,c.study_digest)
        self.assertIsNone(a.exposure_fingerprint)
        self.assertIsNone(b.exposure_fingerprint)

    def test_observational_conflicting_assumption_evidence_flagged(self):
        c=study('observational')
        a=Assumption(name='consistency',source='human_confirmation',confirmed=True,
                     evidence=['one'])
        b=Assumption(name='consistency',source='human_confirmation',confirmed=False,
                     evidence=['two'],status='UNRESOLVED')
        r=run(c,ass=(a,b))
        self.assertEqual(r.route_status,'ASSUMPTION_CONFLICT')

    def test_identity_scope_equal_protocol_diff(self):
        a=study(); b=study('observational')
        self.assertEqual(a.shared_scope_digest,b.shared_scope_digest)
        self.assertNotEqual(a.protocol_digest,b.protocol_digest)
        self.assertNotEqual(a.study_digest,b.study_digest)
        self.assertEqual(target(a).target_digest,target(b).target_digest)
        self.assertEqual(target(a,(1,1,1)).network_fingerprint,target(b,(1,1,1)).network_fingerprint)

    def test_fixed_target_does_not_depend_on_design_or_g(self):
        b=study(); a=declare_network_study(network_id=b.network_id,node_order=b.node_order,
          undirected_edges=b.undirected_edges,treatment_variable=b.treatment_variable,
          outcome_variable=b.outcome_variable,outcome_kind=b.outcome_kind,
          context_reference=b.context_reference,observation_regime='experimental',
          assignment_design={'kind':'complete_randomization_binary_v1','m':2},
          protocol_provenance='design',network_provenance='network')
        self.assertEqual(target(a).target_digest,target(b).target_digest)
        self.assertNotEqual(a.protocol_digest,b.protocol_digest)
        self.assertIsNone(target(a).exposure_fingerprint)
        self.assertIsNone(target(a).assignment_law_fingerprint)

    def test_authority_does_not_change_scientific_target(self):
        c=study(); x=target(c); y=target(c,authority='PROPOSED')
        self.assertEqual(x.target_digest,y.target_digest)
        self.assertEqual(run(c,tgt=y).route_status,'NEEDS_INPUT')

    def test_query_scope_mismatch(self):
        a=study(); b=study(network_id='different')
        r=run(a,tgt=target(b))
        self.assertEqual(r.route_status,'SPECIFICATION_CONFLICT')

    def test_context_changes_scope_and_source_binding(self):
        c=study(); s=source(c)
        for altered in (study(W='W:new'), study(outcome='new-outcome'),
                        study(nodes=('2','0','1'))):
            self.assertNotEqual(c.shared_scope_digest,altered.shared_scope_digest)
            self.assertEqual(run(altered,(s,)).route_status,'INFORMATION_BLOCKED')

    def test_experimental_cannot_use_observational_source(self):
        a=study(); b=study('observational')
        r=run(a,(source(b),))
        self.assertEqual(r.route_status,'INFORMATION_BLOCKED')

    def test_source_different_assignment_protocol_rejected(self):
        a=study()
        b=declare_network_study(network_id=a.network_id,node_order=a.node_order,
          undirected_edges=a.undirected_edges,treatment_variable=a.treatment_variable,
          outcome_variable=a.outcome_variable,outcome_kind=a.outcome_kind,
          context_reference=a.context_reference,observation_regime='experimental',
          assignment_design={'kind':'complete_randomization_binary_v1','m':2},
          protocol_provenance='quota',network_provenance='reviewed')
        self.assertEqual(run(a,(source(b),)).route_status,'INFORMATION_BLOCKED')

    def test_arm_means_not_assignment_means(self):
        c=study()
        r=run(c,(source(c,'NODE_ARM_MEANS'),))
        self.assertEqual(r.route_status,'INFORMATION_BLOCKED')
        self.assertEqual(r.information_status,'INSUFFICIENT')

    def test_pairwise_marginals_not_joint(self):
        c=study(); r=run(c,(source(c,'PAIRWISE_MARGINALS'),))
        self.assertEqual(r.route_status,'INFORMATION_BLOCKED')

    def test_partial_assignment_cells_not_inferred_complete(self):
        c=study()
        r=run(c,(source(c,z=(1,1,1)),))
        self.assertEqual(r.route_status,'INFORMATION_BLOCKED')

    def test_node_full_law_and_joint_law(self):
        c=study()
        for operator in ('NODE_FULL_LAW','FULL_JOINT_LAW'):
            r=run(c,(source(c,operator),))
            self.assertEqual(r.information_status,'SATISFIED')
            self.assertEqual(r.route_status,'THEOREM_BACKEND_UNAVAILABLE')

    def test_full_joint_needs_all_outcome_nodes(self):
        c=study(); r=run(c,(source(c,'FULL_JOINT_LAW',nodes=('0',)),))
        self.assertEqual(r.route_status,'INFORMATION_BLOCKED')

    def test_just_some_positive_weight_nodes(self):
        c=study(); t=fixed_policy_target_from_context(c,(0,0,0),authority='TRUSTED_FIXTURE',
                                                      unit_weights=('1','0','0'))
        r=run(c,(source(c,nodes=('0',)),),tgt=t)
        self.assertEqual(r.route_status,'THEOREM_BACKEND_UNAVAILABLE')
        self.assertEqual(r.required_observable.node_ids,('0',))

    def test_finite_sample_not_pop_operator(self):
        c=study(); r=run(c,(source(c,availability='FINITE_SAMPLE_ESTIMATE'),))
        self.assertEqual(r.route_status,'INFORMATION_BLOCKED')

    def test_proposed_source_remains_unresolved(self):
        c=study(); r=run(c,(source(c,admission='PROPOSED'),))
        self.assertEqual(r.route_status,'NEEDS_INPUT')
        self.assertEqual(r.information_status,'UNRESOLVED')

    def test_missing_source_remains_unresolved(self):
        c=study(); r=run(c,())
        self.assertEqual(r.route_status,'NEEDS_INPUT')

    def test_known_design_without_randomization_not_causal_permission(self):
        c=study(); r=run(c,ass=())
        self.assertEqual(r.route_status,'NEEDS_INPUT')
        self.assertEqual(r.information_status,'SATISFIED')
        self.assertEqual(r.assumption_status,'NEEDS_INPUT')

    def test_disallowed_assumption_blocks(self):
        c=study()
        ass=list(assumptions()); ass[0]=Assumption(name='known_assignment_law',
           source='human_confirmation',confirmed=False,status='NOT_ADMITTED')
        r=run(c,ass=tuple(ass))
        self.assertEqual(r.route_status,'ASSUMPTIONS_NOT_ADMITTED')

    def test_no_known_design_not_positive_support(self):
        c=study(law=False)
        r=run(c)
        self.assertEqual(r.route_status,'NEEDS_INPUT')
        self.assertEqual(r.validity_status,'UNRESOLVED')
        self.assertIn('EXPERIMENTAL_ASSIGNMENT_LAW_UNRESOLVED',r.blockers)

    def test_off_support_policy_defined_not_partially_identified_by_fiat(self):
        base=study()
        quota=declare_network_study(network_id=base.network_id,node_order=base.node_order,
          undirected_edges=base.undirected_edges,treatment_variable='T',
          outcome_variable='Y',outcome_kind='continuous',context_reference='W:fixed',
          observation_regime='experimental',
          assignment_design={'kind':'complete_randomization_binary_v1','m':1},
          protocol_provenance='fixed quota',network_provenance='graph')
        s=source(quota,z=(0,0,0))
        r=run(quota,(s,))
        self.assertEqual(r.route_status,'OFF_SUPPORT_ALTERNATE_THEOREM')
        self.assertEqual(r.validity_status,'OFF_SUPPORT')
        self.assertIsNone(r.mathematical_identification_from_router)

    def test_duplicate_source_conflict(self):
        c=study(); s=source(c); bad=replace(s,availability='FINITE_SAMPLE_ESTIMATE')
        self.assertEqual(run(c,(s,bad)).route_status,'SOURCE_CONFLICT')

    def test_source_id_order_invariant(self):
        c=study(); s=source(c); s2=source(c,'PAIRWISE_MARGINALS',source_id='other')
        self.assertEqual(run(c,(s,s2)).digest,run(c,(s2,s)).digest)

    def test_same_source_replay_tamper_detected(self):
        c=study(); t=target(c); s=source(c); ass=assumptions(); r=run(c,(s,),ass,tgt=t)
        with self.assertRaises(ValueError):
            replay_nonarm_network_inquiry(c,t,(s,),replace(r,route_status='CANDIDATE_READY'),assumptions=ass)
        with self.assertRaises(ValueError):
            replay_nonarm_network_inquiry(c,t,(replace(s,admission='PROPOSED'),),r,assumptions=ass)

    def test_receipt_replay_binds_reviewed_evidence_and_study_provenance(self):
        c=study(); t=target(c); s=source(c); ass=assumptions(); r=run(c,(s,),ass,tgt=t)
        with self.assertRaises(ValueError):
            replay_nonarm_network_inquiry(replace(c,protocol_provenance='changed provenance'),t,(s,),r,assumptions=ass)
        changed=list(ass)
        changed[0]=Assumption(name=ass[0].name,source=ass[0].source,status=ass[0].status,
                              confirmed=True,evidence=['different reviewed evidence'])
        with self.assertRaises(ValueError):
            replay_nonarm_network_inquiry(c,t,(s,),r,assumptions=tuple(changed))

    def test_wrong_family_cannot_mask_observation_regime(self):
        c=study('observational')
        self.assertEqual(run(c,ass=(),family=FIXED_POLICY_CANDIDATE).route_status,'FAMILY_NOT_APPLICABLE')

    def test_legacy_projection_preserves_graph_network_identity(self):
        t=legacy_task(False)
        c=study_from_legacy_arm(t)
        self.assertEqual(c.network_fingerprint,
            IdentificationSpec.model_validate(t.identification_spec).network_exposure.semantic_fingerprint())
        self.assertEqual(c.node_order,t.node_ids)
        p=fixed_policy_target_from_context(c,(0,)*len(c.node_order),authority='TRUSTED_FIXTURE')
        self.assertEqual(p.target_digest,target(c).target_digest)

    def test_malformed_graph_and_design_fail_closed(self):
        c=study()
        with self.assertRaises(ValueError):
            replace(c,undirected_edges=(('0','0'),))
        with self.assertRaises(ValueError):
            replace(c,assignment_design_json=json.dumps({'kind':'complete_randomization_binary_v1','m':9999}))

    def test_cannot_make_a4_source_with_arm_semantics_without_exposure_identity(self):
        c=study()
        with self.assertRaises(ValueError):
            source(c,'NODE_ARM_MEANS') if False else declare_network_a4_source(c,
              source_id='fake',operator='NODE_ARM_MEANS',provenance='asserted',admission='ADMITTED',
              availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=c.node_order)


if __name__=='__main__':
    unittest.main()
