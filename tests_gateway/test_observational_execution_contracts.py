"""Bindings cannot interchange observational targets, information or approval."""
import pytest

from cfm_id import business_dispatch as dispatch, capability_registry
from cfm_id import observational_methods as methods
from cfm_id import research_spec_observational_adapters as attributes
from examples import network_observational_policy_reference as policy
from examples import network_observational_signature_reference as signature
from examples import network_extended_reference as effects
from examples.network_dispatch_reference import approval_records


def setup(name):
    if name in ('full', 'signature'):
        s,e,o = (policy if name == 'full' else signature).setup()
    else:
        s,o,p = effects.setup(name)
    return s,o,dispatch.inspect_methods(s, 'q1', **o)


@pytest.mark.parametrize('name', ['full','signature','observed','stratum','nodewise'])
def test_registry_and_actual_execution_use_same_live_function(monkeypatch, name):
    from pfn_pipeline import identification_business as core
    original = core.identify_network_business_query
    called = []

    def identify(inquiry):
        called.append(type(inquiry).__name__)
        return original(inquiry)

    monkeypatch.setattr(core, 'identify_network_business_query', identify)
    s,o,p = setup(name)
    operation = methods.MEAN if name in ('full','signature') else methods.DIFFERENCE
    method = methods.resolve(p['methods'][0]['method'], operation)
    family = capability_registry.business_binding(p['fact_family'])
    registered = next(m for m in family.methods if m.method_id == method.method_id)
    assert registered.producers == method.producers and registered.replayers == method.replayers
    assert registered.native_route_ids == method.native_route_ids
    assert method.identify is identify
    unapproved = dispatch.execute(s, 'q1', **o, research_protocol_selected=True)
    assert not called and not unapproved['backend_called']
    result = dispatch.execute(s, 'q1', **o, **approval_records(p))
    assert result['state'] == 'POINT' and result['independent_replay'] and len(called) == 1
    assert result['primary_method'] == method.method_id


@pytest.mark.parametrize('name,other', [
    ('observed', methods.STRATIFIED_EFFECT), ('observed', methods.NODEWISE_EFFECT),
    ('stratum', methods.OBSERVED_EFFECT), ('stratum', methods.NODEWISE_EFFECT),
    ('nodewise', methods.OBSERVED_EFFECT), ('nodewise', methods.STRATIFIED_EFFECT),
])
def test_same_local_coordinates_do_not_allow_a_different_average(name, other):
    from tests_gateway.test_research_spec_observational import reading
    c = reading(name)
    question = attributes.from_effect_reading(c, c.information[0])
    with pytest.raises(ValueError, match='OBSERVATIONAL_METHOD_AVERAGING_MISMATCH'):
        methods.require_effect(other, question, c.information[0].operator)


@pytest.mark.parametrize('name,wrong_operator', [
    ('observed', 'STRATIFIED_ARM_LAW'), ('stratum', 'FACTORIZED_ARM_LAW'),
    ('nodewise', 'MIXTURE_ARM_LAW'),
])
def test_method_cannot_promote_an_information_operator_to_a_different_target(name, wrong_operator):
    from tests_gateway.test_research_spec_observational import reading
    c = reading(name)
    question = attributes.from_effect_reading(c, c.information[0])
    method = methods.effect_routes()[question.averaging.kind]
    with pytest.raises(ValueError, match='TARGET_AVERAGING_AND_POPULATION_OPERATOR_MISMATCH'):
        methods.require_effect(method, question, wrong_operator)


@pytest.mark.parametrize('method,operation', [
    ('unknown', methods.MEAN), ('R1B_FULL_ASSIGNMENT', methods.MEAN),
    (methods.FULL_POLICY, methods.DIFFERENCE), (methods.STRATIFIED_EFFECT, methods.MEAN),
])
def test_wrong_method_or_operation_has_no_default(method, operation):
    with pytest.raises(ValueError, match='OBSERVATIONAL_METHOD_OPERATION_MISMATCH'):
        methods.resolve(method, operation)


def test_changing_compatibility_map_cannot_change_actual_method_contract():
    routes = methods.effect_routes()
    routes['OBSERVED_ALLOCATION_CONDITIONAL'] = methods.STRATIFIED_EFFECT
    actual = methods.resolve(methods.OBSERVED_EFFECT, methods.DIFFERENCE)
    assert actual.averaging == 'OBSERVED_ALLOCATION_CONDITIONAL'
    assert methods.effect_routes()['OBSERVED_ALLOCATION_CONDITIONAL'] == actual.method_id


def test_mutated_policy_input_keeps_original_public_failure_reason(monkeypatch):
    from pfn_pipeline import identification_business as core
    original = core.identify_network_business_query

    def change(inquiry):
        result = original(inquiry)
        object.__setattr__(inquiry, 'target', None)
        return result

    monkeypatch.setattr(core, 'identify_network_business_query', change)
    monkeypatch.setattr(core, 'replay_verified_business_outcome',
        lambda *args: pytest.fail('Mutated input reached replay'))
    s,o,p = setup('full')
    result = dispatch.execute(s, 'q1', **o, **approval_records(p))
    assert result['state'] == 'CHECK_BLOCKED'
    assert result['reason_code'] == 'OBSERVATIONAL_NATIVE_INPUT_MUTATED'
    assert result['certificate'] is None and not result['answers']


@pytest.mark.parametrize('name', ['full','observed'])
def test_shared_replay_failure_keeps_native_evidence_out_of_results(monkeypatch, name):
    from pfn_pipeline import identification_business as core
    monkeypatch.setattr(core, 'replay_verified_business_outcome', lambda *args: False)
    s,o,p = setup(name)
    result = dispatch.execute(s, 'q1', **o, **approval_records(p))
    assert result['state'] == 'CHECK_BLOCKED'
    assert result['mathematical_claim'] is None and not result['independent_replay']
    if name == 'full':
        assert result['reason_code'] == 'OBSERVATIONAL_RESULT_INPUT_OR_REPLAY_MISMATCH'
    else:
        assert result['diagnostic'] == 'INDEPENDENT_REPLAY_OR_MUTATION_FAILURE'
