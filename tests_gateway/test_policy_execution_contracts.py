"""Execution bindings are shared; a new registration cannot grant applicability."""
from dataclasses import replace
import json

import pytest

from cfm_id import capability_registry, policy_methods as methods
from cfm_id import policy_execution as execution


def forbidden(*args, **kwargs):
    pytest.fail('No native calculation permitted')


@pytest.mark.parametrize('operation,reader_id', [
    (methods.MEAN, 'NETWORK_FIXED_POLICY_FACTS'),
    (methods.DIFFERENCE, 'NETWORK_POLICY_CONTRAST_FACTS'),
])
def test_registry_and_execution_resolve_the_same_live_functions(operation, reader_id, monkeypatch):
    from cfm_id import bounded_policy_solver, bounded_contrast_solver
    module = bounded_policy_solver if operation == methods.MEAN else bounded_contrast_solver
    monkeypatch.setattr(module, 'solve', forbidden)
    binding = next(b for b in capability_registry.business_bindings() if b.reader_id == reader_id)
    contracts = methods.methods(operation)
    assert [b.method_id for b in binding.methods] == [m.method_id for m in contracts]
    for registered in binding.methods:
        resolved = methods.resolve(registered.method_id, operation)
        assert registered.producers == resolved.producers
        assert registered.replayers == resolved.replayers
        assert registered.native_route_ids == resolved.native_route_ids
    assert forbidden in {f for m in binding.methods for f in m.producers}


@pytest.mark.parametrize('method,operation', [
    ('unknown', methods.MEAN),
    (methods.R1B, methods.DIFFERENCE),
    (methods.R1B_DIFFERENCE, methods.MEAN),
])
def test_unregistered_or_wrong_target_method_is_not_a_default_branch(method, operation):
    with pytest.raises(ValueError, match='POLICY_METHOD_OPERATION_MISMATCH'):
        methods.resolve(method, operation)
    if operation == methods.MEAN:
        with pytest.raises(ValueError, match='POLICY_METHOD_OPERATION_MISMATCH'):
            execution.point_solution(method, ())


def test_new_point_registration_requires_its_own_call_contract(monkeypatch):
    contract = replace(methods.resolve(methods.R1B, methods.MEAN), method_id='NEW_METHOD',
                       kernel=methods.Kernel(forbidden, forbidden))
    monkeypatch.setattr(methods, 'resolve', lambda *args: contract)
    with pytest.raises(ValueError, match='POLICY_POINT_CALL_CONTRACT_REQUIRED'):
        execution.point_solution('NEW_METHOD', (None,) * 6)


def test_plan_cannot_mix_distinct_joint_models_or_silently_map_an_unknown_endpoint():
    # Both point proofs may be proposed; a joint constrained problem stays intact.
    methods.require_plan([{'method': methods.R1B}, {'method': methods.R2}], methods.MEAN)
    with pytest.raises(ValueError, match='EXACT_JOINT_POLICY_MODEL_REQUIRED'):
        methods.require_plan([{'method': methods.R1B},
            {'method': 'BOUNDED_POLICY_MEAN_D2_E1'}], methods.MEAN)
    with pytest.raises(ValueError, match='NO_REGISTERED_POLICY_DIFFERENCE'):
        methods.difference_for('unknown')


@pytest.mark.parametrize('mutation', ['producer_input', 'replay_input', 'replay_certificate', 'replay_false'])
def test_shared_bound_execution_rejects_changed_inputs_or_evidence(mutation, monkeypatch):
    inquiry, information = {'target': 'first minus second'}, {'known': '1/2'}
    calls = []

    def produce(question, info):
        calls.append('produce')
        if mutation == 'producer_input':
            question['target'] = 'different target'
        return {'interval': ['0', '1']}

    def replay(certificate, **inputs):
        calls.append('replay')
        assert inputs['inquiries'] is inquiry and inputs['information'] is information
        if mutation == 'replay_input':
            information['known'] = '1'
        if mutation == 'replay_certificate':
            certificate['interval'] = ['1', '1']
        return mutation != 'replay_false'

    contract = methods.PolicyMethod('TEST', methods.DIFFERENCE, methods.BOX, (), methods.Kernel(
        produce, replay, lambda *args: calls.append('validate'),
        lambda question, info: json.dumps([question, info], sort_keys=True)))
    monkeypatch.setattr(methods, 'resolve', lambda *args: contract)
    with pytest.raises(execution.PolicyEvidenceMismatch):
        execution.bounded_solution('TEST', methods.DIFFERENCE, inquiry, information,
            before_compute=lambda: calls.append('compute'))
    assert calls[:3] == ['validate', 'compute', 'produce']


def test_native_validation_failure_never_marks_or_starts_computation(monkeypatch):
    def reject(*args):
        raise ValueError('MISSING_MATHEMATICAL_CONDITION')

    contract = methods.PolicyMethod('TEST', methods.MEAN, methods.BOX, (),
        methods.Kernel(forbidden, forbidden, reject, forbidden))
    monkeypatch.setattr(methods, 'resolve', lambda *args: contract)
    with pytest.raises(ValueError, match='MISSING_MATHEMATICAL_CONDITION'):
        execution.bounded_solution('TEST', methods.MEAN, {}, {}, before_compute=forbidden)
