"""Reviewed ordered policies -> existing R1b/R2 endpoints or joint mean box.

One common model, one scientific review, two explicit targets. No subtraction
of separate intervals, inferred bounds, fallback or new mathematical theorem.
"""
from copy import deepcopy
from .business_dispatch import (sha, worksheet, checked_review, DispatchError,
    empty_result, PLAN_DECISIONS)
from . import network_policy_dispatch as policy
from . import network_bounded_dispatch as bounded
from . import network_mean_order_dispatch as mean_order
from . import research_spec_policy_adapters as policy_attributes
from .bounded_policy_contract import BoundedPolicyUnavailable
from cfm_id_llm import network_contrast_reading as reading
from cfm_id_bridge.scientific_binding import sha as native_sha, canonical_data

FAMILY = 'NETWORK_POLICY_CONTRAST_FACTS'
POINT_METHOD = 'R1B_ENDPOINT_DIFFERENCE'
R2_METHOD = 'R2_ENDPOINT_DIFFERENCE'
BOUNDED_METHOD = 'BOUNDED_POLICY_CONTRAST_D2_E1'
COUNT_METHOD = 'BOUNDED_POLICY_CONTRAST_D2_E4'
FINITE_METHOD='BOUNDED_POLICY_CONTRAST_FINITE'
BOUNDED_METHODS=(BOUNDED_METHOD,COUNT_METHOD,FINITE_METHOD)
SIDES = reading.SIDES
PAIR_DECISIONS = ('two_complete_policies_and_first_minus_second_direction',
                  'common_evaluation_population_equal_weights_outcome_and_context')


