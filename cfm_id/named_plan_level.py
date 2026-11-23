"""Expected level under a finite distribution of named, supported full plans."""
import re
from fractions import Fraction
from .network_estimate_handoff import delivery, execute_handoff, make_handoff
from .network_query_binding import RATE, NUMBER, read_rate
from .source_network_review import MissingFacts, ORD, count, evidence, one

# Use the order fixed by the unit-level table, including explicit ordinal weights.
TABLE = re.compile(r"^(?P<label>[A-Za-z0-9\u3400-\u9fff]{1,12}?)(?:单|方案|计划)"
                   r"(?P<meta>[^。；=:：]{0,40}?)(?:为|是|[:：=])\s*(?P<values>"
                   +NUMBER+r"(?:\s*[、,，]\s*"+NUMBER+r")+)\s*$")


def unit_weights(question, size):
    if re.search(r"(?:等权|同权|平均分配权重)",question):
        if re.search(r"(?:按|权重|占)\s*"+RATE,question):
            raise MissingFacts("评价对象的权重有两种记录，请确定评价顺序及各自权重。")
        return [Fraction(1,size)]*size
    explicit=list(re.finditer(r"(?:第)?("+ORD+r")([\u3400-\u9fff]{1,3}?)(?:按|权重为|占)("+RATE+r")",question))
    remainder=re.search(r"(?:另|其余|剩下)("+ORD+r")?[^，。；、]{0,6}?各(?:按|占)?("+RATE+r")",question)
    weights=[None]*size
    for m in explicit:
        pos=count(m[1])-1
        if not 0<=pos<size or weights[pos] is not None:
            raise MissingFacts("请核对评价对象的顺序与权重。")
        weights[pos]=read_rate(m[3])
    if remainder:
        if remainder[1] and count(remainder[1])!=weights.count(None):
            raise MissingFacts("其余对象数与总体结果表不一致，请核对评价名单。")
        weights=[read_rate(remainder[2]) if w is None else w for w in weights]
    if None in weights or sum(weights)!=1:
        raise MissingFacts("请给出与整单结果表顺序一致且合计为一的单位权重。")
    return weights


