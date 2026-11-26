"""Adapter safety checks. Real-provider/browser acceptance is recorded separately."""
from copy import deepcopy
import json
import pytest
from cfm_id_llm import joint_reading as reader
from cfm_id_llm.compact_study import digest
from cfm_id import joint_natural_entry as entry
from cfm_id.network_joint_projection import project,replay_projection


def fixture(family='NETWORK_JOINT_MEANS'):
    text='本次按明确材料采用所列前提；甲乙有完整关系；全部总体信息、目标与线性约束已明确。'
    case=dict(case_id='unit',business_question='本次所列目标是什么范围？',sources=[dict(source_id='s',text=text,kind='OTHER')],response_language='zh')
    ev=[dict(source_id='s',quote=text)]
    claim=lambda value:dict(value=value,evidence=ev)
    s={k:None for k in ('dag_target','graph','dag_information','network','exposure','design','network_target','mean_information','bounds')}
    s.update(family=claim(family),conditions=[],constraints=[],remaining=[])
    required=entry.NET_REQUIRED if family=='NETWORK_JOINT_MEANS' else entry.DAG_REQUIRED
    s['conditions']=[dict(code=k,statement=text,status='ADOPTED',evidence=ev) for k in required]
    if family=='DAG_JOINT':
        s.update(dag_target=claim(dict(query_kind='INTERVENTIONAL_DISTRIBUTION',treatments=['A','B'],outcome=['Y'],conditioned_on=[],joint=True,context='同一随访人群',period='下月',intervention_values={'A':'1','B':'1'})),
            graph=claim(dict(nodes=['Z','A','B','Y'],directed=[['Z','A'],['Z','B'],['Z','Y'],['A','B'],['A','Y'],['B','Y']],bidirected=[],finite_discrete=True)),
            dag_information=claim(dict(kind='FULL_JOINT_POPULATION_LAW',variables=['Z','A','B','Y'],matches_target=True)))
    else:
        s.update(network=claim(dict(nodes=['甲','乙'],edges=[['甲','乙']],complete=True,undirected=True)),
            exposure=claim(dict(grouping='exact_treated_neighbor_count',core_collaborators=None)),
            design=claim(dict(kind='complete_randomization_binary_v1',m=1)),
            network_target=claim(dict(description='两站全部使用时的平均准时率',context='同一人群',period='下周',outcome='准时',first={'甲':1,'乙':1},second=None,weights={'甲':'1/2','乙':'1/2'})),
            mean_information=claim(dict(kind='POPULATION_MEANS_ONLY',values=[dict(node=n,own=a,exposure=1-a,value='1/5') for n in ['甲','乙'] for a in (0,1)],matches_target=True)),
            bounds=claim(dict(outcome_domain='BINARY',kind='CONDITIONAL_MEAN',by_node={'甲':['0','1'],'乙':['0','1']},all_assignments=True)))
        s['constraints']=[dict(description='两站全用时平均结果之和不超过1.2',terms=[dict(node=n,own=1,exposure=1,coefficient='1') for n in ['甲','乙']],relation='LE',rhs='6/5',status='ADOPTED',evidence=ev)]
    return case,s


def prepared(case,s):
    s=reader.inspect(case,s)
    a=dict(binding=reader.binding(case,s),scientific_approval=False,findings=[dict(field=k,verdict='MATCH',evidence=v.get('evidence',[]),reason='test audit fixture',question=None) for k,v in reader.fields(s).items()])
    reader.check_audit(case,s,a)
    report=dict(version='direct-verification/25',draft={'status':'PARTIAL'},draft_sha256=digest({'status':'PARTIAL'}),checks=[])
    return entry.plan(case,entry.base(report,case,s,a))


def finish(case,s):
    r=prepared(case,s);sheet=r['condition_review']
    review=dict(binding=sheet['binding'],authority='SYNTHETIC_TEST',decisions={x['code']:'ADOPTED' for x in sheet['items']})
    return entry.complete(case,r,review)


@pytest.mark.parametrize('family',['DAG_JOINT','NETWORK_JOINT_MEANS'])
def test_fresh_source_to_native_replay(family):
    case,s=fixture(family);r=finish(case,s)
    assert r['independent_replay'] and entry.replay(case,r['draft'],r)
    assert not r['estimation_handoff_allowed']
    c=r['joint_entry']['native_result']['certificate']
    if family=='DAG_JOINT':assert c['target']['treatments']==['A','B']
    else:assert (c['lower'],c['upper'])==('0','3/5')
    changed=deepcopy(case);changed['business_question']+=' 改了问题'
    assert not entry.replay(changed,r['draft'],r)


