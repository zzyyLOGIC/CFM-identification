"""Joint intervention entry: reuse the unchanged ID recursion on an explicit set."""
from types import SimpleNamespace
from cfm_id_bridge.scientific_binding import sha
from .dag_joint_contract import VERSION, ROUTE, JointIdProblem, JointIdReview, validate, check_review, DECISIONS
from .dag_joint_contract import SYMBOLIC_SAMPLE_VERSION, decisions_for, information_basis, parse_problem, problem_schema
from .dag_backdoor_contract import Unavailable
from .dag_id_contract import Unavailable as MathUnavailable
from .dag_id_solver import _id, positivity_requirements
from .dag_id_verify import check_hedge
from .dag_joint_verify import replay


def solve(problem):
    p = validate(problem)
    trace = []
    try:
        expression = _id(p.as_graph(), set(p.outcome), set(p.treatments), {'operation':'OBSERVED_JOINT'}, trace, 0)
    except MathUnavailable as error:
        witness = getattr(error, 'witness', None)
        original = SimpleNamespace(nodes=p.nodes, directed=p.directed, bidirected=p.bidirected,
                                   treatment=p.treatments, outcome=p.outcome)
        checked = check_hedge(witness['hedge'], original) if witness and 'hedge' in witness else {'passed':False}
        proved = error.state == 'UNSUPPORTED' and checked.get('passed') is True
        return dict(status='NONIDENTIFIABLE' if proved else 'NO_FORMULA_YET' if witness else error.state,
                    reason_code=error.reason, problem_sha256=sha(p), witness=witness,
                    evidence_report=checked, nonidentification_proved=proved)
    cert = dict(version=p.version, status='POINT', theorem='SHPITSER_PEARL_2006_ID', problem_sha256=sha(p),
                target=dict(treatments=p.treatments, outcome=p.outcome, context=p.context),
                graph=p.as_graph(), functional=expression, positivity=positivity_requirements(expression), derivation=trace)
    if p.version == SYMBOLIC_SAMPLE_VERSION:
        cert['information_basis'] = information_basis(p)
    cert['certificate_sha256'] = sha(cert)
    return cert


def prepare(problem):
    try:
        p = validate(problem)
        return dict(state='REVIEW_REQUIRED', reason_code=None, backend_called=False,
                    worksheet=dict(version=p.version, problem_sha256=sha(p), decisions=list(decisions_for(p)),
                                   treatments=p.treatments, outcome=p.outcome, context=p.context))
    except (Unavailable, MathUnavailable) as e:
        return dict(state=e.state, reason_code=e.reason, backend_called=False)


def submit(problem, review):
    result = prepare(problem)
    result.update(production_admission=False, estimation_handoff_allowed=False, independent_replay=False)
    if result['state'] != 'REVIEW_REQUIRED':
        return result
    try:
        p = validate(problem)
        r = check_review(p, review)
        cert = solve(p)
        if cert['status'] == 'POINT':
            passed = replay(cert, p)
            return dict(state='POINT' if passed else 'CHECK_BLOCKED',
                        reason_code=None if passed else 'INDEPENDENT_REPLAY_FAILED',
                        certificate=cert if passed else None, independent_replay=passed, backend_called=True,
                        review_authority=r.authority, production_admission=False, estimation_handoff_allowed=False)
        return dict(state=cert['status'], reason_code=cert.get('reason_code'), evidence=cert,
                    nonidentification_proved=cert.get('nonidentification_proved', False), backend_called=True,
                    independent_replay=False, production_admission=False, estimation_handoff_allowed=False)
    except (Unavailable, MathUnavailable) as e:
        return dict(result, state=e.state, reason_code=e.reason)
