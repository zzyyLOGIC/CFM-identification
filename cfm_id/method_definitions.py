"""Method meaning, target operation and implementation are separate axes.

These descriptions do not select a reader, approve assumptions or prove a
theorem. Native contracts own the executable checks. A new binding must supply
an explicit shape; names and prefixes are never parsed to infer permissions.
"""
from dataclasses import asdict, dataclass
from .method_compat import canonical_id


@dataclass(frozen=True)
class Definition:
    id: str
    name: str
    identification_basis: str
    target_meaning: str


@dataclass(frozen=True)
class BindingShape:
    definition_ids: tuple[str, ...]
    operation: str
    implementation: str


DEFINITIONS = (
    Definition('network.randomized.local', '原设计条件平均的局部均值识别',
        '完整安排随机化；不由暴露定义推定充分性', '其余安排按原设计条件分布平均'),
    Definition('network.randomized.full_policy', '随机化下的完整政策均值识别',
        '完整安排随机化与目标完整安排支持', '完整政策下的评价对象均值'),
    Definition('network.randomized.signature_policy', '随机化与均值暴露充分性下的政策均值识别',
        '完整安排随机化、已采用的均值充分性及目标签名支持', '完整政策下的评价对象均值'),
    Definition('network.observational.full_policy', '条件交换性下的完整政策均值识别',
        '完整向量条件交换性与完整安排支持', '固定背景下的政策均值'),
    Definition('network.observational.signature_policy', '条件交换性与均值暴露充分性下的政策均值识别',
        '完整向量条件交换性、已采用的均值充分性及签名支持', '固定背景下的政策均值'),
    Definition('network.observational.observed_law', '按观测分配律平均的局部效应识别',
        '完整向量条件交换性', '其余安排按观测律条件平均的局部比较'),
    Definition('network.observational.shared_stratum', '共同分层调整的局部效应识别',
        '暴露充分性及给定共同分层的局部均值交换性', '按声明的总体分层质量平均'),
    Definition('network.observational.local_covariate', '局部协变量调整的局部效应识别',
        '暴露充分性及给定局部特征的均值交换性', '按声明的节点与邻居特征总体律平均'),
    Definition('network.bounds.mean_box', '有限均值模型求界',
        '完整声明的有限均值模型及结果界', '在同一可行模型中求目标范围'),
    Definition('network.bounds.mean_order', '带均值顺序约束的有限模型求界',
        '有限均值模型及实际采用的顺序限制', '在保留顺序限制的共同模型中求目标范围'),
    Definition('graph.backdoor', '后门调整', '后门准则', '指定干预下的结果分布'),
    Definition('graph.adjustment', '指定调整集识别', '对应调整集准则', '指定干预下的结果分布'),
    Definition('graph.frontdoor', '经典前门识别', '经典前门准则', '原合同支持的干预分布'),
    Definition('graph.id', '一般图 ID', '半马尔可夫模型下的图识别推导', '原合同支持的干预分布'),
    Definition('iv.binary.late', '二元工具变量 LATE 识别',
        '工具独立性、排除、单调性等原生条件及非零第一阶段', '服从者局部平均处理效应'),
    Definition('iv.binary.ate_bounds', '二元工具变量 ATE 求界',
        '二元响应类型模型及实际采用的限制', '总体平均处理效应的范围'),
    Definition('population.randomized_ate', '随机试验 ATE 识别',
        '随机化、一致性、无干扰、有限均值及双臂支持', '原合同人群的平均处理效应'),
    Definition('population.one_arm_ate', '单处理组 ATE 求界',
        '单臂支持下的完整声明模型；不得忽略额外限制', '平均处理效应的范围，可能无有限界'),
    Definition('population.binary_ate_bounds', '二元结果 Manski 界',
        '一致性、无干扰及完整声明的二元完成模型', '平均处理效应的范围'),
)

