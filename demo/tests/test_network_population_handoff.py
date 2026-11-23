from copy import deepcopy
from fractions import Fraction as F

import pytest

from cfm_id.direct_verification import verify, replay
from cfm_id.network_query_binding import source_result, unavailable_required_query
from cfm_id.network_policy_handoff import solve
from cfm_id.network_estimate_handoff import evaluate_from_catalog, execute_handoff


def case(q, text):
    return {"business_question":q,"sources":[{"source_id":"att_01","label":"纪要","text":text}]}


def ego(shared=False):
    if shared:
        return case("只评松桥，松桥不发广告时，隔壁至少一家发与隔壁都不发相比，本月订单会多多少？沿用原分配条件，两个联合事件的机会是多少？",
            "松桥的邻店恰是西港、青湾，关系在活动前固定。三家一起掷同一枚公平硬币，正面三家都发，反面全不发。完整列单独立于潜在订单，实际订单对应实际列单。")
    return case("我只管晴这次交班。她本人没抽中时，有伙伴抽中比谁都没抽中，平均返修几件？各端其他人仍照原签的条件规律走，两种情况连同晴没抽中的机会请分别算出来。",
        "工坊里晴要和林、松交换图纸，这两个就是她开工前全部的互助伙伴。三人各掷自己的签，谁也不影响谁抽中。晴抽中机器的机会是二分之一，林是三分之一，松是四分之一。抽签不看任何人的潜在返修数，返修数按实际完整名单记。只要伙伴有人抽中就标作有伙伴。每一端的个人总体平均返修数都可以向台账查询，只需写调用方式。")


def policy(means, margins=("1/2","1/2"), law="unknown"):
    return dict(contrast=dict(kind="binary_policy_level",population="两店等权",scope="whole",outcome="销量",time="下周",
                              intervention="新分配",reference=""),
                network=dict(basis="whole"),exposure=dict(kind="whole_assignment"),
                assignment=dict(kind="binary_policy",margins=margins,coupling=law),
                information=dict(query="joint_state_mean",same_population=True,all_positive=True,values=dict(zip(("00","10","01","11"),means))),
                science=dict(random_full=True,consistent=True,evidence=[dict(quote="整单随机，实际记录一致。")]))


def test_event_only_catalog_can_execute_both_terms():
    c=ego()
    r=verify(c,{"status":"POINT","estimate_handoff":{"mode":"ESTIMATE_POINT","operator":"必须逐张查完整名单均值"}},network_focus=True)
    assert replay(c,r["draft"],r)
    a=r["effective_answer"];assert a["target"]["population"]==["晴"] and a["value"] is None
    h=a["estimate_handoff"];assert h["support"]["晴"]=={"0,0":"1/4","0,1":"1/4"}
    seen=[]
    def catalog(q):
        assert q["kind"]=="person_event_mean" and q["unit"]=="晴" and q["own"]==0
        assert q["neighbors"]==["林","松"] and q["treatment"]=="抽中机器"
        seen.append(q["exposure"]);return {1:19,0:12}[q["exposure"]]
    assert evaluate_from_catalog(h,catalog)=="7" and seen==[1,0]
    assert not r["scientific_approval"] and not r["estimation_handoff_allowed"]


def test_original_zero_end_without_any_outcome_catalog():
    c=ego(True);r=source_result(c);a=r["answer"]
    assert a["status"]=="UNDEFINED" and a["estimate_handoff"]["mode"]=="STOP"
    assert a["estimate_handoff"]["support"]["松桥"]=={"0,1":"0","0,0":"1/2"}
    assert not r["questions"]
    with pytest.raises(ValueError,match="NO_ESTIMABLE_OPERATOR"):
        evaluate_from_catalog(a["estimate_handoff"],lambda q:pytest.fail("zero-support query issued"))
    c["business_question"]=c["business_question"].replace("沿用原分配条件","强制安排两家邻店，改用新政策")
    assert source_result(c) is None


def test_unavailable_fine_queries_must_really_be_required():
    c=case("比较同伴暴露两个端的客流差。","台账只给局部端均值，不能逐张查完整名单的均值。")
    h=dict(mode="ESTIMATE_POINT",query_requirement="all_required",queries=[{"kind":"person_full_assignment_mean"}])
    assert unavailable_required_query(c,{"estimate_handoff":h})
    h["query_requirement"]="alternative"
    assert unavailable_required_query(c,{"estimate_handoff":h}) is None
    h["operator"]="不必逐张查完整名单，也可直接查询两个端。"
    assert unavailable_required_query(c,{"estimate_handoff":h}) is None


def test_unavailable_query_also_blocks_a_preexisting_support_proof(monkeypatch):
    from cfm_id import direct_verification as dv
    c=case("求原人群两端的差。","不能逐张查完整名单均值，但可以查两个局部端的总体均值。")
    h=dict(mode="ESTIMATE_POINT",query_requirement="all_required",queries=[{"kind":"person_full_assignment_mean"}])
    draft={"estimate_handoff":h}
    def old_report(*args,**kwargs):
        if kwargs["version"]!="direct-verification/9":
            return current(*args,**kwargs)
        return {"checks":[],"proof":{"method":"support"},"effective_answer":draft}
    current=dv.verify
    monkeypatch.setattr(dv,"verify",old_report)
    result=current(c,draft,network_focus=True)
    assert result["decision"]=="WITHHELD" and result["effective_answer"] is None and result["proof"] is None


