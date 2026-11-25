"""Closed sufficient DAG method contracts, shared by reading and research APIs.

Graph-specific contracts and adapters own preparation, review, computation and
evidence. General ID and IV are separate entries, not automatic fallbacks here.
"""
from dataclasses import dataclass
from typing import Callable

OPERATION = 'INTERVENTIONAL_DISTRIBUTION'
BACKDOOR = 'DAG_CLASSICAL_BACKDOOR'
ADJUSTMENT = 'DAG_ADJUSTMENT'
FRONTDOOR = 'DAG_CLASSICAL_FRONTDOOR'
METHOD_IDS = (BACKDOOR, ADJUSTMENT, FRONTDOOR)


@dataclass(frozen=True)
class DagMethod:
    method_id: str
    operation: str
    problem_type: type
    review_type: type
    prepare: Callable
    adapter_type: type
    version: str

    @property
    def native_route_ids(self):
        return (self.method_id,)

    @property
    def producers(self):
        return (self.adapter_type.submit,)

    @property
    def replayers(self):
        return (self.adapter_type.replay,)

    def legacy_contract(self):
        return self.problem_type, self.review_type, self.prepare, self.adapter_type, self.version


def methods():
    from . import dag_backdoor, dag_adjustment, dag_frontdoor
    from .dag_backdoor_contract import BackdoorProblem, BackdoorReview
    from .dag_adjustment_contract import AdjustmentProblem, AdjustmentReview
    from .dag_frontdoor_contract import FrontdoorProblem, FrontdoorReview
    from .research_route_adapters import DagBackdoorRoute
    from .dag_adjustment_adapter import DagAdjustmentRoute
    from .dag_frontdoor_adapter import DagFrontdoorRoute
    return (
        DagMethod(BACKDOOR, OPERATION, BackdoorProblem, BackdoorReview,
                  dag_backdoor.prepare, DagBackdoorRoute, 'dag-backdoor-1'),
        DagMethod(ADJUSTMENT, OPERATION, AdjustmentProblem, AdjustmentReview,
                  dag_adjustment.prepare, DagAdjustmentRoute, 'dag-adjustment-1'),
        DagMethod(FRONTDOOR, OPERATION, FrontdoorProblem, FrontdoorReview,
                  dag_frontdoor.prepare, DagFrontdoorRoute, 'dag-frontdoor-1'),
    )


def resolve(method_id, operation=OPERATION):
    for method in methods():
        if method.method_id == method_id and method.operation == operation:
            return method
    raise ValueError('EXPLICIT_SUPPORTED_DAG_ROUTE_REQUIRED')
