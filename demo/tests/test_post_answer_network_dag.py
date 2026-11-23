from copy import deepcopy

from cfm_id.direct_verification import verify, replay
from cfm_id.direct_dag import parse_edges
from cfm_id_llm.network_files import load_network


def source(name, text):
    return dict(source_id=name, label=name, kind="OTHER", text=text)


def draft(status="POINT", mode="ESTIMATE_POINT"):
    return dict(target=dict(quantity="level",scope="whole"),status=status,functional="unreviewed",
                value=None,assumptions=[],estimate_handoff=dict(mode=mode,scope="whole"),reason="")


def test_bound_graph_preserves_entire_variable_names_and_resolves_only_unique_edges():
    assert parse_edges("入口直接影响到岸。",["入口","到岸"],bound_names=True)==[["入口","到岸"]]
    assert parse_edges("入口直接影响到岸。",["入口","到岸","岸"],bound_names=True) is None
    assert parse_edges("入口直接影响到岸。没有入口到到岸的直接边。",["入口","到岸"],bound_names=True) is None


def graph_case(complete=True):
    graph="偏好直接影响开课。偏好直接影响到课。开课直接影响练习。练习直接影响到课。\n研究背景：全班本学期。"
    model="本研究采用静态有向无环模型，剩余噪声相互独立，其他机制保持不变。"
    model+=("边表列出了本模型的全部直接因果关系，所有共同原因均已列出。" if complete else "尚未说明边表是否穷尽全部直接关系和共同原因。")
    return dict(business_question="分别将“开课”设为0和1，保持其他机制不变时，“到课”的总体分布如何表示？",
                sources=[source("variables.md","\n".join(n+"表示二元状态，是为1、否为0；"+("未观测。" if n=="偏好" else "有记录。") for n in ["偏好","开课","练习","到课"])),
                         source("graph.md",graph),source("model.md",model),source("information.md","所有有记录变量的完整符号总体联合分布已给定，每一种联合二元取值的概率严格为正。")])


def test_frontdoor_conditions_and_hedge_do_not_certify_bounds():
    case=graph_case()
    response=dict(answers=[dict(draft(),question_part="设为0"),dict(draft(),question_part="和1")])
    r=verify(case,response)
    assert r["decision"]=="CONDITIONAL_RESULT" and r["proof"]["method"]=="FRONTDOOR"
    assert r["proof"]["frontdoor"]["练习"]=={"FD1":True,"FD2":True,"FD3":True}
    assert replay(case,response,r)
    case["sources"][1]["text"]+="开课直接影响到课。"
    response=draft("PARTIAL","ESTIMATE_BOUNDS")
    response["value"]=["claimed lower","claimed upper"]
    r=verify(case,response)
    assert r["proof"]["method"]=="ID_HEDGE" and not r["proof"]["frontdoor"]["练习"]["FD1"]
    assert r["effective_answer"]==response and r["conditional_answer"]["status"]=="NOT_POINT"
    assert any(c["code"]=="BOUND_SHARPNESS" and c["state"]=="UNCHECKED" for c in r["checks"])


def test_explicit_unknown_requires_evidence_and_reply_stays_with_same_target():
    data=graph_case(False);a=draft()
    r=verify(data,a)
    assert r["effective_answer"]["status"]=="NEEDS_INPUT" and r["clarification_questions"]
    data["sources"].append(source("user_reply_01","所有共同原因均已列出，边表列出了本模型的全部直接因果关系。"))
    r=verify(data,a)
    assert r["proof"]["method"]=="FRONTDOOR" and not r["scientific_approval"] and not r["estimation_handoff_allowed"]
    data["sources"][-1]["text"]="目前不能确认。"
    r=verify(data,a)
    assert not r["proof"] and not r["scientific_approval"]


def test_native_upload_bound_to_local_manifest_and_old_reports_replay(tmp_path):
    p=tmp_path/"nodes.csv";q=tmp_path/"friends.csv"
    p.write_text("node_id\n甲\n乙\n丙\n",encoding="utf8");q.write_text("source,target\n甲,乙\n甲,丙\n",encoding="utf8")
    declaration=dict(kind="UNDIRECTED",description="处理前固定的全部同事关系",completeness="COMPLETE")
    net=load_network(p,q,declaration)
    c=dict(business_question="仅评价【甲】，按 (T,S)=(0,1) 减 (T,S)=(0,0)，其余安排按原设计的条件分布平均。",
        sources=[source("note","结果为期末总量。至少一位邻居接受处理时S=1，否则为0。在完整名单中等概率无放回抽取1人。分配名单与潜在结果独立，研究采纳一致性，所用均值存在且有限。总体条件均值可作为符号算子按人调用。"),net.source()])
    a=draft();r=verify(c,a,network=net)
    assert r["proof"]["joint_probabilities"]["甲"]=={"0,0":"0","0,1":"2/3"}
    assert r["effective_answer"]["status"]=="UNDEFINED" and replay(c,a,r)
    tampered=deepcopy(r);tampered["network_manifest"]["edges"]=[]
    assert not replay(c,a,tampered)
    for version in ("direct-verification/1","direct-verification/2","direct-verification/3"):
        previous=verify(c,a,version=version)
        assert replay(c,a,previous)
    partial=load_network(p,q,dict(declaration,completeness="INCOMPLETE"))
    c["sources"][-1]=partial.source()
    r=verify(c,a,network=partial)
    assert r["effective_answer"]==a and not r["estimation_handoff_allowed"]
    assert r["network_alignment"]["fields"]["exposure"]["state"]!="MATCH"



