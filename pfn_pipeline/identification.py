"""Population identification entry point; finite samples do not establish assumptions.

Supply a TaskSpec with the complete, admitted identification_spec. The archived
I0/UI proposal flows are not called implicitly. Every estimation consumer can
replay_handoff to recheck the proof rather than trusting a saved VERIFIED string.
"""
from dataclasses import replace
import json

from .contracts import TaskSpec, IdentificationResult
from ._internal.identification.schemas import IdentificationSpec
from ._internal.identification.schemas import IdentificationResult as BackendResult
from ._internal.identification.identification import IdentificationEngine
from ._internal.identification.verifier import IdentificationVerifier
from ._internal.identification.handoff import compile_estimation_request
from ._internal.identification.majority_response import REQUIRED as MAJORITY_REQUIREMENTS

__all__ = ["identify", "replay_handoff"]


def identify(task: TaskSpec) -> IdentificationResult:
    """Verify an explicit population specification and compile its estimation request."""
    replace(task)  # Recheck mutable nested payloads at the module boundary.
    if task.identification_spec is None:
        return IdentificationResult(task=task, diagnostics={"workflow_status": "NEEDS_INPUT"}, result={
            "status": "UNSUPPORTED", "verification_status": "UNSUPPORTED",
            "backend": "missing_population_spec", "query": {"type": task.estimand},
            "reason_code": "IDENTIFICATION_SPEC_REQUIRED",
            "message": "Supply the complete identification specification and assumption evidence.",
        })
    spec = IdentificationSpec.model_validate(task.identification_spec)
    result = IdentificationEngine().solve_verified(spec, IdentificationVerifier())
    diagnostics = {"workflow_status": "COMPLETE" if result.verification_status == "VERIFIED" else "UNSUPPORTED"}
    if result.reason_code == "REQUIRED_ASSUMPTIONS_NOT_ADMITTED":
        records = {item.name: item for item in spec.assumptions}
        missing = sorted(set(MAJORITY_REQUIREMENTS) - spec.confirmed_assumptions())
        rejected = [name for name in missing if name in records and
                    records[name].status in {"NOT_ADMITTED", "CONTRADICTED"}]
        diagnostics.update(
            workflow_status="UNSUPPORTED" if rejected else "NEEDS_INPUT",
            missing_assumptions=missing,
            rejected_assumptions=rejected,
        )
    if result.network_policy_mixture_proof is not None:
        request = None
        diagnostics["handoff_gap"] = (
            "Finite-mixture handoff requires separate population truth/program binding; "
            "TaskSpec factual node rows cannot substitute for that input."
        )
    else:
        request = compile_estimation_request(result, spec=spec)
    return IdentificationResult(task=task, result=result.model_dump(mode="python"),
        estimation_request=None if request is None else request.model_dump(mode="python"),
        diagnostics=diagnostics)


def replay_handoff(identification: IdentificationResult):
    """Return a freshly verified typed request; reject changed graphs/queries/proofs."""
    replace(identification.task)
    replace(identification)
    if identification.task.identification_spec is None or identification.estimation_request is None:
        raise ValueError("A complete source specification and verified estimation handoff are required")
    spec = IdentificationSpec.model_validate(identification.task.identification_spec)
    saved = BackendResult.model_validate(identification.result)
    checked = IdentificationVerifier().verify(spec, saved)
    if checked.verification_status != "VERIFIED" or checked.status not in ("POINT", "PARTIAL"):
        raise ValueError("Identification proof replay failed: " + checked.verification_message)
    if checked.network_policy_mixture_proof is not None:
        raise NotImplementedError("Finite-mixture replay needs a separate population/program input")
    request = compile_estimation_request(checked, spec=spec)
    if request is None:
        raise ValueError("The verified result has no executable estimation handoff")
    current = json.dumps(request.model_dump(mode="json"), sort_keys=True)
    original = json.dumps(identification.estimation_request, sort_keys=True)
    if current != original:
        raise ValueError("Estimation handoff differs from the independently replayed request")
    return request
