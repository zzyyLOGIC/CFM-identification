"""Compare the local operator's actual coordinates with the question, protocol and uploaded graph.

An inability to read a design is a limitation of the verifier. It is not a finding of
zero support and does not authorize changing the answer or registering queries.
"""
import csv
import io
import re
from copy import deepcopy
from fractions import Fraction

from cfm_id_llm.compact_study import digest
from cfm_id_llm.network_files import _column
from . import uploaded_network_contrast as contrast
from . import uploaded_network_sources as sources
from .direct_verification import bound_network
from .network_grounded_contrast import source_lines
from .network_protocol_terms import integer, NUM, uniform_quota, named_units
from .network_response import unpack, typed_fields
from . import network_strata


VERSION = "network-source-alignment/1"
LABELS = {"population": "焦点人群与权重", "ends": "比较两端及顺序",
          "exposure": "暴露映射与关系表", "assignment": "分配变量与联合抽签规则"}
GENERATED = {"uploaded_network", "uploaded_data_schema", "uploaded_data_inventory",
             "shared_roster", "shared_edges", "shared_observations"}
RESTRICT = r"(?:只|仅)(?:评价|评估|考察|看|评)|评价对象(?:为|是)"
WHOLE = r"(?:全体|全部|完整名册内)(?:的)?\s*(" + NUM + r")?\s*(?:家|位|人|站|店|门店|单位|站点|节点|对象|个|所)"
EQUAL = r"等权|同权|同等权重|权重(?:均)?相同|同样权重|分量相同"
WEIGHT_CHANGE = r"不等权|不(?:再)?相同|除.{1,25}(?:外|以外)|(?:按|依).{0,12}(?:权重|加权)|权重(?:分别|依次)|(?:只看|仅看)(?:实际|中签|已)|排除"
COMPLEX_DESIGNS = (
    ("stratified", r"分层|每层|各层|层内|层间|两层"),
    ("grouped", r"按组|分组|组内|每组|各组|组间|整群|集群"),
    ("joint_list", r"以下.{0,10}(?:名单|安排)|名单及其概率|逐份名单|名单分别|可能的完整名单|仅有.{0,8}份名单"),
    ("shared", r"同一张签|同签|共签|共用.{0,7}(?:签|硬币)|同掷一枚"),
)
UNCERTAIN_LAW = r"拟(?:采用|使用|按)|假如|假设(?:各|每|独立)|尚未|是否|不清楚|无法确认|未确定|只有边际|备选|改(?:为|用)|可拒绝|未依从|自行决定|按.{0,12}加权|不等概率|有放回|不(?:是|再|能)(?:各自)?独立"
LAW_WORDS = r"抽签|抽取|抽出|概率|机会|随机|投币|分配变量|处理变量|分层|每层|共用|按组|联合分配"


def refs(rows):
    return [{"source_id": r["source_id"], "quote": r["quote"]} for r in rows]


def relevant(rows, pattern):
    return [r for r in rows if re.search(pattern, r["quote"])]


def population(rows, nodes):
    """Consume the whole restriction. An unrecognised second name cannot disappear."""
    claims = []
    evidence = []
    weights = relevant(rows, EQUAL + r"|各占一半|各半")
    for row in rows:
        line = row["quote"]
        if re.search(WEIGHT_CHANGE, line):
            return None, [row]
        limits = list(re.finditer(RESTRICT, line))
        whole = list(re.finditer(WHOLE, line))
        if limits:
            for m in limits:
                clause = line[m.end():].strip()
                clause = clause.translate(str.maketrans("", "", "【】「」"))
                # A following comma may join further names or start a weight/contrast clause.
                clause = re.split(r"[，,]\s*(?=(?:" + NUM + r")?(?:站|店|人|家|个单位)?各占|各半|等权|同权|按(?:原|\s*\()|当|比较|其余|本人|本站|\(T,S\))", clause)[0]
                selected = named_units(clause.strip(), nodes)
                if not selected or len(set(selected)) != len(selected):
                    return None, [row]
                claims.append(selected)
        elif whole:
            if any(m[1] and integer(m[1]) != len(nodes) for m in whole):
                return None, [row]
            claims.append(list(nodes))
        if limits or whole:
            evidence.append(row)
    if not claims or any(set(s) != set(claims[0]) for s in claims):
        return None, evidence
    group = claims[0]
    if len(group) > 1 and not any(re.search(EQUAL, r["quote"]) or len(group) == 2 and re.search(r"各占一半|各半",r["quote"]) for r in weights):
        return None, evidence
    return dict.fromkeys(group, str(Fraction(1, len(group)))), evidence + [w for w in weights if w not in evidence]


