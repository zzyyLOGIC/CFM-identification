"""A route hint cannot erase the explicit comparison before source reading."""
from copy import deepcopy
import pytest
from cfm_id import project,observational_effect_entry as effect,network_existing_entry as policy
from cfm_id_llm import network_source_route as route


def source_scope(case,target='LOCAL_CONTRAST',assignment='SELF_SELECTED'):
    evidence=[dict(source_id='question',quote=case['business_question'])]
    return dict(binding=route.binding(case),scientific_approval=False,
        single_question=dict(value=True,evidence=evidence),target=dict(value=target,evidence=evidence),
        assignment=dict(value=assignment,evidence=evidence),mean_constraints=dict(value='NOT_STATED',evidence=[]))


@pytest.mark.parametrize('nested',[False,True])
def test_policy_hint_comparison_reaches_source_reader_without_reusing_answer(monkeypatch,nested):
    draft={'answers':[{'verification_route':'NETWORK_OBSERVATIONAL_POLICY','functional':'wrong draft formula',
        **({'target':{'quantity':'difference'}} if nested else {'quantity':'difference'})}]}
    before=deepcopy(draft);case={'case_id':'test','business_question':'original question','sources':[]}
    trace=[]
    monkeypatch.setattr('cfm_id.direct_verification.verify',lambda *a,**k:dict(draft=draft,decision='WITHHELD'))
    monkeypatch.setattr('cfm_id_llm.direct_answer.network_request',lambda *a,**k:{'source':'original'})
    def prepare(original,report,call):
        assert original==case and report['draft']==before
        trace.append('fresh_source_reader')
        # A reader may still reject a complete-policy contrast. Routing does
        # not award POINT or change the mathematical scope.
        return dict(report,joint_entry={'state':'UNSUPPORTED','reason_code':'TARGET_NOT_LOCAL'})
    monkeypatch.setattr(effect,'prepare',prepare)
    monkeypatch.setattr(policy,'prepare',lambda *a,**k:pytest.fail('comparison was sent to mean-only reader'))
    out=project.direct_then_verify(case,lambda req,stage:source_scope(case) if stage=='network_source_route' else draft,population_ate=True)
    assert trace==['fresh_source_reader'] and draft==before
    assert out['joint_entry']['state']=='UNSUPPORTED'
    assert out['reader_selection']['scientific_approval'] is False


def test_policy_mean_and_multiple_questions_are_not_recast_as_single_effect():
    mean={'verification_route':'NETWORK_OBSERVATIONAL_POLICY','quantity':'mean'}
    difference={'verification_route':'NETWORK_OBSERVATIONAL_POLICY','quantity':'difference'}
    assert effect.reader_selection({'answers':[mean]}) is None
    assert effect.reader_selection({'answers':[mean,difference]}) is None
    assert effect.reader_selection({'answers':[dict(difference,verification_route='NETWORK_FINITE_POLICY')]}) is None


@pytest.mark.parametrize('hint',['NETWORK_JOINT_MEANS','NETWORK_FINITE_POLICY','NETWORK_OBSERVATIONAL_POLICY',None,'OTHER'])
def test_wrong_hint_is_overridden_by_original_scope(monkeypatch,hint):
    case=dict(case_id='test',business_question='Self-selected treatment; compare local peer states.',sources=[])
    draft=dict(verification_route=hint) if hint else {}
    monkeypatch.setattr('cfm_id.direct_verification.verify',lambda *a,**k:dict(draft=draft))
    seen=[]
    def prepare(case,report,call):
        import json
        call(dict(system_prompt='audit',user_prompt=json.dumps(dict(fields={'coverage':{}}))),'joint_source_audit')
        return dict(report,joint_entry={'state':'REVIEW_REQUIRED'})
    def call(req,stage):
        import json
        if stage=='direct_draft':return draft
        if stage=='network_source_route':
            assert 'draft' not in json.loads(req['user_prompt'])
            return source_scope(case)
        body=json.loads(req['user_prompt']);seen.append(body['fields']['coverage']['reader_scope_to_verify'])
    monkeypatch.setattr(effect,'prepare',prepare)
    out=project.direct_then_verify(case,call,population_ate=True,network={'imported':True})
    assert seen and out['reader_selection']['reader']=='NETWORK_OBSERVATIONAL_EFFECTS'
    assert out['draft']==draft


def test_randomized_local_keeps_native_verdict_and_no_finite_questions(monkeypatch):
    case=dict(case_id='test',business_question='randomized local contrast',sources=[])
    draft=dict(verification_route='NETWORK_JOINT_MEANS');report=dict(draft=draft,decision='WITHHELD')
    monkeypatch.setattr('cfm_id.direct_verification.verify',lambda *a,**k:report)
    out=project.direct_then_verify(case,lambda req,stage:draft if stage=='direct_draft' else source_scope(case,assignment='RANDOMIZED'),population_ate=True)
    assert out['decision']=='WITHHELD' and not out.get('clarification_questions')
    assert out['reader_selection']['reader']=='DIRECT_NETWORK_VERIFICATION'


