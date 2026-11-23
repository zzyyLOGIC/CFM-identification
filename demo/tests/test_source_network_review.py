"""Source-driven integration with independent oracles and adverse changes to evidence."""
from fractions import Fraction
from itertools import product
import pytest

from cfm_id.direct_verification import replay, verify
from cfm_id.network_estimate_handoff import evaluate_from_catalog

DRAFT={"answer":{"status":"NOT_COVERED","target":{"quantity":"difference"},"estimate_handoff":{"mode":"STOP"}}}

def resolve(question,doc,extra=""):
    sources=[dict(source_id="protocol",kind="OTHER",label="原始协议",text=doc)]
    if extra:sources.append(dict(source_id="note",kind="OTHER",label="补充",text=extra))
    case=dict(case_id="independent-scenario",business_question=question,sources=sources)
    result=verify(case,DRAFT,network_focus=True)
    assert replay(case,DRAFT,result)
    assert result["draft"]==DRAFT and all(result[k] is False for k in ("scientific_approval","production_admission","estimation_handoff_allowed"))
    return result

P="编辑要看本周新方案下的平均水平。第一组按1/4计、另两组各3/8。"
PT="历史把整份亮、暗计划随机分配，两单都出现，和全部潜在出勤无关，记录一致。亮计划三组总体出勤数为10、2、4；暗计划为4、8、6。本周只抽一次整份计划，亮占2/5、其他全为暗。"

