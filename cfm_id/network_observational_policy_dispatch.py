"""Reviewed fixed-W policy -> unchanged finite R3 solver and replay.

No observational probability becomes a randomized design or a causal license.
"""
from copy import deepcopy
from fractions import Fraction
from .business_dispatch import (sha, worksheet, checked_review, DispatchError,
                                empty_result, PLAN_DECISIONS)
from .network_policy_dispatch import native_reviews_from_json
from cfm_id_bridge.scientific_binding import sha as native_sha, canonical_data
from cfm_id_llm import network_observational_policy_reading as reading
from . import research_spec_observational_adapters as observed_attributes
from . import research_spec_policy_adapters as policy_attributes

FAMILY = 'NETWORK_OBSERVATIONAL_POLICY_FACTS'
METHOD = 'R3_FULL_ASSIGNMENT'
SIGNATURE_METHOD = 'R3_MEAN_SIGNATURE'
METHODS = (METHOD, SIGNATURE_METHOD)
SIGNATURE_READING_DECISIONS = ('exposure_and_conditional_mean_sufficiency_scope',)
SIGNATURE_SCIENCE_DECISIONS = ('conditional_mean_sufficiency_all_assignments_and_weighted_nodes',)
BASE_CONDITIONS = ('full_vector_conditional_exchangeability', 'consistency',
                   'fixed_pretreatment_network', 'finite_conditional_first_moments')
A4_DECLARATIONS = ('complete_positive_assignment_support', 'means_for_all_positive_assignments',
                   'same_study_and_conditioning')
READING_DECISIONS = ('target_policy_population_and_weights', 'network_and_variable_meaning',
    'observational_regime_and_fixed_pretreatment_context', 'population_table_and_conditional_mean_scope',
    'all_information_and_restrictions_preserved', 'source_entailment')


def target_coordinates(c):
    question=observed_attributes.from_policy_reading(c)
    return observed_attributes.policy_native_question(question).coordinates()


