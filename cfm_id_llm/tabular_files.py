"""Bounded table decoding shared by metadata and local numerical import.

No inference, imputation, formula evaluation or scientific approval.
"""
import csv
import io
import re
from hashlib import sha256
from pathlib import Path


def workbook(raw, name):
    from .document_intake import _decode, _safe_zip, _zip_xml, MAX_FILE_BYTES
    if len(raw)>MAX_FILE_BYTES: raise ValueError('表格超过8MB限制。')
    suffix=Path(name).suffix.lower()
    result={}
    if suffix in ('.csv','.tsv'):
        content=_decode(raw)
        try: dialect=csv.Sniffer().sniff(content[:4096],delimiters=',\t;|')
        except csv.Error: dialect=csv.excel_tab if suffix=='.tsv' else csv.excel
        rows=[]
        for i,row in enumerate(csv.reader(io.StringIO(content),dialect,strict=True),1):
            if i>10001 or len(row)>200: raise ValueError('表格最多10000条记录、200列；不会截断后导入。')
            rows.append(dict(row=i,values=row,numeric=[],formula=[],merged=False))
        result['CSV']=rows
    elif suffix=='.xlsx':
        ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        with _safe_zip(raw) as z:
            book=_zip_xml(z,'xl/workbook.xml'); rels=_zip_xml(z,'xl/_rels/workbook.xml.rels')
            sheets=book.findall('m:sheets/m:sheet',ns)
            if len(sheets)>12: raise ValueError('工作簿最多12个工作表，请拆分后上传。')
            strings=[]
            if 'xl/sharedStrings.xml' in z.namelist():
                strings=[''.join(t.text or '' for t in item.findall('.//m:t',ns)) for item in _zip_xml(z,'xl/sharedStrings.xml').findall('m:si',ns)]
            for s in sheets:
                rid=s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                rel=next((r for r in rels if r.get('Id')==rid),None)
                target=rel.get('Target','') if rel is not None else ''
                if not target or '..' in target or ':' in target or '\\' in target or rel.get('TargetMode')=='External': raise ValueError('工作表引用无效。')
                target=target.lstrip('/'); tree=_zip_xml(z,target if target.startswith('xl/') else 'xl/'+target)
                rows=[]; seen=set(); merged=tree.find('m:mergeCells',ns) is not None
                for row in tree.findall('m:sheetData/m:row',ns):
                    number=int(row.get('r','0'))
                    if not 1<=number<=10001 or number in seen: raise ValueError('工作表行号重复或超过10001行限制。')
                    seen.add(number); values={}; numeric=[]; formulas=[]
                    for c in row.findall('m:c',ns):
                        match=re.fullmatch(r'([A-Z]+)([1-9][0-9]*)',c.get('r',''))
                        if not match or int(match[2])!=number: raise ValueError('单元格坐标无效。')
                        col=0
                        for ch in match[1]: col=col*26+ord(ch)-64
                        if col>200 or col in values: raise ValueError('单元格重复或超过200列。')
                        if c.find('m:f',ns) is not None: formulas.append(col)
                        kind=c.get('t','n'); v=c.find('m:v',ns); v='' if v is None else v.text or ''
                        if kind=='s':
                            if not v.isdigit() or int(v)>=len(strings): raise ValueError('单元格文字索引无效。')
                            v=strings[int(v)]
                        elif kind=='inlineStr': v=''.join(t.text or '' for t in c.findall('.//m:t',ns))
                        elif kind=='n' and v: numeric.append(col)
                        elif kind not in ('n','str'): raise ValueError('请将日期、布尔或错误单元格转换为明确的文字或数值。')
                        values[col]=v
                    rows.append(dict(row=number,values=[values.get(i,'') for i in range(1,max(values,default=0)+1)],numeric=numeric,formula=formulas,merged=merged))
                title=s.get('name','')
                if not title or title in result: raise ValueError('工作表名称缺失或重复。')
                result[title]=sorted(rows,key=lambda r:r['row'])
    else: raise ValueError('此入口支持CSV、TSV、XLSX。')
    if not result: raise ValueError('表格为空。')
    return result


def selected_table(raw,name,*,sheet=None,header_row=1):
    return _select(workbook(raw,name), sha256(raw).hexdigest(), sheet, header_row)


def _select(book, digest, sheet, header_row):
    if sheet is None:
        if len(book)!=1: raise ValueError('请选择要读取的工作表。')
        sheet=next(iter(book))
    if sheet not in book or type(header_row) is not int or header_row<1: raise ValueError('工作表或表头行无效。')
    rows=book[sheet]; first=next((r for r in rows if r['row']==header_row),None)
    if not first: raise ValueError('指定行不存在。')
    selected=[r for r in rows if r['row']>=header_row]
    if any(r['formula'] or r['merged'] for r in selected): raise ValueError('请将公式另存为明确值并取消合并单元格；系统不执行公式。')
    header=[s.strip() for s in first['values']]
    if not header or any(not s for s in header) or len(set(header))!=len(header): raise ValueError('表头应是非空、不重复的列名；请核对表头行。')
    data=[]
    for r in selected[1:]:
        if not any(v.strip() for v in r['values']): continue
        if len(r['values'])>len(header): raise ValueError(f'第{r["row"]}行比表头多出列，不能忽略。')
        data.append(dict(r,values=r['values']+['']*(len(header)-len(r['values']))))
    return dict(headers=header,rows=data,sheet=sheet,header_row=header_row,
                sha256=digest,other_sheets=[s for s in book if s!=sheet],
                skipped_preamble_rows=[r['row'] for r in rows if r['row']<header_row and any(r['values'])])


def preview(raw,name,sheet=None,header_row=1):
    book=workbook(raw,name)
    chosen=sheet or next(iter(book))
    if chosen not in book: raise ValueError('工作表不存在。')
    rows=book[chosen]
    answer=dict(sheets=list(book),sheet=chosen,sha256=sha256(raw).hexdigest(),
                preview=[dict(row=r['row'],values=r['values']) for r in rows[:6]],headers=[],error=None)
    try:
        table=_select(book,answer['sha256'],chosen,header_row)
        answer.update(headers=table['headers'],records=len(table['rows']),other_sheets=table['other_sheets'],skipped_preamble_rows=table['skipped_preamble_rows'])
    except ValueError as exc: answer['error']=str(exc)
    return answer


def dictionary_text(raw,name,sheet=None,header_row=1):
    import json
    book=workbook(raw,name)
    t=_select(book,sha256(raw).hexdigest(),sheet,header_row)
    if len(t['rows'])>200: raise ValueError('字段说明表最多200行；逐条观测记录请使用数据导入。')
    # Explicit opt-in: these are user-designated definitions, never observations.
    lines=[f'文件 {name}；工作表 {t["sheet"]}；表头第{header_row}行：'+json.dumps(t['headers'],ensure_ascii=False),
           '用户指定此表为字段说明；以下内容是来源陈述，不自动成为总体信息或科学批准。']
    for r in t['rows']:
        lines.append(f'第{r["row"]}行：'+json.dumps(dict(zip(t['headers'],r['values'])),ensure_ascii=False))
    if t['other_sheets']: lines.append('未选入的工作表：'+json.dumps(t['other_sheets'],ensure_ascii=False))
    if t['skipped_preamble_rows']: lines.append('表头前文字：'+json.dumps([r for r in book[t['sheet']] if r['row']<header_row],ensure_ascii=False))
    return '\n'.join(lines),t
