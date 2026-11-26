"""Natural-material adapter for already implemented network policy methods.

No identification algebra lives here. Components are solved and replayed by
the native library before its finite-mixture constructor can receive them.
"""
from copy import deepcopy
from fractions import Fraction as F
from cfm_id_llm import network_existing_reading as reader
from cfm_id_llm.compact_study import digest
from . import joint_natural_entry as workflow
from .native_evidence import payload

FAMILIES=('NETWORK_FINITE_POLICY','NETWORK_OBSERVATIONAL_POLICY')
NAMES={'consistency':'实际结果对应实际完整安排','fixed_network':'使用处理前固定的网络',
    'finite_means':'所需平均结果存在且有限','randomization':'完整抽签安排与潜在结果独立',
    'full_vector_exchangeability':'在固定背景下，整个使用名单与潜在结果可比较',
    'mean_sufficiency':'所有完整安排的平均结果由本人和同伴状态决定',
    'first_stage_exclusion':'第一阶段方案不直接影响结果',
    'complete_bounded_model':'除所列信息、结果范围和条件外，本次没有其他限制'}
NATIVE={'consistency':'consistency','fixed_network':'fixed_pretreatment_network',
    'finite_means':'finite_conditional_first_moments','randomization':'full_vector_randomization',
    'full_vector_exchangeability':'full_vector_conditional_exchangeability',
    'first_stage_exclusion':'first_stage_profile_no_direct_outcome_effect'}


def native_stop_message(answer):
    if answer.reason_code=='OFF_SUPPORT_ALTERNATE_THEOREM':
        return '原安排不会产生本题的一份目标使用名单，当前直接政策公式不能用于它；已保留全部方案，未删除这一项或改算另一政策。这不是已证明不可识别。'
    return '已有方法未核准本题，具体检查记录已保留；这不等于已证明目标不可识别。'


def proposed(case,draft):
    return bool(workflow.route_hints(draft).intersection(FAMILIES))


def prepare(case,report,call):
    return workflow.prepare(case,report,call,reader_module=reader,planner=plan,gap_resolver=gaps)


def gaps(r):
    e=r['joint_entry']
    reason=e.get('reason_code')
    if reason in ('UNEXPRESSED_ADDITIONAL_RESTRICTION','UNDECIDED_RESTRICTION'):
        # A source audit may accept a data gap or a permissive model description
        # as an extra assumption. Reuse the bounded source-gap review, never
        # delete the declaration or reinterpret it as scientific permission.
        s=e['reading']
        gap=dict(candidate=s['remaining'],related_conditions=s['conditions'],
            unhandled_declarations=e.get('unhandled_declarations',[]),reason_code=reason,
            proposed_questions=r.get('clarification_questions',[]),
            instruction='核对是否确有额外限制或待决定的科学条件；专用字段已经表达的事实缺口、未使用的可选定义、单纯允许干扰的描述不能重复成为额外假设。误读须完整重读并重新审核，不能直接删除或批准。')
        if reason=='UNEXPRESSED_ADDITIONAL_RESTRICTION':gap['declaration_stop']=True
        return {'remaining':gap}
    if not r.get('clarification_questions'):return {}
    return {k:dict(candidate=e['reading'].get(k),reason_code=e.get('reason_code'),
        proposed_questions=r['clarification_questions']) for k in e.get('missing_fields',[])}


