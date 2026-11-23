"""Bind a single original-design local contrast to the business question and dated records."""
import re
from fractions import Fraction

from .direct_network import sha
from .network_query_binding import solve_reviewed, read_rate, RATE, claims
from .network_response import unpack
from .network_estimate_handoff import delivery, make_handoff, target_for

NAME = r"[\u3400-\u9fffA-Za-z0-9]{1,12}?"
NUMBER = r"[-−+]?(?:\d+/\d+|\d*\.\d+|\d+)%?"
COUNTS = {k:i for i,k in enumerate("零一二三四五六七八九十")}
COUNTS["两"] = 2
ACTIVE = r"获邀|受邀|收到邀请|参加|开灯|亮灯|发广告|试机|试用|上系统|接入|启用|开启|开通|签约"
LOW = r"至多(?:一半|半数)|未过半|不超过(?:半数|一半)|都不|全不|都没|全没|全无|无(?:固定)?(?:好友|朋友|伙伴)|无人|谁都没|都未|搭档不(?:试|用)|不试(?:的|$)"
HIGH = r"过半|超过半数|至少一|有(?:固定)?(?:好友|朋友|伙伴)|搭档(?:试机|试用|用)"
MISALIGN = r"强制(?:固定|指定)|固定(?:另一|其余|其他)组|另一个目标|第二问|第一问|全体平均|单向关注|出边|入边|分层标准化"
# Authorization, full-list support and randomization refer to the assigned variable.
# Synonyms are interpreted only within the clauses that specify the target and the design.
ROLES = {
    "邀请":r"获邀|受邀|邀约|邀请",
    "实际参加":r"实际参[加与]|真正参[加与]",
    "试机":r"试机|试新.{1,7}机|试用.{0,5}(?:机|设备)",
    "开灯":r"开灯|亮灯|开提示灯",
    "发广告":r"发广告|投放广告|投广告",
    "上系统":r"上系统|用系统|系统上线",
    "接入":r"接入",
    "启用":r"启用",
    "开通":r"开通",
}

def count(s):
    return int(s) if s.isdigit() else COUNTS.get(s)

def role(s):
    found=[key for key,pat in ROLES.items() if re.search(pat,s)]
    return found[0] if len(found)==1 else None

def source_lines(case):
    out=[]
    for sid,text in [("question",case["business_question"])]+[(s["source_id"],s["text"]) for s in case["sources"]]:
        for m in re.finditer(r"[^。！？；\n]+",text):
            t=m[0].strip()
            if t:
                start=m.start()+m[0].index(t)
                out.append(dict(source_id=sid,quote=t,start=start,end=start+len(t)))
    return out

def attributed(case,draft):
    doc,location=unpack(draft)
    sheet=doc.get("network_facts") if isinstance(doc,dict) and location and location.get("state")=="LOCATED" else None
    sources={s["source_id"]:s["text"] for s in case["sources"]};sources["question"]=case["business_question"]
    fields={}
    for name in ("network","exposure","assignment","contrast"):
        cell=(sheet or {}).get(name) or {};cell=cell if isinstance(cell,dict) else {}
        quotes=cell.get("evidence") or []
        if isinstance(quotes,dict):quotes=[quotes]
        spans=[]
        for citing in quotes[:20] if isinstance(quotes,list) else []:
            if not isinstance(citing,dict):continue
            q=citing.get("quote");sid=citing.get("source_id")
            if not isinstance(q,str) or not q.strip():continue
            hits=[s for s,t in sources.items() if q in t]
            use=sid if isinstance(sid,str) and sid in hits else hits[0] if len(hits)==1 else None
            if use is not None:
                start=sources[use].index(q)
                spans.append(dict(source_id=use,quote=q,start=start,end=start+len(q),relocated=use!=sid))
        fields[name]=dict(value=cell.get("value"),spans=spans)
    return fields

