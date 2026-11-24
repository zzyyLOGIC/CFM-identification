"""Executable internal attributes for fixed binary policies on one study.

The study coordinates and evaluation have one owner, shared by both endpoints.
This is not an LLM schema, scientific approval, or a new mathematical contract.
Legacy adapters supply values; native adapters construct the existing inputs.
No original JSON or hidden legacy target is stored in these objects.
"""
from dataclasses import dataclass
from .research_spec_coordinates import StudyCoordinates, Evaluation, validate_evaluation


@dataclass(frozen=True)
class FixedPolicy:
    assignment: tuple[int, ...]

    def __post_init__(self):
        if (type(self.assignment) is not tuple or not self.assignment
                or any(type(z) is not int or z not in (0, 1) for z in self.assignment)):
            raise ValueError('POLICY_COMPLETE_BINARY_VECTOR_REQUIRED')


@dataclass(frozen=True)
class PolicyQuestion:
    study: StudyCoordinates
    evaluation: Evaluation
    first: FixedPolicy
    second: FixedPolicy | None
    operation: str

    def __post_init__(self):
        if (not isinstance(self.study, StudyCoordinates) or not isinstance(self.evaluation, Evaluation)
                or not isinstance(self.first, FixedPolicy)
                or (self.second is not None and not isinstance(self.second, FixedPolicy))):
            raise ValueError('TYPED_POLICY_ATTRIBUTES_REQUIRED')
        if (self.operation, self.second is not None) not in (('MEAN', False), ('FIRST_MINUS_SECOND', True)):
            raise ValueError('EXPLICIT_POLICY_OPERATION_REQUIRED')
        validate_evaluation(self.study, self.evaluation)
        if self.study.outcome_domain is None:
            raise ValueError('POLICY_OUTCOME_DOMAIN_UNRESOLVED')
        nodes = self.study.node_order
        if any(len(p.assignment) != len(nodes) for p in (self.first, self.second) if p is not None):
            raise ValueError('POLICY_ASSIGNMENT_DIMENSION_MISMATCH')

    def endpoint(self, side):
        if side == 'first':
            return self.first
        if side == 'second' and self.second is not None:
            return self.second
        raise ValueError('POLICY_ENDPOINT_NOT_PRESENT')

    def coordinates(self):
        """Existing review/result coordinates, constructed from owned attributes."""
        s = self.study
        out = dict(kind='FIXED_FULL_ASSIGNMENT_POLICY_MEAN' if self.second is None
                   else 'FIXED_FULL_ASSIGNMENT_POLICY_CONTRAST',
                   node_order=list(s.node_order), unit_weights=list(self.evaluation.unit_weights),
                   treatment=s.treatment_definition, outcome=s.outcome_definition, context=s.context_reference)
        if self.second is None:
            out['assignment'] = list(self.first.assignment)
        else:
            out.update(first=list(self.first.assignment), second=list(self.second.assignment), operation='first_minus_second')
        return out

    def require_coordinates(self, recorded):
        # Do not accept bools as integers or silently repair stale review targets.
        from cfm_id_bridge.scientific_binding import sha
        if sha(recorded) != sha(self.coordinates()):
            raise ValueError('POLICY_REVIEWED_COORDINATES_CHANGED')


def ordered_difference(first, second):
    """Combine explicit means with common coordinates; never subtract intervals."""
    if first.operation != 'MEAN' or second.operation != 'MEAN':
        raise ValueError('POLICY_MEAN_ENDPOINTS_REQUIRED')
    if (first.study != second.study or set(first.evaluation.population) != set(second.evaluation.population)
            or first.evaluation.unit_weights != second.evaluation.unit_weights):
        raise ValueError('POLICY_COMMON_EVALUATION_AND_CONTEXT_REQUIRED')
    return PolicyQuestion(first.study, first.evaluation, first.first, second.first, 'FIRST_MINUS_SECOND')
