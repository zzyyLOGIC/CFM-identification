"""Reverse targets exercise the real engine/verifier, not new formula fixtures.

Source/audit replies below are stipulated for offline interface tests. They are
not live LLM answers and must not be counted as model-accuracy measurements.
"""
from copy import deepcopy
from fractions import Fraction
from itertools import product
import re

import pytest

from cfm_id import population_ate_entry as entry
from cfm_id import direct_verification
from cfm_id_llm import population_ate_reading as reading


def business_fixture(*, observational=False, probability="1/3", direction="0-1",
                     lower=0, upper=100, finite=True, extra=None):
    order="不参加减参加" if direction=="0-1" else "参加减不参加"
    design="是否参加由员工自行决定。" if observational else f"每位员工独立抽签，参加培训的概率为{probability}。"
    outcome="次月是否达标，达标记1、未达标记0" if observational else "次月评分"
    domain="结果只能取0或1。" if observational else (
        (f"评分最低{lower}。" if lower is not None else "评分没有已知下限。")+
        (f"评分最高{upper}。" if upper is not None else "评分没有已知上限。"))
    text=(f"研究全部客服，参加培训记1，不参加记0。想知道{outcome}的平均差，{order}，只求计算公式。"+
          design+domain+"采用以下研究前提：实际结果对应本人实际接受的处理；其他人的安排不影响本人的结果。"+
          ("两种处理下的平均结果都存在且有限。" if finite else "是否采用平均结果存在且有限的前提，尚未决定。")+
          "已知这批客服在次月的处理与结果联合总体分布P(T,Y)，不是只有一批样本。"+
          (extra or "没有额外采用的限制。"))
    case=dict(case_id="ordinary-ate-direction",business_question=text,sources=[])
    evidence=[dict(source_id="question",quote=text)]
    def claim(value):return dict(value=value,evidence=deepcopy(evidence))
    candidate=dict(family=claim("PLAIN_ATE"),target=claim(dict(population="全部客服",treatment_1="参加培训",
        treatment_0="不参加培训",outcome=outcome,period="次月",direction=direction,conditional=False,output="FORMULA")),
        outcome_domain=claim(dict(kind="binary" if observational else "continuous",lower=0 if observational else lower,
                                 upper=1 if observational else upper,values=None)),
        design=claim(dict(kind="OBSERVATIONAL" if observational else "RANDOMIZED",probability=None if observational else probability)),
        information=claim(dict(kind="POPULATION_JOINT",matches_target=True)),
        conditions=[dict(code=k,status="ADOPTED",statement=statement,evidence=deepcopy(evidence)) for k,statement in (
            ("consistency","实际结果对应本人实际接受的处理"),("no_interference","其他人的安排不影响本人的结果"))]+
            [dict(code="finite_conditional_first_moments",status="ADOPTED" if finite else "UNDECIDED",
                  statement="两种处理下的平均结果都存在且有限",evidence=deepcopy(evidence))],other_information=[])
    if extra:candidate["conditions"].append(dict(code="extra",status="ADOPTED",statement=extra,evidence=deepcopy(evidence)))
    draft=dict(status="POINT",target=dict(quantity="difference",scope="whole",population="全部客服",
        intervention="不参加培训" if direction=="0-1" else "参加培训",
        reference="参加培训" if direction=="0-1" else "不参加培训",outcome=outcome,time="次月"),
        functional="模型原答待核验",assumptions=[],value=None,estimate_handoff=dict(mode="STOP"),reason="离线接口测试答卷")
    return case,candidate,draft


def audit(case,candidate):
    return dict(binding=reading.binding(case,candidate),scientific_approval=False,findings=[
        dict(field=k,verdict="MATCH",evidence=deepcopy(v.get("evidence",[])),
             reason="离线接口验收预置核对，不是模型准确率测评。",question=None)
        for k,v in reading.audit_fields(candidate).items()])


def plan(case,candidate,draft):
    candidate=reading.inspect(case,candidate)
    base=direct_verification.verify(case,draft)
    assert entry.eligible(base)
    return entry.plan(case,entry._base(base,case,candidate,audit(case,candidate)))


def finish(case,pending):
    sheet=pending["condition_review"]
    return entry.complete(case,pending,dict(binding=sheet["binding"],authority="SYNTHETIC_TEST",
        decisions={i["code"]:"ADOPTED" for i in sheet["items"]}))


