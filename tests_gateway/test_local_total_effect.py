"""Local total is a reviewed conditional-design contrast, not a fixed policy."""
from copy import deepcopy
from fractions import Fraction

import pytest

from cfm_id import business_dispatch as dispatch, capability_registry, method_diagnostics
from cfm_id_llm import query_conditioning_contract as default_contract
from examples.network_effect_dispatch_reference import approval_records
from tests_gateway import test_scoped_effect_reading as scoped, test_owned_effect_reading as owned


def setup(monkeypatch, *, reverse=False):
    original=owned.receive
    def receive(case,raw,**options):
        raw=deepcopy(raw)
        for query in raw['queries']:
            query['semantics']['conditioning_context']='UNKNOWN'
            if query['kind']=='LOCAL_TOTAL_EFFECT':
                query['comparison_request']['shared_condition']='UNKNOWN'
        return original(case,raw,**dict(options,profile=default_contract.CONTRACT))
    monkeypatch.setattr(owned,'receive',receive)
    monkeypatch.setattr(scoped,'contract',default_contract)
    return scoped.setup(monkeypatch,kind='LOCAL_TOTAL_EFFECT',reverse=reverse,quantity='INCREASE')


@pytest.mark.parametrize('reverse',[False,True])
def test_default_reading_native_total_and_signed_linear_proof(monkeypatch,reverse):
    session,entry,options=setup(monkeypatch,reverse=reverse)
    plan=dispatch.inspect_methods(session,'q1',**options)
    approvals=approval_records(plan)
    result=dispatch.execute(session,'q1',**options,**approvals)
    assert entry['reader_id']=='NETWORK_RANDOMIZED_EFFECT_FACTS'
    assert result['state']=='POINT' and result['independent_replay']
    assert plan['proposed_target']['kind']=='LOCAL_TOTAL_EFFECT'
    terms=result['certificate']['results'][0]['constituent_arms']
    n=len(plan['proposed_target']['node_order']);sign=-1 if reverse else 1
    expected={(node,a,s):Fraction(sign*(1 if a else -1),n)
        for node in plan['proposed_target']['node_order'] for a,s in ((1,1),(0,0))}
    assert {(t['node_id'],t['own_treatment'],t['exposure_state']):Fraction(t['coefficient']) for t in terms}==expected
    assert result['certificate']['results'][0]['kind']==('CUSTOM_LINEAR' if reverse else 'TOTAL')
    view=method_diagnostics.describe(plan,result=result,**{k:v for k,v in approvals.items() if k!='research_protocol_selected'})
    assert view['methods'][0]['certificate']['calculation_reported']==(
        'REVERSED_TOTAL_NATIVE_LINEAR_COMPOSITION' if reverse else 'NATIVE_NAMED_EFFECT_COMPOSITION')
    assert not view['is_certificate'] and not view['grants_execution']


def test_complete_policy_total_keeps_its_reader():
    assert capability_registry.reader_for('UNIT_NETWORK','TOTAL_EFFECT').reader_id=='NETWORK_POLICY_CONTRAST_FACTS'
    assert capability_registry.reader_for('UNIT_NETWORK','LOCAL_TOTAL_EFFECT').reader_id=='NETWORK_RANDOMIZED_EFFECT_FACTS'


@pytest.mark.parametrize('failure',['same_own','same_exposure','finite_sample','pending_science','stale_direction'])
def test_total_missing_conditions_or_changed_target_never_execute(monkeypatch,failure):
    session,entry,options=setup(monkeypatch)
    plan=dispatch.inspect_methods(session,'q1',**options);approved=approval_records(plan)
    changed=deepcopy(options);facts=changed['candidate']
    if failure=='same_own':facts['target']['reference']['own']=facts['target']['evaluated']['own']
    elif failure=='same_exposure':facts['target']['reference']['exposure']=facts['target']['evaluated']['exposure']
    elif failure=='finite_sample':
        for source in facts['information']:source.update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE',arm_cells=[])
    elif failure=='pending_science':
        approved['native_reviews']['network.randomized.local_contrast']['science_review'].decisions['consistency']='PENDING'
    else:
        facts['target']['reference'],facts['target']['evaluated']=facts['target']['evaluated'],facts['target']['reference']
    result=dispatch.execute(session,'q1',**changed,**approved)
    assert result['state']!='POINT' and not result['backend_called']
    assert not result['independent_replay']
