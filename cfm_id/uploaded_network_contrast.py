"""Connect a cited local comparison to the actual uploaded roster, graph and design.

The source question fixes arm order. The source protocol fixes the design and
query interface. Neither a model's STOP nor its POINT supplies scientific consent.
"""
import re
from copy import deepcopy
from fractions import Fraction

from cfm_id_llm.compact_study import digest
from . import network_reading as reading
from .direct_verification import answer_items, bound_network
from .network_grounded_contrast import source_lines
from .network_query_binding import read_rate, solve_reviewed
from .network_response import exact_event


SELF = r"(?:本店|本站|本校|本院|本单位|该店|该站|自己|自身|本人|自己所在的单位)"
ACTION = r"(?:启用|开通|开启|接受处理|接受干预|使用|参与|收到邀请|获邀|接种|开灯|处理|开放)"
PEERS = r"(?:合作(?:门店|店|站|单位|伙伴)|相邻(?:门店|站点)|邻店|邻站|邻居|邻校|同伴|伙伴|邻接对象|朋友)"
NEGATION = r"不超过|至多一半|一半或更少|半数或更少|未过半|未超过一半|不占多数"
MAJORITY = r"严格过半|超过(?:一半|半数)|过半|多数(?:已)?(?:启用|开通|处理|开放)|多数(?:为|记)1"
NONE = r"都不|均不|都未|均未|无人|没有一个|一个也没有|全部未|全未"
ANY = r"至少(?:一|1)(?:个|位|人|名|家|站)?|有任一"
EXACT = r"(?:恰好|恰有|正好|恰为|恰)(\d+|[零一二两三四五六七八九十])"
COMPARE = r"相比于|相对于|相比|相对|减去|减|对比"
ORIGINAL = r"(?:沿用|按(?:照)?|服从|保留).{0,10}原(?:来(?:的)?|有(?:的)?|始(?:的)?)?(?:独立)?(?:抽签|设计|分配)"
PRE = r"(?:试点|干预|处理|抽签|分配|实验|项目)(?:开始)?前|基线|事前"
NEG_SCI = r"不采用|拒绝|不成立|不独立|不一致|不满足|不能保证|无法确认|不能确认|无法保证|不清楚|无法判断|可能不|并非|撤回|未承诺|不能假定|没有证据|不认为|未知|无限|发散"
PREMISES = {
    "full_vector_randomization": ("完整分配不依赖潜在结果", r"(?:完整|全部|整份|整单).{0,20}(?:名单|安排|分配).{0,22}独立于.{0,12}潜在|(?:任何|每一种|各种).{0,8}安排下.{0,16}(?:评分|结果|结局).{0,10}(?:决定|中签)|潜在.{0,12}(?:结果|结局|评分).{0,12}与.{0,12}(?:完整分配|完整名单).{0,10}独立"),
    "consistency": ("观测结果对应实际的完整分配", r"(?:记录|观测|观察|实际).{0,25}(?:对应|等于|就是).{0,35}(?:实际.{0,8}(?:名单|安排|分配)|当次名单|完整安排)"),
    "finite_conditional_first_moments": ("各比较情形的平均结果有限", r"(?:平均(?:评分|结果|结局)|条件均值|各端均值|条件期望|均值).{0,18}有限|有限(?:的)?(?:条件均值|条件一阶矩)"),
}


def unit_state(text):
    pattern=SELF+r"(?:自己|也|仍|保持|已经|已|为)?(不|未|没有|没)?"+ACTION+r"(?:\s*[=＝]\s*([01]))?"
    found=set()
    for m in re.finditer(pattern,text):
        if m[1] and m[2]=="1":
            return None
        found.add(int(m[2]) if m[2] is not None else int(not m[1]))
    return next(iter(found)) if len(found)==1 else None


def peer_state(text, rule):
    if rule == "majority":
        if re.search(NEGATION,text):
            return 0
        m=re.search("(?:"+MAJORITY+r")(?:\s*[=＝]\s*([01]))?",text)
        if m:
            return int(m[1]) if m[1] is not None else 1
    elif rule == "any":
        if re.search(NONE,text):
            return 0
        m=re.search("(?:"+ANY+r")([^，,。且；]{0,18})",text)
        if m:
            indicator=re.search(r"[=＝]\s*([01])",m[1])
            return int(indicator[1]) if indicator else 1
    elif rule == "count":
        m = re.search(EXACT,text)
        if m:
            return int(m[1]) if m[1].isdigit() else (2 if m[1]=="两" else reading.NUMS[m[1]])
        if re.search(NONE,text):
            return 0
    return None


