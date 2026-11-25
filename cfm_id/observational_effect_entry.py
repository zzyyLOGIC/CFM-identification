"""Reuse the maintained observational planner and native builder on the homepage.

The candidate target is independently audited against original text. No A0 or
human reading receipt is invented. Scientific approval is bound to the actual
native worksheets and supplied explicitly after source review.
"""
from copy import deepcopy
from types import SimpleNamespace
from cfm_id_llm import observational_effect_source as reader
from cfm_id_llm.compact_study import digest
from . import joint_natural_entry as workflow,network_extended_dispatch as existing
from .native_evidence import payload

def reader_selection(draft):
    """Choose a source contract, never a mathematical conclusion.

    A policy-mean hint can contradict the draft's explicit comparison shape.
    The observational effects reader must recover its averaging and both ends
    from the original sources; no draft coordinates or formula are transferred.
    Mixed/multiple questions are not collapsed into one effect here.
    """
    hints=workflow.route_hints(draft)
    if reader.FAMILY in hints:
        return dict(reader=reader.FAMILY,reason='EXPLICIT_READER_HINT',scientific_approval=False)
    answers=draft.get('answers',[]) if isinstance(draft,dict) else []
    if 'NETWORK_OBSERVATIONAL_POLICY' in hints and isinstance(answers,list) and len(answers)==1:
        answer=answers[0]
        if isinstance(answer,dict):
            target=answer.get('target')
            quantity=(target.get('quantity') if isinstance(target,dict) else None) or answer.get('quantity')
            if quantity=='difference':
                return dict(reader=reader.FAMILY,reason='OBSERVATIONAL_COMPARISON_REQUIRES_EFFECT_READING',
                    original_hints=sorted(hints),quantity=quantity,scientific_approval=False)
    return None


def proposed(case,draft):return reader_selection(draft) is not None
def prepare(case,report,call):return workflow.prepare(case,report,call,reader_module=reader,planner=plan,gap_resolver=gaps)

def legacy_plan(case,s):
    # UNAPPROVED metadata is only carried by the old *preparation* result.
    # It cannot be passed to its execution function as an approval record.
    entry=dict(reader_id=existing.reading.OBS,reference_format='short_refs',bundle=reader.bundle(case),
        fact_binding_sha256=digest(case),query_id='source-audited-question',remaining_query_ids=[],
        query_review=dict(authority='UNAPPROVED',scientific_approval=False),request_sha256=digest(s['wire']),
        selected_query=dict(target=dict(kind=s['facts']['target']['kind'])))
    return existing.inspect_methods(entry,s['wire'])

def gaps(r):
    e=r['joint_entry'];s=e['reading'];reason=e.get('reason_code') or ''
    if reason=='INDEPENDENT_READING_NOTE_REVIEW_REQUIRED':
        return {'facts.unresolved':dict(candidate=s['facts']['unresolved'],reason_code=reason,
            related_assumptions=s['facts']['assumptions'],
            instruction='核对是否为真实未解缺项/冲突。已在条件字段表达的未知状态、不能从定义推出的说明，不应重复成新的研究缺项；错误重复由后台完整重读，不自动删除。')}
    # A source audit can wrongly accept a pending/duplicate declaration as an
    # unsupported extra constraint or an explicit refusal. Check that stop
    # against the original source before showing it to the user. This review
    # can only preserve the stop, ask a source question or request a full reread.
    if reason=='ADDITIONAL_RESTRICTIONS_REQUIRE_ADAPTER' or reason.startswith('DECLARED_MODEL_EXCLUDES:'):
        key='additional_restrictions' if reason=='ADDITIONAL_RESTRICTIONS_REQUIRE_ADAPTER' else 'assumptions'
        return {'facts.'+key:dict(candidate=s['facts'][key],reason_code=reason,
            declaration_stop=True,related_assumptions=s['facts']['assumptions'],
            related_restrictions=s['facts']['additional_restrictions'])}
    if not r.get('clarification_questions'):return {}
    return {'facts':dict(candidate=s['facts'],proposed_questions=r['clarification_questions'],reason_code=r['joint_entry'].get('reason_code'))}

