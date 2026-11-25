"""One finite policy distribution, with separately verified complete-policy components.

The binding does not turn a stochastic policy into a fixed assignment, choose
probabilities, or allow a component to acquire mean-sufficiency assumptions as a fallback.
"""
from .method_compat import canonical_id, native_id
from dataclasses import dataclass
from typing import Callable

OPERATION = 'FINITE_POLICY_MEAN'
METHOD = 'network.randomized.finite_policy_mean'
COMPONENT_ROUTE = native_id('network.randomized.full_policy_mean')


@dataclass(frozen=True)
class FinitePolicyMethod:
    method_id: str
    operation: str
    component_route: str
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


def methods():
    from pfn_pipeline import identification_business as core
    return (FinitePolicyMethod(METHOD, OPERATION, COMPONENT_ROUTE,
        core.identify_network_business_query, core.replay_verified_business_outcome),)


def resolve(method_id, operation):
    method_id = canonical_id(method_id)
    for method in methods():
        if method.method_id == method_id and method.operation == operation:
            return method
    raise ValueError('FINITE_POLICY_METHOD_OPERATION_MISMATCH')
