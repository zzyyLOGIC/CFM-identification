"""Audited per-question scopes -> unchanged native local linear composition.

No extraction result is a permission. Shared facts are bound once; each target
keeps its roster, coefficients, source coverage and independently replayed proof.
"""
from copy import deepcopy
from fractions import Fraction as F
from cfm_id_llm import local_bundle_reading as reader
from cfm_id_llm.compact_study import digest
from . import joint_natural_entry as flow
from .native_evidence import payload

FAMILY = reader.FAMILY
NAMES = dict(randomization='完整抽签安排与潜在结果独立', consistency='实际结果对应实际完整安排',
    fixed_network='关系在处理前固定', finite_means='所需平均结果存在且有限',
    first_stage_exclusion='第一阶段名额方案不另外影响结果')


def condition_scope(records,needed,*,code=None,target_index=None):
    """Use only explicitly adopted complete scopes, without extending them."""
    relevant=[c for c in records if (not c['covered_nodes'] or needed.intersection(c['covered_nodes']))
        and not (c.get('local_scope')=='TARGET_EVENT_MEANS' and c.get('target_indices')
                 and target_index not in c['target_indices'])]
    if any(c['status'] in ('NOT_ADOPTED','CONTRADICTED') for c in relevant):
        return 'UNSUPPORTED','本次不采用或存在冲突，未用另一条采用记录覆盖这一选择。'
    if records and not relevant:
        return 'UNSUPPORTED','已声明范围未覆盖本问对象，未扩大假设。'
    if not records or any(c['status'] in ('UNKNOWN','UNDECIDED') for c in relevant):
        return 'NEEDS_INPUT','请说明本问所需对象是否采用此项前提。可回答采用、不采用或尚未决定。'
    def covers(c):
        if c['all_assignments'] is True:return True
        scope=c.get('local_scope')
        if code=='consistency' and scope=='OBSERVED_CONSISTENCY':return True
        if code=='fixed_network' and scope=='FIXED_PRETREATMENT_NETWORK':return True
        return (code=='finite_means' and scope=='TARGET_EVENT_MEANS'
                and target_index is not None and target_index in (c.get('target_indices') or []))
    adopted=set().union(*(set(c['covered_nodes']) for c in relevant
        if c['status']=='ADOPTED' and covers(c)))
    if needed<=adopted:return 'READY',None
    if any(not c['covered_nodes'] or c['all_assignments'] is None for c in relevant):
        return 'NEEDS_INPUT','请说明这项前提适用于哪些对象和安排。'
    return 'UNSUPPORTED','已声明范围未覆盖本问所需对象和完整安排，未扩大假设。'


def check_weight_table(case,claim):
    """Check cited tabular numbers independently; prose meaning stays audited."""
    from .network_target_scope import weight_sources,table_rows
    cited={x['source_id'].split('#L')[0] for x in claim['evidence']}
    tables=[x for x in weight_sources(case) if x['source_id'] in cited]
    if not tables:return
    if len(tables)!=1:raise ValueError('LOCAL_MULTIPLE_WEIGHT_TABLES_FOR_ONE_TARGET')
    rows=table_rows(tables[0]['text']);header=rows.pop(0)
    ni=header.index('node_id' if 'node_id' in header else '对象编号');wi=1-ni
    if len(header)!=2 or any(len(r)!=2 for r in rows):raise ValueError('LOCAL_WEIGHT_TABLE_SHAPE')
    expected={}
    for row in rows:
        n=row[ni].strip()
        if n in expected:raise ValueError('LOCAL_DUPLICATE_WEIGHT_ROW')
        expected[n]=F(row[wi].strip())
    t=claim['value']
    if t['weights'] is None:return  # The source gap review, not auto-fill, resolves omissions.
    actual={n:F(w) for n,w in t['weights'].items()}
    if ({n:w for n,w in expected.items() if w}!={n:w for n,w in actual.items() if w}
            or any(n not in expected for n in actual)):
        raise ValueError('LOCAL_WEIGHTS_DIFFER_FROM_CITED_TABLE')


def prepare(case, report, call):
    report=deepcopy(report)
    report.pop('local_targets',None)
    return flow.prepare(case, report, call, reader_module=reader, planner=plan, gap_resolver=gaps,
                        diagnose_stop=diagnose_sample_stop)


