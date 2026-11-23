"""Read source-bound network facts without granting scientific approval.

Exact spans establish provenance. Only independently decoded values can enter
the native joint-support calculation. Unsupported wording stays reviewable.
"""
import re
from fractions import Fraction

from . import direct_network as native

FIELDS = ("network", "exposure", "assignment", "contrast")
NUMBER = r"(?:\d+/\d+|\d*\.\d+|\d+)(?:%)?"
UNIT = r"[\w-]{1,24}"
NUMS = dict(zip("零一二三四五六七八九十", range(11)))
RULE = {"any": native.GROUP_E5, "count": native.GROUP_E4, "majority": native.GROUP_E1}
CUES = {
    "network": r"邻居|邻站|邻接|联系人|邻边|相连|互连|搭档|边表|好友|合作关系|朋友关系|伙伴|关系网|联系图",
    "exposure": r"邻|同伴|伙伴|好友|合作门店|朋友|同组其他|平票|邻接",
    "assignment": r"抽签|随机|抽取|自选|分配|无放回|独立.*机会|抛硬币|等机会|名额",
    "contrast": r"比较|相对|相比|减|差|水平|多少|影响|相对于|效果|能否",
}


def network_case(case):
    texts = [case["business_question"]] + [s["text"][:14000] for s in case["sources"]]
    return any(re.search(r"干扰|同伴|邻居|邻站|邻港|邻接|邻边|合作门店|合作联系人|伙伴|朋友|相互影响|互相影响|溢出|搭档|相连|联系图|network.edges|interference|spillover|neighbou?r", t, re.I) for t in texts)


def records(case):
    return [("question", case["business_question"])] + [(s["source_id"], s["text"]) for s in case["sources"]]


def sentences(items):
    return [(key, match.group().strip()) for key, text in items
            for match in re.finditer(r"[^。！？；\n]+", text) if match.group().strip()]


def number(text):
    return Fraction(text[:-1]) / 100 if text.endswith("%") else Fraction(text)


def names(text):
    return [n.strip() for n in re.split(r"[、,，和及与]", text) if n.strip()]


def fact_evidence(case, draft):
    """Keep model claims separate from checked facts and identify absent legacy fields."""
    indexed = dict(records(case))
    proposed = draft.get("network_facts") if isinstance(draft, dict) else None
    supplied = isinstance(proposed, dict)
    lines = sentences(records(case))
    facts = {}
    for key in FIELDS:
        item = proposed.get(key) if supplied else None
        item = item if isinstance(item, dict) else {}
        citations = item.get("evidence", [])
        if isinstance(citations, dict):
            citations = [citations]
        spans, failures = [], 0
        for citation in citations[:20] if isinstance(citations, list) else []:
            if not isinstance(citation, dict):
                failures += 1
                continue
            sid, quote = citation.get("source_id"), citation.get("quote")
            if not isinstance(sid, str) or not isinstance(quote, str) or not quote.strip() or quote not in indexed.get(sid, ""):
                failures += 1
                continue
            start = indexed[sid].index(quote)
            spans.append(dict(source_id=sid, quote=quote, start=start, end=start+len(quote)))
        # Source-only references are useful on replay and never attributed to the model.
        source_spans = []
        for sid, line in lines:
            if re.search(CUES[key], line) and (key != "contrast" or sid == "question"):
                start = indexed[sid].find(line)
                source_spans.append(dict(source_id=sid, quote=line, start=start, end=start+len(line)))
                if len(source_spans) == 3:
                    break
        facts[key] = dict(proposed=item.get("value"), evidence=spans, invalid_citations=failures,
                          source_candidates=source_spans, state="CITED" if spans else "UNVERIFIED")
    return dict(origin="model_and_source" if supplied else "source_only_replay", fields=facts)


def signed(lines, yes, no=r"拒绝|尚未确认|不假设|不能确认|无法确定|不能保证|不满足|未承诺"):
    return next(((sid, line) for sid, line in lines if re.search(yes, line) and not re.search(no, line)), None)


