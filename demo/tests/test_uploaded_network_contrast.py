from copy import deepcopy
from fractions import Fraction
from itertools import product
import pytest
from cfm_id.direct_verification import verify,replay
from cfm_id.network_query_exchange import ALIGNED_PACKET,QueryInbox,check_packet
from cfm_id_llm.network_files import load_network


def fixture_case(tmp_path,*,rule="any",reverse=False,isolated=False,fixed=False,subgroup=False):
    nodes=["谷口","江岸","山南","西湾"]
    edges=[(nodes[0],nodes[1]),(nodes[1],nodes[2]),(nodes[2],nodes[0])]
    if not isolated:
        edges.append((nodes[1],nodes[3]))
    n=tmp_path/"stations.csv";e=tmp_path/"ties.csv"
    n.write_text("node_id\n"+"\n".join(nodes),"utf8");e.write_text("source,target\n"+"\n".join(",".join(x) for x in edges),"utf8")
    table=load_network(n,e,dict(kind="UNDIRECTED",description="分配前登记的固定无向联系",completeness="COMPLETE"))
    rule_word={"any":"至少一位邻居开放","majority":"邻居中严格过半开放","count":"邻居中恰好2个开放"}[rule]
    a,b=(0,1) if reverse else (1,0)
    e1=2 if rule=="count" else 1
    sides=["本站未开放","本站开放"]
    part=f"当{rule_word}时，{sides[a]}相比{sides[b]}，本周到站量平均相差多少"
    scope="仅评价【谷口】" if subgroup else "全部4个站点等权"
    q=f"{scope}。其余站点按原分配设计在两端取平均。{part}？"
    items={
      "graph":"分配前登记的固定无向联系，关系表完整。",
      "exp":{"any":"至少一位邻居开放记1，没有人开放记0。","majority":"邻居严格过半开放记1，其余包括平票记0。","count":"暴露是开放邻居的精确人数。"}[rule],
      "law":"在完整名单中等概率无放回抽取2个站点。分配变量为开放。" if fixed else "各站独立抽签，各有1/3概率开放，按签执行。",
      "pop":"原题指定的评价对象等权，名单在抽签前确定。",
      "info":"可查询逐站在原题两个事件下的条件均值。",
      "science":"试点拟采用这些前提。完整名单独立于全部潜在结果。观测结果对应实际完整安排。各端条件均值有限。",
      "outcome":"结果为到站量。时期为本周。"}
    case=dict(case_id="synthetic-station",business_question=q,sources=[
        dict(source_id=k,kind="OTHER",text=v,label=k) for k,v in items.items()]+[table.source()])
    def cell(value,sid,quote):
        return dict(value=value,evidence=[dict(source_id=sid,quote=quote)])
    law=dict(kind="fixed",quota=2) if fixed else dict(kind="independent",probabilities={"各站":"1/3"})
    facts=dict(network=cell(dict(pre_treatment=True,complete=True,undirected=True,nodes=4,edges=len(edges)),"graph",items["graph"]),
               exposure=cell(dict(kind=rule),"exp",items["exp"]),assignment=cell(law,"law",items["law"]),
               contrast=cell(dict(population=["谷口"] if subgroup else nodes,left=[a,e1],right=[b,e1]),"question",part))
    response=dict(status="NOT_COVERED",target=dict(quantity="difference",outcome="到站量",time="本周"),
                  estimate_handoff=dict(mode="STOP"),question_part=part)
    return case,dict(network_facts=facts,answers=[response]),table


def decisions(r,value="ADOPTED"):
    sheet=r["condition_review"]
    return dict(binding=sheet["binding"],authority="SYNTHETIC_TEST",decisions={p["code"]:value for p in sheet["items"]})


@pytest.mark.parametrize("rule,reverse,fixed,subgroup",[("any",False,False,False),("majority",True,False,False),
                  ("count",False,False,True),("any",True,True,True)])
