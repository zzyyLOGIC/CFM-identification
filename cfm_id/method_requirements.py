"""Presentation metadata for native method obligations, never an eligibility engine.

Executable membership belongs to capability_registry. Review keys come from the
native adapter's worksheets/constants. Unknown keys remain visible, not accepted.
"""
from . import capability_registry as capabilities
from . import network_policy_dispatch as policy, network_bounded_dispatch as bounded
from . import network_contrast_dispatch as contrast
from . import network_mean_order_dispatch as orders
from . import network_effect_dispatch as effects
from . import network_observational_policy_dispatch as observational
from cfm_id_llm.network_design_reading import D6_CONDITION
from cfm_id_llm.query_conditioning_contract import MATCH_DECISION
from cfm_id_llm.network_effect_conditioning import SCOPE_DECISION

FAMILY = policy.FAMILY
DIAGNOSTIC_SCOPES = {FAMILY: 'FIXED_POLICY_MEAN', contrast.FAMILY: 'ORDERED_POLICY_MEAN_DIFFERENCE',
                     effects.FAMILY: 'DESIGN_STANDARDIZED_LOCAL_EFFECT',
                     observational.FAMILY: 'OBSERVATIONAL_FIXED_CONTEXT_POLICY_MEAN'}
LABELS = {
    'selected_query_matches_native_target': '当前业务问题与数学目标一致',
    'complete_model_and_constraints_preserved': '完整研究模型及原文限制均保留',
    'method_requests_and_projections_preserved': '方法要求及投影没有改变问题',
    'target_policy_population_and_weights': '政策、评价对象与权重',
    'network_assignment_and_variable_meaning': '网络、分配及变量定义',
    'all_information_and_restrictions_preserved': '所有信息和限制均保留',
    'source_entailment': '原文支持读取内容',
    'known_assignment_law': '分配律已知且可用',
    'full_vector_randomization': '完整分配向量的随机化独立性',
    'consistency': '一致性',
    'fixed_pretreatment_network': '网络固定且在处理前确定',
    'finite_conditional_first_moments': '所需条件均值存在且有限',
    'full_vector_conditional_exchangeability': '固定处理前背景下，完整潜在结果表与实际完整处理向量条件独立',
    'network_and_variable_meaning': '网络与处理、结果定义',
    'observational_regime_and_fixed_pretreatment_context': '观察性采用方式与指定的固定处理前背景',
    'population_table_and_conditional_mean_scope': '完整总体安排表与同一背景下的条件均值覆盖范围',
    'a4_population_operator': '原文声明的观测总体信息算子及来源',
    'complete_positive_assignment_support': '总体安排表已列全正概率安排；不等于目标政策有正概率',
    'means_for_all_positive_assignments': '全部正概率安排下所需对象的总体条件均值可用',
    'same_study_and_conditioning': '总体信息与目标属于同一研究和固定背景',
    observational.SIGNATURE_READING_DECISIONS[0]: '同伴暴露定义、同一固定背景下的均值充分性及明确作用范围',
    observational.SIGNATURE_SCIENCE_DECISIONS[0]: '全部评价对象在所有完整二元安排下的条件均值签名充分性',
    MATCH_DECISION: '事实阶段的固定背景与已审核业务目标一致，须独立核对原文',
    SCOPE_DECISION: '目标条件仅为处理前固定研究背景W，不包含额外子群筛选、处理后条件或跨背景平均',
    policy.SIGNATURE_SCIENCE_DECISIONS[0]: '覆盖目标对象、所有完整安排的均值签名充分性',
    bounded.MODEL_DECISIONS[0]: '精确 A4 数值及总体信息范围完整',
    bounded.MODEL_DECISIONS[1]: '科学界限的类型、单位、范围及全体模型对象',
    bounded.MODEL_DECISIONS[2]: '没有额外耦合限制',
    bounded.MODEL_DECISIONS[3]: '全部模型对象、所有完整安排的均值充分性',
    contrast.PAIR_DECISIONS[0]: '两个完整政策及第一政策减第二政策的方向',
    contrast.PAIR_DECISIONS[1]: '共同评价名单、等权平均、结果定义和研究背景',
    orders.ORDER_DECISIONS[0]: '除已声明均值顺序、基础条件和界限外没有其他限制',
    orders.ORDER_DECISIONS[1]: '顺序针对同一数值结果的条件均值；轴、全部安排范围及假设依据明确',
    effects.READING_DECISIONS[0]: '自身与同伴的两个局部状态，以及第一端减第二端的方向',
    effects.READING_DECISIONS[1]: '抽签前固定的评价名单及权重',
    effects.READING_DECISIONS[2]: '其余安排在各端局部条件下按原设计概率平均',
    effects.READING_DECISIONS[3]: '原生符号与业务处理、结果和固定背景一致',
    'a4_operator_scope_and_provenance': '总体信息算子的两端覆盖范围及来源',
    D6_CONDITION: 'D6第一阶段名额方案在最终完整处理名单之外没有直接作用',
}


