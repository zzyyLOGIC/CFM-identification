"""Reviewed D1-D6/E1-E5 local effects -> existing local-mean composition and replay.

The target averages complete assignments under q conditional on each local
arm. It is neither a fixed-policy effect nor a sufficiency-licensed exposure
intervention. Native mathematics and the explicit synthetic review stay intact.
"""
from .method_compat import canonical_id, native_id
from copy import deepcopy
from fractions import Fraction
from .business_dispatch import (sha, worksheet, checked_review, DispatchReview,
    DispatchError, empty_result, PLAN_DECISIONS)
from cfm_id_llm import network_effect_reading as reading
from cfm_id_llm import network_effect_conditioning as conditioning
from .native_evidence import payload as _native_payload
from . import local_methods, local_execution
from . import network_design_adapter as design_adapter
from . import research_spec_local_adapters as local_attributes
from cfm_id_llm import network_design_reading as design_fields
from cfm_id_llm import assumption_choices

FAMILY = 'NETWORK_RANDOMIZED_EFFECT_FACTS'
METHOD = 'network.randomized.local_contrast'
TARGET_KINDS = ('DIRECT_EFFECT', 'SPILLOVER_EFFECT', 'LOCAL_TOTAL_EFFECT')
READING_DECISIONS = ('local_states_and_first_minus_second_direction',
    'evaluation_population_fixed_before_assignment_and_weights',
    'remaining_assignments_follow_original_conditional_design',
    'native_symbols_match_business_variables_and_context', 'all_information_and_restrictions_preserved', 'source_entailment')
SCIENCE_DECISIONS = ('known_assignment_law', 'full_vector_randomization', 'consistency',
    'fixed_pretreatment_network', 'finite_conditional_first_moments', 'a4_operator_scope_and_provenance')
# The local target averages the remaining assignments under the original conditional design;
# it does not use exposure mean sufficiency. Keep this adapter contract public.
ASSUMPTION_REQUIREMENTS = frozenset(SCIENCE_DECISIONS)
SCIENCE_LABELS = {
    design_fields.D6_CONDITION: '最终完整处理名单相同时，第一阶段配额方案不再直接影响结果',
    'assignment_outcome_independence': '给定本次背景，完整处理安排与潜在结果独立',
    'consistency': '实际观察结果对应实际完整安排下的潜在结果',
    'finite_conditional_means': '本次所需的总体条件均值存在且有限',
}


def canonical_model(plan):
    from cfm_id_llm.owned_effect_reading import CanonicalReading, VERSION
    from cfm_id_llm.scoped_effect_reading import VERSION as SCOPED_VERSION
    return CanonicalReading if plan.get('effect_fact_contract') in (VERSION,SCOPED_VERSION) or plan.get('evidence_dependencies',{}).get('version')==VERSION else reading.NetworkEffectReading


def target_coordinates(c):
    return local_attributes.reading_coordinates(c, local_attributes.from_reading(c))


