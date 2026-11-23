"""Post-answer checks. A retained draft is advisory. Only diagnosed conflicts suppress it."""
from copy import deepcopy
from fractions import Fraction
import re
from . import direct_iv_evidence as iv
from cfm_id_llm.compact_study import digest
from cfm_id_llm.target_evidence import assigned_subjects, explicitly_unrandomized, located_statements, normalized, requested_receipt_as_assignment, target_cues

STATUS={"POINT","PARTIAL","NOT_POINT","INCOMPATIBLE","UNDEFINED","NEEDS_INPUT","NOT_COVERED"}

def field(obj,key):
    return obj.get(key) if isinstance(obj,dict) else None

def action(answer):
    value=field(answer,"estimate_handoff")
    value=field(value,"mode") if isinstance(value,dict) else value
    if not isinstance(value,str):return None
    m=re.match(r"^\s*(?:mode\s*[:=：]\s*)?(ESTIMATE_POINT|ESTIMATE_BOUNDS|STOP)\b",value,re.I)
    return m.group(1).upper() if m else None

def number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float,str)):return None
    s=str(value).strip()
    if len(s)>100 or not re.fullmatch(r"[+-]?(?:\d+/\d+|\d*\.?\d+(?:[Ee][+-]?\d{1,2})?)",s):return None
    try:return Fraction(s)
    except (ValueError,ZeroDivisionError):return None

def values_agree(proposed,expected):
    if expected is None:return proposed is None
    if isinstance(expected,list):
        if not isinstance(proposed,list) or len(proposed)!=len(expected):return False
        if number(expected[0])!=number(expected[-1]) and number(proposed[0])==number(proposed[-1]):return False
        return all(values_agree(p,e) for p,e in zip(proposed,expected))
    p,e=number(proposed),number(expected)
    if p is None:return None if proposed is not None else False
    if p==e:return True
    # Accept a good decimal approximation, without equating zero to a small exact value.
    return bool(p and e and abs(p-e)<=abs(e)/100000)

def role_conflicts(answer,sources,declared):
    conflicts=[];unknown=[]
    items=answer.get("assumptions")
    if not isinstance(items,list):return conflicts,["假设未按条列出，未完成主语检查。"]
    for item in items:
        if not isinstance(item,dict):
            unknown.append("自由文本假设未逐项绑定随机分配的主语。");continue
        statement=normalized(item.get("statement"))
        proposed=assigned_subjects(statement)
        if item.get("kind")!="random_assignment" and not proposed:continue
        subject=normalized(item.get("subject"))
        candidate={subject} if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,15}",subject) else proposed
        if not candidate:unknown.append("随机化主语不能唯一解析。");continue
        if proposed and candidate.isdisjoint(proposed):
            conflicts.append("假设条目所填主语与其陈述的分配对象不一致。")
        if declared:
            r=declared["roles"]
            if r["treatment"] in candidate and declared["assumptions"]["actual_randomization"]=="not_claimed":
                conflicts.append(f"原研究声明支持工具 {r['instrument']} 的独立性，未采纳实际处理 {r['treatment']} 随机。")
            elif candidate!={r["instrument"]}:unknown.append("该假设超出结构化工具声明的主语。")
            continue
        denied=set().union(*(explicitly_unrandomized(s) for s in sources))
        overall=set().union(*(assigned_subjects(s) for s in sources))
        if candidate & (denied-overall):
            conflicts.append("原材料明确说明 "+", ".join(sorted(candidate & (denied-overall)))+" 由研究对象选择或没有随机分配。")
        contexts=located_statements(item.get("quote"),sources)
        found=set().union(*(assigned_subjects(s) for s in contexts))
        if found and candidate.isdisjoint(found):
            conflicts.append("所引原句支持 "+", ".join(sorted(found))+"，答卷将随机分配归给 "+", ".join(sorted(candidate))+"。")
        elif not found:unknown.append("未从所引原句独立确认随机分配的主语。")
    return conflicts,unknown