def plan(case,r):
    e=r['joint_entry'];s=e['reading'];p=legacy_plan(case,s)
    e.update(operation=reader.FAMILY,existing_plan=p,candidate_findings=p.get('exclusions',[]))
    if p.get('reason_code')=='INVALID_EXTENDED_NETWORK_READING':
        # The native planner detects cross-field contradictions that the
        # JSON schema and even a source audit can miss. Return its diagnostic
        # to the existing bounded reread, never repair coordinates ourselves.
        raise ValueError('OBSERVATIONAL_READING_CONTRACT: '+p.get('diagnostic','INVALID_EXTENDED_NETWORK_READING'))
    # A note review may return REVIEW_REQUIRED without any selected method.
    # It is not a science-confirmation sheet and must not index methods[0].
    if p['state']!='REVIEW_REQUIRED' or not p.get('methods'):
        questions=p.get('clarification_questions',[])
        reason=p.get('reason_code') or ''
        message='原有观察性方法尚未核准本次目标，以下保留实际检查结果。'
        if reason.startswith('DECLARED_MODEL_EXCLUDES:'):
            names=[existing.SCIENCE_NAMES.get(k,k) for k in reason.split(':',1)[1].split(',')]
            message='材料明确不采用此方法需要的条件：'+'；'.join(names)+'。未替你采用，也未改用另一种平均方式。'
        elif reason=='ADDITIONAL_RESTRICTIONS_REQUIRE_ADAPTER':
            restrictions=s['facts']['additional_restrictions']
            e['unhandled_declarations']=deepcopy(restrictions)
            message='读取结果中以下声明尚未接入本方法：'+'；'.join(x['text'] for x in restrictions[:3])+'。已保留原声明，未忽略它们继续计算；可在读取记录中核对是否与原文含义一致。'
        elif questions:
            message='以下研究内容尚未明确，补充后再核对；已说明的内容不需重新填写。'
        if p['state']=='NEEDS_INPUT' and s['facts']['information'] and all(v['availability']=='FINITE_SAMPLE' for v in s['facts']['information']):
            e['input_diagnostics']=[dict(field='information',cause='INFORMATION_NOT_SUPPORTED',reason='已经明确只有有限样本，当前观察性总体信息合同不接收样本代替总体律。',question=None)]
            return workflow.stop(r,'UNSUPPORTED','FINITE_SAMPLE_CONTRACT_NOT_CONNECTED','已读到有限样本；当前入口不能按此资料规格核验，不需重复填写。')
        return workflow.stop(r,'UNSUPPORTED' if p['state']=='ADAPTER_NOT_CONNECTED' else p['state'],p.get('reason_code'),
            message,questions)
    row=p['methods'][0]
    # The science worksheet also contains every extra adopted declaration.
    codes=row['science_worksheet']['decisions']
    t=s['facts']['target'];v=p['proposed_target']
    description='、'.join(t['population'])+'；'+v['outcome']+'；先比较本人'+str(t['first']['own'])+'、同伴'+str(t['first']['exposure'])+'，减去本人'+str(t['second']['own'])+'、同伴'+str(t['second']['exposure'])+'。'
    description+= {'OBSERVED_ALLOCATION_CONDITIONAL':'其余安排按同一背景下实际使用规律平均。','SHARED_PRETREATMENT_STRATUM':'先按共同处理前分组比较，再按总体分组占比平均。','OWN_AND_NEIGHBOR_BINARY_FEATURE':'按本人和邻居的处理前特征调整后，按其总体分布平均。'}[t['averaging']]
    items=[dict(code='target',label='确认本次比较和平均方式',quote=description)]
    for code in codes:
        item=s['facts']['assumptions'].get(code)
        source_quotes=[]
        if item:
            locations={v['source_id']:v for v in reader.refs(case)['aliases'].values()}
            source_quotes=[locations[k]['text'] for k in item['source_ids']]
        items.append(dict(code=code,label=existing.SCIENCE_NAMES.get(code,'确认总体信息及本次平均范围'),quote='；'.join(source_quotes) or '按本次已核对的资料覆盖和评价对象。'))
    sheet=dict(kind='joint_natural',items=items,case_sha256=digest(case),reading_binding=reader.binding(case,s),
        plan_sha256=digest(p),draft_sha256=r['draft_sha256'])
    if e.get('condition_evidence') is not None:
        sheet['condition_evidence_binding']=digest(e['condition_evidence'])
    sheet['binding']=digest([sheet.copy(),e['audit']]);r['condition_review']=sheet
    return workflow.stop(r,'REVIEW_REQUIRED',None,'观察性目标、资料和条件已按原文核对，请确认本次采用的科学前提。')

