"""Normalize transport envelopes and simple typed facts, without inferring missing science."""
from copy import deepcopy
import re

from . import network_reading as reading


def unpack(draft):
    """A fact sheet can accompany a single answer inside a provider's JSON envelope."""
    if not isinstance(draft, dict):
        return draft, None
    data = deepcopy(draft)
    root = data.pop("network_facts", None)
    sheets = [("network_facts", root)] if isinstance(root, dict) else []
    if isinstance(data.get("answer"), dict):
        inner = data["answer"]
        value = inner.pop("network_facts", None)
        if isinstance(value, dict):
            sheets.append(("answer.network_facts", value))
    parts = data.get("answers")
    if isinstance(parts, list):
        for i, part in enumerate(parts):
            if isinstance(part, dict):
                value = part.pop("network_facts", None)
                if isinstance(value, dict):
                    sheets.append((f"answers[{i}].network_facts", value))
    if not sheets:
        return data, None
    # Do not silently attach one subquestion's contrast to the entire study.
    if any(sheet != sheets[0][1] for _, sheet in sheets[1:]) or (
            isinstance(parts, list) and len(parts) > 1 and all(path.startswith("answers[") for path,_ in sheets)):
        return data, dict(state="PER_TARGET_OR_CONFLICT", paths=[p for p,_ in sheets])
    data["network_facts"] = sheets[0][1]
    return data, dict(state="LOCATED", paths=[p for p,_ in sheets])


def exact_event(value):
    if isinstance(value, list) and len(value) == 2:
        parsed = []
        for item in value:
            if type(item) is int:
                parsed.append(item)
            elif isinstance(item, str) and re.fullmatch(r"\d{1,3}", item.strip()):
                parsed.append(int(item))
            else:
                return value
        return parsed
    if isinstance(value, str):
        m = re.fullmatch(r"\s*[\[(（]\s*([01])\s*[,，]\s*(\d{1,3})\s*[\])）]\s*", value)
        if m:
            return list(map(int,m.groups()))
    return value


def typed_fields(sheet):
    """Accept exact notational equivalents. Do not infer an unspecified treatment or threshold."""
    if not isinstance(sheet, dict):
        return sheet
    typed = deepcopy(sheet)
    def value(key):
        item=typed.get(key)
        return item["value"] if isinstance(item, dict) and isinstance(item.get("value"),dict) else {}
    graph=value("network")
    c=value("contrast")
    for key in ("left","right"):
        if key in c:
            c[key]=exact_event(c[key])
    if isinstance(c.get("population"),str) and isinstance(graph.get("nodes"),list) and c["population"] in graph["nodes"]:
        c["population"]=[c["population"]]
    return typed


def apply(case, draft, report):
    """Record source attribution accurately even when the provider omits the requested appendix."""
    r=report.get("network_reading")
    if r is None:
        return
    _,location=unpack(draft)
    r["origin"]="model_and_source" if location and location["state"]=="LOCATED" else "source_only"
    if location:
        r["fact_sheet_location"]=location
    # Raw proposed values remain visible; normalization affects arithmetic only.
    if r["origin"]=="model_and_source" and not r.get("conditional_joint_support"):
        extracted,_=unpack(draft)
        normalized=typed_fields(extracted["network_facts"])
        if normalized != extracted["network_facts"]:
            fields=reading.fact_evidence(case,dict(network_facts=normalized))["fields"]
            try:
                joint=reading.proposed_model(fields)
            except (ValueError,KeyError,ArithmeticError,TypeError):
                joint=None
            if joint is not None:
                r["conditional_joint_support"]=joint
                r["conditional_support_scope"]="按引文所附的候选值进行条件复算，等价的端点记法已规范化；不据此确认研究假设。"


