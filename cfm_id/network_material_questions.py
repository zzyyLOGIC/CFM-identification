"""Resolve specific missing quantities and terminal decisions from the submitted study."""
from fractions import Fraction
import re

from . import sequential_policy_value
from .network_grounded_contrast import count, source_lines
from .network_natural_sources import ordered_pair
from .network_query_binding import RATE, read_rate


DEGREE = "INCOMPLETE_NETWORK_FOCAL_SUPPORT"
INVITATION = "RANDOM_INVITATION_RECEIPT_NOT_IDENTIFIED"
METHODS = (sequential_policy_value.METHOD, DEGREE, INVITATION)


def explicit_assignment_question(case, report):
    """Surface the user's explicit assignment question when a draft offers no usable answer."""
    if (report.get('decision') != 'WITHHELD' or report.get('proof')
            or report.get('clarification_questions') or report.get('estimation_handoff_allowed')
            or any(s['source_id'].startswith('user_reply_') for s in case['sources'])):
        return
    query = case['business_question']
    mention = re.search(r'(邀请|入选|处理|试点|推广)名单[^。！？\n]{0,18}(?:怎么|如何|怎样)(?:选|定|分配)'
                        r'[^。！？\n]{0,16}(?:不清楚|不确定|不知道|尚未查明)', query)
    if not mention:
        return
    # If another submitted passage describes selection, keep the disagreement for
    # review. Never infer missing assignment from the absence of a model field.
    remaining = query[:mention.start()] + query[mention.end():]
    materials = '\n'.join([remaining, *(s['text'] for s in case['sources'])])
    if re.search(r'独立.{0,12}(?:抽签|随机|概率)|等概率|无放回|中签率|各.{0,8}(?:抽取|抽中)|'
                 r'按[^。\n]{1,16}(?:挑选|选出|确定名单|选取)|(?:名额|中签概率)(?:为|是)', materials):
        return
    report['clarification_questions'] = [f'当时怎样决定谁进入{mention[1]}名单？若为抽签，请说明每人的机会或各组名额。']
    report['checks'].append(dict(code='DECLARED_ASSIGNMENT_GAP', state='UNCHECKED', detail=mention[0]))


def citation(row, subject):
    return dict(subject=subject, source=row["source_id"], quote=row["quote"], statement=row["quote"])


def one_row(rows, pattern):
    found = [r for r in rows if re.search(pattern, r["quote"])]
    return found[0] if len(found) == 1 else None


def reported_degree(rows, focus, roster, known):
    """A focal degree may be supplied directly or via a complete, roster-bound list."""
    if not rows:
        return None
    text = rows[-1]["quote"].strip()
    prefix = r"(?:" + re.escape(focus) + r"(?:的)?)?(?:处理前|真实|实际)?"
    n = r"(\d{1,4}|[零一二两三四五六七八九十])"
    degree = re.fullmatch(prefix+r"(?:邻(?:站|店|居)(?:的)?(?:总数|数|数量)|度数)(?:为|是|共|=|＝)?\s*"+n+r"(?:家|个|位|站)?", text)
    if not degree:
        degree = re.fullmatch(n+r"(?:家|个|位|站)?", text)
    if degree:
        value = count(degree[1])
        return value if value is not None and len(known) <= value < len(roster) else None
    listing = re.fullmatch(prefix+r"(?:全部|完整)(?:邻站|邻店|邻居)(?:名单)?(?:是|为|有|[：:])(.+)", text)
    if listing:
        members = [x.strip() for x in re.split(r"[、,，和与]", listing[1])]
        if (len(members) == len(set(members)) and known <= set(members)
                and set(members) <= set(roster)-{focus}):
            return len(members)
    return None