def test_novel_uploaded_events_are_matched_to_enumerated_allocations(tmp_path,rule,reverse,fixed,subgroup):
    c,d,t=fixture_case(tmp_path,rule=rule,reverse=reverse,fixed=fixed,subgroup=subgroup)
    r=verify(c,d,network=t,network_focus=True)
    assert r["decision"]=="PREMISES_REQUIRED",r["clarification_questions"]
    assert r["effective_answer"]["estimate_handoff"]["queries"]==[] and len(r["condition_review"]["items"])==3
    assert replay(c,d,r)
    adopted=verify(c,d,network=t,network_focus=True,science_review=decisions(r))
    assert adopted["estimation_handoff_allowed"] and not adopted["scientific_approval"] and replay(c,d,adopted)
    h=adopted["effective_answer"]["estimate_handoff"];pop=["谷口"] if subgroup else list(t.nodes)
    assert h["population"]==pop
    assert list(map(Fraction,h["operator_spec"]["forms"][0]))==[Fraction(k,len(pop)) for _ in pop for k in (1,-1)]
    for u in pop:
        peers=[j for j,n in enumerate(t.nodes) if any({u,n}==set(edge) for edge in t.edges)]
        totals={k:Fraction() for k in h["support"][u]}
        for z in product((0,1),repeat=len(t.nodes)):
            if fixed and sum(z)!=2:continue
            mass=Fraction(1,6) if fixed else Fraction(1,3)**sum(z)*Fraction(2,3)**(len(z)-sum(z))
            k=sum(z[j] for j in peers)
            g=int(k>0) if rule=="any" else int(2*k>len(peers)) if rule=="majority" else k
            key=f"{z[list(t.nodes).index(u)]},{g}"
            if key in totals:totals[key]+=mass
        assert totals=={k:Fraction(p) for k,p in h["support"][u].items()}
    arm=2 if rule=="count" else 1
    assert [q["own"] for q in h["queries"]]==([0,1] if reverse else [1,0])*len(pop)
    assert all(q["exposure"]==arm for q in h["queries"])


def test_isolated_node_preserves_original_population(tmp_path):
    c,d,t=fixture_case(tmp_path,isolated=True)
    r=verify(c,d,network=t,network_focus=True)
    assert r["effective_answer"]["status"]=="UNDEFINED" and "condition_review" not in r
    assert r["proof"]["population"]==list(t.nodes) and r["proof"]["joint_probabilities"]["西湾"]=={"1,1":"0","0,1":"0"}