def proposed_arm(value,rule):
    arm=exact_event(value)
    if isinstance(arm,list) and len(arm)==2 and all(type(i) is int for i in arm):
        return tuple(arm)
    if isinstance(value,str) and re.search(PEERS,value):
        return unit_state(value),peer_state(value,rule)
    return None


def question_arms(line,rule):
    coded=reading.native.contrasts(line)
    if len(coded)==1 and "(T,S)" in line.replace(" ",""):
        return tuple(coded[0][1:])
    if re.search(r"后者减前者|减少量|节约量|下降量|改用|而非|而不是|固定(?:具体|哪几|其他|其余)",line):
        return None
    # A leading condition is shared only across the clauses it actually governs.
    context=""
    shared=re.search(r"当([^，,。；？]{2,70}?)(?:时)?[，,]|在([^，,。；？]{2,70}?)(?:时|条件下|情况下)[，,]",line)
    if shared:
        context,line=shared[1] or shared[2],line[shared.end():]
    parts=re.split(COMPARE,line)
    if len(parts)!=2:
        return None
    before,after=parts
    # Chinese uses both "A 相比 B" and "与 B 相比，A". Direction is part of the query.
    if re.match(r"^\s*(?:与|和|跟)",before) and re.match(r"^[，,]",after):
        parts=[after.lstrip("，,"),before.lstrip("与和跟 ")]
    elif "与" in before and (not after.strip("，,， ") or re.match(r"^[，,]",after)):
        named=before.split("与")
        if len(named)==2 and all(unit_state(t) is not None or re.search(PEERS,t) for t in named):
            parts=named
    xs=[]
    for part in parts:
        a=unit_state(part)
        peer=peer_state(part,rule) if re.search(PEERS,part) else None
        x=unit_state(context)
        s=peer_state(context,rule) if re.search(PEERS,context) else None
        if (x is not None and a is not None and x!=a) or (s is not None and peer is not None and s!=peer):
            return None
        xs.append((a if a is not None else x,peer if peer is not None else s))
    return tuple(xs) if all(None not in pair for pair in xs) and xs[0]!=xs[1] else None


def group_from_source(q, lines, nodes, proposed, *, source_only=False):
    counts=re.findall(r"(?:全部|全体|名册含|名册包括)(\d+)\s*(?:家|个|所|名|位|座)",q)
    if any(int(n)!=len(nodes) for n in counts):
        return None
    if re.search(r"按.{0,10}(?:人数|营收|收入|销售额|规模).{0,6}(?:加权|权重)|不等权|仅看实际|只看中签|只看已|只看有记录",q):
        return None
    selected=reading.focal_units(q,nodes)
    restricted=re.search(r"(?:仅评(?:价)?|只评(?:价)?|只看|只考察|仅看)[【「]?([^，。；、\s】」]{1,24})[】」]?",q)
    if restricted and not selected:
        name=restricted[1]
        if name not in nodes:
            return None
        selected=[name]
    if restricted and selected:
        group=selected
    else:
        if restricted or not re.search(r"(?:全部|全体|完整名册内)(?:的)?(?:\d+\s*)?(?:家|人|站|门店|单位|站点|节点|校|对象|个)",q):
            return None
        group=list(nodes)
    if len(group)>1 and not any(re.search(r"等权|权重相同|同等权重|分量相同|同样权重",r["quote"]) for r in lines):
        return None
    if source_only:
        return group
    if isinstance(proposed,str):
        proposed=[proposed]
    generic=(len(group)==len(nodes) and isinstance(proposed,list) and len(proposed)==1
             and isinstance(proposed[0],str) and re.fullmatch(r"(?:每|各|全体|全部)(?:一|个|家|位|\d+)*(?:店|门店|站点|站|单位|人|对象|节点|学校|校)",proposed[0]))
    return group if generic or (isinstance(proposed,list) and all(isinstance(n,str) for n in proposed)
                                and len(proposed)==len(group) and set(proposed)==set(group)) else None