def local_graph(text):
    roster = re.search(r"(?:全体名单|完整名单|登记名单|完整名册|值班名册)(?:按顺序)?(?:为|是|包括)?[（(：:]\s*([^）)。；\n]+)", text)
    if not roster:
        return None
    nodes = names(roster[1])
    if not 1 <= len(nodes) <= 128 or len(set(nodes)) != len(nodes) or not all(re.fullmatch(UNIT,n) for n in nodes):
        return None
    edge_list = re.search(r"(?:全部(?:不分方向的|无向的?)?(?:合作)?(?:联系人|联系|边|连线|邻边)|所有无向联系)(?:只有|仅有|为|是|包括|如下)?[：:]?\s*([^。；\n]+)", text)
    if not edge_list or not re.search(r"不分方向|无向|双向|互为",text):
        return None
    edges = []
    raw = edge_list[1].strip()
    if raw not in ("无","没有","空"):
        for part in re.split(r"[、，,]", raw):
            pair = re.fullmatch(r"(.+?)(?:与|和|—|↔|连着|相连于)(.+)", part.strip())
            if not pair or pair[1] not in nodes or pair[2] not in nodes or pair[1] == pair[2]:
                return None
            edges.append((pair[1], pair[2]))
    if len(set(map(frozenset, edges))) != len(edges):
        return None
    return native.types.NetworkExposureSpec(network_id="source-prose", node_ids=nodes, undirected_edges=edges)


def focal_graph(text):
    # Under independent assignment all unlisted non-neighbors integrate out.
    # The egocentric enumeration cannot replace the full sampling frame for a quota.
    matches=re.findall(r"(?:抽签前|干预前|处理前|试点前|基线时)[，, ]*([A-Za-z0-9\u4e00-\u9fff]{1,12}?)(?:的)?(?:全部|所有|唯一)(?:直接)?(?:联系人|邻居|搭档|合作伙伴)(?:只有|仅有|为|是|只有以下)[：:]?\s*([^，,。；\n]+)", text)
    if len(matches)!=1 or not re.search(r"互为|双向|无向|不分方向",text):
        return None,None
    focus,raw=matches[0]
    peers=names(raw)
    if not peers or focus in peers or len(peers)>24 or len(set(peers))!=len(peers) or not all(re.fullmatch(UNIT,n) for n in peers):
        return None,None
    return focus,native.types.NetworkExposureSpec(network_id="source-focal",node_ids=[focus,*peers],undirected_edges=[(focus,n) for n in peers])


def assignment(text, nodes):
    fixed = re.findall(r"等(?:概率|机会)(?:无放回)?(?:抽取|选出|抽出|选定)\s*(\d+|[一二三四五六七八九十])\s*(?:人|家|个|站|处|条)", text)
    independent = bool(re.search(r"各(?:人|站|店|线|自|单位).{0,8}独立|彼此独立|相互独立|各自抛.{0,4}硬币|独立(?:Bernoulli|抽签|投币)", text, re.I))
    if fixed and not independent and len(set(fixed)) == 1:
        m = int(fixed[0]) if fixed[0].isdigit() else NUMS[fixed[0]]
        return native.types.CompleteRandomizationDesignV1(m=m) if 0 <= m <= len(nodes) else None
    if not independent or fixed:
        return None
    matched = re.search(r"(?:名单|名册|登记)(?:的)?顺序[，, ]*(?:每[人家站处]|各单位)?(?:入选|抽中|启动)?概率(?:分别|依次)?(?:为|是)[：:]?\s*("+NUMBER+r"(?:[、，,]\s*"+NUMBER+r")*)",text)
    ps = []
    if matched:
        ps = [number(v.strip()) for v in re.split(r"[、，,]",matched[1])]
    else:
        common = re.search(r"(?:每(?:人|站|家|处|个单位)|各自)(?:的)?(?:抽中|入选|启用)?(?:的)?(?:概率|机会)(?:均|都)?(?:为|是)\s*("+NUMBER+r")", text)
        if common:
            ps = [number(common[1])] * len(nodes)
        else:
            for node in nodes:
                hits = re.findall(re.escape(node)+r"(?:单独)?(?:的)?(?:抽中|入选|启动|获选)(?:的)?概率(?:为|是)?\s*("+NUMBER+r")", text)
                if len(set(hits)) != 1:
                    return None
                ps.append(number(hits[0]))
    if len(ps) == len(nodes) and all(0 <= p <= 1 for p in ps):
        return native.types.HeterogeneousBernoulliDesignV1(propensities=dict(zip(nodes,map(str,ps))))
    return None


