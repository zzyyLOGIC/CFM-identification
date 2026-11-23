"""Bind supported natural-language population queries to fixed targets before issuing a handoff."""
import re
from fractions import Fraction

from . import network_event_handoff, network_policy_handoff
from .network_estimate_handoff import probability
from .direct_network import sha

NUMBER = r"[-−+]?(?:\d+/\d+|\d*\.\d+|\d+)%?"
NAME = r"[\u3400-\u9fffA-Za-z]{1,8}"
CN = dict(zip("零一二三四五六七八九十",range(11)))
RATE = rf"(?:{NUMBER}|[一二三四五六七八九十]分之[一二三四五六七八九十]|一半)"


def read_rate(text):
    if text=="一半":
        return Fraction(1,2)
    if "分之" in text:
        den,num=text.split("分之")
        return probability(Fraction(CN[num],CN[den]))
    if text.endswith("%"):
        return probability(Fraction(text[:-1])/100)
    return probability(text)


def cited(sid,line,original):
    start=original.index(line)
    return dict(source_id=sid,quote=line,start=start,end=start+len(line))


def claims(rows):
    return [dict(kind="other",subject="原整单随机与一致性",statement=r["quote"],quote=r["quote"],source=r["source_id"]) for r in rows]


def local_packet(q, doc):
    text=doc["text"]
    if not re.search(r"原(?:分配|抽签|设计|签).{0,10}条件",q) or re.search(r"反过来|后者减前者|另一个|第二问|全体平均|降低量|节约量|反事实固定|固定其余|只看其中",q):
        return None
    # A single named focal unit, untreated on both sides and at least one vs no treated peers.
    f=re.search(r"(?:只评|只看|只管)(?P<name>[\u3400-\u9fffA-Za-z]{1,8}?)(?:[，,。]|这次)",q)
    if not f:
        return None
    focus=f["name"]
    if not re.search(r"(?:本人|她本人|他本人|"+re.escape(focus)+r")(?:没|不|未)[^，。；]{0,10}时",q):
        return None
    if not re.search(r"(?:有伙伴|至少一.{0,6}(?:发|处理|选中|开启)).{0,9}(?:比|与|减).{0,7}(?:全不|谁都没|都不|全没)",q):
        return None
    if not re.search(r"联合|连同.{0,12}机会",q) or re.search(r"(?:无需|不用|不要|不必|不求).{0,8}(?:联合|连同)",q):
        return None
    if re.search(r"并非|不一致|不独立|预告|邀请|存在混杂|有冲突|两种规则|尚未确认|重新定义|不许.{0,5}查询",text):
        return None
    src=doc["source_id"];lines=[m[0] for m in re.finditer(r"[^。！？]+",text)]
    gt=next((s for s in lines if re.search(r"(?:开工前|试点前|活动前|处理前|分配前).{0,14}(?:伙伴|邻居|固定)",s)),None)
    if not gt:
        return None
    pair=re.search(re.escape(focus)+r"(?:的邻店恰是|的邻居为|的伙伴为|要和)("+NAME+r")[、和]("+NAME+r"?)(?=交换|，|$)",gt)
    if not pair:
        return None
    nodes=[focus,*pair.groups()]
    if len(set(nodes))!=3 or not re.search(r"恰是|全部|仅有|只有",gt):
        return None
    source_science=next((x for x in lines if re.search(r"抽签不看.{0,9}潜在|完整(?:名单|列单|分配).{0,7}独立于潜在",x) and
                         re.search(r"按实际完整名单记|实际.{0,10}对应实际(?:列单|名单)|记录一致",x)),None)
    inf=next((x for x in lines if re.search(r"(?:每一端|两端|各端|有支持状态).{0,15}总体.{0,6}均值|每一端.{0,12}总体平均",x)),None)
    if not source_science:
        return None
    if inf and re.search(r"不能|不可|无法|遗失|尚无|没有|不提供|未提供",inf):
        inf=None
    design=next((x for x in lines if re.search(r"各掷自己的签|各自独立抽签|一起掷同一枚公平硬币|共用一枚公平硬币",x)),None)
    if not design or re.search(r"若|假如|如果|并非|不是|不采用",design):
        return None
    rate_line=None
    if re.search(r"同一枚|共用",design):
        if not re.search(r"正面.{0,10}(?:都发|都开|全开|同开|全选).{0,12}反面.{0,8}(?:全不|全关|都不)",design):
            return None
        variable=re.search(re.escape(focus)+r"不([^，。时]{1,8})时",q)
        if not variable:return None
        var=variable[1];law=dict(kind="shared",p="1/2",variable=var)
        if any(w in text for w in ("独立抽签","各自抽","各掷自己的签")):return None
    else:
        if re.search(r"共用|共签|一起抽|同一枚",text):return None
        m=re.search(re.escape(focus)+r"(抽中[^，。]{0,8}?)的机会是("+RATE+r")，"+re.escape(nodes[1])+r"是("+RATE+r")，"+re.escape(nodes[2])+r"是("+RATE+r")",text)
        if not m or "抽中" not in q:return None
        var=m[1];rate_line=m[0]
        law=dict(kind="independent",variable=var,p={n:str(read_rate(x)) for n,x in zip(nodes,m.groups()[1:])})
    outcome=re.search(r"平均([^，。？]{1,9}?)(?:几件|多少件)",q) or re.search(r"(?:本周|本月|本轮)([^，。？]{1,8}?)(?:会多多少|差多少)",q)
    period=re.search(r"这次交班|本次交班|本周|本月|本轮",q)
    if not outcome or not period:return None
    science_ev=cited(src,source_science,text)
    cues=[cited("question",q,q),cited(src,gt,text),cited(src,design,text),science_ev]
    if inf:cues.append(cited(src,inf,text))
    if rate_line:cues.append(cited(src,rate_line,text))
    f=dict(network=dict(basis="focal",pre=True,nodes=nodes,edges=[[focus,n] for n in nodes[1:]],complete_for=[focus],roster_complete=False),
           exposure=dict(kind="any"),assignment=law,contrast=dict(kind="original_local",population=[focus],scope="subgroup",weights=["1"],
               variable=var,ends=[[0,1],[0,0]],remaining="按原分配各端的条件规律",outcome=outcome[1],time=period[0],
               intervention="本人未处理且至少一位伙伴处理",reference="本人未处理且所有伙伴未处理",joint_requested=True),
           information=dict(query="event_mean" if inf else "unavailable",same_population=bool(inf),
                            numeric_required=not inf or ("只需写调用方式" not in inf and "只写调用方式" not in inf)),
           science=dict(random_full=True,consistent=True,evidence=claims([science_ev])))
    return f,cues