def uploaded_graph_agrees(case, table, docs):
    if (table.completeness != "COMPLETE" or not re.search(contrast.PRE, table.description)
            or re.search(r"事后|处理后|试点后|抽签后|尚未|不确定", table.description)
            or relevant(docs, r"(?:关系|边表|网络|邻居名单).{0,14}(?:不完整|缺行|互相矛盾)|(?:处理后|抽签后|事后).{0,14}(?:记录|调查).{0,10}(?:关系|邻居)")
            or not sources.matches_file_declarations(table, docs)):
        return False
    raw = {s["source_id"]: s["text"] for s in case["sources"]}
    if "shared_roster" not in raw and "shared_edges" not in raw:
        return True  # bound_network has already checked the native, hashed file manifest.
    if not {"shared_roster", "shared_edges"} <= raw.keys():
        return False
    roster = list(csv.reader(io.StringIO(raw["shared_roster"], newline="")))
    edges = list(csv.reader(io.StringIO(raw["shared_edges"], newline="")))
    index = _column(roster[0], {"node_id", "unit_id", "id", "对象编号", "门店编号", "节点编号"})
    left = _column(edges[0], {"source", "unit_a", "from", "对象1", "对象一", "起点"})
    right = _column(edges[0], {"target", "unit_b", "to", "对象2", "对象二", "终点"})
    return ([r[index].strip() for r in roster[1:]] == list(table.nodes)
            and len(edges) - 1 == len(table.edges)
            and {frozenset((r[left].strip(), r[right].strip())) for r in edges[1:]} == {frozenset(e) for e in table.edges})


def focal_reading(rows, nodes):
    scope_rows=[r for r in rows if r["source_id"] in ("question",) or r["source_id"] not in GENERATED and
                (re.search(RESTRICT+"|评价人群|评价对象|权重|不等权|加权",r["quote"]) or r["source_id"].startswith("user_reply_"))]
    return population(scope_rows,nodes)


def assignment(rows, nodes, arm_text, *, source_case=None):
    evidence = relevant(rows, LAW_WORDS)
    lines = [r["quote"] for r in evidence]
    text = "。".join(lines)
    for name, pattern in COMPLEX_DESIGNS:
        if re.search(pattern, text):
            if name=="stratified" and source_case is not None:
                parsed=network_strata.read(source_case,rows,nodes)
                variable=contrast.treatment_name(arm_text,lines,text)
                if parsed and variable:
                    law,spans=parsed
                    return dict(law,variable=variable),spans
            if (name == "shared" and not re.search(UNCERTAIN_LAW + r"|独立抽签|名额|无放回", text)
                    and re.search(r"公平|等概率", text)
                    and re.search(r"正面.{0,8}(?:全部|全体|全开).{0,18}反面.{0,8}(?:全部不|全体不|全关|全部未)", text)):
                variable = contrast.treatment_name(arm_text, lines, text)
                if variable:
                    return dict(kind="shared",p="1/2",variable=variable), evidence
            # Preserve the intended family when its particular parameters cannot be bound.
            return {"protocol": name}, relevant(evidence, pattern)
    if re.search(UNCERTAIN_LAW, text):
        return None, evidence
    independent = bool(re.search(r"独立(?:抽签|分配|随机|投币)|(?:彼此|各自|相互)独立", text))
    fixed = uniform_quota(lines, nodes)
    if fixed is not None and not independent:
        sizes = re.findall(r"(?:全(?:部|体)|从|在)(" + NUM + r")(?:个单位|个站|人|家|站|台|区)", text)
        law = {"kind": "fixed", "quota": fixed} if all(integer(s) == len(nodes) for s in sizes) else None
    elif independent and not re.search(r"无放回|固定名额|抽取|抽出|名额相同|相关抽签", text):
        law = contrast.actual_law(None, lines, nodes)
        if law and law.get("kind") != "independent":
            law = None
    else:
        law = None
    variable = contrast.treatment_name(arm_text, lines, text)
    if not variable or not law:
        return None, evidence
    from .network_query_binding import RATE
    for node in nodes:
        values = re.findall(re.escape(node) + r"(?:的)?(?:入选|抽中|中签|启用)?(?:的)?概率(?:为|是|等于|[：:])\s*(" + RATE + ")", text)
        expected = Fraction(law["quota"], len(nodes)) if law["kind"] == "fixed" else Fraction(law["p"][node])
        if any(contrast.read_rate(v) != expected for v in values):
            return None, evidence
    return dict(law, variable=variable), evidence


