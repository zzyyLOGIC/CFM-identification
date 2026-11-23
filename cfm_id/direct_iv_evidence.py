"""Conditional exact checks for an explicitly supplied, self-contained binary-IV study.

The input is part of the researcher's original materials, equally visible to a direct
answerer. A model's assertions never populate the law, the target or the assumptions.
"""
import json
import re
from fractions import Fraction
from itertools import product

from .iv_ate_solver import solve_ate_bounds
from .iv_ate_verify import verify_ate_result
from .iv_contract import validate_observed, IVInputError

FORMAT="causal-id.binary-iv/1"
TOP={"format","question","population","period","outcome_label","roles","target","information","assumptions","additional_restrictions","complete_for_declared_model"}
CONDS={"instrument_independence","exclusion","consistency","no_interference","instrument_support","monotonicity","actual_randomization"}

def unique_keys(pairs):
    obj={}
    for k,v in pairs:
        if k in obj:raise ValueError("DUPLICATE_FIELD")
        obj[k]=v
    return obj

def read_declaration(case):
    sources=case.get("sources",[])
    found=[]
    for source in sources:
        text=source.get("text","").strip()
        if not text.startswith("{") or FORMAT not in text:continue
        try:doc=json.loads(text,object_pairs_hook=unique_keys)
        except (ValueError,RecursionError):return None,"INVALID_DECLARATION"
        if isinstance(doc,dict) and doc.get("format")==FORMAT:found.append(doc)
    if not found:return None,"NO_STRUCTURED_IV_DECLARATION"
    if len(found)!=1 or len(sources)!=1:return None,"ADDITIONAL_SOURCE_REQUIRES_REVIEW"
    doc=found[0]
    if set(doc)!=TOP or doc["question"]!=case["business_question"] or doc["complete_for_declared_model"] is not True:
        return None,"DECLARATION_SCOPE_REQUIRES_REVIEW"
    if doc["additional_restrictions"]!=[]:return None,"ADDITIONAL_RESTRICTIONS_REQUIRE_REVIEW"
    roles=doc["roles"];target=doc["target"];info=doc["information"];a=doc["assumptions"]
    if not all(isinstance(s,str) and s.strip() for s in (doc["population"],doc["period"],doc["outcome_label"])):
        return None,"TARGET_SCOPE_REQUIRED"
    if not isinstance(roles,dict) or set(roles)!={"instrument","treatment","outcome"} or not all(
        isinstance(v,str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,15}",v) for v in roles.values()) or len(set(roles.values()))!=3:
        return None,"BINARY_VARIABLE_ROLES_REQUIRED"
    if (not isinstance(target,dict) or set(target)!={"type","treated","reference"} or target["type"] not in ("ATE","LATE")
        or any(type(target[k]) is not int for k in ("treated","reference")) or {target["treated"],target["reference"]}!={0,1}):
        return None,"TARGET_OR_DIRECTION_REQUIRED"
    if not isinstance(a,dict) or set(a)!=CONDS or a["instrument_independence"]!=roles["instrument"] or any(
        a[k]!="adopted" for k in ("exclusion","consistency","no_interference")) or a["instrument_support"]!="both_positive":
        return None,"IV_ASSUMPTIONS_NOT_DECLARED"
    if a["actual_randomization"]!="not_claimed" or a["monotonicity"] not in ("nondecreasing","not_imposed"):
        return None,"MODEL_RESTRICTIONS_REQUIRE_REVIEW"
    if target["type"]=="LATE" and a["monotonicity"]!="nondecreasing":return None,"LATE_MONOTONICITY_NOT_DECLARED"
    if not isinstance(info,dict) or set(info)!={"kind","row_variable","cell_variables","cell_order","rows"} or (
        info["kind"]!="binary_population_conditional_law" or info["row_variable"]!=roles["instrument"] or
        info["cell_variables"]!=[roles["treatment"],roles["outcome"]]):
        return None,"EXACT_POPULATION_LAW_REQUIRED"
    order=info["cell_order"];rows=info["rows"]
    if not isinstance(order,list) or len(order)!=4 or not all(isinstance(k,str) for k in order) or set(order)!={"00","01","10","11"}:
        return None,"INVALID_CELL_COORDINATES"
    if not isinstance(rows,dict) or set(rows)!={"0","1"} or not all(isinstance(row,list) and len(row)==4 for row in rows.values()):
        return None,"INCOMPLETE_BINARY_ROWS"
    if not all(isinstance(p,str) and len(p)<=100 and re.fullmatch(r"(?:\d+/\d+|\d*\.?\d+(?:[Ee][+-]?\d{1,2})?)",p) for row in rows.values() for p in row):
        return None,"EXACT_CELLS_REQUIRED"
    try:
        law=validate_observed({(int(z),int(code[0]),int(code[1])):p for z,row in rows.items() for code,p in zip(order,row)})
    except (IVInputError,ArithmeticError,ValueError):
        return None,"INVALID_CONDITIONAL_LAW"
    return (doc,law),"DECLARED"

def conditional_answer(doc,law):
    from cfm_id_llm.compact_study import digest
    roles=doc["roles"];z,d,y=(roles[k] for k in ("instrument","treatment","outcome"))
    target=doc["target"];mono=doc["assumptions"]["monotonicity"]=="nondecreasing"
    sol=solve_ate_bounds(law,monotonicity=mono)
    if not verify_ate_result(law,sol,monotonicity=mono)["valid"]:raise ValueError("IV_REPLAY_FAILED")
    sign=1 if target["treated"]==1 else -1
    late=target["type"]=="LATE";scope="compliers" if late else "whole"
    population=doc["population"]+("中仅在工具从0变为1时才接受处理的依从者" if late else "")
    t=dict(quantity="difference",scope=scope,population=population,intervention=f"{d}={target['treated']}",
           reference=f"{d}={target['reference']}",outcome=doc["outcome_label"],time=doc["period"])
    science=[f"{z} 与潜在处理及潜在结果独立",f"{z} 只通过 {d} 影响 {y}","一致性及无单位间干扰","二元变量，两种工具状态均有正支持"]
    if mono:science.append(f"{d}(1)≥{d}(0)")
    value=None;mode="STOP"
    support=f"P({z}=0)>0, P({z}=1)>0"
    operator=f"按 {z} 两层取总体 P({d},{y}|{z})，按原坐标交接"
    if sol["status"]=="INCOMPATIBLE":
        status="INCOMPATIBLE"; cert=sol["certificate"]
        formula="不存在与采用的条件和这八格总体概率同时相容的潜在类型分布。"
        reason="可重放的不相容对偶证据，严格矛盾幅度为 "+cert["exact_margin"]+"。"
        if mono:
            for treatment,response in product(range(2),repeat=2):
                low,high=(1,0) if treatment==0 else (0,1)
                excess=law[low,treatment,response]-law[high,treatment,response]
                if excess>0:
                    reason+=f"单调与排除要求 ({d},{y})=({treatment},{response}) 在 {z}={low} 层的概率不超过 {z}={high} 层，实为 {law[low,treatment,response]} 对 {law[high,treatment,response]}，超出 {excess}。"
                    break
    elif late:
        first=sum((2*k-1)*a*p for (k,a,b),p in law.items())
        itt=sum((2*k-1)*b*p for (k,a,b),p in law.items())
        if first==0:
            acceptance=[sum(law[k,1,b] for b in range(2)) for k in range(2)]
            status="UNDEFINED";formula=f"P(C)=P({d}=1|{z}=1)−P({d}=1|{z}=0)={acceptance[1]}−{acceptance[0]}=0"
            reason="总体律可相容；单调性下依从者质量为零，条件效应无定义。"
        else:
            if first<0:raise ValueError("IV_FIRST_STAGE_REPLAY_FAILED")
            v=sign*itt/first;w=list(map(Fraction,sol["exact"]["lower_witness"]))
            check=sum(p*(b1-b0) for (a0,a1,b0,b1),p in zip(sol["types"],w) if a0==0 and a1==1)
            if check!=itt or sum(p for (a0,a1,_,__),p in zip(sol["types"],w) if a0==0 and a1==1)!=first:
                raise ValueError("IV_WITNESS_REPLAY_FAILED")
            status="POINT";mode="ESTIMATE_POINT";value=str(v)
            formula=f"({sign}) × (E[{y}|{z}=1]−E[{y}|{z}=0])/(E[{d}|{z}=1]−E[{d}|{z}=0])"
            reason=f"结果差 {itt}，一阶段 {first}，对应目标方向的 Wald 商为 {v}。"
            support+=f"，依从者质量={first}>0";operator+="，计算结果差和一阶段的商"
    else:
        bounds=list(map(Fraction,sol["exact"]["bounds"]))
        lo,hi=bounds if sign==1 else [-bounds[1],-bounds[0]]
        status="POINT" if lo==hi else "PARTIAL";mode="ESTIMATE_POINT" if lo==hi else "ESTIMATE_BOUNDS"
        value=str(lo) if lo==hi else [str(lo),str(hi)]
        formula=f"在相容类型 t=({d}0,{d}1,{y}0,{y}1) 质量 p_t 上求 {sign}×Σp_t({y}1−{y}0) 的最小和最大值；Σ_{{t:Dz=a,Ya=b}}p_t=P({d}=a,{y}=b|{z}=z)，p_t≥0。"
        reason=f"两端 {lo}、{hi} 均由附带的非负潜在类型分布达到，且通过独立对偶检查。"
    answer=dict(target=t,status=status,functional=formula,value=value,assumptions=science,
                estimate_handoff=dict(mode=mode,scope=scope,population=population,variables=[z,d,y],operator=operator,support=support),reason=reason)
    return answer,dict(type="binary_iv",source_sha256=digest(doc),conditional_on_declared_model=True,
                       checked="exact_population_law_and_target",solver=sol)
