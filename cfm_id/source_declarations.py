"""Conservative clause-level reading of declarations, separate from mathematical proofs.

These rules do not infer a scientific assumption. A negative, undecided, conflicting,
or unconsumed statement cannot be turned into an affirmative solver input.
"""
import re

UNKNOWN = r'尚未|未决定|待(?:定|确认)|不清楚|不确定|不详|是否|无法|不能(?:确认|保证|确定)|不一定|未必|可能|假如|如果|拟采用|未(?:确认|说明|证实)'
DENIED = r'不采用|拒绝|撤回|没有|尚无|缺少|缺乏|并非|并不|不成立|不完整|不独立|不保证|未(?:提供|给定|给出|列出|列全|满足)|不(?:都|全|再|满足|作为|作假设|假定|接受|维持|保持|是)|不能'


def stance(text):
    if re.search(UNKNOWN, text):
        return 'UNDECIDED'
    if re.search(DENIED, text):
        return 'NOT_ADOPTED'
    return 'ADOPTED'


def clauses(text):
    return [s.strip() for s in re.split(r'[。；;，,\n]+', text) if s.strip()]


DAG_FIELDS = {
    'complete_edges': (r'全部直接(?:因果)?关系|直接因果边完整', '图中是否已列全直接因果关系'),
    'complete_latents': (r'全部共同原因|所有共同原因均已|穷尽全部直接关系和共同原因', '可能同时影响多个变量的共同原因是否已列全'),
    'independent_errors': (r'噪声相互独立|剩余误差相互独立', '是否采用模型中剩余误差相互独立这一前提'),
    'modularity': (r'其他(?:结构)?机制(?:保持)?不变', '改变处理时，其他机制是否保持不变'),
    'population_law': (r'完整(?:符号)?(?:联合总体分布|总体联合分布)', '是否有本次所需的总体联合分布，而不只是样本记录'),
    'positive_joint': (r'严格大于零|严格为正', '所用联合取值是否都有正概率'),
}


def dag_declarations(model, information):
    model_rows, info_rows = clauses(model), clauses(information)
    declarations = {}
    used = set()
    for name, (pattern, question) in DAG_FIELDS.items():
        rows = info_rows if name in ('population_law', 'positive_joint') else model_rows
        hits = [s for s in rows if re.search(pattern, s)]
        states = {stance(s) for s in hits}
        state = next(iter(states)) if len(states) == 1 else 'CONFLICT' if states else 'MISSING'
        declarations[name] = dict(state=state, evidence=hits, question=question)
        used.update(hits)
    # Only explicit model descriptions, context and no-extra-restriction statements
    # may remain. Unrecognized model prose is retained, never silently erased.
    harmless = r'(?:本研究|本次|研究)?(?:采用|使用)?(?:静态)?(?:递归)?有向无环模型|研究背景[：:].+|没有其他(?:模型)?(?:假设|限制|约束)'
    restrictions = [s for s in model_rows if s not in used and not re.fullmatch(harmless, s)]
    restrictions += [s for s in info_rows if s not in used]
    # An extra condition in the same clause must not hide behind an affirmative
    # declaration. Unknown prose remains unsupported rather than being discarded.
    restrictions += [s for s in used if re.search(r'额外假|另(?:外|行)(?:假定|假设|要求)|同时要求|还要求|还假定', s)]
    restrictions = list(dict.fromkeys(restrictions))
    return declarations, restrictions
