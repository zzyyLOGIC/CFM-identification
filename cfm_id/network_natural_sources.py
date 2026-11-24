"""Read one ordered local-event contrast from the question, protocol and actual roster.

Only affirmative source declarations enter the solver. Its answer is subsequently
checked against these coordinates, the model's claims, and the uploaded columns.
"""
import json
import re
from fractions import Fraction

from . import uploaded_network_contrast as contrast
from .network_grounded_contrast import source_lines
from .network_protocol_terms import NUM, integer, named_units, uniform_quota
from .network_query_binding import RATE, read_rate


VERSION = "natural-network-materials/1"
WEIGHT = r"等权|同权|同等权重|权重相同|各占一半|各半"
RESTRICTION = r"(?:只|仅)(?:考核|考察|评价|评估|看|对)|评价对象(?:为|是)"
PEER = r"相邻|邻|同伴|伙伴|搭档"
SEPARATOR = r"[，,]"
COMPARISON = r"减去|(?<![对相])比(?!(?:较|例|率))(?=[^。？；]{1,45}?(?:多|高))"
DISPLACED = (r"后者减前者|反过来|降低量|减少量|节约量|低多少|再比较|同时求|第二问|另一个目标|"
             r"固定(?:其余|其他|具体)|(?:其余|其他).{0,12}(?:固定|改为|改用|一律)|"
             r"不(?:再)?(?:保持|沿用|服从)|不按|另(?:一套|一个)(?:政策|设计)|强制|外推|新的?(?:政策|抽签方案)|"
             r"改(?:为|用|成|问)|换成|仅供参考|不采用|反事实固定|加权邻居|按距离加权|有向关系|"
             r"至少一半|一半(?:及|或)以上|(?:平票|孤立点).{0,5}(?:记为?1|算高)|"
             r"不等权|按.{0,9}(?:营收|人数|规模)加权|排除|除.{1,12}以外")


def conditional_mixture(row):
    """A request for randomization probabilities alone says nothing about the estimand."""
    line = row["quote"]
    return (re.search(r"(?:其余|其[他它]|剩余|未固定)(?:的)?(?:单位|对象|站点|门店|站|人|安排|分配|处理)", line)
            and re.search(r"两端|各端|每端|事件(?:内|下)|各(?:自|事件)|分别", line)
            and re.search(r"(?:保持|保留|沿用|遵循|服从|来自|依照|依|按).{0,14}"
                          r"(?:原|本次(?:试验|试点|实验|设计|抽签)|实际(?:分配|随机化|抽签)).{0,14}"
                          r"(?:条件(?:分布|规律|概率|分配|抽取|抽签)|给定(?:本端|该事件|本事件)后的分布)", line)
            and not re.search(r"是否|假如|不清楚|可能|未指定|不(?:再)?(?:维持|保持|遵循|服从)", line))


def focal(rows, nodes):
    from .network_source_alignment import EQUAL, WEIGHT_CHANGE
    groups = []
    refs = []
    halves = False
    for row in rows:
        for clause in re.split(SEPARATOR, row["quote"]):
            clause = clause.strip()
            if re.search(WEIGHT_CHANGE, clause):
                return None, []
            weight = re.search(WEIGHT, clause)
            if weight:
                refs.append(row)
                halves |= weight[0] in ("各半", "各占一半")
            subject = re.sub(r"^仅(?!(?:评价|评估|考察|看|对))", "", clause)
            if weight:
                subject = subject[:subject.find(weight[0])].rstrip("，, ")
            singleton = re.fullmatch(r"(.+?)(?:是唯一(?:的)?评价对象|只评价自身|仅评价自身)", subject)
            prefix = re.match(RESTRICTION, subject)
            if not (weight or singleton or prefix) and named_units(subject,nodes):
                # A comma-separated extra name may extend an earlier restriction.
                # Only consume a list when its full membership is unambiguous.
                return None, refs + [row]
            if not subject or not (weight or singleton or prefix):
                continue
            names = singleton[1] if singleton else subject[prefix.end():] if prefix else subject
            selected = named_units(names.strip("【】「」 "), nodes)
            if not selected:
                counted = re.fullmatch(r"(?:全体|全部)?(" + NUM + r")(?:个|处|家|位|座)?(.{1,8})", names)
                generic = re.fullmatch(r"(?:全体|全部)(?:单位|对象|站点|门店|节点|名册成员)", names)
                if counted and integer(counted[1]) == len(nodes):
                    noun = counted[2]
                    if (noun in ("单位", "对象", "站点", "门店", "节点")
                            or any(label and all(n.endswith(label) for n in nodes) for label in (noun,noun.removesuffix("区")))):
                        selected = nodes
                elif generic:
                    selected = nodes
            if not selected or len(set(selected)) != len(selected):
                return None, refs + [row]
            groups.append(selected)
            refs.append(row)
    if not groups or any(set(g) != set(groups[0]) for g in groups):
        return None, refs
    units = groups[0]
    if halves and len(units) != 2 or len(units)>1 and not halves and not any(re.search(EQUAL,r["quote"]) for r in refs):
        return None, refs
    return dict.fromkeys(units, str(Fraction(1,len(units)))), refs


