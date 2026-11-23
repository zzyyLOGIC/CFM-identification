"""Two exhaustive groups with known population arm means and an unknown target weight."""
from fractions import Fraction
import re

from .network_grounded_contrast import source_lines


METHOD="POPULATION_WEIGHTED_SAVINGS"
NAME=r"[\w\u3400-\u9fff]{1,12}?(?:名单|方案|菜单|计划|政策|案)"
NUMBER=r"[−-]?(?:\d+/\d+|\d+(?:\.\d+)?)"


def label(value):
    return re.sub(r"(?:名单|方案|菜单|计划|政策|案)$","",value)


def apply(case,draft,report):
    rows=source_lines(case)
    qrows=[r for r in rows if r["source_id"]=="question"]
    relation=r"(?:相对(?:于)?|相比(?:于)?|比)"
    amount=r"(?:节约|节省|少花|省下)(?:了)?"
    units=r"(分钟|小时|秒|元)"
    matches=[(r,m) for r in qrows for m in [re.fullmatch(
        r"(?P<a>"+NAME+r")"+relation+r"(?P<b>"+NAME+r")[，,]?(?:在)?(?:全体|所有)(?:成员|对象|单位|用户)"
        r"(?:中)?(?:的)?(?:平均)?(?:能|可)?"+amount+r"(?:多少"+units+r"|"+units+r"(?:数|金额)?(?:是多少|为多少|多少))",r["quote"])] if m]
    if len(matches)!=1 or any(re.search(r"减去|反过来|另一个|改用|另问|第二问",r["quote"]) for r in qrows):
        return
    q,m=matches[0]
    intervention,reference,unit=m["a"],m["b"],m[3] or m[4]
    if label(intervention)==label(reference):
        return
    docs=[r for r in rows if r["source_id"]!="question" and not r["source_id"].startswith(("user_reply_","shared_","uploaded_"))]
    def evidence(pattern):
        return [r for r in docs if re.search(pattern,r["quote"])]
    science=evidence(r"(?:公平|随机)抽签.{0,20}独立于.{0,8}潜在结果.{0,16}按抽中(?:名单|方案)记录")
    partition=evidence(r"两类.{0,8}固定.{0,4}互斥且穷尽")
    availability=evidence(r"精确总体(?:量|均值)|精确的总体(?:量|均值)")
    target=evidence(r"(?:所有|全体).{0,5}(?:每人|各对象|各单位)等权")
    if not (science and partition and availability and target and evidence(r"(?:两案|两种方案|两份名单)均(?:有支持|存在)")
            and evidence(r"(?:不知道|未知|待补|未提供).{0,22}(?:占比|人数|权重)")):
        return
    if evidence(r"不独立|并非独立|未确认|只是样本|非总体|仅为样本|还包括|固定各半|采用各半|权重已知"):
        return
    pattern=(r"(?:^|[，,])([^，,。；]{1,12}?类)在("+NAME+r")[和与]("+NAME+r")"
             r"(?:的)?(?:平均|均值)(?:分别)?为("+NUMBER+r")[和与]("+NUMBER+r")"+re.escape(unit))
    pairs=[]
    for r in docs:
        for s in re.finditer(pattern,r["quote"]):
            groups={label(s[2]):Fraction(s[4].replace("−","-")),label(s[3]):Fraction(s[5].replace("−","-"))}
            if set(groups)!={label(intervention),label(reference)}:
                return
            pairs.append((s[1],groups[label(reference)]-groups[label(intervention)],r))
    if len(pairs)!=2 or pairs[0][0]==pairs[1][0]:
        return
    (u,a,_),(v,b,_)=pairs
    slope=a-b
    formula=(str(slope)+"p"+(f"+{b}" if b>0 else str(b) if b else "")) if slope else str(b)
    lo,hi=sorted((a,b))
    question=f"请提供{u}在目标全体中的占比 p，或{u}与{v}各自的成员人数。"
    responses=[r for r in rows if r["source_id"].startswith("user_reply_")]
    weight=None
    for r in responses[-1:]:
        reply=r["quote"].strip()
        percent=re.fullmatch(r"(?:p|"+re.escape(u)+r"(?:成员)?(?:的)?占比)\s*(?:=|＝|为|是)\s*("+NUMBER+r")(%|％)?",reply,re.I)
        counts=re.fullmatch(re.escape(u)+r"\s*(\d+)人[，,、和与]\s*"+re.escape(v)+r"\s*(\d+)人",reply)
        if percent:
            try:
                candidate=Fraction(percent[1].replace("−","-"))/(100 if percent[2] else 1)
            except (ValueError,ZeroDivisionError):
                break
        elif counts and int(counts[1])+int(counts[2])>0:
            candidate=Fraction(int(counts[1]),int(counts[1])+int(counts[2]))
        else:
            weight=None
            break
        if not 0<candidate<1:
            weight=None
            break
        weight=candidate
    value=b if slope==0 else None if weight is None else b+slope*weight
    citations=[dict(source=r["source_id"],quote=r["quote"],statement=r["quote"]) for r in (science[0],partition[0],availability[0],target[0])]
    direction=f"{reference}的均值减去{intervention}的均值"
    text=f"节约量按{direction}。{u}节约 {a} {unit}，{v}节约 {b} {unit}。令 p 为{u}占比，平均节约量为 p×({a})+(1−p)×({b}) = {formula} {unit}。"
    bounds=f"下确界为 {lo}，上确界为 {hi} {unit}。"
    if slope:
        bounds+="两类均占正比例时，两个端点均不能取到。"
    status="NEEDS_INPUT" if value is None else "POINT"
    ans=dict(status=status,target=dict(quantity="difference",scope="whole",population="全体成员每人等权",
             intervention=intervention,reference=reference,outcome="平均节约"+unit+"数",time=None),
             question_part=q["quote"],functional=text+bounds,value=None if value is None else str(value),assumptions=citations,
             reason=question if value is None else f"平均节约量为 {value} {unit}。",
             estimate_handoff=dict(mode="STOP" if value is None else "EXACT_POPULATION_VALUE",queries=[],operator=formula,
                 group_contrasts={u:str(a),v:str(b)},weight_parameter=dict(name="p",group=u,value=None if weight is None else str(weight)),
                 closure=[str(lo),str(hi)],point_reason="两个已给总体差按目标成员比例加权"))
    for key in ("parts","network_alignment","condition_review","draft_parts"):
        report.pop(key,None)
    proof=dict(method=METHOD,ordered_policies=[reference,intervention],strata=[u,v],unit=unit,
               differences=[str(a),str(b)],closure=[str(lo),str(hi)],direction="REFERENCE_MINUS_INTERVENTION",
               sources=[q,science[0],partition[0],target[0],*(x[2] for x in pairs),*responses])
    report.update(decision="CORRECTED" if draft else "CONDITIONAL_RESULT",effective_answer=ans,conditional_answer=None,
                  proof=proof,clarification_questions=[question] if value is None else [],
                  estimation_handoff_allowed=False,scientific_approval=False)
    report["checks"].append(dict(code=METHOD,state="CHECKED",detail=text+bounds))
