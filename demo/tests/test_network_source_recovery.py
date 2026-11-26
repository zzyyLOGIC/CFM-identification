"""Source recovery never substitutes a model judgment for scientific approval."""
from copy import deepcopy
import json

import pytest

from cfm_id import network_existing_entry as entry
from cfm_id_llm import network_existing_reading as reader
from cfm_id_llm.compact_study import digest
from cfm_id_llm.information_semantics import GUIDANCE
from demo.tests.test_network_existing_entry import fixture, prepared


def exercise(case, initial, repaired=None, cause='READING_OMISSION'):
    calls=[]
    def call(request, stage):
        calls.append(stage)
        body=json.loads(request['user_prompt'])
        if stage.startswith('joint_source_read'):
            return deepcopy(repaired if stage.endswith('retry1') and repaired is not None else initial)
        if stage.startswith('joint_source_audit'):
            return dict(binding=body['input_binding'],scientific_approval=False,
                findings=[dict(field=k,verdict='MATCH',evidence=v.get('evidence',[]),
                    reason='Deterministic source-audit fixture, not LLM evidence.',question=None)
                    for k,v in body['fields'].items()])
        assert stage.startswith('joint_gap_review')
        return dict(binding=body['binding'],scientific_approval=False,findings=[
            dict(field=k,cause=cause,evidence=initial['family']['evidence'],
                reason='Source-gap fixture; no scientific permission.',
                question='这项额外的平均结果顺序本次是否采用？' if cause=='EXPLICIT_UNKNOWN' else None)
            for k in body['gaps']])
    r=entry.prepare(case,dict(version='test',draft={},draft_sha256=digest({}),checks=[]),call)
    return r,calls


@pytest.mark.parametrize('status',['ADOPTED','UNKNOWN'])
def test_misfiled_declaration_requires_fresh_read_and_audit(status):
    case,correct=fixture();wrong=deepcopy(correct)
    wrong['remaining']=[dict(code='misfiled',statement='范围或事实说明被误列为条件',
        status=status,evidence=wrong['family']['evidence'])]
    before=deepcopy(wrong)
    r,calls=exercise(case,wrong,correct)
    assert wrong==before
    assert r['joint_entry']['state']=='REVIEW_REQUIRED'
    assert calls==['joint_source_read','joint_source_audit','joint_gap_review',
                   'joint_source_read_retry1','joint_source_audit_retry1']
    assert len(r['joint_entry']['attempts'])==2
    assert r['joint_entry']['attempts'][0]['reading']['remaining']==before['remaining']
    assert not r['backend_called'] and not r['scientific_approval']
    assert not r['estimation_handoff_allowed']


def test_true_extra_restriction_stays_blocked_after_gap_check():
    case,s=fixture()
    s['remaining']=[dict(code='individual',statement='每个对象在每份名单下都不能变差',
        status='ADOPTED',evidence=s['family']['evidence'])]
    r,calls=exercise(case,s,cause='DECLARATION_CONFIRMED')
    assert r['joint_entry']['state']=='UNSUPPORTED'
    assert r['joint_entry']['unhandled_declarations']==s['remaining']
    assert not r['clarification_questions'] and not r['backend_called']
    assert calls[-1]=='joint_gap_review' and len(calls)==3


def test_true_pending_restriction_remains_a_question():
    case,s=fixture()
    s['remaining']=[dict(code='order',statement='本次尚未决定是否采用额外平均结果顺序',
        status='UNDECIDED',evidence=s['family']['evidence'])]
    r,_=exercise(case,s,cause='EXPLICIT_UNKNOWN')
    assert r['joint_entry']['state']=='NEEDS_INPUT'
    assert r['clarification_questions']==['这项额外的平均结果顺序本次是否采用？']
    assert not r['backend_called'] and not r.get('condition_review')


def test_failed_reread_cannot_drop_restriction_or_loop_indefinitely():
    case,s=fixture()
    s['remaining']=[dict(code='extra',statement='未解决的声明',status='UNKNOWN',
        evidence=s['family']['evidence'])]
    r,calls=exercise(case,s)
    assert r['joint_entry']['state']=='READING_RECHECK_REQUIRED'
    assert calls.count('joint_source_read_retry1')==1
    assert not r['backend_called'] and not r['estimation_handoff_allowed']