def exposure(text):
    matches = []
    for name, pattern in (("count", r"精确邻居人数|逐人计数|按实际人数计|记.{0,8}邻居.{0,7}的确切人数|记为.{0,6}邻居.{0,6}人数"),
                          ("majority", r"严格(?:超过一半|过半)|超过半数.{0,12}平票|平票.{0,9}(?:低|不算)"),
                          ("any", r"至少(?:一[位名个家站]?|有一[位名个]?).{0,12}(?:时|即|就|算|则|记|为).{0,8}(?:1|有|高)|只要.{0,10}(?:邻居|伙伴).{0,8}(?:就|便)")):
        if re.search(pattern,text):
            matches.append(name)
    return matches[0] if len(matches) == 1 else None


def pair_terms(q):
    coded = native.contrasts(q)
    if len(coded) == 1:
        return coded[0][1:]
    if re.search(r"分别|另(?:一|外)|第二问|两项目标", q):
        return None
    own = re.search(r"(?:本人|本站|本店|自己|自身|本组)(?:保持|一直|仍)?(未|不|没有|已|也|正)(?:领|启|处|用|获|开|入|选|参|做|接|抽)", q)
    if not own:
        return None
    sides = re.split(r"相对于|相比于|相比|相对|减(?:去)?|对比", q)
    if len(sides) != 2 or re.search(r"减少量|下降量|后者减前者|倒过来",q):
        return None
    def state(side):
        if re.search(r"无人|没有(?:任何|一[个名位])?(?:邻|伙伴)|无邻|零(?:人|个|位)|未有",side):
            return 0
        if re.search(r"至少一|有(?:伙伴|邻居)|严格过半|超过半数",side):
            return 1
        count = re.search(r"(?:恰好|正好|恰有|恰为)(\d+|[零一二两三四五六七八九十])",side)
        if count:
            val=count[1]
            return int(val) if val.isdigit() else 2 if val=="两" else NUMS[val]
    a = int(own[1] in ("已","也","正"))
    left,right = map(state,sides)
    return ((a,left),(a,right)) if None not in (left,right) and left != right else None


def focal_units(q, nodes):
    m=re.search(r"仅评价【([^】]+)】",q)
    if m:
        group = names(m[1])
    elif re.search(r"(?:全体|全部登记|全部单位|每[站家人]).{0,12}(?:同等|等权|一样重)|(?:等权).{0,10}(?:全体|全部)", q):
        group = list(nodes)
    else:
        hits=[n for n in nodes if re.search(r"(?:只看|只评价|仅看|仅评价|只关心|只评|只算|只考察)(?:焦点)?[“「【]?"+re.escape(n)+r"(?:[”」】]|站|本人|一处|一人|这个|，|、|[。；：:\s])",q)]
        group=hits if len(hits)==1 else []
    return group if group and len(set(group))==len(group) and set(group)<=set(nodes) else []


def target_labels(q):
    for patt in (r"求(.{1,35}?)差", r"对([^，。？?]{2,30}?)(?:的(?:平均|均值|变化|影响)|有何影响)",r"(?:关心|衡量|考核)([^，。？?]{2,30})"):
        m=re.search(patt,q)
        if m:
            label=m[1].strip()
            period=re.search(r"期末|本月|周末|月底|当季|下周|本季|本周|季末|学年末|年末|次日|次月|月底|本期|当月", q)
            return label,period[0] if period else None
    return None,None


def underlying_conditions(lines):
    independent = signed(lines,r"(?:名单|分配|安排).{0,28}(?:独立于.{0,6}潜在|潜在.{0,20}独立)|潜在.{0,20}(?:与|同).{0,8}(?:名单|安排|分配).{0,6}独立")
    consistent = signed(lines,r"完整(?:安排|名单).{0,6}一致|(?:实际|记录|观察).{0,20}(?:反映|对应|等于).{0,15}(?:潜在|完整安排)|采用.{0,12}一致性")
    return independent,consistent


