"""One declared DAG model, several existing sufficient-method checks.

All projections are explicit. Requested roles constrain the method search, not
the scientific model. No route is allowed to bypass a pending/rejected review.
"""
from copy import deepcopy
import re
from cfm_id_llm.dag_frontdoor_reading import parse
from . import dag_business as native
from . import dag_methods
from .business_dispatch import (sha, worksheet, checked_review, empty_result,
                                DispatchError, PLAN_DECISIONS)

METHODS = dag_methods.METHOD_IDS


def _legacy_binary_view(entry, target):
    """Bind only values explicitly assigned to the selected treatment in the reviewed question."""
    question=entry['bundle']['question']
    if entry.get('remaining_query_ids') or not target.treatment or not target.outcome or target.outcome not in question:
        return None
    if not re.search(r'(总体|干预|概率)分布',question) or re.search(r'分别比较|相减|多少差|差值',question):
        return None
    pattern=(r'[“「"]?'+re.escape(target.treatment)+r'[”」"]?(?:分别)?(?:统一)?(?:设为|置为|设定为)'
             r'\s*([01])(?:\s*[和与、]\s*([01]))?(?=\s*[，,。；、？?时])')
    matches=list(re.finditer(pattern,question))
    if len(matches)!=1 or len(re.findall(r'设为|置为|设定为',question))!=1:
        return None
    match=matches[0]
    if re.match(r'\s*[、，,]\s*\d',question[match.end():]):
        return None
    values=[int(v) for v in match.groups() if v is not None]
    if len(set(values))==len(values):
        from .source_locations import build_catalog
        locations=build_catalog({'__question__':question})
        ids=[sid for sid,row in locations.items() if row['start']<=match.start() and match.end()<=row['end']]
        if len(ids)==1:
            return dict(kind='TREATMENT_VALUES',values=values,source_ids=ids)


