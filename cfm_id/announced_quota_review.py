"""Joint equipment support and a separately specified notice in a two-stage quota design."""
import re
from fractions import Fraction

from cfm_id_llm.network_files import MAX_NODES
from .network_estimate_handoff import delivery, make_handoff
from .network_event_handoff import native_support, solve
from .network_query_binding import RATE, read_rate
from .source_network_review import MissingFacts, count, evidence, one, require_statement

N = r"(?:\d{1,4}|[零一二两三四五六七八九十])"
GROUP = r"[\w]{1,8}?(?:班|组|队|区)"
NOTICE = r"(?:预告|通知|广播)"
FIX = "为了只比较实际设备，请说明两端共同固定哪一种名额预告，或采用哪一条相同的预告干预规则？"


def group_roster(rows, focus):
    roster = one(rows, GROUP+r"[^，,。]{1,80}、[^，,。]+[，,]"+GROUP,message="需要两组的处理前人数以及焦点所在组的完整名单。")
    m = re.fullmatch(r"("+GROUP+r")(?:成员为|包括|有)?([^，,]+)[，,]("+GROUP+r")(.+)",roster["quote"])
    if not m or m[1]==m[3]:
        raise MissingFacts("请分组标出已固定的两份名单或各组人数。")
    group_names = [m[1],m[3]]
    members = []
    for name, roster_text in zip(group_names,(m[2],m[4])):
        size = re.fullmatch(r"(?:也有|也是|共|有)?("+N+r")(?:个)?(?:人|成员)",roster_text)
        if size:
            n = count(size[1])
            if not 0<n<=MAX_NODES:raise MissingFacts("该组人数超出可核验的名单范围。")
            group = [f"{name}#{i+1}" for i in range(n)]
        else:
            group = re.sub(r"^(?:成员为|包括|有)","",roster_text).split("、")
            if not all(re.fullmatch(r"[\w]{1,12}",x) for x in group):
                raise MissingFacts("请核准各组名单或提供人数。")
        members.append(group)
    nodes = members[0]+members[1]
    if len(set(nodes))!=len(nodes) or nodes.count(focus)!=1 or len(nodes)>MAX_NODES:
        raise MissingFacts("焦点须在名册中唯一出现，且组别互斥。")
    j = int(focus in members[1])
    mapping = one(rows,r"(?:前|事先).{0,12}固定同(?:班|组|队|区)另("+N+r")(?:个)?人.{0,10}(?:全部|所有)(?:伙伴|同伴|邻居)",message="请确认处理前同组的哪些成员构成焦点的完整伙伴集合。")
    k = count(re.search(r"另("+N+r")",mapping["quote"])[1])
    if k!=len(members[j])-1:
        raise MissingFacts("伙伴人数与焦点所在组的名单不一致。")
    net = dict(basis="focal",pre=True,nodes=nodes,edges=[(focus,n) for n in members[j] if n!=focus],
               complete_for=[focus],roster_complete=True)
    return group_names, members, j, net, [roster,mapping]


