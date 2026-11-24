"""Read one closed finite policy problem from original source spans.

An unmatched clause is retained for review. Neither model labels nor example
identifiers supply graph edges, policy coordinates, numbers, or assumptions.
"""
import re
import csv
from io import StringIO
from fractions import Fraction
from .bounded_policy_contract import MAX_N
from .bounded_policy_materials import NUMBER, equal_weight_question
from .network_grounded_contrast import source_lines
from .network_protocol_terms import NUM, integer, named_units, treated_neighbor_majority


class Incomplete(ValueError):
    pass


class Statements:
    def __init__(self, rows):
        self.rows = rows
        self.used = set()

    def all(self, pattern):
        hits = []
        for i, row in enumerate(self.rows):
            m = re.fullmatch(pattern, row['quote'])
            if m:
                self.used.add(i)
                hits.append((row, m))
        return hits

    def one(self, pattern, label):
        matches = self.all(pattern)
        if len(matches) != 1:
            raise Incomplete(label)
        return matches[0]


def group_members(text, nodes):
    exact = named_units(text, nodes)
    if exact:
        return exact
    # A shared noun can be elided (“甲乙一组”). Only unambiguous single-character
    # aliases with the exact same suffix are safe to segment without separators.
    aliases = {n[0]: n for n in nodes}
    if len({n[1:] for n in nodes}) == 1 and len(aliases) == len(nodes) and all(c in aliases for c in text):
        return [aliases[c] for c in text]
    raise Incomplete('分组名单中的完整对象名称')


def allocation(phrase, nodes):
    text = phrase.strip(' “”“”‘’')
    all_state = re.fullmatch(r'(?:('+NUM+r')家?(?:门?店|网点|站点))?(?:全部|全体|都)(不)?(?:启用|使用)', text)
    if all_state:
        if all_state[1] and integer(all_state[1]) != len(nodes):
            raise Incomplete('政策所称全体与原名册的人数')
        return [int(not all_state[2])] * len(nodes)
    named = re.fullmatch(r'(.+?)(?:启用|使用)[，,]其余(?:门?店|网点|站点|对象)不(?:启用|使用)', text)
    members = named_units(named[1], nodes) if named else None
    if not members or len(set(members)) != len(members):
        raise Incomplete('政策对原名册每个对象的安排')
    return [int(n in members) for n in nodes]


def target(question, nodes, period, outcome, unit):
    # Bind the whole objective including direction, population and period. Do not
    # discard an unparsed modifier following a recognizable policy or outcome.
    parts = [s.strip() for s in re.split('[。！？]', question) if s.strip()]
    population = rf'(?:{NUM}家?(?:门?店|网点|站点)|每家|各{unit})'
    if len(parts) < 2:
        raise Incomplete('评价对象及各自权重')
    weight = rf'(?:{population}(?:等权|权重相同|在平均数中所占的份额一样))'
    declaration = parts.pop()
    explicit = re.fullmatch(r'(?:两端共用的|评价|各对象的)权重(?:分别)?[为是：:](.+?)(?:，采用附件研究条件)?', declaration)
    if explicit:
        weights = {}
        for field in re.split('[、，,]',explicit[1]):
            pair = re.fullmatch(r'(.+?)[=:：]('+NUMBER+')',field.strip())
            if not pair or pair[1] not in nodes or pair[1] in weights:
                raise Incomplete('按原名册逐一给出各对象的权重')
            weights[pair[1]] = Fraction(pair[2])
        if set(weights)!=set(nodes) or min(weights.values())<0 or sum(weights.values())!=1:
            raise Incomplete('每个对象的非负权重及合计为一')
    elif equal_weight_question(declaration) and re.fullmatch(rf'(?:两种方案都评价刚才列出的同一批{unit}[，,])?{weight}(?:[，,]采用附件研究条件)?', declaration):
        weights = dict.fromkeys(nodes, Fraction(1,len(nodes)))
    else:
        raise Incomplete('评价人群及其在两端共用的权重')
    weights = [str(weights[n]) for n in nodes]
    for n in re.findall(r'('+NUM+r')家?(?:门?店|网点|站点)', question):
        if integer(n) != len(nodes):
            raise Incomplete('问题与名单的对象数')
    if len(parts) == 2 and re.fullmatch(rf'我们{NUM}家{unit}考虑换一种[^，,。]+的推广安排', parts[0]):
        parts.pop(0)
    if len(parts) != 1:
        raise Incomplete('单一政策目标及比较方向')
    metric = re.sub(r'^是否(?:每天)?', '', outcome)
    body = re.sub(rf'^(?:{NUM}(?:门?店|站点|网点){re.escape(period)}[，,]|如果)', '', parts[0])
    endpoint, separator, result = body.rpartition('，平均')
    if not separator:
        endpoint, separator, result = body.partition('，在')
        prefix = re.match(r'(?:同一个|同一)(.+?)[，,](.+?)的平均', result)
        focal=named_units(prefix[2],nodes) if prefix else None
        if not prefix or '同一'+prefix[1] != period or not focal or sorted(focal)!=sorted(nodes):
            raise Incomplete('结果期间和明确列出的评价对象')
        result = result[prefix.end():]
    if not result.startswith(metric):
        raise Incomplete('问题的结果指标与研究说明是否一致')
    kind = result[len(metric):]
    contrast = re.fullmatch(r'从(.+?)(?:改为|改成|变为)(.+)', endpoint)
    if contrast and re.fullmatch(r'率?(?:会)?(?:增加|提高|减少|降低)多少', kind):
        first, second = allocation(contrast[2], nodes), allocation(contrast[1], nodes)
        return (second, first, weights) if re.search('减少|降低', kind) else (first, second, weights)
    if not contrast and endpoint.startswith('若') and re.fullmatch(r'率?(?:是多少|的范围是多少)', kind):
        return allocation(endpoint[1:], nodes), None, weights
    raise Incomplete('比较方向或单政策水平')


