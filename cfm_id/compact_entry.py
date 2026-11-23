"""Deterministic matching and reviewed dispatch for one source-bound study reading."""
from copy import deepcopy
from fractions import Fraction
from . import dag_id_solver, dag_id_verify, dag_backdoor_solver, dag_backdoor_verify
from .dag_id_contract import DagIdProblem
from .dag_backdoor_contract import BackdoorProblem, PopulationLaw, Unavailable
from .iv_route_contract import IVProblem, IVReview, VERSION, READING_DECISIONS, science_decisions, digest as iv_digest
from . import iv_research
from cfm_id_llm.compact_study import Reading, CONDITIONS, digest, inspect, materials
from .compact_review import reading_items, external_scope, IV_SCIENCE, method_name, LOCAL_CONTRAST, FULL_POLICY, EXPOSURE_POLICY


def stop(state,reason,questions=()):
    return dict(state=state,reason_code=reason,clarification_questions=list(questions),backend_called=False,
                independent_replay=False,mathematical_claim=None,estimate_handoff=dict(mode="STOP",reason=reason),
                scientific_approval=False,estimation_handoff_allowed=False,production_admission=False)


def plan(case,raw):
    issues=inspect(raw,case)
    if issues:return stop("READING_RECHECK_REQUIRED","SOURCE_OR_SCHEMA_DISAGREEMENT",issues.values())
    s=Reading.model_validate(raw)
    t=s.target
    methods=[]
    def add(method,requirements,extra=()):
        missing=[CONDITIONS[k] for k in requirements if k not in s.assumptions]
        methods.append(dict(method=method,conditions=list(requirements),missing=[*missing,*extra]))
    if t.kind=="do_risk" and s.graph:
        g=s.graph
        gap=[] if g.info=="positive_population_joint" and g.binary else ["需要目标总体上有正支持的完整观测联合律及二元变量声明"]
        for name in ("BACKDOOR","GENERAL_ID"):
            add(name,["causal_graph","consistency","no_interference","positive_joint"],gap)
    if t.kind in ("late","ate") and s.iv:
        keys=["iv_independence","exclusion","consistency","no_interference","instrument_support"]
        if t.kind=="late" or "monotonicity" in s.assumptions:keys+=["monotonicity"]
        gap=[] if s.iv.binary and s.iv.cells else ["需要明确二元Z、D、Y的完整目标总体条件律 P(D,Y|Z)"]
        add("IV_"+t.kind.upper(),keys,gap)
    if t.kind in ("policy_mean","local_difference") and s.network:
        n=s.network;keys=["randomization","consistency","fixed_network"]
        if n.outcome_kind!="binary":keys+=["finite_means"]
        gaps=[] if n.design in ("fixed_quota","independent") and n.outcome_kind!="unknown" else ["需要可计算的原分配律及结果类型"]
        if t.kind=="policy_mean":
            add(FULL_POLICY,keys,gaps+([] if any(r["z"]==n.policy for r in n.full) else ["缺少目标完整名单的总体条件均值"]))
            add(EXPOSURE_POLICY,keys+["mean_sufficiency"],gaps+([] if n.local and n.exposure in ("majority","count","any") else ["缺少明确的暴露定义或节点标签总体均值"]))
        else:
            add(LOCAL_CONTRAST,keys,gaps+([] if n.arms and n.local and n.exposure in ("majority","count","any") else ["缺少局部对比、暴露定义或总体条件均值"]))
    if t.kind=="unclear":
        out=stop("NEEDS_INPUT","TARGET_UNRESOLVED",s.gaps or ["请确认目标人群、干预、比较对象及方向。"])
        out.update(target=t.model_dump(),assumptions=s.assumptions)
        return out
    if not methods:
        out=stop("ADAPTER_NOT_CONNECTED","NO_MATCHING_COMPACT_METHOD",[t.comparison,*s.gaps])
        out.update(target=t.model_dump(),proposed_assumptions=s.assumptions)
        return out
    if s.restrictions:
        out=stop("READING_RECHECK_REQUIRED","ADDITIONAL_RESTRICTIONS_REQUIRE_REVIEW",s.restrictions)
        out.update(target=t.model_dump(),proposed_assumptions=s.assumptions,methods=methods)
        return out
    # Additional unresolved facts never disappear just because one method looks applicable.
    if s.gaps:
        for row in methods:row["missing"].extend(s.gaps)
    if not t.population.strip() or not t.outcome.strip() or not t.treatment.strip():
        for row in methods:row["missing"].append("请补全所问总体、处理及结果")
    if any(row["method"].startswith("IV_") for row in methods):
        if len(t.population.strip())<3 or len(t.context.strip())<3:
            for row in methods:row["missing"].append("请独立核对工具研究的总体和背景范围")
    if not any(not m["missing"] for m in methods):
        out=stop("NEEDS_INPUT","REQUIRED_CONDITIONS_OR_INFORMATION_MISSING",
                 dict.fromkeys(q for r in methods for q in r["missing"]))
        out.update(target=t.model_dump(),methods=methods,assumptions=s.assumptions)
        out["estimate_handoff"].update(target=t.model_dump(),population=t.population,required_before_estimation=out["clarification_questions"])
        if s.graph and s.graph.info in ("sample","unknown"):
            out["estimate_handoff"].update(variables=s.graph.nodes,operators=["目标总体的观测联合律及干预各相关分层的正支持"],
                reason="当前观测资料尚不能提供目标总体的条件律和边际律；需明确抽样与向目标总体标准化的依据。")
        return out
    for row in methods:
        row["review_items"]=reading_items(row["method"],s) if not row["missing"] else {}
    body=dict(spec=s.model_dump(),sources=materials(case),methods=methods)
    return dict(state="REVIEW_REQUIRED",binding=digest(body),**body)


