"""Standardization when the protocol directly supplies strata, arm means and support."""
import re
from fractions import Fraction
from .network_query_binding import NUMBER, RATE, read_rate
from .network_estimate_handoff import delivery, make_handoff, execute_handoff
from .source_network_review import MissingFacts, evidence, one

LABEL=r"[\u3400-\u9fffA-Za-z0-9]{1,12}"
PEERS=r"伙伴|同伴|邻居|朋友"
NEG=r"全没|都不|都没|全不|全未|无人|没有(?:伙伴|邻居|朋友)"


def derive(q,rows):
    text="。".join(r["quote"] for r in rows)
    if not (re.search(r"自选|自己定|自行决定",text) and re.search(r"联合(?:暴露|状态)可交换",text)
            and re.search(r"两个(?:端点|总体条件均值)",text) and re.search(r"按.{1,22}(?:构成|比例).{0,5}平均",q)):
        return None
    if re.search(r"不采用|未采用|无法保证|不成立|不固定|回忆登记|事后确定|后来才|未确认|条件不同|相减顺序不明|顺序(?:不明|未知|反过来)|不知哪端|未标.{0,6}(?:左右|哪一端)|不可用于|只有样本|没有总体均值|来自另[一外]|未记.{0,12}(?:同时|共同)|原表顺序|降低量|第二问|反向再",q+"。"+text):
        raise MissingFacts("请核对观察性比较采用的条件，以及分层总体均值的对象、来源和相减顺序。")
    focus=re.search(r"(?:只管|只评价|只评)([\u3400-\u9fffA-Za-z0-9]+?)(?=本人|自身|[，,。！？])",q)
    own=re.search(r"(?:自身|自己|本人)(没|不|未|已)?([^，,。]{1,6}?)时",q)
    part=next((s for s in re.split(r"[，,。！？]",q) if re.search(PEERS,s) and re.search(r"相对于|相比|相对|减",s)),None)
    if not focus or not own or not part:return None
    focus=focus[1];a=int(own[1] not in ("没","不","未"));treatment=own[2]
    sides=re.split(r"相对于|相比|相对|减去|减",part,maxsplit=1)
    if len(sides)!=2 or not all(treatment in s for s in sides):return None
    arms=[0 if re.search(NEG+"|(?:无|没有)"+re.escape(treatment),s) else 1 for s in sides]
    if set(arms)!={0,1}:return None
    sample=re.search(r"(本季|本周|本月)([^，,。！？]{1,18}?)(?:差多少|平均差)",q)
    activity=re.search(r"在([^，,。]{1,14}中)[，,]",q)
    point_outcome=re.search(r"(?:多少|几)([^，,。！？]{1,12}?)(?=[？?，,。])",q)
    if sample:period,outcome=sample.groups()
    elif activity and point_outcome:period,outcome=activity[1],point_outcome[1]
    else:return None
    named_outcomes=re.findall(r"两个端点的总体([^，,。；]{1,12}?)(?:是|为)"+NUMBER,text)
    aliases={"再次购买概率":"回购率","再次购买率":"回购率"}
    if any(aliases.get(outcome,outcome)!=aliases.get(y,y) for y in named_outcomes):
        raise MissingFacts("题中的结果与所给两端总体指标不同，请核对。")
    if any(name!=focus for name in re.findall(r"都是("+LABEL+r")的(?:[，。]|$)",text)):
        raise MissingFacts("分层均值所属对象与评价对象不同，请核对。")
    exchange=one(rows,r"联合(?:暴露|状态)可交换",message="需逐层的本人和同伴联合暴露可交换性。")
    network=one(rows,r"(?:干预前|活动前|开课前|处理前|季前).{0,15}固定",message="需确定用于暴露的处理前固定关系。")
    suff=one(rows,r"(?:标签|映射).{0,15}(?:潜在结果充分性|足以描述潜在)",message="需确定所用同伴标签能否充分刻画潜在结果。")
    cons=one(rows,r"一致性(?:成立)?",message="请说明实际观察与潜在结果的一致性。")
    stated={};mass_rows=[]
    for row in rows:
        for m in re.finditer(r"(?:^|[，,])("+LABEL+r")占("+RATE+r"|其余|剩余)",row["quote"]):
            if m[1] in stated:raise MissingFacts("同一个分层有多份权重记录，请核准。")
            stated[m[1]]=None if m[2] in ("其余","剩余") else read_rate(m[2])
            mass_rows.append(row)
    pair=re.search(r"在("+LABEL+r")(?:与|和)("+LABEL+r")分别",exchange["quote"])
    if pair:
        names=list(pair.groups())
        if set(stated)-set(names):raise MissingFacts("层内交换性的对象和提供总体权重的分层不一致。")
        weights={k:stated.get(k) for k in names}
    elif len(stated)==2 and re.search(r"在([^，,]{1,8})内联合状态可交换",exchange["quote"]):
        cov=re.search(r"在([^，,]{1,8})内联合状态可交换",exchange["quote"])[1]
        if not all(cov in n for n in stated) or not re.search(r"两种"+re.escape(cov),q):return None
        weights=stated
    else:return None
    if len(weights)!=2 or len([w for w in weights.values() if w is None])>1:
        raise MissingFacts("请提供两层的总体质量及完整覆盖声明。")
    missing=[k for k,w in weights.items() if w is None]
    if missing:weights[missing[0]]=1-sum(v for v in weights.values() if v is not None)
    if sum(weights.values())!=1 or any(w<=0 for w in weights.values()):
        raise MissingFacts("两层的正总体权重需要合计为一。")
    target=dict(quantity="difference",scope="subgroup",population=[focus],intervention=sides[0],reference=sides[1],
                outcome=outcome,time=period,own=a,treatment_variable=treatment)
    science=[evidence(network,"处理前固定关系"),evidence(suff,"暴露映射充分性"),evidence(cons,"一致性"),evidence(exchange,"层内联合暴露均值交换性")]
    spans=[network,suff,cons,exchange,*mass_rows]
    proof=dict(method="OBSERVED_REPORTED_STRATA",stratum_masses={k:str(v) for k,v in weights.items()},population=[focus],
               ordered_events=[[a,s] for s in arms],observation_regime="observational",source_spans=spans)
    support={};values={};queries=[];coefs=[]
    for layer,w in weights.items():
        queried=[r for r in rows if layer in r["quote"]]
        zero=next((r for r in queried if re.search(re.escape(layer)+r"[^，。；]{0,8}(?:从未|不可能).{0,20}(?:不可能|出现)",r["quote"])),None)
        if zero:
            if any(re.search(r"两端(?:都|均)?(?:有支持|可能|可达)",r["quote"]) for r in queried):
                raise MissingFacts("该层同时记载了零支持和两端正支持，请核对适用记录。")
            pos=zero["quote"]
            own_low=bool(re.search(r"本人(?:没|未|不)"+re.escape(treatment),pos))
            if not own_low or a!=0 or not re.search(r"有(?:伙伴|邻居|朋友)"+re.escape(treatment),pos):
                raise MissingFacts("请确认该层零支持对应原题的哪一个本人和同伴事件。")
            unrestricted=next((r for r in rows if re.search(r"没有跨.{0,12}可迁移性",r["quote"]) and "进一步限制" in r["quote"]),None)
            if not unrestricted:
                raise MissingFacts("该总体层缺少一个比较端的支持；是否有额外可用的迁移资料或限制？")
            signed=w*(1 if arms[0]==1 else -1)
            formula=f"在{layer}固定所有可观测均值，让达不到的臂的潜在均值分别取 t 和 t+1。两种模型的观测分布相同，总体效应相差 {signed}。"
            proof.update(zero_event=[layer,a,1],witness_difference=str(signed))
            spans.extend([zero,unrestricted])
            support[layer]={"own":a,"exposure":1,"probability":"0"}
            h=make_handoff(target,"STOP",[treatment,outcome],[],[],formula,support)
            return delivery(target,"NOT_POINT",formula,None,science,h,"正质量分层失去一个干预端的支持。"+formula,proof)
        positivity=next((r for r in queried if re.search(r"两端(?:都|均)?(?:有支持|可能|可达)",r["quote"])),None)
        if not positivity:raise MissingFacts("请说明每个正质量分层内，所问联合状态的两端是否都有支持。")
        support[layer]="所问两端均有正支持";spans.append(positivity)
        pairs=[]
        for r in queried:
            clauses=re.split(r"[，,]",r["quote"]);active=False
            for clause in clauses:
                if layer in clause:active=True
                elif any(other in clause for other in weights if other!=layer):active=False
                if not active:continue
                m=re.search(r"(?:是|为)("+NUMBER+r")(?:与|和|、)("+NUMBER+r")\s*$",clause)
                if m:pairs.append((m[1],m[2],r))
        if len(pairs)!=1:raise MissingFacts("需要每一层按原题两端排列的两个总体条件均值。")
        v1,v2,data=pairs[0];spans.append(data)
        for s,v,sign in zip(arms,[v1,v2],[1,-1]):
            key=f"{focus}|{layer}|{a},{s}"
            queries.append(dict(id=key,kind="reported_stratum_arm_population_mean",unit=focus,stratum=layer,own=a,exposure=s,
                                outcome=outcome,time=period,treatment=treatment))
            numeric=v.replace("−","-");values[key]=str(Fraction(numeric[:-1])/100 if numeric.endswith("%") else Fraction(numeric))
            if re.search(r"(?:概率|率)$",outcome) and not 0<=Fraction(values[key])<=1:
                raise MissingFacts("所列总体概率超出零到一，请核对取值或单位。")
            coefs.append(sign*w)
    proof.update(population_values=values,support_origin="材料明确给出每层两端的正支持")
    form=" + ".join(f"({w})×[μ({layer},本人={a},同伴={arms[0]})−μ({layer},本人={a},同伴={arms[1]})]" for layer,w in weights.items())
    hand=make_handoff(target,"ESTIMATE_POINT",[treatment,outcome,"处理前分层"],queries,[coefs],form,support)
    return delivery(target,"POINT",form,execute_handoff(hand,values),science,hand,
                    "按原资料所列的层内充分性、可交换性、一致性和正支持，分别取两端的观察总体均值，再按目标层构成加权。",proof)
