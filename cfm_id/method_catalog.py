"""Read-only method descriptions tied to the existing executable registry.

This module neither selects a theorem nor grants a review. Native conditions and
proof formats remain owned by their contracts. Unknown registrations are errors,
not guessed descriptions or an automatic fallback to another method.
"""
from .method_compat import canonical_id, native_id
from copy import deepcopy

from . import capability_registry as registry
from . import method_definitions


VERIFICATION = {
    'arm': ('逐臂核验与组合重放',
        '检查输入、单臂证明和非零系数；组合重算与单独支持概率核对并存，不称整条链路有第二套独立求解器。'),
    'policy': ('同实现重算＋单独概率检查',
        '由已绑定输入再次调用政策求解实现，并用另一段概率计算核对支持；有限混合另核对分量和权重。'),
    'signature': ('同实现重算',
        '签名方法 replay 再次调用 _solve 并比较完整结果；不据此声称存在独立实现的签名公式证明器。'),
    'observational': ('同实现重算＋单独支持检查',
        '重算已绑定的观察性结果，再执行单独的完整安排／局部支持审计；不把两者合称独立求解。'),
    'box': ('独立有限模型端点核验',
        '验证器核对完整安排、支持、已知均值、目标系数及可达端点；符号路径另查参数域，不声称所有界都使用对偶证书。'),
    'order': ('独立端点与对偶核验',
        '验证可行端点及最优性对偶证据；不可行时检查 Farkas 证据，不重新调用生产端优化器。'),
    'graph': ('独立图准则与公式核验',
        '按对应图准则重新检查路径／调整集和证书中的公式；仍共享输入合同，不验证现实中的图是否正确。'),
    'id': ('图推导／hedge 核验',
        '检查递归 ID 推导或 hedge 见证；另有数值一致性检查。资源耗尽或未产生公式不等于不可识别证明。'),
    'iv': ('精确见证、比值与对偶核验',
        '用有理数核对响应类型见证、LATE 比值、ATE 端点和对偶约束；不相容时核对 Farkas 证据。'),
    'ate': ('原生公式／界限独立核验',
        '原验证器另查条件、公式或完成见证；网页整份报告还会重走适配过程，两种重放不混为一种。'),
}


def _profile(ids, label, science, information, checks, limits, verification, sources):
    return dict(method_ids=ids.split(), label=label, scientific_conditions=science,
                information=information, computable_conditions=checks,
                implementation_limits=limits, verification=verification,
                source_modules=sources.split())


def _population_backend_description(backend):
    """Describe historical registrations without treating them as capabilities.

    This metadata does not enable/disable a backend. Unknown additions remain
    unaudited until their actual supports/solve behavior has been inspected.
    """
    active = {
        'randomized_network_arm_mean_v1', 'network_majority_score_composition_v1',
        'network_majority_design_average_v1', 'randomized_ate_v3',
        'one_arm_ate_support_v2', 'manski_binary_ate_v2',
    }
    retired = {'network_direct_effect_threshold_point_v2',
               'network_policy_value_bernoulli_v1'}
    if backend.is_fallback:
        state, detail = 'STOP_ONLY', '保守停止分支，不提供新的识别公式或界限。'
    elif backend.name in retired:
        state, detail = 'RETIRED', '旧规则已停用：supports 始终为 false，不能计入当前能力。'
    elif backend.name == 'network_direct_effect_sensitivity_bounds_v2':
        state, detail = 'QUARANTINED', '暴露概率比不足以推出所需结果密度比桥接；仅返回未覆盖，不给因果界限。'
    elif backend.name in active:
        state, detail = 'ACTIVE_CANDIDATE', '可参与原生候选选择，仍须通过本题条件、信息与证书核验。'
    else:
        state, detail = 'NOT_AUDITED', '新登记后端尚未核对可执行状态，不据登记推定数学覆盖。'
    return dict(name=backend.name, implementation=_name(type(backend)),
                is_fallback=backend.is_fallback, execution_status=state,
                execution_detail=detail)