def test_reverse_point_preserves_coding_probability_and_replays():
    case,s,draft=business_fixture()
    pending=plan(case,s,draft)
    assert "不参加培训 减去 参加培训" in pending["condition_review"]["items"][0]["quote"]
    out=finish(case,pending)
    assert out["conditional_answer"]["functional"]=="E[Y | T=0] - E[Y | T=1]"
    assert out["conditional_answer"]["target"]["intervention"]=="不参加培训"
    native=out["population_ate"]["native_spec"]
    assert native["support_domain"]["assignment_probability"]==pytest.approx(1/3)
    assert "T=1：参加培训；T=0：不参加培训" in native["query"]["interpretation_notes"]
    assert out["proof"]["native_result"]["identified_functional"]["left"]["treatment_value"]==1
    assert not out["estimation_handoff_allowed"] and out["draft"]==draft
    assert direct_verification.replay(case,draft,out)


def test_forward_result_unchanged_and_no_reverse_proof_added():
    case,s,draft=business_fixture(direction="1-0")
    out=finish(case,plan(case,s,draft))
    assert out["conditional_answer"]["functional"]=="E[Y | T=1] - E[Y | T=0]"
    assert "target_operation" not in out["proof"]
    assert direct_verification.replay(case,draft,out)


def test_reverse_manski_matches_all_binary_missing_outcome_completions():
    case,s,draft=business_fixture(observational=True)
    out=finish(case,plan(case,s,draft))
    assert out["population_ate"]["state"]=="PARTIAL"
    assert out["population_ate"]["native_result"]["guarantee"]=="sharp"
    bounds=out["proof"]["target_operation"]["derived_interval"]
    # Independent attainable-extremes check on all joint tables of 4 units.
    for counts in product(range(5),repeat=4):
        if sum(counts)!=4:continue
        masses={f"P(Y={y},T={t})":Fraction(counts[2*t+y],4) for t,y in product(range(2),repeat=2)}
        units=[(t,y) for t,y in product(range(2),repeat=2) for _ in range(counts[2*t+y])]
        completions=[]
        for missing in product((0,1),repeat=4):
            completions.append(sum((y-m if t==0 else m-y) for (t,y),m in zip(units,missing))/4)
        def evaluate(expr):
            # Evaluate only this trusted native expression after substituting probabilities.
            for key,value in masses.items():expr=expr.replace(key,str(float(value)))
            assert re.fullmatch(r"[0-9.()+\- ]+",expr)
            return eval(expr,{"__builtins__":{}},{})
        assert evaluate(bounds["lower"])==min(completions)
        assert evaluate(bounds["upper"])==max(completions)
    assert direct_verification.replay(case,draft,out)


@pytest.mark.parametrize("p",["0","1"])
@pytest.mark.parametrize("lower,upper",[(0,100),(None,100),(0,None),(None,None)])
def test_reverse_one_arm_including_open_infinite_endpoints(p,lower,upper):
    case,s,draft=business_fixture(probability=p,lower=lower,upper=upper)
    out=finish(case,plan(case,s,draft))
    interval=out["proof"]["target_operation"]["derived_interval"]
    observed=int(p);mu="E[Y | T="+p+"]"
    def value(expr):
        if expr=="-inf":return float('-inf')
        if expr=="+inf":return float('inf')
        expr=expr.replace(mu,"40")
        assert re.fullmatch(r"[0-9.()+\- ]+",expr)
        return eval(expr,{"__builtins__":{}},{})
    lo=float('-inf') if (upper is None if observed==0 else lower is None) else (40-upper if observed==0 else lower-40)
    hi=float('inf') if (lower is None if observed==0 else upper is None) else (40-lower if observed==0 else upper-40)
    assert (value(interval["lower"]),value(interval["upper"]))==(lo,hi)
    assert interval["lower_closed"]==(lo!=float('-inf'))
    assert interval["upper_closed"]==(hi!=float('inf'))
    assert direct_verification.replay(case,draft,out)


@pytest.mark.parametrize("change",["direction","formula","operation","native_probability"])
def test_reverse_proof_tampering_fails_replay(change):
    case,s,draft=business_fixture();out=finish(case,plan(case,s,draft))
    if change=="direction":out["population_ate"]["reading"]["target"]["value"]["direction"]="1-0"
    elif change=="formula":out["conditional_answer"]["functional"]="E[Y | T=1] - E[Y | T=0]"
    elif change=="operation":out["proof"]["target_operation"]["treatment_recoded"]=True
    else:out["population_ate"]["native_spec"]["support_domain"]["assignment_probability"]=2/3
    assert not direct_verification.replay(case,draft,out)


