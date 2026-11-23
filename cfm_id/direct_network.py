"""Conditional local effects. Bind a contrast to source evidence before calling the native support engines."""
import csv
import io
import json
import re
from fractions import Fraction

from cfm_id_bridge.scientific_binding import sha
from pfn_pipeline._internal.identification import schemas as types
from pfn_pipeline._internal.identification.randomized_arm_family.assignment import AssignmentSpec, neighbor_set
from pfn_pipeline._internal.identification.randomized_arm_family.exposure import ExposureSpec, GROUP_E1, GROUP_E4, GROUP_E5
from pfn_pipeline._internal.identification.randomized_arm_family.support import SupportEngine
from pfn_pipeline.identification_batch import _independent_count_masses, _support_comparison

RULES = {GROUP_E1: "S=1 当且仅当处理邻居严格过半，平票为0",
         GROUP_E4: "S 为已处理邻居的精确人数", GROUP_E5: "S=1 当且仅当至少一位邻居接受处理"}


def contrasts(q):
    coded = re.findall(r"\(T,S\)\s*=\s*\(([01]),(\d+)\)\s*减\s*\(T,S\)\s*=\s*\(([01]),(\d+)\)", q)
    if coded:
        if len(coded) != 1 or re.search(r"另外|还要|另一问|分别求", q):
            return []
        a, s, b, t = map(int, coded[0])
        return [(q, (a,s), (b,t))]
    numbered = re.findall(r"(?m)^[1-9][.、]\s*([^\n]+)", q)
    lines = numbered or [q]
    result = []
    for line in lines:
        compact = re.sub(r'[“”\s*]', '', line)
        if "至多一半" in compact and "在合作门店至多一半" in compact and "使用减不使用" in compact:
            pair = (1,0), (0,0)
        elif "在本店使用" in compact and "过半减至多一半" in compact:
            pair = (1,1), (1,0)
        elif "在本店使用" in compact and "至多一半减超过一半" in compact:
            pair = (1,0), (1,1)
        elif re.search(r"本店使用且合作门店超过一半.*相比本店不使用且合作门店至多一半", compact) and "前者减后者" in compact:
            pair = (1,1), (0,0)
        elif "自己没有接种" in compact and re.search(r"(三人接种减一人接种|一人接种减三人接种)", compact):
            pair = ((0,3),(0,1)) if "三人接种减一人接种" in compact else ((0,1),(0,3))
        elif "自己没有收到邀请" in compact and re.search(r"至少一位朋友获邀[，,]?相比没有朋友获邀|有朋友获邀减没有朋友获邀", compact):
            pair = (0,1), (0,0)
        elif "自己没有收到邀请" in compact and "没有朋友获邀减至少一位朋友获邀" in compact:
            pair = (0,0), (0,1)
        else:
            return []
        result.append((line, *pair))
    return result


def csv_tables(sources):
    result = {}
    for source in sources:
        text = source["text"].strip()
        first = text.split("\n", 1)[0].strip()
        if first.split(",")[0] not in {"unit_id", "unit_a", "profile", "n_treated"}:
            continue
        if first in result or len(text) > 200000:
            raise ValueError("AMBIGUOUS_OR_OVERSIZE_TABLE")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        if any(None in row or None in row.values() for row in rows) or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("INVALID_TABLE")
        result[first] = rows
    return result


def network_data(text, tables):
    members = tables.get("unit_id", tables.get("unit_id,group", []))
    nodes = [r["unit_id"] for r in members]
    raw_edges = tables.get("unit_a,unit_b")
    edges = [(r["unit_a"],r["unit_b"]) for r in raw_edges] if raw_edges is not None else None
    if not nodes:
        match = re.search(r"完整研究名单按顺序为[：:]([^。\n]+)", text)
        if match:
            nodes = match[1].split("、")
    if edges is None:
        bracket = re.search(r"完整边表，没有其他边[：:]\s*(\[\[.*?\]\])", text)
        if bracket:
            edges = json.loads(bracket[1])
    if not nodes or len(nodes) > 256:
        return None, None
    if edges is None or not re.search(r"没有其他边|此外没有其他边|完整无向边表", text):
        return nodes, None
    return nodes, types.NetworkExposureSpec(network_id="source-network", node_ids=nodes, undirected_edges=edges)


