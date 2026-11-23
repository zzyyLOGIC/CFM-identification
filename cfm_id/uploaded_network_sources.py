"""Bind a single original-design network comparison from user materials and the uploaded graph."""
import json
import re

from . import uploaded_network_contrast as contrast
from .network_grounded_contrast import source_lines
from .direct_verification import bound_network


def exposure_rules(case, rows):
    # The encoding has to be a protocol definition. A comparison mentioning a majority
    # does not by itself declare an exposure map for the entire study.
    patterns = {
        "majority": r"(?:严格)?(?:超过(?:一半|半数)|过半)(?:的邻居.{0,16})?[^；。]{0,26}?(?:算|记|为|编码)[^；。]{0,15}1",
        "any": r"至少(?:一|1)(?:位|名|个|家|站)?[^；。]{0,22}?(?:算|记|为|编码)[^；。]{0,7}1",
        "count": r"(?:暴露|同伴状态).{0,18}(?:精确人数|确切人数|实际人数|实际.{0,6}家数)|取精确人数",
    }
    peer_docs={s["source_id"] for s in case["sources"] if re.search(contrast.PEERS,s["text"])}
    return {key:[r for r in rows if r["source_id"] in peer_docs and re.search(p,r["quote"])]
            for key,p in patterns.items()}


def outcome_period(question_row, docs):
    # Bind the measured outcome to the original question and at least one independent
    # protocol statement. Dates and clock times come from that protocol, not a paraphrase.
    text=question_row["quote"]
    names={m[1].strip() for m in re.finditer(
        r"(?:^|[，,：:])([^，,。？！；:：]{1,36}?)(?:平均|的均值)?(?:会|将|能)?(?:高多少|增加多少|相差多少|会怎样变化|的平均差(?:是多少)?)$",text)}
    declared=set()
    for r in docs:
        for m in re.finditer(r"(?:结果(?:指标|变量)?|结局指标)(?:是|为|定义为|[：:])([^，,。；]{1,35})",r["quote"]):
            name=m[1].strip()
            if name in text:declared.add(name)
    # Prefer the protocol's outcome label to a colloquial phrase that includes units or a time qualifier.
    names=declared or {n for n in names if any(n in r["quote"] for r in docs)}
    if len(names)>1:
        return contrast.gap("题目与材料对应多个结果指标，请确认使用哪个指标。")
    if len(names)!=1:
        return None
    name=names.pop()
    date=r"\d{4}(?:年\d{1,2}月\d{1,2}日|[-/]\d{1,2}[-/]\d{1,2})"
    clock=r"\d{1,2}:\d{2}:\d{2}"
    interval=rf"{date}\s*{clock}\s*(?:至|到|—|–|~)\s*(?:{date}\s*)?{clock}(?:\s*[（(]?(?:UTC|GMT)(?:[+-]\d{{1,2}}(?::?\d{{2}})?)?[）)]?)?"
    periods=set()
    period_rows=[]
    outcome_sources={r["source_id"] for r in docs if name in r["quote"]}
    for r in docs:
        if r["source_id"] not in outcome_sources and not re.search(r"观察|评分|结果|结局|随访|考核|指标",r["quote"]):continue
        matches={m[0].strip() for m in re.finditer(interval,r["quote"])}
        if not matches:
            matches={m[1].strip() for m in re.finditer(
                r"(?:结果(?:的)?期间|随访期间|观察时段|观察期间|观察期|观察时期|考核期间|^时期)(?:为|是|[：:])([^，,。；]{1,35})",r["quote"])}
        if matches:
            periods.update(matches);period_rows.append(r)
    if len(periods)>1:
        return contrast.gap("材料列出了不同的结果期间，请核对本次比较两端采用的同一时期。")
    if not periods:
        return None
    return (name,periods.pop()),period_rows


