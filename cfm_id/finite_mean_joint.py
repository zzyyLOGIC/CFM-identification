"""Reviewed explicit finite-mean constraint route, separate from all old bound solvers."""
from cfm_id_bridge.scientific_binding import sha
from .finite_mean_joint_contract import VERSION, ROUTE, JointMeanProblem, JointMeanReview, DECISIONS, validate, check_review
from .finite_mean_joint_solver import solve
from .finite_mean_joint_verify import replay
from .dag_backdoor_contract import Unavailable


def prepare(problem):
    try:
        p=validate(problem)
        return dict(state='REVIEW_REQUIRED',reason_code=None,backend_called=False,
            worksheet=dict(version=VERSION,problem_sha256=sha(p),decisions=list(DECISIONS),
                target=p.target,target_description=p.target_description,
                adopted_constraints=[c.id for c in p.constraints if c.adoption=='ADOPTED'],
                not_adopted_constraints=[c.id for c in p.constraints if c.adoption=='NOT_ADOPTED']))
    except Unavailable as e:
        return dict(state=e.state,reason_code=e.reason,backend_called=False)


def submit(problem,review):
    result=prepare(problem)
    result.update(production_admission=False,estimation_handoff_allowed=False,independent_replay=False)
    if result['state']!='REVIEW_REQUIRED': return result
    try:
        p=validate(problem); r=check_review(p,review)
        certificate=solve(p)
        passed=replay(certificate,p)
        return dict(state=certificate['status'] if passed else 'CHECK_BLOCKED',
            reason_code=None if passed else 'INDEPENDENT_REPLAY_FAILED',
            certificate=certificate if passed else None,independent_replay=passed,backend_called=True,
            review_authority=r.authority,production_admission=False,estimation_handoff_allowed=False)
    except Unavailable as e:
        return dict(result,state=e.state,reason_code=e.reason)