def field(source, used, rows, *, allowed=True):
    state = "UNCHECKED" if source is None or used is None else "MATCH" if source == used and allowed else "DISAGREEMENT"
    return dict(state=state, source=source, solver=used, evidence=refs(rows))


def check_table_terms(case, fields, nodes, *, source_scope=False):
    """Cross-check explicit design/target columns. Ordinary realized treatment is not a propensity."""
    relevant_columns = {
        "population": r"焦点|评价权重|评价对象|目标人群|目标权重|unit_weight|target_weight|is_focal|focal_weight",
        "ends": r"比较左端|比较右端|第一比较端|第二比较端|left_arm|right_arm",
        "exposure": r"暴露定义|暴露映射|暴露规则|邻居阈值|平票规则|exposure_rule|exposure_mapping",
        "assignment": r"分配概率|启用概率|抽中概率|中签概率|入选概率|抽签分层|抽签层|抽签组|抽签规则|propensity|assignment_probability|randomization_strat",
    }
    if source_scope:
        relevant_columns["assignment"]+="|"+network_strata.STRATUM_COLUMN.pattern
    for src in case["sources"]:
        sid, text = src["source_id"], src["text"]
        if sid in ("shared_roster", "shared_observations"):
            body = text
        elif not sid.startswith("shared_") and (src.get("label") or "").lower().endswith((".csv", ".tsv", ".xlsx")):
            body = text.partition("\n")[2] if text.startswith("工作") or "原行号" in text.partition("\n")[0] else text
        else:
            continue
        rows = list(csv.reader(io.StringIO(body, newline="")))
        if not rows:
            continue
        title = body.splitlines()[0]
        for j, column in enumerate(rows[0]):
            for name, pattern in relevant_columns.items():
                if not re.search(pattern, column.strip(), re.I):
                    continue
                f = fields[name]
                id_cols = [i for i, c in enumerate(rows[0]) if c.strip().lower() in
                           {"node_id","unit_id","id","对象编号","门店编号","节点编号"}]
                expected = None
                if name == "assignment" and re.search(r"概率|propensity|probability", column, re.I):
                    law = f["source"] or {}
                    if law.get("kind") == "independent":
                        expected = law["p"]
                    elif law.get("kind") == "fixed":
                        expected = dict.fromkeys(nodes, str(Fraction(law["quota"],len(nodes))))
                    elif law.get("kind") == "stratified":
                        expected = network_strata.marginal_rates(law)
                if name == "population" and re.search(r"权重|weight",column,re.I) and f["source"]:
                    expected = {n:f["source"].get(n,"0") for n in nodes}
                agrees = False
                if name=="assignment" and network_strata.STRATUM_COLUMN.fullmatch(column.strip()):
                    law=f["source"] or {}
                    agrees=law.get("kind")=="stratified" and network_strata.table_partition(rows,nodes,j)==law["groups"]
                if expected is not None and len(id_cols) == 1:
                    try:
                        pairs = [(r[id_cols[0]].strip(), contrast.read_rate(r[j].strip())) for r in rows[1:]]
                        agrees = (len(pairs) == len(nodes) and dict(pairs) == {n:Fraction(v) for n,v in expected.items()})
                    except (ArithmeticError, ValueError, IndexError, KeyError):
                        pass
                f["evidence"].append(dict(source_id=sid, quote=title))
                if not agrees:
                    f.update(state="UNCHECKED", table_note="上传表的“" + column + "”列尚未与求解输入核准。")


