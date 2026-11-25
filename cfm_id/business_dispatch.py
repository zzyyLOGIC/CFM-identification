"""Reviewed neutral intake -> fact reader, without a user-selected theorem.

Connected fact contracts cover finite variable DAGs and fixed network policies.
Other structures remain explicit coverage gaps in this bridge.
No keyword dispatch, scientific approval creation, or native math changes.
"""
from copy import deepcopy
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer
from . import business_intake as intake_api
from . import capability_registry as capabilities
from cfm_id_llm.compact_response_contract import evidence_contract

sha = intake_api._sha
QUERY_DECISIONS = ('business_target_and_population', 'research_structure', 'source_entailment')
PLAN_DECISIONS = ('selected_query_matches_native_target', 'complete_model_and_constraints_preserved',
                  'method_requests_and_projections_preserved')


class DispatchError(ValueError):
    def __init__(self, state, reason):
        self.state, self.reason = state, reason
        super().__init__(reason)


class DispatchReview(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    version: Literal['business-dispatch-review-1'] = 'business-dispatch-review-1'
    binding_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    reviewer: str = Field(min_length=3)
    evidence: str = Field(min_length=12)
    authority: Literal['EXTERNAL_RESEARCH_REVIEW', 'SYNTHETIC_TEST']
    decisions: dict[str, Literal['ACCEPTED', 'PENDING', 'REJECTED']]
    field_review: dict | None = None

    @model_serializer(mode='wrap')
    def omit_absent_field_review(self, handler):
        value = handler(self)
        if value.get('field_review') is None: value.pop('field_review', None)
        return value


def worksheet(binding, decisions):
    return dict(version='business-dispatch-review-1', binding_sha256=binding,
                decisions={key: 'PENDING' for key in decisions}, is_approval=False)


def checked_review(value, sheet, *, field_worksheet=None):
    if value is None:
        raise DispatchError('REVIEW_REQUIRED', 'INDEPENDENT_DISPATCH_REVIEW_REQUIRED')
    raw = value.model_dump(mode='json') if type(value) is DispatchReview else value
    r = DispatchReview.model_validate(raw)
    if not r.reviewer.strip() or not r.evidence.strip():
        raise DispatchError('CHECK_BLOCKED', 'NONBLANK_REVIEW_REQUIRED')
    if r.binding_sha256 != sheet['binding_sha256'] or set(r.decisions) != set(sheet['decisions']):
        raise DispatchError('CHECK_BLOCKED', 'STALE_OR_WRONG_SCOPE_DISPATCH_REVIEW')
    if r.field_review is not None:
        from .business_field_review import validate_attached
        validate_attached(r, field_worksheet)
    if 'REJECTED' in r.decisions.values():
        raise DispatchError('CHECK_BLOCKED', 'DISPATCH_REVIEW_REJECTED')
    if 'PENDING' in r.decisions.values():
        raise DispatchError('REVIEW_REQUIRED', 'DISPATCH_REVIEW_PENDING')
    return r


def empty_result():
    return dict(state='CHECK_BLOCKED', reason_code=None, backend_called=False,
                method_identity_version='semantic-methods-1',
                independent_replay=False, mathematical_claim=None, certificate=None,
                answers=[], clarification_questions=[],
                evidence_status='CURRENT_READING_NOT_PROVEN_SOURCE_ABSENCE',
                production_admission=False, estimation_handoff_allowed=False)


def _fact_request(bundle, binding, reader_id, reference_format, query, contexts, *, assignment_semantics=None, network_fact_contract=None, observational_fact_profile=None, signed_comparison=False, ordered_target=None, target_contract=None, reviewed_target_context=None, material_inventory=None, reviewed_policy_request=None, reviewed_intent=None):
    # Preserve the public diagnostic before the common registry checks metadata.
    if reader_id == 'VARIABLE_DAG_FACTS' and reference_format not in ('short_refs', 'source_hash'):
        raise ValueError('UNKNOWN_FACT_REFERENCE_FORMAT')
    try:
        network = capabilities.business_binding(reader_id).structure == 'UNIT_NETWORK'
    except capabilities.RegistryError as exc:
        # Registration lookup must preserve the caller-facing unknown-reader
        # diagnostic. Other registry defects remain explicit wiring errors.
        if str(exc) == 'UNREGISTERED_BUSINESS_READER':
            raise ValueError('UNKNOWN_FACT_READER') from exc
        raise
    from cfm_id_llm.fact_reading_contracts import contract_for_entry
    reading_contract = contract_for_entry(dict(reader_id=reader_id,reference_format=reference_format,
                                              network_fact_contract=network_fact_contract, observational_fact_profile=observational_fact_profile))
    if reading_contract is not None:
        request = reading_contract.request(bundle, binding=binding, assignment_semantics=assignment_semantics,
                                           signed_comparison=signed_comparison, network_fact_contract=network_fact_contract)
    elif reader_id == 'VARIABLE_DAG_FACTS':
        if reference_format == 'short_refs':
            from cfm_id_llm.dag_query_reading import make_request
            request = make_request(bundle, binding=binding)
        elif reference_format == 'source_hash':
            from cfm_id_llm.dag_frontdoor_reading import make_request
            request = make_request(bundle)
        else:
            raise ValueError('UNKNOWN_FACT_REFERENCE_FORMAT')
    else:
        raise ValueError('UNKNOWN_FACT_READER')
    focus = {key: query[key] for key in ('query_id', 'business_goal', 'requested_comparison_or_policy', 'semantics')}
    if reviewed_policy_request is not None:
        from cfm_id_llm.compact_response_contract import policy_focus_readers
        if reader_id not in policy_focus_readers(reviewed_policy_request['contract']):
            raise ValueError('POLICY_FOCUS_READER_MISMATCH')
        adapter=evidence_contract(reviewed_policy_request['contract'])
        if not hasattr(adapter,'policy_focus'):raise ValueError('POLICY_FOCUS_CONTRACT_REQUIRED')
        focus=adapter.policy_focus(reviewed_policy_request['raw_query'],query_id=query['query_id'],binding=binding)
    if ordered_target is not None:
        if reader_id!='NETWORK_RANDOMIZED_EFFECT_FACTS':raise ValueError('ORDERED_LOCAL_READER_REQUIRED')
        from cfm_id_llm import ordered_target_handoff
        adapter=evidence_contract(target_contract) if target_contract is not None else ordered_target_handoff
        if not hasattr(adapter,'fact_focus'):raise ValueError('REVIEWED_TARGET_CONTRACT_REQUIRED')
        focus=adapter.fact_focus(ordered_target,query_id=query['query_id'],binding=binding)
        request=adapter.clarify_fact_request(request)
    if reviewed_target_context is not None:
        focus['reviewed_target_context'] = deepcopy(reviewed_target_context)
        if reading_contract is not None and reading_contract.target_context is not None:
            request = reading_contract.target_context.clarify_request(request)
        elif reader_id == 'NETWORK_RANDOMIZED_EFFECT_FACTS':
            from cfm_id_llm import network_effect_conditioning
            if network_effect_conditioning.has_explicit_context(reviewed_target_context):
                request = network_effect_conditioning.clarify_request(request)
    if reviewed_intent is not None:
        from cfm_id_llm.reviewed_intent_handoff import attach
        request=attach(request,reviewed_intent,binding)
        # One selected intent instead of duplicate canonical policy aliases.
        focus=dict(query_id=query['query_id'],reviewed_intent_sha256=reviewed_intent['intent_sha256'])
    method_instruction = ('原文仍以 source_catalog 为准。不要混入其他子问题，也不要判断识别定理是否成立。\n' if network else
                          '原文仍以 source_catalog 为准。不要混入其他子问题，也不要判断后门、调整或前门是否成立。\n')
    request['user'] += ('\n\n本次只读取下面选定子问题。以下定位信息及此前助手提问均不是可引用事实来源；'
                        + method_instruction
                        + json.dumps(dict(focus=focus, assistant_context_not_evidence=contexts), ensure_ascii=False))
    if material_inventory is not None:
        from .reading_material_handoff import attach
        request=attach(request,material_inventory,reading_contract.reference_catalog(bundle,binding=binding))
    return request


def _checked_query_review(s, query_id, value, sheet):
    field_sheet = None
    detailed = (value.field_review if isinstance(value, DispatchReview) else
                value.get('field_review') if type(value) is dict else None)
    if evidence_contract(s.a0_response_contract) is not None and value is not None and detailed is None:
        raise DispatchError('REVIEW_REQUIRED', 'EXPLICIT_EVIDENCE_FIELD_REVIEW_REQUIRED')
    if detailed is not None:
        from .business_field_review import _worksheet
        authority = value.authority if isinstance(value, DispatchReview) else value.get('authority')
        field_sheet = _worksheet(s, query_id, authority)
    return checked_review(value, sheet, field_worksheet=field_sheet)


def prepare_reader(intake, query_id, *, query_review=None, reading_revision=None):
    """Select a fact-reading contract from audited fields, never a proof method."""
    out = dict(empty_result(), query_id=query_id, result_scope='SELECTED_QUERY_ONLY', reader_id=None, request=None,
               method_matching='NOT_PERFORMED', query_worksheet=None)
    try:
        s = intake_api._checked(intake)
        reading = intake_api.inspect(s)
        if 'report' not in reading:
            return dict(out, state=reading['state'], reason_code=reading.get('reason_code'))
        draft = reading['report']['draft']
        query = next((q for q in draft['queries'] if q['query_id'] == query_id), None)
        if query is None:
            raise DispatchError('CHECK_BLOCKED', 'EXACT_CURRENT_QUERY_REQUIRED')
        audit = next(q for q in reading['report']['query_quality'] if q['query_id'] == query_id)
        out.update(selected_query=deepcopy(query), remaining_query_ids=[q['query_id'] for q in draft['queries']
                   if q['query_id'] != query_id], intake_sha256=sha(s.model_dump(mode='json')))
        binding = sha(dict(intake_sha256=out['intake_sha256'], query_id=query_id))
        query_sheet = worksheet(binding, QUERY_DECISIONS)
        review = None
        if query_review is not None:
            try:
                # A submitted rejection/pending/stale review must not disappear
                # behind a simultaneous genuine target gap. Acceptance still
                # cannot bypass any of the original gates below.
                review = _checked_query_review(s, query_id, query_review, query_sheet)
            except (DispatchError, ValueError, TypeError, KeyError, AttributeError):
                out['query_worksheet'] = query_sheet
                out['deferred_clarification_questions'] = [i['question'] for i in
                    (reading.get('wire_gate') or {}).get('proposed_business_questions', [])
                    if i['query_id'] == query_id]
                raise
        stopped = (reading.get('reading_stop_receipt') or {}).get('queries', {}).get(query_id)
        if stopped is not None:
            return dict(out,state=stopped['state'],reason_code=stopped['reason_code'],
                clarification_questions=[x['question'] for x in stopped['clarification_questions']],
                wire_issues=deepcopy(stopped['original_wire_issues']),
                reading_stop_receipt=deepcopy(reading['reading_stop_receipt']))
        gate = reading.get('wire_gate') or {}
        issues = [i for i in intake_api.wire_recheck_issues(gate) if not i['path'].startswith('queries.')
                  or i['path'].startswith(f'queries.{query_id}.')]
        questions = [i['question'] for i in gate.get('proposed_business_questions', [])
                     if i['query_id'] == query_id]
        if issues:
            return dict(out, state='READING_RECHECK_REQUIRED', reason_code='SELECTED_QUERY_WIRE_RECHECK',
                        wire_issues=issues)
        if questions:
            return dict(out, state='NEEDS_INPUT', reason_code='SELECTED_QUERY_COORDINATES_MISSING',
                        clarification_questions=questions)
        if audit['business_status'] != 'FORMALIZATION_READY':
            state = ('READING_RECHECK_REQUIRED' if audit['business_status'] == 'FORMULATION_RECHECK_REQUIRED'
                     else 'NEEDS_INPUT')
            return dict(out, state=state, reason_code='SELECTED_QUERY_READING_NOT_READY',
                        clarification_questions=[q['question'] for q in audit['business_questions']],
                        reading_audit=deepcopy(audit))
        out['query_worksheet'] = query_sheet
        if review is None:
            review = _checked_query_review(s, query_id, query_review, query_sheet)
        structure = draft['shared_draft']['structure']
        network = structure['unit_network']['basis'] != 'UNRESOLVED'
        dag = structure['variable_causal_graph']['basis'] != 'UNRESOLVED'
        if network and dag:
            return dict(out, state='ADAPTER_NOT_CONNECTED', reason_code='COMBINED_OR_AMBIGUOUS_GRAPH_REPRESENTATIONS',
                        scope_note='Both descriptions are retained. This bridge does not compose unit networks and variable DAGs.')
        if not network and not dag:
            return dict(out, state='NEEDS_INPUT', reason_code='RESEARCH_STRUCTURE_NOT_ESTABLISHED',
                        clarification_questions=['材料中的关系指变量之间的因果影响，还是对象之间的相互影响？请核对研究对象与关系说明。'])
        assignment_family = draft['shared_draft']['information_design']['assignment_family']
        binding = capabilities.reader_for('UNIT_NETWORK' if network else 'VARIABLE_DAG', query['target']['kind'],
                                          assignment_family=assignment_family)
        if network and binding is None:
            return dict(out, state='ADAPTER_NOT_CONNECTED', reason_code=(
                'OBSERVATIONAL_NETWORK_TARGET_NOT_CONNECTED' if assignment_family=='OBSERVATIONAL'
                else 'NETWORK_TARGET_NOT_CONNECTED_TO_FIXED_POLICY_MEAN'))
        if network and s.fact_format != 'short_refs':
            return dict(out, state='ADAPTER_NOT_CONNECTED', reason_code='NETWORK_BRIDGE_REQUIRES_SHORT_FACT_READING')
        if dag and binding is None:
            return dict(out, state='ADAPTER_NOT_CONNECTED', reason_code='TARGET_NOT_CONNECTED_TO_DAG_DISTRIBUTION_CONTRACT')
        # Original text only in the source catalog; A0 paraphrases are metadata.
        docs = {d.source_id: d.text for d in s.case.sources}
        docs['business_question'] = s.case.business_question
        bundle = dict(case_id=s.case.case_id, documents=docs, question=s.case.business_question)
        fact_binding = sha(dict(intake_sha256=out['intake_sha256'], query_id=query_id,
                                query_review=review.model_dump(mode='json')))
        reader_id = binding.reader_id
        target_context = None
        # Use the registered contract capability, not one historical profile
        # name: instruction-only profiles must retain the same target guards.
        conditioning = evidence_contract(s.a0_response_contract)
        if conditioning is not None and hasattr(conditioning, 'target_context'):
            target_context = conditioning.target_context(s.candidate['queries'][int(query_id[1:])-1], query_id=query_id)
            blocked = conditioning.admission(target_context, reader_id)
            if blocked is not None:
                state, reason = blocked
                return dict(out, state=state, reason_code=reason, reviewed_target_context=target_context,
                    clarification_questions=[conditioning.QUESTION] if state=='NEEDS_INPUT' else [])
        contexts=[c.model_dump(mode='json') for c in s.clarifications]
        from cfm_id_llm.compact_response_contract import REVIEWED_TARGET_PROFILES,ROLE_REQUEST_PROFILES
        ordered_target=(s.candidate['queries'][int(query_id[1:])-1]
            if s.a0_response_contract in REVIEWED_TARGET_PROFILES and reader_id=='NETWORK_RANDOMIZED_EFFECT_FACTS' else None)
        material_inventory=None
        policy_request=None
        from cfm_id_llm.compact_response_contract import policy_focus_readers
        if reader_id in policy_focus_readers(s.a0_response_contract):
            policy_request=dict(contract=s.a0_response_contract,raw_query=deepcopy(s.candidate['queries'][int(query_id[1:])-1]))
        if s.material_handoff is not None:
            from .reading_material_handoff import build,FAMILIES
            if reader_id not in FAMILIES:
                raise DispatchError('ADAPTER_NOT_CONNECTED','MATERIAL_HANDOFF_NOT_CONNECTED_FOR_READER')
            material_inventory=build(s,query_id,review.model_dump(mode='json'))
        reviewed_intent=None
        if getattr(conditioning,'REVIEWED_INTENT_HANDOFF',False):
            from cfm_id_llm import reviewed_intent_handoff as intent_handoff
            if reader_id in intent_handoff.READERS:
                from cfm_id_llm.fact_reading_contracts import contract_for_entry
                contract=contract_for_entry(dict(reader_id=reader_id,reference_format=s.fact_format,
                    network_fact_contract=s.network_fact_contract,observational_fact_profile=s.observational_fact_profile))
                references=contract.reference_catalog(bundle,binding=fact_binding)
                reviewed_intent=intent_handoff.build(s,query_id,review.model_dump(mode='json'),reader_id,references)
        request=_fact_request(bundle,fact_binding,reader_id,s.fact_format,query,contexts,
                              assignment_semantics=s.assignment_semantics, network_fact_contract=s.network_fact_contract,
                              observational_fact_profile=s.observational_fact_profile,
                              signed_comparison=evidence_contract(s.a0_response_contract) is not None,ordered_target=ordered_target,
                              target_contract=s.a0_response_contract if ordered_target is not None else None,
                              reviewed_target_context=target_context,material_inventory=material_inventory,reviewed_policy_request=policy_request,
                              reviewed_intent=reviewed_intent)
        digest = sha(dict(intake=out['intake_sha256'], query_id=query_id,
                          query_review=review.model_dump(mode='json'), request=request))
        entry = dict(out, state='READY_TO_READ', reader_id=reader_id,
                    bundle=bundle, request=request, request_sha256=digest,
                    reference_format=s.fact_format, fact_binding_sha256=fact_binding,
                    query_review=review.model_dump(mode='json'))
        if material_inventory is not None:entry['material_inventory']=material_inventory
        if policy_request is not None:entry['reviewed_policy_request']=policy_request
        if reviewed_intent is not None:entry['reviewed_intent']=reviewed_intent
        if s.assignment_semantics is not None:
            entry['assignment_semantics'] = s.assignment_semantics
        if target_context is not None:
            entry['reviewed_target_context'] = target_context
        if s.a0_response_contract in ROLE_REQUEST_PROFILES and ordered_target is not None:
            # Reconstruct this same reviewed target on every explicit fact recheck.
            # Older protocol receipts keep their original request construction.
            entry['reviewed_local_request']=dict(contract=s.a0_response_contract,raw_query=deepcopy(ordered_target))
        from cfm_id_llm.fact_reading_contracts import contract_for_entry
        reading_contract = contract_for_entry(dict(entry,network_fact_contract=s.network_fact_contract, observational_fact_profile=s.observational_fact_profile))
        if reading_contract is not None:
            entry.update(reading_contract.entry_metadata())
        if s.network_fact_contract is not None and (reading_contract is None or reader_id in ('NETWORK_RANDOMIZED_EFFECT_FACTS','VARIABLE_DAG_FACTS')):
            entry['network_fact_contract'] = s.network_fact_contract
        if reader_id == 'NETWORK_RANDOMIZED_EFFECT_FACTS':
            from cfm_id_llm.network_effect_reading import VERSION
            entry['effect_fact_contract'] = getattr(evidence_contract(s.a0_response_contract),'FACT_VERSION',VERSION)
        if reading_revision is not None:
            from .fact_reading_revision import apply_revision
            return apply_revision(entry,reading_revision,contexts=contexts,
                                  signed_comparison=evidence_contract(s.a0_response_contract) is not None)
        return entry
    except DispatchError as exc:
        return dict(out, state=exc.state, reason_code=exc.reason)
    except capabilities.RegistryError as exc:
        return dict(out, state='CHECK_BLOCKED', reason_code='CAPABILITY_REGISTRATION_MISMATCH',
                    registration_error=str(exc))
    except (ValueError, TypeError, KeyError, AttributeError):
        return dict(out, state='CHECK_BLOCKED', reason_code='INVALID_INTAKE_OR_QUERY_REVIEW')


def inspect_methods(intake, query_id, *, query_review, candidate, request_sha256, note_review=None, reading_revision=None, change_review=None, information_evidence_review=None, source_review=None):
    entry = prepare_reader(intake, query_id, query_review=query_review,reading_revision=reading_revision)
    if entry['state'] != 'READY_TO_READ':
        return entry
    if request_sha256 != entry['request_sha256']:
        return dict(empty_result(), reason_code='STALE_FACT_READING_REQUEST')
    source_entry = entry  # Same reader snapshot used to issue the source worksheet.
    try:
        if reading_revision is None:
            if change_review is not None:raise ValueError('CHANGE_REVIEW_WITHOUT_REVISION')
        else:
            from .fact_reading_revision import _references,_paths
            from .reading_change_review import inspect_changes
            _paths(candidate)
            refs=_references(entry)
            if candidate.get('reference_context')!=refs['context']:
                raise ValueError('STALE_FACT_READING_CONTEXT')
            changes=inspect_changes(binding=entry,before=entry['reading_revision']['steps'][-1]['candidate'],
                after=candidate,source_catalog={r['source_id']:r for r in refs['aliases'].values()},
                authority=entry['query_review']['authority'],review=change_review)
            if changes['state'] not in ('UNCHANGED','CHANGES_REVIEWED'):
                return _revision_evidence(dict(empty_result(),state=changes['state'],reason_code=changes['reason_code'],
                    reading_change_worksheet=changes['worksheet'],reading_change_receipt=changes['receipt'],
                    reading_candidate=deepcopy(candidate)),entry)
            if changes['receipt']:
                entry=dict(entry,reading_change_review=changes['receipt']['review'],reading_change_receipt=changes['receipt'])
    except (ValueError,TypeError,KeyError,AttributeError):
        return dict(empty_result(),reason_code='INVALID_OR_STALE_READING_CHANGE_REVIEW')
    try:
        if entry.get('reviewed_intent') is not None and source_review is None:
            from .fact_source_review import prepare
            try:
                sheet=prepare(source_entry,candidate)
            except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError):
                return _revision_evidence(dict(empty_result(),reason_code='INVALID_REVIEWED_INTENT_FACT_READING'),entry)
            return _revision_evidence(dict(empty_result(),state='REVIEW_REQUIRED',
                reason_code='REVIEWED_INTENT_ALIGNMENT_REVIEW_REQUIRED',source_review_worksheet=sheet),entry)
        if entry.get('material_inventory') is not None:
            from .reading_impact_review import VERSION,prepare,pending_assessment,invalid_assessment
            if source_review is None:
                try:sheet=prepare(source_entry,candidate)
                except (ValueError,TypeError,KeyError,AttributeError):
                    return _revision_evidence(dict(empty_result(),reason_code='INVALID_MATERIAL_ACCOUNTING_INPUT',
                        reading_assessment=invalid_assessment()),entry)
                return _revision_evidence(dict(empty_result(),state='REVIEW_REQUIRED',reason_code='MATERIAL_ACCOUNTING_REVIEW_REQUIRED',
                    source_review_worksheet=sheet,reading_assessment=pending_assessment()),entry)
            raw=source_review.model_dump(mode='json') if hasattr(source_review,'model_dump') else source_review
            if not isinstance(raw,dict) or raw.get('version')!=VERSION:
                return _revision_evidence(dict(empty_result(),reason_code='MATERIAL_ACCOUNTING_REVIEW_VERSION_REQUIRED'),entry)
        if source_review is not None:
            from .fact_source_review import inspect_review
            try:
                source = inspect_review(source_entry, candidate, source_review)
            except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
                return _revision_evidence(dict(empty_result(),reason_code='INVALID_OR_STALE_FACT_SOURCE_REVIEW'),entry)
            if source['state'] != 'SOURCE_REVIEWED':
                return _revision_evidence(dict(empty_result(),**source),entry)
            # All downstream plans bind this exact review. Removing or changing
            # it at execution makes previously issued native approvals stale.
            entry = dict(entry,source_review_record=deepcopy(source['source_review_record']),
                         source_review_receipt=deepcopy(source['source_review_receipt']))
            if 'reading_assessment' in source:entry['reading_assessment']=deepcopy(source['reading_assessment'])
        binding = capabilities.business_binding(entry['reader_id'])
        if information_evidence_review is not None and not binding.information_evidence_review:
            return dict(empty_result(),reason_code='INFORMATION_EVIDENCE_REVIEW_NOT_CONNECTED_FOR_READER')
        if note_review is not None and not binding.note_review:
            return dict(empty_result(),state='ADAPTER_NOT_CONNECTED',reason_code='NOTE_REVIEW_NOT_CONNECTED_FOR_THIS_READER')
        options = {}
        if binding.note_review:
            options['note_review'] = note_review
        if binding.information_evidence_review:
            options['information_evidence_review'] = information_evidence_review
        result = binding.inspect(entry, candidate, **options)
        # Compare validated states from the current independently reviewed
        # intake. Do not change request/feedback hashes or interpret its prose.
        # Matching here has not invoked the mathematical backend.
        local = entry.get('reviewed_local_request')
        bind_information = bool(local and getattr(evidence_contract(local['contract']),'BIND_POPULATION_INFORMATION',False))
        if entry['reader_id']=='NETWORK_OBSERVATIONAL_POLICY_FACTS':
            current = intake_api._checked(intake)
            bind_information = getattr(evidence_contract(current.a0_response_contract),'BIND_POPULATION_INFORMATION',False)
        if bind_information and result.get('facts') is not None:
            from .reading_information_consistency import population_information_conflict
            current = intake_api._checked(intake)
            # Omitted optional claims have the existing UNKNOWN meaning. Do
            # not crash or invent population information for a legal omission.
            context = dict(entry,reviewed_population_information=current.candidate['common'].get('available_information','UNKNOWN'))
            conflict = population_information_conflict(context,result['facts']['information'])
            if conflict is not None:
                for key in ('proposed_target','plan_sha256','plan_worksheet'):
                    result.pop(key,None)
                result.update(state='READING_RECHECK_REQUIRED',reason_code=conflict['reason_code'],methods=[],
                    method_matching='NOT_PERFORMED_READING_CONFLICT',reading_consistency_conflict=conflict,
                    clarification_questions=['已审核的业务读取声明缺少总体信息，事实读取却声明可用总体信息。请复查两阶段原文和实际引用；若补充材料，应重新读取和审核。'])
        if result.get('methods') or 'plan_worksheet' in result:
            capabilities.plan_binding(result, reader_id=entry['reader_id'])
    except capabilities.RegistryError as exc:
        result = dict(empty_result(), reason_code='CAPABILITY_REGISTRATION_MISMATCH', registration_error=str(exc))
    from .method_matching import attach
    return attach(_revision_evidence(result,entry), reader_id=entry['reader_id'])


