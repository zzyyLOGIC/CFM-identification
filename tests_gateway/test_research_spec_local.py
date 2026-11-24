"""Target semantics and construction boundaries for local comparisons."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import pytest

from cfm_id.research_spec_coordinates import StudyCoordinates, Evaluation
from cfm_id.research_spec_local import LocalState, LocalQuestion, ORIGINAL_DESIGN_CONDITIONAL
from cfm_id import research_spec_local_adapters as adapters


def question(first=(1, 1), second=(0, 1)):
    return LocalQuestion(StudyCoordinates(('乙', '甲', '丙'), '启用助手', '本周评分', 'continuous', '本周固定背景'),
        Evaluation(('丙', '乙'), ('1/3', '0', '2/3')), LocalState(*first), LocalState(*second),
        'FIRST_MINUS_SECOND', ORIGINAL_DESIGN_CONDITIONAL)


def test_local_coordinates_produce_native_terms_without_a_legacy_json():
    from pfn_pipeline.identification_composition import compile_effect_query_terms
    q = question()
    request = adapters.native_request(q, authority='SYNTHETIC_TEST', cohort_evidence='Explicit original evaluation roster.')
    terms = compile_effect_query_terms(request)
    assert tuple((*t.coordinates, t.coefficient) for t in terms) == q.signed_terms()
    assert request.node_weights == (('丙', Fraction(2, 3)), ('乙', Fraction(1, 3)))
    assert not hasattr(q.first, 'assignment') and not hasattr(q, 'projection')
    # A zero-weight unit remains a member of the complete network, not the cohort.
    assert q.study.node_order == ('乙', '甲', '丙')
    assert all(term[0] != '甲' for term in q.signed_terms())


@pytest.mark.parametrize('first,second,kind', [((1, 1), (0, 1), 'DIRECT_EFFECT'),
    ((0, 1), (0, 0), 'SPILLOVER_EFFECT'), ((1, 1), (0, 0), 'LOCAL_TOTAL_EFFECT'),
    ((0, 0), (1, 1), 'LOCAL_TOTAL_EFFECT')])
def test_coordinate_changes_determine_description_without_selecting_a_solver(first, second, kind):
    q = question(first, second)
    assert q.effect_kind == kind
    reverse = replace(q, first=q.second, second=q.first)
    assert reverse.effect_kind == kind
    a = {(n, own, e): w for n, own, e, w in q.signed_terms()}
    b = {(n, own, e): w for n, own, e, w in reverse.signed_terms()}
    assert b == {k: -v for k, v in a.items()}


def test_reverse_total_effect_preserves_order_through_existing_linear_api():
    from pfn_pipeline.identification_composition import ArmLinearTerm
    q = question((0, 0), (1, 1))
    request = adapters.native_request(q, authority='SYNTHETIC_TEST', cohort_evidence='Fixed before randomization.')
    assert isinstance(request, tuple) and all(isinstance(t, ArmLinearTerm) for t in request)
    assert tuple((*t.coordinates, t.coefficient) for t in request) == q.signed_terms()
    assert q.first.coordinates() == (0, 0)  # no endpoint swap or fixed assignment


@pytest.mark.parametrize('remaining', ['UNKNOWN', 'FIXED_FULL_ASSIGNMENT', '', None])
def test_other_assignments_are_never_defaulted_to_the_original_design(remaining):
    with pytest.raises(ValueError, match='ORIGINAL_CONDITIONAL_DESIGN_REQUIRED'):
        replace(question(), remaining_assignment=remaining)


@pytest.mark.parametrize('state', [(True, 1), (1, False), (None, 1), (1, None), (2, 1), (1, -1), (1, '')])
def test_unknown_or_malformed_local_states_cannot_be_used(state):
    with pytest.raises(ValueError): LocalState(*state)


def test_weighted_and_grouped_coordinates_stay_exact_until_native_validation():
    q = question((1, '[1, 0]'), (0, '[1, 0]'))
    assert q.first.exposure == '[1, 0]' and q.effect_kind == 'DIRECT_EFFECT'
    changed = replace(q, second=LocalState(0, '1/3'))
    assert changed.effect_kind == 'LOCAL_TOTAL_EFFECT'
    # Defining a coordinate cannot assert that it has support under a design.
    assert not hasattr(q, 'positive_support') and not hasattr(q, 'scientific_approval')


def test_stale_target_or_design_cannot_reuse_the_original_plan():
    from examples.network_effect_dispatch_reference import setup
    from cfm_id.network_effect_dispatch import canonical_model
    _, _, _, plan = setup()
    c = canonical_model(plan).model_validate(plan['facts'])
    q = adapters.from_reading(c)
    adapters.require_reading_coordinates(c, q, plan['proposed_target'])
    for changed in (replace(q, first=q.second, second=q.first),
                    replace(q, study=replace(q.study, context_reference='另一期'))):
        with pytest.raises(ValueError, match='TARGET_PLAN_MISMATCH'):
            adapters.require_reading_coordinates(c, changed, plan['proposed_target'])
    new_c = deepcopy(c)
    new_c.assignment.probabilities[next(iter(new_c.assignment.probabilities))] = '1/4'
    with pytest.raises(ValueError, match='TARGET_PLAN_MISMATCH'):
        adapters.require_reading_coordinates(new_c, q, plan['proposed_target'])


def test_source_event_constructs_coordinates_without_inventing_an_outcome_domain():
    facts = dict(contrast=dict(kind='original_local',population=['丙','乙'],weights=['2/3','1/3'],
        ends=[[1,1],[0,1]],variable='启用助手',outcome='本周评分',time='本周',remaining='按原抽签规则平均'),
        network=dict(nodes=['乙','甲','丙']), science={'not_adopted':'sufficiency'})
    before = deepcopy(facts)
    q = adapters.from_event_facts(facts)
    assert q.study.outcome_domain is None
    assert q.evaluation.unit_weights == ('1/3', '0', '2/3')
    changed = replace(q, first=LocalState(0,0), second=LocalState(1,0),
                      study=replace(q.study, context_reference='下周'))
    out = adapters.event_inputs(facts, changed)
    assert out['contrast']['ends'] == [[0,0],[1,0]] and out['contrast']['time'] == '下周'
    assert out['science'] == before['science'] and facts == before
    from cfm_id.research_spec_policy_adapters import native_study
    with pytest.raises(ValueError, match='OUTCOME_DOMAIN_REQUIRED'):
        native_study(q, network_id='n', edges=[], assignment_design=None, observation_regime='experimental',
                     protocol_provenance='source', network_provenance='source', graph_timing_claim='UNRESOLVED')


def test_shared_coordinates_have_one_definition_with_old_policy_import_compatible():
    from cfm_id.research_spec_policy import StudyCoordinates as OldStudy, Evaluation as OldEvaluation
    assert OldStudy is StudyCoordinates and OldEvaluation is Evaluation