def source_solution(case, table):
    """Conditional local contrast only. Other scientific targets retain their own route."""
    if table is not None:
        return None
    q=case["business_question"]
    lines=sentences(records(case))
    t="\n".join(s["text"] for s in case["sources"])
    if (len(t)>90000 or re.search(r"拒绝|不(?:再|是)等权|改用|后测网络|处理后才|基于处理后的|加权而非等权|名额通知|第一阶段|第二阶段|获邀|邀请|自选|并非随机|不保证|无法确认|不能保证|不假设|更正|更改|矛盾",t)
            or not re.search(r"原.{0,22}(?:设计|分配|抽签|抽取).{0,15}条件|条件分布平均其余",q+t)):
        return None
    if any(s["source_id"].startswith("user_reply_") and not re.fullmatch(r"(?:补充(?:说明)?[：:])?(?:本次|实际|我们)?在完整名单中等概率无放回抽取\d+人[。.]?",s["text"].strip()) for s in case["sources"]):
        return None
    pre = signed(lines,r"处理前|试点前|干预前|抽签前|季前.{0,8}固定|事先固定|基线.{0,5}固定")
    # The dated statement must bind the graph, not an unrelated pretreatment variable.
    if not pre or not re.search(CUES["network"]+"|名册",pre[1]):
        return None
    graph=local_graph(t)
    ego=None
    if graph is None:
        ego,graph=focal_graph(t)
    if graph is None:
        return None
    nodes=list(graph.node_ids)
    group=focal_units(q,nodes)
    pair=pair_terms(q)
    kind=exposure(t)
    y,period=target_labels(q)
    if not (group and pair and kind and y and period):
        return None
    if len(group)>1 and not signed(lines,r"等权|每人同等权重"):
        return None
    if kind!="count" and any(s not in (0,1) for _,s in pair):
        return None
    d=assignment(t,nodes)
    if ego and (group!=[ego] or not isinstance(d,native.types.HeterogeneousBernoulliDesignV1)):
        return None
    ind,con=underlying_conditions(lines)
    if not (ind and con):
        return None
    declared_gap=signed(lines,r"分配设计待补|尚不清楚.{0,8}(?:抽签|分配)|未记录.{0,8}(?:抽签办法|联合分配)")
    if declared_gap and d is not None and not any(s["source_id"].startswith("user_reply_") for s in case["sources"]):
        return None
    if not d and not declared_gap:
        return None
    means_known=signed(lines,r"每个有支持.{0,30}(?:总体条件期望|总体条件均值)|正概率.{0,20}总体条件均值|可符号.{0,12}总体条件|可调用.{0,15}总体条件均值")
    specific=re.search(r"两个(?:目标)?(?:局部状态|比较端|事件)的?总体条件(?:均值|期望)(?:按题目顺序|依次|分别)(?:为|是)\s*("+NUMBER+r")[、，,]\s*("+NUMBER+r")(?![\d/])",t)
    if specific and len(group)!=1:
        return None
    if not means_known and not specific and not declared_gap:
        return None
    if means_known and re.search(r"(?:均值|期望|风险).{0,10}(?:为|是)[：:]?\s*[\d.]",t) and not specific:
        return None
    joint=native.support_record(graph,d,RULE[kind],group,pair) if d else {}
    left,right=pair
    unsupported=[(n,a,s) for n in group for a,s in pair if joint and joint[n][f"{a},{s}"]=="0"]
    gap="请补充原分配规则或各份完整安排的概率，以计算两个比较端的联合支持和其余安排的条件权重。"
    status="NEEDS_INPUT" if not d else "UNDEFINED" if unsupported else "POINT"
    expr=(gap if not d else f"{unsupported} 的原设计联合概率为零，所要求的条件分配没有定义，须保留原评价名单。" if unsupported else
          f"令 μ_i(a,s)=E[Y_i | T_i=a,S_i=s]。按原设计条件分布，目标为 (Σ_i [μ_i{left} − μ_i{right}])/{len(group)}，i 遍历指定评价名单。")
    value=str(number(specific[1])-number(specific[2])) if status=="POINT" and specific else None
    scope="whole" if not ego and set(group)==set(nodes) else "subgroup"
    asm=[dict(kind="random_assignment" if label=="完整安排独立" else "other",subject="完整处理安排" if label=="完整安排独立" else label,statement=line,source=sid,quote=line)
         for label,item in (("完整安排独立",ind),("完整安排一致性",con),("有限均值",signed(lines,r"期望有限|均值有限|有限均值|有限期望")),("总体条件均值",means_known)) if item for sid,line in [item]]
    answer=dict(target=dict(quantity="difference",scope=scope,population=group,intervention=str(left),reference=str(right),
               outcome=y,time=period,remaining="在每端按原设计条件平均其余分配"), status=status,functional=expr,value=value,assumptions=asm,
               estimate_handoff=dict(mode="ESTIMATE_POINT" if status=="POINT" else "STOP",scope=scope,population=group,
                  variables=["Y_i","T_i","S_i"],operator=expr,support=joint,exposure=native.RULES[RULE[kind]]),
               reason="完整安排独立与一致性将各端的原设计条件政策均值化为观察条件均值。" if status=="POINT" else expr)
    values=dict(network=dict(nodes=nodes,edges=[list(p) for p in graph.undirected_edges]),exposure=kind,
                assignment=d.model_dump(mode="json") if d else None,contrast=dict(population=group,left=list(left),right=list(right)))
    if ego:
        values["network"]["focal_only"]=ego
    return dict(answer=answer,values=values,proof=dict(method="LOCAL_DESIGN_CONDITIONAL_MEAN",joint_probabilities=joint,
                source_sha256=native.sha(case["sources"]),design=values["assignment"],exposure=native.RULES[RULE[kind]],
                population=group,checked_by="source prose, native SupportEngine and independent design-specific arithmetic" if joint else None),
                questions=[gap] if not d else [])