def matched_upload(case, network):
    from .direct_verification import bound_network
    table = bound_network(case,network)
    clean = {s['source_id']:s for s in case['sources'] if s['source_id'] in ('shared_roster','shared_edges')}
    if table.completeness!='COMPLETE' or table.unused_node_columns:
        raise Incomplete('关系表的完整性及名册附加列的用途')
    if (not re.search(r'(?:处理|分配|抽签)前',table.description) or
        re.search(r'不固定|未固定|尚未|不确定|可能变化|处理后|分配后|抽签后|不是|并非',table.description)):
        raise Incomplete('上传关系是否来自处理前同一时期')
    for key, expected in [('shared_roster',[(n,) for n in table.nodes]),('shared_edges',table.edges)]:
        if key not in clean:
            raise Incomplete('原名册和关系表的逐行记录')
        content=list(csv.reader(StringIO(clean[key]['text'])))
        if not content or len(content[0])!=(1 if key=='shared_roster' else 2):
            raise Incomplete('名册和关系表的列对应')
        actual=list(map(tuple,content[1:]))
        # Original edge columns may be target,source. These edges are undirected.
        if key=='shared_edges':
            actual=[tuple(sorted(e)) for e in actual]
            expected=[tuple(sorted(e)) for e in expected]
        if actual!=list(expected):
            raise Incomplete('逐行关系与导入名册的对应')
    return table