def quota_design(rows, names, groups):
    sizes=[len(g) for g in groups]
    measure=r"(?:台|套|份|个名额|名额|名|人)"
    pattern = (re.escape(names[0])+r"(?:有|获|分得)?("+N+r")"+measure+r"[、，,和与]"
               +re.escape(names[1])+r"(?:有|获|分得)?("+N+r")"+measure+r"的?(?:机会|概率)(?:是|为)("+RATE+r")")
    quota=one(rows,pattern,message="请给出两组名额的联合配置及其第一阶段概率。")
    m=re.search(pattern,quota["quote"])
    first=[count(m[1]),count(m[2])]
    if first[0]==first[1] or not re.search(r"(?:剩下|其余|剩余).{0,18}(?:倒给"+re.escape(names[1])+r"|对调|互换|调换)",quota["quote"]):
        raise MissingFacts("请说明其余概率对应的两组名额配置。")
    if re.search(r"倒给",quota["quote"]) and first[1]!=0:
        raise MissingFacts("请给出第二个名额配置的具体数值。")
    profiles=[first,list(reversed(first))]
    if any(m>n for profile in profiles for m,n in zip(profile,sizes)):
        raise MissingFacts("其中一种配置的名额超过组人数。")
    p=read_rate(m[3])
    if not 0<p<1:raise MissingFacts("请核准实际可能出现的第一阶段名额配置。")
    draws=one(rows,r"(?:广播|通知|预告)后.{0,18}均匀无放回",message="需核实广播名额后各组是否均匀无放回抽取。")
    if not re.search(r"(?:各自|独立).{0,5}(?:抽|选)|分别独立",draws["quote"]):
        raise MissingFacts("请核准两组的组内抽取是否各自进行。")
    return dict(kind="quota_mixture",groups=groups,quotas=profiles,weights=[str(p),str(1-p)]), [quota,draws]


def equipment_contrast(q,focus,n):
    parts=re.split(r"减去|减掉",q)
    if len(parts)!=2 or not re.search(r"(?:联合概率|联合机会)",q) or not re.search(r"(?:剩余|其他|其余)安排按原",q):
        raise MissingFacts("请列出按原抽法比较的两个联合设备事件及其减法顺序。")
    ends=[]
    treatments=[]
    for side in parts:
        own=re.search(r"(?:她|他|本人|"+re.escape(focus)+r")(没|未|不|已)?(拿|领|取得|获配|获发)([\w]{0,8}?)(?=而|[，,、。]|$)",side)
        if not own:raise MissingFacts("请说明每一端焦点本人是否实际获得设备。")
        a=int(own[1] not in ("没","未","不"))
        treatments.append((own[2],own[3]))
        if re.search(r"(?:组里|班里|同伴|伙伴|其余).{0,3}(?:没人|无人|都不|均未|都没)(?:拿|领|获|取)",side):
            k=0
        else:
            peers=re.search(r"(?:其余|其餘|另外|剩余)("+N+r")(?:个)?人(?:都|全|均)(?:拿|领|获|取)",side)
            if not peers or count(peers[1])!=n-1:
                raise MissingFacts("名册须覆盖题中全部同伴，才能计算该端的联合设备概率。")
            k=n-1
        ends.append([a,k])
    objects={obj for _,obj in treatments if obj}
    if ends[0]==ends[1] or treatments[0][0]!=treatments[1][0] or len(objects)>1:
        raise MissingFacts("请确认两个不同设备事件使用同一处理变量。")
    period=re.search(r"(散场|离场|结课|课后|学期末|次日|本周|本月|本季)([\w]{1,12}?)差(?:如何|多少|为)",q)
    if not period:raise MissingFacts("请说明所问结果及观测时间。")
    variable=treatments[0][0]+next(iter(objects),"")
    def label(pair):
        return f"{focus}本人{'获得' if pair[0] else '未获得'}设备，同组伙伴中 {pair[1]} 人实际获得设备"
    return dict(kind="original_local",variable=variable,population=[focus],scope="subgroup",weights=["1"],ends=ends,
                intervention=label(ends[0]),reference=label(ends[1]),outcome=period[2],time=period[1],
                remaining="组内及其余安排按原两阶段抽法",joint_requested=True)


def fixed_notice(replies):
    choices=set()
    outstanding=[]
    for row in replies:
        line=row["quote"]
        m=re.fullmatch(r"(?:两端|两边)(?:都|均)?(?:固定|设定)(?:为|成)?(?:本组|焦点组)("+N+r")(?:个)?(?:名额|台|份)(?:的)?(?:预告|通知|广播)(?:[，,](?:只|仅)比较(?:实际)?设备)?",line)
        if m:
            choices.add(count(m[1]))
        elif not re.fullmatch(r"(?:预告|通知)?(?:规则)?(?:还|尚)?(?:没有决定|未决定|不清楚)",line):
            outstanding.append(line)
    return (choices.pop() if len(choices)==1 else None),outstanding