def unsettled_design(case, report):
    """Only a stated unresolved conflict about the original local design calls for a user reply."""
    q=case["business_question"]
    if not re.search(r"原.{0,10}(?:设计|抽签|抽法|分配)|本轮抽取.{0,12}条件",q):
        return
    docs=[(sid,text) for sid,text in reading.records(case) if sid!="question"]
    full="\n".join(t for _,t in docs)
    if not re.search(r"无法(?:辨别|确认|判定).{0,15}(?:哪|何|采用)|两份.{0,12}(?:互相矛盾|相互冲突)|两种说法.{0,8}(?:冲突|待核实)",full):
        return
    if re.search(r"以.{0,20}为准|已(?:确认|更正|澄清)|已核对|不适用于(?:本|这)|另一个演练|第一阶段|第二阶段|各有.{0,12}概率",full):
        return
    local=reading.sentences(docs)
    laws={}
    for label,pat in (("逐人独立抽签",r"各自独立|各(?:人|站|店)独立|独立抛|分别独立"),
                      ("共用一次抽签",r"共用.{0,10}(?:签|硬币)|一起掷同一|一开全开"),
                      ("整份名单固定名额",r"等概率无放回|均匀.{0,8}(?:恰好|恰抽)|固定名额.{0,8}等概率")):
        hit=reading.signed(local,pat)
        if hit:
            laws[label]=dict(source_id=hit[0],quote=hit[1])
    if len(laws)<2:
        return
    # The user can keep an already conditional answer that presents the alternatives.
    from .direct_verification import action, answer_items
    parts=answer_items(report.get("effective_answer"))
    stopped=any(p.get("status") in ("NEEDS_INPUT","NOT_POINT","UNDEFINED") and action(p)=="STOP" for p in parts)
    preserve=stopped and not any(p.get("status")=="POINT" and p.get("target",{}).get("quantity")=="difference" for p in parts if isinstance(p.get("target",{}),dict))
    question="关于本轮原分配，材料同时记载了"+"和".join(laws)+"。请确认哪项记录适用于这次比较，以确定两端的联合支持与其余安排的条件权重。"
    if not preserve:
        report.update(decision="WITHHELD",effective_answer=None,conditional_answer=None,proof=None)
    report.update(clarification_questions=[question])
    report["network_reading"]["unresolved_design_sources"]=laws
    report["checks"].append(dict(code="CONFLICTING_ORIGINAL_DESIGN",state="CONFLICT",detail=question))


def population_information(case, report):
    """A support certificate after a design supplement cannot supply population outcomes."""
    ans = report.get("conditional_answer") or {}
    proof = report.get("proof") or {}
    if not str(proof.get("checked_by","")).startswith("source prose") or ans.get("status")!="POINT":
        return
    source = "\n".join(s["text"] for s in case["sources"])
    means_evidence = any(a.get("subject")=="总体条件均值" for a in ans.get("assumptions",[]) if isinstance(a,dict))
    def keep_support():
        from .direct_verification import verify, clarification_items
        normalized,_ = unpack(report.get("draft"))
        plain={k:v for k,v in normalized.items() if k!="network_facts"} if isinstance(normalized,dict) else normalized
        prior=verify(case,plain,version="direct-verification/2")
        report["network_reading"]["support_proof"]=proof
        report.update(decision=prior["decision"],conditional_answer=None,proof=None,effective_answer=prior["effective_answer"],
                      clarification_questions=clarification_items(prior["effective_answer"]))
    if ans.get("value") is not None:
        # A bare “respectively” may refer to a different list than the one in the question.
        if "按题目顺序" not in source:
            keep_support()
            if re.search(r"顺序(?:缺失|不明|未注明|待确认)|未标(?:注|明).{0,10}(?:哪一端|对应关系)",source):
                report.update(effective_answer=None,decision="WITHHELD",
                    clarification_questions=["两个报告的总体均值分别对应题中哪一个比较端？请确认顺序，以确定所求差的符号。"])
            report["checks"].append(dict(code="ORDER_OF_REPORTED_MEANS",state="UNCHECKED",
                detail="联合支持已核算，文中均值的排列顺序尚未与题中左右端独立绑定。"))
        return
    if means_evidence and not reading.native.missing_event_means(source):
        return
    if not (reading.native.missing_event_means(source) or re.search(r"只有.{0,12}(?:未分层|无条件)|没有.{0,10}(?:条件均值|结局资料)|结局信息待补",source)):
        keep_support()
        report["checks"].append(dict(code="POPULATION_INFORMATION",state="UNCHECKED",detail="联合支持已重算，程序未能独立验证总体结局算子。"))
        return
    msg="原分配与两端的联合支持已经确定。请指出各比较端个人总体条件均值，或能推出这些均值的总体联合分布。"
    checked=deepcopy(ans)
    checked.update(status="NEEDS_INPUT",functional=msg,reason=msg)
    checked["estimate_handoff"].update(mode="STOP",operator=msg)
    report["network_reading"]["support_proof"]=proof
    report.update(effective_answer=checked,conditional_answer=None,proof=None,decision="CORRECTED",clarification_questions=[msg])
    report["checks"].append(dict(code="POPULATION_INFORMATION",state="UNCHECKED",detail=msg))