@pytest.mark.parametrize('family',['DAG_JOINT','NETWORK_JOINT_MEANS'])
def test_saved_browser_json_replays_and_tampering_still_fails(family):
    case,s=fixture(family);r=json.loads(json.dumps(finish(case,s)))
    assert entry.replay(case,r['draft'],r)
    r['proof']['certificate']['status']='FORGED'
    assert not entry.replay(case,r['draft'],r)


@pytest.mark.parametrize('status,expected',[('UNDECIDED','NEEDS_INPUT'),('NOT_ADOPTED','REVIEW_REQUIRED'),('ADOPTED','REVIEW_REQUIRED')])
def test_constraint_adoption_is_not_dropped(status,expected):
    case,s=fixture();s['constraints'][0]['status']=status
    assert prepared(case,s)['joint_entry']['state']==expected
    if status=='NOT_ADOPTED':assert finish(case,s)['joint_entry']['native_result']['certificate']['upper']=='1'


def test_extra_individual_restriction_blocks():
    case,s=fixture();s['remaining']=[dict(code='individual',statement='每次结果都不能变差',status='ADOPTED',evidence=s['family']['evidence'])]
    r=prepared(case,s);assert r['joint_entry']['state']=='UNSUPPORTED' and not r['backend_called']


def test_sample_does_not_become_population():
    case,s=fixture();s['mean_information']['value']['kind']='FINITE_SAMPLE'
    r=prepared(case,s);assert r['clarification_questions'] and r['joint_entry']['state']=='NEEDS_INPUT'


def test_data_notes_are_preserved_and_reviewed_without_scientific_adoption():
    case,s=fixture('DAG_JOINT')
    s['dag_information']['value'].update(kind='FINITE_SAMPLE',sample_size=200)
    s['material_notes']=[dict(kind='OUTPUT_REQUEST',statement='这里只求公式',evidence=s['family']['evidence'])]
    r=prepared(case,s)
    assert r['joint_entry']['reason_code']=='JOINT_OBSERVATIONS_REQUIRED' and r['clarification_questions']
    assert r['joint_entry']['reading']['dag_information']['value']['sample_size']==200
    assert 'material_notes.0' in reader.fields(r['joint_entry']['reading'])
    a=deepcopy(r['joint_entry']['audit']);a['findings']=[x for x in a['findings'] if x['field']!='material_notes.0']
    with pytest.raises(ValueError):reader.check_audit(case,r['joint_entry']['reading'],a)
    # A real individual restriction remains blocking, regardless of data notes.
    s['remaining']=[dict(code='individual',statement='每人的结果不能变差',status='ADOPTED',evidence=s['family']['evidence'])]
    assert prepared(case,s)['joint_entry']['state']=='UNSUPPORTED'


def test_zero_objective_cells_and_conflicts_survive():
    case,s=fixture();s['constraints'].append(dict(description='未入目标的均值冲突',terms=[dict(node='乙',own=0,exposure=0,coefficient='1')],relation='GE',rhs='2',status='ADOPTED',evidence=s['family']['evidence']))
    r=finish(case,s);assert r['joint_entry']['state']=='INCOMPATIBLE' and r['independent_replay']


def test_projection_tampering_and_full_scope():
    case,s=fixture();p,m=project(s,reader.sources(case));assert len(p['coordinates'])==8
    assert replay_projection(s,reader.sources(case),p,m)
    m['cells'][0]['support']='1';assert not replay_projection(s,reader.sources(case),p,m)


def test_missing_audit_item_and_missing_citation_rejected():
    case,s=fixture();r=prepared(case,s);a=deepcopy(r['joint_entry']['audit']);a['findings'].pop()
    with pytest.raises(ValueError):reader.check_audit(case,r['joint_entry']['reading'],a)
    s['conditions'][0]['evidence']=[]
    with pytest.raises(ValueError):reader.inspect(case,s)


def test_missing_relevant_reading_block_remains_an_explicit_audit_item():
    case,s=fixture();s['design']=None;s=reader.inspect(case,s)
    fields=reader.fields(s)
    assert fields['design']['value'] is None and fields['design']['check']
    request=json.loads(reader.audit_request(case,s)['user_prompt'])
    assert 'design' in request['output_schema']['$defs']['AuditFinding']['properties']['field']['enum']


def test_declined_science_does_not_execute():
    case,s=fixture('DAG_JOINT');r=prepared(case,s);sheet=r['condition_review']
    out=entry.complete(case,r,dict(binding=sheet['binding'],authority='SYNTHETIC_TEST',decisions={x['code']:'DECLINED' for x in sheet['items']}))
    assert not out['backend_called'] and not out['independent_replay']


def test_identical_questions_are_presented_once_without_losing_different_gaps():
    out=entry.stop({'joint_entry':{}},'NEEDS_INPUT','TEST','message',['确认时期？','确认时期？','均值关系是否采用？'])
    assert out['clarification_questions']==['确认时期？','均值关系是否采用？']


