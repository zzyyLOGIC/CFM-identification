"""A successful source audit cannot silently turn a reading error into a limit."""
from copy import deepcopy
import json
import pytest
from cfm_id import observational_effect_entry as entry
from cfm_id_llm import observational_effect_source as reader, source_gap_review as gap
from cfm_id_llm.compact_study import digest
from test_observational_effect_entry import fixture
from test_observational_contract_recovery import audit


@pytest.mark.parametrize('defect',['extra','refusal'])
@pytest.mark.parametrize('cause',['READING_OMISSION','DECLARATION_CONFIRMED','EXPLICIT_UNKNOWN'])
def test_stopping_declarations_checked_without_automatic_value_changes(defect,cause):
    case,good=fixture('observed');bad=deepcopy(good)
    if defect=='extra':
        bad['additional_restrictions']=[dict(text='原文中的条件声明',source_ids=good['study']['source_ids'])]
    else:bad['assumptions']['full_vector_conditional_exchangeability']['value']=False
    original=deepcopy(bad);stages=[];current=bad
    def call(request,stage):
        nonlocal current
        stages.append(stage)
        if stage=='joint_source_read':return bad
        if stage=='joint_source_read_retry1':
            assert 'READING_OMISSION' in str(json.loads(request['user_prompt'])['reading_feedback_not_evidence'])
            current=good;return good
        if stage.startswith('joint_source_audit'):return audit(case,current)
        if stage.startswith('joint_condition_semantics'):
            # Deliberately simulate agreement here: this test exercises the
            # later stop-diagnosis gate even if both earlier readers miss it.
            from test_observational_condition_evidence import mocked_inventory
            inventory=mocked_inventory(case,current)
            if defect=='extra':
                # Keep this test focused on the later stop review: the source
                # inventory also reports a distinct restriction in the same
                # broad fixture paragraph, not solely known basic premises.
                inventory['statements'].append(dict(inventory['statements'][0],
                    kind='OTHER',conditioning='OTHER',explanation='separate restriction mock',
                    evidence=reader.fields(case,reader.inspect(case,current))['facts.study']['evidence']))
            return inventory
        assert stage=='joint_gap_review'
        body=json.loads(request['user_prompt']);gaps=body['gaps']
        assert all(x['declaration_stop'] for x in gaps.values())
        evidence=next(v['evidence'] for v in reader.fields(case,reader.inspect(case,bad)).values() if v.get('evidence'))
        return dict(binding=gap.binding(case,body['candidate'],gaps),scientific_approval=False,
            findings=[dict(field=k,cause=cause,evidence=evidence,reason='核对停止所用的原文声明',
                question='这项条件本次是否采用？' if cause=='EXPLICIT_UNKNOWN' else None) for k in gaps])
    out=entry.prepare(case,dict(draft={},draft_sha256=digest({}),checks=[]),call)
    assert bad==original and not out['backend_called'] and not out['independent_replay']
    if cause=='READING_OMISSION':
        assert out['joint_entry']['state']=='REVIEW_REQUIRED'
        assert out['joint_entry']['reading']['wire']==good
        assert stages.count('joint_source_read_retry1')==1 and 'joint_source_audit_retry1' in stages
    elif cause=='DECLARATION_CONFIRMED':
        assert out['joint_entry']['state']=='UNSUPPORTED' and not out['clarification_questions']
        assert out['joint_entry']['reading']['wire']==bad and 'condition_review' not in out
    else:
        assert out['joint_entry']['state']=='NEEDS_INPUT'
        assert out['clarification_questions']==['这项条件本次是否采用？']
        assert 'condition_review' not in out


def test_stop_confirmation_is_not_a_general_gap_approval():
    case,wire=fixture('observed');s=reader.inspect(case,wire);gaps={'facts':{}}
    raw=dict(binding=gap.binding(case,s,gaps),scientific_approval=False,findings=[
        dict(field='facts',cause='DECLARATION_CONFIRMED',evidence=[],reason='unsupported',question=None)])
    with pytest.raises(ValueError,match='SOURCE_DECLARATION_STOP_REQUIRED'):gap.check(case,s,gaps,raw)
    schema=json.loads(gap.request(case,s,gaps)['user_prompt'])['output_schema']
    assert 'DECLARATION_CONFIRMED' not in schema['$defs']['Finding']['properties']['cause']['enum']
    gaps['facts']['declaration_stop']=True
    schema=json.loads(gap.request(case,s,gaps)['user_prompt'])['output_schema']
    assert 'DECLARATION_CONFIRMED' in schema['$defs']['Finding']['properties']['cause']['enum']


def test_crosscheck_uses_required_coverage_without_breaking_saved_audits():
    case,wire=fixture('observed');s=reader.inspect(case,wire)
    fields=reader.fields(case,s)
    assert fields['coverage']['scientific_declarations_crosscheck']['assumptions']==s['facts']['assumptions']
    assert 'scientific_declarations_crosscheck' not in fields
    a=audit(case,wire);reader.check_audit(case,s,a)
    a['findings']=[x for x in a['findings'] if x['field']!='coverage']
    with pytest.raises(ValueError,match='AUDIT_COVERAGE'):reader.check_audit(case,s,a)


@pytest.mark.parametrize('genuine',[False,True])
def test_empty_method_note_review_is_diagnosed_before_science(genuine):
    from test_observational_condition_evidence import mocked_inventory
    case,good=fixture('observed');bad=deepcopy(good)
    bad['unresolved']=[dict(source_ids=good['study']['source_ids'],text='模型记录的一条未解决说明')]
    current=bad;calls=[]
    def call(req,stage):
        nonlocal current
        calls.append(stage)
        if stage=='joint_source_read':return bad
        if stage=='joint_source_read_retry1':current=good;return good
        if stage.startswith('joint_source_audit'):return audit(case,current)
        if stage.startswith('joint_condition_semantics'):return mocked_inventory(case,current)
        assert stage=='joint_gap_review'
        body=json.loads(req['user_prompt']);gaps=body['gaps'];assert list(gaps)==['facts.unresolved']
        ev=reader.fields(case,reader.inspect(case,bad))['facts.unresolved.0']['evidence']
        return dict(binding=gap.binding(case,body['candidate'],gaps),scientific_approval=False,findings=[dict(
            field='facts.unresolved',cause='SOURCE_CONFLICT' if genuine else 'READING_OMISSION',evidence=ev,
            reason='原文存在冲突' if genuine else '已经表达的状态重复到未解决说明',question='请说明这两处冲突采用哪一项？' if genuine else None)])
    result=entry.prepare(case,dict(draft={},draft_sha256=digest({}),checks=[]),call)
    assert not result['backend_called']
    if genuine:
        assert result['joint_entry']['state']=='NEEDS_INPUT' and len(result['clarification_questions'])==1
        assert 'joint_source_read_retry1' not in calls and 'condition_review' not in result
    else:
        assert result['joint_entry']['state']=='REVIEW_REQUIRED' and not result['clarification_questions']
        assert calls.count('joint_source_read_retry1')==1 and result['joint_entry']['reading']['wire']==good
