from copy import deepcopy
import pytest
from test_joint_natural_entry import fixture as joint_fixture,prepared,finish
from cfm_id import joint_natural_entry as workflow,joint_query_exchange as exchange

def fixture(confounded=False):
    case,s=joint_fixture('DAG_JOINT');ev=s['family']['evidence']
    s['dag_target']['value'].update(treatments=['X'],outcome=['Y'],joint=False,intervention_values={'X':'1'})
    g=dict(nodes=['W','X','M','Y'],directed=[['W','X'],['W','M'],['W','Y'],['X','M'],['M','Y']],bidirected=[['X','Y']],finite_discrete=True)
    if confounded:g=dict(nodes=['X','Y'],directed=[['X','Y']],bidirected=[['X','Y']],finite_discrete=True)
    s['graph']['value']=g;s['dag_information']['value']['variables']=g['nodes']
    s['conditions'].append(dict(code='no_between_unit_interference',status='ADOPTED',statement='不同对象之间不存在相互影响',evidence=ev))
    return case,s

def test_single_id_keeps_source_declarations_and_original_certificate():
    case,s=fixture();p=prepared(case,s)
    assert p['joint_entry']['problem']['graph_status']=='UNKNOWN'
    assert p['joint_entry']['problem']['reading_declarations'] is not None
    out=finish(case,s);assert out['joint_entry']['state']=='POINT' and workflow.replay(case,out['draft'],out)
    c=out['joint_entry']['native_result']['certificate'];assert c['native']['certificate']['target']['treatment']=='X'
    assert c['target']['intervention_values']=={'X':'1'}
    from cfm_id.dag_id_route import submit,DECISIONS,digest
    native=submit(c['problem'],dict(version=c['problem']['version'],problem_sha256=digest(c['problem']),reviewer='offline native comparison',evidence='same fully reviewed explicit original graph',authority='SYNTHETIC_TEST',decisions={k:'ACCEPTED' for k in DECISIONS}))
    assert native['certificate']==c['native']['certificate']
    receipt=exchange.check_packet(case['case_id'],exchange.packet(case,out));assert receipt['query_count']==1
    bad=deepcopy(out);bad['joint_entry']['reading']['graph']['value']['bidirected']=[]
    assert not workflow.replay(case,out['draft'],bad)

def test_nonidentification_is_verified_not_relabelled_as_unavailable():
    case,s=fixture(True);out=finish(case,s)
    assert out['joint_entry']['state']=='NONIDENTIFIABLE' and out['independent_replay']
    assert out['joint_entry']['native_result']['certificate']['native']['nonidentification_proved']
    assert workflow.replay(case,out['draft'],out)
    with pytest.raises(ValueError):exchange.packet(case,out)

@pytest.mark.parametrize('status,expected',[('UNKNOWN','NEEDS_INPUT'),('NOT_ADOPTED','UNSUPPORTED')])
def test_no_interference_requirement_keeps_original_scope(status,expected):
    case,s=fixture();s['conditions'][-1]['status']=status
    out=prepared(case,s);assert out['joint_entry']['state']==expected and not out['backend_called']

def test_single_id_sample_is_not_promoted_and_extra_constraint_not_erased():
    case,s=fixture();s['dag_information']['value']['kind']='FINITE_SAMPLE'
    assert prepared(case,s)['joint_entry']['reason_code']=='JOINT_OBSERVATIONS_REQUIRED'
    s['dag_information']['value']['kind']='FULL_JOINT_POPULATION_LAW'
    s['remaining']=[dict(code='specified_adjustment',statement='只允许控制W，不得改用其他公式',status='ADOPTED',evidence=s['family']['evidence'])]
    assert prepared(case,s)['joint_entry']['reason_code']=='UNEXPRESSED_ADDITIONAL_RESTRICTION'
