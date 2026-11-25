"""R3-Full wiring: scientific permission, exact native target and replay."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as F
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_dispatch as d,business_intake as intake,business_case,capability_registry as registry
from cfm_id import network_observational_policy_dispatch as bridge
from cfm_id_llm import network_observational_policy_reading as reader
from cfm_id_llm.wire_type_diagnostics import diagnose
from cfm_id_bridge.scientific_binding import sha
from examples.network_observational_policy_reference import setup,material,a0_reference,fact_reference,approval_records,approve


def execute(s,o):
    p=d.inspect_methods(s,'q1',**o);assert p['state']=='REVIEW_REQUIRED',p
    return p,d.execute(s,'q1',**o,**approval_records(p))


@pytest.mark.parametrize('scene',['care','depots'])
def test_complete_business_selects_r3_without_user_route_and_replays(scene):
    s,e,o=setup(scene);raw=deepcopy(o['candidate']);body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    Draft202012Validator(body['output_schema']).validate(raw)
    assert e['reader_id']==bridge.FAMILY and e['observational_fact_contract']==reader.VERSION
    p,r=execute(s,o)
    assert r['state']=='POINT' and r['primary_method']==bridge.METHOD and r['independent_replay'] and raw==o['candidate']
    assert r['certificate']['target_observational_probability']=='1/2'
    native=r['answers'][0]['native_evidence']
    assert native['signature'] is None and native['sufficiency'] is None
    assert native['study']['observation_regime']=='observational' and native['study']['assignment_design_json'] is None
    assert {a['name'] for a in native['assumptions']}==set(bridge.BASE_CONDITIONS)
    assert native['target']['policy_assignment']==p['proposed_target']['assignment']
    assert native['source']['outcome_nodes']==raw['information'][0]['outcome_nodes']
    assert r['mathematical_claim']['numeric_value'] is None and not r['estimation_handoff_allowed']
    assert not r['production_admission']
    a=approval_records(p)
    whole=business_case.execute_case(s,{'q1':dict(o,**{k:v for k,v in a.items() if k!='research_protocol_selected'})},
        case_review=approve(business_case.prepare_case(s)['case_worksheet']),research_protocol_selected=True)
    assert len(whole['results'])==1 and whole['results'][0]['result']['independent_replay']


def test_registered_scope_and_scientific_conditions_match_native_contract():
    from pfn_pipeline.identification_observational_r3 import REQUIRED_A5,MAX_FINITE_NODES
    assert bridge.BASE_CONDITIONS==REQUIRED_A5 and MAX_FINITE_NODES==12
    b=registry.reader_for('UNIT_NETWORK','FIXED_POLICY_VALUE',assignment_family='OBSERVATIONAL')
    assert b.reader_id==bridge.FAMILY and b.assignment_family=='OBSERVATIONAL'
    assert registry.reader_for('UNIT_NETWORK','FIXED_POLICY_VALUE').reader_id=='NETWORK_FIXED_POLICY_FACTS'
    for kind in ('DIRECT_EFFECT','SPILLOVER_EFFECT','LOCAL_TOTAL_EFFECT'):
        assert registry.reader_for('UNIT_NETWORK',kind,assignment_family='OBSERVATIONAL').reader_id=='NETWORK_OBSERVATIONAL_EFFECT_FACTS'
    # A local contrast is not an observational comparison of complete policies.
    assert registry.reader_for('UNIT_NETWORK','TOTAL_EFFECT',assignment_family='OBSERVATIONAL') is None
    assert registry.reader_for('VARIABLE_DAG','INTERVENTIONAL_DISTRIBUTION',assignment_family='OBSERVATIONAL').reader_id=='VARIABLE_DAG_FACTS'
    data=registry.inventory()['separate_native_entries'][0]
    from cfm_id.method_compat import native_id
    assert {native_id(bridge.METHOD),native_id(bridge.SIGNATURE_METHOD)} <= set(data['common_business_routes'])
    assert native_id(bridge.SIGNATURE_METHOD) not in data['native_only_routes']


def test_formula_in_correlated_non_exposure_sufficient_potential_world():
    s,e,o=setup();p,r=execute(s,o);raw=o['candidate'];nodes=raw['study']['nodes'];z=p['proposed_target']['assignment']
    law={tuple(row['assignment'][n] for n in nodes):F(row['probability']) for row in raw['information'][0]['assignment_masses']}
    marginal=[sum(prob*t[i] for t,prob in law.items()) for i in range(len(nodes))]
    assert law[tuple(z)]!=marginal[0]*marginal[1]*marginal[2]
    # Entire potential table is deterministic at W, hence independent of T.
    # Node zero depends on the non-neighbor's treatment; no exposure sufficiency.
    mean=lambda i,t:F(i+1,10)+F(t[0],10)+F(t[-1],5)
    assert mean(0,(0,0,0))!=mean(0,(0,0,1))
    for i,n in enumerate(nodes):
        conditional=sum(prob*mean(i,t) for t,prob in law.items() if list(t)==z)/law[tuple(z)]
        assert conditional==mean(i,z)
    assert len(r['certificate']['required_observables'])==len(nodes)


@pytest.mark.parametrize('layer',['query','plan','reading','science'])
@pytest.mark.parametrize('decision',['PENDING','REJECTED'])
def test_all_review_layers_block_before_compilation(monkeypatch,layer,decision):
    s,e,o=setup();p=d.inspect_methods(s,'q1',**o);a=approval_records(p)
    review=o['query_review'] if layer=='query' else a['plan_review'] if layer=='plan' else a['native_reviews'][bridge.METHOD][layer+'_review']
    key='full_vector_conditional_exchangeability' if layer=='science' else next(iter(review.decisions))
    review.decisions[key]=decision
    monkeypatch.setattr(bridge,'_compile',lambda *a,**kw:pytest.fail('review before compile'))
    r=d.execute(s,'q1',**o,**a)
    assert r['state']==('REVIEW_REQUIRED' if decision=='PENDING' else 'CHECK_BLOCKED') and not r['backend_called']


@pytest.mark.parametrize('defect,expected',[
    ('unknown_exchangeability','NEEDS_INPUT'),('refused_exchangeability','ADAPTER_NOT_CONNECTED'),
    ('sample_only','NEEDS_INPUT'),('unknown_information','NEEDS_INPUT'),('empty_information','NEEDS_INPUT'),
    ('missing_policy','NEEDS_INPUT'),('missing_population','NEEDS_INPUT'),('missing_context','NEEDS_INPUT'),
    ('other_conditioning','ADAPTER_NOT_CONNECTED'),('wrong_a4_context','ADAPTER_NOT_CONNECTED'),
    ('incomplete_table','NEEDS_INPUT'),('table_not_confirmed','NEEDS_INPUT'),('mean_coverage_missing','NEEDS_INPUT'),
    ('incomplete_row','NEEDS_INPUT'),('probability_missing','NEEDS_INPUT'),('uncovered_node','NEEDS_INPUT'),
    ('extra_constraint','ADAPTER_NOT_CONNECTED'),('two_population_models','ADAPTER_NOT_CONNECTED'),
    ('randomized_facts','READING_RECHECK_REQUIRED'),('unknown_regime','NEEDS_INPUT'),
    ('unknown_source','CHECK_BLOCKED'),('missing_row_reference','CHECK_BLOCKED'),('stale_context','CHECK_BLOCKED'),
    ('probability_not_normalized','CHECK_BLOCKED'),('marginal_probabilities','CHECK_BLOCKED'),
    ('duplicate_assignment','CHECK_BLOCKED'),('sample_as_population','CHECK_BLOCKED'),
    ('noncanonical_probability','CHECK_BLOCKED'),('zero_mass_row','CHECK_BLOCKED'),('boolean_treatment','CHECK_BLOCKED'),
    ('randomization_license','CHECK_BLOCKED'),('unknown_node','CHECK_BLOCKED')])
def test_gaps_and_unsupported_models_are_preserved_without_backend(monkeypatch,defect,expected):
    s,e,o=setup(**(dict(sample_only=True) if defect=='sample_only' else {}));c=o['candidate'];source=c['information'][0]
    if defect=='unknown_exchangeability':c['assumptions']['full_vector_conditional_exchangeability']['value']=None
    elif defect=='refused_exchangeability':c['assumptions']['full_vector_conditional_exchangeability']['value']=False
    elif defect=='unknown_information':source['availability']='UNKNOWN'
    elif defect=='empty_information':c['information']=[]
    elif defect=='missing_policy':c['target']['assignment'].pop(c['study']['nodes'][-1])
    elif defect=='missing_population':c['target']['population']=None
    elif defect=='missing_context':c['conditioning']['definition']=None
    elif defect=='other_conditioning':c['conditioning']['kind']='OTHER'
    elif defect=='wrong_a4_context':source['same_study_and_conditioning']['value']=False
    elif defect=='incomplete_table':source['assignment_masses'].pop();source['complete_positive_assignment_support']['value']=False
    elif defect=='table_not_confirmed':source['complete_positive_assignment_support']['value']=None
    elif defect=='mean_coverage_missing':source['means_for_all_positive_assignments']['value']=None
    elif defect=='incomplete_row':source['assignment_masses'][0]['assignment'].pop(c['study']['nodes'][0])
    elif defect=='probability_missing':source['assignment_masses'][0]['probability']=None
    elif defect=='uncovered_node':source['outcome_nodes'].pop()
    elif defect=='extra_constraint':c['additional_restrictions']=[dict(text='另有跨对象结果均值的线性限制。',source_ids=c['study']['source_ids'])]
    elif defect=='two_population_models':c['information'].append(deepcopy(source))
    elif defect=='randomized_facts':c['regime']['kind']='RANDOMIZED'
    elif defect=='unknown_regime':c['regime']['kind']='UNKNOWN'
    elif defect=='unknown_source':c['target']['source_ids']=['s9999']
    elif defect=='missing_row_reference':source['assignment_masses'][0]['source_ids']=[]
    elif defect=='stale_context':c['reference_context']='c000000000000'
    elif defect=='probability_not_normalized':source['assignment_masses'][0]['probability']='1/8'
    elif defect=='marginal_probabilities':source['probabilities']={n:'1/2' for n in c['study']['nodes']}
    elif defect=='duplicate_assignment':source['assignment_masses'].append(deepcopy(source['assignment_masses'][0]))
    elif defect=='sample_as_population':source['operator']='FINITE_SAMPLE'
    elif defect=='noncanonical_probability':source['assignment_masses'][0]['probability']='2/8'
    elif defect=='zero_mass_row':source['assignment_masses'][0]['probability']='0'
    elif defect=='boolean_treatment':source['assignment_masses'][0]['assignment'][c['study']['nodes'][0]]=True
    elif defect=='randomization_license':c['assumptions']['full_vector_randomization']=c['assumptions'].pop('full_vector_conditional_exchangeability')
    elif defect=='unknown_node':c['target']['assignment']['outside']=1
    before=deepcopy(c);monkeypatch.setattr(bridge,'_compile',lambda *a,**kw:pytest.fail('no ready model'))
    r=d.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']==expected,(defect,r)
    assert not r['backend_called'] and r['mathematical_claim'] is None and c==before


def test_zero_support_is_not_nonidentification_and_never_tries_signature(monkeypatch):
    from pfn_pipeline import identification_business as core
    s,e,o=setup(zero_support=True);original=core.identify_network_business_query;calls=[]
    def capture(q):
        assert isinstance(q,core.ObservationalPolicyInquiryV23) and q.signature is None and q.sufficiency is None
        calls.append(q);return original(q)
    monkeypatch.setattr(core,'identify_network_business_query',capture)
    p,r=execute(s,o)
    assert len(calls)==1 and r['state']=='UNSUPPORTED' and r['reason_code']=='ZERO_OBSERVATIONAL_FULL_ASSIGNMENT_SUPPORT'
    assert r['backend_called'] and not r['independent_replay'] and not r['nonidentification_proved'] and not r['partial_fallback_performed']


@pytest.mark.parametrize('defect',['wrong_target','wrong_weights','different_source','different_context','replay_false','rehashed_coefficient','mutated_input','mutated_replay'])
def test_native_evidence_must_match_reviewed_inputs_and_independent_replay(monkeypatch,defect):
    from pfn_pipeline import identification_business as core
    from pfn_pipeline.identification_observational_r3 import _payload,_sha
    from pfn_pipeline.network_inquiry_shadow import fixed_policy_target_from_context
    s,e,o=setup();original=core.identify_network_business_query
    def corrupt(q):
        if defect=='wrong_target':q=replace(q,target=fixed_policy_target_from_context(q.study,tuple(0 for _ in q.study.node_order),unit_weights=q.target.unit_weights,authority='TRUSTED_FIXTURE'))
        elif defect=='wrong_weights':q=replace(q,target=fixed_policy_target_from_context(q.study,q.target.policy_assignment,unit_weights=('1','0','0'),authority='TRUSTED_FIXTURE'))
        elif defect=='different_source':q=replace(q,source=replace(q.source,provenance=q.source.provenance+' other source'))
        elif defect=='different_context':q=replace(q,target=replace(q.target,context='another W'))
        result=original(q)
        if defect=='rehashed_coefficient':
            bad=replace(result.result,node_weights=('1','0','0'));bad=replace(bad,certificate_sha256=_sha(_payload(bad)))
            result=replace(result,result=bad)
        if defect=='mutated_input':q.assumptions[0].evidence.append('unreviewed appended evidence')
        return result
    monkeypatch.setattr(core,'identify_network_business_query',corrupt)
    if defect=='replay_false':monkeypatch.setattr(core,'replay_verified_business_outcome',lambda _:False)
    if defect=='mutated_replay':
        def bad_replay(result):result.result.assumptions[0].evidence.append('changed during verification');return True
        monkeypatch.setattr(core,'replay_verified_business_outcome',bad_replay)
    p,r=execute(s,o)
    # Invalid native scope may itself be refused by the unchanged Core.
    assert r['state'] in (('UNSUPPORTED','CHECK_BLOCKED') if defect=='different_context' else ('CHECK_BLOCKED',)),r
    assert r['backend_called'] and not r['independent_replay'] and r['mathematical_claim'] is None


def test_extra_sample_record_does_not_replace_or_promote_population_source():
    s,e,o=setup();sample=deepcopy(o['candidate']['information'][0]);sample.update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE')
    o['candidate']['information'].insert(0,sample);p,r=execute(s,o)
    assert p['methods'][0]['source_index']==1 and r['state']=='POINT'
    assert p['facts']['information'][0]['availability']=='FINITE_SAMPLE'


@pytest.mark.parametrize('field',['conditioning','policy','source'])
def test_changed_target_or_source_invalidates_previous_approval(field):
    s,e,o=setup();p=d.inspect_methods(s,'q1',**o);old=approval_records(p)
    if field=='conditioning':o['candidate']['conditioning']['definition']='a different explicitly fixed background'
    elif field=='policy':o['candidate']['target']['assignment']={n:0 for n in o['candidate']['study']['nodes']}
    else:o['candidate']['information'][0]['assignment_masses'][0]['source_ids']=o['candidate']['study']['source_ids']
    r=d.execute(s,'q1',**o,**old);assert r['state']=='CHECK_BLOCKED' and not r['backend_called']


def test_recheck_reuses_original_sources_and_requires_complete_change_and_new_science():
    from cfm_id.fact_reading_revision import prepare_recheck
    from tests_gateway.test_fact_reading_revision import feedback,accept_changes
    s,e,o=setup();plan=d.inspect_methods(s,'q1',**o);old=approval_records(plan)
    bad=deepcopy(o);bad['candidate']['information'][0]['means_for_all_positive_assignments']['value']=None
    sheet=prepare_recheck(s,'q1',**bad)['feedback_worksheet']
    r=prepare_recheck(s,'q1',**bad,feedback=feedback(sheet,path='/information/0/means_for_all_positive_assignments',doc='information'))
    assert r['state']=='READY_TO_READ' and r['reader_id']==bridge.FAMILY and r['bundle']==e['bundle']
    _,data=material();new=dict(query_review=o['query_review'],candidate=fact_reference(r,data),request_sha256=r['request_sha256'],reading_revision=r['reading_revision'])
    pending=d.execute(s,'q1',**new,research_protocol_selected=True)
    assert pending['state']=='REVIEW_REQUIRED' and not pending['backend_called']
    new['change_review']=accept_changes(pending['reading_change_worksheet'])
    assert d.execute(s,'q1',**new,**old)['state']=='CHECK_BLOCKED'
    p,result=execute(s,new);assert result['state']=='POINT' and result['independent_replay']
    assert result['reading_revision']['steps'][0]['candidate']==bad['candidate']


def test_format_diagnostics_use_actual_observational_schema():
    s,e,o=setup();o['candidate']['regime']['kind']='BAD_ENUM'
    rows=diagnose(e,o['candidate']);assert any(r['field_path']=='/regime/kind' and 'OBSERVATIONAL' in r['allowed_literals'] for r in rows)


def test_save_restore_and_json_native_reviews_preserve_target_and_result(tmp_path):
    s,e,o=setup();p,r=execute(s,o);intake.save(s,tmp_path/'session.json');restored=intake.restore(tmp_path/'session.json')
    assert d.prepare_reader(restored,'q1',query_review=o['query_review'])==e
    a=approval_records(p);a['native_reviews']={m:{k:v.model_dump(mode='json') for k,v in pair.items()} for m,pair in a['native_reviews'].items()}
    assert d.execute(restored,'q1',**o,**a)==r


def test_external_authority_does_not_gain_synthetic_execution():
    s,e,o=setup();o['query_review']=o['query_review'].model_copy(update={'authority':'EXTERNAL_RESEARCH_REVIEW'})
    e=d.prepare_reader(s,'q1',query_review=o['query_review']);_,data=material();o.update(candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
    p=d.inspect_methods(s,'q1',**o);a=approval_records(p)
    a['plan_review']=a['plan_review'].model_copy(update={'authority':'EXTERNAL_RESEARCH_REVIEW'})
    a['native_reviews'][bridge.METHOD]={k:v.model_copy(update={'authority':'EXTERNAL_RESEARCH_REVIEW'}) for k,v in a['native_reviews'][bridge.METHOD].items()}
    r=d.execute(s,'q1',**o,**a)
    assert r['state']=='ADAPTER_NOT_CONNECTED' and not r['backend_called']


@pytest.mark.parametrize('a0_state,sample_only,expected',[
    ('MISSING',False,'READING_RECHECK_REQUIRED'),('MISSING',True,'NEEDS_INPUT'),
    ('UNKNOWN',False,'REVIEW_REQUIRED'),('STATED',False,'REVIEW_REQUIRED')])
def test_reviewed_population_state_consistency_uses_existing_contract(a0_state,sample_only,expected):
    from tests_gateway.test_inline_evidence_slots import wire,receive
    from tests_gateway.test_business_field_review import sheet,record,submit
    case,data=material(sample_only=sample_only);raw=wire(a0_reference(case,data))
    refs=raw['common']['analysis_unit']['refs']
    raw['common']['available_information']=('UNKNOWN' if a0_state=='UNKNOWN' else
        dict(state='MISSING',reason='只有有限记录，缺少总体信息',refs=refs) if a0_state=='MISSING' else
        dict(state='STATED',value='研究材料声明了总体信息算子',refs=refs))
    s=receive(case,raw,profile='local-role-ownership-4')
    review=submit(s,record(sheet(s)))['query_review']
    e=d.prepare_reader(s,'q1',query_review=review)
    assert e['reader_id']==bridge.FAMILY and 'reviewed_local_request' not in e
    o=dict(query_review=review,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])
    before=deepcopy(o['candidate']);p=d.inspect_methods(s,'q1',**o)
    assert p['state']==expected and not p['backend_called'] and o['candidate']==before
    assert not d.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    if expected=='READING_RECHECK_REQUIRED':
        assert p['reason_code']=='POPULATION_INFORMATION_DISAGREES_WITH_REVIEWED_A0'
        assert not p['methods'] and 'plan_worksheet' not in p
    elif expected=='REVIEW_REQUIRED':
        r=d.execute(s,'q1',**o,**approval_records(p));assert r['state']=='POINT' and r['independent_replay']


@pytest.mark.parametrize('disposition,expected',[
    ('PENDING','REVIEW_REQUIRED'),('MATERIAL_GAP','NEEDS_INPUT'),
    ('READING_ERROR','READING_RECHECK_REQUIRED'),('NONBLOCKING_COMMENT','POINT'),
    ('DEFER_TO_MATHEMATICS','POINT')])
def test_notes_reuse_independent_adjudication_and_never_approve_science(disposition,expected):
    s,e,o=setup();o['candidate']['unresolved']=[dict(text='需要审核总体算子的同一背景声明。',source_ids=o['candidate']['information'][0]['source_ids'])]
    before=deepcopy(o['candidate']);p=d.inspect_methods(s,'q1',**o);w=p['note_review_worksheet']
    o['note_review']=dict(version=w['version'],binding_sha256=w['binding_sha256'],authority=w['expected_authority'],
        reviewer='Independent fixture reviewer',evidence='Independently examine original declared population source scope.',
        decisions={k:dict(disposition=disposition,reason='Review original scope statement, preserving all typed requirements.',
            source_ids=list(w['source_catalog'])[:1]) for k in w['decisions']})
    p=d.inspect_methods(s,'q1',**o)
    assert not d.execute(s,'q1',**o,research_protocol_selected=True)['backend_called']
    r=d.execute(s,'q1',**o,**(approval_records(p) if p.get('methods') else dict(research_protocol_selected=True)))
    assert r['state']==expected and r['independent_replay']==(expected=='POINT') and o['candidate']==before


def test_finite_native_enumeration_limit_is_checked_before_backend(monkeypatch):
    s,e,o=setup();c=o['candidate'];extra=[str(i) for i in range(10)];c['study']['nodes']+=extra
    c['target']['assignment'].update({n:0 for n in extra})
    for row in c['information'][0]['assignment_masses']:row['assignment'].update({n:0 for n in extra})
    monkeypatch.setattr(bridge,'_compile',lambda *a,**kw:pytest.fail('unsupported node count'))
    r=d.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='ADAPTER_NOT_CONNECTED' and r['reason_code']=='FINITE_OBSERVATIONAL_SUPPORT_ENUMERATION_LIMIT'
    assert not r['backend_called']


def test_explicit_research_protocol_selection_remains_required():
    s,e,o=setup();p=d.inspect_methods(s,'q1',**o);a=approval_records(p);a['research_protocol_selected']=False
    r=d.execute(s,'q1',**o,**a)
    assert r['state']=='REVIEW_REQUIRED' and not r['backend_called']