def test_audit_format_retry_keeps_original_reading_and_exact_scope():
    from demo.tests.test_design_scope_audit import audit_fields
    case,s=fixture();p=prepared(case,s);audit=p['joint_entry']['audit'];calls=[]
    audit.update(audit_fields(s))
    def call(request,stage):
        calls.append(stage)
        if stage=='joint_source_read':return s
        if stage=='joint_source_audit':
            bad=deepcopy(audit);bad['findings'][0]['field']='wrong_key';return bad
        assert stage=='joint_audit_format_retry';return audit
    base=dict(version='direct-verification/25',draft={},draft_sha256=digest({}),checks=[])
    r=entry.prepare(case,base,call)
    assert r['joint_entry']['state']=='REVIEW_REQUIRED' and not r['backend_called']
    assert calls==['joint_source_read','joint_source_audit','joint_audit_format_retry']
    assert r['joint_entry']['audit_repairs'][0]['raw']['findings'][0]['field']=='wrong_key'


def test_new_candidate_gets_one_audit_repair_without_losing_prior_objection():
    case,correct=fixture('DAG_JOINT');wrong=deepcopy(correct)
    wrong['dag_target']['value']['period']='另一个被误读的时期'
    candidates=[reader.inspect(case,x) for x in (wrong,correct)]
    def audit(s):
        return dict(binding=reader.binding(case,s),scientific_approval=False,findings=[
            dict(field=k,verdict='MATCH',evidence=v.get('evidence',[]),reason='来源核对测试',question=None)
            for k,v in reader.fields(s).items()])
    calls=[]
    def call(request,stage):
        calls.append(stage);i=int(stage.endswith('_retry1'));s=candidates[i]
        if stage.startswith('joint_source_read'):return s
        a=audit(s);finding=next(x for x in a['findings'] if x['field']=='dag_target')
        if stage.startswith('joint_source_audit'):
            finding['question']='不应直接交给用户的格式矛盾？'
            return a
        assert stage.startswith('joint_audit_format_retry')
        body=json.loads(request['user_prompt'])
        assert body['input_binding']==reader.binding(case,s)
        assert 'field=dag_target' in body['format_feedback_not_evidence']
        assert 'question应为null' in body['format_feedback_not_evidence']
        if not i:finding.update(verdict='READING_ERROR',reason='候选改变了原问题，必须重新读取')
        return a
    report=dict(version='direct-verification/25',draft={},draft_sha256=digest({}),checks=[])
    r=entry.prepare(case,report,call)
    assert r['joint_entry']['state']=='REVIEW_REQUIRED' and not r['backend_called']
    assert r['joint_entry']['reading']==candidates[1] and not r['clarification_questions']
    assert calls==['joint_source_read','joint_source_audit','joint_audit_format_retry',
                   'joint_source_read_retry1','joint_source_audit_retry1','joint_audit_format_retry_retry1']
    assert [x['attempt'] for x in r['joint_entry']['audit_repairs']]==[0,1]
    assert len({x['reading_binding'] for x in r['joint_entry']['audit_repairs']})==2
    assert any(x['verdict']=='READING_ERROR' for x in r['joint_entry']['attempts'][0]['audit']['findings'])


def test_repeated_audit_contradictions_stop_after_six_calls_without_execution():
    case,s=fixture('DAG_JOINT');s=reader.inspect(case,s);calls=[]
    def call(request,stage):
        calls.append(stage)
        if stage.startswith('joint_source_read'):return s
        return dict(binding=reader.binding(case,s),scientific_approval=False,findings=[
            dict(field=k,verdict='MATCH',evidence=v.get('evidence',[]),reason='格式冲突测试',question='错误追问？')
            for k,v in reader.fields(s).items()])
    report=dict(version='direct-verification/25',draft={},draft_sha256=digest({}),checks=[])
    r=entry.prepare(case,report,call)
    assert len(calls)==6 and len(r['joint_entry']['audit_repairs'])==2
    assert r['joint_entry']['state']=='READING_RECHECK_REQUIRED'
    assert not r['backend_called'] and not r['clarification_questions']
    assert r['joint_entry']['failure_details'][0]['kind']=='MODEL_OUTPUT_CONTRACT'


@pytest.mark.parametrize('verdict,question',[
    ('MATCH','请补充？'),('READING_ERROR','请修复模型？'),('NEEDS_CLARIFICATION',None),
    ('NEEDS_CLARIFICATION','  '),('NEEDS_CLARIFICATION','')])
def test_audit_question_conflict_reports_field_and_does_not_change_verdict(verdict,question):
    case,s=fixture('DAG_JOINT');a=prepared(case,s)['joint_entry']['audit']
    a['findings'][0].update(verdict=verdict,question=question);original=deepcopy(a)
    with pytest.raises(ValueError,match='JOINT_AUDIT_QUESTION: field=family'):
        reader.check_audit(case,reader.inspect(case,s),a)
    assert a==original