def population_matches(claim, members, *, allow_index_ranges=False):
    if len(claim) == len(set(claim)) and set(claim) == set(members):
        return True
    if not allow_index_ranges or len(claim) != 1:
        return False
    # The endpoints name actual IDs. Row positions, leading-zero identifiers and
    # descriptions of filtered groups cannot establish equality with the roster.
    expression = claim[0].strip().replace("（", "(").replace("）", ")")
    wrapper = re.fullmatch(r"(?:每家(?:门店|店)?|每个(?:对象|单位|节点|站点)?|每位(?:对象)?)\s*\(([^()]*)\)", expression)
    if wrapper:
        expression = wrapper[1].strip()
    match = re.fullmatch(r"[ij]\s*=\s*(0|[1-9][0-9]{0,17})\s*(?:\.\.|…|至)\s*(0|[1-9][0-9]{0,17})", expression)
    if not match:
        return False
    low, high = map(int, match.groups())
    return high - low + 1 == len(members) and all(
        re.fullmatch(r"0|[1-9][0-9]{0,17}", unit) and low <= int(unit) <= high for unit in members)


def assess(case, network, draft, proof, answer, *, source_scope=False,scope_resolution=None,allow_index_ranges=False):
    """Read declarations from the source, never from a model citation or an answer key."""
    table = bound_network(case, network)
    nodes = list(table.nodes)
    # Technical data inventories and raw observation rows are not research declarations.
    protocol = dict(case, sources=[s for s in case["sources"] if s["source_id"] not in GENERATED])
    rows = source_lines(protocol)
    qrows = [r for r in rows if r["source_id"] == "question"]
    docs = [r for r in rows if r["source_id"] != "question"]
    q = case["business_question"]
    members, scope_refs = focal_reading(rows, nodes)
    # The user can specify or amend the exposure and graph in the question itself.
    # Keep that declaration alongside the protocol. A comparison alone defines no map.
    sources_with_question = dict(protocol, sources=[*protocol["sources"], {"source_id": "question", "text": q}])
    rules = sources.exposure_rules(sources_with_question, rows)
    named = [name for name, evidence in rules.items() if evidence]
    rule = named[0] if len(named) == 1 else None
    exposure_refs = [r for evidence in rules.values() for r in evidence]
    if not named:
        from .network_reading import exposure
        explicit = [(r, exposure(r["quote"])) for r in rows if re.search(r"S\s*=|记为|编码为",r["quote"])]
        kinds = {value for _, value in explicit if value}
        if len(kinds) == 1:
            rule = kinds.pop()
            exposure_refs = [r for r, value in explicit if value == rule]
    changed_map = relevant(rows, r"至少一半|一半(?:及|或)以上|平票.{0,8}(?:记1|算高)|有向关系|加权邻居|按距离加权|暴露.{0,8}(?:未定|另有|改用)|不再按|(?:无邻居|孤立).{0,8}(?:未定|记为?1)")
    graph_ok = uploaded_graph_agrees(case, table, rows)
    pairs = [(r, contrast.question_arms(r["quote"], rule)) for r in qrows] if rule else []
    pairs = [(r, pair) for r, pair in pairs if pair]
    pair = [list(x) for x in pairs[0][1]] if len(pairs) == 1 else None
    remaining = bool(re.search(contrast.ORIGINAL, q)) and not re.search(r"而非|后者减前者|降低量|减少量|改用|不(?:再)?沿用|固定(?:其余|其他|具体)|(?:其余|其他).{0,7}固定|另(?:一问|外还)|再比较", q)
    amendment = relevant(docs, r"(?:改为|改问|换成|颠倒|反过来|本次改用|不再采用)")
    law, law_refs = assignment(rows, nodes, pairs[0][0]["quote"] if pairs else q,source_case=case if source_scope else None)
    from . import network_natural_sources as natural
    natural_binding = proof.get("binding_source")==natural.VERSION
    if natural_binding:
        # Re-read immutable source material rather than trusting the proof's coordinates.
        reading = natural.read(case,table,scope_resolution=scope_resolution)
        if not reading:
            return unavailable(case)
        members,scope_refs = reading["weights"],reading["group_rows"]
        rule,exposure_refs = reading["rule"],reading["map_rows"]
        pairs = [(reading["arm_row"],reading["pair"])]
        pair = [list(arm) for arm in reading["pair"]]
        remaining = bool(reading["remaining"])
        law,law_refs = reading["law"],reading["design_rows"]
    local = proof.get("binder") == "uploaded-network-comparison/1"
    native = proof.get("method") == "LOCAL_DESIGN_CONDITIONAL_MEAN" and bool(proof.get("joint_probabilities"))
    target = (answer or {}).get("target") or {}
    used = proof.get("population") if local or native else None
    weights = None
    if used and len(used) == len(set(used)) and target.get("population") == used:
        # This binder is defined for equal unit weights. Cross-check its actual signed query weights.
        weights = dict.fromkeys(used, str(Fraction(1, len(used))))
        handoff = answer.get("estimate_handoff") or {}
        if local and handoff.get("mode") == "ESTIMATE_POINT":
            forms = (handoff.get("operator_spec") or {}).get("forms")
            expected = [Fraction(s, len(used)) for _ in used for s in (1, -1)]
            if not forms or len(forms) != 1 or list(map(Fraction, forms[0])) != expected:
                weights = None
    ends = [list(map(int, value.split(","))) for value in proof["ordered_events"]] if local else None
    used_rule = proof.get("exposure") if local else None
    used_law = proof.get("assignment") if local else None
    if native:
        from . import direct_network as math
        from .network_event_handoff import RULES
        from .network_response import exact_event
        ends = [exact_event(str(target.get(k, "")).rsplit("=",1)[-1]) for k in ("intervention","reference")]
        used_rule = next((kind for kind, group in RULES.items() if math.RULES[group] == proof["exposure"]), None)
        design = proof.get("design") or {}
        coded = "(T,S)" in q.replace(" ", "") and not relevant(docs, r"仅.*邀请|资格|可拒绝|未依从")
        if coded and design.get("kind") == "complete_randomization_binary_v1":
            used_law = dict(kind="fixed", quota=design["m"], variable="T")
            m = uniform_quota([r["quote"] for r in law_refs], nodes)
            if not law and m is not None and not any(relevant(law_refs,p) for _,p in COMPLEX_DESIGNS) and not relevant(law_refs,UNCERTAIN_LAW):
                law = dict(kind="fixed", quota=m, variable="T")
    fields = {
        "population": field(members, weights, scope_refs),
        "ends": field(pair, ends, [r for r, _ in pairs] + amendment, allowed=remaining and not amendment),
        "exposure": field(rule if graph_ok and not changed_map else None, used_rule, exposure_refs + changed_map),
        "assignment": field(law, used_law, law_refs),
    }
    if natural_binding:
        fields["ends"]["evidence"].extend(refs([reading["remaining"]]))
    check_table_terms(case, fields, nodes,source_scope=source_scope)
    # When an explicit machine-readable claim disagrees, show both readings and hold delivery.
    normalized, location = unpack(draft)
    facts = typed_fields((normalized or {}).get("network_facts") or {})
    def cell(name):
        value = (facts.get(name) or {}).get("value")
        return value if isinstance(value, dict) else {}
    def conflict(name, value):
        fields[name].update(state="DISAGREEMENT", model=value)
    def check_population(claim):
        if not members or scope_resolution:
            return
        if isinstance(claim, list) and all(isinstance(unit, str) for unit in claim):
            units = claim
        elif allow_index_ranges and isinstance(claim, str) and re.search(r"[ij]\s*=\s*[0-9]+\s*(?:\.\.|…|至)", claim):
            units = [claim]
        else:
            return
        if not population_matches(units, members, allow_index_ranges=allow_index_ranges):
            conflict("population", claim)
    model = cell("contrast")
    people = model.get("population")
    check_population(people)
    from .direct_verification import answer_items
    raw_items = answer_items(draft)
    raw_target = (raw_items[0].get("target") or {}) if len(raw_items) == 1 else {}
    if not isinstance(raw_target, dict):
        raw_target = {}
    if natural_binding and members and not scope_resolution:
        scope = raw_target.get("scope")
        printed = raw_target.get("population")
        if isinstance(printed,str):
            named = named_units(re.split(r"[，,。]",printed)[0].strip(),nodes)
            if named and (len(set(named))!=len(named) or set(named)!=set(members)):
                conflict("population",printed)
        if scope=="compliers" or scope=="whole" and set(members)!=set(nodes):
            conflict("population",dict(scope=scope,population=raw_target.get("population")))
    explicit_group = raw_target.get("population")
    check_population(explicit_group)
    if not scope_resolution and members and not isinstance(explicit_group, list) and explicit_group in nodes and set(members) != {explicit_group}:
        conflict("population", explicit_group)
    for source, order in ((model, people), (raw_target, explicit_group)):
        declared_weights = source.get("weights", source.get("unit_weights"))
        if declared_weights is not None and members:
            if isinstance(declared_weights, list) and isinstance(order, list) and len(order) == len(declared_weights):
                declared_weights = dict(zip(order, declared_weights))
            if not isinstance(declared_weights,dict) or {n:Fraction(str(w)) for n,w in declared_weights.items() if Fraction(str(w))} != {n:Fraction(w) for n,w in members.items()}:
                conflict("population", declared_weights)
    if pair and any(key in model for key in ("left", "right")):
        parsed = [contrast.proposed_arm(model.get(k), rule) for k in ("left", "right")]
        if any(p is None or None in p for p in parsed) or [list(p) for p in parsed] != pair:
            conflict("ends", [model.get("left"), model.get("right")])
    if local and ends and [contrast.proposed_arm(target.get(k), rule) for k in ("intervention", "reference")] != [tuple(e) for e in ends]:
        fields["ends"]["state"] = "DISAGREEMENT"
    if pair and raw_target:
        for key, endpoint in zip(("intervention","reference"), pair):
            stated = contrast.proposed_arm(raw_target.get(key), rule)
            if stated and None not in stated and list(stated) != endpoint:
                conflict("ends", [raw_target.get("intervention"),raw_target.get("reference")])
    graph_claim = cell("network")
    if graph_claim:
        wrong = any(graph_claim.get(k) is False for k in ("pre_treatment", "complete", "undirected"))
        for key, actual in (("nodes", table.nodes), ("edges", table.edges)):
            proposed = graph_claim.get(key)
            if natural_binding and isinstance(proposed,dict):
                count = proposed.get("count")
                if count is not None:
                    wrong |= type(count) is not int or count!=len(actual)
                proposed = proposed.get("list",proposed.get("details"))
            if type(proposed) is int:
                wrong |= proposed != len(actual)
            elif isinstance(proposed, list):
                convert = set if key == "nodes" else lambda es: {frozenset(e) for e in es}
                wrong |= len(proposed) != len(actual) or convert(proposed) != convert(actual)
        if wrong:
            conflict("exposure", "模型摘录的网络与上传的处理前关系表存在分歧")
    model_rule = cell("exposure").get("kind")
    if model_rule and rule and model_rule != rule:
        conflict("exposure", model_rule)
    model_law = cell("assignment")
    if law and "kind" in law and model_law:
        subject = model_law.get("variable")
        if subject and subject != law["variable"]:
            conflict("assignment", model_law)
        if law["kind"]=="stratified":
            if not network_strata.candidate_agrees(model_law,law,nodes):
                conflict("assignment",model_law)
        elif model_law.get("kind") != law["kind"]:
            conflict("assignment", model_law)
        elif law["kind"] == "fixed" and model_law.get("quota") is not None and str(model_law["quota"]) != str(law["quota"]):
            conflict("assignment", model_law)
        probabilities = model_law.get("probabilities")
        if isinstance(probabilities, dict) and probabilities:
            expected = law.get("p")
            if law["kind"]=="stratified":
                expected=network_strata.marginal_rates(law)
            if not isinstance(expected, dict):
                common = expected if law["kind"] == "shared" else str(Fraction(law["quota"], len(nodes)))
                expected = dict.fromkeys(nodes, common)
            if set(probabilities) == set(nodes):
                agrees = all(contrast.read_rate(str(probabilities[k])) == Fraction(expected[k]) for k in nodes)
            else:
                name = next(iter(probabilities))
                agrees = (len(probabilities) == 1 and re.fullmatch(r"(?:每|各|全体|全部|所有)[^\d]{0,8}|all|common", name, re.I)
                          and {contrast.read_rate(str(probabilities[name]))} == set(map(Fraction, expected.values())))
            if not agrees:
                conflict("assignment", model_law)
    if location and location.get("state") != "LOCATED":
        conflict("ends", "多份摘录归属不同")
    return dict(version=VERSION, matched=all(f["state"] == "MATCH" for f in fields.values()),
                network_reference=table.token, fields=fields)


