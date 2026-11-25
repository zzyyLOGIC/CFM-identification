"""Shared design/exposure field rules, without inference or scientific approval.

Only declared values are checked. Missing parameters stay missing; this module
does not estimate a design, complete groups or select a target from prose.
"""
from fractions import Fraction
from cfm_id.research_spec_catalog import BUSINESS_DESIGN_FIELDS, BUSINESS_EXPOSURE_GROUPS


DESIGN_FIELDS = dict(BUSINESS_DESIGN_FIELDS)
ASSIGNMENT_FIELDS = tuple(dict.fromkeys(k for fields in DESIGN_FIELDS.values() for k in fields))
PROBABILITIES_DESCRIPTION = (
    '仅INDEPENDENT_BERNOULLI使用：各对象独立抽签的启用概率，约分分数字符串。'
    '该设计的明确概率规则应完整读取；缺少规则保持null。'
    '固定名额、分组、簇或两阶段设计使用各自专门参数，本字段必须为null；'
    '不能把这些设计可推导的边际启用概率填到此处，也不能因此判定材料缺少概率。')
EXPOSURE_GROUPS = dict(BUSINESS_EXPOSURE_GROUPS)
D6_CONDITION = 'first_stage_profile_no_direct_outcome_effect'
CORE_EXPOSURE = 'PRETREATMENT_CORE_COLLABORATOR_MAJORITY'


def assignment_schema(schema):
    """Publish the same mutually exclusive fields enforced by validation.

    Missing active parameters remain nullable and require clarification. Only
    inactive parameters are restricted to null; no design is inferred here.
    """
    props=schema.get('properties',{})
    schema['allOf']=[
        {'if':{'properties':{'kind':{'const':kind}},'required':['kind']},
         'then':{'properties':{name:{'type':'null'} for name in ASSIGNMENT_FIELDS
                               if name not in allowed and name in props}}}
        for kind,allowed in DESIGN_FIELDS.items()]


def validate_assignment_ownership(assignment):
    allowed=DESIGN_FIELDS.get(assignment.kind)
    if allowed is not None and any(getattr(assignment,k) is not None
            for k in ASSIGNMENT_FIELDS if k not in allowed):
        raise ValueError('CONFLICTING_DESIGN_FIELDS')

ASSIGNMENT_GUIDANCE = '''assignment只读原试点的完整分配规则，不是未来政策。INDEPENDENT_BERNOULLI为逐对象独立抽签，probabilities按对象记录已知概率；UNIFORM_FIXED_QUOTA为均匀固定总名额，fixed_count记录名额。TWO_GROUP_FIXED_QUOTA为两个不交组各自均匀抽固定名额，MULTI_GROUP_FIXED_QUOTA为多个组的同类设计，groups与treated_quotas按相同顺序填写，各组抽取独立。CLUSTER_BERNOULLI为固定簇内对象一起处理、不同簇独立抽签，clusters与cluster_probabilities按相同顺序记录。TWO_STAGE_QUOTA_MIXTURE先按已知联合概率抽一个各组名额向量，再在各组均匀抽取且给定向量后各组独立；groups、quota_profiles、profile_probabilities保留原顺序与全部方案，不能用平均名额或组边际概率替代联合方案。分组或簇必须是原文明示的完整不交划分；无法对应的规则用OTHER，未说明用UNKNOWN；缺少必要参数保留null，不估计或补造。不属于所选设计的参数为null。assignment.source_ids覆盖设计、划分、名额或概率全部实际填写的事实。UNEQUAL_PROBABILITY_FIXED_QUOTA为恰好抽取固定名额fixed_count但各完整名单概率不等：treated_sets与set_probabilities按相同顺序列出全部m人处理名单及其精确概率，或改用unit_weights按各对象非负权重的乘积归一得到名单概率；两者只填其一。RERANDOMIZED_BALANCED先按明确的固定名额基础律抽签，再只保留满足平衡条件的名单并重新归一（拒绝抽样）。基础律仍须填写unit_weights或treated_sets/set_probabilities；原文明示均匀抽取时unit_weights为各对象1，未说明概率规则则保持缺项。balance_covariates为处理前协变量，balance_tolerance为处理组与对照组协变量均值的绝对差上限。'''
EXPOSURE_GUIDANCE = '''exposure只读原文明示的定义，不批准暴露充分性。STRICT_MAJORITY_TIES_LOW：处理邻居严格过半为1，平票及孤立点为0。THREE_LEVEL_TREATED_NEIGHBOR_FRACTION：比例小于1/3为0，至少1/3但小于2/3为1，至少2/3为2；孤立点未定义。PRETREATMENT_CORE_COLLABORATOR_MAJORITY：对原文指定的处理前核心同伴作严格多数分组，core_collaborators按每个对象列出非空邻居子集，不能自行选人。EXACT_TREATED_NEIGHBOR_COUNT：暴露值为使用的邻居人数。ANY_TREATED_NEIGHBOR：至少一名邻居使用为1，否则0。其他定义用OTHER，未说明用UNKNOWN；除核心同伴定义外core_collaborators=null。exposure.source_ids须覆盖定义及实际核心名单。LocalArm和总体均值格子的exposure使用该定义的真实状态，不一律限制成0/1；格子范围仅由原文提供的信息决定。WEIGHTED_EXPOSURE为处理邻居的固定权重暴露：weights记录非负权重（有理字符串），mode明确为'sum'（加权和）或'proportion'（按权重和归一的比例），两者都必须填写；GROUPED_EXPOSURE为按处理前分组分别记录的处理邻居人数：groups给出组标签到成员邻居的映射（各组不相交），状态是按标签稳定排序的元组；这两类暴露已接入正式流程（单臂/批量/组合证书、效应派单与单局部均值入口）；政策值路线不依赖暴露，随机化均值签名路线不采用 W/G，但读取仍须完整捕获weights/mode/groups。'''
STAGE_GUIDANCE = '''first_stage_exclusion独立记录原文是否采用“在最终完整处理名单相同的情况下，第一阶段抽到哪个配额方案不再直接影响结果”。它不是完整分配规律或随机化声明。D6需要这项条件；按原文填写ADOPTED/PROPOSED/NOT_ADOPTED/UNDECIDED/NOT_STATED/CONFLICTING及source_ids，不能由两阶段抽签本身推定。非D6且未提该条件时用null。读取状态不是科学批准，后续必须独立审核。'''


