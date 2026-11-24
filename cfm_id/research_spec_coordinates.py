"""Shared study and evaluation coordinates; no intervention or causal license.

These values are shared by fixed-policy and design-conditional local targets.
An absent outcome domain is retained as absent in contracts that do not record
it. Consumers requiring a domain must reject it, rather than assume binary Y.
"""
from dataclasses import dataclass
from fractions import Fraction


def _text(value, field):
    if type(value) is not str or not value.strip():
        raise ValueError('POLICY_ATTRIBUTE_REQUIRED: ' + field)


def _names(value, field):
    if type(value) is not tuple or not value or any(type(x) is not str or not x.strip() for x in value):
        raise ValueError('POLICY_NAMES_REQUIRED: ' + field)
    if len(set(value)) != len(value):
        raise ValueError('POLICY_DUPLICATE_NAMES: ' + field)


@dataclass(frozen=True)
class StudyCoordinates:
    node_order: tuple[str, ...]
    treatment_definition: str
    outcome_definition: str
    outcome_domain: str | None
    context_reference: str

    def __post_init__(self):
        _names(self.node_order, 'node_order')
        for field in ('treatment_definition', 'outcome_definition', 'context_reference'):
            _text(getattr(self, field), field)
        if self.outcome_domain not in ('binary', 'count', 'continuous', None):
            raise ValueError('POLICY_OUTCOME_DOMAIN_UNRESOLVED')


@dataclass(frozen=True)
class Evaluation:
    population: tuple[str, ...]
    unit_weights: tuple[str, ...]

    def __post_init__(self):
        _names(self.population, 'evaluation_population')
        if type(self.unit_weights) is not tuple or not self.unit_weights:
            raise ValueError('POLICY_WEIGHTS_REQUIRED')
        if any(type(w) is not str for w in self.unit_weights):
            raise ValueError('POLICY_EXACT_WEIGHT_STRINGS_REQUIRED')
        values = tuple(Fraction(w) for w in self.unit_weights)
        if any(w < 0 for w in values) or sum(values) != 1:
            raise ValueError('POLICY_MEAN_WEIGHTS_MUST_SUM_TO_ONE')


def validate_evaluation(study, evaluation):
    if not isinstance(study, StudyCoordinates) or not isinstance(evaluation, Evaluation):
        raise ValueError('TYPED_STUDY_AND_EVALUATION_REQUIRED')
    nodes = study.node_order
    if not set(evaluation.population) <= set(nodes):
        raise ValueError('POLICY_EVALUATION_OUTSIDE_STUDY')
    if len(evaluation.unit_weights) != len(nodes):
        raise ValueError('POLICY_WEIGHT_DIMENSION_MISMATCH')
    if any(n not in evaluation.population and Fraction(w) != 0
           for n, w in zip(nodes, evaluation.unit_weights)):
        raise ValueError('POLICY_WEIGHT_OUTSIDE_EVALUATION')


def native_study(coordinates, *, network_id, edges, assignment_design, protocol_provenance,
                 network_provenance, observation_regime, graph_timing_claim):
    """Construct existing study coordinates, without a target or scientific admission."""
    from pfn_pipeline.network_inquiry_shadow import declare_network_study
    s = coordinates
    if not isinstance(s, StudyCoordinates) or s.outcome_domain is None:
        raise ValueError('NATIVE_STUDY_OUTCOME_DOMAIN_REQUIRED')
    return declare_network_study(network_id=network_id, node_order=s.node_order,
        undirected_edges=tuple(tuple(e) for e in edges), treatment_variable=s.treatment_definition,
        outcome_variable=s.outcome_definition,
        # Retain the existing POINT mean embedding; no count sharpness inference.
        outcome_kind='continuous' if s.outcome_domain == 'count' else s.outcome_domain,
        context_reference=s.context_reference, observation_regime=observation_regime,
        assignment_design=assignment_design, protocol_provenance=protocol_provenance,
        network_provenance=network_provenance, graph_timing_claim=graph_timing_claim)
