"""Presentation can change; source review and native admission cannot weaken."""
import json
from copy import deepcopy
from fractions import Fraction
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_dispatch as dispatch,network_effect_dispatch as effects
from cfm_id_llm import network_effect_reading as reading
from examples.network_effect_dispatch_reference import setup,approval_records
from evaluation.network_effect_citation_cases import CASES,setup as case_setup


def test_request_presents_facts_before_citations_without_changing_answer_contract():
    s,e,o,p=setup();body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    schema=body['output_schema']
    assert body['source_coverage_contract']['emission_order']=='facts_then_local_sources'
    for name,groups in reading.CITATION_GROUPS.items():
        keys=list(schema['$defs'][name]['properties']);citations=set(groups)
        assert max(keys.index(k) for k in keys if k not in citations)<min(keys.index(k) for k in citations)
    raw=deepcopy(o['candidate'])
    def reverse(v):
        if isinstance(v,dict):return {k:reverse(x) for k,x in reversed(list(v.items()))}
        if isinstance(v,list):return [reverse(x) for x in v]
        return v
    shuffled=reverse(raw)
    for candidate in (raw,shuffled):
        Draft202012Validator(schema).validate(candidate)
        assert reading.parse(e['bundle'],candidate,binding=e['fact_binding_sha256'])==reading.parse(e['bundle'],raw,binding=e['fact_binding_sha256'])
    assert raw==o['candidate'] and shuffled==raw


@pytest.mark.parametrize('field',['first','second','population','background'])
def test_valid_coordinates_and_real_but_insufficient_citations_require_rejection(field,monkeypatch):
    s,e,o,p=setup();raw=o['candidate'];catalog=reading.reference_catalog(e['bundle'],binding=e['fact_binding_sha256'])
    intro=[k for k,v in catalog['aliases'].items() if v['doc_id']=='study']
    if field in ('first','second'):raw['target'][field]['source_ids']=intro
    elif field=='population':raw['target']['source_ids']=intro
    else:raw['study']['source_ids']=intro
    p=dispatch.inspect_methods(s,'q1',**o);assert p['state']=='REVIEW_REQUIRED'
    a=approval_records(p);r=a['native_reviews']['network.randomized.local_contrast']['reading_review'].model_dump(mode='json')
    r['decisions']['source_entailment']='REJECTED';r['evidence']='Explicit synthetic audit rejects local references: an introduction does not specify the requested comparison, population/aggregation or shared background.'
    a['native_reviews']['network.randomized.local_contrast']['reading_review']=dispatch.DispatchReview.model_validate(r)
    before=deepcopy(raw)
    monkeypatch.setattr(effects,'_compile',lambda *a,**kw:pytest.fail('Rejected source review must not reach math'))
    result=dispatch.execute(s,'q1',**o,**a)
    assert result['state']=='CHECK_BLOCKED' and not result['backend_called'] and result['mathematical_claim'] is None
    assert raw==before


@pytest.mark.parametrize('name',CASES)
def test_complete_frozen_network_business_keeps_positive_and_negative_contracts(name):
    s,e,data,raw=case_setup(name);before=deepcopy(raw)
    Draft202012Validator(json.JSONDecoder().raw_decode(e['request']['user'])[0]['output_schema']).validate(raw)
    opts=dict(query_review=e['query_review'],candidate=raw,request_sha256=e['request_sha256'])
    plan=dispatch.inspect_methods(s,'q1',**opts)
    expected={'service_context_pending':'NEEDS_INPUT','grocery_science_pending':'NEEDS_INPUT','library_extra':'ADAPTER_NOT_CONNECTED'}.get(name,'POINT')
    a=approval_records(plan) if expected=='POINT' else dict(research_protocol_selected=True)
    result=dispatch.execute(s,'q1',**opts,**a)
    assert result['state']==expected and raw==before
    if expected!='POINT':
        assert not result['backend_called'] and result['mathematical_claim'] is None
        if name=='service_context_pending':assert raw['target']['shared_outcome_and_context']['value'] is None
        elif name=='grocery_science_pending':assert raw['scientific_statements']['assignment_outcome_independence']['status']=='UNDECIDED'
        else:assert raw['additional_restrictions'] and '12' in raw['additional_restrictions'][0]['text']
    else:
        assert result['independent_replay']
        t=result['mathematical_claim']['target'];assert t['evaluation_population']==data['members']
        assert (t['first'],t['second'])==(list(data['arms'][0]),list(data['arms'][1]))
        for arm in result['certificate']['results'][0]['constituent_arms']:
            sign=1 if (arm['own_treatment'],arm['exposure_state'])==data['arms'][0] else -1
            assert Fraction(arm['coefficient'])==Fraction(sign,len(data['members']))