def verify_one(case,draft,*,question,allow_exact):
    from cfm_id_llm.schemas import BusinessCase
    if isinstance(case,BusinessCase):case=case.model_dump(mode="json")
    original=deepcopy(draft);answer=draft if isinstance(draft,dict) else {}
    if "status" not in answer and isinstance(answer.get("answer"),dict):answer=answer["answer"]
    checks=[]
    def record(code,state,detail):checks.append(dict(code=code,state=state,detail=detail))
    target=answer.get("target");handoff=answer.get("estimate_handoff")
    state=answer.get("status");mode=action(answer)
    if not isinstance(state,str) or state not in STATUS or mode is None:
        record("ANSWER_CONTRACT","CONFLICT","缺少可解释的识别状态或估计动作。")
    elif (state=="POINT" and mode=="ESTIMATE_BOUNDS") or (state!="POINT" and mode=="ESTIMATE_POINT") or (state in {"INCOMPATIBLE","UNDEFINED","NEEDS_INPUT","NOT_COVERED"} and mode=="ESTIMATE_BOUNDS"):
        record("STATUS_ACTION","CONFLICT",f"同一目标自报 {state}，却下发 {mode}。")
    else:record("STATUS_ACTION","CHECKED","已核对同一答案中声明的识别状态和估计动作。")
    cues=target_cues(question);tq=field(target,"quantity");ts=field(target,"scope");hs=field(handoff,"scope")
    if ts in ("whole","compliers","subgroup") and hs in ("whole","compliers","subgroup") and ts!=hs:
        record("HANDOFF_POPULATION","CONFLICT",f"目标总体 {ts} 与估计端总体 {hs} 不一致。")
    if requested_receipt_as_assignment(question,target):
        record("INTERVENTION_SUBJECT","CONFLICT","原题明确比较实际接受处理，所填干预和对照却都描述取得资格或收到邀请。")
    target_seen=False
    for name,claimed in (("quantity",tq),("scope",ts)):
        expected=cues[name]
        if expected is None:continue
        if claimed in ("level","difference","whole","compliers","unknown","subgroup"):
            target_seen=True
            if (name=="quantity" and expected=="unknown" and mode=="STOP"
                    and all(field(target,k) in (None,"","unknown","待定","待确认","未确定") for k in ("intervention","reference"))):
                # The form of a contrast can be known while its two arms still await selection.
                record("UNRESOLVED_INTERVENTION","CHECKED","尚未选定干预，两端均留待确认，估计已暂停。")
                continue
            if claimed!=expected and (claimed!="unknown" or mode=="ESTIMATE_POINT"):
                record("QUESTION_"+name.upper(),"CONFLICT",f"原题的 {name} 为 {expected}，答卷写成 {claimed}。")
    if cues["quantity"]=="level" and tq=="level" and field(target,"reference") not in (None,"","无","不适用","none","N/A"):
        claims_difference=bool(re.search(r"减去(?:对照|基准)|扣除基准|减对照|(?:ATT|ATE)\s*=",normalized(answer.get("functional"))))
        record("LEVEL_WITH_COMPARATOR","CONFLICT" if claims_difference else "UNCHECKED","水平题填写了对照说明，请核对是否参与了相减。")
    record("QUESTION_COVERAGE","CHECKED" if target_seen else "UNCHECKED",
           "只检查原题可独立定位的目标维度。其余语义需要研究者核对。")
    prepared,why=iv.read_declaration(case) if allow_exact else (None,"MULTIPLE_TARGETS_REQUIRE_SEPARATE_MODEL_BINDING")
    declared=prepared[0] if prepared else None
    issues,unknown=role_conflicts(answer,[s["text"] for s in case["sources"]]+[case["business_question"]],declared)
    for message in dict.fromkeys(issues):record("RANDOMIZATION_SUBJECT","CONFLICT",message)
    for message in dict.fromkeys(unknown):record("RANDOMIZATION_SUBJECT","UNCHECKED",message)
    math=None;proof=None
    if prepared:
        d,law=prepared;kind=d["target"]["type"];scope="compliers" if kind=="LATE" else "whole"
        var=re.escape(d["roles"]["treatment"])
        pair=re.search(var+r"\s*=\s*([01])\s*(?:相对(?:于)?|减去)\s*"+var+r"\s*=\s*([01])",normalized(case["business_question"]))
        reversed_source=pair is not None and tuple(map(int,pair.groups()))!=(d["target"]["treated"],d["target"]["reference"])
        if (cues["quantity"] not in (None,"difference") or cues["scope"] not in (None,scope) or reversed_source):
            record("SOURCE_TARGET","CONFLICT","声明与原题的目标口径发生冲突，需核对原材料。")
        else:
            math,proof=iv.conditional_answer(d,law)
            record("EXACT_IV","CHECKED","以研究者给定的完整模型和精确总体表独立求解，并重放可行性或对偶证据。")
            mismatch=state!=math["status"] or mode!=action(math)
            match=values_agree(answer.get("value"),math["value"])
            mismatch=mismatch or match is False or tq in ("level","unknown") or (ts in ("whole","compliers","subgroup") and ts!=scope)
            for k in ("intervention","reference"):
                cell=normalized(field(target,k)).replace(" ","")
                m=re.fullmatch(re.escape(d["roles"]["treatment"])+r"=([01])",cell)
                if m and int(m[1])!=d["target"]["treated" if k=="intervention" else "reference"]:mismatch=True
            if mismatch:record("IV_DRAFT_CONFLICT","CONFLICT","原答的目标、结论、数值或行动与独立计算不一致。")
            elif match is None:record("IV_DRAFT_VALUE","UNCHECKED","未能解析原答的数值写法，数值比较待审。")
    else:record("EXACT_IV","UNCHECKED",why)
    flagged=any(c["state"]=="CONFLICT" for c in checks)
    decision=("CORRECTED" if math else "WITHHELD") if flagged else "RETAINED"
    delivered=math if decision=="CORRECTED" else None if flagged else deepcopy(answer)
    return dict(version="direct-verification/1",decision=decision,checks=checks,
                input_sha256=digest({"question":case["business_question"],"sources":[(s["source_id"],s.get("label",""),s["text"]) for s in case["sources"]]}),
                draft_sha256=digest(original),draft=original,effective_answer=delivered,conditional_answer=math,proof=proof,
                scientific_approval=False,estimation_handoff_allowed=False,production_admission=False)

