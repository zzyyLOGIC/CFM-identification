"""Bind two labelled population rates to one focal unit and an explicitly ordered risk difference."""
import re
from decimal import Decimal
from fractions import Fraction

from .network_estimate_handoff import delivery, execute_handoff, make_handoff
from .network_query_binding import NUMBER, read_rate
from .source_network_review import MissingFacts, evidence, one, require_statement

PEER = r"(?:友站|伙伴|搭档|邻居|同伴|友邻|朋友|邻店|邻站|邻校)"
TITLE = r"(?:驿站|站点|门店|诊所|学校|本店|本校|本站|本人|自身|自己|站|店)"
DENIED = r"(?:不|未|没有|不曾)(?:采用|采纳|接受|承诺|成立)|不能确认|不确认|尚未|未获|拒绝|撤回|不支持|待确认|是否|拟采用|仅假设|不再采用|不予采纳"


def display(x):
    decimal = Decimal(x.numerator)/Decimal(x.denominator)
    return format(decimal,"f") if Fraction(decimal)==x else str(x)


def ordered_target(q):
    people = re.findall(r"(?:只评(?:价)?|仅评(?:价)?|只看)([\w]{1,14})(?=[，,。！？?]|$)", q)
    if len(set(people)) != 1:
        raise MissingFacts("请指明本次评价哪一个焦点单位。")
    focus = people[0]
    own = re.search(re.escape(focus) + TITLE + r"{0,2}(不|未|没|已)?([\w]{1,8}?)时", q)
    if not own:
        raise MissingFacts("请确认焦点本人的处理，在比较两端是否固定于同一状态。")
    a, treatment = int(own[1] not in ("不", "未", "没")), own[2]
    segments = [s for s in re.split(r"[，,。！？?]", q) if re.search(PEER,s) and re.search(r"相对于|相比于?|减去",s)]
    if len(segments) != 1:
        raise MissingFacts("请列明两个同伴处理标签及其比较顺序。")
    labels = re.split(r"相对于|相比于?|减去", segments[0], maxsplit=1)
    arms = []
    for label in labels:
        act = re.escape(treatment)
        if re.fullmatch(r"(?:都|均|全)(?:不|没|未)" + act, label) and a == 0:
            arms.append(0)
        elif re.fullmatch(PEER+r"(?:均|都|全)?(?:不|未|没)" + act, label):
            arms.append(0)
        elif re.fullmatch(PEER + act, label):
            arms.append(1)
        else:
            raise MissingFacts("请核对两端的同伴标签及本人状态与资料中的含义。")
    if set(arms) != {0,1}:
        raise MissingFacts("两端没有给出一对互异的同伴状态。")
    y = re.search(r"(本季|本周|本月|本期|当季|本学期)([\w]{1,15}?(?:率|概率|风险))(?=将|会|降低|减少|下降|增加|上升|提升|变化|改变|相差|差)", q)
    if not y:
        raise MissingFacts("请说明所指的总体率及其观察时期。")
    if re.search(r"相对(?:降低|变化|减少|增长)|百分之几|风险比|比值|降低比例|下降比例|降幅百分比|降低百分比", q):
        raise MissingFacts("请确认要计算两端率的绝对差，还是以参照率为分母的相对变化。")
    reduction = bool(re.search(r"降低|减少|下降", q))
    inverted = bool(re.search(r"后者减前者|参照减干预",q))
    forward = bool(re.search(r"先者减后者|前者减后者|干预减参照|减去",q))
    if (forward and (inverted or reduction)) or (inverted and re.search(r"增加量|提升量", q)):
        raise MissingFacts("降低量与写出的减法方向有冲突，请确认哪一端减哪一端。")
    ordered = list(reversed(arms)) if inverted or reduction else arms
    target = dict(quantity="difference",scope="subgroup",population=[focus],own=a,treatment_variable=treatment,
                  intervention=labels[0],reference=labels[1],outcome=y[2],time=y[1],
                  requested_operation="reference_minus_intervention" if ordered != arms else "intervention_minus_reference")
    return target, dict(zip(arms,labels)), ordered


