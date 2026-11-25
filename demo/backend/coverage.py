"""Public coverage descriptions. Presentation only; never selects or admits a method."""
from .capabilities import inventory


def summary():
    from cfm_id.bounded_policy_contract import MAX_N
    from cfm_id.network_bounded_dispatch import DESIGNS, EXPOSURES
    from cfm_id_llm.network_files import MAX_NODES, MAX_EDGES
    from cfm_id_llm.compact_study import CONDITIONS

    registered = {m['id']: m['label'] for r in inventory() for m in r['methods']}
    groups = [
        ('网络中的直接与同伴效应',
         '比较本人或同伴的参与状态；也可求一个指定状态下的平均结果。其余人的安排按所声明的分配规律平均。',
         ('network.randomized.local_mean', 'network.randomized.local_contrast')),
        ('完整方案的平均结果与差值',
         '说明每个对象在方案中做什么，计算一份方案的平均结果，或两份方案的差。也支持明确列出的有限随机方案。',
         ('network.randomized.full_policy_mean', 'network.randomized.signature_policy_mean', 'network.randomized.full_policy_contrast', 'network.randomized.signature_policy_contrast', 'network.randomized.finite_policy_mean')),
        ('观察性网络问题',
         '处理不是随机分配时，支持已实现的固定背景、共同分层及本人和邻居特征调整。必须另行确认排除混杂的条件。',
         ('network.observational.full_policy_mean', 'network.observational.signature_policy_mean', 'network.observational.observed_law_contrast', 'network.observational.shared_stratum_contrast', 'network.observational.local_covariate_contrast')),
        ('有限网络的上下界 · PARTIAL',
         '一份完整方案的均值、两份方案的均值差。需明确总体信息、结果或均值范围，以及采用的模型条件。可给出界限公式；有总体数值时再代入。',
         ('BOUNDED_POLICY_MEAN_D2_E1', 'BOUNDED_POLICY_MEAN_D2_E4', 'BOUNDED_POLICY_MEAN_FINITE',
          'BOUNDED_POLICY_CONTRAST_D2_E1', 'BOUNDED_POLICY_CONTRAST_D2_E4', 'BOUNDED_POLICY_CONTRAST_FINITE', 'MEAN_ORDER_D2_E1')),
        ('变量因果图 · DAG',
         '支持经典后门、调整和单变量经典前门。这里的图描述变量之间的因果关系，不是人或门店之间的联系。',
         ('DAG_CLASSICAL_BACKDOOR', 'DAG_ADJUSTMENT', 'DAG_CLASSICAL_FRONTDOOR')),
    ]
    shown = {method for _, _, methods in groups for method in methods}
    if shown != registered.keys():
        raise ValueError('WEB_COVERAGE_PRESENTATION_MISMATCH')
    # Wire names also occur in archived evidence. Only project them to text here.
    labels = dict(registered)
    from cfm_id.method_compat import aliases
    labels.update({old: registered[new] for old, new in aliases().items() if new in registered})
    from cfm_id.compact_review import LOCAL_CONTRAST, FULL_POLICY, EXPOSURE_POLICY
    for alias, key in {
        LOCAL_CONTRAST: 'network.randomized.local_contrast', FULL_POLICY: 'network.randomized.full_policy_mean',
        EXPOSURE_POLICY: 'network.randomized.signature_policy_mean',
        'R1a': 'network.randomized.local_contrast', 'R1b': 'network.randomized.full_policy_mean',
        'R2': 'network.randomized.signature_policy_mean', 'R2_MEAN_SUFFICIENCY': 'network.randomized.signature_policy_mean',
        'BACKDOOR': 'DAG_CLASSICAL_BACKDOOR',
    }.items():
        labels[alias] = registered[key]
    labels.update(GENERAL_ID='一般因果图识别（ID 算法）',
                  IV_LATE='二元工具变量下的依从者平均效应',
                  IV_ATE='二元工具变量下总体平均效应的可达界')
    return dict(
        method_labels=labels, condition_labels=dict(CONDITIONS),
        groups=[dict(title=title, description=text, methods=[dict(id=m, label=registered[m]) for m in methods])
                for title, text, methods in groups],
        import_limits=dict(nodes=MAX_NODES, edges=MAX_EDGES),
        finite_partial=dict(max_nodes=MAX_N, extended_design_max_nodes=8,
                            designs=list(DESIGNS), exposures=list(EXPOSURES)),
        notes=[
            '是否适用，仍由本次问题、材料、假设和支持条件决定；列在这里不代表任意输入都能识别。',
            '网络入口主要处理：处理前已知且固定的无向关系、单期二元处理。上传关系表目前不接收方向或边权。',
            '均值顺序界限目前限固定名额、过半分组（D2/E1）和数值总体均值；一般额外等式、混合符号与数值信息尚不支持。',
            '一次读取入口可匹配经典后门、一般图 ID 和二元 IV。完整分阶段入口另接观察性网络与有限均值求界，各方法仍分别核对适用域。',
            '这是研究演示入口；不同路线的审核权限不同。合成示例模式不等于确认真实数据或现实中的假设。',
        ],
    )