def declared_coupling(line):
    if re.search(r"不能确认|没(?:有)?提供|未知|只报|尚未|不清楚|是否|还是|不确定",line):
        return "unknown",None
    if re.search(r"若|如果|假如|假设|并非|不是|不再|不采用|未采用|不独立|不同开同关|不共签|不能用",line):
        return None,None
    m=re.search(r"(?:两者|两家|两个单位)?同时(?:处理|开|打开|开启)的?概率(?:为|是|等于)?\s*("+RATE+r")",line)
    kinds=[]
    if m:kinds.append(("specified",str(read_rate(m[1]))))
    if re.search(r"各抛自己的公平签|签独立|各自独立(?:抽签|抛签|抛硬币)|二者独立|两者独立",line) and "不独立" not in line:
        kinds.append(("independent",None))
    if re.search(r"同一枚硬币|共用一张签|同开同关|共签",line):
        kinds.append(("same_draw",None))
    if re.search(r"一定相反|恰有一个|一开一关|反向抽签",line):
        kinds.append(("opposite",None))
    return kinds[0] if len(kinds)==1 else (None,None)


def parse_policy_values(text):
    # Support both explicit per-cell labels and a declared order followed by four values.
    pattern=rf"都处理时[^。；，]{{0,12}}为({NUMBER})，都不处理为({NUMBER})，只有第一个处理为({NUMBER})，只有第二个处理为({NUMBER})"
    a=list(re.finditer(pattern,text))
    orders=list(re.finditer(r"(?:全开|全处理)、(?:全关|全不处理)、只(?:开|处理)([^、，。时]{1,7})、只(?:开|处理)([^、，。时]{1,7})时，[^。；]{0,24}?(?:分别|依次)为("+NUMBER+r")、("+NUMBER+r")、("+NUMBER+r")、("+NUMBER+r")",text))
    if len(a)+len(orders)!=1:return None
    if a:
        data=a[0].groups();labels=["第一个","第二个"];line=a[0][0]
    else:
        order=orders[0]
        labels=list(order.groups()[:2]);data=order.groups()[2:];line=order[0]
        if len(set(labels))!=2:return None
    return dict(zip(("11","00","10","01"),[str(Fraction(v.replace("−","-"))) for v in data])),labels,line


