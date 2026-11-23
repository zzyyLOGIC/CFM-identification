"""Paired adversarial examples for focal rate contrasts, announced quotas and whole policies."""
from fractions import Fraction as F
from itertools import combinations

import pytest

from cfm_id.direct_verification import verify, replay
from cfm_id.network_estimate_handoff import evaluate_from_catalog

DRAFT={"answer":{"status":"NOT_COVERED","target":{"quantity":"difference"},"estimate_handoff":{"mode":"STOP"}}}


def run(q,text,reply=None):
    records=[dict(source_id="source",kind="OTHER",label="设计与资料",text=text)]
    if reply:records.append(dict(source_id="user_reply_review",kind="OTHER",label="追加",text=reply))
    c=dict(case_id="input",business_question=q,sources=records)
    r=verify(c,DRAFT,network_focus=True)
    assert replay(c,DRAFT,r)
    assert r["draft"]==DRAFT and not any(r[k] for k in ("scientific_approval","production_admission","estimation_handoff_allowed"))
    return r


Q="白杨门店不展示时，邻店展示相比都不展示，会让本月回访率降低多少？只评白杨。"
TABLE="合作伙伴在签约前固定。两端的总体观察回访率为71%（都不展示）和41%（邻店展示），均有支持。实际暴露记录一致，伙伴标签足以描述潜在回访。展示自己选。"
EX="业务协议采用白杨本店与邻店联合暴露对潜在回访的无条件可交换性。"
CF="未记的客流同时影响展示与回访，没有其他可交换条件或工具。"


@pytest.mark.parametrize("q,cols,expected",[
    (Q,TABLE,F(30,100)),
    (Q,TABLE.replace("71%（都不展示）和41%（邻店展示）","41%（邻店展示）和71%（都不展示）"),F(30,100)),
    (Q.replace("降低多少","增加多少"),TABLE,F(-30,100)),
    (Q.replace("邻店展示相比都不展示","都不展示相比邻店展示"),TABLE,F(-30,100)),
    (Q,TABLE.replace("71%","24%").replace("41%","55%"),F(-31,100))])
def test_observed_arms_bind_by_label_person_and_signed_operation(q,cols,expected):
    r=run(q,cols+EX)
    a=r["effective_answer"]; h=a["estimate_handoff"]
    assert a["status"]=="POINT" and a["target"]["population"]==["白杨"] and a["target"]["own"]==0
    assert a["target"]["time"]=="本月" and a["target"]["outcome"]=="回访率"
    assert r["proof"]["observation_regime"]=="observational" and F(a["value"])==expected
    assert len(h["queries"])==2 and [q["unit"] for q in h["queries"]]==["白杨"]*2
    for i,item in enumerate(h["queries"]):
        assert F(evaluate_from_catalog(h,lambda x:int(x["id"]==item["id"])))==[1,-1][i]


def test_same_positive_observed_rates_with_shared_cause_are_only_descriptive():
    r=run(Q,TABLE+CF); a,p=r["effective_answer"],r["proof"]
    assert a["status"]=="NOT_POINT" and a["value"] is None
    assert a["estimate_handoff"]["queries"]==[] and F(p["descriptive_difference"])==F(3,10)
    models=p["witness"]["models"]
    assert len({m["causal_difference"] for m in models})==2
    for m in models:
        assert F(m["causal_difference"])==(F(71,100)+F(m["unobserved_rate_arm0_given_u1"])
                                           -F(m["unobserved_rate_arm1_given_u0"])-F(41,100))/2


@pytest.mark.parametrize("q,doc",[
    (Q,TABLE),(Q,TABLE+EX.replace("无条件可交换性","给定年龄后的可交换性")),
    (Q,TABLE+EX+CF),(Q,TABLE+EX.replace("白杨","海桐")),
    (Q,TABLE+EX.replace("采用","没有采用")),(Q,TABLE.replace("均有支持","一端没有支持")+EX),
    (Q,TABLE.replace("实际暴露记录一致","尚未确认实际暴露记录一致")+EX),
    (Q,TABLE.replace("71%（都不展示）","71%（邻店展示）")+EX),
    (Q,TABLE.replace("两端的总体观察回访率","上月两端的总体观察回访率")+EX),
    (Q.replace("降低多少","相对降低多少"),TABLE+EX),
    (Q.replace("只评白杨","取前者减后者，只评白杨"),TABLE+EX)])
def test_incomplete_misaligned_or_conflicting_inputs_never_auto_identify(q,doc):
    r=run(q,doc)
    assert r["decision"]=="RETAINED" and r["effective_answer"]==DRAFT and not r["network_alignment"]["matched"]


QU="只评云松。她没领仪器而组里其余三人都领，减去她没领、组里也没人领，课后信任度差如何？请算各端连同她没领的联合概率。剩余安排按原抽法。"
RULE=("甲组云松、柏舟、春桥、山禾，乙组也是四个人；活动前固定同组另三人是每人的全部伙伴。"
      "甲组有三台、乙组零台的机会是一半，剩余机会将额度倒给乙组。额度广播后，组内均匀无放回，两组各自抽人。"
      "整个抽法与潜在信任度无关，实际记录对应实际安排，事件总体均值可查。")
DIRECT="通知本身会影响评分，即使实际设备相同。设备分配试验没有单独随机通知，单位只求实际设备的作用，尚未约定固定哪种通知。"


