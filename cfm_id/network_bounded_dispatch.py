"""Reviewed mean model -> finite D1-D8/E1-E5 solver and replay.

This is an explicit model connection, not a fallback after a POINT failure.
The native mathematics is unchanged; complete A4 and model scope are reviewed.
"""
from copy import deepcopy
from .business_dispatch import sha,worksheet,PLAN_DECISIONS,DispatchError
from .bounded_policy_contract import (VERSION,MAX_N,BoundedMeanInformation,
    BoundedPolicyUnavailable,validate_model,input_digest)
from cfm_id_bridge.scientific_binding import sha as native_sha,canonical_data

METHOD='BOUNDED_POLICY_MEAN_D2_E1'
COUNT_METHOD='BOUNDED_POLICY_MEAN_D2_E4'
FINITE_METHOD='BOUNDED_POLICY_MEAN_FINITE'
METHODS=(METHOD,COUNT_METHOD,FINITE_METHOD)
DESIGNS=('INDEPENDENT_BERNOULLI','UNIFORM_FIXED_QUOTA','TWO_GROUP_FIXED_QUOTA',
         'CLUSTER_BERNOULLI','MULTI_GROUP_FIXED_QUOTA','TWO_STAGE_QUOTA_MIXTURE',
         'UNEQUAL_PROBABILITY_FIXED_QUOTA','RERANDOMIZED_BALANCED')
EXPOSURES=('STRICT_MAJORITY_TIES_LOW','THREE_LEVEL_TREATED_NEIGHBOR_FRACTION',
           'PRETREATMENT_CORE_COLLABORATOR_MAJORITY','EXACT_TREATED_NEIGHBOR_COUNT','ANY_TREATED_NEIGHBOR')
MODEL_DECISIONS=('exact_a4_values_and_complete_information_scope',
    'scientific_bounds_kind_scope_units_and_all_nodes','no_additional_coupling_constraints',
    'mean_sufficiency_all_assignments_and_all_model_nodes')


def model_information_indices(c):
    """Retain every population/unknown claim; only explicit sample records stay out of A4.

    The full candidate, citations and data descriptions remain in reading review
    and plan bindings. This does not discard a scientific constraint, infer an
    information closure, or promote sample estimates to population values.
    """
    return [i for i,s in enumerate(c.information)
            if not (s.operator=='FINITE_SAMPLE' and s.availability=='FINITE_SAMPLE')]


