"""Whole-population levels under an all-on/all-off policy and a fixed-size historical draw."""
import re
from fractions import Fraction
from math import comb
from cfm_id_llm.network_files import MAX_NODES

from .direct_network import AssignmentSpec, types
from .network_estimate_handoff import delivery, execute_handoff, make_handoff
from .network_query_binding import NUMBER
from .source_network_review import ORD, MissingFacts, count, evidence, one, require_statement

SIZE=ORD
QUOTA=re.compile(r"从("+SIZE+r")(?P<units>[\w]{1,10}?)(?:中|里)(?:均匀|等概率)(?:随机)?抽(?:出|取)?("+SIZE+r")")
ALL=r"同时|全部|全体|全都|都"
POS_BRIDGE=r"(?:均值|平均结果).{0,6}(?:只随|仅随|仅取决于|只取决于).{0,18}(?:伙伴|搭档|同伴)"
DENY_BRIDGE=r"(?:拒绝|不采用|不作|不允许|没有).{0,35}(?:相等|跨名单|迁移|跨安排|等价)"


def derive(q,rows):
    if not re.search(r"(?:同时|全部|全体|全都)",q) or not re.search(r"平均[^，。？]{1,22}(?:多少|几)",q):
        return None
    matches=[(r,m) for r in rows if (m:=QUOTA.search(r["quote"]))]
    if not matches:return None
    if len(matches)!=1:
        raise MissingFacts("请核准历史抽取的总人数和固定名额。")
    law,m=matches[0];n=count(m[1]);quota=count(m[3])
    if not 0<=quota<=n or n<2:
        raise MissingFacts("原抽签的总数与名额不相容。")
    if n>MAX_NODES:
        raise MissingFacts("此处核验需要一份大小在支持范围内的完整名单。")
    unit=re.sub(r"^[个间家名所座](?=.)","",m["units"])
    rest=law["quote"][m.end():]
    act=re.match(r"(?:[个间家名所座])?(?:"+re.escape(unit)+r")?([\w]{1,14}?)(?=[，,。；]|$)",rest)
    if not act or not re.search(r"(?:其他|其余).{0,5}(?:不|未|为0)",law["quote"]):
        return None
    treatment=act[1]
    binary=re.search(r"(?:"+ALL+r")(不|未)?"+re.escape(treatment),q)
    if not binary or re.search(r"相对|相比|减去|第二问|各自.{0,4}概率",q):return None
    state=int(binary[1] is None)
    pop_match=re.search(r"("+SIZE+r")(?:个|间|家|名|所|座)?[^，。]{0,8}?"+re.escape(unit)+r"(?:"+ALL+r")",q)
    if (pop_match and count(pop_match[1])!=n) or (not pop_match and not re.search(r"所有|全部|全体",q)):
        raise MissingFacts("请核对目标政策覆盖的全体单位与原设计名单。")
    if not re.search(r"同样的权重|等权|同权|权重相同",q):
        raise MissingFacts("请说明各评价单位在政策水平中的权重。")
    outcome=re.search(r"平均([^，。？\s]{1,14}?)(?:是|为)?(?:多少|几)",q)
    period=re.search(r"那一[晚天周]|当[日晚天周]|本[周月季期]|这一[天晚周]|干预期",q)
    if not outcome or not period:return None
    text="。".join(r["quote"] for r in rows)
    if re.search(r"并非均匀|名额(?:不固定|改为)|(?:并非|不再|未必)按.{0,10}抽|可自由(?:拒绝|参加)|未必执行|仅为样本|资料.{0,9}冲突",text):
        raise MissingFacts("请核对本期固定名额的分配规则及其与实际处理的关系。")
    # Node positions stand for roster positions in the outcome table. The
    # complete-randomization law uses only N and the quota, never network edges.
    units=[f"第{i+1}{unit}" for i in range(n)]
    net=types.NetworkExposureSpec(network_id="roster-for-full-policy-probability",node_ids=units,undirected_edges=[])
    law_spec=types.CompleteRandomizationDesignV1(m=quota)
    plan={node:state for node in units}
    actual=AssignmentSpec(law_spec).full_assignment_probability(net,plan)
    expected=Fraction(1,comb(n,quota)) if n*state==quota else Fraction(0)
    if actual!=expected:raise MissingFacts("完整名单的两种概率核算不一致。")
    if actual:return None
    exog=one(rows,r"抽签.{0,20}潜在.{0,12}(?:独立|无关)|独立于.{0,8}潜在",message="请核对整份名单的随机化依据。")
    cons=one(rows,r"实际.{0,12}(?:对应|等于).{0,10}(?:单|安排)|一致性成立",message="请说明记录是否对应实际完整安排。")
    catalog=one(rows,r"(?:各张|每张|各份|每份|所有).{0,6}可抽.{0,16}(?:各|每).{0,9}总体均值",message="请说明历史总体均值覆盖哪些完整安排。")
    denied=[r for r in rows if re.search(DENY_BRIDGE,r["quote"])]
    accepted=[r for r in rows if re.search(POS_BRIDGE,r["quote"])]
    spans=[law,exog,cons,catalog]
    for row in spans:
        require_statement(row,"分配设计和完整安排的总体资料")
    if (re.search(r"不独立|不一致|未承诺|无法确认|并非对应|(?:只有|仅有)样本|总体均值(?:不全|未知|不可用)|(?:另有|另给|外部|直接提供).{0,25}(?:均值|平均)",text)
            or any(re.search(r"不只|不光|并非|(?:未|不|没有)(?:采用|采纳|证据|接受|承认)|是否|拒绝",r["quote"]) for r in accepted)
            or (denied and accepted)):
        raise MissingFacts("请核对原随机安排、直接提供的政策均值和跨名单条件。")
    target=dict(quantity="level",scope="whole",population=units,intervention=f"全体{n}{unit}"+("均" if state else "均不")+treatment,
                reference="",outcome=outcome[1],time=period[0],unit_weights=[str(Fraction(1,n))]*n)
    support=dict(target_full_assignment_probability=str(actual),historical_treated_quota=quota,roster_size=n,
                 supported_full_assignments=comb(n,quota))
    proof=dict(method="FIXED_QUOTA_WHOLE_POLICY",target_assignment=[state]*n,design="complete_randomization",
               support=support,source_spans=spans)
    conditions=[evidence(exog,"整份名单随机"),evidence(cons,"实际安排一致性")]
    if denied:
        # The explicit refusal licenses two completions on the unsupported atom.
        # A refusal of just one proposed bridge would not suffice.
        if not any(re.search(r"不同完整.{0,18}(?:任何|一切).{0,18}(?:相等|等价)",r["quote"])
                   and re.search(r"不作迁移|不允许迁移|拒绝.{0,25}跨名单限制",r["quote"]) for r in denied):
            raise MissingFacts("请说明是否还有可约束该完整政策潜在均值的资料或跨名单限制。")
        spans.extend(denied)
        conditions.append(evidence(denied[0],"跨完整名单的限制未获采用"))
        form=f"原目标是 {n} 个单位在同一完整政策下的等权潜在均值。历史每次处理 {quota} 个，该政策处理 {state*n} 个，联合概率为 0。"
        reason="在两种模型中保持所有可抽名单的潜在结果相同，只将目标名单下各单位的均值分别设为 0 或 1。观测分布完全相同，政策均值分别为 0 和 1，原政策水平不能点识别。"
        proof["witness"]=dict(observed_law_unchanged=True,unchanged_on="all_supported_full_assignments",target_levels=["0","1"])
        h=make_handoff(target,"STOP",[treatment,outcome[1]],[],[],form,support)
        return delivery(target,"NOT_POINT",form+reason,None,conditions,h,reason,proof)
    if not accepted:
        raise MissingFacts("该完整政策在原设计下概率为零。是否有适用于目标名单的均值等价条件，或直接可用的目标总体均值？")
    bridge=require_statement(accepted[0],"所有名单下的局部均值等价")
    if len(accepted)!=1 or not re.search(r"所有名单|全部(?:完整)?(?:安排|名单)",text):
        raise MissingFacts("请确认局部均值等价条件是否也覆盖原设计达不到的完整政策。")
    # A stated fixed, disjoint partnership gives each target unit exactly one peer.
    if n%2 or not re.search(r"每对.{0,15}(?:前|事先).{0,6}(?:定|固定)|预先.{0,9}固定搭档",text):
        raise MissingFacts("请核对预先固定的成对伙伴以及每个单位的对应范围。")
    if state:
        mass=Fraction(quota*(quota-1),n*(n-1))
    else:
        mass=Fraction((n-quota)*(n-quota-1),n*(n-1))
    if not mass:raise MissingFacts("相同局部状态也没有原设计支持，还需要其他识别依据。")
    label=r"两.{0,3}都"+("不" if not state else "")+r"(?:亮|开|处理|启用|参加)"
    row=one(rows,label+r"时.{0,22}(?:总体|人口).{0,12}均值(?:依次|分别)",message="请提供各单位在所需伙伴状态下可查询的总体均值。")
    y=outcome[1]
    if "晚" in period[0]:
        y=re.sub(r"^(?:夜间|夜|当晚|晚间)","",y)
    same_action=treatment in row["quote"] or ("灯" in treatment and "灯" in bridge["quote"] and "灯" in row["quote"])
    if (not y or y not in bridge["quote"] or not re.search(r"(?:总体|人口)"+re.escape(y)+r"均值",row["quote"])
            or not same_action):
        raise MissingFacts("请核对跨名单的均值条件和总体表是否属于原题同一结果与处理。")
    require_statement(row,"各评价单位的局部总体均值")
    data=re.search(r"均值(?:依次|分别)(?:是|为)("+NUMBER+r"(?:[、,，]"+NUMBER+r")*)$",row["quote"])
    if not data:return None
    nums=re.findall(NUMBER,data[1])
    if len(nums)!=n:raise MissingFacts("局部均值表的长度与评价名单不一致。")
    queries=[dict(id=u,unit=u,kind="unit_partner_state_mean",own=state,partner_treatment=state,treatment=treatment,outcome=outcome[1],time=period[0]) for u in units]
    form=f"全体政策下各单位的均值由本人和固定伙伴均取 {state} 的局部总体均值给出，再按 1/{n} 求和。"
    h=make_handoff(target,"ESTIMATE_POINT",[treatment,outcome[1]],queries,[[Fraction(1,n)]*n],form,{**support,"local_arm_probability":str(mass)})
    values=dict(zip(units,nums))
    proof.update(population_values=values,local_arm_probability=str(mass))
    spans.extend([bridge,row])
    return delivery(target,"POINT",form,execute_handoff(h,values),conditions+[evidence(bridge,"全名单均值等价")],h,form,proof)