def solve_graph(s,method,source_hash):
    g=s.graph
    p=DagIdProblem(nodes=g.nodes,directed=g.directed,bidirected=g.bidirected,treatment=g.x,outcome=[g.y],context=s.target.context)
    at={g.x:g.x_value,g.y:g.y_value}
    if method=="GENERAL_ID":
        cert=dag_id_solver.identify_or_report(p)
        if cert["status"]=="POINT":
            if not dag_id_verify.replay(cert,p)["passed"]:raise ValueError("GENERAL_ID_REPLAY_FAILED")
            return dict(method=method,state="POINT",functional=cert["functional"],at=at,certificate=cert,
                        variables=g.nodes,operators=["P("+",".join(g.nodes)+")","按公式树求和、条件化，并代入指定干预与结果值"])
        if cert.get("nonidentification_proved") and dag_id_verify.check_failure(cert["witness"],p)["passed"]:
            return dict(method=method,state="NOT_POINT",functional="同一观测总体律允许不同干预分布，见经核对的 hedge。",
                        certificate=cert["witness"],at=at,variables=g.nodes,operators=[])
        return dict(method=method,state="NOT_APPLICABLE",reason=cert.get("reason",cert["status"]))
    # Expand each declared bidirected edge into its own latent common parent.
    nodes=list(g.nodes);edges=list(g.directed);latent=[]
    for i,(a,b) in enumerate(g.bidirected):
        name=f"latent_{i}"
        while name in nodes:name="_"+name
        nodes.append(name);latent.append(name);edges.extend([[name,a],[name,b]])
    info=PopulationLaw(source_id="observed_joint",source_sha256=source_hash,variables=g.nodes,
        availability="SYMBOLIC_POPULATION_LAW",strictly_positive_joint=True,provenance="Reviewed original population-law declaration: "+g.quote)
    prob=BackdoorProblem(version="dag-backdoor-1",model="RECURSIVE_SCM_EXPLICIT_LATENTS_INDEPENDENT_ERRORS",
        variable_domain="BINARY",nodes=nodes,observed=g.nodes,latent=latent,edges=edges,graph_status="DECLARED",
        graph_source=g.quote,materials_sha256=source_hash,context=s.target.context,treatment=g.x,outcome=g.y,
        adjustment=None,information=info,additional_restrictions=[])
    try:cert=dag_backdoor_solver.solve(prob)
    except Unavailable as exc:return dict(method=method,state="NOT_APPLICABLE",reason=exc.reason)
    if not dag_backdoor_verify.replay(cert,problem=prob):raise ValueError("BACKDOOR_REPLAY_FAILED")
    return dict(method=method,state="POINT",functional=cert["functional"],certificate=cert,at=at,
                variables=[g.x,g.y,*cert["adjustment"]],operators=[cert["functional"]])