def find_focus(q,fields):
    patterns=(rf"(?:只评(?:价)?|仅评(?:价)?|只考察|只关心|只看)({NAME})(?=本人|[，,。])",
              rf"(?:只要|仅要)({NAME})的(?:数字|结果|数据)",
              rf"(?:问的是|评价对象是)({NAME})本人",
              rf"(?:^|[。？！？])({NAME})(?:本周|本月|本季)(?:不|未|没)",
              rf"(?:^|[。？！？])({NAME})本人(?:不|未|没)")
    for group in (patterns[:3],patterns[3:]):
        names={m[1] for pat in group for m in re.finditer(pat,q)}
        if len(names)==1:return names.pop()
        if names:return None
    # A proposed individual can locate the referent only if the question explicitly singles them out.
    c=fields["contrast"]["value"];g=fields["network"]["value"]
    nodes=g.get("nodes") if isinstance(g,dict) else None
    if isinstance(c,dict) and isinstance(nodes,list):
        exact=[n for n in nodes if isinstance(n,str) and n and n in str(c.get("population",""))
               and re.search(re.escape(n)+r"(?:本人|自己)(?:不|没|未|开)",q)]
        if len(exact)==1:return exact[0]
    return None

def neighbor_event(clause, degree):
    """Read one requested endpoint as a predicate on the treated-neighbor count."""
    counts = range(degree + 1)
    if re.search(r"并非|不都是|并不全|不是|但不|而非|除了|除外|且不|或者", clause):
        return None
    if re.search(r"至多(?:一半|半数)|未过半|不超过(?:半数|一半)", clause):
        return "majority", frozenset(k for k in counts if 2 * k <= degree)
    if re.search(r"过半|超过半数", clause):
        return "majority", frozenset(k for k in counts if 2 * k > degree)
    exact = re.search(r"(?:恰好|刚好|正好|恰有|恰为)(?:有)?([零一二两三四五六七八九十\d]+)"
                      r"(?:位|名|个|家|处|站)?(?:邻站|邻居|伙伴|好友|朋友)?(?:获邀|受邀|开灯|亮灯|参加|接入|启用|上系统|试机|发广告)", clause)
    if exact:
        k = count(exact[1])
        return ("count", frozenset([k])) if k is not None and k <= degree else None
    if re.search(r"恰好|刚好|正好|恰有|恰为|仅有|只有|至多|不到|超过|至少(?!一|1(?!\d))", clause):
        return None
    if re.search(r"(?:均|都|全)(?:不|没|未|无)", clause):
        return "any", frozenset([0])
    if re.search(r"(?:均|都|全)(?:" + ACTIVE + r")", clause):
        return "count", frozenset([degree])
    if re.search(LOW, clause):
        return "any", frozenset([0])
    if re.search(HIGH, clause):
        return "any", frozenset(range(1, degree + 1))
    return None


