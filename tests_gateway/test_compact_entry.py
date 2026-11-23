"""Business matching, source/authority gates, multiple proofs and estimate handoff."""
from copy import deepcopy
import pytest
from cfm_id.compact_entry import plan,complete
from cfm_id_llm.compact_study import inspect
from cfm_id.iv_route_contract import IVProblem
from examples.iv_research_fixture import make_problem,synthetic_review
from cfm_id.iv_research import submit
from cfm_id.iv_late_verify import verify_late_result
from cfm_id.iv_ate_verify import verify_ate_result
from cfm_id.iv_research_adapter import BinaryIVRoute

def law(cells,target):
    d=make_problem().model_dump()
    d.update(target=target,cells=[dict(z=i//4,d=i%4//2,y=i%2,probability=x) for i,x in enumerate(cells)])
    return IVProblem.model_validate(d)

def execute(p):
    return submit(p,review=synthetic_review(p),research_protocol_selected=True)

def test_exact_iv_conflict_and_unresolved_width_with_replay():
    p=law([".4",".2",".2",".2",".199999999",".200000001",".3",".3"],"LATE")
    bad=execute(p)
    assert bad["state"]=="INCOMPATIBLE" and bad["certificate_replayed"]
    assert verify_late_result(p.observed(),bad["certificate"])["valid"]
    p=law(["1","0","0","0","1e-20","0","0.99999999999999999999","0"],"ATE")
    out=execute(p);cert=out["certificate"]
    assert out["state"]=="PARTIAL" and cert["exact"]["bounds"]==["0","1/100000000000000000000"]
    assert BinaryIVRoute().claim(cert)["kind"]=="PARTIAL"
    false=deepcopy(cert);false["bounds"]=[0.,0.];false.pop("exact")
    assert not verify_ate_result(p.observed(),false,monotonicity=True)["valid"]
    false=deepcopy(cert);false["exact"]["bounds"][1]="0"
    assert not verify_ate_result(p.observed(),false,monotonicity=True)["valid"]

def test_exact_iv_handles_zero_and_endpoints_with_same_float():
    p=law(["1","0","0","0","0","0","1","0"],"ATE")
    assert execute(p)["state"]=="POINT"
    p=law(["1","0","0","0","1e-20","0","0","0.99999999999999999999"],"ATE")
    r=execute(p);assert r["state"]=="PARTIAL" and r["certificate"]["bounds"]==[1.,1.]
    assert BinaryIVRoute().claim(r["certificate"])["kind"]=="PARTIAL"
    with pytest.raises(ValueError):law(["1","0","0","0","1","0","1e-20","0"],"ATE")

def fixture():
    note="Alpha and Beta are the complete fixed network. Both binary outcomes are measured on day one. Independent fair draws, consistency, and mean sufficiency for every arrangement are adopted. Both target means are known in the population."
    case=dict(business_question="What if both devices are enabled?",sources=[dict(source_id="memo",text=note)])
    raw=dict(target=dict(kind="policy_mean",population="Both registered devices",outcome="alarm",treatment="enabled",context="day one",comparison="both enabled",quote=case["business_question"]),
        network=dict(nodes=["Alpha","Beta"],edges=[["Alpha","Beta"]],design="independent",probabilities={"Alpha":"1/2","Beta":"1/2"},
        outcome_kind="binary",exposure="any",weights=["1/2","1/2"],policy=[1,1],full=[dict(z=[1,1],means=["1/2","3/4"])],
        local=[dict(own=1,peer=1,means=["1/2","3/4"])],quote="Both target means are known in the population."),
        assumptions={k:note for k in ("consistency","randomization","fixed_network","mean_sufficiency")})
    return case,raw

def review(p):
    needed={"target_and_source_reading",*(k for m in p["methods"] if not m["missing"] for k in (*m["conditions"],*m["review_items"]))}
    return dict(binding=p["binding"],reviewer="Synthetic test",evidence="Independently checked both test devices, coordinates, and assumptions.",
                authority="SYNTHETIC_TEST",decisions=dict.fromkeys(needed,"ACCEPTED"))

def test_one_spec_two_methods_and_handoff():
    case,raw=fixture();assert inspect(raw,case)=={}
    p=plan(case,raw);r=review(p);result=complete(p,r,authority="SYNTHETIC_TEST")
    assert [a["method"] for a in result["method_results"] if a["state"]=="POINT"]==["FULL_ASSIGNMENT_POLICY_MEAN","EXPOSURE_SUFFICIENT_POLICY_MEAN"]
    assert result["mathematical_claim"]["value"]=="5/8" and result["estimate_handoff"]["mode"]=="ESTIMATE_POINT"
    assert "mean_sufficiency" not in result["estimate_handoff"]["assumptions"]
    assert "mean_sufficiency" in result["method_results"][1]["assumptions"]
    assert result["estimate_handoff"]["design"]["node_order"]==["Alpha","Beta"]
    assert result["independent_replay"] is True and not result["estimation_handoff_allowed"]
    r["decisions"]["mean_sufficiency"]="PENDING"
    fallback=complete(p,r,authority="SYNTHETIC_TEST")
    assert fallback["state"]=="POINT" and {m["method"] for m in fallback["method_results"] if m["state"]=="POINT"}=={"FULL_ASSIGNMENT_POLICY_MEAN"}
    r["decisions"]["target_and_source_reading"]="PENDING"
    assert not complete(p,r,authority="SYNTHETIC_TEST")["backend_called"]
    p["spec"]["network"]["policy"]=[0,0]
    with pytest.raises(ValueError):complete(p,r,authority="SYNTHETIC_TEST")

def test_local_and_unknown_assumption_source():
    case,raw=fixture();n=raw["network"]
    raw["target"]["kind"]="local_difference";n.update(policy=[],arms=[[1,1],[0,1]],local=n["local"]+[dict(own=0,peer=1,means=["0","1/4"])])
    del raw["assumptions"]["mean_sufficiency"]
    p=plan(case,raw);out=complete(p,review(p),authority="SYNTHETIC_TEST")
    assert out["state"]=="POINT" and out["mathematical_claim"]["value"]=="1/2"
    raw["assumptions"]["randomization"]="never contained in this study"
    assert not plan(case,raw)["backend_called"]


def test_focus_scopes_corrections_and_requires_explicit_extra_removal():
    from cfm_id_llm.compact_study import apply_focus,focus
    case,good=fixture()
    raw={**good,"time":"day one"}
    issues=inspect(raw,case)
    assert "time" in issues and focus(case,raw,issues) is not None
    repair=dict(target=good["target"],gaps=[],restrictions=[],remove_extras=["time"])
    fixed=apply_focus(raw,repair,issues)
    assert not inspect(fixed,case) and fixed["network"]==good["network"]
    assert apply_focus(raw,{**repair,"remove_extras":[]},issues)==raw
    assert apply_focus(raw,{**repair,"assumptions":{}},issues)==raw


def test_native_review_for_iv_requires_the_entire_conditional_table():
    q="What is the effect among invitation compliers?"
    note="This is an invitation trial using binary Z,D,Y in the whole city this year. Both Z values occur. Independence, exclusion, monotonicity, consistency and no interference are accepted."
    case=dict(business_question=q,sources=[dict(source_id="memo",text=note)])
    case["sources"].append(dict(source_id="law",text="For (D,Y)=00,01,10,11 the population rows are .36,.29,.16,.19 and .16,.09,.25,.50."))
    reading=dict(target=dict(kind="late",population="city residents",outcome="Y",treatment="D",context="this year",comparison="D=1 minus D=0 for compliers",quote=q),
        assumptions={k:note for k in ("iv_independence","exclusion","monotonicity","consistency","no_interference","instrument_support")},
        iv=dict(z="Z",d="D",y="Y",binary=True,cells=[[".36",".29",".16",".19"],[".16",".09",".25",".50"]],quote=note))
    prepared=plan(case,reading);receipt=review(prepared)
    receipt["decisions"]["review_complete_observed_conditional_law"]="PENDING"
    assert not complete(prepared,receipt,authority="SYNTHETIC_TEST")["backend_called"]
    receipt["decisions"]["review_complete_observed_conditional_law"]="ACCEPTED"
    result=complete(prepared,receipt,authority="SYNTHETIC_TEST")
    assert result["state"]=="POINT" and result["mathematical_claim"]["value"]=="11/40"
    case["business_question"]="What is the effect among all city residents?"
    case["sources"][1]["text"]="For (D,Y)=00,01,10,11 the population rows are 1,0,0,0 and 0,0,1,0."
    reading["target"].update(kind="ate",comparison="D=1 minus D=0 for all city residents",quote=case["business_question"])
    reading["iv"]["cells"]=[["1","0","0","0"],["0","0","1","0"]]
    prepared=plan(case,reading)
    result=complete(prepared,review(prepared),authority="SYNTHETIC_TEST")
    assert result["estimate_handoff"]["mode"]=="ESTIMATE_POINT" and result["mathematical_claim"]["value"]=="0"


def test_external_local_effect_preserves_existing_design_and_source_scope():
    case,raw=fixture()
    raw["target"]["kind"]="local_difference"
    raw["network"].update(arms=[[1,1],[0,1]],policy=[],design="fixed_quota",quota=1)
    p=plan(case,raw);r=review(p);r["authority"]="EXTERNAL_RESEARCH_REVIEW"
    result=complete(p,r,authority=r["authority"])
    assert result["reason_code"]=="EXTERNAL_EFFECT_DESIGN_NOT_CONNECTED" and not result["backend_called"]


def test_design_probability_disagreement_requests_a_focused_read():
    case,raw=fixture()
    raw["network"].update(design="fixed_quota",quota=1,probabilities={"Alpha":"1/3","Beta":"1/3"})
    assert set(inspect(raw,case))=={"network"}


def test_delivery_rebuild_rejects_a_changed_estimation_contract():
    from cfm_id.compact_entry import replay_delivery
    case,raw=fixture()
    p=plan(case,raw);r=review(p);out=complete(p,r,authority="SYNTHETIC_TEST")
    assert replay_delivery(p,r,out,authority="SYNTHETIC_TEST")
    out["estimate_handoff"]["mode"]="ESTIMATE_BOUNDS"
    assert not replay_delivery(p,r,out,authority="SYNTHETIC_TEST")