# Human-readable summaries, not a second implementation of native admission.
# Route IDs retain their compatibility meaning; endpoint aliases are compositions.
PROFILES = (
    _profile('network.randomized.local_mean network.randomized.local_contrast', '原设计局部均值及效应',
        '完整安排随机化、一致性、处理前固定网络、所需均值有限；D6 另审第一阶段无直接作用。不要求均值暴露充分性。',
        '已知分配律及所需局部状态的总体结果信息。',
        '每个非零项的联合局部状态正支持、信息覆盖、共同研究和系数。',
        '设计、暴露及权限以实际入口为准；外部研究与合成研究的范围不同。', 'arm',
        'pfn_pipeline.identification_batch pfn_pipeline.identification_composition'),
    _profile('network.randomized.full_policy_mean network.randomized.finite_policy_mean network.randomized.full_policy_contrast', '完整政策、有限混合与两政策差',
        '随机化、一致性、处理前固定网络、均值有限；D6 另审第一阶段无直接作用。不要求均值暴露充分性。',
        '已知分配律、目标完整安排的总体结果信息。',
        '每个非零政策分量的完整安排正支持；混合权重／差值方向及共同总体。',
        '有限显式完整政策；两端组合不构成一种新定理，也不能只识别一端。', 'policy',
        'pfn_pipeline.identification_policy_r1b cfm_id.fixed_comparison'),
    _profile('network.randomized.signature_policy_mean network.randomized.signature_policy_contrast', '均值签名政策及两政策差',
        '随机化基础条件，加覆盖全部相关完整安排的均值签名充分性；不能由暴露定义自动推出。',
        '已知分配律及目标节点签名的总体均值。',
        '逐对象目标签名正支持、信息覆盖；两端使用同一研究与科学模型。',
        '当前受支持的签名与设计；不要求完整目标政策本身有正概率。', 'signature',
        'pfn_pipeline.identification_policy_r2 cfm_id.workflows.policy_difference'),
    _profile('network.observational.full_policy_mean network.observational.signature_policy_mean', '固定背景下的观察性政策',
        '完整向量条件交换性、一致性、处理前固定网络、均值有限；签名方法另需全安排均值充分性。',
        '同一固定 W 下的观测总体安排律及条件均值。',
        '完整政策或逐对象目标签名正支持；不以边际支持替代联合支持。',
        '共同读取入口限有限总体表、最多12节点和固定 W；不自动跨 W 平均。', 'observational',
        'pfn_pipeline.identification_observational_r3'),
    _profile('network.observational.observed_law_contrast', '观测律条件平均的局部效应',
        '完整向量条件交换性、一致性、处理前固定网络、均值有限；不要求暴露充分性。',
        '观测总体分配律和对应局部状态均值。',
        '非零局部项正支持、信息与同一 W 的匹配。',
        '按原观测律作条件平均；有限联合律、乘积律和混合律各有专用合同。', 'observational',
        'pfn_pipeline.identification_observational_effects'),
    _profile('network.observational.shared_stratum_contrast', '共同处理前分层调整',
        '一致性、固定网络、均值有限；个体暴露充分性及给定分层变量的局部均值交换性。',
        '分层总体权重、逐层分配与局部结果均值。',
        '每个正权重层的目标局部状态正支持。',
        '有限共同分层，不是任意高维协变量调整。', 'observational',
        'pfn_pipeline.identification_observational_exposure_adjustment'),
    _profile('network.observational.local_covariate_contrast', '节点及邻居特征调整',
        '一致性、固定网络、均值有限；个体暴露充分性及局部协变量条件均值交换性。',
        '总体特征律、给定特征的因子化处理律及节点条件均值。',
        '每个正质量节点特征层的目标局部状态正支持。',
        '指定的二元本人特征与邻居计数合同，不是一般网络混杂消除器。', 'observational',
        'pfn_pipeline.identification_observational_nodewise_adjustment'),
    _profile('BOUNDED_POLICY_MEAN_D2_E1 BOUNDED_POLICY_CONTRAST_D2_E1 '
             'BOUNDED_POLICY_MEAN_D2_E4 BOUNDED_POLICY_CONTRAST_D2_E4 '
             'BOUNDED_POLICY_MEAN_FINITE BOUNDED_POLICY_CONTRAST_FINITE', '有限均值盒政策界限',
        '随机化基础条件、全安排均值充分性及所声明的科学界；模型中没有未纳入的额外耦合限制。',
        '完整信息清单、数值或符号总体均值及界；样本极值不能代替科学界。',
        '有限模型可行性、目标联合系数、端点可达；sharp 只相对于完整声明的模型。',
        '有限 D1–D8/E1–E5；D1–D6最多12节点，D7/D8最多8；旧 E1/count 合同保留。合成研究审核。', 'box',
        'cfm_id.bounded_policy_contract cfm_id.bounded_count_contract cfm_id.bounded_finite_contract '
        'cfm_id.bounded_policy_verify cfm_id.bounded_contrast_verify cfm_id.bounded_count_verify cfm_id.bounded_finite_verify'),
    _profile('MEAN_ORDER_D2_E1', '有均值顺序限制的联合政策差',
        '有限均值模型基础条件，加逐对象明确采用的本人／同伴均值顺序；保留完整限制清单。',
        '数值总体均值、结果界和明确的顺序方向与范围。',
        '共同模型可行性、端点可达、最优性或不可行对偶证据。',
        '当前 D2/E1、最多12对象、数值合同；不能泛化到任意额外不等式。合成研究审核。', 'order',
        'cfm_id.mean_order_contract cfm_id.mean_order_verify'),
    _profile('DAG_CLASSICAL_BACKDOOR DAG_ADJUSTMENT DAG_CLASSICAL_FRONTDOOR', 'DAG 后门、调整集及经典前门',
        '完整因果图与干预语义、对应结构模型、观察总体信息；图的科学正确性由研究者承担。',
        '合同所需的观测联合总体分布及严格支持。',
        '分别检查后门、指定调整集或前门准则；不是用一个准则替代三个。',
        '专用有限二元变量合同；经典前门的目标与中介范围受原合同限制。', 'graph',
        'cfm_id.dag_backdoor_contract cfm_id.dag_adjustment_contract cfm_id.dag_frontdoor_contract '
        'cfm_id.dag_backdoor_verify cfm_id.dag_adjustment_verify cfm_id.dag_frontdoor_verify'),
    _profile('DAG_GENERAL_ID', '一般图 ID',
        '声明的半马尔可夫模型、观测总体律及明确的干预目标。',
        '对应有限离散观测联合律与变量定义。',
        '递归识别推导或不可识别 hedge 见证及其适用条件。',
        '有限离散、单处理合同和资源上限；资源停止不能报告为不可识别。', 'id',
        'cfm_id.dag_id_contract cfm_id.dag_id_verify'),
    _profile('BINARY_IV_LATE_ATE', '二元工具变量 LATE／ATE 界',
        '工具独立性、排除、一致性、无干扰；LATE 另需单调性。',
        '二元完整条件总体概率表。',
        '总体表一致性与响应类型可行性；LATE 另需非零第一阶段，ATE 界无此要求。',
        '二元专用模型、独立科学审核；自由文本核验不自动下发估计查询。', 'iv',
        'cfm_id.iv_route_contract cfm_id.iv_exact_verify'),
    _profile('RANDOMIZED_ATE_V3', '普通随机 ATE',
        '随机化、一致性、无干扰；所用均值存在且有限，有限数值域可提供该依据。',
        '同一人群和时期的实验总体 P(T,Y)。',
        '两种处理均有正概率，目标和结果定义符合原合同。',
        '默认网页限完整声明人群的无条件 1−0 公式；不自动交接估计。', 'ate',
        'pfn_pipeline._internal.identification.legacy_ate_contract pfn_pipeline._internal.identification.verifier'),
    _profile('ONE_ARM_ATE_BOUNDS_V2 ONE_ARM_NO_OUTCOME_RESTRICTION_V2', '只观测一个处理组的 ATE',
        '随机化、一致性、无干扰、均值有限；有界／无有效界结论均不得忽略额外限制。',
        '实验总体 P(T,Y)，完整声明的结果域及信息。',
        '处理概率为0或1；检查闭合模型、结果界和完成见证。',
        '单侧界不保证均值存在；不支持的已采用或待定限制会停止。', 'ate',
        'pfn_pipeline._internal.identification.legacy_ate_contract pfn_pipeline._internal.identification.verifier'),
    _profile('MANSKI_BINARY_ATE_V2', '二元结果的 Manski 界',
        '一致性、无干扰；二元结果保证均值有限。不默认随机化或无混杂。',
        '观测总体 P(T,Y)；T/Y 的0、1均保留在模型域中。',
        '基础完成模型完整，界限和见证一致；额外已采用或待定条件不能被忽略。',
        '不支持任意额外限制；明确不采用的提议不加入模型。默认网页输出公式，不自动估计。', 'ate',
        'pfn_pipeline._internal.identification.legacy_ate_contract pfn_pipeline._internal.identification.verifier'),
)


