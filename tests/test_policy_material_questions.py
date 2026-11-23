from pathlib import Path
import sys

import pytest

package_root = Path(__file__).resolve().parents[1] / "identification"
if package_root.is_dir():
    sys.path.insert(0, str(package_root))
from cfm_id.network_grounded_contrast import source_lines
from cfm_id.network_material_questions import reported_degree, invitation_stop
from cfm_id.sequential_policy_value import evaluate, SCOPE_QUESTION


Q = "按两轮策略，竹叶店下一轮平均完成几件？只要策略水平。"
STUDY = ("第一轮统一采用橙标。第二轮若邻店报告拥堵就增派专车，否则不派。"
         "各轮安排在相应已观测历史内随机且有正支持，满足一致性，全部所需历史均已记录。"
         "目标总体资料显示橙标后发生拥堵的权重是20%；无拥堵且不派的下一轮均值是7，拥堵并增派专车的目标店下一轮均值是2。")


def data(text):
    return [r for r in source_lines(dict(business_question=Q,sources=[dict(source_id="protocol",text=text)])) if r["source_id"]!="question"]


def policy(text=STUDY,question=Q,replies=(),nodes=("竹叶店","绿竹店")):
    return evaluate(question,data(text),list(replies),nodes)


def test_policy_binds_reversed_rows_and_complement_to_original_action():
    a,p,qs=policy()
    assert p["archive_weighted_value"]=="6" and [t["contribution"] for t in p["terms"]]==["2/5","28/5"]
    assert [t["history"] for t in p["terms"]]==["拥堵","无拥堵"] and a["value"] is None and qs==[SCOPE_QUESTION]
    assert policy(nodes=())[1]["archive_weighted_value"]=="6"
    assert policy(STUDY.replace("20%","3/4"))[1]["archive_weighted_value"]=="13/4"
    a,p,qs=policy(STUDY+"分支均值和权重已按目标政策下的完整历史标准化。")
    assert a["value"]=="6" and not qs and a["estimate_handoff"]["mode"]=="EXACT_POPULATION_VALUE"
    sufficient="原设计第一轮无条件随机。第二轮完整决策历史仅为拥堵。两项分支均值与权重均来自橙标后的同一目标总体。"
    a,p,qs=policy(STUDY+sufficient)
    assert p["information_scope"]=="BRANCH_SUFFICIENT" and a["value"]=="6" and not qs


@pytest.mark.parametrize("text",[
    STUDY.replace("橙标后","紫标后"),
    STUDY.replace("拥堵并增派专车","拥堵并退车"),
    STUDY.replace("无拥堵且不派","无拥堵且不派船"),
    STUDY.replace("20%","120%"),
    STUDY.replace("20%","1/0"),
    STUDY+"无拥堵的概率是1/2。",
    STUDY.replace("目标店下一轮","绿竹店下一轮"),
    STUDY.replace("目标总体资料","一天样本表"),
    STUDY.replace("满足一致性","不满足一致性"),
    STUDY.replace("正支持","无正支持"),
    STUDY.replace("邻店报告拥堵","邻店报告损坏"),
    STUDY.replace("均已记录","未记录"),
])
def test_unmatched_or_conflicting_policy_summaries_do_not_replace_answer(text):
    assert policy(text) is None


def test_policy_level_and_source_of_confirmation():
    assert policy(question=Q+"再问相对旧政策的差。") is None
    assert policy(replies=[dict(source_id="user_reply_2",quote="是")])[0]["value"] is None
    answer,_,qs=policy(replies=[dict(source_id="user_reply_3",quote="否",reply_to=SCOPE_QUESTION)])
    assert answer["value"] is None and not qs
    assert policy(STUDY+"分支均值和权重没有按政策完整历史标准化。")[0]["value"] is None
    assert policy(replies=[dict(source_id="user_reply_4",quote="权重改为一半")]) is None


@pytest.mark.parametrize("reply,expected",[("北仓的度数为3",3),("2",2),("4",None),("0",None),
                          ("北仓的完整邻居名单为东仓、南仓",2),("完整邻居名单为南仓",None),
                          ("完整邻居名单为东仓、东仓",None),("完整邻居名单为东仓、西站",None)])
def test_degree_and_complete_list_respect_known_edges_and_roster(reply,expected):
    assert reported_degree([dict(quote=reply)],"北仓",["北仓","东仓","南仓","西仓"],{"东仓"})==expected


def test_random_invitation_does_not_close_a_supported_effect_or_a_different_question():
    q = "强制所有相邻伙伴均上线相比均不上线，可点识别吗？这次不增加假设。"
    txt = ("只有整份邀请的随机性，未假定实际处理随机。各组自行决定是否上线，不保证依从，资料未采用排除限制或实际处理可交换性。"
           "精确总体档案只给邀请组与未邀请组的平均质量分。")
    assert invitation_stop(q,data(txt),[],None)[0]["status"]=="NOT_POINT"
    assert invitation_stop(q.replace("不增加假设","请给我可选假设"),data(txt),[],None) is None
    assert invitation_stop(q,data(txt+"另有强制上线的干预均值。"),[],None) is None
    assert invitation_stop(q.replace("均上线相比均不上线","均获邀相比均未获邀"),data(txt),[],None) is None
