"""Existing set-ID dispatch and source-only numbers keep their distinct claims."""
from copy import deepcopy
import json
import pytest
from test_dag_single_source_entry import fixture
from test_joint_natural_entry import prepared,finish
from cfm_id import joint_natural_entry as workflow,joint_query_exchange as exchange
from cfm_id_llm import joint_reading as reader


def test_single_treatment_joint_outcomes_reuses_set_solver():
    case,s=fixture();s['dag_target']['value']['outcome']=['M','Y']
    r=finish(case,s);e=r['joint_entry']
    assert e['operation']=='DAG_JOINT_ID' and e['state']=='POINT'
    assert e['native_result']['certificate']['target']['outcome']==['M','Y']
    assert workflow.replay(case,r['draft'],json.loads(json.dumps(r)))
    h=exchange.packet(case,r)['estimate_handoff']
    assert h['target']['outcome']==['M','Y']
    assert h['target']['intervention_values']=={'X':'1'}
    packet=exchange.packet(case,r);assert exchange.check_packet(case['case_id'],packet)['query_count']==1
    old=exchange.packet(case,r,operator_revision=3)
    assert 'intervention_values' not in old['estimate_handoff']['target']
    assert exchange.check_packet(case['case_id'],old)['query_count']==1
    packet['estimate_handoff']['target']['intervention_values']['X']='0'
    with pytest.raises(ValueError):exchange.check_packet(case['case_id'],packet)


def test_single_treatment_sample_yields_symbolic_function_not_population_value():
    case,s=fixture();s['dag_information']['value'].update(kind='FINITE_SAMPLE',jointly_observed=True,sample_size=120)
    r=finish(case,s);e=r['joint_entry'];c=e['native_result']['certificate']
    assert e['operation']=='DAG_JOINT_ID' and e['state']=='POINT'
    assert c['information_basis']['numeric_population_known'] is False
    assert c['information_basis']['sample_size']==120
    assert workflow.replay(case,r['draft'],r)


@pytest.mark.parametrize('observed,state',[(None,'NEEDS_INPUT'),(False,'UNSUPPORTED')])
def test_single_sample_without_joint_records_cannot_execute(observed,state):
    case,s=fixture();s['dag_information']['value'].update(kind='FINITE_SAMPLE',jointly_observed=observed)
    r=prepared(case,s)
    assert r['joint_entry']['state']==state and not r['backend_called']


def test_set_target_preserves_extra_conditions_and_science_refusal():
    case,s=fixture();s['dag_target']['value']['outcome']=['M','Y']
    s['remaining']=[dict(code='extra',statement='只允许控制W',status='ADOPTED',evidence=s['family']['evidence'])]
    assert prepared(case,s)['joint_entry']['state']=='UNSUPPORTED'
    s['remaining']=[];r=prepared(case,s);sheet=r['condition_review']
    d={x['code']:'ADOPTED' for x in sheet['items']};d['no_between_unit_interference']='DECLINED'
    out=workflow.complete(case,r,dict(binding=sheet['binding'],authority='SYNTHETIC_TEST',decisions=d))
    assert out['joint_entry']['state']=='UNSUPPORTED' and not out['backend_called']


def supplied_fixture():
    case,s=fixture(True);q=dict(intervention={'X':'1'},event={'Y':'1'},conditioned_on={},
        population='同一随访人群',period=s['dag_target']['value']['period'],context='本次研究')
    ev=s['family']['evidence']
    s['requested_probability']=dict(value=q,evidence=ev)
    s['given_probabilities']=[dict(quantity=deepcopy(q),value='1/2',information_kind='EXACT_POPULATION',status='ADOPTED',evidence=ev)]
    return case,s


def test_given_number_shown_but_not_promoted_to_math_or_estimation():
    case,s=supplied_fixture();r=prepared(case,s);e=r['joint_entry']
    assert e['given_probability_source']['value']=='1/2'
    assert e['state']=='UNSUPPORTED' and not r['backend_called'] and not r.get('proof')
    assert not r['independent_replay'] and not r['estimation_handoff_allowed']
    assert e['unhandled_declarations'] and not r['clarification_questions']
    with pytest.raises(ValueError):exchange.packet(case,r)


@pytest.mark.parametrize('field,value',[
    ('population','另一人群'),('period','去年'),('context','另一个场景'),
    ('event',{'Y':'0'}),('intervention',{'X':'0'}),('conditioned_on',{'Z':'1'}),('period','')])
