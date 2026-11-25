"""Public-entry evidence for the Task-1 additions.

Three groups are produced and printed as a JSON report:

  positive      complete business / native cases that reach POINT + VERIFIED
                and whose certificates replay independently;
  rejection     gap and refusal cases with the exact reason code or error;
  certificates  the verification status, certificate digest and independent
                replay result for every positive case.

Reading provenance is reported explicitly and kept separate:

  * ``hand_written_fixture`` -- every reading below is a hand-authored fixture
    passed through the same public intake/dispatch/native entry points a real
    reading would use. No language model is called (``model_api_calls == 0``).
  * ``real_llm_runs`` -- 0. This is not a model evaluation and claims no
    language-model reading accuracy.

Run:
    python -m examples.task1_public_entry_evidence [--output DIR]
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from cfm_id import business_dispatch as dispatch, business_intake as intake
from cfm_id import network_policy_dispatch as policy_dispatch
from cfm_id import network_contrast_dispatch as contrast_dispatch
from cfm_id import network_extended_dispatch as extended_dispatch
from cfm_id.workflows import policy_difference
from cfm_id_llm.network_policy_reading import Assignment, Exposure
from cfm_id_llm import network_design_reading as fields
from pfn_pipeline import identification as native
from pfn_pipeline import identification_business as business
from pfn_pipeline.identification_business import FixedPolicyInquiryV21
from pfn_pipeline.identification_policy_r2 import (
    R2PolicyUnavailable, declare_policy_signature, admit_mean_signature_sufficiency,
    declare_signature_population_source, identify_verified_signature_policy,
    replay_verified_signature_policy)
from pfn_pipeline.network_inquiry_shadow import (
    declare_network_study, fixed_policy_target_from_context)
from pfn_pipeline._internal.identification.schemas import (
    Assumption, UnequalProbabilityFixedQuotaDesignV1)

import examples.network_design_exposure_reference as reference
import examples.network_extended_reference as extended
import examples.task1_weighted_grouped_business_case as wg
from examples.business_dispatch_reference import approve

POSITIVE, REJECTION = [], []
NODES = ["a", "b", "c", "d"]
EDGES = [["a", "b"], ["a", "c"], ["b", "d"], ["c", "d"]]


def _digest(certificate):
    if not isinstance(certificate, dict):
        return certificate
    for key in ('certificate_sha256', 'receipt_sha256', 'target_fingerprint'):
        if certificate.get(key):
            return certificate[key]
    identified = certificate.get('identified_functional')
    if isinstance(identified, dict) and identified.get('target_fingerprint'):
        return identified['target_fingerprint']
    results = certificate.get('results')
    if isinstance(results, list) and results and isinstance(results[0], dict):
        return results[0].get('certificate_sha256')
    return None


def _extended_approvals(plan):
    return dict(plan_review=approve(plan['plan_worksheet']),
        native_reviews={r['method']: dict(reading_review=approve(r['reading_worksheet']),
                                          science_review=approve(r['science_worksheet']))
                        for r in plan['methods']},
        research_protocol_selected=True)


def _record_positive(group, case, status, verification, replay, certificate, note=""):
    POSITIVE.append(dict(group=group, case=case, state=status,
                         verification=verification, independent_replay=bool(replay),
                         certificate=certificate, note=note))


def _record_rejection(case, expected, actual, ok):
    REJECTION.append(dict(case=case, expected=expected, actual=actual, ok=bool(ok)))


# ---------------------------------------------------------------------------
# Positives
# ---------------------------------------------------------------------------

def _wg_effect_business(tmp):
    summary = wg.run(str(tmp / 'wg'))
    for row in summary['rows']:
        _record_positive('effect', f"{row['scenario']}/{row['query']}",
                         row['state'], 'VERIFIED' if row['state'] == 'POINT' else 'REJECTED',
                         row['independent_replay'], _digest(row.get('certificate')),
                         note='weighted/grouped exposure, hand-written reading, public dispatch')


def _fixed_policy_business(family):
    rows = []
    for design in ('D7', 'D8'):
        s, entry, options, plan = reference.setup(design, 'E1', family)
        result = dispatch.execute(s, 'q1', **options, **reference.approval_records(plan))
        rows.append(dict(design=design, family=family, result=result))
        _record_positive(family, f"{design}/{family}", result['state'],
                         'VERIFIED' if result['state'] == 'POINT' else 'REJECTED',
                         result.get('independent_replay', False), _digest(result.get('certificate')),
                         note=f"primary={result.get('primary_method')}")
    return rows


def _r2_policy_outcome(design):
    s, entry, options, plan = reference.setup(design, 'E1', 'policy')
    row = next(m for m in plan['methods'] if m['method'] == 'network.randomized.signature_policy_mean')
    records = reference.approval_records(plan)['native_reviews']['network.randomized.signature_policy_mean']
    study, target, sources, assumptions, signature, sufficiency = policy_dispatch._compile(
        plan, row, records, 'SYNTHETIC_TEST')
    inquiry = FixedPolicyInquiryV21(study=study, target=target, assumptions=assumptions,
        r2_signature=signature, r2_sufficiency=sufficiency, r2_sources=sources)
    return business.identify_network_business_query(inquiry)


def _r2_policy():
    for design in ('D7', 'D8'):
        outcome = _r2_policy_outcome(design)
        ok = outcome.status == 'POINT' and outcome.route == 'R2_MEAN_SIGNATURE'
        replay = business.replay_verified_business_outcome(outcome) if ok else False
        _record_positive('policy_r2', f"{design}/policy", outcome.status,
                         'VERIFIED' if ok else 'REJECTED', replay,
                         outcome.result.certificate_sha256 if hasattr(outcome.result, 'certificate_sha256') else None,
                         note='mean-signature sufficiency, public business entry')


def _r2_contrast():
    for design in ('D7', 'D8'):
        s, entry, options, plan = reference.setup(design, 'E1', 'contrast')
        row = next(m for m in plan['methods'] if m['method'] == 'network.randomized.signature_policy_contrast')
        records = reference.approval_records(plan)['native_reviews']['network.randomized.signature_policy_contrast']
        inquiries, _ = contrast_dispatch._compile_pair(plan, row, records, 'SYNTHETIC_TEST')
        outcomes = {side: business.identify_network_business_query(inquiries[side])
                    for side in ('first', 'second')}
        target = {k: plan['proposed_target'][k]
                  for k in ('node_order', 'first', 'second', 'unit_weights', 'operation')}
        ok = all(o.status == 'POINT' and o.route == 'R2_MEAN_SIGNATURE' for o in outcomes.values())
        if ok:
            receipt = policy_difference.compose(outcomes['first'], outcomes['second'],
                                                target=target, binding='evidence')
            replay = policy_difference.replay(receipt, outcomes['first'], outcomes['second'],
                                              target=target, binding='evidence')
            certificate = receipt['receipt_sha256']
        else:
            replay, certificate = False, None
        _record_positive('contrast_r2', f"{design}/contrast",
                         'POINT' if ok else 'UNSUPPORTED', 'VERIFIED' if ok else 'REJECTED',
                         replay, certificate,
                         note='two public R2 endpoints -> public signed composition')


def _extended_routes():
    nodes = extended.NODES
    # R1A single arm with W/G on D7/D8 (hand-written reading, public dispatch).
    for design, tag in (('D7', 'W'), ('D8', 'G')):
        s, options, _ = extended.setup('arm')
        cand = deepcopy(options['candidate'])
        cand['target']['first']['own'] = 0
        if design == 'D7':
            cand['assignment'] = dict(kind='UNEQUAL_PROBABILITY_FIXED_QUOTA', probabilities=None,
                                      fixed_count=1, unit_weights={n: '1' for n in nodes},
                                      source_ids=cand['assignment']['source_ids'])
        else:
            cand['assignment'] = dict(kind='RERANDOMIZED_BALANCED', probabilities=None,
                                      fixed_count=1, unit_weights={n: '1' for n in nodes},
                                      balance_covariates={'x': {n: '1' for n in nodes}},
                                      balance_tolerance='1/2',
                                      source_ids=cand['assignment']['source_ids'])
        if tag == 'W':
            cand['exposure'] = dict(kind='WEIGHTED_EXPOSURE', weights={n: '1' for n in nodes},
                                    mode='sum', source_ids=cand['exposure']['source_ids'])
            cand['target']['first']['exposure'] = '1'
        else:
            cand['exposure'] = dict(kind='GROUPED_EXPOSURE',
                                    groups={'g1': nodes[:2], 'g2': nodes[2:]},
                                    source_ids=cand['exposure']['source_ids'])
            cand['target']['first']['exposure'] = '[1, 0]'
        opts = dict(query_review=options['query_review'], candidate=cand,
                    request_sha256=options['request_sha256'])
        plan = dispatch.inspect_methods(s, 'q1', **opts)
        result = dispatch.execute(s, 'q1', **opts, **_extended_approvals(plan)) \
            if plan['state'] == 'REVIEW_REQUIRED' else plan
        _record_positive('extended_arm', f"{design}/R1A/{tag}", result['state'],
                         'VERIFIED' if result['state'] == 'POINT' else 'REJECTED',
                         result.get('independent_replay', False), _digest(result.get('certificate')),
                         note='W/G single-arm extended business route')
    # R1B finite policy mixture on D7 (hand-written reading, public dispatch).
    s, options, _ = extended.setup('mixture')
    cand = deepcopy(options['candidate'])
    cand['assignment'] = dict(kind='UNEQUAL_PROBABILITY_FIXED_QUOTA', probabilities=None,
                              fixed_count=1, unit_weights={n: '1' for n in nodes},
                              source_ids=cand['assignment']['source_ids'])
    opts = dict(query_review=options['query_review'], candidate=cand,
                request_sha256=options['request_sha256'])
    plan = dispatch.inspect_methods(s, 'q1', **opts)
    result = dispatch.execute(s, 'q1', **opts, **_extended_approvals(plan)) \
        if plan['state'] == 'REVIEW_REQUIRED' else plan
    _record_positive('extended_mix', 'D7/R1B_finite_policy', result['state'],
                     'VERIFIED' if result['state'] == 'POINT' else 'REJECTED',
                     result.get('independent_replay', False), _digest(result.get('certificate')),
                     note='finite policy value on a new design')


# ---------------------------------------------------------------------------
# Rejections
# ---------------------------------------------------------------------------

def _expect_raise(case, expected, fn):
    try:
        fn()
        _record_rejection(case, expected, 'NO_ERROR', False)
    except Exception as exc:  # reason code or exception text
        actual = getattr(exc, 'reason_code', None) or str(exc).split(':')[0] or type(exc).__name__
        _record_rejection(case, expected, actual, expected in str(actual))


def _task1_study(kind='D7'):
    base = dict(kind='unequal_probability_fixed_quota_binary_v1', nodes=list(NODES), m=2,
                unit_weights={n: '1' for n in NODES})
    design = base if kind == 'D7' else dict(
        kind='rerandomized_balanced_binary_v1', base_design=base,
        balance_rule=dict(tolerance='1/2', covariates={'x': {n: '0' for n in NODES}}))
    return declare_network_study(network_id='r2-evidence', node_order=tuple(NODES),
        undirected_edges=tuple(tuple(e) for e in EDGES), treatment_variable='AI',
        outcome_variable='sales', outcome_kind='continuous', context_reference='W:evidence',
        observation_regime='experimental', assignment_design=design,
        protocol_provenance='hand-written fixture', network_provenance='hand-written fixture',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def _assumptions():
    names = ('known_assignment_law', 'full_vector_randomization', 'consistency',
             'fixed_pretreatment_network', 'finite_conditional_first_moments')
    return tuple(Assumption(name=n, source='demo_specification', confirmed=True,
                            status='ADMITTED', evidence=['hand-written fixture']) for n in names)


def _rejection_cases():
    # W/G reading completeness.
    _expect_raise('weighted exposure without weights/mode',
                  'WEIGHTED_EXPOSURE_REQUIRES_WEIGHTS_AND_MODE',
                  lambda: fields.validate_components(
                      Assignment(kind='UNIFORM_FIXED_QUOTA', probabilities=None, fixed_count=2, source_ids=['s']),
                      Exposure(kind='WEIGHTED_EXPOSURE', source_ids=['s']), NODES, EDGES))
    grouped = Exposure(kind='GROUPED_EXPOSURE', groups={'g1': ['b'], 'g2': ['c']}, source_ids=['s'])
    _expect_raise('grouped coordinate given as a single 0/1',
                  'EXPOSURE_COORDINATE_OUTSIDE_DECLARED_MAPPING',
                  lambda: fields.validate_exposure_coordinate(grouped, 'a', '1', EDGES))
    weighted = Exposure(kind='WEIGHTED_EXPOSURE', weights={'b': '1', 'c': '2'}, mode='sum', source_ids=['s'])
    _expect_raise('weighted coordinate beyond the neighbour weight total',
                  'EXPOSURE_COORDINATE_OUTSIDE_DECLARED_MAPPING',
                  lambda: fields.validate_exposure_coordinate(weighted, 'a', '4', EDGES))
    _expect_raise('balance covariate outside the study node set',
                  'BALANCE_COVARIATES_COMPLETE_NODE_SCOPE_REQUIRED',
                  lambda: fields.validate_components(
                      Assignment(kind='RERANDOMIZED_BALANCED', probabilities=None, fixed_count=2,
                                 unit_weights={n: '1' for n in NODES},
                                 balance_covariates={'x': {**{n: '0' for n in NODES}, 'e': '0'}},
                                 balance_tolerance='1/2', source_ids=['s']), grouped, NODES, EDGES))

    # Zero-support W/G arm through the public native entry.
    net = dict(network_id='reject', node_ids=NODES, undirected_edges=EDGES)
    zero = native.identify(native.make_unequal_probability_fixed_quota_arm_task(
        net, design=UnequalProbabilityFixedQuotaDesignV1(
            nodes=tuple(NODES), m=1, unit_weights={n: '1' for n in NODES}),
        node_id='a', own_treatment_value=1, exposure_value='1', source='s', evidence='e',
        exposure_definition='weighted_exposure_sum', exposure_weights={'b': '1', 'c': '2'},
        admitted=True, synthetic=True, query_authority='TRUSTED_FIXTURE'))
    reason = zero.result.get('reason_code') if isinstance(zero.result, dict) else None
    _record_rejection('weighted arm with zero support (D7 m=1, own=1, S=1)',
                      'ZERO_ARM_SUPPORT', reason, reason == 'ZERO_ARM_SUPPORT')

    # Rerandomized finite policy atom that violates the balance rule.
    nodes = extended.NODES
    s, options, _ = extended.setup('mixture')
    cand = deepcopy(options['candidate'])
    cand['assignment'] = dict(kind='RERANDOMIZED_BALANCED', probabilities=None, fixed_count=1,
                              unit_weights={n: '1' for n in nodes},
                              balance_covariates={'x': dict(zip(nodes, ('0', '1', '1')))},
                              balance_tolerance='1/2', source_ids=cand['assignment']['source_ids'])
    opts = dict(query_review=options['query_review'], candidate=cand,
                request_sha256=options['request_sha256'])
    plan = dispatch.inspect_methods(s, 'q1', **opts)
    off = dispatch.execute(s, 'q1', **opts, **_extended_approvals(plan)) \
        if plan['state'] == 'REVIEW_REQUIRED' else plan
    _record_rejection('D8 finite policy with an off-balance atom', 'OFF_SUPPORT_ALTERNATE_THEOREM',
                      off.get('reason_code'), off.get('reason_code') == 'OFF_SUPPORT_ALTERNATE_THEOREM')

    # R2 with insufficient signature-arm cells.
    st = _task1_study('D7')
    sig = declare_policy_signature(st, grouping='strict_majority_ties_low')
    claim = admit_mean_signature_sufficiency(st, sig,
        assumption=Assumption(name='mean_signature_sufficiency', source='human_confirmation',
            status='ADMITTED', confirmed=True, evidence=['hand-written fixture']),
        covered_nodes=st.node_order)
    target = fixed_policy_target_from_context(st, (1, 1, 0, 0), authority='TRUSTED_FIXTURE')
    partial = declare_signature_population_source(st, sig, source_id='A4',
        operator='NODE_SIGNATURE_MEANS', outcome_nodes=st.node_order,
        signature_cells=((  'a', 1, 0),), admission='ADMITTED',
        availability='SYMBOLIC_POPULATION_OPERATOR', provenance='hand-written fixture')
    _expect_raise('R2 with incomplete signature-arm coverage',
                  'A4_SIGNATURE_INFORMATION_INSUFFICIENT',
                  lambda: identify_verified_signature_policy(st, target, sig, (partial,),
                      assumptions=_assumptions(), sufficiency=claim))

    # R2 with explicit mean-signature sufficiency NOT adopted.
    denied = admit_mean_signature_sufficiency(st, sig,
        assumption=Assumption(name='mean_signature_sufficiency', source='human_confirmation',
            status='NOT_ADMITTED', confirmed=False, evidence=['explicitly rejected']),
        covered_nodes=st.node_order)
    full = declare_signature_population_source(st, sig, source_id='A4',
        operator='NODE_SIGNATURE_MEANS', outcome_nodes=st.node_order,
        signature_cells=tuple((n, a, s2) for n in st.node_order for a in (0, 1) for s2 in (0, 1)),
        admission='ADMITTED', availability='SYMBOLIC_POPULATION_OPERATOR',
        provenance='hand-written fixture')
    _expect_raise('R2 with mean-signature sufficiency explicitly NOT adopted',
                  'MEAN_SIGNATURE_SUFFICIENCY_NOT_ADMITTED',
                  lambda: identify_verified_signature_policy(st, target, sig, (full,),
                      assumptions=_assumptions(), sufficiency=denied))


# ---------------------------------------------------------------------------

def run(output=None):
    POSITIVE.clear()
    REJECTION.clear()
    tmp = Path(output) if output else None
    if tmp is not None:
        tmp.mkdir(parents=True, exist_ok=False)
    work = tmp if tmp is not None else Path(__import__('tempfile').mkdtemp())

    _wg_effect_business(work)
    _fixed_policy_business('policy')
    _fixed_policy_business('contrast')
    _r2_policy()
    _r2_contrast()
    _extended_routes()
    _rejection_cases()

    positives_ok = all(p['state'] == 'POINT' and p['verification'] == 'VERIFIED'
                       and p['independent_replay'] for p in POSITIVE)
    rejections_ok = all(r['ok'] for r in REJECTION)
    summary = dict(
        reading_provenance=dict(
            hand_written_fixture=True,
            real_llm_runs=0,
            model_api_calls=0,
            note='All readings are hand-authored fixtures passed through the public '
                 'intake/dispatch/native entries. No language model was called; this is '
                 'not a model-accuracy evaluation.'),
        positives=POSITIVE,
        rejections=REJECTION,
        passed=bool(positives_ok and rejections_ok),
        positive_count=len(POSITIVE), rejection_count=len(REJECTION))
    if tmp is not None:
        intake.write_json(tmp / 'SUMMARY.json', summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    summary = run(args.output)
    printable = dict(
        passed=summary['passed'],
        reading_provenance=summary['reading_provenance'],
        positives=[(p['group'], p['case'], p['state'], p['verification'], p['independent_replay'])
                   for p in summary['positives']],
        rejections=[(r['case'], r['expected'], r['actual'], r['ok']) for r in summary['rejections']])
    print(json.dumps(printable, ensure_ascii=True, indent=1))
    raise SystemExit(0 if summary['passed'] else 1)


if __name__ == '__main__':
    main()
