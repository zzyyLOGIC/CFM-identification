import json
from copy import deepcopy
from cfm_id import project
from cfm_id.direct_verification import verify,replay
from cfm_id_llm.target_evidence import assigned_subjects
from demo.backend.engine import Engine

def case(q, text):
    return {"business_question":q,"sources":[{"source_id":"att_01","text":text}]}
def answer(q="difference",scope="whole"):
    return {"status":"POINT","target":{"quantity":q,"scope":scope},"value":"0.25","functional":"E[Y(1)-Y(0)]",
            "assumptions":[],"estimate_handoff":{"mode":"ESTIMATE_POINT","scope":scope},"reason":"草案"}
def formal():
    q="所有居民在实际 A=1 相对 A=0 下的风险差？"
    d=dict(format="causal-id.binary-iv/1",question=q,population="居民",period="次日",outcome_label="达标",
        roles=dict(instrument="T",treatment="A",outcome="O"),target=dict(type="ATE",treated=1,reference=0),
        information=dict(kind="binary_population_conditional_law",row_variable="T",cell_variables=["A","O"],
                         cell_order=["11","10","01","00"],rows={"1":[".55",".45","0","0"],"0":["0","0",".25",".75"]}),
        assumptions=dict(instrument_independence="T",exclusion="adopted",consistency="adopted",no_interference="adopted",
                         instrument_support="both_positive",monotonicity="nondecreasing",actual_randomization="not_claimed"),
        additional_restrictions=[],complete_for_declared_model=True)
    return q,d
def test_target_mismatch_holds_same_draft_and_advice_never_approves():
    c=case("所有住户的平均水平是多少？","分配详见原文。")
    u=answer();calls=[]
    def once(req,stage):
        calls.append((req,stage));return u
    r=project.direct_then_verify(c,once)
    assert len(calls)==1 and calls[0][1]=="direct_draft" and r["decision"]=="WITHHELD"
    assert r["draft"]==u and r["effective_answer"] is None and r["scientific_approval"] is False
    assert replay(c,u,r)
    r["estimation_handoff_allowed"]=True
    assert not replay(c,u,r)
def test_positions_not_names_and_dual_randomization():
    q="是否可以做差？"
    u=answer();u["assumptions"]=[dict(kind="random_assignment",subject="Z",statement="Z 随机分配",quote="资格 D 随机分配")]
    c=case(q,"资格 D 随机分配。Z 由个人选择。")
    assert verify(c,u)["decision"]=="WITHHELD"
    c=case(q,"资格 D 随机分配。实际 Z 由独立硬币随机分配。")
    u["assumptions"][0]["quote"]="实际 Z 由独立硬币随机分配"
    assert verify(c,u)["decision"]=="RETAINED"
    assert assigned_subjects("R 与所有潜在结果独立")=={"R"}
    assert not assigned_subjects("不假定 Z 随机分配")
def test_conditional_iv_corrects_without_approval_and_replays():
    q,d=formal();c=case(q,json.dumps(d,ensure_ascii=False))
    r=verify(c,answer())
    assert r["decision"]=="CORRECTED" and r["effective_answer"]["value"]=="3/10" and replay(c,answer(),r)
    assert r["proof"]["conditional_on_declared_model"] and not r["estimation_handoff_allowed"]
    r["effective_answer"]["value"]="1";assert not replay(c,answer(),r)
    assert verify(c,answer("difference","subgroup"))["decision"]=="CORRECTED"
def test_source_scope_and_target_direction_are_checked():
    q,d=formal();u=answer()
    d["target"]["treated"],d["target"]["reference"]=0,1
    assert verify(case(q,json.dumps(d,ensure_ascii=False)),u)["decision"]=="WITHHELD"
    q,d=formal(); d["assumptions"]["exclusion"]="pending"
    c=case(q,json.dumps(d,ensure_ascii=False))
    assert verify(c,u)["proof"] is None
    q,d=formal();c=case(q,json.dumps(d,ensure_ascii=False));c["sources"].append({"source_id":"later","text":"还有额外限制"})
    assert verify(c,u)["proof"] is None
def test_unmarked_source_and_symbolic_draft_can_pass_advisory_checks():
    c=case("给出第七天总体概率的符号公式。","联合律已知。")
    u=answer("level");u["value"]=None
    r=verify(c,u)
    assert r["decision"]=="RETAINED" and r["proof"] is None and not r["production_admission"]
def test_default_browser_entry_calls_model_only_once(tmp_path):
    import base64,time
    class Local(Engine):
        def call(self,run,request,stage):
            self.seen.append(stage);return answer("level")
    e=Local(tmp_path);e.seen=[];e.credential("visitor","longcat","temporary-local-test-token")
    run_id=e.start("visitor",dict(question="平均水平是多少？",allow_send=True,files=[dict(name="study.txt",role="document",
        content=base64.b64encode("给定总体均值。".encode()).decode())]))
    for _ in range(200):
        run=e.view("visitor",run_id)
        if not run["busy"]:break
        time.sleep(.025)
    assert run["reading_mode"]=="direct_verify" and run["stage"]=="RESULT" and e.seen==["direct_draft"]
    assert run["result"]["decision"]=="RETAINED" and run["can_estimate"] is False


def test_correct_iv_value_with_wrong_operator_delivers_proved_functional():
    from cfm_id import direct_iv_evidence as iv
    _, declaration = formal()
    question = "依从者中，实际 A=1 相对 A=0 的次日风险差是多少？"
    declaration["question"] = question
    declaration["target"]["type"] = "LATE"
    declaration["information"].update(
        cell_order=["00", "01", "10", "11"],
        rows={"0": [".40", ".20", ".20", ".20"], "1": [".18", ".12", ".40", ".30"]},
    )
    study = case(question, json.dumps(declaration, ensure_ascii=False))
    prepared, _ = iv.read_declaration(study)
    canonical, _ = iv.conditional_answer(*prepared)
    assert canonical["value"] == "1/15"
    draft = deepcopy(canonical)
    draft["functional"] = "E[O|A=1] - E[O|A=0]"
    draft["estimate_handoff"]["operator"] = "比较实际处理组和未处理组的观察风险差"
    draft["reason"] = "按实际处理分组直接相减。"
    previous = verify(study, draft, version="direct-verification/1")
    assert previous["effective_answer"] == draft
    assert replay(study, draft, previous)
    for model_answer in (draft, {"answers": [dict(draft, question_part=question)]}):
        calls = []
        def answer_once(request, stage):
            calls.append(stage)
            return model_answer
        report = project.direct_then_verify(study, answer_once)
        assert calls == ["direct_draft"]
        assert report["decision"] == "CONDITIONAL_RESULT"
        assert report["effective_answer"] == canonical
        assert report["draft"] == model_answer
        assert not any(report[k] for k in ("scientific_approval", "production_admission", "estimation_handoff_allowed"))
        assert replay(study, model_answer, report)
        altered = deepcopy(report)
        altered["effective_answer"]["estimate_handoff"]["operator"] = "观察差"
        assert not replay(study, model_answer, altered)
