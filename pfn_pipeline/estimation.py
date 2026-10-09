"""Execute the verified target and convert backend outputs to EstimateBundle."""
from fractions import Fraction

from .contracts import TaskSpec, IdentificationResult, EstimateBundle
from .identification import replay_handoff

__all__ = ["estimate_effects"]


def _unavailable(identification, reason):
    task = identification.task
    return EstimateBundle(identification=identification, method="not_run", estimand=task.estimand,
        semantics=task.target_semantics, kind="unavailable", note=reason)


def estimate_effects(task: TaskSpec, identification: IdentificationResult, model=None,
                     *, allow_untrained=False, allow_new_graph=False) -> EstimateBundle:
    """Estimate four response arms or execute the retained scalar ATE programs.

    The typed population handoff is independently replayed before any model call.
    Unsupported structured/count-table routes return an explicit unavailable
    result; partial identification is never converted to a PFN point estimate.
    """
    if identification.task is not task:
        raise ValueError("Pass the same TaskSpec instance used by identification")
    if identification.verification_status != "VERIFIED" or identification.status not in ("POINT", "PARTIAL"):
        return _unavailable(identification, identification.result.get("message") or
                            "No verified, estimable identification result")
    if identification.estimation_request is None:
        return _unavailable(identification, identification.diagnostics.get("handoff_gap") or
                            "No executable handoff for this identified target")
    request = replay_handoff(identification)
    from ._internal.identification.schemas import (
        NetworkMajorityResponseEstimationRequestV1, NetworkMajorityScoreEstimationRequestV1,
        PointEstimationRequest, BoundEstimationRequest)
    if isinstance(request, (NetworkMajorityResponseEstimationRequestV1, NetworkMajorityScoreEstimationRequestV1)):
        from .pfn import predict
        response = request.response_request if isinstance(request, NetworkMajorityScoreEstimationRequestV1) else request
        declared_p = Fraction(response.program.assignment_probability_rational)
        if declared_p != Fraction(str(task.assignment_design.get("assignment_probability"))):
            raise ValueError("Factual task design differs from the identified response design")
        if model is None:
            raise ValueError("A current random-DGP model is required; the bundled baseline is not that model")
        prediction = predict(model, task, allow_untrained=allow_untrained, allow_new_graph=allow_new_graph)
        return EstimateBundle.from_state_means(identification=identification,
            method="random_dgp_four_arm_gmm", estimand=response.estimand,
            semantics=response.program.semantics, mu_by_state=prediction["mu_by_state"],
            provenance=prediction["provenance"], diagnostics={
                "marginal_gmms": prediction["marginals"],
                "empirical_support": "not inferred for node-specific conditional means",
                "intervals": "no joint effect posterior or calibrated simultaneous band supplied",
            })
    if isinstance(request, (PointEstimationRequest, BoundEstimationRequest)):
        import pandas as pd
        from ._internal.estimation.functional import ProgramExecutorEstimator
        if task.treatment is None:
            raise ValueError("Scalar estimation requires factual treatment and outcome observations")
        result = ProgramExecutorEstimator().estimate(request, pd.DataFrame({
            request.treatment: task.treatment, request.outcome: task.outcome}))
        common = dict(identification=identification, method=result.estimator,
                      estimand=request.estimand, semantics=task.target_semantics, kind="scalar",
                      diagnostics={"original_result": result.model_dump(mode="python")})
        if isinstance(request, PointEstimationRequest):
            return EstimateBundle(**common, center=result.estimate,
                sampling_lower=result.wald_interval_95[0], sampling_upper=result.wald_interval_95[1],
                uncertainty_method="approximate_two_group_wald", coverage_level=.95, coverage_scope="marginal")
        return EstimateBundle(**common, lower=result.lower, upper=result.upper)
    return _unavailable(identification,
        f"{request.request_type} requires its specialized finite-sample/table contract; "
        "the current node-row TaskSpec does not supply it")
