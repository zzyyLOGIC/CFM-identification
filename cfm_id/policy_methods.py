"""Executable contracts for fixed-policy means and ordered differences.

The registry and reviewed adapters consume the same bindings. This is not a
reader, an assumption catalogue, or a new theorem selector. Native contracts
still decide mathematical applicability. Bindings are resolved afresh so the
registered producer/verifier and the callable used at execution cannot drift.
"""
from .method_compat import canonical_id, native_id
from dataclasses import dataclass
from functools import partial
from typing import Callable

MEAN = 'MEAN'
DIFFERENCE = 'FIRST_MINUS_SECOND'
POINT = 'NATIVE_POINT'
COMPOSITION = 'ENDPOINT_COMPOSITION'
BOX = 'JOINT_MEAN_BOX'
ORDER = 'JOINT_MEAN_ORDER'

FULL_POLICY = 'network.randomized.full_policy_mean'
SIGNATURE_POLICY = 'network.randomized.signature_policy_mean'
FULL_POLICY_DIFFERENCE = 'network.randomized.full_policy_contrast'
SIGNATURE_POLICY_DIFFERENCE = 'network.randomized.signature_policy_contrast'


@dataclass(frozen=True)
class Kernel:
    produce: Callable
    replay: Callable
    validate: Callable | None = None
    digest: Callable | None = None


@dataclass(frozen=True)
class PolicyMethod:
    method_id: str
    operation: str
    strategy: str
    native_route_ids: tuple[str, ...]
    kernel: Kernel
    endpoint_method: str | None = None
    composition: Kernel | None = None

    @property
    def producers(self):
        return (self.kernel.produce,) + ((self.composition.produce,) if self.composition else ())

    @property
    def replayers(self):
        return (self.kernel.replay,) + ((self.composition.replay,) if self.composition else ())


def methods(operation=None):
    # Fixed imports only. User material never supplies a module/function path.
    from pfn_pipeline import identification_policy_r1b as r1b, identification_policy_r2 as r2
    from pfn_pipeline import identification_business as business
    from . import fixed_comparison
    from .workflows import policy_difference
    from . import bounded_policy_contract as mean, bounded_policy_solver as mean_s, bounded_policy_verify as mean_v
    from . import bounded_contrast_contract as pair, bounded_contrast_solver as pair_s, bounded_contrast_verify as pair_v
    from . import bounded_count_contract as count, bounded_count_solver as count_s, bounded_count_verify as count_v
    from . import bounded_finite_contract as finite, bounded_finite_solver as finite_s, bounded_finite_verify as finite_v
    from . import mean_order_solver, mean_order_verify

    endpoint = Kernel(business.identify_network_business_query, business.replay_verified_business_outcome)
    rows = [
        PolicyMethod(FULL_POLICY, MEAN, POINT, (native_id(FULL_POLICY),),
            Kernel(r1b.identify_verified_fixed_policy, r1b.replay_verified_fixed_policy)),
        PolicyMethod(SIGNATURE_POLICY, MEAN, POINT, (native_id(SIGNATURE_POLICY),),
            Kernel(r2.identify_verified_signature_policy, r2.replay_verified_signature_policy)),
    ]
    pairs = [
        ('D2_E1', Kernel(mean_s.solve, mean_v.replay, mean.validate_model, mean.input_digest),
                    Kernel(pair_s.solve, pair_v.replay, pair.validate_pair, pair.input_digest)),
        ('D2_E4', Kernel(count_s.solve_policy, count_v.replay_policy, count.validate_model,
                         partial(count.input_digest, mode='policy')),
                    Kernel(count_s.solve_contrast, count_v.replay_contrast, count.validate_pair,
                         partial(count.input_digest, mode='contrast'))),
        ('FINITE', Kernel(finite_s.solve_policy, finite_v.replay_policy, finite.validate_model,
                          partial(finite.input_digest, mode='policy')),
                     Kernel(finite_s.solve_contrast, finite_v.replay_contrast, finite.validate_pair,
                          partial(finite.input_digest, mode='contrast'))),
    ]
    for suffix, single, _ in pairs:
        method = 'BOUNDED_POLICY_MEAN_' + suffix
        rows.append(PolicyMethod(method, MEAN, BOX, (method,), single))
    rows += [
        PolicyMethod(FULL_POLICY_DIFFERENCE, DIFFERENCE, COMPOSITION, (native_id(FULL_POLICY),), endpoint,
            FULL_POLICY, Kernel(fixed_comparison.compose, fixed_comparison.replay)),
        PolicyMethod(SIGNATURE_POLICY_DIFFERENCE, DIFFERENCE, COMPOSITION, (native_id(SIGNATURE_POLICY),), endpoint,
            SIGNATURE_POLICY, Kernel(policy_difference.compose, policy_difference.replay)),
    ]
    for suffix, _, joint in pairs:
        method = 'BOUNDED_POLICY_CONTRAST_' + suffix
        rows.append(PolicyMethod(method, DIFFERENCE, BOX, (method,), joint,
            'BOUNDED_POLICY_MEAN_' + suffix))
    rows.append(PolicyMethod('MEAN_ORDER_D2_E1', DIFFERENCE, ORDER, ('MEAN_ORDER_D2_E1',),
        Kernel(mean_order_solver.solve, mean_order_verify.replay), 'MEAN_ORDER_D2_E1'))
    if operation is not None and operation not in (MEAN, DIFFERENCE):
        raise ValueError('UNKNOWN_POLICY_OPERATION')
    if len({row.method_id for row in rows}) != len(rows):
        raise ValueError('DUPLICATE_POLICY_METHOD')
    return tuple(row for row in rows if operation is None or row.operation == operation)


def resolve(method_id, operation):
    method_id = canonical_id(method_id)
    for row in methods(operation):
        if row.method_id == method_id:
            return row
    raise ValueError('POLICY_METHOD_OPERATION_MISMATCH:' + str(method_id))


def difference_for(endpoint_method):
    """Existing method correspondence, not proof that both endpoints identify."""
    endpoint_method = canonical_id(endpoint_method)
    matches = [row for row in methods(DIFFERENCE) if row.endpoint_method == endpoint_method]
    if len(matches) != 1:
        raise ValueError('NO_REGISTERED_POLICY_DIFFERENCE:' + str(endpoint_method))
    return matches[0]


def require_plan(rows, operation):
    """Check wiring only. Source/science reviews and native checks remain required."""
    if not rows or len({row['method'] for row in rows}) != len(rows):
        raise ValueError('NONEMPTY_UNIQUE_POLICY_METHOD_PLAN_REQUIRED')
    resolved = tuple(resolve(row['method'], operation) for row in rows)
    if any(method.strategy in (BOX, ORDER) for method in resolved) and len(resolved) != 1:
        raise ValueError('EXACT_JOINT_POLICY_MODEL_REQUIRED')
    return resolved


def __getattr__(name):
    from .method_compat import legacy_attribute
    return legacy_attribute(name, globals())
