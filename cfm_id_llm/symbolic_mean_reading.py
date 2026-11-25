"""Source-audited explicit symbolic mean model, never inferred causal structure."""
import json
from copy import deepcopy
from typing import Literal
from pydantic import create_model
from .population_ate_reading import Strict
from . import joint_reading as shared
from .compact_study import digest
from cfm_id.symbolic_mean_contract import Problem

Draft=create_model('SymbolicMeanDraft',__base__=Strict,**{
    name:(field.annotation,deepcopy(field)) for name,field in Problem.model_fields.items() if name!='sources'})

class Reading(Strict):
    binding:str
    scientific_approval:Literal[False]
    problem:Draft

# Source declarations have an adoption status; the mathematical contract still
# receives only the adopted, unexpressed restrictions. Keep v1 for saved replay.
SourceDraft=create_model('SymbolicSourceDraft',__base__=Draft,
    additional_restrictions=(list[shared.Condition],...))

class ReadingV2(Strict):
    version:Literal['symbolic-source-reading/2']
    binding:str
    scientific_approval:Literal[False]
    problem:SourceDraft

RULES='''按原始业务文字和附件读取一项有限均值的符号联合求界问题，输出JSON。你不决定科学条件，也不选择更容易的目标。
target_description只解释原问题的目标，不填你推导的上下界或答案。坐标、目标和约束单独表达；原答保存在别处，不作为本次原文证据。
每个coordinate是原文明确的总体平均结果；parameters是原文保留为未知符号的总体信息或限制参数，必须保留符号含义、范围和来源。所有表达式使用constant与coefficients表达仿射式；目标的均值系数和限制左边系数必须是有理常数，不能把未知系数当常数。每个参数都需原文给定有限范围。
source_ids只用本次目录中的片段编号。二元结果界可来自二元定义，连续结果不能默认0到1。不将样本估计改成确切总体均值。等式、线性不等式、采用或待定态度全部保留；不能忽略个体层、非线性或其他额外限制，放入additional_restrictions并说明。model_complete只有原文明确说明这是完整模型才true；未知null。无法确定的内容保留unresolved；不补科学条件，不补数值。
不从网络暴露定义推出均值充分性或完整有限模型；只有原文已明确把研究模型限定到这些均值及限制，才交付该有限模型。'''

RULES+='''\nadditional_restrictions逐项保存线性字段未表达的科学条件、原文采用状态和来源。ADOPTED=明确采用；NOT_ADOPTED=明确不采用；UNDECIDED=尚未决定；UNKNOWN=没有说明；CONTRADICTED=原文对该条件自身有相互矛盾的声明。不以“当前方法不支持”代替“尚未决定”。已经列入这些记录的采用状态不在unresolved重复；unresolved只放其余事实缺口。
完整模型声明和每条额外条件分开核对：后文明确“另外采用”的条件要保留；它未进入前面的列举、不能用线性式表达，本身不等于采用态度有歧义。若同一条条件明确既采用又不采用，仍保留冲突，不能默选一方。资料备注、只求公式等输出请求不属于额外科学限制。'''

def request(case,feedback=None):
    schema=ReadingV2.model_json_schema();schema['properties']['binding']['const']=digest(case)
    schema['$defs']['Citation']['properties']['source_id']['enum']=list(shared.sources(case))
    for item in schema.get('$defs',{}).values():
        if 'source_ids' in item.get('properties',{}):item['properties']['source_ids']['items']={'type':'string','enum':list(shared.sources(case))}
    return dict(system_prompt=RULES,user_prompt=json.dumps(dict(binding=digest(case),source_catalog=shared.sources(case),
        source_descriptions=shared.source_descriptions(case),output_schema=schema,feedback_not_evidence=feedback),ensure_ascii=False))

def inspect(case,raw):
    wire=raw.get('wire',raw);v2='version' in wire
    s=(ReadingV2 if v2 else Reading).model_validate(wire)
    if s.binding!=digest(case):raise ValueError('SYMBOLIC_SOURCE_READING_STALE')
    p=s.problem.model_dump();catalog=shared.sources(case)
    if v2:
        for row in s.problem.additional_restrictions:
            row.evidence=[shared.Citation.model_validate(x) for x in shared.resolve_evidence(case,row.model_dump()['evidence'])]
            if row.status!='UNKNOWN' and not row.evidence:raise ValueError('SYMBOLIC_RESTRICTION_SOURCE_REQUIRED')
        p['additional_restrictions']=[x.statement for x in s.problem.additional_restrictions if x.status=='ADOPTED']
        p['unresolved']+=['额外条件采用状态：'+x.statement for x in s.problem.additional_restrictions
            if x.status in ('UNDECIDED','UNKNOWN','CONTRADICTED')]
    ids=set(k for c in [*p['coordinates'],*p['constraints'],*p['parameters']] for k in c['source_ids'])
    if not ids<=catalog.keys():raise ValueError('UNKNOWN_SYMBOLIC_SOURCE')
    p['sources']={k:catalog[k] for k in sorted(ids)}
    out=dict(family=dict(value='SYMBOLIC_MEAN_JOINT'),wire=s.model_dump(),problem=p)
    if 'wire' in raw and out!=raw:raise ValueError('SYMBOLIC_CANONICAL_READING_CHANGED')
    return out


def inspect_current(case,raw):
    if raw.get('version')!='symbolic-source-reading/2':raise ValueError('SYMBOLIC_SOURCE_READING_V2_REQUIRED')
    return inspect(case,raw)

def fields(case,s):
    p=s['problem'];catalog=shared.sources(case)
    # Audit the lossless source declarations, not the executable projection:
    # declined restrictions are intentionally absent from the math problem.
    candidate=s['wire']['problem'] if s['wire'].get('version')=='symbolic-source-reading/2' else p
    out={'target':dict(target=p['target'],offset=p['target_offset'],description=p['target_description']),
         'coverage':dict(candidate=candidate,check='逐条核对原问、参数范围、模型完整性和未表达的限制，不因可求解而补条件。')}
    for group in ('coordinates','parameters','constraints'):
        for i,row in enumerate(p[group]):out[f'{group}.{i}']=dict(value=row,evidence=[dict(source_id=k,quote=catalog[k]) for k in row['source_ids']])
    if s['wire'].get('version')=='symbolic-source-reading/2':
        for i,row in enumerate(s['wire']['problem']['additional_restrictions']):
            out[f'additional_restrictions.{i}']=dict(value=row,evidence=row['evidence'],
                check='单独核对这条条件的含义、适用范围、采用状态及它是否确实未被线性字段表达；不要将模型完整性问题当作本条采用态度冲突。')
    return out

def audit_request(case,s):return shared.audit_request(case,s,field_catalog=fields(case,s),reading_contract=RULES)
def check_audit(case,s,raw):return shared.check_audit(case,s,raw,field_catalog=fields(case,s))
binding=shared.binding