def substantive(draft):
    from .direct_verification import answer_items
    return any(item.get("status") or item.get("functional") or item.get("reason") for item in answer_items(draft))


def same_answer(draft, answer):
    from .direct_verification import answer_items
    def content(value):
        return [{k:v for k,v in item.items() if k != "network_facts"} for item in answer_items(value)]
    return content(draft) == content(answer)


def retain(report, draft, alignment, case, *, text_only=False):
    """The retained scientific answer and its own questions stay separate from a verifier disagreement."""
    from .direct_verification import retained_question
    for key in ("parts", "draft_parts", "review_record", "condition_review"):
        report.pop(key, None)
    reading = report.get("network_reading") or {}
    questions = list(report.get("clarification_questions") or [])
    if reading:
        # A failed projection must not present legacy inferred coordinates as corrected facts.
        from . import network_reading
        normalized, _ = unpack(draft)
        report["network_reading"] = network_reading.fact_evidence(case, normalized or {})
        for key in ("unresolved_design_sources", "clarification_evidence"):
            if key in reading:
                report["network_reading"][key] = reading[key]
    failed = [LABELS[k] for k, v in alignment["fields"].items() if v["state"] != "MATCH"]
    report.update(decision="RETAINED" if draft else "UNCHECKED", proof=None, conditional_answer=None,
                  effective_answer=deepcopy(draft) if draft else None, estimation_handoff_allowed=False,
                  scientific_approval=False, clarification_questions=[], network_alignment=alignment,
                  checks=[dict(code="NETWORK_SOURCE_ALIGNMENT", state="UNCHECKED",
                               detail="原文与求解输入尚未核准的项目为" + "、".join(failed) + "。本次没有登记估计查询。")])
    if alignment.get("source_target_complete"):
        report["checks"][0]["detail"] = "原问和上传表已核准求解坐标。模型在" + "、".join(failed) + "上的声明与之冲突，保留原答供复核。"
    else:
        retained_question(report)
    if text_only and questions and not report["clarification_questions"]:
        # Only an explicitly documented unresolved choice can open the reply form.
        # An unrecognised but fully supplied joint law is not a reason to ask again.
        document = "\n".join(s["text"] for s in case["sources"])
        if (reading.get("unresolved_design_sources") or reading.get("clarification_evidence")
                or re.search(r"分配设计待补|实际分配规则未提供", document) and not any(
                    s["source_id"].startswith("user_reply_") for s in case["sources"])):
            report["clarification_questions"] = questions


