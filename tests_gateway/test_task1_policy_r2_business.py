"""D7/D8 policy mean and two-policy difference through the R2 business route.

R1B already covers these designs; this pins the newly connected R2 route, where
the reading explicitly adopts mean-signature sufficiency. The dispatcher plans
both routes; here we drive the R2 plan row directly so the endpoint that was
previously excluded for the new designs is exercised end to end.
"""
import pytest

from examples import network_design_exposure_reference as ref
from examples.network_effect_dispatch_reference import approval_records
from cfm_id import network_policy_dispatch as policy_dispatch, network_contrast_dispatch as contrast
from pfn_pipeline.identification_business import FixedPolicyInquiryV21
from pfn_pipeline import identification_business as core


def _plan(design, family):
    _, _, options, plan = ref.setup(design, 'E1', family)
    assert plan['state'] == 'REVIEW_REQUIRED'
    return options, plan


@pytest.mark.parametrize('design', ['D7', 'D8'])
def test_r2_policy_mean_is_planned_and_point(design):
    _, plan = _plan(design, 'policy')
    assert 'network.randomized.signature_policy_mean' in [m['method'] for m in plan['methods']]
    row = next(m for m in plan['methods'] if m['method'] == 'network.randomized.signature_policy_mean')
    records = approval_records(plan)['native_reviews']['network.randomized.signature_policy_mean']
    st, target, sources, assumptions, signature, sufficiency = policy_dispatch._compile(
        plan, row, records, 'SYNTHETIC_TEST')
    inquiry = FixedPolicyInquiryV21(study=st, target=target, assumptions=assumptions,
        r2_signature=signature, r2_sufficiency=sufficiency, r2_sources=sources)
    result = core.identify_network_business_query(inquiry)
    assert result.status == 'POINT'
    assert result.route == 'R2_MEAN_SIGNATURE'


@pytest.mark.parametrize('design', ['D7', 'D8'])
def test_r2_two_policy_difference_endpoints_are_point(design):
    _, plan = _plan(design, 'contrast')
    assert 'network.randomized.signature_policy_contrast' in [m['method'] for m in plan['methods']]
    row = next(m for m in plan['methods'] if m['method'] == 'network.randomized.signature_policy_contrast')
    records = approval_records(plan)['native_reviews']['network.randomized.signature_policy_contrast']
    inquiries, _ = contrast._compile_pair(plan, row, records, 'SYNTHETIC_TEST')
    out = dict(attempts=[], backend_called=False)
    result = contrast._point(inquiries, plan, out, method='network.randomized.signature_policy_contrast')
    assert result['state'] == 'POINT'
    assert result['primary_method'] == 'network.randomized.signature_policy_contrast'
    assert [a['state'] for a in out['attempts']] == ['POINT', 'POINT']