# Each tuple records meaning / operation / implementation, not an applicability
# assertion. Finite-policy weighting and contrasts are not new base theorems.
_ROWS = (
    ('network.randomized.local_mean', 'network.randomized.local', 'ARM_MEAN', 'native_arm'),
    ('network.randomized.local_contrast', 'network.randomized.local', 'FIRST_MINUS_SECOND', 'native_local_composition'),
    ('network.randomized.full_policy_mean', 'network.randomized.full_policy', 'MEAN', 'native_full_policy'),
    ('network.randomized.full_policy_contrast', 'network.randomized.full_policy', 'FIRST_MINUS_SECOND', 'native_endpoint_composition'),
    ('network.randomized.finite_policy_mean', 'network.randomized.full_policy', 'FINITE_POLICY_MEAN', 'native_finite_mixture'),
    ('network.randomized.signature_policy_mean', 'network.randomized.signature_policy', 'MEAN', 'native_signature_policy'),
    ('network.randomized.signature_policy_contrast', 'network.randomized.signature_policy', 'FIRST_MINUS_SECOND', 'native_endpoint_composition'),
    ('network.observational.full_policy_mean', 'network.observational.full_policy', 'MEAN', 'native_fixed_background'),
    ('network.observational.signature_policy_mean', 'network.observational.signature_policy', 'MEAN', 'native_fixed_background_signature'),
    ('network.observational.observed_law_contrast', 'network.observational.observed_law', 'FIRST_MINUS_SECOND', 'native_observed_law'),
    ('network.observational.shared_stratum_contrast', 'network.observational.shared_stratum', 'FIRST_MINUS_SECOND', 'native_shared_strata'),
    ('network.observational.local_covariate_contrast', 'network.observational.local_covariate', 'FIRST_MINUS_SECOND', 'native_local_binary_features'),
    *((f'BOUNDED_POLICY_{target}_{variant}', 'network.bounds.mean_box', operation, variant.lower())
      for target, operation in (('MEAN', 'MEAN'), ('CONTRAST', 'FIRST_MINUS_SECOND'))
      for variant in ('D2_E1', 'D2_E4', 'FINITE')),
    ('MEAN_ORDER_D2_E1', 'network.bounds.mean_order', 'FIRST_MINUS_SECOND', 'd2_e1_order'),
    ('DAG_CLASSICAL_BACKDOOR', 'graph.backdoor', 'INTERVENTIONAL_DISTRIBUTION', 'native_backdoor'),
    ('DAG_ADJUSTMENT', 'graph.adjustment', 'INTERVENTIONAL_DISTRIBUTION', 'native_adjustment'),
    ('DAG_CLASSICAL_FRONTDOOR', 'graph.frontdoor', 'INTERVENTIONAL_DISTRIBUTION', 'native_frontdoor'),
    ('DAG_GENERAL_ID', 'graph.id', 'INTERVENTIONAL_DISTRIBUTION', 'native_id'),
    ('BINARY_IV_LATE_ATE', 'iv.binary.late iv.binary.ate_bounds', 'EXPLICIT_IV_TARGETS', 'binary_response_types'),
    ('RANDOMIZED_ATE_V3', 'population.randomized_ate', 'FIRST_MINUS_SECOND', 'native_population_ate'),
    ('ONE_ARM_ATE_BOUNDS_V2', 'population.one_arm_ate', 'FIRST_MINUS_SECOND', 'bounded_outcome_domain'),
    ('ONE_ARM_NO_OUTCOME_RESTRICTION_V2', 'population.one_arm_ate', 'FIRST_MINUS_SECOND', 'unrestricted_outcome_domain'),
    ('MANSKI_BINARY_ATE_V2', 'population.binary_ate_bounds', 'FIRST_MINUS_SECOND', 'binary_outcome_domain'),
)
_SHAPES = {key: BindingShape(tuple(definitions.split()), operation, implementation)
           for key, definitions, operation, implementation in _ROWS}
if len(_SHAPES) != len(_ROWS):
    raise RuntimeError('DUPLICATE_METHOD_BINDING_SHAPE')
_DEFINITIONS = {d.id: d for d in DEFINITIONS}
if len(_DEFINITIONS) != len(DEFINITIONS) or any(
        id not in _DEFINITIONS for s in _SHAPES.values() for id in s.definition_ids):
    raise RuntimeError('INVALID_METHOD_DEFINITION_REGISTRY')


def describe_binding(method_id):
    key = canonical_id(method_id)
    if key not in _SHAPES:
        raise ValueError('UNDOCUMENTED_METHOD_BINDING_SHAPE:' + str(method_id))
    return asdict(_SHAPES[key])


def definitions():
    return [asdict(d) for d in DEFINITIONS]