def unavailable(case):
    rows = source_lines(dict(case, sources=[s for s in case["sources"] if s["source_id"] not in GENERATED]))
    cues = {"population": RESTRICT + "|" + WHOLE + "|评价|权重", "ends": r"相比|比较|减去|两端|相对",
            "exposure": r"同伴|邻居|伙伴|合作门店|暴露", "assignment": LAW_WORDS}
    return dict(version=VERSION, matched=False, network_reference=None,
                fields={k:field(None, None, relevant(rows, cues[k])[:2]) for k in LABELS})


def text_replay(case, proof, answer):
    """Dedicated text-only methods bind their own target, including single-policy levels.

    Accept a supported projection only if the original question and documents alone give
    the identical target, formula and source certificate. A gap or model-only claim
    supplies no authority to replace an existing answer.
    """
    from . import (announced_quota_review, direct_network, direct_policy_exchange,
                   named_plan_level, network_grounded_contrast, network_query_binding, network_reading,
                   observed_peer_review, quota_policy_support, reported_peer_strata,
                   roster_event_review, unstratified_peer_rates)
    if proof.get("binder") == direct_policy_exchange.VERSION:
        return direct_policy_exchange.derive(case) == proof.get("evidence")
    q = case["business_question"]
    docs = [r for r in source_lines(case) if r["source_id"] != "question"]
    routes = {"NAMED_FULL_PLAN_LEVEL": named_plan_level, "OBSERVED_NODEWISE_STANDARDIZATION": observed_peer_review,
              "OBSERVED_PEER_CONDITION_GAP": observed_peer_review,
              "OBSERVED_REPORTED_STRATA": reported_peer_strata, "ANNOUNCED_TWO_STAGE_QUOTA": announced_quota_review,
              "FIXED_QUOTA_WHOLE_POLICY": quota_policy_support, "LABELED_OBSERVATIONAL_ARMS": unstratified_peer_rates}
    method = proof.get("method")
    if method in {"LOCAL_DESIGN_CONDITIONAL_MEAN","ORIGINAL_EVENT_MEANS"}:
        qrows = [r for r in source_lines(case) if r["source_id"] == "question"]
        used = proof.get("population") or []
        if re.search(RESTRICT, q):
            members, _ = population(qrows, proof.get("roster") or used)
            if not members or set(members) != set(used):
                return False
        for family, pattern in COMPLEX_DESIGNS:
            if relevant(docs, pattern) and proof.get("design") != family:
                return False
    if proof.get("binder") == "source-roster-local-events":
        result = roster_event_review.derive(q, docs)
    elif proof.get("binder") == "source-grounded-contrast/1":
        fields = proof.get("bound_fields") or {}
        if not all(fields.get(k) for k in ("population", "ends", "exposure", "assignment", "network")):
            return False
        result = network_grounded_contrast.derive(case, {})
    elif method in routes:
        result = routes[method].derive(q, docs)
    elif method in ("TWO_BINARY_POLICY_MARGINS", "ORIGINAL_EVENT_MEANS"):
        result = network_query_binding.source_result(case)
    elif method == "LOCAL_DESIGN_CONDITIONAL_MEAN" and proof.get("design") and proof.get("joint_probabilities"):
        result = network_reading.source_solution(case, None) or direct_network.verified(case, revision=7)
        if result and result.get("values"):
            values = result["values"]
            qrows = [r for r in source_lines(case) if r["source_id"] == "question"]
            group, _ = population(qrows, values["network"]["nodes"])
            if (not group or set(group) != set(values["contrast"]["population"])
                    or any(re.search(p, s["text"]) for _,p in COMPLEX_DESIGNS for s in case["sources"])):
                return False
    else:
        return False
    if not result or not result.get("proof") or digest(result["answer"]) != digest(answer):
        return False
    return all(digest(proof.get(k)) == digest(v) for k, v in result["proof"].items() if k != "model_field_spans")


