"""Internal native calls after existing review; no public admission or fallback.

Adapters still check the returned route, target and scientific inputs before
replay. Native mathematical checks remain in the existing producers/verifiers.
"""
from . import local_methods, native_outcome_execution
from .native_evidence import payload
from .business_dispatch import sha


def _fingerprint(value):
    return sha(payload(value))


def identify(method_id, operation, inquiry):
    method = local_methods.resolve(method_id, operation)
    return native_outcome_execution.identify(method, inquiry, fingerprint=_fingerprint)


def replay_outcome(method_id, operation, result, *, inquiry, input_digest):
    method = local_methods.resolve(method_id, operation)
    native_outcome_execution.replay_outcome(method, result, inquiry=inquiry,
        input_digest=input_digest, fingerprint=_fingerprint)


def arm_batch(method_id, task):
    method = local_methods.resolve(method_id, local_methods.DIFFERENCE)
    if method.batch is None:
        raise ValueError('LOCAL_BATCH_CALL_CONTRACT_REQUIRED')
    original = sha(payload(task))
    batch = method.batch(task)
    if sha(payload(task)) != original or sha(payload(batch.template)) != original:
        raise ValueError('EFFECT_BATCH_INPUT_MISMATCH')
    return batch
