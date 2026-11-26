from copy import deepcopy
from fractions import Fraction as F
import pytest
from cfm_id import local_bundle_entry as entry, joint_natural_entry as flow
from cfm_id_llm import local_bundle_reading as reader
from cfm_id_llm.compact_study import digest
from demo.tests.test_uploaded_network_contrast import fixture_case


def fixture(tmp_path):
    case,draft,table=fixture_case(tmp_path)
    def claim(v,key='science'):
        return dict(value=v,evidence=[dict(source_id=key,quote=next(s['text'] for s in case['sources'] if s['source_id']==key))])
    nodes=list(table.nodes)
    target=dict(question='比较本站开放和未开放',kind='CONTRAST',first=dict(own=1,exposure=1),second=dict(own=0,exposure=1),
        population=nodes[:2],weights={nodes[0]:'3/4',nodes[1]:'1/4'},fixed_before_assignment=True,
        remaining_assignment='ORIGINAL_DESIGN_CONDITIONAL',same_outcome_and_context=True)
    second=dict(target,question='另外两站的相反比较',population=nodes[2:],weights={nodes[2]:'1/3',nodes[3]:'2/3'},
        first=dict(own=0,exposure=1),second=dict(own=1,exposure=1))
    s=dict(family=claim(reader.FAMILY),study=claim(dict(treatment='开放1未开放0',outcome='到站量',outcome_kind='count',period='本周',fixed_background='本次试点',regime='EXPERIMENTAL')),
        network=claim(dict(nodes=nodes,edges=[list(e) for e in table.edges],complete=True,undirected=True),'graph'),
        design=claim(dict(kind='heterogeneous_bernoulli_binary_v1',propensities={n:'1/3' for n in nodes}),'law'),
        exposure=claim(dict(grouping='any_treated_neighbor',core_collaborators=None),'exp'),targets=[claim(target),claim(second)],
        information=[claim(dict(operator='NODE_FULL_LAW',availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=nodes,arm_cells=[],same_scope=True),'info')],
        conditions=[dict(code=k,statement=v,status='ADOPTED',covered_nodes=nodes,all_assignments=True,evidence=claim(None)['evidence']) for k,v in entry.NAMES.items() if k!='first_stage_exclusion'],remaining=[],material_notes=[])
    return case,draft,table,s


def planned(case,draft,s,table=None):
    s=reader.inspect(case,s)
    a=dict(binding=reader.binding(case,s),scientific_approval=False,findings=[
        dict(field=k,verdict='MATCH',reason='原文与测试候选一致，仅供离线合同测试',question=None,evidence=v.get('evidence',[]))
        for k,v in reader.fields(s).items()])
    a=reader.check_audit(case,s,a)
    r=dict(draft=draft,draft_sha256=digest(draft),input_sha256=digest(case),network_manifest=table.manifest() if table else None)
    return entry.plan(case,flow.base(r,case,s,a))


def approved(r):
    return dict(binding=r['condition_review']['binding'],authority='SYNTHETIC_TEST',
        decisions={x['code']:'ADOPTED' for x in r['condition_review']['items']})


def test_distinct_subgroups_weights_and_direction_replay(tmp_path):
    c,d,table,s=fixture(tmp_path);p=planned(c,d,s,table);r=entry.complete(c,p,approved(p))
    assert r['joint_entry']['state']=='BUNDLE_COMPLETE',r['joint_entry']['parts']
    assert flow.replay(c,d,r)
    parts=r['joint_entry']['parts']
    for part,sign in zip(parts,(1,-1)):
        actual={(a['node_id'],a['own_treatment']):F(a['coefficient']) for a in part['summary']['constituent_arms']}
        assert actual=={(n,own):F(w)*sgn*sign for n,w in part['target']['weights'].items() for own,sgn in ((1,1),(0,-1))}
        assert part['native_evidence']['source_batch']['node_ids']==list(table.nodes)
    assert not r['estimation_handoff_allowed']
    forged=deepcopy(r);forged['joint_entry']['parts'][0]['target']['weights'][table.nodes[0]]='1'
    assert not flow.replay(c,d,forged)
    c['business_question']+='新增另一个问题'
    assert not flow.replay(c,d,r)


def test_one_post_treatment_subgroup_does_not_borrow_other_certificate(tmp_path):
    c,d,table,s=fixture(tmp_path);s['targets'][1]['value']['fixed_before_assignment']=False
    p=planned(c,d,s,table);r=entry.complete(c,p,approved(p))
    assert [v['state'] for v in r['joint_entry']['parts']]==['POINT','UNSUPPORTED']
    assert r['joint_entry']['state']=='BUNDLE_INCOMPLETE' and flow.replay(c,d,r)


