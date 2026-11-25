"""Ordered-comparison record projection for the shared read-only diagnostics.

Checks record identity/coherence, never support, feasibility, proof or approval.
Endpoint composition and joint bounds retain their distinct native record shapes.
"""
from copy import deepcopy
from cfm_id_bridge.scientific_binding import sha
from . import network_contrast_dispatch as contrast
from . import network_policy_dispatch as policy, network_bounded_dispatch as bounded
from . import method_requirements as requirements
from . import network_mean_order_dispatch as orders

BASE_METHODS = {contrast.POINT_METHOD: policy.FULL_POLICY, contrast.SIGNATURE_METHOD: policy.SIGNATURE_POLICY,
                contrast.BOUNDED_METHOD: bounded.METHOD, orders.METHOD: orders.METHOD}
JOINT_METHODS = (contrast.BOUNDED_METHOD, orders.METHOD)
COORDINATES = ('node_order', 'first', 'second', 'unit_weights', 'operation')


def attempts(result, method_ids):
    """Keep both endpoint attempts; a single-method native record omits method."""
    grouped = {}
    for row in result.get('attempts', []):
        method = row.get('method')
        if method is None and len(method_ids) == 1:
            method = next(iter(method_ids))
        side = row.get('endpoint')
        if (method not in method_ids or method in JOINT_METHODS
                or side not in contrast.SIDES or side in grouped.get(method, {})):
            raise ValueError('DIAGNOSTIC_INVALID_CONTRAST_ENDPOINT_ATTEMPT')
        grouped.setdefault(method, {})[side] = deepcopy(row)
    out = {}
    for method, endpoints in grouped.items():
        states = [r.get('state') for r in endpoints.values()]
        state = ('POINT' if set(endpoints) == set(contrast.SIDES) and all(s == 'POINT' for s in states)
                 else 'NOT_APPLICABLE' if 'UNSUPPORTED' in states else 'NOT_ESTABLISHED')
        out[method] = dict(state=state, endpoint_attempts=endpoints)
    return out


def check_answer(plan, answer, attempt):
    """Match the reported certificate to the ordered question; not a verifier."""
    from .fixed_comparison import VERSION as r1b_version
    from .workflows.policy_difference import VERSION as r2_version
    from .bounded_contrast_contract import VERSION as joint_version, input_digest

    if answer['method'] == orders.METHOD:
        return _check_order_answer(plan, answer, attempt)
    try:
        target = plan['proposed_target']
        coordinates = {k: target[k] for k in COORDINATES}
        if coordinates['operation'] != 'first_minus_second':
            raise ValueError('direction')
        claim, cert, native = (answer[k] for k in ('mathematical_claim', 'certificate', 'native_evidence'))
        inquiries = native['inquiries']
        if set(inquiries) != set(contrast.SIDES):
            raise ValueError('endpoints')
        for side in contrast.SIDES:
            t, study = inquiries[side]['target'], inquiries[side]['study']
            if (t['policy_assignment'] != coordinates[side]
                    or any(t[k] != target[k] for k in ('node_order', 'unit_weights', 'outcome', 'context'))
                    or study['treatment_variable'] != target['treatment']):
                raise ValueError('endpoint target')
        if answer['method'] == contrast.BOUNDED_METHOD:
            # The native joint solver has no per-endpoint solve attempts.
            information = native['information']
            if (attempt or set(information) != set(contrast.SIDES) or cert['version'] != joint_version
                    or cert['input_sha256'] != answer['reviewed_input_sha256']
                    or cert['input_sha256'] != input_digest(inquiries, information)
                    or cert['target_sha256'] != sha(coordinates)
                    or claim['target_sha256'] != cert['target_sha256']
                    or claim['interval'] != [cert['lower'], cert['upper']]
                    or any(claim[k] != cert[k] for k in ('width', 'sharp', 'informative', 'logical_range'))
                    or claim['kind'] != cert['status']):
                raise ValueError('joint record')
        else:
            expected_version = {contrast.POINT_METHOD: r1b_version, contrast.SIGNATURE_METHOD: r2_version}[answer['method']]
            endpoints = native['endpoints']
            expected_binding = dict(plan_sha256=plan['plan_sha256'], query_id=plan['query_id'],
                                    reviewed_inputs_sha256=answer['reviewed_input_sha256'])
            if (not attempt or attempt['state'] != 'POINT' or claim['kind'] != 'POINT'
                    or set(endpoints) != set(contrast.SIDES) or cert['version'] != expected_version
                    or cert['target'] != coordinates or cert['binding'] != expected_binding
                    or sha(inquiries) != answer['reviewed_input_sha256']
                    or cert['endpoint_sha256'] != {s: sha(endpoints[s]) for s in contrast.SIDES}
                    or claim['expression'] != cert['identified_functional']):
                raise ValueError('composition record')
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError('DIAGNOSTIC_INCOHERENT_CONTRAST_RECORD') from exc


