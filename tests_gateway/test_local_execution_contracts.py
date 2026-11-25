"""Shared local calls preserve distinct targets and actual evidence binding."""
from dataclasses import dataclass

import pytest

from cfm_id import business_dispatch as dispatch, capability_registry
from cfm_id import local_execution as execution, local_methods as methods
from examples import network_extended_reference as arm


def forbidden(*args, **kwargs):
    pytest.fail('Unexpected native calculation')


@pytest.mark.parametrize('operation,reader', [
    (methods.ARM_MEAN, 'NETWORK_RANDOMIZED_ARM_FACTS'),
    (methods.DIFFERENCE, 'NETWORK_RANDOMIZED_EFFECT_FACTS'),
])
def test_registry_and_calls_use_the_same_live_binding(monkeypatch, operation, reader):
    from pfn_pipeline import identification_business as core
    original = core.identify_network_business_query
    called = []

    def identify(inquiry):
        called.append(type(inquiry).__name__)
        return original(inquiry)

    monkeypatch.setattr(core, 'identify_network_business_query', identify)
    binding = capability_registry.business_binding(reader)
    assert len(binding.methods) == 1
    row = binding.methods[0]
    method = methods.resolve(row.method_id, operation)
    assert row.producers == method.producers and row.replayers == method.replayers
    assert row.native_route_ids == method.native_route_ids
    assert identify in row.producers
    if operation == methods.ARM_MEAN:
        s,o,p = arm.setup('arm')
    else:
        from examples.network_effect_dispatch_reference import setup
        s,e,o,p = setup()
    from examples.network_effect_dispatch_reference import approval_records
    result = dispatch.execute(s, 'q1', **o, **approval_records(p))
    assert result['state'] == 'POINT' and result['independent_replay']
    assert called == (['ArmInquiryV21'] if operation == methods.ARM_MEAN else ['ArmInquiryV21', 'EffectsInquiryV21'])


def test_single_arm_does_not_invent_a_second_endpoint_or_call_composition(monkeypatch):
    from pfn_pipeline import identification_batch, identification_composition
    from examples.network_effect_dispatch_reference import approval_records
    monkeypatch.setattr(identification_batch, 'identify_randomized_network_batch', forbidden)
    monkeypatch.setattr(identification_composition, 'identify_verified_linear_target', forbidden)
    s,o,p = arm.setup('arm')
    original = dict(p['proposed_target'])
    result = dispatch.execute(s, 'q1', **o, **approval_records(p))
    assert result['state'] == 'POINT'
    assert result['mathematical_claim']['target'] == original
    assert result['primary_method'] == methods.ARM


@pytest.mark.parametrize('method,operation', [
    ('unknown', methods.ARM_MEAN),
    (methods.CONTRAST, methods.ARM_MEAN),
    (methods.ARM, methods.DIFFERENCE),
])
def test_wrong_operation_never_defaults_to_a_local_method(monkeypatch, method, operation):
    from pfn_pipeline import identification_business as core
    monkeypatch.setattr(core, 'identify_network_business_query', forbidden)
    with pytest.raises(ValueError, match='LOCAL_METHOD_OPERATION_MISMATCH'):
        execution.identify(method, operation, {})


def test_native_producer_cannot_change_its_inputs(monkeypatch):
    from pfn_pipeline import identification_business as core

    def change(inquiry):
        inquiry['target'] = 'another target'
        return {'status': 'POINT'}

    monkeypatch.setattr(core, 'identify_network_business_query', change)
    with pytest.raises(ValueError, match='NATIVE_INPUT_MUTATED'):
        execution.identify(methods.ARM, methods.ARM_MEAN, {'target': 'original'})


@pytest.mark.parametrize('mutation', ['result', 'input', 'false'])
def test_replay_is_bound_to_both_original_input_and_unchanged_proof(monkeypatch, mutation):
    from pfn_pipeline import identification_business as core
    inquiry, result = {'target': 'original'}, {'certificate': 'original'}
    digest = dispatch.sha(inquiry)

    def replay(outcome):
        if mutation == 'result': outcome['certificate'] = 'changed'
        elif mutation == 'input': inquiry['target'] = 'changed'
        return mutation != 'false'

    monkeypatch.setattr(core, 'replay_verified_business_outcome', replay)
    with pytest.raises(ValueError, match='INDEPENDENT_REPLAY_OR_MUTATION_FAILURE'):
        execution.replay_outcome(methods.ARM, methods.ARM_MEAN, result,
            inquiry=inquiry, input_digest=digest)


@pytest.mark.parametrize('mutation', ['template', 'input'])
def test_batch_cannot_rebind_the_reviewed_study(monkeypatch, mutation):
    from pfn_pipeline import identification_batch

    @dataclass
    class Batch:
        template: dict

    def changed(task):
        if mutation == 'input':
            task['context'] = 'another period'
            return Batch(task)
        return Batch(dict(task, context='another period'))

    monkeypatch.setattr(identification_batch, 'identify_randomized_network_batch', changed)
    with pytest.raises(ValueError, match='EFFECT_BATCH_INPUT_MISMATCH'):
        execution.arm_batch(methods.CONTRAST, {'context': 'original period'})


def test_reverse_effect_uses_registered_linear_producer_and_object_replayer(monkeypatch):
    from pfn_pipeline import identification_composition as native
    from tests_gateway.test_local_total_effect import setup
    from examples.network_effect_dispatch_reference import approval_records
    producer, verifier = native.identify_verified_linear_target, native.replay_verified_composition
    calls = []

    def linear(*args, **kwargs):
        calls.append('linear')
        return producer(*args, **kwargs)

    def replay(*args, **kwargs):
        calls.append('replay')
        return verifier(*args, **kwargs)

    monkeypatch.setattr(native, 'identify_verified_linear_target', linear)
    monkeypatch.setattr(native, 'replay_verified_composition', replay)
    s,e,o = setup(monkeypatch, reverse=True)
    p = dispatch.inspect_methods(s, 'q1', **o)
    result = dispatch.execute(s, 'q1', **o, **approval_records(p))
    contract = methods.resolve(methods.CONTRAST, methods.DIFFERENCE)
    assert contract.linear is linear and contract.replay_linear is replay
    assert result['state'] == 'POINT' and result['independent_replay']
    assert result['certificate']['results'][0]['kind'] == 'CUSTOM_LINEAR'
    assert 'linear' in calls and 'replay' in calls
