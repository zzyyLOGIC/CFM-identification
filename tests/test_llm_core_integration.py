"""Actual Gateway 0.9 -> v2.8 P1.1 theorem integration regression.

Never a real LLM API benchmark, never externally authenticated A4/A5.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from cfm_id_llm.multiquery import ReviewedMultiQueryV09, HumanMultiQueryReviewV09
from cfm_id_llm.orchestration_schemas import canonical_sha256
from cfm_id_llm.schemas import BusinessCase, TargetDraft, TargetKind
from cfm_id_bridge.bridge import (
    FormalQueryBindingV29, ScientificAdmissionV29, run_verified_multiquery_v29,
)
from cfm_id_bridge.d1_binding import ReviewedD1ArmPacketV29, prepare_d1_arm_binding_v29
from examples.llm_core_fixture import reviewed_case, bindings, scientist, d1_arm_packet

from pfn_pipeline.network_inquiry_shadow import declare_network_study, fixed_policy_target_from_context, declare_network_a4_source
from pfn_pipeline.identification_business import FixedPolicyInquiryV21

ROOT = Path(__file__).resolve().parents[1]


class ActualV29CoreIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.case, self.reviewed = reviewed_case()
        self.binds = bindings(self.case, self.reviewed)

    def run_join(self, bound=None, case=None, reviewed=None):
        return run_verified_multiquery_v29(self.case if case is None else case,
            self.reviewed if reviewed is None else reviewed,
            self.binds if bound is None else bound)

    def test_two_different_targets_both_real_theorem_point_with_replay(self):
        report = self.run_join()
        self.assertEqual(report.verified_query_count, 2)
        self.assertEqual([(r.status, r.route) for r in report.results],
            [('POINT','R1A_RANDOMIZED_ARM'),('POINT','R1B_FULL_ASSIGNMENT')])
        for r in report.results:
            self.assertEqual(r.verification_level, 'CORE_REPLAY_VERIFIED')
            self.assertIsNotNone(r.core_outcome_sha256)
            self.assertTrue(r.identification)
            self.assertFalse(r.estimation_handoff_allowed)
        self.assertFalse(report.estimation_handoff_allowed)

    def test_gateway_finite_sample_does_not_itself_grant_point(self):
        result=self.run_join(bound=())
        self.assertEqual(result.verified_query_count,0)
        self.assertEqual([x.reason_code for x in result.results],
            ['A4_SCIENTIFIC_ADMISSION_REQUIRED','A4_SCIENTIFIC_ADMISSION_REQUIRED'])
        self.assertTrue(all(x.identification is None for x in result.results))

    def test_one_formal_binding_can_only_verify_its_own_query(self):
        out=self.run_join(bound=(self.binds[0],))
        self.assertEqual((out.results[0].status,out.results[1].status),('POINT','NEEDS_INPUT'))

    def test_case_content_change_invalidates_all_confirmations(self):
        modified=self.case.model_copy(update={'business_question':self.case.business_question+' 另加备注。'})
        with self.assertRaisesRegex(ValueError,'stale review'):
            self.run_join(case=modified)

    def test_rebinding_old_admission_to_changed_query_rejected(self):
        b=self.binds[0]
        old=b.admission
        bad=old.model_copy(update={'target_sha256':'0'*64})
        v=self.run_join(bound=(FormalQueryBindingV29(bad,b.inquiry),))
        self.assertEqual(v.results[0].status,'INCOMPATIBLE')
        self.assertEqual(v.results[0].reason_code,'STALE_SCIENTIFIC_ADMISSION')

    def test_binding_cannot_claim_incompatible_theorem_class(self):
        with self.assertRaisesRegex(ValueError,'actual typed inquiry'):
            FormalQueryBindingV29(self.binds[1].admission, self.binds[0].inquiry)

    def test_duplicate_or_nonexistent_bindings_block_entire_run(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            self.run_join(bound=(self.binds[0],self.binds[0]))
        a=self.binds[0].admission.model_copy(update={'query_id':'q999'})
        with self.assertRaisesRegex(ValueError,'nonexistent'):
            self.run_join(bound=(FormalQueryBindingV29(a,self.binds[0].inquiry),))

    def test_no_human_business_confirmation_means_no_core_call(self):
        h=self.reviewed.human_review.model_copy(update={'confirmed_query_ids':['q2']})
        updated=ReviewedMultiQueryV09(report=self.reviewed.report,human_review=h)
        v=self.run_join(reviewed=updated)
        self.assertEqual(v.results[0].status,'AWAITING_HUMAN_REVIEW')
        # Altering the human review changes the approved scientific-binding digest.
        self.assertEqual(v.results[1].status,'INCOMPATIBLE')

    def test_unresolved_a3_not_overridden_by_scientist_review(self):
        from cfm_id_llm.schemas import StructureDraft, SemanticClaim
        from cfm_id_llm.multiquery import audit_multiquery, approve_multiquery
        # Structural gate is a local test of audit: dynamic q-dependent fields
        draft=self.reviewed.report.draft.model_copy(deep=True)
        draft.shared_draft.structure.exposure_mapping=SemanticClaim()
        report=audit_multiquery(self.case,draft,provider='test',prompt_version='local')
        self.assertIn('A3_EXPOSURE_UNRESOLVED',
            [i.code for i in report.query_audits[0].issues])
        from cfm_id_llm.audit import fingerprint_business_case
        newhuman=self.reviewed.human_review.model_copy(update={
            'draft_sha256':report.draft_sha256})
        validated=approve_multiquery(self.case,report,newhuman)
        # Remap approved target fingerprint to updated source/draft; scientific
        # claims cannot magically fix unresolved business exposure semantics.
        newa=self.binds[0].admission.model_copy(update={'draft_sha256':report.draft_sha256})
        out=run_verified_multiquery_v29(self.case,validated,
                           (FormalQueryBindingV29(newa,self.binds[0].inquiry),))
        self.assertEqual(out.results[0].status,'NEEDS_INPUT')
        self.assertEqual(out.results[0].reason_code,'UNRESOLVED_BUSINESS_AUDIT')

    def test_a4_a5_declared_scientist_truth_required(self):
        data=self.binds[0].admission.model_dump(mode='json')
        for field in ('a4_scientifically_admitted','a5_scientifically_admitted',
                      'math_target_crosswalk_confirmed'):
            with self.subTest(field=field):
                tmp=data.copy();tmp[field]=False
                with self.assertRaises(ValidationError): ScientificAdmissionV29.model_validate(tmp)

    def test_science_admission_is_not_a_digital_signature(self):
        self.assertFalse(hasattr(self.binds[0].admission,'cryptographic_signature'))
        self.assertTrue(self.binds[0].admission.is_synthetic_fixture)

    def test_nonpoint_payload_not_emitted_when_theorem_fails(self):
        with patch('cfm_id_bridge.bridge.identify_network_business_query') as core:
            from pfn_pipeline.identification_business import VerifiedBusinessOutcomeV21
            core.return_value=VerifiedBusinessOutcomeV21('ARM','NEEDS_INPUT',None,
                'A4_POPULATION_OPERATOR_REQUIRED',None)
            result=self.run_join(bound=(self.binds[0],))
        self.assertEqual(result.results[0].status,'NEEDS_INPUT')
        self.assertIsNone(result.results[0].identification)
        self.assertEqual(result.results[0].fallback,'BLOCKED')

    def test_unsupported_a5_block_does_not_authorize_candidate_fallback(self):
        with patch('cfm_id_bridge.bridge.identify_network_business_query') as core:
            from pfn_pipeline.identification_business import VerifiedBusinessOutcomeV21
            core.return_value=VerifiedBusinessOutcomeV21('ARM','UNSUPPORTED',None,
                'A5_ASSUMPTIONS_NOT_ADMITTED',None)
            result=self.run_join(bound=(self.binds[0],))
        self.assertEqual(result.results[0].status,'UNSUPPORTED')
        self.assertEqual(result.results[0].fallback,'BLOCKED')

    def test_only_explicit_true_theorem_gap_allows_unexecuted_fallback(self):
        with patch('cfm_id_bridge.bridge.identify_network_business_query') as core:
            from pfn_pipeline.identification_business import VerifiedBusinessOutcomeV21
            core.return_value=VerifiedBusinessOutcomeV21('ARM','UNSUPPORTED',None,
                'THEOREM_BACKEND_UNAVAILABLE',None)
            result=self.run_join(bound=(self.binds[0],))
        self.assertEqual(result.results[0].fallback,'ELIGIBLE_NOT_EXECUTED')
        self.assertIsNone(result.results[0].identification)

    def test_core_replay_failure_blocks_point_and_handoff(self):
        with patch('cfm_id_bridge.bridge.replay_verified_business_outcome', return_value=False):
            r=self.run_join(bound=(self.binds[0],))
        self.assertEqual(r.results[0].status,'CORE_VERIFICATION_FAILED')
        self.assertEqual(r.results[0].verification_level,'FAILED')
        self.assertIsNone(r.results[0].identification)
        self.assertEqual(r.verified_query_count,0)

    def test_core_exception_fail_closed(self):
        with patch('cfm_id_bridge.bridge.identify_network_business_query',side_effect=RuntimeError('bad')):
            r=self.run_join(bound=(self.binds[0],))
        self.assertEqual(r.results[0].status,'CORE_ERROR')
        self.assertEqual(r.results[0].fallback,'BLOCKED')

    def test_business_target_cannot_be_silently_relabelled(self):
        a=self.binds[0].admission.model_copy(update={'formal_family':'R1B_FIXED_POLICY'})
        with self.assertRaises(ValueError):FormalQueryBindingV29(a,self.binds[0].inquiry)

    def test_packet_validates_exact_node_and_propensity_domain(self):
        cfg=d1_arm_packet(self.case,self.reviewed)
        payload=cfg.model_dump(mode='json')
        payload['propensities'].pop('C')
        with self.assertRaises(ValidationError): ReviewedD1ArmPacketV29.model_validate(payload)
        payload=cfg.model_dump(mode='json');payload['target_node_id']='ABSENT'
        with self.assertRaises(ValidationError): ReviewedD1ArmPacketV29.model_validate(payload)

    def test_d1_packet_no_arbitrary_injected_executable_object(self):
        data=d1_arm_packet(self.case,self.reviewed).model_dump(mode='json')
        data['python_callable']='malicious:code'
        with self.assertRaises(ValidationError):ReviewedD1ArmPacketV29.model_validate(data)

    def test_real_core_d1_off_support_does_not_create_point(self):
        # All experimental randomization at zero treatment => node arm a=1 off support.
        from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec
        from pfn_pipeline.identification import make_heterogeneous_bernoulli_arm_task
        from pfn_pipeline.identification_business import ArmInquiryV21
        net=NetworkExposureSpec(network_id='SYNTH_BRIDGE29_GRAPH',node_ids=['A','B','C'],
            undirected_edges=[('A','B'),('A','C')])
        try:
            t=make_heterogeneous_bernoulli_arm_task(net,
                propensities={'A':'1/2','B':'1','C':'1'},
                node_id='A',own_treatment_value=0,exposure_value=0,
                source='test',evidence='independent exact hypothetical experimental population',
                admitted=True,synthetic=True,query_authority='TRUSTED_FIXTURE')
            o=self.run_join(bound=(FormalQueryBindingV29(self.binds[0].admission,
                             ArmInquiryV21(t)),))
            self.assertNotEqual(o.results[0].status,'POINT')
        except ValueError:
            pass  # core constructor itself may reject degenerate q

    def test_r2_mean_signature_requires_a_separate_scientific_license_and_replays(self):
        # A second real, but hypothetical, D2 4-of-5 randomized study. The
        # all-treated policy has full-assignment q=0, yet R2 can be POINT with
        # a strictly admitted mean-signature assumption and population operator.
        from cfm_id_llm.schemas import (
            SemanticClaim, EvidenceQuote, DraftProblemSpec, UnitsVariablesDraft,
            InformationDesignDraft, AssignmentFamily, PopulationInformationLevel,
            StructureDraft, BusinessCase, TargetDraft,
        )
        from cfm_id_llm.providers.mock import MockProvider
        from cfm_id_llm.multiquery import (
            MultiQueryDraftV09, BusinessInquiryV09, approve_multiquery,
        )
        from cfm_id_llm.multiquery_formulator import MultiQueryFormulatorV09
        from pfn_pipeline._internal.identification.schemas import Assumption
        from pfn_pipeline.identification_policy_r2 import (
            declare_policy_signature, declare_signature_population_source,
            admit_mean_signature_sufficiency,
        )
        from network_study_fixtures import star_study, r2_assumptions
        qtext=("一家销售团队有5名员工，1名销售组长连接其余4名员工，所有合作关系在实验前确定。"
               "每轮实验恰好随机抽取4名员工开放AI工具，持续记录处理状态和销售额。"
               "我们想知道如果今后五个人全部使用AI，团队的平均销售额会怎样。")
        case=BusinessCase(case_id='SYNTH_R2BRIDGE29',business_question=qtext)
        def cl(x):
            assert x in qtext
            return SemanticClaim(value=x,basis='EXPLICIT_TEXT',
                evidence=[EvidenceQuote(source_id='business_question',quote=x)])
        goal='如果今后五个人全部使用AI，团队的平均销售额会怎样'
        target=TargetDraft(kind=TargetKind.FIXED_POLICY_VALUE,description=cl(goal))
        draft=MultiQueryDraftV09(primary_query_id='q1',shared_draft=DraftProblemSpec(
            target=target,
            units_variables=UnitsVariablesDraft(analysis_unit=cl('5名员工'),
                treatment=cl('开放AI工具'),outcome=cl('销售额')),
            structure=StructureDraft(unit_network=cl('1名销售组长连接其余4名员工'),
                network_pretreatment_status=cl('所有合作关系在实验前确定')),
            information_design=InformationDesignDraft(
                assignment_family=AssignmentFamily.COMPLETE_RANDOMIZATION,
                assignment_law=cl('恰好随机抽取4名员工开放AI工具'),
                population_information_level=PopulationInformationLevel.FINITE_SAMPLE_DESCRIPTION,
                sample_data_description=cl('记录处理状态和销售额')),
        ),queries=[BusinessInquiryV09(query_id='q1',target=target,business_goal=cl(goal))])
        rep=MultiQueryFormulatorV09(MockProvider(draft.model_dump(mode='json'))).formulate(case)
        from cfm_id_llm.multiquery import HumanMultiQueryReviewV09
        review=approve_multiquery(case,rep,HumanMultiQueryReviewV09(
            case_id=case.case_id,input_sha256=rep.input_sha256,draft_sha256=rep.draft_sha256,
            confirmed_query_ids=['q1'],reviewed_by='Scientific tester',decision='CONFIRMED',
            review_note='The meaning of the all-treated five-node policy was confirmed'))
        study=star_study(); policy=fixed_policy_target_from_context(study,(1,)*5,authority='TRUSTED_FIXTURE')
        signature=declare_policy_signature(study,grouping='strict_majority_ties_low')
        src=declare_signature_population_source(study,signature,
            source_id='R2_ADMITTED_SYNTHETIC_NODE_SIGNATURE_MEANS',operator='NODE_SIGNATURE_MEANS',
            provenance='independently admitted synthetic population means',admission='ADMITTED',
            availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=study.node_order,
            signature_cells=tuple((n,1,1) for n in study.node_order))
        suff=admit_mean_signature_sufficiency(study,signature,
            assumption=Assumption(name='mean_signature_sufficiency',source='demo_specification',
                confirmed=True,status='ADMITTED',evidence=['explicit hypothetical signature-mean license']),
            covered_nodes=study.node_order)
        science=ScientificAdmissionV29(
            case_id=case.case_id,input_sha256=rep.input_sha256,draft_sha256=rep.draft_sha256,
            query_id='q1',target_sha256=canonical_sha256(target),
            formal_family='R2_FIXED_POLICY',formal_target_fingerprint=policy.target_digest,
            math_target_description='All-treated fixed policy value for star-5 network; equally weighted team sales mean',
            math_target_crosswalk_confirmed=True,
            scientific_reviewer='Synthetic R2 subject matter expert',
            evidence_reference='HYPOTHETICAL_D2_4_OF_5_PROTOCOL_2026',
            a4_population_operator_reference='SYNTHETIC_POPULATION_NODE_SIGNATURE_MEANS',
            a4_scientifically_admitted=True,
            a5_assumption_reference='SYNTHETIC_MEAN_SIGNATURE_SUFFICIENCY_EXPLICIT',
            a5_scientifically_admitted=True,
            scientific_review_note='Signature sufficiency is a separate synthetic scientific assumption, not a property of E1.',
            is_synthetic_fixture=True,
        )
        formal=FixedPolicyInquiryV21(study,policy,r2_assumptions(),
                                    r2_signature=signature,r2_sufficiency=suff,r2_sources=(src,))
        from examples.llm_core_fixture import independently_review_fixture
        science=independently_review_fixture(science,formal,review,'q1','R2_MEAN_SIGNATURE')
        from examples.llm_core_fixture import independently_confirm_business_intent_v292
        intent=independently_confirm_business_intent_v292(review,'q1',
            dict(classification='FIXED_POLICY',node_order=list(study.node_order),
                 assignment=[1]*5,unit_weights=['1/5']*5),
            evidence='Synthetic researcher confirmed all five employees receive AI')
        from examples.llm_core_fixture import independently_review_evidence_v292
        evidence=independently_review_evidence_v292(science,formal)
        outcome=run_verified_multiquery_v29(case,review,(FormalQueryBindingV29(science,formal,intent,evidence),))
        self.assertEqual((outcome.results[0].status,outcome.results[0].route),
            ('POINT','R2_MEAN_SIGNATURE'))
        self.assertEqual(outcome.results[0].verification_level,'CORE_REPLAY_VERIFIED')
        with self.assertRaisesRegex(ValueError,'R1b science review'):
            FormalQueryBindingV29(science.model_copy(update={'formal_family':'R1B_FIXED_POLICY'}),formal)

    def test_no_numeric_business_effect_produced(self):
        result=self.run_join()
        for r in result.results:
            self.assertNotIn('numeric_effect', json.dumps(r.model_dump(mode='json')))
            self.assertIs(r.estimation_handoff_allowed, False)

    def test_separate_gateway_and_math_baseline_named(self):
        res=self.run_join()
        self.assertEqual(res.math_baseline,'v2.8-postrelease-P1.1')
        self.assertEqual(res.gateway_baseline,'v0.9.0')

    def test_gateway_mock_used_only_as_draft_provider(self):
        from cfm_id_llm.providers.mock import MockProvider
        from cfm_id_llm.multiquery_formulator import MultiQueryFormulatorV09
        from examples.llm_core_fixture import case_and_mock_draft
        case,draft=case_and_mock_draft(); mock=MockProvider(draft.model_dump(mode='json'))
        a=MultiQueryFormulatorV09(mock).formulate(case)
        self.assertEqual(mock.calls,1)
        self.assertEqual(a.mathematical_verification,'NOT_PERFORMED')

    def test_unified_cli_end_to_end_mock_review_then_real_d1_core(self):
        from examples.llm_core_fixture import case_and_mock_draft
        case, draft = case_and_mock_draft()
        with tempfile.TemporaryDirectory() as t:
            base=Path(t)
            def dump(name,obj):
                path=base/name
                path.write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')
                return str(path)
            casepath=dump('case.json',case.model_dump(mode='json'))
            mockpath=dump('mock.json',draft.model_dump(mode='json'))
            pkgpath=dump('d1.json',d1_arm_packet(self.case,self.reviewed).model_dump(mode='json'))
            reportpath=str(base/'formulation.json')
            humanpath=str(base/'approved.json')
            resultpath=str(base/'result.json')
            def cli(*args):
                result=subprocess.run([sys.executable,'-m','cfm_id_bridge',*args],
                                      cwd=str(ROOT),capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,msg=result.stderr[-700:])
            cli('formulate','--case-json',casepath,'--provider','mock',
                '--mock-response',mockpath,'--format','json','--output',reportpath)
            cli('review','--case-json',casepath,'--report-json',reportpath,
                '--confirmed','q1','--confirmed','q2','--reviewer','Synthetic study reviewer',
                '--note','Human-confirmed synthetic business target meanings and explicit comparison',
                '--output',humanpath)
            businesspath=dump('business_intent_q1.json',self.binds[0].business_intent.model_dump(mode='json'))
            evidencepath=dump('evidence_q1.json',self.binds[0].evidence_manifest.model_dump(mode='json'))
            cli('identify','--case-json',casepath,'--report-json',reportpath,
                '--human-review-json',humanpath,'--d1-packet-json',pkgpath,
                '--business-intent-json',businesspath,'--scientific-evidence-json',evidencepath,'--output',resultpath)
            x=json.loads(Path(resultpath).read_text(encoding='utf-8'))
            self.assertEqual([r['status'] for r in x['results']], ['POINT','NEEDS_INPUT'])
            self.assertEqual(x['results'][0]['verification_level'],'CORE_REPLAY_VERIFIED')
            self.assertEqual(x['results'][1]['reason_code'],'A4_SCIENTIFIC_ADMISSION_REQUIRED')

    def test_d1_target_coordinate_tampering_blocked_before_any_theorem(self):
        packet=d1_arm_packet(self.case,self.reviewed).model_copy(update={'target_own_treatment':1})
        with self.assertRaisesRegex(ValueError,'scientific target fingerprint'):
            prepare_d1_arm_binding_v29(packet)

    def test_benchmark_public_gold_separation_preserved(self):
        base=ROOT/'assets/benchmark_assets'/'benchmarks'/'network_business_identification'
        self.assertTrue((base/'public'/'case_index.json').is_file())
        self.assertTrue((base/'gold'/'references'/'NBIB-001.json').is_file())
        self.assertTrue((base/'oracle'/'generator_worlds'/'NBIB-001.json').is_file())


if __name__=='__main__':
    unittest.main()
