"""Public source dependencies must neither edit candidates nor grant admission."""
from copy import deepcopy
import json
import pytest
from cfm_id import business_intake as intake,business_dispatch as dispatch
from cfm_id.fact_reading_revision import prepare_recheck
from cfm_id_llm import network_source_dependencies as deps,network_effect_reading as reading
from examples.network_effect_dispatch_reference import setup,approval_records,fact_reference
from examples.business_dispatch_reference import approve
from tests_gateway.test_fact_reading_revision import feedback,accept_changes


def configured():
    old,e,o,p=setup();s=intake.configure_network_fact_contract(old,deps.CONTRACT)
    q=approve(dispatch.prepare_reader(s,'q1')['query_worksheet'])
    new=dispatch.prepare_reader(s,'q1',query_review=q)
    raw=deepcopy(o['candidate']);raw['reference_context']=reading.reference_catalog(new['bundle'],binding=new['fact_binding_sha256'])['context']
    opts=dict(query_review=q,candidate=raw,request_sha256=new['request_sha256'])
    return s,e,new,opts


def types(node):
    if isinstance(node,dict):return {k:types(v) for k,v in node.items() if k!='description'}
    if isinstance(node,list):return [types(v) for v in node]
    return node


def test_schema_types_sources_and_values_unchanged():
    s,old,e,o=configured();base=reading.make_request(e['bundle'],binding=e['fact_binding_sha256'])
    before=json.loads(base['user']);after=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    assert types(before['output_schema'])==types(after['output_schema'])
    assert before['source_catalog']==after['source_catalog']
    candidate=deepcopy(o['candidate']);assert reading.parse(e['bundle'],candidate,binding=e['fact_binding_sha256'])
    assert candidate==o['candidate']
    schema=after['output_schema'];rows=deps.field_constraints(['/assignment/source_ids','/information/0/source_ids','/target/first/source_ids'],request=e['request'])
    assert {r['field_path'] for r in rows}=={'/assignment/source_ids','/information/*/source_ids','/target/first/source_ids'}
    assert next(r['description'] for r in rows if r['field_path']=='/target/first/source_ids')==schema['$defs']['LocalArm']['properties']['source_ids']['description']
    assert deps.NAMES in schema['$defs']['Assignment']['properties']['source_ids']['description']
    assert deps.apply(deps.apply(base))==deps.apply(base)


def test_effect_recheck_transmits_current_public_rules_but_not_private_reason():
    s,old,e,o=configured();bad=deepcopy(o['candidate'])
    bad['target']['first']['source_ids']=bad['study']['source_ids']
    opts=dict(o,candidate=bad);w=prepare_recheck(s,'q1',**opts)['feedback_worksheet']
    new=prepare_recheck(s,'q1',**opts,feedback=feedback(w,path='/target/first/source_ids',doc='study'))
    assert new['state']=='READY_TO_READ'
    public=json.loads(new['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    assert public['public_field_constraints']==deps.field_constraints(['/target/first/source_ids'],request=e['request'])
    assert 'PRIVATE_REASON_NOT_SENT' not in new['request']['user'] and public['previous_candidate']==bad
    fresh=deepcopy(o['candidate']);fresh['reference_context']=reading.reference_catalog(new['bundle'],binding=new['fact_binding_sha256'])['context']
    revised=dict(query_review=o['query_review'],candidate=fresh,request_sha256=new['request_sha256'],reading_revision=new['reading_revision'])
    p=dispatch.inspect_methods(s,'q1',**revised)
    assert p['reason_code']=='INDEPENDENT_READING_CHANGE_REVIEW_REQUIRED' and not p['backend_called']
    revised['change_review']=accept_changes(p['reading_change_worksheet'])
    pending=dispatch.execute(s,'q1',**revised,research_protocol_selected=True)
    assert pending['state']=='REVIEW_REQUIRED' and not pending['backend_called']
    r=dispatch.execute(s,'q1',**revised,**approval_records(dispatch.inspect_methods(s,'q1',**revised)))
    assert r['state']=='POINT' and r['independent_replay']


@pytest.mark.parametrize('variant,expected',[('full','POINT'),('sample','NEEDS_INPUT'),('refused','ADAPTER_NOT_CONNECTED'),('rejected_source','CHECK_BLOCKED')])
def test_positive_missing_refusal_and_rejected_source_keep_native_boundaries(variant,expected):
    s,_,e,o=configured()
    if variant=='sample':o['candidate']['information']=[dict(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',outcome_nodes=o['candidate']['study']['nodes'],arm_cells=[],source_ids=o['candidate']['information'][0]['source_ids'])]
    elif variant=='refused':o['candidate']['scientific_statements']['consistency']['status']='NOT_ADOPTED'
    p=dispatch.inspect_methods(s,'q1',**o)
    a=approval_records(p) if variant in ('full','rejected_source') else dict(research_protocol_selected=True)
    if variant=='rejected_source':
        rec=a['native_reviews']['network.randomized.local_contrast']['reading_review'].model_dump(mode='json');rec['decisions']['source_entailment']='REJECTED'
        a['native_reviews']['network.randomized.local_contrast']['reading_review']=rec
    before=deepcopy(o['candidate']);r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']==expected and o['candidate']==before
    assert bool(r['independent_replay'])==(variant=='full')
    if variant!='full':assert not r['backend_called']


@pytest.mark.parametrize('kind',['point','partial'])
def test_existing_policy_contrast_contract_gets_updated_endpoint_rules(kind):
    from examples.network_contrast_dispatch_reference import setup as contrast,approval_records as approvals
    s,e,o=contrast(kind,profile=deps.CONTRACT)
    p=dispatch.inspect_methods(s,'q1',**o)
    body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    rules=deps.field_constraints(['/target/first/source_ids'],request=e['request'])
    assert len(rules)==1 and rules[0]['description']==body['output_schema']['$defs']['PolicyEndpoint']['properties']['source_ids']['description']
    r=dispatch.execute(s,'q1',**o,**approvals(p))
    assert r['state']==kind.upper() and r['independent_replay']


def test_old_effect_request_keeps_old_recheck_contract_and_new_profile_rejects_old_review():
    s,e,o,p=setup();w=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    old=prepare_recheck(s,'q1',**o,feedback=feedback(w))
    public=json.loads(old['request']['user'].split('独立复查定位（不是新增事实）：\n')[1])
    assert 'public_field_constraints' not in public
    new=intake.configure_network_fact_contract(s,deps.CONTRACT)
    assert intake.prepare_request(new)==intake.prepare_request(s)
    assert dispatch.prepare_reader(new,'q1',query_review=o['query_review'])['state']=='CHECK_BLOCKED'
