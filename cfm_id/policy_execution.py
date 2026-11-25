"""Internal calls after existing source/science review; no public admission API.

Only wiring and proof binding live here. All mathematical calculations and
theorem checks remain in the registered native producer and verifier.
"""
from . import policy_methods
from .business_intake import _sha as certificate_sha


class PolicyEvidenceMismatch(ValueError):
    pass


def point_solution(method_id, compiled):
    method = policy_methods.resolve(method_id, policy_methods.MEAN)
    if method.strategy != policy_methods.POINT:
        raise ValueError('NATIVE_POLICY_POINT_METHOD_REQUIRED')
    if method.method_id not in (policy_methods.FULL_POLICY, policy_methods.SIGNATURE_POLICY):
        raise ValueError('POLICY_POINT_CALL_CONTRACT_REQUIRED')
    study, target, sources, assumptions, signature, sufficiency = compiled
    if method.method_id == policy_methods.FULL_POLICY:
        result = method.kernel.produce(study, target, sources, assumptions=assumptions)
    else:  # Only the explicitly supported SIGNATURE_POLICY call contract reaches this branch.
        result = method.kernel.produce(study, target, signature, sources,
            assumptions=assumptions, sufficiency=sufficiency)
    return result, method.kernel.replay


def bounded_solution(method_id, operation, inquiries, information, *, before_compute):
    """Run the whole objective; never subtract separately computed intervals."""
    method = policy_methods.resolve(method_id, operation)
    if method.strategy != policy_methods.BOX:
        raise ValueError('JOINT_MEAN_BOX_METHOD_REQUIRED')
    kernel = method.kernel
    kernel.validate(inquiries, information)
    original = kernel.digest(inquiries, information)
    before_compute()
    certificate = kernel.produce(inquiries, information)
    before = certificate_sha(certificate)
    inputs = {'inquiry' if operation == policy_methods.MEAN else 'inquiries': inquiries,
              'information': information}
    if (kernel.digest(inquiries, information) != original
            or kernel.replay(certificate, **inputs) is not True
            or kernel.digest(inquiries, information) != original
            or certificate_sha(certificate) != before):
        raise PolicyEvidenceMismatch('POLICY_INPUT_OR_REPLAY_MISMATCH')
    return certificate, original