@pytest.mark.parametrize('field,value,expected',[
    ('weights',None,'NEEDS_INPUT'),('weights',{'谷口':'3/4','江岸':'3/4'},'NEEDS_INPUT'),
    ('fixed_before_assignment',None,'NEEDS_INPUT'),('remaining_assignment','OTHER','REVIEW_REQUIRED')])
def test_missing_and_invalid_target_not_normalized(tmp_path,field,value,expected):
    c,d,table,s=fixture(tmp_path);s['targets'][0]['value'][field]=value
    p=planned(c,d,s,table)
    assert p['joint_entry']['state']==expected
    assert p['joint_entry']['reading']['targets'][0]['value'][field]==value


def test_assumption_scope_not_expanded_and_rejection_saved(tmp_path):
    c,d,table,s=fixture(tmp_path);s['conditions'][1]['covered_nodes']=[table.nodes[0]]
    p=planned(c,d,s,table)
    assert p['joint_entry']['state']=='UNSUPPORTED' and 'condition_review' not in p
    s['conditions'][1]['covered_nodes']=list(table.nodes);p=planned(c,d,s,table)
    review=approved(p);review['decisions']['consistency']='DECLINED'
    r=entry.complete(c,p,review)
    assert r['joint_entry']['reason_code']=='REVIEW_PREMISE_DECLINED' and not r.get('proof')
    assert r['review_record']==review


def scoped_local_conditions(s):
    kinds={'consistency':'OBSERVED_CONSISTENCY', 'fixed_network':'FIXED_PRETREATMENT_NETWORK',
           'finite_means':'TARGET_EVENT_MEANS'}
    for c in s['conditions']:
        if c['code'] in kinds:
            c.update(all_assignments=None,local_scope=kinds[c['code']],
                     target_indices=list(range(len(s['targets']))) if c['code']=='finite_means' else None)


def test_method_specific_scopes_keep_native_targets_and_formulas(tmp_path):
    c,d,table,s=fixture(tmp_path)
    old=entry.complete(c,planned(c,d,s,table),approved(planned(c,d,s,table)))
    scoped_local_conditions(s)
    p=planned(c,d,s,table);r=entry.complete(c,p,approved(p))
    assert r['joint_entry']['state']=='BUNDLE_COMPLETE' and flow.replay(c,d,r)
    for a,b in zip(old['joint_entry']['parts'],r['joint_entry']['parts']):
        assert a['target']==b['target']
        assert a['summary']['identified_functional']==b['summary']['identified_functional']
        assert a['summary']['constituent_arms']==b['summary']['constituent_arms']
    # Parsed source scopes remain explicit; admission never rewrites them to
    # universal conditions to obtain the unchanged native formula.
    assert all(x['all_assignments'] is None for x in r['joint_entry']['reading']['conditions']
               if x['code']!='randomization')


@pytest.mark.parametrize('problem',['other_target','missing_nodes','refusal','randomization_unknown'])
def test_local_scope_does_not_supply_missing_or_declined_premises(tmp_path,problem):
    c,d,table,s=fixture(tmp_path);scoped_local_conditions(s)
    mean=next(x for x in s['conditions'] if x['code']=='finite_means')
    if problem=='other_target':mean['target_indices']=[0]
    elif problem=='missing_nodes':mean['covered_nodes']=[table.nodes[0]]
    elif problem=='refusal':mean['status']='NOT_ADOPTED'
    else:s['conditions'][0]['all_assignments']=None
    p=planned(c,d,s,table)
    parts=p['joint_entry']['parts']
    if problem=='other_target':
        r=entry.complete(c,p,approved(p))
        assert [v['state'] for v in r['joint_entry']['parts']]==['POINT','UNSUPPORTED']
        assert flow.replay(c,d,r)
    else:
        assert any(v['state']!='READY' for v in parts)
        assert not p.get('proof') and not p.get('backend_called')


@pytest.mark.parametrize('scope,indices',[
    ('FIXED_PRETREATMENT_NETWORK',[0]),('TARGET_EVENT_MEANS',[-1]),
    ('TARGET_EVENT_MEANS',[9]),('TARGET_EVENT_MEANS',[0,0])])
def test_wrong_condition_scope_or_target_binding_is_rejected(tmp_path,scope,indices):
    c,d,table,s=fixture(tmp_path)
    s['conditions'][-1].update(local_scope=scope,target_indices=indices)
    with pytest.raises(ValueError,match='LOCAL_CONDITION_'):reader.inspect(c,s)