def _review_draft(case,draft):
    from cfm_id_llm.schemas import BusinessCase
    if isinstance(case,BusinessCase):case=case.model_dump(mode="json")
    question=case["business_question"]
    items=field(draft,"answers")
    if not isinstance(items,list) or not 1<=len(items)<=32:
        return verify_one(case,draft,question=question,allow_exact=True)
    if len(items)==1 and isinstance(items[0],dict) and items[0].get("question_part")==question:
        declared,_=iv.read_declaration(case)
        if declared:
            # A one-item JSON wrapper cannot change a source-bound single estimand.
            item=items[0]
            result=verify_one(case,item,question=question,allow_exact=True)
            result["draft"]=deepcopy(draft)
            result["draft_sha256"]=digest(draft)
            return result
    reports=[]
    for item in items:
        part=field(item,"question_part")
        bound=isinstance(part,str) and len(part.strip())>=3 and part in question
        result=verify_one(case,item,question=part if bound else "",allow_exact=False)
        if not bound:result["checks"].append(dict(code="QUESTION_PART",state="UNCHECKED",detail="未能将该子目标逐字绑定原题。"))
        reports.append(result)
    held=any(r["decision"]=="WITHHELD" for r in reports)
    checks=[dict(c,part=i+1) for i,r in enumerate(reports) for c in r["checks"]]
    return dict(version="direct-verification/1",decision="WITHHELD" if held else "RETAINED",checks=checks,
                input_sha256=reports[0]["input_sha256"],draft_sha256=digest(draft),draft=deepcopy(draft),
                effective_answer=None if held else deepcopy(draft),conditional_answer=None,proof=None,parts=reports,
                scientific_approval=False,estimation_handoff_allowed=False,production_admission=False)

def clarification_items(answer):
    """Surface only a material gap named by an answer. A rejected draft is a different event."""
    if not isinstance(answer, dict):
        return []
    if isinstance(answer.get("answers"), list):
        return list(dict.fromkeys(item for part in answer["answers"] for item in clarification_items(part)))
    if answer.get("status") != "NEEDS_INPUT" or action(answer) != "STOP":
        return []
    for key in ("functional", "reason"):
        value = answer.get(key)
        if isinstance(value, str) and value.strip():
            return [value.strip()]
    return []


