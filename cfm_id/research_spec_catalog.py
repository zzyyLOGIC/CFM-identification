"""Single registry for orthogonal study attributes, not a solver registry.

Names are semantic keys. D/E numbers are legacy template aliases; R identifiers
are methods. Adding a descriptor here never registers an executable combination.
"""
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class Dimension:
    key: str
    label: str
    legacy_fields: tuple[str, ...] = ()


def dimensions(*rows):
    return tuple(Dimension(key, label, tuple(fields.split())) for key, label, fields in rows)


FACET_DIMENSIONS = MappingProxyType({
    'target': dimensions(
        ('intervention', '干预及有序比较两端', 'first second intervention reference comparator comparison assignment policy_assignment policy arms arm x x_value treatment'),
        ('remaining_assignment', '其余安排如何固定或平均', 'remaining_assignment remaining_source_ids averaging averaging_scope'),
        ('endpoint_function', '单端函数：均值、概率或分布', 'quantity endpoint_function outcome_function'),
        ('operation', '比较操作及方向', 'operation direction'),
        ('population', '评价人群', 'population scope node_id node_ids evaluation_roster'),
        ('aggregation', '汇总和政策混合权重', 'aggregation weights unit_weights policy_probabilities terms'),
        ('outcome', '结果与事件', 'outcome outcome_ref y y_value'),
        ('time_context', '时期、固定背景与标准化', 'time period outcome_period context shared_outcome_and_context conditioning context_reference'),
        ('label', '原目标名称（不作互斥分类）', 'kind estimand target_semantics name'),
    ),
    'assignment': dimensions(
        ('assigned_quantity', '被分配的量', 'assigned_variable assigned_quantity treatment_variable'),
        ('randomization_unit', '分配单位：个体或簇', 'randomization_unit clusters'),
        ('joint_law', '完整分配律及概率参数', 'probabilities propensities p cluster_probabilities treated_sets set_probabilities unit_weights assignment_design_json assignment_design regime observation_regime'),
        ('stratification', '分层及层内名单', 'groups strata'),
        ('quota', '名额', 'fixed_count treated_quotas quota m'),
        ('stages', '阶段与方案混合', 'quota_profiles profile_probabilities stages'),
        ('acceptance', '接受筛选及基础设计', 'base_design balance_rule balance_covariates balance_tolerance'),
        ('template', '原设计模板与版本', 'kind design'),
    ),
    'exposure': dimensions(
        ('reference_set', '参考对象及方向', 'core_collaborators groups reference_set'),
        ('statistic', '统计量与权重', 'weights mode statistic'),
        ('labels', '标签、分档与阈值', 'threshold labels'),
        ('boundary', '平票、孤立点及零分母', 'boundary isolated ties'),
        ('template', '原映射模板与版本', 'kind grouping exposure'),
    ),
    'structure': dimensions(
        ('representation', '模型表示与语义', 'causal_semantics representation_type model'),
        ('unit_network', '对象关系网', 'edges undirected_edges adjacency graph_kind graph_timing_claim edge_list_complete network_id graph_scope'),
        ('variable_graph', '变量因果图与潜在共同原因', 'directed directed_edges bidirected bidirected_edges relations common_causes graph_status'),
        ('variable_roles', '变量角色', 'z d y instrument treatment outcome binary'),
        ('domain', '数学适用域', 'model_scope candidate_structure_scope context_semantics outcome_semantics variable_domains domain'),
    ),
    'information': dimensions(
        ('object', '信息对象及具体内容', 'operator basis values cells full local observed population_truth x treatment outcome means'),
        ('level', '总体值、符号算子或有限记录', 'availability level regime outcome_representation data_kind'),
        ('coverage', '对象、时期、背景与坐标覆盖', 'outcome_nodes assignment_cells signature_cells arm_cells joint_scope scope information_scope shared_scope_digest protocol_digest'),
        ('closure', '信息清单的完整性声明', 'listed_means_are_complete_information closure complete_information'),
        ('acquisition', '抽样、缺失、选择与测量', 'data_description sampling missingness measurement selection'),
        ('source', '信息来源与版本', 'provenance source_ids source_id source_sha256 a4_provenance'),
    ),
    'assumptions': dimensions(
        ('proposition', '命题内容', 'value proposition statement code kind constraint definition'),
        ('polarity', '明确的肯定或否定', 'polarity negated'),
        ('scope', '对象和适用范围', 'scope covered_nodes nodes order_scope mean_sufficiency_scope bounds_scope context'),
        ('adoption', '原文采用态度', 'status adoption choice decision'),
        ('evidence', '原文依据', 'source_ids source_id quote evidence'),
        ('review', '独立审核（不从原文状态推定）', 'review_record review_scope'),
    ),
})


