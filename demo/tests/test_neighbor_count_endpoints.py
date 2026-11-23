from fractions import Fraction
from itertools import combinations

import pytest

from cfm_id.direct_verification import replay, verify
from cfm_id.network_estimate_handoff import evaluate_from_catalog
from cfm_id.network_grounded_contrast import derive


def dispatch_case(contrast, three_neighbors=False):
    edges = "松桥、竹湾和柳埠" if three_neighbors else "松桥和竹湾"
    text = (
        f"芦港、松桥、竹湾、柳埠、白涧这五处都在名单上。试验前芦港只与{edges}相连。"
        "每周在五站中均匀选定恰好3站开灯，任意组合等机会。"
        "名单与一切潜在等待时数独立，实际名单对应其潜在记录。可调用每个正概率状态的总体平均时数。"
    )
    question = (f"调度只要芦港的数字：它这周开灯时，{contrast}的平均等待时数。"
                "其余站仍按旧抽签条件取平均，给两个联合概率。")
    return {"business_question": question, "sources": [{"source_id":"ledger", "text":text}]}


@pytest.mark.parametrize("contrast,rule,states,counts", [
    ("两个邻站均开灯减两个邻站都不开灯", "count", (2, 0), ({2}, {0})),
    ("两个邻站恰好一个开灯减两个邻站均未开灯", "count", (1, 0), ({1}, {0})),
    ("两个邻站全不开灯减两个邻站都开灯", "count", (0, 2), ({0}, {2})),
    ("两个邻站至少一处开灯减两个邻站都不开灯", "any", (1, 0), ({1, 2}, {0})),
    ("两个邻站过半开灯减至多一半开灯", "majority", (1, 0), ({2}, {0, 1})),
    ("两个邻站过半开灯减两个邻站全不开灯", "count", (2, 0), ({2}, {0})),
])
def test_ordered_support_matches_full_assignment_enumeration(contrast, rule, states, counts):
    case = dispatch_case(contrast)
    report = verify(case, {}, network_focus=True)
    assert replay(case, {}, report)
    proof = report["proof"]
    assert proof["exposure"] == rule
    draws = list(combinations(range(5), 3))
    expected = {}
    for state, group in zip(states, counts):
        n = sum(0 in d and len({1, 2}.intersection(d)) in group for d in draws)
        expected[f"1,{state}"] = str(Fraction(n, len(draws)))
    assert proof["joint_probabilities"]["芦港"] == expected
    handoff = report["effective_answer"]["estimate_handoff"]
    assert [q["exposure"] for q in handoff["queries"]] == list(states)
    assert all(q["exposure_rule"] == rule for q in handoff["queries"])
    assert evaluate_from_catalog(handoff, lambda q: 10 + 2 * q["exposure"]) == str(2 * (states[0] - states[1]))


@pytest.mark.parametrize("phrase", [
    "三个邻站过半开灯减三个邻站都不开灯",
    "三个邻站不都是开灯减三个邻站都不开灯",
    "两个邻站均开灯减两个邻站都不开灯",
])
def test_mixed_unrepresentable_ambiguous_or_inconsistent_events_get_no_proof(phrase):
    assert derive(dispatch_case(phrase, three_neighbors=True), {}) is None


def test_no_numeric_answer_from_different_population_queries():
    question = "我们要看本人没收到邀请时，两个好友均获邀对比好友全无的月底回访率变化。问的是云堤本人。"
    text = ("云堤和两位固定好友各自独立抛公平硬币决定有没有训练邀请；邀请名单与所有潜在回访独立，记录按实际邀请名单一致。"
            "比较按原抽签条件平均；云堤本人未获邀时，在有好友获邀和无好友获邀两种情况下，总体回访率依次是0.8、0.35。")
    case = {"business_question":question, "sources":[{"source_id":"ledger","text":text}]}
    assert derive(case, {}) is None
    case["business_question"] = question.replace("两个好友均获邀", "有朋友获邀")
    assert derive(case, {})["answer"]["value"] == "9/20"


@pytest.mark.parametrize("substitute,denied", [
    ("名单与一切潜在等待时数独立吗？研究者没有得到确认", False),
    ("是否能认为名单与一切潜在等待时数独立，评审目前尚无定论", False),
    ("名单与一切潜在等待时数独立这句话在本轮不成立", True),
])
def test_scientific_statement_has_to_be_asserted(substitute, denied):
    case = dispatch_case("两个邻站都开灯减两个邻站都不开灯")
    doc = case["sources"][0]
    doc["text"] = doc["text"].replace("名单与一切潜在等待时数独立", substitute)
    result = verify(case, {}, network_focus=True)
    assert replay(case, {}, result)
    answer, proof = result["effective_answer"], result["proof"]
    assert answer["status"] == "NEEDS_INPUT" and answer["estimate_handoff"]["mode"] == "STOP"
    assert answer["assumptions"] == [] and len(result["clarification_questions"]) == 1
    field = "denied" if denied else "unconfirmed"
    assert proof[field] == ["整份名单独立于各名单下的潜在结局"]
    assert result["checks"][-1]["state"] == "UNCHECKED"
    assert not result["scientific_approval"]


def test_unconfirmed_consistency_is_not_randomization_doubt():
    case = dispatch_case("两个邻站均开灯减两个邻站都不开灯")
    doc = case["sources"][0]
    doc["text"] = doc["text"].replace("实际名单对应其潜在记录", "是否实际名单对应其潜在记录，目前未知")
    result = verify(case, {}, network_focus=True)
    assert result["proof"]["unconfirmed"] == ["实测结局对应实际名单下的潜在结局"]
    assert result["effective_answer"]["estimate_handoff"]["mode"] == "STOP"


@pytest.mark.parametrize("relationship_record", [
    "试验前只登记站点名称。试验后才调查当时的关系，芦港只与松桥和竹湾相连。",
    "试验前芦港只与松桥和竹湾相连。另一份分配前的表写芦港只与白涧相连。",
    "另一份分配前的表写芦港只与白涧相连。试验前芦港只与松桥和竹湾相连。",
])
def test_relation_dates_and_conflicts_are_bound_to_the_actual_edges(relationship_record):
    case = dispatch_case("两个邻站均开灯减两个邻站都不开灯")
    doc = case["sources"][0]
    doc["text"] = doc["text"].replace("试验前芦港只与松桥和竹湾相连。", relationship_record)
    result = verify(case, {}, network_focus=True)
    assert replay(case, {}, result)
    assert result["effective_answer"] is None and result["proof"] is None
    assert len(result["clarification_questions"]) == 1
    assert "分配前" in result["clarification_questions"][0]
    assert "等价事件" in result["clarification_questions"][0]
    check = result["checks"][-1]
    assert check["code"] == "UNRESOLVED_BASELINE_NEIGHBORS"
    assert all(doc["text"][r["start"]:r["end"]] == r["quote"] for r in check["evidence"])


def test_explicit_baseline_record_can_be_dated_in_its_own_sentence():
    case = dispatch_case("两个邻站均开灯减两个邻站都不开灯")
    doc = case["sources"][0]
    doc["text"] = doc["text"].replace("试验前芦港只与松桥和竹湾相连。",
                    "合作图在试验前画好。芦港只与松桥和竹湾相连。上线后芦港只与白涧相连。")
    result = verify(case, {}, network_focus=True)
    assert result["effective_answer"]["status"] == "POINT"
    refs = result["proof"]["bound_fields"]["network"]
    assert any(r["quote"] == "合作图在试验前画好" for r in refs)
    assert not any("上线后" in r["quote"] for r in refs)