def test_missing_design_and_unused_exposure_are_not_scientific_choices():
    case,s=fixture();s['design']=None
    r=prepared(case,s)
    assert r['joint_entry']['missing_fields']==['design']
    assert list(entry.gaps(r))==['design']
    assert r['clarification_questions']==['过去试点怎样抽签，概率或名额是多少？']
    assert not r['backend_called']


def test_information_guidance_reaches_both_stages_without_rewriting_values():
    case,s=fixture()
    assert GUIDANCE in reader.request(case)['system_prompt']
    assert GUIDANCE in json.loads(reader.audit_request(case,s)['user_prompt'])['reading_contract']
    bindings=[]
    for op in ['NODE_FULL_LAW','FULL_JOINT_LAW']:
        s['information']['value']['operator']=op
        s['information']['value']['assignment_cells']=[]
        raw=deepcopy(s);checked=reader.inspect(case,s)
        assert s==raw and checked['information']['value']['operator']==op
        bindings.append(reader.binding(case,checked))
    assert bindings[0]!=bindings[1]


@pytest.mark.parametrize('bad_kind',[False,True])
def test_bounds_diagnostic_identifies_actual_missing_attribute(bad_kind):
    from demo.tests.test_joint_natural_entry import fixture as joint_fixture,prepared as joint_prepared
    from cfm_id.joint_natural_entry import proposed_gaps
    case,s=joint_fixture()
    if bad_kind:s['bounds']['value']['kind']='UNKNOWN'
    else:s['bounds']['value']['by_node']={}
    before=deepcopy(s)
    r=joint_prepared(case,s)
    question=' '.join(r['clarification_questions'])
    assert r['joint_entry']['reason_code']=='BOUND_SCOPE_REQUIRED'
    assert not r['backend_called'] and s==before
    assert ('条件平均结果' in question)==bad_kind
    if not bad_kind:assert '甲' in question and '乙' in question and '下限和上限' in question
    assert proposed_gaps(r)['bounds']['proposed_questions']==r['clarification_questions']


@pytest.mark.parametrize('network,original_state,network_target,recover',[
    (True,'UNSUPPORTED','FIXED_POLICY_LEVEL',True),
    (True,'UNSUPPORTED','OTHER',False),
    (False,'UNSUPPORTED','FIXED_POLICY_LEVEL',False),
    (True,'REVIEW_REQUIRED','FIXED_POLICY_LEVEL',False),
])
def test_symbolic_hint_cannot_trap_imported_network_or_bypass_extra_limits(
        monkeypatch,network,original_state,network_target,recover):
    from cfm_id import project,joint_natural_entry,symbolic_mean_entry
    from demo.tests.test_observational_reader_selection import source_scope
    case=dict(case_id='route-test',business_question='Original complete-policy mean question.',sources=[])
    draft=dict(verification_route='SYMBOLIC_MEAN_JOINT')
    stopped=dict(state=original_state,reason_code='ADDITIONAL_RESTRICTIONS_NOT_EXPRESSED'
        if original_state=='UNSUPPORTED' else None,problem={'additional_restrictions':['source declaration']})
    monkeypatch.setattr('cfm_id.direct_verification.verify',lambda *a,**k:dict(draft=deepcopy(draft)))
    monkeypatch.setattr(symbolic_mean_entry,'prepare',lambda c,r,call:dict(r,joint_entry=deepcopy(stopped)))
    seen=[]
    def fresh(c,r,call):
        assert c==case and r['draft']==draft and 'joint_entry' not in r
        seen.append('fresh_source_read_and_audit')
        # The source-selected network reader can still reject a true extra
        # restriction; route recovery must not force execution or POINT.
        return dict(r,joint_entry=dict(state='UNSUPPORTED',reason_code='TRUE_EXTRA_LIMIT'),backend_called=False)
    monkeypatch.setattr(joint_natural_entry,'prepare',fresh)
    def call(req,stage):
        if stage=='direct_draft':return deepcopy(draft)
        assert stage=='network_source_route'
        body=json.loads(req['user_prompt']);assert 'draft' not in body
        return source_scope(case,network_target,'RANDOMIZED')
    out=project.direct_then_verify(case,call,network={'imported':True} if network else None,population_ate=True)
    assert out['draft']==draft and bool(seen)==recover
    assert not out.get('scientific_approval') and not out.get('estimation_handoff_allowed')
    if recover:
        assert out['joint_entry']['reason_code']=='TRUE_EXTRA_LIMIT'
        assert out['reader_selection']['previous_symbolic_entry']==stopped
        assert not out['backend_called']
    else:assert out['joint_entry']==stopped