def plan(case,r):
    e=r['joint_entry'];s=e['reading'];family=s['family']['value'];e['operation']=family
    if family not in FAMILIES:return workflow.stop(r,'UNSUPPORTED','NETWORK_TARGET_NOT_CONNECTED','原问题不是本入口的完整政策均值，未改写原目标。')
    st=s['study']['value'];net=s['network']['value'];t=s['target']['value'];info=s['information']['value']
    required=['consistency','fixed_network','finite_means',
        'randomization' if family=='NETWORK_FINITE_POLICY' else 'full_vector_exchangeability']
    if family=='NETWORK_FINITE_POLICY' and s['design'] and s['design']['value'] and s['design']['value']['kind']=='two_stage_quota_mixture_binary_v2_7':
        required.append('first_stage_exclusion')
    cs={x['code']:x for x in s['conditions']}
    bounded=(family=='NETWORK_OBSERVATIONAL_POLICY' and st['outcome_kind']=='binary'
             and cs.get('full_vector_exchangeability',{}).get('status')=='NOT_ADOPTED')
    if bounded:required=['consistency','fixed_network','finite_means','complete_bounded_model']
    missing={}
    if not st['treatment'] or not st['outcome'] or not st['period'] or not st['fixed_background'] or st['outcome_kind']=='unknown':
        missing['study']='请说明处理含义、结果、评价时期，以及本题固定的处理前背景。'
    if not net['nodes'] or net['complete'] is not True or net['undirected'] is not True:
        missing['network']='关系表是否列全了本次对象之间的无向关系？'
    experimental=family=='NETWORK_FINITE_POLICY'
    if st['regime']=='UNKNOWN':missing['study']='过去怎样决定谁使用：抽签还是自行选择？'
    elif st['regime']!=('EXPERIMENTAL' if experimental else 'OBSERVATIONAL'):
        return workflow.stop(r,'UNSUPPORTED','ASSIGNMENT_REGIME_MISMATCH','原材料的安排产生方式与本入口不一致，未把观察资料改成随机试验。')
    if experimental and (not s['design'] or not s['design']['value']):missing['design']='过去试点怎样抽签，概率或名额是多少？'
    if not experimental and s['design'] and s['design']['value'] is not None:
        return workflow.stop(r,'UNSUPPORTED','OBSERVATIONAL_RANDOM_DESIGN_CONFLICT','观察性研究同时填写了实验抽签规则，需要重新核对安排的来源。')
    if t['quantity'] not in ('MEAN','DIFFERENCE'):return workflow.stop(r,'UNSUPPORTED','POLICY_FUNCTIONAL_NOT_CONNECTED','此入口核验完整政策的均值和两端均值差；未改写其他目标。')
    if t['quantity']=='MEAN' and t.get('reference_components'):raise ValueError('MEAN_HAS_UNDECLARED_SECOND_TARGET')
    if t['quantity']=='DIFFERENCE' and not t.get('reference_components'):missing['target']='第二端要比较哪份完整安排或哪些随机方案？'
    if not t['components'] or not t['weights']:
        missing['target']='请说明完整的使用方案、方案选择概率和参与平均的对象。'
    if info['availability']!='SYMBOLIC_POPULATION_OPERATOR' or info['same_scope'] is not True or info['complete'] is not True:
        missing['information']='现有资料覆盖哪些对象和安排，是总体信息还是有限样本？'
    operators=('NODE_FULL_LAW','FULL_JOINT_LAW','ASSIGNMENT_NODE_MEANS','NODE_SIGNATURE_MEANS') if experimental else ('OBSERVATIONAL_ASSIGNMENT_NODE_CONDITIONAL_MEANS',)
    if info['operator'] not in operators:
        if info['operator']=='UNKNOWN':missing['information']='现有资料提供哪些总体分布或条件平均数？'
        else:return workflow.stop(r,'UNSUPPORTED','POPULATION_OPERATOR_NOT_CONNECTED','已有总体信息的形式尚未接入本政策方法，未丢弃或改写资料。')
    if not experimental and not info['assignment_masses']:
        missing['information']='请提供完整使用名单的实际总体概率及对应条件均值的覆盖说明；边际使用比例不能代替联合分配律。'
    for code in required:
        if code=='complete_bounded_model' and code not in cs:
            missing['conditions']='除已列的资料、二元结果定义和采用条件外，本题还有其他限制吗？不确定也可以注明。'
            continue
        if code not in cs:raise ValueError('REQUIRED_CONDITION_READING_OMITTED:'+code)
        if cs[code]['status'] in ('NOT_ADOPTED','CONTRADICTED'):
            return workflow.stop(r,'UNSUPPORTED','REQUIRED_PREMISE_NOT_ADOPTED','本研究不采用所需前提：'+NAMES[code]+'；未替你批准。')
        if cs[code]['status']!='ADOPTED':missing['conditions']='本次是否采用以下前提：'+'；'.join(NAMES[k] for k in required if cs.get(k,{}).get('status')!='ADOPTED')+'？'
    optional=cs.get('mean_sufficiency')
    # An unused standard premise left UNKNOWN is not a new scientific claim.
    # Keep it in the reading, but do not turn a questionnaire slot into a user
    # obligation. Explicit pending/declined/adopted claims keep their meaning;
    # unknown restrictions in remaining are still asked about.
    extras=[c for c in s['conditions'] if c['code'] not in required and c['code']!='mean_sufficiency'
        and not (c['status']=='UNKNOWN' and c['code'] in NAMES)]+s['remaining']
    if optional and optional['status']=='CONTRADICTED':extras.append(optional)
    # A pending optional premise does not restrict the model. Full-assignment
    # identification can run without it; the signature-only branch below asks
    # for it when needed. Keep the source declaration unchanged in all cases.
    if experimental and info['operator']=='NODE_SIGNATURE_MEANS' and (not optional or optional['status']!='ADOPTED'):
        if optional and optional['status']=='NOT_ADOPTED':
            return workflow.stop(r,'UNSUPPORTED','SIGNATURE_SUFFICIENCY_NOT_ADOPTED',
                '本题只有按本人和同伴状态汇总的总体均值，但明确不采用相应的均值充分性；不能据此外推完整政策，未替你采用该前提。')
        missing['conditions']='仅有本人和同伴状态的汇总均值。本次是否采用：对同一个对象，所有完整安排下本人状态和同伴状态相同，其平均结果也相同？'
    if any(c['status'] in ('UNDECIDED','UNKNOWN') for c in extras):
        return workflow.stop(r,'NEEDS_INPUT','UNDECIDED_RESTRICTION','还有尚未决定的条件，已保留。',
            ['这项条件本次采用、不采用还是尚未决定？ '+c['statement'] for c in extras if c['status'] in ('UNDECIDED','UNKNOWN')])
    blocked=[c for c in extras if c['status'] in ('ADOPTED','CONTRADICTED')]
    if blocked:
        e['unhandled_declarations']=deepcopy(blocked)
        return workflow.stop(r,'UNSUPPORTED','UNEXPRESSED_ADDITIONAL_RESTRICTION',
            '读取结果中以下声明尚未接入本政策方法：'+'；'.join(c['statement'] for c in blocked[:3])+
            '。原声明已保留，未忽略它们继续计算；可在读取记录中核对是否与原文含义一致。')
    if missing:
        e['missing_fields']=list(missing)
        return workflow.stop(r,'NEEDS_INPUT','NETWORK_INFORMATION_REQUIRED','有具体研究信息需要核对。',list(missing.values()))
    nodes=set(net['nodes'])
    if len(nodes)!=len(net['nodes']) or any(len(edge)!=2 or not set(edge)<=nodes or edge[0]==edge[1] for edge in net['edges']):raise ValueError('INVALID_NETWORK_ROSTER_OR_EDGES')
    if set(t['weights'])!=nodes or any(F(v)<0 for v in t['weights'].values()) or sum(map(F,t['weights'].values()))!=1:raise ValueError('COMPLETE_NORMALIZED_TARGET_WEIGHTS_REQUIRED')
    def assignment(z):
        if set(z)!=nodes or any(type(a) is not int or a not in (0,1) for a in z.values()):raise ValueError('COMPLETE_BINARY_POLICY_REQUIRED')
    sides=[t['components']]+([t['reference_components']] if t['quantity']=='DIFFERENCE' else [])
    for side in sides:
        for c in side:assignment(c['assignment'])
        if len(side)>1 or side[0]['probability'] is not None:
            if any(c['probability'] is None or F(c['probability'])<=0 for c in side):raise ValueError('FINITE_POLICY_PROBABILITIES_REQUIRED')
            if sum(F(c['probability']) for c in side)!=1:raise ValueError('FINITE_POLICY_PROBABILITIES_NOT_NORMALIZED')
            if t['distribution_complete'] is not True:raise ValueError('FINITE_POLICY_DISTRIBUTION_COMPLETENESS_REQUIRED')
    if experimental:
        if info['assignment_masses']:raise ValueError('UNUSED_OBSERVATIONAL_LAW')
    else:
        for row in info['assignment_masses']:assignment(row['assignment'])
        if any(F(row['probability'])<=0 for row in info['assignment_masses']) or sum(F(row['probability']) for row in info['assignment_masses'])!=1:raise ValueError('COMPLETE_OBSERVATIONAL_LAW_REQUIRED')
        if info['assignment_cells']:
            # Some readers repeat the same conditional-mean scope here.
            # Accept only an exact duplicate of the already audited law,
            # never extra or missing cells; retain both source-bound fields.
            def key(z):return tuple(z[n] for n in net['nodes'])
            for z in info['assignment_cells']:assignment(z)
            cells=[key(z) for z in info['assignment_cells']]
            if len(cells)!=len(set(cells)) or set(cells)!={key(row['assignment']) for row in info['assignment_masses']}:
                raise ValueError('OBSERVATIONAL_MEAN_SCOPE_DISAGREES_WITH_LAW')
    for cell in info['assignment_cells']:assignment(cell)
    if not set(info['outcome_nodes'])<=nodes:raise ValueError('OUTCOME_NODES_NOT_IN_STUDY')
    signature_cells=info.get('signature_cells',[])
    if info['operator']=='NODE_SIGNATURE_MEANS':
        cells=[(c['node'],c['own'],c['exposure']) for c in signature_cells]
        if not cells or len(cells)!=len(set(cells)) or not {c[0] for c in cells}<=set(info['outcome_nodes']):
            raise ValueError('EXPLICIT_SIGNATURE_MEAN_COVERAGE_REQUIRED')
        if info['assignment_cells']:raise ValueError('SIGNATURE_MEANS_HAVE_ASSIGNMENT_CELLS')
    elif signature_cells:raise ValueError('SIGNATURE_CELLS_REQUIRE_SIGNATURE_OPERATOR')
    if optional and optional['status']=='ADOPTED':
        if bounded:
            return workflow.stop(r,'UNSUPPORTED','BOUNDED_EXPOSURE_RESTRICTION_NOT_PROJECTED',
                '已保留采用的均值充分性。当前观察性界限转换尚不能一起表达它，未忽略此条件求界。')
        if not s['exposure'] or s['exposure']['value']['grouping'] in ('OTHER','UNKNOWN'):
            e['missing_fields']=['exposure'];return workflow.stop(r,'NEEDS_INPUT','NETWORK_INFORMATION_REQUIRED','均值充分性的同伴状态尚未明确。',['本次均值充分性采用哪种同伴状态？'])
        scope=(s.get('mean_sufficiency_scope') or {}).get('value')
        if not scope or scope['scope']=='UNKNOWN':
            e['missing_fields']=['mean_sufficiency_scope']
            return workflow.stop(r,'NEEDS_INPUT','SUFFICIENCY_SCOPE_REQUIRED','这项假设的适用范围尚未明确。',
                ['相同本人和同伴状态对应相同平均结果，这项假设适用于哪些对象？是所有可能的使用名单，还是仅列出的几份？'])
        covered=scope['covered_nodes']
        if len(set(covered))!=len(covered) or not set(covered)<=nodes:raise ValueError('INVALID_SUFFICIENCY_NODE_SCOPE')
        for z in scope['assignments']:assignment(z)
        if scope['scope']=='ALL_BINARY_ASSIGNMENTS' and scope['assignments']:raise ValueError('CONFLICTING_SUFFICIENCY_ASSIGNMENT_SCOPE')
        if scope['scope']!='ALL_BINARY_ASSIGNMENTS':
            return workflow.stop(r,'UNSUPPORTED','SUFFICIENCY_ASSIGNMENT_SCOPE_NOT_CONNECTED',
                '本次假设只覆盖所列使用名单；现有签名政策方法要求覆盖所有可能名单，未扩大原假设。')
        from .method_preparation import signature_scope_covers_target
        target_nodes=[n for n in net['nodes'] if F(t['weights'][n])>0]
        if not signature_scope_covers_target(scope['scope'],covered,target_nodes):
            e['uncovered_nodes']=[n for n in target_nodes if n not in covered]
            return workflow.stop(r,'UNSUPPORTED','SUFFICIENCY_NODE_COVERAGE_INCOMPLETE',
                '该假设未覆盖本题参与平均的对象：'+'、'.join(e['uncovered_nodes'])+'。未将其他对象的假设扩大到这些对象。')
        required.append('mean_sufficiency')
    e['required_conditions']=required
    if bounded:
        from .observational_policy_bounds import plan_validated
        return plan_validated(case,r)
    items=[dict(code='target',label='本次问题与方案概率',quote=t['description']),
        dict(code='information',label='资料覆盖与实际安排',quote='；'.join(x['quote'] for x in s['information']['evidence']))]
    items += [dict(code=k,label=NAMES[k],quote=cs[k]['statement']) for k in required]
    sheet=dict(kind='joint_natural',items=items,case_sha256=digest(case),reading_binding=reader.binding(case,s),draft_sha256=r['draft_sha256'])
    sheet['binding']=digest([sheet.copy(),e['audit']]);r['condition_review']=sheet
    return workflow.stop(r,'REVIEW_REQUIRED',None,'原文与资料已核对。请确认本次问题及所列科学前提。')


