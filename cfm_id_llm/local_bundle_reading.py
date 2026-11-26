"""Shared source facts, independently scoped local questions. No approvals."""
import json
from copy import deepcopy
from importlib.resources import files
from typing import Literal
from pydantic import Field, StrictInt
from . import joint_reading as shared
from .joint_reading import Strict, Claim, Condition, MaterialNote, Network, Design, Exposure
from .network_existing_reading import Study
from . import information_scope_audit
from . import local_target_event_audit
from .information_semantics import GUIDANCE as INFORMATION_SCOPE_GUIDANCE

FAMILY = 'NETWORK_LOCAL_BUNDLE'


class Arm(Strict):
    own: StrictInt = Field(ge=0, le=1)
    exposure: StrictInt = Field(ge=0)


class Target(Strict):
    question: str
    kind: Literal['MEAN', 'CONTRAST', 'OTHER', 'UNKNOWN']
    first: Arm | None
    second: Arm | None
    population: list[str] | None
    weights: dict[str, str] | None
    fixed_before_assignment: bool | None
    remaining_assignment: Literal['ORIGINAL_DESIGN_CONDITIONAL', 'OTHER', 'UNKNOWN']
    same_outcome_and_context: bool | None


class Cell(Arm):
    node: str


class ScopedCondition(Condition):
    covered_nodes: list[str]
    all_assignments: bool | None
    local_scope: Literal['OBSERVED_CONSISTENCY', 'FIXED_PRETREATMENT_NETWORK', 'TARGET_EVENT_MEANS'] | None = Field(
        default=None, description='Condition-specific scope explicitly supported by the source: actual outcome versus actual complete assignment; network fixed before treatment and during the study; or finite conditional means for specified target events. Not a substitute for full assignment randomization. Null when unknown.')
    target_indices: list[StrictInt] | None = Field(default=None,
        description='Only for TARGET_EVENT_MEANS: zero-based indices of targets whose FIRST and SECOND (if any) conditional means are explicitly covered for covered_nodes. Do not infer coverage from the requested target or from one arm alone.')


class Information(Strict):
    operator: Literal['NODE_ARM_MEANS', 'NODE_FULL_LAW', 'FULL_JOINT_LAW', 'FINITE_SAMPLE', 'OTHER', 'UNKNOWN']
    availability: Literal['SYMBOLIC_POPULATION_OPERATOR', 'FINITE_SAMPLE', 'UNKNOWN']
    outcome_nodes: list[str]
    arm_cells: list[Cell]
    same_scope: bool | None


class Reading(Strict):
    family: Claim[Literal['NETWORK_LOCAL_BUNDLE', 'OTHER', 'UNKNOWN']]
    study: Claim[Study]
    network: Claim[Network]
    design: Claim[Design | None] = Field(description=(
        'Complete joint assignment mechanism expressible by Design, or null when not yet specified. '
        'When only margins, group quotas or within-group rules are given and the joint mechanism is missing, '
        'keep null and cite those known facts in evidence. Null here does not erase those source facts. '
        'Do not invent cross-group independence or fill a mathematically different complete Design.'))
    exposure: Claim[Exposure]
    targets: list[Claim[Target]] = Field(min_length=1, max_length=16)
    information: list[Claim[Information]]
    conditions: list[ScopedCondition]
    remaining: list[Condition]
    material_notes: list[MaterialNote] = Field(default_factory=list)


def contract():
    return files('cfm_id_llm').joinpath('resources/local_bundle/SKILL.md').read_text('utf8')+'\n'+INFORMATION_SCOPE_GUIDANCE


def request(case, feedback=None):
    schema = Reading.model_json_schema()
    shared.fragment_citation_schema(schema, case)
    return dict(system_prompt=contract(), user_prompt=json.dumps(dict(
        source_catalog=shared.sources(case), source_descriptions=shared.source_descriptions(case),
        output_schema=schema, reading_feedback_not_evidence=feedback), ensure_ascii=False))


