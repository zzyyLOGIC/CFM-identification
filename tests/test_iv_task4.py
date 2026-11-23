import pytest
from cfm_id.iv_types import enumerate_types
from cfm_id.iv_late_solver import identify_late
from cfm_id.iv_late_verify import verify_late_result
from cfm_id.iv_ate_solver import solve_ate_bounds
from cfm_id.iv_ate_verify import verify_ate_result

OBS_POS = {
    (0,0,0):1.0,(0,0,1):0.0,(0,1,0):0.0,(0,1,1):0.0,
    (1,0,0):0.5,(1,0,1):0.0,(1,1,0):0.0,(1,1,1):0.5,
}
OBS_NEG_HALF = {
    (0,0,0):0.0,(0,0,1):1.0,(0,1,0):0.0,(0,1,1):0.0,
    (1,0,0):0.0,(1,0,1):0.75,(1,1,0):0.125,(1,1,1):0.125,
}
OBS_MONOTONE_CONFLICT = {
    (0,0,0):0.6,(0,0,1):0.0,(0,1,0):0.0,(0,1,1):0.4,
    (1,0,0):0.5,(1,0,1):0.0,(1,1,0):0.4,(1,1,1):0.1,
}

def test_type_counts():
    assert len(enumerate_types(False))==16
    assert len(enumerate_types(True))==12

def test_positive_late_and_independent_replay():
    r=identify_late(OBS_POS,assumptions_accepted=True)
    assert r['status']=='POINT' and r['late']==pytest.approx(1.0)
    assert verify_late_result(OBS_POS,r)['valid']

def test_negative_late_is_legal_and_replayed():
    r=identify_late(OBS_NEG_HALF,assumptions_accepted=True)
    assert r['status']=='POINT'
    assert r['late']==pytest.approx(-0.5)
    assert r['logical_range']==[-1.0,1.0]
    assert verify_late_result(OBS_NEG_HALF,r)['valid']

def test_positive_first_stage_does_not_bypass_monotone_compatibility():
    assert sum(d*OBS_MONOTONE_CONFLICT[1,d,y] for d in (0,1) for y in (0,1)) > sum(d*OBS_MONOTONE_CONFLICT[0,d,y] for d in (0,1) for y in (0,1))
    r=identify_late(OBS_MONOTONE_CONFLICT,assumptions_accepted=True)
    assert r['status']=='INCOMPATIBLE'
    assert r['reason_code']=='OBSERVED_LAW_CONFLICTS_WITH_MONOTONE_IV_MODEL'

def test_late_requires_review_and_zero_first_stage_stops():
    assert identify_late(OBS_POS)['status']=='REVIEW_REQUIRED'
    no_fs={(z,d,y):.25 for z in (0,1) for d in (0,1) for y in (0,1)}
    assert identify_late(no_fs,assumptions_accepted=True)['reason_code']=='NO_POSITIVE_COMPLIER_MASS_LATE_UNDEFINED'

def test_ate_bounds_and_independent_replay_both_models():
    for mono,n in ((False,16),(True,12)):
        r=solve_ate_bounds(OBS_POS,monotonicity=mono)
        assert r['status']=='SHARP_BOUNDS' and r['type_count']==n
        assert verify_ate_result(OBS_POS,r,monotonicity=mono)['valid']

def test_tampered_ate_dual_and_target_are_rejected():
    r=solve_ate_bounds(OBS_POS,monotonicity=True)
    bad={**r,'upper_dual':list(r['upper_dual'])}
    bad['upper_dual'][0]+=0.25
    assert not verify_ate_result(OBS_POS,bad,monotonicity=True)['valid']
    bad_target={**r,'target':{'kind':'LATE'}}
    assert not verify_ate_result(OBS_POS,bad_target,monotonicity=True)['valid']

def test_invalid_input_is_not_reported_as_infeasible():
    bad=dict(OBS_POS);bad[(0,0,0)]=0.8
    assert solve_ate_bounds(bad)['status']=='CHECK_BLOCKED'