def diagnose_sample_stop(case, report):
    e=report['joint_entry']; infos=e['reading']['information']
    if not infos or not all(x['value']['availability']=='FINITE_SAMPLE' for x in infos):return None
    # Never bypass an unresolved information/coverage finding. An unrelated
    # question about design cannot turn this sample into a population source.
    if any(f['verdict']!='MATCH' and (f['field'].startswith('information') or f['field']=='coverage')
           for f in e['audit']['findings']):return None
    r=plan(case,report)
    return r if r['joint_entry'].get('reason_code')=='LOCAL_SAMPLE_ONLY_INFORMATION' else None


def gaps(r):
    e = r['joint_entry']
    if e.get('reason_code')=='LOCAL_ADDITIONAL_RESTRICTIONS':
        # Reuse the established bounded source-gap review for declarations
        # mistakenly duplicated from target/data fields. A genuine additional
        # restriction remains stopped; only a fresh read and audit can repair
        # a misclassification. No text matching or automatic deletion.
        return dict(remaining=dict(candidate=e['reading'],
            unhandled_declarations=e['unhandled_declarations'],
            reason_code=e['reason_code'],declaration_stop=True,proposed_questions=[],
            instruction='核对是否确有额外科学限制，还是目标定义、原设计条件平均或资料说明被重复填入。误填须按原文完整重读并重新审核；真实限制必须保留，不能直接删除、改为不采用或批准。'))
    return {k:dict(candidate=e['reading'], reason_code=e.get('reason_code'),
        proposed_questions=r.get('clarification_questions', [])) for k in e.get('missing_fields', [])}