def test_line_endings_are_presented_consistently_without_deleting_rows():
    case,s=fixture();case['sources'][0]['text']='1,node,value\r\n2,A,1\r\n3,B,0'
    for block in [v for v in s.values() if isinstance(v,dict)]+s['conditions']+s['constraints']:
        block['evidence']=[dict(source_id='s',quote='1,node,value\n2,A,1\n3,B,0')]
    reader.inspect(case,s)
    s['network']['evidence'][0]['quote']='node,value\nA,1\nB,0'
    with pytest.raises(ValueError):reader.inspect(case,s)


def test_source_fragment_references_expand_only_to_exact_original_text():
    case,s=fixture();s['family']['evidence']=[{'source_id':'s#L1'}]
    checked=reader.inspect(case,s)
    assert checked['family']['evidence'][0]['quote']==case['sources'][0]['text']
    s['family']['evidence']=[{'source_id':'s#L999'}]
    with pytest.raises(ValueError):reader.inspect(case,s)
    s['family']['evidence']=[{'source_id':'s'}]
    with pytest.raises(ValueError):reader.inspect(case,s)


def test_absent_other_model_slots_are_not_extra_assumptions():
    case,s=fixture('DAG_JOINT')
    s['conditions'].append(dict(code='randomization',statement='未声明随机分配',status='UNKNOWN',evidence=[]))
    assert prepared(case,s)['joint_entry']['state']=='REVIEW_REQUIRED'
    s['conditions'][-1].update(status='UNDECIDED',evidence=s['family']['evidence'])
    assert prepared(case,s)['joint_entry']['state']=='NEEDS_INPUT'


def test_declared_rejection_is_not_asked_again_as_unknown():
    case,s=fixture('DAG_JOINT');s['conditions'][0]['status']='NOT_ADOPTED'
    r=prepared(case,s)
    assert r['joint_entry']['state']=='UNSUPPORTED' and not r['clarification_questions'] and not r['backend_called']


def test_conditional_intervention_is_not_hidden_in_context():
    case,s=fixture('DAG_JOINT');s['dag_target']['value'].update(query_kind='CONDITIONAL_INTERVENTIONAL_DISTRIBUTION',conditioned_on=['Z'])
    r=prepared(case,s)
    assert r['joint_entry']['reason_code']=='JOINT_TARGET_FUNCTIONAL_NOT_CONNECTED' and not r['backend_called']


@pytest.mark.parametrize('design,exposure',[(f'D{d}',f'E{e}') for d in range(1,9) for e in range(1,6)])
def test_network_projection_preserves_existing_forty_mean_box_cases(design,exposure):
    from tests_gateway.test_finite_mean_box import native
    from cfm_id.bounded_finite_solver import solve_contrast
    from cfm_id.finite_mean_joint_solver import solve
    from cfm_id.finite_mean_joint_verify import replay
    _,q,information=native(design,exposure)
    if design=='D2' and exposure=='E1':
        from cfm_id.bounded_contrast_solver import solve as solve_contrast
    elif design=='D2' and exposure=='E4':
        from cfm_id.bounded_count_solver import solve_contrast
    old=solve_contrast(q,information)
    first=q['first'];st=first.study;nodes=list(st.node_order);info=information['first']
    case,s=fixture();ev=s['family']['evidence'];claim=lambda value:dict(value=value,evidence=ev)
    s.update(network=claim(dict(nodes=nodes,edges=list(map(list,st.undirected_edges)),complete=True,undirected=True)),
        exposure=claim(dict(grouping=first.r2_signature.grouping,core_collaborators=dict(first.r2_signature.core_collaborators) or None)),
        design=claim(st.design().model_dump()),
        network_target=claim(dict(description='两份完整政策的均值之差',context=st.context_reference,period=info.outcome_period,outcome=st.outcome_variable,
            first=dict(zip(nodes,first.target.policy_assignment)),second=dict(zip(nodes,q['second'].target.policy_assignment)),weights=dict(zip(nodes,first.target.unit_weights)))),
        mean_information=claim(dict(kind='POPULATION_MEANS_ONLY',values=[v.model_dump() for v in info.values],matches_target=True)),
        bounds=claim(dict(outcome_domain='BINARY',kind=info.bounds_kind,by_node={b.node:[b.lower,b.upper] for b in info.bounds},all_assignments=True)),constraints=[])
    p,receipt=project(s,reader.sources(case));new=solve(p)
    assert replay_projection(s,reader.sources(case),p,receipt) and replay(new,p)
    assert (new['lower'],new['upper'])==(old['lower'],old['upper'])
