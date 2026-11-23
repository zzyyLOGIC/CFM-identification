"""Explicit local network-table import. File structure is not scientific approval.

Ordinary document uploads remain metadata-only. This opt-in reader preserves IDs,
isolates and row provenance; it never infers edges, drops weights or completes a graph.
"""
from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
import csv
import io
import json
import re

from .document_intake import _decode, _safe_zip, _zip_xml, MAX_FILE_BYTES

MAX_NODES = 2000
MAX_EDGES = 50000
MAX_COLUMNS = 64


class NetworkFileError(ValueError):
    pass


def fail(code, message):
    raise NetworkFileError(f'{code}: {message}')


def _xlsx(raw):
    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with _safe_zip(raw) as archive:
        book = _zip_xml(archive, 'xl/workbook.xml')
        sheets = book.findall('m:sheets/m:sheet', ns)
        if len(sheets) != 1:
            fail('NETWORK_SINGLE_SHEET_REQUIRED', '每个网络文件请只保留一张工作表，避免遗漏其他表。')
        rid = sheets[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        rels = _zip_xml(archive, 'xl/_rels/workbook.xml.rels')
        rel = next((r for r in rels if r.get('Id') == rid), None)
        target = rel.get('Target', '') if rel is not None else ''
        if (not target or '..' in target or ':' in target or '\\' in target or
                rel.get('TargetMode') == 'External'):
            fail('NETWORK_SHEET_PATH_INVALID', '工作表引用无效。')
        target = target.lstrip('/')
        sheet = _zip_xml(archive, target if target.startswith('xl/') else 'xl/' + target)
        if sheet.find('m:mergeCells', ns) is not None:
            fail('NETWORK_MERGED_CELLS', '请取消网络表的合并单元格，并逐行明确填写。')
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(t.text or '' for t in item.findall('.//m:t', ns))
                       for item in _zip_xml(archive, 'xl/sharedStrings.xml').findall('m:si', ns)]
        rows = []
        for row in sheet.findall('m:sheetData/m:row', ns):
            if len(rows) > MAX_EDGES + 1:
                fail('NETWORK_TABLE_LIMIT', '关系表超过本入口的行数上限。')
            values = {}
            for cell in row.findall('m:c', ns):
                match = re.fullmatch(r'([A-Z]+)[1-9][0-9]*', cell.get('r', ''))
                if not match: fail('NETWORK_CELL_INVALID', '单元格坐标无效。')
                col = 0
                for char in match[1]: col = col * 26 + ord(char) - 64
                if col > MAX_COLUMNS or col in values:
                    fail('NETWORK_COLUMN_LIMIT', '列数过多或单元格重复。')
                if cell.find('m:f', ns) is not None:
                    fail('NETWORK_FORMULA_CELL', '请把公式结果另存为明确值；网络导入不执行公式。')
                kind = cell.get('t', 'n'); value = cell.find('m:v', ns)
                value = '' if value is None else value.text or ''
                if kind == 's':
                    try: value = strings[int(value)]
                    except (ValueError, IndexError): fail('NETWORK_STRING_INVALID', '文字索引无效。')
                elif kind == 'inlineStr': value = ''.join(t.text or '' for t in cell.findall('.//m:t', ns))
                elif kind == 'n' and value:
                    # Numeric IDs can lose leading zeroes through Excel formatting.
                    value = ('NUMERIC', value)
                elif kind not in ('n', 'str'):
                    fail('NETWORK_CELL_TYPE', '请使用文字编号，不要使用日期、布尔值或错误单元格。')
                values[col] = value
            rows.append((int(row.get('r', len(rows) + 1)),
                         [values.get(i, '') for i in range(1, max(values, default=0) + 1)]))
        return rows, sheets[0].get('name', '')


def _table(path):
    path = Path(path)
    if path.stat().st_size > MAX_FILE_BYTES: fail('NETWORK_FILE_SIZE', '单文件不能超过 8 MB。')
    raw = path.read_bytes()
    if path.suffix.lower() == '.xlsx': rows, sheet = _xlsx(raw)
    elif path.suffix.lower() in ('.csv', '.tsv'):
        content = _decode(raw)
        try: dialect = csv.Sniffer().sniff(content[:4096], delimiters=',\t;')
        except csv.Error: dialect = csv.excel_tab if path.suffix.lower() == '.tsv' else csv.excel
        rows = []
        for i, row in enumerate(csv.reader(io.StringIO(content), dialect, strict=True), 1):
            if i > MAX_EDGES + 1: fail('NETWORK_TABLE_LIMIT', '关系表超过 50000 行，不会截断后继续。')
            if len(row) > MAX_COLUMNS: fail('NETWORK_COLUMN_LIMIT', '网络表列数过多。')
            rows.append((i, row))
        sheet = ''
    else: fail('NETWORK_FILE_FORMAT', '对象表和关系表目前支持 CSV、TSV 或单工作表 XLSX。')
    if not rows: fail('NETWORK_EMPTY_TABLE', '文件缺少表头。')
    header = rows[0][1]
    if (not header or not all(isinstance(x, str) and x.strip() for x in header)
            or len(set(x.strip().casefold() for x in header)) != len(header)):
        fail('NETWORK_HEADER_INVALID', '请提供不重复的文字列名。')
    header = [x.strip() for x in header]
    for rowno, row in rows[1:]:
        if len(row) != len(header) or not any(x != '' for x in row):
            fail('NETWORK_ROW_INVALID', f'第 {rowno} 条记录为空或列数与表头不一致。')
    return header, rows[1:], dict(name=path.name, sha256=sha256(raw).hexdigest(), sheet=sheet)


