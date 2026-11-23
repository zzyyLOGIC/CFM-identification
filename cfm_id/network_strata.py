"""Read an explicitly declared two-stratum fixed-quota design from original materials."""
import csv
import io
import re
from fractions import Fraction

from .network_protocol_terms import NUM, integer, named_units


LAYER = r"(?:第?[一二12]层|层[一二12])"
EACH = r"(?:每(?:一)?层|各层|两层(?:各|分别))"
UNIT = r"(?:个单位|个节点|家门店|个站点|个对象|个|位|名|人|站|家|店|所|台|席|户)"
CUE = r"分层|每层|各层|两层|层间|层内|" + LAYER
CONFLICT = (r"不独立|并非(?:相互)?独立|无[法从].{0,6}确定|不清楚|是否|尚未|待定|假如|假设|拟(?:采用|按)|备选|"
            r"不等概|按.{0,10}加权|有放回|可拒绝|未依从|改用|撤回|个人独立|逐人独立|共用一|"
            r"(?:第三|三|多)层|层间.{0,5}(?:相关|联动|互斥)|(?:仅有|只有|仅知)边际|全(?:网|体|名册).{0,8}(?:统一抽|只抽|抽取|共抽|恰抽)|(?:不|未)(?:是|声明|确认)?.{0,5}(?:独立|等概率)")
INDEPENDENT = re.compile(r"(?:两层|各层|层间|层与层)(?:之间)?(?:的抽签|抽签|彼此|各自|相互|均|分别|\s)*独立")
UNIFORM = re.compile(r"("+EACH+r"|层内|"+LAYER+r")[^。；;，,]{0,20}(?:等概率|等机会|均匀|简单随机)")
UNIFORM_SUBSETS = re.compile(r"("+EACH+r"|层内|"+LAYER+r")[^。；;，,]{0,20}"
                            r"(?:简单随机|(?:等概率|均匀)无放回抽|(?:子集|组合|名单)(?:均|都)?等概率)")
STRATUM_COLUMN = re.compile(r"抽签(?:分层|层|组)|随机化(?:分层|层)|分配层|randomization_strat(?:um|a)|assignment_stratum", re.I)
NODE_ID = {"node_id", "unit_id", "id", "对象编号", "门店编号", "节点编号"}
TECHNICAL = {"uploaded_network","uploaded_data_schema","uploaded_data_inventory",
             "shared_roster","shared_edges","shared_observations"}


def layer_index(label):
    if re.fullmatch(r"(?:第?[一1]层|层[一1]|[1一])",label):
        return 0
    if re.fullmatch(r"(?:第?[二2]层|层[二2]|[2二])",label):
        return 1
    return None


def uniform_for_quotas(text, counts):
    stated={layer_index(m[1]) for m in UNIFORM.finditer(text)}
    subsets={layer_index(m[1]) for m in UNIFORM_SUBSETS.finditer(text)}
    # Equal inclusion probabilities suffice for a single draw; they need not
    # determine the joint law of several treated members of the same stratum.
    return all((None in stated or i in stated) and (k<=1 or None in subsets or i in subsets)
               for i,k in enumerate(counts))


def declared_members(text, nodes):
    """Every membership claim must consume its whole list, including an explicit complement."""
    groups = [None, None]
    complement = {}
    # Split at a change of declaration, never at commas between roster identifiers.
    text=re.sub(r"((?:属于|划入|列入|为|是)"+LAYER+r")[，,]",r"\1。",text)
    pieces = re.split(r"[。；;\n]|[，,]\s*(?=其余|剩余|其[他它]|" + LAYER + r"(?:为|是|包括|含|[：:]))",text)
    for piece in pieces:
        part = piece.strip().strip("【】")
        forward = re.fullmatch(r"(.+?)(?:属于|列入|划入|为|是)(" + LAYER + r")",part)
        reverse = re.fullmatch(r"(" + LAYER + r")(?:为|是|包括|含|[：:])(.+)",part)
        if not forward and not reverse:
            if re.search(r"(?:属于|划入|为|是)"+LAYER+"|"+LAYER+r"(?:为|是|包括|含|[：:])",part):
                return None
            continue
        names, label = forward.groups() if forward else tuple(reversed(reverse.groups()))
        idx = layer_index(label)
        rest = re.fullmatch(r"(?:其余|剩余|其[他它])(?:的)?("+NUM+r")?(?:"+UNIT+r")?",names)
        if rest:
            count=integer(rest[1]) if rest[1] else None
            if idx in complement and complement[idx]!=count:
                return None
            complement[idx]=count
            continue
        parsed=named_units(names.strip(),nodes)
        if not parsed or len(set(parsed))!=len(parsed):
            return None
        member_set=set(parsed)
        if groups[idx] is not None and member_set!=groups[idx]:
            return None
        groups[idx]=member_set
    for idx,count in complement.items():
        other=groups[1-idx]
        if not other:
            return None
        rest=set(nodes)-other
        if not rest or count is not None and count!=len(rest) or groups[idx] is not None and groups[idx]!=rest:
            return None
        groups[idx]=rest
    if not any(groups):
        return []
    if not all(groups) or groups[0]&groups[1] or groups[0]|groups[1]!=set(nodes):
        return None
    return [[n for n in nodes if n in group] for group in groups]