def enforce(case, network, draft, report, review, *, source_scope=False,scope_resolution=None,allow_index_ranges=False):
    from .network_reading import network_case
    proof = report.get("proof") or {}
    answer = report.get("conditional_answer") or report.get("effective_answer") or {}
    if (report.get("decision") == "RETAINED" and not proof and not report.get("estimation_handoff_allowed") and not report.get("condition_review")
            and same_answer(draft, report.get("effective_answer"))):
        return
    if network is None:
        # A declared IV model often contains "no_interference" in its scientific
        # contract. That string does not make it a network exposure comparison.
        from . import direct_iv_evidence
        declared, _ = direct_iv_evidence.read_declaration(case)
        if declared or not network_case(case) or (not substantive(draft) and not report.get("estimation_handoff_allowed")):
            return
        if proof.get("method") in {"FRONTDOOR", "BACKDOOR", "ID_HEDGE", "GENERAL_ID"}:
            return
        try:
            if proof and text_replay(case, proof, answer):
                return
        except (ValueError, KeyError, TypeError, ArithmeticError, IndexError):
            pass
        alignment = unavailable(case)
    else:
        try:
            alignment = assess(case, network, draft, proof, answer,source_scope=source_scope,
                               scope_resolution=scope_resolution,allow_index_ranges=allow_index_ranges)
        except (ValueError, KeyError, TypeError, AttributeError, ArithmeticError, IndexError):
            alignment = unavailable(case)
    report["network_alignment"] = alignment
    if not alignment["matched"]:
        if (proof.get("binding_source")=="natural-network-materials/1"
                and all(v["state"]=="MATCH" or "model" in v and not v.get("table_note") and v["source"] is not None and v["source"]==v["solver"]
                        for v in alignment["fields"].values())):
            alignment["source_target_complete"] = True
        if review is not None:
            raise ValueError("NETWORK_ALIGNMENT_CHANGED_REVIEW_REQUIRED")
        retain(report, draft, alignment, case, text_only=network is None)
