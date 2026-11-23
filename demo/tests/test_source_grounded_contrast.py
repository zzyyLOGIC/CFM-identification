from fractions import Fraction
from itertools import combinations

import pytest
from cfm_id.direct_verification import verify,replay
from cfm_id.network_grounded_contrast import derive


def material(question,text):
    return dict(business_question=question,sources=[dict(source_id="ledger",text=text)])


@pytest.mark.parametrize("quota",range(1,6))
def test_named_focal_threshold_with_three_neighbors_and_varying_quota(quota):
    case=material("负责人只要白栈的数字：它这周开灯时，三个邻站过半开灯减至多一半开灯的平均等待时数。其余站按旧抽签条件平均，给两个联合概率。",
        f"白栈、栗亭、竹桥、芹口、浅渡这五处都在名单上。分配前白栈只与栗亭、竹桥和芹口相连。"
        f"在五站中均匀选定恰好{quota}站开灯，组合等机会。名单与一切潜在等待时数独立，实际名单对应其潜在记录。可调用每个正概率状态的总体平均时数。")
    a=derive(case,{})["answer"];h=a["estimate_handoff"]
    draws=list(combinations(range(5),quota))
    high=sum(0 in d and len(set(d)&{1,2,3})>1 for d in draws)
    low=sum(0 in d and len(set(d)&{1,2,3})<=1 for d in draws)
    assert h["support"]["白栈"]=={"1,1":str(Fraction(high,len(draws))),"1,0":str(Fraction(low,len(draws)))}
    assert a["status"]==("POINT" if min(high,low)>0 else "UNDEFINED")
    assert a["target"]["population"]==["白栈"]


def test_named_randomization_and_negative_control_for_actual_participation():
    q="我们要看本人没收到邀请时，有朋友获邀对比朋友全无的月底回访率变化。问的是檀桥本人。"
    t=("檀桥和三位固定好友各自独立抛公平硬币决定有没有训练邀请；邀请名单与所有潜在回访独立，记录按实际邀请名单一致。"
       "邀请比较按原抽签条件平均；檀桥本人未获邀时，在有好友获邀和无好友获邀两种情况下，总体回访率依次是0.57、0.43。"
       "实际参加受未记录的意愿影响。")
    c=material(q,t)
    # An extractor can supply a correct literal from the wrong source or falsely call attendance randomized.
    draft={"network_facts":{"contrast":{"value":{"population":"所有人"},"evidence":[{"source_id":"ledger","quote":q}]},
             "assignment":{"value":{"description":"实际参加随机"}}}}
    v=verify(c,draft,network_focus=True);p=v["proof"]
    assert v["effective_answer"]["value"]=="7/50" and p["target_variable"]==p["assigned_variable"]=="邀请"
    assert v["effective_answer"]["target"]["population"]==["檀桥"]
    assert p["model_field_spans"]["contrast"][0]["relocated"] and replay(c,draft,v)
    assert derive(material(q.replace("没收到邀请","没实际参加").replace("获邀","实际参加"),t),draft) is None
    assert derive(material(q,t.replace("总体回访率","总体旷课率")),draft) is None


def test_reported_pairs_keep_sign_scope_and_remaining_design():
    q="仓间互相借货。焦点货台本人不试新读卡机，在同组搭档试机减不试的两个世界里，下班平均错单差多少？"
    t=("共有四个组，各组两人，搭档开班前已固定。两组的试机整单随机生成，所有完整名单与潜在错单独立，实际记录一致。"
       "焦点不试时，搭档试和不试的联合事件都有支持，其总体错单均值是15和6。每一端都按原整单设计在该端的条件分布平均其余安排。")
    v=derive(material(q,t),{});assert v["answer"]["value"]=="9" and v["answer"]["target"]["population"]==["焦点货台"]
    assert derive(material(q,t.replace("每一端都按原整单设计在该端的条件分布平均其余安排","另一组都固定为使用读卡机")),{}) is None
    assert derive(material(q,t.replace("实际记录一致","不满足一致性")),{}) is None
