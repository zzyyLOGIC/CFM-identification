"""Source-reviewed homepage adapter for the existing binary-IV research API."""
from copy import deepcopy
import re
from cfm_id_llm import iv_source_reading as reader
from cfm_id_llm.compact_study import digest
from . import joint_natural_entry as workflow,iv_research,iv_route_contract as native

OPERATION='BINARY_IV_SOURCE'
LABELS={'instrument_independence':'工具分配与潜在处理和结果独立',
 'exclusion_restriction':'工具只通过实际处理影响结果',
 'consistency_and_binary_outcome':'实际记录与实际处理一致，结果为二元',
 'no_interference':'不同对象之间没有相互影响',
 'positive_instrument_support':'两种工具状态在总体中都有正概率',
 'monotonicity_direction':'没有因得到工具机会反而不接受处理的人',
 'complete_model':'已完整列出本次采用的条件'}

def proposed(case,draft):
    if 'BINARY_IV' in workflow.route_hints(draft):return True
    return bool(re.search(r'工具变量|instrumental variable|\bLATE\b|依从者', '\n'.join(reader.shared.sources(case).values()),re.I))

def prepare(case,report,call):
    return workflow.prepare(case,report,call,reader_module=reader,planner=plan,gap_resolver=gaps)

def gaps(r):
    e=r['joint_entry']
    return {k:dict(candidate=e['reading'].get(k),reason_code=e.get('reason_code'),proposed_questions=r['clarification_questions'])
        for k in e.get('missing_fields',[])} if r.get('clarification_questions') else {}

def plan(case,r):
    e=r['joint_entry'];e['operation']=OPERATION;s=e['reading'];st=s['study']['value'];t=s['target']['value'];info=s['information']['value']
    if s['family']['value']!='BINARY_IV' or t['kind'] not in ('ATE','LATE'):
        return workflow.stop(r,'UNSUPPORTED','IV_TARGET_NOT_CONNECTED','本题不是当前二元工具变量方法支持的总体ATE或依从者LATE，未改写目标。')
    cs={c['code']:c for c in s['conditions']};missing={}
    if set(LABELS)-set(cs):raise ValueError('IV_SOURCE_CONDITIONS_OMITTED:'+','.join(sorted(set(LABELS)-set(cs))))
    if not all(st.get(k,'').strip() for k in ('population','period','context','instrument','treatment','outcome')) or set(st['binary_coding'])!={'instrument','treatment','outcome'} or not all(v.strip() for v in st['binary_coding'].values()):
        missing['study']='请说明研究人群、评价时期，以及邀请或资格、实际接受服务、结果这三个变量各自0和1的含义。'
    if t['treated'] is None or t['reference'] is None:missing['target']='本题是实际接受服务减去未接受，还是相反方向？'
    elif {t['treated'],t['reference']}!={0,1}:return workflow.stop(r,'UNSUPPORTED','BINARY_IV_DIRECTION_REQUIRED','现有方法支持二元实际处理的两端比较，未改写其他对比。')
    if info['kind']=='FINITE_SAMPLE':return workflow.stop(r,'UNSUPPORTED','IV_SAMPLE_CONTRACT_NOT_CONNECTED','当前工具变量求界接口需要总体条件概率；上传的是样本，未把频率当成精确总体概率。')
    if info['kind'] not in ('EXACT_POPULATION_CONDITIONAL_LAW','UNKNOWN'):
        return workflow.stop(r,'UNSUPPORTED','IV_INFORMATION_NOT_CONNECTED','现有工具变量方法需要按工具两种状态给出的处理与结果联合总体概率，当前资料形式未接入。')
    if info['kind']=='UNKNOWN' or info['complete'] is not True or info['same_scope'] is not True or len(info['cells'])!=8:
        missing['information']='请提供同一研究下，按工具两种状态分别列出的实际处理与结果的八格总体条件概率，并说明表格是否完整。'
    required=[k for k in LABELS if k!='monotonicity_direction']
    mono=cs['monotonicity_direction']['status']
    if t['kind']=='LATE' or mono=='ADOPTED':required.append('monotonicity_direction')
    elif mono in ('UNKNOWN','UNDECIDED'):missing['conditions']='本题是否采用无违背者条件：得到机会不会使原本愿意参加的人反而不参加？也可以明确不采用。'
    elif mono=='CONTRADICTED':return workflow.stop(r,'UNSUPPORTED','IV_MONOTONICITY_CONFLICT','单调性声明存在冲突，未替你选择采用状态。')
    for k in required:
        if cs[k]['status'] in ('NOT_ADOPTED','CONTRADICTED'):
            return workflow.stop(r,'UNSUPPORTED','IV_PREMISE_NOT_ADOPTED','本题未采用所需前提：'+LABELS[k]+'，未替你补上。')
        if cs[k]['status']!='ADOPTED':missing['conditions']='本次是否采用：'+'；'.join(LABELS[j] for j in required if cs[j]['status']!='ADOPTED')+'？'
    extras=[c for c in s['conditions'] if c['code'] not in LABELS]+s['remaining']
    blocked=[c for c in extras if c['status'] in ('ADOPTED','CONTRADICTED')]
    if blocked:
        e['unhandled_declarations']=blocked
        return workflow.stop(r,'UNSUPPORTED','IV_ADDITIONAL_RESTRICTION_NOT_CONNECTED','以下额外条件尚未纳入当前工具变量模型：'+'；'.join(c['statement'] for c in blocked)+'。未忽略它们求界。')
    pending=[c for c in extras if c['status'] in ('UNKNOWN','UNDECIDED')]
    if pending:missing['remaining']='本次对以下条件如何决定：'+'；'.join(c['statement'] for c in pending)+'？'
    if missing:
        e['missing_fields']=list(missing)
        return workflow.stop(r,'NEEDS_INPUT','IV_INFORMATION_REQUIRED','本题有具体信息需要补充。',list(missing.values()))
    codes=list(native.SCIENCE_DECISIONS if mono=='ADOPTED' else [k for k in native.SCIENCE_DECISIONS if k!='monotonicity_direction'])
    source_ids=list(dict.fromkeys(['question',*[v['source_id'] for v in case['sources']]]))
    if len(source_ids)>30:return workflow.stop(r,'UNSUPPORTED','IV_SOURCE_COUNT_LIMIT','当前工具变量研究合同最多登记30份来源，原材料未截断。')
    p=native.IVProblem(version=native.VERSION,target=t['kind'],cells=info['cells'],monotonicity=mono=='ADOPTED',
        instrument=st['instrument'],treatment=st['treatment'],outcome=st['outcome'],population=st['population'],
        context=st['context']+'；时期：'+st['period'],source_ids=source_ids,
        source_sha256=digest(case),assumptions=codes)
    native.validate(p);e['problem']=p.model_dump(mode='json')
    items=[dict(code='target',label='本次比较的人群和方向',quote=t['description']),
        dict(code='information',label='总体概率及变量编码',quote='；'.join(info_row['quote'] for info_row in s['information']['evidence']))]
    items += [dict(code=k,label=LABELS[k],quote=cs[k]['statement']) for k in required]
    sheet=dict(kind='joint_natural',items=items,case_sha256=digest(case),reading_binding=reader.binding(case,s),draft_sha256=r['draft_sha256'])
    sheet['binding']=digest([sheet.copy(),e['audit']]);r['condition_review']=sheet
    return workflow.stop(r,'REVIEW_REQUIRED',None,'原问题与概率表已核对，请确认本次采用的科学前提。')