def actual_law(assignment, texts, nodes):
    text="。".join(texts)
    from .network_protocol_terms import independent_draw, common_probability
    if re.search(r"不(?:再|是)?独立抽签|不是独立分配|并非独立|无法确认.{0,14}(?:独立|无放回)|是否独立.{0,12}(?:未知|不清楚)|改为.{0,12}(?:抽取|抽签|名额)",text):
        return None
    law=reading.assignment(text,nodes)
    if assignment is None:
        # A complete design declaration can be read without a model-supplied quota or propensity map.
        if isinstance(law,reading.native.types.CompleteRandomizationDesignV1):
            return dict(kind="fixed",quota=law.m)
        kind="independent"
    else:
        kind=assignment.get("kind")
    if kind=="fixed" and isinstance(law,reading.native.types.CompleteRandomizationDesignV1):
        if type(assignment.get("quota")) is int and assignment["quota"]==law.m:
            return dict(kind="fixed",quota=law.m)
    if kind!="independent" or not independent_draw(text):
        return None
    if re.search(r"共用.{0,6}(?:签|硬币)|固定(?:名额|选取)|恰好(?:抽取|选出)|无放回|抽签后.{0,15}(?:自行选择|可拒绝)|(?:只|仅)(?:随机|抽取)邀请",text):
        return None
    rate=r"(?:\d+/\d+|\d*\.?\d+%?|一半|[二三四五六七八九十]分之[一二三四五六七八九])"
    hits=[m[1] for m in re.finditer(r"(?:各|都|均|每(?:个|家|人|站|位|单位)?)(?:自|店|站|节点|对象)?(?:有|以|按)("+rate+r")(?:的)?(?:机会|概率)",text)]
    hits += [m[1] for m in re.finditer(r"(?:各|都|均|每(?:个|家|人|站|位|单位)?)(?:店|站|节点|对象)?(?:的)?(?:中签|抽中|启用|入选)?(?:的)?(?:概率|机会)(?:均|都)?(?:为|是)("+rate+r")",text)]
    rates={read_rate(v) for v in hits}
    if len(rates)>1:
        return None
    if isinstance(law,reading.native.types.HeterogeneousBernoulliDesignV1):
        ps=law.propensities
        if rates and any(read_rate(v) not in rates for v in ps.values()):
            return None
    elif len(rates)==1:
        ps=dict.fromkeys(nodes,str(rates.pop()))
    else:
        ps=common_probability(text,nodes)
        if ps is None:
            return None
    if assignment is None:
        return dict(kind="independent",p=ps)
    proposed=assignment.get("probabilities")
    if not isinstance(proposed,dict) or not proposed:
        return None
    if set(proposed)==set(nodes):
        if any(read_rate(str(proposed[n]))!=Fraction(ps[n]) for n in nodes):
            return None
    elif len(proposed)!=1 or not re.fullmatch(r"(?:每|各|全体|全部|所有|所有的)[^\d]{0,8}|all|common",next(iter(proposed)),re.I) or set(map(Fraction,ps.values()))!={read_rate(str(next(iter(proposed.values()))))}:
        return None
    return dict(kind="independent",p=ps)


def treatment_name(question_row,design_rows,corpus):
    stated=re.findall(r"(?:处理变量|分配变量)(?:是|为|：)([^。；，,\n]{1,28})",corpus)
    by_chance=[m[1] for s in design_rows for m in re.finditer(
        r"(?:概率|机会)(?:直接)?("+ACTION+r"[\w]{0,14}?)(?=[。！，；,\s]|$)",s)]
    by_chance += [m[1] for s in design_rows for m in re.finditer(
        r'(?:^|[，,])('+ACTION+r'[\w]{0,14}?)的(?:概率|机会)(?:均|都)(?:为|是)',s)]
    names=set(stated or by_chance)
    if len(names)!=1:
        return None
    name=names.pop()
    own_prefix=SELF+r"(?:自己|也|仍|保持|已经|已)?(?:不|未|没有|没)?"
    operations=set(re.findall(own_prefix+"("+ACTION+")",question_row))
    if operations and not all(op in name for op in operations):
        return None
    for match in re.finditer(own_prefix+"("+ACTION+r")([^，。；？,=＝]*)",question_row):
        obj=re.split(r"相比|相对|对比|减|时|且|与|和",match[2])[0].strip()
        if obj and obj not in name:
            return None
    if not operations and name not in question_row and not stated:
        return None
    return name


