"""Reviewed fixed-policy facts -> unchanged full-policy/signature-policy solvers and verifiers.

The LLM declares facts only. Typed scientific admissions are constructed only
after separate, exact, independently supplied reviews. No partial-ID fallback.
"""
from .method_compat import canonical_id, native_id
from copy import deepcopy
from dataclasses import asdict
from .business_dispatch import (sha, worksheet, checked_review, DispatchReview,
    DispatchError, empty_result, PLAN_DECISIONS)
from cfm_id_llm.network_policy_reading import NetworkPolicyReading
from cfm_id_llm.network_fact_protocols import network_fact_protocol
from cfm_id_bridge.scientific_binding import sha as native_sha, canonical_data
from . import network_design_adapter as design_adapter
from . import research_spec_policy_adapters as policy_attributes
from cfm_id_llm import network_design_reading as design_fields

FULL_POLICY = 'network.randomized.full_policy_mean'
SIGNATURE_POLICY = 'network.randomized.signature_policy_mean'
FAMILY = 'NETWORK_FIXED_POLICY_FACTS'
BASE_CONDITIONS = ('known_assignment_law','full_vector_randomization','consistency',
                   'fixed_pretreatment_network','finite_conditional_first_moments')
READING_DECISIONS = ('target_policy_population_and_weights','network_assignment_and_variable_meaning',
                     'all_information_and_restrictions_preserved','source_entailment')
SIGNATURE_SCIENCE_DECISIONS = ('mean_sufficiency_all_assignments_and_weighted_nodes',)
# SIGNATURE_POLICY's mean-signature route conditions on an E1-E5 grouping; weighted/grouped
# exposures are not (yet) a signature family for that route.
SIGNATURE_KINDS = frozenset(design_fields.EXPOSURE_GROUPS) - {'WEIGHTED_EXPOSURE','GROUPED_EXPOSURE'}


def target_coordinates(c):
    return policy_attributes.from_reading(c).coordinates()