def _column(headers, aliases):
    matches = [i for i, h in enumerate(headers) if h.casefold() in aliases]
    if len(matches) != 1:
        fail('NETWORK_COLUMN_REQUIRED', '请明确使用一个列名：' + ' / '.join(sorted(aliases)))
    return matches[0]


def _id(value, row):
    if not isinstance(value, str):
        fail('NETWORK_TEXT_ID_REQUIRED', f'第 {row} 条记录的对象编号请保存为文本，以保留前导零。')
    if not value or value != value.strip() or len(value) > 100 or any(ord(c) < 32 for c in value):
        fail('NETWORK_ID_INVALID', f'第 {row} 条记录缺少明确编号，或编号含空白/控制字符。')
    return value


@dataclass(frozen=True)
class NetworkTable:
    nodes: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]
    node_rows: tuple[int, ...]
    edge_rows: tuple[int, ...]
    node_file: tuple[str, str, str]
    edge_file: tuple[str, str, str]
    description: str
    completeness: str
    unused_node_columns: tuple[str, ...] = ()

    @property
    def token(self):
        return 'network_' + sha256(json.dumps(asdict(self), ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    def manifest(self):
        return dict(asdict(self), reference=self.token, scientific_approval=False)

    def source(self):
        complete = {'COMPLETE': '用户声明这是上述时期和范围的完整关系表；未列出的对象对没有该类关系。',
                    'INCOMPLETE': '用户声明只掌握部分关系，不能当作完整网络。',
                    'UNKNOWN': '用户尚未确定关系表是否完整，不能当作完整网络。'}[self.completeness]
        text = (f'用户上传的对象关系文件，结构引用 {self.token}。'
                f'对象表 {self.node_file[0]}（SHA256 {self.node_file[1]}）；关系表 {self.edge_file[0]}（SHA256 {self.edge_file[1]}）。'
                f'程序读取完整对象编号及顺序：{json.dumps(self.nodes, ensure_ascii=False)}。'
                f'共 {len(self.edges)} 条无向、无权重、无自环关系；完整关系在本次本地文件对象中，可通过结构引用读取，不需重新抄写。'
                f'关系含义与记录时期（用户说明）：{json.dumps(self.description, ensure_ascii=False)}。{complete}'
                '这些记录不证明随机化、均值充分性、无其他干扰或总体信息可用；科学条件另行审核。')
        return dict(source_id='uploaded_network', kind='OTHER', label='上传的对象名单和关系表', text=text)


def load_network(nodes_path, edges_path, declaration, *, shared_tables=None):
    if not isinstance(declaration, dict) or set(declaration) != {'kind', 'completeness', 'description'}:
        fail('NETWORK_DESCRIPTION_REQUIRED', '请说明关系的含义、记录时期及是否完整。')
    if declaration['kind'] != 'UNDIRECTED':
        fail('NETWORK_KIND_UNSUPPORTED', '此入口处理相互联系的无向关系；不会自动去掉方向或推定关系含义。')
    if declaration['completeness'] not in ('COMPLETE', 'INCOMPLETE', 'UNKNOWN'):
        fail('NETWORK_COMPLETENESS_REQUIRED', '请选择完整、部分或尚不清楚。')
    desc = declaration['description']
    if not isinstance(desc, str) or not 3 <= len(desc.strip()) <= 2000:
        fail('NETWORK_DESCRIPTION_REQUIRED', '请简短说明关系代表什么、来自哪段时间；不清楚的直接注明。')
    nh, nr, nf = _table(nodes_path); eh, er, ef = _table(edges_path)
    ni = _column(nh, {'node_id', 'unit_id', 'id', '对象编号', '门店编号', '节点编号'})
    si = _column(eh, {'source', 'unit_a', 'from', '对象1', '对象一', '起点'})
    ti = _column(eh, {'target', 'unit_b', 'to', '对象2', '对象二', '终点'})
    if len(eh) != 2 or si == ti:
        fail('NETWORK_EDGE_ATTRIBUTES_UNSUPPORTED', '关系表目前仅接受两列对象编号；权重、方向、时间或其他属性不能被忽略。请保留原文件并明确研究所用的关系定义。')
    nodes = tuple(_id(row[ni], i) for i, row in nr)
    if not 2 <= len(nodes) <= MAX_NODES or len(set(nodes)) != len(nodes):
        fail('NETWORK_ROSTER_INVALID', '对象表须有 2 至 2000 个不重复的编号；没有联系的对象也要保留。')
    known = set(nodes); seen = set(); edges = []
    for i, row in er:
        u, v = _id(row[si], i), _id(row[ti], i)
        if u not in known or v not in known: fail('NETWORK_UNKNOWN_NODE', f'关系表第 {i} 条记录的编号不在对象表中。')
        if u == v: fail('NETWORK_SELF_EDGE', f'关系表第 {i} 条记录连接对象自身。')
        key = frozenset((u, v))
        if key in seen: fail('NETWORK_DUPLICATE_EDGE', f'关系表第 {i} 条记录重复，包括反向重复；请确认是否实际代表多次事件。')
        seen.add(key); edges.append((u, v))
    if shared_tables is not None:
        from .shared_materials import table_source
        shared_tables.extend([
            table_source('shared_roster', '上传名册 · '+nf['name'], nh, (row for _, row in nr)),
            table_source('shared_edges', '上传关系表 · '+ef['name'], eh, (row for _, row in er)),
        ])
    return NetworkTable(nodes, tuple(edges), tuple(i for i, _ in nr), tuple(i for i, _ in er),
                        tuple(nf[k] for k in ('name', 'sha256', 'sheet')),
                        tuple(ef[k] for k in ('name', 'sha256', 'sheet')), desc.strip(), declaration['completeness'],
                        tuple(h for i, h in enumerate(nh) if i != ni))