def inspect_methods(entry, raw, *, note_review=None):
    out = dict(empty_result(),query_id=entry['query_id'],result_scope='SELECTED_QUERY_ONLY',
        remaining_query_ids=deepcopy(entry['remaining_query_ids']),fact_family=FAMILY,
        request_sha256=entry['request_sha256'],query_review=deepcopy(entry['query_review']),
        methods=[],exclusions=[],method_matching='NOT_CHECKED_BEFORE_SCIENCE_REVIEW')
    try:
        from cfm_id_llm.fact_reading_contracts import contract_for_entry
        contract=contract_for_entry(entry)
        if contract is None or contract.reader_id!=FAMILY:
            raise ValueError('LOCAL_EFFECT_READING_CONTRACT_REQUIRED')
        decoded=contract.parse_candidate(entry,raw)
        if 'target_kind_origin' in decoded:
            decoded['target_kind_origin'].update(query_id=entry['query_id'],intake_sha256=entry['intake_sha256'],
                query_review_sha256=sha(entry['query_review']),
                reviewed_target=deepcopy(entry['selected_query']['target']))
        c=canonical_model(entry).model_validate(decoded['facts']);t=c.target
        out.update(decoded,reading_candidate=deepcopy(raw),bundle=deepcopy(entry['bundle']))
        missing,unsupported=[],[]
        choices = assumption_choices.applicability(c.assumption_choices, required_conditions=ASSUMPTION_REQUIREMENTS)
        out['assumption_choices_review'] = dict(method=METHOD, required_conditions=sorted(ASSUMPTION_REQUIREMENTS),
            **deepcopy(choices), scientific_approval=False)
        missing += choices['missing']; unsupported += choices['blocked']
        if t.kind in TARGET_KINDS and t.kind!=entry['selected_query']['target']['kind']:
            return dict(out,state='READING_RECHECK_REQUIRED',reason_code='EFFECT_TARGET_DISAGREES_WITH_REVIEWED_QUERY')
        assignment_question = design_adapter.assignment_availability_question(c.design_facts.assignment_rule_available)
        if assignment_question: missing.append(assignment_question)
        for label,condition in [('处理前固定网络',c.design_facts.network_fixed_before_treatment),
                ('评价名单在抽签前固定',t.population_fixed_before_assignment),
                ('两端结果定义、期间和背景相同',t.shared_outcome_and_context)]:
            if condition.value is None:
                missing.append(reading.population_contract.QUESTION if condition is t.population_fixed_before_assignment
                               else '请核对原文是否明确：'+label+'。')
            elif condition.value is False: unsupported.append('DECLARED_EFFECT_SCOPE_EXCLUDES:'+label)
        for name,condition in c.scientific_statements:
            if condition.status=='CONFLICTING':
                return dict(out,state='READING_RECHECK_REQUIRED',reason_code='CONFLICTING_EFFECT_SCIENCE_STATEMENTS')
            if condition.status in ('NOT_STATED','UNDECIDED'):
                missing.append('本次计算需要以下条件，请说明是否采用：“'+SCIENCE_LABELS[name]+'”。不知道或尚未决定也可以说明。')
            elif condition.status=='NOT_ADOPTED': unsupported.append('DECLARED_MODEL_EXCLUDES:'+name)
        if c.additional_restrictions: unsupported.append('ADDITIONAL_EFFECT_MODEL_REQUIRES_SEPARATE_ADAPTER')
        if c.study.graph_kind=='OTHER' or c.study.outcome_kind=='OTHER': unsupported.append('EFFECT_STUDY_SCOPE_NOT_CONNECTED')
        if c.assignment.kind=='OTHER': unsupported.append('EFFECT_ASSIGNMENT_NOT_CONNECTED')
        gaps, exclusions=design_adapter.component_gaps(c,local_effect=True)
        if 'CONFLICTING_FIRST_STAGE_EXCLUSION' in exclusions:
            return dict(out,state='READING_RECHECK_REQUIRED',reason_code='CONFLICTING_FIRST_STAGE_EXCLUSION')
        missing += ['请补充原文中的设计或暴露字段：'+field for field in gaps]
        unsupported += exclusions
        if c.exposure.kind in ('OTHER','NONE'): unsupported.append('EFFECT_EXPOSURE_NOT_CONNECTED')
        if t.kind=='OTHER' or t.operation=='OTHER' or t.aggregation=='OTHER' or t.remaining_assignment=='OTHER':
            unsupported.append('TARGET_OUTSIDE_DESIGN_STANDARDIZED_LOCAL_CONTRAST')
        if not c.study.nodes: missing.append('请提供完整研究对象名单，包括没有关系或没有结果记录的对象。')
        if c.study.graph_kind=='UNKNOWN': missing.append('对象之间的关系是否有方向？例如，甲联系乙是否也表示乙联系甲？')
        if c.study.edge_list_complete is not True:
            missing.append('关系表已声明只列出一部分。请补充本次研究范围内遗漏的关系；当前方法需要完整关系。'
                           if c.study.edge_list_complete is False else
                           '上传的关系表是否列出了本次研究范围内的全部关系？未列出的对象对是否确定没有这种联系？')
        if c.study.outcome_kind=='UNKNOWN': missing.append('关注的结果是二元状态、次数，还是连续数值？请说明结果的取值含义。')
        for name,label in [('treatment','启用与未启用各指什么，以及数据中的取值编码'),
                           ('outcome','要比较的结果指标及其含义'),('context','这项结果对应的时期，以及是否限定共同背景')]:
            if not getattr(c.study,name) or not getattr(c.study,name).strip(): missing.append('请说明'+label+'。')
        if c.assignment.kind=='INDEPENDENT_BERNOULLI' and (c.assignment.probabilities is None or set(c.assignment.probabilities)!=set(c.study.nodes)):
            missing.append('请说明原试点是否逐对象独立抽签，以及每个对象的已知概率。')
        if c.exposure.kind=='UNKNOWN' or not c.exposure.source_ids:
            missing.append('请明确同伴分组定义；不能仅凭受到同事影响而选择分组规则。')
        if t.kind=='UNKNOWN' or t.operation=='UNKNOWN' or any(x is None for arm in (t.first,t.second) for x in (arm.own,arm.exposure)):
            missing.append('请明确比较两端的自身处理、同伴状态及相减方向。')
        if not t.population or t.aggregation=='UNKNOWN': missing.append('请明确评价全体、指定子集还是单个对象，以及汇总方式。')
        if t.aggregation=='SINGLE' and t.population and len(t.population)!=1:
            return dict(out,state='READING_RECHECK_REQUIRED',reason_code='SINGLE_AGGREGATION_REQUIRES_ONE_NODE')
        if t.remaining_assignment=='UNKNOWN' or not t.remaining_source_ids:
            missing.append('在满足两端条件的安排中，其余对象按原试点抽签概率平均，还是另有固定安排？请核对目标原文。')
        if not all((c.study.source_ids,c.assignment.source_ids,t.source_ids,t.first.source_ids,t.second.source_ids)):
            missing.append('研究结构、原设计、比较方向和两端状态均须有各自的原文来源。')
        out.update(clarification_questions=list(dict.fromkeys(missing)),unsupported_reasons=unsupported)
        if c.additional_restrictions:
            out['processing_explanation'] = '读取结果保留了以下额外声明，当前方法尚未处理其含义：' + '；'.join(n.text for n in c.additional_restrictions)
        elif choices['blocked']:
            out['processing_explanation'] = '材料还声明了已采用、拟采用、被断言不成立或相互冲突的假设；本路线不能忽略这些模型声明。'
        elif any(code.startswith('DECLARED_MODEL_EXCLUDES:') for code in unsupported):
            names=[SCIENCE_LABELS[code.split(':',1)[1]] for code in unsupported if code.startswith('DECLARED_MODEL_EXCLUDES:')]
            out['processing_explanation']='本次明确不采用“'+'；'.join(names)+'”。当前方法需要这些条件，因此没有执行识别；这不是不可识别证明。'
        if unsupported: return dict(out,state='ADAPTER_NOT_CONNECTED',reason_code=unsupported[0])
        if missing: return dict(out,state='NEEDS_INPUT',reason_code='NETWORK_EFFECT_FACTS_INCOMPLETE')
        a,e=t.first.own,t.first.exposure;b,f=t.second.own,t.second.exposure
        if (t.kind=='DIRECT_EFFECT' and not (a!=b and e==f)) or (
                t.kind=='SPILLOVER_EFFECT' and not (a==b and e!=f)) or (
                t.kind=='LOCAL_TOTAL_EFFECT' and not (a!=b and e!=f)):
            return dict(out,state='READING_RECHECK_REQUIRED',reason_code='LOCAL_CONTRAST_DOES_NOT_MATCH_EFFECT_KIND',
                clarification_questions=['请核对效应名称、两端条件和相减方向；系统不会交换两端或补齐基准。'])
        if not c.information or all(s.operator=='FINITE_SAMPLE' or s.availability=='FINITE_SAMPLE' for s in c.information):
            return dict(out,state='NEEDS_INPUT',reason_code='POPULATION_INFORMATION_NOT_DECLARED',
                clarification_questions=['请说明理论识别可以使用的总体观测信息及覆盖范围；有限样本不能代替。'])
        if any(s.operator=='UNKNOWN' or s.availability=='UNKNOWN' for s in c.information):
            return dict(out,state='NEEDS_INPUT',reason_code='POPULATION_INFORMATION_SCOPE_UNRESOLVED')
        if any(s.operator=='OTHER' or s.availability=='EXACT_POPULATION_VALUE' for s in c.information):
            return dict(out,state='ADAPTER_NOT_CONNECTED',reason_code='EFFECT_INFORMATION_OPERATOR_NOT_CONNECTED')
        required={(n,x.own,x.exposure) for n in t.population for x in (t.first,t.second)}
        eligible=[];joint_scope=set()
        for i,s in enumerate(c.information):
            if s.availability!='SYMBOLIC_POPULATION_OPERATOR' or s.operator=='FINITE_SAMPLE': continue
            if not s.source_ids or not s.outcome_nodes:
                return dict(out,state='NEEDS_INPUT',reason_code='POPULATION_SOURCE_SCOPE_OR_PROVENANCE_MISSING')
            if s.operator=='FULL_JOINT_LAW' and set(s.outcome_nodes)!=set(c.study.nodes):
                return dict(out,state='READING_RECHECK_REQUIRED',reason_code='FULL_JOINT_LAW_REQUIRES_FULL_OUTCOME_SCOPE')
            scope=({(x.node,x.own,x.exposure) for x in s.arm_cells} if s.operator=='NODE_ARM_MEANS' else
                {(n,x.own,x.exposure) for n in s.outcome_nodes for x in (t.first,t.second)})
            joint_scope.update(scope)
            if required<=scope: eligible.append(i)
        if not eligible:
            if required<=joint_scope:
                return dict(out,state='ADAPTER_NOT_CONNECTED',reason_code='EFFECT_MULTI_SOURCE_JOINT_ADAPTER_REQUIRED')
            return dict(out,state='NEEDS_INPUT',reason_code='NO_SINGLE_SOURCE_COVERS_EFFECT_ARMS',
                clarification_questions=['请核对总体来源是否覆盖评价名单的两端状态；多来源联合适配尚未接入，不能补造未声明格子。'])
        from .reading_note_review import inspect_notes
        notes=inspect_notes(entry,raw,[n.model_dump() for n in c.unresolved],reading.documents(entry['bundle']),note_review)
        if notes['worksheet'] is not None:
            out.update(note_review_worksheet=notes['worksheet'],note_review_receipt=notes['receipt'],
                reading_notes=deepcopy(decoded['facts']['unresolved']),reading_recheck_notes=notes['reading_recheck_notes'])
        if notes['state'] not in ('NO_NOTES','NOTES_RELEASED_FOR_CHECKS'):
            return dict(out,state=notes['state'],reason_code=notes['reason_code'],clarification_questions=notes['clarification_questions'])
        if notes['review'] is not None: entry=dict(entry,reading_note_review=deepcopy(notes['review']))
        target=target_coordinates(c)
        reading_decisions = READING_DECISIONS
        context = entry.get('reviewed_target_context')
        if conditioning.has_explicit_context(context):
            out['target_conditioning_review'] = conditioning.review_item(context, c.study)
            reading_decisions = (*READING_DECISIONS, *conditioning.DECISIONS)
        binding=sha(dict(entry=entry,raw=raw,target=target,source_index=eligible[0]))
        row=dict(method=METHOD,source_index=eligible[0],applicability='NOT_CHECKED_BEFORE_SCIENCE_REVIEW',
            reading_worksheet=worksheet(binding,reading_decisions),science_worksheet=worksheet(binding,(*SCIENCE_DECISIONS,*design_adapter.extra_science(c))))
        binding=sha(dict(entry=entry,raw=raw,methods=[row],target=target))
        return dict(out,state='REVIEW_REQUIRED',proposed_target=target,methods=[row],plan_sha256=binding,
            plan_worksheet=worksheet(binding,PLAN_DECISIONS))
    except DispatchError as exc: return dict(out,state=exc.state,reason_code=exc.reason)
    except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError):
        return dict(out,state='CHECK_BLOCKED',reason_code='INVALID_SOURCE_BOUND_EFFECT_READING')