def source_labels(target, question, lines):
    # Prefer exact field names from the question or a declared outcome; never use
    # an ungrounded model gloss as the lookup key for the estimator.
    outcome=target.get("outcome")
    if not isinstance(outcome,str):
        return None
    parts=re.split(r"[（(，,；;]",outcome)
    y=parts[0].strip()
    y=re.sub(r"^(?:同一|本次)(?:观察时段|时段|观察期)(?:内|中)?的","",y)
    if not y or len(y)>80 or not any(y in line["quote"] for line in lines) or y not in question and not any(
            re.search(r"(?:结果|指标)(?:为|是|定义为)"+re.escape(y),line["quote"]) for line in lines):
        return None
    period=target.get("time")
    if not isinstance(period,str) or not period.strip() or re.search(r"未知|未提及|未指定|不明确|未提供",period):
        return None
    if period in question or any(period in line["quote"] for line in lines):
        return y,period
    # Localized and ISO spellings of the same interval may differ; retain the
    # unique original interval with matching date and both clock times.
    date=re.search(r"(\d{4})[-年](\d{1,2})[-月](\d{1,2})",period)
    times=re.findall(r"\d{1,2}:\d{2}:\d{2}",period)
    if not date or len(times)!=2:
        return None
    pat=rf"{date[1]}[-年]0?{int(date[2])}[-月]0?{int(date[3])}(?:日)?"
    hits=[r["quote"] for r in lines if re.search(pat,r["quote"]) and all(t in r["quote"] for t in times)
          and ("UTC" not in period or "UTC" in r["quote"])]
    return (y,hits[0]) if len(set(hits))==1 else None


def gap(message):
    return {"question":message}


