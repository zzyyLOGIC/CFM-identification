"""Design-conditional local means, distinct from full fixed interventions.

Own treatment and the peer summary identify an event of the original design.
Other assignments are averaged conditionally under that design, not fixed.
The design and exposure definition remain separate study inputs; none of these
attributes imply exchangeability, sufficiency, positive support or permission.
"""
from dataclasses import dataclass
from fractions import Fraction

from .research_spec_coordinates import StudyCoordinates, Evaluation, validate_evaluation

ORIGINAL_DESIGN_CONDITIONAL = 'ORIGINAL_DESIGN_CONDITIONAL'


def effect_kind(first, second):
    """Coordinate change only; independent of averaging law or causal license."""
    own, peer = first.own != second.own, first.exposure != second.exposure
    return {(True, False): 'DIRECT_EFFECT', (False, True): 'SPILLOVER_EFFECT',
            (True, True): 'LOCAL_TOTAL_EFFECT', (False, False): 'NO_CHANGE'}[own, peer]


@dataclass(frozen=True)
class LocalState:
    own: int
    exposure: int | str

    def __post_init__(self):
        if type(self.own) is not int or self.own not in (0, 1):
            raise ValueError('LOCAL_BINARY_OWN_STATE_REQUIRED')
        if not ((type(self.exposure) is int and self.exposure >= 0)
                or (type(self.exposure) is str and self.exposure.strip())):
            raise ValueError('LOCAL_EXPLICIT_EXPOSURE_STATE_REQUIRED')

    def coordinates(self):
        return self.own, self.exposure


@dataclass(frozen=True)
class LocalQuestion:
    study: StudyCoordinates
    evaluation: Evaluation
    first: LocalState
    second: LocalState
    operation: str
    remaining_assignment: str

    def __post_init__(self):
        validate_evaluation(self.study, self.evaluation)
        if not isinstance(self.first, LocalState) or not isinstance(self.second, LocalState):
            raise ValueError('TYPED_LOCAL_STATES_REQUIRED')
        if self.operation != 'FIRST_MINUS_SECOND':
            raise ValueError('EXPLICIT_LOCAL_DIRECTION_REQUIRED')
        if self.remaining_assignment != ORIGINAL_DESIGN_CONDITIONAL:
            raise ValueError('ORIGINAL_CONDITIONAL_DESIGN_REQUIRED')

    @property
    def effect_kind(self):
        """Describe which coordinates change; do not choose an identification method."""
        return effect_kind(self.first, self.second)

    def selected_weights(self):
        by_node = dict(zip(self.study.node_order, self.evaluation.unit_weights))
        return tuple((n, by_node[n]) for n in self.evaluation.population)

    def signed_terms(self):
        """Target coefficients only; no support calculation or identification proof."""
        return tuple((n, arm.own, arm.exposure, sign * Fraction(w))
                     for n, w in self.selected_weights() if Fraction(w)
                     for arm, sign in ((self.first, 1), (self.second, -1)))