def mapping(rows):
    definitions = {
        "majority": r"(?:超过(?:一半|半数)|严格过半|严格多数)[^，,]{0,18}(?:记|编[码]?|算|定)为?1",
        "any": r"至少(?:一|1)(?:个|位|家|名)?[^，,]{0,18}(?:记|编[码]?|算|定)为?1",
        "count": r"(?:暴露|同伴状态)[^，,]{0,28}(?:精确|确切|实际)(?:个数|数量|人数|家数)",
    }
    relevant = [r for r in rows if re.search(PEER,r["quote"]) and re.search(r"记为?[01]|编码|暴露取|暴露(?:为|是|定义为)|映射规则",r["quote"])]
    if any(re.search(r"(?:不|未)(?:启用|处理|开通|开放)|关闭|可能|是否|拟采用|尚未|不确定|二阶|加权",r["quote"].split("，")[0]) for r in relevant):
        return None, []
    matches = [(kind, row) for row in relevant
               for kind, pattern in definitions.items() if re.search(pattern,row["quote"])]
    kinds = {kind for kind,_ in matches}
    if len(kinds) != 1:
        return None, []
    rule = kinds.pop()
    alternatives = [r for r in relevant if re.search(r"(?:暴露|同伴状态)(?:取|为|是|定义为)|记为?[01]",r["quote"])
                    and r not in [row for _,row in matches]]
    if alternatives or rule != "count" and not any(re.search(r"(?:否则|零个|没有|均未|其余).{0,9}(?:记|算|编码)为?0",r["quote"]) for _,r in matches):
        return None, []
    return rule, [r for _,r in matches]


