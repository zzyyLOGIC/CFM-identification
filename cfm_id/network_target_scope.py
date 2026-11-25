"""Source-owned evaluation weights and explicit question lists, not exposure weights.

No normalization, automatic zero fill, post-treatment cohort selection or model
answer is used here. A table describes the entire roster, including zero weights.
"""
import csv
import io
import re
from fractions import Fraction


class ScopeGap(ValueError):
    pass


HEADERS = ({'node_id', 'evaluation_weight'}, {'对象编号', '评价权重'})


def table_rows(text):
    text=text.lstrip('\ufeff')
    numbered=text.startswith('工作表 ') and '（第一列为原文件行号）\n' in text
    if numbered:text=text.split('\n',1)[1]
    rows=list(csv.reader(io.StringIO(text)))
    if numbered:
        if any(not r or r[0]!=str(i) for i,r in enumerate(rows,1)):
            raise ScopeGap('评价权重文件的工作表或行号不完整，请上传一张完整的权重表。')
        rows=[r[1:] for r in rows]
    return rows


def weight_sources(case):
    result=[]
    for source in case['sources']:
        text=source['text'].lstrip('\ufeff')
        if text.startswith('工作表 ') and '（第一列为原文件行号）\n' in text:
            text=text.split('\n',1)[1]
            header=next(csv.reader(io.StringIO(text)),[])[1:]
        else:header=next(csv.reader(io.StringIO(text)),[])
        if set(header) in HEADERS:result.append(source)
    return result


def weights(case, nodes):
    sources=weight_sources(case)
    if not sources:return None
    if len(sources)!=1:raise ScopeGap('有多份评价权重表，请明确本次使用哪一份。')
    source=sources[0]
    rows=table_rows(source['text'])
    header=rows.pop(0)
    if len(header)!=2 or len(rows)!=len(nodes) or any(len(r)!=2 for r in rows):
        raise ScopeGap('评价权重表应列出名册中的每个对象；不参与平均的对象请明确填0。')
    ni=header.index('node_id' if 'node_id' in header else '对象编号');wi=1-ni
    values={}
    for row in rows:
        node,value=(row[i].strip() for i in (ni,wi))
        if node not in nodes or node in values:raise ScopeGap('评价权重表中的对象有重复或不在研究名册中，请核对编号。')
        try:
            if not re.fullmatch(r'(?:\d+(?:/\d+)?|\d*\.\d+)',value):raise ValueError()
            values[node]=Fraction(value)
        except (ValueError,ZeroDivisionError):raise ScopeGap('评价权重请填写非负数或分数，例如0.25或1/4。')
    if sum(values.values())!=1:raise ScopeGap('评价权重之和应为1；当前未自动调整权重，请核对这份表。')
    text='。'.join([case['business_question'],*[s['text'] for s in case['sources'] if s is not source]])
    if not re.search(r'(?:按|使用|采用).{0,12}评价权重表',text):
        raise ScopeGap('这份表是否就是本次平均效果使用的评价权重？请说明。')
    if not re.search(r'(?:名单|评价对象).{0,8}(?:和|及|与)权重.{0,12}(?:抽签|试点|处理|分配)前.{0,5}确定',text):
        raise ScopeGap('本次评价的名单和权重是在处理前确定的，还是根据处理后的记录选出来的？')
    if re.search(r'(?:按|根据|依照).{0,12}(?:中签|实际使用|实际结果|回访|试点后).{0,12}(?:筛选|选择|权重|加权)|名单.{0,8}尚未|权重.{0,8}(?:未知|尚未|未定)|(?<!不)等权|权重相同',text):
        raise ScopeGap('评价权重表与名单选择或平均方式的文字说明不一致，请明确本次采用的口径。')
    # Explicit restrictions must agree with the positive-weight evaluation set.
    from .network_protocol_terms import named_units
    positive=[n for n in nodes if values[n]>0]
    for m in re.finditer(r'(?:只|仅)(?:评价|评估|看)([^。，；\n]+)',text):
        named=named_units(m[1].strip('【】 '),nodes)
        if not named or set(named)!=set(positive):raise ScopeGap('文字中的评价名单与权重表中非零权重的对象不一致。')
    if re.search(r'(?:全体|全部).{0,5}(?:对象|站点|门店).{0,5}(?:平均|评价)',text) and len(positive)!=len(nodes):
        raise ScopeGap('文字要求评价全体对象，但权重表有零权重，请明确评价范围。')
    return dict(values={n:str(values[n]) for n in positive},all_values={n:str(values[n]) for n in nodes},
                evidence=dict(source_id=source['source_id'],quote=source['text']))


def questions(case):
    """Preserve a shared preamble and every sequential numbered question verbatim."""
    text=case['business_question']
    matches=list(re.finditer(r'(?m)^\s*(\d+)[.、]\s*([^\n]+)',text))
    if len(matches)<2:return None
    if len(matches)>16 or [int(m[1]) for m in matches]!=list(range(1,len(matches)+1)):
        raise ScopeGap('请用连续编号列出各个问题；本入口一次最多核验16问。')
    if any(text[a.end():b.start()].strip() for a,b in zip(matches,matches[1:])) or text[matches[-1].end():].strip():
        raise ScopeGap('问题编号之间还有未归属的内容，请将共同说明放在编号之前，或写入对应问题。')
    shared=text[:matches[0].start()]
    if re.search(r'[？?]|相比|减去|还想|另问',shared):
        raise ScopeGap('编号前似乎还有一个比较问题，请一并编号，避免遗漏。')
    return [dict(id=f'q{i}',question=m[2],projected_question=shared+m[2],
                 start=m.start(2),end=m.end(2),shared=shared) for i,m in enumerate(matches,1)]
