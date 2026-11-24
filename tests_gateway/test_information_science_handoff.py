"""Source ownership and scientific admission across maintained network readers.

These are deterministic interface tests, not LLM accuracy measurements. Inputs
are frozen reference readings; invalid fields must never be silently repaired.
"""
from copy import deepcopy

import pytest

from cfm_id import business_dispatch as dispatch
from cfm_id import network_extended_dispatch as extended
from examples import network_extended_reference as ref


def inspect(name, change):
    entry, raw = ref.fixture(name)
    change(raw)
    before = deepcopy(raw)
    plan = extended.inspect_methods(entry, raw)
    assert raw == before
    return plan


@pytest.mark.parametrize('name', ['arm', 'mixture'])
@pytest.mark.parametrize('value', [False, None])
def test_assignment_availability_is_a_gap_not_scientific_rejection(name, value):
    plan = inspect(name, lambda r: r['assumptions']['known_assignment_law'].update(value=value))
    assert plan['state'] == 'NEEDS_INPUT'
    assert plan['facts']['assumptions']['known_assignment_law']['value'] is value
    assert not plan['backend_called']
    assert not any('DECLARED_MODEL_EXCLUDES' in v for v in plan.get('unsupported_reasons', []))


@pytest.mark.parametrize('name', ['observed', 'stratum', 'nodewise'])
@pytest.mark.parametrize('value', [False, None])
@pytest.mark.parametrize('declaration', ['complete_law_and_mean_scope', 'same_study_and_context'])
def test_population_scope_does_not_become_a_causal_assumption(name, value, declaration):
    plan = inspect(name, lambda r: r['information'][0][declaration].update(value=value))
    assert plan['state'] == 'NEEDS_INPUT'
    assert plan['facts']['information'][0][declaration]['value'] is value
    assert len(plan['clarification_questions']) == 1
    assert not plan['backend_called']


@pytest.mark.parametrize('value', [False, None, True])
def test_partial_policy_list_is_not_normalized_or_certified(value):
    def change(r):
        r['target']['components'] = r['target']['components'][:1]
        r['target']['policy_distribution_complete']['value'] = value
    plan = inspect('mixture', change)
    assert plan['state'] == ('CHECK_BLOCKED' if value is True else 'NEEDS_INPUT')
    assert plan['facts']['target']['components'][0]['weight'] == '1/4'
    assert not plan['backend_called']


@pytest.mark.parametrize('value', [False, None, True])
def test_partial_observed_law_is_not_normalized_or_certified(value):
    def change(r):
        s = r['information'][0]
        s.pop('probabilities'); s.pop('covered_cells')
        s.update(operator='FINITE_ASSIGNMENT_LAW', assignment_masses=[dict(
            source_ids=s['source_ids'], assignment=dict.fromkeys(ref.NODES, 0), probability='1/2')])
        s['complete_law_and_mean_scope']['value'] = value
    plan = inspect('observed', change)
    assert plan['state'] == ('CHECK_BLOCKED' if value is True else 'NEEDS_INPUT')
    assert plan['facts']['information'][0]['assignment_masses'][0]['probability'] == '1/2'
    assert not plan['backend_called']


@pytest.mark.parametrize('name', ['arm', 'mixture'])
def test_full_law_cannot_silently_discard_a_cell_table(name):
    def change(r):
        s = r['information'][0]
        if name == 'arm':
            s['arm_cells'] = [dict(node=ref.NODES[0], own=1, exposure=0)]
        else:
            s['assignment_cells'] = [[1, 0, 0]]
    plan = inspect(name, change)
    assert plan['state'] == 'CHECK_BLOCKED'
    assert ('ARM_CELLS_REQUIRE_ARM_INFORMATION' if name == 'arm'
            else 'ASSIGNMENT_CELLS_WITH_OTHER_OPERATOR') in plan['diagnostic']
    assert not plan['backend_called']


@pytest.mark.parametrize('invalid', ['duplicate', 'outside_source', 'invalid_exposure', 'invalid_own'])
def test_single_arm_checks_all_supplied_cells_including_unused_ones(invalid):
    def change(r):
        s = r['information'][0]
        cell = dict(node=ref.NODES[0], own=1, exposure=0)
        extra = dict(cell)
        if invalid == 'outside_source': extra['node'] = ref.NODES[1]
        if invalid == 'invalid_exposure': extra['exposure'] = 2
        if invalid == 'invalid_own': extra['own'] = 2
        s.update(operator='NODE_ARM_MEANS', outcome_nodes=ref.NODES[:1], arm_cells=[cell, extra])
    plan = inspect('arm', change)
    assert plan['state'] == 'CHECK_BLOCKED'
    assert not plan['backend_called']


@pytest.mark.parametrize('invalid', ['duplicate', 'dimension', 'binary'])
def test_finite_policy_checks_all_assignment_cells(invalid):
    def change(r):
        extra = [1, 0, 0] if invalid == 'duplicate' else [0, 1] if invalid == 'dimension' else [0, 0, 2]
        r['information'][0].update(operator='ASSIGNMENT_NODE_MEANS',
                                    assignment_cells=[[1, 0, 0], [0, 1, 0], extra])
    plan = inspect('mixture', change)
    assert plan['state'] == 'CHECK_BLOCKED'
    assert not plan['backend_called']


