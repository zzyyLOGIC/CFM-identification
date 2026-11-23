"""Explicit finite-record import shared by ID-only and full-pipeline web adapters.

No estimation, scientific approval, population-law inference or raw-value upload.
"""
from pathlib import Path
import math
from pydantic import BaseModel,ConfigDict,Field
from .tabular_files import selected_table


class TableMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    sheet: str | None = None
    header_row: int = Field(default=1,ge=1,le=10001)
    id_column: str
    treatment_column: str
    outcome_column: str
    feature_columns: list[str] = Field(min_length=1)
    period_column: str | None = None
    treated_value: str
    untreated_value: str
    missing_outcome_values: list[str] = Field(default_factory=lambda:[''])
    treatment: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    context: str = Field(min_length=1)
    outcome_kind: str
    observation_scheme: str = Field(min_length=1)


def read_records(path, mapping, network, *, shared_tables=None):
    m=TableMapping.model_validate(mapping)
    if network is None: raise ValueError('表格数据需配套上传对象表和关系表；不会假设对象之间没有联系。')
    if not m.treated_value or not m.untreated_value or m.treated_value==m.untreated_value:
        raise ValueError('启用与未启用的原始编码须不同且非空。')
    columns=[m.id_column,m.treatment_column,m.outcome_column,*m.feature_columns]+([m.period_column] if m.period_column else [])
    if len(set(columns))!=len(columns): raise ValueError('编号、处理、结果、时期与特征不能重复选用同一列。')
    path=Path(path);raw=path.read_bytes();t=selected_table(raw,path.name,sheet=m.sheet,header_row=m.header_row)
    if any(c not in t['headers'] for c in columns): raise ValueError('映射中的列不在当前表头；请重新预览。')
    indices={c:t['headers'].index(c) for c in columns}; by_id={}; periods=set()
    def number(v,row,col):
        try: result=float(v)
        except ValueError: raise ValueError(f'第{row}行的“{col}”不是数值；类别需明确编码，缺失特征不能自动填补。') from None
        if not math.isfinite(result): raise ValueError(f'第{row}行的“{col}”为空或非有限数值。')
        return result
    for r in t['rows']:
        vals=r['values']; row=r['row']; uid=vals[indices[m.id_column]]
        if indices[m.id_column]+1 in r['numeric']: raise ValueError(f'第{row}行编号是Excel数值，请保存为文本，避免前导零丢失。')
        if not uid or uid!=uid.strip() or any(ord(c)<32 for c in uid) or uid in by_id:
            raise ValueError(f'第{row}行对象编号缺失、重复或含空白；多期数据请先明确本次时期，不会自动合并。')
        value=vals[indices[m.treatment_column]]
        if value not in (m.treated_value,m.untreated_value): raise ValueError(f'第{row}行处理值不符合已确认的两个编码。')
        features=[number(vals[indices[c]],row,c) for c in m.feature_columns]
        y=vals[indices[m.outcome_column]]
        y=None if y in m.missing_outcome_values else number(y,row,m.outcome_column)
        by_id[uid]=(row,int(value==m.treated_value),features,y)
        if m.period_column:
            period=vals[indices[m.period_column]].strip()
            if not period: raise ValueError(f'第{row}行时期缺失。')
            periods.add(period)
    if len(periods)>1: raise ValueError('选定表包含多个时期，请先选出本次研究时期；不会自动平均或丢弃其他时期。')
    if set(by_id)!=set(network.nodes): raise ValueError('数据表与完整对象表的编号集合不一致；未回访对象也应保留一行，结果留空。')
    ordered=[by_id[n] for n in network.nodes]; n=len(ordered); idx={u:i for i,u in enumerate(network.nodes)}
    obs=[i for i,(_,_,_,y) in enumerate(ordered) if y is not None]
    if not obs: raise ValueError('没有可用于估计的结果记录；仍可仅提交业务与研究材料做识别。')
    schema=dict(version="autocfm-data-1",node_ids=list(network.nodes),feature_names=m.feature_columns,
        treatment=m.treatment+'；原表编码 '+m.treated_value+'→1，'+m.untreated_value+'→0',
        outcome=m.outcome,context=m.context+('；表中时期：'+next(iter(periods)) if periods else ''),
        outcome_kind=m.outcome_kind,feature_preprocessing='按用户选择列及编号对齐；数值特征未缩放、未插补。',observation_scheme=m.observation_scheme)

    if schema['outcome_kind'] not in ('CONTINUOUS','BINARY','COUNT'):
        raise ValueError('OUTCOME_KIND_REQUIRED')
    if len(network.nodes)<2: raise ValueError('AT_LEAST_TWO_RECORD_NODES_REQUIRED')
    if any(not v.strip() or v!=v.strip() for v in m.feature_columns):
        raise ValueError('FEATURE_NAMES_MUST_BE_NONBLANK')
    ys=[ordered[i][3] for i in obs]
    if m.outcome_kind=='BINARY' and any(y not in (0,1) for y in ys):
        raise ValueError('BINARY_OUTCOME_DECLARATION_MISMATCH')
    if m.outcome_kind=='COUNT' and any(y<0 or y!=math.floor(y) for y in ys):
        raise ValueError('COUNT_OUTCOME_DECLARATION_MISMATCH')
    manifest=dict(file=path.name,sha256=t['sha256'],sheet=t['sheet'],header_row=t['header_row'],mapping=m.model_dump(mode='json'),
        node_order=list(network.nodes),source_rows=[r[0] for r in ordered],observed_indices=obs,
        other_sheets=t['other_sheets'],skipped_preamble_rows=t['skipped_preamble_rows'],
        unused_columns=[h for h in t['headers'] if h not in columns],network_reference=network.token,
        scientific_approval=False,raw_measurements_sent_to_llm=False)

    if shared_tables is not None:
        from .shared_materials import table_source
        shared_tables.append(table_source('shared_observations', '逐行观测 · '+path.name+' · '+t['sheet'],
                                          t['headers'], (r['values'] for r in t['rows'])))
        manifest.pop('raw_measurements_sent_to_llm')
        manifest['raw_measurements_in_shared_input'] = True
    inventory=summarize_records(list(network.nodes),m.feature_columns,obs,[r[1] for r in ordered])
    return dict(schema=schema,rows=ordered,observed_indices=obs,manifest=manifest,inventory=inventory)


def summarize_records(nodes, features, indices, treatments):
    """Metadata from validated records, not outcomes or scientific claims."""
    n=len(nodes); observed=len(indices); observed_set=set(indices); treated=sum(treatments)
    return dict(
        node_count=n,
        feature_count=len(features),
        observed_outcome_count=observed,
        missing_outcome_count=n - observed,
        feature_and_treatment_node_ids=list(nodes),
        observed_outcome_node_ids=[nodes[i] for i in indices],
        missing_outcome_node_ids=[node for i, node in enumerate(nodes) if i not in observed_set],
        coverage_note='特征和使用记录覆盖全部名单；结果记录只覆盖observed_outcome_node_ids，'
                      '其顺序与文件内observed_indices及outcomes_observed一致。未回访对象没有结果记录。',
        treatment_counts={'0': n - treated, '1': treated},
        evidence_level='FINITE_SAMPLE_RECORDS_ONLY',
        limits='这是本次上传文件的实际记录数量，不是精确总体均值或总体分布。'
               '全部对象有记录也不等于掌握总体信息；实际使用人数不能证明随机分配方式或概率。'
               '不能仅由这些数量判断评价名单、时期、背景或科学假设。'
               'CSV等普通附件的行数不自动等于不同对象人数。',
    )
