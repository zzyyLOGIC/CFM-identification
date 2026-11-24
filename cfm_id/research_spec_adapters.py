"""Display-only format adapters. No imports from readers, validators or solvers."""
from .research_spec_view import COMMON, DAG, IV, MEAN_ORDER, NATIVE, Rule, _ADDITIONAL, _rules


def under(prefix, rules):
    return tuple(Rule(prefix + r.path, r.facet, r.role) for r in rules)


POLICY = (
    *_rules('definitions', '名单及变量原定义', '/nodes', '/treatment', '/outcome', '/period', '/policy_period'),
    *_rules('target', '完整政策两端与共同权重', '/first', '/second', '/weights'),
    *_rules('assignment', '分配模板及完整参数', '/design', '/quota'),
    *_rules('exposure', '暴露模板及原参数', '/grouping'),
    *_rules('structure', '对象关系', '/edges'),
    *_rules('information', '精确总体单元与原清单', '/values', '/information'),
    *_rules('assumptions', '界限、范围及条件原声明（不是审核）', '/bounds', '/bounds_kind', '/conditions'),
    *_rules('evidence', '原材料及逐项来源', '/graph', '/facts', '/protocol', '/bounds_source',
            '/design_source', '/exposure_source', '/signature_source'),
    *_rules('method', '原求解路线', '/operator'),
    *_rules('review', '原路线权限限制（不扩大）', '/synthetic_review_only'),
    *_rules('unresolved', '原阻断与待澄清事项', '/blocked', '/status', '/reason', '/questions'),
)

# Conditions are referenced once; their code determines the display role, not approval.
CONDITION_FACETS = {
    'policy_target': 'target', 'original_design': 'assignment', 'known_assignment_law': 'assignment',
    'exposure_definition': 'exposure', 'fixed_network': 'structure', 'complete_information': 'information',
}


def policy_rules(record):
    rules = list(COMMON + POLICY)
    for i, item in enumerate(record.get('conditions', []) or []):
        if isinstance(item, dict):
            facet = CONDITION_FACETS.get(item.get('code'), 'assumptions')
            rules += _rules(facet, '原条件声明及范围；外层审核另列', f'/conditions/{i}')
    return tuple(rules)


STUDY = NATIVE + (
    *_rules('assignment', '完整分配律原参数', '/assignment_design'),
)
INQUIRY = (
    *under('/study', STUDY),
    *_rules('target', '原目标、请求顺序与权重', '/target', '/requests'),
    *_rules('assignment', '原观察分配律', '/assignment'),
    *_rules('information', '原总体算子与范围', '/source', '/sources', '/r1b_sources', '/r2_sources'),
    *_rules('exposure', '签名映射及原参数', '/signature', '/r2_signature'),
    *_rules('assumptions', '原模型前提与许可；不是新的批准', '/assumptions', '/sufficiency', '/r2_sufficiency', '/license'),
)
SPEC = (
    *_rules('definitions', '变量取值定义', '/variable_domains'),
    *_rules('structure', '模型语义与对象/变量结构', '/causal_semantics', '/structure', '/network_exposure'),
    *_rules('exposure', '暴露映射声明', '/exposure_mapping_claim', '/exposure_uncertainty'),
    *_rules('assumptions', '原假设及冲突', '/assumptions', '/assumption_conflicts'),
    *_rules('target', '目标与条件背景', '/query', '/support_domain'),
    *_rules('information', '总体信息及来源层次', '/information_signature', '/provenance',
            '/reference_exposure_propensity_upper_bound_fact', '/network_policy_mixture_information_contract',
            '/network_policy_mixture_population_facts'),
    *_rules('assignment', '原政策分配律', '/network_policy_mixture_assignment_design'),
    *_rules('method', '原结构资格记录', '/interference_structure_receipt'),
    *_rules('target', '原确定政策及其背景', '/deterministic_policy_oracle'),
)
for _root in ('/randomized_network_arm_theorem_contract', '/network_policy_mixture_theorem_contract', '/majority_response_theorem_contract'):
    SPEC += (
        *_rules('method', '原定理合同；专门字段另列', _root),
        *_rules('method', '原定理合同版本', _root+'/version'),
        *_rules('assignment', '定理合同的原分配律', _root+'/design'),
        *_rules('exposure', '定理合同的原暴露定义', _root+'/grouping'),
        *_rules('target', '定理合同的原目标', _root+'/target'),
        *_rules('information', '定理合同的原总体信息', _root+'/information'),
        *_rules('information', '原总体信息范围', _root+'/population_information_scope'),
        *_rules('structure', '原模型适用域及背景', _root+'/candidate_structure_scope', _root+'/context_semantics', _root+'/outcome_semantics'),
        *_rules('assumptions', '原耦合条件', _root+'/conditional_coupling_semantics', _root+'/cross_block_response_constraints'),
    )
TASK = (
    *_rules('target', '原任务目标与评价范围', '/estimand', '/target_semantics', '/node_ids', '/budget', '/budget_mode'),
    *_rules('structure', '原对象关系矩阵', '/adjacency'),
    *_rules('assignment', '原分配记录', '/assignment_design'),
    *_rules('exposure', '原暴露定义', '/exposure_definition'),
    *_rules('definitions', '结果取值类型', '/outcome_kind'),
    *_rules('information', '原任务数据；不升级为总体', '/x', '/treatment', '/outcome'),
    *_rules('assumptions', '原任务条件', '/assumptions'),
    *_rules('evidence', '原名称、标识及元信息', '/name', '/target_id', '/target_fingerprint', '/metadata'),
    *under('/identification_spec', SPEC),
)

