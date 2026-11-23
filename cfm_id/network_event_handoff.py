"""Design-conditional local contrasts over the focal population declared in the question."""
from fractions import Fraction

from . import direct_network as native
from .network_estimate_handoff import delivery, execute_handoff, make_handoff, probability, target_for

RULES = {"any":native.GROUP_E5,"count":native.GROUP_E4,"majority":native.GROUP_E1}


def native_support(network, design, exposure, population, ends):
    kind = design.get("kind")
    if network.get("basis") not in ("edges","focal") or exposure.get("kind") not in RULES:
        return None
    nodes = network["nodes"]
    if not set(population) <= set(network["complete_for"]) or not set(population) <= set(nodes):
        return None
    if network["basis"]=="focal" and kind not in ("independent","shared","fixed","quota_mixture"):
        return None
    if kind in ("fixed","quota_mixture","stratified") and not network.get("roster_complete"):
        return None
    net = native.types.NetworkExposureSpec(network_id="reviewed-focal-neighborhood",node_ids=nodes,undirected_edges=network["edges"])
    if kind=="independent" and set(design["p"])==set(nodes):
        law = native.types.HeterogeneousBernoulliDesignV1(propensities=design["p"])
    elif kind=="fixed":
        law = native.types.CompleteRandomizationDesignV1(m=design["quota"])
    elif kind=="stratified" and network["basis"]=="edges":
        law = native.types.TwoGroupFixedQuotaDesignV1(groups=design["groups"],treated_quotas=design["quotas"])
        if set(law.groups[0]+law.groups[1])!=set(nodes):
            return None
    elif kind=="shared":
        law = native.types.ClusterBernoulliDesignV24(clusters=(nodes,),cluster_probabilities=(str(probability(design["p"])),))
    elif kind=="quota_mixture":
        law = native.types.TwoStageQuotaMixtureDesignV27(groups=design["groups"],quota_profiles=design["quotas"],
                                                         profile_probabilities=design["weights"])
    else:
        return None
    return native.support_record(net,law,RULES[exposure["kind"]],population,ends)


