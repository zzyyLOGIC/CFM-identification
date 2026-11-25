"""Source diagnosis must not turn unsupported, adopted conditions into questions."""
from copy import deepcopy
import json
import pytest
from cfm_id import symbolic_mean_entry as entry, joint_natural_entry as workflow
from cfm_id_llm import symbolic_mean_reading as reader
from cfm_id_llm.compact_study import digest


def fixture(status='ADOPTED'):
    text='两店成功率均值为p，0到1。完整模型另采用两店成功率乘积为1/5。'
    case=dict(case_id='unit',business_question=text,sources=[],response_language='zh')
    aff=lambda c='0',**co:dict(constant=c,coefficients=co)
    p=dict(version='symbolic-mean-joint-1',model='FINITE_MEANS_AFFINE_PARAMETERS',outcome_domain='BINARY',
        context='本月两店新方案',target_description='甲店成功概率的范围',target={'a':'1'},target_offset=aff(),
        parameters=[dict(id='p',description='两店成功率等权均值',lower='0',upper='1',source_ids=['question#L1'])],
        coordinates=[dict(id=k,description=k+'店成功概率',lower=aff(),upper=aff('1'),known=None,source_ids=['question#L1']) for k in ('a','b')],
        constraints=[dict(id='average',coefficients={'a':'1/2','b':'1/2'},relation='EQ',rhs=aff(p='1'),adoption='ADOPTED',source_ids=['question#L1'])],
        information='POPULATION_MEANS',model_complete=True,unresolved=[],additional_restrictions=[dict(
            code='product',statement='两店成功概率乘积为1/5',status=status,evidence=[dict(source_id='question#L1')])])
    return case,dict(version='symbolic-source-reading/2',binding=digest(case),scientific_approval=False,problem=p)


def audit(case,s,changes=None):
    a=dict(binding=reader.binding(case,s),scientific_approval=False,findings=[
        dict(field=k,verdict='MATCH',evidence=v.get('evidence',[]),reason='source audit fixture',question=None)
        for k,v in reader.fields(case,s).items()])
    for f in a['findings']:
        if f['field'] in (changes or {}):f.update(changes[f['field']])
    return a


def report():return dict(draft={},draft_sha256=digest({}),checks=[])


def test_adopted_stop_precedes_unrelated_completeness_question_without_approval():
    case,wire=fixture();wire['problem']['model_complete']=None
    s=reader.inspect(case,wire);a=audit(case,s,{'coverage':dict(verdict='NEEDS_CLARIFICATION',question='完整模型是否含乘积条件？')})
    stages=[]
    def call(req,stage):
        stages.append(stage)
        return wire if stage=='joint_source_read' else a
    r=entry.prepare(case,report(),call)
    assert stages==['joint_source_read','joint_source_audit']
    assert r['joint_entry']['state']=='UNSUPPORTED' and not r['clarification_questions']
    assert '乘积为1/5' in r['joint_entry']['message']
    assert r['joint_entry']['deferred_questions']==[a['findings'][1]]
    assert r['joint_entry']['audit']==reader.check_audit(case,s,a)
    assert not r['backend_called'] and not r['estimation_handoff_allowed'] and not r.get('proof')
    assert not r.get('condition_review')


@pytest.mark.parametrize('status,expected',[('ADOPTED','UNSUPPORTED'),('NOT_ADOPTED','REVIEW_REQUIRED'),
    ('UNDECIDED','NEEDS_INPUT'),('UNKNOWN','NEEDS_INPUT'),('CONTRADICTED','NEEDS_INPUT')])
def test_adoption_states_preserved_separately(status,expected):
    case,wire=fixture(status);s=reader.inspect(case,wire);a=audit(case,s)
    r=entry.plan(case,workflow.base(report(),case,s,a))
    assert r['joint_entry']['state']==expected and not r['backend_called']
    assert s['wire']['problem']['additional_restrictions'][0]['status']==status
    assert bool(s['problem']['additional_restrictions'])==(status=='ADOPTED')
    assert bool(r['clarification_questions'])==(expected=='NEEDS_INPUT')
    if expected=='NEEDS_INPUT':assert '乘积为1/5' in r['clarification_questions'][0]