def bind(case,draft,network,report):
    fields=(report.get("network_reading") or {}).get("fields") or {}
    if not all(isinstance(fields.get(k,{}).get("proposed"),dict) for k in reading.FIELDS):
        return None
    c=fields["contrast"]["proposed"]
    items=answer_items(draft)
    if len(items)!=1 or not isinstance(items[0].get("target"),dict):
        return None
    target=items[0]["target"]
    q=case["business_question"]
    if target.get("quantity")!="difference" or not re.search(ORIGINAL,q) or re.search(r"第二问|另一问|反向再|两种设计|后者减前者|固定其余|外推",q):
        return None
    if len(re.findall(r"[？?]",q))>1 or re.search(r"另外还|还想(?:问|知道)|再比较|同时求",q):
        return None
    rule=fields["exposure"]["proposed"].get("kind")
    if rule not in ("majority","any","count"):
        return None
    lines=source_lines(case)
    qlines=[r for r in lines if r["source_id"]=="question"]
    found=[(r,question_arms(r["quote"],rule)) for r in qlines]
    found=[(r,pair) for r,pair in found if pair]
    if len(found)!=1:
        return None
    row,pair=found[0]
    if re.search(r"(?:不再|不|并非|禁止)(?:沿用|按).{0,8}原(?:设计|分配|抽签)|(?:另外|改为|改用).{0,10}(?:强制|固定名单|新政策)|(?:其余|其他).{0,12}固定(?:为|不变)",q):
        return gap("请明确其余单位在每个比较端沿用哪一套安排。")
    if not all(fields[k].get("evidence") and not fields[k].get("invalid_citations") for k in reading.FIELDS):
        return gap("请核对网络、分配、暴露和两端所对应的原文。")
    if not any(e["source_id"]=="question" and question_arms(e["quote"],rule)==pair for e in fields["contrast"]["evidence"]):
        return gap("请确认原题所比较的两个事件和相减方向。")
    proposed=tuple(proposed_arm(c.get(key),rule) for key in ("left","right"))
    if pair!=proposed:
        return gap("模型摘出的比较两端与原题不一致。请确认两端的本单位状态、邻居状态和相减方向。")
    table=bound_network(case,network)
    nodes=list(table.nodes)
    docs=[r for r in lines if r["source_id"] not in ("question","uploaded_network")]
    if any(r["source_id"].startswith("user_reply_") and re.search(r"改为|改用|换成|改问|只看|颠倒|反过来",r["quote"]) for r in docs):
        return gap("补充说明更改了比较内容，请明确这次采用的评价对象和两个比较端。")
    g=fields["network"]["proposed"]
    if table.completeness!="COMPLETE" or not re.search(PRE,table.description) or re.search(r"事后|处理后|试点后|抽签后|实施后|尚未|不确定",table.description):
        return gap("请提供本次分析使用的处理前完整关系表，或说明已有关系的覆盖范围与记录时期。")
    if not all(g.get(k) is True for k in ("pre_treatment","complete","undirected")):
        return gap("请核对模型摘出的网络与上传关系表的方向、时期及完整性。")
    for key,actual in (("nodes",nodes),("edges",list(table.edges))):
        value=g.get(key)
        if type(value) is int:
            agrees=value==len(actual)
        elif isinstance(value,list):
            if key=="nodes":
                agrees=all(isinstance(n,str) for n in value) and len(value)==len(actual) and set(value)==set(actual)
            else:
                agrees=(len(actual)==len(value) and all(isinstance(e,(list,tuple)) and len(e)==2 and all(isinstance(n,str) for n in e) for e in value)
                        and {frozenset(e) for e in actual}=={frozenset(e) for e in value})
        else:
            agrees=value is None
        if not agrees:
            return gap("请核对模型摘出的名单或关系与上传文件的差异。")
    if any(re.search(r"(?:关系|邻居名单|网络|边表).{0,18}(?:试点后|事后|抽签后|处理后)|(?:试点后|事后|抽签后|处理后).{0,18}(?:调查|才登记|才记录).{0,9}(?:关系|邻居)|(?:关系表|网络).{0,8}(?:不完整|互相矛盾)",r["quote"]) for r in docs):
        return gap("关系材料的覆盖范围或时期存在分歧，请核准本次使用的处理前完整关系表。")
    if len(nodes)>256:
        return None
    group=group_from_source(q,lines,nodes,c.get("population"))
    if group is None:
        return gap("请核对评价名单以及各单位在平均结果中的权重。")
    exposure_quotes=[e["quote"] for e in fields["exposure"]["evidence"]]
    source_rule={"majority":MAJORITY,"any":ANY,"count":r"确切人数|精确人数|精确邻居人数|实际人数|准确人数|个数|确切数量"}
    if not any(re.search(source_rule[rule],line) for line in exposure_quotes) or any(
            re.search(r"至少一半|一半(?:及|或)以上|平票.{0,6}(?:记1|算高)|不再按|改用",s)
            for s in exposure_quotes+[r["quote"] for r in docs if re.search(PEERS,r["quote"])]):
        return gap("请核对原题所用的邻居暴露规则及临界值的归类。")
    design_rows=[e["quote"] for e in fields["assignment"]["evidence"]]
    corpus="。".join(r["quote"] for r in docs)
    variable=treatment_name(row["quote"],design_rows,corpus)
    invitation_design=re.search(r"(?:邀请|鼓励|资格).{0,18}(?:随机|抽签)|(?:抽签|随机).{0,18}(?:邀请|鼓励|资格)|可拒绝|未依从|自行决定",corpus)
    design_lines=[r["quote"] for r in lines if r["source_id"]!="uploaded_network" and re.search(r"抽签|概率|机会|分配变量|无放回|固定名额",r["quote"])]
    try:
        proposal=fields["assignment"]["proposed"]
        law=actual_law(proposal,design_rows,nodes)
        complete_law=actual_law(proposal,list(dict.fromkeys(design_rows+design_lines)),nodes)
    except (KeyError,TypeError,ValueError,ArithmeticError):
        law=complete_law=None
    if (not variable or not law or complete_law!=law
            or invitation_design and not re.search(r"获邀|收到邀请",variable)
            or re.search(r"两份.{0,8}(?:冲突|矛盾)|共用.{0,6}(?:签|硬币)|尚不清楚.{0,12}抽签",corpus)):
        return gap("请确认实际随机分配的变量及联合分配规则，并说明它是否直接决定了题中所比较的处理。")
    labels=source_labels(target,q,docs)
    if not labels:
        return gap("请核对这次比较的结果指标与观察时期。")
    cited={key:fields[key]["evidence"] for key in reading.FIELDS}
    return solve_materials(case,table,group,row,pair,rule,law,variable,labels,lines,docs,cited)


