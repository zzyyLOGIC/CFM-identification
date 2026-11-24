"""v0.7 local, bounded ingestion of business attachments into the existing BusinessCase.

No theorem claims. No network calls. Tabular files are SCHEMA-ONLY by default:
individual values/outcomes are NOT placed into LLM prompts. Attachment source kind is
caller-reported provenance, *never* proof of scientific authenticity or A4 sufficiency.
"""
from __future__ import annotations

import csv
from hashlib import sha256
from io import BytesIO, StringIO
from pathlib import Path, PurePosixPath
import re
from typing import Literal
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

from pydantic import Field

from .schemas import BusinessCase, SourceDocument, SourceKind, StrictModel

MAX_ATTACHMENTS = 10
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
MAX_SOURCE_CHARS = 11000
MAX_TOTAL_SOURCE_CHARS = 42000
MAX_PDF_PAGES = 15
MAX_TABLE_HEADERS = 50
MAX_TABLE_SCAN_ROWS = 10000
MAX_ARCHIVE_INFLATED = 16 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 1000
SUPPORTED_SUFFIXES = frozenset({'.txt', '.md', '.json', '.pdf', '.csv', '.tsv', '.xlsx', '.docx'})


class AttachmentError(ValueError):
    """Refuse unsafe, unsupported, or malformed attachments without partial trust."""


class AttachmentRequestV07(StrictModel):
    path: str = Field(min_length=1, max_length=2048)
    kind: SourceKind = SourceKind.OTHER
    label: str | None = Field(default=None, max_length=200)
    purpose: Literal['DOCUMENT', 'DATA_DICTIONARY'] = 'DOCUMENT'
    sheet: str | None = None
    header_row: int = Field(default=1, ge=1, le=10001)


class AttachmentRecordV07(StrictModel):
    source_id: str
    display_name: str
    source_kind: SourceKind
    file_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    extracted_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    bytes: int
    suffix: str
    mode: Literal['TEXT_EXCERPT', 'SCHEMA_ONLY', 'NO_EXTRACTABLE_TEXT']
    warnings: list[str] = Field(default_factory=list)
    extracted_chars: int


class IntakeReportV07(StrictModel):
    version: Literal['0.7.0'] = '0.7.0'
    case: BusinessCase
    attachments: list[AttachmentRecordV07]
    warnings: list[str] = Field(default_factory=list)
    # The following are status assertions, not quantities estimated or certified.
    mathematical_verification: Literal['NOT_PERFORMED'] = 'NOT_PERFORMED'
    estimation_handoff_allowed: Literal[False] = False


