"""Set-valued static interventions. The original single-treatment contract is unchanged."""
from typing import Literal,Annotated
from pydantic import Field,TypeAdapter
from cfm_id_bridge.scientific_binding import sha
from .dag_backdoor_contract import Record, DECISIONS, Unavailable, fail
from .dag_id_contract import as_problem, validate as validate_graph

VERSION = 'dag-joint-id-1'
SYMBOLIC_SAMPLE_VERSION = 'dag-joint-id-2'
ROUTE = 'DAG_JOINT_ID'


class JointIdProblem(Record):
    version: Literal['dag-joint-id-1']
    model: Literal['RECURSIVE_SEMI_MARKOVIAN_DISCRETE']
    nodes: list[str] = Field(min_length=2)
    directed: list[list[str]]
    bidirected: list[list[str]]
    treatments: list[str] = Field(min_length=1)
    outcome: list[str] = Field(min_length=1)
    context: str = Field(min_length=3)
    graph_status: Literal['RESEARCHER_CONFIRMED', 'UNKNOWN']
    graph_source: str = Field(min_length=3)
    materials_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    information: Literal['FULL_JOINT_POPULATION_LAW', 'FINITE_SAMPLE', 'MARGINAL_STATISTICS', 'UNKNOWN']
    information_variables: list[str]
    strictly_positive_joint: bool | None
    unresolved: list[str]
    additional_restrictions: list[str]

    def as_graph(self):
        return dict(nodes=list(self.nodes), directed=sorted(map(tuple, self.directed)),
                    bidirected=sorted(tuple(sorted(e)) for e in self.bidirected))


class JointIdReview(Record):
    version: Literal['dag-joint-id-1', 'dag-joint-id-2']
    problem_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    reviewer: str = Field(min_length=3)
    evidence: str = Field(min_length=12)
    authority: Literal['EXTERNAL_RESEARCH_REVIEW', 'SYNTHETIC_TEST']
    decisions: dict[str, Literal['ACCEPTED', 'PENDING', 'REJECTED']]


class SampleJointIdProblem(JointIdProblem):
    """A functional of the target observational law, never its sample plug-in."""
    version: Literal['dag-joint-id-2']
    information: Literal['FINITE_SAMPLE']
    joint_observations: Literal[True]
    sample_size: int | None = Field(ge=0)
    output_kind: Literal['SYMBOLIC_FUNCTIONAL_ONLY']


def decisions_for(p):
    if p.version == SYMBOLIC_SAMPLE_VERSION:
        return (*DECISIONS[:-1], 'observed_variable_scope_and_strict_positivity')
    return DECISIONS


def information_basis(p):
    return dict(kind=p.information, variables=p.information_variables,
                joint_observations=p.joint_observations, sample_size=p.sample_size,
                output_kind=p.output_kind, numeric_population_known=False,
                sampling_and_estimation_validity='NOT_ASSESSED')


def parse_problem(problem):
    raw = problem.model_dump() if isinstance(problem, JointIdProblem) else problem
    cls = SampleJointIdProblem if raw.get('version') == SYMBOLIC_SAMPLE_VERSION else JointIdProblem
    return cls.model_validate(raw)


def problem_schema():
    return TypeAdapter(Annotated[JointIdProblem|SampleJointIdProblem,Field(discriminator='version')]).json_schema()


def validate(problem):
    p = parse_problem(problem)
    if len(set(p.treatments)) != len(p.treatments):
        fail('CHECK_BLOCKED', 'DUPLICATE_INTERVENTION_VARIABLE')
    # Reuse unchanged graph/domain/scale validation, not single-variable identification.
    for x in p.treatments:
        validate_graph(as_problem(p.nodes, p.directed, p.bidirected, x, p.outcome, p.context))
    if p.graph_status != 'RESEARCHER_CONFIRMED':
        fail('NEEDS_INPUT', 'GRAPH_NOT_CONFIRMED_BY_RESEARCHER')
    if p.version == VERSION and p.information != 'FULL_JOINT_POPULATION_LAW':
        fail('NEEDS_INPUT', 'INFORMATION_IS_NOT_A_POPULATION_LAW')
    if len(set(p.information_variables)) != len(p.information_variables) or set(p.information_variables) != set(p.nodes):
        fail('NEEDS_INPUT', 'POPULATION_LAW_VARIABLE_COVERAGE_MISMATCH')
    if p.strictly_positive_joint is not True:
        fail('NEEDS_INPUT' if p.strictly_positive_joint is None else 'UNSUPPORTED', 'STRICT_POSITIVITY_NOT_ESTABLISHED')
    if p.unresolved:
        fail('NEEDS_INPUT', 'UNRESOLVED_MATERIAL_ITEMS')
    if p.additional_restrictions:
        fail('UNSUPPORTED', 'ADDITIONAL_RESTRICTIONS_NOT_EXPRESSED')
    return p


def check_review(p, review):
    if review is None:
        fail('REVIEW_REQUIRED', 'EXTERNAL_REVIEW_REQUIRED')
    r = JointIdReview.model_validate(review.model_dump() if isinstance(review, JointIdReview) else review)
    if r.version != p.version:
        fail('CHECK_BLOCKED', 'JOINT_ID_REVIEW_VERSION_MISMATCH')
    if r.problem_sha256 != sha(p):
        fail('CHECK_BLOCKED', 'STALE_JOINT_ID_REVIEW')
    if set(r.decisions) != set(decisions_for(p)):
        fail('CHECK_BLOCKED', 'EXACT_REVIEW_DECISIONS_REQUIRED')
    if 'REJECTED' in r.decisions.values():
        fail('CHECK_BLOCKED', 'SCIENTIFIC_CONDITION_REJECTED')
    if 'PENDING' in r.decisions.values():
        fail('REVIEW_REQUIRED', 'SCIENTIFIC_CONDITION_PENDING')
    return r