@pytest.mark.parametrize('name', ['arm', 'mixture'])
def test_partial_outcome_scope_is_not_a_full_joint_law(name):
    def change(r):
        r['target']['population'] = ref.NODES[:1]
        r['information'][0].update(operator='FULL_JOINT_LAW', outcome_nodes=ref.NODES[:1])
    plan = inspect(name, change)
    assert plan['state'] == 'READING_RECHECK_REQUIRED'
    assert plan['reason_code'] == 'FULL_JOINT_LAW_REQUIRES_FULL_OUTCOME_SCOPE'
    assert not plan['backend_called']


@pytest.mark.parametrize('name', ['arm', 'mixture', 'observed', 'stratum', 'nodewise'])
@pytest.mark.parametrize('value', [False, None])
def test_actual_scientific_nonadoption_and_unknown_still_stop(name, value):
    plan = inspect(name, lambda r: r['assumptions']['consistency'].update(value=value))
    assert plan['state'] == ('NEEDS_INPUT' if value is None else 'ADAPTER_NOT_CONNECTED')
    assert plan['facts']['assumptions']['consistency']['value'] is value
    assert not plan['backend_called']


@pytest.mark.parametrize('name', ['stratum', 'nodewise'])
def test_scientific_scope_cannot_be_expanded_to_all_assignments(name):
    plan = inspect(name, lambda r: r['assumptions']['potential_outcome_exposure_sufficiency'].update(scope='OTHER'))
    assert plan['state'] == 'ADAPTER_NOT_CONNECTED'
    assert 'SCIENTIFIC_SCOPE_NOT_CONNECTED' in plan['reason_code']
    assert not plan['backend_called']


@pytest.mark.parametrize('name', ['arm', 'mixture'])
@pytest.mark.parametrize('status,state', [('CONFLICTING', 'READING_RECHECK_REQUIRED'),
    ('NOT_ADOPTED', 'ADAPTER_NOT_CONNECTED'), ('UNDECIDED', 'NEEDS_INPUT')])
def test_first_stage_scientific_states_remain_distinct(name, status, state):
    def change(r):
        ids = r['assignment']['source_ids']
        r['assignment'] = dict(source_ids=ids, kind='TWO_STAGE_QUOTA_MIXTURE',
            probabilities=None, fixed_count=None, groups=[ref.NODES[:1], ref.NODES[1:]],
            quota_profiles=[[1, 0], [0, 1]], profile_probabilities=['1/2', '1/2'])
        r['first_stage_exclusion'] = dict(status=status, source_ids=ids)
    plan = inspect(name, change)
    assert plan['state'] == state, plan
    assert not plan['backend_called']


@pytest.mark.parametrize('name', ['arm', 'mixture', 'observed', 'stratum', 'nodewise'])
@pytest.mark.parametrize('record', ['information', 'science'])
def test_updated_conditions_or_information_cannot_reuse_previous_reviews(name, record):
    session, options, plan = ref.setup(name)
    records = {row['method']: dict(reading_review=ref.approve(row['reading_worksheet']),
                                  science_review=ref.approve(row['science_worksheet'])) for row in plan['methods']}
    candidate = deepcopy(options['candidate'])
    # A semantically equivalent but newly sourced record still has a new binding.
    changed = candidate['information'][0] if record == 'information' else candidate['assumptions']['consistency']
    changed['source_ids'] = list(reversed(changed['source_ids']))
    assert candidate != options['candidate']
    result = dispatch.execute(session, 'q1', **dict(options, candidate=candidate),
        plan_review=ref.approve(plan['plan_worksheet']), native_reviews=records, research_protocol_selected=True)
    assert not result['backend_called']
    assert result['state'] != 'POINT'


@pytest.mark.parametrize('name', ['arm', 'mixture', 'observed', 'stratum', 'nodewise'])
def test_valid_plan_keeps_sample_separate_and_requires_science_review(name):
    entry, raw = ref.fixture(name)
    sample = dict(source_ids=raw['information'][0]['source_ids'], operator='FINITE_SAMPLE',
                  availability='FINITE_SAMPLE', outcome_nodes=ref.NODES[:1])
    if name == 'arm': sample['arm_cells'] = []
    elif name == 'mixture': sample['assignment_cells'] = []
    else: sample['description'] = 'Finite records only; separate from the declared population source.'
    raw['information'].insert(0, sample)
    plan = extended.inspect_methods(entry, raw)
    assert plan['state'] == 'REVIEW_REQUIRED', plan
    assert plan['methods'][0]['source_index'] == 1
    assert plan['facts']['information'][0]['availability'] == 'FINITE_SAMPLE'
    pending = extended._execute_plan(plan, research_protocol_selected=True)
    assert not pending['backend_called']
    row = plan['methods'][0]
    for decision in ('PENDING', 'REJECTED'):
        science = ref.approve(row['science_worksheet']).model_dump(mode='json')
        science['decisions']['consistency'] = decision
        result = extended._execute_plan(plan, plan_review=ref.approve(plan['plan_worksheet']),
            native_reviews={row['method']: dict(reading_review=ref.approve(row['reading_worksheet']), science_review=science)},
            research_protocol_selected=True)
        assert not result['backend_called']
    result = ref.execute(plan)
    assert result['state'] == 'POINT', result
    assert result['independent_replay'] is True