def design_data(text, tables, nodes):
    probabilities = tables.get("unit_id,treatment_probability")
    if probabilities and re.search(r"独立.{0,15}(?:抽签|Bernoulli)|独立进行 Bernoulli", text):
        ps = {r["unit_id"]:r["treatment_probability"] for r in probabilities}
        if set(ps) != set(nodes) or len(ps) != len(probabilities):
            return None
        return types.HeterogeneousBernoulliDesignV1(propensities=ps)
    profiles = tables.get("profile,group_a_quota,group_b_quota,probability")
    if profiles and re.search(r"等概率抽取|组内均匀", text) and re.search(r"第二阶段抽取独立|两组独立", text):
        # Bind quota columns by the dictionary, never by sorting the observed group names.
        label_rows = [re.search(r"\|\s*`?"+column+r"`?\s*\|\s*([\w-]+组)接种名额", text)
                      for column in ("group_a_quota", "group_b_quota")]
        if not all(label_rows):
            return None
        groups = tuple(tuple(r["unit_id"] for r in tables.get("unit_id,group",[]) if r["group"] == m[1]) for m in label_rows)
        if set().union(*map(set, groups)) != set(nodes):
            return None
        return types.TwoStageQuotaMixtureDesignV27(groups=groups,
            quota_profiles=tuple((int(r["group_a_quota"]),int(r["group_b_quota"])) for r in profiles),
            profile_probabilities=tuple(r["probability"] for r in profiles))
    split = re.search(r"第一组([^；。\n]+)；第二组([^。\n]+)。各组独立从(\d+)人中等概率抽出(\d+)人", text)
    if split:
        groups = tuple(tuple(v.split("、")) for v in split.groups()[:2])
        if any(len(v) != int(split[3]) for v in groups) or set(groups[0]+groups[1]) != set(nodes):
            return None
        return types.TwoGroupFixedQuotaDesignV1(groups=groups, treated_quotas=(int(split[4]),)*2)
    fixed = re.search(r"在完整名单中等概率无放回抽取(\d+)人", text)
    if fixed and int(fixed[1]) <= len(nodes):
        return types.CompleteRandomizationDesignV1(m=int(fixed[1]))
    return None


def support_record(network, design, rule, population, arms):
    exposure = ExposureSpec(rule)
    assignment = AssignmentSpec(design)
    rows = {}
    for node in population:
        neighbors = neighbor_set(network, node)
        joint = SupportEngine.joint_support(network=network, assignment=assignment, exposure=exposure, node_id=node)
        if sum(joint.values(), Fraction()) != 1:
            raise ValueError("JOINT_SUPPORT_NOT_NORMALIZED")
        independent = _independent_count_masses(design, neighbors) if isinstance(design, types.HeterogeneousBernoulliDesignV1) else None
        values = {}
        for a, state in sorted(arms):
            p = joint.get((a,state), Fraction())
            checked = _support_comparison(design, network, node, a, (state,), rule, None, independent)
            if p != checked[state]:
                raise ValueError("INDEPENDENT_SUPPORT_DISAGREEMENT")
            values[f"{a},{state}"] = str(p)
        rows[node] = values
    return rows


def paired_focal(case):
    """A named focal unit, two exchangeable neighbors, and two given population means in question order."""
    q = case["business_question"]
    if len(case["sources"]) != 1 or not re.search(r"只对[^，。]{1,20}求本人(?:开启减关闭|关闭减开启)",q):
        return None
    t = case["sources"][0]["text"]
    design = re.search(r"([^，。\s]{1,15})和两邻站分别以(\d+/\d+)独立抽签",t)
    label = re.search(r"固定邻居标签为(至少一站开启|两站都开启)",q)
    means = re.search(r"两个目标局部状态的总体条件均值依次为([\d./-]+)、([\d./-]+)[。；]",t)
    if not all((design,label,means)) or not re.search(r"名单与潜在结果独立",t) or "完整名单一致" not in t:
        return None
    node = design[1]
    if node not in q or not re.search(r"在原抽签设计中",q):
        return None
    prob = Fraction(design[2])
    if not 0 < prob < 1:
        return None
    nodes=[node,"邻居甲","邻居乙"]
    net=types.NetworkExposureSpec(network_id="source-network",node_ids=nodes,undirected_edges=[(node,j) for j in nodes[1:]])
    spec=types.HeterogeneousBernoulliDesignV1(propensities=dict.fromkeys(nodes,str(prob)))
    rule,state=(GROUP_E5,1) if label[1]=="至少一站开启" else (GROUP_E4,2)
    a,b=(1,0) if "开启减关闭" in q else (0,1)
    joint=support_record(net,spec,rule,[node],[(a,state),(b,state)])
    y=re.search(r"的([^，。]{2,30}?)差",q)
    if not y:
        return None
    expr=f"E[Y | T={a},S={state}] − E[Y | T={b},S={state}] = {means[1]} − {means[2]}"
    target=dict(quantity="difference",scope="subgroup",population=node,intervention=f"T={a}, {label[1]}",reference=f"T={b}, {label[1]}",outcome=y[1],time=y[1])
    answer=dict(status="POINT",target=target,functional=expr,value=str(Fraction(means[1])-Fraction(means[2])),
                assumptions=[dict(kind="other",subject="原分配与一致性",statement=t,quote=t)],
                estimate_handoff=dict(mode="ESTIMATE_POINT",scope="subgroup",population=node,variables=["Y","T","S"],operator=expr,
                                      exposure=RULES[rule],support=joint),
                reason="在原名单抽签的条件分布下，完整名单独立与一致性将每端均值化为观察条件均值。")
    return dict(answer=answer,proof=dict(method="LOCAL_DESIGN_CONDITIONAL_MEAN",source_sha256=sha(case["sources"]),exposure=RULES[rule],joint_probabilities=joint),
                checks=[dict(code="JOINT_SUPPORT",state="CHECKED",detail=f"{label[1]}，各端联合概率 {joint}")],questions=[])


