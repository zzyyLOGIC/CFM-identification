"""Shared contracts for the research identification -> estimation -> policy flow.

The four public dataclasses follow the demo's organization, with explicit network
and target semantics suitable for the existing research backends. Results retain
their upstream object: ``IdentificationResult.task``, ``EstimateBundle.identification``
and ``PolicyResult.estimates``. This keeps the task, graph and node order together
without copying independent target IDs into every stage.

These are structural contracts, NOT identification proof verifiers or estimator
capability checks. Existing backends must still replay the identification handoff,
check the checkpoint/target match and validate their numerical results. Importing
this module does not import a backend, load a checkpoint or execute a model.

Arrays are copied and made read-only to prevent accidental input mutation. Nested
payloads are defensively copied but must be treated as immutable by consumers.
Simulation oracle labels intentionally have no field in these runtime contracts.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
import json
from numbers import Integral, Real
from typing import Any, Literal

import numpy as np

__all__ = ["TaskSpec", "IdentificationResult", "EstimateBundle", "PolicyResult"]

IdentificationStatus = Literal[
    "POINT", "PARTIAL", "NO_USEFUL_ID", "INCOMPATIBLE", "UNSUPPORTED"
]
VerificationStatus = Literal["VERIFIED", "REJECTED", "UNSUPPORTED"]
BudgetMode = Literal["exact", "at_most"]
ExposureDefinition = Literal["strict_majority", "treated_neighbor_count_1hop"]
EstimateKind = Literal["response_surface", "scalar", "structured", "unavailable"]
State = tuple[int, int]


def _text(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


def _choice(value: Any, choices: tuple[str, ...], name: str) -> None:
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"{name} must be one of {choices}")


def _integer(value: Any, name: str, maximum: int | None = None) -> None:
    if (isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral)
            or value < 0 or (maximum is not None and value > maximum)):
        raise ValueError(f"{name} must be a nonnegative integer"
                         + (f" <= {maximum}" if maximum is not None else ""))


def _number(value: Any, name: str) -> None:
    if (isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
            or not np.isfinite(value)):
        raise ValueError(f"{name} must be a finite real number")


def _payload(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not all(isinstance(k, str) for k in value):
        raise ValueError(f"{name} must be a mapping with string keys")
    return deepcopy(dict(value))


def _array(value: Any, name: str, shape: tuple[int, ...] | None = None,
           *, binary: bool = False, allow_infinite: bool = False) -> np.ndarray:
    array = np.asarray(value)
    if array.dtype.kind not in ("biuf" if binary else "iuf"):
        raise ValueError(f"{name} must contain real numeric values")
    if shape is not None and array.shape != shape:
        raise ValueError(f"{name} must have shape {shape}, got {array.shape}")
    if np.any(np.isnan(array)) or (not allow_infinite and not np.all(np.isfinite(array))):
        raise ValueError(f"{name} contains NaN or unsupported infinity")
    # Check BEFORE converting: e.g. treatment=0.7 must not become treatment=0.
    if binary and not np.isin(array, [0, 1]).all():
        raise ValueError(f"{name} must contain only 0 and 1")
    result = np.array(array, dtype=np.int64 if binary else np.float64, copy=True)
    result.setflags(write=False)
    return result


def _set_payloads(instance: Any, *names: str) -> None:
    for name in names:
        value = getattr(instance, name)
        if value is not None:
            object.__setattr__(instance, name, _payload(value, name))


def _same_payload(left: Any, right: Any) -> bool:
    # Serialized legacy schemas can use either tuples (Python) or lists (JSON).
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def _check_network_binding(task: TaskSpec, network: Any) -> None:
    if network is None:
        return
    if not isinstance(network, Mapping) or tuple(network.get("node_ids", ())) != task.node_ids:
        raise ValueError("identification network node order differs from TaskSpec")
    if "undirected_edges" not in network:
        raise ValueError("identification network must preserve its undirected edges")
    expected = np.zeros_like(task.adjacency)
    index = {node: i for i, node in enumerate(task.node_ids)}
    for edge in network["undirected_edges"]:
        if (not isinstance(edge, (tuple, list)) or len(edge) != 2
                or any(not isinstance(node, str) or node not in index for node in edge)):
            raise ValueError("identification network has an invalid edge")
        i, j = (index[node] for node in edge)
        if i == j or expected[i, j]:
            raise ValueError("identification network has a loop or duplicate edge")
        expected[i, j] = expected[j, i] = 1
    if not np.array_equal(expected, task.adjacency):
        raise ValueError("identification network differs from TaskSpec.adjacency")


@dataclass(frozen=True, kw_only=True, eq=False)
class TaskSpec:
    """Declared task and optional factual sample on a fixed undirected network.

    ``estimand`` names the requested target (e.g. the majority-response policy
    score); ``target_semantics`` explains its meaning. The assignment design and
    assumptions are declarations, never inferred from the observed treatment rate.
    ``identification_spec`` can carry the existing schema's complete serialized
    input; it is not reconstructed from a few Boolean assumptions here.

    Provide x[N,P], treatment[N], outcome[N] together, or omit all three for a
    population-only identification task. Outcomes remain on their original scale.
    Isolates are allowed at this generic boundary; the current four-arm backend
    must reject them. Budget belongs to the declared task when it defines the
    identified policy class; otherwise it can be supplied to the policy stage.
    """

    name: str
    target_id: str
    estimand: str
    target_semantics: str
    node_ids: tuple[str, ...]
    adjacency: np.ndarray
    assignment_design: Mapping[str, Any]
    exposure_definition: ExposureDefinition
    outcome_kind: Literal["continuous", "binary"] = "continuous"
    x: np.ndarray | None = None
    treatment: np.ndarray | None = None
    outcome: np.ndarray | None = None
    assumptions: tuple[Mapping[str, Any], ...] = ()
    identification_spec: Mapping[str, Any] | None = None
    target_fingerprint: str | None = None
    budget: int | None = None
    budget_mode: BudgetMode = "at_most"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("name", "target_id", "estimand", "target_semantics"):
            _text(getattr(self, name), name)
        if isinstance(self.node_ids, (str, bytes)):
            raise ValueError("node_ids must be a sequence of explicit node IDs")
        ids = tuple(self.node_ids)
        if not ids or any(not isinstance(i, str) or not i.strip() for i in ids):
            raise ValueError("node_ids must contain nonempty strings")
        if len(set(ids)) != len(ids):
            raise ValueError("node_ids must be unique; implicit renaming is prohibited")
        object.__setattr__(self, "node_ids", ids)
        adjacency = _array(self.adjacency, "adjacency", (self.n_nodes, self.n_nodes), binary=True)
        if not np.array_equal(adjacency, adjacency.T) or np.any(np.diag(adjacency)):
            raise ValueError("adjacency must be symmetric and have no self-loops")
        object.__setattr__(self, "adjacency", adjacency)
        _choice(self.exposure_definition, ("strict_majority", "treated_neighbor_count_1hop"),
                "exposure_definition")
        _choice(self.outcome_kind, ("continuous", "binary"), "outcome_kind")
        _choice(self.budget_mode, ("exact", "at_most"), "budget_mode")
        if self.budget is not None:
            _integer(self.budget, "budget", self.n_nodes)
        if self.target_fingerprint is not None:
            _text(self.target_fingerprint, "target_fingerprint")
        _set_payloads(self, "assignment_design", "identification_spec", "metadata")
        _choice(self.assignment_design.get("design_type"),
                ("randomized_experiment", "observational", "unknown"), "design_type")
        probability = self.assignment_design.get("assignment_probability")
        if probability is not None:
            _number(probability, "assignment_probability")
            if not 0 <= probability <= 1:
                raise ValueError("assignment_probability must lie in [0, 1]")
        object.__setattr__(self, "assumptions", tuple(
            _payload(assumption, "assumption") for assumption in self.assumptions))
        if self.identification_spec is not None:
            query = self.identification_spec.get("query")
            if not isinstance(query, Mapping) or query.get("type") != self.estimand:
                raise ValueError("identification_spec.query.type differs from task.estimand")
            _check_network_binding(self, self.identification_spec.get("network_exposure"))
            domain = self.identification_spec.get("variable_domains", {}).get(query.get("outcome"))
            if domain is not None and domain.get("kind") != self.outcome_kind:
                raise ValueError("identification outcome domain differs from task.outcome_kind")
        present = (self.x is not None, self.treatment is not None, self.outcome is not None)
        if any(present) and not all(present):
            raise ValueError("x, treatment and outcome must be supplied together")
        if all(present):
            x = _array(self.x, "x")
            if x.ndim != 2 or x.shape[0] != self.n_nodes or x.shape[1] < 1:
                raise ValueError("x must have shape [n_nodes, n_features] with n_features >= 1")
            object.__setattr__(self, "x", x)
            object.__setattr__(self, "treatment", _array(
                self.treatment, "treatment", (self.n_nodes,), binary=True))
            outcome = _array(self.outcome, "outcome", (self.n_nodes,))
            if self.outcome_kind == "binary" and not np.isin(outcome, [0, 1]).all():
                raise ValueError("binary outcomes must be 0 or 1 before any conversion")
            object.__setattr__(self, "outcome", outcome)

    @property
    def n_nodes(self) -> int:
        return len(self.node_ids)

    @property
    def n_features(self) -> int | None:
        return None if self.x is None else self.x.shape[1]

    def factual_tokens(self) -> np.ndarray:
        """Build the existing [X,T,Y,E_obs,degree/(N-1)] backend input.

        E_obs is a SHARE, not the binary majority state. This explicit adapter
        checks the current backend's one-feature/no-isolate shape restriction;
        checkpoint and identification compatibility still require their verifiers.
        """
        if self.x is None or self.n_features != 1:
            raise ValueError("the current factual-token schema requires one observed feature")
        degree = self.adjacency.sum(axis=1)
        if np.any(degree == 0):
            raise ValueError("the current factual-token schema does not support isolated nodes")
        share = self.adjacency @ self.treatment / degree
        return np.column_stack((self.x[:, 0], self.treatment, self.outcome,
                                share, degree / (self.n_nodes - 1)))


@dataclass(frozen=True, kw_only=True, eq=False)
class IdentificationResult:
    """Task-bound envelope preserving the existing identification result intact.

    ``result`` is the existing result's ``model_dump(mode='python')`` payload,
    including query, programs, certificate, trace and validity domain. Keeping it
    intact avoids replacing the existing executable theorem contracts with text.
    ``estimation_request`` is the handoff compiler's complete serialized request.
    VERIFIED here records an upstream verifier's result; construction does not
    prove it. The consumer must revalidate/replay the request before execution.
    """

    task: TaskSpec
    result: Mapping[str, Any]
    estimation_request: Mapping[str, Any] | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.task, TaskSpec):
            raise ValueError("task must be a TaskSpec")
        _set_payloads(self, "result", "estimation_request", "diagnostics")
        _choice(self.status, ("POINT", "PARTIAL", "NO_USEFUL_ID", "INCOMPATIBLE", "UNSUPPORTED"),
                "identification status")
        _choice(self.verification_status, ("VERIFIED", "REJECTED", "UNSUPPORTED"),
                "verification_status")
        _text(self.result.get("backend"), "identification backend")
        query = self.result.get("query")
        if not isinstance(query, Mapping):
            raise ValueError("result must preserve the original query mapping")
        if query.get("type") != self.task.estimand:
            raise ValueError("identification query.type must match task.estimand")
        if self.task.identification_spec is not None and not _same_payload(
                query, self.task.identification_spec["query"]):
            raise ValueError("identification query differs from the task's complete query")
        _check_network_binding(self.task, self.result.get("network_exposure"))
        if self.verification_status == "VERIFIED":
            programs = ("identified_functional", "set_program") if self.status == "POINT" else (
                "bound_program", "set_program", "identified_set")
            if self.status in ("POINT", "PARTIAL") and not any(
                    self.result.get(key) is not None for key in programs):
                raise ValueError("a verified identified result must preserve its program or set")
        if self.estimation_request is not None:
            if self.status not in ("POINT", "PARTIAL") or self.verification_status != "VERIFIED":
                raise ValueError("only verified POINT/PARTIAL results can carry an estimation request")
            for key, expected in (("identification_status", self.status),
                                  ("verification_status", self.verification_status)):
                if self.estimation_request.get(key) != expected:
                    raise ValueError(f"estimation_request.{key} disagrees with identification")
            _text(self.estimation_request.get("request_type"), "estimation request_type")
            if self.estimation_request.get("estimand") != self.task.estimand:
                raise ValueError("estimation request target differs from task.estimand")
            _check_network_binding(self.task, self.estimation_request.get("network"))
            source = self.estimation_request.get("source_spec")
            if source is not None:
                if not isinstance(source, Mapping) or not _same_payload(source.get("query"), query):
                    raise ValueError("handoff source query differs from the identification query")
                _check_network_binding(self.task, source.get("network_exposure"))
                if self.task.identification_spec is not None and not _same_payload(
                        source, self.task.identification_spec):
                    raise ValueError("handoff source_spec differs from the declared task")
        program = self.result.get("identified_functional")
        if isinstance(program, Mapping):
            if (self.task.target_fingerprint is not None
                    and program.get("target_fingerprint") != self.task.target_fingerprint):
                raise ValueError("identified target fingerprint differs from the declared task")
            if "semantics" in program and program["semantics"] != self.task.target_semantics:
                raise ValueError("identified program semantics differ from the declared task")
            policy_class = program.get("policy_class")
            if policy_class is not None and (
                    tuple(policy_class.get("node_ids", ())) != self.task.node_ids
                    or policy_class.get("budget") != self.task.budget
                    or policy_class.get("budget_mode") != self.task.budget_mode):
                raise ValueError("identified policy class differs from the task's budget/node binding")

    @property
    def status(self) -> IdentificationStatus:
        return self.result.get("status")

    @property
    def verification_status(self) -> VerificationStatus:
        return self.result.get("verification_status")

    @property
    def target_id(self) -> str:
        return self.task.target_id

    @property
    def node_ids(self) -> tuple[str, ...]:
        return self.task.node_ids


@dataclass(frozen=True, kw_only=True, eq=False)
class EstimateBundle:
    """Estimated response surface, scalar, structured set, or unavailable result.

    ``estimand`` and ``semantics`` describe the estimated object, which can be a
    response dependency of the task's policy-score target. A response surface has
    axes [node, treatment, exposure], shape [N,2,2], on the ORIGINAL outcome scale.
    ``lower/upper`` estimate identified-set endpoints; one-sided bounds are valid.
    They are not sampling intervals. ``sampling_lower/upper`` require an explicit
    method, nominal level and coverage scope; their presence certifies no coverage.
    None means unavailable, never zero-width uncertainty or inferred support.

    Nonrectangular sets and specialized count/policy tables belong in
    ``structured_result`` with their original programs and coordinate definitions.
    Population support and finite-sample support remain separate [N,2,2] masks.
    """

    identification: IdentificationResult
    method: str
    estimand: str
    semantics: str
    kind: EstimateKind = "response_surface"
    center: np.ndarray | float | None = None
    lower: np.ndarray | float | None = None
    upper: np.ndarray | float | None = None
    sampling_lower: np.ndarray | float | None = None
    sampling_upper: np.ndarray | float | None = None
    uncertainty_method: str | None = None
    coverage_level: float | None = None
    coverage_scope: Literal["marginal", "simultaneous"] | None = None
    population_support: np.ndarray | None = None
    empirical_support_mask: np.ndarray | None = None
    structured_result: Mapping[str, Any] | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.identification, IdentificationResult):
            raise ValueError("identification must be an IdentificationResult")
        for name in ("method", "estimand", "semantics"):
            _text(getattr(self, name), name)
        _choice(self.kind, ("response_surface", "scalar", "structured", "unavailable"), "kind")
        _set_payloads(self, "structured_result", "provenance", "diagnostics")
        numeric_fields = ("center", "lower", "upper", "sampling_lower", "sampling_upper")
        if self.kind == "unavailable":
            _text(self.note, "unavailable result reason")
        elif (self.status not in ("POINT", "PARTIAL")
              or self.identification.verification_status != "VERIFIED"
              or self.identification.estimation_request is None):
            raise ValueError("estimates require a verified POINT/PARTIAL handoff")
        if self.kind != "unavailable":
            request = self.identification.estimation_request
            dependency = request.get("response_request")
            expected = request
            if isinstance(dependency, Mapping) and self.estimand == dependency.get("estimand"):
                expected = dependency
            if self.estimand != expected.get("estimand"):
                raise ValueError("estimated object is neither the requested target nor its response dependency")
            program = expected.get("program")
            if isinstance(program, Mapping) and "semantics" in program and self.semantics != program["semantics"]:
                raise ValueError("estimate semantics differ from the requested program")
        if self.kind in ("structured", "unavailable"):
            if any(getattr(self, name) is not None for name in numeric_fields):
                raise ValueError("structured/unavailable results must not fabricate numeric surfaces")
            if self.kind == "structured" and not self.structured_result:
                raise ValueError("structured results must preserve their original result payload")
            if self.kind == "unavailable" and self.structured_result is not None:
                raise ValueError("unavailable results cannot carry a computed result")
        else:
            if self.structured_result is not None:
                raise ValueError("use kind='structured' for a specialized result payload")
            if self.kind == "response_surface" and self.task.exposure_definition != "strict_majority":
                raise ValueError("the four-state surface requires strict-majority exposure semantics")
            shape = (self.task.n_nodes, 2, 2) if self.kind == "response_surface" else ()
            for name in numeric_fields:
                value = getattr(self, name)
                if value is not None:
                    array = _array(value, name, shape, allow_infinite=name != "center")
                    object.__setattr__(self, name, float(array) if shape == () else array)
            if self.status == "POINT" and self.center is None:
                raise ValueError("a POINT numeric estimate requires center")
            if self.status == "PARTIAL":
                if self.center is not None:
                    raise ValueError("PARTIAL cannot be silently replaced by a point or midpoint")
                if self.lower is None and self.upper is None:
                    raise ValueError("a PARTIAL numeric result requires at least one bound")
            for low, high in ((self.lower, self.upper), (self.sampling_lower, self.sampling_upper)):
                if low is not None and high is not None and np.any(np.asarray(low) > high):
                    raise ValueError("interval lower endpoints cannot exceed upper endpoints")
            for endpoint, forbidden in ((self.lower, np.inf), (self.upper, -np.inf),
                                        (self.sampling_lower, np.inf), (self.sampling_upper, -np.inf)):
                if endpoint is not None and np.any(np.asarray(endpoint) == forbidden):
                    raise ValueError("interval endpoints have an invalid infinity direction")
        intervals = (self.sampling_lower is not None, self.sampling_upper is not None)
        if any(intervals) != all(intervals):
            raise ValueError("sampling intervals require both endpoints")
        if all(intervals):
            _text(self.uncertainty_method, "uncertainty_method")
            _number(self.coverage_level, "coverage_level")
            if not 0 < self.coverage_level < 1:
                raise ValueError("coverage_level must lie strictly between 0 and 1")
            _choice(self.coverage_scope, ("marginal", "simultaneous"), "coverage_scope")
        elif any(value is not None for value in (
                self.uncertainty_method, self.coverage_level, self.coverage_scope)):
            raise ValueError("interval metadata requires actual sampling interval endpoints")
        for name in ("population_support", "empirical_support_mask"):
            value = getattr(self, name)
            if value is not None:
                if self.kind != "response_surface":
                    raise ValueError("four-state support masks require kind='response_surface'")
                mask = _array(value, name, (self.task.n_nodes, 2, 2), binary=True).astype(bool)
                mask.setflags(write=False)
                object.__setattr__(self, name, mask)
        digest = self.provenance.get("checkpoint_sha256")
        if digest is not None and (not isinstance(digest, str) or len(digest) != 64
                or any(char not in "0123456789abcdefABCDEF" for char in digest)):
            raise ValueError("checkpoint_sha256 must be a 64-character SHA256 hex digest")
        if self.provenance.get("outcome_scale", "original") != "original":
            raise ValueError("estimates must be returned on the original outcome scale")

    @classmethod
    def from_state_means(cls, *, mu_by_state: Mapping[State, np.ndarray], **kwargs: Any) -> EstimateBundle:
        """Assemble named 00/10/11/01 vectors, never reshape an ordered [N,4] array.

        All vectors must already follow task.node_ids. Independent prediction IDs
        must be explicitly aligned by the backend adapter before this call.
        """
        if not isinstance(mu_by_state, Mapping) or set(mu_by_state) != {(0, 0), (0, 1), (1, 0), (1, 1)}:
            raise ValueError("mu_by_state must contain exactly the four (treatment, exposure) states")
        for state in mu_by_state:
            if not isinstance(state, tuple) or any(
                    isinstance(coordinate, (bool, np.bool_)) or not isinstance(coordinate, Integral)
                    for coordinate in state):
                raise ValueError("state coordinates must be integer pairs, not bools or floats")
        identification = kwargs.get("identification")
        if not isinstance(identification, IdentificationResult):
            raise ValueError("identification must be an IdentificationResult")
        n = identification.task.n_nodes
        center = np.empty((n, 2, 2), dtype=float)
        for (treatment, exposure), values in mu_by_state.items():
            center[:, treatment, exposure] = _array(values, f"mu({treatment},{exposure})", (n,))
        return cls(center=center, kind="response_surface", **kwargs)

    @property
    def task(self) -> TaskSpec:
        return self.identification.task

    @property
    def status(self) -> IdentificationStatus:
        return self.identification.status

    @property
    def target_id(self) -> str:
        return self.task.target_id

    @property
    def node_ids(self) -> tuple[str, ...]:
        return self.task.node_ids


@dataclass(frozen=True, kw_only=True, eq=False)
class PolicyResult:
    """Network allocation and its declared objective, or an explicit abstention.

    ``objective`` must name task.estimand; ``criterion`` describes how estimates
    were used. No objective is implicitly reinterpreted as actual rollout welfare.
    Budget usage and selected nodes are derived from allocation, never duplicated.
    trace carries serialized upstream optimization steps without losing gains.
    assignments_considered is optional: greedy steps are not exhaustive counts.
    Construction checks feasibility and exposure, not optimality or causal value.
    """

    estimates: EstimateBundle
    objective: str
    criterion: str
    method: str
    budget: int
    budget_mode: BudgetMode
    feasible: bool
    stop_reason: str
    allocation: np.ndarray | None = None
    predicted_value: float | None = None
    initial_value: float | None = None
    resulting_exposure: np.ndarray | None = None
    abstain: bool = False
    support_violations: int | None = None
    assignments_considered: int | None = None
    trace: tuple[Mapping[str, Any], ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.estimates, EstimateBundle):
            raise ValueError("estimates must be an EstimateBundle")
        for name in ("objective", "criterion", "method", "stop_reason"):
            _text(getattr(self, name), name)
        if self.objective != self.task.estimand:
            raise ValueError("policy objective must match the declared task estimand")
        _integer(self.budget, "budget", self.task.n_nodes)
        _choice(self.budget_mode, ("exact", "at_most"), "budget_mode")
        if self.task.budget is not None and (
                self.budget != self.task.budget or self.budget_mode != self.task.budget_mode):
            raise ValueError("policy budget/class differs from the declared task")
        if not isinstance(self.feasible, bool) or not isinstance(self.abstain, bool):
            raise ValueError("feasible and abstain must be bool")
        for name in ("support_violations", "assignments_considered"):
            if getattr(self, name) is not None:
                _integer(getattr(self, name), name)
        _set_payloads(self, "diagnostics")
        object.__setattr__(self, "trace", tuple(_payload(step, "trace step") for step in self.trace))
        if self.abstain:
            if self.feasible or any(value is not None for value in (
                    self.allocation, self.predicted_value, self.initial_value, self.resulting_exposure)):
                raise ValueError("abstention has no allocation/value/exposure and cannot be feasible")
            return
        if self.estimates.kind == "unavailable":
            raise ValueError("an unavailable estimate requires policy abstention")
        if self.criterion in ("center", "lower", "upper") and getattr(self.estimates, self.criterion) is None:
            raise ValueError(f"criterion={self.criterion!r} requires the corresponding numeric estimate")
        allocation = _array(self.allocation, "allocation", (self.task.n_nodes,), binary=True)
        object.__setattr__(self, "allocation", allocation)
        _number(self.predicted_value, "predicted_value")
        if self.initial_value is not None:
            _number(self.initial_value, "initial_value")
        budget_ok = (self.budget_used == self.budget if self.budget_mode == "exact"
                     else self.budget_used <= self.budget)
        counts = self.task.adjacency @ allocation
        if self.task.exposure_definition == "strict_majority":
            degree = self.task.adjacency.sum(axis=1)
            if np.any(degree == 0):
                raise ValueError("current strict-majority policy does not support isolated nodes")
            exposure = (counts > degree // 2).astype(np.int64)
        else:
            exposure = counts
        if self.resulting_exposure is not None:
            supplied = _array(self.resulting_exposure, "resulting_exposure", (self.task.n_nodes,))
            if not np.array_equal(supplied, exposure):
                raise ValueError("resulting_exposure differs from allocation and the declared graph")
        exposure.setflags(write=False)
        object.__setattr__(self, "resulting_exposure", exposure)
        if self.estimates.population_support is not None:
            mask = self.estimates.population_support
            violations = int(np.count_nonzero(~mask[np.arange(self.task.n_nodes), allocation, exposure]))
            if self.support_violations is not None and self.support_violations != violations:
                raise ValueError("support_violations differs from the population support mask")
            object.__setattr__(self, "support_violations", violations)
        if self.feasible and (not budget_ok or (self.support_violations or 0) > 0):
            raise ValueError("feasible=True conflicts with budget or population support constraints")

    @property
    def task(self) -> TaskSpec:
        return self.estimates.task

    @property
    def target_id(self) -> str:
        return self.task.target_id

    @property
    def node_ids(self) -> tuple[str, ...]:
        return self.task.node_ids

    @property
    def budget_used(self) -> int | None:
        return None if self.allocation is None else int(self.allocation.sum())

    @property
    def selected_nodes(self) -> tuple[int, ...]:
        return () if self.allocation is None else tuple(int(i) for i in np.flatnonzero(self.allocation))

    @property
    def objective_gain(self) -> float | None:
        if self.predicted_value is None or self.initial_value is None:
            return None
        return self.predicted_value - self.initial_value
