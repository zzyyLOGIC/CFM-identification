from copy import deepcopy
from itertools import combinations
import pytest
from cfm_id_bridge.scientific_binding import sha
from cfm_id import dag_joint, finite_mean_joint
from cfm_id.dag_joint_contract import JointIdProblem, DECISIONS as DAG_DECISIONS
from cfm_id.dag_joint_verify import replay as replay_joint
from cfm_id.finite_mean_joint_contract import JointMeanProblem, DECISIONS as MEAN_DECISIONS
from cfm_id.finite_mean_joint_verify import replay as replay_mean


@pytest.mark.parametrize('op,build,keys',[
    ('DAG_JOINT_ID',lambda:graph_problem(),DAG_DECISIONS),
    ('FINITE_MEAN_JOINT',lambda:mean_problem(),MEAN_DECISIONS)])
def test_public_registry_preserves_review_and_native_result(op,build,keys):
    from cfm_id.research_route_entry import run_registered_route
    p=build();r=review(p,keys)
    assert run_registered_route(op,p,review=r)['state']=='REVIEW_REQUIRED'
    out=run_registered_route(op,p,review=r,research_protocol_selected=True)
    assert out['independent_replay'] and out['entry_diagnostics']['method']['input_facts']
    assert not out['business_reading_checked'] and not out['estimation_handoff_allowed']
    invalid=run_registered_route(op,{},research_protocol_selected=True)
    assert invalid['entry_diagnostics']['reason_code']=='INVALID_ROUTE_PROBLEM_OR_REVIEW'


@pytest.mark.parametrize('op,build,keys',[
    ('DAG_JOINT_ID',lambda:graph_problem(),DAG_DECISIONS),
    ('FINITE_MEAN_JOINT',lambda:mean_problem(),MEAN_DECISIONS)])
def test_uploaded_dedicated_spec_is_bound_to_whole_original_study(tmp_path,op,build,keys):
    import json
    from demo.backend.engine import Engine,Run
    from demo.backend.study_math import FORMAT,offered,submit
    p=build();q='请按本次明确给出的研究规格核对目标。'
    doc=dict(format=FORMAT,question=q,operation=op,problem=p.model_dump())
    engine=Engine(tmp_path/'runs',max_api_calls=0)
    original={'draft':{'status':'NEEDS_INPUT'}}
    parent=Run(owner='reader',synthetic=True,case=dict(business_question=q,sources=[
        dict(source_id='spec',text=json.dumps(doc)),dict(source_id='notes',text='本次研究原始说明')]),
        result=deepcopy(original),attachment_report={'receipt':{'ready':True}})
    engine.runs[parent.id]=parent
    request=dict(source_run=parent.id,source_binding=offered(parent.case)['binding'],source_confirmed=True)
    assert submit(engine,'reader',request)['state']=='REVIEW_REQUIRED'
    out=submit(engine,'reader',dict(request,review=review(p,keys)))
    assert out['independent_replay'] and parent.result==original and engine.calls==0
    assert not engine.estimate_inbox.path_for(parent.id).exists()
    parent.synthetic=False
    with pytest.raises(ValueError,match='AUTHORITY_SCOPE'):
        submit(engine,'reader',dict(request,review=review(p,keys)))
    parent.synthetic=True;parent.case['sources'][1]['text']='背景已修改'
    with pytest.raises(ValueError,match='ORIGINAL_TARGET'):
        submit(engine,'reader',dict(request,review=review(p,keys)))


def test_diagnostic_exposes_actual_pending_condition_without_approving_or_rewriting():
    from cfm_id.entry_diagnostics import summarize
    result=dict(state='NEEDS_INPUT',result=dict(reason_code='NEEDS_INPUT',attempted_routes=[dict(route='existing',result='NEEDS_INPUT')]))
    original=deepcopy(result)
    p=dict(license=dict(name='exposure_level_conditional_exchangeability',confirmed=False,status='PROPOSED'))
    d=summarize(result,operation='business',problem=p)
    assert result==original and len(d['unconfirmed_declarations'])==1
    assert d['candidate_findings']==result['result']['attempted_routes']
    assert any('可比较' in text for text in d['missing_or_stopping'])
    assert not d['scientific_approval'] and not d['estimation_handoff_allowed']


def graph_problem(**changes):
    data=dict(version='dag-joint-id-1',model='RECURSIVE_SEMI_MARKOVIAN_DISCRETE',nodes=['A','B','Y'],
        directed=[['A','Y'],['B','Y']],bidirected=[],treatments=['A','B'],outcome=['Y'],
        context='本次完整随访人群',graph_status='RESEARCHER_CONFIRMED',graph_source='研究方案中明确列出的完整因果图',
        materials_sha256='a'*64,information='FULL_JOINT_POPULATION_LAW',information_variables=['A','B','Y'],
        strictly_positive_joint=True,unresolved=[],additional_restrictions=[])
    return JointIdProblem.model_validate(dict(data,**changes))