def allocation(rows, nodes):
    from .network_source_alignment import COMPLEX_DESIGNS, UNCERTAIN_LAW, assignment, relevant
    evidence = relevant(rows,r"抽签|概率|机会|无放回|处理变量|分配变量|名册顺序")
    lines = [r["quote"] for r in evidence]
    text = "。".join(lines)
    variables = set(re.findall(r"(?:处理变量|分配变量)(?:为|是|[：:])([^。，,；]{1,28})",text))
    if len(variables) != 1 or re.search(UNCERTAIN_LAW+r"|邀请|鼓励|资格|有权拒绝|相关抽签|并非独立",
                                       "。".join(r["quote"] for r in rows if r["source_id"]!="question")):
        return None, evidence
    if any(re.search(pattern,text) for _,pattern in COMPLEX_DESIGNS):
        return None, evidence
    variable = variables.pop()
    ordered = [named_units(m[1],nodes) for line in lines for m in
               re.finditer(r"(?:名册|名单)顺序(?:为|是|[：:])(.+)$",line)]
    if any(order != nodes for order in ordered):
        return None, evidence
    totals = re.findall(r"(?:从|在)(?:全(?:部|体))?(" + NUM + r")(?:个点|个单位|个对象|个节点|人|站|家)",text)
    if any(integer(n) != len(nodes) for n in totals):
        return None, evidence
    from .network_protocol_terms import independent_draw, common_probability
    independent = independent_draw(text)
    fixed = uniform_quota(lines,nodes)
    if independent and not re.search(r"无放回|名额|抽取|抽出",text):
        vectors = []
        common = common_probability(text,nodes)
        if common is not None:
            vectors.append(common)
        for line in lines:
            vector = re.search(r"(?:按|依照)(?:名册|名单)顺序[^，,]{0,12}(?:概率|机会)(?:分别|依次)(?:为|是)(.+)$",line)
            if vector:
                parts = re.split(r"[、，,]",vector[1])
                if not ordered or len(parts)!=len(nodes) or not all(re.fullmatch(RATE,v.strip()) for v in parts):
                    return None, evidence
                vectors.append({n:str(read_rate(v.strip())) for n,v in zip(nodes,parts)})
            for m in re.finditer(r"(?:每|各)(?:个)?(?:点|单位|对象|节点|店|站|人)(?:均|都)?(?:以|按|有)("+RATE+r")(?:的)?(?:概率|机会)",line):
                vectors.append(dict.fromkeys(nodes,str(read_rate(m[1]))))
        declared, _ = assignment(rows,nodes,"")
        if declared and declared.get("kind")=="independent":
            vectors.append({n:str(Fraction(p)) for n,p in declared["p"].items()})
        if not vectors or any(v != vectors[0] for v in vectors):
            return None, evidence
        law = dict(kind="independent",p=vectors[0])
        rates = vectors[0]
    elif not independent and fixed is not None:
        law = dict(kind="fixed",quota=fixed)
        rates = dict.fromkeys(nodes,str(Fraction(fixed,len(nodes))))
    else:
        return None, evidence
    for n in nodes:
        named = re.findall(re.escape(n)+r"(?:的)?(?:启用|中签|入选|抽中)?(?:的)?(?:概率|机会)(?:为|是|等于)("+RATE+r")",text)
        if any(read_rate(p)!=Fraction(rates[n]) for p in named):
            return None, evidence
    return dict(law,variable=variable), evidence


def peer_value(clause, rule, degrees):
    if rule == "majority":
        threshold = r"(?:严格多数|(?:严格)?过半|超过(?:一半|半数))"
        if re.search(r"(?:没(?:有|达)?|未(?:达|达到)?|不(?:达|到)?)"+threshold,clause):
            return 0
        if re.search(threshold,clause) and not re.search(r"(?:不|未)(?:开|启用)",clause):
            return 1
        return None
    if rule == "count":
        exact = re.search(r"(?:恰好|正好|恰有|恰为|恰)(零|"+NUM+r")",clause)
        if exact:
            return integer(exact[1])
        both = re.search(r"("+NUM+r")(?:个|位|家)?(?:邻|同伴|伙伴).{0,6}?(?:都|均|全部)(不|未)?(?:开|启用)",clause)
        if both and degrees == {integer(both[1])}:
            return 0 if both[2] else integer(both[1])
        return None
    if re.search(r"没有(?:一个)?邻|无邻|(?:全|均|都)(?:未|不|没)|一个也没|零个",clause):
        return 0
    if re.search(r"(?:有邻|至少(?:一|1))",clause) and not re.search(r"(?:不|未)(?:开|启用)",clause):
        return 1
    return None


