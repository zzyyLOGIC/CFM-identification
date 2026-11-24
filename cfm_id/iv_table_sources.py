"""Read an explicitly scoped binary-IV protocol and eight original population cells."""
import csv
import io
import json
import re
from . import direct_iv_evidence as iv
from .network_grounded_contrast import source_lines

VAR=r'[A-Za-z][A-Za-z0-9_]{0,15}'


def read(case):
    # A protocol and its probability table can be separate uploads. The table
    # reader also accepts the lossless CSV projection produced by the website.
    tables=[]; notes=[]
    for source in case['sources']:
        raw=source['text'].strip()
        lines=raw.splitlines()
        numbered=bool(lines and re.fullmatch(r'工作表 .+（第一列为原文件行号）',lines[0]))
        data=list(csv.reader(io.StringIO('\n'.join(lines[1:]) if numbered else raw)))
        if numbered and not all(r and r[0].isdigit() for r in data):
            return None
        if numbered:
            data=[r[1:] for r in data]
        if data and len(data[0])==4 and data[0][-1].strip() in ('条件概率','总体条件概率'):
            tables.append((source,data))
        else:
            notes.append(source)
    if len(tables)!=1 or not any('工具变量' in s['text'] for s in notes):
        return None
    rows=[r for r in source_lines(dict(case,sources=notes)) if r['source_id']!='question']
    used=[]
    def one(pattern,label):
        hits=[(r,m) for r in rows if (m:=re.fullmatch(pattern,r['quote']))]
        if len(hits)!=1:
            raise ValueError(label)
        row,match=hits[0];used.append(row)
        return match
    try:
        pop=one(r'研究总体[为是：:]([^，,。]+)','研究总体')[1]
        period=one(r'(?:研究|结果)时期[为是：:]([^，,。]+)','结果时期')[1]
        roles={}
        for key,word in [('instrument','工具变量'),('treatment','实际处理'),('outcome','结果变量')]:
            m=one(word+r'[为是：:]?\s*('+VAR+r')\s*[（(]([^，,。)）]+)[）)]',word+'及其二元含义')
            roles[key]=m[1]
            if key=='outcome':outcome=m[2]
        z,d,y=[roles[k] for k in ('instrument','treatment','outcome')]
        one(r'三个变量(?:都|均)为二元[（(]?0/1[）)]?','三个变量的取值')
        one(z+r'与全部潜在处理和潜在结果独立','工具变量独立性')
        one(z+r'仅通过'+d+'影响'+y,'工具变量的排除限制')
        one(r'(?:本研究)?采用一致性和无干扰','一致性及无干扰')
        one(z+r'的两个取值均有正概率','工具的正支持')
        one(r'不假定'+d+r'随机分配','实际处理的分配依据')
        mono=one(r'(采用无违背者单调性|不施加单调性)','是否采用单调性')[1]
        one(r'所附表为精确总体条件概率，(?:不是|并非)样本频率','表格的总体含义')
        one(r'以上是本题的全部条件，没有其他限制','额外限制是否列全')
        if len(used)!=len(rows):
            raise ValueError('尚未纳入模型的原文说明')
        q=case['business_question'].strip().rstrip('？?')
        goal=re.fullmatch(r'(所有'+re.escape(pop)+'|'+re.escape(pop)+r'中的依从者)在实际\s*'+d+
            r'\s*=\s*([01])\s*(?:相对(?:于)?|减去)\s*'+d+r'\s*=\s*([01])\s*下(?:的|，)'+
            r'(?:'+y+'|'+re.escape(outcome)+r')?(?:的)?(?:风险差|平均差)(?:是多少)?',q)
        if not goal or goal[2]==goal[3]:
            raise ValueError('原问的人群、实际处理两端、结果及相减方向')
        source,table=tables[0]
        if table[0][:3]!=[z,d,y] or len(table)!=9 or any(len(r)!=4 for r in table):
            raise ValueError('按工具、实际处理和结果标明的八项条件概率')
        cells={(a,b+c):v for a,b,c,v in table[1:]}
        if len(cells)!=8 or any((a,bc) not in cells for a in '01' for bc in ('00','01','10','11')):
            raise ValueError('互不重复的八个总体单元格')
        order=['00','01','10','11']
        doc=dict(format=iv.FORMAT,question=case['business_question'],population=pop,period=period,outcome_label=outcome,
            roles=roles,target=dict(type='ATE' if goal[1]=='所有'+pop else 'LATE',treated=int(goal[2]),reference=int(goal[3])),
            information=dict(kind='binary_population_conditional_law',row_variable=z,cell_variables=[d,y],cell_order=order,
                             rows={a:[cells[a,bc] for bc in order] for a in '01'}),
            assumptions=dict(instrument_independence=z,exclusion='adopted',consistency='adopted',no_interference='adopted',
                             instrument_support='both_positive',monotonicity='nondecreasing' if mono.startswith('采用') else 'not_imposed',
                             actual_randomization='not_claimed'),additional_restrictions=[],complete_for_declared_model=True)
        prepared,why=iv.read_declaration(dict(case,sources=[dict(text=json.dumps(doc,ensure_ascii=False))]))
        if prepared is None:
            raise ValueError(why)
        return dict(prepared=prepared,spans=used+[dict(source_id=source['source_id'],quote=source['text'])])
    except ValueError as exc:
        return dict(issue=str(exc))