def reported_events(case):
    """Accept protected edges only with an explicitly equivalent event dictionary."""
    q=case["business_question"]
    text="\n".join(s["text"] for s in case["sources"])
    pairs=pair_terms(q)
    focal=re.search(r"仅评价【([^】、]+)】",q)
    if not (pairs and focal and len(case["sources"])==1 and native.equivalent_exposure_reported(text)
            and signed(sentences(records(case)),r"季前关系固定|预先固定|处理前.{0,8}固定")
            and re.search(r"能对所有可能名单精确判定|完整设计支持上逐一判定",text)
            and re.search(r"按原(?:来的)?(?:分配|设计).{0,8}条件|原设计的条件分布",text+q)):
        return None
    if re.search(r"不适用|已撤回|尚待核实|可能有误|更正|拒绝|并非随机",text):
        return None
    # Tie the order of both conditional means to the order of the source events.
    event=re.search(re.escape(focal[1])+r"本人未处理且有邻居获处理的联合概率为("+NUMBER+
                    r")[，,]无邻居获处理的联合概率为("+NUMBER+r")[。；]\s*两个事件的总体条件([^。；\n]*?)均值分别是("+NUMBER+
                    r")和("+NUMBER+r")[。；]",text)
    y,period=target_labels(q)
    if not (event and y and period and pairs in (((0,1),(0,0)),((0,0),(0,1)))):
        return None
    ps={(0,1): number(event[1]),(0,0): number(event[2])}
    if min(ps.values())<=0 or sum(ps.values())>1:
        return None
    lines=sentences(records(case)); ind,con=underlying_conditions(lines)
    if not ind or not (con or signed(lines,r"实际.{0,10}一致")):
        return None
    values={(0,1):number(event[4]),(0,0):number(event[5])}
    left,right=pairs; m=focal[1]; joint={m:{f"{a},{s}":str(p) for (a,s),p in ps.items()}}
    op=f"E[Y_{m}|(T,S)={left}] − E[Y_{m}|(T,S)={right}] = {values[left]} − {values[right]}"
    facts=dict(contrast=dict(population=[m],left=list(left),right=list(right)),exposure="any")
    ans=dict(status="POINT",target=dict(quantity="difference",scope="subgroup",population=[m],intervention=str(left),reference=str(right),outcome=y,time=period,remaining="原设计条件分布"),
             functional=op,value=str(values[left]-values[right]),assumptions=[dict(kind="other",subject="原设计及登记条件",quote=line,statement=line,source=sid) for sid,line in lines if sid!="question"],
             estimate_handoff=dict(mode="ESTIMATE_POINT",scope="subgroup",population=[m],variables=["Y","T","S"],support=joint,operator=op),
             reason="登记系统对所有可能名单给出了同一事件的精确标签和联合概率，原文明确报告两端总体条件均值。")
    return dict(answer=ans,values=facts,proof=dict(method="REPORTED_LOCAL_EVENT_MEANS",source_sha256=native.sha(case["sources"]),joint_probabilities=joint,probability_origin="reported_not_recomputed"),questions=[])


