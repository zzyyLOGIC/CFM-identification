"""Source-bound local target lists, using the existing native linear composition.

The model's answer is retained separately. Each question keeps its own source
projection, weights and native certificate; missing questions cannot disappear.
This adapter does not aggregate intervals or register estimation deliveries.
"""
from copy import deepcopy
from fractions import Fraction
import re

from cfm_id_llm.compact_study import digest
from . import network_target_scope as scope

VERSION='network-local-targets/1'


def eligible(case, network):
    return network is not None and (bool(scope.weight_sources(case)) or
        len(re.findall(r'(?m)^\s*\d+[.、]\s*[^\n]+',case['business_question']))>1)


def check_review(sheet, review):
    if (not isinstance(review,dict) or set(review)!={'binding','authority','decisions'}
            or review['binding']!=sheet['binding']
            or review['authority'] not in ('SYNTHETIC_TEST','EXTERNAL_RESEARCH_REVIEW')
            or not isinstance(review['decisions'],dict)
            or set(review['decisions'])!={i['code'] for i in sheet['items']}
            or any(v not in ('ADOPTED','UNSURE','DECLINED') for v in review['decisions'].values())):
        raise ValueError('LOCAL_TARGET_REVIEW_REQUIRED_OR_STALE')


def _unsupported_constraints(case):
    from .network_grounded_contrast import source_lines
    rows=source_lines(case)
    for row in rows:
        line=row['quote']
        if re.search(r'单调|均值顺序|额外.{0,5}(?:限制|约束)|跨(?:对象|单位).{0,8}(?:等式|限制)|均值.{0,12}(?:相等|不低于|不小于)',line):
            if not re.fullmatch(r'(?:不采用|没有|无|不增加)[^，,]*(?:单调性|均值顺序|额外限制|额外约束)',line.strip()):
                return line
    return None


def _native(case, table, answer, proof, authority, binding):
    import pfn_pipeline as native
    from pfn_pipeline.identification_a4_shadow import declare_a4_source
    from .native_evidence import payload
    law=proof['assignment'];nodes=list(table.nodes);population=proof['population']
    ends=[list(map(int,s.split(','))) for s in proof['ordered_events']]
    common=dict(node_id=population[0],own_treatment_value=ends[0][0],exposure_value=ends[0][1],
        source='reviewed_business_source',evidence=binding,admitted=True,
        query_authority='TRUSTED_FIXTURE' if authority=='SYNTHETIC_TEST' else 'HUMAN_CONFIRMED',
        synthetic=authority=='SYNTHETIC_TEST',exposure_definition={
            'majority':'strict_majority','any':'any_treated_neighbor','count':'treated_neighbor_count'}[proof['exposure']])
    graph=dict(network_id=table.token,node_ids=nodes,undirected_edges=list(table.edges))
    if law['kind']=='independent':task=native.make_heterogeneous_bernoulli_arm_task(graph,propensities=law['p'],**common)
    elif law['kind']=='fixed':task=native.make_complete_randomization_arm_task(graph,m=law['quota'],**common)
    elif law['kind']=='stratified':task=native.make_two_group_quota_arm_task(graph,groups=law['groups'],treated_quotas=law['quotas'],**common)
    else:raise ValueError('LOCAL_TARGET_NATIVE_DESIGN_NOT_CONNECTED')
    batch=native.identify_randomized_network_batch(task)
    queries=answer['estimate_handoff']['queries'];coefficients=answer['estimate_handoff']['operator_spec']['forms'][0]
    cells=tuple((q['unit'],q['own'],q['exposure']) for q in queries)
    source=declare_a4_source(task,source_id='reviewed-local-population-means',operator='NODE_ARM_MEANS',
        provenance=binding,admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR',
        outcome_nodes=tuple(population),node_order=tuple(nodes),arm_cells=cells)
    terms=tuple(native.ArmLinearTerm(*cell,coef) for cell,coef in zip(cells,coefficients,strict=True))
    result=native.identify_verified_linear_target(batch,source,terms)
    native.replay_verified_composition(result)
    actual={t.coordinates:str(t.coefficient) for t in result.terms}
    expected={(q['unit'],q['own'],q['exposure']):str(Fraction(c)) for q,c in zip(queries,coefficients,strict=True)}
    if actual!=expected:raise ValueError('LOCAL_TARGET_NATIVE_COEFFICIENT_CHANGED')
    return dict(summary=result.summary(),evidence=payload(result),source_binding=binding)