def native_reviews_from_json(plan, records):
    if type(records) is not dict or set(records)!={METHOD}: raise ValueError('EXACT_EFFECT_REVIEW_REQUIRED')
    pair=records[METHOD]
    if type(pair) is not dict or set(pair)!={'reading_review','science_review'}: raise ValueError('EXACT_REVIEW_PAIR_REQUIRED')
    return {METHOD:{k:DispatchReview.model_validate(v.model_dump(mode='json') if type(v) is DispatchReview else v)
        for k,v in pair.items()}}


def _compile(plan, row, records):
    from pfn_pipeline.identification_a4_shadow import declare_a4_source
    from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec
    c=canonical_model(plan).model_validate(plan['facts']);t=c.target;s=c.information[row['source_index']]
    question=local_attributes.from_reading(c)
    local_methods.resolve(row['method'], question.operation)
    local_attributes.require_reading_coordinates(c,question,plan['proposed_target'])
    net=NetworkExposureSpec(network_id='effect_'+sha(dict(study=c.study.model_dump(),context=c.study.context)),
        node_ids=list(question.study.node_order),undirected_edges=c.study.edges)
    evidence=records['science_review'].evidence+'; review='+sha(records['science_review'].model_dump(mode='json'))
    authority=records['science_review'].authority
    task=design_adapter.make_arm(c,net,
        source='Reviewed original source locators: '+','.join(s.source_ids), evidence=evidence,
        authority=authority, local_question=question)
    source=declare_a4_source(task,source_id='reviewed_effect_source_'+str(row['source_index']),operator=s.operator,
        provenance='Reviewed original source locators: '+','.join(s.source_ids),admission='ADMITTED',
        availability=s.availability,regime='experimental',outcome_nodes=tuple(s.outcome_nodes),node_order=tuple(c.study.nodes),
        arm_cells=tuple((v.node,v.own,v.exposure) for v in s.arm_cells))
    request=local_attributes.native_request(question,authority=authority,
        cohort_evidence='Reviewed fixed evaluation population: '+','.join(t.population_fixed_before_assignment.source_ids))
    return task,source,request


