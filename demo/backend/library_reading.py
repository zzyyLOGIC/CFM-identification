"""Open a new reviewed classic run while keeping the original answer and its receipt intact."""
from copy import deepcopy
from cfm_id import business_intake, business_dispatch, business_field_review
from cfm_id_llm.compact_response_contract import evidence_contract


def start(engine,owner,value):
    from .engine import Run
    if 'source_run' in value:
        parent=engine.get(owner,value['source_run'])
        if value.get('allow_send') is not True or parent.busy or not parent.case:
            raise ValueError('CLASSIC_READING_REQUIRES_CONSENT_AND_COMPLETE_INPUT')
        run=Run(owner=owner,synthetic=parent.synthetic,provider=parent.provider,model_settings=deepcopy(parent.model_settings),
                automatic_review=parent.automatic_review)
        run.case=dict(deepcopy(parent.case),case_id=run.id)
        run.network=parent.network
        run.attachment_report=deepcopy(parent.attachment_report)
        action=engine._read_case
    else:
        intake=business_intake._checked(value['intake'])
        query=value['query_id']
        entry=business_dispatch.prepare_reader(intake,query)
        if not entry.get('query_worksheet'):
            raise ValueError('CURRENT_QUERY_WORKSHEET_REQUIRED')
        if not isinstance(value['candidate'],dict) or not isinstance(value['request_sha256'],str):
            raise ValueError('SAVED_READING_REQUIRED')
        run=Run(owner=owner,synthetic=value.get('synthetic') is True,intake=intake,query_id=query,
                case=intake.case.model_dump(mode='json'))
        run.submission=dict(candidate=deepcopy(value['candidate']),request_sha256=value['request_sha256'])
        original=value['query_review']
        if not isinstance(original,dict) or original.get('authority')!=run.authority:
            raise ValueError('ORIGINAL_READING_REVIEW_REQUIRED')
        sheet = entry['query_worksheet']
        if evidence_contract(intake.a0_response_contract) is not None:
            sheet = business_field_review.prepare(intake,query,authority=run.authority)['field_worksheet']
        run.artifacts['imported_reading_source']=intake.case.case_id
        run.artifacts['original_target_record']=deepcopy(original)
        def action(r):
            engine._set_review(r,'saved_target',{'query':sheet})
    with engine.lock:
        if any(r.owner==owner and r.busy for r in engine.runs.values()):
            raise ValueError('RUN_ALREADY_BUSY')
        if len(engine.runs)>=100:
            raise ValueError('LOCAL_RUN_LIMIT_RESTART_SERVER')
        engine.runs[run.id]=run
        engine.save(run,'case',run.case)
        engine.launch(run,action)
    return run.id


def review_target(engine,run,record):
    # Original fact references include the original reviewer's identity and evidence.
    # Validate both records on the same question. Preserve the hash seen by the reader.
    original=run.artifacts['original_target_record']
    if record.get('version') == business_field_review.VERSION:
        current_review=business_field_review.submit(run.intake,run.query_id,record,authority=run.authority)
        if original.get('version') == business_field_review.VERSION:
            original=business_field_review.submit(run.intake,run.query_id,original,authority=run.authority)['query_review']
        record=current_review['query_review']
    current=business_dispatch.prepare_reader(run.intake,run.query_id,query_review=record)
    entry=business_dispatch.prepare_reader(run.intake,run.query_id,query_review=original)
    if (current.get('state')!='READY_TO_READ' or entry.get('state')!='READY_TO_READ'
            or entry.get('request_sha256')!=run.submission['request_sha256']
            or entry.get('intake_sha256')!=current.get('intake_sha256') or entry.get('selected_query')!=current.get('selected_query')):
        run.result=dict(state='CHECK_BLOCKED',reason_code=current.get('reason_code') or entry.get('reason_code') or 'READING_DOES_NOT_MATCH_ORIGINAL_REQUEST',
                        clarification_questions=current.get('clarification_questions'),independent_replay=False)
        run.review_kind=None
        engine.event(run,'STOPPED','目标审核或原读题绑定未通过，请核对相应材料。')
        return
    run.entry=entry
    run.submission['query_review']=original
    engine._plan(run)
