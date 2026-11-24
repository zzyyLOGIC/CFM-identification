"""Observed study attributes -> existing native contracts, without new approval.

The two legacy context encodings are kept at this boundary for old worksheet
and certificate compatibility. Internally, outcome context and fixed W are
separate. The distribution of B or C_i is NOT appended to fixed W.
"""
from dataclasses import replace
from fractions import Fraction
import json

from .research_spec_coordinates import StudyCoordinates, Evaluation, native_study
from .research_spec_local import LocalState
from .research_spec_observational import (FixedBackground, ObservedAllocationAverage,
    SharedStratumAverage, NodewiseFeatureAverage, ObservationalEffectQuestion, ObservationalPolicyQuestion)
from . import research_spec_policy_adapters as policy


AVERAGING_OPERATORS = {
    'OBSERVED_ALLOCATION_CONDITIONAL': ('FINITE_ASSIGNMENT_LAW', 'FACTORIZED_ARM_LAW', 'MIXTURE_ARM_LAW'),
    'SHARED_PRETREATMENT_STRATUM': ('STRATIFIED_ARM_LAW',),
    'OWN_AND_NEIGHBOR_BINARY_FEATURE': ('NODEWISE_ARM_LAW', 'NODEWISE_MIXTURE_ARM_LAW'),
}


def population_operators(averaging):
    """One correspondence shared by intake validation and native construction."""
    return AVERAGING_OPERATORS.get(averaging, ())


def _background(c):
    if c.regime.kind != 'OBSERVATIONAL' or c.conditioning.kind != 'FIXED_PRETREATMENT_CONTEXT':
        raise ValueError('OBSERVATIONAL_FIXED_CONTEXT_REQUIRED')
    return FixedBackground(c.conditioning.definition)


def from_effect_reading(c, source):
    t, s = c.target, c.study
    if t.aggregation not in ('SINGLE', 'EQUAL_MEAN') or not t.population:
        raise ValueError('EXPLICIT_LOCAL_EVALUATION_REQUIRED')
    if t.aggregation == 'SINGLE' and len(t.population) != 1:
        raise ValueError('SINGLE_LOCAL_EVALUATION_REQUIRED')
    if source.operator not in population_operators(t.averaging):
        raise ValueError('TARGET_AVERAGING_AND_POPULATION_OPERATOR_MISMATCH')
    if t.averaging == 'OBSERVED_ALLOCATION_CONDITIONAL':
        average = ObservedAllocationAverage()
    elif t.averaging == 'SHARED_PRETREATMENT_STRATUM':
        average = SharedStratumAverage(source.adjustment_variable)
    else:
        average = NodewiseFeatureAverage(source.adjustment_variable)
    study = StudyCoordinates(tuple(s.nodes), s.treatment, s.outcome, s.outcome_kind.lower(), s.context)
    evaluation = Evaluation(tuple(t.population), tuple(
        str(Fraction(1, len(t.population))) if n in t.population else '0' for n in study.node_order))
    q = ObservationalEffectQuestion(study, evaluation, _background(c),
        LocalState(t.first.own, t.first.exposure), LocalState(t.second.own, t.second.exposure), t.operation, average)
    if q.effect_kind != t.kind:
        raise ValueError('LOCAL_EFFECT_LABEL_COORDINATES_DISAGREE')
    return q


def effect_coordinates(q, *, exposure_kind):
    s = q.study
    return dict(node_order=list(s.node_order), population=list(q.evaluation.population),
        unit_weights=list(q.evaluation.unit_weights), treatment=s.treatment_definition,
        outcome=s.outcome_definition, context=s.context_reference,
        first=list(q.first.coordinates()), exposure=exposure_kind, averaging=q.averaging.kind,
        kind=q.effect_kind, second=list(q.second.coordinates()), fixed_context=q.fixed_background.definition)


def require_effect_coordinates(q, recorded, *, exposure_kind):
    from cfm_id_bridge.scientific_binding import sha
    if sha(effect_coordinates(q, exposure_kind=exposure_kind)) != sha(recorded):
        raise ValueError('TARGET_PLAN_MISMATCH')


def effect_native_study(q, **kwargs):
    s = replace(q.study, context_reference=q.study.context_reference + '; fixed pretreatment W: ' + q.fixed_background.definition)
    return native_study(s, observation_regime='observational', assignment_design=None, **kwargs)


def native_effect_request(q, *, cohort_evidence):
    from pfn_pipeline.identification_composition import EffectQueryV18
    # Do not silently broaden this native entry to reversed-own named effects.
    if q.effect_kind != 'SPILLOVER_EFFECT' and q.first.own != 1:
        raise ValueError('NATIVE_OBSERVATIONAL_NAMED_EFFECT_REVERSE_OWN_NOT_CONNECTED')
    return EffectQueryV18({'DIRECT_EFFECT': 'DIRECT', 'SPILLOVER_EFFECT': 'SPILLOVER',
                          'LOCAL_TOTAL_EFFECT': 'TOTAL'}[q.effect_kind],
        q.selected_weights(), q.second.exposure, q.first.exposure, spillover_own_treatment=q.first.own,
        cohort_authority='TRUSTED_FIXTURE', cohort_evidence=cohort_evidence)


def from_policy_reading(c):
    return ObservationalPolicyQuestion(policy.from_reading(c), _background(c))


def policy_native_question(q):
    p = q.target
    context = json.dumps(dict(business_context=p.study.context_reference,
                              fixed_pretreatment_W=q.fixed_background.definition), sort_keys=True, ensure_ascii=False)
    return replace(p, study=replace(p.study, context_reference=context))