def condition_label(key):
    if key.startswith('mean_order_axis:'):
        import json
        node, axis = json.loads(key.split(':',1)[1])
        return str(node) + ('：本人' if axis=='OWN' else '：同伴') + '均值非减条件的采用或明确不采用'
    if key.startswith('a4_source_'):
        return '该方法使用的总体信息：' + key
    return LABELS.get(key, key)


def catalog(family=FAMILY):
    """Describe registered routes; these templates do not generate approvals."""
    definitions = {
        observational.SIGNATURE_METHOD: ('固定背景下的观察性均值签名',
            (*observational.READING_DECISIONS, *observational.SIGNATURE_READING_DECISIONS,
             *observational.BASE_CONDITIONS, *observational.SIGNATURE_SCIENCE_DECISIONS,
             'a4_population_operator', *observational.A4_DECLARATIONS),
            '逐评价对象的目标签名正支持、同一固定W下的A4覆盖和原生证书重放',
            '沿用有限观察性总体表，另审对所有完整二元安排的条件均值充分性。'
            'E1–E5逐题检查适用域；不从暴露定义或总体概率推出充分性、交换性。'),
        observational.METHOD: ('固定背景下的观察性完整政策均值',
            (*observational.READING_DECISIONS, *observational.BASE_CONDITIONS,
             'a4_population_operator', *observational.A4_DECLARATIONS),
            '固定W下完整政策的联合正支持、同一A4覆盖及原生证书重放',
            '当前有限观察性完整安排入口；保留完整政策、评价名单及等权平均。'
            '交换性须独立审核；不是随机化，不以逐对象边际支持替代联合支持。'
            '不跨W平均，不自动改用均值签名或PARTIAL。'),
        policy.FULL_POLICY: ('完整政策识别', policy.BASE_CONDITIONS,
                     '完整政策正支持及该方法所需 A4 覆盖',
                     '固定完整政策均值；不要求均值签名充分性。'),
        policy.SIGNATURE_POLICY: ('均值签名识别', (*policy.BASE_CONDITIONS, *policy.SIGNATURE_SCIENCE_DECISIONS),
                    '评价对象的目标签名正支持及对应 A4 覆盖',
                    '不要求完整政策本身正支持；须另行审核暴露定义、充分性和覆盖范围。'),
        bounded.METHOD: ('有限有界均值模型', (*policy.BASE_CONDITIONS, *bounded.MODEL_DECISIONS),
                         '原生有限模型适用域、可行性及界限证书',
                         '当前 D2/E1 有限完整模型；可能返回 POINT 或 PARTIAL，sharp 相对于该模型。'),
        contrast.POINT_METHOD: ('两完整政策之差', (*contrast.PAIR_DECISIONS, *policy.BASE_CONDITIONS),
                               '两端完整政策的支持与 A4；两个端点重放及有向差值组合重放',
                               '同一研究、评价名单和等权平均，第一政策减第二政策；单端成功不识别差值。'),
        contrast.SIGNATURE_METHOD: ('两政策均值签名之差',
                            (*contrast.PAIR_DECISIONS, *policy.BASE_CONDITIONS, *policy.SIGNATURE_SCIENCE_DECISIONS),
                            '两端目标签名的支持与 A4；两个端点重放及有向差值组合重放',
                            '共同暴露、均值充分性、科学模型和评价范围；不拼接不同方法的单端证明。'),
        contrast.BOUNDED_METHOD: ('有限共同模型中的联合差值界限',
                                 (*contrast.PAIR_DECISIONS, *policy.BASE_CONDITIONS, *bounded.MODEL_DECISIONS),
                                 '共同有限模型、完整信息与约束；直接对有向差值联合求界并重放',
                                 '当前 D2/E1 完整均值模型；不相减独立端点区间，抵消可使差值为 POINT。'),
        orders.METHOD: ('均值顺序模型中的联合政策差值界限',
                        (*contrast.PAIR_DECISIONS, *policy.BASE_CONDITIONS, *orders.model_decisions([])),
                        '在同一有限模型中直接求差值；独立重放可达端点、最优性或不可行证书',
                        '现有 D2/E1、至多12个对象；逐对象本人/同伴均值非减或明确不假定。sharp仅相对于审核后的完整模型。'),
        effects.METHOD: ('原设计条件平均的局部直接／同伴效应',
                         (*effects.READING_DECISIONS, *effects.SCIENCE_DECISIONS),
                         '全部非零局部状态的原设计正支持、同一A4来源覆盖和有向组合证书重放',
                         '直接效应改变自身处理、同伴状态不变；同伴效应改变同伴状态、自身处理不变。'
                         '保留原设计下的条件平均和固定评价名单；不要求均值暴露充分性，不替换成完整政策目标。'
                         'D1–D6/E1–E5仍须逐题核查适用域；D6另有原生科学审核项。'),
    }
    rows = []
    if family not in DIAGNOSTIC_SCOPES:
        return rows
    from .method_catalog import catalog as method_catalog
    descriptions = {row['method_id']: row for row in method_catalog()['methods']}
    for method in capabilities.business_binding(family).methods:
        definition = definitions.get(method.method_id)
        description = descriptions[method.method_id]
        label, keys, math, scope = definition or (
            description['label'], (), description['computable_conditions'], description['implementation_limits'])
        rows.append(dict(method=method.method_id, label=label, native_route_ids=list(method.native_route_ids),
            template_documented=definition is not None, scope=scope,
            review_topics=[dict(key=k,label=condition_label(k)) for k in keys],
            a4_requirement='仅使用当前原生计划明确选入的总体信息；不能把样本提升为总体信息。',
            mathematical_check=math,
            certificate_requirement=descriptions[method.method_id]['verification']['label'] + '：' +
                descriptions[method.method_id]['verification']['detail'],
            template_is_approval=False))
    return rows


