"""Shared lifecycle for already reviewed native business-outcome calls.

Bindings and fingerprint functions come from trusted adapters, never user data.
Target, route, scientific inputs and output type still require their original
adapter checks. This does not choose methods, approve conditions or do algebra.
"""


class NativeInputMutation(ValueError):
    pass


class NativeReplayMismatch(ValueError):
    pass


def identify(method, inquiry, *, fingerprint):
    original = fingerprint(inquiry)
    result = method.identify(inquiry)
    if fingerprint(inquiry) != original:
        raise NativeInputMutation('NATIVE_INPUT_MUTATED')
    return result, original


def replay_outcome(method, result, *, inquiry, input_digest, fingerprint):
    saved = fingerprint(result)
    if (fingerprint(inquiry) != input_digest
            or method.replay(result) is not True
            or saved != fingerprint(result)
            or fingerprint(inquiry) != input_digest):
        raise NativeReplayMismatch('INDEPENDENT_REPLAY_OR_MUTATION_FAILURE')