def _decode(raw: bytes) -> str:
    for encoding in ('utf-8-sig', 'gb18030'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AttachmentError('Text encoding not supported (use UTF-8)')


def _clip(text: str, warnings: list[str]) -> str:
    # Avoid silent truncation: a warning is attached to both the source and manifest.
    text = text.replace('\x00', ' ').strip()
    if len(text) > MAX_SOURCE_CHARS:
        warnings.append('CONTENT_TRUNCATED')
        text = text[:MAX_SOURCE_CHARS].rstrip() + '\n[CONTENT_TRUNCATED: subsequent text not reviewed]'
    if not text:
        warnings.append('NO_EXTRACTABLE_TEXT')
        return '[NO_EXTRACTABLE_TEXT]'
    return text


def _safe_zip(raw: bytes) -> ZipFile:
    try:
        archive = ZipFile(BytesIO(raw))
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS or sum(x.file_size for x in infos) > MAX_ARCHIVE_INFLATED:
            raise AttachmentError('Document archive exceeds safe extraction limits')
        if any(x.file_size > MAX_ARCHIVE_INFLATED or
               x.filename.startswith('/') or
               '..' in PurePosixPath(x.filename).parts or
               x.flag_bits & 1 for x in infos):
            raise AttachmentError('Unsafe encrypted or traversing document archive')
        return archive
    except (BadZipFile, OSError) as exc:
        raise AttachmentError('Invalid document archive') from exc


def _zip_xml(archive: ZipFile, name: str, max_bytes: int = 4 * 1024 * 1024) -> ET.Element:
    try:
        if archive.getinfo(name).file_size > max_bytes:
            raise AttachmentError('Document XML exceeds per-section limit')
        return ET.fromstring(archive.read(name))
    except (KeyError, ET.ParseError, BadZipFile, OSError) as exc:
        raise AttachmentError('Required document XML is missing or invalid') from exc


def _read_docx(raw: bytes, warnings: list[str]) -> str:
    z = _safe_zip(raw)
    try:
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        import json
        pieces=[]
        parts=['word/document.xml']+[n for n in sorted(z.namelist()) if re.fullmatch(r'word/(footnotes|endnotes|header\d+|footer\d+)\.xml',n)]
        for part in parts:
            root=_zip_xml(z,part)
            def paragraph(p):
                value=''.join(t.text or '' for t in p.findall('.//w:t',ns)).strip()
                refs=p.findall('.//w:footnoteReference',ns)+p.findall('.//w:endnoteReference',ns)
                return value+''.join('[注释编号 '+r.get('{'+ns['w']+'}id','?')+']' for r in refs)
            def walk(el):
                tag=el.tag.rsplit('}',1)[-1]
                if tag=='p':
                    text=paragraph(el)
                    if text: pieces.append(f'{part} 段落 {len(pieces)+1}: {text}')
                elif tag=='tbl':
                    for i,row in enumerate(el.findall('w:tr',ns),1):
                        cells=['\n'.join(paragraph(p) for p in cell.findall('.//w:p',ns)) for cell in row.findall('w:tc',ns)]
                        pieces.append(f'{part} 表格行 {i}: '+json.dumps(cells,ensure_ascii=False))
                    if el.findall('.//w:gridSpan',ns) or el.findall('.//w:vMerge',ns): warnings.append('DOCX_MERGED_TABLE:'+part)
                else:
                    if tag in ('footnote','endnote'): pieces.append(part+' 注释编号 '+el.get('{'+ns['w']+'}id','?'))
                    for child in el: walk(child)
            walk(root)
            if any(e.tag.rsplit('}',1)[-1] in ('drawing','pict','object','oMath','altChunk','del','ins') for e in root.iter()):
                warnings.append('DOCX_VISUAL_OR_REVISION_NOT_FULLY_READ:'+part)
        if 'word/comments.xml' in z.namelist(): warnings.append('DOCX_COMMENTS_NOT_READ')
        return _clip('\n'.join(pieces), warnings)
    finally:
        z.close()


def _read_pdf(raw: bytes, warnings: list[str]) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise AttachmentError('PDF text extraction requires optional pypdf dependency') from exc
    try:
        reader = PdfReader(BytesIO(raw), strict=False)
        if reader.is_encrypted:
            raise AttachmentError('Encrypted PDF is not supported')
        count = len(reader.pages)
        pieces = []
        if count > MAX_PDF_PAGES:
            warnings.append('PAGE_LIMIT_REACHED')
        for idx in range(min(count, MAX_PDF_PAGES)):
            extracted = (reader.pages[idx].extract_text() or '').strip()
            if extracted:
                pieces.append(f'第 {idx + 1} 页:\n{extracted}')
                if reader.pages[idx].images: warnings.append(f'PDF_IMAGE_CONTENT_NOT_READ:PAGE_{idx+1}')
            else:
                warnings.append(f'PDF_PAGE_NO_TEXT:PAGE_{idx+1}')
            if sum(len(x) for x in pieces) >= MAX_SOURCE_CHARS:
                if idx+1<count: warnings.append('PDF_REMAINING_PAGES_NOT_READ')
                break
        if not pieces:
            warnings.append('SCANNED_OR_IMAGE_ONLY_PDF_NO_OCR')
            return '[NO_EXTRACTABLE_TEXT: image-only PDF; OCR not performed]'
        return _clip('\n\n'.join(pieces), warnings)
    except AttachmentError:
        raise
    except Exception as exc:
        raise AttachmentError('Could not safely extract text from PDF') from exc


def _schema_summary(filename: str, sheets: list[tuple[str, list[str], int, bool]], warnings: list[str]) -> str:
    # Avoid exposing customer IDs, salary, transaction values or individual outcomes.
    pieces = [f'文件：{filename}', '提取摘要：仅元数据与表头；业务数据行不会纳入摘要或发送给 LLM。']
    for sheet_name, headers, count, incomplete in sheets:
        pieces += [f'数据表：{sheet_name}', f'表头字段：{", ".join(headers) if headers else "[无可用表头]"}',
                   f'数据行数：{str(count) + "+" if incomplete else str(count)}（表头不计入）']
        if incomplete:
            warnings.append('TABLE_ROW_SCAN_LIMIT_REACHED')
    pieces.append('注意：字段名和行数只能描述有限样本结构，不能证明 A4 总体可观测信息充分。')
    return _clip('\n'.join(pieces), warnings)


def _read_csv(raw: bytes, filename: str, warnings: list[str]) -> str:
    content = _decode(raw)
    try:
        dialect = csv.Sniffer().sniff(content[:4096], delimiters=',\t;|')
    except csv.Error:
        dialect = csv.excel_tab if Path(filename).suffix.lower() == '.tsv' else csv.excel
    # Keep the reader bounded and never materialize cell values in any source.
    reader = csv.reader(StringIO(content), dialect)
    try:
        raw_header = next(reader)
        if len(raw_header) > MAX_TABLE_HEADERS:
            warnings.append('COLUMN_LIMIT_REACHED')
        columns = [str(v).strip()[:100] for v in raw_header[:MAX_TABLE_HEADERS]]
    except StopIteration:
        columns = []
    count = 0
    truncated = False
    for _ in reader:
        if count == MAX_TABLE_SCAN_ROWS:
            truncated = True
            break
        count += 1
    return _schema_summary(filename, [('CSV', columns, count, truncated)], warnings)


def _col_number(a1: str) -> int:
    letters = re.match(r'[A-Z]+', a1.upper())
    if not letters:
        return 0
    number = 0
    for char in letters.group(0):
        number = number * 26 + ord(char) - 64
    return number


def _read_xlsx(raw: bytes, filename: str, warnings: list[str]) -> str:
    z = _safe_zip(raw)
    try:
        ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
              'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
              'p': 'http://schemas.openxmlformats.org/package/2006/relationships'}
        workbook = _zip_xml(z, 'xl/workbook.xml')
        rel_root = _zip_xml(z, 'xl/_rels/workbook.xml.rels')
        relationships = {}
        for rel in rel_root.findall('p:Relationship', ns):
            target = rel.attrib.get('Target', '')
            normalized = target.lstrip('/')
            if (not target or '..' in PurePosixPath(normalized).parts
                    or '://' in normalized or '\\' in normalized):
                raise AttachmentError('Invalid workbook sheet relationship')
            # OOXML allows both /xl/worksheets/sheet1.xml and
            # worksheets/sheet1.xml as relationship targets.
            relationships[rel.attrib.get('Id', '')] = (
                normalized if normalized.startswith('xl/') else 'xl/' + normalized
            )
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            shared = _zip_xml(z, 'xl/sharedStrings.xml')
            strings = shared.findall('m:si', ns)
        result = []
        for sheet in workbook.findall('m:sheets/m:sheet', ns)[:12]:
            name = sheet.attrib.get('name', 'Sheet')[:100]
            rid = sheet.attrib.get('{' + ns['r'] + '}id', '')
            target = relationships.get(rid)
            if not target:
                raise AttachmentError('Workbook sheet reference missing')
            xml = _zip_xml(z, target)
            rows = xml.findall('m:sheetData/m:row', ns)
            first = rows[0] if rows else None
            names = [''] * MAX_TABLE_HEADERS
            if first is not None:
                for cell in first.findall('m:c', ns):
                    idx = _col_number(cell.attrib.get('r', 'A')) - 1
                    if idx < 0 or idx >= MAX_TABLE_HEADERS:
                        if idx >= MAX_TABLE_HEADERS and 'COLUMN_LIMIT_REACHED' not in warnings:
                            warnings.append('COLUMN_LIMIT_REACHED')
                        continue
                    if cell.find('m:f', ns) is not None:
                        names[idx] = '[formula header not evaluated]'
                        continue
                    ty = cell.attrib.get('t', '')
                    val = cell.find('m:v', ns)
                    if ty == 'inlineStr':
                        text = ''.join(t.text or '' for t in cell.findall('.//m:t', ns))
                    elif ty == 's':
                        index = val.text if val is not None else None
                        if not index or not index.isdecimal() or int(index) >= len(strings):
                            raise AttachmentError('Invalid workbook header shared string index')
                        text = ''.join(t.text or '' for t in strings[int(index)].findall('.//m:t', ns))
                    else:
                        text = (val.text or '') if val is not None else ''
                    names[idx] = text[:100]
            while names and not names[-1]:
                names.pop()
            actual_count = max(0, len(rows) - 1)
            result.append((name, names, min(actual_count, MAX_TABLE_SCAN_ROWS), actual_count > MAX_TABLE_SCAN_ROWS))
        if len(workbook.findall('m:sheets/m:sheet', ns)) > 12:
            warnings.append('SHEET_LIMIT_REACHED')
        return _schema_summary(filename, result, warnings)
    finally:
        z.close()


