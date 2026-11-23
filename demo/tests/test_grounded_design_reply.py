import pytest

from cfm_id.direct_verification import replay, verify
from cfm_id.network_grounded_contrast import derive


def exchange(replies, rate="1/3"):
    question = "只评冬亭，冬亭不发广告时，隔壁至少一家发与隔壁都不发相比，本周客流会多多少？沿用原分配条件，两个联合事件出现的机会是多少？"
    text = ("原来三家商户共用通道。冬亭的邻店恰是南溪、北塘，关系在活动前固定。"
            f"留存的只有各店自己被选的概率，三个都是{rate}。没有人知道联合机制，采购没人能确认签是各自抽还是一起抽。"
            "完整列单独立于潜在客流，实际客流对应实际列单。只许用有支持状态的总体条件客流均值。")
    records = [dict(source_id="att_01", text=text)]
    records.extend(dict(source_id=f"user_reply_{i}", kind="OTHER", label="用户补充说明", text=value)
                   for i, value in enumerate(replies))
    return dict(business_question=question, sources=records)


@pytest.mark.parametrize(("replies","status","support"),[
    (["各自独立抽签"], "POINT", {"0,1":"10/27","0,0":"8/27"}),
    (["所有单位同签同处理"], "UNDEFINED", {"0,1":"0","0,0":"2/3"}),
    (["不知道", "独立抽签。"], "POINT", {"0,1":"10/27","0,0":"8/27"}),
    (["仍不清楚"], "NEEDS_INPUT", None),
    (["独立抽签", "同签"], "NEEDS_INPUT", None),
])
def test_explicit_answer_updates_only_original_joint_law(replies, status, support):
    case = exchange(replies)
    result = verify(case, {}, network_focus=True)
    assert replay(case, {}, result)
    assert result["effective_answer"]["status"] == status
    assert result["effective_answer"]["target"]["population"] == ["冬亭"]
    proof = result["proof"]
    if support is not None:
        assert proof["joint_probabilities"]["冬亭"] == support
    else:
        assert len(proof["alternative_joint_probabilities"]) == 2
    docs = {s["source_id"]: s["text"] for s in case["sources"]}
    evidence = [e for e in proof["bound_fields"]["assignment"] if e["source_id"].startswith("user_reply_")]
    assert len(evidence) == len(replies)
    assert all(docs[e["source_id"]][e["start"]:e["end"]] == e["quote"] for e in evidence)


@pytest.mark.parametrize("text",[
    "若各自独立抽签", "下个月各自独立抽签", "独立抽签，同时把总体改为全城",
    "各单位独立抽签，边际概率改成一成", "另一组独立抽签", "不是各自独立抽签",
])
def test_qualified_and_out_of_scope_reply_cannot_select_the_rule(text):
    assert derive(exchange([text]), {}) is None


def test_attachment_cannot_speak_for_user_and_reply_cannot_override_a_known_rule():
    case = exchange(["共签"])
    case["sources"][-1]["source_id"] = "att_02"
    assert derive(case, {}) is None
    case = exchange(["各自独立抽签"])
    case["sources"][0]["text"] = case["sources"][0]["text"].replace(
        "留存的只有各店自己被选的概率，三个都是1/3。没有人知道联合机制，采购没人能确认签是各自抽还是一起抽。",
        "三家一起掷同一枚公平硬币，正面三家都发，反面全不发。")
    assert derive(case, {}) is None