def test_joint_device_probabilities_against_enumeration_and_common_notice_followup():
    r=run(QU,RULE+DIRECT)
    a,p=r["effective_answer"],r["proof"]
    assert a["status"]=="NEEDS_INPUT" and len(r["clarification_questions"])==1
    assert "共同" in r["clarification_questions"][0] and "是否" not in r["clarification_questions"][0]
    profiles=[(3,F(1,2)),(0,F(1,2))]
    expected={s:sum(w*F(sum(0 not in arm and len(arm)==s for arm in combinations(range(4),m)),
                         len(list(combinations(range(4),m)))) for m,w in profiles) for s in (3,0)}
    assert {s:F(p["joint_probabilities"]["云松"][f"0,{s}"]) for s in (3,0)}==expected=={3:F(1,8),0:F(1,2)}
    assert not a["estimate_handoff"]["queries"]
    for k,unsupported in [("零","0,3"),("三","0,0")]:
        fixed=run(QU,RULE+DIRECT,"两端都固定为本组"+k+"名额的通知。")
        assert fixed["effective_answer"]["status"]=="NOT_POINT" and fixed["proof"]["zero_crossed_arms"]==[unsupported]
        assert not fixed["clarification_questions"]


def test_explicit_notice_exclusion_gives_two_usable_original_event_queries():
    a=run(QU,RULE+"广播预告本身不改变评分，别组也影响不到本组。")["effective_answer"]
    assert a["status"]=="POINT" and [(q["own"],q["exposure"]) for q in a["estimate_handoff"]["queries"]]==[(0,3),(0,0)]
    assert a["value"] is None


@pytest.mark.parametrize("doc,reply",[
    (RULE+DIRECT,"两端都固定为本组零名额的通知。另外有新的交叉实验。"),
    (RULE+DIRECT,"通知规则还没有决定。"),
    (RULE.replace("乙组零台","乙组一台")+DIRECT,None),
    (RULE.replace("同组另三人","同组另两人")+DIRECT,None),
    (RULE+DIRECT+"广播不一定等于实际配额。",None)])
def test_missing_or_contradictory_equipment_evidence_remains_unresolved(doc,reply):
    r=run(QU,doc,reply)
    assert not (r["effective_answer"] or {}).get("value")
    assert not ((r["effective_answer"] or {}).get("estimate_handoff") or {}).get("queries")
    if r.get("network_alignment"):
        assert r["effective_answer"]==DRAFT and not r["network_alignment"]["matched"]
    else:
        assert r["clarification_questions"]


def test_additional_experiment_does_not_erase_the_fixed_notice_or_authorize_estimation():
    r=run(QU,RULE+DIRECT,"两端都固定为本组三名额的通知。另有新的交叉实验。")
    assert r["proof"]["notice_resolution"]=="SUPPLEMENTARY_EVIDENCE"
    assert r["effective_answer"]["target"]["notice_intervention"]["quota"]==3
    assert len(r["clarification_questions"])==1 and "补充资料覆盖" in r["clarification_questions"][0]


POL="试办方想在六个合伙店同时通电那一晚，给各店同样的权重，平均毛收入是多少？"
LAW=("三对预先登记的合伙店在做实验。每天从六店中均匀抽三店通电，其他都不通电。"
     "抽签和所有潜在收入独立，实际账目对应那张名单；各张可抽名单的各店总体均值都已掌握。")
REFUSED="业主拒绝对不同完整名单下的收入作任何相等、平滑、上下界假定，即使本店及伙伴状态相同也不作迁移。"


@pytest.mark.parametrize("symbol",[1,0])
def test_unsupported_whole_policy_remains_a_defined_level(symbol):
    q=POL if symbol else POL.replace("同时通电","同时不通电")
    r=run(q,LAW+REFUSED);a,p=r["effective_answer"],r["proof"]
    assert a["status"]=="NOT_POINT" and a["target"]["quantity"]=="level"
    assert p["target_assignment"]==[symbol]*6 and p["support"]["supported_full_assignments"]==len(list(combinations(range(6),3)))
    assert p["witness"]["target_levels"]==["0","1"] and a["estimate_handoff"]["queries"]==[]


def test_zero_full_policy_support_with_open_scientific_question_is_not_a_nonidentification_proof():
    r=run(POL,LAW)
    assert r["decision"]=="WITHHELD" and r["clarification_questions"] and r["effective_answer"] is None


def test_global_pair_mean_license_can_identify_an_unsupported_full_policy():
    q=POL.replace("六","四").replace("通电","开灯")
    law=LAW.replace("三对","两对").replace("六店","四店").replace("三店","两店").replace("通电","开灯")
    bridge=("每对合伙店在公告前就已固定，每店毛收入均值只随本店及搭档的灯变；此说法适用于所有名单。"
            "两灯都亮时四店各自的总体毛收入均值依次是2、6、8、12。")
    r=run(q,law+bridge);a,p=r["effective_answer"],r["proof"]
    assert a["status"]=="POINT" and a["value"]=="7" and p["support"]["target_full_assignment_probability"]=="0"
    assert p["local_arm_probability"]=="1/6" and len(a["estimate_handoff"]["queries"])==4
    mixed=run(q,law+bridge+REFUSED)
    assert mixed["decision"]=="RETAINED" and mixed["effective_answer"]==DRAFT and not mixed["network_alignment"]["matched"]
    mismatched=run(q,law+bridge.replace("总体毛收入","总体净收入"))
    assert mismatched["decision"]=="RETAINED" and mismatched["effective_answer"]==DRAFT and not mismatched["network_alignment"]["matched"]
