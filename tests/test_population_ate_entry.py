"""Source binding, scientific adoption and existing native formula regressions."""
from copy import deepcopy
from unittest.mock import patch

import pytest

from cfm_id import population_ate_entry as entry
from cfm_id_llm import population_ate_reading as reader
from cfm_id_llm.compact_study import digest


TEXT = "全部客服参加培训记1、不参加记0，求次月评分的平均影响，参加减不参加，只求公式。每人随机安排，概率一半。评分0到100。采用一致性和无干扰。已知同一人群时期的P(T,Y)。没有其他条件。"


def fixture(observed=False):
    case=dict(case_id="ate-source",business_question=TEXT,sources=[])
    e=[dict(source_id="question",quote=TEXT)]
    def claim(v):return dict(value=v,evidence=deepcopy(e))
    s=dict(
        family=claim("PLAIN_ATE"),
        target=claim(dict(population="全部客服",treatment_1="参加培训",treatment_0="不参加培训",
            outcome="次月评分",period="次月",direction="1-0",conditional=False,output="FORMULA")),
        outcome_domain=claim(dict(kind="binary" if observed else "continuous",
            lower=0,upper=1 if observed else 100,values=None)),
        design=claim(dict(kind="OBSERVATIONAL" if observed else "RANDOMIZED",probability=None if observed else "1/2")),
        information=claim(dict(kind="POPULATION_JOINT",matches_target=True)),
        conditions=[dict(code=k,status="ADOPTED",statement=k,evidence=deepcopy(e)) for k in ("consistency","no_interference")]+[
            dict(code="finite_conditional_first_moments",status="UNKNOWN",statement="",evidence=[])],
        other_information=[])
    report=dict(version="direct-verification/24",draft={"target":{"quantity":"difference"}},draft_sha256=digest({}),
        checks=[],decision="RETAINED",proof=None,estimation_handoff_allowed=False)
    return case,reader.inspect(case,s),report


def audit(case,s):
    return dict(binding=reader.binding(case,s),scientific_approval=False,findings=[
        dict(field=k,verdict="MATCH",evidence=deepcopy(v.get("evidence",[])),reason="测试审核记录；真实读取另行实测。",question=None)
        for k,v in reader.audit_fields(s).items()])


def planned(case,s,r):
    checked=reader.inspect(case,s)
    return entry.plan(case,entry._base(r,case,checked,audit(case,checked)))


def review(report):
    sheet=report["condition_review"]
    return dict(binding=sheet["binding"],authority="SYNTHETIC_TEST",decisions={i["code"]:"ADOPTED" for i in sheet["items"]})


@pytest.mark.parametrize("observed,expected,formula",[
    (False,"POINT","E[Y | T=1] - E[Y | T=0]"),
    (True,"PARTIAL","[-P(Y=0,T=1)-P(Y=1,T=0), P(Y=1,T=1)+P(Y=0,T=0)]"),
])
def test_native_formula_only_after_explicit_current_review(observed,expected,formula):
    case,s,r=fixture(observed);p=planned(case,s,r)
    assert p["population_ate"]["state"]=="REVIEW_REQUIRED" and not p["backend_called"]
    assert not p["proof"] and not p["scientific_approval"]
    done=entry.complete(case,p,review(p))
    assert done["population_ate"]["state"]==expected
    assert done["conditional_answer"]["functional"]==formula
    assert done["independent_replay"] and done["backend_called"]
    native=done["population_ate"]["native_spec"]
    assert native["query"]["target_population"]=="overall_population"
    assert native["support_domain"]["analysis_unit"]=="全部客服"
    assert "全部客服" in native["query"]["interpretation_notes"]
    assert not done["estimation_handoff_allowed"]
    assert p["population_ate"]["state"]=="REVIEW_REQUIRED"  # input not mutated


@pytest.mark.parametrize("status",["UNKNOWN","UNDECIDED","NOT_ADOPTED"])
def test_unbounded_moments_cannot_be_invented(status):
    case,s,r=fixture();s["outcome_domain"]["value"].update(lower=None,upper=None)
    s["conditions"][2].update(status=status,statement="均值存在且有限",evidence=s["target"]["evidence"] if status!="UNKNOWN" else [])
    p=planned(case,s,r)
    assert not p.get("condition_review") and not p["backend_called"]
    if status=="NOT_ADOPTED":assert p["population_ate"]["state"]=="NOT_COVERED"
    else:
        assert p["population_ate"]["state"]=="NEEDS_INPUT"
        assert "存在且有限" in p["clarification_questions"][0]


