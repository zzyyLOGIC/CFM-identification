"""Unapproved source facts for existing observational and finite-policy methods."""
import json
from importlib.resources import files
from typing import Literal
from pydantic import Field,StrictInt
from . import joint_reading as shared
from .joint_reading import Strict,Claim,Network,Exposure,Design,Condition,MaterialNote
from .information_semantics import GUIDANCE as INFORMATION_SCOPE_GUIDANCE


class Study(Strict):
    treatment: str
    outcome: str = Field(description='原文中的结果含义、单位、编码及已给出的好坏方向；不因方向更有利就倒置目标两端。')
    outcome_kind: Literal['binary','continuous','count','unknown']
    period: str
    fixed_background: str
    regime: Literal['EXPERIMENTAL','OBSERVATIONAL','UNKNOWN']


class Policy(Strict):
    assignment: dict[str,StrictInt]
    probability: str | None


class Target(Strict):
    description: str
    quantity: Literal['MEAN','DIFFERENCE','OTHER','UNKNOWN']
    components: list[Policy]
    reference_components: list[Policy] | None = Field(default=None,description='差值的第二端完整政策或有限混合，第一端减第二端。均值目标留null。每端概率分别归一。')
    weights: dict[str,str]
    distribution_complete: bool | None = Field(description='仅指未来随机政策的全部方案是否列全。观察性固定政策填null，不是问历史总体分配表是否列全。')


class Mass(Strict):
    assignment: dict[str,StrictInt]
    probability: str


class SignatureCell(Strict):
    node: str
    own: StrictInt = Field(ge=0,le=1)
    exposure: StrictInt = Field(ge=0)


class SufficiencyScope(Strict):
    covered_nodes: list[str] = Field(description='原文明确采用该假设的对象；不采用或未说明的对象不能列入。')
    scope: Literal['ALL_BINARY_ASSIGNMENTS','LISTED_ASSIGNMENTS','UNKNOWN']
    assignments: list[dict[str,StrictInt]] = Field(description='仅限定若干完整安排时逐一记录；不能将试点出现的安排扩成所有安排。')


class Information(Strict):
    availability: Literal['SYMBOLIC_POPULATION_OPERATOR','FINITE_SAMPLE','UNKNOWN']
    operator: Literal['NODE_FULL_LAW','FULL_JOINT_LAW','ASSIGNMENT_NODE_MEANS','NODE_SIGNATURE_MEANS',
                      'OBSERVATIONAL_ASSIGNMENT_NODE_CONDITIONAL_MEANS','OTHER','UNKNOWN'] = Field(
        description='NODE_FULL_LAW是逐对象的P(Y_i,完整T)，FULL_JOINT_LAW是P(全部Y,完整T)。区别在结果是否联合，不在T是否完整；分别覆盖所有对象不等于知道全部结果的联合依赖。只有均值不能升级为分布，范围不明用UNKNOWN。')
    outcome_nodes: list[str]
    assignment_cells: list[dict[str,StrictInt]] = Field(description='实验的ASSIGNMENT_NODE_MEANS所覆盖的完整安排。观察性算子的覆盖已随assignment_masses逐行记录，本字段留空。')
    assignment_masses: list[Mass]
    signature_cells: list[SignatureCell] = Field(default_factory=list,description='仅NODE_SIGNATURE_MEANS使用：原资料覆盖的对象、本人0/1和同伴状态格子，不从希望计算的目标倒填。')
    same_scope: bool | None
    complete: bool | None = Field(description='已有资料的覆盖清单是否列完整；不是所有理论状态都有数据，也不是目标已可识别。签名格子只需原样列全实际提供的格子，正支持和目标覆盖由数学库另查。')


class Reading(Strict):
    family: Claim[Literal['NETWORK_FINITE_POLICY','NETWORK_OBSERVATIONAL_POLICY','OTHER','UNKNOWN']]
    study: Claim[Study]
    network: Claim[Network]
    design: Claim[Design | None] | None
    exposure: Claim[Exposure] | None
    mean_sufficiency_scope: Claim[SufficiencyScope] | None = None
    target: Claim[Target]
    information: Claim[Information]
    conditions: list[Condition]
    remaining: list[Condition]
    material_notes: list[MaterialNote]=Field(default_factory=list)


def contract():
    # Reuse the same information semantics as the maintained A4 reader. Both
    # the fresh reading and its independent source audit receive this contract.
    return files('cfm_id_llm').joinpath('resources/network_existing/SKILL.md').read_text('utf8')+'\n'+INFORMATION_SCOPE_GUIDANCE


def request(case,feedback=None):
    schema=Reading.model_json_schema()
    schema['$defs']['Citation']['properties']['source_id']['enum']=list(shared.sources(case))
    return dict(system_prompt=contract(),user_prompt=json.dumps(dict(source_catalog=shared.sources(case),
        source_descriptions=shared.source_descriptions(case),output_schema=schema,
        reading_feedback_not_evidence=feedback),ensure_ascii=False))


def inspect(case,raw):
    s=Reading.model_validate(raw).model_dump(mode='json')
    if 'mean_sufficiency_scope' not in raw:s.pop('mean_sufficiency_scope',None)
    if 'signature_cells' not in raw['information']['value']:s['information']['value'].pop('signature_cells',None)
    if 'reference_components' not in raw['target']['value']:s['target']['value'].pop('reference_components',None)
    def walk(value):
        if isinstance(value,dict):
            if 'evidence' in value:
                value['evidence']=shared.resolve_evidence(case,value['evidence'])
                if not value['evidence'] and value.get('status')!='UNKNOWN' and value.get('value',True) is not None:
                    raise ValueError('NETWORK_SOURCE_EVIDENCE_REQUIRED')
            for v in value.values():walk(v)
        elif isinstance(value,list):
            for v in value:walk(v)
    walk(s)
    codes=[x['code'] for x in s['conditions']]
    if len(codes)!=len(set(codes)):raise ValueError('DUPLICATE_SCIENTIFIC_CONDITION')
    return s


def fields(s):
    out={k:v for k,v in s.items() if isinstance(v,dict)}
    if any(c['code']=='mean_sufficiency' and c['status']=='ADOPTED' for c in s['conditions']):
        out.setdefault('mean_sufficiency_scope',dict(value=None,evidence=[],check='核对假设适用的对象和完整安排范围，不能按目标扩大。'))
    if s['family']['value']=='NETWORK_FINITE_POLICY':out.setdefault('design',dict(value=None,evidence=[]))
    for k in ('conditions','remaining','material_notes'):
        out.update({f'{k}.{i}':v for i,v in enumerate(s[k])})
    out['target_scope_crosscheck']=dict(target=s['target'],study=s['study'],evidence=s['target']['evidence'])
    out['coverage']=dict(candidate=s)
    return out


def audit_request(case,s):
    return shared.audit_request(case,s,field_catalog=fields(s),reading_contract=contract())


def check_audit(case,s,raw):
    return shared.check_audit(case,s,raw,field_catalog=fields(s))


binding=shared.binding
