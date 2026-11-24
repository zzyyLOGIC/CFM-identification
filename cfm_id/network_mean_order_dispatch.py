"""Reviewed comparison facts -> the existing finite mean-order backend.

This module adapts records only. Solver, feasibility analysis and independent
replay remain in the unchanged mean_order mathematical implementation.
"""
from copy import deepcopy
import json
from .business_dispatch import sha, DispatchError
from .mean_order_contract import (MeanOrderProblem, ReviewedMeanOrder,
    VERSION, MODEL, SCOPE, input_digest)

METHOD = 'MEAN_ORDER_D2_E1'
ORDER_DECISIONS = ('only_declared_mean_orders_and_bounds',
                   'mean_order_outcome_axes_scope_and_assumption_basis')


def axis_decision(node, axis):
    return 'mean_order_axis:' + json.dumps([node, axis], ensure_ascii=False, separators=(',', ':'))


def model_decisions(nodes):
    from .network_bounded_dispatch import MODEL_DECISIONS
    return (*MODEL_DECISIONS[:2], MODEL_DECISIONS[3], *ORDER_DECISIONS,
            *(axis_decision(n, a) for n in nodes for a in ('OWN', 'PEERS')))


def inspect_reading(entry, decoded):
    from cfm_id_llm.network_mean_order_reading import NetworkMeanOrderModel, project_model
    model = NetworkMeanOrderModel.model_validate(decoded['mean_order_model'])
    nodes = decoded['endpoint_readings']['first']['facts']['study']['nodes']
    projection = project_model(entry['bundle'], model.model_dump(), nodes)
    return dict(model=model, projection=projection)


def compile_reviewed(plan, row, records, authority):
    from . import network_policy_dispatch as policy
    from . import research_spec_policy_adapters as policy_attributes
    from cfm_id_llm.network_policy_reading import NetworkPolicyReading
    from cfm_id_bridge.scientific_binding import canonical_data
    question = policy_attributes.from_endpoint_plans(plan['endpoint_plans'])
    question.require_coordinates(plan['proposed_target'])
    # Compile both endpoints through the same reviewed native target/A4/A5
    # constructors as the existing contrast. Do not create mean-box evidence.
    compiled = {s: policy._compile(dict(plan['endpoint_plans'][s], plan_sha256=plan['plan_sha256']),
        dict(row, method=policy.R2), records, authority) for s in ('first', 'second')}
    first, second = compiled['first'], compiled['second']
    if any(sha(canonical_data(first[i])) != sha(canonical_data(second[i])) for i in (0, 2, 3, 4, 5)):
        raise DispatchError('CHECK_BLOCKED', 'MEAN_ORDER_COMMON_MODEL_MISMATCH')
    c = NetworkPolicyReading.model_validate(plan['endpoint_plans']['first']['facts'])
    information = [c.information[i] for i in row['source_indices']]
    b = c.bounded_model
    t = plan['proposed_target']
    for side, values in compiled.items():
        target = values[1]
        if (list(target.policy_assignment) != t[side] or list(target.node_order) != t['node_order']
                or list(target.unit_weights) != t['unit_weights'] or target.outcome != t['outcome']
                or target.context != t['context']):
            raise DispatchError('CHECK_BLOCKED', 'MEAN_ORDER_TARGET_BINDING_MISMATCH')
    if b.outcome_definition != c.study.outcome:
        raise DispatchError('CHECK_BLOCKED', 'MEAN_ORDER_OUTCOME_DEFINITION_MISMATCH')
    context = plan['endpoint_plans']['first']['mean_order_context']
    if context != plan['endpoint_plans']['second']['mean_order_context']:
        raise DispatchError('CHECK_BLOCKED', 'MEAN_ORDER_COMMON_ASSUMPTIONS_MISMATCH')
    provenance = 'Reviewed source/target/science plan: ' + plan['plan_sha256']
    return MeanOrderProblem(version=VERSION, model_scope=MODEL,
        node_order=list(first[0].node_order), undirected_edges=[list(e) for e in c.study.edges],
        graph_scope='KNOWN_FIXED_PRETREATMENT_SIMPLE_UNDIRECTED',
        design='D2_UNIFORM_FIXED_QUOTA', quota=c.assignment.fixed_count,
        exposure='E1_STRICT_MAJORITY_TIES_LOW_ISOLATED_ZERO',
        context=c.study.context, treatment_definition=c.study.treatment,
        outcome_definition=c.study.outcome, outcome_kind=c.study.outcome_kind.lower(),
        outcome_unit=b.outcome_unit, outcome_period=b.outcome_period,
        order_direction='NONDECREASING_NUMERIC_OUTCOME_MEAN', order_scope=SCOPE,
        node_orders=context['projection']['proposed_node_orders'],
        randomization_claim='WHOLE_ASSIGNMENT_INDEPENDENT_OF_ALL_POTENTIAL_OUTCOMES_GIVEN_CONTEXT',
        consistency_claim='OBSERVED_OUTCOME_EQUALS_ASSIGNED_POTENTIAL_OUTCOME',
        moments_claim='FINITE_FIRST_MOMENTS', mean_sufficiency_scope=SCOPE,
        mean_sufficiency_claim='NODE_OWN_AND_E1_SIGNATURE_DETERMINES_CONDITIONAL_MEAN',
        information_scope='EXACT_LISTED_SIGNATURE_MEANS_ONLY', availability='EXACT_POPULATION_VALUE',
        values=[dict(node=v.node, own=v.own, exposure=v.exposure, value=v.value)
                for s in information for v in s.signature_cells],
        a4_source='Source table: ' + sha([s.model_dump() for s in information]),
        a4_provenance=provenance + '; exact information: ' + sha(b.listed_means_are_complete_information.model_dump()),
        bounds=[dict(node=v.node, lower=v.lower, upper=v.upper) for v in b.bounds],
        bounds_kind=b.bounds_kind, bounds_scope=b.bounds_scope,
        bounds_provenance=provenance + '; bounds: ' + sha(b.model_dump()),
        first=t['first'], second=t['second'], weights=t['unit_weights'], operation='FIRST_MINUS_SECOND',
        scientific_provenance=provenance + '; per-axis review: ' + sha(context))