def derive(q,rows):
    inputs=[r for r in rows if not r["source_id"].startswith("user_reply_")]
    replies=[r for r in rows if r["source_id"].startswith("user_reply_")]
    text="。".join(r["quote"] for r in inputs)
    if not (re.search(r"均匀无放回",text) and re.search(NOTICE,text) and re.search(r"额度|名额",text)
            and re.search(r"其余|另外|剩余",q) and re.search(r"联合概率|联合机会",q) and re.search(r"减去|减掉",q)):
        return None
    if re.search(r"非均匀|并非均匀|不是均匀|额度.{0,4}后来改|并非独立|与潜在.{0,8}有关|不一致|(?:预告|广播|通知).{0,10}(?:报错|可能错误|不一定等于|并非实际|并不对应)",text):
        raise MissingFacts("请核准从预告到实际分配的两阶段规则。")
    f=re.search(r"(?:只评(?:价)?|仅评(?:价)?|只看)([\w]{1,14}?)(?=[，,。！？?]|$)",q)
    if not f:raise MissingFacts("请指明唯一的评价对象。")
    focus=f[1]
    names,groups,j,net,spans=group_roster(inputs,focus)
    law,design_spans=quota_design(inputs,names,groups)
    spans.extend(design_spans)
    n=len(groups[j])
    c=equipment_contrast(q,focus,n)
    law["variable"]=c["variable"]
    exp=dict(kind="count")
    joint=native_support(net,law,exp,[focus],c["ends"])
    if not joint:raise MissingFacts("原设计尚不能核算所问两端的联合设备概率。")
    keys=[f"{a},{s}" for a,s in c["ends"]]
    # Crossing each *actual* equipment arm with its announced group quota keeps
    # two marginally positive equipment events from proving a pure equipment effect.
    by_notice={}
    for profile,weight in zip(law["quotas"],law["weights"]):
        quota=profile[j]
        by_notice[str(quota)]={key:str(Fraction(weight)*Fraction(quota if a else n-quota,n)) if a+s==quota else "0"
                                for (a,s),key in zip(c["ends"],keys)}
    if any(sum(Fraction(t[k]) for t in by_notice.values())!=Fraction(joint[focus][k]) for k in keys):
        raise MissingFacts("分预告核算的概率与原设计支持引擎不一致。")
    science=[]
    for pattern,subject in [(r"(?:整个抽法|完整抽签|整份分配).{0,18}潜在.{0,14}(?:无关|独立)","整份随机分配"),
                            (r"实际记录对应实际安排|一致性成立","实际分配一致性")]:
        row=one(inputs,pattern,message="请核对"+subject+"的原文依据。")
        spans.append(row)
        science.append(evidence(row,subject))
    info=one(inputs,r"事件总体(?:平均|均值).{0,8}可查",message="请说明原设计两端的总体条件均值是否可查。")
    spans.append(info)
    proof=dict(method="ANNOUNCED_TWO_STAGE_QUOTA",population=[focus],ordered_events=c["ends"],joint_probabilities=joint,
               joint_by_announced_group_quota=by_notice,quota_profiles=law["quotas"],profile_weights=law["weights"],
               groups=names,focal_group=names[j],group_sizes=list(map(len,groups)),source_spans=spans)
    target={k:c[k] for k in ("scope","population","intervention","reference","outcome","time","remaining")}
    target.update(quantity="difference",treatment_variable=c["variable"],ordered_events=c["ends"])
    probabilities=f"按原抽法，{focus}所问两端（连同本人状态）的联合设备概率依次为 {joint[focus][keys[0]]} 和 {joint[focus][keys[1]]}。"
    supported={focus:joint[focus],"by_announced_group_quota":by_notice}
    notice=one(inputs,NOTICE+r"(?:本身)?(?:会|也会|仍会|不|不会|并不|可能)(?:改变|影响)",message="设备配置相同时，广播内容本身是否仍会影响结果？")
    spans.append(notice)
    for r in spans:
        require_statement(r,"分配规则、总体资料和预告作用")
    science.append(evidence(notice,"预告对结果的直接作用"))
    excluded=bool(re.search(NOTICE+r"(?:本身)?(?:不|不会|并不)(?:改变|影响)",notice["quote"]))
    if excluded and not replies:
        if not re.search(r"别组也?影响不到|其他组.{0,4}不影响|无跨组影响",text):
            raise MissingFacts("请说明原抽法下其他组安排如何进入所求设备效应。")
        facts=dict(contrast=c,network=net,exposure=exp,assignment=law,information=dict(query="event_mean",same_population=True),
                   science=dict(consistent=True,random_full=True,evidence=science))
        result=solve(facts)
        if not result:raise MissingFacts("所列设备事件与原抽法的条件均值尚不能对应。")
        result["proof"].update(proof,notice_resolution="EXCLUDED_BY_SOURCE")
        result["answer"]["functional"]=probabilities+result["answer"]["functional"]
        return result
    goal=one(inputs,r"(?:只要|只求|仅考虑|仅比较).{0,7}(?:设备|仪器).{0,4}(?:作用|效应|影响)",message="请确认所求目标是否仅含设备本身的作用。")
    spans.append(goal)
    if not re.search(r"未曾单独随机|没有单独随机|未独立随机|未另行随机",text):
        raise MissingFacts("请给出是否另行分配预告以及预告和设备的联合支持。")
    if not (re.search(r"未定义固定|没有定义|未指定|尚未约定",goal["quote"]) or replies):
        raise MissingFacts("请标明目标中两端分别如何设置预告。")
    spans.extend(replies)
    target["notice_intervention"]=None
    direction="预告本身"+("可能" if "可能" in notice["quote"] else "会")+"影响结果。原设计的事件均值差同时改变预告和设备。"
    status="NEEDS_INPUT"
    questions=[FIX]
    reason=probabilities+direction
    resolution="UNSPECIFIED"
    if replies:
        selected,additional=fixed_notice(replies)
        if selected is None:
            resolution="UNRESOLVED_REPLY"
            reason+="补充材料尚不能对应到一个可核验的共同预告及跨预告支持。"
        elif additional:
            target["notice_intervention"]=dict(kind="fixed_focal_group_quota",quota=selected)
            resolution="SUPPLEMENTARY_EVIDENCE"
            reason+=f"用户指定了共同的本组 {selected} 名额预告，并提供了其他说明。需要核准这份补充资料与原抽法的关系。"
            questions=["请说明补充资料覆盖哪些预告和实际设备的组合，以及对应的分配依据和总体信息。"]
        else:
            target["notice_intervention"]=dict(kind="fixed_focal_group_quota",quota=selected)
            zero=[k for k in keys if Fraction(by_notice.get(str(selected),{}).get(k,"0"))==0]
            if not zero:raise MissingFacts("请核准固定预告后两个设备事件的共同支持及其他组安排。")
            resolution="FIXED"
            proof["zero_crossed_arms"]=zero
            # At least one desired potential outcome is never observed with this
            # notice. Change this missing mean alone; the original law stays identical.
            reason+=f"两端现均固定为本组 {selected} 名额预告。设备事件 {', '.join(zero)} 与这个预告同时出现的概率为零。保持所有可见结果固定，改变一个缺失组合的潜在均值即可改变所求差，因此现有资料不能点识别。"
            status="NOT_POINT"
            questions=[]
    else:
        reason+="要比较纯设备作用，须先定义共同的预告干预，再核对该预告下两端是否都有支持。"
    proof["notice_resolution"]=resolution
    hand=make_handoff(target,"STOP",[c["variable"],"名额预告",c["outcome"]],[],[],reason,supported)
    return delivery(target,status,reason,None,science,hand,reason,proof,questions)