def proposed_model(fields):
    """Compute a conditional sensitivity check from cited proposed inputs.

    This branch never substitutes a scientific answer or grants a release.
    """
    if not all(x["evidence"] and not x["invalid_citations"] and isinstance(x["proposed"],dict) for x in fields.values()):
        return None
    g,e,d,c=(fields[k]["proposed"] for k in FIELDS)
    if not all(g.get(k) is True for k in ("pre_treatment","complete","undirected")):
        return None
    nodes,edges=g.get("nodes"),g.get("edges")
    if not isinstance(nodes,list) or not 1<=len(nodes)<=32 or not isinstance(edges,list) or len(edges)>256:
        return None
    if any(not isinstance(n,str) or not n or len(n)>80 for n in nodes) or len(set(nodes))!=len(nodes):
        return None
    if any(not isinstance(pair,list) or len(pair)!=2 or any(n not in nodes for n in pair) or pair[0]==pair[1] for pair in edges):
        return None
    net=native.types.NetworkExposureSpec(network_id="cited-proposal",node_ids=nodes,undirected_edges=edges)
    if d.get("kind")=="independent" and isinstance(d.get("probabilities"),dict) and set(d["probabilities"])==set(nodes):
        ps={n:str(number(str(p))) for n,p in d["probabilities"].items()}
        design=native.types.HeterogeneousBernoulliDesignV1(propensities=ps)
    elif d.get("kind")=="fixed" and type(d.get("quota")) is int and 0<=d["quota"]<=len(nodes):
        design=native.types.CompleteRandomizationDesignV1(m=d["quota"])
    else:
        return None
    group=c.get("population")
    arms=[c.get("left"),c.get("right")]
    if (e.get("kind") not in RULE or not isinstance(group,list) or not group or any(n not in nodes for n in group)
            or len(set(group))!=len(group) or any(not isinstance(a,list) or len(a)!=2 or
                any(type(k) is not int for k in a) or a[0] not in (0,1) or a[1]<0 or
                (e["kind"]!="count" and a[1]>1) for a in arms)):
        return None
    return native.support_record(net,design,RULE[e["kind"]],group,[tuple(a) for a in arms])


def equals_source(key, proposed, checked):
    if not isinstance(proposed,dict):
        return None
    if key=="exposure":
        return proposed.get("kind")==checked if "kind" in proposed else None
    if key=="contrast":
        if not all(isinstance(proposed.get(k),list) for k in ("population","left","right")):
            return None
        return (set(proposed["population"])==set(checked["population"]) and
                proposed["left"]==checked["left"] and proposed["right"]==checked["right"])
    if key=="network" and checked.get("focal_only"):
        return None
    if key=="network" and isinstance(proposed.get("nodes"),list) and isinstance(proposed.get("edges"),list):
        return (all(proposed.get(k) is True for k in ("pre_treatment","undirected","complete"))
                and set(proposed["nodes"])==set(checked["nodes"])
                and set(map(frozenset,proposed["edges"]))==set(map(frozenset,checked["edges"])))
    if key=="assignment" and checked:
        if "propensities" in checked and isinstance(proposed.get("probabilities"),dict):
            return proposed.get("kind")=="independent" and {k:number(str(v)) for k,v in proposed["probabilities"].items()}=={k:number(str(v)) for k,v in checked["propensities"].items()}
        if "m" in checked and proposed.get("quota") is not None:
            return proposed.get("kind")=="fixed" and proposed["quota"]==checked["m"]
    return None