def plan(case, r):
    # Older deterministic projections are not authoritative for this audited
    # input contract. Preserve the original draft, not their inferred scopes.
    r.pop('local_targets', None)
    e = r['joint_entry']; s = e['reading']; e['operation'] = FAMILY
    if s['family']['value'] != FAMILY:
        return flow.stop(r, 'UNSUPPORTED', 'LOCAL_BUNDLE_SCOPE', '原问题不属于本入口的同一研究局部均值或比较，未改写问题。')
    st=s['study']['value']; net=s['network']['value']; nodes=net['nodes']
    d=s['design']['value']; ex=s['exposure']['value']; missing={}
    if r.get('network_manifest'):
        from .direct_verification import bound_network
        table=bound_network(case,r['network_manifest'])
        if set(nodes)!=set(table.nodes) or {frozenset(x) for x in net['edges']}!={frozenset(x) for x in table.edges}:
            raise ValueError('LOCAL_NETWORK_DIFFERS_FROM_UPLOADED_ROSTER_OR_EDGES')
    if len(set(nodes)) != len(nodes): raise ValueError('DUPLICATE_NETWORK_NODES')
    if any(len(x)!=2 or x[0]==x[1] or not set(x)<=set(nodes) for x in net['edges']):
        raise ValueError('INVALID_NETWORK_EDGE')
    if not nodes or net['complete'] is not True or net['undirected'] is not True:
        missing['network']='请说明完整研究名单和关系表是否齐全、关系是否为双方关系。'
    if st['regime'] == 'OBSERVATIONAL':
        return flow.stop(r,'UNSUPPORTED','OBSERVATIONAL_BUNDLE_NOT_CONNECTED','这批问题来自观察性研究；当前多问题入口只复用随机试验的局部方法，未替你采用随机化。')
    if st['regime'] == 'UNKNOWN' or d is None:
        missing['design']='当时怎样决定哪些对象使用？请说明抽签方式及概率或名额。'
    if not all(st[k] for k in ('treatment','outcome','period','fixed_background')) or st['outcome_kind']=='unknown':
        missing['study']='请明确处理含义、结果指标、时期及本次共同背景。'
    if ex['grouping'] in ('UNKNOWN','OTHER'):
        missing['exposure']='同伴状态按哪些关系计算、怎样分组？请说明。'
    active=[c for c in s['remaining'] if c['status']!='NOT_ADOPTED']
    extra=[c for c in s['conditions'] if c['code'] not in NAMES and c['status'] not in ('NOT_ADOPTED','UNKNOWN')]
    if active or extra:
        e['unhandled_declarations']=active+extra
        return flow.stop(r,'UNSUPPORTED','LOCAL_ADDITIONAL_RESTRICTIONS',
            '本入口尚不能联合核验这些声明：'+'；'.join(c['statement'] for c in active+extra)+'。声明已保留，未删去后继续计算。')
    required=['randomization','consistency','fixed_network','finite_means']
    if d and d['kind']=='two_stage_quota_mixture_binary_v2_7': required.append('first_stage_exclusion')
    cs={k:[c for c in s['conditions'] if c['code']==k] for k in required}
    parts=[]
    for i,claim in enumerate(s['targets']):
        check_weight_table(case,claim)
        t=claim['value']; p=dict(id=f'q{i+1}',question=t['question'],target=deepcopy(t),state='READY')
        parts.append(p)
        def part_stop(state,message):p.update(state=state,message=message)
        # New source reviews preserve unresolved arm components. A known
        # post-treatment selection already rules this method out; do not ask
        # for irrelevant missing components or obscure it under generic OTHER.
        # Historical reports keep their original diagnostic for replay.
        if t['fixed_before_assignment'] is False and e['audit'].get('local_target_event_version'):
            part_stop('UNSUPPORTED','这问按处理后的信息选择对象或权重，当前处理前固定目标的方法不适用。');continue
        if t['kind']=='OTHER' or t['remaining_assignment']=='OTHER' or t['same_outcome_and_context'] is False:
            part_stop('UNSUPPORTED','这问不属于相同结果、时期和原设计下的局部比较，未改写为其他目标。');continue
        if t['fixed_before_assignment'] is False:
            part_stop('UNSUPPORTED','这问按处理后的信息选择对象或权重，当前处理前固定目标的方法不适用。');continue
        if t['kind']=='UNKNOWN' or not t['first'] or (t['kind']=='CONTRAST' and not t['second']):
            missing[f'targets.{i}']='第'+str(i+1)+'问具体比较哪两种本人和同伴状态？';part_stop('NEEDS_INPUT',missing[f'targets.{i}']);continue
        if t['kind']=='MEAN' and t['second'] is not None:raise ValueError('MEAN_HAS_SECOND_ARM')
        pop=t['population']; weights=t['weights']
        if (not pop or weights is None or t['fixed_before_assignment'] is None
                or t['remaining_assignment']=='UNKNOWN' or t['same_outcome_and_context'] is None):
            absent=[]
            if not pop:absent.append('评价哪些对象')
            if weights is None:absent.append('这些对象等权还是按明确权重平均')
            if t['fixed_before_assignment'] is None:absent.append('名单和权重是否在处理前确定')
            if t['remaining_assignment']=='UNKNOWN':absent.append('其余对象是否按原抽签规则在对应条件下平均')
            if t['same_outcome_and_context'] is None:absent.append('是否使用共同的结果和时期')
            message='第'+str(i+1)+'问请说明：'+'；'.join(absent)+'。'
            missing[f'targets.{i}']=message;part_stop('NEEDS_INPUT',message);continue
        if len(set(pop))!=len(pop) or not set(pop)<=set(nodes) or set(weights)!=set(pop):
            raise ValueError('LOCAL_POPULATION_WEIGHT_KEYS:'+str(i+1))
        if any(F(v)<0 for v in weights.values()) or sum(map(F,weights.values()))!=1:
            # This is an invalid source specification, never a normalization.
            missing[f'targets.{i}']='第'+str(i+1)+'问的评价权重需要非负且合计1，请核对原表；系统未自动调整。'
            part_stop('NEEDS_INPUT',missing[f'targets.{i}']);continue
        scope_checks=[]
        for k in required:
            need=set(nodes) if k in ('randomization','fixed_network','first_stage_exclusion') else {n for n in pop if F(weights[n])}
            state,reason=condition_scope(cs[k],need,code=k,target_index=i)
            if state!='READY':
                message=('“'+NAMES[k]+'”的已声明范围未覆盖本问所需对象和完整安排，未扩大假设。'
                    if reason.startswith('已声明范围') else '“'+NAMES[k]+'”：'+reason)
                scope_checks.append((k,state,message))
        unsupported=[x for x in scope_checks if x[1]=='UNSUPPORTED']
        if unsupported:
            part_stop('UNSUPPORTED',unsupported[0][2])
        else:
            for k,state,message in scope_checks:
                missing[f'targets.{i}.conditions.{k}']=message
                part_stop(state,message)
    e.update(parts=parts,required_conditions=required)
    infos=[x['value'] for x in s['information']]
    if not infos:missing['information']='本次能使用哪些总体资料，覆盖哪些对象和状态？只有样本也请直接说明。'
    if infos and all(x['availability']=='FINITE_SAMPLE' for x in infos):
        # This admission contract requires declared population operators.
        # A known lack of them cannot be cured by reconfirming the design,
        # weights or scientific premises. Do not call it nonidentification.
        for p in parts:
            if p['state'] in ('READY','NEEDS_INPUT'):
                p.update(state='UNSUPPORTED',message='材料只有有限样本，本入口尚不能据此核验所需总体信息；未把样本升级为总体。')
        return flow.stop(r,'UNSUPPORTED','LOCAL_SAMPLE_ONLY_INFORMATION',
            '材料已明确只有样本。本入口的总体资料合同尚未满足，不需重复确认已说明的条件；这不是数学不可识别的证明。')
    if missing:
        e['missing_fields']=list(missing)
        return flow.stop(r,'NEEDS_INPUT','LOCAL_INPUT_REQUIRED','有具体缺项，其他问题及资料均已保留。',list(missing.values()))
    if not any(p['state']=='READY' for p in parts):
        return flow.stop(r,'UNSUPPORTED','LOCAL_TARGETS_OUTSIDE_SCOPE','各问的适用边界已分别列出，未生成识别结论。')
    items=[dict(code='targets',label='各问的对象、权重和比较方向',quote='；'.join(p['question'] for p in parts)),
           dict(code='information',label='资料来源与覆盖',quote='；'.join(x['quote'] for c in s['information'] for x in c['evidence']))]
    items += [dict(code=k,label=NAMES[k],quote='；'.join(
        c['statement'] for c in cs[k] if c['status']=='ADOPTED')) for k in required]
    sheet=dict(kind='joint_natural',items=items,case_sha256=digest(case),reading_binding=reader.binding(case,s),draft_sha256=r['draft_sha256'])
    sheet['binding']=digest([sheet.copy(),e['audit']]);r['condition_review']=sheet
    return flow.stop(r,'REVIEW_REQUIRED',None,'各问的对象和权重已分别核对；请确认本次采用的研究前提。')


