"""Meaning and compatibility boundaries of observational target attributes."""
from copy import deepcopy
from dataclasses import replace
import pytest

from cfm_id import research_spec_observational_adapters as a
from cfm_id.research_spec_observational import ObservedAllocationAverage, SharedStratumAverage, NodewiseFeatureAverage
from cfm_id.research_spec_local import LocalQuestion, ORIGINAL_DESIGN_CONDITIONAL
from cfm_id_llm.network_extended_reading import ObservationalEffectsReading
from examples.network_extended_reference import fixture


def reading(name):
    _, raw = fixture(name)
    return ObservationalEffectsReading.model_validate(raw)


@pytest.mark.parametrize('name,kind', [('observed',ObservedAllocationAverage),
    ('stratum',SharedStratumAverage),('nodewise',NodewiseFeatureAverage)])
def test_averaging_is_a_separate_object_from_fixed_w_and_outcome_period(name,kind):
    c=reading(name); q=a.from_effect_reading(c,c.information[0])
    assert type(q.averaging) is kind and not isinstance(q,LocalQuestion)
    assert q.study.context_reference == c.study.context
    assert q.fixed_background.definition == c.conditioning.definition
    if name!='observed':
        assert q.averaging.variable==c.information[0].adjustment_variable
        assert q.averaging.variable not in q.fixed_background.definition
    study=a.effect_native_study(q,network_id='n',edges=c.study.edges,protocol_provenance='explicit source',
        network_provenance='explicit network',graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    assert study.observation_regime=='observational' and study.assignment_design_json is None
    assert study.context_reference==c.study.context+'; fixed pretreatment W: '+c.conditioning.definition
    # A factorized observed law never grants a randomized design or approval.
    assert not hasattr(q,'scientific_approval') and not hasattr(q,'assumptions')


def test_target_changes_invalidate_coordinates_and_preserve_direction():
    c=reading('observed');q=a.from_effect_reading(c,c.information[0])
    original=a.effect_coordinates(q,exposure_kind=c.exposure.kind)
    a.require_effect_coordinates(q,original,exposure_kind=c.exposure.kind)
    for changed in (replace(q,study=replace(q.study,context_reference='另一期')),
                    replace(q,fixed_background=replace(q.fixed_background,definition='另一背景')),
                    replace(q,first=q.second,second=q.first)):
        with pytest.raises(ValueError,match='TARGET_PLAN_MISMATCH'):
            a.require_effect_coordinates(changed,original,exposure_kind=c.exposure.kind)
    reverse=replace(q,first=q.second,second=q.first)
    assert reverse.first==q.second
    with pytest.raises(ValueError,match='REVERSE_OWN_NOT_CONNECTED'):
        a.native_effect_request(reverse,cohort_evidence='fixed evaluation population')


def test_nodewise_adjustment_uses_all_neighbors_even_with_core_partner_exposure():
    _,raw=fixture('nodewise')
    raw['exposure'].update(kind='PRETREATMENT_CORE_COLLABORATOR_MAJORITY',
        core_collaborators={n:[] for n in raw['study']['nodes']})
    c=ObservationalEffectsReading.model_validate(raw)
    q=a.from_effect_reading(c,c.information[0])
    assert q.averaging.neighbor_reference=='ALL_STUDY_NEIGHBORS'
    assert q.averaging.feature_domain=='BINARY'
    assert a.effect_coordinates(q,exposure_kind=c.exposure.kind)['exposure']=='PRETREATMENT_CORE_COLLABORATOR_MAJORITY'
    # This assertion describes different reference sets; it does not assert
    # that the chosen zero-core target has mathematical support.


@pytest.mark.parametrize('name,wrong', [('observed','SHARED_PRETREATMENT_STRATUM'),
    ('stratum','OWN_AND_NEIGHBOR_BINARY_FEATURE'),('nodewise','OBSERVED_ALLOCATION_CONDITIONAL')])
def test_an_information_model_cannot_be_reused_for_a_different_averaging_target(name,wrong):
    _,raw=fixture(name);raw['target']['averaging']=wrong
    c=ObservationalEffectsReading.model_validate(raw)
    with pytest.raises(ValueError,match='POPULATION_OPERATOR_MISMATCH'):
        a.from_effect_reading(c,c.information[0])


def test_no_randomized_averaging_or_missing_background_is_defaulted():
    c=reading('observed');q=a.from_effect_reading(c,c.information[0])
    with pytest.raises(ValueError,match='OBSERVATIONAL_AVERAGING_REQUIRED'):
        replace(q,averaging=ORIGINAL_DESIGN_CONDITIONAL)
    _,raw=fixture('observed');raw['conditioning']['kind']='UNKNOWN'
    c=ObservationalEffectsReading.model_validate(raw)
    with pytest.raises(ValueError,match='FIXED_CONTEXT_REQUIRED'):
        a.from_effect_reading(c,c.information[0])


def test_observational_policy_has_separate_period_and_w_with_legacy_binding_preserved():
    import json
    from cfm_id.network_observational_policy_dispatch import target_coordinates
    from cfm_id_llm.network_observational_policy_reading import ObservationalPolicyReading
    from examples.network_observational_policy_reference import setup
    _,_,options=setup();raw=deepcopy(options['candidate'])
    c=ObservationalPolicyReading.model_validate(raw);q=a.from_policy_reading(c)
    p=a.policy_native_question(q)
    assert q.target.study.context_reference==c.study.context
    assert json.loads(p.study.context_reference)==dict(business_context=c.study.context,
        fixed_pretreatment_W=c.conditioning.definition)
    assert p.coordinates()==target_coordinates(c)
    assert options['candidate']==raw


def test_selected_information_source_is_not_implicitly_the_first_record():
    from cfm_id import network_extended_dispatch as d
    from examples.network_extended_reference import execute
    entry,raw=fixture('stratum');source=raw['information'][0]
    raw['information'].insert(0,dict(source_ids=source['source_ids'],operator='FINITE_SAMPLE',
        availability='FINITE_SAMPLE',outcome_nodes=source['outcome_nodes'],description='仅有样本记录'))
    p=d.inspect_methods(entry,raw)
    assert p['state']=='REVIEW_REQUIRED' and p['methods'][0]['source_index']==1
    r=execute(p)
    assert r['state']=='POINT' and r['independent_replay']