def complete(case,report,review):
    e=report['joint_entry']
    if e['case_sha256']!=digest(case) or report['draft_sha256']!=digest(report['draft']):raise ValueError('OBSERVATIONAL_SOURCE_CHANGED')
    s=reader.inspect(case,e['reading']);a=reader.check_audit(case,s,e['audit'])
    if any(x['verdict']!='MATCH' for x in a['findings']):raise ValueError('OBSERVATIONAL_SOURCE_NOT_REVIEWED')
    r=workflow.base(report,case,s,a)
    if e.get('condition_evidence') is not None:
        receipt,findings=reader.check_semantics(case,s,e['condition_evidence'],historical=True)
        if any(x['verdict']!='MATCH' for x in findings):raise ValueError('OBSERVATIONAL_CONDITION_EVIDENCE_NOT_MATCHED')
        r['joint_entry']['condition_evidence']=receipt
    r=plan(case,r);ne=r['joint_entry']
    if r.get('condition_review')!=report.get('condition_review'):raise ValueError('OBSERVATIONAL_PLAN_CHANGED')
    if workflow.record_review_decisions(r,review):return r
    p=ne['existing_plan'];row=p['methods'][0]
    evidence=SimpleNamespace(evidence='Explicit confirmation after original-source audit',binding_sha256=review['binding'],
        reviewer='homepage synthetic researcher' if review['authority']=='SYNTHETIC_TEST' else 'homepage research reviewer',authority=review['authority'])
    inquiry=existing._native_inputs(p,row,dict(science_review=evidence))
    from . import observational_methods,native_outcome_execution
    binding=observational_methods.resolve(row['method'],observational_methods.DIFFERENCE)
    fingerprint=lambda q:digest(payload(q))
    answer,before=native_outcome_execution.identify(binding,inquiry,fingerprint=fingerprint)
    verified=answer.status=='POINT'
    if verified:
        native_outcome_execution.replay_outcome(binding,answer,inquiry=inquiry,input_digest=before,fingerprint=fingerprint)
        for key in ('study','source','assumptions','signature','requests','license'):
            if hasattr(inquiry,key) and getattr(answer.result,key)!=getattr(inquiry,key):raise ValueError('OBSERVATIONAL_INPUT_MISMATCH:'+key)
        if len(answer.result.proofs)!=1:raise ValueError('EXACT_OBSERVATIONAL_EFFECT_REQUIRED')
    certificate=dict(kind='EXISTING_OBSERVATIONAL_EFFECT',operation=row['method'],target=p['proposed_target'],
        native_inputs=payload(inquiry),native_outcome=payload(answer),
        identified_functional=answer.result.proofs[0].identified_functional if verified else None)
    ne.update(completed=True,state=answer.status,reason_code=answer.reason_code,candidate_findings=[answer.summary()],
        native_result=dict(state=answer.status,certificate=certificate,summary=answer.summary(),independent_replay=verified),
        message='识别库已按本题的观察性平均方式计算并核验证书。' if verified else '原有观察性方法未核准本题，保留实际停止原因。')
    for key in ('attempts','audit_repairs','reading_repairs','gap_reviews','semantic_repairs'):ne[key]=deepcopy(e.get(key,[]))
    r.update(review_record=deepcopy(review),backend_called=True,independent_replay=verified,decision='CONDITIONAL_RESULT' if verified else 'WITHHELD')
    if verified:r['proof']=dict(method=row['method'],binder=workflow.VERSION,certificate=certificate,source_binding=reader.binding(case,s),review_binding=review['binding'])
    return r