def prepare(entry,raw,c,out,*,_mean_order_context=None):
    from .network_policy_dispatch import BASE_CONDITIONS,READING_DECISIONS,target_coordinates
    def stop(state,reason,question=None):
        return dict(out,state=state,reason_code=reason,
            clarification_questions=[question] if question else out['clarification_questions'])
    # A POINT identity for real-valued outcomes also applies to counts. Sharp
    # bounds/nonidentification additionally need count-valued witness models;
    # that transfer has not been established by this business adapter.
    if c.study.outcome_kind == 'COUNT':
        return stop('ADAPTER_NOT_CONNECTED','COUNT_BOUNDED_MODEL_NOT_CONNECTED')
    if (c.assignment.kind not in DESIGNS or len(c.study.nodes)>MAX_N
            or c.exposure.kind not in (*EXPOSURES,'UNKNOWN','NONE','OTHER')):
        return stop('ADAPTER_NOT_CONNECTED','BOUNDED_D1_D8_E1_E5_FINITE_DOMAIN_REQUIRED')
    if c.assignment.kind in ('UNEQUAL_PROBABILITY_FIXED_QUOTA','RERANDOMIZED_BALANCED') and len(c.study.nodes)>8:
        return stop('ADAPTER_NOT_CONNECTED','EXTENDED_DESIGN_EXACT_ENUMERATION_LIMIT_8')
    if any(s.operator not in ('NODE_SIGNATURE_MEANS','FINITE_SAMPLE','UNKNOWN') for s in c.information):
        return stop('ADAPTER_NOT_CONNECTED','FULL_INFORMATION_CANNOT_BE_DOWNGRADED_TO_MEAN_BOX')
    indices=model_information_indices(c)
    information=[c.information[i] for i in indices]
    if not information or any(s.operator!='NODE_SIGNATURE_MEANS' or s.availability not in ('EXACT_POPULATION_VALUE','SYMBOLIC_POPULATION_OPERATOR')
                                for s in information):
        return stop('NEEDS_INPUT','EXACT_POPULATION_SIGNATURE_MEANS_REQUIRED',
                    '请核对精确总体签名均值的来源、格子和数值；不能使用样本估计替代。')
    availability={s.availability for s in information}
    if len(availability)!=1:
        return stop('ADAPTER_NOT_CONNECTED','MIXED_SYMBOLIC_NUMERIC_A4_NOT_CONNECTED')
    symbolic=availability=={'SYMBOLIC_POPULATION_OPERATOR'}
    if any(not s.source_ids or not s.signature_cells or
           set(s.outcome_nodes)!={v.node for v in s.signature_cells} or
           any((v.value is not None if symbolic else v.value is None) for v in s.signature_cells) for s in information):
        return stop('NEEDS_INPUT','COMPLETE_EXACT_A4_VALUE_LIST_REQUIRED',
                    '请核对总体均值覆盖的对象、自身状态与同伴状态；符号信息不填数值，已声明精确数值的信息不能漏值。')
    # Partitioning one original table into several JSON rows does not change A4.
    # Only concatenate exact disjoint cells from one source document. Records
    # may additionally cite definitions, but only after explicit evidence-role
    # review. Never merge independent sources or average duplicate cells.
    from .source_locations import build_catalog
    from cfm_id_llm.network_policy_reading import documents
    catalog=build_catalog(documents(entry['bundle']))
    source_documents={catalog[sid]['doc_id'] for s in information for sid in s.source_ids}
    supporting_evidence=entry.get('information_evidence_review')
    if len(source_documents)!=1 and supporting_evidence is None:
        return stop('ADAPTER_NOT_CONNECTED','EXACT_SINGLE_SOURCE_TABLE_REQUIRED')
    cells=[(v.node,v.own,v.exposure) for s in information for v in s.signature_cells]
    if len(cells)!=len(set(cells)):
        return stop('CHECK_BLOCKED','DUPLICATE_A4_CELL_ACROSS_ENTRIES')
    if _mean_order_context is not None and (c.exposure.kind!='STRICT_MAJORITY_TIES_LOW' or c.assignment.kind!='UNIFORM_FIXED_QUOTA'):
        return stop('ADAPTER_NOT_CONNECTED','MEAN_ORDER_D2_E1_DOMAIN_REQUIRED')
    sf=c.mean_sufficiency
    if sf.value is False or sf.scope=='OTHER' or c.exposure.kind in ('NONE','OTHER'):
        return stop('ADAPTER_NOT_CONNECTED','BOUNDED_MEAN_SIGNATURE_MODEL_NOT_ADOPTED')
    if (sf.value is not True or sf.scope!='ALL_BINARY_ASSIGNMENTS' or
        set(sf.covered_nodes)!=set(c.study.nodes) or c.exposure.kind not in EXPOSURES or
        not c.exposure.source_ids):
        return stop('NEEDS_INPUT','ALL_MODEL_NODES_REQUIRE_MEAN_SUFFICIENCY',
                    '该有限模型需另行确认全部对象、全部完整二元安排上的均值暴露充分性及明确的同伴状态定义。')
    b=c.bounded_model
    if b is None:
        return stop('NEEDS_INPUT','EXPLICIT_BOUNDS_AND_COMPLETE_MODEL_REQUIRED',
                    '请明确科学界限及其含义，并单独说明总体信息和模型限制是否完整。')
    if b.bounds_kind=='OTHER' or b.bounds_scope=='OTHER':
        return stop('ADAPTER_NOT_CONNECTED','BOUNDS_KIND_OR_SCOPE_NOT_CONNECTED')
    from .method_preparation import bounded_mean_implementation
    method = bounded_mean_implementation(assignment_kind=c.assignment.kind,
        exposure_kind=c.exposure.kind, symbolic=symbolic)
    if symbolic and _mean_order_context is not None:
        return stop('ADAPTER_NOT_CONNECTED','SYMBOLIC_MEAN_ORDER_NOT_CONNECTED')
    model_decisions = MODEL_DECISIONS
    if _mean_order_context is not None:
        from .network_mean_order_dispatch import METHOD as order_method, model_decisions as order_decisions
        order_model = _mean_order_context['model']
        modes = _mean_order_context['projection']['proposed_node_orders']
        expected_no_coupling = all(v['mode']=='NONE' for v in modes)
        if b.no_additional_coupling_constraints.value is None:
            return stop('NEEDS_INPUT','MEAN_ORDER_COUPLING_STATUS_REQUIRED')
        if b.no_additional_coupling_constraints.value is not expected_no_coupling:
            return stop('READING_RECHECK_REQUIRED','MEAN_ORDER_AND_COUPLING_DECLARATION_CONFLICT')
        method, model_decisions = order_method, order_decisions(c.study.nodes)
        declarations=(b.listed_means_are_complete_information,
                      order_model.no_additional_constraints_beyond_declared_orders)
        out['mean_order_context'] = dict(model=order_model.model_dump(),
                                        projection=_mean_order_context['projection'])
    else:
        declarations=(b.listed_means_are_complete_information,b.no_additional_coupling_constraints)
    if any(d.value is False for d in declarations):
        return stop('ADAPTER_NOT_CONNECTED','ADDITIONAL_INFORMATION_OR_COUPLING_REQUIRES_OTHER_MODEL')
    if (any(d.value is not True for d in declarations) or not b.source_ids or
        not b.outcome_definition or not b.outcome_unit or not b.outcome_period or
        b.bounds_kind=='UNKNOWN' or b.bounds_scope=='UNKNOWN' or
        set(v.node for v in b.bounds)!=set(c.study.nodes) or
        any(v.lower is None or v.upper is None or not v.source_ids for v in b.bounds)):
        return stop('NEEDS_INPUT','BOUNDED_MODEL_DECLARATIONS_INCOMPLETE',
                    '请核对逐对象界限、均值界或结果界、期间单位、全部安排范围，以及信息完整性和无额外耦合限制声明。')
    from . import network_design_adapter as design_adapter
    binding=sha(dict(entry=entry,raw=raw,method=method,source_indices=indices))
    row=dict(method=method,source_indices=indices,applicability='NOT_CHECKED_BEFORE_SCIENCE_REVIEW',
        reading_worksheet=worksheet(binding,READING_DECISIONS),
        science_worksheet=worksheet(binding,(*BASE_CONDITIONS,*design_adapter.extra_science(c),*('a4_source_'+str(i) for i in indices),*model_decisions)))
    out.update(methods=[row],proposed_target=target_coordinates(c),
        a4_projection=dict(kind='DISJOINT_EXACT_CELLS_FROM_ONE_SOURCE_DOCUMENT',
            source_documents=sorted(source_documents),original_entry_indices=indices,cell_count=len(cells)))
    if len(indices)!=len(c.information):
        out['a4_projection']['finite_sample_entry_indices']=[i for i in range(len(c.information)) if i not in indices]
    if supporting_evidence is not None:
        out['a4_projection'].update(kind='ONE_EXACT_TABLE_WITH_REVIEWED_SUPPORTING_REFERENCES',
            table_documents=supporting_evidence['table_documents'],supporting_documents=supporting_evidence['supporting_documents'],
            evidence_review_sha256=supporting_evidence['review_sha256'])
    binding=sha(dict(entry=entry,raw=raw,methods=out['methods'],exclusions=out['exclusions'],target=out['proposed_target']))
    return dict(out,state='REVIEW_REQUIRED',plan_sha256=binding,plan_worksheet=worksheet(binding,PLAN_DECISIONS))