def verify(case,draft,network,*,science_review=None,network_focus=False):
    from .direct_verification import bound_network
    from .uploaded_network_sources import from_materials
    from .uploaded_network_contrast import PREMISES
    table=bound_network(case,network)
    report=dict(version='direct-verification/25',draft=deepcopy(draft),draft_sha256=digest(draft),input_sha256=digest(case),
        network_manifest=table.manifest(),decision='RETAINED',effective_answer=deepcopy(draft),conditional_answer=None,
        proof=None,checks=[],clarification_questions=[],scientific_approval=False,estimation_handoff_allowed=False,
        production_admission=False,independent_replay=False,
        local_targets=dict(version=VERSION,state='READING_RECHECK_REQUIRED',parts=[]))
    if network_focus:report['network_focus']=True
    record=report['local_targets']
    try:
        partitions=scope.questions(case) or [dict(id='q1',question=case['business_question'],projected_question=case['business_question'],
                                                start=0,end=len(case['business_question']),shared='')]
        custom=scope.weights(case,list(table.nodes))
    except scope.ScopeGap as exc:
        if science_review is not None:raise ValueError('LOCAL_TARGET_SOURCE_CHANGED') from exc
        record.update(state='NEEDS_INPUT',message=str(exc));report['clarification_questions']=[str(exc)]
        return report
    record['weight_source']=custom
    extra=_unsupported_constraints(case)
    from .network_grounded_contrast import source_lines
    declarations=[r for r in source_lines(case) if r['source_id']!='uploaded_network']
    uncertain=[r for r in declarations if re.search(r'是否|尚未|未决定|不确定|待确认',r['quote']) and
               any(re.search(pattern,r['quote']) for _,pattern in PREMISES.values())]
    for partition in partitions:
        part=dict(partition,state='READING_RECHECK_REQUIRED',answer=None,proof=None)
        record['parts'].append(part)
        if extra:
            part.update(state='NOT_COVERED',message='原材料还包含本入口尚不能核验的限制，已保留：'+extra)
            continue
        if uncertain:
            part.update(state='NEEDS_INPUT',message='这项研究前提目前尚未决定，请说明采用、不采用或仍未决定：'+uncertain[0]['quote'])
            report['clarification_questions'].append(part['message']);continue
        if not custom and not any(re.search(r'(?:名单|评价对象).{0,12}(?:抽签|试点|处理|分配)前.{0,5}确定',r['quote']) for r in declarations):
            part.update(state='NEEDS_INPUT',message='本次评价名单是在处理前确定的，还是按是否使用、回访或结果选出的？')
            report['clarification_questions'].append(part['message']);continue
        projected=dict(case,business_question=partition['projected_question'])
        try:
            bound=from_materials(projected,table,extended=True,source_scope=True,
                                 evaluation_weights=custom['values'] if custom else None)
        except (ValueError,TypeError,KeyError,ArithmeticError):bound=None
        if not bound:
            part['message']='这问的比较或材料还不能完整对应现有入口，未改写目标。'
            continue
        if 'question' in bound:
            part.update(state='NEEDS_INPUT',message=bound['question']);report['clarification_questions'].append(bound['question'])
            continue
        result=bound['result'];answer=result['answer'];proof=result['proof']
        if answer['status']!='POINT':
            part.update(state=answer['status'],message=answer['reason'],answer=answer,proof=proof)
            report['clarification_questions'].extend(result.get('questions',[]));continue
        if len(bound['premises'])!=len(PREMISES):
            part.update(state='NEEDS_INPUT',message='本问的科学前提尚未完整声明。');report['clarification_questions'].append(part['message']);continue
        # The complete original, exact question projection and file weights all
        # belong to the review binding; local target selection is not a new study.
        part.update(state='REVIEW_REQUIRED',answer=answer,proof=proof,premises=bound['premises'])
    ready=[p for p in record['parts'] if p['state']=='REVIEW_REQUIRED']
    report['clarification_questions']=list(dict.fromkeys(report['clarification_questions']))
    if not ready:
        if science_review is not None:raise ValueError('LOCAL_TARGET_REVIEW_NO_LONGER_AVAILABLE')
        record['state']='NEEDS_INPUT' if report['clarification_questions'] else 'NOT_COVERED'
        record['message']='各问的结果分别列出；尚未生成整批识别证书。'
        return report
    items=[dict(code=code,label=label,quote='；'.join(dict.fromkeys(
        p['quote'] for item in ready for p in item['premises'] if p['code']==code))) for code,(label,_) in PREMISES.items()]
    sheet=dict(kind='network_local_targets',items=items,case_sha256=digest(case),draft_sha256=digest(draft),
               target_binding=digest(record))
    sheet['binding']=digest(sheet)
    report['condition_review']=sheet;record.update(state='REVIEW_REQUIRED',message='请确认材料中列出的共同前提。各问保留自己的名单、方向和权重。')
    if science_review is None:return report
    check_review(sheet,science_review);report['review_record']=deepcopy(science_review)
    if any(v!='ADOPTED' for v in science_review['decisions'].values()):return report
    for part in ready:
        try:
            native=_native(case,table,part['answer'],part['proof'],science_review['authority'],digest([sheet['binding'],part['id']]))
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
            part.update(state='NOT_COVERED',message='当前原生合同尚不能核验本问：'+str(exc));continue
        part.update(state='POINT',native=native,independent_replay=True)
    complete=all(p.get('independent_replay') for p in record['parts'])
    record.update(state='COMPLETED' if complete else 'INCOMPLETE',
                  message='全部问题已逐项核验。' if complete else '部分问题尚未完成核验；已完成结果与未完成原因逐问列出。')
    report.update(decision='CONDITIONAL_RESULT',independent_replay=complete,
                  scientific_approval=science_review['authority']=='EXTERNAL_RESEARCH_REVIEW')
    # Native source and certificates are attached per target, not a misleading
    # bundle-level POINT or implicit authorization for an estimation consumer.
    report['proof']=dict(binder=VERSION,case_sha256=digest(case),review_binding=sheet['binding'],
                        targets=[dict(id=p['id'],state=p['state'],native=p.get('native')) for p in record['parts']])
    return report