def test_asymmetric_margins_have_attainable_bounds_even_for_negative_interaction():
    f=policy(["9","12","10","2"],("1/3","3/4"))
    r=solve(f,point_required=True);a=r["answer"]
    assert r["proof"]["feasible_joint_11"]==["1/12","1/3"]
    for row in r["proof"]["endpoint_laws"]:
        p00,p10,p01,p11=map(F,row)
        assert p10+p11==F(1,3) and p01+p11==F(3,4) and min(p00,p10,p01,p11)>=0
    # Intercept 9 + 3/3 + 1*3/4 = 43/4, and interaction 2-12-10+9=-11.
    assert a["value"]==["85/12","59/6"]
    assert a["status"]=="PARTIAL" and len(r["questions"])==1
    assert not solve(f)["questions"]


def test_no_question_for_additivity_or_degenerate_margins():
    for f in (policy([10,7,5,2]),policy([2,7,10,1],("0","1"))):
        r=solve(f,point_required=True);h=r["answer"]["estimate_handoff"]
        assert r["answer"]["status"]=="POINT" and not r["questions"]
        assert execute_handoff(h,f["information"]["values"])==r["answer"]["value"]
    base=policy([10,7,5,2]);a=solve(base)["answer"]
    with pytest.raises(ValueError,match="POINT_EQUALITY_NOT_PRESERVED"):
        execute_handoff(a["estimate_handoff"],{"00":9,"10":7,"01":5,"11":2})


def test_a_known_policy_can_execute_when_unused_old_cells_are_unavailable():
    facts=policy([20,7,9,4],law="same_draw")
    info=facts["information"];info.pop("all_positive")
    info.update(supported_cells=["00","11"],values={"00":"20","11":"4"})
    answer=solve(facts)["answer"];handoff=answer["estimate_handoff"]
    assert [q["assignment"] for q in handoff["queries"]]==["00","11"]
    assert evaluate_from_catalog(handoff,lambda q:info["values"][q["assignment"]])=="12"
    facts["assignment"]["coupling"]="unknown"
    assert solve(facts) is None


def test_no_default_exchangeability_or_unavailable_state_mean():
    f=policy([4,6,9,20])
    for field in ("random_full","consistent"):
        g=deepcopy(f);g["science"][field]=None
        assert solve(g) is None
    f["information"]["all_positive"]=False
    assert solve(f) is None


def test_point_request_is_only_for_a_material_joint_rule():
    q="两个库下月重新排班，两个库等权的平均耗电是多少？"
    text="旧的四种完整开关情形都有正概率，随机且和各情形潜在耗电独立，实际耗电对应实际开关。两库全开、全关、只开东、只开西时，全体等权总体耗电分别为4、20、7、9。下月两库各有一半机会打开。只报边际，联合抽法未知。"
    c=case(q,text);assert source_result(c)["answer"]["value"]==["8","12"]
    c["sources"].append(dict(source_id="user_reply_1",text="我需要单一点值。"))
    assert len(source_result(c)["questions"])==1
    c["sources"].append(dict(source_id="user_reply_2",text="两家各自独立抽签。"))
    assert source_result(c)["answer"]["value"]=="10" and not source_result(c)["questions"]
    c["sources"][-1]["text"]="若两家各自独立抽签呢？"
    assert source_result(c) is None
    c=case(q,text.replace("潜在耗电独立","潜在耗电不独立"))
    assert source_result(c) is None
    c=case(q,text.replace("各有一半机会打开","各有一半机会打开仅为旧说，东库实际机会是三分之一"))
    assert source_result(c) is None


def test_point_refinement_reuses_a_saved_model_draft(tmp_path,monkeypatch):
    from demo.backend.engine import Engine, Run
    engine=Engine(tmp_path,max_api_calls=0)
    monkeypatch.setattr(engine,"call",lambda *args:pytest.fail("model called again"))
    run=Run(owner="review",reading_mode="network_direct_verify")
    run.case=case("两个库下月重新排班，两个库等权的平均耗电是多少？",
        "旧的四种完整开关情形都有正概率，随机且和各情形潜在耗电独立，实际耗电对应实际开关。两库全开、全关、只开东、只开西时，全体等权总体耗电分别为4、20、7、9。下月两库各有一半机会打开。只报边际，联合抽法未知。")
    draft={"status":"POINT","value":"13"}
    run.result=verify(run.case,draft,network_focus=True)
    engine._clarify(run,"我需要单一点值。")
    assert run.stage=="REVIEW_REQUIRED" and run.result["draft"]==draft
    engine._clarify(run,"两家各自独立抽签。")
    assert run.stage=="RESULT" and run.result["effective_answer"]["value"]=="10"
    assert run.result["draft"]==draft and engine.calls==0
