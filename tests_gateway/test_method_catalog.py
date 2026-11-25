"""Guard the maintained inventory without treating descriptions as admission."""
from dataclasses import replace
from pathlib import Path

import pytest

from cfm_id import capability_registry as registry, method_catalog
from demo.backend import math_library
from pfn_pipeline.identification_assumption_inventory import (
    implemented_assumption_catalog_v27, requirements_for_route_v27, legacy_ate_condition_catalog)


def test_every_registered_method_and_native_entry_is_described():
    result = method_catalog.catalog()
    rows = {row['method_id']: row for row in result['methods']}
    assert len(rows) == len(result['methods'])
    common = {m.method_id for b in registry.business_bindings() for m in b.methods}
    research = {r.capability.route_id for r in registry.registrations()} | {'DAG_GENERAL_ID'}
    homepage = {m for e in method_catalog.homepage_entries() for m in e['method_ids']}
    assert set(rows) == common | research | homepage
    native = {r for entry in registry.separate_entries() for r in entry['route_ids']}
    assert native <= {r for row in rows.values() for r in row['native_route_ids']}
    assert rows['network.randomized.full_policy_contrast']['native_route_ids'] == ['R1B_FULL_ASSIGNMENT']
    assert rows['network.randomized.signature_policy_contrast']['native_route_ids'] == ['R2_MEAN_SIGNATURE']
    assert result['scientific_validity_certified_by_software'] is False
    root = Path(__file__).resolve().parents[1]
    for row in rows.values():
        assert row['verification']['detail']
        for module in row['source_modules']:
            assert (root / (module.replace('.', '/') + '.py')).is_file(), module


def test_new_registration_cannot_silently_receive_guessed_metadata(monkeypatch):
    original = registry.business_bindings()
    first = original[0]
    extra = replace(first.methods[0], method_id='NEW_UNDOCUMENTED_METHOD')
    monkeypatch.setattr(registry, 'business_bindings',
                        lambda: (replace(first, methods=first.methods + (extra,)), *original[1:]))
    with pytest.raises(ValueError, match='UNDOCUMENTED_REGISTERED_METHOD:NEW_UNDOCUMENTED_METHOD'):
        method_catalog.catalog()


def test_homepage_listing_does_not_register_a_new_network_or_research_route():
    snapshot = registry.inventory()
    before = registry.session_lanes()
    entry = snapshot['homepage_adapters'][0]
    assert entry['common_business_reader'] is False
    assert entry['estimation_handoff_allowed'] is False
    assert registry.reader_for('UNIT_NETWORK', 'ATE') is None
    assert 'MANSKI_BINARY_ATE_V2' not in {r.capability.route_id for r in registry.registrations()}
    # Caller changes to returned metadata cannot create a review, method or route.
    entry['estimation_handoff_allowed'] = True
    entry['method_ids'].append('FAKE')
    altered = method_catalog.catalog()
    altered['methods'][0]['common_business_entries'].clear()
    assert registry.inventory()['homepage_adapters'][0]['estimation_handoff_allowed'] is False
    assert registry.session_lanes() == before
    assert method_catalog.catalog()['methods'][0]['common_business_entries']
    with pytest.raises(ValueError, match='UNKNOWN_METHOD_DESCRIPTION'):
        method_catalog.describe('FAKE')


def test_readonly_requirements_preserves_old_data_and_never_solves(monkeypatch):
    from pfn_pipeline._internal.identification.identification import IdentificationEngine
    def forbidden(*args, **kwargs):
        raise AssertionError('Descriptions must not execute mathematical identification')
    monkeypatch.setattr(IdentificationEngine, 'solve', forbidden)
    monkeypatch.setattr(IdentificationEngine, 'solve_verified', forbidden)
    old = implemented_assumption_catalog_v27()
    response = math_library.run(dict(operation='requirements', problem=
        {'route': 'R1A_RANDOMIZED_ARM', 'design_kind': 'two_stage_quota_mixture_binary_v2_7'}))
    assert response['state'] == 'DIAGNOSTIC'
    assert response['estimation_handoff_allowed'] is False
    result = response['result']
    assert result['catalog'] == old
    assert result['legacy_ate_catalog'] == legacy_ate_condition_catalog()
    assert result['required'] == requirements_for_route_v27(
        'R1A_RANDOMIZED_ARM', design_kind='two_stage_quota_mixture_binary_v2_7')
    assert result['method_required'] is None
    schema = math_library.schema('requirements')
    assert schema['route_ids'] == old['route_ids']
    for method in ('MANSKI_BINARY_ATE_V2', 'DAG_GENERAL_ID', 'BOUNDED_POLICY_MEAN_D2_E4'):
        assert method in schema['method_ids']
        response = math_library.run(dict(operation='requirements', problem={'method': method}))
        assert response['state'] == 'DIAGNOSTIC'
        assert response['estimation_handoff_allowed'] is False
        assert response['result']['method_required']['method_id'] == method
    with pytest.raises(ValueError, match='UNKNOWN_METHOD_DESCRIPTION'):
        math_library.run(dict(operation='requirements', problem={'method': 'FAKE'}))
    with pytest.raises(ValueError, match='UNREPRESENTED_INPUT_FIELD'):
        math_library.run(dict(operation='requirements', problem={'method': 'MANSKI_BINARY_ATE_V2', 'adopt': True}))


def test_verification_descriptions_distinguish_recomputation_from_separate_checks():
    from cfm_id.method_requirements import catalog
    r2 = next(row for row in catalog() if row['method'] == 'network.randomized.signature_policy_mean')
    assert r2['certificate_requirement'].startswith('同实现重算：')
    rows = {r['method_id']: r for r in method_catalog.catalog()['methods']}
    assert rows['MEAN_ORDER_D2_E1']['verification']['label'] == '独立端点与对偶核验'
    assert rows['network.observational.full_policy_mean']['verification']['label'] == '同实现重算＋单独支持检查'