def apply(case, draft, report, table=None, *, network_focus=False):
    if (not network_focus and not network_case(case)) or not isinstance(draft,dict) or not draft:
        return
    reading=fact_evidence(case,draft)
    report["network_reading"]=reading
    fields=reading["fields"]
    try:
        conditional=proposed_model(fields)
        if conditional is not None:
            reading["conditional_joint_support"]=conditional
            reading["conditional_support_scope"]="按模型摘录的四项取值计算；逐字引文不能单独证明这些取值。"
    except (ValueError,KeyError,ArithmeticError,TypeError):
        reading["conditional_support_scope"]="所提取的网络参数不足以计算联合支持。"
    # Keep the signed native report for tables, multiple goals, and nonlocal proofs.
    if report.get("proof") or table is not None:
        return
    try:
        result=source_solution(case,table) or reported_events(case)
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
        report["checks"].append(dict(code="SOURCE_PROSE",state="UNCHECKED",detail="原文中的数学参数尚不能验证 ("+type(exc).__name__+")。"))
        return
    if result is None:
        check_internal_support(case, draft, report, reading)
        return
    for k,checked in result["values"].items():
        row=fields[k]
        row["source_value"]=checked
        try:
            match=equals_source(k,row["proposed"],checked)
        except (TypeError,ValueError,KeyError,ArithmeticError):
            match=None
        row["state"]="SOURCE_ONLY" if not row["evidence"] or match is None else "AGREES" if match else "CORRECTED_FROM_SOURCE"
    from .direct_verification import action, answer_items, values_agree
    ans=result["answer"]; parts=answer_items(draft)
    conflict=(len(parts)!=1 or parts[0].get("status")!=ans["status"] or action(parts[0])!=action(ans))
    if not conflict and ans.get("value") is not None:
        conflict=values_agree(parts[0].get("value"),ans["value"]) is False
    if any(r["state"]=="CORRECTED_FROM_SOURCE" for r in fields.values()):
        report["checks"].append(dict(code="EXTRACTION_CONFLICT",state="CONFLICT",detail="摘录取值与可独立解析的原文不同。已按原材料重算，可查看各项引文。"))
    report.update(effective_answer=ans,conditional_answer=ans,proof=result["proof"],clarification_questions=result["questions"],
                  decision="CORRECTED" if conflict else "CONDITIONAL_RESULT")
    if "parts" in report:
        report["draft_parts"]=report.pop("parts")
    report["checks"].append(dict(code="SOURCE_PROSE",state="CHECKED",detail="已按题目顺序核对指定人群、比较两端和原设计条件。联合支持的取得方式见核验记录。"))


def check_internal_support(case, draft, report, reading):
    """Ask about a consequential internal contradiction with comparable joint probabilities."""
    from .direct_verification import answer_items
    checked=reading.get("conditional_joint_support")
    items=answer_items(draft)
    if not checked or len(items)!=1 or items[0].get("status")!="POINT":
        return
    # A verbatim sentence can still be irrelevant to a proposed edge or design.
    # Escalate arithmetic only after independently reconstructing the same inputs.
    t="\n".join(s["text"] for s in case["sources"])
    q=case["business_question"]
    if re.search(r"拒绝|更正|处理后|两个设计|第一阶段|第二阶段|名额通知|获邀|而非|不保证|不同版本",t):
        return
    graph=local_graph(t)
    if graph is None or not signed(sentences(records(case)),r"(?:处理前|试点前|抽签前).*(?:邻|联系|无向)"):
        return
    nodes=list(graph.node_ids); kind=exposure(t); pair=pair_terms(q); pop=focal_units(q,nodes)
    design=assignment(t,nodes)
    if not (kind and pair and pop and design):
        return
    independently=native.support_record(graph,design,RULE[kind],pop,pair)
    values=dict(network=dict(nodes=nodes,edges=list(graph.undirected_edges)),exposure=kind,
                assignment=design.model_dump(mode="json"),contrast=dict(population=pop,left=list(pair[0]),right=list(pair[1])))
    if checked!=independently or not all(equals_source(k,reading["fields"][k]["proposed"],v) for k,v in values.items()):
        return
    answer=items[0]; handoff=answer.get("estimate_handoff")
    claimed=handoff.get("support") if isinstance(handoff,dict) else None
    if not isinstance(claimed,dict):
        return
    discrepancy=[]
    for node, events in checked.items():
        row=claimed.get(node)
        if not isinstance(row,dict):
            continue
        for arm, p in events.items():
            if arm not in row or not isinstance(row[arm],(int,float,str)):
                continue
            try:
                declared=number(str(row[arm]))
            except (ValueError,ZeroDivisionError):
                continue
            expected=number(p)
            # Allow decimal display precision; zero-versus-positive is material.
            if (declared==0)!=(expected==0) or abs(declared-expected)>Fraction(1,100000):
                discrepancy.append(dict(unit=node,event=arm,reported=str(declared),recomputed=p))
    if discrepancy:
        reading["disputed_support"]=discrepancy
        first=discrepancy[0]
        msg=(f"请核对 {first['unit']} 在局部状态 ({first['event']}) 的原设计联合支持。"
             f"原答写 {first['reported']}，按所摘录的网络、暴露映射与分配规则计算为 {first['recomputed']}。"
             "请确认摘录中的分配规则和邻接关系适用于这个比较端。")
        report.update(decision="WITHHELD",effective_answer=None,clarification_questions=[msg])
        report["checks"].append(dict(code="CITED_JOINT_DISAGREEMENT",state="CONFLICT",detail=msg))