def shared_exposure(left, right, degree):
    """Choose a supported rule only if each named state is exactly the requested event."""
    if left is None or right is None or left[1] == right[1]:
        return None
    kinds = (left[0], right[0])
    events = (left[1], right[1])
    rules = {"any": (frozenset([0]), frozenset(range(1, degree + 1))),
             "majority": (frozenset(range(degree // 2 + 1)), frozenset(range(degree // 2 + 1, degree + 1)))}
    for kind in dict.fromkeys(kinds):
        if kind in rules and all(event in rules[kind] for event in events):
            first, second = (rules[kind].index(event) for event in events)
            return kind, first, second
    if all(len(event) == 1 for event in events):
        first, second = (next(iter(event)) for event in events)
        return "count", first, second
    return None


def contrast(q, focus, degree):
    totals = re.findall(r"(?<!至少)(?<!恰好)(?<!恰有)(?<!只有)([零一二两三四五六七八九十\d]+)"
                        r"(?:个|位|名|家|处)(?:老|固定)?(?:邻站|邻居|邻店|好友|伙伴)(?=均|全|都|过半|中|里|恰|至少)", q)
    if any(count(total) != degree for total in totals):
        return None
    quantity=role(q)
    if not quantity or re.search(MISALIGN,q):return None
    own0=re.search(r"(?:本人|自己|"+re.escape(focus)+r")(?:本周|本月|本季)?(?:没(?:有)?|未|不)",q)
    own1=re.search(r"(?:它|本人|自己|"+re.escape(focus)+r")(?:这周|本周|本月|本季)?(?:已)?(?:"+ACTIVE+r")时",q)
    if bool(own0)==bool(own1):return None
    own=int(bool(own1))
    # An explicit definition of a reduction overrides the narrative order of the two worlds.
    direction=re.search(r"(?:节约量|减少量|降低量|差值)(?:按|是|等于|定义为)([^。？！]+)",q)
    if not direction and re.search(r"节约|减少量|降低量|后者减前者|反过来",q):return None
    text=direction[1] if direction else q
    pairs=[]
    for sent in re.split(r"[。？！；]",text):
        if not sent.strip():continue
        if "减" in sent and not re.search(r"减少",sent):
            seg=re.split("减去?",sent,maxsplit=1)
        elif "对比" in sent:
            seg=sent.split("对比",1)
        elif re.search("与.+(?:相比|比[，,])",sent):
            seg=re.split("与",sent,maxsplit=1)
        else:continue
        def side(t):
            # The focal unit's own negative state is not a negative neighbor exposure.
            t=re.sub(re.escape(focus)+r"(?:本周|本月|本季)?(?:不|没|未)[^，,]{0,10}时","",t)
            return neighbor_event(t, degree)
        comparison = shared_exposure(side(seg[0]), side(seg[1]), degree)
        if comparison is not None:pairs.append(comparison)
    if len(set(pairs))!=1:return None
    exp,a,b=pairs[0]
    time=re.search(r"这周|本周|本月|月底|下班|季末|本季|次日|本轮|期末|下课|本班|当天|收班",q)
    # Prefer the explicitly named outcome next to its time, or the quantity requested in the question.
    y=None
    for pat in (r"(?:这周|本周|本月|月底|下班|季末|本季|次日|期末|下课|本班|当天|收班)(?:平均)?([\u3400-\u9fff]{1,10}?)(?=变化|差多少|会多多少|的平均差|之差)",
                r"(?:的平均|的总体)([\u3400-\u9fff]{1,9}?)(?=[。，？]|是多少)"):
        hit=re.search(pat,q)
        if hit:y=hit[1];break
    if not time:return None
    return dict(variable=quantity,population=[focus],scope="subgroup",weights=["1"],kind="original_local",
                ends=[[own,a],[own,b]],exposure=exp,time=time[0],outcome=y,joint_requested=bool(re.search(r"联合(?:机会|概率|事件)|连同.{0,14}机会",q)),
                intervention=f"{focus} 本人状态 {own}、邻居暴露 {a}",reference=f"{focus} 本人状态 {own}、邻居暴露 {b}",
                remaining="按原分配各端的条件规律")

def named_neighbors(sentence, focus, roster):
    name = re.escape(focus)
    match = re.search(name + r"(?:只与|仅与)([^，,。；]{1,80}?)(?:相连|互通|是伙伴)", sentence)
    if match is None:
        match = re.search(name + r"的(?:邻店|邻居|伙伴)(?:恰是|只有|仅有|为)([^，,。；]{1,80})(?=[，,]|$)", sentence)
    if match:
        names = re.split(r"[、和与及]", match[1])
        if all(re.fullmatch(NAME, n) for n in names):
            return names
    if roster and roster[0] == focus and len(roster) == 3 and re.search(name + r"与后两[家人站](?:均|都)是(?:伙伴|邻居|搭档)", sentence):
        return roster[1:]
    match = re.search(name + r"和([一二两三四五六七八九十\d]+)位固定(?:好友|伙伴)", sentence)
    if match and count(match[1]) in range(1, 21):
        return [f"固定伙伴{i+1}" for i in range(count(match[1]))]
    if re.search(r"各组两人|每组两人", sentence) and "搭档" in sentence and re.search(r"前已固定|事前固定", sentence):
        return ["同组搭档"]
    return None


def network(lines, focus):
    roster = None
    for row in lines:
        match = re.search(r"^("+NAME+r"(?:、"+NAME+r"){1,30})(?:这[零一二两三四五六七八九十\d]+处都在名单上|[零一二两三四五六七八九十\d]+(?:家|人|站|处)在册|均在册|都在名册)", row["quote"])
        if match:
            roster = match[1].split("、")
            break
    phase = r"(?:试验|分配|开班|活动|上线|试点|开工|处理)"
    pre = phase + r"(?:之|以)?前|事前固定|固定(?:好友|伙伴|搭档)"
    post = phase + r"(?:结束|实施|完成)?(?:以|之)?后|事后"
    unknown = r"(?:没有|缺少|未留|无法恢复|未保存).{0,8}(?:处理前|试验前|活动前|原有|原始).{0,7}(?:关系|图|伙伴)"
    records = []
    for i, row in enumerate(lines):
        sentence = row["quote"]
        neighbors = named_neighbors(sentence, focus, roster)
        if not neighbors or focus in neighbors or len(set(neighbors)) != len(neighbors):
            continue
        evidence = [row]
        before = bool(re.search(pre, sentence))
        after = bool(re.search(post, sentence))
        if not before and not after and i:
            previous = lines[i-1]
            prior = previous["quote"]
            # A separate dating sentence must explicitly describe the relation record.
            if re.fullmatch(r".{0,25}(?:关系图|合作图|关系网|伙伴图|伙伴关系).{0,15}(?:分配|活动|试验|处理)前.{0,12}(?:冻结|画好|固定|锁定|建好)", prior) and not re.search(unknown, prior):
                before = True
                evidence.insert(0, previous)
        timing = "unknown" if re.search(unknown, sentence) or (before and after) else "before" if before else "after" if after else "unknown"
        records.append((neighbors, timing, evidence))
    if not records:
        return None
    dated = [r for r in records if r[1] == "before"]
    comparable = {frozenset(names) for names,timing,_ in records if timing != "after"}
    if not dated or len(comparable) != 1:
        conflict = bool(dated and len(comparable) > 1)
        reason = "关于原分配时的伙伴，材料给出不一致的名单。" if conflict else "材料没有把这份具体伙伴名单确认为分配前的关系。"
        issue = dict(detail=reason, degrees=sorted({len(names) for names,_,_ in records}),
                     sources=[row for _,_,evidence in records for row in evidence])
        return None, [], issue
    neighbors, _, evidence = dated[0]
    nodes = roster or [focus, *neighbors]
    if not set([focus,*neighbors]) <= set(nodes) or len(nodes) != len(set(nodes)):
        return None
    net = dict(basis="focal", pre=True, nodes=nodes, edges=[[focus,n] for n in neighbors],
               complete_for=[focus], roster_complete=roster is not None)
    return net, evidence, None

def design_rows(lines):
    text="。".join(z["quote"] for z in lines)
    indep=[z for z in lines if re.search(r"(?:各自|各人|分别|各店)独立(?:抛|抽|掷)",z["quote"])]
    joint=[z for z in lines if re.search(r"共用一(?:张|枚)|同掷一枚|一起掷同一",z["quote"])]
    if indep and joint:
        # A record for another period must be excluded by an explicit dated correction.
        current=next((z for z in lines if re.search(r"核对|确认",z["quote"]) and re.search(r"本轮|本周|本次",z["quote"])),None)
        if current and re.search(r"下个|下月|另一个演练|不适用",text):
            active=re.search(r"([甲乙丙丁])(?:写的|记录的|记的|所记)(?:是|为)(?:本轮|本周|本次)",current["quote"])
            if active:
                key=active[1];selected=[r for r in indep+joint if re.search(key+r"(?:写|记|报告|说明)",r["quote"])]
                if len(selected)==1:return ("independent" if selected[0] in indep else "shared"),selected[0],[current]
        if re.search(r"无法辨别|不能确认|无法确认|不能区分",text):return "conflict",indep[0],joint
        return None
    if indep:
        if len(indep)!=1 or re.search(r"如果|若|不独立|假设|尚未|是否",indep[0]["quote"]):return None
        return "independent",indep[0],[]
    if joint:
        if re.search(r"如果|若|假设|是否|无法|不确定",joint[0]["quote"]):return None
        return "shared",joint[0],[]
    fixed=[z for z in lines if re.search(r"均匀(?:选定|选取|抽取)|等概率(?:抽取|选取)|均匀无放回",z["quote"])]
    if len(fixed)==1:return "fixed",fixed[0],[]
    marginal=[z for z in lines if re.search(r"只有.{0,16}(?:概率|边际)|只报.{0,12}边际",z["quote"])]
    if marginal and re.search(r"没人能确认|无法确定|不能确认|无法确认|联合.{0,5}未知",text):return "margins_only",marginal[0],[]
    random=[z for z in lines if re.search(r"整单随机生成|完整名单随机产生|整份名单随机生成",z["quote"])]
    if len(random)==1:return "reported",random[0],[]
    return None

def assignment(lines,net,var):
    binding=design_rows(lines)
    if not binding:return None
    kind,z,other=binding;s=z["quote"];text="。".join(w["quote"] for w in lines)
    assigned=role(s)
    if assigned is None:
        # Binary selection without a named substance is usable only for a single matching
        # intervention. Never reinterpret an invitation as actual receipt.
        if var not in ("发广告","上系统","接入","启用","开通") or not re.search(r"被选|公平签|公平硬币",s) or "决定" in s:return None
        if re.search(r"获邀|邀请|实际参加|不依从|改用|多项处理",text):return None
        assigned=var
    if assigned!=var:return None
    law=dict(kind=kind,variable=var)
    if kind=="fixed":
        n=re.search(r"(?:在|从)([零一二两三四五六七八九十\d]+)(?:站|家|人|处|组)中",s)
        m=re.search(r"(?:恰好|恰取|恰选|选取|抽取)([零一二两三四五六七八九十\d]+)(?:站|家|人|处|组)",s)
        if not net["roster_complete"] or not n or count(n[1])!=len(net["nodes"]) or not m or not 0<=count(m[1])<=len(net["nodes"]):return None
        law["quota"]=count(m[1])
    elif kind in ("shared","margins_only","conflict","independent"):
        if kind=="margins_only":
            m=re.search(r"(?:各|均|都)(?:为|是|有)?("+RATE+r")",s)
            if not m:return None
            rate=str(read_rate(m[1]))
        else:
            if not re.search(r"公平|各半|一半",s):return None
            rate="1/2"
        if kind=="shared":
            if not re.search(r"一开全开|正面.{0,12}(?:全|都).{0,12}反面.{0,10}(?:全|都)",s):return None
            law["p"]=rate
        else:law["p"]=dict.fromkeys(net["nodes"],rate)
        if kind in ("margins_only","conflict"):law["material_alternatives"]=["独立","共签"]
    return law,[z,*other]

def population_table(lines,goal):
    focus=goal["population"][0];own=goal["ends"][0][0];y=goal["outcome"]
    numeric=None;source=None;positive=False
    # Bind each historical mean to a peer state and to the focal unit's own treatment.
    for z in lines:
        s=z["quote"];pair=None
        if focus not in s and "焦点" not in s:continue
        if own!=0 or not re.search(r"未获邀|未受邀|不试|不上|未接入|未启用|未开通|不发",s):continue
        if role(s) not in (None,goal["variable"]):continue
        seq=re.search(r"(有(?:固定)?(?:好友|伙伴).{0,4}(?:获邀|受邀)|搭档(?:试机|试用|试))和(无(?:固定)?(?:好友|伙伴).{0,4}(?:获邀|受邀)|不试).{0,25}?(?:率|均值)(?:依次|分别)?(?:是|为)("+NUMBER+r")[、和]("+NUMBER+r")",s)
        if seq and goal["exposure"] == "any":
            measure=re.search(r"总体([\u3400-\u9fff]{1,12}?)(?:均值|率)(?:依次|分别)?(?:为|是)",s)
            if not y or not measure or measure[1] not in y:return None
            pair={1:seq[3],0:seq[4]}
        split=re.search(r"(都不上|均未接入|均未启用)时的总体([\u3400-\u9fff]{1,7}?)("+NUMBER+r")[，,](?:有伙伴上|有伙伴接入|有伙伴启用)时(?:为|是)("+NUMBER+r")",s)
        if split and goal["exposure"] == "any":
            pair={0:split[3],1:split[4]}
            if y and y!=split[2]:return None
            y=split[2]
        if pair:
            if numeric is not None:return None
            def val(t):return str(Fraction(t[:-1])/100 if t.endswith("%") else Fraction(t.replace("−","-")))
            numeric={f"{focus}|{own},{k}":val(v) for k,v in pair.items()}
            source=z;positive=bool(re.search(r"都可达|都有支持|均有正概率",s))
    if source:return dict(query="event_mean",same_population=True,positive_both=positive,values=numeric),source,y
    candidates=[z for z in lines if re.search(r"可(?:调用|查询|取得).{0,15}(?:正概率|各端|两端|状态).{0,12}总体.{0,7}(?:平均|均值)|只许用有支持状态的总体条件",z["quote"])]
    if len(candidates)==1:return dict(query="event_mean",same_population=True,values={}),candidates[0],y
    return None

def science_statement(rows, source, pattern, affirmative):
    """Classify a scientific statement in its own clause and preserve its original span."""
    candidates = []
    uncertain = re.compile(r"是否|能否|可能|假设|若|不成立|否认|无定论|未确认|未经确认|未获证实|未得到确认|尚不清楚|不确定|有待|未知|存疑|待核")
    for row in rows:
        quote = row["quote"]
        clauses = re.split(r"[，,:：]", quote)
        relevant = [clause.strip() for clause in clauses if re.search(pattern, clause)]
        if not relevant:
            continue
        punctuation = source[row["end"]:row["end"] + 1]
        neighboring = [clauses[i + 1] for i in range(len(clauses) - 1) if clauses[i].strip() in relevant]
        if len(clauses) > 1 and clauses[1].strip() in relevant:
            neighboring.append(clauses[0])
        unscoped_doubt = any(uncertain.search(clause) and not re.search(r"名单|列单|潜在|一致|实测", clause)
                             for clause in neighboring)
        if punctuation in ("?", "？") or unscoped_doubt or any(uncertain.search(c) or c.endswith("吗") for c in relevant):
            explicit_denial = any(re.search(r"不成立|明确否认", c) for c in relevant)
            open_question = punctuation in ("?", "？") or any(re.search(r"是否|能否|吗|不确定", c) for c in relevant)
            return row, "denied" if explicit_denial and not open_question else "unconfirmed"
        state = "affirmed" if all(re.fullmatch(affirmative, clause) for clause in relevant) else None
        candidates.append((row, state))
    if not candidates:
        return None, None
    return next((item for item in candidates if item[1] is None), candidates[0])


def confirmed_design(replies, law):
    """A business reply can select a documented alternative, keeping all marginal rates."""
    if not replies or law["kind"] not in ("margins_only", "conflict"):
        return None
    rates = law.get("p")
    if not isinstance(rates, dict) or len(set(rates.values())) != 1:
        return None
    choices = set()
    evidence = []
    for reply in replies:
        text = reply["text"]
        quote = text.strip().rstrip("。！.!").strip()
        if re.fullmatch(r"(?:各单位|各店|大家|各人)?(?:各自|分别|逐人)?独立抽签", quote):
            choice = "independent"
        elif re.fullmatch(r"(?:所有单位|各单位|各店|大家|全体)?(?:共用一张签|同签同处理|共签|同签)", quote):
            choice = "shared"
        elif re.fullmatch(r"(?:暂时|目前|还是|仍然|仍)?(?:不清楚|不知道|不能确认|无法确认|尚未确定)", quote):
            choice = "unknown"
        else:
            return None
        choices.add(choice)
        start = text.index(quote)
        evidence.append(dict(source_id=reply["source_id"], quote=quote, start=start, end=start+len(quote)))
    # A later doubt withdraws a confirmation. Two conflicting definite statements
    # need another reading. Neither is resolved by taking the last distinct choice.
    if len(choices - {"unknown"}) > 1 or choice == "unknown":
        return law, evidence
    p = rates if choice == "independent" else next(iter(rates.values()))
    return dict(kind=choice, variable=law["variable"], p=p), evidence


def derive(case,draft):
    base = []
    replies = []
    for source in case["sources"]:
        if (source["source_id"].startswith("user_reply_") and source.get("kind") == "OTHER"
                and source.get("label") == "用户补充说明"):
            replies.append(source)
        else:
            base.append(source)
    if len(base)!=1 or len(base[0]["text"])>4500:return None
    original_case = dict(case, sources=base)
    q=case["business_question"]; fields=attributed(original_case,draft);focus=find_focus(q,fields)
    if not focus:return None
    all_lines=source_lines(original_case);docs=[z for z in all_lines if z["source_id"]!="question"];t="。".join(z["quote"] for z in docs)
    if re.search(MISALIGN,t) or re.search(r"另一组.{0,12}固定|固定为|不满足一致性|不独立|未随机|未承诺|不能保证|事后才|假如|若改用|(?:不认为|不能假设|没有证据).{0,18}(?:随机|独立|一致)",t):return None
    original=next((z for z in all_lines if re.search(r"按(?:旧|原).{0,16}条件|沿用原分配条件|本轮抽取在各端的条件|按原整单设计在该端的条件",z["quote"])),None)
    if not original:return None
    graph=network(docs,focus)
    if not graph:return None
    net, graph_evidence, problem = graph
    if problem:
        if not any(contrast(q, focus, degree) for degree in problem["degrees"]):
            return None
        question = f"{focus}在分配前的完整伙伴名单是什么？也可以提供按原关系核准、能区分题目两端的等价事件标签。"
        return dict(network_evidence_gap=dict(focus=focus, evidence=problem["sources"], detail=problem["detail"]),
                    questions=[question])
    graph_source = graph_evidence[-1]
    goal = contrast(q, focus, len(net["edges"]))
    if not goal:return None
    rule = assignment(docs, net, goal["variable"])
    if not rule:return None
    law,law_sources=rule
    if replies:
        confirmed = confirmed_design(replies, law)
        if confirmed is None:return None
        law, reply_evidence = confirmed
        law_sources = [*law_sources, *reply_evidence]
    subject = r"(?:(?:所有|完整|整份|各份|邀请|开灯|试机|排班|试点|本轮|原始)){0,3}(?:名单|列单)"
    independence = r"(?:名单|列单).{0,24}(?:潜在.{0,12}独立|独立于潜在)"
    positive = subject + r"(?:与.{0,6}潜在[\u3400-\u9fff]{1,12}独立|独立于.{0,6}潜在[\u3400-\u9fff]{1,12})"
    consistency = r"实际名单对应其潜在记录|实际.{0,12}对应实际|记录按实际.{0,12}一致|实际记录一致|实测与实际.{0,6}一致"
    consistent = r"(?:实际名单对应其潜在记录|实际[\u3400-\u9fff]{1,8}对应实际(?:列单|名单|安排)|记录按实际.{0,12}一致|实际记录一致|实测与实际.{0,6}一致)"
    ind, independent = science_statement(docs, base[0]["text"], independence, positive)
    con, matches_observed = science_statement(docs, base[0]["text"], consistency, consistent)
    if independent is None or matches_observed is None:return None
    tbl=population_table(docs,goal)
    if not tbl:return None
    info,info_source,y=tbl
    if not y:return None
    goal["outcome"]=y
    shape=goal.pop("exposure")
    labels=("至多一半邻居处理","严格过半邻居处理") if shape=="majority" else ("所有邻居未处理","至少一位邻居处理")
    for field,(own,side) in zip(("intervention","reference"),goal["ends"]):
        label = f"恰有 {side} 位邻居处理" if shape == "count" else labels[side]
        goal[field]=f"{focus} 的{goal['variable']}状态为 {own}，{label}"
    assertions = ((independent, "整份名单独立于各名单下的潜在结局"),
                  (matches_observed, "实测结局对应实际名单下的潜在结局"))
    denied = [label for state, label in assertions if state == "denied"]
    pending = [label for state, label in assertions if state == "unconfirmed"]
    if denied or pending:
        detail = ("原材料否定了以下条件：" + "、".join(denied) + "。" if denied else "")
        detail += ("原材料尚未确认以下条件：" + "、".join(pending) + "。" if pending else "")
        question = ("能否提供“" + "”和“".join(pending) + "”的原设计依据？" if pending else "")
        if denied:
            question += "已知上述条件不成立。还有哪些资料或经研究者确认的其他假设可以支持原比较？"
        target = target_for(goal, "difference")
        handoff = make_handoff(target, "STOP", [goal["variable"], goal["outcome"]], [], [], detail, {})
        solved = delivery(target, "NEEDS_INPUT", detail, None, [], handoff, detail,
                          dict(method="ORIGINAL_EVENT_ASSUMPTIONS_UNCONFIRMED", unconfirmed=pending, denied=denied), [question])
    else:
        facts=dict(network=net,exposure=dict(kind=shape),assignment=law,contrast=goal,information=info,
                   science=dict(random_full=True,consistent=True,evidence=claims([ind] if ind==con else [ind,con])))
        solved=solve_reviewed(facts)
    if not solved:return None
    question=dict(source_id="question",quote=q,start=0,end=len(q))
    network_refs=[z for z in docs if z in graph_evidence or (net["roster_complete"] and re.search(r"在册|都在名单上|都在名册",z["quote"]))]
    refs=dict(population=[question,graph_source],treatment=[question,*law_sources],ends=[question,info_source],
              network=network_refs,exposure=[question],assignment=law_sources,remaining=[original],information=[info_source],science=[ind,con])
    spans=[]
    for rows in refs.values():
        for r in rows:
            if r not in spans:spans.append(r)
    solved["proof"].update(binder="source-grounded-contrast/1",source_sha256=sha(case["sources"]),question_sha256=sha(q),
        source_spans=spans,bound_fields=refs,assigned_variable=law["variable"],target_variable=goal["variable"],
        model_field_spans={k:v["spans"] for k,v in fields.items()})
    if replies:
        solved["proof"]["design_reply_sources"] = [r["source_id"] for r in replies]
    return solved