def execute_reviewed(plan, row, records, authority, out):
    from . import mean_order as backend, mean_order_verify as verifier
    from .network_contrast_dispatch import _success
    if authority != 'SYNTHETIC_TEST':
        raise DispatchError('ADAPTER_NOT_CONNECTED', 'CONTRAST_SYNTHETIC_REVIEW_SCOPE_ONLY')
    problem = compile_reviewed(plan, row, records, authority)
    original = input_digest(problem)
    record = records['science_review']
    review = ReviewedMeanOrder(version=VERSION, problem_sha256=original,
        reviewer=record.reviewer, evidence=record.evidence + '; checked common review: ' + record.binding_sha256,
        reviewed_target_direction_population=True, reviewed_complete_a4_and_no_unmodeled_constraints=True,
        reviewed_base_assumptions_and_all_arrangement_scope=True, reviewed_bounds_and_each_order_axis=True,
        synthetic_fixture=True)
    result = backend.submit(problem, review=review, synthetic_protocol_selected=True)
    out['backend_called'] = result['bounded_backend_called']
    if input_digest(problem) != original:
        raise DispatchError('CHECK_BLOCKED', 'MEAN_ORDER_INPUT_MUTATED')
    cert = result.get('bounded_result') or result.get('incompatibility_certificate')
    if cert is None:
        return dict(out, state=result['state'], reason_code=result.get('reason_code'),
                    partial_fallback_performed=False, incompatibility_proved=False)
    cert_hash = sha(cert)
    if (result['bounded_certificate_replayed'] is not True
            or verifier.replay(cert, problem=problem) is not True
            or input_digest(problem) != original or sha(cert) != cert_hash):
        raise DispatchError('CHECK_BLOCKED', 'MEAN_ORDER_INPUT_OR_REPLAY_MISMATCH')
    native = dict(problem=problem.model_dump(), review=review.model_dump())
    if cert['status'] == 'INCOMPATIBLE':
        return dict(out, state='INCOMPATIBLE', primary_method=METHOD,
            reason_code='VERIFIED_EMPTY_MEAN_ORDER_MODEL', incompatibility_proved=True,
            incompatibility_certificate=deepcopy(cert), native_evidence=native,
            reviewed_input_sha256=original, independent_replay=True, partial_fallback_performed=False)
    interval = [cert['lower'], cert['upper']]
    claim = dict(kind=cert['status'], representation='EXACT_IDENTIFIED_INTERVAL',
        target=deepcopy(plan['proposed_target']), target_sha256=sha(plan['proposed_target']),
        interval=interval, width=cert['width'], sharp=cert['sharp'],
        baseline_bounds_only_range=deepcopy(cert['baseline_bounds_only_range']),
        informative_relative_to_bounds_only=cert['informative_relative_to_bounds_only'],
        sharp_relative_to_reviewed_model=MODEL,
        numeric_value=interval[0] if cert['status']=='POINT' else None)
    return _success(out, METHOD, claim, cert, native, original)