def inspect_methods(entry, candidate):
    out = dict(empty_result(), query_id=entry['query_id'], result_scope='SELECTED_QUERY_ONLY',
               remaining_query_ids=deepcopy(entry['remaining_query_ids']), request_sha256=entry['request_sha256'],
               method_matching='PREPARING_REVIEW', methods=[], exclusions=[],
               bundle=deepcopy(entry['bundle']), query_review=deepcopy(entry['query_review']))
    try:
        native_candidate = candidate
        if entry.get('reference_format') == 'short_refs':
            from cfm_id_llm.fact_reading_contracts import contract_for_entry
            contract = contract_for_entry(entry)
            if contract is None:raise ValueError('DAG_READING_CONTRACT_REQUIRED')
            projection = contract.parse_candidate(entry, candidate)
            native_candidate = projection['native_candidate']
            out.update(projection)
            out['reading_candidate'] = deepcopy(candidate)
            if projection['query_scope']['kind'] == 'UNKNOWN':
                return dict(out, state='NEEDS_INPUT', reason_code='QUERY_INTERVENTION_SCOPE_UNRESOLVED',
                    clarification_questions=['请先核对原文：这个子问题要查看哪些干预取值，还是整个干预分布函数？'])
            if projection['query_scope']['kind'] == 'OTHER':
                return dict(out, state='ADAPTER_NOT_CONNECTED', reason_code='QUERY_SCOPE_OUTSIDE_KERNEL_VIEW')
        c = parse(entry['bundle'], native_candidate)
        if 'query_scope' not in out:
            scope=_legacy_binary_view(entry,c.target)
            if scope:
                out['query_scope']=scope
        out['reading_candidate'] = deepcopy(candidate)
        choice = c.frontdoor_choice.status
        if choice == 'UNDECIDED':
            return dict(out, state='NEEDS_INPUT', reason_code='REQUESTED_METHOD_ROLE_UNDECIDED',
                        clarification_questions=['请核对原文中尚未决定的方法角色要求；不能把未决定当成允许搜索。'])
        if choice == 'SPECIFIED' and c.adjustment is not None:
            return dict(out, state='ADAPTER_NOT_CONNECTED', reason_code='COMBINED_FRONTDOOR_AND_ADJUSTMENT_REQUEST')
        # These rules preserve explicit user restrictions; none asserts a theorem.
        from .method_preparation import dag_roles
        permitted = []
        for selection in dag_roles(frontdoor_status=choice, specified_adjustment=c.adjustment is not None):
            if selection.reason_code:
                out['exclusions'].append(dict(method=selection.method, reason_code=selection.reason_code))
            else:
                permitted.append(selection.method)
        for method in permitted:
            wire = deepcopy(native_candidate)
            projection = 'UNCHANGED_COMMON_READING'
            if method != native.FRONTDOOR_ROUTE:
                wire.pop('frontdoor_choice')
                wire['version'] = 'dag-reading-1'
                projection = 'COMMON_FIELDS_ONLY_ROLE_RESTRICTION_RETAINED_IN_DISPATCH_PLAN'
            view = native.inspect_candidate(entry['bundle'], wire, route_id=method)
            row = {key: deepcopy(view.get(key)) for key in (
                'state', 'reason_code', 'clarification_questions', 'unsupported_reasons',
                'proposed_problem', 'reading_worksheet', 'science_worksheet')}
            out['methods'].append(dict(row, method=method, candidate=wire, projection=projection,
                                       applicability='NOT_CHECKED_BEFORE_SCIENCE_REVIEW'))
        # Shared model declaration failures block the whole plan, never just one
        # branch that could otherwise silently ignore part of the model.
        stops = [row for row in out['methods'] if row['state'] != 'REVIEW_REQUIRED']
        if stops:
            first = next((r for r in stops if r['state'] == 'CHECK_BLOCKED'), stops[0])
            questions = list(dict.fromkeys(q for row in stops for q in (row['clarification_questions'] or [])))
            return dict(out, state=first['state'], reason_code=first['reason_code'], clarification_questions=questions)
        if not out['methods']:
            raise DispatchError('ADAPTER_NOT_CONNECTED', 'NO_CONNECTED_METHOD_RESPECTS_REQUEST')
        # Bind the full original candidate as well as projections; changing a
        # role field must invalidate approval even if a common projection is equal.
        bound=dict(entry=entry, candidate=candidate, methods=out['methods'], exclusions=out['exclusions'])
        if entry.get('reference_format')!='short_refs' and out.get('query_scope'):
            bound['query_scope']=out['query_scope']
        binding = sha(bound)
        return dict(out, state='REVIEW_REQUIRED', plan_sha256=binding,
                    plan_worksheet=worksheet(binding, PLAN_DECISIONS + (
                        ('requested_intervention_values_and_kernel_view',) if 'query_scope' in out else ())))
    except DispatchError as exc:
        return dict(out, state=exc.state, reason_code=exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError):
        return dict(out, state='CHECK_BLOCKED', reason_code='INVALID_SOURCE_BOUND_DAG_READING')


def _preflight_reviews(plan, records, authority):
    """Validate every approval before invoking any solver. Native gates repeat."""
    if records is None:
        raise DispatchError('REVIEW_REQUIRED', 'NATIVE_READING_AND_SCIENCE_REVIEWS_REQUIRED')
    expected = {row['method'] for row in plan['methods']}
    if type(records) is not dict or set(records) != expected:
        raise DispatchError('CHECK_BLOCKED', 'EXACT_PLANNED_NATIVE_REVIEWS_REQUIRED')
    statuses, typed = [], {}
    for row in plan['methods']:
        method = row['method']
        pair = records[method]
        if type(pair) is not dict or set(pair) != {'reading_review', 'science_review'}:
            raise DispatchError('CHECK_BLOCKED', 'EXACT_NATIVE_REVIEW_PAIR_REQUIRED')
        classes = dict(reading_review=native.reading_contract(method)[2],
                       science_review=native.route_contract(method)[1])
        sheets = dict(reading_review=row['reading_worksheet'], science_review=row['science_worksheet'])
        typed[method] = {}
        for name, cls in classes.items():
            record = pair[name]
            if type(record) is not cls:
                raise DispatchError('CHECK_BLOCKED', 'TYPED_NATIVE_REVIEW_REQUIRED')
            r = cls.model_validate(record.model_dump())
            sheet = sheets[name]
            if not r.reviewer.strip() or not r.evidence.strip() or r.authority != authority:
                raise DispatchError('CHECK_BLOCKED', 'NATIVE_REVIEW_AUTHORITY_OR_IDENTITY_MISMATCH')
            if set(r.decisions) != set(sheet['decisions']):
                raise DispatchError('CHECK_BLOCKED', 'EXACT_NATIVE_REVIEW_DECISIONS_REQUIRED')
            for key, value in sheet.items():
                if key not in ('decisions', 'is_approval') and getattr(r, key) != value:
                    raise DispatchError('CHECK_BLOCKED', 'STALE_NATIVE_REVIEW')
            statuses.extend(r.decisions.values())
            typed[method][name] = r
    if 'REJECTED' in statuses:
        raise DispatchError('CHECK_BLOCKED', 'NATIVE_REVIEW_REJECTED_NO_METHOD_BYPASS')
    if 'PENDING' in statuses:
        raise DispatchError('REVIEW_REQUIRED', 'NATIVE_REVIEW_PENDING_NO_METHOD_BYPASS')
    return typed


