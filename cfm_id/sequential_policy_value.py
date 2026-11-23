"""Bind two-stage, binary-history policy summaries to their original actions and weights."""
from fractions import Fraction
import re

from .network_query_binding import RATE, read_rate
from .network_estimate_handoff import execute_handoff


METHOD = "TWO_STAGE_POLICY_BRANCH_MEANS"
SCOPE_QUESTION = "请确认档案的权重和两项分支均值是否已按第一阶段政策下目标对象的完整历史标准化。"
FIRST = r"(?:第一(?:班|轮|阶段)|首(?:班|轮))"
SECOND = r"(?:第二(?:班|轮|阶段)|次(?:班|轮))"
NAME = r"[\w\u3400-\u9fff]{1,16}?"
AMOUNT = r"[+−-]?(?:\d{1,12}/\d{1,12}|\d{1,12}(?:\.\d{1,12})?)"


def unique_match(rows, pattern):
    matches = [(r, m) for r in rows for m in re.finditer(pattern, r["quote"])]
    return matches[0] if len(matches) == 1 else (None, None)


def checked_action(observed, prescribed, alternative):
    if observed == prescribed:
        return True
    # 同一动作的简写，例如派协作车与派车。否定动词可省略前句的宾语。
    if prescribed.startswith("不") and observed.startswith(prescribed):
        return observed[1:] in (alternative,alternative[0]+alternative[-1])
    return len(observed)==2 and len(prescribed)>2 and observed==prescribed[0]+prescribed[-1]


def branch_means(rows, event, actions, focus):
    states = rf"(?P<neg>没有|未出现|未发生|无|未)?{re.escape(event)}"
    who = rf"(?:(?:目标(?:站|店|单位|对象)|{re.escape(focus)})(?:的)?)?"
    pattern = (rf"(?:^|[，,、]){states}(?:并且|并|且|时)(?P<act>{NAME})的{who}"
               rf"(?P<time>次班|下一班|第二班|次轮|下一轮|第二轮|第二阶段)(?:结果)?"
               rf"(?:均值|平均值)(?:为|是|等于)\s*(?P<mean>{AMOUNT})(?=$|[，,、]|件|份|个)")
    means = {}
    for row in rows:
        for match in re.finditer(pattern, row["quote"]):
            positive = not match["neg"]
            if positive in means or not checked_action(match["act"], actions[positive], actions[not positive]):
                return None
            try:
                value = Fraction(match["mean"].replace("−", "-"))
            except (ValueError, ZeroDivisionError):
                return None
            means[positive] = (value, row)
    return means if len(means) == 2 else None


def interpretation(rows, first_action, event):
    """Only an explicit statement about the target policy distribution can certify the value."""
    accepted = []
    denied = []
    for row in rows:
        text = row["quote"]
        if row.get("reply_to") == SCOPE_QUESTION:
            if re.fullmatch(r"是(?:的)?|对|已(?:经)?标准化|已确认|确认属实", text):
                accepted.append(row)
                continue
            if re.fullmatch(r"否|不是|没有|未经标准化|未标准化|不知道|不清楚|不能确认", text):
                denied.append(row)
                continue
        if not re.search(r"分支均值|两项均值|两支均值|两个均值", text):
            continue
        if re.search(r"未经|没有|未按|未作|尚未|未标准化|仅为|只是|不能确认|不确定|是否|可能|拟|假如|如果|若按|其他政策|另一(?:项)?政策|旧政策|对照政策", text):
            denied.append(row)
        elif (re.search(r"政策|策略", text) and re.search(r"权重|概率|分布", text)
              and re.search(r"(?:完整|全部|所有)(?:的)?历史", text)
              and re.search(r"已(?:经)?(?:按.{0,35})?标准化|已(?:经)?标准化|已按.{0,40}加权", text)):
            accepted.append(row)
    if denied:
        return "UNVERIFIED", denied
    if accepted:
        return "POLICY_STANDARDIZED", accepted
    # A raw within-branch action mean also suffices when selection is constant
    # within each of those branches and the first-stage margins target the same population.
    start, _ = unique_match(rows,r"原设计"+FIRST+r"(?:为|是)?无条件随机")
    history, _ = unique_match(rows,SECOND+r"(?:(?:的)?完整决策历史|的全部决策历史)(?:仅为|只有|仅含)"+re.escape(event)+r"$")
    scope, _ = unique_match(rows,r"(?:两项|两支)分支均值(?:与|和)权重均来自"+re.escape(first_action)+r"(?:后|下)的同一目标总体$")
    if start and history and scope:
        return "BRANCH_SUFFICIENT", [start,history,scope]
    return "UNSPECIFIED", []


