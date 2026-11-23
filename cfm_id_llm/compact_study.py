"""One source-bound study reading, shared by all candidate methods."""
import hashlib
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError

CONDITIONS={
    "consistency":"实际观察与对应干预的潜在结果一致",
    "no_interference":"不同单位之间无干扰",
    "randomization":"整个原处理名单独立于潜在结果",
    "fixed_network":"网络为干预前固定的完整研究网络",
    "finite_means":"所需均值存在且有限",
    "mean_sufficiency":"全部完整安排中，同单位同局部状态的潜在结果均值相同",
    "iv_independence":"工具与潜在处理及结果独立",
    "exclusion":"工具只经实际处理影响结果",
    "monotonicity":"每人 D(1)≥D(0)",
    "instrument_support":"工具的两种取值均有正概率",
    "causal_graph":"采纳所列完整递归因果图及其外生误差模型",
    "positive_joint":"有关观测总体联合分布严格为正",
}
class Record(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)
class Target(Record):
    kind:Literal["policy_mean","local_difference","do_risk","late","ate","other","unclear"]
    population:str
    outcome:str
    treatment:str
    context:str
    comparison:str
    quote:str
class Graph(Record):
    nodes:list[str]
    directed:list[list[str]]
    bidirected:list[list[str]]
    x:str
    y:str
    x_value:Literal[0,1]
    y_value:Literal[0,1]
    binary:bool
    info:Literal["positive_population_joint","population_joint","sample","unknown"]
    quote:str
class IV(Record):
    z:str
    d:str
    y:str
    binary:bool
    cells:list[list[str]]  # conditional population table only, z rows, then d,y.
    quote:str
class Network(Record):
    nodes:list[str]
    edges:list[list[str]]
    design:Literal["fixed_quota","independent","unknown"]
    quota:int|None=None
    probabilities:dict[str,str]=Field(default_factory=dict)
    outcome_kind:Literal["binary","count","continuous","unknown"]
    exposure:Literal["majority","count","any","none","unknown"]
    weights:list[str]
    policy:list[int]=Field(default_factory=list)
    arms:list[list[int]]=Field(default_factory=list)
    full:list[dict]=Field(default_factory=list)
    local:list[dict]=Field(default_factory=list)
    quote:str
class Reading(Record):
    target:Target
    assumptions:dict[str,str]
    graph:Graph|None=None
    iv:IV|None=None
    network:Network|None=None
    restrictions:list[str]=Field(default_factory=list)
    gaps:list[str]=Field(default_factory=list)

GUIDE="""你在填写一份供研究者核对的规格，只摘取事实，不求解。输出一个符合下列结构的JSON对象。顶层只能有这七个键：
{"target":{"kind":"unclear","population":"","outcome":"","treatment":"","context":"","comparison":"","quote":""},"assumptions":{},"graph":null,"iv":null,"network":null,"restrictions":[],"gaps":[]}
以上为空表。用材料填写target内部的七项，时间放在context内，范围和方向放在population、comparison内；不要自行另建字段。没有相关资料的整块必须为null，有相关资料时按下文填写。如有多种资料可同时填写。不要输出答案或识别状态。
target={kind,population,outcome,treatment,context,comparison,quote}。kind取policy_mean(完整名单均值)、local_difference(原设计局部臂差)、do_risk(指定干预后指定结果概率)、late(服从者)、ate(全体实际处理平均效应)、other、unclear。分期DiD的ATT、断点局部效应使用other。给出方向及范围、时间。quote逐字摘录题面。
assumptions是{条件名:逐字原文片段}，只列原文已明确采用或可从文字直接得知的条件。同一引用可对应多个条件。拒绝、否定和未知不能填入。只准使用下列键：
"""
GUIDE+="水平题保留指定名单，禁止补造对照；依从者与全体保持原意；干预或总体未定义时只记录已知部分。\n"
GUIDE+="IV 题逐项核对主语。iv_independence 引工具的独立性声明；randomization 只有实际处理本身有单独的随机分配证据才填写。\n"
GUIDE+="\n".join(f"{k}={v}" for k,v in CONDITIONS.items())
GUIDE+="""
各块quote逐字引用原文，不添加省略号。概率、权重、均值均按原值用字符串（包括精确小数）。材料没有的数值不得编造。额外模型限制写入restrictions，缺少决定目标或解释数据的内容写入gaps，均为字符串列表。完整性、零支持和未采纳其他假设本身不算额外限制。
graph={nodes:[观测变量名],directed:[[起,终]],bidirected:[[一,二]],x,y,x_value:0或1,y_value:0或1,binary:true或false,info:positive_population_joint/population_joint/sample/unknown,quote}。保留完整图，选择样本不能写成总体律。
iv={z:工具列名,d:实际处理列名,y:结果列名,binary:true或false,cells:[[四个概率字符串],[四个概率字符串]],quote}。只填已知总体 P(D,Y|Z)，Z依次0、1，每行按(D,Y)=00,01,10,11；缺表给[]，不要用样本估计填充。
network={nodes:[按来源顺序的单位],edges:[[节点,节点]],design:fixed_quota/independent/unknown,quota:整数或null,probabilities:{节点:概率字符串},outcome_kind:binary/count/continuous/unknown,exposure:majority/count/any/none/unknown,weights:[节点权重字符串],policy:[按节点顺序0或1],arms:[[本人,暴露],[本人,暴露]],full:[{z:[完整名单0或1],means:[各节点总体均值字符串]}],local:[{own:0或1,peer:暴露整数,means:[各节点总体均值字符串]}],quote}。等权可写各项分数如"1/3"。无此信息给空列表；局部差的arms先被减数后减数。只有指定完整名单的目标才填policy。只收总体均值，不能把样本列成exact。"""