@pytest.mark.parametrize("issue",["swapped_ends","false_citation","wrong_graph","uncertain_science","mean_not_available","invitation","conflicting_rates","inclusive_tie","partial_graph","late_graph"])
def test_real_disagreements_are_not_released(tmp_path,issue):
    c,d,t=fixture_case(tmp_path,rule="majority")
    facts=d["network_facts"]
    if issue=="swapped_ends":facts["contrast"]["value"].update(left=[0,1],right=[1,1])
    elif issue=="false_citation":facts["contrast"]["evidence"][0]["quote"]="未出现在材料中"
    elif issue=="wrong_graph":facts["network"]["value"]["edges"]=1
    elif issue in ("partial_graph","late_graph"):
        from dataclasses import replace
        t=replace(t,**({"completeness":"INCOMPLETE"} if issue=="partial_graph" else {"description":"试点后登记的关系"}))
        c["sources"][-1]=t.source()
    elif issue=="mean_not_available":
        next(s for s in c["sources"] if s["source_id"]=="info")["text"]="只有全体均值，没有任何逐站查询。"
    else:
        text={"uncertain_science":"研究者不采用完整名单独立于全部潜在结果这一项。",
              "invitation":"抽签决定的只是邀请。用户可拒绝，是否开放自行决定。",
              "conflicting_rates":"另一份本轮分配记录称各站独立抽签，各有1/4概率开放。",
              "inclusive_tie":"另份说明称邻居一半或以上时已达标，平票记1。"}[issue]
        c["sources"].append(dict(source_id="note",label="补充",kind="OTHER",text=text))
    d["answers"][0].update(status="POINT",estimate_handoff=dict(mode="ESTIMATE_POINT"))
    old=verify(c,d,version="direct-verification/14",network=t,network_focus=True)
    assert old["decision"]=="WITHHELD" and old["clarification_questions"] and replay(c,d,old)
    r=verify(c,d,network=t,network_focus=True)
    if issue == "false_citation":
        # A redundant model citation is unnecessary when all four coordinates
        # can be obtained independently from the actual files.
        assert r["decision"]=="PREMISES_REQUIRED" and not r["clarification_questions"]
        assert r["proof"]["ordered_events"]==["1,1","0,1"] and r["proof"]["network_reference"]==t.token
        assert r["proof"]["binding_source"]=="uploaded-materials/1" and len(r["condition_review"]["items"])==3
        assert r["proof"]["joint_probabilities"]==verify(c,{},network=t)["proof"]["joint_probabilities"]
    else:
        assert r["decision"]=="RETAINED" and r["effective_answer"]==d and "condition_review" not in r
        assert not r["network_alignment"]["matched"]
    assert not r["estimation_handoff_allowed"] and replay(c,d,r)


def test_scope_and_decisions_bound_before_delivery(tmp_path):
    c,d,t=fixture_case(tmp_path);r=verify(c,d,network=t)
    rec=decisions(r)
    for state in ("UNSURE","DECLINED"):
        s=deepcopy(rec);s["decisions"]["consistency"]=state
        pending=verify(c,d,network=t,science_review=s)
        assert not pending["estimation_handoff_allowed"] and pending["effective_answer"]["estimate_handoff"]["mode"]=="STOP"
    changed=deepcopy(c);changed["case_id"]="other"
    with pytest.raises(ValueError,match="STALE_NETWORK"):
        verify(changed,d,network=t,science_review=rec)
    adopted=verify(c,d,network=t,science_review=rec)
    a=adopted["effective_answer"]
    packet=dict(status="POINT",review=rec,condition_review=r["condition_review"],estimation_handoff_allowed=True,
          scientific_approval=False,production_admission=False,release_scope="SYNTHETIC_TEST",source_proof=adopted["proof"],
          network_manifest=adopted["network_manifest"],target=a["target"],estimate_handoff=a["estimate_handoff"])
    packet.update(version=ALIGNED_PACKET,source_case=c,source_draft=d,network_alignment=adopted["network_alignment"],
                  assumptions=a["assumptions"],value=a["value"])
    inbox=QueryInbox(tmp_path/"inbox");one=inbox.receive(c["case_id"],packet)
    assert one==inbox.receive(c["case_id"],packet)
    changed=deepcopy(packet);changed["estimate_handoff"]["queries"][0]["unit"]="west"
    with pytest.raises(ValueError,match="BINDING_MISMATCH"):check_packet(changed)
    changed=deepcopy(packet);changed["network_manifest"]["edges"]=[]
    with pytest.raises(ValueError,match="GRAPH_MISMATCH"):check_packet(changed)
    with pytest.raises(ValueError,match="RUN_MISMATCH"):inbox.receive("other",packet)
    inbox.revoke(c["case_id"])
    import json
    assert json.loads((inbox.root/(c["case_id"]+".json")).read_bytes())["packet"] is None


def test_zero_support_precedes_missing_means_and_unconfirmed_science(tmp_path):
    c,d,t=fixture_case(tmp_path,isolated=True)
    c["sources"]=[s for s in c["sources"] if s["source_id"] not in ("science","info")]
    r=verify(c,d,network=t)
    assert r["effective_answer"]["status"]=="UNDEFINED" and not r["clarification_questions"]
    assert not r["estimation_handoff_allowed"] and not r["effective_answer"]["assumptions"]
    assert "西湾" in r["proof"]["population"]


