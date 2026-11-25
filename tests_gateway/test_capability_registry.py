"""Registration must agree with real plans and preserve independent admission."""
import ast
from copy import deepcopy
import inspect
import json
from pathlib import Path

import pytest

from cfm_id import capability_registry as registry, business_dispatch as dispatch
from cfm_id import research_route_catalog, session_routes, session_policy_routes
from examples import network_dispatch_reference as mean
from examples import network_bounded_dispatch_reference as bounded
from examples import network_contrast_dispatch_reference as contrast


def setup(kind):
    if kind.startswith('contrast_'):
        s, e, o = contrast.setup(kind.removeprefix('contrast_'))
        p = dispatch.inspect_methods(s, 'q1', **o)
        return s, e, o, p, contrast.approval_records
    if kind.startswith('bounded_'):
        s, e, o, p = bounded.setup(**(dict(center_bounds=('1/2','1/2')) if kind=='bounded_point' else {}))
    else:
        s, e, o, p = mean.setup(**(dict(design='D1', sufficiency=False) if kind=='r1b' else {}))
    return s, e, o, p, mean.approval_records


def test_native_catalog_agrees_with_core_replay_and_common_connection_is_explicit():
    from pfn_pipeline import identification_business as native
    tree = ast.parse(inspect.getsource(native.replay_verified_business_outcome))
    route_types = next(ast.literal_eval(n.value) for n in ast.walk(tree) if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id=='route_types' for t in n.targets))
    data = registry.inventory()
    network = data['separate_native_entries'][0]
    assert network['route_ids'] == list(route_types)
    assert network['common_business_routes'] == list(route_types)
    assert network['native_only_routes'] == []
    assert research_route_catalog.registrations is registry.registrations
    assert research_route_catalog.separate_entries is registry.separate_entries
    assert {r.capability.route_id for r in registry.registrations()} == {
        'MEAN_ORDER_D2_E1', 'DAG_CLASSICAL_BACKDOOR', 'DAG_ADJUSTMENT', 'DAG_CLASSICAL_FRONTDOOR', 'BINARY_IV_LATE_ATE'}
    assert not data['creates_reviews'] and not data['automatic_fallback']


def test_session_registry_matches_existing_handlers_and_frozen_acceptance_inventory():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root/'evaluation/framework_acceptance.json').read_text(encoding='utf8'))
    assert list(registry.session_lanes()) == manifest['lanes']
    assert session_routes.LANES == registry.session_lanes()
    assert session_policy_routes.LANES == registry.session_lanes('POLICY')
    for lane in registry.session_lanes():
        session_routes.require_lane(lane)
    assert registry.session_lanes('DAG') == session_routes.DAG


@pytest.mark.parametrize('kind,method,state', [
    ('r1b','network.randomized.full_policy_mean','POINT'), ('r2','network.randomized.signature_policy_mean','POINT'),
    ('bounded_point','BOUNDED_POLICY_MEAN_D2_E1','POINT'),
    ('bounded_partial','BOUNDED_POLICY_MEAN_D2_E1','PARTIAL'),
    ('contrast_point','network.randomized.full_policy_contrast','POINT'),
    ('contrast_partial','BOUNDED_POLICY_CONTRAST_D2_E1','PARTIAL'),
    ('contrast_cancellation','BOUNDED_POLICY_CONTRAST_D2_E1','POINT')])
def test_registered_network_plans_execute_existing_certificates(kind,method,state):
    s,e,o,p,approve = setup(kind)
    binding = registry.plan_binding(p,reader_id=e['reader_id'])
    assert method in {m.method_id for m in binding.methods}
    assert method in {r['method'] for r in p['methods']}
    # An inspector can propose several methods; support is checked only after
    # scientific review. Registration must never promise every proposal works.
    assert {r['method'] for r in p['methods']} <= {m.method_id for m in binding.methods}
    assert all(v=='PENDING' for v in p['plan_worksheet']['decisions'].values())
    before = deepcopy(o['candidate'])
    approval = approve(p)
    wire = {m:{k:v.model_dump(mode='json') for k,v in pair.items()} for m,pair in approval['native_reviews'].items()}
    approval['native_reviews'] = dispatch.native_reviews_from_json(p,wire)
    r = dispatch.execute(s,'q1',**o,**approval)
    assert r['state'] == state and r['independent_replay'] is True
    assert r['primary_method'] == method and r['certificate'] and r['mathematical_claim']['kind'] == state
    assert o['candidate'] == before
    assert not r['production_admission'] and not r['estimation_handoff_allowed']