def inspect_methods(entry, raw, *, note_review=None):
    out = dict(empty_result(), query_id=entry['query_id'], result_scope='SELECTED_QUERY_ONLY',
        remaining_query_ids=deepcopy(entry['remaining_query_ids']), fact_family=FAMILY,
        request_sha256=entry['request_sha256'], query_review=deepcopy(entry['query_review']),
        methods=[], exclusions=[], method_matching='NOT_CHECKED_BEFORE_SCIENCE_REVIEW')
    try:
        from cfm_id_llm.fact_reading_contracts import contract_for_entry
        contract = contract_for_entry(entry)
        if contract is None or contract.reader_id != FAMILY:
            raise ValueError('OBSERVATIONAL_READING_CONTRACT_REQUIRED')
        decoded = contract.parse(entry['bundle'], raw, binding=entry['fact_binding_sha256'])
        out.update(decoded, reading_candidate=deepcopy(raw), bundle=deepcopy(entry['bundle']))
        c = (contract.facts_model or contract.model).model_validate(decoded['facts'])
        from .reading_note_review import inspect_notes
        notes = inspect_notes(entry, raw, [n.model_dump() for n in c.unresolved],
                              contract.documents(entry['bundle']), note_review)
        if notes['worksheet'] is not None:
            out.update(note_review_worksheet=notes['worksheet'], note_review_receipt=notes['receipt'],
                       reading_notes=deepcopy(decoded['facts']['unresolved']), reading_recheck_notes=notes['reading_recheck_notes'])
        if c.regime.kind=='RANDOMIZED':
            return dict(out, state='READING_RECHECK_REQUIRED', reason_code='OBSERVATIONAL_A0_AND_RANDOMIZED_FACTS_DISAGREE')
        unsupported=[]; missing=[]
        if c.regime.kind=='OTHER': unsupported.append('OBSERVATIONAL_REGIME_NOT_ESTABLISHED')
        if c.regime.kind=='UNKNOWN' or not c.regime.source_ids: missing.append('请核对历史使用方式及其原文来源。')
        if c.study.graph_kind=='OTHER' or c.study.outcome_kind=='OTHER': unsupported.append('NETWORK_OR_OUTCOME_SCOPE_NOT_CONNECTED')
        if c.study.outcome_kind=='COUNT': unsupported.append('COUNT_OBSERVATIONAL_POLICY_NOT_CONNECTED')
        if c.target.kind=='OTHER' or c.target.aggregation=='OTHER': unsupported.append('TARGET_NOT_FIXED_EQUAL_WEIGHT_POLICY_MEAN')
        if c.conditioning.kind=='OTHER': unsupported.append('ONLY_FIXED_PRETREATMENT_W_CONNECTED')
        if c.additional_restrictions: unsupported.append('ADDITIONAL_INFORMATION_OR_RESTRICTIONS_REQUIRE_SEPARATE_ADAPTER')
        if len(c.study.nodes)>12: unsupported.append('FINITE_OBSERVATIONAL_SUPPORT_ENUMERATION_LIMIT')
        if c.study.graph_kind=='UNKNOWN' or c.study.edge_list_complete is not True or not c.study.nodes:
            missing.append('请明确对象名单、完整合作网络及网络类型。')
        if not c.study.source_ids or any(not v or not v.strip() for v in (c.study.treatment,c.study.outcome,c.study.context)) or c.study.outcome_kind=='UNKNOWN':
            missing.append('请明确处理、结果、期间背景及研究结构的原文来源。')
        if c.conditioning.kind=='UNKNOWN' or not c.conditioning.definition or not c.conditioning.definition.strip() or not c.conditioning.source_ids:
            missing.append('请明确本次固定的处理前条件W；不能代替为总体跨层平均或处理后条件。')
        if c.target.kind=='UNKNOWN' or c.target.assignment is None or set(c.target.assignment)!=set(c.study.nodes):
            missing.append('请明确本次完整政策中每个对象的处理，未提及对象不能默认不使用。')
        if not c.target.population or c.target.aggregation=='UNKNOWN' or not c.target.source_ids:
            missing.append('请明确评价名单、等权口径和目标原文来源。')
        for name in BASE_CONDITIONS:
            value=getattr(c.assumptions,name).value
            if value is None: missing.append('请独立核对科学条件声明：'+name)
            elif value is False: unsupported.append('DECLARED_MODEL_EXCLUDES:'+name)
        populations=[]
        for i,source in enumerate(c.information):
            if source.availability=='FINITE_SAMPLE':continue
            if source.operator=='OTHER':unsupported.append('INFORMATION_OPERATOR_NOT_CONNECTED');continue
            if source.operator=='UNKNOWN' or source.availability=='UNKNOWN':
                missing.append('请核对信息属于总体算子还是有限记录，以及实际覆盖范围。');continue
            populations.append(i)
            if not source.source_ids or not source.outcome_nodes:
                missing.append('请明确总体算子的来源及逐对象结果覆盖范围。')
            if c.target.population and not set(c.target.population)<=set(source.outcome_nodes):
                missing.append('总体条件结果均值未覆盖全部评价对象。')
            for name in A4_DECLARATIONS:
                value=getattr(source,name).value
                if name=='same_study_and_conditioning' and value is False:
                    unsupported.append('A4_DIFFERENT_STUDY_OR_CONDITIONING')
                elif value is not True:missing.append('请明确总体信息声明：'+name)
            cells=source.assignment_masses
            if not cells or any(set(x.assignment)!=set(c.study.nodes) or x.probability is None for x in cells):
                missing.append('请提供完整正质量安排表及精确总体概率，不能把遗漏安排补为零。')
            elif source.complete_positive_assignment_support.value is True and sum(Fraction(x.probability) for x in cells)!=1:
                raise ValueError('COMPLETE_POPULATION_LAW_MUST_SUM_TO_ONE')
        if not populations:missing.append('需要明确的观测总体分配律及同一声明下的结果条件均值；有限记录不能替代。')
        if len(populations)>1:unsupported.append('MULTIPLE_POPULATION_MODELS_NOT_COMBINED')
        method = METHOD
        # Route preparation only: presence in a complete positive-mass table.
        # Native R3 still proves support after independent scientific review.
        # Historical readings never acquire a signature license implicitly.
        if not missing and not unsupported and hasattr(c, 'mean_sufficiency'):
            source = c.information[populations[0]]
            listed = any(cell.assignment == c.target.assignment for cell in source.assignment_masses)
            if not listed:
                method = SIGNATURE_METHOD
                sf = c.mean_sufficiency
                if sf.value is None:
                    missing.append('完整政策不在给定正质量表中；请独立确认是否采用同一固定W下的均值签名充分性，不能由暴露定义推定。')
                elif sf.value is False:
                    unsupported.append('DECLARED_MODEL_EXCLUDES:mean_signature_sufficiency')
                else:
                    from cfm_id_llm.network_design_reading import EXPOSURE_GROUPS, missing_exposure
                    if sf.scope == 'UNKNOWN': missing.append('请明确条件均值充分性是否适用于所有完整二元安排。')
                    elif sf.scope != 'ALL_BINARY_ASSIGNMENTS': unsupported.append('CONDITIONAL_MEAN_SUFFICIENCY_SCOPE_NOT_CONNECTED')
                    if not set(c.target.population) <= set(sf.covered_nodes):
                        missing.append('条件均值充分性未覆盖全部评价对象，请核对其明确作用范围。')
                    if c.exposure.kind == 'UNKNOWN' or missing_exposure(c.exposure,c.study.nodes):
                        missing.append('请明确同伴暴露定义及所需的处理前核心同伴名单。')
                    elif c.exposure.kind not in EXPOSURE_GROUPS:
                        unsupported.append('OBSERVATIONAL_SIGNATURE_MAPPING_NOT_CONNECTED')
        out.update(clarification_questions=list(dict.fromkeys(missing)), unsupported_reasons=unsupported)
        if unsupported:return dict(out,state='ADAPTER_NOT_CONNECTED',reason_code=unsupported[0])
        if missing:return dict(out,state='NEEDS_INPUT',reason_code='OBSERVATIONAL_POLICY_FACTS_INCOMPLETE')
        if notes['state'] not in ('NO_NOTES','NOTES_RELEASED_FOR_CHECKS'):
            return dict(out,state=notes['state'],reason_code=notes['reason_code'],clarification_questions=notes['clarification_questions'])
        if notes['review'] is not None:entry=dict(entry,reading_note_review=deepcopy(notes['review']))
        out['proposed_target']=target_coordinates(c)
        reading_decisions = READING_DECISIONS + (SIGNATURE_READING_DECISIONS if method==SIGNATURE_METHOD else ())
        context = entry.get('reviewed_target_context')
        if context is not None:
            # Show both independently read declarations. Text equality cannot
            # prove semantic equivalence; explicit source review is mandatory.
            out['target_conditioning_review'] = contract.target_context.review_item(context,c.conditioning.model_dump())
            reading_decisions = (*reading_decisions, contract.target_context.decision)
        binding=sha(dict(entry=entry,raw=raw,method=method,source_index=populations[0],target=out['proposed_target']))
        row=dict(method=method,source_index=populations[0],applicability='NOT_CHECKED_BEFORE_SCIENCE_REVIEW',
            reading_worksheet=worksheet(binding,reading_decisions),
            science_worksheet=worksheet(binding,(*BASE_CONDITIONS,'a4_population_operator',*A4_DECLARATIONS,
                *(SIGNATURE_SCIENCE_DECISIONS if method==SIGNATURE_METHOD else ()))))
        out['methods']=[row]
        binding=sha(dict(entry=entry,raw=raw,methods=out['methods'],target=out['proposed_target']))
        return dict(out,state='REVIEW_REQUIRED',plan_sha256=binding,plan_worksheet=worksheet(binding,PLAN_DECISIONS))
    except DispatchError as exc:
        return dict(out,state=exc.state,reason_code=exc.reason)
    except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError):
        return dict(out,state='CHECK_BLOCKED',reason_code='INVALID_SOURCE_BOUND_OBSERVATIONAL_POLICY_READING')


