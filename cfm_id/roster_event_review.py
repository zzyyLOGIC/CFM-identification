"""Local design contrast on an exhaustively described undirected graph with isolates."""
import re
from fractions import Fraction
from . import network_event_handoff
from .network_query_binding import RATE, read_rate
from .source_network_review import MissingFacts, ORD, count, evidence, one

NAME=r"[\w\u3400-\u9fff]{1,12}?"
ACTION=r"发(?:放)?(?:优惠)?券|开放|发通知|启用|接种|开灯|参加"
PRE=r"(?:开业|试点|抽签|处理|干预|活动|分配)前|基线|事前"
ISOLATE=r"单干|无邻居|无伙伴|为孤立点|是孤立点"
LOW=r"(?:伙伴|邻居|同伴)(?:全|都|均)(?:不|未|没)|(?:无|没有)(?:任何)?(?:伙伴|邻居|同伴)"
HIGH=r"有[^，。；]{0,12}(?:伙伴|邻居|同伴)|至少一[^，。；]{0,6}(?:伙伴|邻居|同伴)"


def parse_graph(line):
    body=re.split(r"只有|仅有|完整边表(?:为|是)|全部边(?:为|是)",line,maxsplit=1)
    if len(body)!=2 or not re.search(PRE,body[0]):
        raise MissingFacts("请明确原评价名单的处理前完整关系列表，以及哪些单位没有伙伴。")
    nodes=[];edges=[];isolates=set()
    for part in re.split(r"[，,；;]",body[1]):
        part=part.strip()
        edge=re.fullmatch(r"("+NAME+r")(?:与|和|—|↔)("+NAME+r")(?:互通客户|相连|合作|互为伙伴|相邻)?",part)
        isolated=re.fullmatch(r"("+NAME+r")(?:"+ISOLATE+r")",part)
        if isolated:
            name=isolated[1]
            isolates.add(name); nodes.append(name)
        elif edge:
            a,b=edge.groups()
            if a==b or {a,b} in [set(e) for e in edges]:
                raise MissingFacts("请核对关系表中的自环或重复边。")
            nodes.extend([a,b]);edges.append([a,b])
        else:
            raise MissingFacts("请核对完整边表和没有邻居的单位。")
    if not isolates or any(n in isolates for e in edges for n in e):
        raise MissingFacts("孤立单位与边表的记录不一致，请核对。")
    return list(dict.fromkeys(nodes)),edges


def scope(question,nodes):
    if re.search(r"(?:都算|全(?:部|体)).{0,10}(?:同权|等权)|(?:全部|全体).{0,10}(?:平均)",question):
        m=re.search(r"("+ORD+r")(?:间|处|个|家|所|名|座|站)",question)
        if m and count(m[1])!=len(nodes):
            raise MissingFacts("评价单位数与完整关系列表不符，请核对原名单。")
        return nodes
    m=re.search(r"(?:只给|只评(?:价)?|仅评(?:价)?|只看)([^，。；]+)[，,]?(?:各半|等权|同权)",question)
    if m:
        group=re.split(r"、|与|和|及",m[1])
        if group and len(group)==len(set(group)) and set(group)<=set(nodes) and ("各半" not in m[0] or len(group)==2):
            return group
    raise MissingFacts("请明确这次比较包含哪些原单位以及各自权重。")


def role(text):
    return re.sub(r"发(?:放)?(?:优惠)?券","发券",text)


