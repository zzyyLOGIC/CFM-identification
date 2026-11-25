"""Reviewed natural-language bridge to the unchanged plain ATE/Manski backends.

Source audit, scientific adoption and mathematical replay are separate records.
Base formulas/bounds come only from native methods, never the model answer.
An explicitly reviewed reverse target adds a recorded negation of that result.
"""
from copy import deepcopy
from fractions import Fraction
import math

from cfm_id_llm import population_ate_reading as reading
from cfm_id_llm.compact_study import digest

VERSION = "population-ate-entry/1"
LABELS = {
    "consistency":"实际结果对应本人实际接受的处理（Consistency）",
    "no_interference":"其他对象是否接受处理，不影响本人的结果（No interference）",
    "finite_conditional_first_moments":"本题涉及的平均结果存在且有限（Finite means）",
    "random_assignment":"实际处理由所述随机安排决定（Randomization）",
}


def eligible(report, network=None):
    if network is not None or report.get("proof") or report.get("condition_review"):
        return False
    from .direct_verification import answer_items
    draft=report.get("draft")
    if isinstance(draft,dict) and isinstance(draft.get("answers"),list) and len(draft["answers"])!=1:
        return False
    answers=answer_items(draft)
    if len(answers)!=1 or not isinstance(answers[0],dict):return False
    answer=answers[0]
    # Only proposes source reading, never certifies the draft. Preserve the
    # original answer; misplaced target fields cannot become scientific facts.
    target=answer.get("target")
    if isinstance(target,dict):return target.get("quantity")=="difference"
    return "target" not in answer and answer.get("quantity")=="difference"


def _base(report, case, candidate=None, audit=None):
    result=deepcopy(report)
    for key in ("proof","conditional_answer","condition_review","review_record","clarification_questions"):
        result.pop(key,None)
    result.update(proof=None,conditional_answer=None,decision="WITHHELD",effective_answer=None,
        scientific_approval=False,estimation_handoff_allowed=False,production_admission=False,
        clarification_questions=[],backend_called=False,independent_replay=False)
    result["population_ate"]=dict(version=VERSION,case_sha256=digest(case),reading=candidate,audit=audit)
    return result


def _stop(report, state, reason, message, questions=()):
    report["population_ate"].update(state=state,reason_code=reason,message=message)
    report["clarification_questions"]=list(dict.fromkeys(questions))
    report["checks"].append(dict(code=reason,state="UNCHECKED",detail=message))
    return report


def prepare(case, report, call):
    """At most one recorded reread; never ask a user to repair a model error."""
    feedback=None
    for attempt in range(2):
        suffix="" if attempt==0 else "_reread"
        raw=call(reading.request(case,feedback),"population_ate_read"+suffix)
        try:
            candidate=reading.inspect(case,raw)
            audit=reading.check_audit(case,candidate,
                call(reading.audit_request(case,candidate),"population_ate_audit"+suffix))
        except (ValueError,TypeError,KeyError) as exc:
            feedback=dict(problem="读取或核对未符合合同",detail=str(exc)[:1200],previous_candidate=raw)
            continue
        findings=audit["findings"]
        errors=[f for f in findings if f["verdict"]=="READING_ERROR"]
        if errors:
            feedback=dict(findings=errors,previous_candidate=candidate)
            continue
        if candidate["family"]["value"]=="OTHER":
            return None
        result=_base(report,case,candidate,audit)
        questions=[f["question"] for f in findings if f["verdict"]=="NEEDS_CLARIFICATION"]
        if questions:
            return _stop(result,"NEEDS_INPUT","POPULATION_ATE_SOURCE_AMBIGUOUS",
                         "原材料中有需要确认的含义。",questions)
        return plan(case,result)
    result=_base(report,case)
    result["population_ate"]["reading_feedback"]=feedback
    return _stop(result,"READING_RECHECK_REQUIRED","POPULATION_ATE_SOURCE_REVIEW_FAILED",
        "系统对这份材料的读取仍未通过复核，没有进入数学计算。请保留原材料，无需为模型错误添加条件。")