def test_finite_model_without_extra_relations_is_still_routable():
    c=dict(case_id='test',business_question='complete randomized policy',sources=[])
    s=route.check(c,source_scope(c,'FIXED_POLICY_CONTRAST','RANDOMIZED'))
    assert route.select(s)=='NETWORK_JOINT_MEANS'


@pytest.mark.parametrize('corrected',[True,False])
def test_source_route_disagreement_recovers_once_without_changing_question(monkeypatch,corrected):
    case=dict(case_id='test',business_question='Original local peer comparison.',sources=[])
    draft=dict(verification_route='NETWORK_OBSERVATIONAL_EFFECTS');calls=[]
    monkeypatch.setattr('cfm_id.direct_verification.verify',lambda *a,**k:dict(draft=draft,checks=[]))
    rejected=dict(state='READING_RECHECK_REQUIRED',attempts=[dict(audit=dict(findings=[dict(
        field='coverage',verdict='READING_ERROR',reason='The original target is local, not a full-policy mixture.')]))])
    monkeypatch.setattr(policy,'prepare',lambda original,report,call:dict(report,joint_entry=deepcopy(rejected)))
    def prepare(original,report,call):
        assert original==case and report['draft']==draft
        import json
        call(dict(system_prompt='read original',user_prompt=json.dumps({})),'joint_source_read')
        return dict(report,joint_entry={'state':'REVIEW_REQUIRED'})
    monkeypatch.setattr(effect,'prepare',prepare)
    def call(req,stage):
        calls.append(stage)
        if stage=='direct_draft':return draft
        if stage=='network_source_route':return source_scope(case,'FINITE_POLICY_MIXTURE_CONTRAST')
        if stage=='network_source_route_recovery':
            assert 'Original local peer comparison.' in req['user_prompt']
            return source_scope(case,'LOCAL_CONTRAST' if corrected else 'FINITE_POLICY_MIXTURE_CONTRAST')
    out=project.direct_then_verify(case,call,population_ate=True)
    assert calls.count('network_source_route_recovery')==1
    assert out['joint_entry']['state']==('REVIEW_REQUIRED' if corrected else 'READING_RECHECK_REQUIRED')
    assert ('joint_source_read_rerouted' in calls)==corrected
    assert out['draft']==draft and not out.get('estimation_handoff_allowed')
    assert out['reader_selection']['recovery']['previous_attempts']==rejected['attempts']


@pytest.mark.parametrize('corrected',[True,False])
def test_same_reader_scope_correction_gets_fresh_audit_once(monkeypatch,corrected):
    import json
    from cfm_id import local_bundle_entry
    case=dict(case_id='scope-recovery',business_question='One weighted contrast for two sites.',sources=[])
    draft=dict(verification_route='NETWORK_LOCAL_BUNDLE'); calls=[]; seen=[]
    monkeypatch.setattr('cfm_id.direct_verification.verify',lambda *a,**k:dict(draft=draft,checks=[]))
    rejected=dict(state='READING_RECHECK_REQUIRED',attempts=[dict(audit=dict(findings=[dict(
        field='coverage',verdict='READING_ERROR',reason='Two sites are not two questions.')]))])
    def prepare(original,report,call):
        assert original==case
        call(dict(system_prompt='audit',user_prompt=json.dumps(dict(fields={'coverage':{}}))),'joint_source_audit')
        return dict(report,joint_entry=deepcopy(rejected) if len(seen)==1 else dict(state='REVIEW_REQUIRED'))
    monkeypatch.setattr(local_bundle_entry,'prepare',prepare)
    def call(req,stage):
        calls.append(stage)
        if stage=='direct_draft':return draft
        if stage.startswith('network_source_route'):
            s=source_scope(case,assignment='RANDOMIZED')
            s['local_scope']=dict(value='SCOPED_OR_MULTIPLE',evidence=s['target']['evidence'])
            s['single_question']['value']=bool(corrected and stage.endswith('recovery'))
            return s
        seen.append(json.loads(req['user_prompt'])['reader_scope_to_verify']['single_question']['value'])
    out=project.direct_then_verify(case,call,population_ate=True)
    assert seen==([False,True] if corrected else [False])
    assert calls.count('network_source_route_recovery')==1
    assert out['joint_entry']['state']==('REVIEW_REQUIRED' if corrected else 'READING_RECHECK_REQUIRED')
    assert out['reader_selection']['reader']=='NETWORK_LOCAL_BUNDLE'
    assert not out.get('backend_called') and not out.get('estimation_handoff_allowed')