def test_reference_first_grammar_and_extra_unneeded_assumption(tmp_path):
    c,d,t=fixture_case(tmp_path,rule="majority")
    def reorder(s):
        return s.replace("本站开放相比本站未开放","与本站未开放相比，本站开放")
    c["business_question"]=reorder(c["business_question"])
    d["network_facts"]["contrast"]["evidence"][0]["quote"]=reorder(d["network_facts"]["contrast"]["evidence"][0]["quote"])
    c["sources"].append(dict(source_id="extra",kind="OTHER",label="科学范围",text="研究不采用暴露均值充分性。"))
    r=verify(c,d,network=t)
    assert r["decision"]=="PREMISES_REQUIRED" and r["proof"]["ordered_events"]==["1,1","0,1"]
    assert len(r["condition_review"]["items"])==3


@pytest.mark.parametrize("change",["roster","treatment_object","scope_science"])
def test_changed_scope_variable_or_assumption_does_not_receive_a_release(tmp_path,change):
    c,d,t=fixture_case(tmp_path)
    if change=="roster":
        c["business_question"]=c["business_question"].replace("全部4个站点","全部5个站点")
    elif change=="treatment_object":
        c["business_question"]=c["business_question"].replace("本站开放相比本站未开放","本站开放货运相比本站未开放货运")
        d["network_facts"]["contrast"]["evidence"][0]["quote"]=d["network_facts"]["contrast"]["evidence"][0]["quote"].replace("本站开放相比本站未开放","本站开放货运相比本站未开放货运")
        for cell in [next(s for s in c["sources"] if s["source_id"]=="law"),d["network_facts"]["assignment"]["evidence"][0]]:
            key="text" if "text" in cell else "quote"
            cell[key]=cell[key].replace("概率开放","概率开放客运")
    else:
        s=next(s for s in c["sources"] if s["source_id"]=="science")
        s["text"]=s["text"].replace("完整名单独立于全部潜在结果","仅对部分站点，完整名单独立于全部潜在结果")
    r=verify(c,d,network=t)
    assert r["decision"]=="RETAINED" and r["effective_answer"]==d and not r["network_alignment"]["matched"]
    assert "condition_review" not in r and not r["estimation_handoff_allowed"]


def test_delivery_failure_can_retry_and_withdraw_without_recalling_model(tmp_path):
    from demo.backend.engine import Engine,Run
    c,d,t=fixture_case(tmp_path)
    class RetryInbox(QueryInbox):
        fail_once=True
        def receive(self,run_id,packet):
            ret=super().receive(run_id,packet)
            if self.fail_once:
                self.fail_once=False
                raise ValueError("SIMULATED_INTAKE_FAILURE")
            return ret
    receiver=RetryInbox(tmp_path/"estimates")
    engine=Engine(tmp_path/"runs",max_api_calls=0,estimate_inbox=receiver)
    run=Run(owner="browser",id=c["case_id"],case=c,network=t,synthetic=True,reading_mode="network_direct_verify")
    engine.runs[run.id]=run
    pending=verify(c,d,network=t,network_focus=True)
    engine._finish_direct_verification(run,pending)
    review=decisions(pending)
    with pytest.raises(ValueError,match="SIMULATED_INTAKE_FAILURE"):
        engine._review_network(run,review)
    assert not run.artifacts["identification_handoff"]["estimation_handoff_allowed"]
    engine._review_network(run,review)
    assert run.artifacts["estimate_intake_receipt"]["state"]=="RECEIVED"
    engine._review_network(run,decisions(pending,"DECLINED"))
    assert run.artifacts["estimate_intake_receipt"]["state"]=="SUPERSEDED"
    assert not run.result["estimation_handoff_allowed"] and engine.calls==0
