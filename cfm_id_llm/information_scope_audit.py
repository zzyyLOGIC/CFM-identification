"""Source decomposition checked against network information, not a new solver.

The auditor must report what the source says, rather than just approve an
operator label. Deterministic checks can reject inconsistent audit outputs;
they do not certify the truth or semantics of natural-language evidence.
"""
from copy import deepcopy
import json
from typing import Literal
from pydantic import Field
from . import joint_reading as shared
from .information_semantics import GUIDANCE

VERSION = 'network-information-scope-audit/1'


class Scope(shared.Strict):
    field: str
    nature: Literal['POPULATION', 'FINITE_SAMPLE', 'UNKNOWN']
    statistic: Literal['DISTRIBUTION', 'MEANS', 'RECORDS', 'OTHER', 'UNKNOWN']
    results: Literal['SEPARATE_OUTCOMES', 'JOINT_OUTCOMES', 'UNSPECIFIED']
    treatments: Literal['FULL_ASSIGNMENT', 'OWN_AND_EXPOSURE', 'OTHER', 'UNKNOWN']
    outcome_nodes: list[str]
    evidence: list[shared.Citation] = Field(min_length=1)


def claims(reading):
    info = reading.get('information')
    if isinstance(info, list):
        return {f'information.{i}': row for i, row in enumerate(info)}
    return {'information': info} if info else {}


def augment_request(request, reading):
    request = deepcopy(request)
    body = json.loads(request['user_prompt'])
    schema = body['output_schema']
    scope_schema = Scope.model_json_schema()
    scope_schema.pop('$defs', None)  # Use the same restricted Citation schema.
    scope_schema['properties']['field']['enum'] = list(claims(reading))
    schema['properties']['information_scope_version'] = {'const': VERSION, 'type': 'string'}
    schema['properties']['information_scopes'] = dict(type='array', items=scope_schema,
        minItems=len(claims(reading)), maxItems=len(claims(reading)))
    schema['required'] += ['information_scope_version', 'information_scopes']
    request['system_prompt'] += '''
本次输出另含 information_scope_version 和 information_scopes，必须按 output_schema 填写。
对每份 information 原材料，先独立描述资料本身，再核对候选，不能从候选 operator 倒填：
nature：总体分布/总体均值为POPULATION；记录、频数、样本均值、拟合估计为FINITE_SAMPLE；未说清UNKNOWN。
statistic：完整概率分布DISTRIBUTION，只有均值MEANS，逐条样本RECORDS，其余OTHER或UNKNOWN。
results：每个对象各自一份结果分布是SEPARATE_OUTCOMES；全部结果一起出现在同一个分布中才是JOINT_OUTCOMES；否则UNSPECIFIED。覆盖所有对象不等于联合结果。每份分布都含完整安排，也不等于联合结果。
treatments：每份信息包含完整处理名单为FULL_ASSIGNMENT；只按本人/同伴状态为OWN_AND_EXPOSURE；只有本人或其他范围为OTHER；未说清UNKNOWN。
outcome_nodes 只列这份资料实际覆盖的结果对象，引用声明这些内容的原句。不要引用目标名单推测资料覆盖。
每个信息字段恰好一项，field与fields中的编号一致。分解是对原文的描述，不是另一份批准；程序会比较它和候选。若二者不同，在对应finding指出READING_ERROR，不用追问用户已经写明的内容。
'''+GUIDANCE
    request['user_prompt'] = json.dumps(body, ensure_ascii=False)
    return request


def differences(value, scope):
    errors = []
    nature = {'SYMBOLIC_POPULATION_OPERATOR':'POPULATION', 'FINITE_SAMPLE':'FINITE_SAMPLE', 'UNKNOWN':'UNKNOWN'}[value['availability']]
    if nature != scope['nature']: errors.append('总体/样本性质')
    operator = value['operator']
    expected = {
        'NODE_FULL_LAW': ('DISTRIBUTION','SEPARATE_OUTCOMES','FULL_ASSIGNMENT'),
        'FULL_JOINT_LAW': ('DISTRIBUTION','JOINT_OUTCOMES','FULL_ASSIGNMENT'),
        'NODE_ARM_MEANS': ('MEANS',None,'OWN_AND_EXPOSURE'),
        'NODE_SIGNATURE_MEANS': ('MEANS',None,'OWN_AND_EXPOSURE'),
        'ASSIGNMENT_NODE_MEANS': ('MEANS',None,'FULL_ASSIGNMENT'),
        'OBSERVATIONAL_ASSIGNMENT_NODE_CONDITIONAL_MEANS': ('MEANS',None,'FULL_ASSIGNMENT'),
    }.get(operator)
    if expected:
        for key, want in zip(('statistic','results','treatments'), expected):
            if want and scope[key] != want: errors.append(key)
        if scope['nature'] != 'POPULATION': errors.append('总体算子被用于非总体来源')
    if operator == 'FINITE_SAMPLE' and scope['nature'] != 'FINITE_SAMPLE':
        errors.append('样本算子与来源性质不同')
    if set(value['outcome_nodes']) != set(scope['outcome_nodes']): errors.append('结果对象覆盖')
    return errors


def check(case, reading, raw, field_catalog, *, current=False):
    raw = deepcopy(raw)
    version = raw.pop('information_scope_version', None)
    scopes = raw.pop('information_scopes', None)
    audit = shared.check_audit(case, reading, raw, field_catalog=field_catalog, current=current)
    if version is None and scopes is None and not current:
        return audit  # Historical replay; new requests must use the new contract.
    if version != VERSION or not isinstance(scopes, list):
        raise ValueError('INFORMATION_SCOPE_AUDIT_REQUIRED: 按output_schema独立分解各份资料，不能省略。')
    info = claims(reading)
    if sorted(x.get('field', '') for x in scopes) != sorted(info):
        raise ValueError('INFORMATION_SCOPE_AUDIT_COVERAGE:'+json.dumps(list(info)))
    checked = []
    for raw_scope in scopes:
        scope = Scope.model_validate(raw_scope).model_dump(mode='json')
        scope['evidence'] = shared.resolve_evidence(case, scope['evidence'])
        shared.check_citations(scope['evidence'], shared.sources(case))
        if len(scope['outcome_nodes']) != len(set(scope['outcome_nodes'])):
            raise ValueError('INFORMATION_SCOPE_DUPLICATE_NODES')
        checked.append(scope)
        errors = differences(info[scope['field']]['value'], scope)
        finding = next(f for f in audit['findings'] if f['field'] == scope['field'])
        if errors and finding['verdict'] == 'MATCH':
            finding.update(verdict='READING_ERROR', question=None, evidence=scope['evidence'],
                reason='来源分解与候选不一致（'+ '、'.join(errors)+'）；按原文重新读取，不把复核记录当作新增业务条件。')
    audit.update(information_scope_version=VERSION, information_scopes=checked)
    return audit
