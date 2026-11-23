"""Conservative checks on explicit target and randomization language, with abstention."""
import re
import unicodedata

VAR = r"(?<![A-Za-z0-9_])([A-Za-z][A-Za-z0-9_]{0,15})(?![A-Za-z0-9_])"
RELATION = r"(?:接受|被|系|是|为|由|按|通过|经|采用|独立|实际|被研究者|公开|公平|硬币|等概率|的|方案|分配|指派|确定|\s)*"
RANDOM = r"(?:随机(?:分配|指派|抽取|决定)?|抽签|掷币|抛硬币)"
NEG = re.compile(r"未|不(?:是|由|采用|假定|接受|能|可|足以|代表|随机)|不(?:据此|据以|表示|表明|意味着|等于|由此|声称|主张|推断|蕴含|构成)|无(?:证据|依据)|拒绝|尚待|未知|假如|如果|是否|假设若|没有|并非|does not|not randomized", re.I)
SUBJECT = [
    re.compile(VAR + r"\s*(?:与|独立于|is independent of|is randomized|was randomly assigned)", re.I),
    re.compile(VAR + RELATION + RANDOM),
    re.compile(RANDOM + r"(?:分配|指派|决定|的是|的是对|实际|施加|邀请|提醒|资格|治疗|用药|采用|操作|接受|处理|\s)*" + VAR),
]
def normalized(value):
    return unicodedata.normalize("NFKC", value).strip() if isinstance(value,str) else ""

def statements(text):
    return [s.strip() for s in re.split(r"[。！？；;\n]",normalized(text)) if s.strip()]

def located_statements(quote, sources):
    quote=normalized(quote).strip('。；;.! ')
    if not quote:
        return []
    found=[]
    for s in sources:
        body=normalized(s)
        if quote not in body:
            continue
        for sentence in statements(body):
            if sentence in quote or quote in sentence:
                found.append(sentence)
    return found

def assigned_subjects(text):
    positive=set()
    for phrase in re.split(r"[,，；;。!\n]",normalized(text)):
        if NEG.search(phrase):
            continue
        for pattern in SUBJECT:
            for match in pattern.finditer(phrase):
                # “A 与 B” is an independence claim only when independence is actually stated.
                if "与" in match.group() and ("独立" not in phrase or "潜在" not in phrase):
                    continue
                token=match.group(1)
                if token.lower() not in {"is","was","of","the","and","independent"}:
                    positive.add(token)
    return positive

def explicitly_unrandomized(text):
    pattern=VAR+r"\s*(?:并非随机|不是随机|未随机|不随机|由(?:个人|用户|学员|本人|顾客|医生|病人)(?:按[^，。；;]{0,10})?(?:自行|自己|自主)?(?:选择|决定))"
    return {m[1] for m in re.finditer(pattern,normalized(text))}

def requested_receipt_as_assignment(question, target):
    """Use only an explicit receipt contrast and two unambiguous assignment descriptions."""
    if not isinstance(target, dict):
        return False
    q = normalized(question)
    receipt = re.search(r"实际(?:参加|接受|使用|处理|治疗|购买|接种).{0,28}(?:相对|相比|减去)|(?:培训|治疗|接受服务)带来的平均", q)
    if not receipt:
        return False
    def assignment_arm(value):
        text = normalized(value)
        # A direct statement of receipt remains receipt even when access is described later.
        if re.match(r"^(?:实际|强制|直接|接受|参加|不参加|未参加|不接受|未接受|施加|使用|不使用)", text):
            return False
        return bool(re.search(r"(?:获得|获分配|收到|抽中|接到|发出|发放|给予|取得|取消|分配)(?:了|的)?[^,，。;；()]{0,8}(?:通知|邀请|资格)|^(?:未获邀|获邀)(?:$|[ (])", text))
    return all(assignment_arm(target.get(field)) for field in ("intervention", "reference"))


def target_cues(question):
    text=normalized(question)
    excluded=r"(?:不问|无需|不要计算|不求|不要求|不能把|不应将|不是(?:要问|针对)?|并非(?:要问|针对)?)[^，。；;？?\n]*"
    scope_text=re.sub(excluded,"",text)
    quotations=[line.strip()[1:].strip() for line in text.splitlines() if line.lstrip().startswith(">")]
    active=re.sub(excluded,""," ".join(quotations)) if quotations else scope_text
    level=bool(re.search(r"平均水平|风险水平|平均(?:箱数|件数|耗时|等待时间|数量|出库量|完成量)|均值是多少|总体概率|达标率是多少|风险是多少|水平为多少|政策均值",active))
    contrast=bool(re.search(r"之差|风险差|率差|差值|效应|减去|相比|相对.{0,18}的差",active))
    pending=r".{0,5}(?:尚未确定|尚未选定|待确认|待定|未确定)"
    unresolved=bool(re.search(r"(?:干预|比较对象)"+pending,active))
    unresolved_scope=bool(re.search(r"(?:研究总体|目标总体|人群)"+pending,scope_text))
    quantity="unknown" if unresolved else ("level" if level and not contrast else "difference" if contrast and not level else None)
    complier=bool(re.search(r"依从者|遵从者|服从者|仅因.{0,12}(?:才|而)(?:接受|参加|采用|使用)|仅对有.{0,8}才会",scope_text))
    whole=bool(re.search(r"全体|全部|整个队列|整个总体|全队列|所有入组",scope_text))
    scope="unknown" if unresolved_scope else "compliers" if complier else "whole" if whole else None
    return {"quantity":quantity,"scope":scope}