def _name(function):
    return function.__module__ + '.' + function.__qualname__


def _native_conditions():
    from pfn_pipeline.identification_assumption_inventory import (
        implemented_assumption_catalog_v27, requirements_for_route_v27, legacy_ate_condition_catalog)
    from pfn_pipeline.identification_observational_exposure_adjustment import requirements_for_exposure_adjustment_v27p2
    from pfn_pipeline.identification_observational_nodewise_adjustment import requirements_for_nodewise_adjustment_v28
    conditions = {route: requirements_for_route_v27(route)
                  for route in implemented_assumption_catalog_v27()['route_ids']}
    conditions[native_id('network.observational.shared_stratum_contrast')] = requirements_for_exposure_adjustment_v27p2()
    conditions[native_id('network.observational.local_covariate_contrast')] = requirements_for_nodewise_adjustment_v28()
    legacy = legacy_ate_condition_catalog()
    for ids, rule in legacy['rules'].items():
        for route in ids.split(' / '):
            conditions[route] = dict(rule=rule, mean_existence=legacy['mean_existence'],
                closed_model=legacy['closed_model'] if rule.get('closed_model_required') else None,
                checks=legacy['checks'])
    return conditions


def homepage_entries():
    """Special adapters are not common-business readers or new research routes."""
    from . import population_ate_entry as ate
    from . import network_existing_entry as policy, observational_effect_entry as observed
    from . import iv_natural_entry as iv, dag_single_source_entry as single, joint_natural_entry as shared
    entries = [dict(entry_id='POPULATION_ATE_HOMEPAGE',
        method_ids=['RANDOMIZED_ATE_V3', 'ONE_ARM_ATE_BOUNDS_V2',
                    'ONE_ARM_NO_OUTCOME_RESTRICTION_V2', 'MANSKI_BINARY_ATE_V2'],
        prepare=_name(ate.prepare), complete=_name(ate.complete), replay=_name(ate.replay),
        scope='默认网页显式启用；完整声明人群的无条件1−0，来源审核与科学确认仍必需。公共调用历史默认不变。',
        common_business_reader=False, estimation_handoff_allowed=False)]
    def source_entry(entry_id, ids, prepare, complete, scope, handoff):
        return dict(entry_id=entry_id, method_ids=ids.split(), prepare=_name(prepare),
                    complete=_name(complete), replay=_name(shared.replay), scope=scope,
                    common_business_reader=False, estimation_handoff_allowed=True,
                    handoff_scope=handoff, estimator_execution=False)
    entries += [
        source_entry('RANDOMIZED_POLICY_SOURCE',
            'network.randomized.full_policy_mean network.randomized.finite_policy_mean '
            'network.randomized.full_policy_contrast network.randomized.signature_policy_mean '
            'network.randomized.signature_policy_contrast',policy.prepare,policy.complete,
            '来源审核后的固定完整政策、有限混合及两端差；签名资料保留实际格子及独立的均值充分性许可。原设计、暴露、支持与信息限制不变。',
            '按原完整安排或本人/同伴状态登记条件均值查询；未自动运行样本估计器。'),
        source_entry('OBSERVATIONAL_POLICY_SOURCE',
            'network.observational.full_policy_mean network.observational.signature_policy_mean',policy.prepare,policy.complete,
            '同一固定背景的有限观察性政策及组合；所需交换性、充分性和完整信息仍按原合同审核。',
            '认证目标的总体均值查询；界限分支另保留原模型与适用范围。'),
        source_entry('OBSERVATIONAL_EFFECT_SOURCE',
            'network.observational.observed_law_contrast network.observational.shared_stratum_contrast '
            'network.observational.local_covariate_contrast',observed.prepare,observed.complete,
            '原三种平均方式与六种有限资料合同；不将条件或平均权重互换。',
            '逐项保留原平均方式、条件坐标和系数的总体均值查询。'),
        source_entry('BINARY_IV_SOURCE','BINARY_IV_LATE_ATE',iv.prepare,iv.complete,
            '二元工具、处理、结果与八格精确总体条件概率；来源核对和显式科学确认后调用原IV方法。',
            '只登记认证公式/数值/界限，零样本估计查询；不是已接通IV样本估计器。'),
        source_entry('DAG_SINGLE_SOURCE','DAG_GENERAL_ID',shared.prepare,single.complete,
            '一个处理、一个结果的无条件干预分布；保留原一般ID读取声明、图范围、完整观测总体律和严格正性。',
            'POINT登记观测联合分布与认证函数；不可识别见证不发送估计查询。'),
    ]
    return entries