def policy_packet(q, doc, supplements):
    text=doc["text"];sid=doc["source_id"]
    if re.search(r"相比|相对|减去|降低|差多少|对比|分别计算|只看|第二问|若改|反过来",q):return None
    population=re.search(r"(?:两个|两)([\u3400-\u9fff]{1,8}?)等权的平均([^，。？]{1,10}?)(?:水平)?是多少",q)
    period=re.search(r"新政策实施后|下月|来月|下季",q)
    if not population or not period:return None
    if (len(text)>3000 or re.search(r"不独立|没有正概率|不一致|未随机|只是假设|假设不成立|可能是|有矛盾|更正|还有其他|仅为样本",text)):
        return None
    lines=[m[0] for m in re.finditer(r"[^。！？]+",text)]
    science=next((x for x in lines if re.search(r"四种.{0,18}(?:都被随机抽到|都有正概率)",x) and
                  "潜在" in x and ("独立" in x) and re.search(r"(?:实测|实际).{0,12}(?:一致|对应实际)",x)),None)
    # Only an unqualified, equal marginal for both units is bound from free text.
    # Structured inputs can independently specify the two probabilities.
    equal_margin = (r"(?:新政策|新办法|下月|来月)(?:下|让|规定|使)?(?:两个|两)(?:圃|库|单位|店|家)"
                    r"(?:各自(?:处理|开启|打开)?的?(?:边际)?(?:机会|概率)(?:均为|均是|都是|为|是)|各有)"
                    r"(?:一半|1/2)(?:的?机会(?:打开|处理|开启)?)?")
    margin_lines=[line for line in lines if re.fullmatch(equal_margin,line.strip())]
    margins=margin_lines[0] if len(margin_lines)==1 else None
    vs=parse_policy_values(text)
    if not science or not vs or not margins or re.search(r"若|如果|假如|并非",science):
        return None
    values,labels,vl=vs
    if any(v.endswith("%") for v in values.values()):return None
    # Values must be the requested outcome on the same weighted population.
    y=population[2]
    if y not in vl and not (y.endswith("损失") and "总体损失" in vl and "潜在损失" in science and y in q):
        return None
    if re.search(r"非等权|权重不同|仅其中|仅有一家|只报告第一",text):return None
    if not re.search(r"等权总体|全体等权总体",vl):return None
    idx=lines.index(margins)
    statements=[(sid,line,text) for line in lines[idx:] if line!=margins]+[(s["source_id"],s["text"],s["text"]) for s in supplements]
    specified=[]; cited_law=[];unknown=False
    for source,line,original in statements:
        kind,z=declared_coupling(line)
        if kind:
            cited_law.append(cited(source,line,original))
            if kind=="unknown":unknown=True
            else:specified.append((kind,z))
        elif source!=sid and not re.fullmatch(r"我?(?:现在)?(?:需要|只要|要求)(?:一个|单一)?点值[。！]?",line.strip()):
            return None
        elif source==sid and line.strip():
            return None
    if len(set(specified))>1 or (not specified and not unknown):return None
    kind,p=specified[0] if specified else ("unknown",None)
    law=dict(kind="binary_policy",margins=["1/2","1/2"],coupling=kind,labels=labels)
    if p is not None:law["both"]=p
    ev=cited(sid,science,text)
    facts=dict(network=dict(basis="whole",nodes=2),exposure=dict(kind="whole_assignment"),assignment=law,
               contrast=dict(kind="binary_policy_level",population="两个"+population[1]+"等权",scope="whole",outcome=y,time=period[0],
                             intervention="按新联合政策分配两个单位",reference=""),
               information=dict(query="joint_state_mean",same_population=True,all_positive=True,values=values,labels=labels),
               science=dict(random_full=True,consistent=True,evidence=claims([ev])))
    return facts,[cited("question",q,q),ev,cited(sid,vl,text),cited(sid,margins,text),*cited_law]


