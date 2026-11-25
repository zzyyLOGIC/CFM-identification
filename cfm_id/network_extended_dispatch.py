"""Reviewed adapters for five existing native routes; no identification algebra.

All scientific admission follows source review and version-bound worksheets.
No native producer, support calculator or independent replayer is changed.
"""
from .method_compat import canonical_id, native_id
from copy import deepcopy
from fractions import Fraction
from functools import partial
from .business_dispatch import sha,worksheet,checked_review,DispatchError,empty_result,PLAN_DECISIONS
from .network_policy_dispatch import native_reviews_from_json,BASE_CONDITIONS
from .native_evidence import payload as _native_payload
from . import local_methods, local_execution, observational_methods, native_outcome_execution
from . import finite_policy_methods
from . import network_design_adapter as design
from . import research_spec_observational_adapters as observed_attributes
from cfm_id_llm import network_extended_reading as reading

ARM='network.randomized.local_mean';MIX=finite_policy_methods.METHOD
P=observational_methods.OBSERVED_EFFECT;B=observational_methods.STRATIFIED_EFFECT;X=observational_methods.NODEWISE_EFFECT
METHODS={reading.ARM:(ARM,),reading.MIX:(MIX,),reading.OBS:(P,B,X)}
AVG=observational_methods.effect_routes()
BASIC=('consistency','fixed_pretreatment_network','finite_conditional_first_moments')
SCIENCE_NAMES={
 'known_assignment_law':'过去试点的完整抽签规则已知',
 'full_vector_randomization':'完整抽签名单与各对象在不同安排下的潜在结果独立',
 'consistency':'实际观察结果对应实际执行的完整安排',
 'fixed_pretreatment_network':'关系网络在处理前已经确定，并在本次研究中保持固定',
 'finite_conditional_first_moments':'所需的条件平均结果存在且有限',
 'full_vector_conditional_exchangeability':'在相同处理前背景下，完整使用名单与各对象不同安排下的潜在结果独立',
 'potential_outcome_exposure_sufficiency':'对评价对象，自己的处理和所定义的同伴状态足以决定每种完整安排下的结果',
 'exposure_level_conditional_exchangeability':'控制附件中的共同处理前分层后，本人与同伴的实际状态不会进一步反映各状态下的潜在平均结果',
 'local_covariate_exposure_mean_exchangeability':'控制本人和邻居的指定处理前特征后，本人与同伴的实际状态不会进一步反映各状态下的潜在平均结果',
}
SCIENCE={P:(*BASIC,'full_vector_conditional_exchangeability'),
 B:(*BASIC,'potential_outcome_exposure_sufficiency','exposure_level_conditional_exchangeability'),
 X:(*BASIC,'potential_outcome_exposure_sufficiency','local_covariate_exposure_mean_exchangeability')}
READING_DECISIONS=('target_coordinates_direction_and_averaging','evaluation_population_and_timing',
 'network_variables_period_and_fixed_background','all_information_and_restrictions_preserved','source_entailment')

def reviewed_observation_period(entry,decoded,study):
    """Recover an already reviewed outcome period without inventing a conditioning stratum."""
    from cfm_id_llm.network_effect_conditioning import has_explicit_context
    context=entry.get('reviewed_target_context') or {}
    if (study.context or not study.outcome or not entry.get('source_review_receipt')
            or entry['reader_id']!=reading.MIX or has_explicit_context(context)):
        return None
    slot=(entry.get('reviewed_intent') or {}).get('slots',{}).get('query.time_horizon',{})
    claim=slot.get('claim')
    period=context.get('target_period') or {}
    if (not isinstance(claim,dict) or not isinstance(period,dict) or claim.get('state')!='STATED'
            or period.get('state')!='STATED' or claim.get('value')!=period.get('value')):
        return None
    value=claim.get('value')
    if not isinstance(value,str) or not value.strip() or value not in study.outcome:
        return None
    bundle=entry['bundle']
    documents=dict(bundle['documents'],business_question=bundle['question'])
    aliases=decoded['reference_binding']['aliases']
    links=[]
    for link in slot['source_links']:
        doc=documents.get(link['document_id'],'')
        quote=doc[link['start']:link['end']]
        if quote!=link['quote'] or value not in quote:
            continue
        refs=[aliases[r] for r in link['fact_source_ids'] if r in aliases]
        links.append(dict(document=link['document_id'],start=link['start'],end=link['end'],refs=refs,quote=quote))
    if (not any(link['document']=='business_question' for link in links) or not any(
            link['document']!='business_question' and set(link['refs']).intersection(study.source_ids)
            and study.outcome in link['quote'] for link in links)):
        return None
    return dict(value=value,source_links=links,field='study.context',role='outcome_period',
                intent_sha256=entry['reviewed_intent']['intent_sha256'])

