"""Observed-law targets and covariate-averaged exposure targets stay distinct.

These attributes specify the question, not exchangeability or a scientific
approval. Population laws and their source coverage stay with the A4 records.
No observed factorization is converted into a randomization design.
"""
from dataclasses import dataclass
from typing import ClassVar

from .research_spec_coordinates import StudyCoordinates, Evaluation, validate_evaluation
from .research_spec_local import LocalState, effect_kind
from .research_spec_policy import PolicyQuestion


def _defined(value):
    if type(value) is not str or not value.strip():
        raise ValueError('EXPLICIT_OBSERVATIONAL_DEFINITION_REQUIRED')


@dataclass(frozen=True)
class FixedBackground:
    definition: str

    def __post_init__(self):
        _defined(self.definition)


@dataclass(frozen=True)
class ObservedAllocationAverage:
    """Condition remaining assignments on each local event, at the same W."""
    kind: ClassVar[str] = 'OBSERVED_ALLOCATION_CONDITIONAL'


@dataclass(frozen=True)
class SharedStratumAverage:
    """Average over a shared pretreatment B distribution, keeping W fixed."""
    variable: str
    kind: ClassVar[str] = 'SHARED_PRETREATMENT_STRATUM'

    def __post_init__(self):
        _defined(self.variable)


@dataclass(frozen=True)
class NodewiseFeatureAverage:
    """Average over C_i=(own binary X, number of ALL neighbors with X=1).

    The feature reference set is fixed by this existing native contract. It
    does not shrink to the reference set used by a core-partner exposure.
    """
    variable: str
    kind: ClassVar[str] = 'OWN_AND_NEIGHBOR_BINARY_FEATURE'
    feature_domain: ClassVar[str] = 'BINARY'
    neighbor_reference: ClassVar[str] = 'ALL_STUDY_NEIGHBORS'

    def __post_init__(self):
        _defined(self.variable)


@dataclass(frozen=True)
class ObservationalEffectQuestion:
    study: StudyCoordinates
    evaluation: Evaluation
    fixed_background: FixedBackground
    first: LocalState
    second: LocalState
    operation: str
    averaging: ObservedAllocationAverage | SharedStratumAverage | NodewiseFeatureAverage

    def __post_init__(self):
        validate_evaluation(self.study, self.evaluation)
        if not isinstance(self.fixed_background, FixedBackground):
            raise ValueError('EXPLICIT_FIXED_BACKGROUND_REQUIRED')
        if not isinstance(self.first, LocalState) or not isinstance(self.second, LocalState):
            raise ValueError('TYPED_LOCAL_STATES_REQUIRED')
        if self.operation != 'FIRST_MINUS_SECOND':
            raise ValueError('EXPLICIT_LOCAL_DIRECTION_REQUIRED')
        if type(self.averaging) not in (ObservedAllocationAverage, SharedStratumAverage, NodewiseFeatureAverage):
            raise ValueError('EXPLICIT_OBSERVATIONAL_AVERAGING_REQUIRED')
        if self.effect_kind == 'NO_CHANGE':
            raise ValueError('NAMED_LOCAL_CONTRAST_REQUIRED')

    @property
    def effect_kind(self):
        return effect_kind(self.first, self.second)

    def selected_weights(self):
        by_node = dict(zip(self.study.node_order, self.evaluation.unit_weights))
        return tuple((n, by_node[n]) for n in self.evaluation.population)


@dataclass(frozen=True)
class ObservationalPolicyQuestion:
    target: PolicyQuestion
    fixed_background: FixedBackground

    def __post_init__(self):
        if not isinstance(self.target, PolicyQuestion) or self.target.operation != 'MEAN':
            raise ValueError('OBSERVATIONAL_POLICY_MEAN_REQUIRED')
        if not isinstance(self.fixed_background, FixedBackground):
            raise ValueError('EXPLICIT_FIXED_BACKGROUND_REQUIRED')
        # Preserve this entry's existing scope; count embedding belongs elsewhere.
        if self.target.study.outcome_domain not in ('binary', 'continuous'):
            raise ValueError('OBSERVATIONAL_POLICY_OUTCOME_NOT_CONNECTED')
