from copy import deepcopy

from cfm_id import project
from cfm_id.direct_verification import replay, verify
from cfm_id.network_reading import fact_evidence, proposed_model
from cfm_id_llm.direct_answer import network_request, request

Q="仅评价【赤】，按 (T,S)=(0,1) 减 (T,S)=(0,0) 求本月运量差，其余名单按原设计条件分布平均。"
TEXT=("处理前就确定了全体名单（赤、白、蓝），全部不分方向的合作联系人只有赤与白、赤与蓝。"
      "至少一位邻居接受处理时S=1，否则为0。各人独立Bernoulli抽签。按刚才名单顺序，每人概率分别为1/2、1/4、1/2。"
      "完整安排同全部潜在运量独立，记录反映实际安排的潜在结果，期望有限。每个有支持的局部状态都知道个人总体条件均值。")
CASE={"business_question":Q,"sources":[{"source_id":"att_01","label":"访谈","text":TEXT}]}
RAW={"status":"POINT","target":{},"value":None,"functional":"待核对","assumptions":[],"estimate_handoff":{"mode":"ESTIMATE_POINT"}}

def evidence(value,quote,sid="att_01"):
    return dict(value=value,evidence=[dict(source_id=sid,quote=quote)])

def proposal():
    return {**RAW,"network_facts":dict(network=evidence(dict(pre_treatment=True,complete=True,undirected=True,nodes=["赤","白","蓝"],edges=[["赤","白"],["赤","蓝"]]),TEXT.split("。")[0]),
        exposure=evidence(dict(kind="any"),TEXT.split("。")[1]),assignment=evidence(dict(kind="independent",probabilities={"赤":"1/2","白":"1/4","蓝":"1/2"}),TEXT.split("。")[3]),
        contrast=evidence(dict(population=["赤"],left=[0,1],right=[0,0]),Q,"question"))}

def test_one_call_and_joint_probabilities():
    calls=[]
    def send(req,stage):
        calls.append((req,stage))
        return proposal()
    report=project.direct_then_verify(CASE,send)
    assert len(calls)==1 and calls[0][1]=="direct_draft" and "network_facts" in calls[0][0]["system_prompt"]
    assert report["proof"]["joint_probabilities"]["赤"]=={"0,1":"5/16","0,0":"3/16"}
    assert all(r["state"]=="AGREES" for r in report["network_reading"]["fields"].values())
    assert replay(CASE,proposal(),report) and not report["scientific_approval"]
    assert "network_facts" not in report["effective_answer"]

def test_invalid_citation_does_not_approve_or_trigger_question():
    d=proposal()
    d["network_facts"]["network"]["evidence"][0]["source_id"]="not_in_upload"
    v=verify(CASE,d)
    field=v["network_reading"]["fields"]["network"]
    assert field["invalid_citations"]==1 and not field["evidence"] and field["state"]=="SOURCE_ONLY"
    assert not v["clarification_questions"] and "conditional_joint_support" not in v["network_reading"]
    d["network_facts"]["network"]["evidence"][0]["source_id"]="att_01"
    assert not replay(CASE,d,v)

def test_transposed_probabilities_and_reversed_arms_corrected_from_original():
    d=proposal()
    d["network_facts"]["assignment"]["value"]["probabilities"].update(赤="1/4",白="1/2")
    d["network_facts"]["contrast"]["value"].update(left=[0,0],right=[0,1])
    v=verify(CASE,d)
    assert all(v["network_reading"]["fields"][k]["state"]=="CORRECTED_FROM_SOURCE" for k in ("assignment","contrast"))
    assert v["proof"]["joint_probabilities"]["赤"]["0,1"]=="5/16"
    assert v["clarification_questions"]==[]

def test_missing_law_and_supplement():
    c=deepcopy(CASE)
    c["sources"][0]["text"]=TEXT.replace("各人独立Bernoulli抽签。按刚才名单顺序，每人概率分别为1/2、1/4、1/2。","分配设计待补。")
    r=verify(c,RAW)
    assert len(r["clarification_questions"])==1 and r["effective_answer"]==RAW
    assert not r["network_alignment"]["matched"] and not r["estimation_handoff_allowed"]
    c["sources"].append(dict(source_id="user_reply_1",label="补充",text="在完整名单中等概率无放回抽取1人。"))
    s=verify(c,RAW)
    assert s["effective_answer"]["status"]=="UNDEFINED" and not s["clarification_questions"]
    assert s["proof"]["joint_probabilities"]["赤"]=={"0,1":"2/3","0,0":"0"}