def target_coordinates(c,family,*,source_index=0):
    if family==reading.OBS:
        q=observed_attributes.from_effect_reading(c,c.information[source_index])
        return observed_attributes.effect_coordinates(q,exposure_kind=c.exposure.kind)
    t=c.target;nodes=c.study.nodes
    base=dict(node_order=nodes,population=t.population,unit_weights=[str(Fraction(1,len(t.population))) if n in t.population else '0' for n in nodes],
        treatment=c.study.treatment,outcome=c.study.outcome,context=c.study.context)
    if family==reading.MIX:
        return dict(base,kind='FINITE_POLICY_MEAN',policies=[dict(assignment=[x.assignment[n] for n in nodes],weight=x.weight) for x in t.components])
    if family==reading.ARM:
        return dict(base,kind='SINGLE_ARM_MEAN',first=[t.first.own,t.first.exposure],
                    exposure=c.exposure.kind,averaging=t.averaging)
    raise ValueError('REGISTERED_EXTENDED_READER_REQUIRED')

def inspect_methods(entry,raw,*,note_review=None):
    family=entry['reader_id']
    out=dict(empty_result(),query_id=entry['query_id'],remaining_query_ids=deepcopy(entry['remaining_query_ids']),
        result_scope='SELECTED_QUERY_ONLY',fact_family=family,query_review=deepcopy(entry['query_review']),
        request_sha256=entry['request_sha256'],methods=[],exclusions=[])
    try:
        from cfm_id_llm.fact_reading_contracts import contract_for_entry
        contract=contract_for_entry(entry)
        if contract is None or contract.reader_id not in METHODS:raise ValueError('REGISTERED_EXTENDED_READER_REQUIRED')
        decoded=contract.parse_candidate(entry,raw);c=contract.model.model_validate(decoded['facts']);t=c.target
        period=reviewed_observation_period(entry,decoded,c.study)
        if period:
            # Keep the wire candidate and its existing source-review binding unchanged.
            # The native plan and its new review worksheets cover the resolved coordinates.
            decoded['facts']['study']['context']=period['value']
            c=contract.model.model_validate(decoded['facts'])
            out['study_context_binding']=period
        out.update(decoded,reading_candidate=deepcopy(raw),bundle=deepcopy(entry['bundle']))
        missing=[];blocked=[]
        def require(d,name):
            if d.value is None:
                missing.append(reading.population_contract.QUESTION if name=='评价对象在抽签前固定'
                               else '请明确本次分析是否采用这一条件：'+SCIENCE_NAMES.get(name,name)+'。')
            elif d.value is False:blocked.append('DECLARED_MODEL_EXCLUDES:'+name)
            elif not d.source_ids:missing.append('请补充声明的原文来源：'+name)
        def require_information(d,question):
            # Availability/completeness is not a causal premise. Preserve the
            # supplied false/unknown value and ask for the missing information.
            if d.value is not True:missing.append(question)
            elif not d.source_ids:missing.append('请补充这项信息声明的原文来源。')
        if not c.study.nodes or c.study.graph_kind=='UNKNOWN' or c.study.edge_list_complete is not True:
            missing.append('请明确完整对象名单与处理前关系网络。')
        if c.study.graph_kind=='OTHER' or c.study.outcome_kind=='OTHER':blocked.append('STUDY_SCOPE_NOT_CONNECTED')
        if c.study.outcome_kind=='UNKNOWN' or not c.study.source_ids or not all(v and v.strip() for v in (c.study.treatment,c.study.outcome)):
            missing.append('请明确处理编码、结果和时期背景及其来源。')
        elif not c.study.context or not c.study.context.strip():
            missing.append('请说明本题结果的评价时期与研究背景，以及相应的原文位置。')
        if not t.population or not t.source_ids:missing.append('请明确评价对象及目标原文。')
        if c.additional_restrictions:blocked.append('ADDITIONAL_RESTRICTIONS_REQUIRE_ADAPTER')
        method=ARM if family==reading.ARM else MIX if family==reading.MIX else AVG.get(t.averaging)
        if family!=reading.OBS:
            gaps,excluded=design.component_gaps(c,local_effect=family==reading.ARM)
            if 'CONFLICTING_FIRST_STAGE_EXCLUSION' in excluded:
                return dict(out,state='READING_RECHECK_REQUIRED',reason_code='CONFLICTING_FIRST_STAGE_EXCLUSION')
            missing+=['请补充设计或暴露字段：'+x for x in gaps];blocked+=excluded
            if c.assignment.kind=='OTHER':blocked.append('ASSIGNMENT_NOT_CONNECTED')
            if not c.assignment.source_ids:missing.append('请提供历史分配规则的来源。')
            science=tuple(BASE_CONDITIONS)+design.extra_science(c)
            for name in BASE_CONDITIONS:
                if name=='known_assignment_law':
                    question=design.assignment_availability_question(c.assumptions.known_assignment_law)
                    if question:missing.append(question)
                else:require(getattr(c.assumptions,name),name)
        else:
            if method is None:
                if t.averaging=='UNKNOWN':missing.append('请说明其余安排按实际采用规律平均，还是对处理前协变量调整后再平均。')
                else:blocked.append('OBSERVATIONAL_AVERAGING_NOT_CONNECTED')
            if c.regime.kind!='OBSERVATIONAL':missing.append('请明确采用方式是否属于观察性研究。')
            if not c.regime.source_ids:missing.append('请提供采用方式的来源。')
            if c.conditioning.kind=='OTHER':blocked.append('FIXED_CONTEXT_REQUIRED')
            elif c.conditioning.kind=='UNKNOWN' or not c.conditioning.definition or not c.conditioning.source_ids:
                missing.append('请明确固定处理前背景W；时期不能代替具体背景。')
            science=SCIENCE.get(method,BASIC)
            for name in science:
                d=getattr(c.assumptions,name);require(d,name)
                if getattr(d,'scope',None) is not None and d.value is True:
                    if d.scope=='UNKNOWN':missing.append('请明确科学声明是否覆盖所有二元完整安排：'+name)
                    elif d.scope!='ALL_BINARY_ASSIGNMENTS':blocked.append('SCIENTIFIC_SCOPE_NOT_CONNECTED:'+name)
                    if d.covered_nodes is not None and not set(t.population or [])<=set(d.covered_nodes):missing.append('科学声明没有覆盖全部评价对象：'+name)
            # A stronger, unused claim is retained and reviewed, never silently discarded.
            science=tuple(dict.fromkeys((*science,*(n for n,d in c.assumptions if d.value is True))))
            if t.kind!=entry['selected_query']['target']['kind']:
                return dict(out,state='READING_RECHECK_REQUIRED',reason_code='EFFECT_TARGET_DISAGREES_WITH_REVIEWED_QUERY')
            require(t.population_fixed_before_treatment,'评价名单在处理前固定')
            require(t.shared_outcome_and_context,'两端结果和背景相同')
            if t.operation=='UNKNOWN' or t.kind=='UNKNOWN' or t.aggregation=='UNKNOWN':missing.append('请明确效应目标、比较方向和平均方式。')
            if 'OTHER' in (t.operation,t.kind,t.aggregation):blocked.append('LOCAL_EFFECT_TARGET_NOT_CONNECTED')
            if t.aggregation=='SINGLE' and t.population and len(t.population)!=1:raise ValueError('SINGLE_TARGET_REQUIRES_ONE_NODE')
        if family!=reading.MIX:
            from cfm_id_llm.network_design_reading import missing_exposure,EXPOSURE_GROUPS
            missing+=['请明确暴露定义：'+x for x in missing_exposure(c.exposure,c.study.nodes)]
            if c.exposure.kind not in EXPOSURE_GROUPS:
                (missing if c.exposure.kind=='UNKNOWN' else blocked).append('EXPOSURE_DEFINITION_NOT_ESTABLISHED')
            if not c.exposure.source_ids:missing.append('请提供同伴状态定义的来源。')
            arms=[t.first] if family==reading.ARM else [t.first,t.second]
            if any(a.own is None or a.exposure is None or not a.source_ids for a in arms):missing.append('请明确本人处理和同伴状态的取值及各端来源。')
            if any(a.own not in (0,1,None)
                   or (type(a.exposure) is int and a.exposure<0)
                   for a in arms):raise ValueError('INVALID_ARM_COORDINATES')
            if family==reading.ARM:
                if t.population and len(t.population)!=1:blocked.append('NATIVE_SINGLE_ARM_REQUIRES_ONE_EVALUATION_NODE')
                require(t.population_fixed_before_assignment,'评价对象在抽签前固定')
                if t.averaging=='OTHER':blocked.append('NONDESIGN_ARM_AVERAGING_NOT_CONNECTED')
                elif t.averaging=='UNKNOWN':missing.append('请明确其余安排是否按原设计在该状态下的条件分布平均。')
            elif all(a.own is not None and a.exposure is not None for a in arms):
                a,e=t.first.own,t.first.exposure;b,f=t.second.own,t.second.exposure
                if ((t.kind=='DIRECT_EFFECT' and not(a!=b and e==f)) or
                    (t.kind=='SPILLOVER_EFFECT' and not(a==b and e!=f)) or
                    (t.kind=='LOCAL_TOTAL_EFFECT' and not(a!=b and e!=f))):raise ValueError('LOCAL_EFFECT_KIND_COORDINATES_MISMATCH')
                if t.kind!='SPILLOVER_EFFECT' and a!=1:blocked.append('NATIVE_OBSERVATIONAL_NAMED_EFFECT_REVERSE_OWN_NOT_CONNECTED')
        else:
            if t.aggregation=='UNKNOWN':missing.append('请明确政策结果的平均方式。')
            elif t.aggregation!='EQUAL_MEAN':blocked.append('POLICY_AGGREGATION_NOT_CONNECTED')
            require_information(t.policy_distribution_complete,'请列全未来政策的候选方案和各自概率，并说明这是否是全部方案。')
            if not t.components:missing.append('请列出未来政策的全部完整方案与选择概率。')
            for x in t.components:
                if set(x.assignment)!=set(c.study.nodes) or x.weight is None or not x.source_ids:missing.append('请补齐每份方案的完整名单、概率和来源。')
                if any(v not in (0,1) for v in x.assignment.values()):raise ValueError('BINARY_POLICY_REQUIRED')
            if t.components and all(x.weight is not None for x in t.components):
                if t.policy_distribution_complete.value is True and sum(Fraction(x.weight) for x in t.components)!=1:raise ValueError('POLICY_WEIGHTS_DO_NOT_SUM_TO_ONE')
                if len({tuple(sorted(x.assignment.items())) for x in t.components})!=len(t.components):raise ValueError('DUPLICATE_POLICY_ATOM')
        available=[];information_scope_gap=False
        for i,s in enumerate(c.information):
            if s.availability=='FINITE_SAMPLE':continue
            if s.availability=='UNKNOWN' or s.operator=='UNKNOWN':missing.append('请明确信息类型、总体或样本属性及覆盖范围。');continue
            if s.operator=='OTHER' or s.availability!='SYMBOLIC_POPULATION_OPERATOR':blocked.append('INFORMATION_OPERATOR_NOT_CONNECTED');continue
            if not s.source_ids or not s.outcome_nodes:missing.append('请提供总体信息的来源和对象覆盖范围。');continue
            if s.operator=='FULL_JOINT_LAW' and set(s.outcome_nodes)!=set(c.study.nodes):
                return dict(out,state='READING_RECHECK_REQUIRED',reason_code='FULL_JOINT_LAW_REQUIRES_FULL_OUTCOME_SCOPE',
                    clarification_questions=['读取结果把资料记为全体结果的联合分布，但覆盖名单只有一部分。请按原材料核对信息类型与覆盖名单，不能自动补齐。'])
            if not set(t.population or [])<=set(s.outcome_nodes):continue
            if family==reading.ARM:
                required={(t.population[0],t.first.own,t.first.exposure)} if t.population else set()
                if s.operator=='NODE_ARM_MEANS' and not required<={(a.node,a.own,a.exposure) for a in s.arm_cells}:continue
            elif family==reading.MIX:
                if s.operator not in ('FULL_JOINT_LAW','NODE_FULL_LAW','ASSIGNMENT_NODE_MEANS'):blocked.append('FINITE_POLICY_REQUIRES_ASSIGNMENT_LEVEL_INFORMATION');continue
                if s.operator=='ASSIGNMENT_NODE_MEANS' and all(set(x.assignment)==set(c.study.nodes) for x in t.components):
                    if not {tuple(x.assignment[n] for n in c.study.nodes) for x in t.components}<={tuple(x) for x in s.assignment_cells}:continue
            else:
                if method and s.operator not in observed_attributes.population_operators(t.averaging):blocked.append('TARGET_AVERAGING_AND_POPULATION_OPERATOR_MISMATCH');continue
                require_information(s.complete_law_and_mean_scope,'请说明总体分布和结果均值实际覆盖哪些情况；如果目前只提供了一部分，请补充缺少的范围。')
                require_information(s.same_study_and_context,'请核对这份总体信息是否针对本次研究对象和背景；其他研究或其他背景的资料不能直接代入。')
                if s.complete_law_and_mean_scope.value is not True or s.same_study_and_context.value is not True:
                    # A declared partial table need not sum to one. It remains
                    # unavailable; do not normalize it or send it to the solver.
                    information_scope_gap=True
                    continue
                _information_shape(s,c.study.nodes)
            available.append(i)
        if not available and not information_scope_gap:missing.append('需要覆盖本目标的总体信息；有限记录不能替代，未给定的格子不能补造。')
        if len(available)>1:blocked.append('MULTIPLE_POPULATION_SOURCES_REQUIRE_JOINT_ADAPTER')
        if blocked:return dict(out,state='ADAPTER_NOT_CONNECTED',reason_code=blocked[0],unsupported_reasons=blocked,clarification_questions=missing)
        if missing:return dict(out,state='NEEDS_INPUT',reason_code='EXTENDED_NETWORK_FACTS_INCOMPLETE',clarification_questions=list(dict.fromkeys(missing)))
        from .reading_note_review import inspect_notes
        notes=inspect_notes(entry,raw,[x.model_dump() for x in c.unresolved],contract.documents(entry['bundle']),note_review)
        if notes['worksheet'] is not None:out.update(note_review_worksheet=notes['worksheet'],note_review_receipt=notes['receipt'],reading_notes=decoded['facts']['unresolved'],reading_recheck_notes=notes['reading_recheck_notes'])
        if notes['state'] not in ('NO_NOTES','NOTES_RELEASED_FOR_CHECKS'):return dict(out,state=notes['state'],reason_code=notes['reason_code'],clarification_questions=notes['clarification_questions'])
        target=target_coordinates(c,family,source_index=available[0])
        decisions=READING_DECISIONS
        if entry.get('reviewed_target_context'):
            out['target_conditioning_review']=contract.target_context.review_item(entry['reviewed_target_context'],dict(study=c.study.model_dump(),target=t.model_dump()))
            decisions=(*decisions,contract.target_context.decision)
            from cfm_id_llm.network_effect_conditioning import has_explicit_context
            if family!=reading.OBS and has_explicit_context(entry['reviewed_target_context']):
                from .network_contrast_context import SCIENCE_REQUIREMENTS
                # An unconditional randomization declaration cannot silently
                # become a conditional one merely by adding W to the target.
                out['target_conditioning_review']['scientific_requirements']=dict(SCIENCE_REQUIREMENTS)
                science=(*science,*SCIENCE_REQUIREMENTS)
        binding=sha(dict(entry=entry,raw=raw,target=target,method=method,notes=notes))
        row=dict(method=method,source_index=available[0],reading_worksheet=worksheet(binding,decisions),
            science_worksheet=worksheet(binding,(*science,'a4_population_operator','target_averaging_and_population_information_scope')))
        digest=sha(dict(entry=entry,raw=raw,methods=[row],target=target,notes=notes))
        return dict(out,state='REVIEW_REQUIRED',methods=[row],proposed_target=target,plan_sha256=digest,plan_worksheet=worksheet(digest,PLAN_DECISIONS))
    except DispatchError as exc:return dict(out,state=exc.state,reason_code=exc.reason)
    except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError) as exc:
        return dict(out,state='CHECK_BLOCKED',reason_code='INVALID_EXTENDED_NETWORK_READING',diagnostic=str(exc)[:500])