def inspect_methods(entry, raw, *, note_review=None, information_evidence_review=None, _mean_order_context=None):
    out = dict(empty_result(), query_id=entry['query_id'], result_scope='SELECTED_QUERY_ONLY',
        remaining_query_ids=deepcopy(entry['remaining_query_ids']), fact_family=FAMILY,
        request_sha256=entry['request_sha256'], methods=[], exclusions=[],
        method_matching='NOT_CHECKED_BEFORE_SCIENCE_REVIEW', query_review=deepcopy(entry['query_review']))
    try:
        if _mean_order_context is not None and not (
                entry.get('reader_id') == 'NETWORK_POLICY_CONTRAST_FACTS'
                and entry.get('comparison_endpoint') in ('first', 'second')):
            raise ValueError('MEAN_ORDER_REQUIRES_ORDERED_COMPARISON')
        from cfm_id_llm.fact_reading_contracts import contract_for_entry
        reader_entry = entry
        if (entry.get('reader_id') == 'NETWORK_POLICY_CONTRAST_FACTS'
                and entry.get('comparison_endpoint') in ('first', 'second')):
            # Existing contrast projections use this mean parser. Only select
            # its components; keep the original comparison entry in all hashes.
            reader_entry = dict(entry, reader_id=FAMILY)
        contract = contract_for_entry(reader_entry)
        if contract is None or contract.reader_id != FAMILY:
            raise ValueError('FIXED_POLICY_READING_CONTRACT_REQUIRED')
        decoded = contract.parse(entry['bundle'],raw,binding=entry['fact_binding_sha256'])
        out.update(decoded, reading_candidate=deepcopy(raw), bundle=deepcopy(entry['bundle']))
        if decoded.get('statement_reading_receipt',{}).get('conflicts'):
            return dict(out,state='READING_RECHECK_REQUIRED',reason_code='CONFLICTING_SOURCE_SCIENCE_STATEMENTS')
        c = NetworkPolicyReading.model_validate(decoded['facts'])
        if c.study.outcome_kind == 'COUNT':
            out['outcome_domain_embedding'] = dict(business_kind='COUNT', native_kind='continuous',
                scope='POLICY_POINT_MEAN_ONLY', count_restriction_retained_in_business=True,
                distributional_continuity_assumed=False, sharp_bound_or_nonidentification_transfer=False)
        if information_evidence_review is not None:
            from .network_information_evidence import check
            receipt=check(entry,raw,c,information_evidence_review)
            entry=dict(entry,information_evidence_review=deepcopy(receipt))
            out['information_evidence_receipt']=deepcopy(receipt)
        from .reading_note_review import inspect_notes
        notes=inspect_notes(entry,raw,[n.model_dump() for n in c.unresolved],contract.documents(entry['bundle']),note_review)
        if notes['worksheet'] is not None:
            out.update(note_review_worksheet=notes['worksheet'],note_review_receipt=notes['receipt'],
                reading_notes=deepcopy(decoded['facts']['unresolved']),reading_recheck_notes=notes['reading_recheck_notes'])
        gaps, unsupported = design_adapter.component_gaps(c)
        if 'CONFLICTING_FIRST_STAGE_EXCLUSION' in unsupported:
            return dict(out,state='READING_RECHECK_REQUIRED',reason_code='CONFLICTING_FIRST_STAGE_EXCLUSION')
        missing = [
            ('在最终启用名单相同的情况下，先抽中的名额方案本身是否还会影响结果？'
             '请说明本研究是否采用“名额方案只通过最终名单影响结果”这一条件；'
             '尚未决定或不采用也请直接说明。')
            if field == 'first_stage_exclusion'
            else '请补充原文中的分配或科学条件字段：'+field
            for field in gaps
        ]
        if c.additional_restrictions:
            unsupported.append('ADDITIONAL_INFORMATION_OR_RESTRICTIONS_REQUIRE_SEPARATE_ADAPTER')
        if c.study.graph_kind=='OTHER' or c.study.outcome_kind=='OTHER':
            unsupported.append('NETWORK_OR_OUTCOME_SCOPE_NOT_CONNECTED')
        if c.target.kind=='OTHER' or c.target.aggregation=='OTHER':
            unsupported.append('TARGET_NOT_FIXED_EQUAL_WEIGHT_POLICY_MEAN')
        if c.assignment.kind=='OTHER': unsupported.append('ASSIGNMENT_DESIGN_NOT_CONNECTED')
        if c.study.graph_kind=='UNKNOWN' or c.study.edge_list_complete is not True or not c.study.nodes:
            missing.append('请核对对象名单、完整合作边及网络类型；不能从提到“网络”就假定结构已齐全。')
        if (not c.study.treatment or not c.study.outcome or not c.study.context or
                c.study.outcome_kind=='UNKNOWN'):
            missing.append('请明确处理、结果的含义和研究对象、期间背景。')
        if c.assignment.kind=='UNKNOWN': missing.append('请说明原试点实际如何决定每一轮的完整名单。')
        if c.assignment.kind=='INDEPENDENT_BERNOULLI' and (c.assignment.probabilities is None or
                set(c.assignment.probabilities)!=set(c.study.nodes)):
            missing.append('原试点独立抽签时，每个对象的中签概率分别是多少？')
        if c.assignment.kind=='UNIFORM_FIXED_QUOTA' and c.assignment.fixed_count is None:
            missing.append('原试点每轮均匀抽取的固定人数是多少？人数上限或平均人数不能替代。')
        if (c.target.kind=='UNKNOWN' or c.target.assignment is None or
                set(c.target.assignment)!=set(c.study.nodes)):
            missing.append('请明确本次政策中每个对象是否使用处理，未提及的对象不能默认不使用。')
        if not c.target.population or c.target.aggregation=='UNKNOWN':
            missing.append('请明确评价哪些对象，以及是否对这些对象取等权平均。')
        for name in BASE_CONDITIONS:
            condition = getattr(c.assumptions,name)
            if name == 'known_assignment_law':
                question = design_adapter.assignment_availability_question(condition)
                if question: missing.append(question)
                continue
            if condition.value is None: missing.append('请研究者核对原材料中的科学条件声明：'+name+'；模型漏读不等于原文没有。')
            elif condition.value is False: unsupported.append('DECLARED_MODEL_EXCLUDES:'+name)
        if not c.study.source_ids or not c.target.source_ids or not c.assignment.source_ids:
            missing.append('研究结构、原设计和目标都需要各自的原文来源。')
        out.update(clarification_questions=list(dict.fromkeys(missing)),unsupported_reasons=unsupported)
        # A source can repeat the sample-only caveat in free-text restrictions.
        # Diagnose the typed A4 gap without interpreting or discarding that text.
        # After A4 is supplied, any remaining restrictions still block this bridge.
        if c.information and all(s.operator=='FINITE_SAMPLE' and s.availability=='FINITE_SAMPLE'
                                 for s in c.information):
            question = '现有材料只有有限样本；请明确理论识别允许使用的总体观测信息及其范围，不能把样本估计值当作精确总体信息。'
            return dict(out,state='NEEDS_INPUT',reason_code='POPULATION_INFORMATION_NOT_DECLARED',
                clarification_questions=list(dict.fromkeys([question,*missing])))
        unresolved_information = [i for i,s in enumerate(c.information)
                                  if s.operator=='UNKNOWN' or s.availability=='UNKNOWN']
        if unresolved_information:
            # A typed uncertainty is a reading/material question, not a known
            # theorem coverage gap. Keep all other notes/restrictions intact;
            # resolving this gap must not release those independent blockers.
            question = ('请先核对尚未明确的信息材料：它描述总体规律还是样本统计？'
                        '结果是逐个对象分别描述还是所有对象一起描述，处理是完整名单还是个人处理，覆盖哪些对象？'
                        '若原文已说明而读取遗漏，应重新读取；不能代用户选择信息范围。')
            return dict(out,state='NEEDS_INPUT',reason_code='POPULATION_INFORMATION_SCOPE_UNRESOLVED',
                unresolved_information_indices=unresolved_information,
                clarification_questions=list(dict.fromkeys([question,*missing])))
        if unsupported:
            return dict(out,state='ADAPTER_NOT_CONNECTED',reason_code=unsupported[0])
        if missing:
            return dict(out,state='NEEDS_INPUT',reason_code='NETWORK_POLICY_FACTS_INCOMPLETE')
        if notes['state'] not in ('NO_NOTES','NOTES_RELEASED_FOR_CHECKS'):
            return dict(out,state=notes['state'],reason_code=notes['reason_code'],
                clarification_questions=notes['clarification_questions'])
        if notes['review'] is not None:
            # Every downstream plan and native review binds this exact adjudication.
            entry=dict(entry,reading_note_review=deepcopy(notes['review']))
        if _mean_order_context is not None or c.bounded_model is not None or any(s.availability=='EXACT_POPULATION_VALUE' for s in c.information):
            from .network_bounded_dispatch import prepare
            from .network_contrast_context import bind_single_policy
            return bind_single_policy(entry,contract,c.study,prepare(entry,raw,c,out,_mean_order_context=_mean_order_context))
        usable = []
        for i,source in enumerate(c.information):
            if source.operator=='OTHER':
                return dict(out,state='ADAPTER_NOT_CONNECTED',reason_code='INFORMATION_OPERATOR_NOT_CONNECTED')
            if source.availability != 'SYMBOLIC_POPULATION_OPERATOR' or source.operator=='FINITE_SAMPLE':
                continue  # Kept in full facts, never promoted to population information.
            if not source.source_ids or not source.outcome_nodes:
                return dict(out,state='NEEDS_INPUT',reason_code='POPULATION_SOURCE_SCOPE_OR_PROVENANCE_MISSING')
            if source.operator=='ASSIGNMENT_NODE_MEANS' and not source.assignment_cells:
                return dict(out,state='NEEDS_INPUT',reason_code='ASSIGNMENT_MEAN_CELLS_MISSING')
            if source.operator=='NODE_SIGNATURE_MEANS' and not source.signature_cells:
                return dict(out,state='NEEDS_INPUT',reason_code='SIGNATURE_MEAN_CELLS_MISSING')
            usable.append(i)
        from .method_preparation import randomized_policy
        for choice in randomized_policy(c, usable):
            method = choice.method
            indices = list(choice.source_indices)
            if choice.reason_code:
                out['exclusions'].append(dict(method=method,reason_code=choice.reason_code,
                    unresolved=choice.unresolved))
                continue
            binding = sha(dict(entry=entry,raw=raw,method=method,source_indices=indices))
            science = (*BASE_CONDITIONS,*design_adapter.extra_science(c),*('a4_source_'+str(i) for i in indices))
            if method==SIGNATURE_POLICY: science += SIGNATURE_SCIENCE_DECISIONS
            out['methods'].append(dict(method=method,source_indices=indices,
                applicability='NOT_CHECKED_BEFORE_SCIENCE_REVIEW',
                reading_worksheet=worksheet(binding,READING_DECISIONS),
                science_worksheet=worksheet(binding,science)))
        if not out['methods']:
            return dict(out,state='NEEDS_INPUT',reason_code='NO_REVIEWABLE_POLICY_METHOD',
                clarification_questions=['请先核对可用总体信息及其范围；若希望使用暴露分组信息，还需独立说明是否采用覆盖目标对象、所有完整安排的均值充分性。'])
        out['proposed_target'] = target_coordinates(c)
        binding = sha(dict(entry=entry,raw=raw,methods=out['methods'],exclusions=out['exclusions'],target=out['proposed_target']))
        from .network_contrast_context import bind_single_policy
        return bind_single_policy(entry,contract,c.study,dict(out,state='REVIEW_REQUIRED',plan_sha256=binding,
                    plan_worksheet=worksheet(binding,PLAN_DECISIONS)))
    except DispatchError as exc:
        return dict(out,state=exc.state,reason_code=exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError, ZeroDivisionError):
        return dict(out,state='CHECK_BLOCKED',reason_code='INVALID_SOURCE_BOUND_NETWORK_POLICY_READING')


