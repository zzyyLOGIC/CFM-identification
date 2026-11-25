from copy import deepcopy
import pytest
from cfm_id import iv_natural_entry as entry,joint_natural_entry as workflow,joint_query_exchange as exchange
from cfm_id_llm import iv_source_reading as reader
from cfm_id_llm.compact_study import digest

def fixture(kind='LATE'):
    text='适配器单元样例：总体、时期、三项二元编码、八格总体表和全部采用条件。'
    case=dict(case_id='iv-source-test',business_question='培训参加的效果',sources=[dict(source_id='s',kind='OTHER',text=text)])
    ev=[dict(source_id='s',quote=text)];claim=lambda v:dict(value=v,evidence=ev)
    rows=[('1','0','0','0'),('3/4','0','1/8','1/8')]
    s=dict(family=claim('BINARY_IV'),study=claim(dict(population='本次参加研究的居民',period='半年后',context='同一批试点居民',instrument='收到培训邀请',treatment='实际参加培训',outcome='半年后是否就业',binary_coding={k:'1为是，0为否' for k in ('instrument','treatment','outcome')})),
        target=claim(dict(description='参加减未参加的就业概率差',kind=kind,treated=1,reference=0)),
        information=claim(dict(kind='EXACT_POPULATION_CONDITIONAL_LAW',cells=[dict(z=z,d=d,y=y,probability=rows[z][2*d+y]) for z in range(2) for d in range(2) for y in range(2)],complete=True,same_scope=True)),
        conditions=[dict(code=k,statement=k,status='ADOPTED',evidence=ev) for k in entry.LABELS],remaining=[],material_notes=[])
    return case,s

def prepared(case,s):
    s=reader.inspect(case,s);a=dict(binding=reader.binding(case,s),scientific_approval=False,
        findings=[dict(field=k,verdict='MATCH',reason='unit test fixture',question=None,evidence=v.get('evidence',[])) for k,v in reader.fields(s).items()])
    reader.check_audit(case,s,a)
    return entry.plan(case,workflow.base(dict(draft={},draft_sha256=digest({}),checks=[]),case,s,a))

def finish(case,s):
    r=prepared(case,s);sheet=r['condition_review']
    return entry.complete(case,r,dict(binding=sheet['binding'],authority='SYNTHETIC_TEST',decisions={i['code']:'ADOPTED' for i in sheet['items']}))

@pytest.mark.parametrize('kind,state,value',[('LATE','POINT','1/2'),('ATE','PARTIAL',['1/8','7/8'])])
def test_reuse_original_iv_solver_and_replay(kind,state,value):
    case,s=fixture(kind);out=finish(case,s)
    assert out['joint_entry']['state']==state and out['independent_replay']
    assert out['joint_entry']['native_result']['certificate']['answer']['value']==value
    assert workflow.replay(case,out['draft'],out)
    packet=exchange.packet(case,out);receipt=exchange.check_packet(case['case_id'],packet)
    assert receipt['mode']=='REGISTER_CERTIFIED_FUNCTIONAL' and receipt['query_count']==0
    changed=deepcopy(out);changed['joint_entry']['reading']['information']['value']['cells'][0]['probability']='1/2'
    assert not workflow.replay(case,out['draft'],changed)

def test_reverse_difference_keeps_requested_orientation():
    case,s=fixture('ATE');s['target']['value'].update(treated=0,reference=1)
    assert finish(case,s)['joint_entry']['native_result']['certificate']['answer']['value']==['-7/8','-1/8']

@pytest.mark.parametrize('code',['exclusion_restriction','instrument_independence','monotonicity_direction','no_interference'])
def test_declined_required_condition_stops_without_adoption(code):
    case,s=fixture();next(c for c in s['conditions'] if c['code']==code)['status']='NOT_ADOPTED'
    out=prepared(case,s)
    assert out['joint_entry']['state']=='UNSUPPORTED' and not out['clarification_questions'] and not out['backend_called']

def test_unknown_condition_asks_but_extra_condition_blocks():
    case,s=fixture();s['conditions'][1]['status']='UNKNOWN'
    out=prepared(case,s);assert out['joint_entry']['state']=='NEEDS_INPUT' and out['clarification_questions']
    s['conditions'][1]['status']='ADOPTED';s['remaining']=[dict(code='response_monotone',statement='培训对每个人都不降低就业结果',status='ADOPTED',evidence=s['family']['evidence'])]
    out=prepared(case,s);assert out['joint_entry']['reason_code']=='IV_ADDITIONAL_RESTRICTION_NOT_CONNECTED' and not out['backend_called']

def test_sample_is_not_converted_to_population_and_missing_cell_not_zero_filled():
    case,s=fixture();s['information']['value']['kind']='FINITE_SAMPLE'
    assert prepared(case,s)['joint_entry']['reason_code']=='IV_SAMPLE_CONTRACT_NOT_CONNECTED'
    s['information']['value']['kind']='EXACT_POPULATION_CONDITIONAL_LAW';s['information']['value']['cells'].pop()
    out=prepared(case,s);assert out['joint_entry']['state']=='NEEDS_INPUT' and not out['backend_called']

def test_pending_or_declined_current_review_never_executes():
    case,s=fixture();r=prepared(case,s);sheet=r['condition_review']
    decisions={i['code']:'ADOPTED' for i in sheet['items']};decisions['exclusion_restriction']='UNSURE'
    out=entry.complete(case,r,dict(binding=sheet['binding'],authority='SYNTHETIC_TEST',decisions=decisions))
    assert not out['backend_called'] and not out['independent_replay']

def test_default_route_uses_source_reader_and_retains_original_answer(monkeypatch):
    from cfm_id import project
    case,s=fixture();draft=dict(verification_route='BINARY_IV',answer='model answer kept')
    monkeypatch.setattr('cfm_id.direct_verification.verify',lambda *a,**k:dict(draft=draft,decision='RETAINED'))
    monkeypatch.setattr(entry,'prepare',lambda original,r,call:dict(r,joint_entry={'operation':entry.OPERATION},fresh_source=original))
    out=project.direct_then_verify(case,lambda *a:draft,population_ate=True)
    assert out['draft']==draft and out['fresh_source']==case and out['joint_entry']['operation']==entry.OPERATION
