"""Canonical attributes really construct native inputs, without restoring JSON."""
from dataclasses import replace
import pytest

from cfm_id.research_spec_policy import (StudyCoordinates, Evaluation, FixedPolicy,
                                        PolicyQuestion, ordered_difference)
from cfm_id import research_spec_policy_adapters as adapters


def question():
    # Deliberately not alphabetical; a zero weight does not remove a policy node.
    return PolicyQuestion(StudyCoordinates(('乙', '甲', '丙'), '使用助手：1是，0否', '下周评分',
                                         'continuous', '下周；保持原有配送区域'),
                          Evaluation(('乙', '丙'), ('1/3', '0', '2/3')),
                          FixedPolicy((0, 1, 1)), None, 'MEAN')


def study(q):
    return adapters.native_study(q, network_id='network_attributes', edges=(('乙', '甲'), ('甲', '丙')),
        assignment_design=dict(kind='complete_randomization_binary_v1', m=1),
        protocol_provenance='原设计每轮等概率选一家', network_provenance='研究前固定的合作关系',
        observation_regime='experimental', graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def test_attributes_construct_a_native_question_without_a_legacy_record():
    q = question()
    native = study(q)
    target = adapters.native_target(q, native, side='first', authority='TRUSTED_FIXTURE')
    assert target.node_order == ('乙', '甲', '丙')
    assert target.policy_assignment == (0, 1, 1)
    assert target.unit_weights == ('1/3', '0', '2/3')
    assert target.context == '下周；保持原有配送区域'
    assert target.outcome == '下周评分'
    assert not hasattr(q, 'legacy') and not hasattr(q, 'projection')
    # Design has quota 1; the target treats 2 nodes. These are distinct attributes.
    assert '"m":1' in native.assignment_design_json
    assert sum(target.policy_assignment) == 2


def test_changed_attributes_change_native_inputs_instead_of_using_a_saved_target():
    q = question()
    changed = replace(q, first=FixedPolicy((1, 0, 0)),
        evaluation=Evaluation(('甲',), ('0', '1', '0')),
        study=replace(q.study, context_reference='下下周；只固定配送区域'))
    target = adapters.native_target(changed, study(changed), side='first', authority='TRUSTED_FIXTURE')
    assert target.policy_assignment == (1, 0, 0)
    assert target.unit_weights == ('0', '1', '0')
    assert target.context == '下下周；只固定配送区域'
    with pytest.raises(ValueError, match='COORDINATES_CHANGED'):
        changed.require_coordinates(q.coordinates())
    with pytest.raises(ValueError, match='NATIVE_STUDY_COORDINATES_CHANGED'):
        adapters.native_target(changed, study(q), side='first', authority='TRUSTED_FIXTURE')


def test_ordered_endpoints_share_context_and_evaluation_but_not_assignments():
    a = question(); b = replace(a, first=FixedPolicy((1, 0, 0)))
    pair = ordered_difference(a, b)
    assert pair.study is a.study and pair.evaluation is a.evaluation
    assert pair.coordinates()['first'] == [0, 1, 1]
    assert pair.coordinates()['second'] == [1, 0, 0]
    assert ordered_difference(b, a).coordinates()['first'] == [1, 0, 0]
    assert pair.operation == 'FIRST_MINUS_SECOND'
    for wrong in (replace(b, study=replace(b.study, context_reference='另一周')),
                  replace(b, evaluation=Evaluation(('乙', '丙'), ('2/3', '0', '1/3')))):
        with pytest.raises(ValueError, match='COMMON_EVALUATION_AND_CONTEXT'):
            ordered_difference(a, wrong)


@pytest.mark.parametrize('mutation', [
    lambda q: replace(q, first=FixedPolicy((1, 0))),
    lambda q: replace(q, first=FixedPolicy((True, 0, 1))),
    lambda q: replace(q, study=replace(q.study, node_order=('乙', '乙', '丙'))),
    lambda q: replace(q, study=replace(q.study, context_reference='')),
    lambda q: replace(q, evaluation=Evaluation(('乙',), ('1/3', '0', '2/3'))),
    lambda q: replace(q, evaluation=Evaluation(('乙', '丙'), ('1/3', '0', '1/3'))),
    lambda q: replace(q, evaluation=Evaluation(('乙', '丙'), ('-1', '0', '2'))),
    lambda q: replace(q, operation='UNKNOWN'),
    lambda q: replace(q, operation='FIRST_MINUS_SECOND'),
])
def test_unknown_or_conflicting_attributes_do_not_get_defaults(mutation):
    with pytest.raises((ValueError, TypeError)):
        mutation(question())


def test_exact_original_weight_strings_are_retained_for_existing_bindings():
    q = replace(question(), evaluation=Evaluation(('乙', '丙'), ('2/4', '0', '2/4')))
    target = adapters.native_target(q, study(q), side='first', authority='TRUSTED_FIXTURE')
    assert q.coordinates()['unit_weights'] == ['2/4', '0', '2/4']
    # The unchanged native constructor already normalizes rational numbers.
    assert target.unit_weights == ('1/2', '0', '1/2')


def test_reading_constructor_does_not_adopt_unknown_or_rejected_science():
    from examples.network_dispatch_reference import setup
    from cfm_id import business_dispatch as dispatch
    from cfm_id_llm.network_policy_reading import NetworkPolicyReading
    _, _, options, plan = setup(design='D1', sufficiency=False)
    facts = plan['facts']
    q = adapters.from_reading(NetworkPolicyReading.model_validate(facts))
    assert q.coordinates() == plan['proposed_target']
    for value in (False, None):
        s, _, opts, _ = setup(design='D1', sufficiency=False)
        opts['candidate']['assumptions']['consistency']['value'] = value
        stopped = dispatch.inspect_methods(s, 'q1', **opts)
        assert stopped['state'] in ('NEEDS_INPUT', 'ADAPTER_NOT_CONNECTED')
        assert not stopped['backend_called']


def test_endpoint_facts_cannot_silently_use_stale_reviewed_coordinates():
    from examples.network_dispatch_reference import setup, approval_records
    from cfm_id import network_policy_dispatch as dispatch
    _, _, _, plan = setup(design='D1', sufficiency=False)
    row = plan['methods'][0]
    records = approval_records(plan)['native_reviews'][row['method']]
    plan['proposed_target']['assignment'][0] ^= 1
    with pytest.raises(ValueError, match='COORDINATES_CHANGED'):
        dispatch._compile(plan, row, records, 'SYNTHETIC_TEST')


@pytest.mark.parametrize('change', ['boolean', 'weights', 'context', 'second'])
def test_material_and_target_disagreement_cannot_be_silently_repaired(change):
    q = question()
    materials = dict(nodes=list(q.study.node_order), treatment=q.study.treatment_definition,
        outcome=q.study.outcome_definition, period=q.study.context_reference,
        weights=list(q.evaluation.unit_weights), first=[0, 1, 1], second=[1, 0, 0])
    target = dict(node_order=materials['nodes'], treatment=materials['treatment'], outcome=materials['outcome'],
        context=materials['period'], population=list(q.evaluation.population), unit_weights=list(q.evaluation.unit_weights),
        kind='FIXED_POLICY_CONTRAST', first=[0, 1, 1], second=[1, 0, 0], operation='FIRST_MINUS_SECOND')
    assert adapters.from_materials(materials, target).first.assignment == (0, 1, 1)
    if change == 'boolean': target['first'][1] = True
    if change == 'weights': target['unit_weights'] = ['2/3', '0', '1/3']
    if change == 'context': target['context'] = '另一期'
    if change == 'second': target['second'] = [0, 0, 1]
    with pytest.raises(ValueError):
        adapters.from_materials(materials, target)
