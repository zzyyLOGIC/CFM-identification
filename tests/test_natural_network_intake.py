"""Source permutations independent of the saved replay bank."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from serve import integrated_engine
from cfm_id.direct_verification import answer_items, replay, verify
from cfm_id_llm.network_files import load_network


def harbor(tmp_path, *, reverse=False):
    nodes = ["清港","北港","竹港","溪港"]
    roster, edges = tmp_path/"nodes.csv",tmp_path/"edges.csv"
    roster.write_text("node_id\n"+"\n".join(nodes),"utf8")
    edges.write_text("source,target\n清港,北港\n清港,竹港\n","utf8")
    net = load_network(roster,edges,dict(kind="UNDIRECTED",description="抽签前登记的完整关系。",completeness="COMPLETE"))
    docs = dict(design="名册顺序为清港、北港、竹港、溪港。处理变量为启用泊位牌。各点独立抽签，按名册顺序启用概率分别为1/4、1/2、3/4、1/3。",
                exposure="至少一个邻港启用记为1，零个记为0。",
                mixture="在各端内，其他单位按本次试验给定该事件后的分布取平均。",
                outcome="结果指标为首周预约件数。观察期间为试点后首周。",
                info="每个单位在任何正概率的本人状态和邻居暴露下的总体条件均值可查询。",
                premises="完整分配独立于所有潜在结果，观测结果对应实际发生的完整分配，各端条件均值有限。")
    arms = ["有邻港启用","无邻港启用"]
    ends = [[0,1],[0,0]]
    if reverse:
        arms.reverse()
        ends.reverse()
    q = "只对清港，本港未启用泊位牌时，"+"减去".join(arms)+"，首周预约件数相差多少？请列每端的联合概率。"
    case = dict(case_id="port-trial",business_question=q,sources=[
        dict(source_id=k,kind="OTHER",text=v,label=k) for k,v in docs.items()]+[net.source()])
    draft = dict(answers=[dict(status="NEEDS_INPUT",target=dict(population="清港",scope="subgroup"),
                               reason="请提供关系表。",estimate_handoff=dict(mode="STOP"))],
                 network_facts=dict(contrast=dict(value=dict(population=["清港"],left=ends[0],right=ends[1]),
                                                   evidence=[dict(source_id="question",quote=q)])))
    return case,draft,net


@pytest.mark.parametrize("reverse",[False,True])
def test_source_order_and_named_rates_without_a_lottery_keyword(tmp_path,reverse):
    case,draft,net=harbor(tmp_path,reverse=reverse)
    assert "原" not in case["business_question"] and "原" not in case["sources"][2]["text"]
    old=verify(case,draft,version="direct-verification/18",network=net)
    assert not old.get("condition_review") and not old.get("estimation_handoff_allowed")
    report=verify(case,draft,network=net)
    assert report["network_alignment"]["matched"] and report["decision"]=="PREMISES_REQUIRED"
    proof=report["proof"]
    assert proof["joint_probabilities"]=={"清港":{"0,1":"21/32","0,0":"3/32"}}
    assert proof["ordered_events"]==(["0,0","0,1"] if reverse else ["0,1","0,0"])
    assert report["conditional_answer"]["estimate_handoff"]["remaining_assignment"] in case["sources"][2]["text"]
    assert not report["estimation_handoff_allowed"] and replay(case,draft,report)


@pytest.mark.parametrize("issue",["probability_request_only","different_policy","roster_order","second_rate",
                                 "reversed_exposure","undetermined_law","lost_member","second_endpoint",
                                 "other_treatment","opposite_weight","incomplete_graph","other_population","model_graph_count",
                                 "future_means","refused_science"])
def test_incomplete_or_incompatible_coordinates_do_not_release(tmp_path,issue):
    case,draft,net=harbor(tmp_path)
    def modify(source,old,new):
        doc=next(s for s in case["sources"] if s["source_id"]==source)
        assert old in doc["text"]
        doc["text"]=doc["text"].replace(old,new)
    if issue=="probability_request_only":
        case["sources"]=[s for s in case["sources"] if s["source_id"]!="mixture"]
        case["business_question"]+="请报告原抽签下的联合概率。"
    elif issue=="different_policy":
        case["business_question"]+="比较时固定其余单位的具体处理。"
    elif issue=="roster_order":
        modify("design","北港、竹港","竹港、北港")
    elif issue=="second_rate":
        modify("design","各点独立抽签","北港启用概率为1/5。各点独立抽签")
    elif issue=="reversed_exposure":
        modify("exposure","邻港启用记为1","邻港未启用记为1")
    elif issue=="undetermined_law":
        modify("design","各点独立抽签","无法确认各点是否独立抽签")
    elif issue=="lost_member":
        case["business_question"]=case["business_question"].replace("只对清港","只对清港，北港")
    elif issue=="second_endpoint":
        case["business_question"]+="另外还要比较本站启用减去本站未启用。"
    elif issue=="other_treatment":
        case["business_question"]=case["business_question"].replace("泊位牌","扩音器")
    elif issue=="incomplete_graph":
        case["sources"].append(dict(source_id="memo",kind="OTHER",label="记录",text="处理前的关系表缺行。"))
    elif issue=="opposite_weight":
        draft["network_facts"]["contrast"]["value"]["weights"]={"清港":"1/2","北港":"1/2"}
    elif issue=="model_graph_count":
        draft["network_facts"]["network"]=dict(value=dict(edges={"count":40}),evidence=[])
    elif issue=="future_means":
        modify("info","每个单位","若管理方将来开放，每个单位")
    elif issue=="refused_science":
        modify("premises","完整分配独立","研究者不能确认完整分配独立")
    else:
        draft["answers"][0]["target"]["scope"]="whole"
    r=verify(case,draft,network=net)
    assert r["draft"]==draft and answer_items(r["effective_answer"])==answer_items(draft)
    assert not r.get("condition_review") and not r["estimation_handoff_allowed"]
    assert replay(case,draft,r)
    if issue=="other_population":
        assert r["network_alignment"]["fields"]["population"]["state"]=="DISAGREEMENT"
        assert r["network_alignment"]["source_target_complete"]
        assert r["clarification_questions"]==[r["scope_worksheet"]["question"]]
        assert [v["id"] for v in r["scope_worksheet"]["options"]]==["named","whole"]