def _source_text(claim):
    return "；".join(e["quote"] for e in claim["evidence"])


def _domain(value):
    from pfn_pipeline._internal.identification.schemas import VariableDomain
    raw={k:v for k,v in value.items() if v is not None}
    # The legacy name denotes a real-valued domain, not a density assumption.
    if raw["kind"]=="numeric":raw["kind"]="continuous"
    return VariableDomain.model_validate(raw)


def _bounded(domain):
    if domain.kind in ("binary","categorical"):
        return bool(domain.values) and all(type(v) in (int,float) and math.isfinite(v) for v in domain.values)
    return (domain.lower is not None and domain.upper is not None
            and math.isfinite(domain.lower) and math.isfinite(domain.upper)
            and domain.lower<=domain.upper)


def plan(case, report):
    record=report["population_ate"];s=record["reading"]
    t=s["target"]["value"];d=s["design"]["value"];info=s["information"]["value"]
    questions=[]
    if s["family"]["value"]!="PLAIN_ATE":questions.append("你希望比较哪些对象的哪两种情况，以及哪个时期的什么结果？")
    if any(not t[k].strip() for k in ("population","treatment_1","treatment_0","outcome","period")):
        questions.append("请说明评价哪些对象、比较哪两种处理、关注什么结果，以及结果对应的时期。")
    if t["direction"]=="UNKNOWN":questions.append("这次希望用哪一种情况减去哪一种情况？请同时说明原来的0/1编码。")
    elif t["direction"] not in ("1-0","0-1") or t["conditional"] is True:
        return _stop(report,"NOT_COVERED","POPULATION_ATE_TARGET_NOT_SUPPORTED",
                     "这份目标含其他运算或条件分层，尚未接到普通ATE入口；目标已保留，没有改写。")
    if t["conditional"] is None:questions.append("这次是对所述整个人群比较平均结果，还是只看某一特征条件下的人群？")
    if s["outcome_domain"]["value"]["kind"]=="unknown":
        questions.append("结果是0/1、评分、收入还是其他类型？如果有规定的取值范围，请说明。")
        domain=None
    else:
        try:domain=_domain(s["outcome_domain"]["value"])
        except (ValueError,TypeError):
            return _stop(report,"READING_RECHECK_REQUIRED","POPULATION_ATE_DOMAIN_INVALID","结果取值域的读取不完整或相互矛盾，尚未计算。")
    if d["kind"]=="UNKNOWN":questions.append("实际由谁决定是否接受处理，是怎样安排的？")
    if d["kind"]=="RANDOMIZED":
        if d["probability"] is None:questions.append("所述人群中，每个对象实际接受处理的概率是多少？如果概率不同，也请说明。")
        else:
            try:
                p=Fraction(d["probability"])
                if not 0<=p<=1:raise ValueError()
            except (ValueError,ZeroDivisionError):
                return _stop(report,"READING_RECHECK_REQUIRED","POPULATION_ATE_PROBABILITY_INVALID","读取的处理概率无法核对，没有进入计算。")
    if info["kind"]!="POPULATION_JOINT" or info["matches_target"] is not True:
        questions.append("目前有哪些关于该人群、该时期的处理和结果资料？请区分联合总体分布与一批样本记录，并说明是否适用于这次问题。")
    conditions=s["conditions"]
    required={"consistency","no_interference"}
    if domain is not None and not _bounded(domain):required.add("finite_conditional_first_moments")
    for c in conditions:
        needed=c["code"] in required or c["code"]=="extra"
        if c["status"]=="CONTRADICTED":
            return _stop(report,"CONFLICT","POPULATION_ATE_CONDITION_CONFLICT","材料中有明确否定或相互冲突的科学条件："+c["statement"])
        if c["status"] in ("UNKNOWN","UNDECIDED") and needed:
            if c["code"]=="finite_conditional_first_moments":
                questions.append("本研究是否采用“两种处理下的平均结果都存在且有限”这一条件？可以回答采用、不采用或仍未决定。")
            elif c["code"]=="consistency":
                questions.append("本研究是否采用“实际看到的结果，就是本人实际处理安排下的结果”这一条件？")
            elif c["code"]=="no_interference":
                questions.append("本研究是否采用“其他对象是否接受处理，不影响本人的结果”这一条件？")
            else:
                questions.append("对于“"+c["statement"]+"”，本次是采用、不采用，还是仍未决定？")
        elif c["status"]=="NOT_ADOPTED" and c["code"] in required:
            return _stop(report,"NOT_COVERED","POPULATION_ATE_REQUIRED_CONDITION_DECLINED",
                         "当前方法所需条件已明确不采用，不能默认补上："+LABELS[c["code"]])
    if questions:
        return _stop(report,"NEEDS_INPUT","POPULATION_ATE_INPUT_REQUIRED","请补充或确认下列研究信息；未决定的内容会继续保留。",questions)
    if s["other_information"]:
        return _stop(report,"NOT_COVERED","POPULATION_ATE_ADDITIONAL_INFORMATION",
            "这份研究还包括普通ATE入口尚不能核验的资料或结构，已保留："+"；".join(x["value"] for x in s["other_information"]))
    if d["kind"]=="OBSERVATIONAL" and domain.kind!="binary":
        return _stop(report,"NOT_COVERED","POPULATION_ATE_NONBINARY_OBSERVATIONAL",
                     "当前Manski入口处理0/1结果，不能把这个结果改成二元变量。")
    if t["output"]!="FORMULA":
        return _stop(report,"NOT_COVERED","POPULATION_ATE_NUMERIC_REQUEST",
                     "本入口提供总体识别公式；数值代入尚未接通，原数值需求已保留。")
    first,second=(t['treatment_0'],t['treatment_1']) if t['direction']=='0-1' else (t['treatment_1'],t['treatment_0'])
    items=[dict(code="target",label="确认本次问题和比较方向",quote=
        f"{t['population']}：{t['period']}的{t['outcome']}；{first} 减去 {second}。")]
    if d["kind"]=="RANDOMIZED":
        items.append(dict(code="random_assignment",label=LABELS["random_assignment"],quote=_source_text(s["design"])))
    for i,c in enumerate(conditions):
        if c["status"]=="ADOPTED":
            items.append(dict(code=f"condition_{i}",label=LABELS.get(c["code"],"原文额外采用的条件"),quote=c["statement"]))
    sheet=dict(kind="population_ate",items=items,case_sha256=digest(case),
               reading_binding=reading.binding(case,s),draft_sha256=report["draft_sha256"])
    sheet["binding"]=digest([sheet.copy(),record["audit"]])
    report["condition_review"]=sheet
    record.update(state="REVIEW_REQUIRED",reason_code="POPULATION_ATE_SCIENCE_CONFIRMATION",
                  message="已核对目标和原文。请确认本次问题及材料中采用的条件，然后由数学库计算。")
    return report