def matches_file_declarations(table, docs):
    """Text describing the same roster/edge file is evidence; the model's summary is not."""
    for r in docs:
        line=r["quote"]
        counts=re.findall(r"(?:关系表|边表).{0,10}?(?:共|包括|包含|共有|有|列出)\s*(\d+)\s*条",line)
        if any(int(n)!=len(table.edges) for n in counts):return False
        counts=re.findall(r"(?:名册|完整名单).{0,8}?(?:包括|包含|共计|共有)\s*(\d+)\s*(?:家|人|个|位|所|座)",line)
        if any(int(n)!=len(table.nodes) for n in counts):return False
        edges=re.search(r"(?:完整边表|全部无向边|全部边|完整合作边)[：:为\s]*(\[\s*\[.*?\]\s*\])",line)
        if edges:
            try:named=json.loads(edges[1])
            except ValueError:return False
            if (any(not isinstance(e,list) or len(e)!=2 or not all(isinstance(n,str) for n in e) for e in named)
                    or len(named)!=len(table.edges) or {frozenset(e) for e in named}!={frozenset(e) for e in table.edges}):return False
    return True


def from_materials(case, network, *, extended=False, source_scope=False):
    q=case["business_question"]
    if (not re.search(contrast.ORIGINAL,q) or len(re.findall(r"[？?]",q))>1
            or re.search(r"第二问|另一问|反向再|两种设计|后者减前者|外推|另外还|还想(?:问|知道)|再比较|同时求|并(?:比较|报告|估计|计算)另一|降低量|减少量|低多少",q)):
        return None
    lines=source_lines(case)
    docs=[r for r in lines if r["source_id"] not in ("question","uploaded_network")]
    maps=exposure_rules(case,docs)
    candidates=[(rule,row,pair) for rule,ev in maps.items() if ev
                for row in lines if row["source_id"]=="question"
                for pair in [contrast.question_arms(row["quote"],rule)] if pair]
    if len(candidates)!=1:return None
    rule,row,pair=candidates[0]
    corpus="。".join(r["quote"] for r in docs)
    if any(r["source_id"].startswith("user_reply_") and
           re.search(r"改为|改用|改成|改问|替换|更正|撤回|取消|只看|颠倒|反过来",r["quote"]) for r in docs):
        return contrast.gap("请明确补充说明后采用的目标、比较两端与分配规则。")
    if (sum(bool(v) for v in maps.values())!=1 or
            re.search(r"至少一半|一半(?:及|或)以上|平票.{0,8}(?:记1|算高)|含平局.{0,6}(?:记1|为1)",corpus)):
        return contrast.gap("请核对原题使用的暴露映射及平局的归类。")
    if re.search(r"(?:其余|其他).{0,7}固定(?:为|不变)|固定(?:其余|其他|具体)|不(?:再)?沿用.{0,9}原(?:抽签|设计|分配)|改(?:用|为).{0,8}新政策",q+"。"+corpus):
        return contrast.gap("请确认两端内其余单位是否沿用原抽签的条件分布。")
    table=bound_network(case,network)
    if not matches_file_declarations(table,docs):
        return contrast.gap("上传的名册或关系表与业务材料中的完整表声明不一致，请核对实际采用的表。")
    if (table.completeness!="COMPLETE" or not re.search(contrast.PRE,table.description) or
            re.search(r"事后|处理后|试点后|抽签后|尚未|不确定",table.description) or
            re.search(r"(?:关系|邻居名单|网络|边表).{0,18}(?:试点后|事后|抽签后|处理后)|(?:试点后|事后|抽签后|处理后).{0,18}(?:调查|才登记|才记录).{0,9}(?:关系|邻居)|(?:关系表|网络).{0,8}(?:不完整|互相矛盾)",corpus)):
        return contrast.gap("请核准上传关系表的记录时期和完整性。")
    nodes=list(table.nodes)
    if len(nodes)>256:return None
    if re.search(r"不等权|权重不(?:同|等)|按.{0,10}(?:人数|营收|销售额|规模)(?:比例)?加权",corpus):
        return contrast.gap("请核对评价名册及其权重。")
    group=contrast.group_from_source(q,lines,nodes,None,source_only=True)
    scope_evidence=[]
    if source_scope:
        from .network_source_alignment import focal_reading
        weights,scope_evidence=focal_reading(lines,nodes)
        if weights:
            group=list(weights)
    if not group:return contrast.gap("请说明评价的是名册中的哪些单位，以及各单位的权重。")
    design=[r for r in lines if r["source_id"]!="uploaded_network" and
            re.search(r"抽签|投币|概率|机会|分配变量|无放回|固定名额|处理变量",r["quote"])]
    statements=[r["quote"] for r in design]
    from . import network_strata
    protocol=[r for r in lines if r["source_id"] not in network_strata.TECHNICAL]
    stratified=source_scope and any(re.search(network_strata.CUE,r["quote"]) for r in protocol)
    if re.search(r"是否独立|联合.{0,8}(?:未知|不清楚)|若(?:是|为)?独立抽签|假设独立抽签|两份.{0,8}(?:冲突|矛盾)|实际参加由|可拒绝|未依从",q+"。"+corpus):
        return contrast.gap("请核对实际分配的变量和完整名单的联合分配规则。")
    shared=[r for r in docs if re.search(r"共用一(?:张签|枚.{0,3}硬币)|同掷一枚",r["quote"])]
    if stratified:
        parsed=network_strata.read(case,protocol,nodes)
        if not parsed:
            return contrast.gap("两层抽签的完整分层名册、各层名额或层间独立规则尚未核准。")
        law,design=parsed
        statements=[r["quote"] for r in design]
    elif shared:
        # A common marginal probability does not identify the joint design. Require
        # both allocations and their actual randomization to be stated in the protocol.
        text="。".join(r["quote"] for r in shared)
        if (re.search(r"独立(?:抽签|投币)|无放回|固定名额|若|假如|尚未|不清楚",q+"。"+corpus)
                or not re.search(r"公平|等概率",text)
                or not re.search(r"正面.{0,8}(?:全部|全体|全开).{0,18}反面.{0,8}(?:全部不|全体不|全关|全部未)",text)):
            return contrast.gap("请核对共同抽签与其他设计说明，以及各完整名单的概率。")
        law={"kind":"shared","p":"1/2"}
    else:
        law=contrast.actual_law(None,statements,nodes)
        if extended and law is None and not re.search(r'共用|分层|分组|可拒绝|自行决定|各自独立|相互独立',corpus):
            from .network_protocol_terms import uniform_quota
            quota=uniform_quota(statements,nodes)
            if quota is not None:
                law=dict(kind='fixed',quota=quota)
    variable=contrast.treatment_name(row["quote"],statements,corpus)
    if extended and not variable and law and law['kind']=='fixed':
        names={m[1] for line in statements for m in re.finditer(
            r'(?:抽取|抽出|选出|抽)[\d一二两三四五六七八九十]+(?:台|站|个单位|区|人|家|席|线)(启用[^。，；,]{1,20})[，,](?:抽到即用|中签即用|中签即执行)',line)}
        if len(names)==1 and '启用' in row['quote']:
            variable=names.pop()
    if not law or not variable or (re.search(r"邀请|鼓励|资格",corpus) and not re.search(r"获邀|收到邀请",variable)):
        return contrast.gap("请确认实际随机分配的变量及联合分配规则。")
    labels=outcome_period(row,docs)
    if isinstance(labels,dict):
        return labels
    if not labels:
        # The historic binder can use an exact, source-backed model label when a
        # free-text protocol does not contain a unique machine-readable outcome.
        return None
    target_labels,period_rows=labels
    cited={"network":[r for r in lines if r["source_id"]=="uploaded_network"],
           "contrast":[row],"assignment":design,"exposure":maps[rule]}
    catalog=[]
    if extended:
        from .network_protocol_terms import population_queries
        catalog=population_queries(docs,group)
    bound=contrast.solve_materials(case,table,group,row,pair,rule,law,variable,target_labels,lines,docs,cited,
                                   population_rows=catalog)
    if bound and "result" in bound:
        proof=bound["result"]["proof"]
        proof["binding_source"]="uploaded-materials/1"
        proof["source_spans"].extend(period_rows)
        if stratified:
            proof["source_spans"].extend(scope_evidence)
    return bound