def compile_reviewed(plan,row,records,authority):
    from .network_policy_dispatch import _compile,SIGNATURE_POLICY
    from cfm_id_llm.network_policy_reading import NetworkPolicyReading
    from pfn_pipeline.identification_business import FixedPolicyInquiryV21
    st,target,sources,assumptions,sig,suff=_compile(plan,dict(row,method=SIGNATURE_POLICY),records,authority)
    c=NetworkPolicyReading.model_validate(plan['facts']);b=c.bounded_model
    information=[c.information[i] for i in row['source_indices']]
    symbolic=all(s.availability=='SYMBOLIC_POPULATION_OPERATOR' for s in information)
    if len(sources)>1:
        from pfn_pipeline.identification_policy_r2 import declare_signature_population_source
        nodes={n for source in sources for n in source.outcome_nodes}
        grouped=declare_signature_population_source(st,sig,source_id='table_'+native_sha(c.information),
            operator='NODE_SIGNATURE_MEANS',outcome_nodes=tuple(n for n in st.node_order if n in nodes),
            admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR' if symbolic else 'EXACT_POPULATION_VALUE',
            signature_cells=tuple(cell for source in sources for cell in source.signature_cells),
            provenance='Reviewed exact table partition: '+sha(plan['a4_projection'])+'; plan:'+plan['plan_sha256'])
        sources=(grouped,)
    inquiry=FixedPolicyInquiryV21(study=st,target=target,assumptions=assumptions,
        r2_signature=sig,r2_sufficiency=suff,r2_sources=sources)
    info_type,version=BoundedMeanInformation,VERSION
    if symbolic:
        from .bounded_finite_contract import SymbolicMeanInformation,SYMBOLIC_VERSIONS
        info_type,version=SymbolicMeanInformation,SYMBOLIC_VERSIONS['policy']
    elif c.assignment.kind!='UNIFORM_FIXED_QUOTA' or sig.grouping not in ('strict_majority_ties_low','exact_treated_neighbor_count'):
        from .bounded_finite_contract import FiniteMeanInformation,POLICY_VERSION
        info_type,version=FiniteMeanInformation,POLICY_VERSION
    elif sig.grouping=='exact_treated_neighbor_count':
        from .bounded_count_contract import CountMeanInformation,POLICY_VERSION
        info_type,version=CountMeanInformation,POLICY_VERSION
    info=info_type(version=version,inquiry_sha256=native_sha(inquiry),
        source_id=sources[0].source_id,source_sha256=native_sha(sources[0]),
        information_scope='EXACT_LISTED_SIGNATURE_MEANS_ONLY',
        model_scope='SIGNATURE_MEANS_AND_NODE_BOUNDS_ONLY',
        availability='SYMBOLIC_POPULATION_OPERATOR' if symbolic else 'EXACT_POPULATION_VALUE',
        values=[dict(node=v.node,own=v.own,exposure=v.exposure,value=v.value) for s in information for v in s.signature_cells],
        bounds=[dict(node=v.node,lower=v.lower,upper=v.upper) for v in b.bounds],
        bounds_kind=b.bounds_kind,bounds_scope=b.bounds_scope,outcome_definition=b.outcome_definition,
        outcome_unit=b.outcome_unit,outcome_period=b.outcome_period,
        a4_provenance='Reviewed exact source locators: '+sha([sid for s in information for sid in s.source_ids]+
            b.listed_means_are_complete_information.source_ids)+'; plan:'+plan['plan_sha256'],
        bounds_provenance='Reviewed bound/model source locators: '+sha(b.source_ids+
            [sid for v in b.bounds for sid in v.source_ids]+b.no_additional_coupling_constraints.source_ids)
            +'; plan:'+plan['plan_sha256'])
    return inquiry,info