def _extract(raw: bytes, path: Path, warnings: list[str]) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in {'.txt', '.md', '.json'}:
        text = _decode(raw)
        if suffix=='.json' and 'causal-id.math-request/1' in text and len(text)<=30000:
            import json
            try:
                value=json.loads(text)
            except (ValueError,RecursionError):
                value=None
            if isinstance(value,dict) and value.get('format')=='causal-id.math-request/1':
                # The exact JSON also goes to the direct reader, within the
                # existing SourceDocument and combined-document size limits.
                return text, 'TEXT_EXCERPT'
        return _clip(text, warnings), 'TEXT_EXCERPT'
    if suffix == '.pdf':
        extracted = _read_pdf(raw, warnings)
        return extracted, ('NO_EXTRACTABLE_TEXT' if 'SCANNED_OR_IMAGE_ONLY_PDF_NO_OCR' in warnings else 'TEXT_EXCERPT')
    if suffix == '.docx':
        return _read_docx(raw, warnings), 'TEXT_EXCERPT'
    if suffix in {'.csv', '.tsv'}:
        return _read_csv(raw, path.name, warnings), 'SCHEMA_ONLY'
    if suffix == '.xlsx':
        return _read_xlsx(raw, path.name, warnings), 'SCHEMA_ONLY'
    raise AttachmentError(f'Unsupported attachment type: {suffix}')


