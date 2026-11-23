"""Ask about an explicitly unselected network when the reported comparisons differ."""
import re

from . import network_reading as reading

RELATION = re.compile(r"关系|网络|伙伴|搭档|邻居|邻点|同伴|关联点|好友|联系图|口径")
UNSELECTED = re.compile(
    r"(?:尚未|还没有|没有|未)(?:明确|指定|选定|确定|说明|决定|确认)"
    r"[^。；，！？]{0,24}(?:哪[一两]?[套种个项类]|何种)"
)
AMOUNT = r"[-−+]?(?:\d+/\d+|\d*\.\d+|\d+)%?"
ENDPOINTS = re.compile(
    rf"(?:^|[，,])\s*(?:按|依据|采用)(?P<label>[^，。；：、,\s]{{1,18}}?)的?两端"
    rf"[^，。；0-9]{{0,20}}?(?:分别为|分别是|为|是|：|:)\s*(?P<left>{AMOUNT})"
    rf"\s*(?:和|与|、|，|,)\s*(?P<right>{AMOUNT})(?![\d./%])"
)


def ask_if_unselected(case, report):
    if not report.get("network_reading") or report.get("proof") or report.get("clarification_questions"):
        return
    question = case["business_question"]
    if not RELATION.search(question) or re.search(r"分别(?:求|给|计算)|两套都|两种都|每套|是否相同|是否随|不论哪|不论用|无论用", question):
        return
    sources = {s["source_id"]: s["text"] for s in case["sources"]}
    lines = reading.sentences(sources.items())
    choice = next(((sid, line) for sid, line in lines if UNSELECTED.search(line) and RELATION.search(line)), None)
    if not choice or not any(re.search(r"处理前|试点前|开始前|实施前|开工前|基线", line) for _, line in lines):
        return

    options = {}
    for sid, line in lines:
        match = ENDPOINTS.search(line)
        if not match:
            continue
        label = match["label"]
        try:
            pair = tuple(reading.number(match[x].replace("−", "-")) for x in ("left", "right"))
        except (ArithmeticError, ValueError):
            return
        if label in options and pair != options[label][0]:
            return
        options[label] = (pair, sid, line)
    if len(options) != 2 or any(label in question for label in options):
        return
    contrasts = {left - right for (left, right), _, _ in options.values()}
    if len(contrasts) != 2:
        return
    for sid, line in lines:
        if UNSELECTED.search(line) or not any(label in line for label in options):
            continue
        explicit_reply = sid.startswith("user_reply") and (line.strip() in options or re.search(r"(?:我选|我们选择|请用|请按|只采用)", line))
        if explicit_reply or re.search(r"已(?:经)?(?:选定|指定|决定|确认)|以.{1,22}为准|本次(?:只|用|按|选|采用)|最终(?:决定|选)", line):
            return

    def span(sid, line):
        start = sources[sid].index(line)
        return dict(source_id=sid, quote=line, start=start, end=start+len(line))

    evidence = [span(*choice)] + [span(sid, line) for _, sid, line in options.values()]
    labels = list(options)
    prompt = f"本次比较的关联点采用“{labels[0]}”还是“{labels[1]}”？两套口径在材料中给出的比较结果不同。"
    # Keep a scientifically meaningful conditional answer. A facts-only response or
    # a fabricated point answer cannot stand in for the user's choice.
    from .direct_verification import action, answer_items
    parts = answer_items(report.get("effective_answer"))
    conditional_text = " ".join(str(parts[0].get(key, "")) for key in ("functional", "reason")) if len(parts) == 1 else ""
    usable = (len(parts) == 1 and parts[0].get("status") == "NEEDS_INPUT" and action(parts[0]) == "STOP"
              and all(label in conditional_text for label in labels))
    if not usable:
        report.update(decision="WITHHELD", effective_answer=None, conditional_answer=None)
    report["clarification_questions"] = [prompt]
    report["network_reading"]["relation_choice_evidence"] = evidence
    report["checks"].append(dict(code="UNSELECTED_NETWORK_RELATION", state="CONFLICT", detail=prompt, evidence=evidence))
