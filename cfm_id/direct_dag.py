"""Source-bound, symbolic DAG checks after a direct answer. No review is signed here."""
import re
from itertools import combinations

from cfm_id_bridge.scientific_binding import sha
from . import dag_backdoor_contract as back, dag_backdoor_solver, dag_backdoor_verify
from . import dag_frontdoor_contract as front, dag_frontdoor_solver, dag_frontdoor_verify
from . import dag_id_contract, dag_id_solver, dag_id_verify


def sections(sources):
    parts = {}
    for source in sources:
        pieces = re.split(r"(?m)^##\s+([a-z]+)\s*$", source["text"])
        for name, value in zip(pieces[1::2], pieces[2::2]):
            parts.setdefault(name, []).append(value.strip())
        label = re.fullmatch(r"(variables|graph|model|information)\.md(?:\.txt)?", source.get("label", ""))
        if label:
            parts.setdefault(label[1], []).append(source["text"].strip())
    return {k: v[0] for k, v in parts.items() if len(v) == 1}


def variables(text):
    ordered = re.search(r"变量为([^。]+)。前三者有观测，最后一项没有观测", text)
    if ordered:
        names = ordered[1].split("、")
        if len(names) == 4:
            return names[:3], names[3:]
    observed, latent = [], []
    for line in text.strip().splitlines():
        m = re.fullmatch(r"([\w-]{1,30})表示[^。\n]+[；;](有记录|没有记录|未观测)。", line.strip())
        if not m:
            return [], []
        (observed if m[2] == "有记录" else latent).append(m[1])
    return observed, latent


def roles(q, observed):
    def mentioned(fragment):
        # An outcome may have a time prefix in its registered full name.
        return [n for n in observed if n in fragment or (len(n) >= 4 and n[-2:] in fragment)]
    explicit = re.search(r'将[“「]([^”」]+)[”」]设为[01]和[01].*?[“「]([^”」]+)[”」]的总体分布', q)
    if explicit and all(n in observed for n in explicit.groups()):
        return explicit.groups()
    terms = re.search(r"主动改变(.{1,35}?)后[，,]?(.{1,30}?)(?:的概率|发生的分布|的总体分布)", q)
    if not terms and "干预后分布" in q:
        terms = re.search(r"是否存在(.{1,16}?)到(.{1,16}?)的直接边", q)
    if terms:
        x, y = map(mentioned, terms.groups())
        if len(x) == len(y) == 1 and x != y:
            return x[0], y[0]
    return None


def parse_edges(text, nodes, *, bound_names=False, qualified_text=""):
    names = {n: [n] for n in nodes}
    if qualified_text:
        for node in nodes:
            timed = re.fullmatch(r"(随访|基线|期末|术后)([\w-]{2,})", node)
            if timed and re.search(re.escape(timed[1])+r"(?:期间|时|中|的)"+re.escape(timed[2]), qualified_text):
                names[node].append(timed[2])
    edges = []
    forbidden = []
    for clause in re.split(r"[。；;\n]+", text.replace("**", "")):
        clause = clause.strip()
        if bound_names:
            negative = [(a,b) for a in nodes for b in nodes
                        if any(clause == f"没有{x}到{y}的直接边" for x in names[a] for y in names[b])]
            if qualified_text and len(negative)>1:
                return None
            if negative:
                forbidden.extend(negative)
                continue
            if clause.startswith("没有") and clause.endswith("的直接边"):
                return None
        if not clause or re.fullmatch(r"没有其他直接边|没有[\w-]+到[\w-]+的直接边|研究背景[：:][^。]+", clause):
            continue
        if bound_names:
            pairs = [(a,b) for a in nodes for b in nodes
                     if any(clause == a+verb+b for verb in ("直接影响","还直接影响","直接影响到","还直接影响到"))]
            if len(pairs) != 1:
                return None
            edges.append(list(pairs[0]))
            continue
        pair = re.fullmatch(r"([\w-]+?)(?:还)?直接影响(?:到)?([\w-]+)", clause)
        if not pair or not set(pair.groups()) <= set(nodes):
            return None
        edges.append(list(pair.groups()))
    return None if any(list(p) in edges for p in forbidden) else edges