@pytest.mark.parametrize("status,state",[
    ("ADOPTED","NOT_COVERED"),("NOT_ADOPTED","PARTIAL"),("UNDECIDED","NEEDS_INPUT")])
def test_manski_extra_status_survives_reading_review_and_native_input(status,state):
    case,s,r=fixture(True)
    s["conditions"].append(dict(code="extra",statement="培训不会降低任何人的结果",status=status,evidence=s["target"]["evidence"]))
    p=planned(case,s,r)
    if status=="UNDECIDED":
        assert "仍未决定" in p["clarification_questions"][0]
        assert not p["backend_called"] and not p.get("condition_review")
    else:
        p=entry.complete(case,p,review(p))
        native=p["population_ate"]["native_spec"]
        assert native["assumptions"][-1]["status"]==("ADMITTED" if status=="ADOPTED" else "NOT_ADMITTED")
        assert native["assumptions"][-1]["details"]=="培训不会降低任何人的结果"
        if status=="ADOPTED":
            assert p["population_ate"]["reason_code"]=="LEGACY_ATE_UNSUPPORTED_EXTRA_ASSUMPTION"
            assert p["backend_called"] and not p["proof"]
    assert p["population_ate"]["state"]==state


def test_narrowed_binary_domain_reaches_native_rejection():
    case,s,r=fixture(True);s["outcome_domain"]["value"]["upper"]=0
    p=planned(case,s,r);out=entry.complete(case,p,review(p))
    assert out["population_ate"]["reason_code"]=="LEGACY_ATE_NARROWED_BINARY_DOMAIN"
    assert out["backend_called"] and not out["independent_replay"]


@pytest.mark.parametrize("change",["case","candidate","audit","review","sheet"])
def test_stale_or_tampered_records_never_call_math(change):
    case,s,r=fixture();p=planned(case,s,r);rec=review(p)
    if change=="case":case["business_question"]+="现在改看另一个人群。"
    elif change=="candidate":p["population_ate"]["reading"]["target"]["value"]["population"]="另一人群"
    elif change=="audit":p["population_ate"]["audit"]["scientific_approval"]=True
    elif change=="review":rec["binding"]="wrong"
    elif change=="sheet":p["condition_review"]["items"][0]["quote"]="改过的问题"
    with patch("pfn_pipeline._internal.identification.identification.IdentificationEngine.solve_verified") as solve:
        with pytest.raises(ValueError):entry.complete(case,p,rec)
        solve.assert_not_called()


@pytest.mark.parametrize("decision",["UNSURE","DECLINED"])
def test_user_does_not_adopt_science_no_solver(decision):
    case,s,r=fixture();p=planned(case,s,r);rec=review(p);rec["decisions"]["condition_0"]=decision
    with patch("pfn_pipeline._internal.identification.identification.IdentificationEngine.solve_verified") as solve:
        out=entry.complete(case,p,rec)
        solve.assert_not_called()
    assert not out["proof"] and not out["backend_called"]


def test_semantic_reread_preserves_original_model_answer():
    case,s,r=fixture()
    first=deepcopy(s);first["conditions"][0]["status"]="NOT_ADOPTED"
    bad=audit(case,first)
    bad["findings"][5].update(verdict="READING_ERROR",reason="原文采用，被读成不采用。")
    replies=[first,bad,s,audit(case,s)];stages=[]
    def call(req,stage):
        stages.append(stage);return deepcopy(replies.pop(0))
    p=entry.prepare(case,r,call)
    assert len(stages)==4 and stages[-1].endswith("_reread")
    assert p["draft"]==r["draft"]
    assert p["population_ate"]["reading"]["conditions"][0]["status"]=="ADOPTED"
    assert not p["backend_called"] and p["condition_review"]


