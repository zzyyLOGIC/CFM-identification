"""Proposition-level guidance preserves real constraints and independent review."""
from copy import deepcopy
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_dispatch as dispatch, network_effect_dispatch as effects
from cfm_id_llm import network_effect_reading as reading
from examples.network_effect_dispatch_reference import approval_records
from evaluation.network_effect_residual_cases import CASES, EXPECTED, setup


def test_public_roles_match_the_actual_schema_without_new_output_fields():
    _, entry, _, raw = setup('retail_mixed')
    body = json.JSONDecoder().raw_decode(entry['request']['user'])[0]
    roles = body['residual_field_contract']
    assert roles['fields'] == reading.RESIDUAL_ROLES
    assert roles['unit'] == 'proposition_not_paragraph' and roles['automatic_repair'] is False
    for key, text in roles['fields'].items():
        assert key in raw and body['output_schema']['properties'][key]['description'] == text
    schema = body['output_schema']
    # D6 added a nullable scientific declaration shared by all design schemas.
    # This D1 fixture may omit it; D6 admission still requires independent review.
    assert raw['assignment']['kind'] == 'INDEPENDENT_BERNOULLI'
    assert set(raw) == set(schema['properties']) - {'first_stage_exclusion', 'assumption_choices'}
    assert 'assumption_choices' not in schema['required']
    assert reading.NetworkEffectReading.model_validate(raw).assumption_choices == []
    assert 'first_stage_exclusion' not in schema['required']
    assert schema['properties']['first_stage_exclusion']['default'] is None


@pytest.mark.parametrize('name', CASES)
def test_complete_new_business_preserves_information_gaps_and_same_paragraph_bound(name):
    state, entry, data, raw = setup(name)
    before = deepcopy(raw)
    Draft202012Validator(json.JSONDecoder().raw_decode(entry['request']['user'])[0]['output_schema']).validate(raw)
    opts = dict(query_review=entry['query_review'], candidate=raw, request_sha256=entry['request_sha256'])
    plan = dispatch.inspect_methods(state, 'q1', **opts)
    approved = approval_records(plan) if EXPECTED[name] == 'POINT' else dict(research_protocol_selected=True)
    result = dispatch.execute(state, 'q1', **opts, **approved)
    assert result['state'] == EXPECTED[name]
    assert result['independent_replay'] == (EXPECTED[name] == 'POINT')
    assert result['backend_called'] == (EXPECTED[name] == 'POINT')
    assert raw == before
    if name == 'retail_extra':
        assert data['extra_text'] in data['docs']['information']
        assert len(raw['information'][0]['arm_cells']) == 16
        assert len(raw['information']) == 2 and raw['additional_restrictions']
    if name == 'retail_gap':
        assert len(raw['information'][0]['arm_cells']) == 2
        assert raw['unresolved'][0]['source_ids']


@pytest.mark.parametrize('extra_kind', ['duplicate', 'bound', 'numeric_value'])
def test_parser_never_silently_deletes_residual_text_to_reach_point(extra_kind, monkeypatch):
    state, entry, data, raw = setup('retail_mixed')
    text = {'duplicate': data['docs']['information'],
            'bound': '每家店在每种完整安排下的总体平均等待不超过18分钟。',
            'numeric_value': '百合店自己不使用、合作状态1时，总体平均等待为7分钟。'}[extra_kind]
    raw['additional_restrictions'] = [dict(text=text, source_ids=raw['information'][0]['source_ids'])]
    before = deepcopy(raw)
    parsed = reading.parse(entry['bundle'], raw, binding=entry['fact_binding_sha256'])
    assert parsed['facts']['additional_restrictions'][0]['text'] == text
    monkeypatch.setattr(effects, '_compile', lambda *a, **kw: pytest.fail('Unreviewed extra reached math'))
    result = dispatch.execute(state, 'q1', query_review=entry['query_review'], candidate=raw,
        request_sha256=entry['request_sha256'], research_protocol_selected=True)
    assert result['state'] == 'ADAPTER_NOT_CONNECTED' and not result['backend_called']
    assert raw == before


def test_deleting_real_same_paragraph_bound_fails_independent_source_review(monkeypatch):
    state, entry, _, raw = setup('retail_extra')
    raw['additional_restrictions'] = []  # Deliberately unfaithful test candidate.
    opts = dict(query_review=entry['query_review'], candidate=raw, request_sha256=entry['request_sha256'])
    plan = dispatch.inspect_methods(state, 'q1', **opts)
    assert plan['state'] == 'REVIEW_REQUIRED'
    a = approval_records(plan)
    review = a['native_reviews']['network.randomized.local_contrast']['reading_review'].model_dump(mode='json')
    review['decisions']['all_information_and_restrictions_preserved'] = 'REJECTED'
    review['decisions']['source_entailment'] = 'REJECTED'
    review['evidence'] = 'Synthetic source audit: the numerical bound in the original information paragraph was omitted. Type-correct information is insufficient.'
    a['native_reviews']['network.randomized.local_contrast']['reading_review'] = dispatch.DispatchReview.model_validate(review)
    monkeypatch.setattr(effects, '_compile', lambda *a, **kw: pytest.fail('Rejected source reached math'))
    result = dispatch.execute(state, 'q1', **opts, **a)
    assert result['state'] == 'CHECK_BLOCKED' and not result['backend_called']


def test_guidance_change_invalidates_old_request_and_scientific_reviews(monkeypatch):
    state, entry, _, raw = setup('retail_mixed')
    opts = dict(query_review=entry['query_review'], candidate=raw, request_sha256=entry['request_sha256'])
    old_plan = dispatch.inspect_methods(state, 'q1', **opts)
    old_reviews = approval_records(old_plan)
    monkeypatch.setattr(reading, 'SYSTEM', reading.SYSTEM + '\nA changed public reading instruction.')
    new_entry = dispatch.prepare_reader(state, 'q1', query_review=entry['query_review'])
    assert new_entry['request_sha256'] != entry['request_sha256']
    assert dispatch.execute(state, 'q1', **opts, **old_reviews)['state'] == 'CHECK_BLOCKED'
    opts['request_sha256'] = new_entry['request_sha256']
    assert dispatch.execute(state, 'q1', **opts, **old_reviews)['state'] == 'CHECK_BLOCKED'
    pending = dispatch.execute(state, 'q1', **opts, research_protocol_selected=True)
    assert pending['state'] == 'REVIEW_REQUIRED' and not pending['backend_called']
