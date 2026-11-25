"""A symbolic ID functional is not a finite-sample estimate or a known law."""
from copy import deepcopy
import pytest
from cfm_id import joint_natural_entry as entry, dag_joint_verify
from cfm_id.joint_query_exchange import packet, check_packet
from cfm_id_bridge.scientific_binding import sha
from test_joint_natural_entry import fixture, prepared, finish


def sample():
    case,s=fixture('DAG_JOINT')
    s['dag_information']['value'].update(kind='FINITE_SAMPLE',sample_size=200,jointly_observed=True)
    return case,s


def test_sample_preserves_the_same_symbolic_id_and_never_becomes_known_law():
    case,s=sample();r=finish(case,s)
    original=deepcopy(s);original['dag_information']['value']['kind']='FULL_JOINT_POPULATION_LAW'
    before=finish(case,original)
    e=r['joint_entry'];c=e['native_result']['certificate']
    assert e['reading']['dag_information']['value']['kind']=='FINITE_SAMPLE'
    assert e['problem']['information']=='FINITE_SAMPLE' and e['problem']['version']=='dag-joint-id-2'
    assert c['functional']==before['joint_entry']['native_result']['certificate']['functional']
    assert c['derivation']==before['joint_entry']['native_result']['certificate']['derivation']
    assert c['information_basis']['numeric_population_known'] is False
    assert entry.replay(case,r['draft'],r)
    from cfm_id import dedicated_entries
    from demo.backend import math_library
    declared=dedicated_entries.resolve('DAG_JOINT_ID')
    assert 'dag-joint-id-2' in str(declared.problem_schema())
    assert dedicated_entries.run('DAG_JOINT_ID',e['problem'])['state']=='REVIEW_REQUIRED'
    assert math_library._run(dict(operation='DAG_JOINT_ID',problem=e['problem']))['state']=='REVIEW_REQUIRED'
    p=packet(case,r);receipt=check_packet(case['case_id'],p)
    q=p['estimate_handoff']['queries'][0]
    assert receipt['state']=='RECEIVED' and receipt['estimator_executed'] is False
    assert q['numeric_value_available'] is False and q['observed_data']['sample_size']==200
    assert p['target']['intervention_values']=={'A':'1','B':'1'}
    p['estimate_handoff']['queries'][0]['numeric_value_available']=True
    with pytest.raises(ValueError):check_packet(case['case_id'],p)
    # Even a rehashed certificate cannot substitute its information semantics.
    forged=deepcopy(c);forged['information_basis']['numeric_population_known']=True
    forged['certificate_sha256']=sha({k:v for k,v in forged.items() if k!='certificate_sha256'})
    assert not dag_joint_verify.replay(forged,e['problem'])


@pytest.mark.parametrize('joint,state,reason',[(None,'NEEDS_INPUT','JOINT_OBSERVATIONS_REQUIRED'),
    (False,'UNSUPPORTED','JOINT_OBSERVATIONS_NOT_AVAILABLE')])
def test_variables_on_a_list_are_not_evidence_of_joint_observations(joint,state,reason):
    case,s=sample();s['dag_information']['value']['jointly_observed']=joint
    r=prepared(case,s)
    assert r['joint_entry']['state']==state and r['joint_entry']['reason_code']==reason
    assert not r['backend_called']


@pytest.mark.parametrize('mutation,reason',[
    ('coverage','OBSERVED_VARIABLE_COVERAGE_NOT_CONNECTED'),
    ('positivity','SCIENTIFIC_PREMISES_NOT_DECLARED'),
    ('refused','REQUIRED_PREMISE_NOT_ADOPTED'),
    ('scope','TARGET_DATA_SCOPE_REQUIRED'),
    ('marginals','POPULATION_LAW_REQUIRED'),
])
def test_sample_path_keeps_original_requirements(mutation,reason):
    case,s=sample()
    if mutation=='coverage':s['dag_information']['value']['variables'].remove('Z')
    if mutation in ('positivity','refused'):
        next(x for x in s['conditions'] if x['code']=='strict_positivity')['status']='UNKNOWN' if mutation=='positivity' else 'NOT_ADOPTED'
    if mutation=='scope':s['dag_information']['value']['matches_target']=False
    if mutation=='marginals':s['dag_information']['value'].update(kind='MARGINAL_STATISTICS',jointly_observed=False)
    r=prepared(case,s)
    assert r['joint_entry']['reason_code']==reason and not r['backend_called']


def test_review_does_not_silently_approve_new_science():
    case,s=sample();r=prepared(case,s);sheet=r['condition_review']
    decisions={x['code']:'ADOPTED' for x in sheet['items']};decisions['strict_positivity']='DECLINED'
    stopped=entry.complete(case,r,dict(binding=sheet['binding'],authority='SYNTHETIC_TEST',decisions=decisions))
    assert not stopped['backend_called'] and not stopped['independent_replay']