def test_different_or_unknown_scope_does_not_become_the_requested_value(field,value):
    case,s=supplied_fixture();s['given_probabilities'][0]['quantity'][field]=value
    r=prepared(case,s)
    assert 'given_probability_source' not in r['joint_entry']
    assert not r['backend_called']


@pytest.mark.parametrize('field,value',[
    ('information_kind','SAMPLE_ESTIMATE'),('information_kind','UNKNOWN'),('status','NOT_ADOPTED'),
    ('status','UNDECIDED'),('value','3/2'),('value','unknown')])
def test_estimates_unaccepted_or_invalid_numbers_are_not_given_population_values(field,value):
    case,s=supplied_fixture();s['given_probabilities'][0][field]=value
    r=prepared(case,s)
    assert 'given_probability_source' not in r['joint_entry']
    assert not r['backend_called']


def test_conflicting_given_numbers_are_not_arbitrarily_selected():
    case,s=supplied_fixture();s['given_probabilities'].append(dict(s['given_probabilities'][0],value='2/3'))
    e=prepared(case,s)['joint_entry']
    assert e['given_probability_source']['state']=='CONFLICTING_SOURCE_VALUES'
    assert 'value' not in e['given_probability_source']


def test_old_reading_bindings_and_all_source_audit_fields_still_required():
    case,s=fixture();old=reader.inspect(case,s)
    assert 'given_probabilities' not in old and 'requested_probability' not in old
    case,s=supplied_fixture();r=prepared(case,s);e=r['joint_entry'];a=deepcopy(e['audit'])
    a['findings']=[f for f in a['findings'] if f['field']!='given_probabilities.0']
    with pytest.raises(ValueError):workflow.plan(case,workflow.base(r,case,e['reading'],a))


def test_other_or_unspecified_target_cannot_use_one_event_number():
    case,s=supplied_fixture();s['dag_target']['value']['intervention_values']={}
    assert 'given_probability_source' not in prepared(case,s)['joint_entry']
    s['dag_target']['value'].update(intervention_values={'X':'1'},query_kind='CONTRAST')
    assert 'given_probability_source' not in prepared(case,s)['joint_entry']


def test_unhandled_information_stops_before_unnecessary_graph_questions():
    case,s=supplied_fixture();s['graph']=None;s['conditions']=[]
    r=prepared(case,s)
    assert r['joint_entry']['state']=='UNSUPPORTED' and not r['clarification_questions']


def test_constant_variable_is_not_ignored_by_general_graph_witness():
    case,s=fixture(True)
    s['graph']['value']['variable_definitions']={'Y':dict(description='结果恒为1',values=['1'])}
    r=prepared(case,s)
    assert r['joint_entry']['reason_code']=='DECLARED_CONSTANT_VARIABLE_NOT_CONNECTED'
    assert not r['backend_called'] and not r.get('proof')


def test_sample_value_does_not_require_irrelevant_population_alignment():
    case,s=supplied_fixture();s['given_probabilities'][0].update(information_kind='SAMPLE_ESTIMATE',scope_matches_question=None)
    r=prepared(case,s)
    assert 'given_probability_alignment.0' not in reader.fields(r['joint_entry']['reading'])
    assert 'given_probability_source' not in r['joint_entry']
    assert r['joint_entry']['state']=='UNSUPPORTED' and not r['clarification_questions']


def test_equivalent_scope_requires_separate_source_audit_not_word_replacement():
    case,s=supplied_fixture();s['given_probabilities'][0]['quantity']['context']='背景与本次研究相同'
    assert 'given_probability_source' not in prepared(case,s)['joint_entry']
    s['given_probabilities'][0]['scope_matches_question']=True
    r=prepared(case,s);e=r['joint_entry'];assert e['given_probability_source']['value']=='1/2'
    a=deepcopy(e['audit']);a['findings']=[f for f in a['findings'] if f['field']!='given_probability_alignment.0']
    with pytest.raises(ValueError):workflow.plan(case,workflow.base(r,case,e['reading'],a))
    a=deepcopy(e['audit']);next(f for f in a['findings'] if f['field']=='given_probability_alignment.0')['verdict']='READING_ERROR'
    assert 'given_probability_source' not in workflow.plan(case,workflow.base(r,case,e['reading'],a))['joint_entry']
    s['given_probabilities'][0]['scope_matches_question']=False
    assert 'given_probability_source' not in prepared(case,s)['joint_entry']