def complete(case,report,review):
    e=report['joint_entry']
    if e['case_sha256']!=digest(case) or report['draft_sha256']!=digest(report['draft']):raise ValueError('IV_SOURCE_CHANGED')
    s=reader.inspect(case,e['reading']);a=reader.check_audit(case,s,e['audit'])
    if any(f['verdict']!='MATCH' for f in a['findings']):raise ValueError('IV_SOURCE_NOT_REVIEWED')
    r=plan(case,workflow.base(report,case,s,a));current=r['joint_entry']
    if r.get('condition_review')!=report.get('condition_review') or current.get('problem')!=e.get('problem'):raise ValueError('IV_REVIEW_CHANGED')
    if workflow.record_review_decisions(r,review):return r
    p=native.IVProblem.model_validate(current['problem']);ph=native.digest(p)
    def subreview(codes):return dict(authority=review['authority'],reviewer='homepage researcher',
        evidence='Audited original materials plus explicit current scientific confirmation: '+review['binding'],
        problem_sha256=ph,decisions={k:'ACCEPTED' for k in codes})
    nr=iv_research.submit(p,review=native.IVReview(version=p.version,problem_sha256=ph,
        reading_review=native.IVReadingReview(**subreview(native.READING_DECISIONS)),
        science_review=native.IVScienceReview(**subreview(native.science_decisions(p)))),research_protocol_selected=True)
    verified=nr.get('certificate_replayed',False);state=nr['state'];certificate=None
    if verified:
        # The existing presentation adapter retains the requested subtraction
        # direction; its exact verifier also checks the original IV result.
        from .direct_iv_evidence import conditional_answer
        st=s['study']['value'];t=s['target']['value']
        doc=dict(roles=dict(instrument='Z',treatment='D',outcome='Y'),target=dict(type=t['kind'],treated=t['treated'],reference=t['reference']),
            assumptions=dict(monotonicity='nondecreasing' if p.monotonicity else 'not_imposed'),
            population=st['population'],period=st['period'],outcome_label=st['outcome'])
        answer,ev=conditional_answer(doc,p.observed())
        if answer['status']!=state:raise ValueError('IV_NATIVE_DISPLAY_STATE_MISMATCH')
        certificate=dict(kind=OPERATION,target=t,study=st,answer=answer,native=nr,conditional_evidence=ev)
    current.update(completed=True,state=state,reason_code=nr.get('reason_code'),
        native_result=dict(state=state,certificate=certificate,independent_replay=verified),
        message='识别库已核验本次工具变量结果和证书。' if verified else '识别库已返回本题的具体停止原因，未生成可交付结果。')
    for k in ('attempts','audit_repairs','gap_reviews'):current[k]=deepcopy(e.get(k,[]))
    r.update(review_record=deepcopy(review),backend_called=nr['backend_called'],independent_replay=verified,decision='CONDITIONAL_RESULT' if verified else 'WITHHELD')
    if verified:r['proof']=dict(method=OPERATION,binder=workflow.VERSION,certificate=certificate,source_binding=reader.binding(case,s),review_binding=review['binding'])
    return r