def test_citation_alone_does_not_assert_semantics():
    c=deepcopy(CASE)
    c["sources"][0]["text"]="邻居根据抽签决定。"
    d=proposal()
    for k in ("network","assignment","exposure"):
        d["network_facts"][k]["evidence"]=[dict(source_id="att_01",quote=c["sources"][0]["text"])]
    r=verify(c,d)
    assert r["proof"] is None and r["network_reading"]["conditional_joint_support"]
    d["estimate_handoff"]={"mode":"ESTIMATE_POINT","support":{"赤":{"0,1":"1"}}}
    v=verify(c,d)
    assert v["decision"]!="WITHHELD" and not v["clarification_questions"]
    c=deepcopy(CASE)
    c["sources"][0]["text"]=TEXT.split("完整安排同")[0]
    d=proposal(); d["estimate_handoff"]={"mode":"ESTIMATE_POINT","support":{"赤":{"0,1":"1"}}}
    v=verify(c,d)
    assert v["decision"]=="RETAINED" and v["effective_answer"]==d and not v["network_alignment"]["matched"]
    assert not v["scientific_approval"]

def test_legacy_no_fields_and_nonnetwork():
    c={"business_question":"单个价格政策的销售额水平？","sources":[]}
    base, current = request(c), network_request(c)
    assert current["user_prompt"] == base["user_prompt"]
    assert current["system_prompt"].startswith(base["system_prompt"])
    assert "verification_route" in current["system_prompt"]
    assert "network_facts" not in current["system_prompt"]
    r=verify(CASE,RAW)
    assert r["network_reading"]["origin"]=="source_only" and replay(CASE,RAW,r)
    v6=verify(CASE,RAW,version="direct-verification/6")
    assert "network_reading" not in v6 and replay(CASE,RAW,v6)


def test_explicit_network_selects_fact_contract_without_keyword_or_approval(monkeypatch):
    """The file input controls routing, not incidental business nouns."""
    import cfm_id.direct_verification as verification
    c={"business_question":"甲站本周开了助手后的平均用时？","sources":[]}
    calls=[]; received=[]; manifest=object()
    raw={"status":"NEEDS_INPUT"}
    def verify_case(case,draft,**options):
        received.append((case,draft,options))
        return {"scientific_approval":False,"estimation_handoff_allowed":False}
    monkeypatch.setattr(verification,"verify",verify_case)
    def send(req,stage):
        calls.append((req,stage));return raw
    r=project.direct_then_verify(c,send,network=manifest)
    assert len(calls)==1 and "network_facts" in calls[0][0]["system_prompt"]
    assert received==[(c,raw,{"network":manifest,"network_focus":False})]
    assert not r["scientific_approval"] and not r["estimation_handoff_allowed"]
    calls.clear()
    project.direct_then_verify(c,send)
    assert len(calls) == 1 and calls[0][1] == "direct_draft"
    assert calls[0][0] == network_request(c)
    assert calls[0][0]["user_prompt"] == request(c)["user_prompt"]
    assert "network_facts" not in calls[0][0]["system_prompt"]
    assert received[-1] == (c, raw, {"network": None, "network_focus": False})


def test_wrapped_fact_sheet_and_notation_do_not_change_signed_source_draft():
    d=proposal()
    wrapped={"answer":d}
    r=verify(CASE,wrapped)
    assert r["network_reading"]["fact_sheet_location"]["paths"]==["answer.network_facts"]
    assert r["draft"]==wrapped and replay(CASE,wrapped,r)
    assert "network_facts" not in r["effective_answer"]
    d["network_facts"]["contrast"]["value"].update(left="(0,1)",right="(0,0)",population="赤")
    r=verify(CASE,{"answers":[d]})
    assert r["network_reading"]["conditional_joint_support"]["赤"]["0,1"]=="5/16"
    v7=verify(CASE,wrapped,version="direct-verification/7")
    assert v7["network_reading"]["origin"]=="source_only_replay" and replay(CASE,wrapped,v7)

def test_material_unresolved_law_conflict_but_not_different_dated_polices():
    c=deepcopy(CASE)
    c["sources"][0]["text"]+="甲记为各自独立抽签；乙记为共用同一枚硬币。两份记录无法辨别本轮采用哪张。"
    r=verify(c,proposal())
    assert r["clarification_questions"] and r["effective_answer"]==proposal() and r["proof"] is None
    assert set(r["network_reading"]["unresolved_design_sources"])=={"逐人独立抽签","共用一次抽签"}
    c["sources"][0]["text"]+="已确认乙的计划不适用于本轮。"
    assert not verify(c,proposal()).get("clarification_questions")

