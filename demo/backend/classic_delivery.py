"""Create a registration only from the selected run's reviewed, replayed native answer."""
from copy import deepcopy

from cfm_id.classic_query_exchange import VERSION, SCOPES, UnsupportedRegistration, project_handoff, require
from cfm_id_llm.compact_study import digest
from .capabilities import identity


def approved_record(sheet,record,authority):
    require(identity(sheet)==identity(record) and record['authority']==authority and
            set(sheet['decisions'])==set(record['decisions']) and set(record['decisions'].values())=={'ACCEPTED'},
            'CLASSIC_REVIEW_DOES_NOT_BIND_RESULT')
    return deepcopy(record)


def prepare(run):
    plan,result=run.plan,run.result
    if (result.get('state') not in ('POINT','PARTIAL') or not result.get('independent_replay')
            or result.get('clarification_questions')):
        return None
    source_bound=(run.id==run.case['case_id'] or (run.artifacts.get('imported_reading_source')==run.case['case_id']
                  and run.intake.case.model_dump(mode='json')==run.case))
    require(run.reading_mode=='classic' and run.authority in SCOPES and source_bound
            and run.query_id==result['query_id']==plan['query_id']
            and plan['plan_sha256']==result['plan_sha256'],'CLASSIC_REVIEWED_RUN_REQUIRED')
    method=result.get('primary_method')
    if not method or method not in run.reviews.get('native_reviews',{}):
        raise UnsupportedRegistration('UNCONNECTED_CLASSIC_REVIEW_CONTRACT')
    answer=next(a for a in result['answers'] if a['method']==method)
    row=next(m for m in plan['methods'] if m['method']==method)
    require(answer['independent_replay'] and result['mathematical_claim']==answer['mathematical_claim']
            and result['certificate']==answer['certificate'],'CLASSIC_PRIMARY_ANSWER_MISMATCH')
    pair=run.reviews['native_reviews'][method]
    records=dict(plan=approved_record(plan['plan_worksheet'],run.reviews['plan_review'],run.authority),
                 reading=approved_record(row['reading_worksheet'],pair['reading_review'],run.authority),
                 science=approved_record(row['science_worksheet'],pair['science_review'],run.authority))
    facts=plan.get('facts') or plan.get('endpoint_plans',{}).get('first',{}).get('facts')
    if facts:
        materials={k:deepcopy(facts[k]) for k in ('study','exposure','assignment','regime','conditioning','information',
                   'bounded_model') if k in facts}
    elif 'proposed_problem' in row:
        materials=deepcopy(row['proposed_problem'])
    else:
        raise UnsupportedRegistration('UNCONNECTED_CLASSIC_STUDY')
    evidence=dict(method=method,claim=deepcopy(answer['mathematical_claim']),certificate=deepcopy(answer['certificate']),
                  materials=materials,query_view=deepcopy(answer.get('query_view')),case_sha256=digest(run.case))
    if 'endpoint_sha256' in answer['certificate']:
        evidence['endpoints']=deepcopy(answer['native_evidence']['endpoints'])
    if method in ('R3_MEAN_SIGNATURE','R3_P_STANDARDIZED_EFFECTS'):
        native=answer['native_evidence']
        native=native.get('result',native)
        if 'assignment_masses' in native['source']:
            evidence['finite_observation']=dict(source_index=row['source_index'],source_id=native['source']['source_id'],
                signature=deepcopy(native['signature']),operator=native['source']['operator'])
    packet=dict(version=VERSION,case_id=run.id,query_id=run.query_id,plan_sha256=plan['plan_sha256'],
                purpose='REGISTER_FOR_DATA_REVIEW',release_scope=run.authority,reviews=records,evidence=evidence,
                estimate_handoff=project_handoff(evidence))
    packet['binding']=digest(packet)
    return packet