def evaluate(question, docs, replies, nodes):
    if (not re.search(r"(?:政策|策略)(?:水平|均值)|(?:两班|两阶段|两轮)(?:政策|策略)", question)
            or re.search(r"相对|相比|减去|之差|对照|另外|另问", question)):
        return
    targets = [n for n in nodes if n in question]
    if not nodes:
        targets = re.findall(r"(?:^|[，,。])([\w\u3400-\u9fff]{1,14}?(?:站|点|店|厂))(?=(?:的)?(?:下一?[班轮]|第二(?:班|轮|阶段))(?:的)?平均)", question)
    if len(targets) != 1:
        return
    focus, = targets
    outcome = re.search(re.escape(focus) + r"(?:的)?(下(?:一)?(?:班|轮)|第二(?:班|阶段|轮))"
                        r"(?:的)?平均([^，,。？?]{1,22})[？?。]", question)
    if not outcome:
        return
    first_row, first = unique_match(docs, FIRST + r"(?:统一|一律|都)(?:采用|使用|实行)(?P<label>" + NAME + r")$")
    rule_row, rule = unique_match(docs, SECOND + r"(?:若|如|当)(?:邻站|邻店|邻居|邻点|伙伴)(?:回报|报告|反馈)"
                                  r"(?P<event>" + NAME + r")(?:时)?(?:则|就)(?P<yes>" + NAME
                                  + r")[，,](?:否则|其余情况)(?P<no>" + NAME + r")$")
    if first is None or rule is None:
        return
    event, first_action = rule["event"], first["label"]
    actions = {True: rule["yes"], False: rule["no"]}
    if actions[True] == actions[False]:
        return
    law_row, law = unique_match(docs, r"(?:各|每)(?:班|轮|阶段)(?:决策|分配|安排)[^，,]{0,22}"
                                r"(?:历史|状态)(?:内|下|中)(?:是)?随机.{0,8}正支持")
    cons_row, cons = unique_match(docs, r"(?:状态与结果一致|满足一致性|状态和结果一致)")
    hist_row, hist = unique_match(docs, r"(?:所有|全部)(?:所需|必要)?历史(?:都|均)?已记录")
    archive_row, archive = unique_match(docs, r"(?:原设计|精确|目标)?总体(?:档案|记录|资料|表)(?:给出?|显示|列出|记载)")
    if any(x is None for x in (law, cons, hist, archive)):
        return
    if any(re.search(r"不随机|非随机|未随机|没有正支持|无正支持|未确认|不一致|[不未]满足一致性|未记录|只是样本|仅为样本|并非总体|未经确认|拟采用|尚未证实", r["quote"]) for r in docs):
        return
    archive_rows = [r for r in docs if r["source_id"] == archive_row["source_id"] and r["start"] >= archive_row["start"]]
    weight_row, weight = unique_match(archive_rows, re.escape(first_action) + r"(?:之后|后)(?:出现|发生)?"
                                      + re.escape(event) + r"(?:的)?(?:概率|权重)(?:为|是|等于)\s*(" + RATE + r")(?![\d./%])")
    means = branch_means(archive_rows, event, actions, focus)
    if not weight or not means:
        return
    if any(node != focus and node in r["quote"] for node in nodes for r in (weight_row,means[True][1],means[False][1])):
        return
    if any(re.search(r"改为|更正|更换|另问|修正|改用|权重(?:是|为|改)|概率(?:是|为|改)|均值(?:是|为|改)",r["quote"]) for r in replies):
        return
    try:
        prob = read_rate(weight[1])
    except (KeyError, ValueError, ZeroDivisionError):
        return
    if not 0 < prob < 1:
        return
    # For an explicitly binary policy the other weight is 1-p. Any separately
    # supplied probability for this event must match, including its denominator.
    reported = re.compile(r"(没有|未出现|未发生|无|未)?"+re.escape(event)+r"(?:的)?(?:概率|权重)(?:为|是|等于)\s*("+RATE+r")(?![\d./%])")
    for row in docs:
        for m in reported.finditer(row["quote"]):
            try:
                if row not in archive_rows or read_rate(m[2]) != (1-prob if m[1] else prob):
                    return
            except (KeyError, ValueError, ZeroDivisionError):
                return
    if any(r["source_id"] != archive_row["source_id"] and event in r["quote"] and
           re.search(r"均值|概率|权重", r["quote"]) for r in docs):
        return
    scope, scope_rows = interpretation([*docs, *replies], first_action, event)
    weighted = []
    for active, w in ((True, prob), (False, 1-prob)):
        mean, ref = means[active]
        weighted.append(dict(history=event if active else "无"+event, action=actions[active], weight=str(w),
                             mean=str(mean), contribution=str(w*mean), source=ref, weight_source=weight_row,
                             weight_rule="reported" if active else "binary_complement"))
    operator = dict(version="population-query/1",forms=[[t["weight"] for t in weighted]])
    operands = [dict(id=t["history"],action=t["action"]) for t in weighted]
    total = execute_handoff(dict(mode="ESTIMATE_POINT",queries=operands,operator_spec=operator),
                            {t["history"]:t["mean"] for t in weighted})
    product = " + ".join(t["weight"]+" × "+t["mean"] for t in weighted) + " = " + str(total)
    confirmed = scope in ("POLICY_STANDARDIZED", "BRANCH_SUFFICIENT")
    assumptions = [dict(subject=label, statement=row["quote"], source=row["source_id"], quote=row["quote"])
                   for label, row in (("按历史随机且有正支持", law_row), ("一致性", cons_row), ("已记录所需历史", hist_row))]
    gformula = "按第一阶段政策产生的完整历史分布，对每个历史下执行指定动作的目标结果条件均值加权。"
    text = gformula + " 代入档案的两支数据，" + product + "。"
    if scope=="BRANCH_SUFFICIENT":
        reason = f"首轮无条件随机，第二阶段的完整决策历史只含{event}，权重和两支均值属于同一目标总体。{focus}的政策水平为 {total}。"
    elif confirmed:
        reason = f"档案的权重及两支均值已按这项政策的完整历史标准化，{focus}的政策水平为 {total}。"
    else:
        reason = (f"若这些是该政策下的分支权重和标准化均值，{focus}的政策水平为 {total}。"
                  "若是实际采取各动作的对象均值，组内不同历史的动作概率可能不同；仅凭这两个均值不能确定政策数值。")
    questions = [] if confirmed or scope == "UNVERIFIED" else [SCOPE_QUESTION]
    outcome_name = re.sub(r"(?:多少|几)(件|份|箱|单)$",r"\1数",outcome[2])
    target = dict(quantity="level", population=focus, scope="individual", intervention=first_row["quote"]+"。"+rule_row["quote"],
                  reference=None, outcome=outcome_name, time=outcome[1])
    handoff = dict(mode="EXACT_POPULATION_VALUE" if confirmed else "STOP", queries=[], population=focus,
                   operator=product, terms=weighted, archive_weighted_value=str(total), information_scope=scope)
    if not confirmed:
        handoff["required_information"] = "相同政策历史分布下的分支权重与均值，或各完整历史的分布和对应动作的条件均值"
    answer = dict(status="POINT" if confirmed else "NEEDS_INPUT", target=target, functional=text, reason=reason,
                  full_history_functional="POINT_GIVEN_LONGITUDINAL_LAW",
                  assumptions=assumptions, value=str(total) if confirmed else None, estimate_handoff=handoff)
    proof = dict(method=METHOD, first_action=first_action, event=event, population=focus, terms=weighted,
                 archive_weighted_value=total, information_scope=scope, archive_operator=operator, sources=[first_row, rule_row, archive_row,
                 law_row, cons_row, hist_row, *scope_rows])
    return answer, proof, questions
