"""Actual local-effect business entry, independent admission and native proofs."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import product
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_dispatch as dispatch, network_effect_dispatch as effects, business_case
from cfm_id import business_intake as intake, fact_reading_revision as revisions
from cfm_id_llm import network_effect_reading as reading
from examples.network_effect_dispatch_reference import setup, approval_records, material, a0_reference, fact_reference
from examples.business_dispatch_reference import approve


def test_located_recheck_inherits_current_effect_field_ownership_without_answers():
    from cfm_id_llm.fact_reading_contracts import contract_for_entry
    s,e,o,_=setup()
    contract=contract_for_entry(e)
    schema=json.JSONDecoder().raw_decode(e['request']['user'])[0]['output_schema']
    for name in ('information','additional_restrictions','unresolved'):
        path=f'/{name}/0/text'
        rules=contract.public_constraints(e,[path])
        assert dict(field_path=path,description=schema['properties'][name]['description']) in rules
    assert not any(r.get('description')==schema['properties']['additional_restrictions']['description']
                   for r in contract.public_constraints(e,['/additional_restrictions_other/0']))
    o['candidate']['additional_restrictions']=[dict(text='原文的一条待核对说明',source_ids=o['candidate']['study']['source_ids'])]
    prepared=revisions.prepare_recheck(s,'q1',**o)
    sheet=prepared['feedback_worksheet']
    feedback=dict(version=sheet['version'],binding_sha256=sheet['binding_sha256'],authority='SYNTHETIC_TEST',
        reviewer='Offline contract test',evidence='Only locate a possible duplicate without supplying corrected values.',
        issues=[dict(field_path='/additional_restrictions/0',kind='POSSIBLE_DUPLICATION',
                     source_ids=[next(iter(sheet['source_catalog']))],reason='private reviewer diagnosis must stay local')])
    revised=revisions.prepare_recheck(s,'q1',**o,feedback=feedback)
    assert revised['state']=='READY_TO_READ'
    request=revised['request']['user']
    assert schema['properties']['additional_restrictions']['description'] in request
    assert 'private reviewer diagnosis' not in request
    assert 'POSSIBLE_DUPLICATION' in request


@pytest.mark.parametrize('field,value,phrase', [
    ('graph_kind','UNKNOWN','是否有方向'),
    ('edge_list_complete',None,'全部关系'),
    ('edge_list_complete',False,'遗漏的关系'),
    ('outcome_kind','UNKNOWN','取值含义'),
    ('treatment','','取值编码'),
    ('outcome','','结果指标'),
    ('context','','对应的时期'),
])
def test_single_study_gap_asks_only_for_the_missing_fact(monkeypatch,field,value,phrase):
    s,e,o,_=setup()
    o['candidate']['study'][field]=value
    before=deepcopy(o['candidate'])
    monkeypatch.setattr(effects,'_compile',lambda *a,**kw:pytest.fail('Missing input reached mathematics'))
    result=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert result['state']=='NEEDS_INPUT' and not result['backend_called']
    assert len(result['clarification_questions'])==1, result['clarification_questions']
    assert phrase in result['clarification_questions'][0]
    assert o['candidate']==before and result['certificate'] is None


def test_unknown_evaluation_rule_asks_selection_basis_without_admitting_a_roster():
    s,e,o,_=setup()
    o['candidate']['target']['population_fixed_before_assignment']['value']=None
    before=deepcopy(o['candidate'])
    result=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert result['clarification_questions']==[reading.population_contract.QUESTION]
    assert result['state']=='NEEDS_INPUT' and not result['backend_called']
    assert o['candidate']==before


@pytest.mark.parametrize('qid',['q1','q2'])
@pytest.mark.parametrize('population',['all','subset','single'])
def test_business_population_and_signed_terms_match_exhaustive_assignment_oracle(qid,population):
    s,e,o,p=setup(qid,population=population)
    assert e['reader_id']==effects.FAMILY and e['effect_fact_contract']==reading.VERSION
    body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    Draft202012Validator(body['output_schema']).validate(o['candidate'])
    assert p['state']=='REVIEW_REQUIRED' and all(v=='PENDING' for v in p['plan_worksheet']['decisions'].values())
    r=dispatch.execute(s,qid,**o,**approval_records(p))
    assert r['state']=='POINT' and r['independent_replay'] is True, r.get('reason_code')
    assert r['primary_method']=='network.randomized.local_contrast' and r['mathematical_claim']['numeric_value'] is None
    c=o['candidate'];nodes=c['study']['nodes'];target=c['target'];rates=c['assignment']['probabilities']
    # Independent enumeration allows Y_i to vary within an exposure group.
    # It therefore also catches accidentally substituting an exposure-sufficient
    # or a fixed-policy target for the requested design-standardized target.
    def moment(n,a,e):
        i=nodes.index(n);neighbours={nodes.index(v) for edge in c['study']['edges'] if n in edge for v in edge if v!=n}
        mass=Fraction(0);total=Fraction(0)
        for z in product((0,1),repeat=len(nodes)):
            if z[i]!=a or int(2*sum(z[j] for j in neighbours)>len(neighbours))!=e:continue
            prob=Fraction(1)
            for name,t in zip(nodes,z):prob*=Fraction(rates[name]) if t else 1-Fraction(rates[name])
            y=(i+1)+7*z[i]+2*sum(z)+3*z[(i+2)%len(nodes)]*z[(i+3)%len(nodes)]
            mass+=prob;total+=prob*y
        return total/mass,mass
    expected=sum((moment(n,target['first']['own'],target['first']['exposure'])[0]-
                  moment(n,target['second']['own'],target['second']['exposure'])[0] for n in target['population']),Fraction(0))/len(target['population'])
    proof=r['certificate']['results'][0];actual=Fraction(0)
    for arm in proof['constituent_arms']:
        value,mass=moment(arm['node_id'],arm['own_treatment'],arm['exposure_state'])
        assert Fraction(arm['joint_support'])==mass
        actual+=Fraction(arm['coefficient'])*value
    assert actual==expected
    assert {a['node_id'] for a in proof['constituent_arms']}==set(target['population'])
    assert all(a['assumptions_used']==tuple(effects.SCIENCE_DECISIONS[:5]) or set(a['assumptions_used'])==set(effects.SCIENCE_DECISIONS[:5]) for a in r['certificate']['results'])
    assert not r['production_admission'] and not r['estimation_handoff_allowed']


@pytest.mark.parametrize('scenario',['shops','delivery'])
def test_two_question_case_requires_both_results_and_keeps_original_material(scenario):
    case,data=material(scenario=scenario);original=case.model_dump(mode='json')
    s=intake.start(case,reading_format='canonical',fact_format='short_refs')
    s=intake.receive_candidate(s,a0_reference(case,data),request_sha256=s.request_sha256)
    submissions={}
    for qid in ('q1','q2'):
        q=approve(dispatch.prepare_reader(s,qid)['query_worksheet']);e=dispatch.prepare_reader(s,qid,query_review=q)
        o=dict(query_review=q,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
        p=dispatch.inspect_methods(s,qid,**o);a=approval_records(p)
        submissions[qid]=dict(o,**{k:v for k,v in a.items() if k!='research_protocol_selected'})
    review=approve(business_case.prepare_case(s)['case_worksheet'])
    one=business_case.execute_case(s,{'q1':submissions['q1']},case_review=review,research_protocol_selected=True)
    assert one['state']=='CASE_INCOMPLETE' and one['unresolved_query_ids']==['q2']
    both=business_case.execute_case(s,submissions,case_review=review,research_protocol_selected=True)
    assert both['state']=='ALL_QUERIES_IDENTIFIED' and both['point_identified_query_ids']==['q1','q2']
    assert s.case.model_dump(mode='json')==original


@pytest.mark.parametrize('case_kwargs,state,reason',[
    ({'sample_only':True},'NEEDS_INPUT','POPULATION_INFORMATION_NOT_DECLARED'),
    ({'missing_remaining':True},'NEEDS_INPUT','NETWORK_EFFECT_FACTS_INCOMPLETE'),
    ({'post_assignment':True},'ADAPTER_NOT_CONNECTED','DECLARED_EFFECT_SCOPE_EXCLUDES:评价名单在抽签前固定')])
def test_complete_business_negative_materials_never_reach_native_compilation(monkeypatch,case_kwargs,state,reason):
    s,e,o,p=setup(**case_kwargs)
    monkeypatch.setattr(effects,'_compile',lambda *a,**kw:pytest.fail('No mathematical compilation allowed'))
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert (r['state'],r['reason_code'])==(state,reason)
    assert not r['backend_called'] and r['mathematical_claim'] is None and r['certificate'] is None


@pytest.mark.parametrize('mutation,state',[
    ('missing_population','NEEDS_INPUT'),('missing_remaining_source','NEEDS_INPUT'),
    ('unknown_science','NEEDS_INPUT'),('undecided_science','NEEDS_INPUT'),
    ('rejected_science','ADAPTER_NOT_CONNECTED'),('conflicting_science','READING_RECHECK_REQUIRED'),
    ('unknown_exposure','NEEDS_INPUT'),('other_design','ADAPTER_NOT_CONNECTED'),
    ('extra_restriction','ADAPTER_NOT_CONNECTED'),
    ('unequal_exposure_direct','READING_RECHECK_REQUIRED'),('wrong_target_kind','READING_RECHECK_REQUIRED'),
    ('missing_a4_cell','NEEDS_INPUT'),('stale_context','CHECK_BLOCKED'),('unknown_source','CHECK_BLOCKED'),
    ('missing_probability','NEEDS_INPUT'),('single_many_nodes','READING_RECHECK_REQUIRED'),
    ('missing_first_source','NEEDS_INPUT'),('different_context','ADAPTER_NOT_CONNECTED')])
def test_missing_misread_or_outside_scope_readings_block_without_repair(monkeypatch,mutation,state):
    s,e,o,p=setup();c=o['candidate'];t=c['target']
    if mutation=='missing_population':t['population']=None
    elif mutation=='missing_remaining_source':t['remaining_source_ids']=[]
    elif mutation in ('unknown_science','undecided_science','rejected_science','conflicting_science'):
        c['scientific_statements']['consistency']['status']={'unknown_science':'NOT_STATED','undecided_science':'UNDECIDED',
            'rejected_science':'NOT_ADOPTED','conflicting_science':'CONFLICTING'}[mutation]
        if mutation=='unknown_science':c['scientific_statements']['consistency']['source_ids']=[]
    elif mutation=='unknown_exposure':c['exposure']['kind']='UNKNOWN'
    elif mutation=='other_design':c['assignment'].update(kind='OTHER',probabilities=None,fixed_count=None)
    elif mutation=='extra_restriction':c['additional_restrictions']=[dict(text='另要求改变合作关系后比较。',source_ids=t['source_ids'])]
    elif mutation=='unequal_exposure_direct':t['second']['exposure']=0
    elif mutation=='wrong_target_kind':t['kind']='SPILLOVER_EFFECT'
    elif mutation=='missing_a4_cell':c['information'][0]['arm_cells']=[x for x in c['information'][0]['arm_cells'] if not (x['node']=='甲店' and x['own']==1 and x['exposure']==1)]
    elif mutation=='stale_context':c['reference_context']='c000000000000'
    elif mutation=='unknown_source':t['first']['source_ids']=['s9999']
    elif mutation=='missing_probability':c['assignment']['probabilities'].pop('甲店')
    elif mutation=='single_many_nodes':t['aggregation']='SINGLE'
    elif mutation=='missing_first_source':t['first']['source_ids']=[]
    elif mutation=='different_context':t['shared_outcome_and_context']['value']=False
    before=deepcopy(c)
    monkeypatch.setattr(effects,'_compile',lambda *a,**kw:pytest.fail('Blocked before native compilation'))
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']==state,r.get('reason_code')
    assert not r['backend_called'] and r['mathematical_claim'] is None and c==before


@pytest.mark.parametrize('qid',['q1','q2'])
@pytest.mark.parametrize('layer',['plan','reading','science'])
@pytest.mark.parametrize('decision',['PENDING','REJECTED'])
def test_every_independent_review_remains_required(monkeypatch,qid,layer,decision):
    s,e,o,p=setup(qid);a=approval_records(p)
    review=a['plan_review'] if layer=='plan' else a['native_reviews'][effects.METHOD][layer+'_review']
    review.decisions[next(iter(review.decisions))]=decision
    monkeypatch.setattr(effects,'_compile',lambda *a,**kw:pytest.fail('Unreviewed math'))
    r=dispatch.execute(s,qid,**o,**a)
    assert r['state']==('REVIEW_REQUIRED' if decision=='PENDING' else 'CHECK_BLOCKED')
    assert not r['backend_called'] and r['mathematical_claim'] is None


def test_zero_support_is_native_inapplicability_without_partial_or_candidate_fallback():
    s,e,o,_=setup();o['candidate']['assignment']['probabilities']['甲店']='0'
    p=dispatch.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED'
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['backend_called'] and r['state']=='UNSUPPORTED' and not r['independent_replay']
    assert r['mathematical_claim'] is None and r['certificate'] is None
    assert r['partial_fallback_performed'] is False


def test_spillover_direction_is_preserved_and_not_automatically_sorted():
    s,e,o,p=setup('q2');a=dispatch.execute(s,'q2',**o,**approval_records(p))
    o['candidate']['target']['first'],o['candidate']['target']['second']=o['candidate']['target']['second'],o['candidate']['target']['first']
    changed=dispatch.inspect_methods(s,'q2',**o)
    stale=dispatch.execute(s,'q2',**o,**approval_records(p))
    assert stale['state']=='CHECK_BLOCKED' and not stale['backend_called']
    b=dispatch.execute(s,'q2',**o,**approval_records(changed))
    def terms(r):return {(x['node_id'],x['own_treatment'],x['exposure_state']):Fraction(x['coefficient']) for x in r['certificate']['results'][0]['constituent_arms']}
    assert b['state']=='POINT' and terms(a)=={k:-v for k,v in terms(b).items()}


@pytest.mark.parametrize('operator',['NODE_FULL_LAW','FULL_JOINT_LAW'])
def test_existing_full_law_sources_preserve_actual_native_operator(operator):
    s,e,o,_=setup();o['candidate']['information'][0].update(operator=operator,arm_cells=[])
    p=dispatch.inspect_methods(s,'q1',**o);r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='POINT' and r['independent_replay']
    assert r['answers'][0]['native_evidence']['result']['a4_source']['operator']==operator


def test_multiple_sources_not_silently_combined_or_reported_as_absent():
    s,e,o,_=setup();source=o['candidate']['information'][0]
    first,second=deepcopy(source),deepcopy(source)
    first['outcome_nodes']=source['outcome_nodes'][:2];second['outcome_nodes']=source['outcome_nodes'][2:]
    for item in (first,second):item['arm_cells']=[x for x in source['arm_cells'] if x['node'] in item['outcome_nodes']]
    o['candidate']['information']=[first,second]
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='ADAPTER_NOT_CONNECTED' and r['reason_code']=='EFFECT_MULTI_SOURCE_JOINT_ADAPTER_REQUIRED'
    assert not r['backend_called']


def test_failed_replay_or_substituted_native_target_cannot_publish(monkeypatch):
    from pfn_pipeline import identification_business as core
    s,e,o,p=setup();a=approval_records(p)
    original=core.identify_network_business_query
    def wrong(query):
        if isinstance(query,core.EffectsInquiryV21):
            request=replace(query.requests[0],node_weights=((query.requests[0].node_weights[0][0],'1'),))
            return original(replace(query,requests=(request,)))
        return original(query)
    monkeypatch.setattr(core,'identify_network_business_query',wrong)
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']=='CHECK_BLOCKED' and not r['independent_replay'] and r['certificate'] is None
    monkeypatch.setattr(core,'identify_network_business_query',original)
    monkeypatch.setattr(core,'replay_verified_business_outcome',lambda *a,**kw:False)
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']=='CHECK_BLOCKED' and r['mathematical_claim'] is None


def test_recheck_uses_effect_contract_and_cannot_reuse_previous_approval():
    s,e,o,p=setup();bad=deepcopy(o['candidate']);bad['target']['population']=None
    pending=revisions.prepare_recheck(s,'q1',query_review=o['query_review'],candidate=bad,request_sha256=e['request_sha256'])
    assert pending['state']=='REVIEW_REQUIRED' and pending['request'] is None
    assert '/target/population' in pending['feedback_worksheet']['field_paths']
    sheet=pending['feedback_worksheet']
    sources=[k for k,v in sheet['source_catalog'].items() if v['doc_id']=='population']
    feedback=revisions.ReadingFeedback(binding_sha256=sheet['binding_sha256'],authority=sheet['expected_authority'],
        reviewer='Synthetic source reviewer',evidence='Independently checked the original population statement.',
        issues=[dict(field_path='/target/population',kind='OMITTED_OR_MISREAD',source_ids=sources,
            reason='The draft omits the population explicitly stated in the source.')])
    fresh_entry=revisions.prepare_recheck(s,'q1',query_review=o['query_review'],candidate=bad,
        request_sha256=e['request_sha256'],feedback=feedback)
    assert fresh_entry['state']=='READY_TO_READ' and fresh_entry['reader_id']==effects.FAMILY
    assert fresh_entry['request_sha256']!=e['request_sha256']
    _,data=material()
    new=dict(query_review=o['query_review'],candidate=fact_reference(fresh_entry,data),
        request_sha256=fresh_entry['request_sha256'],reading_revision=fresh_entry['reading_revision'])
    change_sheet=dispatch.inspect_methods(s,'q1',**new)['reading_change_worksheet']
    new['change_review']=dict(version='reading-change-review-1',binding_sha256=change_sheet['binding_sha256'],
        authority=change_sheet['expected_authority'],reviewer='Synthetic source reviewer',
        evidence='Independently checked every changed field against the original materials.',
        decisions={k:dict(disposition='ACCEPTED',reason='The synthetic correction agrees with its original source.',
            source_ids=list(change_sheet['source_catalog'])) for k in change_sheet['changes']})
    assert dispatch.execute(s,'q1',**new,**approval_records(p))['state']=='CHECK_BLOCKED'
    fresh_plan=dispatch.inspect_methods(s,'q1',**new)
    result=dispatch.execute(s,'q1',**new,**approval_records(fresh_plan))
    assert result['state']=='POINT' and result['independent_replay']
    assert result['reading_revision']['steps'][0]['candidate']==bad
    from cfm_id_llm.wire_type_diagnostics import diagnose
    invalid=deepcopy(bad);invalid['target']['first']['own']='1'
    assert any(x['field_path']=='/target/first/own' for x in diagnose(e,invalid))


def test_changed_effect_prompt_rejects_old_request_and_approvals(monkeypatch):
    s,e,o,p=setup();old=approval_records(p)
    monkeypatch.setattr(reading,'SYSTEM',reading.SYSTEM+' Explicit changed reading instructions.')
    blocked=dispatch.execute(s,'q1',**o,**old)
    assert blocked['state']=='CHECK_BLOCKED' and not blocked['backend_called']
    fresh=dispatch.prepare_reader(s,'q1',query_review=o['query_review'])
    assert fresh['request_sha256']!=e['request_sha256']
    _,data=material()
    new=dict(query_review=o['query_review'],candidate=fact_reference(fresh,data),request_sha256=fresh['request_sha256'])
    assert dispatch.execute(s,'q1',**new,**old)['state']=='CHECK_BLOCKED'
    plan=dispatch.inspect_methods(s,'q1',**new)
    result=dispatch.execute(s,'q1',**new,**approval_records(plan))
    assert result['state']=='POINT' and result['independent_replay']