def create_intake(*, case_id: str, business_question: str,
                  attachments: list[AttachmentRequestV07], response_language: Literal['zh', 'en'] = 'zh') -> IntakeReportV07:
    if len(attachments) > MAX_ATTACHMENTS:
        raise AttachmentError(f'At most {MAX_ATTACHMENTS} attachments per intake')
    total_bytes = 0
    sources: list[SourceDocument] = []
    records: list[AttachmentRecordV07] = []
    all_warnings: list[str] = []
    total_source = 0
    for index, item in enumerate(attachments):
        path = Path(item.path)
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise AttachmentError('Unsupported attachment extension')
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise AttachmentError('Attachment cannot be read') from exc
        if size > MAX_FILE_BYTES or total_bytes + size > MAX_TOTAL_BYTES:
            raise AttachmentError('Attachment exceeds size or total size budget')
        total_bytes += size
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise AttachmentError('Attachment cannot be read') from exc
        if len(raw) != size:
            raise AttachmentError('Attachment changed while reading')
        warnings: list[str] = []
        if item.purpose == 'DATA_DICTIONARY':
            from .tabular_files import dictionary_text
            extracted, table = dictionary_text(raw,path.name,item.sheet,item.header_row)
            if len(extracted)>MAX_SOURCE_CHARS:
                raise AttachmentError('字段说明超过文字限制，请拆成较小的说明表；不会截断解释后继续。')
            if table['other_sheets']: warnings.append('DICTIONARY_OTHER_SHEETS_NOT_SELECTED')
            mode='TEXT_EXCERPT'
        else:
            extracted, mode = _extract(raw, path, warnings)
        if total_source + len(extracted) > MAX_TOTAL_SOURCE_CHARS:
            raise AttachmentError('Combined LLM document context exceeds safe text budget')
        total_source += len(extracted)
        source_id = f'att_{index + 1:02d}'
        label = (item.label or path.name)[:200]
        sources.append(SourceDocument(source_id=source_id, kind=item.kind, label=label, text=extracted))
        records.append(AttachmentRecordV07(source_id=source_id,
                                           display_name=(item.label or path.name)[:200], source_kind=item.kind,
                                           file_sha256=sha256(raw).hexdigest(), extracted_sha256=sha256(extracted.encode('utf-8')).hexdigest(), bytes=size,
                                           suffix=path.suffix.lower(), mode=mode,
                                           warnings=warnings, extracted_chars=len(extracted)))
        all_warnings.extend(f'{source_id}:{code}' for code in warnings)
    case = BusinessCase(case_id=case_id, business_question=business_question,
                        response_language=response_language, sources=sources)
    return IntakeReportV07(case=case, attachments=records, warnings=all_warnings)