def ordered_pair(line, rule, variable, group, nodes, degrees):
    # Parse clauses on each side separately. Inheritance is limited to a shared
    # condition BEFORE the first arm and a bare predicate with the same subject.
    splits = list(re.finditer(COMPARISON,line))
    if len(splits)!=1:
        return None
    sep, = splits
    if sep[0]=="比" and re.search(r"平均少|更少|低于|减少",line[sep.end():]):
        return None
    suffixes = {n[-1] for n in nodes if n}
    unit = r"(?:本(?:站|单位|人|店|校|院)|自身|自己|评价(?:对象|单位)|(?:本|评价)["+"".join(map(re.escape,sorted(suffixes)))+r"]|"+ "|".join(map(re.escape,group))+r")"
    action = r"(?:未启用|没有启用|不启用|未开|不开|关闭|启用|开启|开通|开)"
    own = re.compile(unit+r"(?:自身|自己)?(?:均|都|维持|保持|仍|也)?("+action+r")")
    predicates = re.compile(r"^(?:本站)?("+action+r")")
    def state(m):
        return int(not re.match(r"未|没有|不|关闭",m[1]))
    def parse(part, ellipsis=None):
        part = part.strip(" ，,")
        m = own.search(part)
        if not m and ellipsis=="own":
            m = predicates.match(part)
        own_value = None
        if m:
            own_value = state(m)
            # An explicitly named treatment must name this intervention. Remove
            # outcome grammar; permit a short, source-backed label (e.g. 开灯).
            obj = re.split(r"(?:时|且|减|为第一端|的|有邻|没有邻|，|,|既)",part[m.end():])[0]
            if obj and (obj not in variable or not variable.endswith(obj)):
                return None
        peer_clause = part
        if m and re.search(PEER,part[m.end():]):
            peer_clause = part[m.end():]
        elif m and re.search(PEER,part[:m.start()]):
            peer_clause = part[:m.start()]
        has_peer = bool(re.search(PEER,peer_clause))
        exposure = peer_value(peer_clause,rule,degrees) if has_peer or ellipsis=="peer" else None
        if has_peer and exposure is None:
            return None
        return own_value,exposure
    before = [t for t in re.split(SEPARATOR,line[:sep.start()]) if t.strip()]
    after = [t for t in re.split(SEPARATOR,line[sep.end():]) if t.strip()]
    if not before or not after or any(re.search(PEER,clause) or own.search(clause) for clause in after[1:]):
        return None
    common = [None,None]
    for clause in before[:-1]:
        read = parse(clause)
        if read is None:
            return None
        for i, value in enumerate(read):
            if value is not None:
                if common[i] is not None and common[i]!=value:
                    return None
                common[i] = value
    left = parse(before[-1])
    if not left or left==(None,None):
        return None
    ellipsis = "own" if left[1] is None else "peer" if left[0] is None else None
    right = parse(after[0],ellipsis)
    if not right or right==(None,None):
        return None
    ends = []
    for side in (left,right):
        if any(a is not None and b is not None and a!=b for a,b in zip(side,common)):
            return None
        arm = tuple(a if a is not None else b for a,b in zip(side,common))
        if None in arm:
            return None
        ends.append(arm)
    return tuple(ends) if ends[0]!=ends[1] else None


def measured_target(case, docs, variable):
    outcomes = {m[1] for r in docs for m in re.finditer(r"(?:结果指标|结局指标)(?:为|是|[：:])([^，,。；]{1,50})",r["quote"])}
    if len(outcomes)!=1:
        return None
    name = outcomes.pop()
    from .uploaded_network_sources import outcome_period
    labels = outcome_period({"quote":name},docs)
    if not isinstance(labels,tuple):
        return None
    q = case["business_question"]
    stem = re.sub(r"^(?:首周|首日|当日|本周|次周|当月|本月)(?:完成的|记录的|的)?","",name)
    reduced = re.sub(r"多少(?:个|份|件|张)?","",q)
    if name not in q and (len(stem.rstrip("数量"))<3 or stem.rstrip("数量") not in reduced):
        return None
    for time in re.findall(r"首周|次周|第二周|本月|次月|去年|首日|次日",q):
        if time not in name and time not in labels[0][1]:
            return None
    for src in case["sources"]:
        if src["source_id"]=="uploaded_data_schema":
            schema = json.loads(src["text"])
            if schema["outcome"]!=name or schema["treatment"].partition("；")[0]!=variable:
                return None
    return labels