def focal_support(case, docs, replies, table, question_rows):
    q = case["business_question"]
    if table is None or table.completeness != "INCOMPLETE" or not re.search(r"联合(?:概率|机会)", q):
        return
    targets = [unit for unit in table.nodes if unit in q]
    if len(targets) != 1:
        return
    focus, = targets
    known = {b if a == focus else a for a,b in table.edges if focus in (a,b)}
    if not known:
        return
    text = "。".join(r["quote"] for r in docs)
    if (not re.search(r"处理前|抽签前|分配前", table.description)
            or re.search(r"共用|共签|无放回|分层|不独立|并非独立|拟采用|尚未确认|不满足|未确认|无正支持", text)
            or any(re.search(r"抽签|分配|分组|概率|改为|更正|换用",r["quote"]) for r in replies)):
        return
    rate_pattern = r"(?:各自|各(?:站|店|点|单位)?|每(?:站|店|点|个单位))(?:均|都)?以("+RATE+r")(?:的)?概率"
    law = one_row(docs, r"独立(?:抽签|分配|随机)[^。]{0,40}"+rate_pattern)
    mapping = one_row(docs, r"(?:邻站|邻居|邻店)至少(?:一|1)(?:家|个|位)?(?:开启|启用|开通|开放)(?:记|编[码]?|算)为?1")
    available = one_row(docs, r"总体(?:查询|资料).{0,16}(?:真实|实际)邻(?:居|站|店)暴露.{0,18}正支持事件的条件均值")
    science = one_row(docs, r"确认完整分配独立于.{0,10}潜在结果[，,].{0,18}观测结果对应实际完整安排[，,].{0,12}均值有限")
    outcome_row = one_row(docs, r"^[^，,。]{1,30}越[高低]越好$")
    if not all((law, mapping, available, science, outcome_row)):
        return
    rates = re.findall(rate_pattern, text)
    other_rate = any(r != law and re.search(r"(?:抽签|执行|启用|中签).{0,10}概率|概率.{0,8}(?:为|改)",r["quote"])
                     for r in docs)
    if len(rates) != 1 or other_rate:
        return
    try:
        p = read_rate(rates[0])
    except (ValueError, ZeroDivisionError, KeyError):
        return
    if not 0 < p < 1:
        return
    contrast_rows = [(r, ordered_pair(r["quote"], "any", "启用", [focus], table.nodes, [len(known)])) for r in question_rows]
    ordered = [(r, seq) for r, seq in contrast_rows if seq]
    if len(ordered) != 1:
        return
    query, ends = ordered[0]
    if ends[0][0] != ends[1][0] or {ends[0][1], ends[1][1]} != {0,1}:
        return
    low, high = len(known), len(table.nodes)-1
    degree = low if low == high else reported_degree(replies, focus, table.nodes, known)
    own_p = p if ends[0][0] else 1-p
    def probabilities(d):
        none = (1-p)**d
        return [own_p * (1-none if peer else none) for _,peer in ends]
    exact = [str(x) for x in probabilities(degree)] if degree is not None else None
    limits = [[str(min(a,b)), str(max(a,b))] for a,b in zip(probabilities(low),probabilities(high))]
    symbols = [f"({own_p})×(1−({1-p})^d)" if peer else f"({own_p})×({1-p})^d" for _,peer in ends]
    arms = [f"Z={own}, E={peer}" for own,peer in ends]
    outcome = re.split(r"越[高低]越好", outcome_row["quote"])[0]
    estimand = f"E[{outcome} | {arms[0]}] − E[{outcome} | {arms[1]}]"
    desc = (f"{focus}至少有 {low} 位已登记邻居。按原分配在各端的条件分布平均，两个事件均有正支持。"
            f"效应已点识别，依次查询{focus}的两个总体条件均值并相减。")
    support_text = f"令 d 为{focus}真实的处理前邻居数。按所问顺序，两端联合概率为 {symbols[0]} 和 {symbols[1]}。"
    if exact:
        support_text += f" 取 d={degree}，得到 {exact[0]} 和 {exact[1]}。"
    else:
        support_text += f" 现有名单给出 {low} ≤ d ≤ {high}；两端须取同一个 d。"
    conditions = [citation(row,label) for row,label in ((science,"完整分配随机化、一致性与有限均值"),
                  (law,"独立同概率分配"),(mapping,"真实邻居暴露"),(available,"总体条件均值查询"))]
    target = dict(quantity="difference", scope="individual", population=focus, intervention=arms[0], reference=arms[1],
                  outcome=outcome, time=outcome[:2] if re.match(r"次班|次日|次周|本期|当日", outcome) else None)
    questions = [] if exact else [f"请提供{focus}处理前的真实邻居总数，或该站的完整邻居名单。"]
    answer = dict(target=target, status="POINT", functional=estimand+"。"+support_text, reason=desc,
                  value=None, assumptions=conditions,
                  estimate_handoff=dict(mode="ESTIMATE_POINT",population=focus,outcome=outcome,operator=estimand,
                      queries=[dict(kind="population_conditional_mean",unit=focus,own=z,exposure=e,outcome=outcome)
                               for z,e in ends], support=dict(formulas=symbols, probabilities=exact, bounds=limits)))
    proof = dict(method=DEGREE, focus=focus, ordered_events=[list(e) for e in ends], known_neighbors=sorted(known),
                 degree_bounds=[low,high], degree=degree, probabilities=exact, probability_bounds=limits, rate=str(p),
                 network_reference=table.token, sources=[query,law,mapping,science,available,outcome_row,*replies])
    return answer, proof, questions