def materials(case):
    return [{"source_id":"question","text":case["business_question"]}]+[
        {"source_id":s["source_id"],"text":s["text"]} for s in case["sources"]]


def request(case):
    return {"system_prompt":GUIDE,"user_prompt":json.dumps(materials(case),ensure_ascii=False)}


def digest(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def inspect(raw,case):
    if not isinstance(raw,dict):
        return {"target":"未返回研究规格的JSON对象"}
    try:
        record=Reading.model_validate(raw)
    except ValidationError as exc:
        found={}
        for err in exc.errors(include_input=False):
            loc=err["loc"]
            key=str(loc[0]) if loc else "target"
            found.setdefault(key,[]).append(".".join(map(str,loc))+" "+err["type"])
        return {key:", ".join(messages) for key,messages in found.items()}
    docs=materials(case)
    issues={}
    def cited(text):return isinstance(text,str) and len(text.strip())>=2 and any(text in s["text"] for s in docs)
    if not cited(record.target.quote):issues["target"]="目标引用无法在题面或附件中原样定位"
    for code,quote in record.assumptions.items():
        if code not in CONDITIONS or not cited(quote):issues["assumptions"]="条件名或条件所引原句无法核对："+code
    for name in ("graph","iv","network"):
        part=getattr(record,name)
        if part and not cited(part.quote):issues[name]="该资料块的引用无法逐字定位"
    g=record.graph
    if g and (g.x==g.y or not {g.x,g.y}<=set(g.nodes) or len(g.nodes)!=len(set(g.nodes)) or
              any(len(edge)!=2 or not set(edge)<=set(g.nodes) for edge in g.directed+g.bidirected)):
        issues["graph"]="变量清单与边或干预/结果坐标不一致"
    iv=record.iv
    if iv and "randomization" in record.assumptions:
        from .target_evidence import assigned_subjects,located_statements
        contexts=located_statements(record.assumptions["randomization"],[s["text"] for s in docs])
        subjects=set().union(*(assigned_subjects(s) for s in contexts))
        if iv.d not in subjects:
            issues["assumptions"]=f"请定位实际处理 {iv.d} 本身的分配声明。仅有工具 {iv.z} 随机的证据时移除 randomization。"
    if iv and iv.cells:
        from cfm_id.iv_contract import validate_observed
        try:
            if len(iv.cells)!=2 or any(len(row)!=4 for row in iv.cells):raise ValueError()
            validate_observed({(z,k//2,k%2):v for z,row in enumerate(iv.cells) for k,v in enumerate(row)})
        except (ValueError,ArithmeticError):issues["iv"]="核对原表坐标和精确行和，不能修正原表"
    n=record.network
    if n:
        from fractions import Fraction
        try:
            count=len(n.nodes)
            if not 1<=count<=64 or len(set(n.nodes))!=count:raise ValueError()
            if len(n.weights)!=count or min(map(Fraction,n.weights))<0 or sum(map(Fraction,n.weights))!=1:raise ValueError()
            if any(len(e)!=2 or e[0]==e[1] or not set(e)<=set(n.nodes) for e in n.edges):raise ValueError()
            if len({tuple(sorted(e)) for e in n.edges})!=len(n.edges):raise ValueError()
            if n.design=="fixed_quota" and (n.quota is None or not 0<=n.quota<=count):raise ValueError()
            if n.design=="fixed_quota" and n.probabilities:
                if (not set(n.probabilities)<=set(n.nodes) or
                        any(Fraction(value)!=Fraction(n.quota,count) for value in n.probabilities.values())):
                    raise ValueError()
            if n.design=="independent" and (set(n.probabilities)!=set(n.nodes) or any(not 0<=Fraction(x)<=1 for x in n.probabilities.values())):raise ValueError()
            def binary(z):return isinstance(z,list) and len(z)==count and all(type(x) is int and x in (0,1) for x in z)
            if record.target.kind=="policy_mean" and not binary(n.policy):raise ValueError()
            if record.target.kind=="local_difference" and (len(n.arms)!=2 or any(len(a)!=2 or a[0] not in (0,1) for a in n.arms)):raise ValueError()
            for rows,fields in ((n.full,{"z","means"}),(n.local,{"own","peer","means"})):
                seen=set()
                for row in rows:
                    if set(row)!=fields or len(row["means"])!=count or not all(isinstance(v,str) for v in row["means"]):raise ValueError()
                    for v in row["means"]:
                        num=Fraction(v)
                        if n.outcome_kind=="binary" and not 0<=num<=1:raise ValueError()
                    if "z" in row:
                        if not binary(row["z"]):raise ValueError()
                        coord=tuple(row["z"])
                    else:
                        if type(row["own"]) is not int or row["own"] not in (0,1) or type(row["peer"]) is not int:raise ValueError()
                        coord=(row["own"],row["peer"])
                    if coord in seen:raise ValueError()
                    seen.add(coord)
        except (ValueError,KeyError,TypeError,ZeroDivisionError):issues["network"]="请核对单位、权重、设计、边或已列总体均值的坐标和长度"
    return issues


def focus_fields(raw, issues):
    allowed=set(Reading.model_fields)
    extras=sorted(set(raw)-allowed) if isinstance(raw,dict) else []
    keys=set(issues)&allowed
    if extras:
        # Preserve substantive material from misplaced fields for the researcher's review.
        keys.update(("target","restrictions","gaps"))
    return sorted(keys),extras


def focus(case,raw,issues):
    keys,extras=focus_fields(raw,issues)
    if not keys:
        return None
    instructions="这是定点复核。仅返回下列指定键及其完整替换值："+",".join(keys)+"。未争议的字段保持原样。"
    if extras:
        instructions+="多余键已列在unexpected中。将其中属于目标、额外限制或缺口的信息归入指定字段；另返回remove_extras字符串列表，逐项确认移除所有多余键。保留原文中的未知。"
    return dict(system_prompt=GUIDE+"\n"+instructions,
        user_prompt=json.dumps(dict(disputes=issues,unexpected=extras,
            current={k:raw.get(k) for k in keys+extras} if isinstance(raw,dict) else {},
            sources=materials(case)),ensure_ascii=False))


def apply_focus(raw, change, issues):
    keys,extras=focus_fields(raw,issues)
    required=set(keys)|({"remove_extras"} if extras else set())
    if not isinstance(raw,dict) or not isinstance(change,dict) or set(change)!=required:
        return raw
    if extras:
        removed=change["remove_extras"]
        if not isinstance(removed,list) or not all(isinstance(x,str) for x in removed) or sorted(removed)!=extras:
            return raw
    return {**{k:v for k,v in raw.items() if k not in extras},**{k:change[k] for k in keys}}