def quotas(text):
    values=[set(),set()]
    pattern=(r"("+EACH+"|"+LAYER+r")(?:内|中)?\s*(?:均|都|分别|各|恰好|恰|仅|再|独立|等概率|等机会|均匀|随机|无放回|地|\s)*"
             r"(?:抽取|抽出|选出|选定|抽|启用|名额为|名额是)\s*("+NUM+r")\s*(?:"+UNIT+r")?")
    for m in re.finditer(pattern,text):
        amount=integer(m[2])
        if amount is None:
            return None
        idx=layer_index(m[1])
        for i in ([0,1] if idx is None else [idx]):
            values[i].add(amount)
    if any(len(v)!=1 for v in values):
        return None
    return [next(iter(v)) for v in values]


def table_partition(rows, nodes, column):
    ids=[i for i,value in enumerate(rows[0]) if value.strip().lower() in NODE_ID]
    if len(ids)!=1:
        return None
    by_node={}
    for row in rows[1:]:
        if max(column,ids[0])>=len(row):
            return None
        name=row[ids[0]].strip()
        idx=layer_index(row[column].strip())
        if name in by_node or idx is None:
            return None
        by_node[name]=idx
    if set(by_node)!=set(nodes) or set(by_node.values())!={0,1}:
        return None
    return [[n for n in nodes if by_node[n]==i] for i in (0,1)]


def read(case, rows, nodes):
    """Bind a complete partition and two quotas, independently of the candidate or its citations."""
    evidence=[r for r in rows if r["source_id"] not in TECHNICAL and
              re.search(CUE+r"|独立|概率|放回|处理变量|分配变量|名额|抽|中签|全网|全体",r["quote"])]
    text="。".join(r["quote"] for r in evidence)
    if not INDEPENDENT.search(text) or re.search(CONFLICT,text):
        return None
    groups=declared_members(text,nodes)
    counts=quotas(text)
    if groups is None or counts is None or not uniform_for_quotas(text,counts):
        return None
    for s in case.get("sources",[]):
        if s["source_id"]!="shared_roster":
            continue
        data=list(csv.reader(io.StringIO(s["text"],newline="")))
        for j,header in enumerate(data[0] if data else []):
            if not STRATUM_COLUMN.fullmatch(header.strip()):
                continue
            tab=table_partition(data,nodes,j)
            if not tab or groups and tab!=groups or not groups and not re.search(r"按[^。；;]{0,12}(?:名册|抽签层|分配层|随机化层)[^。；;]{0,12}(?:分层|抽签)",text):
                return None
            groups=tab
            evidence.append(dict(source_id=s["source_id"],quote=s["text"].splitlines()[0]))
    if not groups or any(k<0 or k>len(g) for k,g in zip(counts,groups)):
        return None
    law=dict(kind="stratified",groups=groups,quotas=counts)
    from .network_query_binding import RATE, read_rate
    for node,expected in marginal_rates(law).items():
        values=re.findall(re.escape(node)+r"(?:的)?(?:入选|抽中|中签|启用)?(?:的)?概率(?:为|是|等于|[：:])\s*("+RATE+")",text)
        if any(read_rate(v)!=expected for v in values):
            return None
    return law,evidence


def marginal_rates(law):
    return {n:Fraction(k,len(g)) for g,k in zip(law["groups"],law["quotas"]) for n in g}


def candidate_agrees(proposal, law, nodes):
    """The old prompt has no 'stratified' enum. A 'fixed' label needs explicit within-layer quotas."""
    kind=proposal.get("kind")
    if kind not in ("fixed","other","stratified","two_group_fixed_quota_binary_v1"):
        return False
    text="。".join(str(proposal.get(k,"")) for k in ("description","quota"))
    if re.search(CONFLICT,text):
        return False
    by_name=declared_members(text,nodes)
    if by_name is None or by_name and by_name!=law["groups"]:
        return False
    groups=proposal.get("groups")
    if groups is not None and (not isinstance(groups,list) or len(groups)!=2 or any(
            not isinstance(g,list) or len(g)!=len(actual) or set(g)!=set(actual) for g,actual in zip(groups,law["groups"]))):
        return False
    if not by_name and not groups:
        return False
    typed=kind=="two_group_fixed_quota_binary_v1" and groups is not None
    if not typed and (not INDEPENDENT.search(text) or not uniform_for_quotas(text,law["quotas"])):
        return False
    numeric=proposal.get("quotas",proposal.get("treated_quotas"))
    stated=quotas(text)
    if numeric is not None and (not isinstance(numeric,list) or any(type(v) is not int for v in numeric) or numeric!=law["quotas"]):
        return False
    scalar=proposal.get("quota")
    if (scalar is not None and (not isinstance(scalar,str) or re.fullmatch(NUM,scalar.strip()))
            or stated and stated!=law["quotas"]):
        return False
    return numeric==law["quotas"] or stated==law["quotas"]