def missing_assignment(assignment, nodes):
    fields = DESIGN_FIELDS.get(assignment.kind, ())
    missing = [f'assignment.{k}' for k in fields if getattr(assignment, k) is None]
    if assignment.kind == 'UNKNOWN':
        missing.append('assignment.kind')
    if assignment.kind == 'INDEPENDENT_BERNOULLI' and assignment.probabilities is not None:
        if set(assignment.probabilities) != set(nodes):
            missing.append('assignment.probabilities:complete_node_scope')
    if assignment.kind in ('UNEQUAL_PROBABILITY_FIXED_QUOTA', 'RERANDOMIZED_BALANCED'):
        missing = [m for m in missing
                   if m not in ('assignment.treated_sets', 'assignment.set_probabilities', 'assignment.unit_weights')]
        law = assignment.treated_sets is not None and assignment.set_probabilities is not None
        weights = assignment.unit_weights is not None
        if not (law ^ weights):
            missing.append('assignment.treated_sets/set_probabilities or unit_weights')
        elif weights and set(assignment.unit_weights) != set(nodes):
            missing.append('assignment.unit_weights:complete_node_scope')
    if assignment.kind == 'RERANDOMIZED_BALANCED':
        if assignment.balance_covariates is None or assignment.balance_tolerance is None:
            missing.append('assignment.balance_covariates/balance_tolerance')
    return missing


def missing_exposure(exposure, nodes):
    if exposure.kind == 'UNKNOWN':
        return ['exposure.kind']
    if exposure.kind == CORE_EXPOSURE:
        if exposure.core_collaborators is None or set(exposure.core_collaborators) != set(nodes):
            return ['exposure.core_collaborators:complete_pretreatment_map']
    if exposure.kind == 'WEIGHTED_EXPOSURE':
        missing = []
        if exposure.weights is None:
            missing.append('exposure.weights')
        if exposure.mode is None:
            missing.append('exposure.mode')
        return missing
    if exposure.kind == 'GROUPED_EXPOSURE':
        if exposure.groups is None:
            return ['exposure.groups']
    return []