def equivalent_exposure_reported(text):
    """Detect source-reported substitutes. This never certifies the reported probabilities."""
    clauses = re.split(r"[。；，,;\n]", text)
    for clause in clauses:
        if re.search(r"(?:没有|不曾|未能|未|无法|尚待|待核|不完整|不可靠|不能|是否)", clause):
            continue
        registry = re.search(r"(?:等价|等效)(?:的)?(?:逐人)?(?:邻居|邻接|暴露|标签|映射|事件)", clause)
        if registry and re.search(r"核验|确认|提供|给出|具备|可用|已有", clause):
            return True
    return False


def missing_event_means(text):
    """A marginal outcome summary alone cannot supply event-specific population moments."""
    if not re.search(r"(?:已知|只有|仅有|仅提供|只知道|仅可获得)[^。；\n]{0,35}(?:无条件|边际)(?:总体)?(?:平均|均值|结局分布|结果分布)", text):
        return False
    for phrase in re.split(r"[。；，,\n]", text):
        if re.search(r"没有|未提供|不知道|未知|缺少|待补|仅有边际", phrase):
            continue
        moments = r"(?:条件均值|总体联合分布)"
        availability = r"(?:可(?:符号)?调用|可按人调用|以符号给出|已提供|已给定|已知|给出了|取得了)"
        if re.search(moments+r".{0,16}"+availability, phrase) or re.search(availability+r".{0,16}"+moments, phrase):
            return False
    return bool(re.search(r"(?:没有|缺少|尚无|未提供|未保存)(?:给出)?(?:任何|这些|目标|各端|两端|局部|逐人|暴露|事件|相应|下|的|总体|状态|按人)*(?:条件均值|条件结局分布|条件结果分布)", text))


