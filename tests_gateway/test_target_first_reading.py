"""Target-first compatibility, ownership and independent-review boundaries."""
from copy import deepcopy
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_intake as intake, business_dispatch as dispatch
from cfm_id_llm import target_first_reading as new
from cfm_id_llm.compact_reference_contract import split_user
from cfm_id_llm.schemas import TargetKind
from tests_gateway.test_policy_interface_contracts import a0_case
from tests_gateway.test_inline_evidence_slots import receive
from tests_gateway.test_business_field_review import sheet, record, submit

def fixture(family='contrast'):
    case,raw=a0_case(family)
    raw['common']={k:raw['common'].get(k,'UNKNOWN') for k in new.COMMON_FIELDS}
    for q in raw['queries']:
        q['semantics'].pop('policy_assignment',None)
        q['semantics']['outcome']=deepcopy(raw['common']['outcome'])
        q['semantics']['decision_constraints']='UNKNOWN'
        # A complete-policy question does not separately specify a peer state
        # or a distribution over backgrounds. Current wire contracts require
        # explicit unknown slots; these are test inputs, not answer repair.
        q['semantics']['neighbor_exposure']='UNKNOWN'
        q['semantics']['standardization_distribution']='UNKNOWN'
    return case,raw

def test_new_schema_and_multi_query_do_not_lose_old_vocabulary():
    case,raw=fixture(); s=receive(case,raw,profile=new.CONTRACT)
    schema=split_user(intake.prepare_request(s)['user_prompt'])[2]
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(s.candidate)
    assert set(schema['$defs']['TargetKind']['enum'])=={k.value for k in TargetKind}
    raw['queries'].append(deepcopy(raw['queries'][0]))
    raw['queries'][1]['goal']['value']='另请单独评价主方案的平均结果'
    raw['queries'][1]['kind']='FIXED_POLICY_VALUE'
    raw['queries'][1]['semantics']['comparator']='NOT_APPLICABLE'
    raw['queries'][1]['comparison_order']['operation']='NOT_APPLICABLE'
    s=receive(case,raw,profile=new.CONTRACT)
    assert len(intake.inspect(s)['report']['draft']['queries'])==2
    assert [q['kind'] for q in s.candidate['queries']]==['TOTAL_EFFECT','FIXED_POLICY_VALUE']

@pytest.mark.parametrize('family',['policy','contrast'])
def test_native_point_and_replay_remain_behind_independent_reviews(family):
    from examples.network_design_exposure_reference import material, fact_reference
    from examples.network_dispatch_reference import approval_records
    from tests_gateway.test_fact_source_review import record as source_record
    from cfm_id.fact_source_review import prepare as source_sheet
    case,raw=fixture(family);s=receive(case,raw,profile=new.CONTRACT)
    s=intake.configure_network_fact_contract(s,'network-policy-scopes-1')
    q=submit(s,record(sheet(s)))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    _,data=material('D1','E5',family);c=fact_reference(e,data)
    c['assignment']['definition_refs']=['study'];c['mean_sufficiency']['definition_refs']=['study']
    for end in ([c['target']] if family=='policy' else [c['target']['first'],c['target']['second']]):
        end['definition_refs']=['study']
    for row in c['information']:
        row.update(definition_refs=['study'],scope_status='DECLARED',scope_source_ids=list(row['source_ids']))
    opts=dict(query_review=q,candidate=c,request_sha256=e['request_sha256'])
    opts['source_review']=source_record(source_sheet(e,c))
    plan=dispatch.inspect_methods(s,'q1',**opts)
    assert not dispatch.execute(s,'q1',**opts,research_protocol_selected=True)['backend_called']
    result=dispatch.execute(s,'q1',**opts,**approval_records(plan))
    assert result['state']=='POINT' and result['independent_replay']

def test_alias_and_deferred_fields_not_model_or_a0_review_obligations():
    case,raw=fixture('policy');s=receive(case,raw,profile=new.CONTRACT);before=deepcopy(s.candidate)
    result=intake.inspect(s); assert 'report' in result,result
    sem=result['report']['draft']['queries'][0]['semantics']
    assert sem['policy_assignment']==sem['intervention']
    w=sheet(s)
    assert all('common.'+k not in w['fields'] for k in new.DEFERRED_COMMON)
    assert 'queries.q1.semantics.policy_assignment' not in w['fields']
    assert 'queries.q1.semantics.outcome' in w['fields']
    q=submit(s,record(w))['query_review'];e=dispatch.prepare_reader(s,'q1',query_review=q)
    assert e['state']=='READY_TO_READ',e
    assert e['bundle']['documents']==dict({x.source_id:x.text for x in case.sources},business_question=case.business_question)
    assert e['reviewed_target_context']['target_period']==before['queries'][0]['semantics']['time_horizon']
    assert s.candidate==before

@pytest.mark.parametrize('defect',['duplicate','missing_outcome','missing_common','bad_reference'])
def test_invalid_wire_is_not_repaired(defect):
    case,raw=fixture();sem=raw['queries'][0]['semantics']
    if defect=='duplicate':sem['policy_assignment']=deepcopy(sem['intervention'])
    elif defect=='missing_outcome':sem.pop('outcome')
    elif defect=='missing_common':raw['common'].pop('assignment_law')
    else:sem['outcome']['refs']=['not-a-reference']
    s=receive(case,raw,short=False,profile=new.CONTRACT);before=deepcopy(s.candidate)
    assert 'report' not in intake.inspect(s)
    assert s.candidate==before

@pytest.mark.parametrize('decision',['REJECTED','PENDING'])
def test_outcome_review_remains_required(decision):
    case,raw=fixture();s=receive(case,raw,profile=new.CONTRACT);w=sheet(s);r=record(w)
    r['decisions']['queries.q1.semantics.outcome']['source_coverage']=decision
    submitted=submit(s,r)
    e=dispatch.prepare_reader(s,'q1',query_review=submitted['query_review'])
    assert e['state']!='READY_TO_READ' and not e['backend_called']


def test_unknown_outcome_enters_stop_review_without_confirming_a_source_gap():
    from cfm_id.intake_stop_review import prepare_review

    case,raw=fixture('policy')
    raw['common']['outcome']='UNKNOWN'
    raw['queries'][0]['semantics']['outcome']='UNKNOWN'
    submission=receive(case,raw,profile=new.CONTRACT)
    review=prepare_review(submission,authority='SYNTHETIC_TEST')
    item=review['stop_worksheet']['items']['q1']
    assert any(field['field']=='outcome' for field in item['missing_coordinates'])
    assert item['material_gap_allowed'] is False
    assert review['scientific_approval'] is False and review['core_called'] is False


@pytest.mark.parametrize('field',['conditioning_context','outcome','decision_constraints'])
def test_plain_text_claim_reports_field_without_repair_or_core(field):
    case,raw=fixture();raw['queries'][0]['semantics'][field]='原文中的普通字符串，未提供字段状态或引用'
    s=receive(case,raw,profile=new.CONTRACT);before=deepcopy(s.candidate)
    inspected=intake.inspect(s)
    assert inspected['reason_code']=='TARGET_FIRST_CONTRACT_REJECTED'
    assert inspected['diagnostics']['reason']=='TARGET_FIRST_FIELD_TYPE'
    assert inspected['diagnostics']['field']==f'queries.q1.semantics.{field}'
    assert inspected['diagnostics']['received_type']=='str'
    assert inspected['core_called'] is False and s.candidate==before