def execute_reviewed(plan,row,records,review,out):
    # Keep the existing bounded entry's hypothetical-research admission boundary.
    if review.authority!='SYNTHETIC_TEST':
        return dict(out,state='ADAPTER_NOT_CONNECTED',reason_code='BOUNDED_SYNTHETIC_REVIEW_SCOPE_ONLY')
    from .policy_execution import bounded_solution, PolicyEvidenceMismatch
    from .policy_methods import MEAN
    try:
        inquiry,info=compile_reviewed(plan,row,records,review.authority)
        try:
            certificate,original=bounded_solution(row['method'],MEAN,inquiry,info,
                before_compute=lambda: out.update(backend_called=True))
        except PolicyEvidenceMismatch:
            raise DispatchError('CHECK_BLOCKED','BOUNDED_INPUT_OR_REPLAY_MISMATCH')
        status=certificate['status']
        from .bounded_mean_formula import mathematical_claim
        claim=mathematical_claim(certificate,plan['proposed_target'])
        answer=dict(method=row['method'],mathematical_claim=claim,certificate=deepcopy(certificate),
            native_evidence=dict(inquiry=canonical_data(inquiry),information=canonical_data(info)),
            independent_replay=True,reviewed_input_sha256=original)
        return dict(out,state=status,answers=[answer],independent_replay=True,primary_method=row['method'],
            mathematical_claim=deepcopy(claim),certificate=deepcopy(certificate),
            attempts=[dict(method=row['method'],state=status,independent_replay=True)],partial_fallback_performed=False)
    except BoundedPolicyUnavailable as exc:
        return dict(out,state=exc.state,reason_code=exc.reason,
            diagnostic_only=True,incompatibility_proved=False,partial_fallback_performed=False)