def grounded_questions(case, report):
    """A model's inability to supply a number is not by itself a request for more study data."""
    if not report.get("clarification_questions") or report.get("proof"):
        return
    diagnosed={"CONFLICTING_ORIGINAL_DESIGN","CITED_JOINT_DISAGREEMENT","POPULATION_INFORMATION","ORDER_OF_REPORTED_MEANS"}
    if any(c.get("code") in diagnosed for c in report.get("checks",[])):
        return
    sources=reading.records(case)
    full="\n".join(t for _,t in sources)
    missing=r"待补|待定|不详|不清楚|未说明|没有说明|没有指定|未指定|尚未指定|还没有指定|没说|无法确认|不能确认|无法辨别|遗失|没有保留|只留|只报|没有提供|未提供|未记录|没有记录|缺失|无法.{0,12}倒推|不清楚|无法恢复"
    # The clarification must name the same type of fact that the sources leave open.
    requests=" ".join(str(q) for q in report["clarification_questions"])
    topics=(
        (r"伙伴|网络|邻居|边表|联系|关联|老伙伴|方向|标签|关注", "请确认采用哪一套处理前关系或暴露定义，并指出可用于该定义的邻接资料或等价事件信息。"),
        (r"设计|分配|抽签|名单概率|联合概率|共签|规则|机制", "请说明原设计如何产生完整名单，或提供两个比较端所需的联合概率与端内分配规律。"),
        (r"均值|结局|时点|时间|结果|回访|借还记录|数据", "请补充所问时点、评价对象及两个比较端的总体结局信息，或可导出它的总体分布。"),
        (r"通知|预告|广播|干预定义", "请明确所求处理效应要固定或平均哪种通知安排，并说明这种比较有何识别依据。"),
    )
    hits=[]
    for pat,msg in topics:
        if not re.search(pat,requests):
            continue
        for sid,line in reading.sentences(sources):
            if re.search(missing,line) and re.search(pat,line):
                if (re.search(r"数值|具体数",line) and re.search(r"只.{0,6}(?:符号|写调用|公式)|可符号|不必.{0,4}报数",full)):
                    continue
                if pat==topics[0][0] and (reading.native.equivalent_exposure_reported(full) or
                        re.search(r"能对.{0,16}所有可能.{0,25}(?:判定|标记)|每一份可能.{0,25}准确打上",full)):
                    continue
                hits.append(dict(question=msg,source_id=sid,quote=line))
                break
    if hits:
        report["clarification_questions"]=[r["question"] for r in hits]
        report["network_reading"]["clarification_evidence"]=hits
    elif not case["sources"] and len(case["business_question"])<180:
        report["clarification_questions"]=["请提供本题使用的研究材料，并标明目标人群、比较安排及已知的分配和总体结局信息。"]
    else:
        report["network_reading"]["unconfirmed_model_questions"]=report["clarification_questions"]
        report["clarification_questions"]=[]
        report["checks"].append(dict(code="UNCONFIRMED_MODEL_GAP",state="UNCHECKED",
             detail="模型提出了补件要求，现有原文尚不能证实该项确有缺失。已保留草案和请求供复核。"))
