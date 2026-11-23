"""The same signed claim must fit the whole target and lottery at display and at actual intake."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from serve import integrated_engine
from demo.backend.engine import Run
from demo.tests.test_uploaded_network_contrast import decisions, fixture_case
from cfm_id.direct_verification import replay, verify
from cfm_id.network_source_alignment import named_units
from cfm_id_llm.compact_study import digest


def test_ambiguous_lists_and_punctuation():
    assert named_units("和平站、河口", ["和平站","河口"]) == ["和平站","河口"]
    assert named_units("A与AB", ["A","AB"]) == ["A","AB"]
    assert named_units("A与B", ["A","B","A与B"]) is None
    assert named_units("东站、未登记的站", ["东站","西站"]) is None


@pytest.mark.parametrize("change", ["two_focal", "strata", "mixed_mapping", "reverse", "unequal_weights",
                                    "conflicting_table", "partial_graph", "candidate_target", "question_tie"])
def test_ungrounded_coordinates_leave_the_same_answer_and_no_review(tmp_path,change):
    case,draft,net=fixture_case(tmp_path,rule="majority",fixed=True,subgroup=True)
    if change=="two_focal":
        case["business_question"]=case["business_question"].replace("仅评价【谷口】","只评价谷口、西湾，两站各占一半")
    elif change=="strata":
        case["sources"].append(dict(source_id="allocation",label="招募规程",kind="OTHER",
                                    text="名额按区域分层，各层分别抽签。"))
    elif change=="mixed_mapping":
        case["sources"].append(dict(source_id="amendment",label="实施记录",kind="OTHER",
                                    text="合作单位的暴露在平票时记1。"))
    elif change=="reverse":
        v=draft["network_facts"]["contrast"]["value"]
        v["right"],v["left"]=v["left"],v["right"]
    elif change=="unequal_weights":
        draft["network_facts"]["contrast"]["value"]["weights"]={"谷口":"1/3","西湾":"2/3"}
    elif change=="conflicting_table":
        case["sources"].append(dict(source_id="att_rates",label="抽签备案.csv",kind="OTHER",
            text="node_id,启用概率\n谷口,1/4\n江岸,1/2\n山南,1/2\n西湾,1/2"))
    elif change=="partial_graph":
        case["sources"].append(dict(source_id="edge_memo",label="关系复核",kind="OTHER",text="处理前边表缺行。"))
    elif change=="question_tie":
        case["business_question"] += "本次计算平票记1。"
    else:
        draft["answers"][0]["target"]["population"]=["西湾"]
    report=verify(case,draft,network=net)
    assert report["effective_answer"]==draft and report["draft"]==draft
    assert report["decision"]=="RETAINED" and not report["network_alignment"]["matched"]
    assert report.get("condition_review") is None and not report["estimation_handoff_allowed"]
    assert not report["clarification_questions"] and replay(case,draft,report)


def test_receiver_recomputes_source_even_with_internally_rehashed_wrong_packet(tmp_path):
    case,draft,net=fixture_case(tmp_path,rule="majority")
    engine=integrated_engine(tmp_path/"web",max_api_calls=0)
    run=Run(id=case["case_id"],owner="offline",case=case,network=net,synthetic=True,reading_mode="network_direct_verify")
    engine.runs[run.id]=run
    pending=verify(case,draft,network=net)
    assert pending["decision"]=="PREMISES_REQUIRED" and pending["network_alignment"]["matched"]
    engine._finish_direct_verification(run,pending)
    assert not engine.estimate_inbox.path_for(run.id).exists()
    engine._review_network(run,decisions(pending))
    import json
    path=engine.estimate_inbox.path_for(run.id)
    packet=json.loads(path.read_text(encoding="utf8"))["packet"]
    assert engine.estimate_inbox.receive(run.id,packet)["query_count"]==2*len(net.nodes)
    amended=deepcopy(packet)
    amended["source_case"]["business_question"]=case["business_question"].replace("全部4个站点等权","只评价谷口")
    sheet=amended["condition_review"]
    sheet["case_sha256"]=digest(amended["source_case"])
    sheet["binding"]=digest([{k:v for k,v in sheet.items() if k!="binding"},amended["source_proof"],
                            amended["target"],amended["estimate_handoff"]])
    amended["review"]["binding"]=sheet["binding"]
    with pytest.raises(ValueError,match="SOURCE_ALIGNMENT_FAILED"):
        engine.estimate_inbox.receive(run.id,amended)
    old=deepcopy(packet)
    old["version"]="identification-handoff/1"
    with pytest.raises(ValueError,match="SOURCE_ALIGNED_PACKET_REQUIRED"):
        engine.estimate_inbox.receive(run.id,old)
    # A prior signed release is withdrawn when the run's actual materials change.
    run.case=amended["source_case"]
    with pytest.raises(ValueError):
        engine._review_network(run,decisions(pending))
    assert json.loads(path.read_text(encoding="utf8"))["packet"] is None and engine.calls==0