def derive(q,rows):
    text="。".join(r["quote"] for r in rows)
    if not (re.search(ISOLATE,text) and re.search(r"(?:原抽签|原设计|原分配).{0,12}条件",q)
            and re.search(r"伙伴|邻居|同伴",q) and re.search(r"相比|相对于|对比|减",q)):
        return None
    if re.search(r"再问|第二问|同时求|其余.{0,5}固定|后者减前者",q):
        return None
    graph=one(rows,r"(?:只有|仅有|完整边表|全部边).{1,100}(?:"+ISOLATE+r")",message="请说明原题所用的完整处理前关系与孤立单位。")
    nodes,edges=parse_graph(graph["quote"])
    group=scope(q,nodes)
    if re.search(r"不完整|可能遗漏|事后才|处理后才|关系会变|还有.{0,10}(?:边|伙伴)|新增.{0,6}(?:边|伙伴)|不仅",text):
        raise MissingFacts("请确认评价时期内的完整处理前关系，现有材料对边集的记录有分歧。")
    a=re.search(r"(?:自己|本人|本单位)(没|未|不|已)?("+ACTION+r")时",q)
    if not a:return None
    own=int(a[1] in (None,"已"))
    comparison=q[a.end():].split("？")[0]
    parts=re.split(r"相对于|相比|对比|减去|减",comparison,maxsplit=1)
    if len(parts)!=2:return None
    def event(side):
        if re.search(LOW,side):return 0
        if re.search(HIGH,side):return 1
        return None
    pair=[event(side) for side in parts]
    if sorted(str(s) for s in pair)!=["0","1"] or any(role(a[2]) not in role(side) and (not re.search(LOW,side) or re.search(r"启用|开灯|接种|发券",role(side))) for side in parts):
        return None
    exp=one(rows,r"(?:无伙伴|无邻居|孤立.+)(?:者|单位|点)?.{0,12}(?:没有|无人|为0|记0)",message="请说明没有伙伴时的暴露编码。")
    design=one(rows,r"(?:独立.{0,16}(?:抽签|抛|决定)|(?:公平硬币|抽签).{0,14}独立)",message="请说明完整名单的分配规则和各单位的处理概率。")
    statement=design["quote"]
    if role(a[2]) not in role(statement) or re.search(r"共用|共签|有权拒绝|自行决定|未必执行|实际.{0,6}可拒绝|不独立|不公平",text):
        raise MissingFacts("请核对实际分配变量、独立性及它与目标处理的关系。")
    m=re.search(r"(?:各|每).{0,15}?(?:概率|机会)(?:均?为|是)?("+RATE+r")",statement)
    rate=read_rate(m[1]) if m else Fraction(1,2) if "公平硬币" in statement else None
    laws=[r["quote"] for r in rows if re.search(r"独立|共签|抽签概率|处理概率",r["quote"]) and re.search(r"硬币|抽签|概率",r["quote"])]
    if rate is None or len(set(laws))!=1:
        raise MissingFacts("请确认各单位共同适用的原分配概率。")
    y=re.search(r"(次日|翌日|本周|本月|当周)([^，。？]{1,10}?)(?:平均|相差|多|差)",q)
    if not y:return None
    outcome=y[2]
    if re.search(r"几个|几人|多少个|多少人",q) and not outcome.endswith(("数","量","率")):
        outcome+="数"
    ends=[[own,s] for s in pair]
    contrast=dict(kind="original_local",population=group,scope="whole" if group==nodes else "subgroup",
                  weights=[str(Fraction(1,len(group)))]*len(group),ends=ends,variable=role(a[2]),outcome=outcome,time=y[1],
                  remaining="在原抽签每个比较端条件平均其他安排",
                  intervention=f"本人处理={own}，至少一位伙伴处理={pair[0]}",reference=f"本人处理={own}，至少一位伙伴处理={pair[1]}")
    facts=dict(contrast=contrast,network=dict(basis="edges",nodes=nodes,edges=edges,pre=True,complete_for=nodes,roster_complete=True),
               exposure=dict(kind="any"),assignment=dict(kind="independent",p={n:str(rate) for n in nodes},variable=role(a[2])),
               information=dict(query=None,same_population=False),science=dict(evidence=[],random_full=False,consistent=False))
    spans=[graph,design,exp]
    result=network_event_handoff.solve(facts,design_only=True)
    if result is None:
        exog=one(rows,r"(?:整份|完整|整单).{0,25}潜在.{0,10}(?:无关|独立)|独立于.{0,10}潜在",message="请说明原整单分配与各完整安排下潜在结果的关系。")
        cons=one(rows,r"实际.{0,12}(?:就是|对应|等于)实际.{0,10}潜在|记录一致",message="请说明实际观测结果与实际完整分配的关系。")
        info=one(rows,r"(?:能给|可查询|可提供).{0,12}(?:各|逐|每).{0,14}(?:事件|状态).{0,6}总体条件均值",message="请说明能否查询各评价单位在两端的总体条件均值。")
        if re.search(r"不一致|不能查|不可查|不提供|不独立|未确认|无法确认|不采用|撤回|拒绝|不能保证|不成立|仅有样本",text):
            raise MissingFacts("请核对用于有支持两端的科学前提和逐单位总体均值接口。")
        facts["science"]=dict(random_full=True,consistent=True,evidence=[evidence(exog,"整单随机"),evidence(cons,"一致性")])
        facts["information"]=dict(query="event_mean",same_population=True)
        result=network_event_handoff.solve(facts)
        spans.extend([exog,cons,info])
    if result is not None:
        result["proof"].update(binder="source-roster-local-events",source_spans=spans,edges=edges,roster=nodes)
        if result["answer"]["status"]=="UNDEFINED":
            result["answer"]["assumptions"]=[evidence(graph,"原评价名单与处理前完整网络"),evidence(design,"独立分配"),evidence(exp,"无邻居的暴露定义")]
    return result
