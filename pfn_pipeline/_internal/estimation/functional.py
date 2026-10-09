from __future__ import annotations

import math

import numpy as np
import pandas as pd

from pfn_pipeline._internal.identification.schemas import (
    BoundEstimationRequest,
    BoundEstimationResult,
    ConditionalMean,
    DifferenceFunctional,
    EstimationRequest,
    EstimationResult,
    ManskiBinaryATEBoundsProgram,
    OneArmATEBoundsProgram,
    PointEstimationRequest,
    PointEstimationResult,
)


class FunctionalExecutor:
    """Finite-sample executor for the typed programs emitted by Identification.

    Identification defines the target functional/bound program. This executor only
    estimates the required population objects from finite data and evaluates that
    program. It does not re-identify the causal query.
    """

    def execute_conditional_mean(self, node: ConditionalMean, data: pd.DataFrame) -> tuple[float, int, float]:
        missing = {node.treatment, node.outcome}.difference(data.columns)
        if missing:
            raise ValueError(f"Estimation data missing required columns: {sorted(missing)}")
        values = data.loc[data[node.treatment] == node.treatment_value, node.outcome].astype(float)
        if len(values) == 0:
            raise ValueError(
                f"No finite-sample observations for {node.treatment}={node.treatment_value}; cannot execute {node.to_text()}"
            )
        mean = float(values.mean())
        variance = float(values.var(ddof=1)) if len(values) > 1 else 0.0
        return mean, int(len(values)), variance

    def execute_difference(self, program: DifferenceFunctional, data: pd.DataFrame) -> PointEstimationResult:
        left_mean, n_left, var_left = self.execute_conditional_mean(program.left, data)
        right_mean, n_right, var_right = self.execute_conditional_mean(program.right, data)
        estimate = left_mean - right_mean
        se = math.sqrt(var_left / n_left + var_right / n_right)
        z = 1.96
        ci = (estimate - z * se, estimate + z * se)
        if not np.isfinite([left_mean, right_mean, estimate, se, *ci]).all():
            raise ValueError("Point program executor produced non-finite output")
        return PointEstimationResult(
            estimand="ATE",
            estimator="program_executor_v2",
            estimate=float(estimate),
            treated_mean=float(left_mean),
            control_mean=float(right_mean),
            standard_error=float(se),
            wald_interval_95=(float(ci[0]), float(ci[1])),
            finite_sample_guarantee=(
                "approximate 95% Wald interval from the simple two-group variance formula; "
                "no exact/randomization-based coverage guarantee is claimed"
            ),
            n_treated=n_left,
            n_control=n_right,
            requested_population_objects=program.required_population_objects(),
            executed_program=program.to_text(),
        )

    def execute_manski_bounds(self, program: ManskiBinaryATEBoundsProgram, data: pd.DataFrame) -> BoundEstimationResult:
        t, y = program.treatment, program.outcome
        missing = {t, y}.difference(data.columns)
        if missing:
            raise ValueError(f"Estimation data missing required columns: {sorted(missing)}")
        if len(data) == 0:
            raise ValueError("Cannot estimate bound endpoints from an empty dataset")
        if not set(pd.unique(data[t])).issubset({0, 1}) or not set(pd.unique(data[y])).issubset({0, 1}):
            raise ValueError("Manski binary bound executor requires finite-sample T,Y values in {0,1}")

        objects = {
            f"P({y}=0,{t}=0)": float(((data[y] == 0) & (data[t] == 0)).mean()),
            f"P({y}=1,{t}=0)": float(((data[y] == 1) & (data[t] == 0)).mean()),
            f"P({y}=0,{t}=1)": float(((data[y] == 0) & (data[t] == 1)).mean()),
            f"P({y}=1,{t}=1)": float(((data[y] == 1) & (data[t] == 1)).mean()),
        }
        lower = -objects[f"P({y}=0,{t}=1)"] - objects[f"P({y}=1,{t}=0)"]
        upper = objects[f"P({y}=1,{t}=1)"] + objects[f"P({y}=0,{t}=0)"]
        return self._bound_result(program, data, lower, upper, objects)

    def execute_one_arm_bounds(self, program: OneArmATEBoundsProgram, data: pd.DataFrame) -> BoundEstimationResult:
        t, y = program.treatment, program.outcome
        missing = {t, y}.difference(data.columns)
        if missing:
            raise ValueError(f"Estimation data missing required columns: {sorted(missing)}")
        if len(data) == 0:
            raise ValueError("Cannot estimate bound endpoints from an empty dataset")
        observed = data.loc[data[t] == program.observed_treatment_value, y].astype(float)
        if len(observed) == 0:
            raise ValueError("Observed treatment arm declared by the bound program has no finite-sample observations")
        other = data.loc[data[t] != program.observed_treatment_value]
        if len(other) != 0:
            raise ValueError("One-arm bound program received finite-sample observations from both treatment arms")

        mu = float(observed.mean())
        if program.observed_treatment_value == 1:
            lower = None if program.outcome_upper is None else mu - program.outcome_upper
            upper = None if program.outcome_lower is None else mu - program.outcome_lower
        else:
            lower = None if program.outcome_lower is None else program.outcome_lower - mu
            upper = None if program.outcome_upper is None else program.outcome_upper - mu
        objects = {program.observed_mean_object(): mu}
        return self._bound_result(program, data, lower, upper, objects)

    @staticmethod
    def _bound_result(
        program,
        data: pd.DataFrame,
        lower: float | None,
        upper: float | None,
        objects: dict[str, float],
    ) -> BoundEstimationResult:
        if lower is not None and not np.isfinite(lower):
            raise ValueError("Finite lower endpoint estimate must be numeric and finite")
        if upper is not None and not np.isfinite(upper):
            raise ValueError("Finite upper endpoint estimate must be numeric and finite")
        if lower is not None and upper is not None and lower > upper:
            raise ValueError("Bound executor produced an invalid interval")
        width = None if lower is None or upper is None else upper - lower
        return BoundEstimationResult(
            estimand="ATE",
            estimator="program_executor_v3",
            estimated_lower_endpoint=None if lower is None else float(lower),
            estimated_upper_endpoint=None if upper is None else float(upper),
            estimated_width=None if width is None else float(width),
            n=int(len(data)),
            estimated_population_objects=objects,
            requested_population_objects=program.required_population_objects(),
            executed_program=program.to_text(),
            finite_sample_guarantee="none",
            interpretation=(
                "Plug-in estimates of the finite endpoint(s) of the population identified set; "
                "a missing endpoint denotes an infinite side, and no finite-sample coverage guarantee is claimed."
            ),
        )


class ProgramExecutorEstimator:
    name = "program_executor_v3"

    def __init__(self, executor: FunctionalExecutor | None = None):
        self.executor = executor or FunctionalExecutor()

    def estimate(self, request: EstimationRequest, data: pd.DataFrame) -> EstimationResult:
        if isinstance(request, PointEstimationRequest):
            result = self.executor.execute_difference(request.program, data)
        elif isinstance(request, BoundEstimationRequest):
            if isinstance(request.program, ManskiBinaryATEBoundsProgram):
                result = self.executor.execute_manski_bounds(request.program, data)
            elif isinstance(request.program, OneArmATEBoundsProgram):
                result = self.executor.execute_one_arm_bounds(request.program, data)
            else:
                raise TypeError(f"Unsupported bound program type: {type(request.program).__name__}")
        else:
            raise TypeError(f"Unsupported EstimationRequest type: {type(request).__name__}")

        if result.requested_population_objects != request.required_population_objects:
            raise ValueError("Executor/request population-object contract mismatch")
        return result


# Backward-compatible name for v0.1 imports. It now executes the typed program.
DifferenceInMeansEstimator = ProgramExecutorEstimator
