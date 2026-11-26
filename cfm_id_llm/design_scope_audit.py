"""Separate marginal allocation chances from the source's joint design rule.

This is an evidence gate, not a design parser or scientific approval. The
explicit-independence check is only a necessary textual safeguard; the normal
source audit still checks meaning, parameters, negation and applicability.
"""
from copy import deepcopy
import json
import re
from typing import Literal
from .joint_reading import Strict, Citation, resolve_evidence, sources, check_citations

VERSION = 'network-design-source-audit/1'
QUESTION = '这些对象是各自独立抽签，还是先定总名额、分组抽签，或使用其他规则？请说明实际方式；尚未确定也可以直接说。'
KINDS = {
    'heterogeneous_bernoulli_binary_v1': 'INDEPENDENT_UNITS',
    'complete_randomization_binary_v1': 'FIXED_TOTAL',
    'two_group_fixed_quota_binary_v1': 'GROUP_QUOTAS',
    'multi_group_fixed_quota_binary_v2_5': 'GROUP_QUOTAS',
    'cluster_bernoulli_binary_v2_4': 'CLUSTER_ALLOCATION',
    'two_stage_quota_mixture_binary_v2_7': 'TWO_STAGE',
    'unequal_probability_fixed_quota_binary_v1': 'WEIGHTED_QUOTA',
    'rerandomized_balanced_binary_v1': 'BALANCE_SCREENED',
}


class Scope(Strict):
    basis: Literal['EXPLICIT_JOINT_RULE', 'MARGINAL_CHANCES_ONLY', 'REALIZATION_ONLY', 'NOT_STATED', 'CONFLICTING']
    rule: Literal['INDEPENDENT_UNITS', 'FIXED_TOTAL', 'GROUP_QUOTAS', 'CLUSTER_ALLOCATION',
                  'TWO_STAGE', 'WEIGHTED_QUOTA', 'BALANCE_SCREENED', 'OTHER', 'UNKNOWN']
    evidence: list[Citation]


def applies(reading):
    return isinstance(reading.get('design'), dict)


def explicit_independence(evidence):
    """Conservative evidence anchor; a marginal chance or Y⊥T is not enough.

    Unknown paraphrases require a fresh source review, never automatic approval.
    Matching an anchor alone is deliberately insufficient for admission.
    """
    for item in evidence:
        for clause in re.split(r'[。，,；;\n!?！？]', item['quote']):
            if re.search(r'(?:并非|不(?:是|能|会|认为|假设|采用|保证)?|没有(?:说明|采用|假定)|未说明|未确定|尚未确定|不知道|是否)[^。，,；;\n]{0,20}独立|\b(?:not|whether|unclear|unknown|unsure)\b[^.;,\n]{0,32}\bindependent', clause, re.I):
                continue
            patterns = (
                r'(?:每|各)[^。；;\n]{0,32}独立(?:地)?(?:抽签|随机|分配|抛|掷|决定|生成)',
                r'(?:抽签|分配|处理状态|硬币)[^。；;\n]{0,20}(?:相互|互相|彼此)独立',
                r'(?:相互|互相|彼此)独立[^。；;\n]{0,12}(?:抽签|分配|处理|硬币)',
                r'独立[^。；;\n]{0,12}(?:伯努利|Bernoulli)',
                r'\bindependent(?:ly)?\b[^.;\n]{0,32}\b(?:assign\w*|randomiz\w*|draw\w*|Bernoulli|coin\w*)\b',
                r'\b(?:assign\w*|randomiz\w*|draw\w*|coin\w*)\b[^.;\n]{0,32}\bindependent(?:ly)?\b',
                r'"kind"\s*:\s*"heterogeneous_bernoulli_binary_v1"',
            )
            if any(re.search(p, clause, re.I) for p in patterns):
                return True
    return False


def augment(request, reading):
    if not applies(reading):
        return request
    request = deepcopy(request)
    body = json.loads(request['user_prompt']); schema = body['output_schema']
    item = Scope.model_json_schema(); item.pop('$defs', None)
    schema['properties'].update(design_scope_version={'type': 'string', 'const': VERSION}, design_scope=item)
    schema['required'] += ['design_scope_version', 'design_scope']
    request['system_prompt'] += '''
另按schema输出design_scope_version和design_scope，独立判断原文怎样生成整份处理名单。
“每家一半机会/分别抽签”只给边际机会，不足以推出各家独立；本轮恰好一半启用只是实现值，不证明固定名额。随机安排与潜在结果独立也不等于对象间的抽签彼此独立。
basis=EXPLICIT_JOINT_RULE仅限原文明确说了联合规则（独立、固定名额、分组、两阶段、平衡筛选等）；只给各家机会用MARGINAL_CHANCES_ONLY，只给实际名单用REALIZATION_ONLY，没说用NOT_STATED，矛盾用CONFLICTING。rule保留原文机制，未明确用UNKNOWN；不要从候选design.kind倒填。
INDEPENDENT_UNITS必须引用明确说明对象各自独立分配的原句，不能仅引用概率或潜在结果随机化。固定名额不能从已实现人数推测。各项参数仍由原逐字段审核检查。缺联合规则只问实际怎样抽签，用户不必说出设计英文名。
'''
    request['user_prompt'] = json.dumps(body, ensure_ascii=False)
    return request


def check(case, reading, audit, version, raw, *, current=False):
    if version is None and raw is None and not current:
        return audit  # Historical audit remains governed by its original contract.
    if not applies(reading):
        if version is not None or raw is not None:
            raise ValueError('UNEXPECTED_DESIGN_SCOPE_AUDIT')
        return audit
    if version != VERSION:
        raise ValueError('DESIGN_SCOPE_AUDIT_REQUIRED')
    scope = Scope.model_validate(raw).model_dump(mode='json')
    scope['evidence'] = resolve_evidence(case, scope['evidence'])
    check_citations(scope['evidence'], sources(case))
    finding = next(f for f in audit['findings'] if f['field'] == 'design')
    value = reading['design'].get('value')
    error = None
    if scope['basis'] == 'EXPLICIT_JOINT_RULE':
        if not scope['evidence']:
            error = '联合抽签规则缺少原文依据。'
        elif scope['rule'] == 'INDEPENDENT_UNITS' and not explicit_independence(scope['evidence']):
            error = '所引原文未明确对象间独立抽签；各自概率或与潜在结果独立不能替代。重新核对联合规则，不从候选倒填。'
        elif not value or KINDS.get(value['kind']) != scope['rule']:
            error = '候选分配机制与原文联合规则分解不同。'
    elif scope['rule'] != 'UNKNOWN':
        error = '联合规则未明确时不能填写已确定的联合机制。'
    if finding['verdict'] == 'MATCH':
        if error:
            finding.update(verdict='READING_ERROR', reason=error, question=None, evidence=scope['evidence'])
        elif scope['basis'] != 'EXPLICIT_JOINT_RULE':
            finding.update(verdict='NEEDS_CLARIFICATION', question=QUESTION,
                reason='原文尚未给出明确且一致的联合抽签规则，不能从边际机会或实际人数推断。', evidence=scope['evidence'])
    audit.update(design_scope_version=VERSION, design_scope=scope)
    return audit