RESEARCH_FORMATS = {
    'MEAN_ORDER_D2_E1': MEAN_ORDER,
    'BINARY_IV_LATE_ATE': IV,
    'DAG_CLASSICAL_BACKDOOR': DAG, 'DAG_CLASSICAL_FRONTDOOR': DAG,
    'DAG_ADJUSTMENT': DAG, 'DAG_GENERAL_ID': DAG,
}


def business_rules(problem):
    # An unrecognized inquiry kind is retained opaque, never guessed from its fields.
    kinds = ('fixed_policy', 'finite_policy', 'observational_policy', 'observational_effect', 'shared_stratum', 'nodewise')
    if not isinstance(problem,dict) or problem.get('kind') not in kinds:
        return ()
    rules = _rules('method', '原业务方法标识', '/kind')
    if problem['kind']=='finite_policy':
        # Each component is a FixedPolicyInquiryV21; probabilities belong to the
        # target policy mixture, not to the historical assignment mechanism.
        rules += under('/inquiry/components/*', INQUIRY)
        rules += _rules('target','目标政策混合概率；不替代原分配律','/inquiry/policy_probabilities')
    else:
        rules += under('/inquiry', INQUIRY)
    return rules


def math_rules(record):
    rules = (*_rules('method', '上传格式及原生运算', '/format', '/operation'),
             *_rules('target', '上传规格绑定的原问；不自动证明同义', '/question'))
    if record.get('format') != 'causal-id.math-request/1' or not isinstance(record.get('problem'), dict):
        return rules
    op, p = record.get('operation'), record['problem']
    inner = ()
    if not isinstance(op,str):
        return rules
    if op in RESEARCH_FORMATS:
        inner = COMMON + RESEARCH_FORMATS[op]
        inner += _rules('evidence', '原图及资料来源绑定', '/graph_source', '/materials_sha256', '/source_sha256')
        inner += _rules('assumptions', '原读取声明；不是新审核', '/reading_declarations')
        if op in ('DAG_ADJUSTMENT', 'DAG_CLASSICAL_BACKDOOR', 'DAG_CLASSICAL_FRONTDOOR'):
            inner += _rules('method', '原指定调整/中介；不替换方案', '/adjustment', '/frontdoor_variable')
    elif op == 'population':
        inner = (*under('/spec', SPEC), *_rules('information', '原总体数值记录', '/population_truth'))
    elif op in ('task', 'batch', 'linear', 'effects', 'legacy_bridge', 'legacy_compare'):
        inner = (*under('/task', TASK), *_rules('information', '原 A4 信息及绑定', '/a4'),
                 *_rules('target', '有序线性项或逐问目标', '/terms', '/requests'))
        if op == 'legacy_compare':
            inner += under('/legacy_task', TASK)
    elif op == 'business':
        inner = business_rules(p)
    elif op == 'r3_pair':
        inner = tuple(r for side in ('left', 'right') for r in under('/'+side, business_rules(p.get(side, {}))))
    elif op in ('signature_support', 'quota_support'):
        inner = (*under('/study', STUDY), *_rules('target', '原诊断目标', '/target'),
                 *_rules('exposure', '原诊断签名', '/signature'))
    elif op == 'requirements':
        inner = _rules('method', '诊断请求；不是研究规格或识别结论', '/route', '/design_kind')
        rules += _rules('method', '原诊断参数（可为空）', '/problem')
    return rules + under('/problem', inner)


def record_rules(record, contract):
    if contract == 'policy-materials':
        return policy_rules(record)
    if contract == 'math-request':
        return math_rules(record)
    if contract in ('direct-report', 'policy-packet'):
        prefix = '/proof/evidence' if contract == 'direct-report' else '/evidence'
        parent = record.get('proof') if contract == 'direct-report' else record
        evidence = parent.get('evidence') if isinstance(parent,dict) else None
        evidence = evidence if isinstance(evidence,dict) else {}
        material = evidence.get('materials')
        material = material if isinstance(material,dict) else {}
        rules = (
            *_rules('model_answer', '模型原答；未被视图批准', '/draft', '/draft_parts', '/source_draft'),
            *_rules('result', '原展示结论或条件计算；不是批准', '/effective_answer', '/conditional_answer', '/parts', '/proof', '/evidence'),
            *_rules('target', '条件计算对应的目标（不替代模型原答）', '/conditional_answer/target'),
            *_rules('assumptions', '条件计算依赖的原前提（不是批准）', '/conditional_answer/assumptions'),
            *under(prefix+'/materials', policy_rules(material)),
            *_rules('target', '库所计算的目标；保留与模型目标的区别', prefix+'/claim/target'),
            *_rules('review', '原审核范围、决定和绑定', '/condition_review', '/review_record', '/review', '/review_scope',
                    '/scientific_approval', '/release_scope', '/production_admission'),
            *_rules('handoff', '原交接权限与内容（不推定收件）', '/estimation_handoff_allowed', '/estimate_handoff'),
            *_rules('unresolved', '原追问', '/clarification_questions'),
            *_rules('evidence', '原输入及来源摘要', '/source_case', '/case_id', '/source_text_sha256', '/draft_sha256', '/input_sha256', '/network_manifest'),
            *_rules('method', '原核验版本与检查记录', '/version', '/decision', '/checks', '/network_focus', '/question',
                    '/network_alignment', '/scope_choice', '/network_review'),
        )
        return rules
    return COMMON + _ADDITIONAL[contract]