@dataclass(frozen=True)
class Template:
    key: str
    legacy_id: str
    aliases: tuple[str, ...]
    # (axis, machine value, human explanation); immutable and versioned.
    attributes: tuple[tuple[str, str, str], ...]


STRATIFIED_QUOTA_ATTRIBUTES = (
    ('randomization_unit','individual','单位'),
    ('joint_law','product_uniform_within_strata','各层内均匀固定名额，层间独立'),
    ('stages','one_stage','一阶段'), ('acceptance','none','无附加接受筛选'),
)
MAJORITY_LABEL = ('labels','strict_majority_binary','严格过半记 1，否则 0')

ASSIGNMENT_TEMPLATES = (
    Template('independent_bernoulli', 'D1', ('INDEPENDENT_BERNOULLI', 'iid_bernoulli_binary_v1', 'heterogeneous_bernoulli_binary_v1'), (
        ('randomization_unit', 'individual', '单位'), ('joint_law', 'independent_bernoulli', '独立 Bernoulli；允许不同概率'),
        ('stratification', 'not_required', '此模板不要求分层'), ('stages', 'one_stage', '一阶段'), ('acceptance', 'none', '无附加接受筛选'))),
    Template('uniform_fixed_quota', 'D2', ('UNIFORM_FIXED_QUOTA', 'D2_UNIFORM_FIXED_QUOTA', 'complete_randomization_binary_v1'), (
        ('randomization_unit', 'individual', '单位'), ('joint_law', 'uniform_fixed_quota', '合法固定名额名单等概率'),
        ('stratification', 'whole_roster', '完整名单上的一个名额'), ('stages', 'one_stage', '一阶段'), ('acceptance', 'none', '无附加接受筛选'))),
    Template('two_stratum_fixed_quota', 'D3', ('TWO_GROUP_FIXED_QUOTA', 'two_group_fixed_quota_binary_v1'), (
        *STRATIFIED_QUOTA_ATTRIBUTES, ('stratification', 'exactly_two', '原两组合同'))),
    Template('cluster_bernoulli', 'D4', ('CLUSTER_BERNOULLI', 'cluster_bernoulli_binary_v2_4'), (
        ('randomization_unit', 'cluster', '簇'), ('joint_law', 'independent_cluster_bernoulli', '簇间独立 Bernoulli、簇内共同分配'),
        ('stages', 'one_stage', '一阶段'), ('acceptance', 'none', '无附加接受筛选'))),
    Template('multi_stratum_fixed_quota', 'D5', ('MULTI_GROUP_FIXED_QUOTA', 'multi_group_fixed_quota_binary_v2_5'), (
        *STRATIFIED_QUOTA_ATTRIBUTES, ('stratification', 'at_least_three', '原至少三组合同'))),
    Template('quota_profile_mixture', 'D6', ('TWO_STAGE_QUOTA_MIXTURE', 'two_stage_quota_mixture_binary_v2_7'), (
        ('randomization_unit', 'individual', '单位'), ('joint_law', 'mixture_of_stratified_quota_laws', '按名额方案混合组内固定名额律'),
        ('stratification', 'declared_groups', '保留方案所用分组'), ('stages', 'profile_then_assignment', '先选方案、再按方案分配'), ('acceptance', 'none', '无附加接受筛选'))),
    Template('weighted_fixed_quota', 'D7', ('UNEQUAL_PROBABILITY_FIXED_QUOTA', 'unequal_probability_fixed_quota_binary_v1'), (
        ('randomization_unit', 'individual', '单位'), ('joint_law', 'explicit_or_product_weight_fixed_quota', '不等概率固定名额；原显式名单律或乘积权重'),
        ('stages', 'one_stage', '一阶段'), ('acceptance', 'none', '无附加接受筛选'))),
    Template('balance_conditioned_quota', 'D8', ('RERANDOMIZED_BALANCED', 'rerandomized_balanced_binary_v1'), (
        ('randomization_unit', 'individual', '单位'), ('joint_law', 'base_law_conditioned_on_acceptance', 'D7 基础律条件于接受事件并重新归一化'),
        ('stages', 'base_draw_and_accept', '基础抽签与接受筛选'), ('acceptance', 'coordinatewise_mean_difference', '各给定协变量的两组均值差绝对值不超过原阈值'))),
)