def validate_components(assignment, exposure, nodes, edges):
    """Reject contradictions in supplied values without filling absent values."""
    validate_assignment_ownership(assignment)
    if assignment.probabilities is not None and (not set(assignment.probabilities) <= set(nodes)
            or any(not 0 <= Fraction(v) <= 1 for v in assignment.probabilities.values())):
        raise ValueError('INVALID_DESIGN_PROBABILITIES')
    if assignment.fixed_count is not None and not 0 <= assignment.fixed_count <= len(nodes):
        raise ValueError('INVALID_FIXED_QUOTA')
    for name in ('groups', 'clusters'):
        parts = getattr(assignment, name)
        if parts is None:
            continue
        flat = [n for group in parts for n in group]
        if not parts or any(not g for g in parts) or len(set(flat)) != len(flat) or set(flat) != set(nodes):
            raise ValueError('COMPLETE_DISJOINT_DESIGN_PARTITION_REQUIRED')
        if name == 'groups' and assignment.kind == 'TWO_GROUP_FIXED_QUOTA' and len(parts) != 2:
            raise ValueError('TWO_GROUP_DESIGN_REQUIRES_TWO_GROUPS')
        if name == 'groups' and assignment.kind == 'MULTI_GROUP_FIXED_QUOTA' and not 3 <= len(parts) <= 64:
            raise ValueError('MULTI_GROUP_NATIVE_DOMAIN_REQUIRES_3_TO_64_GROUPS')
        if name == 'groups' and assignment.kind == 'TWO_STAGE_QUOTA_MIXTURE' and not 2 <= len(parts) <= 64:
            raise ValueError('TWO_STAGE_NATIVE_DOMAIN_REQUIRES_2_TO_64_GROUPS')
    groups = assignment.groups
    if assignment.treated_quotas is not None:
        q = assignment.treated_quotas
        if any(v < 0 for v in q) or (groups is not None and
                (len(q) != len(groups) or any(v > len(g) for v,g in zip(q,groups)))):
            raise ValueError('INVALID_GROUP_QUOTAS')
    if assignment.cluster_probabilities is not None:
        p = assignment.cluster_probabilities
        if any(not 0 <= Fraction(v) <= 1 for v in p) or (assignment.clusters is not None and len(p) != len(assignment.clusters)):
            raise ValueError('INVALID_CLUSTER_PROBABILITIES')
    if assignment.quota_profiles is not None:
        profiles = assignment.quota_profiles
        if not 1 <= len(profiles) <= 64 or len({tuple(q) for q in profiles}) != len(profiles):
            raise ValueError('DISTINCT_NONEMPTY_QUOTA_PROFILES_REQUIRED')
        for q in profiles:
            if any(v < 0 for v in q) or (groups is not None and
                    (len(q) != len(groups) or any(v > len(g) for v,g in zip(q,groups)))):
                raise ValueError('INVALID_QUOTA_PROFILE')
    if assignment.profile_probabilities is not None:
        probabilities = [Fraction(v) for v in assignment.profile_probabilities]
        if not probabilities or any(v <= 0 for v in probabilities) or sum(probabilities) != 1:
            raise ValueError('EXACT_NORMALIZED_PROFILE_PROBABILITIES_REQUIRED')
        if assignment.quota_profiles is not None and len(probabilities) != len(assignment.quota_profiles):
            raise ValueError('QUOTA_PROFILE_PROBABILITY_ALIGNMENT_REQUIRED')
    if assignment.treated_sets is not None or assignment.set_probabilities is not None:
        if (assignment.kind not in ('UNEQUAL_PROBABILITY_FIXED_QUOTA', 'RERANDOMIZED_BALANCED')
                or assignment.treated_sets is None or assignment.set_probabilities is None
                or not assignment.treated_sets or len(assignment.treated_sets) != len(assignment.set_probabilities)):
            raise ValueError('UNEQUAL_TREATED_SETS_ALIGNMENT_REQUIRED')
        m = assignment.fixed_count
        if m is None:
            raise ValueError('UNEQUAL_TREATED_SETS_REQUIRE_FIXED_COUNT')
        total = Fraction(0)
        seen = set()
        for treated, raw in zip(assignment.treated_sets, assignment.set_probabilities):
            t = tuple(sorted(treated))
            if len(t) != m or len(set(t)) != len(t) or not set(t) <= set(nodes):
                raise ValueError('UNEQUAL_TREATED_SETS_MUST_BE_SIZE_M_SUBSETS')
            if t in seen:
                raise ValueError('UNEQUAL_TREATED_SETS_DISTINCT_REQUIRED')
            seen.add(t)
            p = Fraction(raw)
            if not 0 <= p <= 1:
                raise ValueError('INVALID_SET_PROBABILITY')
            total += p
        if total != 1:
            raise ValueError('EXACT_NORMALIZED_SET_PROBABILITIES_REQUIRED')
    if assignment.unit_weights is not None:
        if assignment.kind not in ('UNEQUAL_PROBABILITY_FIXED_QUOTA', 'RERANDOMIZED_BALANCED'):
            raise ValueError('UNIT_WEIGHTS_REQUIRE_TASK1_DESIGN')
        if set(assignment.unit_weights) != set(nodes):
            raise ValueError('UNIT_WEIGHTS_COMPLETE_NODE_SCOPE_REQUIRED')
        if any(Fraction(v) < 0 for v in assignment.unit_weights.values()):
            raise ValueError('INVALID_UNIT_WEIGHTS')
    if assignment.balance_covariates is not None or assignment.balance_tolerance is not None:
        if assignment.kind != 'RERANDOMIZED_BALANCED':
            raise ValueError('BALANCE_RULE_REQUIRES_RERANDOMIZED_DESIGN')
        # A missing half of the declaration is a question for the user.
        # Validate supplied values here; missing_assignment owns completeness.
        if assignment.balance_tolerance is not None and Fraction(assignment.balance_tolerance) < 0:
            raise ValueError('INVALID_BALANCE_TOLERANCE')
        if assignment.balance_covariates is not None and not assignment.balance_covariates:
            raise ValueError('BALANCE_COVARIATES_COMPLETE_NODE_SCOPE_REQUIRED')
        for name, values in (assignment.balance_covariates or {}).items():
            if not str(name).strip() or not values or set(values) != set(nodes):
                raise ValueError('BALANCE_COVARIATES_COMPLETE_NODE_SCOPE_REQUIRED')
    if exposure.core_collaborators is not None:
        if exposure.kind != CORE_EXPOSURE:
            raise ValueError('CORE_MAP_WITH_OTHER_EXPOSURE')
        neighbors = {n:set() for n in nodes}
        for u,v in edges:
            neighbors[u].add(v); neighbors[v].add(u)
        if not set(exposure.core_collaborators) <= set(nodes):
            raise ValueError('UNKNOWN_CORE_MAP_NODE')
        for n,core in exposure.core_collaborators.items():
            if not core or len(set(core)) != len(core) or not set(core) <= neighbors[n]:
                raise ValueError('NONEMPTY_PRETREATMENT_NEIGHBOR_SUBSET_REQUIRED')
    if exposure.kind == 'WEIGHTED_EXPOSURE' or exposure.weights is not None or exposure.mode is not None:
        if exposure.kind != 'WEIGHTED_EXPOSURE' or exposure.weights is None or exposure.mode is None:
            raise ValueError('WEIGHTED_EXPOSURE_REQUIRES_WEIGHTS_AND_MODE')
        if exposure.mode not in ('sum', 'proportion'):
            raise ValueError('INVALID_WEIGHTED_MODE')
        if any(Fraction(v) < 0 for v in exposure.weights.values()):
            raise ValueError('INVALID_EXPOSURE_WEIGHTS')
    if exposure.kind == 'GROUPED_EXPOSURE' or exposure.groups is not None:
        if exposure.kind != 'GROUPED_EXPOSURE' or exposure.groups is None or not exposure.groups:
            raise ValueError('GROUPED_EXPOSURE_REQUIRES_GROUPS')
        seen = set()
        for label, members in exposure.groups.items():
            if not str(label).strip() or not members:
                raise ValueError('INVALID_EXPOSURE_GROUPS')
            memberset = set(members)
            if len(memberset) != len(members) or seen.intersection(memberset):
                raise ValueError('EXPOSURE_GROUPS_MUST_BE_DISJOINT')
            seen.update(memberset)


