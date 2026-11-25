"""Consistency-only bounded binary policies -> existing exact mean LP engines.

For each unit i and full assignment z, consistency gives
 E[Y_i(z)] = p(z) m_i(z) + (1-p(z)) u_i(z), 0 <= u_i(z) <= 1.
No exchangeability, exposure sufficiency, or sample-to-population substitution.
For conditional-mean information alone and the explicitly complete model,
all residual means can vary independently: conditional on actual A, generate
the observed diagonal with its specified Bernoulli mean, and choose every
off-diagonal potential outcome with the requested residual Bernoulli mean.
Thus the box is an exact projection, including repeated policies after their
coefficients are combined. Extra adopted restrictions must be rejected first.
"""
from copy import deepcopy
from fractions import Fraction as F
from cfm_id_bridge.scientific_binding import sha
from cfm_id_llm import network_existing_reading as reader
from cfm_id_llm.joint_reading import sources
from cfm_id_llm.compact_study import digest
from . import joint_natural_entry as workflow, symbolic_mean_joint, finite_mean_joint

OPERATION='NETWORK_OBSERVATIONAL_BOUNDS'


def affine(constant='0',coefficients=None):
    return dict(constant=str(constant),coefficients=coefficients or {})


def project(s,catalog):
    """Called only after network_existing_entry.plan's scope/condition checks."""
    st=s['study']['value'];net=s['network']['value'];t=s['target']['value'];info=s['information']['value']
    nodes=net['nodes'];key=lambda z:tuple(z[n] for n in nodes)
    masses={key(row['assignment']):F(row['probability']) for row in info['assignment_masses']}
    if len(masses)!=len(info['assignment_masses']):raise ValueError('DUPLICATE_OBSERVATIONAL_ASSIGNMENT')
    policies={}
    for sign,side in [(1,t['components']),(-1,t.get('reference_components') or [])]:
        for row in side:
            z=key(row['assignment']);policies[z]=policies.get(z,F(0))+sign*F(row['probability'] or '1')
    policies={z:c for z,c in policies.items() if c}
    source_ids=list(dict.fromkeys(e['source_id'] for block in [s['study'],s['target'],s['information']] for e in block['evidence']))
    coordinates=[];parameters=[];target={};offset={};bindings=[];residuals=[]
    for node in nodes:
        w=F(t['weights'][node])
        if not w:continue
        for z,coef in policies.items():
            coef*=w;p=masses.get(z,F(0))
            if p:
                if node not in info['outcome_nodes']:raise ValueError('BOUNDS_CONDITIONAL_MEAN_NOT_COVERED')
                pid='m_'+str(len(parameters)+1)
                description=node+'在完整名单('+','.join(map(str,z))+')下的观测条件总体均值'
                parameters.append(dict(id=pid,description=description,lower='0',upper='1',source_ids=source_ids))
                offset[pid]=str(coef*p)
                bindings.append(dict(id=pid,unit=node,assignment=list(z),probability=str(p)))
            if p<1:
                cid='u_'+str(len(coordinates)+1)
                coordinates.append(dict(id=cid,description=node+'在实际名单不同于('+','.join(map(str,z))+')时，该政策下的潜在平均结果',
                    lower=affine(),upper=affine('1'),known=None,source_ids=source_ids))
                target[cid]=str(coef*(1-p));residuals.append(dict(id=cid,unit=node,assignment=list(z),probability=str(p),coefficient=str(coef)))
    if not coordinates:
        coordinates=[dict(id='zero',description='表达常数目标的辅助零坐标',lower=affine(),upper=affine(),known=affine(),source_ids=source_ids)]
        target={'zero':'0'}
    if len(parameters)>8 or len(coordinates)>12:raise ValueError('BOUNDS_SYMBOLIC_PROJECTION_LIMIT')
    problem=dict(version='symbolic-mean-joint-1',model='FINITE_MEANS_AFFINE_PARAMETERS',outcome_domain='BINARY',
        context=st['fixed_background']+'；时期：'+st['period'],target_description=t['description'],target=target,
        target_offset=affine(coefficients=offset),parameters=parameters,coordinates=coordinates,constraints=[],
        sources={k:catalog[k] for k in source_ids},information='POPULATION_MEANS',model_complete=True,unresolved=[],additional_restrictions=[])
    if not parameters:
        problem.update(version='finite-mean-joint-1',model='FINITE_MEANS_WITH_DECLARED_LINEAR_CONSTRAINTS',target_offset='0')
        problem.pop('parameters')
        for c in problem['coordinates']:
            for k in ('lower','upper','known'):
                if c[k] is not None:c[k]=c[k]['constant']
    projection=dict(version='observational-binary-consistency-projection/1',reading_sha256=digest(s),
        parameter_queries=bindings,residual_means=residuals,problem_sha256=sha(problem),
        identity='E[Y_i(z)|W]=p(z|W)*E[Y_i^obs|A=z,W]+(1-p(z|W))*E[Y_i(z)|A!=z,W]',
        scope='binary outcomes; only node conditional means; explicitly complete model; no additional adopted restrictions')
    return problem,projection