def test_network_and_extra_constraints_preserved(tmp_path):
    c,d,table,s=fixture(tmp_path);s['network']['value']['edges'].pop()
    with pytest.raises(ValueError,match='NETWORK_DIFFERS'):planned(c,d,s,table)
    c,d,table,s=fixture(tmp_path);s['remaining']=[dict(code='monotone',statement='每个对象的效果非负',status='ADOPTED',evidence=s['family']['evidence'])]
    p=planned(c,d,s,table)
    assert p['joint_entry']['reason_code']=='LOCAL_ADDITIONAL_RESTRICTIONS' and not p.get('proof')


def test_unknown_design_remains_a_gap_not_an_inferred_randomized_law(tmp_path):
    c, d, table, s = fixture(tmp_path)
    s['study']['value']['regime'] = 'UNKNOWN'
    s['design']['value'] = None
    p = planned(c, d, s, table)
    assert p['joint_entry']['state'] == 'NEEDS_INPUT'
    assert p['joint_entry']['reading']['design']['value'] is None
    assert 'design' in p['joint_entry']['missing_fields']
    assert not p.get('proof') and not p.get('estimation_handoff_allowed')


def test_finite_sample_and_incomplete_information_not_upgraded(tmp_path):
    c,d,table,s=fixture(tmp_path);s['information'][0]['value'].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE')
    r=planned(c,d,s,table)
    assert all(x['state']=='UNSUPPORTED' for x in r['joint_entry']['parts'])
    assert r['joint_entry']['reason_code']=='LOCAL_SAMPLE_ONLY_INFORMATION'
    assert not r.get('condition_review') and not r.get('clarification_questions') and not r.get('proof')


def test_cited_table_is_checked_without_normalization(tmp_path):
    c,d,table,s=fixture(tmp_path)
    text='node_id,evaluation_weight\n谷口,3/4\n江岸,1/4'
    c['sources'].append(dict(source_id='weights',text=text,kind='OTHER'))
    s['targets'][0]['evidence'].append(dict(source_id='weights',quote=text))
    assert planned(c,d,s,table)['joint_entry']['state']=='REVIEW_REQUIRED'
    s['targets'][0]['value']['weights']={'谷口':'1/2','江岸':'1/2'}
    with pytest.raises(ValueError,match='WEIGHTS_DIFFER'):planned(c,d,s,table)


@pytest.mark.parametrize('misfiled',[True,False])
def test_extra_declaration_uses_bounded_recovery_without_erasing_restrictions(tmp_path,misfiled):
    import json
    c,d,table,correct=fixture(tmp_path);wrong=deepcopy(correct)
    wrong['remaining']=[dict(code='extra',statement='原设计内平均' if misfiled else '每个对象效果不能为负',
        status='ADOPTED',evidence=correct['family']['evidence'])]
    calls=[]
    def call(request,stage):
        calls.append(stage);body=json.loads(request['user_prompt'])
        if stage.startswith('joint_source_read'):
            return deepcopy(correct if misfiled and stage.endswith('retry1') else wrong)
        if stage.startswith('joint_source_audit'):
            from demo.tests.test_information_scope_audit import source_audit
            a=source_audit(c,reader.inspect(c,correct if misfiled and stage.endswith('retry1') else wrong),body['fields'])
            a.update(binding=body['input_binding'],scientific_approval=False,findings=[
                dict(field=k,verdict='MATCH',reason='Offline contract fixture',question=None,evidence=v.get('evidence',[]))
                for k,v in body['fields'].items()])
            return a
        assert stage=='joint_gap_review' and body['gaps']['remaining']['declaration_stop']
        return dict(binding=body['binding'],scientific_approval=False,findings=[dict(field='remaining',
            cause='READING_OMISSION' if misfiled else 'DECLARATION_CONFIRMED',
            evidence=wrong['family']['evidence'],reason='Offline cause fixture',question=None)])
    r=entry.prepare(c,dict(draft=d,draft_sha256=digest(d),checks=[]),call)
    assert r['joint_entry']['state']==('REVIEW_REQUIRED' if misfiled else 'UNSUPPORTED')
    assert ('joint_source_read_retry1' in calls)==misfiled
    assert not r.get('proof') and not r.get('estimation_handoff_allowed')
    if not misfiled:assert r['joint_entry']['unhandled_declarations']==wrong['remaining']


