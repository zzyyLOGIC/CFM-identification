"""Source review of an A0 stop reason. Every disposition remains a stop.

No target correction, semantic classifier, method choice or scientific licence.
Only current compact missing-coordinate/recheck signals can be reviewed here.
"""
from copy import deepcopy
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_serializer
from . import business_intake as intake
from .intake_reading_revision import sources

VERSION = 'intake-stop-review-1'
Authority = Literal['EXTERNAL_RESEARCH_REVIEW', 'SYNTHETIC_TEST']


class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    disposition: Literal['PENDING', 'MATERIAL_GAP', 'READING_ERROR']
    reason: str = Field(min_length=12)
    source_ids: list[str]


class StopReview(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    version: Literal['intake-stop-review-1'] = VERSION
    binding_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    authority: Authority
    reviewer: str = Field(min_length=3)
    evidence: str = Field(min_length=12)
    decisions: dict[str, Decision]
    # Optional source-review scope for a partly specified field, never replacement values.
    target_fields: dict[str, list[str]] = Field(default_factory=dict)

    @model_serializer(mode='wrap')
    def omit_historical_empty_scope(self, handler):
        result = handler(self)
        if not self.target_fields: result.pop('target_fields')
        return result


class SavedReview(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    record: StopReview
    history: list[StopReview] = Field(default_factory=list, max_length=20)


def _worksheet(s, reading, authority, target_fields=None):
    if authority not in ('EXTERNAL_RESEARCH_REVIEW', 'SYNTHETIC_TEST'):
        raise intake.IntakeError('INVALID_STOP_REVIEW_AUTHORITY')
    if s.reading_format != 'compact' or 'report' not in reading:
        raise intake.IntakeError('CURRENT_VALID_COMPACT_REPORT_REQUIRED')
    gate = reading.get('wire_gate') or {}
    audits = {a['query_id']: a for a in reading['report']['query_quality']}
    from cfm_id_llm.business_field_contract import SEMANTICS
    from cfm_id_llm.target_clarification_contract import question, field_path
    allowed_fields = {f.name for f in SEMANTICS} | {'comparison_order', 'outcome'}
    target_fields = {} if target_fields is None else target_fields
    if (type(target_fields) is not dict or any(qid not in audits or type(names) is not list
            or not names or any(type(f) is not str or f not in allowed_fields for f in names)
            or len(names) != len(set(names)) for qid,names in target_fields.items())):
        raise intake.IntakeError('INVALID_TARGET_CLARIFICATION_SCOPE')
    items = {}
    for q in reading['report']['draft']['queries']:
        qid = q['query_id']
        issues = [x for x in intake.wire_recheck_issues(gate)
                  if not x['path'].startswith('queries.') or x['path'].startswith(f'queries.{qid}.')]
        questions = [x for x in gate.get('proposed_business_questions', []) if x['query_id'] == qid]
        for name in target_fields.get(qid, []):
            if not any(x['field'] == name for x in questions):
                questions.append(dict(query_id=qid, field=name, question=question(q['target']['kind'],name),
                    status='VERIFY_MISSING_IN_SOURCE_BEFORE_ASKING'))
        if not (issues or questions):
            continue
        actions = audits[qid]['actions']
        # The target-first contract can explicitly preserve an unknown outcome.
        # The legacy A2 audit still labels the missing definition as extraction
        # work. Permit source review to classify this stop; never release it.
        missing_outcome = (gate.get('target_first') or {}).get('outcomes', {}).get(qid, {})
        outcome_gap_reviewable = (
            isinstance(missing_outcome, dict) and missing_outcome.get('state') == 'MISSING'
            and bool(missing_outcome.get('refs'))
            and any(x['field'] == 'outcome' for x in questions))
        def reviewable_action(action):
            return (outcome_gap_reviewable and action['code'] == 'A2_MISSING_OUTCOME'
                    and action['field_path'] == 'units_variables.outcome')
        extraction_actions = [x for x in actions if x['owner'] == 'A0_FORMULATOR']
        only_reviewable_definition = bool(extraction_actions) and all(map(reviewable_action, extraction_actions))
        reviewed_paths = {'target.kind', *(field_path(x) for x in questions)}
        other_questions = [x for x in audits[qid]['business_questions'] if x['field_path'] not in reviewed_paths]
        # An unknown kind may reflect an undecided target. An OTHER kind or
        # illegal comparator/contradiction cannot be relabelled as source absence.
        gap_allowed = bool(questions) and all(
            (x['code'] == 'TARGET_REQUIRES_REVIEW' and q['target']['kind'] == 'UNRESOLVED') or
            (x['code'] == 'COMPARISON_DIRECTION_UNRESOLVED' and
                any(z['field']=='comparison_order' for z in questions)) or
            (x['code'] == 'CANONICAL_RECHECK_REQUIRED' and x['path'] == 'quality'
                and only_reviewable_definition)
            for x in issues) and not other_questions and all(map(reviewable_action, extraction_actions))
        items[qid] = dict(query_id=qid, business_goal=deepcopy(q['business_goal']),
            target_kind=q['target']['kind'], missing_coordinates=deepcopy(questions), wire_issues=deepcopy(issues),
            original_audit_actions=deepcopy(actions), other_business_questions=deepcopy(other_questions),
            material_gap_allowed=gap_allowed,
            allowed_dispositions=['PENDING', 'READING_ERROR'] + (['MATERIAL_GAP'] if gap_allowed else []))
    if not items:
        raise intake.IntakeError('NO_CURRENT_A0_STOP_TO_REVIEW')
    identity = s.model_dump(mode='json');identity.pop('reading_stop_review', None)
    catalog = sources(s)
    result = dict(version=VERSION, binding_sha256=intake._sha(dict(version=VERSION, intake=identity,
        items=items, source_catalog=catalog, authority=authority)), expected_authority=authority,
        items=items, source_catalog=catalog,
        decisions={qid:dict(disposition='PENDING', reason='', source_ids=[]) for qid in items},
        is_approval=False, scope='Stop reason only. No ready/accepted disposition, target replacement or scientific approval.')
    if target_fields: result['target_fields'] = deepcopy(target_fields)
    return result


def _validate(record, sheet):
    r = StopReview.model_validate(record.model_dump(mode='json') if isinstance(record, StopReview) else record)
    if (r.binding_sha256 != sheet['binding_sha256'] or r.authority != sheet['expected_authority']
            or r.target_fields != sheet.get('target_fields', {})
            or set(r.decisions) != set(sheet['items']) or not r.reviewer.strip() or not r.evidence.strip()):
        raise intake.IntakeError('INVALID_OR_STALE_STOP_REVIEW')
    for qid,d in r.decisions.items():
        if (d.disposition not in sheet['items'][qid]['allowed_dispositions'] or not d.reason.strip()
                or len(set(d.source_ids)) != len(d.source_ids)
                or any(k not in sheet['source_catalog'] for k in d.source_ids)
                or (d.disposition != 'PENDING' and not d.source_ids)):
            raise intake.IntakeError('INVALID_STOP_REVIEW_DECISION_OR_SOURCES')
    return r


def prepare_review(value, *, authority='EXTERNAL_RESEARCH_REVIEW', target_fields=None):
    s = intake._checked(value)
    # Avoid applying the stored stop classification while preparing its own
    # worksheet. Reading-change review and all original gates still run.
    plain = s.model_copy(update={'reading_stop_review': None})
    if target_fields is None and s.reading_stop_review is not None:
        target_fields = SavedReview.model_validate(s.reading_stop_review).record.target_fields
    sheet = _worksheet(plain, intake.inspect(plain), authority, target_fields)
    return dict(state='REVIEW_REQUIRED', stop_worksheet=sheet, request=None,
                api_calls=0, core_called=False, scientific_approval=False, mathematical_claim=None)


def review_stop(value, record, *, authority='EXTERNAL_RESEARCH_REVIEW'):
    s = intake._checked(value)
    proposed = StopReview.model_validate(record.model_dump(mode='json') if isinstance(record,StopReview) else record)
    sheet = prepare_review(s, authority=authority, target_fields=proposed.target_fields)['stop_worksheet']
    r = _validate(record, sheet)
    old = SavedReview.model_validate(s.reading_stop_review) if s.reading_stop_review is not None else None
    history = [*old.history, old.record] if old else []
    for prior in history:
        plain = s.model_copy(update={'reading_stop_review': None})
        _validate(prior, _worksheet(plain, intake.inspect(plain), authority, prior.target_fields))
    saved = SavedReview(record=r, history=history).model_dump(mode='json')
    revised = intake._checked(s.model_copy(update={'reading_stop_review': saved}))
    if intake.inspect(revised)['state'] == 'CHECK_BLOCKED':
        raise intake.IntakeError('INVALID_OR_STALE_STOP_REVIEW')
    return revised


def apply_review(s, reading):
    saved = SavedReview.model_validate(s.reading_stop_review)
    sheet = _worksheet(s, reading, saved.record.authority, saved.record.target_fields)
    for prior in saved.history:
        _validate(prior, _worksheet(s, reading, prior.authority, prior.target_fields))
    r = _validate(saved.record, sheet)
    states = {'PENDING':'REVIEW_REQUIRED', 'MATERIAL_GAP':'NEEDS_INPUT', 'READING_ERROR':'READING_RECHECK_REQUIRED'}
    reasons = {'PENDING':'A0_STOP_REVIEW_PENDING', 'MATERIAL_GAP':'SOURCE_CONFIRMED_TARGET_GAP',
               'READING_ERROR':'SOURCE_REVIEW_REQUIRES_A0_REREAD'}
    rows = {}
    for qid,d in r.decisions.items():
        item = sheet['items'][qid]
        rows[qid] = dict(state=states[d.disposition], reason_code=reasons[d.disposition],
            disposition=d.disposition, reason=d.reason, source_ids=d.source_ids,
            clarification_questions=deepcopy(item['missing_coordinates']) if d.disposition == 'MATERIAL_GAP' else [],
            original_wire_issues=deepcopy(item['wire_issues']), request=None, backend_called=False,
            mathematical_claim=None, scientific_approval=False)
    receipt = dict(version=VERSION, binding_sha256=sheet['binding_sha256'],
        review_sha256=intake._sha(r.model_dump(mode='json')), authority=r.authority, reviewer=r.reviewer,
        candidate_modified=False, scientific_approval=False, mathematical_verification='NOT_PERFORMED',
        queries=rows)
    priority = ['READING_RECHECK_REQUIRED', 'REVIEW_REQUIRED', 'NEEDS_INPUT']
    state = next(v for v in priority if any(x['state']==v for x in rows.values()))
    # Preserve any original blocker outside the reviewed items.
    outside = [a for a in reading['report']['query_quality'] if a['query_id'] not in rows]
    if any(a['business_status']=='FORMULATION_RECHECK_REQUIRED' for a in outside):
        state = 'READING_RECHECK_REQUIRED'
    return dict(reading, state='BUSINESS_CLARIFICATION_REQUIRED' if state=='NEEDS_INPUT' else state,
                reason_code='SOURCE_REVIEWED_A0_STOP', reading_stop_receipt=receipt)
