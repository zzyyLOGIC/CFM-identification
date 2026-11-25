"""Extended business routes now accept W/G exposures and the Task-1 designs.

Covers the two paths in ``network_extended_dispatch`` that previously assumed
integer exposure coordinates / node-less design payloads:

  * the single-arm route (R1A) with a weighted or grouped exposure, and on the
    unequal/rerandomized designs D7/D8;
  * the finite-policy route (R1B_FINITE_POLICY) on D7/D8, including the honest
    OFF_SUPPORT result for a rerandomized policy atom that violates balance.
"""
from copy import deepcopy

import pytest

from examples import network_extended_reference as ext
from cfm_id import business_dispatch as dispatch

NODES = ext.NODES


def _execute(s, options, plan):
    assert plan['state'] == 'REVIEW_REQUIRED', plan
    return dispatch.execute(s, 'q1', **options, plan_review=ext.approve(plan['plan_worksheet']),
        native_reviews={r['method']: dict(reading_review=ext.approve(r['reading_worksheet']),
                                          science_review=ext.approve(r['science_worksheet']))
                        for r in plan['methods']},
        research_protocol_selected=True)


def _d7(assignment):
    return dict(kind='UNEQUAL_PROBABILITY_FIXED_QUOTA', probabilities=None, fixed_count=1,
                unit_weights={n: '1' for n in NODES}, source_ids=assignment['source_ids'])


def _d8(assignment, x):
    return dict(kind='RERANDOMIZED_BALANCED', probabilities=None, fixed_count=1,
                unit_weights={n: '1' for n in NODES},
                balance_covariates={'x': dict(zip(NODES, x))}, balance_tolerance='1/2',
                source_ids=assignment['source_ids'])


def _arm_candidate(design):
    s, options, _ = ext.setup('arm')
    cand = deepcopy(options['candidate'])
    cand['target']['first']['own'] = 0
    if design == 'D7':
        cand['assignment'] = _d7(cand['assignment'])
    elif design == 'D8':
        cand['assignment'] = _d8(cand['assignment'], ('1', '1', '1'))
    return s, options, cand


@pytest.mark.parametrize('design', ['D1', 'D7', 'D8'])
@pytest.mark.parametrize('kind', ['weighted', 'grouped'])
def test_extended_arm_route_accepts_wg(design, kind):
    s, options, cand = _arm_candidate(design)
    if kind == 'weighted':
        cand['exposure'] = dict(kind='WEIGHTED_EXPOSURE', weights={n: '1' for n in NODES},
                                mode='sum', source_ids=cand['exposure']['source_ids'])
        cand['target']['first']['exposure'] = '1'
    else:
        cand['exposure'] = dict(kind='GROUPED_EXPOSURE', groups={'g1': NODES[:2], 'g2': NODES[2:]},
                                source_ids=cand['exposure']['source_ids'])
        cand['target']['first']['exposure'] = '[1, 0]'
    opts = dict(query_review=options['query_review'], candidate=cand,
                request_sha256=options['request_sha256'])
    plan = dispatch.inspect_methods(s, 'q1', **opts)
    result = _execute(s, opts, plan)
    assert result['state'] == 'POINT'
    assert result['primary_method'] == 'network.randomized.local_mean'


def test_extended_finite_policy_route_on_d7():
    s, options, _ = ext.setup('mixture')
    cand = deepcopy(options['candidate'])
    cand['assignment'] = _d7(cand['assignment'])
    opts = dict(query_review=options['query_review'], candidate=cand,
                request_sha256=options['request_sha256'])
    plan = dispatch.inspect_methods(s, 'q1', **opts)
    result = _execute(s, opts, plan)
    assert result['state'] == 'POINT'
    assert result['primary_method'] == 'network.randomized.finite_policy_mean'


def test_extended_finite_policy_route_on_d8_reports_off_support_and_accepts_balanced_atoms():
    s, options, _ = ext.setup('mixture')
    cand = deepcopy(options['candidate'])
    cand['assignment'] = _d8(cand['assignment'], ('0', '1', '1'))
    # Original atoms treat 甲乙; treating 甲 leaves the treated/untreated covariate
    # means unbalanced, so that atom is genuinely off-support under D8.
    opts = dict(query_review=options['query_review'], candidate=cand,
                request_sha256=options['request_sha256'])
    plan = dispatch.inspect_methods(s, 'q1', **opts)
    result = _execute(s, opts, plan)
    assert result['state'] == 'UNSUPPORTED'
    assert result['reason_code'] == 'OFF_SUPPORT_ALTERNATE_THEOREM'

    # Atoms that treat a covariate-1 node satisfy the balance tolerance -> POINT.
    for comp, values in zip(cand['target']['components'], ([0, 1, 0], [0, 0, 1])):
        comp['assignment'] = dict(zip(NODES, values))
    opts = dict(query_review=options['query_review'], candidate=cand,
                request_sha256=options['request_sha256'])
    plan = dispatch.inspect_methods(s, 'q1', **opts)
    result = _execute(s, opts, plan)
    assert result['state'] == 'POINT'
