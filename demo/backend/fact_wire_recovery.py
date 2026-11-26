"""Bounded fact-field rereading; no inferred values, source approval or math.

Wire shorthand is expanded before the existing model and source audits. A field
repair is bound to the entire previous candidate and reviewed request, and may
replace only the explicitly requested top-level fields. All other data is kept.
"""
from copy import deepcopy
from fractions import Fraction
import hashlib
import json


class FactWireError(ValueError):
    def __init__(self, code, path='/assignment'):
        super().__init__(code)
        self.path = path


def _body(entry):
    request = entry['request']
    key = 'user' if 'user' in request else 'user_prompt'
    text = request[key].lstrip()
    body, end = json.JSONDecoder().raw_decode(text)
    return body, key, text[end:]


def prepare(entry):
    """Allow a source-declared common probability, never a default probability."""
    wire = deepcopy(entry)
    try:
        body, key, suffix = _body(wire)
        props = body['output_schema']['$defs']['Assignment']['properties']
        original = props['probabilities']
    except (KeyError, ValueError, TypeError):
        return wire
    props['probabilities'] = {'anyOf': [original, {
        'type': 'object', 'additionalProperties': False,
        'required': ['each_study_node', 'value'],
        'properties': {'each_study_node': {'const': True}, 'value': {'type': 'string'}},
    }]}
    body['assignment_probability_notation'] = (
        '只有原文明示所有研究对象各自独立且启用概率相同，才可把 assignment.probabilities 写为 '
        '{"each_study_node":true,"value":"原文中的概率分数"}。程序按完整 study.nodes 展开，'
        'assignment.source_ids 必须引用这条规则；展开不是科学批准。对象概率不同时逐对象填写，'
        '仅部分对象已知时保留已知对象及缺项；完全未提供规则时填 null，不用空对象 {} 省略已知规则。'
        '固定名额、分簇、两阶段等设计仍使用各自参数，不能用这一简写代替其联合抽签规则。')
    wire['request'][key] = json.dumps(body, ensure_ascii=False) + suffix
    return wire


def expand(candidate):
    if not isinstance(candidate, dict):
        return candidate
    result = deepcopy(candidate)
    assignment = result.get('assignment')
    if not isinstance(assignment, dict):
        return result
    probabilities = assignment.get('probabilities')
    if assignment.get('kind') == 'INDEPENDENT_BERNOULLI' and probabilities == {}:
        raise FactWireError('EMPTY_PROBABILITIES_USE_SOURCE_VALUES_OR_NULL')
    # An actual object may be named "each_study_node"; string-valued maps
    # remain ordinary per-object probabilities.
    if (not isinstance(probabilities, dict) or 'each_study_node' not in probabilities
            or isinstance(probabilities['each_study_node'], str)):
        return result
    nodes = (result.get('study') or {}).get('nodes')
    try:
        value = probabilities['value']
        valid = (set(probabilities) == {'each_study_node', 'value'}
                 and probabilities['each_study_node'] is True
                 and assignment.get('kind') == 'INDEPENDENT_BERNOULLI'
                 and isinstance(value, str) and 0 <= Fraction(value) <= 1
                 and isinstance(nodes, list) and bool(nodes)
                 and all(isinstance(n, str) and n for n in nodes)
                 and len(nodes) == len(set(nodes)) and len(nodes) <= 100_000
                 and bool(assignment.get('source_ids')))
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        valid = False
    if not valid:
        raise FactWireError('COMMON_PROBABILITY_REQUIRES_CITED_INDEPENDENT_RULE_AND_COMPLETE_NODES')
    assignment['probabilities'] = {n: value for n in nodes}
    return result


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def field_request(entry, previous, feedback, format_feedback=None):
    """Return None for unsupported repairs; never broaden unlocatable feedback."""
    if not isinstance(previous, dict) or not isinstance(feedback, dict):
        return None
    try:
        body, user_key, _ = _body(entry)
        schema = body['output_schema']
        properties = schema['properties']
        roots = set()
        for issue in feedback['issues']:
            path = issue['field_path']
            if not isinstance(path, str) or not path.startswith('/'):
                return None
            root = path.split('/')[1].replace('~1', '/').replace('~0', '~')
            if root not in properties or root not in previous or root in ('version', 'reference_context'):
                return None
            roots.add(root)
        if not roots or len(roots) > 3:
            return None
        selected = {key: deepcopy(properties[key]) for key in sorted(roots)}
        definitions = schema.get('$defs', {})
        used = {}
        def visit(value):
            if isinstance(value, dict):
                if '$ref' in value:
                    ref = value['$ref']
                    if not ref.startswith('#/$defs/'):
                        raise ValueError('NONLOCAL_SCHEMA_REFERENCE')
                    name = ref.removeprefix('#/$defs/')
                    if name not in used:
                        used[name] = deepcopy(definitions[name]); visit(used[name])
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(selected)
        binding = _digest(dict(request_sha256=entry['request_sha256'], previous=previous,
                               feedback=feedback, original_request=entry['request']))
        output = dict(type='object', additionalProperties=False,
                      required=['binding_sha256', 'fields'], properties={
                          'binding_sha256': {'const': binding},
                          'fields': dict(type='object', additionalProperties=False,
                                         properties=selected, required=sorted(roots))})
        if used:
            output['$defs'] = used
        payload = {key: deepcopy(value) for key, value in body.items() if key != 'output_schema'}
        payload.update(output_schema=output, previous_candidate=deepcopy(previous),
                       located_feedback=deepcopy(feedback), fields_to_reread=sorted(roots),
                       field_recovery_instruction=(
                           '本轮只对照完整原文重读 fields_to_reread，输出 binding_sha256 和 fields。'
                           '字段职责与原 Skill 不变；输出合同以本轮 output_schema 为准，不重写其他字段。'
                           '反馈不是正确答案，仍须检查全部来源和矛盾。没提供的内容保留未知；'
                           '不得补研究条件、授权科学假设，或为得到成功结论改变目标。'
                           '程序会合回原记录，再完整验证格式、来源和变化，必要科学审核保持。'))
        if format_feedback is not None:
            payload['wire_format_feedback'] = deepcopy(format_feedback)
        wire = deepcopy(entry)
        wire['request'][user_key] = json.dumps(payload, ensure_ascii=False)
        system_key = 'system' if 'system' in wire['request'] else 'system_prompt'
        wire['request'][system_key] += '\n本轮为已定位字段的重读。请按 user 中本轮 output_schema 返回字段包，不输出整份候选。'
        # The native revision gives the same source aliases a new context
        # nonce. This is protocol metadata, not a model-editable business fact.
        context = body.get('reference_context')
        if 'reference_context' in previous and (not isinstance(context,str) or not context):
            return None
        return wire, dict(binding_sha256=binding, fields=sorted(roots), previous=deepcopy(previous),
                          candidate_sha256=_digest(previous), reference_context=context)
    except (KeyError, ValueError, TypeError):
        return None


def merge(answer, receipt):
    if (not isinstance(answer, dict) or set(answer) != {'binding_sha256', 'fields'}
            or answer['binding_sha256'] != receipt['binding_sha256']
            or not isinstance(answer['fields'], dict)
            or set(answer['fields']) != set(receipt['fields'])
            or _digest(receipt['previous']) != receipt['candidate_sha256']):
        raise FactWireError('FIELD_RECOVERY_BINDING_OR_SCOPE_MISMATCH', '/fields')
    candidate = deepcopy(receipt['previous'])
    candidate.update(deepcopy(answer['fields']))
    if receipt.get('reference_context') is not None:
        candidate['reference_context'] = receipt['reference_context']
    return candidate