def normalize_wire(raw):
    """Remove only an unambiguous empty wrapper; never change weight values."""
    wire=deepcopy(raw);changes=[]
    if not isinstance(wire,dict) or not isinstance(wire.get('targets'),list):return wire,changes
    for i,claim in enumerate(wire['targets']):
        t=claim.get('value') if isinstance(claim,dict) else None
        if not isinstance(t,dict):continue
        w=t.get('weights');pop=t.get('population')
        if (isinstance(w,dict) and set(w)=={'population'} and isinstance(w['population'],dict)
                and isinstance(pop,list) and pop and all(isinstance(n,str) for n in pop)
                and len(set(pop))==len(pop) and set(w['population'])==set(pop)
                and all(isinstance(x,str) for x in w['population'].values())):
            t['weights']=w['population']
            changes.append(dict(field=f'targets.{i}.value.weights',action='UNWRAP_POPULATION_ONLY',
                original=deepcopy(w),canonical=deepcopy(t['weights']),values_changed=False))
    return wire,changes


def wire_normalizations(raw):
    return normalize_wire(raw)[1]


def inspect(case, raw):
    wire = normalize_wire(raw)[0]
    s = Reading.model_validate(wire).model_dump(mode='json')
    for c, old in zip(s['conditions'], wire['conditions']):
        # Existing readings/certificates keep their original binding. New
        # scopes require an explicit, independently audited source claim.
        for key in ('local_scope', 'target_indices'):
            if key not in old:c.pop(key, None)
        scope=c.get('local_scope');indices=c.get('target_indices')
        codes={'OBSERVED_CONSISTENCY':'consistency',
               'FIXED_PRETREATMENT_NETWORK':'fixed_network', 'TARGET_EVENT_MEANS':'finite_means'}
        if scope is not None and codes[scope]!=c['code']:
            raise ValueError('LOCAL_CONDITION_SCOPE_KIND_MISMATCH')
        if indices is not None and (scope!='TARGET_EVENT_MEANS' or not indices
                or len(indices)!=len(set(indices)) or any(i<0 or i>=len(s['targets']) for i in indices)):
            raise ValueError('LOCAL_CONDITION_TARGET_SCOPE_INVALID')
    def walk(value):
        if isinstance(value, dict):
            if 'evidence' in value:
                value['evidence'] = shared.resolve_evidence(case, value['evidence'])
                if not value['evidence'] and value.get('status') != 'UNKNOWN' and value.get('value', True) is not None:
                    raise ValueError('LOCAL_SOURCE_EVIDENCE_REQUIRED')
            for v in value.values(): walk(v)
        elif isinstance(value, list):
            for v in value: walk(v)
    walk(s)
    # One premise can have different adoption states for different groups.
    # Retain all scope records; the planner checks coverage and conflicts for
    # each actual target, rather than overwriting records by condition name.
    return s


def fields(s):
    out = {k:v for k,v in s.items() if isinstance(v, dict)}
    for key in ('targets', 'information', 'conditions', 'remaining', 'material_notes'):
        out.update({f'{key}.{i}':v for i,v in enumerate(s[key])})
    out['target_scope_crosscheck'] = dict(targets=s['targets'], study=s['study'],
        check='逐问对照原文：不漏问、不多问、不把子群删成诱导子图；每问的名单、权重、方向和处理前固定状态分别核对。权重表必须对应正确问题。')
    out['coverage'] = dict(candidate=s)
    return out


def audit_request(case, s):
    return local_target_event_audit.augment(information_scope_audit.augment_request(
        shared.audit_request(case, s, field_catalog=fields(s), reading_contract=contract()), s),s)


def check_audit(case, s, raw, *, current=False):
    raw=deepcopy(raw)
    version=raw.pop('local_target_event_version',None);events=raw.pop('local_target_events',None)
    audit=information_scope_audit.check(case,s,raw,fields(s),current=current)
    return local_target_event_audit.check(case,s,audit,version,events,current=current)


def check_audit_current(case, s, raw):
    return check_audit(case,s,raw,current=True)


binding = shared.binding
