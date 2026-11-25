from copy import deepcopy
from fractions import Fraction as F
from itertools import product
import pytest
from cfm_id import joint_natural_entry as workflow
from cfm_id.joint_query_exchange import packet,check_packet,evaluate
from test_network_existing_entry import fixture,prepared


def bounded(contrast=True):
    case,s=fixture(True);ev=s['family']['evidence']
    s['conditions'][-1]['status']='NOT_ADOPTED'
    s['conditions'].append(dict(code='complete_bounded_model',statement='没有其他限制',status='ADOPTED',evidence=ev))
    if contrast:s['target']['value'].update(quantity='DIFFERENCE',reference_components=[dict(assignment={'A':0,'B':0},probability=None)])
    return case,s


def finish(case,s):
    r=prepared(case,s);sheet=r['condition_review']
    return workflow.complete(case,r,dict(binding=sheet['binding'],authority='SYNTHETIC_TEST',decisions={x['code']:'ADOPTED' for x in sheet['items']}))


@pytest.mark.parametrize('mixed',[False,True])
def test_joint_policies_have_attainable_bounds_under_full_potential_outcome_worlds(mixed):
    case,s=bounded();t=s['target']['value']
    if mixed:
        t['components']=[dict(assignment={'A':1,'B':1},probability='1/4'),dict(assignment={'A':0,'B':0},probability='3/4')]
        t['reference_components']=[dict(assignment={'A':1,'B':1},probability='3/4'),dict(assignment={'A':0,'B':0},probability='1/4')]
    r=finish(case,s);assert workflow.replay(case,r['draft'],r)
    p=packet(case,r);assert check_packet(case['case_id'],p)['query_count']==4
    h=p['estimate_handoff'];nodes=['A','B'];assignments=list(product((0,1),repeat=2))
    d={z:F(0) for z in assignments}
    for sign,side in [(1,t['components']),(-1,t['reference_components'])]:
        for c in side:d[tuple(c['assignment'][n] for n in nodes)]+=sign*F(c['probability'] or '1')
    for seed in range(5):
        means={(node,z):F((seed+2*i+j)%6,5) for i,node in enumerate(nodes) for j,z in enumerate(assignments)}
        values={q['id']:str(means[(q['unit'],tuple(q['assignment']))]) for q in h['queries']}
        actual=evaluate(h,values)
        extremes=[]
        for maximize in (False,True):
            # Explicit conditional potential-outcome worlds, not the producer's residual boxes.
            # Bernoulli draws with these means are jointly constructible for every actual A.
            worlds={(i,z,a):(means[(i,a)] if z==a else F(int((d[z]>0)==maximize)))
                    for i in nodes for z in assignments for a in assignments}
            for i in nodes:
                for a in assignments:assert worlds[i,a,a]==means[i,a]  # consistency + all observed means
            effect=sum(F(1,2)*d[z]*sum(F(1,4)*worlds[i,z,a] for a in assignments) for i in nodes for z in assignments)
            extremes.append(effect)
        assert (F(actual['lower']),F(actual['upper']))==tuple(extremes)
    corrupt=deepcopy(r);corrupt['joint_entry']['projection']['parameter_queries'][0]['assignment']=[0,1]
    assert not workflow.replay(case,corrupt['draft'],corrupt)


def test_identical_policies_cancel_jointly_instead_of_subtracting_separate_bounds():
    case,s=bounded();s['target']['value']['reference_components']=deepcopy(s['target']['value']['components'])
    r=finish(case,s);c=r['joint_entry']['native_result']['certificate']
    assert (c['lower'],c['upper'])==('0','0') and workflow.replay(case,r['draft'],r)


def test_off_support_binary_policy_gets_range_without_invented_mean_queries():
    case,s=bounded(False)
    s['information']['value']['assignment_masses']=[dict(assignment={'A':0,'B':0},probability='1')]
    r=finish(case,s);c=r['joint_entry']['native_result']['certificate']
    assert (c['lower'],c['upper'])==('0','1')
    assert not packet(case,r)['estimate_handoff']['queries']


@pytest.mark.parametrize('change,reason',[
    ('extra','UNEXPRESSED_ADDITIONAL_RESTRICTION'),('sufficiency','BOUNDED_EXPOSURE_RESTRICTION_NOT_PROJECTED'),
    ('pending','UNDECIDED_RESTRICTION'),('incomplete','NETWORK_INFORMATION_REQUIRED'),
    ('missing_mean','BOUNDS_CONDITIONAL_MEAN_NOT_COVERED'),
])
def test_no_restriction_or_source_gap_can_be_erased(change,reason):
    case,s=bounded();ev=s['family']['evidence']
    if change in ('extra','pending'):s['remaining']=[dict(code='individual',statement='任何人都不能变差',status='ADOPTED' if change=='extra' else 'UNDECIDED',evidence=ev)]
    if change=='sufficiency':s['conditions'].append(dict(code='mean_sufficiency',statement='采用均值充分性',status='ADOPTED',evidence=ev))
    if change=='incomplete':s['conditions'][-1]['status']='UNKNOWN'
    if change=='missing_mean':s['information']['value']['outcome_nodes']=['A']
    r=prepared(case,s)
    assert r['joint_entry']['reason_code']==reason and not r['backend_called']
