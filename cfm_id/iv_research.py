"""Explicit reviewed IV research entry; no automatic business approval or handoff."""
from cfm_id_bridge.scientific_binding import sha
from .iv_route_contract import (VERSION,IVProblem,IVReview,IVUnavailable,validate,digest,check_review,READING_DECISIONS,SCIENCE_DECISIONS,science_decisions)
from .iv_late_solver import identify_late
from .iv_ate_solver import solve_ate_bounds
from .iv_ate_verify import verify_ate_result
from .iv_late_verify import verify_late_result


def solve(problem):
    p=validate(problem)
    if p.target=='LATE': result = identify_late(p.observed(),assumptions_accepted=True)
    else: result = solve_ate_bounds(p.observed(),monotonicity=p.monotonicity)
    result['problem_sha256'] = digest(p)
    return result

def prepare(problem):
    out=dict(entry='BINARY_IV_LATE_ATE',state='REVIEW_REQUIRED',backend_called=False,
        certificate_replayed=False,reading_review_recorded=False,science_review_recorded=False,
        scientific_approval=False,production_admission=False,estimation_handoff_allowed=False)
    try:
        p=validate(problem)
        out['worksheet']=dict(version=VERSION,problem_sha256=digest(p),is_approval=False,
            reading_decisions={k:'PENDING' for k in READING_DECISIONS},
            science_decisions={k:'PENDING' for k in science_decisions(p)})
    except IVUnavailable as exc: out.update(state=exc.state,reason_code=exc.reason)
    except (ValueError,TypeError,AttributeError): out.update(state='CHECK_BLOCKED',reason_code='INVALID_IV_PROBLEM_CONTRACT')
    return out


def submit(problem,*,review=None,research_protocol_selected=False):
    out=prepare(problem)
    if out['state']!='REVIEW_REQUIRED' or research_protocol_selected is not True:return out
    try:
        p=validate(problem); r=check_review(p,review)
        out.update(reading_review_recorded=True,science_review_recorded=True,
            review_sha256=sha(r),backend_called=True)
        if p.target=='LATE':
            result=solve(p)
            if result['status']=='POINT':
                replay=verify_late_result(p.observed(),result)
                if replay.get('valid') is not True: raise IVUnavailable('CHECK_BLOCKED','INDEPENDENT_LATE_REPLAY_FAILED')
                out.update(state='POINT',claim=dict(kind='POINT',estimand='LATE_FOR_COMPLIERS',value=result['late'],logical_range=[-1.0,1.0]),native_result=result,certificate=result,certificate_replayed=True,replay=replay)
            elif result['status']=='INCOMPATIBLE':
                replay=verify_late_result(p.observed(),result)
                if replay.get('valid') is not True: raise IVUnavailable('CHECK_BLOCKED','INDEPENDENT_LATE_INCOMPATIBILITY_REPLAY_FAILED')
                out.update(state='INCOMPATIBLE',reason_code=result.get('reason_code'),native_result=result,certificate=result,certificate_replayed=True,replay=replay)
            else: out.update(state=result['status'],reason_code=result.get('reason_code'),native_result=result)
        else:
            result=solve(p)
            if result['status']=='SHARP_BOUNDS':
                replay=verify_ate_result(p.observed(),result,monotonicity=p.monotonicity)
                if replay.get('valid') is not True: raise IVUnavailable('CHECK_BLOCKED','INDEPENDENT_ATE_CERTIFICATE_REPLAY_FAILED')
                bounds=result['exact']['bounds']
                out.update(state='PARTIAL' if bounds[0] != bounds[1] else 'POINT',
                    claim=dict(kind='SHARP_ATE_BOUNDS',estimand='ATE',interval=result['bounds'],exact_interval=bounds),
                    certificate=result,certificate_replayed=True,replay=replay)
            elif result['status']=='INCOMPATIBLE':
                replay=verify_ate_result(p.observed(),result,monotonicity=p.monotonicity)
                if replay.get('valid') is not True: raise IVUnavailable('CHECK_BLOCKED','INDEPENDENT_ATE_INCOMPATIBILITY_REPLAY_FAILED')
                out.update(state='INCOMPATIBLE',reason_code=result.get('reason_code'),native_result=result,certificate=result,certificate_replayed=True,replay=replay)
            else: out.update(state=result['status'],reason_code=result.get('reason_code'),native_result=result)
    except IVUnavailable as exc: out.update(state=exc.state,reason_code=exc.reason)
    except (ValueError,TypeError,KeyError,AttributeError): out.update(state='CHECK_BLOCKED',reason_code='INVALID_REVIEW_OR_IV_EVIDENCE')
    return out