def _execute(s,review):
    from pfn_pipeline import identification_business as core
    from pfn_pipeline._internal.identification.schemas import Assumption
    from pfn_pipeline.network_inquiry_shadow import declare_network_study,fixed_policy_target_from_context,declare_network_a4_source
    st=s['study']['value'];net=s['network']['value'];t=s['target']['value'];info=s['information']['value']
    experimental=s['family']['value']=='NETWORK_FINITE_POLICY';nodes=tuple(net['nodes']);cs={c['code']:c for c in s['conditions']}
    provenance='source audited and explicitly confirmed; review='+review['binding']
    study=declare_network_study(network_id='source_'+digest(net),node_order=nodes,
        undirected_edges=tuple(tuple(e) for e in net['edges']),treatment_variable=st['treatment'],
        outcome_variable=st['outcome'],outcome_kind='continuous' if st['outcome_kind']=='count' else st['outcome_kind'],
        context_reference=st['fixed_background']+'；时期：'+st['period'],observation_regime='experimental' if experimental else 'observational',
        assignment_design=s['design']['value'] if experimental else None,protocol_provenance=provenance,
        network_provenance=provenance,graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    def assumption(code):
        return Assumption(name=NATIVE.get(code,code),source='human_confirmation' if review['authority']=='EXTERNAL_RESEARCH_REVIEW' else 'demo_specification',confirmed=True,status='ADMITTED',
            evidence=[provenance,cs[code]['statement'],*[x['quote'] for x in cs[code]['evidence']]])
    required=['consistency','fixed_network','finite_means','randomization' if experimental else 'full_vector_exchangeability']
    assumptions=tuple(assumption(k) for k in required)
    if experimental:
        assumptions+=(Assumption(name='known_assignment_law',source='human_confirmation' if review['authority']=='EXTERNAL_RESEARCH_REVIEW' else 'demo_specification',confirmed=True,status='ADMITTED',evidence=[provenance,*[x['quote'] for x in s['design']['evidence']]]),)
        if s['design']['value']['kind']=='two_stage_quota_mixture_binary_v2_7':assumptions+=(assumption('first_stage_exclusion'),)
    def target(component):
        return fixed_policy_target_from_context(study,tuple(component['assignment'][n] for n in nodes),
            unit_weights=tuple(t['weights'][n] for n in nodes),authority='HUMAN_CONFIRMED' if review['authority']=='EXTERNAL_RESEARCH_REVIEW' else 'TRUSTED_FIXTURE')
    common=dict(source_id='source_'+digest(info),provenance=provenance,admission='ADMITTED',
        availability=info['availability'],outcome_nodes=tuple(info['outcome_nodes']))
    inputs=[];attempts=[]
    def solve(q):
        before=digest(payload(q));answer=core.identify_network_business_query(q)
        if digest(payload(q))!=before:raise ValueError('NATIVE_INPUT_MUTATED')
        if answer.status=='POINT' and not core.replay_verified_business_outcome(answer):raise ValueError('NATIVE_REPLAY_FAILED')
        inputs.append(payload(q));attempts.append(answer.summary());return answer
    signature=sufficiency=None
    if cs.get('mean_sufficiency',{}).get('status')=='ADOPTED':
        from pfn_pipeline.identification_policy_r2 import declare_policy_signature,admit_mean_signature_sufficiency
        signature=declare_policy_signature(study,**s['exposure']['value'])
        declaration=Assumption(name='mean_signature_sufficiency',source='human_confirmation' if review['authority']=='EXTERNAL_RESEARCH_REVIEW' else 'demo_specification',confirmed=True,status='ADMITTED',evidence=[provenance,cs['mean_sufficiency']['statement']])
        scope=s['mean_sufficiency_scope']['value']
        from .method_preparation import signature_scope_covers_target
        if (not signature_scope_covers_target(scope['scope'],scope['covered_nodes'],[n for n in nodes if F(t['weights'][n])>0])
                or not set(scope['covered_nodes'])<=set(nodes)):
            raise ValueError('SUFFICIENCY_SCOPE_NOT_ESTABLISHED')
        sufficiency=admit_mean_signature_sufficiency(study,signature,covered_nodes=tuple(scope['covered_nodes']),assumption=declaration)
    if experimental:
        sources=()
        if info['operator']!='NODE_SIGNATURE_MEANS':
            sources=(declare_network_a4_source(study,**common,operator=info['operator'],
                assignment_cells=tuple(tuple(z[n] for n in nodes) for z in info['assignment_cells'])),)
        signature_sources=()
        if signature is not None and info['operator'] in ('NODE_SIGNATURE_MEANS','NODE_FULL_LAW','FULL_JOINT_LAW'):
            from pfn_pipeline.identification_policy_r2 import declare_signature_population_source
            signature_sources=(declare_signature_population_source(study,signature,**common,operator=info['operator'],
                signature_cells=tuple((c['node'],c['own'],c['exposure']) for c in info.get('signature_cells',[]))),)
        components=[]
        for component in t['components']:
            q=core.FixedPolicyInquiryV21(study,target(component),assumptions,sources,signature,sufficiency,signature_sources);answer=solve(q)
            if answer.status!='POINT':return answer,inputs,attempts
            r=answer.result
            expected_sources=q.r2_sources if answer.route=='R2_MEAN_SIGNATURE' else q.r1b_sources
            if r.study!=q.study or r.target!=q.target or r.sources!=expected_sources or r.assumptions!=q.assumptions:raise ValueError('COMPONENT_INPUT_MISMATCH')
            components.append(r)
        if len(components)==1:return answer,inputs,attempts
        q=core.FinitePolicyInquiryV21(tuple(components),tuple(c['probability'] for c in t['components']))
    else:
        from pfn_pipeline.identification_observational_r3 import declare_observational_population_v23
        source=declare_observational_population_v23(study,**common,
            assignment_masses=tuple((tuple(row['assignment'][n] for n in nodes),row['probability']) for row in info['assignment_masses']))
        q=core.ObservationalPolicyInquiryV23(study,target(t['components'][0]),source,assumptions,signature,sufficiency)
    answer=solve(q)
    if answer.status=='POINT' and experimental:
        expected=sorted((tuple(v.target.policy_assignment),F(p)) for v,p in zip(q.components,q.policy_probabilities))
        actual=sorted((tuple(v.target.policy_assignment),F(p)) for v,p in zip(answer.result.components,answer.result.policy_probabilities))
        if expected!=actual:raise ValueError('FINITE_POLICY_INPUT_MISMATCH')
    if answer.status=='POINT' and not experimental:
        for key in ('study','target','source','assumptions'):
            if getattr(answer.result,key)!=getattr(q,key):raise ValueError('OBSERVATIONAL_INPUT_MISMATCH:'+key)
    return answer,inputs,attempts


def complete(case,report,review):
    e=report['joint_entry']
    if e['case_sha256']!=digest(case) or report['draft_sha256']!=digest(report['draft']):raise ValueError('NETWORK_SOURCE_CHANGED')
    s=reader.inspect(case,e['reading']);a=reader.check_audit(case,s,e['audit'])
    if any(f['verdict']!='MATCH' for f in a['findings']):raise ValueError('NETWORK_SOURCE_NOT_REVIEWED')
    r=plan(case,workflow.base(report,case,s,a));current=r['joint_entry']
    if r.get('condition_review')!=report.get('condition_review'):raise ValueError('NETWORK_REVIEW_CHANGED')
    if workflow.record_review_decisions(r,review):return r
    t=s['target']['value'];signature_used=any(c['code']=='mean_sufficiency' and c['status']=='ADOPTED' for c in s['conditions'])
    composition=t['quantity']=='DIFFERENCE' or ((s['family']['value']=='NETWORK_OBSERVATIONAL_POLICY' or signature_used) and len(t['components'])>1)
    if composition:
        components=[];coefficients=[];attempts=[];failure=None
        sides=[('1',t['components'])]+([('-1',t['reference_components'])] if t['quantity']=='DIFFERENCE' else [])
        for sign,side in sides:
            groups=[(sign,side)] if s['family']['value']=='NETWORK_FINITE_POLICY' and not signature_used else [(str(F(sign)*F(c['probability'] or '1')),[dict(c,probability=None)]) for c in side]
            for coef,group in groups:
                child=deepcopy(s);child['target']['value'].update(quantity='MEAN',components=group,reference_components=None)
                answer,inputs,trace=_execute(child,review);attempts.extend(trace)
                if answer.status!='POINT':failure=answer;continue
                components.append(dict(kind='EXISTING_NETWORK_POLICY',operation=current['operation'],target=child['target']['value'],
                    study=s['study']['value'],native_inputs=inputs,native_outcome=payload(answer),identified_functional=answer.result.identified_functional))
                coefficients.append(coef)
        verified=failure is None
        certificate=dict(kind='EXISTING_NETWORK_POLICY_COMPOSITION',operation=current['operation'],target=t,study=s['study']['value'],
            components=components,coefficients=coefficients,
            identified_functional=' + '.join('('+v+') * ('+c['identified_functional']+')' for v,c in zip(coefficients,components)) if verified else None)
        status='POINT' if verified else failure.status;reason=None if verified else failure.reason_code
        summary=dict(status=status,components=len(components),coefficients=coefficients)
    else:
        answer,inputs,attempts=_execute(s,review);verified=answer.status=='POINT';summary=answer.summary();status=answer.status;reason=answer.reason_code
        certificate=dict(kind='EXISTING_NETWORK_POLICY',operation=current['operation'],
            target=s['target']['value'],study=s['study']['value'],native_inputs=inputs,native_outcome=payload(answer),
            identified_functional=getattr(answer.result,'identified_functional',None) if verified else None)
    current.update(completed=True,state=status,reason_code=reason,candidate_findings=attempts,
        native_result=dict(state=status,certificate=certificate,summary=summary,independent_replay=verified),
        message='识别库已按本题目标计算，并独立核验证书。' if verified else native_stop_message(failure if composition else answer))
    for key in ('attempts','audit_repairs','gap_reviews'):current[key]=deepcopy(e.get(key,[]))
    r.update(review_record=deepcopy(review),backend_called=True,independent_replay=verified,
        decision='CONDITIONAL_RESULT' if verified else 'WITHHELD')
    if verified:r['proof']=dict(method=current['operation'],binder=workflow.VERSION,certificate=certificate,
        source_binding=reader.binding(case,s),review_binding=review['binding'])
    return r
