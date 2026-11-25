"""Explicit specialized contracts shared by CLI and web; no automatic fallback.

These entries retain native states (including resource stops and graph witnesses).
They are not forced into a narrower historical research-result vocabulary.
"""
from dataclasses import dataclass
from copy import deepcopy
from .entry_diagnostics import summarize


@dataclass(frozen=True)
class Entry:
    id: str
    label: str
    module: object
    problem_type: type
    review_type: type
    scope: str

    def parse_problem(self,value):
        return getattr(self.module,'parse_problem',self.problem_type.model_validate)(value)

    def problem_schema(self):
        return getattr(self.module,'problem_schema',self.problem_type.model_json_schema)()


def entries():
    from . import dag_id_route as single, dag_joint as joint, finite_mean_joint as means
    from . import symbolic_mean_joint as symbolic
    return (
        Entry(single.ROUTE,'一般变量图 ID 与不可识别见证',single,single.GeneralIdProblem,single.GeneralIdReview,
              'Existing single-variable intervention contract; retains native stop reasons.'),
        Entry(joint.ROUTE,'一般图的多变量联合干预',joint,joint.JointIdProblem,joint.JointIdReview,
              'Explicit static intervention set, finite discrete ADMG and positive observational joint; v1 known law, v2 joint samples with symbolic functional only; not conditional interventions.'),
        Entry(means.ROUTE,'有限均值等式与线性不等式联合求界',means,means.JointMeanProblem,means.JointMeanReview,
              'Explicit bounded finite means with adopted rational affine constraints; exact per-block search limits; source-reviewed finite network projection available.'),
        Entry(symbolic.ROUTE,'带符号参数的联合均值界限',symbolic,symbolic.Problem,symbolic.Review,
              'Finite bounded means, fixed rational coefficients, affine parameters in bounds/right-hand sides; complete parametric basis certificates, finite work limit.'),
    )


def resolve(id):
    return next((e for e in entries() if e.id==id),None)


def inventory():
    return [dict(route_id=e.id,label=e.label,scope=e.scope,problem_type=e.problem_type.__module__+'.'+e.problem_type.__name__,
                 native_module=e.module.__name__,input_level='EXPLICIT_MATHEMATICAL_PROBLEM',
                 automatic_business_reading=e.id in ('DAG_GENERAL_ID','DAG_JOINT_ID','FINITE_MEAN_JOINT','SYMBOLIC_MEAN_JOINT'),
                 business_reading_scope={
                     'DAG_GENERAL_ID':'Source-audited one-treatment, one-outcome unconditional intervention distribution with complete observed population law; original reading declarations and explicit scientific confirmation retained.',
                     'DAG_JOINT_ID':'Source-audited unconditional joint intervention distribution; explicit scientific confirmation required.',
                     'FINITE_MEAN_JOINT':'Source-audited finite randomized network, exact population means, complete adopted affine restrictions; explicit scientific confirmation required.',
                     'SYMBOLIC_MEAN_JOINT':'Explicit complete finite mean model and parameter domains, source-reviewed from original materials; not inferred from a network definition.',
                 }.get(e.id),
                 production_admission=False,estimation_handoff_allowed=False) for e in entries()]


def run(id,problem,review=None):
    e=resolve(id)
    if e is None: raise ValueError('UNKNOWN_DEDICATED_ENTRY')
    p=e.parse_problem(deepcopy(problem.model_dump() if hasattr(problem,'model_dump') else problem))
    r=None if review is None else e.review_type.model_validate(deepcopy(review.model_dump() if hasattr(review,'model_dump') else review))
    result=e.module.prepare(p) if r is None else e.module.submit(p,r)
    return dict(result,entry_diagnostics=summarize(result,operation=id,problem=p.model_dump()))
