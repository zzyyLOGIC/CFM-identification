"""Lossless textual table evidence for a direct answer and its local verifier."""
import csv
import io
from pathlib import Path

from .tabular_files import workbook

DIRECT_MODES = {'direct_verify', 'network_direct_verify', 'network_local_review'}


def table_source(source_id, label, header, rows):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\r\n')
    writer.writerow(header)
    for row in rows:
        writer.writerow([v[1] if isinstance(v, tuple) and v[0] == 'NUMERIC' else v for v in row])
    return dict(source_id=source_id, kind='OTHER', label=label, text=stream.getvalue())


def document_tables(path):
    """A general spreadsheet submitted as study material carries every sheet, including preambles."""
    pages = []
    for title, rows in workbook(Path(path).read_bytes(), Path(path).name).items():
        if any(row['formula'] or row['merged'] for row in rows):
            raise ValueError('补充表含公式或合并单元格，请另存为明确值和独立单元格。')
        stream = io.StringIO(newline='')
        writer = csv.writer(stream, lineterminator='\r\n')
        for row in rows:
            writer.writerow([row['row'], *row['values']])
        pages.append('工作表 '+title+'（第一列为原文件行号）\n'+stream.getvalue())
    return '\n'.join(pages)


def append_sources(case, tables):
    existing = {source['source_id'] for source in case['sources']}
    for table in tables:
        if table['source_id'] in existing:
            raise ValueError('SHARED_TABLE_SOURCE_ID_COLLISION')
        existing.add(table['source_id'])
        case['sources'].append(table)