def _revision_evidence(result,entry):
    if entry.get('reviewed_intent_handoff') is not None:
        result=dict(result,reviewed_intent_handoff=deepcopy(entry['reviewed_intent_handoff']))
    if entry.get('reviewed_intent') is not None:
        result=dict(result,reviewed_intent_handoff=dict(version=entry['reviewed_intent']['version'],
            intent_sha256=entry['reviewed_intent']['intent_sha256'],
            alignment_review_required=True,automatic_semantic_match=False,scientific_approval=False))
    assessment=entry.get('reading_assessment') or result.get('reading_assessment')
    if assessment:
        from .reading_impact_review import report_result
        result=report_result(result,assessment)
    if entry.get('source_review_receipt'):
        result=dict(result,source_review_receipt=deepcopy(entry['source_review_receipt']))
    if 'reading_revision' in entry:
        result=dict(result,reading_revision=deepcopy(entry['reading_revision']),
                    reading_revision_receipt=deepcopy(entry['reading_revision_receipt']))
    if entry.get('reading_change_receipt'):
        result=dict(result,reading_change_receipt=deepcopy(entry['reading_change_receipt']))
    return result


def native_reviews_from_json(plan, records):
    return capabilities.plan_binding(plan).decode_reviews(plan, records)


def execute(intake, query_id, *, query_review, candidate, request_sha256,
            plan_review=None, native_reviews=None, research_protocol_selected=False, note_review=None, reading_revision=None, change_review=None, information_evidence_review=None, source_review=None):
    plan = inspect_methods(intake, query_id, query_review=query_review,
                           candidate=candidate, request_sha256=request_sha256,note_review=note_review,reading_revision=reading_revision,change_review=change_review,information_evidence_review=information_evidence_review,source_review=source_review)
    if plan['state'] != 'REVIEW_REQUIRED' or 'plan_worksheet' not in plan:
        return plan
    try:
        binding = capabilities.plan_binding(plan)
    except capabilities.RegistryError as exc:
        return dict(empty_result(), reason_code='CAPABILITY_REGISTRATION_MISMATCH', registration_error=str(exc))
    result = binding.execute(plan, plan_review=plan_review, native_reviews=native_reviews,
                           research_protocol_selected=research_protocol_selected)
    from .method_matching import REPORT_KEY
    if REPORT_KEY in plan:
        result[REPORT_KEY] = deepcopy(plan[REPORT_KEY])
    return _revision_evidence(result,plan)