def native_task(s,t,review):
    from pfn_pipeline import identification as native
    from .research_spec_catalog import DESIGN_PROTOCOLS
    d=deepcopy(s['design']['value']);kind=d.pop('kind');net=s['network']['value'];ex=s['exposure']['value']
    protocol=next(p for p in DESIGN_PROTOCOLS if p.native_kind==kind)
    graph=dict(network_id='source-local-'+digest(s['network']),node_ids=net['nodes'],undirected_edges=net['edges'])
    args=dict(node_id=next(n for n in t['population'] if F(t['weights'][n])),
        own_treatment_value=t['first']['own'],exposure_value=t['first']['exposure'],
        source='reviewed_business_source',evidence=review['binding'],admitted=True,
        synthetic=review['authority']=='SYNTHETIC_TEST',
        query_authority='TRUSTED_FIXTURE' if review['authority']=='SYNTHETIC_TEST' else 'HUMAN_CONFIRMED',
        outcome_kind='continuous' if s['study']['value']['outcome_kind']=='count' else s['study']['value']['outcome_kind'],
        exposure_definition='strict_majority' if ex['grouping']=='strict_majority_ties_low' else ex['grouping'],
        core_collaborators=ex['core_collaborators'])
    if kind in ('unequal_probability_fixed_quota_binary_v1','rerandomized_balanced_binary_v1'):
        args['design']=s['design']['value']
    else:
        args.update(d)
        if kind=='two_stage_quota_mixture_binary_v2_7':args['profile_exclusion_admitted']=True
    return getattr(native,protocol.constructor)(graph,**args)