def catalog():
    """Return fresh JSON metadata. No solver, LLM, review or routing is run."""
    from . import dag_id_route
    from pfn_pipeline._internal.identification.identification import IdentificationEngine
    rows = {}
    for profile in PROFILES:
        for method in profile['method_ids']:
            if method in rows:
                raise ValueError('DUPLICATE_METHOD_DESCRIPTION:' + method)
            item = deepcopy(profile)
            item.pop('method_ids')
            label, detail = VERIFICATION[item.pop('verification')]
            rows[method] = dict(method_id=method, **item,
                **method_definitions.describe_binding(method),
                verification=dict(label=label, detail=detail), common_business_entries=[],
                research_entries=[], homepage_entries=[], native_route_ids=[], producers=[], replayers=[])

    def get(method):
        if method not in rows:
            raise ValueError('UNDOCUMENTED_REGISTERED_METHOD:' + method)
        return rows[method]

    for binding in registry.business_bindings():
        for method in binding.methods:
            row = get(method.method_id)
            row['common_business_entries'].append(dict(reader_id=binding.reader_id,
                inspect=_name(binding.inspect), execute=_name(binding.execute)))
            row['native_route_ids'] = list(method.native_route_ids)
            row['producers'].extend(_name(f) for f in method.producers)
            row['replayers'].extend(_name(f) for f in method.replayers)
    for registration in registry.registrations():
        row = get(registration.capability.route_id)
        row['research_entries'].append(registration.describe())
        row['producers'].append(_name(registration.adapter_type.submit))
        row['replayers'].append(_name(registration.adapter_type.replay))
    general = get(dag_id_route.ROUTE)
    general['research_entries'].append(dict(route_id=dag_id_route.ROUTE, entry=dag_id_route.__name__))
    general['producers'].append(_name(dag_id_route.submit))
    general['replayers'].append(_name(dag_id_route.DagGeneralIdRoute.replay))
    for entry in homepage_entries():
        for method in entry['method_ids']:
            get(method)['homepage_entries'].append(deepcopy(entry))
    native_conditions = _native_conditions()
    for row in rows.values():
        if not row['native_route_ids']:
            row['native_route_ids'] = [native_id(row['method_id'])]
        row['declared_native_conditions'] = {route: deepcopy(native_conditions[route])
            for route in row['native_route_ids'] if route in native_conditions}
        row['producers'] = sorted(set(row['producers']))
        row['replayers'] = sorted(set(row['replayers']))
        if not (row['common_business_entries'] or row['research_entries'] or row['homepage_entries']):
            raise ValueError('DESCRIPTION_WITHOUT_ENTRY:' + row['method_id'])
    # Historical population backends are indexed separately, not promoted to new
    # theorem families. Constructing the engine only reads its fixed registration.
    native_backends = [_population_backend_description(b) for b in IdentificationEngine().backends]
    from .dedicated_entries import inventory as dedicated_inventory
    return dict(version='method-description-2', methods=list(rows.values()),
        definitions=method_definitions.definitions(),
        dedicated_entries=dedicated_inventory(),
        population_backend_index=native_backends, descriptive_only=True,
        creates_reviews=False, registration_is_applicability=False, automatic_fallback=False,
        scientific_validity_certified_by_software=False,
        scope='维护中的共同读取、研究及普通ATE首页方法；历史population后端单列，不承诺每个后端均可由自由文本到达。')