def check_review(sheet, review):
    if (not isinstance(review,dict) or set(review)!={"binding","authority","decisions"}
            or review["binding"]!=sheet["binding"]
            or review["authority"] not in ("SYNTHETIC_TEST","EXTERNAL_RESEARCH_REVIEW")
            or not isinstance(review["decisions"],dict)
            or set(review["decisions"])!={i["code"] for i in sheet["items"]}
            or any(v not in ("ADOPTED","UNSURE","DECLINED") for v in review["decisions"].values())):
        raise ValueError("POPULATION_ATE_REVIEW_REQUIRED_OR_STALE")


def compile_spec(s, authority):
    from pfn_pipeline._internal.identification.schemas import IdentificationSpec
    t=s["target"]["value"];d=s["design"]["value"]
    assumptions=[]
    for i,c in enumerate(s["conditions"]):
        name=c["code"] if c["code"]!="extra" else f"extra_condition_{i}"
        status={"ADOPTED":"ADMITTED","NOT_ADOPTED":"NOT_ADMITTED","UNDECIDED":"UNRESOLVED","UNKNOWN":"UNRESOLVED"}[c["status"]]
        assumptions.append(dict(name=name,source="human_confirmation" if status=="ADMITTED" else "study_protocol",
            status=status,evidence=[f"{e['source_id']}: {e['quote']}" for e in c["evidence"]],details=c["statement"]))
    support={"analysis_unit":t["population"]}
    if d["kind"]=="RANDOMIZED":
        p=float(Fraction(d["probability"]));support["assignment_probability"]=p
        assumptions.append(dict(name="random_assignment",source="human_confirmation",status="ADMITTED",evidence=[_source_text(s["design"])]))
        if 0<p<1:assumptions.append(dict(name="positivity",source="deterministic_derivation",status="DERIVED",evidence=["0 < 已核对的处理概率 < 1"]))
    return IdentificationSpec.model_validate(dict(
        structure=dict(representation_type="design_based_potential_outcomes",variables=["T","Y"],source="human_specified"),
        variable_domains={"T":{"kind":"binary"},"Y":_domain(s["outcome_domain"]["value"]).model_dump(mode="json")},
        # The checked joint law defines this native problem's ambient population.
        # No subset/transport mapping is performed: plan requires an unconditional
        # target and an audited joint law for exactly that population and period.
        query=dict(type="ATE",treatment="T",outcome="Y",target_population="overall_population",
            authority="TRUSTED_FIXTURE" if authority=="SYNTHETIC_TEST" else "HUMAN_CONFIRMED",
            interpretation_notes=f"本规格完整总体：{t['population']}；时期：{t['period']}；Y：{t['outcome']}；T=1：{t['treatment_1']}；T=0：{t['treatment_0']}"+
                ("；本原生规格计算1-0作为中间目标；用户的0-1目标由核验后的取负操作交付，处理编码不变" if t['direction']=='0-1' else ""),
            evidence=[_source_text(s["target"])]),assumptions=assumptions,support_domain=support,
        information_signature=dict(objects=[dict(name="P(T,Y)",regime="experimental" if d["kind"]=="RANDOMIZED" else "observational",
            variables=["T","Y"],description=_source_text(s["information"]))])))