def solve_materials(case, table, group, row, pair, rule, law, variable, labels, lines, docs, cited, *,
                    population_rows=(), remaining_row=None, population_unavailable=False):
    nodes=list(table.nodes)
    corpus="。".join(r["quote"] for r in docs)
    interface=[r for r in docs if re.search(r"(?:允许|可(?:以)?查询|可用|可(?:以)?使用|可提供).{0,45}(?:平均(?:评分|结果)|条件均值|条件平均|均值)",r["quote"])]
    catalog_rows=[r for r in interface if re.search(r"(?:每|各|逐)(?:一家|家|个|人|站|校|单位|节点|对象|店)",r["quote"])]
    covers=r"(?:原题|所问|比较)?(?:的)?(?:两端|两个事件|两种比较情形)|(?:每个|各|所有)(?:有支持的?)?(?:事件|局部情形|状态)"
    if rule!="count":
        covers+=r"|四种(?:情形|状态|组合)|四个(?:臂|状态)"
    missing=None
    if population_unavailable or not (population_rows or any(re.search(covers,r["quote"]) for r in catalog_rows)) or re.search(
            r"(?:不可|不能|禁止|不准|无法)(?:以)?(?:用于|使用|查询|提供).{0,18}(?:逐|每|各|条件均值)|只有(?:全体|总体|无条件)(?:平均|均值)|(?:仅|只)(?:对部分|含部分|能查一端|能查左端|能查右端|提供一端).{0,24}(?:均值|平均)",corpus):
        missing="请说明能否按原分配查询评价对象在两个事件下各自的总体条件均值。"
    remaining=remaining_row or next((r for r in lines if re.search(ORIGINAL,r["quote"])),None)
    if not remaining:
        return None
    assumptions=[]
    topics={"full_vector_randomization":r"潜在|整单随机|完整分配.{0,10}独立|名单.{0,8}随机",
            "consistency":r"一致性|观测.{0,14}实际安排|记录.{0,14}实际名单",
            "finite_conditional_first_moments":r"有限(?:数值|期望|一阶矩|均值)|(?:均值|评分|期望).{0,12}(?:无限|有限|发散)"}
    for key,(label,pattern) in PREMISES.items():
        candidates=[r for r in docs if re.search(pattern,r["quote"])]
        if not candidates or any(re.search(NEG_SCI+r"|只针对|仅对|仅限|部分(?:人|对象|单位|店|站|名单|安排)|调整后",r["quote"]) for r in candidates) or any(
                re.search(NEG_SCI,r["quote"]) and re.search(topics[key],r["quote"]) for r in docs):
            missing=missing or ("请说明材料对“"+label+"”的依据或适用范围。")
            continue
        assumptions.append(dict(code=key,label=label,**candidates[0]))
    outcomes,time=labels
    contrast=dict(kind="original_local",scope="whole" if group==nodes else "subgroup",population=group,
                  weights=[str(Fraction(1,len(group)))]*len(group),ends=[list(p) for p in pair],
                  variable=variable,outcome=outcomes,time=time,remaining=remaining["quote"],
                  intervention=str(pair[0]),reference=str(pair[1]))
    facts=dict(contrast=contrast,network=dict(basis="edges",nodes=nodes,edges=list(table.edges),pre=True,complete_for=nodes,roster_complete=True),
               exposure=dict(kind=rule),assignment=dict(law,variable=variable),information=dict(query="event_mean",same_population=True),
               science=dict(random_full=not missing,consistent=not missing,evidence=[dict(kind="other",subject=p["label"],statement=p["quote"],source=p["source_id"],quote=p["quote"]) for p in assumptions]))
    if missing:
        from . import network_event_handoff
        result=network_event_handoff.solve(facts,design_only=True)
        if result is None:
            return gap(missing)
    else:
        result=solve_reviewed(facts)
    if result is None:
        return None
    result["proof"].update(binder="uploaded-network-comparison/1",network_reference=table.token,assignment=facts["assignment"],
                           source_sha256=digest(case["sources"]),cited_network_fields=cited,
                           source_spans=[row,remaining,*catalog_rows,*population_rows,*assumptions])
    return dict(result=result,premises=assumptions)