def solve(facts, *, design_only=False):
    c, net, exp, law, info, sci = (facts[k] for k in ("contrast","network","exposure","assignment","information","science"))
    if c.get("kind") != "original_local" or net.get("pre") is not True or not exp.get("kind"):
        return None
    if law.get("variable") != c.get("variable") or not c.get("variable"):
        return None
    if design_only:
        if net.get("basis")!="edges" or law.get("kind") not in ("independent","fixed","stratified"):
            return None
    elif sci.get("consistent") is not True or sci.get("random_full") is not True:
        return None
    population, ends = c["population"], c["ends"]
    if not population or len(set(population))!=len(population) or len(ends)!=2 or ends[0]==ends[1]:
        return None
    if any(len(a)!=2 or type(a[0]) is not int or a[0] not in (0,1) or type(a[1]) is not int or a[1]<0 for a in ends):
        return None
    if exp["kind"] in ("any","majority") and any(s>1 for _,s in ends):
        return None
    weights=c.get("weights") or []
    if len(weights)!=len(population) or any(probability(w)<=0 for w in weights) or sum(map(probability,weights))!=1:
        return None
    target = target_for(c,"difference")
    keys=[f"{a},{s}" for a,s in ends]
    proof=dict(method="ORIGINAL_EVENT_MEANS",population=population,ordered_events=keys,
               exposure=exp["kind"],design=law["kind"])
    variables=[c["variable"],"按题中处理前关系统计的邻居暴露",c["outcome"]]
    def stop(status, explanation, support, questions=()):
        h=make_handoff(target,"STOP",variables,[],[],explanation,support)
        return delivery(target,status,explanation,None,sci["evidence"],h,explanation,proof,questions)
    if law.get("kind") in ("margins_only","conflict"):
        if not c.get("joint_requested") or not law.get("material_alternatives"):
            return None
        rates=law.get("p")
        if not isinstance(rates,dict) or set(rates)!=set(net.get("nodes",[])) or len(set(rates.values()))!=1:
            return None
        alternatives={"逐人独立":dict(kind="independent",p=rates),"同签":dict(kind="shared",p=next(iter(rates.values())))}
        supports={label:native_support(net,design,exp,population,ends) for label,design in alternatives.items()}
        if any(table is None for table in supports.values()) or supports["逐人独立"]==supports["同签"]:
            return None
        proof["alternative_joint_probabilities"]=supports
        expl="独立签与共签的个人边际相同，而按题中顺序计算的联合概率不同："+str(supports)+"。"
        if info.get("values") and len(population)==1:
            vals=info["values"];n=population[0]
            if all(n+"|"+k in vals for k in keys):
                diff=Fraction(str(vals[n+"|"+keys[0]]))-Fraction(str(vals[n+"|"+keys[1]]))
                expl+=f"两端都可达时均值差 {diff}，某端概率为零时原条件比较未定义。"
        msg="请确认本轮完整名单采用哪项联合分配规则，以计算所问两端的联合概率和端内权重。"
        return stop("NEEDS_INPUT",expl,{},[msg])
    if law.get("kind")=="reported" and net.get("basis") in ("registered","focal","edges"):
        if net.get("basis")=="registered" and not net.get("complete_event_labels"):
            return None
        joint=info.get("reported_joint")
        if joint is None and (c.get("joint_requested") or not info.get("positive_both")):
            return None
        if joint is not None and (set(joint)!=set(population) or any(set(row)!=set(keys) for row in joint.values())):
            return None
        if joint is not None:
            joint={n:{k:str(probability(v)) for k,v in row.items()} for n,row in joint.items()}
            if any(sum(map(Fraction,row.values()))>1 for row in joint.values()):
                return None
        proof["support_origin"]="材料报告的联合事件"
    else:
        joint=native_support(net,law,exp,population,ends)
        if joint is None:
            return None
        proof["support_origin"]="原分配设计的 SupportEngine 与独立核算"
    proof["joint_probabilities"]=joint
    support=joint if joint is not None else {"positive_both":True}
    zero=[(n,k) for n,row in (joint or {}).items() for k in keys if row[k]=="0"]
    if zero:
        proof["zero_events"]=zero
        expl="、".join(f"{n} 的 ({k})" for n,k in zero)+" 联合概率为零。原设计在此端的条件分布未定义，所问原人群、原方向的差无法定义。"
        return stop("UNDEFINED",expl,support)
    if design_only or info.get("query") != "event_mean" or not info.get("same_population"):
        return None
    queries=[]; coefficients=[]
    for n,w in zip(population,weights):
        for sign,(a,s) in zip((1,-1),ends):
            queries.append(dict(id=f"{n}|{a},{s}",kind="person_event_mean",unit=n,own=a,exposure=s,
                                exposure_rule=exp["kind"],outcome=c["outcome"],time=c["time"]))
            coefficients.append(sign*Fraction(w))
    expr="令 μ_i(a,s)=E[Y_i | 本人处理=a, 邻居暴露=s]。按指定权重求和："+" + ".join(
        f"({w})[μ_{n}({keys[0]}) − μ_{n}({keys[1]})]" for n,w in zip(population,weights))
    h=make_handoff(target,"ESTIMATE_POINT",variables,queries,[coefficients],expr,support)
    values=info.get("values",{})
    if values and not all(q["id"] in values for q in queries):
        return None
    value=execute_handoff(h,values) if values else None
    if value is None and info.get("numeric_required"):
        return None
    proof["population_interface"]="person_event_mean";proof["population_values"]=values
    for query in h["queries"]:
        node=query["unit"]
        query["treatment"]=c["variable"]
        if net.get("edges") is not None:
            query["neighbors"]=[b if a==node else a for a,b in net["edges"] if a==node or b==node]
        elif net.get("basis")=="registered":
            query["event_dictionary"]="处理前锁定且经核验的等价事件标签"
        else:
            query["event_dictionary"]="原材料所列的焦点搭档事件"
    h["remaining_assignment"]=c["remaining"]
    return delivery(target,"POINT",expr,value,sci["evidence"],h,
                    "在原设计每端对其余安排取条件平均，完整名单独立与一致性使两端总体条件均值直接识别所问目标。",proof)