# These diagnostics explain existing structural checks. They neither choose a
# design nor repair values. The native parser still owns formal acceptance.
_COMPONENT_DIAGNOSTICS = {
    'BALANCE_COVARIATES_COMPLETE_NODE_SCOPE_REQUIRED': (
        '/assignment/balance_covariates',
        '外层为变量名，内层为全部study.nodes对象编号到有理数字符串的映射。核对原文；缺失值不得编造。'),
    'MULTI_GROUP_NATIVE_DOMAIN_REQUIRES_3_TO_64_GROUPS': (
        '/assignment/kind',
        '当前MULTI_GROUP_FIXED_QUOTA合同要求3至64个组。请重新核对原文的设计类型和分组；不能只为通过检查改枚举。'),
    'TWO_GROUP_DESIGN_REQUIRES_TWO_GROUPS': (
        '/assignment/groups', 'TWO_GROUP_FIXED_QUOTA合同要求恰好两个组，须与原文相符。'),
    'COMPLETE_DISJOINT_DESIGN_PARTITION_REQUIRED': (
        '/assignment', '已填写的分组或簇须完整覆盖研究对象，且不重叠；缺失成员不得编造。'),
    'UNIT_WEIGHTS_COMPLETE_NODE_SCOPE_REQUIRED': (
        '/assignment/unit_weights', '已填写的权重表须覆盖全部study.nodes对象编号；缺失权重不得编造。'),
}