def bound_network(data, manifest):
    from cfm_id_llm.network_files import NetworkTable
    if isinstance(manifest, NetworkTable):
        table = manifest
    elif isinstance(manifest, dict):
        fields = {k:v for k,v in manifest.items() if k not in ("reference","scientific_approval")}
        table = NetworkTable(**fields)
        if digest(table.manifest()) != digest(manifest):
            raise ValueError("NETWORK_MANIFEST_MISMATCH")
    else:
        raise ValueError("NETWORK_MANIFEST_REQUIRED")
    references = [s for s in data["sources"] if s["source_id"]=="uploaded_network"]
    expected = table.source()
    if len(references)!=1 or any(references[0].get(k)!=v for k,v in expected.items()):
        raise ValueError("NETWORK_SOURCE_BINDING_MISMATCH")
    return table


def answer_items(value):
    if not isinstance(value, dict):
        return []
    if isinstance(value.get("answers"), list):
        return [item for item in value["answers"] if isinstance(item, dict)]
    if "status" not in value and isinstance(value.get("answer"), dict):
        return [value["answer"]]
    return [value]


def retained_question(report):
    """Connect one explicit, already displayed request for missing information to the reply form."""
    if report.get('decision')!='RETAINED' or report.get('clarification_questions'):
        return
    items=answer_items(report.get('effective_answer'))
    if len(items)!=1 or items[0].get('status')!='NEEDS_INPUT' or action(items[0])!='STOP':
        return
    reason=items[0].get('reason')
    if not isinstance(reason,str):
        return
    requests=re.findall(r'(?:^|(?<=[。！？?；\n]))\s*(请(?:问|提供|确认|说明|补充|选择|指定|给出)[^。！？?；\n]{2,300}(?:[。？?]|$))',reason)
    if len(requests)==1:
        report['clarification_questions']=requests


