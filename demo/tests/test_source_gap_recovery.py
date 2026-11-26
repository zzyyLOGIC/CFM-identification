from copy import deepcopy
import json
import pytest
from cfm_id import joint_natural_entry as entry
from cfm_id_llm import joint_reading as reader,source_gap_review as gaps
from test_joint_natural_entry import fixture,prepared as historical_prepared


def prepared(case,reading):
    from demo.tests.test_design_scope_audit import audit_fields
    report=historical_prepared(case,reading)
    report['joint_entry']['audit'].update(audit_fields(reading))
    return report


def gap_answer(case,candidate,questions,cause):
    return dict(binding=gaps.binding(case,candidate,questions),scientific_approval=False,
        findings=[dict(field=k,cause=cause,evidence=candidate['family']['evidence'],
            reason='Compare the actual supplied source, not an empty field.',
            question=None if cause in ('READING_OMISSION','INFORMATION_NOT_SUPPORTED') else '材料是否给出所有安排下的均值上下限？') for k in questions])


def test_gap_request_explicit_json_and_shared_field_meaning():
    case,s=fixture();req=gaps.request(case,s,{'design':{}},reading_contract='design is the historical assignment law, not future policy')
    assert 'JSON' in req['system_prompt']
    assert json.loads(req['user_prompt'])['reading_contract']=='design is the historical assignment law, not future policy'


def test_omitted_bounds_reread_without_asking_user_or_patching_values():
    case,full=fixture();bad=deepcopy(full);bad['bounds']['value'].update(by_node={},all_assignments=None)
    calls=[]
    def call(request,stage):
        calls.append(stage)
        if stage=='joint_source_read':return bad
        if stage=='joint_source_read_retry1':
            feedback=json.loads(request['user_prompt'])['reading_feedback_not_evidence']
            assert feedback['cause']=='READING_OMISSION'
            return full
        if stage.startswith('joint_source_audit'):
            return prepared(case,full if 'retry' in stage else bad)['joint_entry']['audit']
        assert stage=='joint_gap_review'
        body=json.loads(request['user_prompt'])
        return gap_answer(case,body['candidate'],body['gaps'],'READING_OMISSION')
    report=prepared(case,full)
    out=entry.prepare(case,report,call)
    assert out['joint_entry']['state']=='REVIEW_REQUIRED'
    assert out['clarification_questions']==[] and not out['backend_called']
    assert len(out['joint_entry']['attempts'])==2 and len(out['joint_entry']['gap_reviews'])==1
    assert out['joint_entry']['reading']['bounds']['value']['by_node']==full['bounds']['value']['by_node']


@pytest.mark.parametrize('cause',['MISSING_IN_SOURCE','EXPLICIT_UNKNOWN'])
def test_true_source_gap_asks_only_specific_reviewed_question(cause):
    case,s=fixture();s['bounds']['value'].update(by_node={},all_assignments=None)
    report=prepared(case,s)
    def call(request,stage):
        if stage=='joint_source_read':return s
        if stage=='joint_source_audit':return report['joint_entry']['audit']
        body=json.loads(request['user_prompt']);return gap_answer(case,body['candidate'],body['gaps'],cause)
    out=entry.prepare(case,report,call)
    assert out['joint_entry']['input_diagnostics'][0]['cause']==cause
    assert out['clarification_questions']==['材料是否给出所有安排下的均值上下限？']
    assert not out['backend_called']


def test_source_type_already_known_is_not_a_repeated_question():
    case,s=fixture();s['bounds']['value'].update(by_node={},all_assignments=None);report=prepared(case,s)
    def call(request,stage):
        if stage=='joint_source_read':return s
        if stage=='joint_source_audit':return report['joint_entry']['audit']
        body=json.loads(request['user_prompt']);return gap_answer(case,body['candidate'],body['gaps'],'INFORMATION_NOT_SUPPORTED')
    out=entry.prepare(case,report,call)
    assert out['joint_entry']['state']=='UNSUPPORTED' and not out['clarification_questions']
    assert not out['backend_called']
    assert 'Compare the actual supplied source' in out['joint_entry']['message']
    assert '不是该因果问题不可识别的证明' in out['joint_entry']['message']


def test_persistent_omission_stops_after_one_reread_without_user_question():
    case,s=fixture();s['bounds']['value'].update(by_node={},all_assignments=None);report=prepared(case,s);stages=[]
    def call(request,stage):
        stages.append(stage)
        if 'source_read' in stage:return s
        if 'source_audit' in stage:return report['joint_entry']['audit']
        body=json.loads(request['user_prompt']);return gap_answer(case,body['candidate'],body['gaps'],'READING_OMISSION')
    out=entry.prepare(case,report,call)
    assert out['joint_entry']['state']=='READING_RECHECK_REQUIRED'
    assert not out['clarification_questions'] and not out['backend_called']
    assert sum('source_read' in x for x in stages)==2


def test_gap_audit_rejects_stale_and_user_question_for_model_omission():
    case,s=fixture();q={'bounds':dict(candidate=s['bounds'])};r=gap_answer(case,s,q,'READING_OMISSION')
    r['binding']='stale'
    with pytest.raises(ValueError,match='STALE'):gaps.check(case,s,q,r)
    r=gap_answer(case,s,q,'READING_OMISSION');r['findings'][0]['question']='请补已经写过的内容'
    with pytest.raises(ValueError,match='MUST_NOT_ASK'):gaps.check(case,s,q,r)