def test_named_policies_weight_units_in_order_without_inventing_a_binary_assignment():
    r=resolve(P,PT);a=r["effective_answer"];h=a["estimate_handoff"]
    assert a["status"]=="POINT" and a["target"]["population"]==["第1组","第2组","第3组"] and not a["target"]["reference"]
    oracle=sum(p*w*z for p,table in [(Fraction(2,5),[10,2,4]),(Fraction(3,5),[4,8,6])]
                        for w,z in zip([Fraction(1,4),Fraction(3,8),Fraction(3,8)],table))
    assert Fraction(a["value"])==oracle
    assert len(h["queries"])==6 and set(q["plan"] for q in h["queries"])=={"亮","暗"}
    for i,q in enumerate(h["queries"]):
        assert Fraction(evaluate_from_catalog(h,lambda t:int(t==q)))==[Fraction(2,5),Fraction(3,5)][i//3]*[Fraction(1,4),Fraction(3,8),Fraction(3,8)][i%3]

def test_policy_queries_only_require_support_of_positive_weight_plans():
    doc=PT.replace("两单都出现","亮计划有正支持、暗计划从未出现").replace("亮占2/5","亮占1")
    a=resolve(P,doc)["effective_answer"]
    assert a["status"]=="POINT" and {q["plan"] for q in a["estimate_handoff"]["queries"]}=={"亮"}

@pytest.mark.parametrize("question,doc,extra",[
 (P,PT,"下周更换人群，不能沿用原响应规律。"),(P,PT,"另一份现行记录显示亮占1/5。"),
 (P,PT.replace("两单都出现","暗计划从未出现"),""),(P,PT.replace("其他全为暗","另有未列方案"),""),
 (P.replace("3/8","1/4"),PT,""),(P,PT.replace("4、8、6","4、8"),""),
 (P,PT,"此表仅为样本；不提供总体响应。"),(P,PT,"记录不一致。"),
 (P,PT,"暗方案的单位顺序相反。"),(P,PT.replace("亮占2/5","亮占2/0"),""),
 (P,PT.replace("其他全为暗","暗占3/5、新方案占1/5"),"")])
def test_named_policy_does_not_fill_in_missing_scope_or_cells(question,doc,extra):
    r=resolve(question,doc,extra)
    assert r["decision"]=="WITHHELD" and r["effective_answer"] is None and r["clarification_questions"]

G="干预前完整边表为禾站—柳站，柳站—枫站，芦站为孤立点。四站各抛一枚公平硬币独立决定开放。无邻居者永远记为没有伙伴开放。整份安排与一切潜在来客无关，实际记录对应实际完整安排的潜在值。资料库可提供各站有支持的事件的总体条件均值。"
Q="四个站都算，同权。本人未开放时，有伙伴开放相比伙伴全不开放，次日来客平均多几个？按原设计条件平均。"

@pytest.mark.parametrize("q,expected,pop",[(Q,"UNDEFINED",["禾站","柳站","枫站","芦站"]),
    (Q.replace("四个站都算，同权","只评价禾站和柳站，各半"),"POINT",["禾站","柳站"]),
    (Q.replace("四个站都算，同权","只评价禾站和柳站，各半").replace("有伙伴开放相比伙伴全不开放","伙伴全不开放相对于有伙伴开放"),"POINT",["禾站","柳站"])])
def test_local_support_matches_full_enumeration(q,expected,pop):
    r=resolve(q,G);a=r["effective_answer"];h=a["estimate_handoff"];proof=r["proof"]
    assert a["status"]==expected and a["target"]["population"]==pop
    allnodes=["禾站","柳站","枫站","芦站"];edges=[(0,1),(1,2)]
    for node in pop:
        i=allnodes.index(node);peers=[v if i==u else u for u,v in edges if i in (u,v)]
        for side in (0,1):
            count=sum(z[i]==0 and int(any(z[j] for j in peers))==side for z in product((0,1),repeat=4))
            assert Fraction(h["support"][node][f"0,{side}"])==Fraction(count,16)
    if expected=="UNDEFINED":
        assert h["queries"]==[] and list(map(tuple,proof["zero_events"]))==[("芦站","0,1")]
    else:
        first="0,0" if "伙伴全不开放相对" in q else "0,1"
        assert proof["ordered_events"][0]==first and len(h["queries"])==4
        for i,query in enumerate(h["queries"]):
            assert Fraction(evaluate_from_catalog(h, lambda u:int(u==query)))==Fraction([1,-1][i%2],2)

@pytest.mark.parametrize("q,g",[(Q,G.replace("完整边表","不完整边表")),(Q,G+"事后才登记，还有遗漏边。"),
    (Q.replace("四个","五个"),G),(Q,G.replace("公平硬币","不公平硬币")),
    (Q.replace("四个站都算，同权","只评价禾站和柳站，各半"),G+"现已撤回均值接口，不能查。")])
def test_local_graph_scope_and_data_conflicts(q,g):
    r=resolve(q,g)
    assert r["effective_answer"]==DRAFT and not r["network_alignment"]["matched"] and r["proof"] is None

Y="河岸普通周中，舟同学自己不参加时，至少一位朋友参加相对于朋友都不参加，会让舟的任务成绩怎样变化？只评价舟。"
O=("研究名单顺序为舟、柏、澜，朋友关系是舟—柏、舟—澜，无其他边，处理前固定的无向网络。"
   "参加本周活动记1，不参加记0；结果是本周任务成绩，连续数值。只评价舟，评价名单在活动前固定。固定背景W是原先登记的普通周，不含风险特征。"
   "活动前是否高风险记X，高为1，低为0。总体只有两个完整X配置：配置(0,0,1)占1/3；配置(1,1,1)占2/3。"
   "舟的调整变量是自身X和全部朋友中X=1的人数。给定任一完整X配置和固定背景W，参加的联合总体分布按三人分解，每人参加概率为1/3。"
   "这是观察分布。提供舟在每种背景组合、自己参加或不参加、朋友有人参加或都不参加时的全部八个条件总体均值算子，不提供均值数值。"
   "同伴状态定义为至少一个朋友参加时为1，否则为0。拟采用：观察结果对应实际完整参加名单；所需条件均值有限。"
   "对舟，在所有完整二元参加安排下，只要本人和同伴状态相同，个体潜在结果就相同。"
   "给定舟自身X、全部朋友中X=1的人数及固定背景W后，舟在每一种本人和同伴状态下的潜在结果均值，不随实际本人和同伴状态改变。")

@pytest.mark.parametrize("reverse",[False,True])
def test_observational_profile_support_weights_signs_and_no_automatic_approval(reverse):
    question=Y.replace("至少一位朋友参加相对于朋友都不参加","朋友都不参加相比至少一位朋友参加") if reverse else Y
    r=resolve(question,O);a=r["effective_answer"];h=a["estimate_handoff"]
    assert r["proof"]["native_replay"] and r["proof"]["observation_regime"]=="observational"
    assert len(h["queries"])==4 and len(a["assumptions"])==5 and a["value"] is None
    for query in h["queries"]:
        p=Fraction(1,3)
        mass=sum(p**sum(z)*(1-p)**(3-sum(z)) for z in product((0,1),repeat=3)
                 if z[0]==0 and int(any(z[1:]))==query["exposure"])
        assert Fraction(query["arm_probability"])==mass
        weight=Fraction(1,3) if (query["own_feature"],query["neighbor_feature_count"])==(0,1) else Fraction(2,3)
        sign=1 if query["exposure"]==int(not reverse) else -1
        assert Fraction(evaluate_from_catalog(h,lambda u:int(u==query)))==sign*weight

@pytest.mark.parametrize("q,doc",[(Y,O+"研究者撤回给定协变量后的交换性。"),
    (Y,O.replace("状态相同，个体潜在结果就相同","状态相同也会有不同的潜在结果")),
    (Y,O.replace("每人参加概率为1/3","每人参加概率为0")),(Y,O.replace("全部八个","全部两个")),
    (Y,O+"另一资料写每人参加概率为1/4。"),(Y,O+"仅提供一端的条件总体均值。"),
    (Y.replace("只评价舟","只评价柏"),O),(Y.replace("任务成绩","情绪评分"),O)])
def test_observational_no_release_on_denial_missing_support_or_different_target(q,doc):
    r=resolve(q,doc);ans=r["effective_answer"]
    if r.get("network_alignment"):
        assert ans==DRAFT and not r["network_alignment"]["matched"] and r["proof"] is None
    else:
        assert ans["status"]=="NEEDS_INPUT" and ans["estimate_handoff"]["queries"]==[]


SHIFT_Q="森棚这家店自身不广播时，伙伴有广播减无广播，本周到店率差多少？我们只管森棚，按它客户总体的班次构成来平均。"
SHIFT_DOC=("广播由店家自己定。干预前的客户关系固定，研究采用这个伙伴标签的潜在结果充分性和一致性。"
           "在晨班与晚班分别，联合暴露可交换且两端均可能；晨班占1/5。"
           "晨班两个端点的总体到店率是0.9与0.3，晚班是0.4与0.2，都是森棚的。")

def test_directly_reported_strata_use_target_masses_not_assignment_propensities():
    r=resolve(SHIFT_Q,SHIFT_DOC);a=r["effective_answer"];h=a["estimate_handoff"]
    assert a["status"]=="POINT" and a["value"]=="7/25"
    assert h["operator_spec"]["forms"]==[["1/5","-1/5","4/5","-4/5"]]
    assert [(q["stratum"],q["own"],q["exposure"]) for q in h["queries"]]==[
        ("晨班",0,1),("晨班",0,0),("晚班",0,1),("晚班",0,0)]

@pytest.mark.parametrize("doc",[
    SHIFT_DOC.replace("两端均可能","支持未经核实"),SHIFT_DOC.replace("到店率","出货率"),
    SHIFT_DOC.replace("都是森棚的","都是另棚的"),SHIFT_DOC.replace("0.9与0.3","1.9与0.3"),
    SHIFT_DOC+"原表顺序不明。", SHIFT_DOC+"研究者未采用联合暴露可交换性。"])
def test_reported_strata_require_support_scope_and_matching_outcome(doc):
    r=resolve(SHIFT_Q,doc)
    assert r["effective_answer"]==DRAFT and not r["network_alignment"]["matched"] and r["proof"] is None