def test_generated_maintenance_table_matches_current_registry():
    root = Path(__file__).resolve().parents[1]
    assert (root / 'docs/METHOD_CONDITIONS_AND_VERIFICATION_ZH.md').read_text(encoding='utf-8') == method_catalog.render_markdown()


def test_source_adapters_are_indexed_without_promising_estimators():
    entries = {e['entry_id']: e for e in method_catalog.homepage_entries()}
    assert 'network.randomized.signature_policy_mean' in entries['RANDOMIZED_POLICY_SOURCE']['method_ids']
    assert entries['DAG_SINGLE_SOURCE']['method_ids'] == ['DAG_GENERAL_ID']
    assert entries['BINARY_IV_SOURCE']['method_ids'] == ['BINARY_IV_LATE_ATE']
    assert entries['BINARY_IV_SOURCE']['estimator_execution'] is False
    from cfm_id.dedicated_entries import inventory
    general = next(e for e in inventory() if e['route_id'] == 'DAG_GENERAL_ID')
    assert general['automatic_business_reading'] is True
    assert 'one-outcome' in general['business_reading_scope']
    assert general['production_admission'] is False


def test_method_operation_and_implementation_do_not_create_duplicate_theorems():
    rows = {r['method_id']: r for r in method_catalog.catalog()['methods']}
    policies = [rows['network.randomized.' + op] for op in
                ('full_policy_mean', 'full_policy_contrast', 'finite_policy_mean')]
    assert {tuple(r['definition_ids']) for r in policies} == {('network.randomized.full_policy',)}
    assert {r['operation'] for r in policies} == {'MEAN', 'FIRST_MINUS_SECOND', 'FINITE_POLICY_MEAN'}
    bounds = [r for r in rows.values() if r['definition_ids'] == ('network.bounds.mean_box',)]
    assert len(bounds) == 6 and len({r['implementation'] for r in bounds}) == 3
    assert rows['MEAN_ORDER_D2_E1']['definition_ids'] != bounds[0]['definition_ids']
    assert rows['BINARY_IV_LATE_ATE']['definition_ids'] == ('iv.binary.late', 'iv.binary.ate_bounds')
    assert rows['ONE_ARM_ATE_BOUNDS_V2']['definition_ids'] == rows['ONE_ARM_NO_OUTCOME_RESTRICTION_V2']['definition_ids']


def test_historical_lookup_cannot_change_native_proof_identity_or_add_capability():
    from cfm_id.method_compat import aliases, canonical_id, native_id
    from cfm_id import policy_methods, local_methods, observational_methods, finite_policy_methods
    for old, current in aliases().items():
        assert native_id(current) == old and canonical_id(old) == current
        assert method_catalog.describe(old) == method_catalog.describe(current)
    for module in (policy_methods, local_methods, observational_methods, finite_policy_methods):
        for binding in module.methods():
            old = native_id(binding.method_id)
            resolved = module.resolve(old, binding.operation)
            assert resolved.method_id == binding.method_id
            assert resolved.native_route_ids == binding.native_route_ids
            assert resolved.producers == binding.producers and resolved.replayers == binding.replayers
            assert all(not route.startswith('network.') for route in binding.native_route_ids)
    for invented in ('network.randomized.new_policy_mean', 'R2_NEW', 'network.observational.local_mean'):
        with pytest.raises(ValueError, match='UNKNOWN_METHOD_DESCRIPTION'):
            method_catalog.describe(invented)


def test_new_plan_and_original_native_certificate_have_separate_identities():
    from examples.network_dispatch_reference import setup, approval_records
    from cfm_id import business_dispatch
    from copy import deepcopy
    s, entry, options, plan = setup(design='D1', sufficiency=False)
    assert plan['method_identity_version'] == 'semantic-methods-1'
    assert plan['methods'][0]['method'] == 'network.randomized.full_policy_mean'
    approvals = approval_records(plan)
    result = business_dispatch.execute(s, 'q1', **options, **approvals)
    assert result['state'] == 'POINT' and result['independent_replay']
    assert result['primary_method'] == plan['methods'][0]['method']
    assert result['certificate']['route'] == 'R1B_RANDOMIZED_FULL_ASSIGNMENT_POLICY_POINT_V1'
    assert result['mathematical_claim']['target'] == plan['proposed_target']
    # Replacing the current review key with a historical alias cannot migrate
    # an approved plan or bypass exact current-plan review matching.
    stale = deepcopy(approvals)
    stale['native_reviews']['R1B_FULL_ASSIGNMENT'] = stale['native_reviews'].pop(plan['methods'][0]['method'])
    blocked = business_dispatch.execute(s, 'q1', **options, **stale)
    assert blocked['state'] == 'CHECK_BLOCKED' and not blocked['backend_called']


def test_current_method_contracts_do_not_embed_historical_route_numbers():
    import ast
    from cfm_id.method_compat import aliases
    root = Path(__file__).resolve().parents[1]
    for name in ('policy_methods', 'local_methods', 'finite_policy_methods', 'observational_methods',
                 'method_definitions', 'network_policy_dispatch', 'network_contrast_dispatch',
                 'network_effect_dispatch', 'network_extended_dispatch', 'network_observational_policy_dispatch'):
        tree = ast.parse((root / 'cfm_id' / (name + '.py')).read_text(encoding='utf-8'))
        literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        assert not set(aliases()) & literals, name
