"""Finite parametric mean LP: fixed rational normals, affine right hand sides.

No natural-language assumptions are introduced. An explicit complete model and
source-bound scientific review are prerequisites, as for the numeric route.
"""
from fractions import Fraction as F
from typing import Literal
from pydantic import Field
from cfm_id_bridge.scientific_binding import sha
from .dag_backdoor_contract import Record,fail
from .finite_mean_joint_contract import rational as Q,DECISIONS

VERSION='symbolic-mean-joint-1'
ROUTE='SYMBOLIC_MEAN_JOINT'
MODEL='FINITE_MEANS_AFFINE_PARAMETERS'

class Affine(Record):
    constant: str
    coefficients: dict[str,str]

class Parameter(Record):
    id: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_]{0,39}$')
    description: str = Field(min_length=3)
    lower: str
    upper: str
    source_ids: list[str] = Field(min_length=1)

class Coordinate(Record):
    id: str = Field(min_length=1,max_length=200)
    description: str = Field(min_length=3)
    lower: Affine
    upper: Affine
    known: Affine | None
    source_ids: list[str] = Field(min_length=1)

class Constraint(Record):
    id: str = Field(min_length=1,max_length=200)
    coefficients: dict[str,str]
    relation: Literal['EQ','LE','GE']
    rhs: Affine
    adoption: Literal['ADOPTED','UNDECIDED','NOT_ADOPTED']
    source_ids: list[str] = Field(min_length=1)

class Problem(Record):
    version: Literal['symbolic-mean-joint-1']
    model: Literal['FINITE_MEANS_AFFINE_PARAMETERS']
    outcome_domain: Literal['BINARY','REAL']
    context: str = Field(min_length=3)
    target_description: str = Field(min_length=3)
    target: dict[str,str]
    target_offset: Affine
    parameters: list[Parameter] = Field(min_length=1,max_length=8)
    coordinates: list[Coordinate] = Field(min_length=1,max_length=12)
    constraints: list[Constraint] = Field(max_length=128)
    # Parameter-only restrictions are Constraint rows with empty coefficients.
    sources: dict[str,str]
    information: Literal['POPULATION_MEANS','FINITE_SAMPLE','UNKNOWN']
    model_complete: bool | None
    unresolved: list[str]
    additional_restrictions: list[str]

class Review(Record):
    version: Literal['symbolic-mean-joint-1']
    problem_sha256: str
    reviewer: str = Field(min_length=3)
    evidence: str = Field(min_length=12)
    authority: Literal['EXTERNAL_RESEARCH_REVIEW','SYNTHETIC_TEST']
    decisions: dict[str,Literal['ACCEPTED','PENDING','REJECTED']]

def vector(value,names):
    value=value.model_dump() if isinstance(value,Affine) else value
    if not set(value['coefficients'])<=set(names):raise ValueError('UNKNOWN_PARAMETER')
    return [Q(value['constant']),*(Q(value['coefficients'].get(k,'0')) for k in names)]

def evaluate_affine(value,parameters):
    names=list(parameters)
    return sum((a*b for a,b in zip(vector(value,names),[F(1),*(Q(parameters[k]) for k in names)])),F(0))

def validate(problem):
    p=Problem.model_validate(problem)
    ids=[c.id for c in p.coordinates];names=[x.id for x in p.parameters]
    if len(set(ids))!=len(ids) or len(set(names))!=len(names) or len({c.id for c in p.constraints})!=len(p.constraints):
        fail('CHECK_BLOCKED','DUPLICATE_SYMBOLIC_COORDINATE')
    if not p.sources or any(not k.strip() or not v.strip() for k,v in p.sources.items()):fail('NEEDS_INPUT','SOURCE_TEXT_REQUIRED')
    for row in [*p.parameters,*p.coordinates,*p.constraints]:
        if len(set(row.source_ids))!=len(row.source_ids) or not set(row.source_ids)<=p.sources.keys():fail('CHECK_BLOCKED','INVALID_SYMBOLIC_SOURCE')
    for x in p.parameters:
        if Q(x.lower)>Q(x.upper):fail('CHECK_BLOCKED','EMPTY_PARAMETER_INTERVAL')
    for co in [p.target,*(c.coefficients for c in p.constraints)]:
        if not set(co)<=set(ids):fail('CHECK_BLOCKED','UNKNOWN_MEAN_COORDINATE')
        for v in co.values():Q(v)
    vector(p.target_offset,names)
    for c in p.coordinates:
        for v in [c.lower,c.upper]+([c.known] if c.known is not None else []):vector(v,names)
    for c in p.constraints:vector(c.rhs,names)
    if p.model_complete is not True:fail('NEEDS_INPUT','FINITE_MEAN_MODEL_NOT_COMPLETE')
    if p.information!='POPULATION_MEANS':fail('NEEDS_INPUT','SAMPLE_IS_NOT_POPULATION_INFORMATION')
    if p.unresolved or any(c.adoption=='UNDECIDED' for c in p.constraints):fail('NEEDS_INPUT','SCIENTIFIC_DECISION_UNRESOLVED')
    if p.additional_restrictions:fail('UNSUPPORTED','ADDITIONAL_RESTRICTIONS_NOT_EXPRESSED')
    return p

def check_review(p,review):
    if review is None:fail('REVIEW_REQUIRED','EXTERNAL_REVIEW_REQUIRED')
    r=Review.model_validate(review)
    if r.problem_sha256!=sha(p):fail('CHECK_BLOCKED','STALE_SYMBOLIC_MEAN_REVIEW')
    if set(r.decisions)!=set(DECISIONS):fail('CHECK_BLOCKED','EXACT_REVIEW_DECISIONS_REQUIRED')
    if 'REJECTED' in r.decisions.values():fail('CHECK_BLOCKED','SCIENTIFIC_CONDITION_REJECTED')
    if 'PENDING' in r.decisions.values():fail('REVIEW_REQUIRED','SCIENTIFIC_CONDITION_PENDING')
    return r

def numeric_problem(problem,parameters):
    p=validate(problem)
    if set(parameters)!={x.id for x in p.parameters}:raise ValueError('EXACT_PARAMETER_VALUES_REQUIRED')
    for x in p.parameters:
        if not Q(x.lower)<=Q(parameters[x.id])<=Q(x.upper):raise ValueError('PARAMETER_OUTSIDE_DECLARED_DOMAIN')
    out=p.model_dump();out.update(version='finite-mean-joint-1',model='FINITE_MEANS_WITH_DECLARED_LINEAR_CONSTRAINTS')
    out.pop('parameters');out['target_offset']=str(evaluate_affine(p.target_offset,parameters))
    for row in out['coordinates']:
        for key in ('lower','upper','known'):
            if row[key] is not None:row[key]=str(evaluate_affine(row[key],parameters))
    for row in out['constraints']:row['rhs']=str(evaluate_affine(row['rhs'],parameters))
    return out