@pytest.mark.parametrize('status',['ADOPTED','NOT_ADOPTED','UNDECIDED','CONTRADICTED'])
def test_whole_source_audit_keeps_same_declarations_as_individual_fields(status):
    case,wire=fixture(status);s=reader.inspect(case,wire)
    payload=json.loads(reader.audit_request(case,s)['user_prompt'])
    fields=payload['fields'];whole=fields['coverage']['candidate']['additional_restrictions'][0]
    assert whole==fields['additional_restrictions.0']['value']
    assert whole['status']==status and whole['evidence']
    # In particular, the mathematical omission of a declined condition is not
    # presented as a source-reading omission to the independent auditor.
    assert fields['coverage']['candidate']==s['wire']['problem']


def test_reading_error_is_reread_before_any_diagnostic_stop():
    case,wire=fixture();stages=[]
    def call(req,stage):
        stages.append(stage)
        if stage.startswith('joint_source_read'):return wire
        s=reader.inspect(case,wire)
        return audit(case,s,{'additional_restrictions.0':dict(verdict='READING_ERROR',question=None)})
    r=entry.prepare(case,report(),call)
    assert r['joint_entry']['state']=='READING_RECHECK_REQUIRED'
    assert sum(x.startswith('joint_source_read') for x in stages)==2
    assert not r['clarification_questions'] and not r['backend_called']


def test_ambiguous_restriction_itself_cannot_become_unsupported_stop():
    case,wire=fixture();s=reader.inspect(case,wire)
    a=audit(case,s,{'additional_restrictions.0':dict(verdict='NEEDS_CLARIFICATION',question='乘积条件采用与否前后不一致，哪一个适用？')})
    assert entry.unsupported_stop(case,workflow.base(report(),case,s,a)) is None


def test_old_saved_binding_unchanged_but_new_request_requires_declarations():
    case,wire=fixture();wire.pop('version');wire['problem']['additional_restrictions']=[]
    s=reader.inspect(case,wire)
    assert s['wire']==wire and reader.inspect(case,s)==s
    reader.check_audit(case,s,audit(case,s))
    with pytest.raises(ValueError,match='V2_REQUIRED'):reader.inspect_current(case,wire)
    schema=json.loads(reader.request(case)['user_prompt'])['output_schema']
    assert 'version' in schema['required']


def test_citations_and_complete_audit_still_mandatory():
    case,wire=fixture();wire['problem']['additional_restrictions'][0]['evidence']=[]
    with pytest.raises(ValueError,match='SOURCE_REQUIRED'):reader.inspect(case,wire)
    case,wire=fixture();s=reader.inspect(case,wire);a=audit(case,s);a['findings'].pop()
    with pytest.raises(ValueError,match='COVERAGE'):entry.unsupported_stop(case,workflow.base(report(),case,s,a))


def test_declined_condition_keeps_original_mathematical_result_and_replay():
    case,wire=fixture('NOT_ADOPTED');s=reader.inspect(case,wire)
    r=entry.plan(case,workflow.base(report(),case,s,audit(case,s)))
    sheet=r['condition_review'];review=dict(binding=sheet['binding'],authority='SYNTHETIC_TEST',
        decisions={x['code']:'ADOPTED' for x in sheet['items']})
    result=entry.complete(case,r,review)
    assert result['independent_replay'] and workflow.replay(case,result['draft'],result)
    from cfm_id.symbolic_mean_joint import evaluate
    c=result['joint_entry']['native_result']['certificate']
    assert evaluate(c,s['problem'],{'p':'1/4'})['upper']=='1/2'