def test_audit_cannot_silently_skip_additional_condition_or_coverage():
    case,s,r=fixture();good=audit(case,s)
    for field in ("coverage","conditions.0"):
        bad=deepcopy(good);bad["findings"]=[f for f in bad["findings"] if f["field"]!=field]
        with pytest.raises(ValueError,match="COVERAGE"):reader.check_audit(case,s,bad)


def test_bad_quote_is_not_a_pass():
    case,s,r=fixture();s["conditions"][0]["evidence"][0]["quote"]="原文没有的话"
    with pytest.raises(ValueError,match="CITATION"):reader.inspect(case,s)


@pytest.mark.parametrize("change,reason",[
    ("sample","POPULATION_ATE_INPUT_REQUIRED"),
    ("other_operation","POPULATION_ATE_TARGET_NOT_SUPPORTED"),
    ("more_information","POPULATION_ATE_ADDITIONAL_INFORMATION")])
def test_scope_sample_and_extra_information_not_rewritten(change,reason):
    case,s,r=fixture()
    if change=="sample":s["information"]["value"]["kind"]="SAMPLE"
    elif change=="other_operation":s["target"]["value"]["direction"]="OTHER"
    else:s["other_information"]=[dict(kind="POPULATION_OBJECT",value="另一个时期的联合分布",evidence=s["target"]["evidence"])]
    p=planned(case,s,r)
    assert p["population_ate"]["reason_code"]==reason and not p["backend_called"]


def test_actual_engine_action_keeps_audit_and_science_separate(tmp_path):
    import json,time
    from demo.backend.engine import Engine
    _,s,_=fixture()
    class Local(Engine):
        def call(self,run,request,stage):
            self.seen.append(stage)
            if stage=="direct_draft":
                return dict(status="POINT",target=dict(quantity="difference",scope="whole"),
                    value=None,functional="model draft only",assumptions=[],
                    estimate_handoff=dict(mode="STOP"),reason="草稿")
            if stage=="population_ate_read":return deepcopy(s)
            if stage=="population_ate_audit":
                body=json.loads(request["user_prompt"])
                return dict(binding=body["input_binding"],scientific_approval=False,findings=[
                    dict(field=k,verdict="MATCH",evidence=v.get("evidence",[]),
                         reason="离线接口测试的预置核对，另做真实LLM验收。",question=None)
                    for k,v in body["fields"].items()])
            raise AssertionError(stage)
    e=Local(tmp_path);e.seen=[]
    e.credential("visitor","longcat","local-test-token")
    rid=e.start("visitor",dict(question=TEXT,synthetic=True,allow_send=True))
    def wait():
        for _ in range(300):
            v=e.view("visitor",rid)
            if not v["busy"]:return v
            time.sleep(.01)
        raise AssertionError("Background worker did not finish")
    v=wait()
    assert not v["error"],v["error"]
    assert e.seen==["direct_draft","population_ate_read","population_ate_audit"]
    assert v["stage"]=="REVIEW_REQUIRED"
    assert not v["result"]["backend_called"] and not v["result"]["proof"]
    rec=review(v["result"])
    with pytest.raises(ValueError):
        e.action("visitor",rid,"review_population_ate_conditions",
                 dict(binding=rec["binding"],decisions=rec["decisions"],authority="EXTERNAL_RESEARCH_REVIEW"))
    e.action("visitor",rid,"review_population_ate_conditions",
             dict(binding=rec["binding"],decisions=rec["decisions"]))
    v=wait()
    assert not v["error"],v["error"]
    assert v["stage"]=="RESULT" and v["result"]["population_ate"]["state"]=="POINT"
    assert v["result"]["independent_replay"] and not v["can_estimate"]
    assert v["result"]["review_record"]["authority"]=="SYNTHETIC_TEST"
    assert len(e.seen)==3  # mathematical execution does not ask the LLM again
    from cfm_id.direct_verification import replay
    run=e.get("visitor",rid)
    assert replay(run.case,run.result["draft"],run.result)
    altered=deepcopy(run.result)
    altered["conditional_answer"]["functional"]="an invented expression"
    assert not replay(run.case,run.result["draft"],altered)
    altered=deepcopy(run.result)
    altered["population_ate"]["native_spec"]["support_domain"]["analysis_unit"]="another population"
    assert not replay(run.case,run.result["draft"],altered)