def native_reviews_from_json(plan, records):
    """Deserialize explicit reviewer records; no field defaults to ACCEPTED."""
    if type(records) is not dict or set(records) != {r['method'] for r in plan['methods']}:
        raise ValueError('EXACT_PLANNED_NATIVE_REVIEWS_REQUIRED')
    result = {}
    for row in plan['methods']:
        method = row['method']; pair = records[method]
        if type(pair) is not dict or set(pair) != {'reading_review', 'science_review'}:
            raise ValueError('EXACT_NATIVE_REVIEW_PAIR_REQUIRED')
        result[method] = dict(reading_review=native.reading_contract(method)[2].model_validate(pair['reading_review']),
                             science_review=native.route_contract(method)[1].model_validate(pair['science_review']))
    return result


def _kernel_view(plan, problem, claim, certificate):
    """Select only the free intervention argument of an already verified kernel.

    We do not substitute variable names through the expression. In particular,
    a front-door formula's inner treatment marginal remains a bound summation.
    The original full-kernel claim and certificate remain unchanged.
    """
    scope = plan.get('query_scope')
    if scope is None:
        return None  # Legacy explicit single-query contract.
    from cfm_id_llm.dag_query_reading import QueryScope
    scope = QueryScope.model_validate(scope)
    if scope.kind not in ('ALL_TREATMENT_VALUES', 'TREATMENT_VALUES') or problem.variable_domain != 'BINARY':
        raise DispatchError('CHECK_BLOCKED', 'INVALID_VERIFIED_KERNEL_SCOPE')
    expected = dict(kind='INTERVENTIONAL_DISTRIBUTION', treatment=problem.treatment,
                    outcome=problem.outcome, context=problem.context)
    if claim.get('target') != expected or certificate.get('target') != expected:
        raise DispatchError('CHECK_BLOCKED', 'QUERY_KERNEL_TARGET_MISMATCH')
    return dict(operation='SELECT_FREE_INTERVENTION_ARGUMENT', target=expected,
                requested_scope=scope.kind,
                intervention_values=list(scope.values) if scope.kind == 'TREATMENT_VALUES' else [0, 1],
                outcome_values=[0, 1], verified_kernel_domain=[0, 1],
                kernel_claim_sha256=sha(claim), certificate_sha256=sha(certificate),
                kernel_view_checked=True, numeric_value=None,
                scope_note='Argument selection only. Original kernel and all bound sums are unchanged; source meaning needs independent review.')