def test_registered_but_inapplicable_point_methods_do_not_trigger_partial_or_llm():
    s,e,o,p=mean.setup(n=7,quota=3)
    assert registry.plan_binding(p,reader_id=e['reader_id'])
    r=dispatch.execute(s,'q1',**o,**mean.approval_records(p))
    assert r['state']=='UNSUPPORTED' and not r['independent_replay']
    assert r['mathematical_claim'] is None and r['certificate'] is None
    assert 'LLM_UNVERIFIED' not in json.dumps(r)


@pytest.mark.parametrize('kind,mutation,state', [
    ('r1b','sample_only','NEEDS_INPUT'),
    ('bounded_partial','model_unknown','NEEDS_INPUT'),
    ('bounded_partial','extra_constraint','ADAPTER_NOT_CONNECTED'),
    ('contrast_point','direction_unknown','NEEDS_INPUT'),
    ('contrast_point','missing_policy','NEEDS_INPUT'),
    ('contrast_partial','different_context','ADAPTER_NOT_CONNECTED'),
    ('contrast_partial','model_unknown','NEEDS_INPUT')])
def test_registration_never_repairs_missing_or_unsupported_scientific_input(monkeypatch,kind,mutation,state):
    s,e,o,p,_ = setup(kind)
    raw = o['candidate']
    if mutation=='sample_only':
        raw['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE')
    elif mutation=='model_unknown':
        raw['bounded_model']['no_additional_coupling_constraints']['value'] = None
    elif mutation=='extra_constraint':
        raw['additional_restrictions'] = [dict(text='另有跨对象均值相等的条件。',source_ids=raw['target']['source_ids'])]
    elif mutation=='direction_unknown': raw['target']['operation'] = 'UNKNOWN'
    elif mutation=='missing_policy': raw['target']['second']['assignment'] = None
    elif mutation=='different_context': raw['target']['shared_outcome_and_context']['value'] = False
    module = inspect.getmodule(registry.business_binding(e['reader_id']).execute)
    monkeypatch.setattr(module,'_execute_plan',lambda *a,**kw:pytest.fail('No mathematical execution allowed'))
    r = dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state'] == state, r.get('reason_code')
    assert not r['backend_called'] and not r['independent_replay']
    assert r['mathematical_claim'] is None and r['certificate'] is None


@pytest.mark.parametrize('kind',['r1b','contrast_partial'])
@pytest.mark.parametrize('decision',['PENDING','REJECTED'])
def test_registration_does_not_approve_science_or_fallback(kind,decision):
    s,e,o,p,approve = setup(kind)
    a = approve(p)
    review = next(iter(a['native_reviews'].values()))['science_review']
    review.decisions[next(iter(review.decisions))] = decision
    r = dispatch.execute(s,'q1',**o,**a)
    assert r['state'] == ('REVIEW_REQUIRED' if decision=='PENDING' else 'CHECK_BLOCKED')
    assert not r['backend_called'] and r['mathematical_claim'] is None
    assert r['certificate'] is None and 'LLM_UNVERIFIED' not in json.dumps(r)