def parse(case, rows, rmatch, table):
    form = Statements(rows)
    roster, match = form.one(rmatch, '完整名册及研究单位')
    nodes = re.split('[、，,]', match[1])
    unit = match[2]
    if not 1 <= len(nodes) <= MAX_N or len(set(nodes)) != len(nodes) or not all(nodes):
        raise Incomplete('有限且无重复的对象名册')
    _, m = form.one(r'((?:启用|使用)[^、，,]+?)记1[、，,]不(?:启用|使用)记0', '实际处理及编码')
    treatment = m[1]
    _, m = form.one(r'结果为(同一[^，,是否]+)(是否[^，,]+)[，,]是记1[、，,]否记0', '同期间二元结果定义')
    period, outcome = m[1], m[2]
    first, second, weights = target(case['business_question'], nodes, period, outcome, unit)
    form.all(r'两端政策比较同一结果定义、单位、期间和研究背景')
    form.all(re.escape(unit)+r'之间存在合作和信息交流，结果可能受相邻店安排影响')
    graphs = form.all(r'(?:网络为)?处理前固定的简单无向(?:网络|合作网)[，,]完整(?:合作边|关系)为([^，,]+)(?:[，,]没有其他边)?')
    if len(graphs)==1:
        graph, m = graphs[0]
        if '没有其他边' not in graph['quote']:
            form.one(r'没有其他边', '关系表是否列全')
        edges = [re.split('[—–-]', edge) for edge in m[1].split('、')]
    elif table is not None and not graphs:
        graph=dict(source_id='uploaded_network',quote=table.source()['text'])
        edges=list(map(list,table.edges))
    else:
        raise Incomplete('处理前固定的完整简单无向网络')
    if table is not None and (set(nodes)!=set(table.nodes) or set(map(frozenset,edges))!=set(map(frozenset,table.edges))):
        raise Incomplete('上传关系表与研究说明中不同的对象或合作边')
    form.all(r'没有列出合作边的店是孤立点|未与任何对象相连的店为孤立点')
    if any(len(e) != 2 or len(set(e)) != 2 or not set(e) <= set(nodes) for e in edges) or len(set(map(frozenset, edges))) != len(edges):
        raise Incomplete('简单无向边与原名册的对应')
    design_row, m = form.one(r'原试点(.+)', '试点分配规则')
    law = m[1]
    quota = re.fullmatch(r'在('+NUM+r')家'+re.escape(unit)+r'中每轮恰好抽取('+NUM+r')家启用(?:AI)?，所有大小为('+NUM+r')的完整名单等概率', law)
    other = re.fullmatch(r'每轮从('+NUM+r')(?:门?店|站点|网点)均匀抽取恰好('+NUM+r')家启用，其余不启用', law)
    grouped = re.fullmatch(r'(.+?)一组、(.+?)一组，每组独立地均匀抽('+NUM+r')家启用', law)
    if quota or other:
        law = quota or other
        if integer(law[1]) != len(nodes) or quota and integer(quota[2]) != integer(quota[3]):
            raise Incomplete('抽取名额和原名册的对应')
        design = dict(kind='complete_randomization_binary_v1', m=integer(law[2]))
        if not 0 <= design['m'] <= len(nodes):
            raise Incomplete('可行的随机名额')
    elif grouped:
        groups = [group_members(grouped[k], nodes) for k in (1, 2)]
        if sorted(groups[0]+groups[1]) != sorted(nodes) or any(integer(grouped[3]) > len(g) for g in groups):
            raise Incomplete('互不重叠且完整的分组及组内名额')
        design = dict(kind='two_group_fixed_quota_binary_v1', groups=groups, treated_quotas=[integer(grouped[3])]*2)
    else:
        raise Incomplete('实际采用的抽签规则')
    exposure, m = form.one(r'(?:同伴暴露按合作邻居定义[：:](.+)|同伴状态直接记录(启用的合作邻居家数)|'
                            r'(合作店启用比例小于1/3记0，至少1/3但小于2/3记1，至少2/3记2))', '同伴暴露的完整定义')
    if m[1]:
        if not treated_neighbor_majority(m[1], treatment, require_otherwise_zero=True):
            raise Incomplete('合作邻居暴露中的处理取值及过半规则')
        form.one(r'平票为0，孤立(?:店|节点|对象)为0', '平票及孤立点的处理')
        grouping = 'strict_majority_ties_low'
    else:
        grouping = 'exact_treated_neighbor_count' if m[2] else 'three_level_treated_neighbor_fraction'
    conditions = []

    def condition(code, label, pattern):
        row, _ = form.one(pattern, label)
        conditions.append(dict(code=code, label=label, **row))
        return row

    condition('known_assignment_law', '完整随机分配律已知', r'(?:本研究明确采用[：:])?上述完整分配律已知')
    condition('full_vector_randomization', '完整分配与全部潜在结果独立', rf'完整处理向量与全部{unit}在所有完整二元安排下的潜在结果独立')
    condition('consistency', '观察结果对应实际完整安排', r'一致性，即观察结果等于实际完整安排下的潜在结果')
    condition('fixed_network', '网络在处理前固定', r'处理前固定网络')
    condition('finite_conditional_first_moments', '条件一阶矩有限', r'所需条件一阶矩有限')
    population = rf'全部(?:{NUM}家)?{unit}'
    signature = condition('signature', '所有安排下的均值只依赖本人处理和同伴状态',
        rf'(?:本研究(?:明确|拟)采用[：:])?对{population}及所有完整二元安排，每(?:店|个对象)潜在结果均值仅依赖自身处理和上述同伴暴露')
    info = condition('population_source', '输入为精确总体均值', r'以下[为是]精确总体条件均值，不是样本估计[：:]|本合成研究提供且只提供以下精确总体均值（不是'+NUM+r'店的一次观测）[：:]')
    bounds_scope = condition('box', '逐对象的均值界适用于所有安排', rf'以下界限限制潜在结果的条件均值，适用于{population}、所有完整二元安排和同一研究背景')
    scope_period = re.escape(period)
    form.one(r'结果定义是(?:该'+re.escape(period.removeprefix('同一'))+'|'+scope_period+')'+re.escape(outcome)+r'，单位为0/1指标，期间为'+scope_period, '界限的结果定义、单位及期间')
    metric = re.escape(re.sub(r'^是否(?:每天)?', '', outcome))
    values = []
    for pat in (r'(.+?)，自身处理=([01])、同伴暴露=(\d+)时，所述'+metric+r'指标的总体条件均值为('+NUMBER+')',
                r'(.+?)自身状态([01])、同伴状态(\d+)，'+metric+r'的总体平均值为('+NUMBER+')'):
        for _, v in form.all(pat):
            values.append(dict(node=v[1], own=int(v[2]), exposure=int(v[3]), value=str(Fraction(v[4]))))
    bounds = [dict(node=v[1], lower=str(Fraction(v[2])), upper=str(Fraction(v[3]))) for _,v in
              form.all(r'(.+?)的均值下界为('+NUMBER+r')，上界为('+NUMBER+')')]
    if (not values or any(v['node'] not in nodes for v in values) or
        len({(v['node'], v['own'], v['exposure']) for v in values}) != len(values) or
        sorted(v['node'] for v in bounds) != sorted(nodes)):
        raise Incomplete('逐对象列出的精确总体单元格及完整上下界')
    condition('complete_information', '所列精确均值是全部可用总体信息',
        r'本研究声明[：:]可用总体信息恰为(?:以上列出|所列)的精确总体均值，没有(?:完整联合分布或)?其他总体信息')
    ordinary = form.all(r'除明确列出的基础科学条件、全安排均值暴露充分性及逐店界限外，没有跨对象或跨安排的额外耦合限制')
    ordered = form.all(r'除基础科学条件、全部安排的均值暴露充分性、逐店界限以及上述明确采用的均值顺序外，没有其他限制')
    if len(ordinary) + len(ordered) != 1:
        raise Incomplete('完整列出的跨对象、跨安排限制')
    closure = (ordinary or ordered)[0][0]
    conditions.append(dict(code='closure', label='完整模型及额外限制', **closure))
    if ordered:
        if second is None or grouping != 'strict_majority_ties_low' or design['kind'] != 'complete_randomization_binary_v1':
            raise Incomplete('均值顺序方法的适用设计、暴露与比较两端')
        form.one(r'本次有均值顺序耦合限制', '是否采用均值顺序')
        form.one(rf'以下科学声明针对{population}、{scope_period}和背景，覆盖所有完整二元安排，包括原试点未出现的安排', '均值顺序适用的研究总体和范围')
        form.one(r'约束的是'+re.escape(outcome)+r'这个0/1数值结果的条件均值，不是每次结果', '顺序针对的结果及均值')
        from .network_mean_order_dispatch import axis_decision
        for axis, change in [('OWN', r'其余门店安排不变，只让本店由不用改为使用工具'),
                             ('PEERS', r'本店及其余门店安排不变，只将任一合作邻居由不用改为使用')]:
            row, _ = form.one(r'本研究(?:拟|明确)采用[：:]'+change+r'，本店的结果均值不会降低', '本人及同伴两个方向各自采用的顺序约束')
            for node in nodes:
                label = '自身处理' if axis == 'OWN' else '单个邻居处理'
                conditions.append(dict(code=axis_decision(node, axis), label=f'{node} · {label}增加时均值不下降', **row))
    extra = [r for i,r in enumerate(rows) if i not in form.used]
    if extra:
        return dict(blocked=True, status='NOT_COVERED', questions=[], evidence=extra,
                    reason='以下原文限制尚未进入可复算的模型。'+'；'.join(r['quote'] for r in extra))
    for row in rows:
        if any(integer(n) != len(nodes) for n in re.findall(r'全部('+NUM+r')家'+re.escape(unit), row['quote'])):
            raise Incomplete('科学条件所覆盖的人数与原名册一致')
    return dict(operator='MEAN_ORDER' if ordered else 'FINITE_MEAN_BOX', nodes=nodes, edges=edges,
                design=design, grouping=grouping, first=first, second=second, weights=weights, period=period, treatment=treatment,
                outcome=outcome, values=values, bounds=bounds, graph=graph, design_source=design_row,
                exposure_source=exposure, information=info, signature_source=signature, bounds_source=bounds_scope,
                conditions=conditions, facts=[dict(label='原文', **r) for r in rows],
                protocol='\n'.join(s['text'] for s in case['sources']))