def _execute_reverse_linear(plan,out,batch,source,terms,original):
    """Bind the reviewed target to unchanged native linear proof and replay APIs."""
    from pfn_pipeline import identification_composition as native
    method=local_methods.resolve(plan['methods'][0]['method'], local_methods.DIFFERENCE)
    c=canonical_model(plan).model_validate(plan['facts']);t=c.target
    matching_exposure=(t.first.exposure==t.second.exposure if t.kind=='DIRECT_EFFECT'
                       else t.kind=='LOCAL_TOTAL_EFFECT' and t.first.exposure!=t.second.exposure)
    if not (t.kind in ('DIRECT_EFFECT','LOCAL_TOTAL_EFFECT') and t.first.own==0 and t.second.own==1 and
            matching_exposure and target_coordinates(c)==plan['proposed_target']):
        raise ValueError('REVERSED_LOCAL_EFFECT_TARGET_REQUIRED')
    expected={(n,arm.own,arm.exposure):sign*Fraction(1,len(t.population))
        for n in t.population for arm,sign in ((t.first,1),(t.second,-1))}
    actual={term.coordinates:term.coefficient for term in terms}
    if len(terms)!=len(expected) or actual!=expected:
        raise ValueError('EFFECT_LINEAR_INPUT_TARGET_MISMATCH')
    before=sha(_native_payload([batch,source,terms]))
    try:
        proof=method.linear(batch,source,terms)
    except native.CompositionUnavailable as exc:
        if sha(_native_payload([batch,source,terms]))!=before:
            raise ValueError('EFFECT_NATIVE_INPUT_MUTATED') from exc
        if exc.reason_code=='ZERO_ARM_SUPPORT':
            return dict(out,state='UNSUPPORTED',reason_code=exc.reason_code,partial_fallback_performed=False)
        raise
    if sha(_native_payload([batch,source,terms]))!=before:
        raise ValueError('EFFECT_NATIVE_INPUT_MUTATED')
    if (type(proof) is not native.VerifiedCompositionV18 or
        sha(_native_payload([proof.source_batch,proof.a4_source,proof.recipe.supplied_terms]))!=before or
        proof.recipe.kind!='CUSTOM_LINEAR' or len(proof.terms)!=len(expected) or
        {term.coordinates:term.coefficient for term in proof.terms}!=expected):
        raise ValueError('EFFECT_RETURNED_INPUT_MISMATCH')
    before_replay=sha(_native_payload(proof))
    replay=method.replay_linear(proof)
    if (type(replay) is not native.VerifiedCompositionV18 or
        sha(_native_payload(proof))!=before_replay or sha(_native_payload(replay))!=before_replay):
        raise ValueError('EFFECT_INDEPENDENT_REPLAY_FAILED')
    out['attempts'].append(dict(stage='LINEAR_COMPOSITION',state=proof.status,reason_code=None))
    claim=dict(kind='POINT',representation='DESIGN_STANDARDIZED_EFFECT_OBSERVED_FUNCTIONAL',
        target=deepcopy(plan['proposed_target']),target_fingerprint=proof.target_fingerprint,
        expression=proof.identified_functional,numeric_value=None)
    # Presentation envelope only: the enclosed certificate is the actual native
    # single linear certificate, not a forged named-effect bundle certificate.
    certificate=dict(contract_version='network-local-effect-linear-evidence-1',
        status=proof.status,verification_status=proof.verification_status,results=[proof.summary()])
    answer=dict(method=METHOD,mathematical_claim=claim,certificate=certificate,independent_replay=True,
        reviewed_input_sha256=original,native_evidence=_native_payload(proof))
    return dict(out,state='POINT',primary_method=METHOD,mathematical_claim=deepcopy(claim),
        certificate=deepcopy(certificate),independent_replay=True,answers=[answer],partial_fallback_performed=False)