def _compile(plan, row, records):
    from pfn_pipeline.identification_observational_r3 import declare_observational_population_v23
    from pfn_pipeline.identification_business import ObservationalPolicyInquiryV23
    from pfn_pipeline._internal.identification.schemas import Assumption
    from cfm_id_llm.network_observational_signature_reading import ObservationalSignatureReading, VERSION
    model = ObservationalSignatureReading if plan['facts']['version']==VERSION else reading.ObservationalPolicyReading
    c=model.model_validate(plan['facts']);target=plan['proposed_target']
    question=observed_attributes.policy_native_question(observed_attributes.from_policy_reading(c))
    question.require_coordinates(target)
    review=records['science_review']
    def provenance(ids):return 'Reviewed original source locators: '+','.join(ids)
    study=policy_attributes.native_study(question,network_id='network_'+sha(dict(nodes=c.study.nodes,edges=sorted(sorted(e) for e in c.study.edges),context=target['context'])),
        edges=c.study.edges,observation_regime='observational',assignment_design=None,
        protocol_provenance=provenance(c.regime.source_ids+c.conditioning.source_ids),
        network_provenance=provenance(c.study.source_ids),graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    native_target=policy_attributes.native_target(question,study,side='first',authority='TRUSTED_FIXTURE')
    source=c.information[row['source_index']]
    ids=list(dict.fromkeys(source.source_ids+[s for x in source.assignment_masses for s in x.source_ids]+
                          [s for name in A4_DECLARATIONS for s in getattr(source,name).source_ids]))
    a4=declare_observational_population_v23(study,source_id='source_'+sha(source.model_dump()),
        provenance=provenance(ids)+'; independent review: '+review.reviewer+'; '+review.evidence+'; binding: '+review.binding_sha256,
        outcome_nodes=tuple(source.outcome_nodes),assignment_masses=tuple((tuple(x.assignment[n] for n in c.study.nodes),x.probability) for x in source.assignment_masses),
        admission='ADMITTED',availability='SYMBOLIC_POPULATION_OPERATOR')
    assumptions=tuple(Assumption(name=name,source='demo_specification',confirmed=True,status='ADMITTED',
        evidence=[provenance(getattr(c.assumptions,name).source_ids),review.reviewer,review.evidence,'review_binding:'+review.binding_sha256]) for name in BASE_CONDITIONS)
    signature = sufficiency = None
    if row['method']==SIGNATURE_METHOD:
        from pfn_pipeline.identification_policy_r2 import declare_policy_signature, admit_mean_signature_sufficiency
        from .network_design_adapter import exposure_payload
        signature=declare_policy_signature(study,**exposure_payload(c.exposure))
        sufficiency=admit_mean_signature_sufficiency(study,signature,covered_nodes=tuple(c.mean_sufficiency.covered_nodes),
            assumption=Assumption(name='mean_signature_sufficiency',source='demo_specification',confirmed=True,status='ADMITTED',
                evidence=[provenance(c.exposure.source_ids+c.mean_sufficiency.source_ids+c.conditioning.source_ids),
                          review.reviewer,review.evidence,'review_binding:'+review.binding_sha256]))
    return ObservationalPolicyInquiryV23(study,native_target,a4,assumptions,signature,sufficiency)


def _execute_plan(plan, *, plan_review=None, native_reviews=None, research_protocol_selected=False):
    out=dict(empty_result(),query_id=plan['query_id'],result_scope='SELECTED_QUERY_ONLY',
        remaining_query_ids=plan['remaining_query_ids'],fact_family=FAMILY,plan_sha256=plan['plan_sha256'],attempts=[])
    if plan.get('note_review_receipt') is not None:out['note_review_receipt']=deepcopy(plan['note_review_receipt'])
    try:
        if research_protocol_selected is not True:raise DispatchError('REVIEW_REQUIRED','EXPLICIT_RESEARCH_PROTOCOL_SELECTION_REQUIRED')
        review=checked_review(plan_review,plan['plan_worksheet'])
        if review.authority!=plan['query_review']['authority']:raise DispatchError('CHECK_BLOCKED','DISPATCH_REVIEW_AUTHORITY_MISMATCH')
        if len(plan['methods'])!=1 or plan['methods'][0]['method'] not in METHODS:raise ValueError('EXACT_R3_POLICY_METHOD_REQUIRED')
        method=plan['methods'][0]['method']
        if native_reviews is None:raise DispatchError('REVIEW_REQUIRED','OBSERVATIONAL_READING_AND_SCIENCE_REVIEWS_REQUIRED')
        records=native_reviews_from_json(plan,native_reviews)[method];row=plan['methods'][0]
        for key,field in (('reading_review','reading_worksheet'),('science_review','science_worksheet')):
            records[key]=checked_review(records[key],row[field])
            if records[key].authority!=review.authority:raise DispatchError('CHECK_BLOCKED','OBSERVATIONAL_REVIEW_AUTHORITY_MISMATCH')
        if review.authority!='SYNTHETIC_TEST':return dict(out,state='ADAPTER_NOT_CONNECTED',reason_code='OBSERVATIONAL_SYNTHETIC_REVIEW_SCOPE_ONLY')
        inquiry=_compile(plan,row,records);original=native_sha(inquiry)
        from pfn_pipeline import identification_business as core
        from pfn_pipeline.identification_observational_r3 import VerifiedObservationalPolicyV23
        out['backend_called']=True
        result=core.identify_network_business_query(inquiry)
        if native_sha(inquiry)!=original:raise DispatchError('CHECK_BLOCKED','OBSERVATIONAL_NATIVE_INPUT_MUTATED')
        out['attempts'].append(dict(method=method,state=result.status,reason_code=result.reason_code))
        if result.status!='POINT':
            return dict(out,state='NEEDS_INPUT' if result.status=='NEEDS_INPUT' else 'UNSUPPORTED',reason_code=result.reason_code,
                nonidentification_proved=False,partial_fallback_performed=False)
        r=result.result
        if type(result) is not core.VerifiedBusinessOutcomeV21 or type(r) is not VerifiedObservationalPolicyV23 or result.route!=method:
            raise DispatchError('CHECK_BLOCKED','OBSERVATIONAL_VERIFIED_FULL_POLICY_REQUIRED')
        actual=native_sha([r.study,r.target,r.source,r.assumptions,r.signature,r.sufficiency])
        expected=native_sha([inquiry.study,inquiry.target,inquiry.source,inquiry.assumptions,inquiry.signature,inquiry.sufficiency])
        before=native_sha(result)
        if actual!=expected or core.replay_verified_business_outcome(result) is not True or native_sha(result)!=before or native_sha(inquiry)!=original:
            raise DispatchError('CHECK_BLOCKED','OBSERVATIONAL_RESULT_INPUT_OR_REPLAY_MISMATCH')
        claim=dict(kind='POINT',representation='FIXED_POLICY_OBSERVED_FUNCTIONAL',target=deepcopy(plan['proposed_target']),
            target_fingerprint=r.target_fingerprint,expression=r.identified_functional,numeric_value=None)
        certificate=r.summary()
        answer=dict(method=method,mathematical_claim=claim,certificate=certificate,native_evidence=canonical_data(r),
            independent_replay=True,reviewed_input_sha256=original)
        return dict(out,state='POINT',primary_method=method,answers=[answer],mathematical_claim=deepcopy(claim),
            certificate=deepcopy(certificate),independent_replay=True,partial_fallback_performed=False)
    except DispatchError as exc:
        return dict(out,state=exc.state,reason_code=exc.reason)
    except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError):
        return dict(out,state='CHECK_BLOCKED',reason_code='INVALID_OBSERVATIONAL_REVIEW_OR_NATIVE_EVIDENCE')