def verify(case, draft, *, version="direct-verification/22", network=None, network_focus=False, science_review=None,scope_choice=None, _index_ranges=False):
    """Use the proven functional for the exact declared target, and preserve the original draft."""
    if version in ("direct-verification/20", "direct-verification/21", "direct-verification/22"):
        from . import network_scope_choice, stratified_savings
        data=case if isinstance(case,dict) else case.model_dump(mode="json")
        report=network_scope_choice.verify(data,draft,network,network_focus,science_review,scope_choice,
                                          allow_index_ranges=version=="direct-verification/22")
        if network is None and not report.get("proof") and not science_review and len(answer_items(draft))<=1:
            try:
                stratified_savings.apply(data,draft,report)
            except (ValueError, ArithmeticError):
                pass
        if version in ("direct-verification/21","direct-verification/22") and not science_review and not scope_choice:
            from . import network_material_questions
            network_material_questions.apply(data,draft,network,report)
            if version=="direct-verification/22":
                network_material_questions.explicit_assignment_question(data,report)
        report["version"]=version
        return report
    if version in ("direct-verification/17","direct-verification/18","direct-verification/19"):
        from . import network_source_alignment as alignment
        data = case if isinstance(case, dict) else case.model_dump(mode="json")
        source_scope = version!="direct-verification/17"
        try:
            if source_scope and network is not None:
                from . import uploaded_network_contrast
                report=verify(data,draft,version="direct-verification/11",network=network,network_focus=network_focus)
                uploaded_network_contrast.apply(data,draft,network,report,science_review,source_first=True,
                                                extended=True,source_scope=True,natural_sources=version=="direct-verification/19")
                retained_question(report)
            else:
                report = verify(data, draft, version="direct-verification/16", network=network,
                                network_focus=network_focus, science_review=science_review)
        except ValueError as error:
            if network is None or science_review is not None or str(error) != "NETWORK_SOURCE_BINDING_MISMATCH":
                raise
            manifest = network.manifest() if hasattr(network,"manifest") else network
            report = dict(version=version, input_sha256=digest(data), draft=deepcopy(draft),
                          draft_sha256=digest(draft), network_manifest=deepcopy(manifest), production_admission=False)
            if network_focus:
                report["network_focus"] = True
            finding = alignment.unavailable(data)
            finding["fields"]["exposure"].update(state="DISAGREEMENT", table_note="本次文件指纹与原材料引用不一致。")
            alignment.retain(report, draft, finding, data)
            return report
        report["version"] = version
        alignment.enforce(data, network, draft, report, science_review,source_scope=source_scope,allow_index_ranges=_index_ranges)
        return report
    if version == "direct-verification/16":
        from . import direct_policy_exchange, uploaded_network_contrast
        data=case if isinstance(case,dict) else case.model_dump(mode="json")
        if network is not None:
            report=verify(data,draft,version="direct-verification/11",network=network,network_focus=network_focus)
            uploaded_network_contrast.apply(data,draft,network,report,science_review,source_first=True,extended=True)
        else:
            report=verify(data,draft,version="direct-verification/15",network_focus=network_focus)
            direct_policy_exchange.apply(data,draft,report,science_review)
            if science_review is not None and report.get('review_record')!=science_review:
                raise ValueError('NETWORK_REVIEW_NOT_AVAILABLE')
        retained_question(report)
        report["version"]=version
        return report
    if version == "direct-verification/15":
        if network is None:
            report=verify(case,draft,version="direct-verification/14",network_focus=network_focus,science_review=science_review)
        else:
            from . import uploaded_network_contrast
            data=case if isinstance(case,dict) else case.model_dump(mode="json")
            report=verify(data,draft,version="direct-verification/11",network=network,network_focus=network_focus)
            uploaded_network_contrast.apply(data,draft,network,report,science_review,source_first=True)
        report["version"]=version
        return report
    if version == "direct-verification/14":
        from . import source_network_review, quota_policy_support, unstratified_peer_rates, announced_quota_review
        data = case if isinstance(case, dict) else case.model_dump(mode="json")
        report = verify(data, draft, version="direct-verification/13", network=network,
                        network_focus=network_focus, science_review=science_review)
        report["version"] = version
        if network is None:
            source_network_review.apply(data, draft, report, routes=(quota_policy_support, unstratified_peer_rates, announced_quota_review))
        return report
    if version == "direct-verification/13":
        from . import source_network_review
        data = case if isinstance(case, dict) else case.model_dump(mode="json")
        report = verify(data, draft, version="direct-verification/12", network=network,
                        network_focus=network_focus, science_review=science_review)
        report["version"] = version
        if network is None:
            source_network_review.apply(data, draft, report)
        return report
    if version == "direct-verification/12":
        from cfm_id_llm.schemas import BusinessCase
        from . import uploaded_network_contrast
        data = case.model_dump(mode="json") if isinstance(case,BusinessCase) else case
        report=verify(data,draft,version="direct-verification/11",network=network,network_focus=network_focus)
        report["version"]=version
        uploaded_network_contrast.apply(data,draft,network,report,science_review)
        return report
    if version == "direct-verification/11":
        from cfm_id_llm.schemas import BusinessCase
        from .network_grounded_contrast import derive
        data = case.model_dump(mode="json") if isinstance(case, BusinessCase) else case
        report = verify(data, draft, version="direct-verification/10", network=network, network_focus=network_focus)
        report["version"] = version
        if network is not None or (report.get("proof") or {}).get("source_spans"):
            return report
        try:
            result = derive(data, draft)
        except (ValueError, TypeError, KeyError, ArithmeticError):
            result = None
        if result and result.get("network_evidence_gap"):
            gap = result["network_evidence_gap"]
            report.pop("parts", None)
            report.update(decision="WITHHELD", effective_answer=None, conditional_answer=None,
                          proof=None, clarification_questions=result["questions"])
            report["checks"].append(dict(code="UNRESOLVED_BASELINE_NEIGHBORS", state="CONFLICT",
                                        evidence=gap["evidence"], detail=gap["detail"]))
        elif result:
            report.pop("parts", None)
            answer = result["answer"]
            report.update(decision="CONDITIONAL_RESULT", effective_answer=answer, conditional_answer=answer,
                          proof=result["proof"], clarification_questions=result["questions"])
            if result["proof"].get("method") == "ORIGINAL_EVENT_ASSUMPTIONS_UNCONFIRMED":
                report["checks"].append(dict(code="UNCONFIRMED_ORIGINAL_DESIGN_ASSUMPTION", state="UNCHECKED",
                    detail="已定位来源和原比较。计算所需的科学条件仍需研究者说明。"))
            else:
                report["checks"].append(dict(code="ORIGINAL_CONTRAST_SOURCE_BINDING",state="CHECKED",
                    detail="已用原文绑定评价对象、实际分配的变量和左右事件，并重算原设计下的支持与估计交接。"))
        return report
    if version == "direct-verification/10":
        from .network_query_binding import source_result, unavailable_required_query
        from cfm_id_llm.schemas import BusinessCase
        data = case.model_dump(mode="json") if isinstance(case, BusinessCase) else case
        report = verify(data, draft, version="direct-verification/9", network=network, network_focus=network_focus)
        report["version"] = version
        if network is not None:
            return report
        result = source_result(data)
        if result:
            answer = result["answer"]
            report.pop("parts", None)
            report.update(decision="CONDITIONAL_RESULT", effective_answer=answer, conditional_answer=answer,
                          proof=result["proof"], clarification_questions=result["questions"])
            report["checks"].append(dict(code="SOURCE_BOUND_POPULATION_OPERATOR", state="CHECKED",
                detail="已按原目标核对支持和总体查询范围。交接中的查询、算子及原文可以重放。"))
        elif denial:=unavailable_required_query(data,report.get("effective_answer")):
            report.update(decision="WITHHELD",effective_answer=None,conditional_answer=None,proof=None,clarification_questions=[])
            report["checks"].append(dict(code="UNAVAILABLE_POPULATION_QUERY",state="CONFLICT",evidence=[denial],
                detail="交接要求逐份查询完整名单均值，材料明确排除了这一查询，草案须修改算子。"))
        elif not draft and network_focus and not report.get("proof"):
            report.update(decision="UNCHECKED",effective_answer=None,conditional_answer=None)
            report["checks"].append(dict(code="LOCAL_COVERAGE",state="UNCHECKED",
                detail="本地入口尚未核实这份材料的识别公式。"))
        return report
    if version == "direct-verification/9":
        from .network_relation_choice import ask_if_unselected
        from cfm_id_llm.schemas import BusinessCase
        data = case.model_dump(mode="json") if isinstance(case, BusinessCase) else case
        report = verify(data, draft, version="direct-verification/8", network=network, network_focus=network_focus)
        report["version"] = version
        ask_if_unselected(data, report)
        return report
    if version == "direct-verification/8":
        from . import network_response
        from cfm_id_llm.schemas import BusinessCase
        data = case.model_dump(mode="json") if isinstance(case, BusinessCase) else case
        normalized, _ = network_response.unpack(draft)
        report = verify(data, normalized, version="direct-verification/7", network=network, network_focus=network_focus)
        report.update(version=version, draft=deepcopy(draft), draft_sha256=digest(draft))
        network_response.apply(data, draft, report)
        if report.get("network_reading"):
            network_response.population_information(data, report)
            network_response.unsettled_design(data, report)
            network_response.grounded_questions(data, report)
        return report
    if version not in ("direct-verification/1", "direct-verification/2", "direct-verification/3", "direct-verification/4", "direct-verification/5", "direct-verification/6", "direct-verification/7"):
        raise ValueError("UNKNOWN_VERIFICATION_VERSION")
    original = draft
    if version == "direct-verification/7" and isinstance(draft, dict) and "network_facts" in draft:
        draft = {key: value for key, value in draft.items() if key != "network_facts"}
    report = _review_draft(case, draft)
    if original is not draft:
        report.update(draft=deepcopy(original), draft_sha256=digest(original))
    if version == "direct-verification/1":
        return report
    report["version"] = version
    if report["decision"] == "RETAINED" and report["proof"] and report["conditional_answer"]:
        report["decision"] = "CONDITIONAL_RESULT"
        report["effective_answer"] = deepcopy(report["conditional_answer"])
    if version in ("direct-verification/3","direct-verification/4","direct-verification/5","direct-verification/6","direct-verification/7"):
        from . import direct_dag, direct_network
        data = case if isinstance(case, dict) else case.model_dump(mode="json")
        revision = int(version.rsplit("/", 1)[-1])
        latest = revision >= 4
        table = bound_network(data, network) if latest and network is not None else None
        if table is not None:
            report["network_manifest"] = table.manifest()
        if not report["proof"] and isinstance(draft, dict) and draft:
            for module in (direct_dag, direct_network):
                try:
                    if latest and module is direct_network:
                        evidence = module.verified(data,network_table=table,revision=revision)
                    elif latest:
                        evidence = module.verified(data,revision=revision if revision >= 6 else 4)
                    else:
                        evidence = module.verified(data)
                except (ValueError, KeyError, ArithmeticError, TypeError) as error:
                    report["checks"].append(dict(code="SOURCE_ADAPTER", state="UNCHECKED",
                        detail=module.__name__ + " 未能验证输入或重放证据 (" + type(error).__name__ + ")。"))
                    continue
                if not evidence:
                    continue
                if revision >= 5 and evidence.get("review_only"):
                    report["checks"].extend(evidence["checks"])
                    continue
                answer = evidence["answer"]
                actual = draft.get("answers", [draft.get("answer", draft)])
                expected = answer.get("answers", [answer])
                fits = isinstance(actual, list) and len(actual) == len(expected) and all(
                    field(a, "status") == b["status"] and action(a) == action(b)
                    for a, b in zip(actual, expected))
                conflict = report["decision"] == "WITHHELD" or not fits
                if latest:
                    claims = answer_items(draft)
                    modes = {action(item) for item in claims}
                    certified = {action(item) for item in expected}
                    # Some correct drafts enumerate x=0 and x=1 or use another valid
                    # stop status. Different formatting alone is not a scientific error.
                    other_status = any(item.get("status") in {"PARTIAL","NOT_POINT","UNDEFINED","NEEDS_INPUT"} for item in claims)
                    conflict = bool(claims and len(certified)==1 and
                                    (modes-certified or (other_status and certified=={"ESTIMATE_POINT"})))
                    if evidence["proof"].get("method")=="ID_HEDGE" and claims and all(
                        i.get("status")=="PARTIAL" and action(i)=="ESTIMATE_BOUNDS" and
                        isinstance(i.get("value"),list) and len(i["value"])==2 for i in claims):
                        # A hedge resolves uniqueness only, not the sharpness of reported bounds.
                        report.update(proof=evidence["proof"],conditional_answer=answer)
                        report["checks"].extend(evidence["checks"])
                        report["checks"].append(dict(code="BOUND_SHARPNESS",state="UNCHECKED",
                            detail="图证据支持非点识别。原答提出的界和可达性仍需核验。"))
                        break
                report.update(decision="CORRECTED" if conflict else "CONDITIONAL_RESULT",
                    conditional_answer=answer, effective_answer=deepcopy(answer), proof=evidence["proof"])
                if latest and "parts" in report:
                    report["draft_parts"] = report.pop("parts")
                report["checks"].extend(evidence["checks"])
                mark_conflict = conflict if latest else not fits
                if mark_conflict:
                    report["checks"].append(dict(code="SOLVER_CONCLUSION", state="CONFLICT",
                        detail="识别状态或估计动作与按原材料得到的结论不一致。" if latest else "子问题数、识别状态或估计动作与按原材料得到的结论不一致。"))
                report["clarification_questions"] = evidence["questions"]
                break
        if revision == 7:
            from . import network_reading
            if network_focus:
                report["network_focus"] = True
            network_reading.apply(data, original, report, table, network_focus=network_focus)
        report.setdefault("clarification_questions", clarification_items(report["effective_answer"]))
    return report


def replay(case, draft, report):
    """Recompute a saved report using the verification version that created it."""
    if not isinstance(report, dict):
        return False
    try:
        options = dict(version=report.get("version"),network=report.get("network_manifest"),network_focus=report.get("network_focus",False))
        if report.get("version") in ("direct-verification/12","direct-verification/13","direct-verification/14","direct-verification/15","direct-verification/16","direct-verification/17","direct-verification/18","direct-verification/19","direct-verification/20","direct-verification/21","direct-verification/22"):
            options["science_review"]=report.get("review_record")
        if report.get("version") in ("direct-verification/20","direct-verification/21","direct-verification/22"):
            options["scope_choice"]=report.get("scope_choice")
        rebuilt = verify(case, draft, **options)
        return digest(rebuilt) == digest(report)
    except (TypeError, KeyError, ValueError, ArithmeticError, RecursionError):
        return False
