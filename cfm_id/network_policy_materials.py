"""Bind finite whole-roster policies to source clauses. Unsupported prose has no executable projection."""
import re
from fractions import Fraction

from .network_grounded_contrast import source_lines
from .network_protocol_terms import NUM, integer, treated_neighbor_majority, uniform_quota
from .uploaded_network_contrast import PREMISES, NEG_SCI

RATE = r'(?:\d+/\d+|\d*\.\d+%?|\d+%?)'
NAME = r'[\w·-]{1,24}'


def split_names(value):
    return [n.strip() for n in re.split(r'[、，,与和及]', value) if n.strip()]


def fraction(value):
    return Fraction(value[:-1])/100 if value.endswith('%') else Fraction(value)


def single(rows, pattern):
    hits=[(r,m) for r in rows for m in re.finditer(pattern,r['quote'])]
    return hits[0] if len(hits)==1 else (None,None)


def assumptions(docs):
    items=[]
    for code,(label,pattern) in PREMISES.items():
        matches=[r for r in docs if re.search(pattern,r['quote'])]
        if code=='full_vector_randomization':
            matches=[r for r in matches if not re.search(r'新方案|新政策|目标(?:策略|政策|名单)',r['quote'])]
        if not matches or any(re.search(NEG_SCI+'|拟采用|假如|若采用',r['quote']) for r in matches):
            return []
        items.append(dict(code=code,label=label,**matches[0]))
    return items


def measure(docs,question):
    _,m=single(docs,r'(?:结果(?:指标|变量)?|结局指标)(?:为|是)([^，,。；]+)')
    if not m:
        return None
    label=m[1]
    period=re.search(r'下一班|次班|当班|当日|次日|当周|次周|当月|次月|本周|本月',label)
    if not period or period[0] not in question:
        return None
    outcome=re.sub(r'各.{0,2}(?='+re.escape(period[0])+r')|是否|指示量|指标|'+re.escape(period[0]),'',label)
    terms=[t for t in re.split(r'(成功|合格|达标)',outcome) if t]
    return (label,period[0]) if terms and all(t in question for t in terms) else None


def weighted_population(question,nodes):
    explicit=[split_names(s) for s in re.findall(r'在([^，。；]{1,180}?)之间等权',question)]
    sizes=[integer(n) for n in re.findall('('+NUM+r')(?:条|个|家)?(?:线|区|站|仓|组|节点|单位)等权',question)]
    if re.search(r'仅评|只评|只看|仅看|不等权|另.{0,3}权重|按.{0,9}加权',question):
        return False
    return bool(explicit or sizes) and all(x==nodes for x in explicit) and all(n==len(nodes) for n in sizes)


def policy_mixture(q,docs,nodes):
    law,_=single(docs,r'(?:可(?:以)?查询|提供|可用).{0,12}完整.{0,8}总体联合(?:分布|律).{0,15}(?:全名单|完整名单).{0,10}Y|'
                      r'(?:可|允许)(?:以)?按(?:完整|整份)名单(?:逐站|逐人|逐单位|逐节点)查询(?:结果|结局)的总体条件均值')
    draw,_=single(docs,r'(?:新方案|政策|策略).{0,18}(?:名单|分配).{0,8}独立于.{0,6}潜在结果')
    if (not law or not draw or not re.search(r'(?:其[他余]|未列)(?:线路|单位|节点|对象|站点|线|站)?(?:全部|都|均)?(?:关闭|不启用|关|不处理)',draw['quote'])
            or re.search(r'不能|未提供|只(?:含|支持)|仅(?:含|支持)|不含',law['quote'])):
        return None
    choices=[]; labels=set()
    terminal='('+RATE+r')(?:的[^，,。；]{0,18}?)?给([^，,。；]{1,100}?)(启用|开启|参加)([^，,。；]*)'
    prefix=r'以('+RATE+r')(?:的)?(?:概率|机会)(启用|开启|安排)([^，,。；]{1,100})'
    clauses=[]
    for part in re.split('[，,。；]',q):
        match=re.search(terminal,part)
        if match:
            clauses.append((match[1],match[2],match[3]+match[4] if match[4].strip() else None))
        else:
            match=re.search(prefix,part)
            if match:
                clauses.append((match[1],match[3],None))
    for weight,roster,operation in clauses:
        names=split_names(roster)
        if not names or not set(names)<=set(nodes) or len(set(names))!=len(names):
            return None
        choices.append((str(fraction(weight)),[int(n in names) for n in nodes]))
        if operation:
            labels.add(operation.strip())
    _,declared=single(docs,r'(?:处理变量|分配变量)(?:为|是|[：:])([^，,。；]{1,30})')
    if declared:
        labels.add(declared[1])
    if (len(choices)<2 or len(labels)!=1 or any(Fraction(p)<=0 for p,_ in choices)
            or sum(Fraction(p) for p,_ in choices)!=1 or len({tuple(z) for _,z in choices})!=len(choices)):
        return None
    stated=re.search(r'分别以([^，,。；]+?)选择',draw['quote'])
    if stated and [fraction(x.strip()) for x in stated[1].split('、')]!=[Fraction(p) for p,_ in choices]:
        return None
    return dict(operator='FINITE_POLICY_MEAN',treatment=labels.pop(),policies=choices,
                conditions=[dict(code='independent_policy',label='政策名单独立于潜在结果',**draw)],
                facts=[dict(label='所给总体查询接口',**law)],information=law)


