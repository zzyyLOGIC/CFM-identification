"""Count means reuse POINT identities, never assume a count sharpness theorem.

Hand-authored adapter fixtures only; not a measure of LLM/source accuracy.
"""
from copy import deepcopy
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_dispatch as dispatch
from cfm_id_llm.network_policy_reading import Study
from examples.network_dispatch_reference import setup as mean_setup, approval_records
from examples.network_contrast_dispatch_reference import setup as contrast_setup


@pytest.mark.parametrize('design,sufficiency,method',[
    ('D1',False,'network.randomized.full_policy_mean'), ('D2',True,'network.randomized.signature_policy_mean')])
def test_count_policy_mean_uses_existing_point_proof(design,sufficiency,method):
    s,e,o,_=mean_setup(design=design,sufficiency=sufficiency)
    o['candidate']['study'].update(outcome_kind='COUNT',outcome='本周任务延误次数')
    Draft202012Validator(Study.model_json_schema()).validate(o['candidate']['study'])
    before=deepcopy(o['candidate'])
    p=dispatch.inspect_methods(s,'q1',**o)
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='POINT' and r['primary_method']==method and r['independent_replay']
    assert r['outcome_domain_embedding']['business_kind']=='COUNT'
    assert not r['outcome_domain_embedding']['sharp_bound_or_nonidentification_transfer']
    assert o['candidate']==before


@pytest.mark.parametrize('profile',[None,'network-policy-scopes-2'])
def test_count_contrast_keeps_direction_and_both_replays(profile):
    s,e,o=contrast_setup('point',profile=profile)
    o['candidate']['study'].update(outcome_kind='COUNT',outcome='同一考核周迟到开门次数')
    p=dispatch.inspect_methods(s,'q1',**o)
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='POINT' and r['independent_replay']
    assert r['certificate']['verification']=='TWO_CORE_REPLAYS_AND_SIGNED_COMPOSITION'
    assert r['mathematical_claim']['target']['operation']=='first_minus_second'
    assert r['outcome_domain_embedding']['native_kind']=='continuous'


@pytest.mark.parametrize('mutation,expected',[
    ('finite_sample','NEEDS_INPUT'),('missing_moment','NEEDS_INPUT'),
    ('denied_moment','ADAPTER_NOT_CONNECTED'),('review_rejected','CHECK_BLOCKED')])
def test_count_does_not_approve_conditions(mutation,expected):
    s,e,o,_=mean_setup(design='D1',sufficiency=False)
    c=o['candidate'];c['study']['outcome_kind']='COUNT'
    if mutation=='finite_sample':c['information'][0].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE')
    elif mutation=='missing_moment':c['assumptions']['finite_conditional_first_moments']['value']=None
    elif mutation=='denied_moment':c['assumptions']['finite_conditional_first_moments']['value']=False
    p=dispatch.inspect_methods(s,'q1',**o)
    if mutation=='review_rejected':
        reviews=approval_records(p)
        reviews['native_reviews'][p['methods'][0]['method']]['science_review'].decisions['finite_conditional_first_moments']='REJECTED'
        p=dispatch.execute(s,'q1',**o,**reviews)
    assert p['state']==expected and not p['backend_called']


@pytest.mark.parametrize('kind',['partial','cancellation'])
def test_count_mean_box_cannot_inherit_sharpness_or_nonidentification(kind):
    s,e,o=contrast_setup(kind)
    o['candidate']['study']['outcome_kind']='COUNT'
    r=dispatch.inspect_methods(s,'q1',**o)
    assert r['state']=='ADAPTER_NOT_CONNECTED' and r['reason_code']=='COUNT_BOUNDED_MODEL_NOT_CONNECTED'
    assert not r['backend_called'] and r['mathematical_claim'] is None


def test_count_r3_reports_explicit_unconnected_adapter():
    from examples.network_observational_policy_reference import setup
    s,e,o=setup('care');o['candidate']['study']['outcome_kind']='COUNT'
    r=dispatch.inspect_methods(s,'q1',**o)
    assert r['reason_code']=='COUNT_OBSERVATIONAL_POLICY_NOT_CONNECTED' and not r['backend_called']