def derive(q, rows):
    text="。".join(r["quote"] for r in rows)
    if (not re.search(r"(?:办法|政策|方案|计划).{0,12}(?:水平|平均|期望)",q)
            or not re.search(r"整份|整张|完整方案",text) or not re.search(r"总体",text)):
        return None
    if re.search(r"差多少|相对于|相比|分别计算|还(?:求|要比较)|减去|预测.{0,12}实现",q):
        return None
    table={}
    source_rows=[]
    outcome=None
    for row in rows:
        m=TABLE.fullmatch(row["quote"])
        if not m:
            continue
        label=m["label"]
        if label in table:
            raise MissingFacts("同一完整方案有多份结果表，请确认适用的总体资料。")
        parsed=[v.replace("−","-") for v in re.findall(NUMBER,m["values"])]
        table[label]=[Fraction(v[:-1])/100 if v.endswith("%") else Fraction(v) for v in parsed]
        source_rows.append(row)
        y=re.search(r"总体(.+)$",m["meta"])
        if y:
            if outcome and outcome!=y[1]:
                raise MissingFacts("请核对各完整方案是否使用同一结果指标。")
            outcome=y[1]
    if len(table)<2 or not outcome:
        return None
    labels=list(table)
    unit_count=len(table[labels[0]])
    if any(len(v)!=unit_count for v in table.values()):
        raise MissingFacts("各方案的评价对象数不同，请提供同一人群的总体结果。")
    weights=unit_weights(q,unit_count)
    history=one(rows,r"(?:历史|原(?:来|先)|试验).{0,35}(?:随机分配|随机指派|随机抽取)",
                message="请说明历史各完整方案的分配及支持。")
    hd=history["quote"]
    independence=one(rows,r"(?:与|和).{0,12}潜在.{0,10}(?:无关|独立)|独立于.{0,10}潜在",
                     message="请说明完整方案的分配与潜在结果的关系。")
    consistency=one(rows,r"记录一致|对应.{0,10}实际完整|一致性成立",message="请说明观察结果与实际完整方案下潜在结果的关系。")
    policy=one(rows,r"(?:整(?:张|份|个)(?:单|方案|计划)|完整方案).*(?:抽取|只抽)|只抽.{0,8}(?:整张|整份|完整)",message="请给出目标政策对各完整方案的联合抽取概率。")
    row=policy["quote"]
    negative=r"未随机|不随机|不独立|不一致|并非总体|(?:只有|仅有|仅为)样本|(?:新|下)(?:月|季).{0,25}(?:改变|漂移|另换|新总体|无法沿用)|(?:拒绝|不能|不可|不再)(?:外推|沿用|迁移)|各自(?:独立|抽签)|更换(?:了)?(?:人群|评价对象)|(?:实际实现|实际将|实际会|当月实现)|(?:变更|新增|替换).{0,6}(?:方案|排片单|人群)|(?:未确认|尚不清楚|不能保证).{0,20}(?:随机|独立|一致)|单位顺序(?:相反|改变|不明)|(?:此表|另一单).{0,10}(?:倒序|反序)"
    if re.search(negative,text+"。"+q):
        raise MissingFacts("请核对原总体、目标时期与各整份方案的支持；更换响应规律需要额外的迁移依据。")
    pm={}
    named=re.findall(r"(?:^|[，,、])\s*([A-Za-z0-9\u3400-\u9fff]{1,10}?)(?:单|方案|计划)?(?:占|概率为|的概率为)("+RATE+r")",row)
    if any(k not in table and read_rate(v)>0 for k,v in named):
        raise MissingFacts("目标政策还给其他完整方案分配了正概率，请补齐这些方案的历史支持和总体结果。")
    for k in labels:
        rates=re.findall(re.escape(k)+r"(?:单|方案|计划)?(?:占|概率为|的概率为)("+RATE+r")",row)
        if len(rates)==1:
            pm[k]=read_rate(rates[0])
        elif rates:
            raise MissingFacts("同一方案出现多种概率，请确定实际政策。")
    for label in set(labels)-pm.keys():
        if len(pm)==len(labels)-1 and re.search(r"(?:其他|其余|剩余)(?:全|均|都)?为"+re.escape(label)+r"(?:单|方案|计划)?(?:[，,。]|$)",row):
            pm[label]=1-sum(pm.values())
    if set(pm)!=set(labels) or sum(pm.values())!=1 or not all(0<=w<=1 for w in pm.values()):
        raise MissingFacts("请说明各完整方案的政策概率及剩余概率归属。")
    active=[k for k in labels if pm[k]>0]
    all_supported=all(k in hd for k in labels) and re.search(r"(?:均|都|皆)(?:有正支持|出现|可见)|均有正概率",hd)
    for k in active:
        if not all_supported and not re.search(re.escape(k)+r"(?:单|计划|方案)?(?:有正支持|有正概率|出现过)",text):
            raise MissingFacts("请说明目标政策中每个有正权重的完整方案是否在历史总体有正支持。")
    unsupported=r"从未出现|未出现|未获支持|没有支持|不曾出现|零支持"
    for clause in re.split(r"[，,。；]",text):
        if re.search(unsupported,clause):
            affected=[k for k in labels if re.search(re.escape(k)+r"(?:单|计划|方案)?(?:在历史中|历史上)?(?:"+unsupported+r")",clause)]
            if not affected or set(affected).intersection(active):
                raise MissingFacts("新政策正权重的完整方案存在历史零支持或支持未核清，请补充相应依据。")
    for other in rows:
        if other==policy or other in source_rows:
            continue
        for k in labels:
            m=re.search(re.escape(k)+r"(?:单|方案|计划)?(?:占|概率为|的概率为)("+RATE+r")",other["quote"])
            if m and not re.search(r"历史|旧政策",other["quote"]) and read_rate(m[1])!=pm[k]:
                raise MissingFacts("政策概率在材料中有冲突，请说明哪份记录适用于这次比较。")
    time=re.search(r"(?:来|下|本)(?:月|季|周|期)|本轮|新政策",q)
    if not time:
        return None
    unit_match=re.search(r"(?:第)?"+ORD+r"([\u3400-\u9fff]{1,3}?)(?:按|权重为|占)"+RATE,q)
    unit_name=unit_match[1] if unit_match else "个评价单位"
    target=dict(quantity="level",scope="whole",population=[f"第{i+1}{unit_name}" for i in range(unit_count)],
                intervention=row,reference="",outcome=outcome,time=time[0],remaining="按目标政策抽取一份完整方案",
                response_population="原研究同一总体下各整份方案的响应")
    queries=[];coefficients=[];values={}
    for label in labels:
        if pm[label]==0:continue
        for i,w in enumerate(weights):
            if not w:continue
            key=f"{label}|{i+1}"
            queries.append(dict(id=key,kind="whole_plan_unit_population_mean",plan=label,unit=target["population"][i],
                                outcome=outcome,time="历史方案的总体资料"))
            coefficients.append(pm[label]*w);values[key]=str(table[label][i])
    levels={k:str(sum(w*y for w,y in zip(weights,v))) for k,v in table.items()}
    form="按原研究总体的方案响应，政策期望水平为 "+" + ".join(f"({pm[k]})×{levels[k]}" for k in labels if pm[k])
    hand=make_handoff(target,"ESTIMATE_POINT",["完整方案","单位","总体结果"],queries,[coefficients],form,
                      dict(historical_plans=active,source=hd))
    val=execute_handoff(hand,values)
    proof=dict(method="NAMED_FULL_PLAN_LEVEL",population_values=values,policy_probabilities={k:str(v) for k,v in pm.items()},
               response_population=target["response_population"],new_population_transport="NOT_ESTABLISHED",
               unit_weights=list(map(str,weights)),plan_levels=levels,source_spans=[history,independence,consistency,policy,*source_rows])
    reason="同一研究总体内，以政策概率对有历史支持的整份方案均值加权。该值是政策期望。若另问不同日历期人群的结果水平，需要响应规律可迁移的依据。"
    return delivery(target,"POINT",form+" = "+val,val,[evidence(independence,"整份方案随机"),evidence(consistency,"一致性"),evidence(history,"整份方案正支持")],hand,reason,proof)