def bounded_level(q,docs,nodes):
    if not re.search(r'全开|全体启用|全部开',q) or not re.search(r'区间|上下界|锐界',q):
        return None
    treatment=re.search(r'(?:一并|全部|全体)(开启|启用)([^，。；？]{1,20})',q)
    graph,g=single(docs,r'(?:处理前|事前)完整无向(?:关系网|网|图|边表)(?:只有|包括|为|是|[：:])(.+)')
    rule,_=single(docs,r'(?:严格过半|超过一半).{0,24}(?:暴露|状态)(?:为|记为)1.{0,8}平票(?:为|记为)0')
    suff,_=single(docs,r'(?:每个|所有|各).{0,8}[、，,]所有完整安排下.{0,10}(?:潜在)?均值只(?:取决于|依赖).{0,22}暴露')
    only,_=single(docs,r'(?:已知|所列|上述).{0,10}均值是全部总体信息')
    box,_=single(docs,r'(?:每个|各).{0,14}每种安排.{0,10}均值介于0与1(?:之间)?[，,].{0,22}没有.{0,18}额外约束')
    binary,_=single(docs,r'(?:取|为)(?:值)?0或1')
    if not all((treatment,graph,rule,suff,only,box,binary)):
        return None
    if not treated_neighbor_majority(rule['quote'], treatment[1] + treatment[2]):
        return None
    edges=[]
    for token in re.split(r'[、，,]',g[1]):
        ends=re.split(r'\s*[—–→-]\s*',token.strip())
        if len(ends)!=2 or '→' in token or not set(ends)<=set(nodes) or ends[0]==ends[1]:
            return None
        edges.append(ends)
    if len({frozenset(e) for e in edges})!=len(edges):
        return None
    known=[]; known_rows=[]
    for row in docs:
        m=re.search(r'(?:本人|自身|自己)(灯亮|启用|处理|开启|未启用|关闭)且暴露为([01])时[，,]([^，,]+?)的精确总体(?:成功率|均值|比例)(?:分别)?为(.+)$',row['quote'])
        if m:
            ids=split_names(m[3]);values=re.split(r'[、，,]',m[4])
            if not set(ids)<=set(nodes) or len(ids)!=len(values) or not all(re.fullmatch(RATE,v.strip()) for v in values):
                return None
            own=int(m[1] not in ('未启用','关闭'))
            known.extend(dict(node=n,own=own,exposure=int(m[2]),value=str(fraction(v.strip()))) for n,v in zip(ids,values))
            known_rows.append(dict(label='给定的精确总体均值',**row))
        elif re.search(r'精确总体(?:成功率|均值|比例)|(?:总体均值|条件均值)(?:为|等于)\s*\d',row['quote']):
            return None
    size=re.search('('+NUM+r')(?:项|个)已知均值',only['quote'])
    if (not known or size and integer(size[1])!=len(known)
            or len({(v['node'],v['own'],v['exposure']) for v in known})!=len(known)):
        return None
    return dict(operator='BOUNDED_SIGNATURE_MEAN',treatment=treatment[1]+treatment[2],
                edges=edges,values=known,graph=graph,information=only,
                conditions=[dict(code=key,label=label,**row) for key,label,row in
                    [('signature','各单位在所有安排下的均值暴露充分性',suff),
                     ('box','全安排的均值界及无额外约束',box)]],
                facts=[dict(label=l,**r) for l,r in [('处理前完整无向网络',graph),('严格过半的邻居暴露映射',rule),
                    ('已给总体信息的范围',only)]]+known_rows)


def read(case):
    q=case['business_question']
    if (len(case['sources'])!=1 or len(q)>3000 or len(case['sources'][0]['text'])>16000
            or not re.search(r'等权',q) or re.search(r'相[对比]|减去|对比|第二问|差值|相比|低多少|比.{0,8}(?:增加|降低)',q)):
        return None
    docs=[r for r in source_lines(case) if r['source_id']!='question']
    text=case['sources'][0]['text']
    if re.search(r'撤回|改为|更正|缺失|未确定|未确认|未知|不成立|不独立|拟采用|假定|有别于|并非|不能查询|不提供|只限|仅限|另有|另外(?:规定|要求|已知)|还(?:有|须满足|要求).{0,15}约束|可拒绝|邀请',text):
        return None
    conditions=assumptions(docs)
    labels=measure(docs,q)
    if not conditions or not labels:
        return None
    _,ordered=single(docs,r'按([^，,。；]{1,180}?)(?:的)?顺序(?:记|列|登记)|(?:名册|名单)(?:的)?顺序(?:为|是|[：:])([^，,。；]{1,180})')
    _,roster=single(docs,r'^([^，,。；]{1,180}?)是全部(?:区域|节点|单位|站点|对象)')
    if bool(ordered)==bool(roster):
        return None
    nodes=split_names(next(v for v in (ordered or roster).groups() if v is not None))
    if (not 2<=len(nodes)<=32 or len(nodes)!=len(set(nodes)) or any(not re.fullmatch(NAME,n) for n in nodes)
            or not weighted_population(q,nodes)):
        return None
    quota=uniform_quota([r['quote'] for r in docs],nodes)
    if quota is None:
        return None
    parsed=policy_mixture(q,docs,nodes) if ordered else bounded_level(q,docs,nodes)
    if not parsed:
        return None
    parsed['conditions']=conditions+parsed['conditions']
    parsed['facts']+= [dict(label='试行的固定名额均匀抽签',**r) for r in docs
                       if uniform_quota([r['quote']],nodes)==quota]
    horizons=set(re.findall(r'(?:下|本|下一)(?:季度|个月|年度|月|周|年)',q))
    if len(horizons)>1:
        return None
    return dict(parsed,nodes=nodes,quota=quota,outcome=labels[0],period=labels[1],policy_period=next(iter(horizons),None))