def describe(method_id):
    method_id = canonical_id(method_id)
    for row in catalog()['methods']:
        if row['method_id'] == method_id:
            return row
    raise ValueError('UNKNOWN_METHOD_DESCRIPTION:' + str(method_id))


def render_markdown():
    data = catalog()
    lines = ['# 方法条件、实际入口与验证方式', '',
        '本表由 cfm_id.method_catalog 从实际能力登记及原生条件目录生成。只作维护说明，不参与方法分派、科学批准或数学判定。', '',
        '六项研究属性共同描述问题；方法可以同时适用。现用网络方法使用可读标识，不从编号或名称前缀决定适用性。旧证书及原生接口标识仅由 method_compat 转换比较，证书本身不改写。D/E 参数与数学支持范围不变。', '',
        '## 基础方法、操作与实现', '',
        '基础方法描述识别依据；差值和有限混合是操作；设计特例与求解版本是实现。下表登记已有能力，不自动开放新组合。二元 IV 的两个目标共用实现但分别保留原生条件，单臂 ATE 的不同结果域也保留原合同。', '',
        '| 基础方法 | 名称 | 识别依据（概要，完整条件见下文） |',
        '| --- | --- | --- |']
    for d in data['definitions']:
        lines.append('| ' + ' | '.join([d['id'], d['name'], d['identification_basis']]) + ' |')
    lines += ['', '| 执行标识 | 基础方法 | 目标操作 | 实现 |', '| --- | --- | --- | --- |']
    for row in data['methods']:
        lines.append('| ' + ' | '.join([row['method_id'], '<br>'.join(row['definition_ids']), row['operation'], row['implementation']]) + ' |')
    lines += ['',
        '## 条件与实现限制', '',
        '科学条件是否符合现实仍由研究者判断；程序核对材料、采用状态及条件下的数学结论。支持概率、图准则和可行性由程序计算，不能靠勾选代替。', '',
        '| 方法（当前执行标识） | 科学条件 | 已有信息与可计算检查 | 当前实现限制 |',
        '| --- | --- | --- | --- |']
    for p in PROFILES:
        lines.append('| ' + ' | '.join([p['label'] + '<br>' + '<br>'.join(p['method_ids']),
            p['scientific_conditions'], p['information'] + '<br>' + p['computable_conditions'], p['implementation_limits']]) + ' |')
    lines += ['', '## 证据怎样核验', '',
        '以下方式不能混称“完全独立重放”。输入绑定防止错用材料；同实现重算可以查出记录不一致，但可能重复同一实现错误；另写的检查器也不证明现实假设成立。', '',
        '| 方法组 | 实际验证方式 | 检查边界与源码 |', '| --- | --- | --- |']
    for p in PROFILES:
        label, detail = VERIFICATION[p['verification']]
        sources = '<br>'.join('[' + module.rsplit('.', 1)[-1] + '](../' + module.replace('.', '/') + '.py)'
                              for module in p['source_modules'])
        lines.append('| ' + p['label'] + ' | ' + label + ' | ' + detail + '<br>' + sources + ' |')
    lines += ['', '## 实际登记的入口', '',
        '共同业务读取、专用研究入口和默认网页适配是不同入口。专用研究入口存在不等于默认网页已支持任意自然问法；任何入口均不得省略来源审核或科学条件。', '',
        '| 方法 | 共同读取 | 专用研究入口 | 普通 ATE 默认网页适配 |', '| --- | --- | --- | --- |']
    for row in data['methods']:
        common = ', '.join(e['reader_id'] for e in row['common_business_entries']) or '—'
        research = ', '.join(e['route_id'] for e in row['research_entries']) or '—'
        homepage = '已接入；不自动交接估计' if row['homepage_entries'] else '—'
        lines.append('| ' + ' | '.join([row['method_id'], common, research, homepage]) + ' |')
    lines += ['', '## 保留的 population 后端', '',
        '以下列表读取原引擎登记，并单独标出停用、隔离和保守停止分支。登记存在不等于规则可执行；不是新增的同层定理分类，也不是自由文本覆盖承诺。', '',
        '| 后端 | 执行状态 | 说明 |', '| --- | --- | --- |']
    for b in data['population_backend_index']:
        lines.append('| ' + b['name'] + ' | ' + b['execution_status'] + ' | ' + b['execution_detail'] + ' |')
    lines += ['', '## 维护与结论边界', '',
        '- 原 v27 条件接口仍只描述原八条网络路线；完整维护清单使用本表。旧接口输出保持兼容。',
        '- POINT、PARTIAL 需要对应证据通过；PARTIAL 的 sharp 性仅针对完整声明的模型。',
        '- 缺材料、待确认、UNSUPPORTED、资源停止、尚未找到公式及验证失败各保留原原因，均不自动升级为不可识别证明。',
        '- 单独的原生条件字典通过 catalog() 返回；没有现成字典的方法引用各自合同，不在这里复制准入逻辑。',
        '- 图与普通 ATE/Manski 的默认入口核验结论不等于估计交接授权。各入口权限继续由原合同控制。',
        '- 文献及定理含义参见 [条件目录](ASSUMPTION_ROUTE_MATRIX_ZH.md) 和 [六项结构](IDENTIFICATION_STUDY_SPEC_ZH.md)。本次没有新增数学定理。', '',
        '当前逐方法覆盖、文献对应及缺口优先级见 [数学覆盖核对](MATHEMATICAL_COVERAGE_AUDIT_ZH.md)。', '',
        '更新命令：python -m cfm_id.method_catalog --write-doc docs/METHOD_CONDITIONS_AND_VERIFICATION_ZH.md', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-doc', required=True)
    args = parser.parse_args()
    Path(args.write_doc).write_text(render_markdown(), encoding='utf-8')