def solve_iv(s,method,review,source_hash):
    a=s.iv
    mono="monotonicity" in s.assumptions
    conditions=["instrument_independence","exclusion_restriction","consistency_and_binary_outcome","no_interference","positive_instrument_support"]
    if mono:conditions.append("monotonicity_direction")
    prob=IVProblem(version=VERSION,target=method[3:],monotonicity=mono,
        cells=[dict(z=z,d=k//2,y=k%2,probability=v) for z,row in enumerate(a.cells) for k,v in enumerate(row)],
        instrument=a.z,treatment=a.d,outcome=a.y,population=s.target.population,context=s.target.context,
        source_ids=["reviewed_source"],source_sha256=source_hash,assumptions=conditions)
    binding=iv_digest(prob)
    def record(keys,scope):
        def decision(key):
            if scope=="source reading" or key=="consistency_and_binary_outcome":
                return review["decisions"]["review_"+key]
            return review["decisions"][IV_SCIENCE[key]]
        return dict(authority=review["authority"],problem_sha256=binding,reviewer=review["reviewer"],
                    evidence=review["evidence"],decisions={k:decision(k) for k in keys})
    rec=IVReview(version=VERSION,problem_sha256=binding,reading_review=record(READING_DECISIONS,"source reading"),
                 science_review=record(science_decisions(prob),"scientific conditions"))
    out=iv_research.submit(prob,review=rec,research_protocol_selected=True)
    if not out["certificate_replayed"]:return dict(method=method,state="NOT_APPLICABLE",reason=out.get("reason_code"))
    cert=out["certificate"];state=out["state"]
    ops=[f"P({a.d},{a.y}|{a.z}=z), z=0,1"]
    if state=="INCOMPATIBLE":
        formula="不存在满足全部已接受条件及两层概率表的共同潜在类型分布；所附Farkas乘子在观测律上严格为负。";value=None
    elif method=="IV_LATE":
        formula=f"(E[{a.y}|{a.z}=1]-E[{a.y}|{a.z}=0])/(E[{a.d}|{a.z}=1]-E[{a.d}|{a.z}=0])"
        value=cert["exact"]["late"];ops+=["两层的结果条件均值、实际处理条件均值及非零一阶段"]
    else:
        formula="对每种相容二元类型 t=(D0,D1,Y0,Y1) 的共同质量 p_t≥0，约束 Σ_{t:Dz=d,Yd=y}p_t=P(d,y|z)，两端分别 min/max Σ_t (Y1−Y0)p_t。两组原始可行解达到对偶界。"
        bounds=cert["exact"]["bounds"]
        if state=="POINT":
            value=bounds[0]
            formula+="给定精确总体律的两个端点相等，点值取共同端点。"
            ops+=["计算两端并核验精确相等；换用样本或另一总体律时重新审核点识别条件"]
        else:
            value=bounds;ops+=["分别代入两端的类型约束并估计界"]
    return dict(method=method,state=state,certificate=cert,functional=formula,value=value,
                variables=[a.z,a.d,a.y],operators=ops)


def complete(prepared,review,*,authority):
    if prepared.get("state")!="REVIEW_REQUIRED":return prepared
    body={k:prepared[k] for k in ("spec","sources","methods")}
    if (digest(body)!=prepared["binding"] or review.get("binding")!=prepared["binding"] or
            review.get("authority")!=authority or authority not in ("SYNTHETIC_TEST","EXTERNAL_RESEARCH_REVIEW")):
        raise ValueError("REVIEW_BINDING_MISMATCH")
    ready=[r for r in prepared["methods"] if not r["missing"]]
    required={"target_and_source_reading",*(k for row in ready for k in (*row["conditions"],*row["review_items"]))}
    decisions=review.get("decisions",{})
    if (set(decisions)!=required or not isinstance(review.get("reviewer"),str) or not 3<=len(review["reviewer"].strip())<=300
            or not isinstance(review.get("evidence"),str) or not 12<=len(review["evidence"].strip())<=4000):
        raise ValueError("EXPLICIT_READING_AND_SCIENCE_REVIEW_REQUIRED")
    if any(v not in ("ACCEPTED","PENDING","REJECTED") for v in decisions.values()):
        raise ValueError("INVALID_REVIEW_DECISION")
    if decisions["target_and_source_reading"]!="ACCEPTED":
        return stop("REVIEW_REQUIRED","PENDING_OR_REJECTED_READING_OR_ASSUMPTION")
    permitted=[m for m in ready if all(decisions[k]=="ACCEPTED" for k in (*m["conditions"],*m["review_items"]))]
    if not permitted:return stop("REVIEW_REQUIRED","PENDING_OR_REJECTED_READING_OR_ASSUMPTION")
    s=Reading.model_validate(prepared["spec"])
    answers=[dict(method=m["method"],state="NOT_APPROVED",reason="尚有未接受的科学前提") for m in ready if m not in permitted]
    source_hash=digest(prepared["sources"])
    for row in permitted:
        m=row["method"]
        boundary=external_scope(m,s) if authority=="EXTERNAL_RESEARCH_REVIEW" else None
        if boundary:
            answers.append(dict(method=m,state="ADAPTER_NOT_CONNECTED",reason=boundary))
            continue
        if m in ("BACKDOOR","GENERAL_ID"):a=solve_graph(s,m,source_hash)
        elif m.startswith("IV_"):a=solve_iv(s,m,review,source_hash)
        else:
            from .compact_network import solve
            a=solve(s,m,review)
        a["assumptions"]={k:s.assumptions[k] for k in row["conditions"]}
        answers.append(a)
    valid=[a for a in answers if a["state"] in ("POINT","PARTIAL","NOT_POINT","INCOMPATIBLE")]
    if not valid:
        if all(a["state"]=="ADAPTER_NOT_CONNECTED" for a in answers):
            return stop("ADAPTER_NOT_CONNECTED",answers[0]["reason"])
        out=stop("NEEDS_INPUT","NO_APPLICABLE_IDENTIFICATION_PROOF",[str(a.get("reason")) for a in answers])
        out.update(methods=answers,target=s.target.model_dump(),assumptions=s.assumptions);return out
    if len({a["state"] for a in valid})>1 or len({str(a["value"]) for a in valid if a.get("value") is not None})>1:
        return stop("CHECK_BLOCKED","METHOD_CONCLUSIONS_DISAGREE")
    a=valid[0];state=a["state"];point=state in ("POINT","PARTIAL");t=s.target.model_dump()
    conditions=a["assumptions"]
    support={"IV_LATE":"两种工具状态有正概率，一阶段为正","IV_ATE":"两种工具状态有正概率，完整条件表相容",
             "BACKDOOR":"目标处理在各调整层有正支持","GENERAL_ID":"观测总体联合律严格正，另见公式分母条件",
             LOCAL_CONTRAST:"两端每个正权单位的目标局部状态均有正支持",FULL_POLICY:"目标完整名单在原分配律下有正概率",EXPOSURE_POLICY:"每个正权单位的目标暴露标签均有正支持"}[method_name(a["method"])]
    handoff=dict(mode=("ESTIMATE_POINT" if state=="POINT" else "ESTIMATE_BOUNDS") if point else "STOP",
        target=t,population=t["population"],variables=a["variables"],operators=a["operators"] if point else [],
        support=support if point else "研究目标未获可估计的点公式；保持阻断",at=a.get("at"),functional=a["functional"] if point else None,
        conditioning=a.get("at"),assumptions=conditions,execute_estimator=False)
    if method_name(a["method"]) in (LOCAL_CONTRAST,FULL_POLICY,EXPOSURE_POLICY):
        n=s.network
        handoff["design"]=dict(node_order=n.nodes,weights=n.weights,edges=n.edges,
            assignment=n.design,quota=n.quota,probabilities=n.probabilities,exposure=n.exposure,
            policy=n.policy,arms=n.arms)
    elif a["method"].startswith("IV_"):
        iv=s.iv
        handoff["law"]=dict(instrument=iv.z,treatment=iv.d,outcome=iv.y,instrument_strata=[0,1],
            cell_order=[[0,0],[0,1],[1,0],[1,1]],domain="binary",source="reviewed_population_conditional_law")
    else:
        handoff["law"]=dict(observed=s.graph.nodes,treatment=s.graph.x,outcome=s.graph.y,
            availability=s.graph.info,directed=s.graph.directed,bidirected=s.graph.bidirected)
    return dict(state=state,reason_code="REVIEWED_COMPACT_METHODS",backend_called=True,independent_replay=True,
        mathematical_claim=dict(kind=state,method=a["method"],target=t,functional=a["functional"],value=a.get("value"),at=a.get("at")),
        certificate=a["certificate"],method_results=answers,methods=prepared["methods"],assumptions=conditions,
        estimate_handoff=handoff,estimation_handoff_allowed=False,production_admission=False,review_binding=prepared["binding"])


def replay_delivery(prepared, review, delivered, *, authority):
    """Rebuild a signed delivery, including values, source bindings and the estimate contract."""
    if not isinstance(delivered,dict) or delivered.get("independent_replay") is not True:
        return False
    try:
        rebuilt=complete(prepared,review,authority=authority)
        return rebuilt.get("independent_replay") is True and digest(rebuilt)==digest(delivered)
    except (ValueError,TypeError,KeyError,ArithmeticError):
        return False
