from copy import deepcopy
from cfm_id_bridge.scientific_binding import sha
from cfm_id_llm import symbolic_mean_reading as reader
from cfm_id_llm.compact_study import digest
from . import symbolic_mean_joint as native,joint_natural_entry as workflow

def prepare(case,report,call):
    return workflow.prepare(case,report,call,reader_module=reader,planner=plan,gap_resolver=lambda r:{},diagnose_stop=unsupported_stop)


def unsupported_stop(case,r):
    """Stop only on individually audited adopted restrictions, never approve."""
    e=r['joint_entry'];s=e['reading'];audit=reader.check_audit(case,s,e['audit'])
    if s['wire'].get('version')!='symbolic-source-reading/2':return None
    if any(f['verdict']=='READING_ERROR' for f in audit['findings']):return None
    findings={f['field']:f for f in audit['findings']};diagnostics=[]
    for i,row in enumerate(s['wire']['problem']['additional_restrictions']):
        field=f'additional_restrictions.{i}';finding=findings[field]
        if row['status']=='ADOPTED' and finding['verdict']=='MATCH' and finding['evidence']:
            diagnostics.append(dict(field=field,cause='ADOPTED_RESTRICTION_NOT_SUPPORTED',
                statement=row['statement'],evidence=finding['evidence'],reason=finding['reason'],question=None))
    if not diagnostics:return None
    e.update(operation=native.ROUTE,problem=s['problem'],input_diagnostics=diagnostics,
        deferred_questions=[f for f in audit['findings'] if f['verdict']=='NEEDS_CLARIFICATION'])
    text='；'.join(x['statement'].rstrip('。； ') for x in diagnostics)
    return workflow.stop(r,'UNSUPPORTED','ADDITIONAL_RESTRICTIONS_NOT_EXPRESSED',
        '已读到本次采用的额外条件：'+text+'。当前符号求界方法只能处理已表达的线性均值约束，尚不能核验这项条件。无需再次确认是否采用；已保留原答和全部条件，未忽略它们计算界限。这不是不可识别的数学证明。')

def plan(case,r):
    stopped=unsupported_stop(case,r)
    if stopped is not None:return stopped
    e=r['joint_entry'];p=e['reading']['problem'];e.update(operation=native.ROUTE,problem=p)
    if e['reading']['wire'].get('version')=='symbolic-source-reading/2':
        pending=[x for x in e['reading']['wire']['problem']['additional_restrictions']
            if x['status'] in ('UNDECIDED','UNKNOWN','CONTRADICTED')]
        if pending:
            return workflow.stop(r,'NEEDS_INPUT','UNDECIDED_RESTRICTION','以下条件的采用态度仍未明确。',
                ['本次是否采用“'+x['statement']+'”？可以回答采用、不采用或尚未决定。' for x in pending])
    ready=native.prepare(p)
    if ready['state']!='REVIEW_REQUIRED':
        messages={'FINITE_MEAN_MODEL_NOT_COMPLETE':'请说明所列均值及限制是否构成本题采用的完整研究模型；不确定也可以注明。',
            'SCIENTIFIC_DECISION_UNRESOLVED':'还有未决定的条件，请说明本次采用、不采用还是仍未决定。',
            'SAMPLE_IS_NOT_POPULATION_INFORMATION':'这份材料是有限样本，不能当成确切总体均值；当前符号入口尚不能据此核验。',
            'ADDITIONAL_RESTRICTIONS_NOT_EXPRESSED':'材料还有未表达的限制，已保留并停止，没有忽略它们求界。'}
        msg=messages.get(ready['reason_code'],'符号问题尚未通过输入检查。')
        return workflow.stop(r,ready['state'],ready['reason_code'],msg,[msg] if ready['state']=='NEEDS_INPUT' and ready['reason_code']!='SAMPLE_IS_NOT_POPULATION_INFORMATION' else [])
    labels=('核对目标与均值情形','确认总体信息及参数范围','确认所列模型完整','确认采用的等式、不等式与来源')
    names={x['id']:x['description'] for x in p['coordinates']}
    quotes=[' + '.join(str(v)+' × '+names[k] for k,v in p['target'].items())+'；固定偏移及参数项见完整目标记录。',
        '；'.join(x['description']+'，范围 '+x['lower']+' 到 '+x['upper'] for x in p['parameters']),
        '本题只采用已列出的均值、范围和限制，没有遗漏其他约束。',
        '采用 '+str(sum(x['adoption']=='ADOPTED' for x in p['constraints']))+' 条限制；不采用 '+str(sum(x['adoption']=='NOT_ADOPTED' for x in p['constraints']))+' 条。原句与具体关系保存在下方来源记录中。']
    sheet=dict(kind='joint_natural',items=[dict(code=k,label=label,quote=quote) for k,label,quote in zip(native.DECISIONS,labels,quotes)],
        case_sha256=digest(case),reading_binding=reader.binding(case,e['reading']),problem_sha256=sha(p),draft_sha256=r['draft_sha256'])
    sheet['binding']=digest([sheet.copy(),e['audit']]);r['condition_review']=sheet
    return workflow.stop(r,'REVIEW_REQUIRED',None,'已核对参数、均值及全部限制，请确认本次研究模型。')

def complete(case,report,review):
    e=report['joint_entry']
    if e['case_sha256']!=digest(case) or report['draft_sha256']!=digest(report['draft']):raise ValueError('SYMBOLIC_SOURCE_CHANGED')
    s=reader.inspect(case,e['reading']);a=reader.check_audit(case,s,e['audit'])
    if any(f['verdict']!='MATCH' for f in a['findings']):raise ValueError('SYMBOLIC_SOURCE_NOT_REVIEWED')
    r=plan(case,workflow.base(report,case,s,a))
    if r.get('condition_review')!=report.get('condition_review'):raise ValueError('SYMBOLIC_REVIEW_CHANGED')
    if workflow.record_review_decisions(r,review):return r
    p=s['problem'];result=native.submit(p,dict(version=native.VERSION,problem_sha256=sha(p),authority=review['authority'],
        reviewer='homepage researcher',evidence='Source-audited complete symbolic mean model and explicit user confirmation',decisions={k:'ACCEPTED' for k in native.DECISIONS}))
    r['joint_entry'].update(native_result=result,completed=True,state=result['state'],reason_code=result.get('reason_code'),message='已生成分段界限并核验证书。' if result['independent_replay'] else '符号求界未通过，保留实际停止原因。')
    r.update(review_record=deepcopy(review),independent_replay=result['independent_replay'],backend_called=result['backend_called'],decision='CONDITIONAL_RESULT' if result['independent_replay'] else 'WITHHELD')
    if result['independent_replay']:r['proof']=dict(method=native.ROUTE,binder=workflow.VERSION,certificate=result['certificate'],source_binding=reader.binding(case,s),review_binding=review['binding'])
    return r
