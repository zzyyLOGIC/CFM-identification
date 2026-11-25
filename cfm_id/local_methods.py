"""Executable bindings for original-design local means and contrasts.

An effect name describes changed coordinates, not a different proof family.
No registration supplies scientific approval or positive support. The existing
single-arm and composition contracts keep their respective input types.
"""
from .method_compat import canonical_id, native_id
from dataclasses import dataclass
from typing import Callable

ARM_MEAN = 'ARM_MEAN'
DIFFERENCE = 'FIRST_MINUS_SECOND'
ARM = 'network.randomized.local_mean'
CONTRAST = 'network.randomized.local_contrast'


@dataclass(frozen=True)
class LocalMethod:
    method_id: str
    operation: str
    native_route_ids: tuple[str, ...]
    identify: Callable
    replay: Callable
    batch: Callable | None = None
    linear: Callable | None = None
    replay_linear: Callable | None = None

    @property
    def producers(self):
        return ((self.batch,) if self.batch else ()) + (self.identify,) + ((self.linear,) if self.linear else ())

    @property
    def replayers(self):
        return (self.replay,) + ((self.replay_linear,) if self.replay_linear else ())


def methods(operation=None):
    # Fixed imports, resolved at use time. User input never selects a callable.
    from pfn_pipeline import identification_business as core
    from pfn_pipeline import identification_batch as batch
    from pfn_pipeline import identification_composition as composition
    if operation is not None and operation not in (ARM_MEAN, DIFFERENCE):
        raise ValueError('UNKNOWN_LOCAL_OPERATION')
    rows = (
        LocalMethod(ARM, ARM_MEAN, (native_id(ARM),), core.identify_network_business_query,
                    core.replay_verified_business_outcome),
        LocalMethod(CONTRAST, DIFFERENCE, (native_id(CONTRAST),), core.identify_network_business_query,
                    core.replay_verified_business_outcome, batch.identify_randomized_network_batch,
                    composition.identify_verified_linear_target, composition.replay_verified_composition),
    )
    return tuple(row for row in rows if operation is None or row.operation == operation)


def resolve(method_id, operation):
    method_id = canonical_id(method_id)
    for row in methods(operation):
        if row.method_id == method_id:
            return row
    raise ValueError('LOCAL_METHOD_OPERATION_MISMATCH:' + str(method_id))
