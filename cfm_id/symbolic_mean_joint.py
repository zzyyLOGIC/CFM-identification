"""Reviewed symbolic joint bounds, additive to the numeric finite-mean route."""
from cfm_id_bridge.scientific_binding import sha
from .symbolic_mean_contract import VERSION,ROUTE,MODEL,DECISIONS,Problem,Review,validate,check_review
from .symbolic_mean_solver import solve
from .symbolic_mean_verify import replay,evaluate
from .dag_backdoor_contract import Unavailable

def prepare(problem):
    try:
        p=validate(problem)
        return dict(state='REVIEW_REQUIRED',reason_code=None,backend_called=False,
            worksheet=dict(version=VERSION,problem_sha256=sha(p),decisions=list(DECISIONS),target=p.target,
                target_description=p.target_description,parameter_domain=[x.model_dump() for x in p.parameters],
                adopted_constraints=[c.id for c in p.constraints if c.adoption=='ADOPTED'],
                not_adopted_constraints=[c.id for c in p.constraints if c.adoption=='NOT_ADOPTED']))
    except Unavailable as e:return dict(state=e.state,reason_code=e.reason,backend_called=False)

def submit(problem,review):
    result=prepare(problem)
    result.update(production_admission=False,estimation_handoff_allowed=False,independent_replay=False)
    if result['state']!='REVIEW_REQUIRED':return result
    try:
        p=validate(problem);r=check_review(p,review);cert=solve(p);verified=replay(cert,p)
        return dict(state='SYMBOLIC_BOUNDS' if verified else 'CHECK_BLOCKED',reason_code=None if verified else 'INDEPENDENT_REPLAY_FAILED',
            certificate=cert if verified else None,independent_replay=verified,backend_called=True,
            review_authority=r.authority,production_admission=False,estimation_handoff_allowed=False)
    except Unavailable as e:return dict(result,state=e.state,reason_code=e.reason)
