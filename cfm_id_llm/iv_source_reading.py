"""Unapproved binary-IV facts; original prose and table coordinates are audited."""
import json
from importlib.resources import files
from typing import Literal
from pydantic import Field,StrictInt
from . import joint_reading as shared
from .joint_reading import Strict,Claim,Condition,MaterialNote

class Study(Strict):
    population:str
    period:str
    context:str
    instrument:str
    treatment:str
    outcome:str
    binary_coding:dict[str,str]

class Target(Strict):
    description:str
    kind:Literal['ATE','LATE','OTHER','UNKNOWN']
    treated:StrictInt | None
    reference:StrictInt | None

class Cell(Strict):
    z:StrictInt=Field(ge=0,le=1)
    d:StrictInt=Field(ge=0,le=1)
    y:StrictInt=Field(ge=0,le=1)
    probability:str

class Information(Strict):
    kind:Literal['EXACT_POPULATION_CONDITIONAL_LAW','FINITE_SAMPLE','OTHER','UNKNOWN']
    cells:list[Cell]
    complete:bool | None
    same_scope:bool | None

class Reading(Strict):
    family:Claim[Literal['BINARY_IV','OTHER','UNKNOWN']]
    study:Claim[Study]
    target:Claim[Target]
    information:Claim[Information]
    conditions:list[Condition]
    remaining:list[Condition]
    material_notes:list[MaterialNote]=Field(default_factory=list)

def contract():return files('cfm_id_llm').joinpath('resources/iv_source/SKILL.md').read_text('utf8')
def request(case,feedback=None):
    schema=Reading.model_json_schema();schema['$defs']['Citation']['properties']['source_id']['enum']=list(shared.sources(case))
    return dict(system_prompt=contract(),user_prompt=json.dumps(dict(source_catalog=shared.sources(case),
        source_descriptions=shared.source_descriptions(case),output_schema=schema,reading_feedback_not_evidence=feedback),ensure_ascii=False))
def inspect(case,raw):
    s=Reading.model_validate(raw).model_dump(mode='json')
    for v in [s[k] for k in ('family','study','target','information')]+s['conditions']+s['remaining']+s['material_notes']:
        v['evidence']=shared.resolve_evidence(case,v['evidence'])
        if not v['evidence'] and v.get('status')!='UNKNOWN' and v.get('value')!='UNKNOWN':raise ValueError('IV_SOURCE_EVIDENCE_REQUIRED')
    codes=[v['code'] for v in s['conditions']]
    if len(codes)!=len(set(codes)):raise ValueError('DUPLICATE_IV_CONDITION')
    return s
def fields(s):
    out={k:s[k] for k in ('family','study','target','information')}
    for k in ('conditions','remaining','material_notes'):out.update({f'{k}.{i}':v for i,v in enumerate(s[k])})
    out['target_scope_crosscheck']=dict(target=s['target'],study=s['study'],evidence=s['target']['evidence'])
    out['coverage']=dict(candidate=s)
    return out
def audit_request(case,s):return shared.audit_request(case,s,field_catalog=fields(s),reading_contract=contract())
def check_audit(case,s,raw):return shared.check_audit(case,s,raw,field_catalog=fields(s))
binding=shared.binding
