"""Read-only projection invariants and old-entry replay; no LLM accuracy claim."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from fractions import Fraction
import json

import pytest

from cfm_id.research_spec_view import build_view, from_json, to_html


def values(view, facet):
    return {e.pointer: e.value for e in view.entries if e.facet == facet}


def test_snapshot_is_lossless_detached_and_never_approval():
    raw = {'study': {'nodes': ['乙', '甲'], 'context': '本周，固定雨天'},
           'target': {'first': [1, 0], 'second': [0, 1], 'operation': 'FIRST_MINUS_SECOND'},
           'first_stage_exclusion': {'status': 'NOT_ADOPTED', 'source_ids': ['s1']},
           'unresolved': [], 'additional_restrictions': None,
           'future/key~': {'missingness': False, 'one': 1, 'decimal': 1.0}}
    text = json.dumps(raw, ensure_ascii=False, indent=3)+'\n'
    review = {'decision': 'PENDING', 'source_hash': 'original'}
    result = {'state': 'REVIEW_REQUIRED', 'backend_called': False}
    original = deepcopy(raw)
    v = from_json(text, contract='network-facts', review=review, result=result)
    assert v.record_json == text and v.original_record() == original
    assert v.original_review() == review and v.original_result() == result
    assert v.as_dict()['is_approval'] is False and v.as_dict()['executable'] is False
    assert '/future~1key~0/missingness' in values(v, 'unmapped')
    assert values(v, 'assumptions')['/first_stage_exclusion/status'] == 'NOT_ADOPTED'
    assert '/unresolved' in values(v, 'unresolved')
    assert '/additional_restrictions' in values(v, 'assumptions')
    assert '/information' not in {e.pointer for e in v.entries}  # no default
    v.assert_current(raw)
    raw['target']['first'].reverse()
    review['decision'] = 'ACCEPTED'
    result['state'] = 'POINT'
    assert v.original_record() == original
    assert v.original_review()['decision'] == 'PENDING'
    assert v.original_result()['state'] == 'REVIEW_REQUIRED'
    with pytest.raises(ValueError, match='VIEW_SOURCE_CHANGED'):
        v.assert_current(raw)
    with pytest.raises(FrozenInstanceError):
        v.contract = 'direct'
    returned = v.original_record()
    returned['study']['nodes'].clear()
    assert v.original_record() == original


@pytest.mark.parametrize('text', ['{"x":1,"x":2}', '{"x":{"y":1,"y":2}}',
                                '{"x":NaN}', '{"x":1e999}', '[]'])
def test_ambiguous_or_non_json_input_is_not_normalized(text):
    with pytest.raises(ValueError):
        from_json(text, contract='compact')


def test_no_implicit_dataclass_tuple_fraction_or_contract_coercion():
    for raw in ({'x': (1, 2)}, {'x': Fraction(1, 3)}, {1: 'x'}):
        with pytest.raises(ValueError):
            build_view(raw, contract='compact')
    with pytest.raises(ValueError):
        build_view({}, contract='guessed')
    v = build_view({'x': 1}, contract='compact')
    for x in (True, 1.0, '1', None):
        with pytest.raises(ValueError):
            v.assert_current({'x': x})


def test_direct_answers_are_separate_and_html_is_escaped():
    raw = {'network_facts': {'assignment': {'value': {'kind': 'fixed', 'quota': 3},
            'evidence': [{'source_id': 'memo', 'quote': '恰好三家'}]}},
           'answers': [{'target': {'population': '<script>alert(1)</script>'},
                        'assumptions': [{'statement': '是否采用尚未决定'}],
                        'status': 'POINT', 'functional': '<img src=x onerror=alert(1)>'}]}
    v = build_view(raw, contract='direct')
    assert values(v, 'model_answer')['/answers/0/status'] == 'POINT'
    assert '/answers/0/status' not in values(v, 'assumptions')
    assert values(v, 'assumptions')['/answers/0/assumptions/0/statement'] == '是否采用尚未决定'
    rendered = to_html(v)
    assert '<script>' not in rendered and '<img src=x' not in rendered
    assert '&lt;script&gt;' in rendered and '不是科学审核摘要' in rendered


def test_compact_point_two_proofs_original_gate_and_handoff_unchanged():
    from tests_gateway.test_compact_entry import fixture, review
    from cfm_id.compact_entry import plan, complete, replay_delivery
    case, raw = fixture()
    prepared = plan(case, raw)
    approval = review(prepared)
    before = complete(prepared, approval, authority='SYNTHETIC_TEST')
    # The public view accepts saved JSON; native tuples use the existing JSON transport.
    saved_result = json.loads(json.dumps(before, ensure_ascii=False, allow_nan=False))
    v = build_view(raw, contract='compact', review=approval, result=saved_result)
    restored = plan(case, v.original_record())
    assert restored == prepared
    after = complete(restored, v.original_review(), authority='SYNTHETIC_TEST')
    assert after == before and v.original_result() == saved_result
    assert after['mathematical_claim']['value'] == '5/8'
    assert replay_delivery(restored, approval, after, authority='SYNTHETIC_TEST')
    assert replay_delivery(restored, approval, v.original_result(), authority='SYNTHETIC_TEST')
    # An unchanged view is not authorization; the original gate still rejects a stale goal.
    changed = v.original_record()
    changed['network']['policy'] = [0, 0]
    with pytest.raises(ValueError):
        complete(plan(case, changed), approval, authority='SYNTHETIC_TEST')
    approval['decisions']['target_and_source_reading'] = 'PENDING'
    assert not complete(restored, approval, authority='SYNTHETIC_TEST')['backend_called']
    missing = v.original_record()
    del missing['assumptions']['consistency']
    assert plan(case, build_view(missing, contract='compact').original_record()) == plan(case, missing)
    assert plan(case, missing)['state'] == 'NEEDS_INPUT'


@pytest.mark.parametrize('design,exposure', [('D1','E1'),('D2','E2'),('D3','E3'),('D4','E4'),
                                          ('D5','E5'),('D6','E4'),('D7','E1'),('D8','E2')])
def test_design_exposure_original_support_bounds_and_certificates_unchanged(design, exposure):
    from examples.finite_mean_box_reference import setup, approval_records
    from cfm_id import business_dispatch as dispatch
    s, options, spec, data = setup(design, exposure)
    raw = options['candidate']
    original = deepcopy(raw)
    v = build_view(raw, contract='network-facts')
    plan1 = dispatch.inspect_methods(s, 'q1', **options)
    options2 = {**options, 'candidate': v.original_record()}
    plan2 = dispatch.inspect_methods(s, 'q1', **options2)
    assert plan1 == plan2 and plan1['state'] == 'REVIEW_REQUIRED'
    approved = approval_records(plan1)
    before = dispatch.execute(s, 'q1', **options, **approved)
    after = dispatch.execute(s, 'q1', **options2, **approved)
    for key in ('state','mathematical_claim','certificate','independent_replay'):
        assert before[key] == after[key]
    assert after['independent_replay'] is True
    for cell in after['certificate']['cells']:
        assert Fraction(cell['support']) == spec['support'].get(tuple(cell['cell']), Fraction(0))
    assert raw == original == v.original_record()


@pytest.mark.parametrize('extra,missing', [(True, False), (False, True)])
def test_real_extra_constraint_and_unknown_closure_do_not_disappear(extra, missing):
    from examples.finite_mean_box_reference import setup
    from cfm_id import business_dispatch as dispatch
    s, options, _, _ = setup('D6', 'E4', extra=extra, missing=missing)
    v = build_view(options['candidate'], contract='network-facts')
    before = dispatch.inspect_methods(s, 'q1', **options)
    after = dispatch.inspect_methods(s, 'q1', **{**options, 'candidate': v.original_record()})
    assert before == after and not after['backend_called']
    assert after['state'] == ('ADAPTER_NOT_CONNECTED' if extra else 'NEEDS_INPUT')


@pytest.mark.parametrize('status', ['NOT_ADOPTED','UNDECIDED','NOT_STATED','CONFLICTING'])
def test_d6_exclusion_status_does_not_become_permission(status):
    from examples.finite_mean_box_reference import setup
    from cfm_id import business_dispatch as dispatch
    s, options, _, _ = setup('D6', 'E4')
    raw = options['candidate']
    raw['first_stage_exclusion']['status'] = status
    if status == 'NOT_STATED':
        raw['first_stage_exclusion']['source_ids'] = []
    v = build_view(raw, contract='network-facts')
    before = dispatch.inspect_methods(s, 'q1', **options)
    after = dispatch.inspect_methods(s, 'q1', **{**options, 'candidate': v.original_record()})
    assert before == after and not after['backend_called']
    assert values(v, 'assumptions')['/first_stage_exclusion/status'] == status


@pytest.mark.parametrize('mode,interval', [('BOTH',('1/5','1')), ('OWN',('-1/5','1')), ('NONE',('-1','1'))])
def test_mean_order_conditions_bounds_and_replay_unchanged(mode, interval):
    from examples.mean_order_fixture import make_problem, synthetic_review
    from cfm_id.mean_order_contract import MeanOrderProblem, ReviewedMeanOrder
    from cfm_id.mean_order import submit
    p = make_problem(mode=mode)
    review = synthetic_review(p)
    before = submit(p, review=review, synthetic_protocol_selected=True)
    v = build_view(p.model_dump(mode='json'), contract='mean-order', review=review.model_dump(mode='json'), result=before)
    after = submit(MeanOrderProblem.model_validate(v.original_record()),
                   review=ReviewedMeanOrder.model_validate(v.original_review()), synthetic_protocol_selected=True)
    assert after == before and after['bounded_certificate_replayed']
    assert (after['bounded_result']['lower'],after['bounded_result']['upper']) == interval
    assert values(v, 'assumptions')['/node_orders/0/mode'] == mode


def test_dag_problem_and_symbolic_formula_replay_unchanged():
    from examples.dag_backdoor_reference import make_problem, synthetic_review
    from cfm_id.dag_backdoor_contract import BackdoorProblem
    from cfm_id.dag_backdoor import submit
    p = make_problem()
    review = synthetic_review(p)
    before = submit(p, review=review, research_protocol_selected=True)
    v = build_view(p.model_dump(mode='json'), contract='dag-problem', result=before)
    after = submit(BackdoorProblem.model_validate(v.original_record()), review=review, research_protocol_selected=True)
    assert after == before and after['state'] == 'POINT'
    assert after['certificate']['numeric_value'] is None


def test_iv_population_scope_and_exact_result_unchanged():
    from examples.iv_research_fixture import make_problem, synthetic_review
    from cfm_id.iv_route_contract import IVProblem
    from cfm_id.iv_research import submit
    p = make_problem()
    review = synthetic_review(p)
    before = submit(p, review=review, research_protocol_selected=True)
    v = build_view(p.model_dump(mode='json'), contract='iv-problem', result=before)
    after = submit(IVProblem.model_validate(v.original_record()), review=review, research_protocol_selected=True)
    assert after == before and after['certificate_replayed']


@pytest.mark.parametrize('kind,count,degree,expected', [
    ('strict_majority_ties_low',0,0,0), ('strict_majority_ties_low',2,4,0),
    ('strict_majority_ties_low',3,4,1), ('three_level_treated_neighbor_fraction',1,3,1),
    ('three_level_treated_neighbor_fraction',2,3,2), ('three_level_treated_neighbor_fraction',0,0,None)])
def test_exposure_boundaries_remain_owned_by_existing_core(kind,count,degree,expected):
    from pfn_pipeline._internal.identification.randomized_arm_family.exposure import ExposureSpec
    v = build_view({'exposure': {'kind': kind}}, contract='network-facts')
    before = ExposureSpec(kind)
    after = ExposureSpec(v.original_record()['exposure']['kind'])
    if expected is None:
        for spec in (before,after):
            with pytest.raises(ValueError):
                spec.classify(count,degree)
    else:
        assert before.classify(count,degree) == after.classify(count,degree) == expected