def counterexample(rates, ordered):
    # U is an example latent selection mechanism. S=U, P(U=1)=1/2 and own treatment
    # can vary independently. Complete every other observed arm identically in both models.
    alternatives = [Fraction(i,4) for i in range(5) if Fraction(i,4) not in rates.values()]
    completions = []
    for missing0, missing1 in ((alternatives[0],alternatives[-1]),(alternatives[-1],alternatives[0])):
        means = [(rates[0]+missing0)/2,(missing1+rates[1])/2]
        completions.append(dict(unobserved_rate_arm0_given_u1=str(missing0), unobserved_rate_arm1_given_u0=str(missing1),
                                causal_difference=str(means[ordered[0]]-means[ordered[1]])))
    return dict(latent_selection="P(U=1)=1/2, S=U。两个模型中本人的处理可同样独立分配",
                observed_rates_given_u=[str(rates[0]),str(rates[1])], models=completions)


def derive(q, rows):
    text = "。".join(r["quote"] for r in rows)
    if not (re.search(r"总体(?:观察|观测).{1,14}(?:率|概率|风险)",text) and re.search(PEER,q)
            and re.search(r"自己选|自选|自行决定",text) and re.search(r"只评|仅评|只看",q)):
        return None
    target, labels, ordered = ordered_target(q)
    focus, a, y, treatment = target["population"][0], target["own"], target["outcome"], target["treatment_variable"]
    if re.search(r"仅为样本|只有样本|只给样本|并非总体|零支持|无支持|没有支持|不一致|不足以|不够描述|尚未固定|未固定|并未固定|不能描述",text):
        raise MissingFacts("请核准实际记录、同伴标签和两个事件的总体正支持。")
    catalog = one(rows,r"两端的?总体(?:观察|观测)"+re.escape(y)+r"(?:为|是)",message="需要所问结果在同一人群和时期的两端总体观察率。")
    if re.search(r"(?:仅覆盖|只来自|只覆盖|另一个|另一家|另一期|全组平均|全网平均|同伴总体|伙伴总体)",text):
        raise MissingFacts("请确认两端总体率确实属于题中这个焦点和时期。")
    catalog_foci = re.findall(r"(?:只评(?:价)?|仅对|只对|仅指|来自)([\w]{1,12}?)(?:本店|本人|本站|[，,。]|的两端)", catalog["quote"])
    if any(n != focus for n in catalog_foci):
        raise MissingFacts("总体率标注的评价对象与原题不同。")
    periods = re.findall(r"上季|本季|本周|上周|本期|上期|本月|上月|本学期",catalog["quote"])
    if any(t != target["time"] for t in periods):
        raise MissingFacts("总体率所属时期与所问时期不一致。")
    entries = re.findall(r"("+NUMBER+r")\s*[（(]([^（）()]+)[）)]",catalog["quote"])
    if len(entries)!=2 or {label for _,label in entries}!=set(labels.values()):
        raise MissingFacts("需要用原标签标出两端分别对应的总体率。")
    by_label = {label:read_rate(v) for v,label in entries}
    rates = {s:by_label[label] for s,label in labels.items()}
    network = one(rows,r"(?:处理前|活动前|季前|事前|干预前|签约前).{0,12}固定",message="请核对用于评价的处理前伙伴关系。")
    support = one(rows,r"均有支持|两端.{0,5}(?:正支持|有支持|可达)",message="请确认焦点本人和同伴的两个联合状态均有正支持。")
    cons = one(rows,r"(?:暴露|处理|观察)记录一致|一致性成立",message="请核对实际记录与对应潜在结果的一致性。")
    suff = one(rows,r"(?:标签|映射).{0,9}(?:足以描述潜在|对潜在.{0,12}充分)",message="请说明同伴标签是否足以刻画该潜在结果。")
    outcome_stem = re.sub(r"(?:概率|风险|率)$","",y)
    if outcome_stem not in suff["quote"] and "潜在结果" not in suff["quote"]:
        raise MissingFacts("暴露充分性所指的结果与原题不同。")
    spans = [catalog,network,support,cons,suff]
    for r in spans:
        require_statement(r,"总体率、支持和暴露条件")
    conditions = [evidence(network,"处理前固定伙伴"),evidence(cons,"实际暴露一致性"),evidence(suff,"暴露映射充分性"),evidence(support,"两端正支持")]
    observed = rates[ordered[0]] - rates[ordered[1]]
    proof = dict(method="LABELED_OBSERVATIONAL_ARMS",observation_regime="observational",population=[focus],
                 ordered_events=[[a,s] for s in ordered], arm_labels={str(s):labels[s] for s in (0,1)},
                 source_spans=spans,descriptive_difference=str(observed))
    arms_text = f"{labels[ordered[0]]} 减 {labels[ordered[1]]}"
    observed_text = f"{arms_text}的总体观察差为 {display(rates[ordered[0]])} − {display(rates[ordered[1]])} = {display(observed)}"
    admissions = [r for r in rows if re.search(r"联合(?:暴露|状态).{0,25}无条件可交换性",r["quote"]) and
                  re.search(r"采用|采纳|承诺",r["quote"]) and not re.search(DENIED,r["quote"])]
    confound = [r for r in rows if re.search(r"(?:未记|未观测|未测|遗漏).{0,18}(?:同时|共同).{0,8}(?:左右|影响|决定)",r["quote"])
                and treatment in r["quote"] and outcome_stem in r["quote"]]
    ruled_out = [r for r in rows if re.search(r"(?:没有|无)其他可交换条件或工具|没有其他识别条件",r["quote"])]
    denied = any(re.search(DENIED,r["quote"]) and "可交换" in r["quote"] for r in rows)
    if admissions and (confound or denied):
        raise MissingFacts("无条件交换性的采用记录与另一条材料冲突，请核准适用的协议。")
    if not admissions:
        if not (confound and ruled_out):
            raise MissingFacts("是否有依据让焦点本人与同伴的联合暴露对潜在结果无条件可交换，或另有识别资料？")
        spans.extend(require_statement(r,"未记录的共同原因及其他识别资料") for r in (confound[0],ruled_out[0]))
        conditions.append(evidence(confound[0],"未记录的共同原因"))
        witness = counterexample(rates,ordered)
        proof["witness"] = witness
        values = [display(Fraction(m["causal_difference"])) for m in witness["models"]]
        reason = f"只评{focus}，本人状态固定为 {a}。{observed_text}。未记录的共同原因同时影响处理和结果。两种与相同观察资料相容的潜在结果模型可使因果差分别为 {'、'.join(values)}，所以不能点识别。"
        hand = make_handoff(target,"STOP",[treatment,y],[],[],reason,{"positive_both":True})
        return delivery(target,"NOT_POINT",reason,None,conditions,hand,reason,proof)
    exchange = require_statement(admissions[0],"无条件可交换性")
    if len(admissions)!=1 or not (focus in exchange["quote"] and re.search(PEER,exchange["quote"])
            and (outcome_stem in exchange["quote"] or "潜在结果" in exchange["quote"])):
        raise MissingFacts("请核对无条件交换性所覆盖的焦点、同伴联合状态及潜在结果。")
    spans.append(exchange)
    conditions.append(evidence(exchange,"本人和同伴联合暴露无条件可交换"))
    queries = [dict(id=f"{focus}|{a},{s}",kind="person_event_mean",unit=focus,own=a,exposure=s,event_label=labels[s],
                    exposure_rule="reported_peer_label",treatment=treatment,outcome=y,time=target["time"]) for s in ordered]
    population_values = {query["id"]:str(rates[s]) for s,query in zip(ordered,queries)}
    proof["population_values"] = population_values
    formula = f"只评{focus}且固定本人状态为 {a}。按协议，两端的潜在均值等于标签对应的总体观察率。{observed_text}（{display(observed*100)} 个百分点）。"
    hand = make_handoff(target,"ESTIMATE_POINT",[treatment,y],queries,[[1,-1]],formula,{"positive_both":True})
    return delivery(target,"POINT",formula,execute_handoff(hand,population_values),conditions,hand,formula,proof)