@pytest.mark.parametrize('mutation',['unknown_family','missing_network_family','cross_family_method','duplicate_method','empty_methods'])
def test_wrong_plan_is_rejected_before_decoder_or_execution(monkeypatch,mutation):
    s,e,o,p,_ = setup('r1b')
    broken = deepcopy(p)
    if mutation=='unknown_family': broken['fact_family'] = 'INVENTED_READER'
    elif mutation=='missing_network_family': broken.pop('fact_family')
    elif mutation=='cross_family_method': broken['methods'][0]['method'] = 'network.randomized.full_policy_contrast'
    elif mutation=='duplicate_method': broken['methods'].append(deepcopy(broken['methods'][0]))
    elif mutation=='empty_methods': broken['methods'] = []
    with pytest.raises(registry.RegistryError): dispatch.native_reviews_from_json(broken,{})
    module = inspect.getmodule(registry.business_binding(e['reader_id']).inspect)
    monkeypatch.setattr(module,'inspect_methods',lambda *a,**kw:broken)
    monkeypatch.setattr(module,'_execute_plan',lambda *a,**kw:pytest.fail('Invalid registry must not execute'))
    r = dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='CHECK_BLOCKED' and r['reason_code']=='CAPABILITY_REGISTRATION_MISMATCH'
    assert not r['backend_called'] and r['mathematical_claim'] is None


def test_cross_family_valid_plan_cannot_replace_selected_reader(monkeypatch):
    s,e,o,_,_ = setup('r1b')
    _,_,_,foreign,_ = setup('contrast_point')
    module = inspect.getmodule(registry.business_binding(e['reader_id']).inspect)
    monkeypatch.setattr(module,'inspect_methods',lambda *a,**kw:foreign)
    r = dispatch.inspect_methods(s,'q1',**o)
    assert r['state']=='CHECK_BLOCKED'
    assert r['registration_error']=='READER_AND_PLAN_FAMILY_MISMATCH'


def test_legacy_dag_plan_without_family_keeps_exact_decoder_and_checks():
    from examples import business_dispatch_reference as dag
    from examples.dag_business_reference import cases
    s,o,p = dag.prepare(cases()[0])
    assert 'fact_family' not in p
    b = registry.plan_binding(p)
    assert b.reader_id=='VARIABLE_DAG_FACTS'
    a=dag.approvals(p)
    wire={m:{k:v.model_dump(mode='json') for k,v in pair.items()} for m,pair in a['native_reviews'].items()}
    a['native_reviews']=dispatch.native_reviews_from_json(p,wire)
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']=='POINT' and r['independent_replay'] is True


def test_mutating_descriptive_inventory_does_not_register_or_enable_capability():
    data=registry.inventory()
    data['common_business_readers'][0]['methods'].append(dict(method_id='IV'))
    data['common_business_readers'].clear()
    data['creates_reviews']=True
    with pytest.raises(registry.RegistryError): registry.business_binding('IV')
    with pytest.raises(registry.RegistryError): registry.plan_binding(dict(methods=[dict(method='IV')]))
    assert registry.reader_for('UNIT_NETWORK','DIRECT_EFFECT').reader_id=='NETWORK_RANDOMIZED_EFFECT_FACTS'
    assert registry.reader_for('UNIT_NETWORK','ATE') is None
    assert registry.reader_for('UNIT_NETWORK','TOTAL_EFFECT').reader_id=='NETWORK_POLICY_CONTRAST_FACTS'
    assert not registry.inventory()['creates_reviews']


@pytest.mark.parametrize('kind,verifier',[
    ('r1b','pfn_pipeline.identification_policy_r1b'),
    ('r2','pfn_pipeline.identification_policy_r2'),
    ('bounded_partial','cfm_id.bounded_policy_verify'),
    ('contrast_point','cfm_id.fixed_comparison'),
    ('contrast_partial','cfm_id.bounded_contrast_verify')])
def test_registered_method_still_requires_actual_independent_replay(monkeypatch,kind,verifier):
    s,e,o,p,approve=setup(kind)
    method=registry.plan_binding(p).methods
    replayer=next(f for m in method for f in m.replayers if f.__module__==verifier)
    monkeypatch.setattr(inspect.getmodule(replayer),replayer.__name__,lambda *a,**kw:False)
    r=dispatch.execute(s,'q1',**o,**approve(p))
    assert r['state']=='CHECK_BLOCKED'
    assert not r['independent_replay'] and r['mathematical_claim'] is None and r['certificate'] is None