def mean_problem(**changes):
    data=dict(version='finite-mean-joint-1',model='FINITE_MEANS_WITH_DECLARED_LINEAR_CONSTRAINTS',
        outcome_domain='BINARY',context='本次服务方案比较',target_description='新方案平均完成率减去原方案平均完成率',
        target={'new':'1','old':'-1'},target_offset='0',
        coordinates=[dict(id=k,description=k+'方案总体完成率',lower='0',upper='1',known=None,source_ids=['protocol']) for k in ('new','old')],
        constraints=[],sources={'protocol':'两方案完成率均在零和一之间；本模型仅采用列出的均值限制。'},
        information='POPULATION_MEANS',model_complete=True,unresolved=[],additional_restrictions=[])
    return JointMeanProblem.model_validate(dict(data,**changes))


def condition(id='same',relation='EQ',rhs='0',adoption='ADOPTED',**kw):
    return dict(id=id,coefficients={'new':'1','old':'-1'},relation=relation,rhs=rhs,adoption=adoption,source_ids=['protocol'],**kw)


def review(p,keys):
    return dict(version=p.version,problem_sha256=sha(p),reviewer='local reviewer',
        evidence='Test-only approval of this explicitly constructed mathematical model.',authority='SYNTHETIC_TEST',
        decisions=dict.fromkeys(keys,'ACCEPTED'))


def test_joint_intervention_point_and_singleton_equivalence():
    from cfm_id.dag_id_solver import identify
    from cfm_id.dag_id_contract import as_problem
    from cfm_id.dag_id_verify import _canonical
    p=graph_problem(); cert=dag_joint.solve(p)
    assert replay_joint(cert,p)
    p=graph_problem(treatments=['A']); cert=dag_joint.solve(p)
    old=identify(as_problem(p.nodes,p.directed,p.bidirected,'A',p.outcome,p.context))
    assert _canonical(cert['functional'])==_canonical(old['functional'])
    assert replay_joint(cert,p)


@pytest.mark.parametrize('edges',[
    [['A','B'],['B','Y']], [['A','B'],['A','Y'],['B','Y']], [['A','Y']], [],
])
def test_intervening_on_mediator_and_parent_together(edges):
    p=graph_problem(directed=edges)
    cert=dag_joint.solve(p)
    assert cert['status']=='POINT' and replay_joint(cert,p)


def test_joint_outcomes_and_latent_frontdoor_mixture():
    p=graph_problem(nodes=['A','B','M','Y','Z'],directed=[['A','M'],['M','Y'],['B','Y'],['B','Z']],
        bidirected=[['A','Y']],outcome=['Y','Z'],information_variables=['A','B','M','Y','Z'])
    cert=dag_joint.solve(p)
    assert cert['status']=='POINT' and replay_joint(cert,p)


def test_joint_nonidentification_has_original_graph_hedge():
    p=graph_problem(bidirected=[['A','Y']])
    result=dag_joint.submit(p,review(p,DAG_DECISIONS))
    assert result['state']=='NONIDENTIFIABLE' and result['nonidentification_proved']
    assert result['evidence']['evidence_report']['passed']


@pytest.mark.parametrize('edit', ['target','trace','functional','positivity','graph'])
def test_joint_certificate_tampering_even_after_rehash(edit):
    p=graph_problem(); c=dag_joint.solve(p)
    if edit=='target': c['target']['treatments']=['A']
    elif edit=='trace': c['derivation'][0]['treatment']=['A']
    elif edit=='functional': c['functional']={'operation':'OBSERVED_JOINT'}
    elif edit=='positivity': c['positivity']={}
    else: c['graph']['directed']=[]
    c['certificate_sha256']=sha({k:v for k,v in c.items() if k!='certificate_sha256'})
    assert not replay_joint(c,p)


@pytest.mark.parametrize('changes,state',[
    ({'information':'FINITE_SAMPLE'},'NEEDS_INPUT'),
    ({'strictly_positive_joint':None},'NEEDS_INPUT'),
    ({'additional_restrictions':['两种方案还采用个体单调性']},'UNSUPPORTED'),
    ({'unresolved':['是否固定第二个变量尚未决定']},'NEEDS_INPUT'),
])
def test_joint_gates_before_producer(changes,state,monkeypatch):
    monkeypatch.setattr(dag_joint,'solve',lambda p:pytest.fail('solver called before gates'))
    p=graph_problem(**changes)
    assert dag_joint.submit(p,review(p,DAG_DECISIONS))['state']==state


def test_joint_stale_pending_and_extra_condition_never_approved_away():
    p=graph_problem(); r=review(p,DAG_DECISIONS)
    assert dag_joint.submit(p,None)['state']=='REVIEW_REQUIRED'
    r['decisions'][DAG_DECISIONS[0]]='PENDING'
    assert dag_joint.submit(p,r)['state']=='REVIEW_REQUIRED'
    r=review(p,DAG_DECISIONS); r['problem_sha256']='b'*64
    assert dag_joint.submit(p,r)['state']=='CHECK_BLOCKED'


