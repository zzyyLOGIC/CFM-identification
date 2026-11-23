"""Source-bound routes for network targets previously left to the model draft."""
import re
from copy import deepcopy

from cfm_id_llm.compact_study import digest
from .network_grounded_contrast import count, source_lines

ORD = r"(?:[1-9]\d*|[一二两三四五六七八九十])"


class MissingFacts(ValueError):
    """A recognized target lacks a specific fact needed by this route."""


def one(rows, pattern, *, message):
    matches = [r for r in rows if re.search(pattern, r["quote"])]
    if len({r["quote"] for r in matches}) != 1:
        raise MissingFacts(message)
    return matches[0]


def evidence(row, subject):
    return dict(kind="other", subject=subject, statement=row["quote"],
                source=row["source_id"], quote=row["quote"])


def require_statement(row, subject):
    """Questions, hypotheticals and unconfirmed claims cannot provide a premise."""
    if re.search(r"能否|是否|如果|若(?:能|有|是|假定|认为)|有待(?:确认|检验)|(?:尚未|未曾|无法|不能|未)(?:确认|核准|核实|验证|保证)|仍有争议",row["quote"]):
        raise MissingFacts("请核准材料中关于"+subject+"的陈述。")
    return row


def apply(case, draft, report, *, routes=None):
    from . import named_plan_level, roster_event_review, observed_peer_review, reported_peer_strata
    from .direct_verification import answer_items
    if report.get("proof") or (report.get("network_reading") or {}).get("unresolved_design_sources"):
        return
    if not isinstance(draft, dict) or not draft or len(answer_items(draft)) != 1:
        return
    rows = source_lines(case)
    docs = [r for r in rows if r["source_id"] != "question"]
    question = case["business_question"]
    for route in (routes or (named_plan_level, roster_event_review, observed_peer_review, reported_peer_strata)):
        try:
            result = route.derive(question, docs)
        except (ValueError, ArithmeticError) as exc:
            # Noncanonical rationals and invalid typed graph coordinates are input gaps.
            question = str(exc) if isinstance(exc, MissingFacts) else "请核对原文中的概率、名单和总体表坐标，现有材料无法构造一致的数学输入。"
            report.pop("parts", None)
            report.update(decision="WITHHELD", effective_answer=None, conditional_answer=None,
                          clarification_questions=[question])
            report["checks"].append(dict(code="NETWORK_SOURCE_GAP", state="UNCHECKED", detail=question))
            return
        if result is None:
            continue
        answer, proof = result["answer"], result["proof"]
        proof.update(source_sha256=digest(case["sources"]), question_sha256=digest(question),
                     question_text=question, conditional_only=True)
        claim = answer_items(draft)[0]
        same_status = claim.get("status") == answer["status"]
        if routes and same_status:
            raw_target = claim.get("target") or {}
            target = answer["target"]
            same_status = isinstance(raw_target, dict) and raw_target.get("quantity") == target["quantity"]
            if same_status and proof.get("method") == "LABELED_OBSERVATIONAL_ARMS":
                people = raw_target.get("population")
                if isinstance(people, str):
                    people = [people]
                same_status = people == target["population"] and raw_target.get("requested_operation") == target["requested_operation"]
        report.pop("parts", None)
        report.update(effective_answer=answer, conditional_answer=deepcopy(answer), proof=proof,
                      decision="CONDITIONAL_RESULT" if same_status else "CORRECTED",
                      clarification_questions=result["questions"])
        report["checks"].append(dict(code="NETWORK_SOURCE_OPERATOR", state="CHECKED", detail=answer["reason"]))
        return