def test_reverse_still_asks_missing_moments_and_retains_extra_restrictions():
    case,s,draft=business_fixture(lower=None,upper=None,finite=False)
    out=plan(case,s,draft)
    assert out["population_ate"]["state"]=="NEEDS_INPUT" and not out["backend_called"]
    assert any("存在且有限" in q for q in out["clarification_questions"])
    case,s,draft=business_fixture(observational=True,extra="另采用：培训不会降低任何人的结果。")
    out=finish(case,plan(case,s,draft))
    assert out["population_ate"]["state"]=="NOT_COVERED"
    assert out["population_ate"]["reason_code"]=="LEGACY_ATE_UNSUPPORTED_EXTRA_ASSUMPTION"
    assert not out["proof"] and not out["independent_replay"]


@pytest.mark.parametrize("wrapper",["flat","answer","answers"])
def test_misplaced_target_only_triggers_independent_source_reading(wrapper):
    case,s,draft=business_fixture(observational=True)
    flat={**draft.pop("target"),**draft}
    flat.update(intervention="参加培训",reference="不参加培训",functional="incorrect model answer")
    draft=flat if wrapper=="flat" else {wrapper:flat if wrapper=="answer" else [flat]}
    saved=deepcopy(draft)
    out=finish(case,plan(case,s,draft))
    assert out["draft"]==saved  # no in-place normalization of the model answer
    assert out["conditional_answer"]["target"]["intervention"]=="不参加培训"
    assert out["population_ate"]["state"]=="PARTIAL"
    assert direct_verification.replay(case,draft,out)


@pytest.mark.parametrize("draft",[
    {"quantity":"difference","target":{"quantity":"mean"}},
    {"quantity":"difference","target":None},
    {"answers":[{"quantity":"difference"},None]},
    {"answers":[{"quantity":"difference"},{"quantity":"difference"}]},
])
def test_conflicting_or_multiple_targets_are_not_flattened(draft):
    assert not entry.eligible(dict(draft=draft))


def test_citation_schema_lists_actual_ids_but_unknown_ids_and_changed_quotes_still_fail():
    import json
    case,s,_=business_fixture()
    case["sources"]=[dict(source_id="protocol-file",text="补充材料原句")]
    for request in (reading.request(case),reading.audit_request(case,s)):
        body=json.loads(request["user_prompt"])
        assert body["valid_source_ids"]==["protocol-file","question"]
        schema=body.get("output_schema",body.get("reading_schema"))
        assert schema["$defs"]["Citation"]["properties"]["source_id"]["enum"]==["protocol-file","question"]
    for source_id,quote,code in [("source_catalog","补充材料原句","UNKNOWN_SOURCE_ID"),
                               ("protocol-file","根本不存在的引用","NOT_IN_SOURCE")]:
        with pytest.raises(ValueError,match=code):
            reading.check_citations([dict(source_id=source_id,quote=quote)],reading.sources(case))


def test_unknown_scope_still_needs_an_answer_not_programmatic_false():
    case,s,draft=business_fixture();s["target"]["value"]["conditional"]=None
    out=plan(case,s,draft)
    assert out["population_ate"]["state"]=="NEEDS_INPUT" and not out["backend_called"]
    assert out["population_ate"]["reading"]["target"]["value"]["conditional"] is None


def test_audit_output_schema_requires_explicit_question_and_does_not_fill_missing_fields():
    import json
    case,s,_=business_fixture(observational=True)
    request=json.loads(reading.audit_request(case,s)["user_prompt"])
    schema=request["output_schema"]
    assert "question" in schema["$defs"]["AuditFinding"]["required"]
    assert "default" not in schema["$defs"]["AuditFinding"]["properties"]["question"]
    assert schema["$defs"]["AuditFinding"]["properties"]["field"]["enum"]==list(reading.audit_fields(s))
    findings=[dict(field=k,verdict="MATCH",evidence=v.get("evidence",[]),reason="checked",question=None)
              for k,v in reading.audit_fields(s).items()]
    audit=dict(binding=reading.binding(case,s),scientific_approval=False,findings=findings)
    assert reading.check_audit(case,s,audit)==audit
    del audit["findings"][0]["question"]
    saved=deepcopy(audit)
    with pytest.raises(ValueError,match='missing=\\["question"\\]'):
        reading.check_audit(case,s,audit)
    assert audit==saved
    audit["findings"][0].update(question=None,verdict="NEEDS_CLARIFICATION")
    with pytest.raises(ValueError,match="QUESTION_REQUIRED"):
        reading.check_audit(case,s,audit)