def _information_shape(s,nodes):
    """Reject ignored coordinates and noncanonical laws; never fill their scope."""
    fields={'FINITE_ASSIGNMENT_LAW':('assignment_masses',),'FACTORIZED_ARM_LAW':('probabilities','covered_cells'),
        'MIXTURE_ARM_LAW':('mixture_components','covered_cells'),'STRATIFIED_ARM_LAW':('adjustment_variable','strata','covered_cells'),
        'NODEWISE_ARM_LAW':('adjustment_variable','profiles','covered_cells'),'NODEWISE_MIXTURE_ARM_LAW':('adjustment_variable','profiles','covered_cells')}
    allfields=set().union(*map(set,fields.values()))
    for name in allfields-set(fields[s.operator]):
        if getattr(s,name,None):raise ValueError('UNUSED_INFORMATION_FIELD:'+name)
    def probs(p):
        if p is None or set(p)!=set(nodes):raise ValueError('COMPLETE_PROBABILITY_VECTOR_REQUIRED')
        for v in p.values():
            reading.exact_number(v)
            if not 0<=Fraction(v)<=1:raise ValueError('PROBABILITY_OUTSIDE_UNIT_INTERVAL')
    def masses(rows):
        if not rows or sum(Fraction(x) for x in rows)!=1 or any(Fraction(x)<=0 for x in rows):raise ValueError('COMPLETE_POSITIVE_MASS_LAW_REQUIRED')
        for v in rows:reading.exact_number(v)
    def mixture(rows):
        masses([x.weight for x in rows])
        for x in rows:probs(x.probabilities)
    if s.operator=='FINITE_ASSIGNMENT_LAW':
        masses([x.probability for x in s.assignment_masses])
        keys=[]
        for x in s.assignment_masses:
            if set(x.assignment)!=set(nodes) or any(v not in (0,1) for v in x.assignment.values()):raise ValueError('COMPLETE_BINARY_ASSIGNMENT_REQUIRED')
            keys.append(tuple(x.assignment[n] for n in nodes))
        if len(keys)!=len(set(keys)):raise ValueError('DUPLICATE_ASSIGNMENT_ROW')
    if s.operator=='FACTORIZED_ARM_LAW':probs(s.probabilities)
    if s.operator=='MIXTURE_ARM_LAW':mixture(s.mixture_components)
    if s.operator=='STRATIFIED_ARM_LAW':
        masses([x.mass for x in s.strata])
        for x in s.strata:probs(x.probabilities)
    if s.operator.startswith('NODEWISE'):
        masses([x.mass for x in s.profiles])
        for x in s.profiles:
            if set(x.features)!=set(nodes) or any(v not in (0,1) for v in x.features.values()):raise ValueError('COMPLETE_BINARY_FEATURE_PROFILE_REQUIRED')
            if s.operator=='NODEWISE_ARM_LAW':
                probs(x.probabilities)
                if x.mixture_components:raise ValueError('UNUSED_PROFILE_MIXTURE')
            else:
                mixture(x.mixture_components)
                if x.probabilities is not None:raise ValueError('UNUSED_PROFILE_PROBABILITIES')
    for cell in getattr(s,'covered_cells',()):
        if cell.node not in s.outcome_nodes or cell.own not in (0,1) or cell.exposure<0:raise ValueError('INVALID_COVERED_CELL')
        if s.operator=='STRATIFIED_ARM_LAW':
            if cell.stratum is None or cell.own_feature is not None or cell.neighbor_feature_count is not None:raise ValueError('SHARED_STRATUM_CELL_REQUIRED')
        elif s.operator.startswith('NODEWISE'):
            if cell.stratum is not None or cell.own_feature not in (0,1) or cell.neighbor_feature_count is None or cell.neighbor_feature_count<0:raise ValueError('NODEWISE_CELL_REQUIRED')
        elif any(v is not None for v in (cell.stratum,cell.own_feature,cell.neighbor_feature_count)):raise ValueError('UNADJUSTED_CELL_REQUIRED')