@pytest.mark.parametrize('other_status',['NOT_ADOPTED','ADOPTED','CONTRADICTED'])
def test_same_premise_records_keep_each_group_status(tmp_path,other_status):
    c,d,table,s=fixture(tmp_path);first=s['conditions'][1]
    first['covered_nodes']=list(table.nodes[:2])
    other=deepcopy(first);other.update(covered_nodes=list(table.nodes[2:]),status=other_status)
    s['conditions'].append(other)
    p=planned(c,d,s,table);r=entry.complete(c,p,approved(p))
    assert [x['state'] for x in r['joint_entry']['parts']]==['POINT','POINT' if other_status=='ADOPTED' else 'UNSUPPORTED']
    assert flow.replay(c,d,r)
    assert r['joint_entry']['reading']['conditions'][-1]['status']==other_status
    # Contradictory states for the SAME nodes never overwrite one another.
    if other_status!='ADOPTED':
        other['covered_nodes']=list(table.nodes[:2]);p=planned(c,d,s,table)
        assert p['joint_entry']['parts'][0]['state']=='UNSUPPORTED'
        assert not p.get('proof')


def test_disjoint_adopted_records_cover_target_without_covering_other_group(tmp_path):
    c,d,table,s=fixture(tmp_path);first=s['conditions'][1]
    first['covered_nodes']=[table.nodes[0]]
    other=deepcopy(first);other['covered_nodes']=[table.nodes[1]];s['conditions'].append(other)
    p=planned(c,d,s,table);r=entry.complete(c,p,approved(p))
    assert [x['state'] for x in r['joint_entry']['parts']]==['POINT','UNSUPPORTED']
    assert flow.replay(c,d,r)


def test_already_declined_target_does_not_ask_irrelevant_pending_premise(tmp_path):
    c,d,table,s=fixture(tmp_path)
    for code,status in [('consistency','NOT_ADOPTED'),('finite_means','UNDECIDED')]:
        first=next(c for c in s['conditions'] if c['code']==code)
        first['covered_nodes']=list(table.nodes[:2])
        second=deepcopy(first);second.update(covered_nodes=list(table.nodes[2:]),status=status)
        s['conditions'].append(second)
    p=planned(c,d,s,table)
    assert p['joint_entry']['state']=='REVIEW_REQUIRED' and not p.get('clarification_questions')
    r=entry.complete(c,p,approved(p))
    assert [x['state'] for x in r['joint_entry']['parts']]==['POINT','UNSUPPORTED']
    assert flow.replay(c,d,r)


@pytest.mark.parametrize('kind',range(1,9))
def test_native_design_constructors_are_reused(tmp_path,kind):
    c,d,table,s=fixture(tmp_path);n=list(table.nodes)
    base=dict(kind='unequal_probability_fixed_quota_binary_v1',nodes=n,m=2,treated_sets=[n[:2],n[2:]],set_probabilities=['1/3','2/3'],unit_weights=None)
    designs={1:s['design']['value'],2:dict(kind='complete_randomization_binary_v1',m=2),
        3:dict(kind='two_group_fixed_quota_binary_v1',groups=[n[:2],n[2:]],treated_quotas=[1,1]),
        4:dict(kind='cluster_bernoulli_binary_v2_4',clusters=[n[:2],n[2:]],cluster_probabilities=['1/3','2/3']),
        5:dict(kind='multi_group_fixed_quota_binary_v2_5',groups=[n[:2],[n[2]],[n[3]]],treated_quotas=[1,1,0]),
        6:dict(kind='two_stage_quota_mixture_binary_v2_7',groups=[n[:2],n[2:]],quota_profiles=[[1,1],[0,2]],profile_probabilities=['1/2','1/2']),
        7:base,8:dict(kind='rerandomized_balanced_binary_v1',base_design=base,balance_rule=dict(tolerance='2',covariates={'baseline':{v:'1' for v in n}}))}
    s['design']['value']=designs[kind]
    s=reader.inspect(c,s)
    task=entry.native_task(s,s['targets'][0]['value'],dict(binding='offline-confirmed',authority='SYNTHETIC_TEST'))
    assert task.estimand=='NETWORK_RANDOMIZED_ARM_MEAN'


@pytest.mark.parametrize('condition',['randomization','consistency','fixed_network','finite_means'])
def test_missing_scope_and_partial_information_are_not_approved(tmp_path,condition):
    c,d,table,s=fixture(tmp_path)
    next(x for x in s['conditions'] if x['code']==condition)['all_assignments']=None
    p=planned(c,d,s,table)
    assert p['joint_entry']['state']=='NEEDS_INPUT' and not p.get('condition_review')
    assert all('local_scope' not in x and 'target_indices' not in x
               for x in p['joint_entry']['reading']['conditions'])
    c,d,table,s=fixture(tmp_path)
    s['information'][0]['value']['outcome_nodes']=list(table.nodes[:2])
    p=planned(c,d,s,table);r=entry.complete(c,p,approved(p))
    assert [p['state'] for p in r['joint_entry']['parts']]==['POINT','UNSUPPORTED']
    assert flow.replay(c,d,r)