EXPOSURE_TEMPLATES = (
    Template('neighbor_strict_majority', 'E1', ('strict_majority_ties_low', 'E1_STRICT_MAJORITY_TIES_LOW_ISOLATED_ZERO'), (
        ('reference_set', 'all_neighbors', '全部直接邻居'), ('statistic', 'count_and_degree', '接受处理的人数及参考集合大小'),
        MAJORITY_LABEL, ('boundary', 'ties_low_isolated_zero', '平票 0；孤立点 0'))),
    Template('neighbor_fraction_tertiles', 'E2', ('three_level_treated_neighbor_fraction',), (
        ('reference_set', 'all_neighbors', '全部直接邻居'), ('statistic', 'treated_fraction', '接受处理的比例'),
        ('labels', 'left_closed_thirds', '[0,1/3)→0；[1/3,2/3)→1；[2/3,1]→2'), ('boundary', 'isolated_undefined', '孤立点未定义'))),
    Template('core_strict_majority', 'E3', ('pretreatment_core_collaborator_majority',), (
        ('reference_set', 'pretreatment_core_neighbors', '预先指定的核心伙伴'), ('statistic', 'count_and_core_size', '核心伙伴中接受处理的人数及集合大小'),
        MAJORITY_LABEL, ('boundary', 'nonempty_neighbor_subset_ties_low', '平票 0；核心集合必须非空且是实际邻居子集'))),
    Template('neighbor_treated_count', 'E4', ('exact_treated_neighbor_count',), (
        ('reference_set', 'all_neighbors', '全部直接邻居'), ('statistic', 'treated_count', '接受处理的人数'),
        ('labels', 'identity_integer', '保留精确人数'), ('boundary', 'isolated_zero', '孤立点 0'))),
    Template('neighbor_any_treated', 'E5', ('any_treated_neighbor',), (
        ('reference_set', 'all_neighbors', '全部直接邻居'), ('statistic', 'any_treated', '是否有至少一人接受处理'),
        ('labels', 'any_binary', '至少一人记 1，否则 0'), ('boundary', 'isolated_zero', '孤立点 0'))),
)


def _aliases(templates, upper=False):
    result = {}
    for item in templates:
        for alias in item.aliases:
            for name in (alias, alias.upper()) if upper else (alias,):
                if name in result and result[name] != item:
                    raise ValueError('AMBIGUOUS_TEMPLATE_ALIAS: ' + name)
                result[name] = item
    return MappingProxyType(result)


DESIGN_LOOKUP = _aliases(ASSIGNMENT_TEMPLATES)
EXPOSURE_LOOKUP = _aliases(EXPOSURE_TEMPLATES, upper=True)


@dataclass(frozen=True)
class DesignProtocol:
    """Legacy wire/constructor compatibility for one internal design template."""
    template: str
    business_kind: str
    native_kind: str
    fields: tuple[str, ...]
    constructor: str


