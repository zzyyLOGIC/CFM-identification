"""Convert audited source fields to the original single-intervention ID contract."""
from copy import deepcopy
from cfm_id_llm.compact_study import digest
from cfm_id_llm import dag_id_reading as old_reader,joint_reading as reader
from . import dag_id_route as native,joint_natural_entry as workflow

OPERATION='DAG_SINGLE_SOURCE'

def problem_from_source(case,s,*,confirmed):
    if workflow.active_graph_restrictions(s):raise ValueError('DAG_EXTRA_LINEAR_CONSTRAINT')
    g=s['graph']['value'];t=s['dag_target']['value'];info=s['dag_information']['value']
    cs={c['code']:c for c in s['conditions']}
    def ids(claim):return list(dict.fromkeys(x['source_id'] for x in claim['evidence']))
    def claim(code):return dict(value=cs[code]['status']=='ADOPTED',source_ids=ids(cs[code]))
    scope={k:claim(v) for k,v in dict(static_acyclic='recursive_scm',graph_complete='graph_complete',
        latent_causes_accounted='graph_complete',independent_errors='recursive_scm',
        perfect_intervention='perfect_intervention',no_between_unit_interference='no_between_unit_interference').items()}
    old=old_reader.DagIdReading.model_validate(dict(version='dag-id-reading-1',
        variables=[dict(name=n,observation='OBSERVED',domain='FINITE_DISCRETE',source_ids=ids(s['graph'])) for n in g['nodes']],
        relations=[dict(cause=a,effect=b,kind='DIRECT_CAUSE',source_ids=ids(s['graph'])) for a,b in g['directed']],
        common_causes=[dict(first=a,second=b,source_ids=ids(s['graph'])) for a,b in g['bidirected']],
        target=dict(kind=t['query_kind'],treatment=t['treatments'][0],outcome=t['outcome'][0],
            context=t['context']+'；时期：'+t['period'],source_ids=ids(s['dag_target'])),
        scope=scope,information=dict(kind=info['kind'],variables=info['variables'],
            source_ids=ids(s['dag_information']),positivity=claim('strict_positivity')),
        adjustment=None,adjustment_source_ids=[],additional_restrictions=[],unresolved=[]))
    return old_reader.to_problem(old,graph_source='independently source-audited reading '+reader.binding(case,s),
        materials_sha256=digest(case),researcher_confirmed=confirmed)

def plan_validated(case,r):
    # Called only after all required source fields/conditions and extra claims
    # have been checked by the shared planner. Preserve native declarations.
    e=r['joint_entry'];s=e['reading'];t=s['dag_target']['value'];info=s['dag_information']['value'];g=s['graph']['value']
    e['operation']=OPERATION
    if len(t['outcome'])!=1:
        return workflow.stop(r,'UNSUPPORTED','SINGLE_ID_OUTCOME_SET_CONTRACT','原单变量ID读取合同暂时只接一个结果变量；未删去原问中的其他结果。')
    if info['kind']!='FULL_JOINT_POPULATION_LAW':
        return workflow.stop(r,'UNSUPPORTED','SINGLE_ID_POPULATION_CONTRACT','当前单变量一般ID合同要求完整观测联合总体分布；没有把样本或边际统计升级为总体分布。')
    if set(info['variables'])!=set(g['nodes']):
        return workflow.stop(r,'NEEDS_INPUT','SINGLE_ID_VARIABLE_COVERAGE','总体联合分布未覆盖图中的全部观测变量。',['已有总体联合分布具体覆盖图中的哪些变量？'])
    # A source declaration is not a human confirmation; graph_status is set
    # only at complete(), after the bound scientific sheet is accepted.
    p=problem_from_source(case,s,confirmed=False);e['problem']=p
    cs={c['code']:c for c in s['conditions']}
    required=(*workflow.DAG_REQUIRED,'no_between_unit_interference')
    items=[dict(code='target',label='本次干预与结果',quote=t['context']+'；设定 '+t['treatments'][0]+'；结果 '+t['outcome'][0])]
    items += [dict(code=k,label=workflow.LABELS[k],quote=cs[k]['statement']) for k in required]
    sheet=dict(kind='joint_natural',items=items,case_sha256=digest(case),reading_binding=reader.binding(case,s),draft_sha256=r['draft_sha256'])
    sheet['binding']=digest([sheet.copy(),e['audit'],p]);r['condition_review']=sheet
    return workflow.stop(r,'REVIEW_REQUIRED',None,'图、研究目标和资料已核对，请确认原文声明的科学前提。')

def complete(case,report,review):
    e=report['joint_entry']
    if e['case_sha256']!=digest(case) or report['draft_sha256']!=digest(report['draft']):raise ValueError('SINGLE_ID_SOURCE_CHANGED')
    s=reader.inspect(case,e['reading']);a=reader.check_audit(case,s,e['audit'])
    if any(f['verdict']!='MATCH' for f in a['findings']):raise ValueError('SINGLE_ID_SOURCE_NOT_REVIEWED')
    r=workflow.plan(case,workflow.base(report,case,s,a));current=r['joint_entry']
    if r.get('condition_review')!=report.get('condition_review') or current.get('problem')!=e.get('problem'):raise ValueError('SINGLE_ID_REVIEW_CHANGED')
    if workflow.record_review_decisions(r,review):return r
    p=problem_from_source(case,s,confirmed=True)
    nr=native.submit(p,dict(version=p['version'],problem_sha256=native.digest(p),authority=review['authority'],
        reviewer='homepage researcher',evidence='source audit plus explicit current scientific confirmation '+review['binding'],
        decisions={k:'ACCEPTED' for k in native.DECISIONS}))
    state=nr.get('native_state',nr['state']);verified=state=='POINT' or nr.get('nonidentification_proved',False)
    if nr.get('nonidentification_proved'):state='NONIDENTIFIABLE'
    certificate=dict(kind=OPERATION,target=s['dag_target']['value'],native=nr,problem=p) if verified else None
    current.update(completed=True,state=state,reason_code=nr.get('reason_code'),
        native_result=dict(state=state,certificate=certificate,independent_replay=verified),
        message='原一般ID方法已给出公式并核验证书。' if state=='POINT' else '原一般ID方法已核验本图下的不可识别见证。' if state=='NONIDENTIFIABLE' else '一般ID方法已返回具体停止原因，未改算其他问题。')
    for k in ('attempts','audit_repairs','gap_reviews'):current[k]=deepcopy(e.get(k,[]))
    r.update(review_record=deepcopy(review),backend_called=nr.get('backend_called',False),independent_replay=verified,decision='CONDITIONAL_RESULT' if verified else 'WITHHELD')
    if verified:r['proof']=dict(method=OPERATION,binder=workflow.VERSION,certificate=certificate,source_binding=reader.binding(case,s),review_binding=review['binding'])
    return r