def verified(case, *, network_table=None, revision=3):
    q, sources = case["business_question"], case["sources"]
    targets = contrasts(q)
    if not targets:
        return paired_focal(case)
    text = "\n".join(s["text"] for s in sources)
    if len(text) > 300000:
        return None
    if revision >= 4 and any(s["source_id"].startswith("user_reply_") for s in sources):
        original = "\n".join(s["text"] for s in sources if not s["source_id"].startswith("user_reply_"))
        replies = [s["text"] for s in sources if s["source_id"].startswith("user_reply_")]
        # Only the supported missing design can be filled from a short reply. Additional
        # changes to the target, the graph or assumptions require a fresh reading.
        if len(replies)!=1 or "分配设计待补" not in original or not re.fullmatch(
            r"(?:补充(?:说明)?[：:])?(?:本次|实际|我们)?在完整名单中等概率无放回抽取\d+人[。.]?",replies[0].strip()):
            return None
    tables = csv_tables(sources)
    nodes, network = network_data(text, tables)
    native_gap = False
    if network_table is not None:
        native_nodes = list(network_table.nodes)
        if len(native_nodes) > 256 or (nodes and nodes != native_nodes):
            raise ValueError("INCONSISTENT_OR_OVERSIZE_NETWORK_ROSTER")
        native_edges = {frozenset(e) for e in network_table.edges}
        if network and native_edges != {frozenset(e) for e in network.undirected_edges}:
            raise ValueError("CONFLICTING_NETWORK_EDGE_SOURCES")
        nodes = native_nodes
        native_gap = network_table.completeness != "COMPLETE"
        network = None if native_gap else types.NetworkExposureSpec(
            network_id=network_table.token,node_ids=nodes,undirected_edges=list(network_table.edges))
    if not nodes:
        return None
    scope = re.search(r"仅评价【([^】]+)】",q)
    if scope:
        population = scope[1].split("、")
    elif re.search(r"全部|全体|完整名单",q) and ("等权" in text+q):
        population = nodes
    else:
        return None
    if not population or not set(population) <= set(nodes) or len(set(population)) != len(population):
        return None
    rule = None
    if re.search(r"取精确人数|精确邻居人数", text):
        rule = GROUP_E4
    elif re.search(r"至少一名朋友收到邀请记同伴状态1|至少一位邻居接受处理时.{0,8}S=1", text):
        rule = GROUP_E5
    elif re.search(r"严格超过一半.{0,25}(?:合作门店|邻居)|严格过半时S=1", text):
        rule = GROUP_E1
    if rule is None:
        return None
    # Read the published outcome/time from the study; no campaign or role names are inferred from the draft.
    outcome = re.search(r"(?:结果(?:变量)?为)[：:]?([^。；：:\n]{2,110})", text)
    context = re.search(r"(?:评价期间为|结果评价期间为|研究背景[：:])([^，。；\n]{2,80})", text)
    if not outcome:
        return None
    y = outcome[1]
    period = context[1] if context else y
    arms = {arm for _, left, right in targets for arm in (left,right)}
    missing = []
    declared_network_gap = re.search(r"完整网络缺失|无法确认完整网络|没有提供完整网络", q+"\n"+text)
    if revision >= 5 and (native_gap or network is None or declared_network_gap):
        # A withheld edge list and known exposure probabilities can coexist. An inability
        # to parse an attachment is likewise insufficient evidence for a scientific STOP.
        if equivalent_exposure_reported(text):
            return dict(review_only=True, checks=[dict(code="REPORTED_EQUIVALENT_EXPOSURE", state="UNCHECKED",
                detail="资料声明已提供等价暴露信息。请核对其覆盖的人群、比较端、事件概率和总体均值；程序未按原始名单重算。")])
        if network is None and not (native_gap or declared_network_gap):
            return None
    if native_gap or network is None or declared_network_gap:
        missing.append("请提供处理前的完整边表或逐人等价邻居信息，以确定暴露映射、目标条件与联合支持。")
    design = design_data(text, tables, nodes)
    if design is None:
        if re.search(r"没有说明每组如何抽取|名单概率是否相同，材料没有说明|分配设计待补", text+q):
            missing.append("请提供原分配设计、各份名单的抽取概率或等价规则，以确定条件加权与各端支持。")
        elif not missing:
            return None
    notification_gap = bool(re.search(r"不能确认名额通知|名额通知.{0,20}直接影响.{0,8}不能确认", text+q))
    if notification_gap:
        missing.append("请确认第一阶段名额通知能否独立于实际接种直接影响结果。若有影响，请另定含通知的组合干预或补足纯接种对比的识别条件。")
    science = bool(re.search(r"潜在结果独立|潜在结果.{0,5}独立", text)) and bool(re.search(r"一致性|实际观察结果对应实际完整安排",text))
    symbolic = bool(re.search(r"总体条件(?:平均|均值|感染概率)|符号总体平均结果",text))
    natural = bool(re.search(r"原.{0,18}(?:规则|设计|分布).{0,16}条件.{0,10}平均|按.{0,18}原.{0,65}条件分布平均", text+q))
    if revision >= 6:
        science = science or (bool(re.search(r"(?:名单|分配|安排)[^。；\n]{0,12}独立于(?:所有|全部)?潜在结果",text)) and "一致性" in text)
    outcome_gap = revision >= 6 and missing_event_means(text)
    if not missing and not (natural and science and (symbolic or outcome_gap)):
        return None
    symbolic_only = bool(re.search(r"符号|不提供具体结果数值|具体结果数.{0,6}未",text))
    if not missing and not outcome_gap and (not symbolic_only or "条件均值表" in text or re.search(r"总体条件(?:均值|平均结果)分别为\s*\d",text)):
        return None
    if not missing and isinstance(design, types.TwoStageQuotaMixtureDesignV27) and (not re.search(r"名额方案本身不直接影响|第一阶段通知没有直接效应", text) or not re.search(r"不同组之间没有干扰|组间无干扰",text)):
        return None
    # Explicitly rejected or competing declarations require a human reading.
    if not missing and re.search(r"拒绝.{0,30}(?:独立|一致|条件平均)|不是等权|不再等权|改用.{0,18}(?:网络|设计|权重)", text+q):
        return None
    joint = support_record(network,design,rule,population,arms) if network is not None and design is not None else {}
    proof = dict(method="LOCAL_DESIGN_CONDITIONAL_MEAN", source_sha256=sha(sources), exposure=RULES[rule], population=population,
                 design=design.model_dump(mode="json") if design else None, joint_probabilities=joint,
                 checked_by="native SupportEngine and independent design-specific support calculation" if joint else None)
    checks = [dict(code="EXPOSURE_MAPPING",state="CHECKED",detail=RULES[rule])]
    if joint:
        checks.append(dict(code="JOINT_SUPPORT",state="CHECKED",detail="按原设计逐人计算 P(T_i=a,S_i=s)；独立算法得到同一结果。"))
    checks.extend(dict(code="SOURCE_GAP",state="UNCHECKED",detail=m) for m in missing)
    answers = []
    questions = list(missing)
    outcome_question = "若比较两端均有正支持，请提供评价对象在各端的总体条件均值或可导出它们的联合分布。现有无条件总体均值不足以完成交接。"
    for part, left, right in targets:
        zero = [(node,str(arm)) for node in population for arm in (left,right) if joint and joint[node][f"{arm[0]},{arm[1]}"]=="0"]
        part_gaps = list(missing)
        if outcome_gap and not zero:
            part_gaps.append(outcome_question)
            if outcome_question not in questions:
                questions.append(outcome_question)
                checks.append(dict(code="POPULATION_OUTCOME_GAP", state="UNCHECKED", detail=outcome_question))
        state = "NEEDS_INPUT" if part_gaps else "UNDEFINED" if zero else "POINT"
        mode = "ESTIMATE_POINT" if state=="POINT" else "STOP"
        scope_kind = "whole" if population==nodes else "subgroup"
        target = dict(quantity="difference", scope=scope_kind, population=population, intervention=f"(T_i,S_i)={left}",
                      reference=f"(T_i,S_i)={right}", outcome=y, time=period, remaining="其余完整安排按原分配设计在各端条件平均")
        expr = (f"令 μ_i(a,s)=E[Y_i | T_i=a,S_i=s,W]，W为研究固定背景。"
                f"目标为 Σ_(i∈评价名单) [μ_i{left} − μ_i{right}]/{len(population)}。")
        if part_gaps:
            expr = " ".join(part_gaps)
        elif zero:
            expr = f"原设计对 {zero} 的联合概率为零，该端原设计条件分布没有定义，无法计算所求差。"
        assumptions = []
        conditions = [("完整分配",r"潜在结果.{0,6}独立|独立于(?:全部|所有)?潜在结果" if revision >= 6 else r"潜在结果.{0,6}独立"),("一致性",r"实际观察结果对应实际完整安排|观察结果等于实际完整安排|采纳.{0,12}一致性"),
                      ("有限矩",r"存在且有限"),("暴露映射", {GROUP_E1:r"严格超过一半|严格过半时",GROUP_E4:r"取精确人数|精确邻居人数",GROUP_E5:r"至少一名朋友收到邀请记|至少一位邻居接受处理时"}[rule])]
        if isinstance(design, types.TwoStageQuotaMixtureDesignV27):
            conditions += [("组间干扰",r"不同组之间没有干扰|组间无干扰"),("名额通知",r"不能确认名额通知" if notification_gap else r"名额方案本身不直接影响|第一阶段通知没有直接效应")]
        for subject, pattern in conditions:
            for source in sources:
                lines = re.split(r"[。\n]",source["text"]) if revision >= 4 else source["text"].splitlines()
                hit = next((line.strip() for line in lines if re.search(pattern,line)), None)
                if hit:
                    assumptions.append(dict(kind="other",subject=subject,statement=hit,quote=hit,source=source["source_id"]))
                    break
        answers.append(dict(question_part=part,target=target,status=state,functional=expr,value=None,assumptions=assumptions,
            estimate_handoff=dict(mode=mode,scope=scope_kind,population=population,variables=["Y_i","T_i","S_i","W"],
                exposure=RULES[rule],operator=expr,support={n:{f"{a},{s}":row[f"{a},{s}"] for a,s in (left,right)} for n,row in joint.items()}),
            reason=expr if part_gaps or zero else "完整分配可交换和一致性把各条件政策均值化为逐人观察条件均值，再按预定权重求差。总体算子与有限样本记录分开。"))
    return dict(answer=answers[0] if len(answers)==1 else {"answers":answers},proof=proof,checks=checks,questions=questions)
