from copy import deepcopy
from fractions import Fraction as F
import json
from pathlib import Path
import runpy
import pytest
from cfm_id import joint_query_exchange as exchange,joint_natural_entry as workflow

HERE=Path(__file__).parent

def reviewed_effect(name,authority='SYNTHETIC_TEST'):
    m=runpy.run_path(str(HERE/'test_observational_effect_entry.py'))
    case,wire=m['fixture'](name);r=m['prepared'](case,wire);s=r['condition_review']
    out=m['entry'].complete(case,r,dict(binding=s['binding'],authority=authority,decisions={i['code']:'ADOPTED' for i in s['items']}))
    return case,out

@pytest.mark.parametrize('name,count',[('observed',2),('stratum',4),('nodewise',4)])
@pytest.mark.parametrize('authority',['SYNTHETIC_TEST','EXTERNAL_RESEARCH_REVIEW'])
def test_observational_operator_and_source_replay(name,count,authority):
    case,out=reviewed_effect(name,authority);p=exchange.packet(case,out);r=exchange.check_packet(case['case_id'],p)
    assert r['query_count']==count and not r['estimator_executed']
    h=p['estimate_handoff'];values={q['id']:str(F(q['own'])+F(q['exposure'])+F(1,4)) for q in h['queries']}
    assert exchange.evaluate(h,values)=='1'
    assert r['release_scope']==authority
    assert workflow.replay(case,out['draft'],json.loads(json.dumps(out)))

@pytest.mark.parametrize('field',['target','coefficient','source','review','run'])
def test_stale_or_forged_handoff_rejected(field):
    case,out=reviewed_effect('stratum');p=exchange.packet(case,out)
    if field=='target':p['target']['first']=[0,0]
    if field=='coefficient':p['estimate_handoff']['operator_spec']['forms'][0][0]='7'
    if field=='source':p['source_case']['business_question']='different target'
    if field=='review':p['source_report']['review_record']['decisions']['consistency']='UNSURE'
    if field=='run':p['run_id']='another'
    with pytest.raises(ValueError):exchange.check_packet(case['case_id'],p)

@pytest.mark.parametrize('observational',[False,True])
def test_policy_contrast_is_signed_combination_of_original_certificates(observational):
    m=runpy.run_path(str(HERE/'test_network_existing_entry.py'));case,s=m['fixture'](observational)
    t=s['target']['value'];t.update(quantity='DIFFERENCE',reference_components=[dict(assignment={'A':0,'B':0},probability=None if observational else '1')])
    out=m['finish'](case,s);assert out['independent_replay']
    c=out['joint_entry']['native_result']['certificate'];assert c['kind']=='EXISTING_NETWORK_POLICY_COMPOSITION'
    p=exchange.packet(case,out);h=p['estimate_handoff'];assert exchange.check_packet(case['case_id'],p)['mode']=='ESTIMATE_POINT'
    assert F(exchange.evaluate(h,{q['id']:str(sum(q['assignment'])/2) for q in h['queries']}))==(F(1) if observational else F(1,4))
    changed=deepcopy(out);changed['joint_entry']['native_result']['certificate']['coefficients'][1]='1'
    assert not workflow.replay(case,out['draft'],changed)

def test_observational_mixture_requires_each_original_support():
    m=runpy.run_path(str(HERE/'test_network_existing_entry.py'));case,s=m['fixture'](True)
    s['target']['value']['components']=[dict(assignment={'A':1,'B':1},probability='1/4'),dict(assignment={'A':0,'B':0},probability='3/4')]
    out=m['finish'](case,s);assert out['independent_replay']
    h=exchange.packet(case,out)['estimate_handoff'];assert F(exchange.evaluate(h,{q['id']:str(sum(q['assignment'])/2) for q in h['queries']}))==F(1,4)
    s['information']['value']['assignment_masses']=[dict(assignment={'A':1,'B':1},probability='1')]
    out=m['finish'](case,s);assert not out['independent_replay']
    with pytest.raises(ValueError):exchange.packet(case,out)

def test_engine_delivers_and_revokes_without_fitting(tmp_path):
    from demo.backend.engine import Engine,Run
    case,out=reviewed_effect('stratum');run=Run(owner='offline',id=case['case_id'],case=case,synthetic=True,reading_mode='direct_verify')
    engine=Engine(tmp_path);engine.runs[run.id]=run
    engine._finish_direct_verification(run,out)
    assert run.result['estimation_handoff_allowed']
    assert (tmp_path/'estimate_inbox').exists()
    blocked=deepcopy(out);blocked['independent_replay']=False;blocked['joint_entry']['completed']=False
    engine._finish_direct_verification(run,blocked)
    assert not run.result['estimation_handoff_allowed']

@pytest.mark.parametrize('family',['DAG_JOINT','NETWORK_JOINT_MEANS'])
def test_joint_distribution_and_bounds_are_registered_without_claiming_estimation(family):
    m=runpy.run_path(str(HERE/'test_joint_natural_entry.py'));case,s=m['fixture'](family);out=m['finish'](case,s)
    p=exchange.packet(case,out);r=exchange.check_packet(case['case_id'],p)
    assert r['mode']==('REGISTER_CAUSAL_DISTRIBUTION' if family=='DAG_JOINT' else 'EXACT_BOUNDS')
    assert not r['estimator_executed']

def test_symbolic_source_review_handoff_and_unknown_parameter_scope():
    from cfm_id import symbolic_mean_entry as route
    from cfm_id_llm import symbolic_mean_reading as reader
    from cfm_id_llm.compact_study import digest
    root=HERE.parents[1];m=runpy.run_path(str(root/'tests_gateway/test_symbolic_joint_bounds.py'));p=m['fixture']()
    case=dict(case_id='symbolic',business_question=p['target_description'],sources=[dict(source_id=k,text=v,kind='OTHER') for k,v in p.pop('sources').items()])
    # Source fragments are generated by the same document intake, not invented.
    ids=list(reader.shared.sources(case));src=next(k for k in ids if k.startswith('s'))
    for row in [*p['parameters'],*p['coordinates'],*p['constraints']]:row['source_ids']=[src]
    s=reader.inspect(case,dict(binding=digest(case),scientific_approval=False,problem=p));fs=reader.fields(case,s)
    a=dict(binding=reader.binding(case,s),scientific_approval=False,findings=[dict(field=k,verdict='MATCH',evidence=v.get('evidence',[]),reason='unit test source review',question=None) for k,v in fs.items()])
    r=route.plan(case,workflow.base(dict(draft={},draft_sha256=digest({}),checks=[]),case,s,a));sheet=r['condition_review']
    out=route.complete(case,r,dict(binding=sheet['binding'],authority='SYNTHETIC_TEST',decisions={i['code']:'ADOPTED' for i in sheet['items']}))
    assert out['independent_replay']
    p=exchange.packet(case,out);assert exchange.check_packet(case['case_id'],p)['query_count']==1
    got=exchange.evaluate(p['estimate_handoff'],{'p':'3/2'});assert (got['lower'],got['upper'])==('1/2','1')
    with pytest.raises(ValueError):exchange.evaluate(p['estimate_handoff'],{'p':'3'})