def complete(case, report, review):
    """Revalidate the current source/audit/review bindings before any native call."""
    record=report["population_ate"]
    if record["case_sha256"]!=digest(case):raise ValueError("POPULATION_ATE_CASE_CHANGED")
    s=reading.inspect(case,record["reading"])
    audit=reading.check_audit(case,s,record["audit"])
    if any(f["verdict"]!="MATCH" for f in audit["findings"]):raise ValueError("POPULATION_ATE_AUDIT_NOT_ACCEPTED")
    rebuilt=plan(case,_base(report,case,s,audit))
    if not rebuilt.get("condition_review"):raise ValueError("POPULATION_ATE_NOT_READY")
    if rebuilt["condition_review"]!=report["condition_review"]:raise ValueError("POPULATION_ATE_REVIEW_SHEET_CHANGED")
    check_review(rebuilt["condition_review"],review)
    rebuilt["review_record"]=deepcopy(review)
    if any(v!="ADOPTED" for v in review["decisions"].values()):
        return _stop(rebuilt,"REVIEW_REQUIRED","POPULATION_ATE_PREMISES_NOT_ADOPTED",
                     "已保存本次判断。目标或所需前提尚未全部确认，没有执行计算。")
    rebuilt["population_ate"]["completed"]=True
    spec=compile_spec(s,review["authority"])
    rebuilt["population_ate"]["native_spec"]=spec.model_dump(mode="json")
    if s["design"]["value"]["kind"]=="RANDOMIZED" and any(c["code"]=="extra" and c["status"]=="ADOPTED" for c in s["conditions"]):
        return _stop(rebuilt,"NOT_COVERED","POPULATION_ATE_EXTRA_RANDOMIZED_RESTRICTION",
                     "原文额外采用的限制已保留。当前普通随机ATE入口不能核验它们与全部信息的相容性，因此尚未生成结论。")
    from pfn_pipeline._internal.identification.identification import IdentificationEngine
    from pfn_pipeline._internal.identification.verifier import IdentificationVerifier
    verifier=IdentificationVerifier()
    result=IdentificationEngine().solve_verified(spec,verifier)
    rebuilt["backend_called"]=True
    rebuilt["population_ate"]["native_result"]=result.model_dump(mode="json")
    if result.verification_status!="VERIFIED":
        return _stop(rebuilt,"NOT_COVERED",result.reason_code or "POPULATION_ATE_NATIVE_UNSUPPORTED",
            "已有数学方法不能在保留本次全部条件的同时给出认证结论。额外限制没有被删除；这不表示已证明不可识别。")
    replayed=verifier.verify(spec,result)
    if replayed.verification_status!="VERIFIED":raise ValueError("POPULATION_ATE_REPLAY_FAILED")
    program=result.identified_functional or result.bound_program
    formula=program.to_text() if program is not None else str(result.identified_set)
    t=s["target"]["value"]
    operation=None
    if t['direction']=='0-1':
        from .population_ate_orientation import reverse_verified_ate
        formula,operation=reverse_verified_ate(result,t)
    first,second=(t['treatment_0'],t['treatment_1']) if operation else (t['treatment_1'],t['treatment_0'])
    target=dict(quantity="difference",scope="whole",population=t["population"],intervention=first,
                reference=second,outcome=t["outcome"],time=t["period"])
    answer=dict(target=target,status=result.status.value,functional=formula,value=None,
        assumptions=[dict(statement=c["statement"],quote=_source_text(c)) for c in s["conditions"] if c["status"]=="ADOPTED"],
        estimate_handoff=dict(mode="STOP",reason="本接口交付识别公式与证书；不自动下发估计查询。"),
        reason="公式来自既有数学规则，已独立重放；结论以本次确认的条件为前提。")
    proof=dict(method="LEGACY_POPULATION_ATE",binder=VERSION,reading_binding=reading.binding(case,s),
        case_sha256=digest(case),review_binding=review["binding"],independent_replay=True,
        native_result=result.model_dump(mode="json"),spec_sha256=digest(spec.model_dump(mode="json")))
    if operation:
        proof["target_operation"]=operation
        answer["reason"]="原方向的公式或界限由数学库核验，再按本题比较方向取负；证书与方向转换可重放，原来的0/1编码不变。"
    rebuilt.update(decision="CONDITIONAL_RESULT",effective_answer=answer,conditional_answer=deepcopy(answer),proof=proof,
        independent_replay=True,scientific_approval=review["authority"]=="EXTERNAL_RESEARCH_REVIEW")
    rebuilt["population_ate"].update(state=result.status.value,reason_code=None,message=answer["reason"])
    return rebuilt


def replay(case, draft, report):
    """Rebuild the bound adapter report and rerun the existing native verifier.

    This checks saved audit/approval bindings, not the real-world truth of a
    scientific premise or the semantic correctness of an LLM's source review.
    """
    from .direct_verification import verify
    if not isinstance(case,dict):case=case.model_dump(mode="json")
    record=report["population_ate"]
    if record["version"]!=VERSION or record["case_sha256"]!=digest(case):
        return False
    base=verify(case,draft,version=report["version"])
    if not eligible(base) or report["draft_sha256"]!=digest(draft):return False
    s=reading.inspect(case,record["reading"])
    audit=reading.check_audit(case,s,record["audit"])
    if any(f["verdict"]!="MATCH" for f in audit["findings"]):return False
    rebuilt=plan(case,_base(base,case,s,audit))
    if report.get("review_record"):
        rebuilt=complete(case,rebuilt,report["review_record"])
    return digest(rebuilt)==digest(report)