def invitation_stop(question, docs, replies, table):
    if replies or not re.search(r"(?:不再|不另|不想|不要|不)(?:补设|另加|添加|增加|补充|追加|加设|引入)(?:新|其他|额外)?(?:的)?(?:假设|前提)", question):
        return
    arms = re.search(r"强制([^，,。？?]{1,18}?(?:邻|伙伴)[^，,。？?]{0,8}?)(均|都|全部)(开通|启用|参加|上线)"
                     r"(?:相比|相对|减去)(?:于)?(?:均|都|全部)不\3", question)
    if (not arms or (table is not None and not table.edges) or not re.search(r"(?:可|能|是否).{0,4}点识别",question)
            or re.search(r"另外|另问|再算|同时(?:求|计算)|还想(?:问|知道)",question)):
        return
    active = re.escape(arms[3])
    randomized = one_row(docs, r"(?:只有|仅有).{0,8}邀请.{0,4}随机性[，,].{0,8}(?:未宣称|未假定|不能认为)实际(?:处理|"+active+r")随机")
    choice = one_row(docs, r"(?:自己|自行)决定是否"+active+r".{0,14}(?:不保证|并非完全)(?:遵从|依从).{0,25}"
                           r"(?:未采用|没有|不作).{0,10}排除限制.{0,16}可交换性")
    available = one_row(docs, r"总体(?:资料|档案).{0,8}(?:仅|只)给.{0,10}邀请组.{0,12}未邀请组的平均([^，,。]{1,24})")
    if not all((randomized, choice, available)):
        return
    if any(re.search(r"(?:另有|同时|已经|已获|现已|确认)(?:了)?(?:实际.{0,5}随机|排除限制|可交换性|完全遵从|干预均值)",r["quote"])
           or (r not in (randomized,choice,available) and re.search(r"完全遵从|排除限制|可交换|(?:实际处理|实际开通).{0,5}随机|强制.{0,15}均值",r["quote"])) for r in docs):
        return
    measure = re.search(r"未邀请组的平均([^，,。]{1,24})", available["quote"])[1]
    label = arms[1]
    target = dict(quantity="difference",scope="unspecified",population=None,intervention=label+"均"+arms[3],
                  reference=label+"均不"+arms[3],outcome=measure,time=None)
    reason = (f"抽签分配的是邀请，各站可自行决定是否{arms[3]}。现有总体档案只给按邀请分组的{measure}均值。"
              f"相同邀请组均值可以对应不同的强制{arms[3]}结果，因此所问效果无法点识别。")
    conditions = [citation(r, tag) for r,tag in ((randomized,"分配变量"),(choice,"实际处理选择与假设范围"),(available,"可用总体信息"))]
    answer = dict(status="NOT_POINT",target=target,value=None,functional=reason,reason="按本次限定的资料停止估计。",
                  assumptions=conditions,estimate_handoff=dict(mode="STOP",queries=[],operator=None))
    return answer, dict(method=INVITATION,assigned="邀请",intervention=arms[3], sources=[randomized,choice,available]), []


def apply(case, draft, network, report):
    if (report.get("decision") != "RETAINED" or report.get("proof") or report.get("network_alignment")
            or report.get("condition_review") or report.get("estimation_handoff_allowed")):
        return
    question = case["business_question"]
    if not re.search(r"政策|策略|联合概率|联合机会|点识别", question):
        return
    from .direct_verification import bound_network
    table = bound_network(case, network) if network is not None else None
    study = dict(case, sources=[s for s in case["sources"] if not s["source_id"].startswith(("shared_","uploaded_"))])
    rows = source_lines(study)
    docs = [r for r in rows if r["source_id"] != "question" and not r["source_id"].startswith("user_reply_")]
    replies = [r for r in rows if r["source_id"].startswith("user_reply_")]
    labels = {s["source_id"]:s.get("label") for s in study["sources"]}
    for r in replies:
        if labels[r["source_id"]] == sequential_policy_value.SCOPE_QUESTION:
            r["reply_to"] = sequential_policy_value.SCOPE_QUESTION
    question_rows = [r for r in rows if r["source_id"] == "question"]
    inferred = (sequential_policy_value.evaluate(question, docs, replies, table.nodes if table else ())
                or focal_support(case, docs, replies, table, question_rows)
                or invitation_stop(question, docs, replies, table))
    if not inferred:
        # A reply to this specific worksheet can change the study rather than supply
        # its missing number. Never relabel the old model draft as a current answer.
        if replies and (labels[replies[-1]["source_id"]]==sequential_policy_value.SCOPE_QUESTION
                        or re.fullmatch(r"请提供.+处理前的真实邻居总数，或该站的完整邻居名单。",labels[replies[-1]["source_id"]] or "")):
            report.pop("parts",None)
            report.update(decision="WITHHELD",effective_answer=None,conditional_answer=None,clarification_questions=[],
                          estimation_handoff_allowed=False,scientific_approval=False)
            report["checks"].append(dict(code="REVISED_MATERIALS",state="CONFLICT",evidence=replies,
                detail="补充说明更改了原计算所用的材料。当前无法复算修改后的目标，请按更新的材料重新读题。"))
        return
    answer, proof, questions = inferred
    for key in ("parts", "draft_parts"):
        report.pop(key,None)
    report.update(effective_answer=answer, conditional_answer=None, proof=proof, clarification_questions=questions,
                  decision="CONDITIONAL_RESULT" if questions else "CORRECTED",
                  estimation_handoff_allowed=False, scientific_approval=False)
    report["checks"].append(dict(code=proof["method"], state="CHECKED", detail=answer["functional"]))