def _native_inputs(plan,row,pair):
    from pfn_pipeline import identification_business as core
    from pfn_pipeline._internal.identification.schemas import Assumption,NetworkExposureSpec
    from pfn_pipeline.network_inquiry_shadow import declare_network_study,fixed_policy_target_from_context,declare_network_a4_source
    from pfn_pipeline.identification_policy_r2 import declare_policy_signature
    c=reading.MODELS[plan['fact_family']].model_validate(plan['facts']);s=c.information[row['source_index']];t=c.target
    if target_coordinates(c,plan['fact_family'],source_index=row['source_index'])!=plan['proposed_target']:raise ValueError('TARGET_PLAN_MISMATCH')
    review=pair['science_review'];evidence=review.evidence+'; review='+review.binding_sha256
    provenance=lambda ids:'Reviewed original source locators: '+','.join(ids)+'; '+evidence
    external=getattr(review,'authority',None)=='EXTERNAL_RESEARCH_REVIEW'
    def condition(name):return Assumption(name=name,source='human_confirmation' if external else 'demo_specification',confirmed=True,status='ADMITTED',evidence=[provenance(getattr(c.assumptions,name).source_ids),review.reviewer])
    if row['method']==ARM:
        local_methods.resolve(row['method'],local_methods.ARM_MEAN)
        net=NetworkExposureSpec(network_id='arm_'+sha(c.study.model_dump()),node_ids=c.study.nodes,undirected_edges=c.study.edges)
        return core.ArmInquiryV21(design.make_arm(c,net,source=provenance(s.source_ids),evidence=evidence))
    isobs=plan['fact_family']==reading.OBS
    if not isobs:
        finite_policy_methods.resolve(row['method'],finite_policy_methods.OPERATION)
    context=plan['proposed_target']['context']
    if isobs:
        question=observed_attributes.from_effect_reading(c,s)
        observed_attributes.require_effect_coordinates(question,plan['proposed_target'],exposure_kind=c.exposure.kind)
        observational_methods.require_effect(row['method'],question,s.operator)
        context=question.study.context_reference+'; fixed pretreatment W: '+question.fixed_background.definition
        study=observed_attributes.effect_native_study(question,
            network_id='network_'+sha(dict(nodes=list(question.study.node_order),edges=sorted(sorted(e) for e in c.study.edges),context=context)),
            edges=c.study.edges,protocol_provenance=provenance(c.regime.source_ids),
            network_provenance=provenance(c.study.source_ids),graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    else:
        study=declare_network_study(network_id='network_'+sha(dict(nodes=c.study.nodes,edges=sorted(sorted(e) for e in c.study.edges),context=context)),
            node_order=tuple(c.study.nodes),undirected_edges=tuple(tuple(e) for e in c.study.edges),
            treatment_variable=c.study.treatment,outcome_variable=c.study.outcome,outcome_kind='continuous' if c.study.outcome_kind=='COUNT' else c.study.outcome_kind.lower(),
            context_reference=context,observation_regime='experimental',assignment_design=design.design_payload(c.assignment, nodes=tuple(c.study.nodes)),
            protocol_provenance=provenance(c.assignment.source_ids),network_provenance=provenance(c.study.source_ids),graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    kwargs=dict(source_id='source_'+sha(s.model_dump()),provenance=provenance(s.source_ids),admission='ADMITTED',availability=s.availability)
    if not isobs:
        assumptions=tuple(condition(n) for n in BASE_CONDITIONS)
        if design.extra_science(c):
            assumptions+= (Assumption(name=design.extra_science(c)[0],source='demo_specification',confirmed=True,status='ADMITTED',evidence=[provenance(c.first_stage_exclusion.source_ids),review.reviewer]),)
        a4=declare_network_a4_source(study,**kwargs,operator=s.operator,outcome_nodes=tuple(s.outcome_nodes),assignment_cells=tuple(tuple(v) for v in s.assignment_cells))
        return tuple(core.FixedPolicyInquiryV21(study,
            fixed_policy_target_from_context(study,tuple(x.assignment[n] for n in c.study.nodes),unit_weights=tuple(plan['proposed_target']['unit_weights']),authority='TRUSTED_FIXTURE'),
            assumptions,(a4,)) for x in t.components)
    signature=declare_policy_signature(study,**design.exposure_payload(c.exposure))
    request=observed_attributes.native_effect_request(question,cohort_evidence=provenance(t.population_fixed_before_treatment.source_ids))
    if external:
        from dataclasses import replace
        request=replace(request,cohort_authority='HUMAN_CONFIRMED_PRETREATMENT')
    method=row['method'];assumptions=tuple(condition(n) for n in (SCIENCE[P] if method==P else BASIC))
    if method==P:
        arms=tuple((a.node,a.own,a.exposure) for a in getattr(s,'covered_cells',()))
        if s.operator=='FINITE_ASSIGNMENT_LAW':
            from pfn_pipeline.identification_observational_r3 import declare_observational_population_v23 as declare
            a4=declare(study,**kwargs,outcome_nodes=tuple(s.outcome_nodes),assignment_masses=tuple((tuple(a.assignment[n] for n in c.study.nodes),a.probability) for a in s.assignment_masses))
        elif s.operator=='FACTORIZED_ARM_LAW':
            from pfn_pipeline.identification_observational_factorized_a4 import declare_observational_factorized_arm_population_v27p1 as declare
            a4=declare(study,signature,**kwargs,treatment_one_probabilities=s.probabilities,covered_arms=arms)
        else:
            from pfn_pipeline.identification_observational_mixture_a4 import declare_observational_mixture_arm_population_v28p1 as declare
            a4=declare(study,signature,**kwargs,components=tuple((x.weight,tuple(x.probabilities[n] for n in c.study.nodes)) for x in s.mixture_components),covered_arms=arms)
        return core.ObservationalEffectsInquiryV26(study,a4,assumptions,signature,(request,))
    covered=tuple(n for n in c.study.nodes if n in set(c.assumptions.potential_outcome_exposure_sufficiency.covered_nodes)&set(getattr(c.assumptions,SCIENCE[method][-1]).covered_nodes))
    if method==B:
        from pfn_pipeline.identification_observational_exposure_adjustment import declare_stratified_observational_arm_population_v27p2 as declare,admit_exposure_adjustment_a5_v27p2 as admit
        a4=declare(study,signature,**kwargs,adjustment_variable=question.averaging.variable,strata=tuple((x.label,x.mass,x.probabilities) for x in s.strata),covered_cells=tuple((x.stratum,x.node,x.own,x.exposure) for x in s.covered_cells))
        license=admit(study,signature,covered_nodes=covered,potential_outcome_exposure_sufficiency=condition('potential_outcome_exposure_sufficiency'),exposure_level_conditional_exchangeability=condition('exposure_level_conditional_exchangeability'))
        return core.ObservationalExposureAdjustedEffectsInquiryV27P2(study,a4,assumptions,signature,license,(request,))
    from pfn_pipeline.identification_observational_nodewise_adjustment import declare_nodewise_local_arm_population_v28 as declare,admit_nodewise_adjustment_a5_v28 as admit
    profiles=tuple((x.label,x.mass,x.features,x.probabilities) for x in s.profiles)
    if s.operator=='NODEWISE_MIXTURE_ARM_LAW':
        from pfn_pipeline.identification_observational_nodewise_mixture_a4 import declare_nodewise_correlated_arm_population_v28p2 as declare
        profiles=tuple((x.label,x.mass,x.features,tuple((v.weight,v.probabilities) for v in x.mixture_components)) for x in s.profiles)
    a4=declare(study,signature,**kwargs,feature_name=question.averaging.variable,profiles=profiles,covered_cells=tuple((x.node,x.own_feature,x.neighbor_feature_count,x.own,x.exposure) for x in s.covered_cells))
    license=admit(study,signature,feature_name=question.averaging.variable,covered_nodes=covered,potential_outcome_exposure_sufficiency=condition('potential_outcome_exposure_sufficiency'),local_covariate_exposure_mean_exchangeability=condition('local_covariate_exposure_mean_exchangeability'))
    return core.ObservationalNodewiseAdjustedEffectsInquiryV28(study,a4,assumptions,signature,license,(request,))

def _execute_plan(plan,*,plan_review=None,native_reviews=None,research_protocol_selected=False):
    out=dict(empty_result(),query_id=plan['query_id'],remaining_query_ids=plan['remaining_query_ids'],result_scope='SELECTED_QUERY_ONLY',fact_family=plan['fact_family'],plan_sha256=plan['plan_sha256'],attempts=[])
    try:
        if research_protocol_selected is not True:raise DispatchError('REVIEW_REQUIRED','EXPLICIT_RESEARCH_PROTOCOL_SELECTION_REQUIRED')
        review=checked_review(plan_review,plan['plan_worksheet'])
        if review.authority!=plan['query_review']['authority']:raise ValueError('REVIEW_AUTHORITY_MISMATCH')
        if review.authority!='SYNTHETIC_TEST':raise DispatchError('ADAPTER_NOT_CONNECTED','EXTENDED_NATIVE_SYNTHETIC_SCOPE_ONLY')
        if len(plan['methods'])!=1 or plan['methods'][0]['method'] not in METHODS[plan['fact_family']]:raise ValueError('EXACT_REGISTERED_METHOD_REQUIRED')
        row=plan['methods'][0];method=row['method']
        if native_reviews is None:raise DispatchError('REVIEW_REQUIRED','NATIVE_REVIEWS_REQUIRED')
        pair=native_reviews_from_json(plan,native_reviews)[method]
        for k,sheet in (('reading_review','reading_worksheet'),('science_review','science_worksheet')):
            pair[k]=checked_review(pair[k],row[sheet])
            if pair[k].authority!=review.authority:raise ValueError('REVIEW_AUTHORITY_MISMATCH')
        inquiry=_native_inputs(plan,row,pair);original=sha(_native_payload(inquiry))
        from pfn_pipeline import identification_business as core
        observed_binding=(observational_methods.resolve(method,observational_methods.DIFFERENCE)
                          if plan['fact_family']==reading.OBS else None)
        mixture_binding=(finite_policy_methods.resolve(method,finite_policy_methods.OPERATION)
                         if plan['fact_family']==reading.MIX else None)
        out['backend_called']=True
        if method==MIX:
            components=[]
            for q in inquiry:
                answer,component_digest=native_outcome_execution.identify(mixture_binding,q,
                    fingerprint=lambda value:sha(_native_payload(value)))
                out['attempts'].append(dict(stage='POLICY_COMPONENT',state=answer.status,reason_code=answer.reason_code))
                if answer.status!='POINT':return dict(out,state=answer.status,reason_code=answer.reason_code)
                r=answer.result
                if answer.route!=mixture_binding.component_route or r.study!=q.study or r.target!=q.target or r.sources!=q.r1b_sources or r.assumptions!=q.assumptions:raise ValueError('FIXED_COMPONENT_INPUT_OR_REPLAY_MISMATCH')
                try:
                    native_outcome_execution.replay_outcome(mixture_binding,answer,inquiry=q,
                        input_digest=component_digest,fingerprint=lambda value:sha(_native_payload(value)))
                except native_outcome_execution.NativeReplayMismatch as exc:
                    raise ValueError('FIXED_COMPONENT_INPUT_OR_REPLAY_MISMATCH') from exc
                components.append(r)
            if original!=sha(_native_payload(inquiry)):raise ValueError('COMPONENT_NATIVE_INPUT_MUTATED')
            inquiry=core.FinitePolicyInquiryV21(tuple(components),tuple(x['weight'] for x in plan['proposed_target']['policies']))
        if method==ARM:
            result,before=local_execution.identify(method,local_methods.ARM_MEAN,inquiry)
        elif observed_binding is not None:
            result,before=native_outcome_execution.identify(observed_binding,inquiry,
                fingerprint=lambda value:sha(_native_payload(value)))
        else:
            result,before=native_outcome_execution.identify(mixture_binding,inquiry,
                fingerprint=lambda value:sha(_native_payload(value)))
        out['attempts'].append(dict(method=method,state=result.status,reason_code=result.reason_code))
        if result.status!='POINT':return dict(out,state=result.status,reason_code=result.reason_code)
        if result.route!=native_id(method):raise ValueError('NATIVE_ROUTE_MISMATCH')
        r=result.result
        if method==ARM:
            if sha(_native_payload(r.task))!=sha(_native_payload(inquiry.task)):raise ValueError('ARM_TARGET_INPUT_MISMATCH')
            cert=result.summary()['identification'];expression=cert['identified_functional'];fingerprint=r.result.get('certificate',{}).get('target_fingerprint')
        elif method==MIX:
            # The native verifier canonicalizes policy ordering but never changes masses.
            expected=sorted((tuple(v.target.policy_assignment),p) for v,p in zip(inquiry.components,inquiry.policy_probabilities))
            actual=sorted((tuple(v.target.policy_assignment),p) for v,p in zip(r.components,r.policy_probabilities))
            if actual!=expected:raise ValueError('FINITE_POLICY_INPUT_MISMATCH')
            cert=r.summary();expression=r.identified_functional;fingerprint=r.target_fingerprint
        else:
            for name in ('study','source','assumptions','signature','requests','license'):
                if hasattr(inquiry,name) and getattr(r,name)!=getattr(inquiry,name):raise ValueError('OBSERVATIONAL_INPUT_MISMATCH:'+name)
            if len(r.proofs)!=1:raise ValueError('EXACT_EFFECT_PROOF_REQUIRED')
            cert=r.summary();expression=r.proofs[0].identified_functional;fingerprint=r.proofs[0].target_fingerprint
        if method==ARM:
            local_execution.replay_outcome(method,local_methods.ARM_MEAN,result,inquiry=inquiry,input_digest=before)
        elif observed_binding is not None:
            native_outcome_execution.replay_outcome(observed_binding,result,inquiry=inquiry,
                input_digest=before,fingerprint=lambda value:sha(_native_payload(value)))
        else:
            native_outcome_execution.replay_outcome(mixture_binding,result,inquiry=inquiry,
                input_digest=before,fingerprint=lambda value:sha(_native_payload(value)))
        claim=dict(kind='POINT',representation='NATIVE_NETWORK_OBSERVED_FUNCTIONAL',target=deepcopy(plan['proposed_target']),target_fingerprint=fingerprint,expression=expression,numeric_value=None)
        answer=dict(method=method,mathematical_claim=claim,certificate=cert,independent_replay=True,reviewed_input_sha256=original,native_evidence=_native_payload(result))
        return dict(out,state='POINT',primary_method=method,mathematical_claim=claim,certificate=cert,independent_replay=True,answers=[answer],partial_fallback_performed=False)
    except DispatchError as exc:return dict(out,state=exc.state,reason_code=exc.reason)
    except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError) as exc:
        return dict(out,state='CHECK_BLOCKED',reason_code='INVALID_EXTENDED_REVIEW_OR_NATIVE_EVIDENCE',diagnostic=str(exc)[:500])
