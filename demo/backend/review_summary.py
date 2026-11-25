"""Presentation only: summarize current evidence without granting any review."""
from .note_review import released_for_plan
from cfm_id.method_compat import canonical_id


def value(item):
    if isinstance(item, dict):
        return item.get('value') or item.get('reason') or '未明确'
    return item if isinstance(item, str) and item != 'UNKNOWN' else '未明确'


def supported_facts(facts):
    return (facts.get('version') == 'network-randomized-effect-reading-1' or
        (facts.get('version') == 'network-source-selections-1' and
         facts.get('target',{}).get('kind') == 'FIXED_POLICY_MEAN') or
        (facts.get('version') == 'network-policy-contrast-reading-1' and
         facts.get('target',{}).get('kind') == 'FIXED_POLICY_MEAN_DIFFERENCE'))


def supported_method(facts, method):
    method = canonical_id(method)
    return ((facts.get('version') == 'network-randomized-effect-reading-1' and method == 'network.randomized.local_contrast') or
        (facts.get('version') == 'network-source-selections-1' and
         facts.get('target',{}).get('kind') == 'FIXED_POLICY_MEAN' and method == 'network.randomized.full_policy_mean') or
        (facts.get('version') == 'network-policy-contrast-reading-1' and
         facts.get('target',{}).get('kind') == 'FIXED_POLICY_MEAN_DIFFERENCE' and method == 'network.randomized.full_policy_contrast'))


def policy_text(policy):
    groups=[(level,[str(n) for n,v in policy.items() if v==level]) for level in (1,0)]
    return '；'.join(('、'.join(nodes) if len(policy)<=6 else str(len(nodes))+' 个对象')+
        ('接受处理' if level else '不接受处理') for level,nodes in groups if nodes)


def peer_text(kind, state):
    if kind == 'THREE_LEVEL_TREATED_NEIGHBOR_FRACTION':
        return {0:'启用的邻居不足三分之一',1:'启用的邻居至少三分之一且不足三分之二',2:'启用的邻居至少三分之二'}.get(state,'同伴状态待明确')
    if kind == 'PRETREATMENT_CORE_COLLABORATOR_MAJORITY':
        return {0:'预先指定的核心伙伴中至多一半启用',1:'预先指定的核心伙伴中超过一半启用'}.get(state,'同伴状态待明确')
    if kind == 'STRICT_MAJORITY_TIES_LOW':
        return {0:'相邻对象中至多一半接受处理',1:'相邻对象中超过一半接受处理'}.get(state,'同伴状态待明确')
    if kind == 'ANY_TREATED_NEIGHBOR':
        return {0:'没有相邻对象接受处理',1:'至少一名相邻对象接受处理'}.get(state,'同伴状态待明确')
    if kind == 'EXACT_TREATED_NEIGHBOR_COUNT': return f'恰好 {state} 名相邻对象接受处理'
    return '同伴状态 '+str(state)


