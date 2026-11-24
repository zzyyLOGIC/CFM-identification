"""Request locality does not relax types, source gates, or native mathematics."""
import json
from copy import deepcopy
import pytest
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id.business_reading_config import ReadingConfig
from cfm_id_llm import compact_unified_contract as unified
from cfm_id_llm.compact_formulator import make_compact_request
from cfm_id_llm.compact_reference_contract import split_user
from cfm_id_llm.network_fact_protocols import network_fact_protocol
from tests_gateway.test_target_summary_contract import fixture
from tests_gateway.test_inline_evidence_slots import receive, wire
from tests_gateway.test_business_field_review import sheet
from tests_gateway.test_unified_reading_contract import no_descriptions
from tests_gateway import test_wire_evidence_contract as old

PROFILE=unified.LOCAL_STATE_CONTRACT

def test_local_states_and_roles_keep_existing_schema_and_share_review_meaning():
    b,raw=fixture();a=split_user(make_compact_request(b,a0_response_contract=unified.WIRE_EVIDENCE_CONTRACT)[1])[2]
    z=split_user(make_compact_request(b,a0_response_contract=PROFILE)[1])[2]
    assert no_descriptions(a)==no_descriptions(z)
    w=sheet(receive(b,wire(raw),True,profile=PROFILE))
    for section,model in [('common','CompactCommon'),('semantics','CompactSemantics')]:
        for rule in unified.fields.fields(section):
            if rule.shape!='claim':continue
            text=z['$defs'][model]['properties'][rule.name]['description']
            assert ('禁止NOT_APPLICABLE' not in text)==rule.allows_inapplicable
    for name in ('target_population','aggregation','standardization_distribution'):
        assert w['fields']['queries.q1.semantics.'+name]['definition']['wire_description']==z['$defs']['CompactSemantics']['properties'][name]['description']
    assert '评价范围' in z['$defs']['CompactSemantics']['properties']['target_population']['description']
    assert '跨研究对象' in z['$defs']['CompactSemantics']['properties']['standardization_distribution']['description']

@pytest.mark.parametrize('name',['time_horizon','standardization_distribution','target_population'])
def test_forbidden_empty_state_still_blocks_without_repair(name):
    b,raw=fixture();s=receive(b,wire(raw),True,profile=PROFILE);candidate=deepcopy(s.candidate)
    candidate['queries'][0]['semantics'][name]='NOT_APPLICABLE'
    r=intake.receive_candidate(s,candidate,request_sha256=s.request_sha256)
    assert r.candidate==candidate and dispatch.prepare_reader(r,'q1')['request'] is None

@pytest.mark.parametrize('name',['enum_claim','enum_null','enum_misspelled','invalid_ref','missing_with_value'])
def test_bad_wire_never_coerced(name,monkeypatch):
    monkeypatch.setattr(old,'PROFILE',PROFILE);old.test_wrong_output_is_not_coerced_or_repaired(name)

@pytest.mark.parametrize('own_refs',[False,True])
def test_cross_field_citations_still_require_independent_source_review(own_refs,monkeypatch):
    monkeypatch.setattr(old,'PROFILE',PROFILE);old.test_separate_fragments_need_this_fields_own_coverage_and_independent_review(own_refs)

@pytest.mark.parametrize('negative',['bounds','sufficiency','sample','scope','extra'])
def test_negative_network_inputs_remain_blocked(negative,monkeypatch):
    monkeypatch.setattr(old,'PROFILE',PROFILE);old.test_negative_network_cases_still_stop_before_native_solver(negative,monkeypatch)

@pytest.mark.parametrize('bounds,expected',[(('1/2','1/2'),'POINT'),(('1/4','3/4'),'PARTIAL')])
def test_native_positive_replays_still_need_independent_science(bounds,expected,monkeypatch):
    monkeypatch.setattr(old,'PROFILE',PROFILE);old.test_native_network_result_still_requires_science_and_independent_replay(bounds,expected,monkeypatch)

def test_fact_local_enum_guidance_preserves_wire_and_single_table_boundary():
    from tests_gateway.test_network_bounded_dispatch import setup
    s,e,o,p=setup();a=network_fact_protocol('network-source-selections-information-2');z=network_fact_protocol('network-source-selections-information-3')
    ar=a.make_request(e['bundle'],binding=e['fact_binding_sha256']);zr=z.make_request(e['bundle'],binding=e['fact_binding_sha256'])
    x=json.loads(ar['user']);y=json.loads(zr['user']);sx=x.pop('output_schema');sy=y.pop('output_schema')
    assert x==y and no_descriptions(sx)==no_descriptions(sy) and a.parse is z.parse and a.model is z.model
    assert '不能翻译或改写' in sy['$defs']['BoundedModel']['properties']['bounds_scope']['description']
    # Supporting definitions can accompany one original table, but references
    # and separate scientific restrictions must still survive source review.
    information = sy['$defs']['Information']['description']
    for requirement in ('同一份原始表', '配套文档可说明', '保留全部必要引用',
                        '按既有来源角色合同审核', '额外等式或约束时仍分别完整保留'):
        assert requirement in information
    assert '处理编码' in sy['properties']['target']['description']

def test_new_options_are_explicit_and_do_not_change_defaults():
    assert ReadingConfig().a0_response_contract is None and ReadingConfig().network_fact_contract is None
    assert ReadingConfig(a0_response_contract=PROFILE,network_fact_contract='network-source-selections-information-3').a0_response_contract==PROFILE
    with pytest.raises(ValueError,match='CURRENT_TARGET'):ReadingConfig(a0_response_contract=PROFILE,target_summary_contract='target-summary-1')
