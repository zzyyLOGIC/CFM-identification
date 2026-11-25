"""Citation duties are explicit, schema-bound and never scientific approval."""
from copy import deepcopy
import json
from fractions import Fraction
import pytest
from jsonschema import Draft202012Validator
from cfm_id_llm import network_effect_reading as reading,source_coverage_contract as coverage
from cfm_id import business_dispatch as dispatch,network_effect_dispatch as effects
from examples.network_effect_dispatch_reference import setup,approval_records
from evaluation.network_effect_source_cases import CASES,setup as case_setup


def test_annotation_only_adds_descriptions_and_preserves_parser_and_sources():
    schema=reading.NetworkEffectReading.model_json_schema();original=deepcopy(schema)
    annotated,contract=coverage.annotate(schema,reading.CITATION_GROUPS)
    def without_descriptions(x):
        if isinstance(x,dict):return {k:without_descriptions(v) for k,v in x.items() if k!='description'}
        if isinstance(x,list):return [without_descriptions(v) for v in x]
        return x
    assert schema==original and without_descriptions(schema)==without_descriptions(annotated)
    s,e,o,p=setup();raw=deepcopy(o['candidate'])
    body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    Draft202012Validator(body['output_schema']).validate(raw)
    assert body['source_coverage_contract']==contract
    assert not contract['establishes_entailment'] and not contract['repairs_model_citations']
    reading.parse(e['bundle'],raw,binding=e['fact_binding_sha256'])
    assert raw==o['candidate']


@pytest.mark.parametrize('change',['new_fact','new_source_field','missing_group','duplicate_field','nested_child_owned_twice'])
def test_schema_or_responsibility_drift_cannot_silently_emit_stale_guidance(change):
    schema=reading.NetworkEffectReading.model_json_schema();groups=deepcopy(reading.CITATION_GROUPS)
    if change=='new_fact':schema['$defs']['Study']['properties']['new_context_fact']={'type':'string'}
    elif change=='new_source_field':schema['$defs']['Study']['properties']['context_source_ids']={'type':'array','items':{'type':'string'}}
    elif change=='missing_group':groups.pop('Declaration')
    elif change=='duplicate_field':groups['EffectTarget']['source_ids'].append('remaining_assignment')
    else:groups['EffectTarget']['source_ids'].append('first')
    with pytest.raises(ValueError):coverage.annotate(schema,groups)


def test_changed_citation_contract_invalidates_request_and_previous_reviews(monkeypatch):
    s,e,o,p=setup();a=approval_records(p)
    monkeypatch.setattr(coverage,'INSTRUCTION',coverage.INSTRUCTION+' New public citation instruction.')
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called']
    fresh=dispatch.prepare_reader(s,'q1',query_review=o['query_review'])
    assert fresh['request_sha256']!=e['request_sha256']


def test_existing_source_number_does_not_prove_coverage_and_rejection_stops_math(monkeypatch):
    s,e,o,p=setup();raw=o['candidate'];refs=reading.reference_catalog(e['bundle'],binding=e['fact_binding_sha256'])
    raw['study']['source_ids']=[k for k in raw['study']['source_ids'] if refs['aliases'][k]['doc_id']!='context']
    p=dispatch.inspect_methods(s,'q1',**o)
    assert p['state']=='REVIEW_REQUIRED'  # Semantic truth cannot be inferred from an ID.
    a=approval_records(p);a['native_reviews']['network.randomized.local_contrast']['reading_review'].decisions['source_entailment']='REJECTED'
    before=deepcopy(raw)
    monkeypatch.setattr(effects,'_compile',lambda *a,**kw:pytest.fail('No math after source rejection'))
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called'] and raw==before


@pytest.mark.parametrize('name',CASES)
def test_frozen_complete_business_variants_keep_target_sources_and_negative_gates(name):
    s,e,data,raw=case_setup(name);before=deepcopy(raw)
    body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    Draft202012Validator(body['output_schema']).validate(raw)
    opts=dict(query_review=e['query_review'],candidate=raw,request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**opts)
    if name in ('missing_science','extra_bound'):
        r=dispatch.execute(s,'q1',**opts,research_protocol_selected=True)
        assert r['state']==('NEEDS_INPUT' if name=='missing_science' else 'ADAPTER_NOT_CONNECTED')
        assert not r['backend_called'] and r['mathematical_claim'] is None
        if name=='missing_science':assert raw['scientific_statements']['consistency']==dict(status='NOT_STATED',source_ids=[])
        else:assert raw['additional_restrictions']
    else:
        r=dispatch.execute(s,'q1',**opts,**approval_records(p))
        assert r['state']=='POINT' and r['independent_replay']
        target=r['mathematical_claim']['target']
        assert target['evaluation_population']==data['members']
        assert target['first']==list(data['arms'][0]) and target['second']==list(data['arms'][1])
        for arm in r['certificate']['results'][0]['constituent_arms']:
            sign=1 if (arm['own_treatment'],arm['exposure_state'])==data['arms'][0] else -1
            assert Fraction(arm['coefficient'])==Fraction(sign,len(data['members']))
    assert raw==before