def test_reported_exposure_substitute_can_replace_private_edges_without_automatic_approval():
    c = dict(business_question="仅评价【甲】，按 (T,S)=(0,1) 减 (T,S)=(0,0)，其余安排按原设计的条件分布平均。",
             sources=[source("roster","unit_id\n甲\n乙"), source("protocol","结果为到达量。至少一位邻居接受处理时S=1。没有提供完整网络。登记库提供等效暴露映射。两个事件的概率各为1/4，总体均值为7和2。")])
    a = dict(draft(), target=dict(quantity="difference",scope="subgroup"), estimate_handoff=dict(mode="ESTIMATE_POINT",scope="subgroup"), value=5)
    old = verify(c,a,version="direct-verification/4")
    assert old["effective_answer"]["status"]=="NEEDS_INPUT" and replay(c,a,old)
    current = verify(c,a)
    assert current["effective_answer"] == a and current["proof"] is None and replay(c,a,current)
    assert not current["scientific_approval"] and not current["estimation_handoff_allowed"]
    assert any(check["code"]=="REPORTED_EQUIVALENT_EXPOSURE" and check["state"]=="UNCHECKED" for check in current["checks"])
    c["sources"][1]["text"] = c["sources"][1]["text"].replace("提供等效暴露映射", "未提供等效暴露映射")
    missing = verify(c,a)
    assert missing["effective_answer"]==a and not missing["network_alignment"]["matched"]
    c["sources"][1]["text"] = "结果为到达量。至少一位邻居接受处理时S=1。附件用另一种格式登记了每份名单。"
    opaque = verify(c,a)
    assert opaque["proof"] is None and opaque["effective_answer"]==a



def test_local_outcome_information_is_checked_at_the_target_events():
    from cfm_id.direct_network import missing_event_means
    gap = "已知三个对象的无条件总体平均。没有局部事件的条件均值。"
    assert missing_event_means(gap)
    assert not missing_event_means(gap + "已提供完整符号总体联合分布。")
    assert not missing_event_means("逐人总体条件均值可符号调用，未给具体结果数值。")
    note = ("结果为季度总量。至少一位邻居接受处理时S=1。处理前固定完整无向边表，没有其他边。"
            "在完整名单中等概率无放回抽取1人。完整安排独立于潜在结果，采纳一致性，期望有限。")
    q="仅评价【青】，按 (T,S)=(0,1) 减 (T,S)=(0,0)，按原设计的条件分布平均其余安排。"
    c=dict(business_question=q,sources=[source("note",note+gap),source("roster","unit_id\n青\n白\n红"),source("edges","unit_a,unit_b\n青,白")])
    a=draft()
    result=verify(c,a)
    assert result["effective_answer"]["status"]=="NEEDS_INPUT"
    assert result["proof"]["joint_probabilities"]["青"]=={"0,0":"1/3","0,1":"1/3"}
    assert any("总体条件均值" in item for item in result["clarification_questions"])
    assert any(v["subject"]=="完整分配" for v in result["effective_answer"]["assumptions"])
    assert replay(c,a,result)
    c["sources"][1]=source("roster","unit_id\n青\n白")
    undefined=verify(c,a)
    assert undefined["effective_answer"]["status"]=="UNDEFINED" and not undefined["clarification_questions"]



def test_qualified_outcome_in_a_negative_edge_requires_unambiguous_source_binding():
    names=["处置","基线压力","随访压力"]
    q="主动改变处置后，随访中压力发生的概率如何变化？"
    graph="处置直接影响基线压力。没有处置到压力的直接边。"
    assert parse_edges(graph,names,bound_names=True,qualified_text=q)==[["处置","基线压力"]]
    assert parse_edges(graph,names,bound_names=True,qualified_text="总体分布如何变化？") is None
    assert parse_edges(graph,names+["压力"],bound_names=True,qualified_text=q) is None
    assert parse_edges(graph+"处置直接影响随访压力。",names,bound_names=True,qualified_text=q) is None
