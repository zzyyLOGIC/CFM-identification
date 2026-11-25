"""Preparation explanations must not become review or proof authority."""
from copy import deepcopy
import pytest

from cfm_id import business_dispatch as dispatch, capability_registry, method_matching, project
from cfm_id.policy_methods import FULL_POLICY, SIGNATURE_POLICY
from examples import network_dispatch_reference as policy
from examples import network_effect_dispatch_reference as local
from examples import network_observational_policy_reference as observed
from examples import network_extended_reference as extended
from examples import network_contrast_dispatch_reference as contrast
from examples import business_dispatch_reference as dag, dag_business_reference


def prepared(name):
    if name == 'policy':
        s, e, options, plan = policy.setup()
    elif name == 'local':
        s, e, options, plan = local.setup()
    elif name == 'observed_policy':
        s, e, options = observed.setup()
        plan = dispatch.inspect_methods(s, 'q1', **options)
    elif name == 'contrast':
        s, e, options = contrast.setup()
        plan = dispatch.inspect_methods(s, 'q1', **options)
    elif name == 'dag':
        s, options, plan = dag.prepare(dag_business_reference.cases()[0])
    else:
        s, options, plan = extended.setup(name)
    reader = dispatch.prepare_reader(s, 'q1', query_review=options['query_review'])['reader_id']
    return s, options, plan, reader


@pytest.mark.parametrize('name', ['policy', 'contrast', 'local', 'observed_policy', 'arm', 'mixture', 'observed', 'dag'])
def test_all_common_readers_report_actual_candidates_and_stale_record(name):
    s, options, plan, reader = prepared(name)
    report = plan[method_matching.REPORT_KEY]
    before = deepcopy(plan)
    assert report == project.explain_method_plan(plan, reader_id=reader)
    assert method_matching.verify_report(plan, report, reader_id=reader)
    assert {c['method_id'] for c in report['candidates']} == {
        m.method_id for m in capability_registry.business_binding(reader).methods}
    assert {c['method_id'] for c in report['candidates'] if c['status'] == 'CANDIDATE_REQUIRES_REVIEW'} == {
        m['method'] for m in plan['methods']}
    assert not report['grants_execution'] and not report['mathematical_applicability_checked']
    for item in report['candidates']:
        assert item['theorem_applicability'] == 'NOT_ESTABLISHED'
    plan['query_id'] = 'changed-question'
    assert not method_matching.verify_report(plan, report, reader_id=reader)
    assert before['query_id'] == 'q1'


def test_unknown_and_refused_sufficiency_are_distinct_without_new_permission():
    for value, expected in [(None, 'DECLARATION_OR_INFORMATION_UNRESOLVED'), (False, 'EXCLUDED_BY_PREPARATION')]:
        s, e, options, _ = policy.setup()
        options['candidate']['mean_sufficiency'].update(value=value)
        plan = dispatch.inspect_methods(s, 'q1', **options)
        report = plan[method_matching.REPORT_KEY]
        rows = {r['method_id']: r for r in report['candidates']}
        assert rows[SIGNATURE_POLICY]['status'] == expected
        assert rows[FULL_POLICY]['status'] == 'CANDIDATE_REQUIRES_REVIEW'
        assert rows['BOUNDED_POLICY_MEAN_D2_E1']['status'] == 'NOT_ASSESSED'
        assert not report['automatic_fallback'] and not report['nonidentification_proved']
        records = policy.approval_records(plan)
        refused = dispatch.execute(s, 'q1', **options, plan_review=report,
            native_reviews=records['native_reviews'], research_protocol_selected=True)
        assert not refused['backend_called']


def test_explanation_is_read_only_and_malformed_method_records_are_rejected(monkeypatch):
    s, options, plan, reader = prepared('policy')
    before = deepcopy(plan)
    def forbidden(*args, **kwargs):
        raise AssertionError('explanation ran a mathematical solver')
    from pfn_pipeline import identification_policy_r1b
    monkeypatch.setattr(identification_policy_r1b, 'identify_verified_fixed_policy', forbidden)
    method_matching.explain(plan, reader_id=reader)
    assert plan == before
    for methods in ([plan['methods'][0]] * 2, [dict(method='made.up.method')]):
        with pytest.raises(ValueError, match='UNKNOWN_OR_DUPLICATE'):
            method_matching.explain(dict(plan, methods=methods), reader_id=reader)
    with pytest.raises(ValueError, match='READER_PLAN_MISMATCH'):
        method_matching.explain(plan, reader_id='VARIABLE_DAG_FACTS')


def test_missing_condition_is_common_stop_not_theorem_rejection():
    s, e, options, _ = policy.setup()
    options['candidate']['assumptions']['consistency']['value'] = None
    plan = dispatch.inspect_methods(s, 'q1', **options)
    report = plan[method_matching.REPORT_KEY]
    assert plan['state'] == report['source_state'] == 'NEEDS_INPUT'
    assert report['clarification_questions']
    assert all(c['status'] == 'NOT_ASSESSED' for c in report['candidates'])
    assert not report['nonidentification_proved']