def read(case, *, network=None):
    rows = [r for r in source_lines(case) if r['source_id'] != 'question']
    roster = r'研究对象(?:只有|为)([^，,]+)[，,]([\w-]{1,30})是研究单位'
    if not any(re.fullmatch(roster, r['quote']) for r in rows) or not any('均值下界' in r['quote'] for r in rows):
        return None
    try:
        table = matched_upload(case,network) if network is not None else None
        prose = [r for r in rows if not table or r['source_id'] not in ('uploaded_network','shared_roster','shared_edges')]
        return parse(case, prose, roster, table)
    except (ValueError, ZeroDivisionError) as exc:
        reason = str(exc) if isinstance(exc, Incomplete) else ('分数的分母须非零' if isinstance(exc,ZeroDivisionError) else '原表引用及字段内容')
        return dict(blocked=True, status='NEEDS_INPUT', questions=['请核实'+reason+'。'],
                    reason='尚需核对'+reason+'。', evidence=rows)


def different_reading(case, draft, m):
    """An explicit contradictory model coordinate cannot authorize a source packet."""
    if m.get('operator')=='BOUNDED_SIGNATURE_MEAN':
        nodes=m['nodes']
        m=dict(m,first=[1]*len(nodes),second=None,weights=[str(Fraction(1,len(nodes)))]*len(nodes),
               design={'m':m['quota']},grouping='strict_majority_ties_low')
    if 'first' not in m:
        return []
    from .network_response import unpack
    normalized, _ = unpack(draft)
    facts = normalized.get('network_facts') if isinstance(normalized,dict) else None
    if not isinstance(facts,dict):
        return ['模型未逐项给出所读网络、暴露、分配及目标']
    texts = {s['source_id']:s['text'] for s in case['sources']}
    texts['question'] = case['business_question']
    differences = []
    def original_quote(ref,key):
        if (not isinstance(ref,dict) or not isinstance(ref.get('source_id'),str)
                or not isinstance(ref.get('quote'),str) or not ref['quote'].strip()):
            return False
        quote=ref['quote'].strip()
        if quote in texts.get(ref.get('source_id'),''):
            return True
        # A saved answer can cite the old equal-weight wording. Accept only a
        # standalone affirmative statement about the same number of units.
        if key!='contrast' or ref.get('source_id')!='question' or len(set(m['weights']))!=1:
            return False
        weights=r'('+NUM+r')(?:家|个)(?:门店|网点|站点|对象)?(?:同等权重|等权|权重相同|在平均数中所占的份额一样)'
        old=re.fullmatch(weights,quote.rstrip('。'))
        now=re.findall(r'(?:^|[。！？])'+weights+r'(?:[。！？]|$)',texts['question'])
        return bool(old and integer(old[1])==len(m['nodes']) and any(integer(n)==len(m['nodes']) for n in now))

    def policy_vector(value,order):
        if isinstance(value,list) or not isinstance(value,str) or not isinstance(order,list):
            return value
        # A verbal all-unit endpoint may omit the switch name or use a name from the question.
        full=re.fullmatch(r'(?:('+NUM+r')(?:家|个)?(?:门店|网点|站点|对象|店)?|(?:所有|全部|全体)(?:门店|网点|站点|对象|店)?)'
                          r'(?:都|均|全部)?(不)?(?:启用|使用|用|开通)([\w-]*)',value.strip())
        if (not full or full[1] and integer(full[1])!=len(order) or
                full[3] and full[3] not in m['treatment'] and full[3] not in texts['question']):
            try:
                return allocation(value,order)
            except Incomplete:
                return value
        return [int(not full[2])]*len(order)

    model_network=facts.get('network')
    model_order=(model_network.get('value') if isinstance(model_network,dict) else None) or {}
    order=model_order.get('nodes') if isinstance(model_order,dict) else None

    def same_vector(value,wanted):
        if wanted is None:
            return value is None or isinstance(value,str) and re.fullmatch(r'无(?:对照|参考)?(?:安排|政策|方案)?|不适用',value.strip()) is not None
        if not isinstance(order,list) or not all(isinstance(n,str) for n in order) or sorted(order)!=sorted(m['nodes']):
            return False
        value=policy_vector(value,order)
        return (isinstance(value,list) and len(value)==len(order) and all(type(x) is int for x in value)
                and dict(zip(order,value))==dict(zip(m['nodes'],wanted)))

    for key, label in [('network','原名册和关系'),('assignment','试点分配'),('exposure','同伴暴露'),('contrast','评价人群及比较两端')]:
        item = facts.get(key)
        if not isinstance(item,dict):
            differences.append(label)
            continue
        v = item.get('value')
        refs = item.get('evidence')
        if not isinstance(v,dict) or not isinstance(refs,list) or not refs or not all(original_quote(r,key) for r in refs):
            differences.append(label)
            continue
        if key=='network':
            try:
                edges=[re.split(r'\s*[—–]\s*',e) if isinstance(e,str) else e for e in v.get('edges',[])]
                ok=(sorted(v.get('nodes',[]))==sorted(m['nodes']) and
                    sorted(sorted(pair) for pair in edges)==sorted(sorted(pair) for pair in m['edges']) and
                    all(v.get(k) is True for k in ('pre_treatment','complete','undirected')))
            except (ValueError,TypeError):
                ok=False
        elif key=='contrast':
            population=[n for n,w in zip(m['nodes'],m['weights']) if Fraction(w)]
            ok=(isinstance(v.get('population'),list) and sorted(v['population'],key=str)==sorted(population) and
                same_vector(v.get('left'),m['first']) and same_vector(v.get('right'),m['second']))
            w=v.get('unit_weights',v.get('weights'))
            if w is not None or len(set(m['weights']))>1:
                try:
                    ok=ok and isinstance(w,list) and len(w)==len(order) and dict(zip(order,map(Fraction,w)))==dict(zip(m['nodes'],map(Fraction,m['weights'])))
                except (ValueError,TypeError,ZeroDivisionError):
                    ok=False
        elif key=='assignment':
            design=m['design']
            ok=(v.get('kind')=='fixed' and v.get('quota')==design['m'] if 'm' in design else
                v.get('kind') in ('other','stratified') and v.get('groups')==design['groups'] and
                v.get('treated_quotas')==design['treated_quotas'])
            if ok and v.get('probabilities') is not None:
                if 'm' in design:
                    rates=dict.fromkeys(m['nodes'],Fraction(design['m'],len(m['nodes'])))
                else:
                    rates={n:Fraction(quota,len(group)) for group,quota in zip(design['groups'],design['treated_quotas']) for n in group}
                given=v['probabilities']
                try:
                    ok=isinstance(given,dict) and {n:Fraction(p) for n,p in given.items()}==rates
                except (ValueError,TypeError,ZeroDivisionError):
                    ok=False
        else:
            expected={'strict_majority_ties_low':'majority','exact_treated_neighbor_count':'count',
                      'three_level_treated_neighbor_fraction':'other'}[m['grouping']]
            description=v.get('description')
            ok=v.get('kind')==expected and (expected!='other' or isinstance(description,str) and description.rstrip('。')==m['exposure_source']['quote'])
            contrary=r'(?:至少一半|不少于半数|未启用|未使用|未处理邻居|全区所有)[^。，；]{0,24}(?:记为?|为)1|平票(?:也)?(?:记为?|为)1'
            if expected=='majority' and isinstance(description,str) and re.search(contrary,description):
                ok=False
        if not ok:
            differences.append(label)
    from .direct_verification import answer_items
    answer=answer_items(draft)[0]
    goal=answer.get('target')
    if isinstance(goal,dict):
        population=[n for n,w in zip(m['nodes'],m['weights']) if Fraction(w)]
        wanted='level' if m['second'] is None else 'difference'
        scope='whole' if len(population)==len(m['nodes']) else 'subgroup'
        if (goal.get('quantity') not in (None,wanted) or goal.get('scope') not in (None,scope) or
            isinstance(goal.get('population'),list) and sorted(goal['population'],key=str)!=sorted(population)):
            differences.append('展示答复中的目标或人群')
        for key,side in [('intervention','first'),('reference','second')]:
            if goal.get(key) is not None and not same_vector(goal[key],m[side]):
                differences.append('展示答复中的政策安排')
    return list(dict.fromkeys(differences))