def _execute_plan(plan, *, plan_review=None, native_reviews=None, research_protocol_selected=False):
    out=dict(empty_result(),query_id=plan['query_id'],remaining_query_ids=plan['remaining_query_ids'],
        result_scope='SELECTED_QUERY_ONLY',fact_family=FAMILY,plan_sha256=plan['plan_sha256'],attempts=[])
    if 'assumption_choices_review' in plan:
        out['assumption_choices_review'] = deepcopy(plan['assumption_choices_review'])
    if 'target_conditioning_review' in plan:
        out['target_conditioning_review'] = deepcopy(plan['target_conditioning_review'])
    try:
        if research_protocol_selected is not True: raise DispatchError('REVIEW_REQUIRED','EXPLICIT_RESEARCH_PROTOCOL_SELECTION_REQUIRED')
        review=checked_review(plan_review,plan['plan_worksheet'])
        if review.authority!=plan['query_review']['authority']: raise ValueError('EFFECT_REVIEW_AUTHORITY_MISMATCH')
        if review.authority=='EXTERNAL_RESEARCH_REVIEW':
            facts=canonical_model(plan).model_validate(plan['facts'])
            if (facts.assignment.kind!='INDEPENDENT_BERNOULLI'
                    or facts.exposure.kind!='STRICT_MAJORITY_TIES_LOW'):
                raise DispatchError('ADAPTER_NOT_CONNECTED','EXTERNAL_EFFECT_DESIGN_NOT_CONNECTED')
        if native_reviews is None: raise DispatchError('REVIEW_REQUIRED','EFFECT_READING_AND_SCIENCE_REVIEWS_REQUIRED')
        if len(plan['methods'])!=1 or plan['methods'][0]['method']!=METHOD: raise ValueError('EXACT_EFFECT_METHOD_REQUIRED')
        row=plan['methods'][0];pair=native_reviews_from_json(plan,native_reviews)[METHOD]
        for key,sheet in (('reading_review','reading_worksheet'),('science_review','science_worksheet')):
            pair[key]=checked_review(pair[key],row[sheet])
            if pair[key].authority!=review.authority: raise ValueError('EFFECT_REVIEW_AUTHORITY_MISMATCH')
        if review.authority=='EXTERNAL_RESEARCH_REVIEW':
            # The existing native batch constructor declares every node-arm.
            # Do not widen a real source that only covers the selected contrast.
            source=facts.information[row['source_index']]
            complete_nodes=set(source.outcome_nodes)==set(facts.study.nodes)
            complete_cells={(n,a,s) for n in facts.study.nodes for a in (0,1) for s in (0,1)}
            supplied_cells={(v.node,v.own,v.exposure) for v in source.arm_cells}
            if (not complete_nodes or (source.operator=='NODE_ARM_MEANS' and
                    not complete_cells<=supplied_cells)):
                raise DispatchError('ADAPTER_NOT_CONNECTED','EXTERNAL_EFFECT_FULL_BATCH_INFORMATION_REQUIRED')
        task,source,request=_compile(plan,row,pair)
        original=sha(_native_payload([task,source,request]))
        from pfn_pipeline import identification_business as core
        out['backend_called']=True
        anchor,_=local_execution.identify(row['method'],local_methods.DIFFERENCE,core.ArmInquiryV21(task))
        if sha(_native_payload([task,source,request]))!=original: raise ValueError('EFFECT_NATIVE_INPUT_MUTATED')
        out['attempts'].append(dict(stage='ANCHOR',state=anchor.status,reason_code=anchor.reason_code))
        if anchor.status!='POINT':
            return dict(out,state=anchor.status,reason_code=anchor.reason_code,partial_fallback_performed=False)
        batch=local_execution.arm_batch(row['method'],task)
        if plan['proposed_target']['kind'] in ('DIRECT_EFFECT','LOCAL_TOTAL_EFFECT') and plan['proposed_target']['first'][0]==0:
            return _execute_reverse_linear(plan,out,batch,source,request,original)
        inquiry=core.EffectsInquiryV21(batch,source,(request,))
        result,before=local_execution.identify(row['method'],local_methods.DIFFERENCE,inquiry)
        out['attempts'].append(dict(stage='COMPOSITION',state=result.status,reason_code=result.reason_code))
        if result.status!='POINT': return dict(out,state=result.status,reason_code=result.reason_code,partial_fallback_performed=False)
        proof=result.result
        if (result.route!=native_id(METHOD) or result.query_type!='EFFECT_BUNDLE' or
                sha(_native_payload([proof.source_batch,proof.a4_source,proof.requests]))!=
                sha(_native_payload([inquiry.batch,inquiry.a4_source,inquiry.requests]))):
            raise ValueError('EFFECT_RETURNED_INPUT_MISMATCH')
        local_execution.replay_outcome(row['method'],local_methods.DIFFERENCE,result,
            inquiry=inquiry,input_digest=before)
        if len(proof.results)!=1 or proof.verification_status!='VERIFIED': raise ValueError('EXACT_VERIFIED_EFFECT_REQUIRED')
        effect=proof.results[0]
        claim=dict(kind='POINT',representation='DESIGN_STANDARDIZED_EFFECT_OBSERVED_FUNCTIONAL',
            target=deepcopy(plan['proposed_target']),target_fingerprint=effect.target_fingerprint,
            expression=effect.identified_functional,numeric_value=None)
        certificate=proof.summary()
        answer=dict(method=METHOD,mathematical_claim=claim,certificate=certificate,independent_replay=True,
            reviewed_input_sha256=original,native_evidence=_native_payload(result))
        return dict(out,state='POINT',primary_method=METHOD,mathematical_claim=deepcopy(claim),certificate=deepcopy(certificate),
            independent_replay=True,answers=[answer],partial_fallback_performed=False)
    except DispatchError as exc: return dict(out,state=exc.state,reason_code=exc.reason)
    except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError):
        return dict(out,state='CHECK_BLOCKED',reason_code='INVALID_EFFECT_REVIEW_OR_NATIVE_EVIDENCE')