@pytest.mark.parametrize('constraints,expected',[
    ([],('-1','1')),
    ([condition()],('0','0')),
    ([condition(relation='GE',rhs='1/5')],('1/5','1')),
    ([condition(relation='LE',rhs='1/4')],('-1','1/4')),
    ([condition(adoption='NOT_ADOPTED')],('-1','1')),
    ([condition(relation='GE',rhs='1/5'),condition(id='cap',relation='LE',rhs='3/5')],('1/5','3/5')),
])
def test_coupled_bounds_and_point(constraints,expected):
    p=mean_problem(constraints=constraints); result=finite_mean_joint.submit(p,review(p,MEAN_DECISIONS))
    c=result['certificate']
    assert (c['lower'],c['upper'])==expected and result['independent_replay'] and replay_mean(c,p)
    assert result['state']==('POINT' if expected[0]==expected[1] else 'PARTIAL')


def test_coupled_non_box_polytope_and_offset():
    # Intersection creates a vertex unavailable to the old anchor/order enumeration.
    p=mean_problem(target={'new':'1'},target_offset='1/7',constraints=[
        dict(condition('sum',rhs='1'),coefficients={'new':'2','old':'1'}),condition('equal')])
    c=finite_mean_joint.solve(p)
    assert c['lower']==c['upper']=='10/21' and replay_mean(c,p)


@pytest.mark.parametrize('constraints',[
    [condition(rhs='0'),condition(id='greater',relation='GE',rhs='1/5')],
    [dict(condition(),coefficients={},relation='LE',rhs='-1')],
])
def test_incompatibility_is_proved_not_empty_interval(constraints):
    p=mean_problem(constraints=constraints); c=finite_mean_joint.solve(p)
    assert c['status']=='INCOMPATIBLE' and 'lower' not in c and replay_mean(c,p)


def test_irrelevant_coordinates_still_check_feasibility():
    p=mean_problem(target={},constraints=[condition(rhs='2')])
    c=finite_mean_joint.solve(p)
    assert c['status']=='INCOMPATIBLE' and replay_mean(c,p)


@pytest.mark.parametrize('changes,state',[
    ({'constraints':[condition(adoption='UNDECIDED')]},'NEEDS_INPUT'),
    ({'additional_restrictions':['结果还必须满足个体层面的单调性']},'UNSUPPORTED'),
    ({'information':'FINITE_SAMPLE'},'NEEDS_INPUT'),({'model_complete':None},'NEEDS_INPUT'),
])
def test_mean_scientific_gates(changes,state,monkeypatch):
    monkeypatch.setattr(finite_mean_joint,'solve',lambda p:pytest.fail('solver called before gates'))
    p=mean_problem(**changes)
    assert finite_mean_joint.submit(p,review(p,MEAN_DECISIONS))['state']==state


@pytest.mark.parametrize('field',['lower','lower_world','lower_dual','sharp','realization'])
def test_mean_certificate_tampering(field):
    p=mean_problem(constraints=[condition(relation='GE',rhs='1/5')]); c=finite_mean_joint.solve(p)
    c[field]={'new':'0','old':'1'} if field=='lower_world' else {} if field=='lower_dual' else False if field=='sharp' else 'wrong'
    c['certificate_sha256']=sha({k:v for k,v in c.items() if k!='certificate_sha256'})
    assert not replay_mean(c,p)


def test_exact_lp_resource_stop_and_independent_verifier(monkeypatch):
    from cfm_id import finite_mean_joint_solver as producer
    p=mean_problem(constraints=[condition()]); c=finite_mean_joint.solve(p)
    with monkeypatch.context() as context:
        context.setattr(producer,'solve',lambda p:pytest.fail('verifier called producer'))
        context.setattr(producer,'compile_rows',lambda p:pytest.fail('verifier reused producer constraints'))
        assert replay_mean(c,p)
    monkeypatch.setattr(producer,'MAX_SYSTEMS',0)
    assert finite_mean_joint.submit(p,review(p,MEAN_DECISIONS))['state']=='RESOURCE_LIMIT'


def test_mean_review_binding_covers_nonadopted_conditions_and_sources():
    p=mean_problem(); r=review(p,MEAN_DECISIONS)
    q=p.model_copy(update={'sources':{'protocol':'changed original'}})
    assert finite_mean_joint.submit(q,r)['reason_code']=='STALE_JOINT_MEAN_REVIEW'


def test_new_web_operations_and_readonly_diagnostic():
    from demo.backend import math_library
    for module,p,keys in [(dag_joint,graph_problem(),DAG_DECISIONS),(finite_mean_joint,mean_problem(),MEAN_DECISIONS)]:
        assert module.ROUTE in math_library.catalog()['research']
        assert 'problem' in math_library.schema(module.ROUTE)
        prepared=math_library.run(dict(operation=module.ROUTE,problem=p.model_dump()))
        assert prepared['state']=='REVIEW_REQUIRED'
        result=math_library.run(dict(operation=module.ROUTE,problem=p.model_dump(),review=review(p,keys)))
        assert result['independent_replay']
        assert result['entry_diagnostics']['result_evidence']=='VERIFIED'
        assert result['entry_diagnostics']['scientific_approval'] is False
        assert not result['estimation_handoff_allowed']