def check_review(sheet, review):
    if not isinstance(review,dict) or set(review)!={"binding","authority","decisions"} or review["binding"]!=sheet["binding"]:
        raise ValueError("STALE_NETWORK_CONDITIONS")
    if review["authority"] not in ("SYNTHETIC_TEST","EXTERNAL_RESEARCH_REVIEW"):
        raise ValueError("INVALID_NETWORK_REVIEW_AUTHORITY")
    ds=review["decisions"]
    keys={item['code'] for item in sheet['items']} if sheet.get('kind')=='source_policy' else set(PREMISES)
    if not keys or not isinstance(ds,dict) or set(ds)!=keys or any(v not in ("ADOPTED","UNSURE","DECLINED") for v in ds.values()):
        raise ValueError("THREE_EXPLICIT_NETWORK_DECISIONS_REQUIRED")


def apply(case,draft,network,report,review,*,source_first=False,extended=False,source_scope=False,natural_sources=False,scope_resolution=None):
    reading_report=report.get("network_reading") or {}
    if (not network or report.get("proof") or reading_report.get("unresolved_design_sources")
            or not source_first and report.get("clarification_questions") and not reading_report):
        if review is not None:
            raise ValueError("NETWORK_REVIEW_NOT_AVAILABLE")
        return
    try:
        binding=None
        if scope_resolution:
            from . import network_natural_sources
            binding=network_natural_sources.bind(case,bound_network(case,network),scope_resolution=scope_resolution)
        elif source_first and len(answer_items(draft))<=1:
            from .uploaded_network_sources import from_materials
            binding=from_materials(case,network,extended=extended,source_scope=source_scope)
            if natural_sources and (not binding or "result" not in binding):
                from . import network_natural_sources
                binding=network_natural_sources.bind(case,bound_network(case,network)) or binding
        if binding is None and not scope_resolution and (reading_report or not report.get("clarification_questions")):
            binding=bind(case,draft,network,report)
    except (TypeError,KeyError,ValueError,ArithmeticError):
        binding=None
    if binding is None or "question" in binding:
        if review is not None:
            raise ValueError("NETWORK_REVIEW_NOT_AVAILABLE")
        if binding:
            report.pop("parts",None)
            report.update(decision="WITHHELD",effective_answer=None,conditional_answer=None,
                          clarification_questions=[binding["question"]])
            report["checks"].append(dict(code="UPLOADED_NETWORK_SOURCE_GAP",state="UNCHECKED",detail=binding["question"]))
        return
    result,conditions=binding["result"],binding["premises"]
    answer=result["answer"]
    report.pop("parts",None)
    report.update(proof=result["proof"],conditional_answer=deepcopy(answer),effective_answer=deepcopy(answer),
                  decision="CONDITIONAL_RESULT",clarification_questions=[])
    report["checks"].append(dict(code="UPLOADED_NETWORK_SUPPORT",state="CHECKED",
        detail="已将原文比较两端与上传关系表绑定，并按原分配逐人重算两端的联合支持。"))
    if answer["status"]!="POINT":
        if review is not None:
            raise ValueError("NETWORK_REVIEW_NOT_AVAILABLE")
        return
    sheet=dict(case_id=case.get("case_id"),case_sha256=digest(case),draft_sha256=report["draft_sha256"],items=conditions)
    sheet["binding"]=digest([sheet.copy(),report["proof"],answer["target"],answer["estimate_handoff"]])
    report["condition_review"]=sheet
    if review is not None:
        check_review(sheet,review)
        report["review_record"]=deepcopy(review)
        if all(v=="ADOPTED" for v in review["decisions"].values()):
            report.update(scientific_approval=review["authority"]=="EXTERNAL_RESEARCH_REVIEW",
                          estimation_handoff_allowed=True,decision="CORRECTED" if (draft or not source_first) and any(
                              a.get("status")!="POINT" for a in answer_items(draft)) else "CONDITIONAL_RESULT")
            return
    pending=report["effective_answer"]
    pending.update(status="NEEDS_INPUT",value=None,estimate_handoff={"mode":"STOP","queries":[]},
                   reason="采用所列三项前提时，原比较可点识别。研究者尚未逐项采用全部前提。")
    report["decision"]="PREMISES_REQUIRED"