def _check_order_answer(plan, answer, attempt):
    from .mean_order_contract import MeanOrderProblem, VERSION, input_digest
    try:
        cert, claim = answer['certificate'], answer['mathematical_claim']
        p = MeanOrderProblem.model_validate(answer['native_evidence']['problem'])
        t = plan['proposed_target']
        if (attempt or cert['version']!=VERSION or input_digest(p)!=answer['reviewed_input_sha256']
                or cert['input_sha256']!=input_digest(p) or claim['target_sha256']!=sha(t)
                or p.first!=t['first'] or p.second!=t['second'] or p.weights!=t['unit_weights']
                or p.node_order!=t['node_order'] or p.context!=t['context']
                or p.outcome_definition!=t['outcome'] or p.treatment_definition!=t['treatment']
                or p.operation!='FIRST_MINUS_SECOND' or t['operation']!='first_minus_second'
                or claim['interval']!=[cert['lower'],cert['upper']] or claim['kind']!=cert['status']
                or any(claim[k]!=cert[k] for k in ('width','sharp','baseline_bounds_only_range',
                                                 'informative_relative_to_bounds_only'))):
            raise ValueError('order record')
    except (KeyError,TypeError,ValueError,AttributeError) as exc:
        raise ValueError('DIAGNOSTIC_INCOHERENT_MEAN_ORDER_RECORD') from exc


def comparison_view(plan):
    target = plan.get('proposed_target') or {}
    return dict(declared_target=deepcopy(plan.get('contrast_target')),
        ordered_coordinates={k: deepcopy(target[k]) for k in COORDINATES if k in target},
        common_scope={k: deepcopy(target[k]) for k in ('node_order', 'unit_weights', 'treatment', 'outcome', 'context') if k in target},
        review_keys=list(contrast.PAIR_DECISIONS),
        origin='CURRENT_NATIVE_PLAN', checked_here=False,
        note='保留第一政策减第二政策、原始两端名单及原生共同坐标；不自动补齐或对齐不同范围。')


def decorate(item, plan, answer, result=None):
    """Surface missing declarations at the actual endpoint, not a guessed gap."""
    base_method = BASE_METHODS.get(item['method'])
    item['endpoint_plans'] = {}
    for side, endpoint in plan.get('endpoint_plans', {}).items():
        exclusion = next((r for r in endpoint.get('exclusions', []) if r['method'] == base_method), None)
        item['endpoint_plans'][side] = dict(state=endpoint.get('state'),
            source_reason=requirements.reason(endpoint.get('reason_code')),
            method_planned=any(r['method'] == base_method for r in endpoint.get('methods', [])),
            method_exclusion=deepcopy(exclusion),
            exclusion_reason=requirements.reason(exclusion.get('reason_code')) if exclusion else None,
            target=deepcopy(endpoint.get('proposed_target')))
    item['calculation_contract'] = ('JOINT_CONTRAST_IN_ONE_MODEL' if item['method'] in JOINT_METHODS
                                    else 'TWO_ENDPOINTS_AND_ORDERED_COMPOSITION')
    if (not answer and item['method'] in JOINT_METHODS and result is not None
            and result.get('backend_called') is True
            and [r['method'] for r in plan.get('methods', [])] == [item['method']]):
        # Native joint failures have no endpoint attempts. Preserve the actual call.
        item['execution'] = 'EXECUTOR_REPORTED_ATTEMPT'
        item['mathematical_applicability'] = 'NOT_ESTABLISHED'
        item['native_attempt'] = dict(state=result['state'], reason_code=result.get('reason_code'),
                                      origin='JOINT_EXECUTOR_RECORD')
        item['reason'] = requirements.reason(result.get('reason_code'))
    if answer:
        item['certificate']['calculation_reported'] = item['calculation_contract']
        item['certificate']['separate_interval_subtraction'] = False
