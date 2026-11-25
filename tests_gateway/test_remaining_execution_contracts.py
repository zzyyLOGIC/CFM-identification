"""Registration/execution agreement without merging scientific contracts."""
from dataclasses import replace
import pytest

from cfm_id import business_dispatch as dispatch, capability_registry
from cfm_id import dag_business, dag_methods, finite_policy_methods
from examples import business_dispatch_reference as dag, network_extended_reference as mixture
from examples import dag_business_reference, dag_adjustment_business_reference, dag_frontdoor_business_reference
from examples.network_dispatch_reference import approval_records


@pytest.mark.parametrize('method,case', [
    (dag_methods.BACKDOOR,dag_business_reference.cases()[0]),
    (dag_methods.ADJUSTMENT,dag_adjustment_business_reference.cases()[0]),
    (dag_methods.FRONTDOOR,dag_frontdoor_business_reference._case('binding_check','specified')),
])
def test_dag_reading_research_registration_and_actual_calls_share_contract(monkeypatch,method,case):
    binding=dag_methods.resolve(method)
    original=binding.adapter_type.submit
    called=[]
    def submit(self,problem,review):
        called.append(type(problem))
        return original(self,problem,review)
    monkeypatch.setattr(binding.adapter_type,'submit',submit)
    registration=next(r for r in capability_registry.registrations() if r.capability.route_id==method)
    business=next(m for m in capability_registry.business_binding('VARIABLE_DAG_FACTS').methods if m.method_id==method)
    assert dag_business.route_contract(method)==binding.legacy_contract()
    assert (registration.problem_type,registration.review_type,registration.adapter_type,registration.version)==(
        binding.problem_type,binding.review_type,binding.adapter_type,binding.version)
    assert business.producers==(submit,) and business.replayers==binding.replayers
    s,o,p=dag.prepare(case)
    assert not called
    pending=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert pending['state']=='REVIEW_REQUIRED' and not called
    result=dispatch.execute(s,'q1',**o,**dag.approvals(p))
    assert result['state']=='POINT' and result['independent_replay']
    assert called==[binding.problem_type]
    assert method in [a['method'] for a in result['answers']]


@pytest.mark.parametrize('method,operation',[
    ('DAG_GENERAL_ID',dag_methods.OPERATION),('BINARY_IV_LATE_ATE',dag_methods.OPERATION),
    (dag_methods.BACKDOOR,'FINITE_POLICY_MEAN'),('unknown',dag_methods.OPERATION),
])
def test_dag_registration_does_not_enable_other_proofs_or_operations(method,operation):
    with pytest.raises(ValueError,match='EXPLICIT_SUPPORTED_DAG_ROUTE_REQUIRED'):
        dag_methods.resolve(method,operation)


@pytest.mark.parametrize('method,operation',[
    ('R2_MEAN_SIGNATURE',finite_policy_methods.OPERATION),('R1B_FULL_ASSIGNMENT',finite_policy_methods.OPERATION),
    (finite_policy_methods.METHOD,'MEAN'),(finite_policy_methods.METHOD,'FIRST_MINUS_SECOND'),
])
def test_finite_policy_requires_its_distribution_operation(method,operation):
    with pytest.raises(ValueError,match='FINITE_POLICY_METHOD_OPERATION_MISMATCH'):
        finite_policy_methods.resolve(method,operation)


def test_mixture_calls_each_component_then_preserves_exact_masses(monkeypatch):
    from pfn_pipeline import identification_business as core
    original=core.identify_network_business_query
    calls=[]
    def identify(inquiry):
        calls.append(inquiry)
        return original(inquiry)
    monkeypatch.setattr(core,'identify_network_business_query',identify)
    registered=capability_registry.business_binding('NETWORK_FINITE_POLICY_FACTS').methods[0]
    assert registered.producers==(identify,)
    s,o,p=mixture.setup('mixture')
    pending=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert pending['state']=='REVIEW_REQUIRED' and not calls
    result=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert result['state']=='POINT' and result['independent_replay']
    assert [type(q) for q in calls]==[core.FixedPolicyInquiryV21]*2+[core.FinitePolicyInquiryV21]
    assert calls[-1].policy_probabilities==tuple(x['weight'] for x in p['proposed_target']['policies'])


@pytest.mark.parametrize('defect',['component_input','component_replay','component_evidence','wrong_mass','mixture_replay'])
def test_mixture_cannot_publish_changed_or_unverified_parts(monkeypatch,defect):
    from pfn_pipeline import identification_business as core
    identify_original=core.identify_network_business_query
    replay_original=core.replay_verified_business_outcome
    calls=[]
    def identify(q):
        calls.append(type(q))
        if defect=='wrong_mass' and type(q) is core.FinitePolicyInquiryV21:
            # A valid proof of a different mixture is not proof of this question.
            return identify_original(replace(q,policy_probabilities=tuple(reversed(q.policy_probabilities))))
        result=identify_original(q)
        if defect=='component_input' and type(q) is core.FixedPolicyInquiryV21:
            object.__setattr__(q,'target',None)
        return result
    def replay(result):
        if defect=='component_replay' and result.route=='R1B_FULL_ASSIGNMENT':return False
        if defect=='mixture_replay' and result.route==finite_policy_methods.methods()[0].native_route_ids[0]:return False
        answer=replay_original(result)
        if defect=='component_evidence' and result.route=='R1B_FULL_ASSIGNMENT':
            object.__setattr__(result.result,'target_fingerprint','changed-during-replay')
        return answer
    monkeypatch.setattr(core,'identify_network_business_query',identify)
    monkeypatch.setattr(core,'replay_verified_business_outcome',replay)
    s,o,p=mixture.setup('mixture')
    result=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert result['state']=='CHECK_BLOCKED' and not result['independent_replay']
    assert result['mathematical_claim'] is None and result['certificate'] is None
    if defect.startswith('component'):
        assert calls==[core.FixedPolicyInquiryV21]