# D3/D5 share one field layout and probability-law family. Their old layer-count
# domains and native certificate types remain explicit compatibility boundaries.
STRATIFIED_QUOTA_FIELDS = ('groups','treated_quotas')
WEIGHTED_QUOTA_FIELDS = ('fixed_count','treated_sets','set_probabilities','unit_weights')
DESIGN_PROTOCOLS = (
    DesignProtocol('independent_bernoulli','INDEPENDENT_BERNOULLI','heterogeneous_bernoulli_binary_v1',
                   ('probabilities',),'make_heterogeneous_bernoulli_arm_task'),
    DesignProtocol('uniform_fixed_quota','UNIFORM_FIXED_QUOTA','complete_randomization_binary_v1',
                   ('fixed_count',),'make_complete_randomization_arm_task'),
    DesignProtocol('two_stratum_fixed_quota','TWO_GROUP_FIXED_QUOTA','two_group_fixed_quota_binary_v1',
                   STRATIFIED_QUOTA_FIELDS,'make_two_group_quota_arm_task'),
    DesignProtocol('cluster_bernoulli','CLUSTER_BERNOULLI','cluster_bernoulli_binary_v2_4',
                   ('clusters','cluster_probabilities'),'make_cluster_bernoulli_arm_task'),
    DesignProtocol('multi_stratum_fixed_quota','MULTI_GROUP_FIXED_QUOTA','multi_group_fixed_quota_binary_v2_5',
                   STRATIFIED_QUOTA_FIELDS,'make_multi_group_quota_arm_task'),
    DesignProtocol('quota_profile_mixture','TWO_STAGE_QUOTA_MIXTURE','two_stage_quota_mixture_binary_v2_7',
                   ('groups','quota_profiles','profile_probabilities'),'make_two_stage_quota_arm_task'),
    DesignProtocol('weighted_fixed_quota','UNEQUAL_PROBABILITY_FIXED_QUOTA','unequal_probability_fixed_quota_binary_v1',
                   WEIGHTED_QUOTA_FIELDS,'make_unequal_probability_fixed_quota_arm_task'),
    DesignProtocol('balance_conditioned_quota','RERANDOMIZED_BALANCED','rerandomized_balanced_binary_v1',
                   WEIGHTED_QUOTA_FIELDS+('balance_covariates','balance_tolerance'),'make_rerandomized_balanced_arm_task'),
)
DESIGN_PROTOCOL_BY_KIND = MappingProxyType({p.business_kind:p for p in DESIGN_PROTOCOLS})
BUSINESS_DESIGN_FIELDS = MappingProxyType({p.business_kind:p.fields for p in DESIGN_PROTOCOLS})
BUSINESS_NATIVE_DESIGNS = MappingProxyType({p.business_kind:p.native_kind for p in DESIGN_PROTOCOLS})
BUSINESS_EXPOSURE_GROUPS = MappingProxyType({
    **{t.aliases[0].upper():t.aliases[0] for t in EXPOSURE_TEMPLATES},
    'WEIGHTED_EXPOSURE':'weighted_exposure','GROUPED_EXPOSURE':'grouped_exposure',
})

# The roles can coexist; this is navigation, not a mutually-exclusive classifier.
ASSUMPTION_ROLES = MappingProxyType({
    'consistency': ('observation_intervention_bridge',),
    'randomization': ('observation_intervention_bridge',),
    'exchangeability': ('observation_intervention_bridge',),
    'full_assignment_randomization': ('observation_intervention_bridge',),
    'randomization_claim': ('observation_intervention_bridge',),
    'consistency_claim': ('observation_intervention_bridge',),
    'first_stage_exclusion': ('response_restriction',),
    'mean_sufficiency': ('response_restriction',),
    'mean_sufficiency_claim': ('response_restriction',),
    'monotonicity': ('response_restriction',),
    'bounds': ('response_restriction',),
    'node_orders': ('response_restriction',),
    'moments_claim': ('well_defined_expression',),
    'integrability': ('well_defined_expression',),
})

METHOD_NAVIGATION = MappingProxyType({
    'R1a': '原设计内局部状态的条件平均',
    'R1b': '完整名单政策的条件均值',
    'R2': '均值充分性下的政策签名均值',
    'R3': '观察性网络方法家族；具体目标与条件另记',
})


def validate_catalog():
    for facet, axes in FACET_DIMENSIONS.items():
        if len({a.key for a in axes}) != len(axes):
            raise ValueError('DUPLICATE_DIMENSION: ' + facet)
    for facet, templates in (('assignment', ASSIGNMENT_TEMPLATES), ('exposure', EXPOSURE_TEMPLATES)):
        allowed = {a.key for a in FACET_DIMENSIONS[facet]}
        for item in templates:
            if any(axis not in allowed for axis, _, _ in item.attributes):
                raise ValueError('UNKNOWN_TEMPLATE_DIMENSION: ' + item.key)
    if len(DESIGN_PROTOCOL_BY_KIND)!=len(DESIGN_PROTOCOLS):
        raise ValueError('DUPLICATE_DESIGN_PROTOCOL')
    for p in DESIGN_PROTOCOLS:
        if DESIGN_LOOKUP[p.business_kind].key!=p.template or DESIGN_LOOKUP[p.native_kind].key!=p.template:
            raise ValueError('PROTOCOL_TEMPLATE_MISMATCH: ' + p.business_kind)
    return True


validate_catalog()