def verified(case, *, revision=3):
    q, sources = case["business_question"], case["sources"]
    parts = sections(sources)
    if not {"variables", "graph", "model", "information"} <= parts.keys():
        return None
    obs, lat = variables(parts["variables"])
    target = roles(q, obs)
    if not target or len(obs + lat) > back.MAX_N or len(set(obs + lat)) != len(obs + lat):
        return None
    x, y = target
    if not re.search(r"总体分布|干预后分布|发生的分布", q) or re.search(r"减去|风险差|分别.*差|只取|联合干预", q):
        return None
    model, graph, info = (parts[k] for k in ("model", "graph", "information"))
    context_match = re.search(r"(?:研究背景|研究对象和时期是)[：:]?([^。\n]+)", "\n".join((model,graph,parts["variables"])))
    context = context_match[1] if context_match else None
    if not context or not re.search(r"二元|[01]和[01]|为1、.{0,8}为0", parts["variables"] + info):
        return None
    # Other attachments may add restrictions or updates. Only indexed sections and a plain
    # dictionary are understood. Extra study facts require another reading.
    recognized = {v for n, v in parts.items() if n in ("variables", "graph", "model", "information")}
    for s in sources:
        t = s["text"].strip()
        if t in recognized or t.startswith("## variables") or s.get("label", "").startswith("data_dictionary.md") or s["source_id"].startswith("user_reply_"):
            continue
        return None
    updates = [s["text"].strip() for s in sources if s["source_id"].startswith("user_reply_")]
    if updates:
        # A new, complete replacement model statement can resolve an earlier explicit unknown.
        # An affirmative reply alone does not identify which edges or assumptions changed.
        if len(updates) != 1 or re.search(r"不能|尚未|未知|不独立|新增|删除|拒绝|还有|不完整", updates[0]):
            return None
        if updates[0].startswith("更新模型声明："):
            model = updates[0].removeprefix("更新模型声明：")
        elif ("全部直接因果关系" in updates[0] or "直接因果边完整" in updates[0]) and ("全部共同原因" in updates[0] or "所有共同原因均已" in updates[0]):
            if revision >= 4:
                # Resolve only a prior missing declaration. Contradictory edges and
                # the other structural assumptions still have to pass independently.
                model = re.sub(r"[^。\n]*(?:尚未说明|尚未确认)[^。\n]*(?:穷尽|完整)[^。\n]*。", "", model)
            model += "\n" + updates[0]
        else:
            return None
    complete = bool(re.search(r"全部直接因果关系|直接因果边完整", model)) and bool(re.search(r"全部共同原因|所有共同原因均已", model))
    independent = "噪声相互独立" in model
    modular = bool(re.search(r"其他(?:结构)?机制(?:保持)?不变", model))
    law = bool(re.search(r"完整(?:符号)?(?:联合总体分布|总体联合分布)", info)) and bool(re.search(r"严格大于零|严格为正", info))
    target_desc = dict(quantity="level", scope="whole", population=context, intervention=f"do({x}=x), x∈{{0,1}}", reference=None, outcome=y, time=context)
    assumptions = [dict(kind="other", subject="DAG", statement=model, quote=model),
                   dict(kind="other", subject="P", statement=info, quote=info)]
    hand = dict(scope="whole", population=context, variables=obs, support="所用观察联合条件概率的分母须为正")
    checks = []
    def result(status, expression, certificate, message, *, ask=None):
        mode = "ESTIMATE_POINT" if status == "POINT" else "STOP"
        ans = dict(target=target_desc, status=status, functional=expression, value=None, assumptions=assumptions,
                   estimate_handoff=dict(hand, mode=mode, operator=expression if mode == "ESTIMATE_POINT" else "STOP"), reason=message)
        return dict(answer=ans, proof=certificate, checks=checks, questions=ask or [])
    if not complete or not independent or not modular or not law:
        missing = [s for ok, s in [(complete, "全部直接边和可能遗漏的共同原因，尤其是干预到结局的直接路径"),
                                    (independent, "结构方程剩余误差的独立性"), (modular, "设定处理时其他机制不变"),
                                    (law, "可用的观测总体联合分布及其正支持")] if not ok]
        question = "请说明" + "、".join(missing) + "，并提供相应的模型或信息声明。"
        checks.append(dict(code="DAG_DECLARATION", state="UNCHECKED", detail=question))
        return result("NEEDS_INPUT", question, dict(method="DAG_INPUT", source_sha256=sha(sources)), "现有声明不足以确定该干预分布。", ask=[question])
    edges = parse_edges(graph, obs + lat, bound_names=revision >= 4, qualified_text=q if revision >= 6 else "")
    if edges is None or "无环" not in model or re.search(r"不能确认|尚未|未知|拒绝|不完整|不独立", model):
        return None
    common = dict(model="RECURSIVE_SCM_EXPLICIT_LATENTS_INDEPENDENT_ERRORS", variable_domain="BINARY",
                  nodes=obs+lat, observed=obs, latent=lat, edges=edges, graph_status="DECLARED", graph_source=graph,
                  materials_sha256=sha(sources), context=context, treatment=x, outcome=y, additional_restrictions=[],
                  information=dict(source_id="observed_joint", source_sha256=sha(info), variables=obs,
                                   availability="SYMBOLIC_POPULATION_LAW", strictly_positive_joint=True, provenance=info))
    fp = front.FrontdoorProblem(**common, version=front.VERSION, frontdoor_variable=None)
    front.validate(fp)
    candidates = {}
    for m in sorted(set(obs)-{x,y}):
        conditions, _ = dag_frontdoor_solver.check_candidate(fp, m)
        if conditions != dag_frontdoor_verify.independent_conditions(fp, m):
            raise ValueError("FRONTDOOR_CHECK_DISAGREEMENT")
        candidates[m] = conditions
    checks.append(dict(code="FRONTDOOR", state="CHECKED", detail=f"逐一检查全中介、处理到中介后门及给定处理后中介到结局后门。{candidates}"))
    proof = dict(source_sha256=sha(sources), frontdoor=candidates)
    bp = back.BackdoorProblem(**common, version=back.VERSION, adjustment=None)
    try:
        cert = dag_backdoor_solver.solve(bp)
    except back.Unavailable as exc:
        if exc.reason != "NO_CLASSICAL_BACKDOOR_SET":
            raise
    else:
        if not dag_backdoor_verify.replay(cert, problem=bp):
            raise ValueError("BACKDOOR_REPLAY_FAILED")
        z = ",".join(cert["adjustment"])
        expr = f"Σ_z P({y}=y | {x}=x, z) P(z), z=({z})" if z else f"P({y}=y | {x}=x)"
        msg = "按所给递归模型作一致的干预，对处理前充分调整集标准化。" if z else "空集已阻断处理的后门路径。总效应保留处理中介的自然分布。"
        for name in dag_backdoor_solver.descendants(obs+lat, edges, x):
            if re.search(r"控制[“「]?"+re.escape(name), q):
                msg += f"固定处理后变量{name}会改变原总分布目标。"
        proof.update(method="BACKDOOR", certificate=cert)
        return result("POINT", expr, proof, msg)
    if any(all(c.values()) for c in candidates.values()):
        cert = dag_frontdoor_solver.solve(fp)
        if not dag_frontdoor_verify.replay(cert, problem=fp):
            raise ValueError("FRONTDOOR_REPLAY_FAILED")
        m = cert["frontdoor_variable"]
        expr = f"Σ_m P({m}=m | {x}=x) Σ_b P({y}=y | {m}=m, {x}=b) P({x}=b)"
        proof.update(method="FRONTDOOR", certificate=cert)
        return result("POINT", expr, proof, f"{m}截住全部有向路径，{x}到{m}无开放后门，给定{x}阻断{m}至{y}的后门。一致干预及正支持下由前门公式识别。")
    # Only project independent root latents with two observed children; no arbitrary
    # latent projection or relaxation of the model is implicit.
    if any(any(b == u for a,b in edges) or len([b for a,b in edges if a == u and b in obs]) != 2 for u in lat):
        return None
    pairs = {tuple(sorted(pair)) for u in lat for pair in combinations([b for a,b in edges if a == u], 2)}
    ip = dag_id_contract.DagIdProblem(nodes=obs, directed=[[a,b] for a,b in edges if a in obs and b in obs],
                                      bidirected=[list(p) for p in sorted(pairs)], treatment=x, outcome=[y], context=context)
    out = dag_id_solver.identify_or_report(ip)
    if out.get("nonidentification_proved"):
        proof.update(method="ID_HEDGE", certificate=out)
        reason = "前门或后门失败本身不能定论。一般 ID 在指定图内找到了经独立验证的 hedge，两种兼容机制可以有相同观察律与不同干预律。"
        return result("NOT_POINT", reason, proof, reason)
    if out.get("status") == "POINT" and dag_id_verify.replay(out, ip)["passed"]:
        proof.update(method="GENERAL_ID", certificate=out)
        return result("POINT", out["functional"], proof, "在给定因果图、干预一致性及正支持条件下，由一般 ID 分解得到所附观察律运算树。")
    return None
