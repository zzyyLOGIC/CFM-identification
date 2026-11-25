"""Planner contradictions enter the same bounded, fully audited source reread."""
from copy import deepcopy
import json
import pytest
from cfm_id import observational_effect_entry as entry
from cfm_id_llm import observational_effect_source as reader
from cfm_id_llm.compact_study import digest
from test_observational_effect_entry import fixture


def audit(case,wire):
    s=reader.inspect(case,wire)
    return dict(binding=reader.binding(case,s),scientific_approval=False,
        findings=[dict(field=k,verdict='MATCH',evidence=v.get('evidence',[]),
            reason='Simulate a missed contradiction in source review',question=None)
            for k,v in reader.fields(case,s).items()])


@pytest.mark.parametrize('persistent',[False,True])
def test_source_schema_repair_has_separate_bounded_budget(persistent):
    from test_observational_condition_evidence import mocked_inventory
    case,good=fixture('observed');bad=deepcopy(good)
    bad['assumptions']['full_vector_conditional_exchangeability']['approved_by_model']=True
    stages=[]
    def call(req,stage):
        stages.append(stage)
        if stage.startswith('joint_source_read'):return bad
        if stage=='joint_source_format_retry':
            assert 'extra_forbidden' in req['user_prompt']
            return bad if persistent else good
        if stage.startswith('joint_source_audit'):return audit(case,good)
        if stage.startswith('joint_condition_semantics'):return mocked_inventory(case,good)
        pytest.fail(stage)
    r=entry.prepare(case,dict(draft={},draft_sha256=digest({}),checks=[]),call)
    assert stages.count('joint_source_format_retry')==1
    assert not r['backend_called'] and not r['clarification_questions']
    assert r['joint_entry']['state']==('READING_RECHECK_REQUIRED' if persistent else 'REVIEW_REQUIRED')
    assert len(r['joint_entry']['reading_repairs'])==1
    if not persistent:assert r['joint_entry']['reading']['wire']==good


@pytest.mark.parametrize('persistent',[False,True])
@pytest.mark.parametrize('defect',['effect_kind','feature_profile'])
def test_native_contract_error_is_reread_once_without_autocorrection(defect,persistent):
    case,wire=fixture('nodewise' if defect=='feature_profile' else 'observed')
    bad=deepcopy(wire)
    if defect=='effect_kind':
        bad['target']['kind']='SPILLOVER_EFFECT' if wire['target']['kind']=='DIRECT_EFFECT' else 'DIRECT_EFFECT'
        code='LOCAL_EFFECT_KIND_COORDINATES_MISMATCH'
    else:
        bad['information'][0]['profiles'][0]['features'].pop(wire['study']['nodes'][-1])
        code='COMPLETE_BINARY_FEATURE_PROFILE_REQUIRED'
    original=deepcopy(bad);stages=[];submitted=bad
    def call(request,stage):
        nonlocal submitted
        stages.append(stage)
        if stage=='joint_source_read':return bad
        if stage=='joint_source_read_retry1':
            assert code in str(json.loads(request['user_prompt'])['reading_feedback_not_evidence'])
            submitted=bad if persistent else wire
            return submitted
        if stage.startswith('joint_condition_semantics'):
            from test_observational_condition_evidence import mocked_inventory
            return mocked_inventory(case,submitted)
        assert stage.startswith('joint_source_audit')
        return audit(case,submitted)
    report=dict(draft={},draft_sha256=digest({}),checks=[])
    result=entry.prepare(case,report,call)
    assert bad==original and not result['backend_called'] and not result['independent_replay']
    assert stages==['joint_source_read','joint_source_audit','joint_condition_semantics',
        'joint_source_read_retry1','joint_source_audit_retry1','joint_condition_semantics_retry1']
    attempts=result['joint_entry']['attempts']
    assert sum('audit' in x for x in attempts)==2
    assert sum('error' in x for x in attempts)==(2 if persistent else 1)
    if persistent:
        assert result['joint_entry']['state']=='READING_RECHECK_REQUIRED'
        assert result['clarification_questions']==[] and 'condition_review' not in result
        assert code in result['joint_entry']['failure_details'][0]['reason']
    else:
        assert result['joint_entry']['state']=='REVIEW_REQUIRED'
        assert result['joint_entry']['reading']['wire']==wire
        assert 'condition_review' in result
