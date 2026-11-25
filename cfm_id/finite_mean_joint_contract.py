"""Explicit finite mean model with rational affine constraints; no assumed causal reading."""
from fractions import Fraction
from typing import Literal
from pydantic import Field
from cfm_id_bridge.scientific_binding import sha
from .dag_backdoor_contract import Record, fail

VERSION = 'finite-mean-joint-1'
ROUTE = 'FINITE_MEAN_JOINT'
MODEL = 'FINITE_MEANS_WITH_DECLARED_LINEAR_CONSTRAINTS'
DECISIONS = ('target_and_coordinates', 'population_information_and_bounds',
             'complete_finite_mean_model', 'adopted_constraints_and_sources')


def rational(value):
    if type(value) is not str or len(value) > 100:
        raise ValueError('EXACT_RATIONAL_STRING_REQUIRED')
    q = Fraction(value)
    if q.numerator.bit_length() > 256 or q.denominator.bit_length() > 256:
        raise ValueError('RATIONAL_SIZE_LIMIT')
    return q


class Coordinate(Record):
    id: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=3, max_length=2000)
    lower: str
    upper: str
    known: str | None
    source_ids: list[str] = Field(min_length=1)


class Constraint(Record):
    id: str = Field(min_length=1, max_length=200)
    coefficients: dict[str, str]
    relation: Literal['EQ', 'LE', 'GE']
    rhs: str
    adoption: Literal['ADOPTED', 'UNDECIDED', 'NOT_ADOPTED']
    source_ids: list[str] = Field(min_length=1)


class JointMeanProblem(Record):
    version: Literal['finite-mean-joint-1']
    model: Literal['FINITE_MEANS_WITH_DECLARED_LINEAR_CONSTRAINTS']
    outcome_domain: Literal['BINARY', 'REAL']
    context: str = Field(min_length=3)
    target_description: str = Field(min_length=3)
    target: dict[str, str]
    target_offset: str
    coordinates: list[Coordinate] = Field(min_length=1, max_length=128)
    constraints: list[Constraint] = Field(max_length=256)
    sources: dict[str, str]
    information: Literal['POPULATION_MEANS', 'FINITE_SAMPLE', 'UNKNOWN']
    model_complete: bool | None
    unresolved: list[str]
    additional_restrictions: list[str]


class JointMeanReview(Record):
    version: Literal['finite-mean-joint-1']
    problem_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    reviewer: str = Field(min_length=3)
    evidence: str = Field(min_length=12)
    authority: Literal['EXTERNAL_RESEARCH_REVIEW', 'SYNTHETIC_TEST']
    decisions: dict[str, Literal['ACCEPTED', 'PENDING', 'REJECTED']]


def validate(problem):
    p = JointMeanProblem.model_validate(problem.model_dump() if isinstance(problem, JointMeanProblem) else problem)
    ids = [c.id for c in p.coordinates]
    if len(set(ids)) != len(ids) or len({c.id for c in p.constraints}) != len(p.constraints):
        fail('CHECK_BLOCKED', 'DUPLICATE_COORDINATE_OR_CONSTRAINT')
    if not p.sources or any(not k.strip() or not v.strip() for k,v in p.sources.items()):
        fail('NEEDS_INPUT', 'SOURCE_TEXT_REQUIRED')
    for c in [*p.coordinates, *p.constraints]:
        if len(set(c.source_ids)) != len(c.source_ids) or not set(c.source_ids) <= p.sources.keys():
            fail('CHECK_BLOCKED', 'UNKNOWN_OR_DUPLICATE_SOURCE_REFERENCE')
    for values in [p.target, *(c.coefficients for c in p.constraints)]:
        if not set(values) <= set(ids):
            fail('CHECK_BLOCKED', 'UNKNOWN_MEAN_COORDINATE')
        for v in values.values(): rational(v)
    rational(p.target_offset)
    for c in p.coordinates:
        rational(c.lower); rational(c.upper)
        if c.known is not None: rational(c.known)
    for c in p.constraints: rational(c.rhs)
    if p.model_complete is not True:
        fail('NEEDS_INPUT', 'FINITE_MEAN_MODEL_NOT_COMPLETE')
    if p.information != 'POPULATION_MEANS':
        fail('NEEDS_INPUT', 'SAMPLE_IS_NOT_POPULATION_INFORMATION')
    if p.unresolved or any(c.adoption == 'UNDECIDED' for c in p.constraints):
        fail('NEEDS_INPUT', 'SCIENTIFIC_DECISION_UNRESOLVED')
    if p.additional_restrictions:
        fail('UNSUPPORTED', 'ADDITIONAL_RESTRICTIONS_NOT_EXPRESSED')
    return p


def check_review(p, review):
    if review is None: fail('REVIEW_REQUIRED', 'EXTERNAL_REVIEW_REQUIRED')
    r = JointMeanReview.model_validate(review.model_dump() if isinstance(review, JointMeanReview) else review)
    if r.problem_sha256 != sha(p): fail('CHECK_BLOCKED', 'STALE_JOINT_MEAN_REVIEW')
    if set(r.decisions) != set(DECISIONS): fail('CHECK_BLOCKED', 'EXACT_REVIEW_DECISIONS_REQUIRED')
    if 'REJECTED' in r.decisions.values(): fail('CHECK_BLOCKED', 'SCIENTIFIC_CONDITION_REJECTED')
    if 'PENDING' in r.decisions.values(): fail('REVIEW_REQUIRED', 'SCIENTIFIC_CONDITION_PENDING')
    return r