def _execute_plan(plan, *, plan_review=None, native_reviews=None, research_protocol_selected=False):
    # Called only with a newly recomputed plan by business_dispatch.execute.
    out = dict(empty_result(), query_id=plan['query_id'], result_scope='SELECTED_QUERY_ONLY',
               remaining_query_ids=deepcopy(plan['remaining_query_ids']), plan_sha256=plan['plan_sha256'],
               method_matching='NOT_EXECUTED', exclusions=deepcopy(plan['exclusions']), attempts=[])
    if research_protocol_selected is not True:
        return dict(out, state='REVIEW_REQUIRED', reason_code='EXPLICIT_RESEARCH_PROTOCOL_SELECTION_REQUIRED')
    try:
        review = checked_review(plan_review, plan['plan_worksheet'])
        if review.authority != plan['query_review']['authority']:
            raise DispatchError('CHECK_BLOCKED', 'DISPATCH_REVIEW_AUTHORITY_MISMATCH')
        records = _preflight_reviews(plan, native_reviews, review.authority)
        answers = []
        for row in plan['methods']:
            method = row['method']
            materials, wire, approvals = deepcopy(plan['bundle']), deepcopy(row['candidate']), deepcopy(records[method])
            def submission_hash():
                return sha(dict(bundle=materials, candidate=wire,
                                reviews={k: v.model_dump(mode='json') for k, v in approvals.items()}))
            before = submission_hash()
            result = native.submit_reviewed(materials, wire, route_id=method,
                                            **approvals, research_protocol_selected=True)
            if submission_hash() != before:
                raise DispatchError('CHECK_BLOCKED', 'METHOD_SUBMISSION_MUTATED_INPUT')
            out['backend_called'] |= result.get('backend_called') is True
            out['attempts'].append(dict(method=method, state=result['state'], reason_code=result.get('reason_code'),
                                        independent_replay=result.get('independent_replay') is True))
            if result['state'] == 'POINT':
                if result.get('independent_replay') is not True or not result.get('certificate') or not result.get('mathematical_claim'):
                    raise DispatchError('CHECK_BLOCKED', 'METHOD_SUCCESS_WITHOUT_VERIFIED_EVIDENCE')
                # Native submission already replays. Repeat publication verification
                # against this exact plan object to reject altered returned claims.
                binding = dag_methods.resolve(method)
                adapter = binding.adapter_type(); p = binding.problem_type.model_validate(row['proposed_problem'])
                cert = deepcopy(result['certificate']); claim = deepcopy(result['mathematical_claim'])
                cert_hash, problem_hash, claim_hash = sha(cert), sha(p.model_dump()), sha(claim)
                if adapter.verify_claim(cert, claim) is not True or adapter.replay(p, cert) is not True:
                    raise DispatchError('CHECK_BLOCKED', 'METHOD_CLAIM_OR_REPLAY_FAILED')
                if sha(cert) != cert_hash or sha(p.model_dump()) != problem_hash or sha(claim) != claim_hash:
                    raise DispatchError('CHECK_BLOCKED', 'METHOD_VERIFICATION_MUTATED_EVIDENCE')
                answer = dict(method=method, mathematical_claim=claim, certificate=cert, independent_replay=True)
                view = _kernel_view(plan, p, claim, cert)
                if view is not None:
                    answer['query_view'] = view
                answers.append(answer)
            elif result['state'] != 'UNSUPPORTED':
                raise DispatchError(result['state'] if result['state'] in ('NEEDS_INPUT', 'REVIEW_REQUIRED', 'CHECK_BLOCKED')
                                    else 'CHECK_BLOCKED', result.get('reason_code') or 'METHOD_EXECUTION_REJECTED')
        out['method_matching'] = 'CHECKED_BY_NATIVE_BACKENDS'
        if answers:
            # Stable presentation order only; all successful proofs remain visible.
            return dict(out, state='POINT', answers=answers, independent_replay=True,
                        primary_method=answers[0]['method'],
                        mathematical_claim=deepcopy(answers[0]['mathematical_claim']),
                        certificate=deepcopy(answers[0]['certificate']))
        return dict(out, state='UNSUPPORTED', reason_code='NO_CONNECTED_SUFFICIENT_METHOD_SUCCEEDED',
                    nonidentification_proved=False)
    except DispatchError as exc:
        return dict(out, state=exc.state, reason_code=exc.reason, answers=[], independent_replay=False)
    except (ValueError, TypeError, KeyError, AttributeError):
        return dict(out, state='CHECK_BLOCKED', reason_code='INVALID_DISPATCH_REVIEW_OR_NATIVE_EVIDENCE',
                    answers=[], independent_replay=False)