def solve(s,t,review):
    from pfn_pipeline.identification_batch import identify_randomized_network_batch
    from pfn_pipeline.identification_a4_shadow import declare_a4_source
    from pfn_pipeline.identification_composition import ArmLinearTerm,identify_verified_linear_target,replay_verified_composition
    if review['authority']=='EXTERNAL_RESEARCH_REVIEW':
        if (s['design']['value']['kind']!='heterogeneous_bernoulli_binary_v1'
                or s['exposure']['value']['grouping']!='strict_majority_ties_low'):
            return dict(state='UNSUPPORTED',reason_code='EXTERNAL_EFFECT_DESIGN_NOT_CONNECTED',
                message='已保留真实研究确认；当前真实研究合同尚未开放这项设计与暴露组合。')
    task=native_task(s,t,review)
    batch=identify_randomized_network_batch(task)
    terms=[ArmLinearTerm(n,a['own'],a['exposure'],str(sign*F(w)))
           for n,w in t['weights'].items() if F(w)
           for a,sign in [(t['first'],1)]+([(t['second'],-1)] if t['second'] else [])]
    failures=[]
    for index,claim in enumerate(s['information']):
        info=claim['value']
        if info['availability']!='SYMBOLIC_POPULATION_OPERATOR' or info['same_scope'] is not True:
            failures.append('资料'+str(index+1)+'不是同一研究的总体信息');continue
        if info['operator'] not in ('NODE_ARM_MEANS','NODE_FULL_LAW','FULL_JOINT_LAW'):
            failures.append('资料'+str(index+1)+'的算子暂未接入');continue
        if review['authority']=='EXTERNAL_RESEARCH_REVIEW':
            nodes=set(s['network']['value']['nodes'])
            full={(n,a,b) for n in nodes for a in (0,1) for b in (0,1)}
            if set(info['outcome_nodes'])!=nodes or (info['operator']=='NODE_ARM_MEANS' and not full<={(c['node'],c['own'],c['exposure']) for c in info['arm_cells']}):
                failures.append('EXTERNAL_EFFECT_FULL_BATCH_INFORMATION_REQUIRED');continue
        source=declare_a4_source(task,source_id='reviewed-local-source-'+str(index),operator=info['operator'],
            provenance=digest(claim),admission='ADMITTED',availability=info['availability'],
            outcome_nodes=tuple(info['outcome_nodes']),node_order=tuple(s['network']['value']['nodes']),
            arm_cells=tuple((c['node'],c['own'],c['exposure']) for c in info['arm_cells']))
        try:
            result=identify_verified_linear_target(batch,source,tuple(terms))
            replay_verified_composition(result)
        except (ValueError,TypeError) as exc:
            failures.append(str(exc));continue
        expected={}
        for term in terms:expected[term.coordinates]=expected.get(term.coordinates,F(0))+term.coefficient
        expected={k:v for k,v in expected.items() if v}
        if {x.coordinates:x.coefficient for x in result.terms}!=expected:raise ValueError('LOCAL_NATIVE_TARGET_CHANGED')
        return dict(state='POINT',summary=result.summary(),native_evidence=payload(result),source_index=index,independent_replay=True)
    return dict(state='UNSUPPORTED',reason_code='LOCAL_INFORMATION_COVERAGE',message='现有总体资料尚不能覆盖本问所需状态；未用样本或其他问的证书替代。',details=failures)


def complete(case,report,review):
    e=report['joint_entry']
    if e['case_sha256']!=digest(case) or report['draft_sha256']!=digest(report['draft']):raise ValueError('LOCAL_SOURCE_CHANGED')
    s=reader.inspect(case,e['reading']);a=reader.check_audit(case,s,e['audit'])
    if any(f['verdict']!='MATCH' for f in a['findings']):raise ValueError('LOCAL_SOURCE_NOT_REVIEWED')
    r=plan(case,flow.base(report,case,s,a));current=r['joint_entry']
    if r.get('condition_review')!=report.get('condition_review'):raise ValueError('LOCAL_REVIEW_CHANGED')
    if flow.record_review_decisions(r,review):return r
    for p in current['parts']:
        if p['state']!='READY':continue
        try:p.update(solve(s,p['target'],review))
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
            p.update(state='UNSUPPORTED',reason_code='LOCAL_NATIVE_REJECTED',message='原方法未核准本问，未换问题或删除对象。',details=[str(exc)])
    complete=all(p['state']=='POINT' for p in current['parts'])
    current.update(completed=True,state='BUNDLE_COMPLETE' if complete else 'BUNDLE_INCOMPLETE',
        message='各问已分别核验。' if complete else '各问的结果和未完成原因分别列出。',
        native_result=dict(parts=deepcopy(current['parts']),independent_replay=complete))
    r.update(review_record=deepcopy(review),backend_called=True,independent_replay=complete,decision='CONDITIONAL_RESULT')
    r['proof']=dict(binder=flow.VERSION,method=FAMILY,source_binding=reader.binding(case,s),
        review_binding=review['binding'],parts=deepcopy(current['parts']))
    return r