def test_incompatibility_has_independently_replayed_farkas_witness():
    late=identify_late(OBS_MONOTONE_CONFLICT,assumptions_accepted=True)
    ate=solve_ate_bounds(OBS_MONOTONE_CONFLICT,monotonicity=True)
    assert late['status']=='INCOMPATIBLE' and late['certificate']['kind']=='FARKAS_INCOMPATIBILITY'
    assert ate['status']=='INCOMPATIBLE' and ate['certificate']['kind']=='FARKAS_INCOMPATIBILITY'
    assert verify_late_result(OBS_MONOTONE_CONFLICT,late)['valid']
    assert verify_ate_result(OBS_MONOTONE_CONFLICT,ate,monotonicity=True)['valid']
    late['certificate']['normalization_l1']+=1
    ate['certificate']['contradiction_margin']+=1
    assert not verify_late_result(OBS_MONOTONE_CONFLICT,late)['valid']
    assert not verify_ate_result(OBS_MONOTONE_CONFLICT,ate,monotonicity=True)['valid']


def test_in_range_wald_still_requires_compatible_model():
    values=[.3,.3,.3,.1,.35,.05,.15,.45]
    law={(z,d,y):values[4*z+2*d+y] for z in (0,1) for d in (0,1) for y in (0,1)}
    dy=sum(y*(law[1,d,y]-law[0,d,y]) for d in (0,1) for y in (0,1))
    dd=sum(d*(law[1,d,y]-law[0,d,y]) for d in (0,1) for y in (0,1))
    assert dd>0 and dy/dd==pytest.approx(.5)
    late=identify_late(law,assumptions_accepted=True)
    ate=solve_ate_bounds(law,monotonicity=True)
    assert late['status']==ate['status']=='INCOMPATIBLE'
    assert verify_late_result(law,late)['valid']
    assert verify_ate_result(law,ate,monotonicity=True)['valid']


@pytest.mark.parametrize('value',[-1,1])
def test_late_endpoints(value):
    law={(z,d,y):float(d==z and y==(z if value==1 else 1-z))
         for z in (0,1) for d in (0,1) for y in (0,1)}
    result=identify_late(law,assumptions_accepted=True)
    assert result['late']==value and verify_late_result(law,result)['valid']


def test_replay_checks_witness_target_and_mapping_without_optimizer(monkeypatch):
    from copy import deepcopy
    late=identify_late(OBS_NEG_HALF,assumptions_accepted=True)
    ate=solve_ate_bounds(OBS_POS,monotonicity=True)
    def forbidden(*args,**kwargs):raise AssertionError('Verifier called optimizer')
    monkeypatch.setattr('scipy.optimize.linprog',forbidden)
    assert verify_late_result(OBS_NEG_HALF,late)['valid']
    assert verify_ate_result(OBS_POS,ate,monotonicity=True)['valid']
    for change in ('witness','target','types','mapping'):
        bad=deepcopy(late)
        if change=='witness':bad['certificate']['witness'][0]+=0.2
        if change=='target':bad['estimand']='ATE'
        if change=='types':bad['certificate']['types'].reverse()
        if change=='mapping':bad['model']['mapping']='Y=Y(Z)'
        assert not verify_late_result(OBS_NEG_HALF,bad)['valid']
    for change in ('target','types','mapping','objective'):
        bad=deepcopy(ate)
        if change=='target':bad['estimand']='LATE'
        if change=='types':bad['types'].reverse()
        if change=='mapping':bad['model']['observed_coordinates'].reverse()
        if change=='objective':bad['lower_objective']+=.1
        assert not verify_ate_result(OBS_POS,bad,monotonicity=True)['valid']


def test_solver_failures_and_small_first_stage_are_not_infeasibility(monkeypatch):
    law={(z,d,y):float(d==0 and y==0) for z in (0,1) for d in (0,1) for y in (0,1)}
    law[1,0,0]=1-1e-12;law[1,1,0]=1e-12
    assert identify_late(law,assumptions_accepted=True)['reason_code']=='FIRST_STAGE_NUMERICALLY_AMBIGUOUS'
    import networkx as nx
    def failed_transport(*args,**kwargs):raise nx.NetworkXError('Optimization failed')
    monkeypatch.setattr(nx,'network_simplex',failed_transport)
    assert identify_late(OBS_POS,assumptions_accepted=True)['status']=='CHECK_BLOCKED'
    assert solve_ate_bounds(OBS_POS)['reason_code']=='ATE_LP_NUMERICAL_FAILURE'


@pytest.mark.parametrize('tol',[float('nan'),float('inf'),-1,0,1,True])
def test_invalid_tolerance_cannot_authorize_late(tol):
    assert identify_late(OBS_POS,assumptions_accepted=True,tol=tol)['reason_code']=='INVALID_TOLERANCE'