def summarize(run):
    from .capabilities import science_summary
    current=science_summary(run)
    if current is not None:return current
    if run.review_kind is None:
        return dict(cards=[dict(title='本次问题',lines=['以本次结果中的目标为准。']),
            dict(title='采用条件',lines=['已执行的审核记录与证书保留在本次结果中。']),
            dict(title='当前状态',lines=['没有待确认的审核表。'])],
            compact_confirmation_available=False,needs_individual_attention=[],is_approval=False)
    query = next((q for q in run.queries if q['query_id'] == run.query_id), {})
    semantics = query.get('semantics', {})
    facts = (run.submission or {}).get('candidate') or {}
    if not isinstance(facts, dict): facts = {}
    target = facts.get('target', {})
    comparison = value(query.get('business_goal'))
    policy=target.get('assignment')
    if target.get('kind')=='FIXED_POLICY_MEAN' and isinstance(policy,dict) and policy:
        comparison=policy_text(policy)
    contrast=target.get('kind')=='FIXED_POLICY_MEAN_DIFFERENCE'
    if contrast and all(isinstance(target.get(k,{}).get('assignment'),dict) for k in ('first','second')):
        comparison='第一方案：'+policy_text(target['first']['assignment'])+'；减去第二方案：'+policy_text(target['second']['assignment'])
    if target.get('first') and target.get('second'):
        def arm(end):
            if not isinstance(end, dict): return str(end)
            own = {0: '本人不接受处理', 1: '本人接受处理'}.get(end.get('own'), '本人状态待明确')
            peer = peer_text(facts.get('exposure', {}).get('kind'),end.get('exposure','待明确'))
            return own + '、' + peer
        if all(isinstance(target[k], dict) and 'own' in target[k] for k in ('first','second')):
            comparison = arm(target['first']) + '，减去' + arm(target['second'])
    population = target.get('first',{}).get('population') if contrast else target.get('population')
    scope = (f'{len(population)} 个评价对象' if isinstance(population, list)
             else value(semantics.get('target_population')))
    aggregation = '等权平均' if (target.get('first',{}) if contrast else target).get('aggregation') == 'EQUAL_MEAN' else value(semantics.get('aggregation'))
    outcome = facts.get('study', {}).get('outcome') or value(semantics.get('outcome'))
    conditions = []
    assignment = facts.get('assignment', {})
    if assignment.get('kind') == 'INDEPENDENT_BERNOULLI':
        probabilities = set(map(str, assignment.get('probabilities', {}).values()))
        conditions.append('每个对象独立随机分配' + ('，启用概率为 '+next(iter(probabilities)) if len(probabilities)==1 else '，各对象的概率见方案'))
    elif assignment.get('kind')=='TWO_STAGE_QUOTA_MIXTURE': conditions.append('先随机确定各组名额，再在各组内按名额随机抽取对象')
    elif assignment.get('kind') in ('TWO_GROUP_FIXED_QUOTA','MULTI_GROUP_FIXED_QUOTA'): conditions.append('各组分别按固定名额随机抽取对象')
    elif assignment.get('kind'): conditions.append('按材料中的分配方案：'+assignment['kind'])
    statements = facts.get('scientific_statements', {})
    names = {'assignment_outcome_independence':'完整安排与潜在结果独立',
             'consistency':'实际结果对应实际完整安排', 'finite_conditional_means':'所需平均值存在且有限'}
    pending = []; adopted = []
    for key, item in statements.items():
        status = item.get('status')
        if status == 'PROPOSED': pending.append(names.get(key,key))
        elif status == 'ADOPTED': adopted.append(names.get(key,key))
        else:
            conditions.append(names.get(key,key)+'：'+{'NOT_STATED':'原文未声明','UNDECIDED':'尚未决定','NOT_ADOPTED':'不采用','REJECTED':'不采用','CONFLICTING':'材料存在冲突'}.get(status,'状态待核对'))
    if pending: conditions.append('本次拟采用：'+'；'.join(pending))
    if adopted: conditions.append('原文明确采用：'+'；'.join(adopted))
    stage=(facts.get('first_stage_exclusion') or {}).get('status')
    if assignment.get('kind')=='TWO_STAGE_QUOTA_MIXTURE':
        conditions.append('第一阶段条件：最终完整名单相同时，名额方案本身不再直接影响结果（'+
            {'ADOPTED':'原文采用','PROPOSED':'拟采用'}.get(stage,'尚未明确采用')+'）')
    if facts.get('design_facts',{}).get('network_fixed_before_treatment',{}).get('value') is True:
        conditions.append('使用试点前固定的关系网络')
    if not conditions: conditions=['依据你提供的研究方案；具体科学条件将在事实读取后列出，不在此默认批准。']
    data = (run.attachment_report or {}).get('factual_data')
    data_text = (f"{data['nodes']} 个对象，{data['observed']} 条结果记录，{data['features']} 项特征。"
                 if data else '以材料声明的总体信息及其覆盖范围为准。')
    information = facts.get('information', [])
    # DAG uses one information record; network families use a list.
    information = [information] if isinstance(information, dict) else information
    if any(x.get('availability')=='SYMBOLIC_POPULATION_OPERATOR' for x in information):
        data_text += '识别依据材料另行声明的总体信息；有限记录仅用于估计。'
    elif data: data_text += '有限记录不自动变为已知总体信息。'
    sheets = run.review_templates
    changes=[d for sheet in run.review_sheets.values() for d in sheet.get('changes',{}).values()]
    simple_changes=(run.review_kind=='changes' and 0<len(changes)<=12 and all(
        d['field_path'].startswith(('/additional_restrictions','/unresolved')) or
        '/source_ids' in d['field_path'] for d in changes))
    eligible = (run.review_kind in ('query','source','science','data') or simple_changes) and bool(sheets)
    for sheet in sheets.values():
        if sheet.get('material_decisions') or not sheet.get('decisions'): eligible = False
        for decision in sheet.get('decisions',{}).values():
            if isinstance(decision,dict) and not (simple_changes and 'disposition' in decision) and not all(k in decision for k in ('field_role','value_state','source_coverage')):
                eligible = False
    rejected = list((run.plan or {}).get('rejected_fields', []))
    if contrast and (target.get('operation')!='FIRST_MINUS_SECOND' or
            target.get('first',{}).get('population')!=target.get('second',{}).get('population') or
            target.get('first',{}).get('aggregation')!=target.get('second',{}).get('aggregation') or
            target.get('shared_outcome_and_context',{}).get('value') is not True):
        rejected.append('比较方向、共同评价名单、加权方式或共同结果背景尚未对齐。')
    # Do not hide conditions that this small presentation mapper cannot explain.
    if facts.get('additional_restrictions') or (facts.get('unresolved') and not released_for_plan(run.plan or {})):
        rejected.append('模型标记了额外说明或待解决问题，请先核对这些说明；这不等于业务已被判定缺条件。')
    if run.review_kind in ('source','science','data'):
        if not supported_facts(facts):
            rejected.append('该研究类型暂使用详细审核，避免摘要遗漏必要条件。')
    if run.review_kind == 'science':
        methods = (run.plan or {}).get('methods', [])
        if not methods or any(not supported_method(facts,m['method']) for m in methods):
            rejected.append('本路线的条件需要查看完整说明。')
        for key in names:
            if statements.get(key,{}).get('status') not in ('ADOPTED','PROPOSED'):
                rejected.append(names[key]+'尚未明确采用或拟采用，不能直接确认。')
        if assignment.get('kind')=='TWO_STAGE_QUOTA_MIXTURE' and stage not in ('ADOPTED','PROPOSED'):
            rejected.append('第一阶段名额方案的排除条件尚未明确采用，不能直接确认。')
    if rejected: eligible = False
    if any(x.get('operator')=='ALL_OUTCOMES_TOGETHER_WITH_FULL_ASSIGNMENT' and
           x.get('availability')=='SYMBOLIC_POPULATION_OPERATOR' for x in information):
        data_text+=' 本次声明可用：全体对象的结果与完整使用安排的联合总体分布（符号形式）。'
    return dict(cards=[
        dict(title='要比较什么',lines=[comparison,scope+' · '+str(aggregation),str(outcome)]),
        dict(title='按什么条件计算',lines=conditions),
        dict(title='依据什么信息',lines=[data_text]),
    ], compact_confirmation_available=eligible,
       needs_individual_attention=rejected,
       confirmation_label='确认上述复核变化并继续' if simple_changes else
            '确认采用上述条件并继续' if run.review_kind=='science' else
            '确认数据与问题对应并估计' if run.review_kind=='data' else '与原材料一致，继续',
       is_approval=False)