def read(case, table, *, scope_resolution=None):
    from .network_source_alignment import GENERATED, uploaded_graph_agrees
    nodes = list(table.nodes)
    if not nodes or len(nodes)>256:
        return None
    rows = source_lines(dict(case,sources=[s for s in case["sources"] if s["source_id"] not in GENERATED]))
    docs = [r for r in rows if r["source_id"]!="question"]
    remaining = next((r for r in rows if conditional_mixture(r)),None)
    if not remaining or any(re.search(DISPLACED,r["quote"]) for r in rows) or not uploaded_graph_agrees(case,table,rows):
        return None
    weights, focal_rows = focal(rows,nodes)
    rule, map_rows = mapping(rows)
    law, design_rows = allocation(rows,nodes)
    if not weights or not rule or not law:
        return None
    if scope_resolution:
        selected=scope_resolution["members"]
        if selected not in (list(weights),nodes):
            return None
        weights=dict.fromkeys(selected,str(Fraction(1,len(selected))))
    degrees = {sum(n in e for e in table.edges) for n in weights}
    comparisons = [(row,pair) for row in rows if row["source_id"]=="question"
                   for pair in [ordered_pair(row["quote"],rule,law["variable"],list(weights),nodes,degrees)] if pair]
    if len(comparisons)!=1 or sum(len(re.findall(COMPARISON,r["quote"])) for r in rows if r["source_id"]=="question")!=1:
        return None
    arm_row, pair = comparisons[0]
    if scope_resolution and scope_resolution["option"]=="whole":
        # A named individual's own treatment cannot be generalized from a subgroup
        # to the entire roster. Each focal must express the same local comparison.
        for node in weights:
            degree={sum(node in e for e in table.edges)}
            if ordered_pair(arm_row["quote"],rule,law["variable"],[node],nodes,degree)!=pair:
                return None
    labels = measured_target(case,docs,law["variable"])
    if not labels:
        return None
    return dict(weights=weights,group_rows=focal_rows,rule=rule,map_rows=map_rows,law=law,design_rows=design_rows,
                pair=pair,arm_row=arm_row,remaining=remaining,labels=labels,rows=rows,docs=docs)


def bind(case, table, *, scope_resolution=None):
    data = read(case,table,scope_resolution=scope_resolution)
    if not data:
        return None
    from .network_protocol_terms import population_queries
    docs = data["docs"]
    units = list(data["weights"])
    catalog = population_queries(docs,units)
    available = r"(?:可查(?:询)?|可(?:以)?查询|允许查询|可以取得)"
    for row in docs:
        line = row["quote"]
        if (re.search(r"(?:每个|各个|每一位)(?:评价对象|对象|单位|节点)",line)
                and re.search(r"(?:任何|任一|所有|各)(?:有)?正概率",line)
                and re.search(r"(?:本人|自身).{0,8}(?:同伴|邻居).{0,6}(?:状态|暴露)",line)
                and re.search(r"总体条件均值",line) and re.search(available,line)):
            catalog.append(row)
    restricted = any(re.search(r"不可查|不能查|无法查|仅可查|只可查|并非.{0,15}可查|只.{0,9}(?:一端|部分)|缺少.{0,10}条件均值",r["quote"])
                     or re.search(r"若|假如|计划|将来|可能|尚未|拟提供|只有",r["quote"]) and re.search(r"条件均值|总体联合",r["quote"])
                     for r in docs)
    law = dict(data["law"])
    variable = law.pop("variable")
    labels, periods = data["labels"]
    cited = dict(network=[r for r in source_lines(case) if r["source_id"]=="uploaded_network"],
                 contrast=[*data["group_rows"],data["arm_row"],data["remaining"]],
                 exposure=data["map_rows"],assignment=data["design_rows"])
    result = contrast.solve_materials(case,table,units,data["arm_row"],data["pair"],data["rule"],law,variable,
                                      labels,data["rows"],docs,cited,population_rows=catalog,remaining_row=data["remaining"],
                                      population_unavailable=restricted)
    if result and "result" in result:
        proof = result["result"]["proof"]
        proof["binding_source"] = VERSION
        proof["source_spans"].extend(periods)
        if scope_resolution:
            proof["confirmed_population"]=dict(scope_resolution)
    return result
