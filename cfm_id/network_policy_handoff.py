"""Sharp policy means for two binary assignments with known marginals and four population means."""
from .network_estimate_handoff import delivery, execute_handoff, make_handoff, probability, ratio, target_for


def solve(facts, *, point_required=False):
    c, design, info, science = (facts[k] for k in ("contrast","assignment","information","science"))
    if c.get("kind") != "binary_policy_level" or design.get("kind") != "binary_policy":
        return None
    if (science.get("random_full") is not True or science.get("consistent") is not True
            or info.get("same_population") is not True or info.get("query") != "joint_state_mean"):
        return None
    cells = ("00", "10", "01", "11")
    if len(design.get("margins",[])) != 2:
        return None
    ma, mb = map(probability, design["margins"])
    lower, upper = max(0,ma+mb-1), min(ma,mb)
    law = design.get("coupling")
    if law == "independent":
        lower = upper = ma*mb
    elif law == "same_draw":
        if ma != mb:
            return None
        lower = upper = ma
    elif law == "opposite":
        if ma+mb != 1:
            return None
        lower = upper = 0
    elif law == "specified":
        p = probability(design["both"])
        if not lower <= p <= upper:
            return None
        lower = upper = p
    elif law != "unknown":
        return None
    def weights(x):
        return [1-ma-mb+x, ma-x, mb-x, x]
    forms = [weights(lower)]
    if upper != lower:
        forms.append(weights(upper))
    active = [i for i in range(len(cells)) if any(law[i] for law in forms)]
    required = [cells[i] for i in active]
    available = info.get("values",{})
    supported = info.get("supported_cells", cells if info.get("all_positive") is True else ())
    if not set(required) <= set(supported) or not set(required) <= set(available):
        return None
    used_forms = [[w[i] for i in active] for w in forms]
    means = [ratio(available[cell]) for cell in required]
    levels = [sum(a*b for a,b in zip(w,means)) for w in used_forms]
    status = "POINT" if min(levels)==max(levels) else "PARTIAL"
    target = target_for(c,"level")
    queries = [dict(id=cell,kind="joint_state_population_mean",assignment=cell,
                    population=target["population"],outcome=target["outcome"],time=info.get("source_time","历史")) for cell in required]
    if lower==upper:
        expr=" + ".join(f"({w})μ{cell}" for w,cell in zip(used_forms[0],required))
        formula=f"两者同时处理的概率 x={lower}。所问总体均值为 {expr} = {levels[0]}。"
    else:
        formula = (f"令 x=P(两者同时处理)，x∈[{lower},{upper}]。按 00、10、01、11 排序，"
                   f"目标为 (1−{ma}−{mb}+x)μ00+({ma}−x)μ10+({mb}−x)μ01+xμ11。"
                   f"x={lower} 时为 {levels[0]}，x={upper} 时为 {levels[-1]}。")
    reason = ("每组可行权重都是满足给定边际的联合分配，线性函数在区间端点取极值。"
              "政策赋予正权重的整单在原设计有支持，整单随机与一致性使相应总体均值可用。")
    h = make_handoff(target,"ESTIMATE_POINT" if status=="POINT" else "ESTIMATE_BOUNDS",
                     ["两个单位的处理状态","按题定人群加权的总体结局"],queries,used_forms,formula,
                     dict(joint_states=required,historical_support="所列历史整单均有正支持"))
    value = execute_handoff(h,available)
    proof = dict(method="TWO_BINARY_POLICY_MARGINS", joint_parameter="P(11)",
                 feasible_joint_11=list(map(str,(lower,upper))), ordered_cells=list(cells),
                 endpoint_laws=[[str(z) for z in w] for w in forms],
                 population_values={cell:available[cell] for cell in required}, point_optional=status=="PARTIAL")
    if len(required)==4:
        proof["interaction"]=str(means[0]-means[1]-means[2]+means[3])
    ask = ["要得到单一点值，请补充两者同时处理的概率，或说明二者独立、共签或反向。各自的边际概率已经给出。"] if status=="PARTIAL" and point_required else []
    return delivery(target,status,formula,value,science["evidence"],h,reason,proof,ask)
