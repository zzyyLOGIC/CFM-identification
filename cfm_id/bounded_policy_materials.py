"""Bind finite mean-box materials to the existing solver, without using saved answers."""
import re
from fractions import Fraction
from .network_grounded_contrast import source_lines
from .source_declarations import stance
from .network_protocol_terms import NUM, integer, treated_neighbor_majority

NUMBER = r'-?(?:\d+/\d+|\d*\.\d+|\d+)'


def equal_weight_question(question):
    unequal = r'不等权|非等权|不(?:尽)?相同|不一样|不均等|不相等|不等重|并非|不是|并不|权重不同|加权偏重'
    equal = r'同等权重|等权|同样权重|权重(?:均)?相同|(?:所占)?(?:的)?份额(?:都|均)?(?:一样|相同|相等)'
    return bool(re.search(equal, question) and not re.search(unequal, question))


def read(case, *, expanded=False):
    q = case['business_question']
    action = r'都用|全部(?:推广|启用|使用)|全体启用|全开' + (r'|都(?:使用|启用)' if expanded else '')
    request = r'范围|上下界|区间|锐界' + (r'|能否.{0,12}唯一确定|能否点识别' if expanded else '')
    if (not re.search(action, q)
            or not re.search(request, q)
            or not (equal_weight_question(q) if expanded else re.search(r'同等权重|等权|同样权重', q))
            or re.search(r'相比|相对|减去|差值|第二问|仅评|只看', q)):
        return None
    if expanded and re.search(r'只评|仅看|仅限|只对|仅对|除.{1,15}(?:外|以外)|其中|分别|子集|另一|下周|下月|按.{1,15}加权|权重(?:为|分别)', q):
        return None
    source_rows = source_lines(case)
    rows = [r for r in source_rows if r['source_id'] != 'question']
    used, issues, remainders = set(), [], []

    def take(pattern, label, *, proposed=False, signed=True):
        matches = [(r, m) for r in rows for m in re.finditer(pattern, r['quote'])]
        if len(matches) != 1:
            issues.append(label)
            return None, None
        row, match = matches[0]
        value = row['quote'].replace('拟采用', '采用') if proposed else row['quote']
        prefix = value[:match.start()]
        if stance(prefix) != 'ADOPTED' or signed and stance(value) != 'ADOPTED':
            issues.append(label)
        used.add((row['source_id'], row['quote']))
        if row['quote'][match.end():].strip(' ，,：:'):
            remainders.append(row)
        return row, match

    roster, m = take(r'(?:名单|名册)(?:为|是|[：:])([^。]+)$', '完整对象名单', signed=False)
    if not m:
        return None
    nodes = [s.strip() for s in re.split('[、，,]', m[1])]
    from .bounded_policy_contract import MAX_N
    if not 1 <= len(nodes) <= MAX_N or len(nodes) != len(set(nodes)):
        return None
    text = '。'.join(r['quote'] for r in rows)
    counts = re.findall(r'(?:本周有|共有|全部)(\d+)(?:个|家)?', text)
    if any(int(n) != len(nodes) for n in counts):
        issues.append('名单数量与文字说明不一致')
    _, m = take(r'(?:每个|各)(?:网点|站点|单位|对象|节点|门店)(.+?)记1[、，,](?:不使用|未使用|不启用|未启用)记0', '处理的0/1含义', signed=False)
    treatment = m[1] if m else None
    _, m = take(r'结果是(.+?)[，,](.+?)记1[、，,](.+?)记0', '本次结果及0/1编码', signed=False)
    outcome = m[1] if m else None
    periods = re.findall(r'本周|本月|本季度|本年度|当日|当班|试点周', outcome or '')
    if len(set(periods)) != 1:
        issues.append('结果对应的时期')
    # Bind the query itself as well as the attachments. A different period,
    # outcome or explicit policy population cannot silently reuse these bounds.
    outcome_words = re.sub(r'^(?:本周|本月|本季度|本年度|当日|当班|试点周)(?:任务)?(?:是否)?', '', outcome or '')
    if not outcome_words or outcome_words not in q:
        issues.append('问题与附件是否关注同一个结果')
    query_periods = set(re.findall(r'本周|下周|本月|下月|本季度|下季度|本年度|当日|次日|当班|试点周', q))
    if query_periods and query_periods != set(periods):
        issues.append('问题与附件的结果时期不同')
    size_context = r'都用|同等权重|同样权重|等权' + (r'|都使用|都启用|在平均数中' if expanded else '')
    sizes = re.findall('('+NUM+r')(?:个|家)?(?:网点|站点|门店)?(?:'+size_context+')', q)
    if any(integer(size) != len(nodes) for size in sizes):
        issues.append('问题中的评价人数与附件名单不同')
    graph, m = take(r'完整边为(.+?)[，,]没有其他边$', '处理前固定的完整无向关系表', signed=False)
    edges = []
    if m:
        if not re.search(r'固定.*处理前.*无向|处理前.*固定.*无向', graph['quote']):
            issues.append('网络是否在处理前固定')
        for item in m[1].split('、'):
            pair = re.split('[—–-]', item)
            if len(pair) != 2 or len(set(pair)) != 2 or not set(pair) <= set(nodes):
                issues.append('关系表中的对象编号')
            edges.append(pair)
        if len({frozenset(e) for e in edges}) != len(edges):
            issues.append('关系表有重复边')
    _, m = take(r'(?:每轮|每次)均匀随机抽取恰好(\d+)个(?:网点|站点|单位|对象|节点|门店)' + re.escape(treatment or ''), '实际采用的固定名额随机规则')
    quota = int(m[1]) if m else None
    take(r'所有同人数名单等概率', '同人数名单是否等概率')
    if quota is None or not 0 < quota <= len(nodes):
        issues.append('合法的试点名额')
    exposure_definition = r'(?:同伴暴露|同伴状态|暴露)定义为'
    exposure, _ = take(exposure_definition + r'.+', '同伴状态的定义', signed=False)
    definitions = [r for r in source_rows if r['source_id'] == 'question'
                   and re.search(exposure_definition, r['quote'])]
    if exposure:
        definitions.append(exposure)
    unsupported_exposure = []
    if treatment:
        for row in definitions:
            if treated_neighbor_majority(row['quote'], treatment, require_otherwise_zero=True):
                continue
            if stance(row['quote']) == 'UNDECIDED':
                issues.append('本次实际采用的同伴暴露定义')
            else:
                unsupported_exposure.append(row)
    take(r'平票为0[，,]孤立节点为0', '平票及无邻居时的归类')
    conditions = []
    for code, label, pattern in (
        ('full_vector_randomization', '完整分配不依赖潜在结果', r'完整处理向量与.+?潜在结果独立'),
        ('consistency', '观测结果对应实际完整安排', r'一致性.+?观察结果等于实际安排下的潜在结果'),
        ('finite_conditional_first_moments', '所用平均结果有限', r'所需条件一阶矩有限'),
        ('signature', '同一对象的均值仅依赖本人处理和同伴状态', r'全部.+?所有完整二元安排.+?潜在结果均值只依赖自身处理与上述同伴暴露'),
    ):
        row, _ = take(pattern, label, proposed=True)
        if row:
            conditions.append(dict(code=code, label=label, **row))
    information, _ = take(r'总体信息只有以上逐项列出的精确总体均值[，,]不包含完整联合分布、其他总体信息或额外聚合均值',
                          '是否只有已列出的总体均值', signed=False)
    closure, _ = take(r'除前述.+?外[，,]没有跨对象、跨情境的额外耦合限制', '是否还有联结不同均值的额外条件', signed=False)
    box_scope, _ = take(r'对每个对象、每一种完整二元安排均成立[，,]限制潜在结果均值', '均值界适用的对象和安排范围', signed=False)
    take(r'以下是本题声明可用的精确总体条件均值[，,]不是有限样本估计[：:]', '均值是总体信息还是样本估计', signed=False)
    values, bounds = [], []
    for row in rows:
        m = re.fullmatch(r'([^，,]+)[，,]自身处理=([01])、同伴暴露=([01])时[，,](.+?)的总体条件均值=('+NUMBER+r')', row['quote'])
        if m:
            if m[1] not in nodes or not periods or periods[0] not in m[4] or outcome_words not in m[4]:
                issues.append('总体均值的对象或时期')
            values.append(dict(node=m[1], own=int(m[2]), exposure=int(m[3]), value=str(Fraction(m[5]))))
            used.add((row['source_id'], row['quote']))
        m = re.fullmatch(r'(.+?)的下界为('+NUMBER+r')[，,]上界为('+NUMBER+r')', row['quote'])
        if m:
            bounds.append(dict(node=m[1], lower=str(Fraction(m[2])), upper=str(Fraction(m[3]))))
            used.add((row['source_id'], row['quote']))
    if not values or len({(v['node'],v['own'],v['exposure']) for v in values}) != len(values):
        issues.append('逐项给定的总体均值')
    if len(bounds) != len(nodes) or {v['node'] for v in bounds} != set(nodes):
        issues.append('每个对象的上下界')
    # Every model statement must be consumed. A declaration that the list is closed
    # cannot override a new equality, a contradiction, or an unrecognized amendment.
    unhandled = [r for r in rows if (r['source_id'],r['quote']) not in used
                 and not re.fullmatch(r'(?:研究明确采用[：:])?已知上述完整分配律|处理前固定网络|界限与上文研究背景相同|'
                                      r'结果定义为.+|单位为0/1指标[，,]期间为.+', r['quote'])]
    unhandled += remainders
    unhandled += [r for r in rows if re.search(r'额外假|另(?:外|行)(?:假定|假设|要求)|同时要求|还要求|还假定', r['quote'])]
    if re.search(r'额外假|另(?:外|行)(?:假定|假设|要求)|同时要求|还要求|还假定', q):
        unhandled.append(dict(source_id='question',quote=q))
    if unsupported_exposure:
        return dict(blocked=True, questions=[], status='NOT_COVERED', evidence=unsupported_exposure + unhandled,
                    reason='本路线按直接邻居中处理取值为 1 的比例严格过半来求界。当前无法用这条路线核验原文的暴露定义：'
                           + '；'.join(r['quote'] for r in unsupported_exposure + unhandled))
    if unhandled:
        return dict(blocked=True, questions=[], reason='以下补充说明尚不能纳入本次求界，不能直接略去：'+'；'.join(r['quote'] for r in unhandled),
                    evidence=unhandled, status='NOT_COVERED')
    if issues:
        return dict(blocked=True, questions=['请核对：'+'；'.join(dict.fromkeys(issues))+'。不知道或不采用可以直接注明。'],
                    reason='现有材料尚未满足这条求界路线的输入要求。', evidence=rows, status='NEEDS_INPUT')
    conditions += [dict(code='box',label='所列全安排均值界',**box_scope),
                   dict(code='complete_information',label='已列均值是全部可用总体信息',**information),
                   dict(code='no_additional_constraints',label='没有未交接的额外均值限制',**closure)]
    return dict(operator='BOUNDED_SIGNATURE_MEAN',nodes=nodes,edges=edges,quota=quota,treatment=treatment,
                outcome=outcome,period=periods[0],policy_period=None,values=values,bounds=bounds,
                bounds_kind='CONDITIONAL_MEAN',graph=graph,information=information,conditions=conditions,
                facts=[dict(label='输入原文',**r) for r in rows],protocol='\n'.join(s['text'] for s in case['sources']))