REASONS = {
    'DECLARED_MODEL_EXCLUDES:mean_signature_sufficiency':
        ('PRESERVE_REJECTED_MEAN_SUFFICIENCY', '完整政策无支持且原模型不采用均值充分性，当前签名路线不能运行；不宣称一般不可识别。'),
    'CONDITIONAL_MEAN_SUFFICIENCY_SCOPE_NOT_CONNECTED':
        ('REVIEW_CONDITIONAL_MEAN_SCOPE', '本路线需要同一固定W下、所有完整二元安排上的条件均值充分性；只在已观测支持内成立不够。'),
    'OBSERVATIONAL_SIGNATURE_MAPPING_NOT_CONNECTED':
        ('REVIEW_SIGNATURE_MAPPING', '当前暴露定义不在此入口的既有映射范围内，保留定义，不自动替换。'),
    'ZERO_OBSERVATIONAL_SIGNATURE_SUPPORT':
        ('INSPECT_OBSERVATIONAL_SIGNATURE_SUPPORT', '原生检查报告至少一个评价对象的目标签名没有支持；不能忽略该对象、改变政策或默认转PARTIAL。'),
    'OBSERVATIONAL_POLICY_FACTS_INCOMPLETE':
        ('CLARIFY_OBSERVATIONAL_TARGET_AND_INFORMATION', '按原生追问核对完整政策、固定背景、评价名单、交换性及总体信息；不补造条件。'),
    'DECLARED_MODEL_EXCLUDES:full_vector_conditional_exchangeability':
        ('PRESERVE_REJECTED_EXCHANGEABILITY', '原模型明确不采用所需条件交换性，当前R3路线不能运行；不改成接受，也不宣称一般不可识别。'),
    'ZERO_OBSERVATIONAL_FULL_ASSIGNMENT_SUPPORT':
        ('INSPECT_JOINT_OBSERVATIONAL_SUPPORT', '原生检查报告固定W下目标完整政策零支持；边际正概率不能替代联合支持，也不自动转PARTIAL。'),
    'A4_DIFFERENT_STUDY_OR_CONDITIONING':
        ('RESOLVE_OBSERVATIONAL_INFORMATION_SCOPE', '总体信息与目标不是同一研究或固定背景，不能借用该信息完成当前目标。'),
    'ONLY_FIXED_PRETREATMENT_W_CONNECTED':
        ('REVIEW_CONDITIONING_TARGET_SCOPE', '本入口只接固定处理前W；跨背景平均或其他条件须走另行接入的合同。'),
    'OBSERVATIONAL_A0_AND_RANDOMIZED_FACTS_DISAGREE':
        ('RECHECK_OBSERVATIONAL_REGIME', '业务阶段与事实阶段对观察性或随机化方式有冲突，回到原文核对。'),
    'R2_ADDITIONAL_DECLARATIONS_NOT_ESTABLISHED':
        ('CHECK_R2_DECLARATIONS', '核对暴露定义、均值充分性及覆盖范围；这是原生汇总缺口，不表示每一项都缺失。'),
    'POPULATION_INFORMATION_NOT_SUPPLIED_FOR_METHOD':
        ('CHECK_METHOD_A4', '核对该方法可用的总体信息及范围。'),
    'OFF_SUPPORT_ALTERNATE_THEOREM':
        ('INSPECT_OTHER_REGISTERED_METHODS', '原生检查报告完整政策没有正支持；不代表目标不可识别。'),
    'ZERO_POLICY_SIGNATURE_SUPPORT':
        ('RECONSIDER_DESIGN_OR_MODEL', '原生检查报告目标签名零支持；该路线不适用，改变设计或条件须新版本审核。'),
    'POPULATION_INFORMATION_NOT_DECLARED':
        ('CLARIFY_POPULATION_INFORMATION', '当前仅有有限样本；明确理论识别可用的总体信息，不将样本估计当精确总体量。'),
    'NETWORK_POLICY_FACTS_INCOMPLETE':
        ('CLARIFY_READING_OR_MATERIAL', '按原生追问核对缺项；先区分模型漏读与材料确实未声明。'),
    'EXPLICIT_BOUNDS_AND_COMPLETE_MODEL_REQUIRED':
        ('CLARIFY_BOUNDED_MODEL', '需要科学界限和完整模型声明；不是 POINT 失败后自动补界。'),
    'BOUNDED_MODEL_DECLARATIONS_INCOMPLETE':
        ('CLARIFY_BOUNDED_MODEL', '核对界限、单位、范围、信息完整性及耦合约束声明；具体缺口以原生追问为准。'),
    'FULL_INFORMATION_CANNOT_BE_DOWNGRADED_TO_MEAN_BOX':
        ('PRESERVE_INFORMATION_MODEL', '不能丢弃完整总体信息以进入较弱的均值模型。'),
    'ADDITIONAL_INFORMATION_OR_COUPLING_REQUIRES_OTHER_MODEL':
        ('REVIEW_MODEL_COVERAGE', '当前有界模型不覆盖这些额外信息或耦合约束；不得删除它们。'),
    'CONTRAST_DIRECTION_OR_COMMON_CONTEXT_UNRESOLVED':
        ('CLARIFY_ORDERED_COMPARISON', '核对第一政策减第二政策的方向，以及结果、期间和研究背景是否相同。'),
    'COMMON_CONTRAST_POPULATION_REQUIRED':
        ('RESOLVE_COMMON_EVALUATION_SCOPE', '当前两端评价名单不同；保留差异，不自动改成同一名单。'),
    'COMMON_CONTRAST_OUTCOME_AND_CONTEXT_REQUIRED':
        ('RESOLVE_COMMON_COMPARISON_CONTEXT', '当前两端结果或研究背景不同；不能拼接成当前差值目标。'),
    'CONTRAST_ENDPOINT_METHOD_COMBINATION_NOT_CONNECTED':
        ('INSPECT_ENDPOINT_METHOD_GAPS', '现有组合要求两端使用同一已连接方法及共同模型；不自动混合单端证明。'),
    'NO_REVIEWABLE_POLICY_METHOD':
        ('INSPECT_ENDPOINT_DECLARATIONS', '保留各端原生排除原因，核对总体信息及科学声明，不把未进入计划说成非识别证明。'),
    'TWO_R1B_ENDPOINTS_NOT_IDENTIFIED':
        ('INSPECT_BOTH_ENDPOINT_RESULTS', '完整政策方法尚未得到两个可组合的端点结果；单端成功不能报告差值成功。'),
    'TWO_R2_ENDPOINTS_NOT_IDENTIFIED':
        ('INSPECT_BOTH_ENDPOINT_RESULTS', 'R2尚未得到两个可组合的端点结果；不自动切换到PARTIAL。'),
    'NETWORK_EFFECT_FACTS_INCOMPLETE':
        ('CLARIFY_LOCAL_EFFECT_TARGET_AND_DESIGN', '按原生追问核对两端自身/同伴状态、方向、评价名单和其余安排的平均规则；不补造缺项。'),
    'EFFECT_TARGET_DISAGREES_WITH_REVIEWED_QUERY':
        ('RECHECK_EFFECT_KIND', '事实阶段的效应类别与已审业务问题不一致，须回到原文复核。'),
    'LOCAL_CONTRAST_DOES_NOT_MATCH_EFFECT_KIND':
        ('RECHECK_LOCAL_STATES', '直接效应应保持同伴状态、同伴效应应保持自身状态；不自动交换或补齐两端。'),
    'TARGET_OUTSIDE_DESIGN_STANDARDIZED_LOCAL_CONTRAST':
        ('REVIEW_LOCAL_TARGET_SCOPE', '该目标不属于当前原设计条件平均的局部比较，不能改写为当前可执行目标。'),
    'NO_SINGLE_SOURCE_COVERS_EFFECT_ARMS':
        ('CHECK_LOCAL_ARM_INFORMATION', '核对每个评价对象的两端总体均值覆盖；不得把有限记录或缺格子补成总体信息。'),
    'EFFECT_MULTI_SOURCE_JOINT_ADAPTER_REQUIRED':
        ('REVIEW_MULTI_SOURCE_ADAPTER', '信息分散在多个来源；当前局部入口尚未连接联合适配，不等于材料完全没有信息。'),
    'ZERO_ARM_SUPPORT':
        ('INSPECT_LOCAL_ARM_SUPPORT', '原生检查报告所需局部状态零支持；本路线不能完成，不是一般非识别证明，也不自动降级到PARTIAL。'),
    'SINGLE_AGGREGATION_REQUIRES_ONE_NODE':
        ('RECHECK_EVALUATION_POPULATION', '单个对象汇总与读取到的名单不一致，保留冲突并要求复核。'),
}


def reason(code):
    if code is None:
        return None
    action, label = REASONS.get(code, ('INSPECT_NATIVE_DIAGNOSTIC', '保留原生原因；尚无专门中文解释，不推断其数学含义。'))
    return dict(reason_code=code, label=label, next_action=action,
                permission_granted=False, weakest_assumptions_claimed=False)
