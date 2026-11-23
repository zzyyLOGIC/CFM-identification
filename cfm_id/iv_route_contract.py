"""Source-bound binary-IV research contract with separate reading/science reviews."""
from typing import Literal
import hashlib, json
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .iv_contract import validate_observed, rational

VERSION='binary-iv-research-1'
ROUTE='BINARY_IV_LATE_ATE'
READING_DECISIONS=('target_and_variable_coding','complete_observed_conditional_law','source_and_population_scope')
SCIENCE_DECISIONS=('instrument_independence','exclusion_restriction','monotonicity_direction','consistency_and_binary_outcome','no_interference','positive_instrument_support')

def science_decisions(problem):
    return tuple(k for k in SCIENCE_DECISIONS if k != 'monotonicity_direction' or problem.monotonicity)

class StrictRecord(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,frozen=True)

class IVCell(StrictRecord):
    z: Literal[0,1]
    d: Literal[0,1]
    y: Literal[0,1]
    probability: str = Field(min_length=1,max_length=40)
    @model_validator(mode='after')
    def probability_is_valid(self):
        if not 0 <= rational(self.probability) <= 1: raise ValueError('PROBABILITY_OUT_OF_RANGE')
        return self

class IVProblem(StrictRecord):
    version: Literal['binary-iv-research-1']
    target: Literal['LATE','ATE']
    cells: list[IVCell] = Field(min_length=8,max_length=8)
    monotonicity: bool
    instrument: str = Field(min_length=1,max_length=300)
    treatment: str = Field(min_length=1,max_length=300)
    outcome: str = Field(min_length=1,max_length=300)
    population: str = Field(min_length=3,max_length=2000)
    context: str = Field(min_length=3,max_length=2000)
    source_ids: list[str] = Field(min_length=1,max_length=30)
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    assumptions: list[str] = Field(min_length=1,max_length=20)
    @model_validator(mode='after')
    def complete(self):
        coords=[(c.z,c.d,c.y) for c in self.cells]
        if len(set(coords))!=8: raise ValueError('ALL_EIGHT_DISTINCT_OBSERVED_CELLS_REQUIRED')
        law={(c.z,c.d,c.y):c.probability for c in self.cells}
        validate_observed(law)
        if len(set(self.source_ids))!=len(self.source_ids): raise ValueError('UNIQUE_SOURCE_IDS_REQUIRED')
        if self.target=='LATE' and self.monotonicity is not True:
            raise ValueError('LATE_REQUIRES_DECLARED_D1_GE_D0_MONOTONICITY')
        return self
    def observed(self): return {(c.z,c.d,c.y):rational(c.probability) for c in self.cells}

class IVReadingReview(StrictRecord):
    authority: Literal['EXTERNAL_RESEARCH_REVIEW','SYNTHETIC_TEST']
    reviewer: str = Field(min_length=3,max_length=300)
    evidence: str = Field(min_length=12,max_length=4000)
    problem_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    decisions: dict[str,Literal['ACCEPTED','PENDING','REJECTED']]

class IVScienceReview(StrictRecord):
    authority: Literal['EXTERNAL_RESEARCH_REVIEW','SYNTHETIC_TEST']
    reviewer: str = Field(min_length=3,max_length=300)
    evidence: str = Field(min_length=12,max_length=4000)
    problem_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    decisions: dict[str,Literal['ACCEPTED','PENDING','REJECTED']]

class IVReview(StrictRecord):
    version: Literal['binary-iv-research-1']
    problem_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    reading_review: IVReadingReview
    science_review: IVScienceReview

class IVUnavailable(ValueError):
    def __init__(self,state,reason): self.state,self.reason=state,reason; super().__init__(reason)

def validate(problem):
    if type(problem) is not IVProblem: raise IVUnavailable('CHECK_BLOCKED','TYPED_IV_PROBLEM_REQUIRED')
    p=IVProblem.model_validate(problem.model_dump())
    if not p.population.strip() or not p.context.strip(): raise IVUnavailable('NEEDS_INPUT','POPULATION_AND_CONTEXT_REQUIRED')
    if not p.source_ids or not p.source_sha256: raise IVUnavailable('NEEDS_INPUT','SOURCE_BOUND_OBSERVED_LAW_REQUIRED')
    required=set(science_decisions(p))
    if set(p.assumptions)!=required or len(p.assumptions)!=len(required): raise IVUnavailable('NEEDS_INPUT','EXACT_TARGET_ASSUMPTIONS_REQUIRED')
    return p

def digest(problem):
    payload=problem.model_dump(mode='json') if hasattr(problem,'model_dump') else problem
    raw=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def check_review(problem,review):
    p=validate(problem)
    if type(review) is not IVReview: raise IVUnavailable('REVIEW_REQUIRED','SEPARATE_READING_AND_SCIENCE_REVIEWS_REQUIRED')
    r=IVReview.model_validate(review.model_dump())
    if r.problem_sha256!=digest(p): raise IVUnavailable('CHECK_BLOCKED','STALE_IV_REVIEW')
    if r.reading_review.problem_sha256!=digest(p) or r.science_review.problem_sha256!=digest(p):
        raise IVUnavailable('CHECK_BLOCKED','STALE_IV_SUBREVIEW')
    if set(r.reading_review.decisions)!=set(READING_DECISIONS): raise IVUnavailable('CHECK_BLOCKED','EXACT_READING_DECISIONS_REQUIRED')
    expected=set(science_decisions(p))
    if r.reading_review.authority != r.science_review.authority:
        raise IVUnavailable('CHECK_BLOCKED','IV_REVIEW_AUTHORITY_MISMATCH')
    if any(not x.reviewer.strip() or len(x.evidence.strip())<12 for x in (r.reading_review,r.science_review)):
        raise IVUnavailable('CHECK_BLOCKED','NONBLANK_IV_REVIEW_REQUIRED')
    if set(r.science_review.decisions)!=expected: raise IVUnavailable('CHECK_BLOCKED','EXACT_SCIENCE_DECISIONS_REQUIRED')
    all_decisions=list(r.reading_review.decisions.values())+list(r.science_review.decisions.values())
    if 'REJECTED' in all_decisions: raise IVUnavailable('UNSUPPORTED','SCIENTIFIC_OR_READING_CONDITION_REJECTED')
    if 'PENDING' in all_decisions: raise IVUnavailable('REVIEW_REQUIRED','SCIENTIFIC_OR_READING_REVIEW_PENDING')
    return r
