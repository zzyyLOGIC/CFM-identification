"""Closed observational method bindings; averaging and causal licenses differ.

Policy support/signature choice remains in the reviewed policy adapter. Effect
methods must match the explicit averaging target and its declared population
operator. No observational law is promoted to randomization by this registry.
"""
from .method_compat import canonical_id, native_id
from dataclasses import dataclass
from typing import Callable
from .research_spec_observational import (
    ObservedAllocationAverage, SharedStratumAverage, NodewiseFeatureAverage)

MEAN = 'MEAN'
DIFFERENCE = 'FIRST_MINUS_SECOND'
FULL_POLICY = 'network.observational.full_policy_mean'
SIGNATURE_POLICY = 'network.observational.signature_policy_mean'
OBSERVED_EFFECT = 'network.observational.observed_law_contrast'
STRATIFIED_EFFECT = 'network.observational.shared_stratum_contrast'
NODEWISE_EFFECT = 'network.observational.local_covariate_contrast'
_EFFECTS = (
    (OBSERVED_EFFECT, ObservedAllocationAverage.kind),
    (STRATIFIED_EFFECT, SharedStratumAverage.kind),
    (NODEWISE_EFFECT, NodewiseFeatureAverage.kind),
)


@dataclass(frozen=True)
class ObservationalMethod:
    method_id: str
    operation: str
    averaging: str | None
    identify: Callable
    replay: Callable

    @property
    def native_route_ids(self):
        return (native_id(self.method_id),)

    @property
    def producers(self):
        return (self.identify,)

    @property
    def replayers(self):
        return (self.replay,)

    @property
    def population_operators(self):
        if self.operation == MEAN:
            return ('OBSERVATIONAL_ASSIGNMENT_NODE_CONDITIONAL_MEANS',)
        # Reuse the established input ownership; do not maintain a second map.
        from .research_spec_observational_adapters import population_operators
        return population_operators(self.averaging)


def effect_routes():
    """A fresh compatibility map; modifying it cannot change method contracts."""
    return {averaging: method for method, averaging in _EFFECTS}


def methods(operation=None):
    from pfn_pipeline import identification_business as core
    if operation is not None and operation not in (MEAN, DIFFERENCE):
        raise ValueError('UNKNOWN_OBSERVATIONAL_OPERATION')
    rows = tuple(ObservationalMethod(method, op, averaging,
        core.identify_network_business_query, core.replay_verified_business_outcome)
        for method, op, averaging in (
            (FULL_POLICY, MEAN, None), (SIGNATURE_POLICY, MEAN, None),
            *((method, DIFFERENCE, averaging) for method, averaging in _EFFECTS)))
    return tuple(row for row in rows if operation is None or row.operation == operation)


def resolve(method_id, operation):
    method_id = canonical_id(method_id)
    for row in methods(operation):
        if row.method_id == method_id:
            return row
    raise ValueError('OBSERVATIONAL_METHOD_OPERATION_MISMATCH:' + str(method_id))


def require_effect(method_id, question, operator):
    """Check wiring against the explicit target, not the truth of assumptions."""
    method = resolve(method_id, question.operation)
    if method.operation != DIFFERENCE or method.averaging != question.averaging.kind:
        raise ValueError('OBSERVATIONAL_METHOD_AVERAGING_MISMATCH')
    if operator not in method.population_operators:
        raise ValueError('TARGET_AVERAGING_AND_POPULATION_OPERATOR_MISMATCH')
    return method