def inspect_methods(entry, raw, *, note_review=None, information_evidence_review=None):
    out = dict(empty_result(), query_id=entry['query_id'], result_scope='SELECTED_QUERY_ONLY',
        remaining_query_ids=entry['remaining_query_ids'], fact_family=FAMILY,
        request_sha256=entry['request_sha256'], query_review=deepcopy(entry['query_review']),
        methods=[], exclusions=[], method_matching='NOT_CHECKED_BEFORE_SCIENCE_REVIEW')
    try:
        if note_review is not None and (type(note_review) is not dict or set(note_review) != set(SIDES)):
            raise ValueError('EXACT_TWO_ENDPOINT_NOTE_REVIEWS_REQUIRED')
        from cfm_id_llm.fact_reading_contracts import contract_for_entry
        contract = contract_for_entry(entry)
        if contract is None or contract.reader_id != FAMILY:
            raise ValueError('ORDERED_CONTRAST_READING_CONTRACT_REQUIRED')
        decoded = contract.parse(entry['bundle'], raw, binding=entry['fact_binding_sha256'])
        from . import network_contrast_context as fixed_context
        context_review = fixed_context.prepare(entry, contract, decoded)
        context_reading_decisions, context_science_decisions = (), ()
        if context_review is not None:
            out['target_conditioning_review'] = context_review
            context_reading_decisions = (context_review['decision'],)
            context_science_decisions = tuple(fixed_context.SCIENCE_REQUIREMENTS)
        information_receipt = None
        if information_evidence_review is not None:
            from .network_information_evidence import check
            from cfm_id_llm.network_policy_reading import NetworkPolicyReading
            shared = NetworkPolicyReading.model_validate(decoded['endpoint_readings']['first']['facts'])
            information_receipt = check(entry, raw, shared, information_evidence_review)
            out['information_evidence_receipt'] = deepcopy(information_receipt)
        t = decoded['target']
        out.update(reading_candidate=deepcopy(raw), bundle=deepcopy(entry['bundle']),
            contrast_target=deepcopy(t), endpoint_readings=decoded['endpoint_readings'])
        if 'evidence_dependencies' in decoded:
            out['evidence_dependencies'] = deepcopy(decoded['evidence_dependencies'])
        if t['kind'] == 'OTHER' or t['operation'] == 'OTHER':
            return dict(out, state='ADAPTER_NOT_CONNECTED', reason_code='TARGET_NOT_ORDERED_FIXED_POLICY_MEAN_DIFFERENCE')
        if t['shared_outcome_and_context']['value'] is False:
            return dict(out, state='ADAPTER_NOT_CONNECTED', reason_code='COMMON_CONTRAST_OUTCOME_AND_CONTEXT_REQUIRED')
        if (t['kind'] == 'UNKNOWN' or t['operation'] == 'UNKNOWN' or not t['source_ids']
                or t['shared_outcome_and_context']['value'] is None):
            return dict(out, state='NEEDS_INPUT', reason_code='CONTRAST_DIRECTION_OR_COMMON_CONTEXT_UNRESOLVED',
                clarification_questions=['请核对要用哪个完整方案减去哪个基准方案，以及是否比较同一结果、单位、期间与研究背景。'])
        a, b = (t[s] for s in SIDES)
        if a['population'] is not None and b['population'] is not None and set(a['population']) != set(b['population']):
            return dict(out, state='ADAPTER_NOT_CONNECTED', reason_code='COMMON_CONTRAST_POPULATION_REQUIRED')
        order_context = None
        if 'mean_order_model' in decoded:
            order_context = mean_order.inspect_reading(entry, decoded)
            out['mean_order_reading'] = deepcopy(order_context['projection'])
            if order_context['projection']['state'] != 'REVIEW_REQUIRED':
                projection = order_context['projection']
                return dict(out, state=('ADAPTER_NOT_CONNECTED' if projection['state']=='UNSUPPORTED' else projection['state']),
                    reason_code='MEAN_ORDER_DECLARATIONS_NOT_READY',
                    clarification_questions=projection['clarification_questions'])
        plans = {}
        for side in SIDES:
            endpoint = dict(entry, comparison_endpoint=side, comparison_candidate_sha256=sha(raw))
            if information_receipt is not None:
                # Reviewed once against the complete ordered candidate, before
                # either endpoint projection. Never accept an LLM-made receipt.
                endpoint['information_evidence_review'] = deepcopy(information_receipt)
            plans[side] = policy.inspect_methods(endpoint, decoded['endpoint_candidates'][side],
                note_review=None if note_review is None else note_review[side], _mean_order_context=order_context)
        out['endpoint_plans'] = plans
        if plans['first'].get('outcome_domain_embedding') is not None:
            out['outcome_domain_embedding'] = deepcopy(plans['first']['outcome_domain_embedding'])
        stops = [p for p in plans.values() if p['state'] != 'REVIEW_REQUIRED' or 'plan_worksheet' not in p]
        if stops:
            # Do not let a ready endpoint stand in for an incomplete second one.
            rank = {'CHECK_BLOCKED': 0, 'READING_RECHECK_REQUIRED': 1, 'ADAPTER_NOT_CONNECTED': 2,
                    'NEEDS_INPUT': 3, 'REVIEW_REQUIRED': 4}
            stopped = min(stops, key=lambda p: rank.get(p['state'], 5))
            return dict(out, state=stopped['state'], reason_code=stopped.get('reason_code'),
                clarification_questions=list(dict.fromkeys(q for p in stops for q in p['clarification_questions'])))
        question = policy_attributes.from_endpoint_plans(plans)
        finite_method = mean_order.METHOD if order_context is not None else next(
            (m for m in bounded.METHODS if all(any(r['method']==m for r in plans[s]['methods']) for s in SIDES)),bounded.METHOD)
        bounded_pair = all(any(r['method'] == finite_method for r in plans[s]['methods']) for s in SIDES)
        base_methods = ((finite_method,) if bounded_pair else tuple(m for m in (policy.R1B,policy.R2)
            if all(any(r['method']==m for r in plans[s]['methods']) for s in SIDES)))
        if not base_methods:
            return dict(out, state='ADAPTER_NOT_CONNECTED', reason_code='CONTRAST_ENDPOINT_METHOD_COMBINATION_NOT_CONNECTED',
                scope_note='Both endpoints need the same connected method and common model; mixed endpoint proofs or interval fallback are not inferred.')
        proposed = question.coordinates()
        for base_method in base_methods:
            rows = {s: next(r for r in plans[s]['methods'] if r['method']==base_method) for s in SIDES}
            first,second = (rows[s] for s in SIDES)
            if (first['source_indices']!=second['source_indices'] or
                    first['science_worksheet']['decisions']!=second['science_worksheet']['decisions']):
                raise ValueError('COMMON_CONTRAST_REVIEW_SCOPE_REQUIRED')
            method = {bounded.METHOD:BOUNDED_METHOD,bounded.COUNT_METHOD:COUNT_METHOD,bounded.FINITE_METHOD:FINITE_METHOD,mean_order.METHOD:mean_order.METHOD,
                      policy.R1B:POINT_METHOD,policy.R2:R2_METHOD}[base_method]
            binding = sha(dict(entry=entry, raw=raw, endpoint_plans=plans, target=proposed, method=method))
            out['methods'].append(dict(method=method, source_indices=first['source_indices'],
                applicability='NOT_CHECKED_BEFORE_SCIENCE_REVIEW',
                reading_worksheet=worksheet(binding, (*policy.READING_DECISIONS, *PAIR_DECISIONS, *context_reading_decisions)),
                science_worksheet=worksheet(binding, (*first['science_worksheet']['decisions'], *context_science_decisions))))
        out.update(proposed_target=proposed,
            scope_note='Existing ordered composition / joint finite model; no automatic endpoint interval subtraction.')
        binding = sha(dict(entry=entry, raw=raw, endpoint_plans=plans, target=proposed, methods=out['methods']))
        return dict(out, state='REVIEW_REQUIRED', plan_sha256=binding,
            plan_worksheet=worksheet(binding, (*PLAN_DECISIONS, *PAIR_DECISIONS)))
    except DispatchError as exc:
        return dict(out, state=exc.state, reason_code=exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
        from cfm_id_llm.network_mean_order_reading import PROFILES
        if entry.get('network_fact_contract') in PROFILES:
            from cfm_id_llm.wire_type_diagnostics import diagnose
            diagnostics = diagnose(entry, raw)
            if diagnostics:out['reading_diagnostics'] = diagnostics
        return dict(out, state='CHECK_BLOCKED', reason_code='INVALID_SOURCE_BOUND_NETWORK_CONTRAST_READING')


native_reviews_from_json = policy.native_reviews_from_json


def _compile_pair(plan, row, records, authority):
    from pfn_pipeline.identification_business import FixedPolicyInquiryV21
    question = policy_attributes.from_endpoint_plans(plan['endpoint_plans'])
    question.require_coordinates(plan['proposed_target'])
    inquiries, information = {}, {}
    for side in SIDES:
        endpoint = dict(plan['endpoint_plans'][side], plan_sha256=plan['plan_sha256'])
        if row['method'] in BOUNDED_METHODS:
            inquiries[side], information[side] = bounded.compile_reviewed(endpoint, row, records, authority)
        else:
            method = policy.R2 if row['method']==R2_METHOD else policy.R1B
            st,target,sources,assumptions,signature,sufficiency = policy._compile(
                endpoint,dict(row,method=method),records,authority)
            inquiries[side] = (FixedPolicyInquiryV21(study=st,target=target,assumptions=assumptions,
                r2_signature=signature,r2_sufficiency=sufficiency,r2_sources=sources) if method==policy.R2 else
                FixedPolicyInquiryV21(study=st,target=target,assumptions=assumptions,r1b_sources=sources))
    return inquiries, information


def _point(inquiries, plan, out, method=POINT_METHOD):
    from pfn_pipeline import identification_business as core
    if method==R2_METHOD:
        from .workflows import policy_difference as composition
    else:
        from . import fixed_comparison as composition
    target = {k: plan['proposed_target'][k] for k in ('node_order','first','second','unit_weights','operation')}
    original = native_sha(inquiries)
    results = {}
    for side in SIDES:
        out['backend_called'] = True
        result = core.identify_network_business_query(inquiries[side])
        if native_sha(inquiries) != original:
            raise DispatchError('CHECK_BLOCKED', 'CONTRAST_NATIVE_INPUT_MUTATED')
        out['attempts'].append(dict(endpoint=side, state=result.status, reason_code=result.reason_code))
        if result.status != 'POINT':
            continue
        r = result.result
        expected = inquiries[side]
        native_route = policy.R2 if method==R2_METHOD else policy.R1B
        actual_input = [r.study,r.target,r.sources,r.assumptions]
        expected_input = [expected.study,expected.target,
            expected.r2_sources if method==R2_METHOD else expected.r1b_sources,expected.assumptions]
        if method==R2_METHOD:
            actual_input += [r.signature,r.sufficiency]
            expected_input += [expected.r2_signature,expected.r2_sufficiency]
        if result.route != native_route or native_sha(actual_input)!=native_sha(expected_input):
            raise DispatchError('CHECK_BLOCKED', 'CONTRAST_ENDPOINT_INPUT_MISMATCH')
        before = native_sha(result)
        if core.replay_verified_business_outcome(result) is not True or native_sha(result) != before:
            raise DispatchError('CHECK_BLOCKED', 'CONTRAST_ENDPOINT_REPLAY_MISMATCH')
        results[side] = result
    if len(results) != 2:
        need = any(r['state'] == 'NEEDS_INPUT' or (r['reason_code'] or '').startswith('A4_') for r in out['attempts'])
        return dict(out, state='NEEDS_INPUT' if need else 'UNSUPPORTED',
                    reason_code='TWO_R2_ENDPOINTS_NOT_IDENTIFIED' if method==R2_METHOD else 'TWO_R1B_ENDPOINTS_NOT_IDENTIFIED',
                    nonidentification_proved=False, partial_fallback_performed=False)
    binding = dict(plan_sha256=plan['plan_sha256'], query_id=plan['query_id'], reviewed_inputs_sha256=original)
    certificate = composition.compose(results['first'], results['second'], target=target, binding=binding)
    before = sha(certificate); endpoints_before = native_sha(results)
    if (composition.replay(certificate, results['first'], results['second'], target=target, binding=binding) is not True
            or sha(certificate) != before or native_sha(results) != endpoints_before or native_sha(inquiries) != original):
        raise DispatchError('CHECK_BLOCKED', 'CONTRAST_COMPOSITION_REPLAY_MISMATCH')
    claim = dict(kind='POINT', representation='ORDERED_POLICY_OBSERVED_FUNCTIONAL',
        target=deepcopy(plan['proposed_target']), expression=certificate['identified_functional'], numeric_value=None)
    return _success(out, method, claim, certificate,
        dict(inquiries=canonical_data(inquiries), endpoints={s: results[s].summary() for s in SIDES}), original)


def _bounded(inquiries, information, plan, out):
    from . import bounded_contrast_contract as contract
    from . import bounded_contrast_solver as producer, bounded_contrast_verify as verifier
    validate,solve,replay,digest=contract.validate_pair,producer.solve,verifier.replay,contract.input_digest
    method=plan['methods'][0]['method']
    if method==COUNT_METHOD:
        from .bounded_count_contract import validate_pair as validate,input_digest as count_digest
        from .bounded_count_solver import solve_contrast as solve
        from .bounded_count_verify import replay_contrast as replay
        digest=lambda q,i:count_digest(q,i,'contrast')
    if method==FINITE_METHOD:
        from .bounded_finite_contract import validate_pair as validate,input_digest as finite_digest
        from .bounded_finite_solver import solve_contrast as solve
        from .bounded_finite_verify import replay_contrast as replay
        digest=lambda q,i:finite_digest(q,i,'contrast')
    validate(inquiries, information)
    original = digest(inquiries, information)
    out['backend_called'] = True
    certificate = solve(inquiries, information)
    before = sha(certificate)
    if (digest(inquiries, information) != original or
            replay(certificate, inquiries=inquiries, information=information) is not True or
            digest(inquiries, information) != original or sha(certificate) != before):
        raise DispatchError('CHECK_BLOCKED', 'JOINT_CONTRAST_INPUT_OR_REPLAY_MISMATCH')
    from .bounded_mean_formula import mathematical_claim
    claim=mathematical_claim(certificate,plan['proposed_target'])
    return _success(out, method, claim, certificate,
        dict(inquiries=canonical_data(inquiries), information=canonical_data(information)), original)


def _success(out, method, claim, certificate, native, inputs):
    answer = dict(method=method, mathematical_claim=claim, certificate=deepcopy(certificate),
        native_evidence=native, reviewed_input_sha256=inputs, independent_replay=True)
    return dict(out, state=claim['kind'], primary_method=method, mathematical_claim=deepcopy(claim),
        certificate=deepcopy(certificate), independent_replay=True, answers=[answer], partial_fallback_performed=False)


def _execute_plan(plan, *, plan_review=None, native_reviews=None, research_protocol_selected=False):
    out = dict(empty_result(), query_id=plan['query_id'], result_scope='SELECTED_QUERY_ONLY',
        remaining_query_ids=plan['remaining_query_ids'], fact_family=FAMILY,
        plan_sha256=plan['plan_sha256'], attempts=[])
    if plan.get('outcome_domain_embedding') is not None:
        out['outcome_domain_embedding'] = deepcopy(plan['outcome_domain_embedding'])
    if plan.get('information_evidence_receipt') is not None:
        out['information_evidence_receipt'] = deepcopy(plan['information_evidence_receipt'])
    try:
        if research_protocol_selected is not True:
            raise DispatchError('REVIEW_REQUIRED', 'EXPLICIT_RESEARCH_PROTOCOL_SELECTION_REQUIRED')
        review = checked_review(plan_review, plan['plan_worksheet'])
        if review.authority != plan['query_review']['authority']:
            raise DispatchError('CHECK_BLOCKED', 'DISPATCH_REVIEW_AUTHORITY_MISMATCH')
        if native_reviews is None:
            raise DispatchError('REVIEW_REQUIRED', 'CONTRAST_READING_AND_SCIENCE_REVIEWS_REQUIRED')
        if not plan['methods'] or (any(r['method'] in (*BOUNDED_METHODS,mean_order.METHOD) for r in plan['methods']) and len(plan['methods'])!=1):
            raise ValueError('EXACT_JOINT_METHOD_REQUIRED')
        by_method = native_reviews_from_json(plan,native_reviews)
        # Check every planned method before invoking either endpoint backend.
        for row in plan['methods']:
            if row['method'] not in (POINT_METHOD,R2_METHOD,*BOUNDED_METHODS,mean_order.METHOD):raise ValueError('UNKNOWN_CONTRAST_METHOD')
            records=by_method[row['method']]
            for key,field in (('reading_review','reading_worksheet'),('science_review','science_worksheet')):
                record=checked_review(records[key],row[field])
                if record.authority!=review.authority:
                    raise DispatchError('CHECK_BLOCKED','CONTRAST_REVIEW_AUTHORITY_MISMATCH')
                records[key]=record
        # Retain the existing comparison / finite-model synthetic research scope.
        if review.authority != 'SYNTHETIC_TEST':
            return dict(out, state='ADAPTER_NOT_CONNECTED', reason_code='CONTRAST_SYNTHETIC_REVIEW_SCOPE_ONLY')
        results=[]
        for row in plan['methods']:
            if row['method']==mean_order.METHOD:
                return mean_order.execute_reviewed(plan,row,by_method[row['method']],review.authority,out)
            inquiries,information=_compile_pair(plan,row,by_method[row['method']],review.authority)
            if row['method'] in BOUNDED_METHODS:return _bounded(inquiries,information,plan,out)
            branch=out if len(plan['methods'])==1 else dict(out,attempts=[])
            try:
                results.append(_point(inquiries,plan,branch,row['method']))
            finally:
                if branch is not out:
                    out['backend_called']=out['backend_called'] or branch['backend_called']
                    out['attempts'].extend(dict(a,method=row['method']) for a in branch['attempts'])
        if len(results)==1:return results[0]
        answers=[a for r in results for a in r['answers']]
        attempts=[dict(a,method=row['method']) for row,r in zip(plan['methods'],results) for a in r['attempts']]
        out.update(backend_called=any(r['backend_called'] for r in results),attempts=attempts)
        if answers:
            first=answers[0]
            return dict(out,state='POINT',answers=answers,primary_method=first['method'],
                mathematical_claim=deepcopy(first['mathematical_claim']),certificate=deepcopy(first['certificate']),
                independent_replay=True,partial_fallback_performed=False)
        return dict(out,state='NEEDS_INPUT' if any(r['state']=='NEEDS_INPUT' for r in results) else 'UNSUPPORTED',
            reason_code='NO_VERIFIED_POLICY_CONTRAST_METHOD',nonidentification_proved=False,partial_fallback_performed=False)
    except BoundedPolicyUnavailable as exc:
        return dict(out, state=exc.state, reason_code=exc.reason, diagnostic_only=True,
                    incompatibility_proved=False, partial_fallback_performed=False)
    except DispatchError as exc:
        return dict(out, state=exc.state, reason_code=exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
        return dict(out, state='CHECK_BLOCKED', reason_code='INVALID_CONTRAST_REVIEW_OR_NATIVE_EVIDENCE')
