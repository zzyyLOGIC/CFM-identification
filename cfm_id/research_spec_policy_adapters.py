"""Boundary adapters for the internal fixed-policy attributes.

Reading formats stay unchanged. A period/background string is retained exactly;
this adapter cannot recover separate fields the original contract never stored.
Binary codes come from the existing contract, not inferred treatment meanings.
Scientific declarations, evidence, reviews and permissions remain with callers.
"""
from fractions import Fraction

from .research_spec_policy import (StudyCoordinates, Evaluation, FixedPolicy,
                                   PolicyQuestion, ordered_difference)


def from_reading(c):
    if c.target.kind != 'FIXED_POLICY_MEAN' or c.target.aggregation != 'EQUAL_MEAN':
        raise ValueError('FIXED_EQUAL_MEAN_READING_REQUIRED')
    s, t = c.study, c.target
    study = StudyCoordinates(tuple(s.nodes), s.treatment, s.outcome, s.outcome_kind.lower(), s.context)
    if not t.population or len(set(t.population)) != len(t.population):
        raise ValueError('EXPLICIT_UNIQUE_POLICY_POPULATION_REQUIRED')
    if t.assignment is None or set(t.assignment) != set(study.node_order):
        raise ValueError('EXACT_FULL_POLICY_ASSIGNMENT_REQUIRED')
    evaluation = Evaluation(tuple(t.population), tuple(
        str(Fraction(1, len(t.population))) if n in t.population else '0' for n in study.node_order))
    return PolicyQuestion(study, evaluation, FixedPolicy(tuple(t.assignment[n] for n in study.node_order)), None, 'MEAN')


def from_endpoint_plans(plans):
    from cfm_id_llm.network_policy_reading import NetworkPolicyReading
    questions = []
    for side in ('first', 'second'):
        q = from_reading(NetworkPolicyReading.model_validate(plans[side]['facts']))
        q.require_coordinates(plans[side]['proposed_target'])
        questions.append(q)
    return ordered_difference(*questions)


def from_compact(reading):
    if reading.target.kind != 'policy_mean':
        raise ValueError('COMPACT_FIXED_POLICY_MEAN_REQUIRED')
    n, t = reading.network, reading.target
    s = StudyCoordinates(tuple(n.nodes), t.treatment, t.outcome, n.outcome_kind, t.context)
    # This contract supplies a weight for every registered unit. Zero weights
    # remain zero; the free-text population description stays in the source review.
    return PolicyQuestion(s, Evaluation(s.node_order, tuple(n.weights)), FixedPolicy(tuple(n.policy)), None, 'MEAN')


def from_materials(m, target, *, legacy_all_enabled=False):
    """Accept already source-checked material, not arbitrary text or model output.

    legacy_all_enabled identifies the existing bounded-signature-mean contract;
    it is not a default for unprovided policies. The caller must name that case.
    """
    s = StudyCoordinates(tuple(m['nodes']), m['treatment'], m['outcome'], 'binary', m['period'])
    for key, expected in (('node_order', list(s.node_order)), ('treatment', s.treatment_definition),
                          ('outcome', s.outcome_definition), ('context', s.context_reference)):
        if target.get(key) != expected:
            raise ValueError('POLICY_MATERIAL_TARGET_MISMATCH: ' + key)
    evaluation = Evaluation(tuple(target['population']), tuple(target['unit_weights']))
    if 'weights' in m and tuple(m['weights']) != evaluation.unit_weights:
        raise ValueError('POLICY_MATERIAL_WEIGHT_MISMATCH')
    if legacy_all_enabled:
        if m['operator'] != 'BOUNDED_SIGNATURE_MEAN':
            raise ValueError('EXPLICIT_LEGACY_ALL_ENABLED_CONTRACT_REQUIRED')
        first, second = (1,) * len(s.node_order), None
    else:
        first = tuple(m['first'])
        second = tuple(m['second']) if m['second'] is not None else None
        if second is None:
            if (target.get('kind') != 'FIXED_POLICY_MEAN'
                    or FixedPolicy(tuple(target.get('assignment', ()))) != FixedPolicy(first)):
                raise ValueError('POLICY_MATERIAL_ENDPOINT_MISMATCH')
        elif (target.get('kind') != 'FIXED_POLICY_CONTRAST'
              or FixedPolicy(tuple(target.get('first', ()))) != FixedPolicy(first)
              or FixedPolicy(tuple(target.get('second', ()))) != FixedPolicy(second)
              or target.get('operation') != 'FIRST_MINUS_SECOND'):
            raise ValueError('POLICY_MATERIAL_COMPARISON_MISMATCH')
    return PolicyQuestion(s, evaluation, FixedPolicy(first), FixedPolicy(second) if second is not None else None,
                          'MEAN' if second is None else 'FIRST_MINUS_SECOND')


def native_study(question, *, network_id, edges, assignment_design, protocol_provenance,
                 network_provenance, observation_regime, graph_timing_claim):
    """Compatibility entry for the shared study-coordinate constructor."""
    from .research_spec_coordinates import native_study as build
    return build(question.study, network_id=network_id, edges=edges, assignment_design=assignment_design,
        protocol_provenance=protocol_provenance, network_provenance=network_provenance,
        observation_regime=observation_regime, graph_timing_claim=graph_timing_claim)


def native_target(question, study, *, side, authority):
    from pfn_pipeline.network_inquiry_shadow import fixed_policy_target_from_context
    s = question.study
    kind = 'continuous' if s.outcome_domain == 'count' else s.outcome_domain
    if (study.node_order != s.node_order or study.treatment_variable != s.treatment_definition
            or study.outcome_variable != s.outcome_definition or study.context_reference != s.context_reference
            or study.outcome_kind != kind):
        raise ValueError('POLICY_NATIVE_STUDY_COORDINATES_CHANGED')
    return fixed_policy_target_from_context(study, question.endpoint(side).assignment,
        unit_weights=question.evaluation.unit_weights, authority=authority)