def plan_validated(case,r):
    e=r['joint_entry'];s=e['reading']
    try:p,projection=project(s,sources(case))
    except ValueError as exc:
        return workflow.stop(r,'UNSUPPORTED',str(exc),'完整材料已保留，当前观察性界限转换不能继续：'+str(exc))
    native=symbolic_mean_joint if p['version']=='symbolic-mean-joint-1' else finite_mean_joint
    ready=native.prepare(p)
    e.update(operation=OPERATION,problem=p,projection=projection)
    if ready['state']!='REVIEW_REQUIRED':return workflow.stop(r,ready['state'],ready['reason_code'],'本题尚未通过界限输入检查。')
    cs={x['code']:x for x in s['conditions']}
    from .network_existing_entry import NAMES
    items=[dict(code='target',label='本次完整政策比较',quote=s['target']['value']['description']),
           dict(code='information',label='观测条件均值与完整安排概率',quote='；'.join(x['quote'] for x in s['information']['evidence']))]
    items.extend(dict(code=k,label=NAMES[k],quote=cs[k]['statement']) for k in e['required_conditions'])
    sheet=dict(kind='joint_natural',items=items,case_sha256=digest(case),reading_binding=reader.binding(case,s),
               problem_sha256=sha(p),draft_sha256=r['draft_sha256'])
    sheet['binding']=digest([sheet.copy(),e['audit']]);r['condition_review']=sheet
    return workflow.stop(r,'REVIEW_REQUIRED',None,'不采用无混杂条件；按已声明的二元结果、总体信息和完整模型核验上下界。')


def complete(case,report,review):
    from .network_existing_entry import plan
    e=report['joint_entry']
    if e['case_sha256']!=digest(case) or report['draft_sha256']!=digest(report['draft']):raise ValueError('BOUNDS_SOURCE_CHANGED')
    s=reader.inspect(case,e['reading']);a=reader.check_audit(case,s,e['audit'])
    if any(x['verdict']!='MATCH' for x in a['findings']):raise ValueError('BOUNDS_SOURCE_NOT_REVIEWED')
    r=plan(case,workflow.base(report,case,s,a));fresh=r['joint_entry']
    if (fresh.get('operation')!=OPERATION or r.get('condition_review')!=report.get('condition_review')
        or fresh.get('problem')!=e.get('problem') or fresh.get('projection')!=e.get('projection')):
        raise ValueError('BOUNDS_PROJECTION_OR_REVIEW_CHANGED')
    if workflow.record_review_decisions(r,review):return r
    p=fresh['problem'];native=symbolic_mean_joint if p['version']=='symbolic-mean-joint-1' else finite_mean_joint
    result=native.submit(p,dict(version=p['version'],problem_sha256=sha(p),authority=review['authority'],
        reviewer='homepage researcher',evidence='Audited observational conditional means, binary complete model and explicit scientific review',
        decisions={k:'ACCEPTED' for k in native.DECISIONS}))
    for key in ('attempts','audit_repairs','reading_repairs','gap_reviews'):
        if key in e:fresh[key]=deepcopy(e[key])
    fresh.update(native_result=result,completed=True,state=result['state'],reason_code=result.get('reason_code'),
        message='已按原文条件生成观察性政策界限，证书独立核验通过。' if result['independent_replay'] else '界限未通过核验，已保留停止原因。')
    r.update(review_record=deepcopy(review),independent_replay=result['independent_replay'],backend_called=result['backend_called'],
        decision='CONDITIONAL_RESULT' if result['independent_replay'] else 'WITHHELD')
    if result['independent_replay']:r['proof']=dict(method=OPERATION,binder=workflow.VERSION,certificate=result['certificate'],
        source_binding=reader.binding(case,s),review_binding=review['binding'],projection=fresh['projection'])
    return r
