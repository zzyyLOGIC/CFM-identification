"""Reuse original policy proofs from source-reviewed default-entry contracts."""
from copy import deepcopy
import pytest
from test_network_existing_entry import fixture,prepared,finish
from cfm_id import joint_natural_entry as workflow,joint_query_exchange as exchange
from cfm_id_llm.network_source_route import select


def signature_fixture():
    case,s=fixture();nodes=['A','B','C','D'];ev=s['family']['evidence']
    s['network']['value'].update(nodes=nodes,edges=[[a,b] for i,a in enumerate(nodes) for b in nodes[i+1:]])
    s['design']['value']=dict(kind='complete_randomization_binary_v1',m=3)
    s['exposure']=dict(value=dict(grouping='strict_majority_ties_low',core_collaborators=None),evidence=ev)
    s['target']['value'].update(components=[dict(assignment={n:1 for n in nodes},probability=None)],
        distribution_complete=None,weights={n:'1/4' for n in nodes})
    s['information']['value'].update(operator='NODE_SIGNATURE_MEANS',outcome_nodes=nodes,assignment_cells=[],
        signature_cells=[dict(node=n,own=1,exposure=1) for n in nodes])
    s['conditions'].append(dict(code='mean_sufficiency',statement='同一对象的平均结果仅由本人和同伴状态决定',status='ADOPTED',evidence=ev))
    s['mean_sufficiency_scope']=dict(value=dict(covered_nodes=nodes,scope='ALL_BINARY_ASSIGNMENTS',assignments=[]),evidence=ev)
    return case,s


@pytest.mark.parametrize('form',['FULL_ASSIGNMENT_INFORMATION','SIGNATURE_MEANS'])
def test_source_attributes_select_policy_not_bounds(form):
    scope={k:dict(value=v) for k,v in dict(single_question=True,target='FIXED_POLICY_LEVEL',
        assignment='RANDOMIZED',mean_constraints='NOT_STATED',policy_information=form).items()}
    assert select(scope)=='NETWORK_FINITE_POLICY'
    scope['mean_constraints']['value']='DECLARED'
    assert select(scope)=='NETWORK_JOINT_MEANS'
    scope['mean_constraints']['value']='NOT_STATED';scope['policy_information']['value']='BOUNDED_MEAN_MODEL'
    assert select(scope)=='NETWORK_JOINT_MEANS'


def test_fixed_policy_without_new_policy_probability():
    case,s=fixture();s['target']['value'].update(components=[dict(assignment={'A':1,'B':1},probability=None)],distribution_complete=None)
    out=finish(case,s);assert out['independent_replay']
    native=out['joint_entry']['native_result']['certificate']['native_outcome']
    assert native['route']=='R1B_FULL_ASSIGNMENT'
    assert exchange.check_packet(case['case_id'],exchange.packet(case,out))['query_count']==2


def test_off_support_policy_uses_original_signature_proof_and_correct_queries():
    case,s=signature_fixture();out=finish(case,s)
    c=out['joint_entry']['native_result']['certificate'];native=c['native_outcome']
    assert out['independent_replay'] and workflow.replay(case,out['draft'],out)
    assert native['route']=='R2_MEAN_SIGNATURE'
    assert native['result']['policy_assignment_probability']=='0'
    packet=exchange.packet(case,out);h=packet['estimate_handoff']
    assert exchange.check_packet(case['case_id'],packet)['query_count']==4
    assert all(q['kind']=='conditional_outcome_mean' and q['own']==1 and q['exposure']==1 and 'assignment' not in q for q in h['queries'])
    changed=deepcopy(out);changed['joint_entry']['native_result']['certificate']['native_outcome']['result']['node_class_support'][0]='0'
    assert not workflow.replay(case,out['draft'],changed)


def test_signature_mixture_reuses_component_proofs_without_new_native_type():
    case,s=signature_fixture();t=s['target']['value']
    t['components'][0]['probability']='1/3'
    t['components'].append(dict(assignment={'A':0,'B':1,'C':1,'D':1},probability='2/3'))
    t['distribution_complete']=True
    s['information']['value']['signature_cells'].append(dict(node='A',own=0,exposure=1))
    out=finish(case,s);assert out['independent_replay'] and workflow.replay(case,out['draft'],out)
    c=out['joint_entry']['native_result']['certificate']
    assert c['kind']=='EXISTING_NETWORK_POLICY_COMPOSITION' and c['coefficients']==['1/3','2/3']
    h=exchange.packet(case,out)['estimate_handoff']
    assert len(h['queries'])==5
    assert all(q['kind']=='conditional_outcome_mean' for q in h['queries'])
    assert exchange.evaluate(h,{q['id']:str(q['own']) for q in h['queries']})=='5/6'
    assert sorted(len(q['source_target_fingerprints']) for q in h['queries'])==[1,1,2,2,2]
    old=exchange.packet(case,out,operator_revision=1)
    assert 'operator_revision' not in old
    assert exchange.check_packet(case['case_id'],old)['query_count']==8
    assert exchange.evaluate(old['estimate_handoff'],{q['id']:str(q['own']) for q in old['estimate_handoff']['queries']})=='5/6'
    new=exchange.packet(case,out)
    assert exchange.check_packet(case['case_id'],new)['query_count']==5
    changed=deepcopy(new);changed['estimate_handoff']['queries'][0]['source_target_fingerprints']=[]
    with pytest.raises(ValueError,match='JOINT_HANDOFF_REPLAY_MISMATCH'):exchange.check_packet(case['case_id'],changed)


@pytest.mark.parametrize('status,expected',[('NOT_ADOPTED','UNSUPPORTED'),('UNDECIDED','NEEDS_INPUT'),('UNKNOWN','NEEDS_INPUT')])
def test_signature_premise_is_never_inferred_from_summary_table(status,expected):
    case,s=signature_fixture();s['conditions'][-1]['status']=status
    out=prepared(case,s)
    assert out['joint_entry']['state']==expected and not out['backend_called']
    assert not out.get('condition_review')


def test_missing_observable_cell_does_not_get_filled_from_policy():
    case,s=signature_fixture();s['information']['value']['signature_cells'].pop()
    out=finish(case,s)
    assert not out['independent_replay'] and out['joint_entry']['state']!='POINT'
    with pytest.raises(ValueError):exchange.packet(case,out)


def test_adopted_individual_constraint_not_ignored_on_signature_route():
    case,s=signature_fixture();s['remaining']=[dict(code='individual',statement='每个对象在每种安排下都不会变差',status='ADOPTED',evidence=s['family']['evidence'])]
    out=prepared(case,s)
    assert out['joint_entry']['reason_code']=='UNEXPRESSED_ADDITIONAL_RESTRICTION' and not out['backend_called']