def solve_reviewed(facts, *, point_required=False):
    if any(not isinstance(facts.get(k),dict) for k in ("network","exposure","assignment","contrast","information","science")):
        return None
    if facts["contrast"].get("kind")=="binary_policy_level":
        if facts["network"].get("basis")!="whole" or facts["exposure"].get("kind")!="whole_assignment":
            return None
        return network_policy_handoff.solve(facts,point_required=point_required)
    return network_event_handoff.solve(facts)


def unavailable_required_query(case, answer):
    """Block an explicitly mandatory fine-list query that the only source expressly excludes."""
    from .direct_verification import answer_items
    parts=answer_items(answer)
    if len(parts)!=1 or len(case["sources"])!=1:
        return None
    h=parts[0].get("estimate_handoff")
    if not isinstance(h,dict) or h.get("mode") not in ("ESTIMATE_POINT","ESTIMATE_BOUNDS"):
        return None
    doc=case["sources"][0]; text=doc["text"]
    if re.search(r"另有|另一套库|另一个台账|更正|改为|第二问",text+case["business_question"]):
        return None
    if "但可" in text:
        allowed=text.split("但可",1)[1]
        if "完整名单" in allowed or not re.search(r"(?:局部|暴露|两个端|两端).{0,12}(?:均值|平均数)",allowed):
            return None
    deny=re.search(r"(?:不能|无法|不提供|不可)(?:按|查询|提供|取得|逐张|分别|各|每|份|张|具体|精细|的|一个|一张|查|取){0,10}完整名单.{0,9}(?:均值|平均数)",text)
    if not deny:return None
    queries=h.get("queries")
    required=(h.get("query_requirement")=="all_required" and isinstance(queries,list) and any(
        isinstance(q,dict) and q.get("kind") in ("full_assignment_mean","person_full_assignment_mean") for q in queries))
    op=h.get("operator")
    if isinstance(op,str) and not re.search(r"或者|也可|可直接|无需|不必|不需要|替代",op):
        required=required or bool(re.search(r"(?:必须|务必|需要先)(?:逐张|逐份|分别|按|查|查询|取得|每份|每张|各|的|具体){1,8}完整名单.{0,8}(?:均值|平均数)",op))
    if required:return cited(doc["source_id"],deny[0],text)
    return None


def source_result(case, *, point_required=False):
    q=case["business_question"];docs=[s for s in case["sources"] if not s["source_id"].startswith("user_reply_")]
    supplements=[s for s in case["sources"] if s["source_id"].startswith("user_reply_")]
    if len(docs)!=1:return None
    try:
        packet=policy_packet(q,docs[0],supplements)
        if not packet and not supplements:packet=local_packet(q,docs[0])
        if not packet:return None
        facts,evidence=packet
        result=solve_reviewed(facts,point_required=point_required or bool(re.search(r"必须.{0,4}点值|只要.{0,4}点值",q)) or any(s["text"].strip()=="我需要单一点值。" for s in supplements))
    except (ValueError,TypeError,KeyError,ArithmeticError):
        return None
    if result:
        result["proof"].update(source_sha256=sha(case["sources"]),question_sha256=sha(q),source_spans=evidence)
        if "labels" in facts["assignment"]:
            result["proof"]["coordinate_labels"]=facts["assignment"]["labels"]
            result["answer"]["estimate_handoff"]["coordinate_labels"]=facts["assignment"]["labels"]
    return result