def native_reviews_from_json(plan, records):
    if type(records) is not dict or set(records)!={r['method'] for r in plan['methods']}:
        raise ValueError('EXACT_PLANNED_NETWORK_REVIEWS_REQUIRED')
    result={}
    for method,pair in records.items():
        if type(pair) is not dict or set(pair)!={'reading_review','science_review'}:
            raise ValueError('EXACT_NETWORK_REVIEW_PAIR_REQUIRED')
        result[method]={k:DispatchReview.model_validate(v) for k,v in pair.items()}
    return result


def _compile(plan, row, records, authority):
    """Only called after every independent review passes; not a parser default."""
    from . import policy_methods
    from pfn_pipeline._internal.identification.schemas import Assumption
    from pfn_pipeline.network_inquiry_shadow import declare_network_a4_source
    from pfn_pipeline.identification_policy_r2 import (declare_policy_signature,
        admit_mean_signature_sufficiency,declare_signature_population_source)
    c = NetworkPolicyReading.model_validate(plan['facts'])
    question = policy_attributes.from_reading(c)
    question.require_coordinates(plan['proposed_target'])
    if policy_methods.resolve(row['method'], question.operation).strategy != policy_methods.POINT:
        raise ValueError('NATIVE_POLICY_POINT_METHOD_REQUIRED')
    provenance = lambda ids: 'Reviewed original source locators: '+','.join(ids)
    design = design_adapter.design_payload(c.assignment, nodes=tuple(c.study.nodes))
    # Target identity must not change merely because q, A4 or A5 changes.
    graph_identity=dict(nodes=c.study.nodes,edges=sorted(sorted(e) for e in c.study.edges),context=c.study.context)
    st = policy_attributes.native_study(question, network_id='network_'+sha(graph_identity), edges=c.study.edges,
        observation_regime='experimental',assignment_design=design,
        protocol_provenance=provenance(c.assignment.source_ids),network_provenance=provenance(c.study.source_ids),
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    target = policy_attributes.native_target(question, st, side='first',
        authority='TRUSTED_FIXTURE' if authority=='SYNTHETIC_TEST' else 'HUMAN_CONFIRMED')
    review = records['science_review']
    def condition(name, ids):
        return Assumption(name=name,source='demo_specification' if authority=='SYNTHETIC_TEST' else 'human_confirmation',confirmed=True,status='ADMITTED',
            evidence=[provenance(ids),review.reviewer,review.evidence,'review_binding:'+review.binding_sha256])
    assumptions = tuple(condition(name,getattr(c.assumptions,name).source_ids) for name in BASE_CONDITIONS)
    if design_adapter.extra_science(c):
        assumptions += (condition(design_fields.D6_CONDITION,c.first_stage_exclusion.source_ids),)
    sig = declare_policy_signature(st,**design_adapter.exposure_payload(c.exposure)) if row['method']==SIGNATURE_POLICY else None
    suff = (admit_mean_signature_sufficiency(st,sig,covered_nodes=tuple(c.mean_sufficiency.covered_nodes),
        assumption=condition('mean_signature_sufficiency',c.mean_sufficiency.source_ids)) if sig else None)
    sources=[]
    for index in row['source_indices']:
        s=c.information[index]
        kwargs=dict(source_id='source_'+sha(s.model_dump()),operator=s.operator,
            outcome_nodes=tuple(s.outcome_nodes),admission='ADMITTED',availability=s.availability,
            provenance=provenance(s.source_ids)+'; independent review: '+review.reviewer+'; '+review.evidence)
        if row['method']==FULL_POLICY:
            source=declare_network_a4_source(st,**kwargs,assignment_cells=tuple(tuple(z) for z in s.assignment_cells))
        else:
            source=declare_signature_population_source(st,sig,**kwargs,
                signature_cells=tuple((x.node,x.own,x.exposure) for x in s.signature_cells))
        sources.append(source)
    return st,target,tuple(sources),assumptions,sig,suff


def _execute_plan(plan, *, plan_review=None, native_reviews=None, research_protocol_selected=False):
    out=dict(empty_result(),query_id=plan['query_id'],result_scope='SELECTED_QUERY_ONLY',
        remaining_query_ids=plan['remaining_query_ids'],plan_sha256=plan['plan_sha256'],
        fact_family=FAMILY,attempts=[],exclusions=deepcopy(plan['exclusions']))
    if plan.get('outcome_domain_embedding') is not None:
        out['outcome_domain_embedding'] = deepcopy(plan['outcome_domain_embedding'])
    if plan.get('note_review_receipt') is not None:
        out['note_review_receipt']=deepcopy(plan['note_review_receipt'])
    if plan.get('statement_reading_receipt') is not None:
        out['statement_reading_receipt']=deepcopy(plan['statement_reading_receipt'])
    if plan.get('information_evidence_receipt') is not None:
        out['information_evidence_receipt']=deepcopy(plan['information_evidence_receipt'])
    try:
        if research_protocol_selected is not True:
            raise DispatchError('REVIEW_REQUIRED','EXPLICIT_RESEARCH_PROTOCOL_SELECTION_REQUIRED')
        review=checked_review(plan_review,plan['plan_worksheet'])
        if review.authority!=plan['query_review']['authority']:
            raise DispatchError('CHECK_BLOCKED','DISPATCH_REVIEW_AUTHORITY_MISMATCH')
        if native_reviews is None:
            raise DispatchError('REVIEW_REQUIRED','NETWORK_READING_AND_SCIENCE_REVIEWS_REQUIRED')
        if type(native_reviews) is not dict or set(native_reviews)!={r['method'] for r in plan['methods']}:
            raise DispatchError('CHECK_BLOCKED','EXACT_PLANNED_NETWORK_REVIEWS_REQUIRED')
        from . import policy_methods
        policy_methods.require_plan(plan['methods'], policy_methods.MEAN)
        # All branch approvals must pass before any mathematical call.
        records={}
        for row in plan['methods']:
            pair=native_reviews[row['method']]
            if type(pair) is not dict or set(pair)!={'reading_review','science_review'}:
                raise ValueError('EXACT_REVIEW_PAIR_REQUIRED')
            records[row['method']]={}
            for key,sheet in (('reading_review','reading_worksheet'),('science_review','science_worksheet')):
                record=checked_review(pair[key],row[sheet])
                if record.authority!=review.authority:
                    raise DispatchError('CHECK_BLOCKED','NETWORK_REVIEW_AUTHORITY_MISMATCH')
                records[row['method']][key]=record
        from .network_bounded_dispatch import METHODS as bounded_methods, execute_reviewed
        if any(row['method'] in bounded_methods for row in plan['methods']):
            if len(plan['methods'])!=1:
                raise DispatchError('CHECK_BLOCKED','EXACT_BOUNDED_MODEL_PLAN_REQUIRED')
            return execute_reviewed(plan,plan['methods'][0],records[plan['methods'][0]['method']],review,out)
        from pfn_pipeline import identification_policy_r1b as r1b,identification_policy_r2 as r2
        from .policy_execution import point_solution
        answers=[]
        for row in plan['methods']:
            st,target,sources,assumptions,sig,suff=_compile(plan,row,records[row['method']],review.authority)
            inputs=native_sha([asdict(st),asdict(target),[asdict(s) for s in sources],
                [a.model_dump(mode='json') for a in assumptions],asdict(sig) if sig else None,
                asdict(suff) if suff else None])
            out['backend_called']=True
            try:
                result,replay=point_solution(row['method'], (st,target,sources,assumptions,sig,suff))
            except (r1b.R1bPolicyUnavailable,r2.R2PolicyUnavailable) as exc:
                out['attempts'].append(dict(method=row['method'],state='NOT_APPLICABLE',reason_code=exc.reason_code))
                continue
            # Check the returned proof against exactly the reviewed native input,
            # not merely against the problem carried inside a returned proof.
            returned=native_sha([asdict(result.study),asdict(result.target),[asdict(s) for s in result.sources],
                [a.model_dump(mode='json') for a in result.assumptions],
                asdict(result.signature) if row['method']==SIGNATURE_POLICY else None,
                asdict(result.sufficiency) if row['method']==SIGNATURE_POLICY else None])
            full_before=native_sha(result)
            if returned!=inputs or replay(result) is not True or native_sha(result)!=full_before:
                raise DispatchError('CHECK_BLOCKED','NETWORK_RESULT_INPUT_OR_REPLAY_MISMATCH')
            cert=result.summary(); before=sha(cert)
            if result.status!='POINT' or result.verification_status!='VERIFIED':
                raise DispatchError('CHECK_BLOCKED','NETWORK_VERIFIED_POINT_REQUIRED')
            claim=dict(kind='POINT',representation='FIXED_POLICY_OBSERVED_FUNCTIONAL',
                target=deepcopy(plan['proposed_target']),target_fingerprint=result.target_fingerprint,
                expression=result.identified_functional,numeric_value=None)
            if sha(result.summary())!=before:
                raise DispatchError('CHECK_BLOCKED','NETWORK_CERTIFICATE_MUTATED')
            answers.append(dict(method=row['method'],mathematical_claim=claim,certificate=cert,
                native_evidence=canonical_data(result),independent_replay=True,reviewed_input_sha256=inputs))
            out['attempts'].append(dict(method=row['method'],state='POINT',independent_replay=True))
        if answers:
            return dict(out,state='POINT',answers=answers,independent_replay=True,
                primary_method=answers[0]['method'],mathematical_claim=deepcopy(answers[0]['mathematical_claim']),
                certificate=deepcopy(answers[0]['certificate']))
        pending = any(r['unresolved'] for r in plan['exclusions']) or any(
            r['reason_code'].startswith('A4_') or r['reason_code'] in ('INFORMATION_BLOCKED','NEEDS_INPUT') for r in out['attempts'])
        return dict(out,state='NEEDS_INPUT' if pending else 'UNSUPPORTED',
            reason_code='NO_VERIFIED_NETWORK_POLICY_METHOD',nonidentification_proved=False,
            partial_fallback_performed=False,
            scope_note='No bounds or new assumptions inferred. Existing finite PARTIAL requires its separate complete contract.')
    except DispatchError as exc:
        return dict(out,state=exc.state,reason_code=exc.reason)
    except (ValueError,TypeError,KeyError,AttributeError,ZeroDivisionError):
        return dict(out,state='CHECK_BLOCKED',reason_code='INVALID_NETWORK_REVIEW_OR_NATIVE_EVIDENCE')


def __getattr__(name):
    from .method_compat import legacy_attribute
    return legacy_attribute(name, globals())