def component_diagnostics(parsed):
    """Bounded, model-independent locations for selected existing checks."""
    from .network_policy_reading import Assignment, Exposure
    if not all(hasattr(parsed, name) for name in ('assignment', 'exposure', 'study')):
        return []
    if not isinstance(parsed.assignment, Assignment) or not isinstance(parsed.exposure, Exposure):
        return []
    study = parsed.study
    if not hasattr(study, 'nodes') or not hasattr(study, 'edges'):
        return []
    try:
        validate_components(parsed.assignment, parsed.exposure, study.nodes, study.edges)
    except (ValueError, TypeError, ArithmeticError) as exc:
        code = str(exc)
        if code in _COMPONENT_DIAGNOSTICS:
            path, rule = _COMPONENT_DIAGNOSTICS[code]
            return [dict(field_path=path, error_code=code, constraint=rule)]
    return []


class ComponentStructureError(ValueError):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        super().__init__('FACT_COMPONENT_STRUCTURE_INVALID')


def check_component_structure(parsed):
    diagnostics = component_diagnostics(parsed)
    if diagnostics:
        raise ComponentStructureError(diagnostics)


def _neighbors_of(node, edges):
    return {edge[1] if edge[0] == node else edge[0]
            for edge in edges if node in edge}


def _validate_weighted_coordinate(exposure, neighbors, value):
    try:
        parsed = Fraction(value)
    except (TypeError, ValueError, ZeroDivisionError):
        raise ValueError('EXPOSURE_COORDINATE_OUTSIDE_DECLARED_MAPPING')
    if parsed < 0:
        raise ValueError('EXPOSURE_COORDINATE_OUTSIDE_DECLARED_MAPPING')
    weights = exposure.weights or {}
    total = sum((Fraction(weights.get(n, '0')) for n in neighbors), Fraction(0))
    if exposure.mode == 'proportion':
        if total == 0 or parsed > 1:
            raise ValueError('EXPOSURE_COORDINATE_OUTSIDE_DECLARED_MAPPING')
    elif parsed > total:
        raise ValueError('EXPOSURE_COORDINATE_OUTSIDE_DECLARED_MAPPING')


def _validate_grouped_coordinate(exposure, neighbors, value):
    import json
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        raise ValueError('EXPOSURE_COORDINATE_OUTSIDE_DECLARED_MAPPING')
    groups = exposure.groups or {}
    labels = sorted(groups)
    if (not isinstance(parsed, list) or len(parsed) != len(labels)
            or any(type(c) is not int or isinstance(c, bool) or c < 0 for c in parsed)):
        raise ValueError('EXPOSURE_COORDINATE_OUTSIDE_DECLARED_MAPPING')
    for label, count in zip(labels, parsed):
        if count > len(set(groups[label]) & neighbors):
            raise ValueError('EXPOSURE_COORDINATE_OUTSIDE_DECLARED_MAPPING')


def validate_exposure_coordinate(exposure, node, value, edges):
    """Coordinate legality only, never assignment support or sufficiency."""
    if exposure.kind not in EXPOSURE_GROUPS:
        return
    neighbors = _neighbors_of(node, edges)
    if exposure.kind == 'WEIGHTED_EXPOSURE':
        _validate_weighted_coordinate(exposure, neighbors, value)
        return
    if exposure.kind == 'GROUPED_EXPOSURE':
        _validate_grouped_coordinate(exposure, neighbors, value)
        return
    degree = len(neighbors)
    if value < 0 or (exposure.kind == 'EXACT_TREATED_NEIGHBOR_COUNT' and value > degree):
        raise ValueError('EXPOSURE_COORDINATE_OUTSIDE_DECLARED_MAPPING')
    if exposure.kind == 'THREE_LEVEL_TREATED_NEIGHBOR_FRACTION':
        if degree == 0 or value not in (0,1,2):
            raise ValueError('EXPOSURE_COORDINATE_OUTSIDE_DECLARED_MAPPING')
    elif exposure.kind != 'EXACT_TREATED_NEIGHBOR_COUNT' and value not in (0,1):
        raise ValueError('EXPOSURE_COORDINATE_OUTSIDE_DECLARED_MAPPING')
