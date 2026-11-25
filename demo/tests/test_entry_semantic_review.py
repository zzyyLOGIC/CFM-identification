"""Source-to-native semantics, not just successful certificate replay."""
from copy import deepcopy
import pytest
from test_randomized_policy_default_entry import signature_fixture
from test_network_existing_entry import fixture as network_fixture, prepared as network_prepared, finish as network_finish
from test_dag_single_source_entry import fixture as dag_fixture
from test_joint_natural_entry import fixture as joint_fixture, prepared as dag_prepared
from test_iv_natural_entry import fixture as iv_fixture, prepared as iv_prepared
from cfm_id import joint_natural_entry as workflow, joint_query_exchange as exchange


def scoped_signature(nodes=None,scope='ALL_BINARY_ASSIGNMENTS'):
    case,s=signature_fixture()
    s['mean_sufficiency_scope']=dict(value=dict(covered_nodes=nodes or ['A','B','C','D'],
        scope=scope,assignments=[]),evidence=s['family']['evidence'])
    return case,s


def test_sufficiency_cannot_expand_one_node_to_whole_target():
    case,s=scoped_signature(['A'])
    s['conditions'][-1]['statement']='仅A采用均值充分性；B、C、D本次不采用。'
    r=network_prepared(case,s)
    assert r['joint_entry']['state']=='UNSUPPORTED'
    assert r['joint_entry']['reason_code']=='SUFFICIENCY_NODE_COVERAGE_INCOMPLETE'
    assert r['joint_entry']['uncovered_nodes']==['B','C','D']
    assert not r['backend_called'] and not r['clarification_questions']
    with pytest.raises(ValueError):exchange.packet(case,r)


def test_scoped_sufficiency_preserved_in_native_certificate():
    case,s=scoped_signature(['A']);s['target']['value']['weights']={'A':'1','B':'0','C':'0','D':'0'}
    r=network_finish(case,s)
    assert r['joint_entry']['state']=='POINT'
    assert r['joint_entry']['native_result']['certificate']['native_inputs'][0]['r2_sufficiency']['covered_nodes']==['A']
    assert workflow.replay(case,r['draft'],r)


@pytest.mark.parametrize('scope,state',[('UNKNOWN','NEEDS_INPUT'),('LISTED_ASSIGNMENTS','UNSUPPORTED')])
def test_sufficiency_cannot_expand_assignment_scope(scope,state):
    case,s=scoped_signature(scope=scope)
    if scope=='LISTED_ASSIGNMENTS':s['mean_sufficiency_scope']['value']['assignments']=[dict.fromkeys('ABCD',1)]
    r=network_prepared(case,s)
    assert r['joint_entry']['state']==state and not r['backend_called']


def test_missing_scope_is_not_implicitly_all_nodes_or_all_assignments():
    case,s=signature_fixture();s.pop('mean_sufficiency_scope',None)
    r=network_prepared(case,s)
    assert r['joint_entry']['state']=='NEEDS_INPUT' and not r['backend_called']


def test_unused_pending_sufficiency_does_not_block_full_assignment():
    case,s=network_fixture()
    s['conditions'].append(dict(code='mean_sufficiency',status='UNDECIDED',statement='本次尚未决定是否采用均值充分性',evidence=s['family']['evidence']))
    r=network_finish(case,s)
    assert r['joint_entry']['state']=='POINT' and not r['clarification_questions']
    assert 'mean_sufficiency' not in r['review_record']['decisions']
    assert r['joint_entry']['reading']['conditions'][-1]['status']=='UNDECIDED'


@pytest.mark.parametrize('single',[True,False])
@pytest.mark.parametrize('status,state',[('ADOPTED','UNSUPPORTED'),('NOT_ADOPTED','REVIEW_REQUIRED'),('UNDECIDED','NEEDS_INPUT')])
def test_graph_constraints_checked_before_single_multi_split(single,status,state):
    case,s=dag_fixture(True) if single else joint_fixture('DAG_JOINT')
    s['constraints']=[dict(description='把X设为1时，二元Y取1的总体概率为1/2',
        terms=[dict(node='Y',own=1,exposure=0,coefficient='1')],relation='EQ',rhs='1/2',status=status,evidence=s['family']['evidence'])]
    r=dag_prepared(case,s)
    assert r['joint_entry']['state']==state and not r['backend_called']
    if status=='ADOPTED':
        assert r['joint_entry']['reason_code']=='DAG_EXTRA_LINEAR_CONSTRAINT'
        assert not r['clarification_questions']


@pytest.mark.parametrize('route',['network','iv','dag'])
@pytest.mark.parametrize('decision,state',[('DECLINED','UNSUPPORTED'),('UNSURE','REVIEW_REQUIRED')])
def test_review_refusal_is_terminal_uncertainty_remains_pending(route,decision,state):
    case,s={'network':network_fixture,'iv':iv_fixture,'dag':dag_fixture}[route]()
    r={'network':network_prepared,'iv':iv_prepared,'dag':dag_prepared}[route](case,s)
    sheet=r['condition_review'];decisions={x['code']:'ADOPTED' for x in sheet['items']}
    decisions[next(x['code'] for x in sheet['items'] if x['code'] not in ('target','information'))]=decision
    review=dict(binding=sheet['binding'],authority='SYNTHETIC_TEST',decisions=decisions)
    out=workflow.complete(case,r,review)
    assert out['joint_entry']['state']==state and not out['backend_called']
    assert out['review_record']==review
    assert out['joint_entry'].get('completed',False)==(decision=='DECLINED')
    assert not out['independent_replay'] and not out['estimation_handoff_allowed']
    with pytest.raises(ValueError):exchange.packet(case,out)


def test_cancelled_policy_means_need_no_data_and_old_packets_keep_coordinates():
    case,s=network_fixture();t=s['target']['value']
    t.update(quantity='DIFFERENCE',components=[dict(assignment={'A':1,'B':1},probability='1/2'),dict(assignment={'A':1,'B':0},probability='1/2')],
        reference_components=[dict(assignment={'A':1,'B':1},probability='1/2'),dict(assignment={'A':0,'B':1},probability='1/2')])
    s['information']['value']['assignment_cells']=[dict(A=a,B=b) for a,b in [(1,1),(1,0),(0,1)]]
    out=network_finish(case,s);packet=exchange.packet(case,out);h=packet['estimate_handoff']
    assert len(h['queries'])==4 and all(w!='0' for w in h['operator_spec']['forms'][0])
    assert exchange.evaluate(h,{q['id']:'1/2' for q in h['queries']})=='0'
    assert exchange.check_packet(case['case_id'],packet)['query_count']==4
    old=exchange.packet(case,out,operator_revision=2)
    assert exchange.check_packet(case['case_id'],old)['query_count']==6


def test_identical_policies_have_zero_functional_without_queries():
    case,s=network_fixture();t=s['target']['value'];t.update(quantity='DIFFERENCE',reference_components=deepcopy(t['components']))
    out=network_finish(case,s);h=exchange.packet(case,out)['estimate_handoff']
    assert h['queries']==[] and h['operator_spec']['forms']==[[]]
    assert exchange.evaluate(h,{})=='0'