def test_multiple_local_fact_sheets_are_not_merged_into_one_contrast():
    a=proposal();b=deepcopy(a)
    b["network_facts"]["contrast"]["value"]["left"]=[1,1]
    v=verify(CASE,{"answers":[a,b]})
    assert v["network_reading"]["fact_sheet_location"]["state"]=="PER_TARGET_OR_CONFLICT"
    assert v["network_reading"]["origin"]=="source_only"


def test_design_supplement_does_not_supply_population_outcomes():
    c=deepcopy(CASE)
    s=TEXT.replace("每个有支持的局部状态都知道个人总体条件均值。","现有资料只有未分层的全期个人均值。")
    c["sources"][0]["text"]=s.replace("各人独立Bernoulli抽签。按刚才名单顺序，每人概率分别为1/2、1/4、1/2。","分配设计待补。")
    # A and its only neighbor give both requested events under this fixed quota.
    c["sources"][0]["text"]=c["sources"][0]["text"].replace("赤与白、赤与蓝","赤与白")
    c["sources"].append(dict(source_id="user_reply_1",label="补充",text="在完整名单中等概率无放回抽取1人。"))
    r=verify(c,RAW)
    assert r["effective_answer"]==RAW and r["proof"] is None and not r["estimation_handoff_allowed"]
    proposal_report=verify(c,RAW,network_focus=True,version="direct-verification/16")
    assert proposal_report["network_reading"]["support_proof"]["joint_probabilities"]["赤"]=={"0,1":"1/3","0,0":"1/3"}
    assert "总体条件均值" in proposal_report["clarification_questions"][0]


def test_unsupported_model_question_does_not_open_a_user_clarification():
    c={"business_question":"伙伴轮班的平均返工差，用符号表示。","sources":[dict(source_id="att_01",label="纪要",text="只有总体条件均值算子，期望存在；只需符号公式，没有提供具体数值。")]}
    raw=dict(RAW,status="NEEDS_INPUT",functional="请提供实际的结果数值。",estimate_handoff={"mode":"STOP"})
    r=verify(c,raw)
    assert not r["clarification_questions"] and r["network_reading"]["unconfirmed_model_questions"]
    c["sources"][0]["text"]="原分配设计待补。"
    raw["functional"]="请提供分配规则。"
    v=verify(c,raw)
    assert len(v["clarification_questions"])==1 and v["network_reading"]["clarification_evidence"][0]["source_id"]=="att_01"


def relation_case():
    text = ("处理前登记了两套关系。依据换货往来的两端总体均值是7和3；按救援关系的两端是8和2。"
            "主管尚未决定本次使用哪一种伙伴关系。")
    return {"business_question": "固定叶井本人不轮岗，关联点有人轮岗比无人轮岗的平均差多少？",
            "sources": [{"source_id": "att_01", "label": "台账", "text": text}]}


def test_source_can_ask_for_relation_even_if_model_omits_answer():
    c = relation_case()
    facts_only = {"network_facts": {"network": {"value": None, "evidence": []}}}
    r = verify(c, facts_only, network_focus=True)
    assert len(r["clarification_questions"]) == 1 and "救援关系" in r["clarification_questions"][0]
    assert r["effective_answer"] is None and not r["estimation_handoff_allowed"]
    for ev in r["network_reading"]["relation_choice_evidence"]:
        assert c["sources"][0]["text"][ev["start"]:ev["end"]] == ev["quote"]
    assert replay(c, facts_only, r)
    old = verify(c, facts_only, network_focus=True, version="direct-verification/8")
    assert not old["clarification_questions"] and replay(c, facts_only, old)


def test_equal_differences_and_user_selection_do_not_trigger_relation_choice():
    c = relation_case()
    c["sources"][0]["text"] = c["sources"][0]["text"].replace("8和2", "8和4")
    assert not verify(c, RAW, network_focus=True)["clarification_questions"]
    c = relation_case()
    c["sources"].append({"source_id": "user_reply_1", "label": "补充", "text": "本次按救援关系。"})
    assert not verify(c, RAW, network_focus=True)["clarification_questions"]
    c = relation_case()
    c["business_question"] += "请分别计算两种。"
    assert not verify(c, RAW, network_focus=True)["clarification_questions"]


def test_unselected_relation_requires_materially_different_source_records():
    c = relation_case()
    c["sources"][0]["text"] = c["sources"][0]["text"].replace("按救援关系的两端是8和2。", "救援关系的数据待审。")
    assert not verify(c, RAW, network_focus=True)["clarification_questions"]
    c = relation_case()
    c["business_question"] = "请选择按救援关系求同伴作用的差。"
    assert not verify(c, RAW, network_focus=True)["clarification_questions"]
