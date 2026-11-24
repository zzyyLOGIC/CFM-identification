"""Existing local-effect formats -> owned attributes -> existing native inputs.

No source text is interpreted here. Known contracts define the ordered local
comparison; source review still establishes whether that is the user's intent.
Legacy scientific declarations and original-design/exposure parameters remain
with their existing owners and reviews.
"""
from copy import deepcopy
from fractions import Fraction

from .research_spec_coordinates import StudyCoordinates, Evaluation
from .research_spec_local import LocalState, LocalQuestion, ORIGINAL_DESIGN_CONDITIONAL


def from_reading(c):
    t, s = c.target, c.study
    if t.aggregation not in ('SINGLE', 'EQUAL_MEAN') or not t.population:
        raise ValueError('EXPLICIT_LOCAL_EVALUATION_REQUIRED')
    if t.aggregation == 'SINGLE' and len(t.population) != 1:
        raise ValueError('SINGLE_LOCAL_EVALUATION_REQUIRED')
    study = StudyCoordinates(tuple(s.nodes), s.treatment, s.outcome, s.outcome_kind.lower(), s.context)
    evaluation = Evaluation(tuple(t.population), tuple(
        str(Fraction(1, len(t.population))) if n in t.population else '0' for n in study.node_order))
    q = LocalQuestion(study, evaluation, LocalState(t.first.own, t.first.exposure),
                      LocalState(t.second.own, t.second.exposure), t.operation, t.remaining_assignment)
    if q.effect_kind != t.kind or q.effect_kind == 'NO_CHANGE':
        raise ValueError('LOCAL_EFFECT_LABEL_COORDINATES_DISAGREE')
    return q


def reading_coordinates(c, q):
    from cfm_id_llm import network_design_reading as design_fields
    result = dict(kind=q.effect_kind, node_order=list(q.study.node_order),
        evaluation_population=list(q.evaluation.population), unit_weights=list(q.evaluation.unit_weights),
        first=list(q.first.coordinates()), second=list(q.second.coordinates()), operation=q.operation,
        remaining_assignment=q.remaining_assignment,
        assignment=dict(kind=c.assignment.kind, **{k:getattr(c.assignment,k) for k in design_fields.ASSIGNMENT_FIELDS
            if getattr(c.assignment,k) is not None}), exposure=c.exposure.kind,
        treatment=q.study.treatment_definition, outcome=q.study.outcome_definition, context=q.study.context_reference,
        native_symbol_mapping=dict(treatment='treatment', outcome='outcome', context='W'))
    for old, new in (('core_collaborators','core_collaborators'), ('weights','exposure_weights'),
                     ('mode','exposure_mode'), ('groups','exposure_groups')):
        value = getattr(c.exposure, old)
        if value is not None:
            result[new] = deepcopy(value)
    if q.study.outcome_domain == 'count':
        result['outcome_domain_embedding'] = dict(business_kind='COUNT', native_kind='continuous',
            scope='LOCAL_POINT_MEAN_ONLY', distributional_continuity_assumed=False,
            sharp_bound_or_nonidentification_transfer=False)
    return result


def require_reading_coordinates(c, q, recorded):
    from cfm_id_bridge.scientific_binding import sha
    if sha(reading_coordinates(c, q)) != sha(recorded):
        raise ValueError('EFFECT_TARGET_PLAN_MISMATCH')


def native_request(q, *, authority, cohort_evidence):
    from pfn_pipeline.identification_composition import ArmLinearTerm, EffectQueryV18
    if authority not in ('SYNTHETIC_TEST', 'EXTERNAL_RESEARCH_REVIEW'):
        raise ValueError('EXPLICIT_RESEARCH_AUTHORITY_REQUIRED')
    if q.effect_kind not in ('DIRECT_EFFECT', 'SPILLOVER_EFFECT', 'LOCAL_TOTAL_EFFECT'):
        raise ValueError('NAMED_LOCAL_CONTRAST_REQUIRED')
    if q.effect_kind in ('DIRECT_EFFECT', 'LOCAL_TOTAL_EFFECT') and q.first.own == 0:
        # Preserve the existing reverse-direction route and its certificate type.
        return tuple(ArmLinearTerm(*term) for term in q.signed_terms())
    return EffectQueryV18({'DIRECT_EFFECT':'DIRECT','SPILLOVER_EFFECT':'SPILLOVER',
                           'LOCAL_TOTAL_EFFECT':'TOTAL'}[q.effect_kind],
        q.selected_weights(), q.second.exposure, q.first.exposure, spillover_own_treatment=q.first.own,
        cohort_authority='TRUSTED_FIXTURE' if authority == 'SYNTHETIC_TEST' else 'HUMAN_CONFIRMED_PRETREATMENT',
        cohort_evidence=cohort_evidence)


def from_compact(reading):
    t, n = reading.target, reading.network
    if t.kind != 'local_difference' or len(n.arms) != 2 or any(len(a) != 2 for a in n.arms):
        raise ValueError('COMPACT_ORDERED_LOCAL_CONTRAST_REQUIRED')
    study = StudyCoordinates(tuple(n.nodes), t.treatment, t.outcome, n.outcome_kind, t.context)
    # local_difference is defined by the existing compact contract as an original
    # design-conditional contrast. Its reading/remainder review is still mandatory.
    return LocalQuestion(study, Evaluation(study.node_order, tuple(n.weights)),
        LocalState(*n.arms[0]), LocalState(*n.arms[1]), 'FIRST_MINUS_SECOND', ORIGINAL_DESIGN_CONDITIONAL)


def from_event_facts(facts):
    c, n = facts['contrast'], facts['network']
    if c.get('kind') != 'original_local' or len(c['ends']) != 2 or any(len(a) != 2 for a in c['ends']):
        raise ValueError('SOURCE_ORDERED_LOCAL_CONTRAST_REQUIRED')
    # This source contract records outcome and time but no outcome domain.
    # Leave it unknown; never declare a binary or continuous outcome on its behalf.
    study = StudyCoordinates(tuple(n['nodes']), c['variable'], c['outcome'], None, c['time'])
    if len(c['population']) != len(c['weights']):
        raise ValueError('SOURCE_LOCAL_WEIGHTS_REQUIRED')
    weights = dict(zip(c['population'], c['weights']))
    evaluation = Evaluation(tuple(c['population']), tuple(str(weights.get(node, '0')) for node in study.node_order))
    return LocalQuestion(study, evaluation, LocalState(*c['ends'][0]), LocalState(*c['ends'][1]),
                         'FIRST_MINUS_SECOND', ORIGINAL_DESIGN_CONDITIONAL)


def event_inputs(facts, q):
    """Rebuild consumed coordinates; other facets keep their original records."""
    result = deepcopy(facts)
    s = q.study
    result['network']['nodes'] = list(s.node_order)
    result['contrast'].update(population=list(q.evaluation.population),
        weights=[w for _, w in q.selected_weights()], ends=[list(q.first.coordinates()), list(q.second.coordinates())],
        variable=s.treatment_definition, outcome=s.outcome_definition, time=s.context_reference)
    return result
