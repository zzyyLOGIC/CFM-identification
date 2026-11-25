"""Classify proposed input questions against sources; never complete a reading.

The response can request a bounded reread, or authorize a specific question.
It cannot supply field values, approve assumptions, or bypass the main audit.
"""
import json
from typing import Literal
from pydantic import Field
from .population_ate_reading import Strict
from .compact_study import digest
from . import joint_reading as sources


class Finding(Strict):
    field: str
    cause: Literal['READING_OMISSION','MISSING_IN_SOURCE','EXPLICIT_UNKNOWN',
                   'SOURCE_CONFLICT','INFORMATION_NOT_SUPPORTED','DECLARATION_CONFIRMED']
    evidence: list[sources.Citation]
    reason: str = Field(min_length=1)
    question: str | None


class Review(Strict):
    binding: str
    scientific_approval: Literal[False]
    findings: list[Finding]


RULES='''只输出符合 output_schema 的 JSON 对象，不加 Markdown 或解释前缀。
你只判断程序准备追问的每项缺口究竟来自哪里，不解题，不填字段，不批准假设。
对照全部原材料、用户补充、candidate的具体值和gaps逐项核对：
READING_OMISSION=原文已经明确提供，但候选缺失/错填；指出原句，question=null，交给后台重读。
MISSING_IN_SOURCE=原文确实没有说明；EXPLICIT_UNKNOWN=原文明说不知道或尚未决定；SOURCE_CONFLICT=原文有冲突或确实歧义。上述三类用一句具体易答的问题，不要让用户重复填写整套材料。
INFORMATION_NOT_SUPPORTED=原文明确提供的资料不符合当前方法所需的资料种类；说明实际资料与所需资料，不把它说成用户漏写，question=null。
DECLARATION_CONFIRMED=程序因明确不采用前提或未表达的额外科学限制而停止，且候选忠实保留了原文；保留停止，question=null。只允许用于明确标有declaration_stop的项。若该限制只是已有字段的重复、待定说明或资料备注，却被错当作额外限制，判READING_OMISSION；不能用此分类批准执行。
凡原文已提供不要追问；不因candidate为null就判定原文缺失。所有cause忠实原文，不替用户接受常用前提，不用模型数学答案。
MISSING_IN_SOURCE可无引文；其他结论必须给原文片段编号。每个gap恰好一项，binding照抄，scientific_approval=false。'''


def binding(case,candidate,gaps):
    return digest(['source-gap-review/1',case,candidate,gaps])


def request(case,candidate,gaps,*,reading_contract=None):
    schema=Review.model_json_schema()
    if not any(x.get('declaration_stop') is True for x in gaps.values()):
        # A normal question cannot be answered by confirming a nonexistent
        # refusal/extra-constraint stop. Do not offer an unusable enum option.
        causes=schema['$defs']['Finding']['properties']['cause']['enum']
        causes.remove('DECLARATION_CONFIRMED')
    schema['$defs']['Finding']['properties']['field']['enum']=list(gaps)
    schema['$defs']['Citation']['properties']['source_id']['enum']=list(sources.sources(case))
    schema['properties']['findings'].update(minItems=len(gaps),maxItems=len(gaps))
    return dict(system_prompt=RULES,user_prompt=json.dumps(dict(
        binding=binding(case,candidate,gaps),candidate=candidate,gaps=gaps,
        source_catalog=sources.sources(case),source_descriptions=sources.source_descriptions(case),reading_contract=reading_contract,
        output_schema=schema),ensure_ascii=False))


def check(case,candidate,gaps,raw):
    value=Review.model_validate(raw).model_dump(mode='json')
    if value['binding']!=binding(case,candidate,gaps):raise ValueError('SOURCE_GAP_REVIEW_STALE')
    if sorted(x['field'] for x in value['findings'])!=sorted(gaps):raise ValueError('SOURCE_GAP_REVIEW_COVERAGE')
    for row in value['findings']:
        row['evidence']=sources.resolve_evidence(case,row['evidence'])
        omission=row['cause']=='READING_OMISSION'
        no_question=row['cause'] in ('READING_OMISSION','INFORMATION_NOT_SUPPORTED','DECLARATION_CONFIRMED')
        if row['cause']=='DECLARATION_CONFIRMED' and gaps[row['field']].get('declaration_stop') is not True:
            raise ValueError('SOURCE_DECLARATION_STOP_REQUIRED')
        if no_question and row['question'] is not None:raise ValueError('OMISSION_MUST_NOT_ASK_USER' if omission else 'UNSUPPORTED_INFORMATION_MUST_NOT_REPEAT_QUESTION')
        if not no_question and not (row['question'] or '').strip():raise ValueError('SOURCE_GAP_QUESTION_REQUIRED')
        if row['cause']!='MISSING_IN_SOURCE' and not row['evidence']:raise ValueError('SOURCE_GAP_EVIDENCE_REQUIRED')
    return value
