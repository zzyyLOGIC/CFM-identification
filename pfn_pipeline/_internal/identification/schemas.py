from __future__ import annotations

import hashlib
import json
import math
from enum import Enum
from typing import Any, Literal, Union

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StrictInt, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IdentificationStatus(str, Enum):
    POINT = "POINT"
    PARTIAL = "PARTIAL"
    NO_USEFUL_ID = "NO_USEFUL_ID"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNSUPPORTED = "UNSUPPORTED"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    UNSUPPORTED = "UNSUPPORTED"


class AssumptionStatus(str, Enum):
    """Workflow status for an assumption record; not a statistical truth probability."""
    CERTIFIED = "CERTIFIED"
    DERIVED = "DERIVED"
    ADMITTED = "ADMITTED"
    PROPOSED = "PROPOSED"
    UNRESOLVED = "UNRESOLVED"
    NOT_ADMITTED = "NOT_ADMITTED"
    CONTRADICTED = "CONTRADICTED"


class Assumption(StrictModel):
    name: str
    source: Literal[
        "study_design_metadata",
        "study_protocol",
        "demo_specification",
        "domain_knowledge",
        "human_confirmation",
        "deterministic_derivation",
        "llm_candidate",
        "withheld_metadata",
        "unresolved_input",
    ]
    # ``confirmed`` is retained because older theorem families consume it.
    # ``status`` is the richer v0.5.1-style workflow state.  The validator keeps
    # the two representations consistent so downstream legacy code cannot treat
    # PROPOSED/UNRESOLVED assumptions as admitted facts.
    confirmed: bool = False
    status: AssumptionStatus | None = None
    evidence: list[str] = Field(default_factory=list)
    details: str = ""

    @model_validator(mode="after")
    def align_status_and_confirmed(self):
        admitted = {AssumptionStatus.CERTIFIED, AssumptionStatus.DERIVED, AssumptionStatus.ADMITTED}
        if self.source in {"llm_candidate", "withheld_metadata", "unresolved_input"}:
            if self.status in admitted or (self.status is None and self.confirmed):
                raise ValueError("A proposal or unresolved source cannot certify/admit an assumption; record its reviewed evidence source first")
        if self.status is None:
            if self.confirmed:
                if self.source in {"study_design_metadata", "study_protocol", "demo_specification"}:
                    self.status = AssumptionStatus.CERTIFIED
                elif self.source == "deterministic_derivation":
                    self.status = AssumptionStatus.DERIVED
                else:
                    self.status = AssumptionStatus.ADMITTED
            else:
                self.status = (AssumptionStatus.PROPOSED if self.source == "llm_candidate"
                               else AssumptionStatus.UNRESOLVED)
        self.confirmed = self.status in admitted
        return self


class StudyDesign(StrictModel):
    design_type: Literal[
        "randomized_experiment",
        "observational",
        "unknown",
    ]
    assignment_probability: float | None = None
    assignment_unit: list[str] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def validate_probability(self):
        if self.assignment_probability is not None and not 0.0 <= self.assignment_probability <= 1.0:
            raise ValueError("assignment_probability must lie in [0, 1]")
        return self


class VariableDomain(StrictModel):
    kind: Literal["binary", "continuous", "categorical"]
    values: list[int | float | str] | None = None
    lower: float | None = None
    upper: float | None = None

    @model_validator(mode="after")
    def validate_domain(self):
        if self.kind == "binary":
            vals = self.values if self.values is not None else [0, 1]
            if set(vals) != {0, 1}:
                raise ValueError("binary variables must use values {0, 1}")
            self.values = [0, 1]
            if self.lower is None:
                self.lower = 0.0
            if self.upper is None:
                self.upper = 1.0
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise ValueError("domain lower bound cannot exceed upper bound")
        return self

    def finite_lower_bound(self) -> float | None:
        if self.lower is None or not math.isfinite(float(self.lower)):
            return None
        return float(self.lower)

    def finite_upper_bound(self) -> float | None:
        if self.upper is None or not math.isfinite(float(self.upper)):
            return None
        return float(self.upper)

    def finite_numeric_bounds(self) -> tuple[float, float] | None:
        lower = self.finite_lower_bound()
        upper = self.finite_upper_bound()
        if lower is None or upper is None:
            return None
        return lower, upper

    def finite_support_restrictions(self) -> tuple[float | None, float | None]:
        """Return finite one- or two-sided support restrictions.

        `None` means that side is not finitely restricted. This matters for
        partial identification: a single finite support bound can imply a
        half-infinite identified set even when no two-sided finite interval is
        available.
        """
        return self.finite_lower_bound(), self.finite_upper_bound()


class BusinessInput(StrictModel):
    business_question: str
    data_schema: dict[str, str]
    analysis_unit: list[str]
    treatment_column: str
    outcome_column: str
    column_domains: dict[str, VariableDomain] = Field(default_factory=dict)
    study_design: StudyDesign
    trusted_assumptions: list[Assumption] = Field(default_factory=list)
    domain_knowledge: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_trusted_role_metadata(self):
        if not self.analysis_unit:
            raise ValueError("BusinessInput.analysis_unit must be supplied as trusted metadata")
        unknown = set(self.analysis_unit).difference(self.data_schema)
        if unknown:
            raise ValueError(
                f"BusinessInput.analysis_unit references unknown columns: {sorted(unknown)}"
            )
        for role, column in {
            "treatment_column": self.treatment_column,
            "outcome_column": self.outcome_column,
        }.items():
            if column not in self.data_schema:
                raise ValueError(f"BusinessInput.{role} references unknown column: {column!r}")
        if self.treatment_column == self.outcome_column:
            raise ValueError("BusinessInput treatment_column and outcome_column must differ")
        return self


QueryType = Literal[
    "ATE",
    "CATE",
    "DIRECT_EFFECT",
    "SPILLOVER_EFFECT",
    "POLICY_VALUE",
    "DISTRIBUTIONAL_EFFECT",
    "NETWORK_RESPONSE_SURFACE",
    "NETWORK_MAJORITY_RESPONSE_POLICY_SCORE",
    "UNRESOLVED",
]


class QueryAlternative(StrictModel):
    """A plausible secondary reading of the business question.

    Alternatives are semantic audit information only. They are never routed to
    an identification backend as if the user had selected them.
    """

    type: QueryType
    reason: str


class QuerySpec(StrictModel):
    """Typed causal-query candidate produced by the semantic front-end.

    The legacy generic Business Mode executes only the narrow ATE contract. The
    advisor-facing network vertical slice can additionally bridge an exactly
    HUMAN_CONFIRMED DIRECT_EFFECT query into the audited I1 network contract and
    the retained POINT/PARTIAL theorem family. POLICY_VALUE remains Theory-Mode.
    Other query types stay explicit so unsupported coverage is reported rather
    than silently coerced to ATE.
    """

    type: QueryType = "ATE"
    treatment: str
    outcome: str
    expression: str = ""
    target_population: str = "overall_population"
    conditioning_variables: list[str] = Field(default_factory=list)
    reference_exposure_definition: str | None = Field(
        default=None,
        validation_alias=AliasChoices("reference_exposure_definition", "exposure_definition"),
    )
    target_exposure_semantics: Literal[
        "true_sufficient_exposure_state",
        "reference_exposure_state",
        "design_averaged_majority_response",
    ] | None = None
    exposure_value: int | float | str | None = None
    policy_description: str | None = None
    # Binds a confirmed policy query to the complete context-indexed action table.
    policy_fingerprint: str | None = None
    # The stochastic response target depends on the graph, context and design p.
    response_target_fingerprint: str | None = None
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    alternatives: list[QueryAlternative] = Field(default_factory=list)
    resolution: Literal["RESOLVED", "NEEDS_CONFIRMATION", "UNRESOLVED"] = "RESOLVED"
    authority: Literal["PROPOSED", "HUMAN_CONFIRMED", "TRUSTED_FIXTURE"] = "PROPOSED"
    interpretation_notes: str = ""

    @property
    def exposure_definition(self) -> str | None:
        """Backward-compatible Python alias for the reference exposure mapping.

        JSON serialization uses ``reference_exposure_definition`` only. New code
        should use that explicit field so reference and target semantics cannot be
        conflated.
        """

        return self.reference_exposure_definition

    @exposure_definition.setter
    def exposure_definition(self, value: str | None) -> None:
        self.reference_exposure_definition = value

    @model_validator(mode="after")
    def canonicalize_expression(self):
        if self.treatment == self.outcome:
            raise ValueError("query treatment and outcome must be different variables")
        # Never trust free-form mathematics from an LLM. ATE has an executable
        # canonical expression; unsupported families receive a non-executable
        # typed descriptor that cannot be mistaken for a derived functional.
        if self.type == "ATE":
            self.expression = f"E[{self.outcome}(1)-{self.outcome}(0)]"
        elif self.type == "CATE":
            condition = ",".join(self.conditioning_variables) or "unspecified_subgroup"
            self.expression = f"CATE[{self.outcome};{self.treatment}|{condition}]"
        elif self.type == "DIRECT_EFFECT":
            reference_exposure = self.reference_exposure_definition or "unspecified_reference_exposure"
            target_semantics = self.target_exposure_semantics or "unspecified_target_exposure_semantics"
            exposure_value = "unspecified" if self.exposure_value is None else str(self.exposure_value)
            self.expression = (
                f"DIRECT_EFFECT[{self.outcome};{self.treatment}|"
                f"reference_g={reference_exposure};target={target_semantics};z={exposure_value}]"
            )
        elif self.type == "SPILLOVER_EFFECT":
            reference_exposure = self.reference_exposure_definition or "unspecified_reference_exposure"
            target_semantics = self.target_exposure_semantics or "unspecified_target_exposure_semantics"
            exposure_value = "unspecified" if self.exposure_value is None else str(self.exposure_value)
            self.expression = (
                f"SPILLOVER_EFFECT[{self.outcome};{self.treatment}|"
                f"reference_g={reference_exposure};target={target_semantics};z={exposure_value}]"
            )
        elif self.type == "POLICY_VALUE":
            policy = self.policy_description or "unspecified_policy"
            self.expression = f"POLICY_VALUE[{self.outcome};{policy}]"
        elif self.type == "NETWORK_RESPONSE_SURFACE":
            self.expression = (f"NETWORK_RESPONSE_SURFACE[{self.outcome};{self.treatment}|"
                               f"design_averaged_majority;target={self.response_target_fingerprint}]")
        elif self.type == "NETWORK_MAJORITY_RESPONSE_POLICY_SCORE":
            self.expression = (f"NETWORK_MAJORITY_RESPONSE_POLICY_SCORE[{self.outcome};{self.treatment}|"
                               f"response={self.response_target_fingerprint};policy_class={self.policy_fingerprint}]")
        elif self.type == "DISTRIBUTIONAL_EFFECT":
            self.expression = f"DISTRIBUTIONAL_EFFECT[{self.outcome};{self.treatment}]"
        else:
            self.expression = "UNRESOLVED_QUERY"
        return self


class AssumptionConflict(StrictModel):
    """Deterministic warning about query semantics versus trusted assumptions.

    This is kept separate from query resolution: a question can be semantically
    unambiguous even when the currently declared assumptions are unsuitable for
    answering it.
    """

    code: str
    query_type: QueryType
    assumption: str
    source: Literal["trusted_assumption_check"] = "trusted_assumption_check"
    severity: Literal["WARNING", "BLOCKING"] = "WARNING"
    details: str


class DiscardedAssumptionCandidate(StrictModel):
    """LLM-only assumption proposal removed by deterministic semantic normalization."""

    assumption: Assumption
    reason_code: str
    details: str


class VariableSemanticSpec(StrictModel):
    analysis_unit: list[str]
    analysis_unit_source: Literal["business_metadata", "llm_candidate"] = "llm_candidate"
    treatment: str
    treatment_source: Literal["business_metadata", "llm_candidate"] = "llm_candidate"
    outcome: str
    outcome_source: Literal["business_metadata", "llm_candidate"] = "llm_candidate"
    covariates: list[str] = Field(default_factory=list)
    variable_domains: dict[str, VariableDomain] = Field(default_factory=dict)
    query: QuerySpec
    study_design: StudyDesign
    candidate_assumptions: list[Assumption] = Field(default_factory=list)
    discarded_candidate_assumptions: list[DiscardedAssumptionCandidate] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    assumption_conflicts: list[AssumptionConflict] = Field(default_factory=list)
    normalization_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_query_alignment(self):
        if self.query.treatment != self.treatment:
            raise ValueError("query.treatment must match the top-level treatment field")
        if self.query.outcome != self.outcome:
            raise ValueError("query.outcome must match the top-level outcome field")
        if self.unresolved and self.query.resolution == "RESOLVED":
            self.query.resolution = "NEEDS_CONFIRMATION"
        return self


class StructureSpec(StrictModel):
    representation_type: Literal[
        "design_based_potential_outcomes",
        "fixed_network_interference",
        "graphical",
        "unspecified",
    ]
    variables: list[str]
    directed_edges: list[tuple[str, str]] = Field(default_factory=list)
    bidirected_edges: list[tuple[str, str]] = Field(default_factory=list)
    source: Literal[
        "study_design",
        "domain_knowledge",
        "causal_discovery",
        "human_specified",
        "none",
    ]
    notes: str = ""


class NetworkExposureSpec(StrictModel):
    """Typed fixed-network exposure semantics for the minimal interference fixture."""

    network_id: str
    node_ids: list[str]
    undirected_edges: list[tuple[str, str]]
    exposure_mapping: Literal["treated_neighbor_count_1hop"] = "treated_neighbor_count_1hop"
    fixed_network: Literal[True] = True

    @model_validator(mode="after")
    def validate_network(self):
        if not self.network_id:
            raise ValueError("network_id must be nonempty")
        if not self.node_ids or len(set(self.node_ids)) != len(self.node_ids):
            raise ValueError("node_ids must be nonempty and unique")
        index = {node: i for i, node in enumerate(self.node_ids)}
        canonical: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for left, right in self.undirected_edges:
            if left not in index or right not in index:
                raise ValueError("every network edge endpoint must appear in node_ids")
            if left == right:
                raise ValueError("self-loops are not allowed in the minimal fixed-network fixture")
            edge = (left, right) if index[left] < index[right] else (right, left)
            if edge in seen:
                raise ValueError("duplicate undirected network edge")
            seen.add(edge)
            canonical.append(edge)
        canonical.sort(key=lambda pair: (index[pair[0]], index[pair[1]]))
        self.undirected_edges = canonical
        return self

    def degree_map(self) -> dict[str, int]:
        result = {node: 0 for node in self.node_ids}
        for left, right in self.undirected_edges:
            result[left] += 1
            result[right] += 1
        return result

    def max_degree(self) -> int:
        return max(self.degree_map().values(), default=0)

    def reachable_neighbor_counts(self) -> dict[str, list[int]]:
        return {node: list(range(degree + 1)) for node, degree in self.degree_map().items()}

    def semantic_fingerprint(self) -> str:
        """Stable fingerprint for the executable network/exposure semantics.

        The fingerprint is intentionally based only on canonical typed fields, not
        on display text or object identity, so another repository can recompute it
        from JSON before consuming an estimation handoff.
        """
        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ThresholdNetworkExposureSpec(StrictModel):
    """Fixed-network binary threshold exposure used by the retained direct-effect oracle.

    For node i, H_i is the treated-neighbor share and the *reference* exposure is
    Z_i = 1[H_i >= threshold].  The point fixture treats this reference mapping as
    correct; the partial fixture relaxes that claim through an explicit propensity-
    ratio sensitivity model.  Isolated nodes are excluded because their treated-
    neighbor share is undefined in this minimal theorem family.
    """

    network_id: str
    node_ids: list[str]
    undirected_edges: list[tuple[str, str]]
    exposure_mapping: Literal["treated_neighbor_share_threshold_1hop"] = (
        "treated_neighbor_share_threshold_1hop"
    )
    threshold: float = Field(ge=0.0, le=1.0)
    fixed_network: Literal[True] = True

    @model_validator(mode="after")
    def validate_network(self):
        if not self.network_id:
            raise ValueError("network_id must be nonempty")
        if not self.node_ids or len(set(self.node_ids)) != len(self.node_ids):
            raise ValueError("node_ids must be nonempty and unique")
        index = {node: i for i, node in enumerate(self.node_ids)}
        canonical: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for left, right in self.undirected_edges:
            if left not in index or right not in index:
                raise ValueError("every network edge endpoint must appear in node_ids")
            if left == right:
                raise ValueError("self-loops are not allowed in the minimal fixed-network fixture")
            edge = (left, right) if index[left] < index[right] else (right, left)
            if edge in seen:
                raise ValueError("duplicate undirected network edge")
            seen.add(edge)
            canonical.append(edge)
        canonical.sort(key=lambda pair: (index[pair[0]], index[pair[1]]))
        self.undirected_edges = canonical
        if any(degree == 0 for degree in self.degree_map().values()):
            raise ValueError(
                "threshold-exposure fixture requires every node to have at least one neighbor"
            )
        return self

    def degree_map(self) -> dict[str, int]:
        result = {node: 0 for node in self.node_ids}
        for left, right in self.undirected_edges:
            result[left] += 1
            result[right] += 1
        return result

    def semantic_fingerprint(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()



class FiniteLocalExposureMappingSpec(StrictModel):
    """Finite deterministic local exposure mapping used by the mixture-ID theorem family.

    Local assignments are encoded as binary strings in the canonical neighbor order of
    the enclosing network spec.  A degree-zero node therefore has the single key ``""``.
    The mapping object itself is network-agnostic; the enclosing network structure checks
    node coverage and assignment-string lengths.
    """

    mapping_id: str
    state_labels: list[str]
    context_ids: list[str]
    state_by_local_assignment: dict[str, dict[str, dict[str, str]]]

    @model_validator(mode="after")
    def validate_mapping(self):
        if not self.mapping_id.strip():
            raise ValueError("mapping_id must be nonempty")
        if not self.state_labels or len(set(self.state_labels)) != len(self.state_labels):
            raise ValueError("state_labels must be nonempty and unique")
        if any(not state.strip() for state in self.state_labels):
            raise ValueError("state_labels must be nonempty strings")
        if not self.context_ids or len(set(self.context_ids)) != len(self.context_ids):
            raise ValueError("context_ids must be nonempty and unique")
        if any(not context.strip() for context in self.context_ids):
            raise ValueError("context_ids must be nonempty strings")
        if set(self.state_by_local_assignment) != set(self.context_ids):
            raise ValueError(
                "state_by_local_assignment must contain exactly the declared context_ids"
            )
        allowed_states = set(self.state_labels)
        for context_id in self.context_ids:
            node_maps = self.state_by_local_assignment[context_id]
            if not node_maps:
                raise ValueError("each exposure-mapping context must contain at least one node")
            for node_id, assignment_map in node_maps.items():
                if not node_id.strip():
                    raise ValueError("exposure-mapping node ids must be nonempty")
                if not assignment_map:
                    raise ValueError("each node exposure mapping must contain local assignments")
                used_states: set[str] = set()
                for assignment, state in assignment_map.items():
                    if any(bit not in {"0", "1"} for bit in assignment):
                        raise ValueError("local assignment keys must be binary strings")
                    if state not in allowed_states:
                        raise ValueError("exposure mapping references an undeclared state label")
                    used_states.add(state)
                if used_states != allowed_states:
                    raise ValueError(
                        "each node exposure truth table must give every declared state a nonempty preimage"
                    )
        return self

    def semantic_fingerprint(self) -> str:
        # mapping_id is provenance/identity, not structural semantics. Excluding it
        # lets the candidate-family validator reject duplicated structural classes
        # that merely carry different labels.
        payload_obj = self.model_dump(mode="json")
        payload_obj.pop("mapping_id", None)
        payload = json.dumps(
            payload_obj,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class FiniteCategoricalNetworkExposureSpec(StrictModel):
    """Fixed network plus a finite recorded/working local exposure mapping."""

    network_id: str
    node_ids: list[str]
    undirected_edges: list[tuple[str, str]]
    exposure_mapping: Literal["finite_local_exposure_table_v1"] = (
        "finite_local_exposure_table_v1"
    )
    working_mapping: FiniteLocalExposureMappingSpec
    fixed_network: Literal[True] = True

    @model_validator(mode="after")
    def validate_network_and_mapping(self):
        if not self.network_id.strip():
            raise ValueError("network_id must be nonempty")
        if not self.node_ids or len(set(self.node_ids)) != len(self.node_ids):
            raise ValueError("node_ids must be nonempty and unique")
        index = {node: i for i, node in enumerate(self.node_ids)}
        canonical: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for left, right in self.undirected_edges:
            if left not in index or right not in index:
                raise ValueError("every network edge endpoint must appear in node_ids")
            if left == right:
                raise ValueError("self-loops are not allowed in the finite exposure fixture")
            edge = (left, right) if index[left] < index[right] else (right, left)
            if edge in seen:
                raise ValueError("duplicate undirected network edge")
            seen.add(edge)
            canonical.append(edge)
        canonical.sort(key=lambda pair: (index[pair[0]], index[pair[1]]))
        self.undirected_edges = canonical
        self.validate_candidate_mapping(self.working_mapping)
        return self

    def degree_map(self) -> dict[str, int]:
        result = {node: 0 for node in self.node_ids}
        for left, right in self.undirected_edges:
            result[left] += 1
            result[right] += 1
        return result

    def neighbor_order(self) -> dict[str, list[str]]:
        index = {node: i for i, node in enumerate(self.node_ids)}
        result = {node: [] for node in self.node_ids}
        for left, right in self.undirected_edges:
            result[left].append(right)
            result[right].append(left)
        for node in result:
            result[node].sort(key=index.__getitem__)
        return result

    @staticmethod
    def _binary_assignment_keys(degree: int) -> set[str]:
        if degree == 0:
            return {""}
        return {
            format(value, f"0{degree}b")
            for value in range(2**degree)
        }

    def validate_candidate_mapping(self, mapping: FiniteLocalExposureMappingSpec) -> None:
        expected_nodes = set(self.node_ids)
        degrees = self.degree_map()
        if set(mapping.context_ids) != set(self.working_mapping.context_ids):
            raise ValueError(
                "finite exposure candidate context_ids must match the working mapping"
            )
        for context_id in mapping.context_ids:
            node_maps = mapping.state_by_local_assignment[context_id]
            if set(node_maps) != expected_nodes:
                raise ValueError(
                    "finite exposure mapping must contain exactly the network node_ids in every context"
                )
            for node_id in self.node_ids:
                expected_assignments = self._binary_assignment_keys(degrees[node_id])
                if set(node_maps[node_id]) != expected_assignments:
                    raise ValueError(
                        "finite exposure mapping must enumerate every local binary neighbor assignment exactly once"
                    )

    def semantic_fingerprint(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class FiniteExposureCandidateSetSpec(StrictModel):
    """Finite global candidate family for set-valued exposure-structure uncertainty."""

    kind: Literal["finite_exposure_candidate_set_v1"] = "finite_exposure_candidate_set_v1"
    candidates: list[FiniteLocalExposureMappingSpec]

    @model_validator(mode="after")
    def validate_candidates(self):
        if not self.candidates:
            raise ValueError("finite exposure candidate set must be nonempty")
        candidate_ids = [candidate.mapping_id for candidate in self.candidates]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("finite exposure candidate mapping_ids must be unique")
        candidate_fingerprints = [candidate.semantic_fingerprint() for candidate in self.candidates]
        if len(set(candidate_fingerprints)) != len(candidate_fingerprints):
            raise ValueError("finite exposure candidate semantic fingerprints must be unique")
        return self

    def semantic_fingerprint(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ExposurePropensityRatioSensitivitySpec(StrictModel):
    """Constant special case of the exposure-propensity sensitivity model.

    Schröder et al. (2026, Eq. 9) allow context/exposure-specific bounds b^- and
    b^+ on the ratio between the true and employed exposure propensities. v0.2.11
    deliberately retains the nested constant family b^- = 1/Gamma, b^+ = Gamma
    with finite Gamma >= 1. Gamma=1 means no exposure-propensity shift; Gamma>1
    is the supported PARTIAL-identification fixture.
    """

    kind: Literal["exposure_propensity_ratio_gamma"] = "exposure_propensity_ratio_gamma"
    gamma: float = Field(ge=1.0)

    @model_validator(mode="after")
    def validate_finite_gamma(self):
        if not math.isfinite(float(self.gamma)):
            raise ValueError("gamma must be finite")
        return self

    def lower_ratio(self) -> float:
        return 1.0 / float(self.gamma)

    def upper_ratio(self) -> float:
        return float(self.gamma)


NetworkStructureSpec = Union[
    NetworkExposureSpec,
    ThresholdNetworkExposureSpec,
    FiniteCategoricalNetworkExposureSpec,
]
ExposureUncertaintySpec = Union[
    ExposurePropensityRatioSensitivitySpec,
    FiniteExposureCandidateSetSpec,
]

# I1 is a structure-qualification layer, not a structure-truth oracle.  Source
# records where the structure came from; analysis status records how it may enter
# the current causal analysis.  These are deliberately orthogonal.
InterferenceStructureSourceStatus = Literal[
    "MODEL_PROPOSED",
    "EXPERT_PROVIDED",
    "SYSTEM_KNOWN",
    "DESIGN_KNOWN",
    "SYNTHETIC_GROUND_TRUTH",
]
InterferenceStructureAnalysisStatus = Literal[
    "UNRESOLVED",
    "ACCEPTED_AS_ASSUMPTION",
    "SET_VALUED",
    "REJECTED",
]
# Compatibility-only vocabulary for v0.2.11 callers. It is no longer the
# authoritative internal representation and must not be read as a truth label.
InterferenceStructureAuthority = Literal["PROPOSED", "HUMAN_CONFIRMED", "TRUSTED_FIXTURE"]
ExposureMappingClaim = Literal[
    "ASSERTED_SUFFICIENT",
    "REFERENCE_WITH_UNCERTAINTY",
    "UNSPECIFIED",
]

# Variable-level causal-structure I1 contract. This is deliberately separate
# from unit-level interference/network structure. It is interface-only in
# v0.2.13: no Identification backend consumes it yet.
VariableCausalStructureSourceStatus = Literal[
    "MODEL_PROPOSED",
    "EXPERT_PROVIDED",
    "SYSTEM_KNOWN",
    "DESIGN_KNOWN",
    "SYNTHETIC_GROUND_TRUTH",
]
VariableCausalStructureAnalysisStatus = Literal[
    "UNRESOLVED",
    "ACCEPTED_AS_ASSUMPTION",
    "SET_VALUED",
    "REJECTED",
]


class VariableCausalGraphCandidate(StrictModel):
    """Ordered variable-level directed-graph candidate for future causal discovery adapters.

    The ordered ``variable_names`` field is part of the semantics because discovery
    models such as CDFM return matrices whose row/column order must be preserved.
    This object intentionally represents a *candidate*, not a certified true DAG.
    """

    representation_type: Literal["directed_graph_candidate"] = "directed_graph_candidate"
    variable_names: list[str]
    directed_edges: list[tuple[str, str]] = Field(default_factory=list)
    edge_probabilities: list[list[float]] | None = None
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_candidate(self):
        if not self.variable_names or len(set(self.variable_names)) != len(self.variable_names):
            raise ValueError("variable_names must be nonempty and unique")
        index = {name: i for i, name in enumerate(self.variable_names)}
        canonical: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for parent, child in self.directed_edges:
            if parent not in index or child not in index:
                raise ValueError("every directed edge endpoint must appear in variable_names")
            if parent == child:
                raise ValueError("self-loops are not allowed in a variable causal graph candidate")
            edge = (parent, child)
            if edge in seen:
                raise ValueError("duplicate directed edge")
            seen.add(edge)
            canonical.append(edge)
        canonical.sort(key=lambda edge: (index[edge[0]], index[edge[1]]))
        self.directed_edges = canonical

        if self.edge_probabilities is not None:
            d = len(self.variable_names)
            if len(self.edge_probabilities) != d or any(len(row) != d for row in self.edge_probabilities):
                raise ValueError("edge_probabilities must be a D x D matrix matching variable_names")
            normalized: list[list[float]] = []
            for i, row in enumerate(self.edge_probabilities):
                out_row: list[float] = []
                for j, value in enumerate(row):
                    value = float(value)
                    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                        raise ValueError("edge probabilities must be finite and lie in [0, 1]")
                    if i == j and abs(value) > 1e-12:
                        raise ValueError("edge-probability diagonal must be zero")
                    out_row.append(value)
                normalized.append(out_row)
            self.edge_probabilities = normalized
        return self

    def semantic_fingerprint(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class VariableCausalStructureReceipt(StrictModel):
    contract_version: Literal["variable-causal-structure-v1"] = "variable-causal-structure-v1"
    provider_id: str
    source_status: VariableCausalStructureSourceStatus
    analysis_status: VariableCausalStructureAnalysisStatus
    semantic_fingerprint: str
    provenance: dict[str, str] = Field(default_factory=dict)


class VariableCausalStructureOutput(StrictModel):
    """Future I1 output for variable-level causal discovery/knowledge providers.

    v0.2.13 intentionally does not route this object into IdentificationSpec.
    It exists so a later CDFM adapter can be added without conflating a learned
    variable graph with the current interference network ``A``.
    """

    contract_version: Literal["variable-causal-structure-v1"] = "variable-causal-structure-v1"
    provider_id: str
    source_status: VariableCausalStructureSourceStatus
    analysis_status: VariableCausalStructureAnalysisStatus
    graph_candidate: VariableCausalGraphCandidate
    provenance: dict[str, str] = Field(default_factory=dict)
    qualification_evidence: list[str] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def validate_output(self):
        if not self.provider_id:
            raise ValueError("provider_id must be nonempty")
        return self

    def semantic_fingerprint(self) -> str:
        # Qualification/provenance are deliberately excluded: changing a candidate
        # from UNRESOLVED to ACCEPTED_AS_ASSUMPTION must not change the graph
        # semantics being fingerprinted. The receipt carries statuses separately.
        payload = {
            "contract_version": self.contract_version,
            "graph_candidate": self.graph_candidate.model_dump(mode="json"),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def receipt(self) -> VariableCausalStructureReceipt:
        return VariableCausalStructureReceipt(
            provider_id=self.provider_id,
            source_status=self.source_status,
            analysis_status=self.analysis_status,
            semantic_fingerprint=self.semantic_fingerprint(),
            provenance=dict(self.provenance),
        )


class CDFMProviderConfig(StrictModel):
    """Configuration seam for a future CDFM adapter; no CDFM import occurs here."""

    provider_kind: Literal["CDFM"] = "CDFM"
    model_id: str = "DMIRLAB/CDFM"
    device: Literal["auto", "cpu", "cuda"] = "auto"
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    preserve_edge_probabilities: bool = True


class ReferenceExposurePropensityUpperBoundFact(StrictModel):
    """Typed population-level applicability fact used only for sharpness checks.

    A finite-sample estimate is not silently promoted to an exact population fact.
    The minimal Theory-Mode demo uses ``THEORY_DECLARED``; production code would
    need an independently justified/certified source before using this fact to
    upgrade a valid outer bound to a sharp identified set.
    """

    kind: Literal["reference_exposure_propensity_upper_bound"] = (
        "reference_exposure_propensity_upper_bound"
    )
    value: float = Field(ge=0.0, le=1.0)
    source_type: Literal[
        "THEORY_DECLARED",
        "DESIGN_KNOWN",
        "SYSTEM_KNOWN",
        "SYNTHETIC_GROUND_TRUTH",
        "EXTERNALLY_CERTIFIED_POPULATION_FACT",
        "FINITE_SAMPLE_ESTIMATE",
    ] = "THEORY_DECLARED"
    analysis_status: Literal["UNRESOLVED", "ACCEPTED_AS_POPULATION_FACT"] = (
        "UNRESOLVED"
    )
    evidence: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_fact(self):
        if not math.isfinite(float(self.value)):
            raise ValueError("reference exposure propensity upper bound must be finite")
        if self.analysis_status == "ACCEPTED_AS_POPULATION_FACT":
            if self.source_type == "FINITE_SAMPLE_ESTIMATE":
                raise ValueError(
                    "a finite-sample estimate cannot be treated as an exact population applicability fact"
                )
            if not any(item.strip() for item in self.evidence):
                raise ValueError(
                    "accepted population applicability fact requires nonempty evidence/provenance"
                )
        return self

    def usable_for_sharpness(self) -> bool:
        return self.analysis_status == "ACCEPTED_AS_POPULATION_FACT"


def interference_structure_semantic_fingerprint(
    network_exposure: NetworkStructureSpec,
    exposure_uncertainty: ExposureUncertaintySpec | None,
    exposure_mapping_claim: ExposureMappingClaim,
) -> str:
    """Hash structural semantics only; qualification/provenance are separate."""
    payload = {
        "contract_version": "interference-structure-v2",
        "network_exposure": network_exposure.model_dump(mode="json"),
        "exposure_mapping_claim": exposure_mapping_claim,
        "exposure_uncertainty": (
            None
            if exposure_uncertainty is None
            else exposure_uncertainty.model_dump(mode="json")
        ),
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _legacy_interference_authority(
    source_status: InterferenceStructureSourceStatus,
    analysis_status: InterferenceStructureAnalysisStatus,
) -> InterferenceStructureAuthority:
    if analysis_status in {"UNRESOLVED", "REJECTED"}:
        return "PROPOSED"
    if source_status == "SYNTHETIC_GROUND_TRUTH":
        return "TRUSTED_FIXTURE"
    return "HUMAN_CONFIRMED"


class InterferenceStructureReceipt(StrictModel):
    """Compact I1->I2 qualification/provenance receipt.

    ``source_status`` says where the structure came from. ``analysis_status`` says
    whether the current analysis accepts it as a working assumption, retains a
    set-valued uncertainty statement, or leaves/rejects it. Neither field claims
    to prove the true causal structure.
    """

    contract_version: Literal["interference-structure-v2"] = "interference-structure-v2"
    provider_id: str
    source_status: InterferenceStructureSourceStatus
    analysis_status: InterferenceStructureAnalysisStatus
    semantic_fingerprint: str
    provenance: dict[str, str] = Field(default_factory=dict)
    qualification_evidence: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_receipt(self):
        if not self.provider_id.strip():
            raise ValueError("provider_id must be nonempty")
        if len(self.semantic_fingerprint) != 64 or any(
            ch not in "0123456789abcdef" for ch in self.semantic_fingerprint
        ):
            raise ValueError("semantic_fingerprint must be a lowercase SHA-256 hex digest")
        return self

    def executable(self) -> bool:
        return (
            self.analysis_status in {"ACCEPTED_AS_ASSUMPTION", "SET_VALUED"}
            and any(item.strip() for item in self.qualification_evidence)
        )

    @property
    def authority(self) -> InterferenceStructureAuthority:
        """v0.2.11 compatibility view; do not interpret as structure truth."""
        return _legacy_interference_authority(self.source_status, self.analysis_status)


class InterferenceStructureOutput(StrictModel):
    """Typed I1 structure-qualification output consumed by population I2.

    I1 records the supplied network/exposure semantics, their source, how they are
    admitted to the current analysis, explicit uncertainty, and provenance. It does
    *not* certify that a discovered graph/mapping is the unique true causal structure
    and it does not decide POINT/PARTIAL status.
    """

    contract_version: Literal["interference-structure-v2"] = "interference-structure-v2"
    provider_id: str
    source_status: InterferenceStructureSourceStatus
    analysis_status: InterferenceStructureAnalysisStatus
    network_exposure: NetworkStructureSpec
    exposure_mapping_claim: ExposureMappingClaim
    exposure_uncertainty: ExposureUncertaintySpec | None = None
    provenance: dict[str, str] = Field(default_factory=dict)
    qualification_evidence: list[str] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def validate_provider_output(self):
        if not self.provider_id.strip():
            raise ValueError("provider_id must be nonempty")
        if isinstance(self.exposure_uncertainty, ExposurePropensityRatioSensitivitySpec):
            if not isinstance(self.network_exposure, ThresholdNetworkExposureSpec):
                raise ValueError(
                    "exposure-propensity uncertainty requires ThresholdNetworkExposureSpec"
                )
        if isinstance(self.exposure_uncertainty, FiniteExposureCandidateSetSpec):
            if not isinstance(self.network_exposure, FiniteCategoricalNetworkExposureSpec):
                raise ValueError(
                    "finite exposure candidate uncertainty requires FiniteCategoricalNetworkExposureSpec"
                )
            for candidate in self.exposure_uncertainty.candidates:
                self.network_exposure.validate_candidate_mapping(candidate)
        if self.exposure_mapping_claim == "ASSERTED_SUFFICIENT" and self.exposure_uncertainty is not None:
            raise ValueError(
                "ASSERTED_SUFFICIENT exposure mapping cannot simultaneously carry uncertainty"
            )
        if self.exposure_mapping_claim == "REFERENCE_WITH_UNCERTAINTY" and self.exposure_uncertainty is None:
            raise ValueError(
                "REFERENCE_WITH_UNCERTAINTY requires an explicit exposure_uncertainty object"
            )
        if self.exposure_mapping_claim == "UNSPECIFIED" and self.exposure_uncertainty is not None:
            raise ValueError(
                "UNSPECIFIED exposure-mapping claim cannot carry executable uncertainty semantics"
            )
        if self.analysis_status == "SET_VALUED" and self.exposure_mapping_claim != "REFERENCE_WITH_UNCERTAINTY":
            raise ValueError(
                "SET_VALUED analysis status requires REFERENCE_WITH_UNCERTAINTY exposure semantics in v2"
            )
        if self.analysis_status == "ACCEPTED_AS_ASSUMPTION" and self.exposure_mapping_claim == "REFERENCE_WITH_UNCERTAINTY":
            raise ValueError(
                "REFERENCE_WITH_UNCERTAINTY must enter I2 as SET_VALUED rather than a single accepted mapping"
            )
        if self.analysis_status in {"ACCEPTED_AS_ASSUMPTION", "SET_VALUED"} and not any(
            item.strip() for item in self.qualification_evidence
        ):
            raise ValueError(
                "executable I1 qualification requires nonempty qualification_evidence"
            )
        return self

    def executable(self) -> bool:
        """Whether the structure statement is admissible to current I2 analysis."""
        return self.analysis_status in {"ACCEPTED_AS_ASSUMPTION", "SET_VALUED"}

    @property
    def authority(self) -> InterferenceStructureAuthority:
        """v0.2.11 compatibility view; not a claim that the structure is true."""
        return _legacy_interference_authority(self.source_status, self.analysis_status)

    def semantic_fingerprint(self) -> str:
        """Stable fingerprint of structural semantics, excluding qualification metadata."""
        return interference_structure_semantic_fingerprint(
            self.network_exposure,
            self.exposure_uncertainty,
            self.exposure_mapping_claim,
        )

    def receipt(self) -> InterferenceStructureReceipt:
        return InterferenceStructureReceipt(
            provider_id=self.provider_id,
            source_status=self.source_status,
            analysis_status=self.analysis_status,
            semantic_fingerprint=self.semantic_fingerprint(),
            provenance=dict(self.provenance),
            qualification_evidence=list(self.qualification_evidence),
        )


class InformationObject(StrictModel):
    name: str
    regime: Literal["experimental", "observational"]
    variables: list[str]
    description: str = ""
    # Optional typed semantics used by newer identification families. Legacy
    # objects may leave these unset; theorem-specific gates must require them.
    basis: Literal[
        "NODE_CONTEXT_WORKING_EXPOSURE_BINARY_MEAN_V1",
        "WHOLE_NETWORK_ASSIGNMENT_LAW_V1",
    ] | None = None
    joint_scope: Literal["node_local_marginals_only", "whole_network_assignment"] | None = None
    outcome_representation: Literal["binary_mean_complete", "full_joint_law"] | None = None
    whole_network_assignment_law_available: bool | None = None


class InformationSignature(StrictModel):
    objects: list[InformationObject]

    def contains_joint(self, treatment: str, outcome: str, regime: str) -> bool:
        wanted = {treatment, outcome}
        return any(
            obj.regime == regime and wanted.issubset(set(obj.variables))
            for obj in self.objects
        )

    def contains_variables(self, variables: list[str], regime: str) -> bool:
        wanted = set(variables)
        return any(
            obj.regime == regime and wanted.issubset(set(obj.variables))
            for obj in self.objects
        )



class DeterministicBinaryNetworkPolicyOracleSpec(StrictModel):
    """Theory/Oracle-only formal policy object for the finite mixture-ID family."""

    policy_id: str
    context_ids: list[str]
    node_ids: list[str]
    actions_by_context: dict[str, list[int]]

    @model_validator(mode="after")
    def validate_policy(self):
        if not self.policy_id.strip():
            raise ValueError("policy_id must be nonempty")
        if not self.context_ids or len(set(self.context_ids)) != len(self.context_ids):
            raise ValueError("policy context_ids must be nonempty and unique")
        if not self.node_ids or len(set(self.node_ids)) != len(self.node_ids):
            raise ValueError("policy node_ids must be nonempty and unique")
        if set(self.actions_by_context) != set(self.context_ids):
            raise ValueError("actions_by_context must contain exactly the declared context_ids")
        for context_id in self.context_ids:
            actions = self.actions_by_context[context_id]
            if len(actions) != len(self.node_ids):
                raise ValueError("every policy action vector must match node_ids length")
            if any(action not in {0, 1} for action in actions):
                raise ValueError("deterministic network policy actions must be binary")
        return self

    def semantic_fingerprint(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class IndependentBernoulliDesignV1(StrictModel):
    kind: Literal["iid_bernoulli_binary_v1"] = "iid_bernoulli_binary_v1"
    p: float | str

    @model_validator(mode="after")
    def validate_finite_probability(self):
        from .rational_arithmetic import fraction
        if not 0 < fraction(self.p) < 1:
            raise ValueError("Bernoulli probability must lie strictly between zero and one")
        return self


class NodeContextWorkingExposureBinaryMeanInfoV1(StrictModel):
    basis: Literal["NODE_CONTEXT_WORKING_EXPOSURE_BINARY_MEAN_V1"] = (
        "NODE_CONTEXT_WORKING_EXPOSURE_BINARY_MEAN_V1"
    )
    regime: Literal["experimental"] = "experimental"
    joint_scope: Literal["node_local_marginals_only"] = "node_local_marginals_only"
    outcome_representation: Literal["binary_mean_complete"] = "binary_mean_complete"
    whole_network_assignment_law_available: Literal[False] = False


class NetworkPolicyMixtureTheoremContractV1(StrictModel):
    """Typed validity domain for the first exact finite-mixture policy-value theorem."""

    contract_version: Literal["network-policy-mixture-theorem-v1"] = (
        "network-policy-mixture-theorem-v1"
    )
    outcome_semantics: Literal["binary"] = "binary"
    population_information_scope: Literal[
        "node_context_binary_outcome_marginals_v1"
    ] = "node_context_binary_outcome_marginals_v1"
    cross_block_response_constraints: Literal[
        "none_beyond_declared_local_marginals",
        "declared_cross_block_restrictions",
    ] = "none_beyond_declared_local_marginals"
    conditional_coupling_semantics: Literal[
        "arbitrary_coupling_allowed"
    ] = "arbitrary_coupling_allowed"
    candidate_structure_scope: Literal[
        "one_global_theta_shared_across_all_nodes_and_contexts"
    ] = "one_global_theta_shared_across_all_nodes_and_contexts"


class NetworkPolicyMixturePopulationFactsV1(StrictModel):
    """Trusted population realization ``o`` for the numeric Theory/Benchmark oracle.

    These are exact population objects, not finite-sample plug-in estimates.  The
    nested outcome table is context -> node -> own treatment ("0"/"1") ->
    working-exposure state -> P(Y=1 | cell).
    """

    contract_version: Literal["network-policy-mixture-population-v1"] = (
        "network-policy-mixture-population-v1"
    )
    source_type: Literal[
        "THEORY_DECLARED",
        "SYNTHETIC_GROUND_TRUTH",
        "EXTERNALLY_CERTIFIED_POPULATION_FACT",
        "FINITE_SAMPLE_ESTIMATE",
    ] = "THEORY_DECLARED"
    analysis_status: Literal["UNRESOLVED", "ACCEPTED_AS_POPULATION_FACT"] = "UNRESOLVED"
    evidence: list[str] = Field(default_factory=list)
    context_weights: dict[str, float]
    outcome_means: dict[str, dict[str, dict[str, dict[str, float]]]]

    @model_validator(mode="after")
    def validate_population_facts(self):
        if not self.context_weights:
            raise ValueError("context_weights must be nonempty")
        normalized_weights: dict[str, float] = {}
        total = 0.0
        for context_id, weight in self.context_weights.items():
            if not context_id.strip():
                raise ValueError("population-fact context ids must be nonempty")
            value = float(weight)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError("context weights must be finite and nonnegative")
            normalized_weights[context_id] = value
            total += value
        if abs(total - 1.0) > 1e-10:
            raise ValueError("context weights must sum to one")
        self.context_weights = normalized_weights

        if set(self.outcome_means) != set(self.context_weights):
            raise ValueError("outcome_means must contain exactly the context-weight ids")
        for context_id, node_table in self.outcome_means.items():
            if not node_table:
                raise ValueError("each population context must contain at least one node")
            for node_id, treatment_table in node_table.items():
                if not node_id.strip():
                    raise ValueError("population-fact node ids must be nonempty")
                if set(treatment_table) != {"0", "1"}:
                    raise ValueError("binary treatment population facts require keys '0' and '1'")
                for working_state_table in treatment_table.values():
                    if not working_state_table:
                        raise ValueError("each treatment cell must contain working exposure states")
                    for working_state, probability in working_state_table.items():
                        if not working_state.strip():
                            raise ValueError("working exposure state labels must be nonempty")
                        value = float(probability)
                        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                            raise ValueError("binary outcome population probabilities must lie in [0, 1]")

        if self.analysis_status == "ACCEPTED_AS_POPULATION_FACT":
            if self.source_type == "FINITE_SAMPLE_ESTIMATE":
                raise ValueError(
                    "a finite-sample estimate cannot be promoted to exact population truth"
                )
            if not any(item.strip() for item in self.evidence):
                raise ValueError("accepted population facts require nonempty evidence/provenance")
        return self

    def usable_for_numeric_oracle(self) -> bool:
        return self.analysis_status == "ACCEPTED_AS_POPULATION_FACT"


class NetworkPolicyBinaryMeanPopulationTruthV1(StrictModel):
    """Exact population o, not an empirical table. Strings such as '1/3' are exact.

    JSON numbers mean their decimal spelling, not hidden infinite precision.
    In particular context weights must sum to one exactly; no normalization or
    empirical-to-population promotion is performed here.
    """
    contract_version: Literal["network-policy-binary-mean-population-v1"] = "network-policy-binary-mean-population-v1"
    authority: Literal["TRUSTED_POPULATION_TRUTH"] = "TRUSTED_POPULATION_TRUTH"
    evidence: list[str]
    context_weights: dict[str, float | str]
    conditional_means: dict[str, dict[str, dict[str, dict[str, float | str]]]]

    @model_validator(mode="after")
    def validate_truth(self):
        from .rational_arithmetic import fraction
        if not any(item.strip() for item in self.evidence):
            raise ValueError("trusted population truth requires nonempty provenance/evidence")
        if not self.context_weights or any(not k.strip() for k in self.context_weights):
            raise ValueError("context_weights must have nonempty context ids")
        weights = [fraction(v) for v in self.context_weights.values()]
        if any(v <= 0 for v in weights) or sum(weights) != 1:
            raise ValueError("context weights must be positive and sum to one exactly; use rational strings")
        if set(self.conditional_means) != set(self.context_weights):
            raise ValueError("conditional_means must contain exactly the context-weight ids")
        for nodes in self.conditional_means.values():
            if not nodes:
                raise ValueError("each population context must contain at least one node")
            for node, arms in nodes.items():
                if not node.strip() or set(arms) != {"0", "1"}:
                    raise ValueError("binary population truth requires node ids and treatment keys '0'/'1'")
                for states in arms.values():
                    if not states:
                        raise ValueError("working exposure states cannot be empty")
                    for state, mean in states.items():
                        if not state.strip() or not 0 <= fraction(mean) <= 1:
                            raise ValueError("binary outcome means must lie in [0,1]")
        return self

    def semantic_fingerprint(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ClosedIntervalV1(StrictModel):
    lower: float
    upper: float

    @model_validator(mode="after")
    def validate_interval(self):
        self.lower = float(self.lower)
        self.upper = float(self.upper)
        if not math.isfinite(self.lower) or not math.isfinite(self.upper):
            raise ValueError("finite-union v1 interval endpoints must be finite")
        if self.lower > self.upper:
            raise ValueError("interval lower endpoint cannot exceed upper endpoint")
        return self


class FiniteUnionClosedIntervalsV1(StrictModel):
    """Canonical exact identified set; the hull is derived convenience only."""

    representation: Literal["FINITE_UNION_CLOSED_INTERVALS_V1"] = (
        "FINITE_UNION_CLOSED_INTERVALS_V1"
    )
    components: list[ClosedIntervalV1]
    interval_hull: ClosedIntervalV1 | None = None
    is_connected: bool = False

    @model_validator(mode="after")
    def canonicalize_components(self):
        if not self.components:
            raise ValueError("finite union must contain at least one closed interval")
        ordered = sorted(self.components, key=lambda interval: (interval.lower, interval.upper))
        merged: list[ClosedIntervalV1] = []
        for interval in ordered:
            if not merged or interval.lower > merged[-1].upper:
                merged.append(ClosedIntervalV1(lower=interval.lower, upper=interval.upper))
            else:
                merged[-1].upper = max(merged[-1].upper, interval.upper)
        self.components = merged
        self.interval_hull = ClosedIntervalV1(
            lower=merged[0].lower,
            upper=merged[-1].upper,
        )
        self.is_connected = len(merged) == 1
        return self

    def is_singleton(self) -> bool:
        return (
            len(self.components) == 1
            and self.components[0].lower == self.components[0].upper
        )


CanonicalProblemVersionV1 = Literal["network-policy-mixture-lp-v1"]
CertificateSide = Literal["LOWER", "UPPER"]


class RowSpacePointCertificateV1(StrictModel):
    certificate_type: Literal["ROW_SPACE_POINT_V1"] = "ROW_SPACE_POINT_V1"
    candidate_id: str
    canonical_problem_version: CanonicalProblemVersionV1 = "network-policy-mixture-lp-v1"
    matrix_fingerprint: str
    rhs_fingerprint: str
    query_fingerprint: str
    variable_order_fingerprint: str
    feasible_witness_z: list[float]
    alpha: list[float]
    identified_value: float
    exact_feasible_z: list[str] | None = None
    exact_alpha: list[str] | None = None
    exact_value: str | None = None


class LPPrimalWitnessV1(StrictModel):
    certificate_type: Literal["LP_PRIMAL_WITNESS_V1"] = "LP_PRIMAL_WITNESS_V1"
    side: CertificateSide
    candidate_id: str
    canonical_problem_version: CanonicalProblemVersionV1 = "network-policy-mixture-lp-v1"
    matrix_fingerprint: str
    rhs_fingerprint: str
    query_fingerprint: str
    variable_order_fingerprint: str
    z: list[float]
    objective_value: float
    exact_z: list[str] | None = None
    exact_objective: str | None = None


class LPDualWitnessV1(StrictModel):
    certificate_type: Literal["LP_DUAL_WITNESS_V1"] = "LP_DUAL_WITNESS_V1"
    side: CertificateSide
    candidate_id: str
    canonical_problem_version: CanonicalProblemVersionV1 = "network-policy-mixture-lp-v1"
    matrix_fingerprint: str
    rhs_fingerprint: str
    query_fingerprint: str
    variable_order_fingerprint: str
    y: list[float]
    objective_value: float
    exact_y: list[str] | None = None
    exact_objective: str | None = None


class FarkasIncompatibilityCertificateV1(StrictModel):
    certificate_type: Literal["FARKAS_INCOMPATIBLE_V1"] = "FARKAS_INCOMPATIBLE_V1"
    candidate_id: str
    canonical_problem_version: CanonicalProblemVersionV1 = "network-policy-mixture-lp-v1"
    matrix_fingerprint: str
    rhs_fingerprint: str
    query_fingerprint: str
    variable_order_fingerprint: str
    y: list[float]
    exact_y: list[str] | None = None
    normalization: Literal["b_dot_y_equals_minus_one"] = "b_dot_y_equals_minus_one"


class CandidateMixtureIdentificationCertificateV1(StrictModel):
    candidate_id: str
    status: Literal["POINT", "PARTIAL", "INCOMPATIBLE"]
    raw_interval: ClosedIntervalV1 | None = None
    row_space_point: RowSpacePointCertificateV1 | None = None
    lower_primal: LPPrimalWitnessV1 | None = None
    lower_dual: LPDualWitnessV1 | None = None
    upper_primal: LPPrimalWitnessV1 | None = None
    upper_dual: LPDualWitnessV1 | None = None
    farkas: FarkasIncompatibilityCertificateV1 | None = None

    @model_validator(mode="after")
    def validate_status_payload(self):
        if self.status == "INCOMPATIBLE":
            if self.raw_interval is not None or self.farkas is None:
                raise ValueError("INCOMPATIBLE candidate requires Farkas and no interval")
            return self
        if self.raw_interval is None:
            raise ValueError("compatible candidate requires a raw identified interval")
        if self.status == "POINT" and self.raw_interval.lower != self.raw_interval.upper:
            raise ValueError("POINT candidate interval must be a singleton")
        if self.status == "PARTIAL" and self.raw_interval.lower >= self.raw_interval.upper:
            raise ValueError("PARTIAL candidate interval must have positive width")
        endpoint_witnesses = [self.lower_primal, self.lower_dual, self.upper_primal, self.upper_dual]
        if self.status == "PARTIAL" and any(item is None for item in endpoint_witnesses):
            raise ValueError("PARTIAL candidate requires lower/upper primal and dual witnesses")
        if self.status == "POINT":
            has_lp_proof = all(item is not None for item in endpoint_witnesses)
            if self.row_space_point is None and not has_lp_proof:
                raise ValueError(
                    "POINT candidate requires either a row-space certificate or lower/upper primal-dual witnesses"
                )
        return self


class NetworkPolicyMixtureProofBundleV1(StrictModel):
    contract_version: Literal["network-policy-mixture-proof-v1"] = "network-policy-mixture-proof-v1"
    theorem_rule_id: Literal["NETWORK_POLICY_FINITE_MIXTURE_ID_V1"] = (
        "NETWORK_POLICY_FINITE_MIXTURE_ID_V1"
    )
    canonical_problem_version: CanonicalProblemVersionV1 = "network-policy-mixture-lp-v1"
    ambiguity_semantics: Literal["FINITE_EXACT_STRUCTURAL_FAMILY"] = "FINITE_EXACT_STRUCTURAL_FAMILY"
    information_basis: Literal["NODE_CONTEXT_WORKING_EXPOSURE_BINARY_MEAN_V1"] = (
        "NODE_CONTEXT_WORKING_EXPOSURE_BINARY_MEAN_V1"
    )
    numeric_policy_version: str = "p1-numeric-v1"
    # Authoritative endpoints; the old float finite union is display-only.
    exact_components_rational: list[tuple[str, str]] | None = None
    policy_fingerprint: str
    spec_fingerprint: str | None = None
    population_truth_fingerprint: str | None = None
    working_mapping_fingerprint: str | None = None
    candidate_set_fingerprint: str | None = None
    exact_set_fingerprint: str | None = None
    sharpness_scope: Literal["EXACT_IDENTIFIED_SET", "EMPTY_FIBER_CERTIFIED"] = "EXACT_IDENTIFIED_SET"
    candidate_results: list[CandidateMixtureIdentificationCertificateV1]
    exact_identified_set: FiniteUnionClosedIntervalsV1 | None = None

    @model_validator(mode="after")
    def validate_bundle(self):
        if not self.candidate_results:
            raise ValueError("proof bundle must contain at least one candidate result")
        candidate_ids = [item.candidate_id for item in self.candidate_results]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("proof-bundle candidate ids must be unique")
        compatible = [item for item in self.candidate_results if item.status != "INCOMPATIBLE"]
        if compatible and self.exact_identified_set is None:
            raise ValueError("compatible proof bundle requires an exact identified set")
        if not compatible and self.exact_identified_set is not None:
            raise ValueError("all-incompatible proof bundle must not contain an identified set")
        return self


class NetworkPolicyFiniteMixtureSetProgram(StrictModel):
    kind: Literal["network_policy_finite_mixture_set_v1"] = "network_policy_finite_mixture_set_v1"
    contract_version: Literal["network-policy-mixture-program-v1"] = (
        "network-policy-mixture-program-v1"
    )
    treatment: str
    outcome: str
    network_id: str
    working_mapping_id: str
    candidate_mapping_ids: list[str]
    policy_id: str
    outcome_semantics: Literal["binary"] = "binary"
    aggregation: Literal["node_average_then_context_expectation"] = (
        "node_average_then_context_expectation"
    )
    canonical_problem_version: CanonicalProblemVersionV1 = "network-policy-mixture-lp-v1"

    @model_validator(mode="after")
    def validate_program(self):
        if not self.candidate_mapping_ids or len(set(self.candidate_mapping_ids)) != len(
            self.candidate_mapping_ids
        ):
            raise ValueError("candidate_mapping_ids must be nonempty and unique")
        return self

    def to_text(self) -> str:
        return (
            "Gamma_pi(o) = union_theta { q_theta^T z : "
            "A_theta z = b, z >= 0 } over compatible finite exposure candidates"
        )

    def required_population_objects(self) -> list[str]:
        return ["P_exp(W)", f"P({self.outcome}_i=1 | W,{self.treatment}_i,C_i,A)"]


SetProgram = NetworkPolicyFiniteMixtureSetProgram


class MajorityResponseTheoremContractV1(StrictModel):
    """Symbolic identification: no population values or empirical estimates are supplied."""
    version: Literal["majority-response-theorem-v1"] = "majority-response-theorem-v1"
    design: IndependentBernoulliDesignV1
    context_semantics: Literal["condition_on_full_pretreatment_network_context"] = "condition_on_full_pretreatment_network_context"
    grouping: Literal["strict_majority_ties_low"] = "strict_majority_ties_low"
    target: Literal["design_averaged_local_stochastic_response"] = "design_averaged_local_stochastic_response"
    information: Literal["node_conditional_majority_outcome_means"] = "node_conditional_majority_outcome_means"


class IdentificationSpec(StrictModel):
    causal_semantics: Literal["potential_outcomes"] = "potential_outcomes"
    structure: StructureSpec
    network_exposure: NetworkStructureSpec | None = None
    exposure_mapping_claim: ExposureMappingClaim | None = None
    exposure_uncertainty: ExposureUncertaintySpec | None = None
    interference_structure_receipt: InterferenceStructureReceipt | None = None
    reference_exposure_propensity_upper_bound_fact: ReferenceExposurePropensityUpperBoundFact | None = None
    majority_response_theorem_contract: MajorityResponseTheoremContractV1 | None = None
    network_policy_mixture_theorem_contract: NetworkPolicyMixtureTheoremContractV1 | None = None
    network_policy_mixture_assignment_design: IndependentBernoulliDesignV1 | None = None
    network_policy_mixture_information_contract: NodeContextWorkingExposureBinaryMeanInfoV1 | None = None
    # Legacy Phase-A field retained for backward compatibility only. New numeric
    # oracle code receives population truth as a separate argument.
    network_policy_mixture_population_facts: NetworkPolicyMixturePopulationFactsV1 | None = None
    deterministic_policy_oracle: DeterministicBinaryNetworkPolicyOracleSpec | None = None
    variable_domains: dict[str, VariableDomain]
    assumptions: list[Assumption]
    assumption_conflicts: list[AssumptionConflict] = Field(default_factory=list)
    information_signature: InformationSignature
    query: QuerySpec
    support_domain: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_network_uncertainty_alignment(self):
        if self.majority_response_theorem_contract is not None and self.query.type not in {"NETWORK_RESPONSE_SURFACE", "NETWORK_MAJORITY_RESPONSE_POLICY_SCORE"}:
            raise ValueError("majority response theorem contract requires a response or majority-score query")
        if isinstance(self.exposure_uncertainty, ExposurePropensityRatioSensitivitySpec):
            if not isinstance(self.network_exposure, ThresholdNetworkExposureSpec):
                raise ValueError(
                    "exposure-propensity uncertainty requires ThresholdNetworkExposureSpec"
                )
        if isinstance(self.exposure_uncertainty, FiniteExposureCandidateSetSpec):
            if not isinstance(self.network_exposure, FiniteCategoricalNetworkExposureSpec):
                raise ValueError(
                    "finite exposure candidate uncertainty requires FiniteCategoricalNetworkExposureSpec"
                )
            for candidate in self.exposure_uncertainty.candidates:
                self.network_exposure.validate_candidate_mapping(candidate)

        mixture_any_fields = [
            self.network_policy_mixture_theorem_contract,
            self.network_policy_mixture_assignment_design,
            self.network_policy_mixture_information_contract,
            self.network_policy_mixture_population_facts,
            self.deterministic_policy_oracle,
        ]
        if any(item is not None for item in mixture_any_fields):
            new_contract_complete = all(
                item is not None
                for item in [
                    self.network_policy_mixture_theorem_contract,
                    self.network_policy_mixture_assignment_design,
                    self.network_policy_mixture_information_contract,
                    self.deterministic_policy_oracle,
                ]
            )
            legacy_phase_a_complete = (
                self.network_policy_mixture_theorem_contract is not None
                and self.network_policy_mixture_population_facts is not None
                and self.deterministic_policy_oracle is not None
                and self.network_policy_mixture_assignment_design is None
                and self.network_policy_mixture_information_contract is None
            )
            if not (new_contract_complete or legacy_phase_a_complete):
                raise ValueError(
                    "network-policy mixture theorem fields must be supplied together: either the frozen typed design/information contract plus deterministic policy, or the legacy Phase-A theorem/population-facts/policy trio"
                )
            if self.query.type != "POLICY_VALUE":
                raise ValueError("network-policy mixture theorem is only valid for POLICY_VALUE")
            if not isinstance(self.network_exposure, FiniteCategoricalNetworkExposureSpec):
                raise ValueError(
                    "network-policy mixture theorem requires FiniteCategoricalNetworkExposureSpec"
                )
            if not isinstance(self.exposure_uncertainty, FiniteExposureCandidateSetSpec):
                raise ValueError(
                    "network-policy mixture theorem requires a finite exposure candidate set"
                )
            policy = self.deterministic_policy_oracle
            facts = self.network_policy_mixture_population_facts
            assert policy is not None
            info_contract = self.network_policy_mixture_information_contract
            if info_contract is not None and info_contract.whole_network_assignment_law_available:
                raise ValueError(
                    "local mixture theorem cannot be the final route when whole-network assignment law is declared available"
                )
            if policy.node_ids != self.network_exposure.node_ids:
                raise ValueError("mixture-oracle policy node_ids must match network node_ids exactly")
            expected_contexts = self.network_exposure.working_mapping.context_ids
            if policy.context_ids != expected_contexts:
                raise ValueError("mixture-oracle policy context_ids must match working mapping order")
            if facts is not None:
                if set(facts.context_weights) != set(expected_contexts):
                    raise ValueError("population-fact contexts must match the working exposure contexts")
                if set(facts.outcome_means) != set(expected_contexts):
                    raise ValueError("population outcome contexts must match the working exposure contexts")
                for context_id in expected_contexts:
                    node_table = facts.outcome_means[context_id]
                    if set(node_table) != set(self.network_exposure.node_ids):
                        raise ValueError(
                            "population facts must contain exactly the network nodes in every context"
                        )
                    working_node_maps = self.network_exposure.working_mapping.state_by_local_assignment[context_id]
                    for node_id in self.network_exposure.node_ids:
                        reachable_states = set(working_node_maps[node_id].values())
                        for treatment_value in ("0", "1"):
                            if set(node_table[node_id][treatment_value]) != reachable_states:
                                raise ValueError(
                                    "population facts must contain exactly the reachable working exposure states"
                                )

        if self.interference_structure_receipt is not None:
            if self.network_exposure is None:
                raise ValueError(
                    "interference_structure_receipt requires a typed network_exposure"
                )
            if self.exposure_mapping_claim is None:
                raise ValueError(
                    "interference_structure_receipt requires exposure_mapping_claim"
                )
            expected = interference_structure_semantic_fingerprint(
                self.network_exposure,
                self.exposure_uncertainty,
                self.exposure_mapping_claim,
            )
            if self.interference_structure_receipt.semantic_fingerprint != expected:
                raise ValueError(
                    "interference_structure_receipt does not match network/exposure semantics"
                )
        return self

    def confirmed_assumptions(self) -> set[str]:
        return {a.name for a in self.assumptions if a.confirmed}

    def domain(self, variable: str) -> VariableDomain | None:
        return self.variable_domains.get(variable)


class ConditionalMean(StrictModel):
    kind: Literal["conditional_mean"] = "conditional_mean"
    outcome: str
    treatment: str
    treatment_value: int

    def to_text(self) -> str:
        return f"E[{self.outcome} | {self.treatment}={self.treatment_value}]"

    def required_population_objects(self) -> list[str]:
        return [self.to_text()]


class DifferenceFunctional(StrictModel):
    kind: Literal["difference"] = "difference"
    left: ConditionalMean
    right: ConditionalMean

    def to_text(self) -> str:
        return f"{self.left.to_text()} - {self.right.to_text()}"

    def required_population_objects(self) -> list[str]:
        return self.left.required_population_objects() + self.right.required_population_objects()


class NetworkPolicyValueProgram(StrictModel):
    """Population point-ID program for a deterministic policy under local network interference."""

    kind: Literal["network_policy_value"] = "network_policy_value"
    treatment: str
    outcome: str
    network_id: str
    exposure_mapping: Literal["treated_neighbor_count_1hop"] = "treated_neighbor_count_1hop"
    policy_symbol: str = "pi"
    aggregation: Literal["node_average_then_context_expectation"] = "node_average_then_context_expectation"
    target_context_distribution: Literal["experimental_regime"] = "experimental_regime"

    def to_text(self) -> str:
        return (
            f"V({self.policy_symbol}) = E_{{W~P_exp}}[1/N * sum_i mu_i("
            f"{self.policy_symbol}_i(W), K_i({self.policy_symbol}(W)); W,A)]"
        )

    def required_population_objects(self) -> list[str]:
        t, y = self.treatment, self.outcome
        return [
            f"mu_i(a,k,W,A)=E[{y}_i | W,A,{t}_i=a,K_i=k]",
            "P_exp(W)",
        ]


class NetworkDirectEffectPointProgram(StrictModel):
    """Point-ID program for the same true-exposure target used by the partial member.

    Point identification follows only after the theorem assumptions assert that the
    true sufficient exposure mapping equals the employed/reference mapping.
    """

    kind: Literal["network_direct_effect_point"] = "network_direct_effect_point"
    treatment: str
    outcome: str
    network_id: str
    reference_exposure_mapping: Literal["treated_neighbor_share_threshold_1hop"] = (
        "treated_neighbor_share_threshold_1hop"
    )
    target_exposure_semantics: Literal["true_sufficient_exposure_state"] = (
        "true_sufficient_exposure_state"
    )
    exposure_value: Literal[0, 1]
    target_context_distribution: Literal["observational_regime"] = "observational_regime"

    def to_text(self) -> str:
        t, y, z = self.treatment, self.outcome, self.exposure_value
        return (
            f"ADE(z={z}) = E_{{X~P_obs}}[E[{y}|{t}=1,Z={z},X] - "
            f"E[{y}|{t}=0,Z={z},X]]"
        )

    def required_population_objects(self) -> list[str]:
        t, y, z = self.treatment, self.outcome, self.exposure_value
        return [
            f"E[{y}|{t}=1,Z={z},X]",
            f"E[{y}|{t}=0,Z={z},X]",
            "P_obs(X)",
        ]


class NetworkMajorityResponseProgram(StrictModel):
    kind: Literal["network_majority_design_averaged_response"] = "network_majority_design_averaged_response"
    treatment: str
    outcome: str
    target_fingerprint: str
    network_fingerprint: str
    assignment_probability_rational: str
    tensor_axes: tuple[Literal["node"], Literal["treatment"], Literal["majority_arm"]] = ("node", "treatment", "majority_arm")
    arm_coordinates: tuple[tuple[int, int], ...] = ((0, 0), (0, 1), (1, 0), (1, 1))
    functional: Literal["mu_bar_i(a,s;W,G)=E_exp[Y_i|T_i=a,S_i=s,W,G]"] = "mu_bar_i(a,s;W,G)=E_exp[Y_i|T_i=a,S_i=s,W,G]"
    context: Literal["full_pretreatment_network_context"] = "full_pretreatment_network_context"
    grouping: Literal["K_i>floor(degree_i/2);ties=0"] = "K_i>floor(degree_i/2);ties=0"
    semantics: Literal["design_averaged_local_stochastic_response_not_fixed_assignment"] = "design_averaged_local_stochastic_response_not_fixed_assignment"

    def to_text(self) -> str:
        return self.functional


class MajorityScorePolicyClassV1(StrictModel):
    """A compact, predeclared allocation class; not an optimizer or its answer."""
    version: Literal["majority-score-policy-class-v1"] = "majority-score-policy-class-v1"
    node_ids: list[str]
    budget: StrictInt = Field(ge=0)
    budget_mode: Literal["exact", "at_most"]
    action_space: Literal["binary_node_allocation"] = "binary_node_allocation"
    scope: Literal["all_budget_feasible_allocations"] = "all_budget_feasible_allocations"

    @model_validator(mode="after")
    def validate_class(self):
        if (not self.node_ids or len(set(self.node_ids)) != len(self.node_ids)
            or any(not n.strip() for n in self.node_ids) or self.budget > len(self.node_ids)):
            raise ValueError("INVALID_MAJORITY_SCORE_POLICY_CLASS")
        return self


class NetworkMajorityPolicyScoreProgram(StrictModel):
    kind: Literal["network_majority_response_policy_score"] = "network_majority_response_policy_score"
    treatment: str
    outcome: str
    target_fingerprint: str
    response_program: NetworkMajorityResponseProgram
    policy_class: MajorityScorePolicyClassV1
    functional: Literal["Q_maj(z;W,G)=sum_i mu_bar_i(z_i,S_i(z);W,G)/N"] = "Q_maj(z;W,G)=sum_i mu_bar_i(z_i,S_i(z);W,G)/N"
    identification_scope: Literal["each_allocation_score_in_declared_class_not_unique_argmax"] = "each_allocation_score_in_declared_class_not_unique_argmax"
    aggregation: Literal["uniform_node_average"] = "uniform_node_average"
    semantics: Literal["design_averaged_majority_response_score_not_rollout_welfare"] = "design_averaged_majority_response_score_not_rollout_welfare"

    def to_text(self) -> str:
        return self.functional


PointProgram = Union[NetworkMajorityPolicyScoreProgram, NetworkMajorityResponseProgram, DifferenceFunctional, NetworkPolicyValueProgram, NetworkDirectEffectPointProgram]


class ManskiBinaryATEBoundsProgram(StrictModel):
    """Population sharp ATE bounds for binary T/Y using observational P(T,Y)."""

    kind: Literal["manski_binary_ate_bounds"] = "manski_binary_ate_bounds"
    treatment: str
    outcome: str

    def to_text(self) -> str:
        t, y = self.treatment, self.outcome
        return (
            f"[-P({y}=0,{t}=1)-P({y}=1,{t}=0), "
            f"P({y}=1,{t}=1)+P({y}=0,{t}=0)]"
        )

    def required_population_objects(self) -> list[str]:
        t, y = self.treatment, self.outcome
        return [
            f"P({y}=0,{t}=0)",
            f"P({y}=1,{t}=0)",
            f"P({y}=0,{t}=1)",
            f"P({y}=1,{t}=1)",
        ]


class OneArmATEBoundsProgram(StrictModel):
    """Sharp one-arm ATE bounds under known outcome support restrictions.

    Either support endpoint may be unknown. A missing lower/upper support bound
    yields a half-infinite identified set; both missing means this program is
    not applicable and the ATE is unrestricted by outcome support.
    """

    kind: Literal["one_arm_ate_bounds"] = "one_arm_ate_bounds"
    treatment: str
    outcome: str
    observed_treatment_value: Literal[0, 1]
    outcome_lower: float | None = None
    outcome_upper: float | None = None

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.outcome_lower is not None and not math.isfinite(float(self.outcome_lower)):
            raise ValueError("outcome_lower must be finite when supplied")
        if self.outcome_upper is not None and not math.isfinite(float(self.outcome_upper)):
            raise ValueError("outcome_upper must be finite when supplied")
        if self.outcome_lower is None and self.outcome_upper is None:
            raise ValueError("one-arm ATE bound program requires at least one finite outcome support restriction")
        if (
            self.outcome_lower is not None
            and self.outcome_upper is not None
            and self.outcome_lower > self.outcome_upper
        ):
            raise ValueError("outcome_lower cannot exceed outcome_upper")
        return self

    def observed_mean_object(self) -> str:
        return f"E[{self.outcome} | {self.treatment}={self.observed_treatment_value}]"

    def endpoint_expressions(self) -> tuple[str, str]:
        mu = self.observed_mean_object()
        if self.observed_treatment_value == 1:
            lower = "-inf" if self.outcome_upper is None else f"{mu} - {self.outcome_upper:g}"
            upper = "+inf" if self.outcome_lower is None else f"{mu} - {self.outcome_lower:g}"
        else:
            lower = "-inf" if self.outcome_lower is None else f"{self.outcome_lower:g} - {mu}"
            upper = "+inf" if self.outcome_upper is None else f"{self.outcome_upper:g} - {mu}"
        return lower, upper

    def to_text(self) -> str:
        lower, upper = self.endpoint_expressions()
        left = "(" if lower == "-inf" else "["
        right = ")" if upper == "+inf" else "]"
        return f"{left}{lower}, {upper}{right}"

    def required_population_objects(self) -> list[str]:
        return [self.observed_mean_object()]


# Backward-compatible import name used by v0.2.2 clients.
OneArmBoundedATEBoundsProgram = OneArmATEBoundsProgram


class NetworkDirectEffectSensitivityBoundsProgram(StrictModel):
    """Direct-effect bounds under exposure-propensity ratio sensitivity.

    This is the constant-Gamma special case of Schröder et al. (2026), Eq. (9),
    Theorem 4.2, and Supplement C.3. For b^- = 1/Gamma and b^+ = Gamma, the
    conditional potential-outcome bounds use quantile levels alpha^- and alpha^+
    and the hinge-moment representation from Theorem 4.2. The direct-effect
    interval subtracts the adverse endpoints and averages over P_obs(X). For
    discrete exposure, Identification separately checks the supplementary
    sharpness applicability condition before attaching a `sharp` guarantee.
    """

    kind: Literal["network_direct_effect_sensitivity_bounds"] = (
        "network_direct_effect_sensitivity_bounds"
    )
    treatment: str
    outcome: str
    network_id: str
    reference_exposure_mapping: Literal["treated_neighbor_share_threshold_1hop"] = (
        "treated_neighbor_share_threshold_1hop"
    )
    target_exposure_semantics: Literal["true_sufficient_exposure_state"] = (
        "true_sufficient_exposure_state"
    )
    exposure_value: Literal[0, 1]
    sensitivity_gamma: float = Field(gt=1.0)
    target_context_distribution: Literal["observational_regime"] = "observational_regime"

    @model_validator(mode="after")
    def validate_finite_sensitivity_gamma(self):
        if not math.isfinite(float(self.sensitivity_gamma)):
            raise ValueError("sensitivity_gamma must be finite")
        return self

    def b_minus(self) -> float:
        return 1.0 / float(self.sensitivity_gamma)

    def b_plus(self) -> float:
        return float(self.sensitivity_gamma)

    def quantile_levels(self) -> tuple[float, float]:
        # Theorem 4.2 / Eq. (18): alpha^+ and alpha^- for b^-<1<b^+.
        b_minus, b_plus = self.b_minus(), self.b_plus()
        alpha_plus = ((1.0 - b_minus) * b_plus) / (b_plus - b_minus)
        alpha_minus = ((1.0 - b_plus) * b_minus) / (b_minus - b_plus)
        return alpha_minus, alpha_plus

    def capo_expression(self, treatment_value: int, side: Literal["lower", "upper"]) -> str:
        z = self.exposure_value
        b_minus, b_plus = self.b_minus(), self.b_plus()
        alpha_minus, alpha_plus = self.quantile_levels()
        if side == "upper":
            alpha = alpha_plus
            return (
                f"Q_{{{alpha:.12g}}}(Y|T={treatment_value},Z={z},X) + "
                f"{1.0/b_minus:.12g} E[(Y-Q)_+|T={treatment_value},Z={z},X] - "
                f"{1.0/b_plus:.12g} E[(Q-Y)_+|T={treatment_value},Z={z},X]"
            )
        alpha = alpha_minus
        return (
            f"Q_{{{alpha:.12g}}}(Y|T={treatment_value},Z={z},X) + "
            f"{1.0/b_plus:.12g} E[(Y-Q)_+|T={treatment_value},Z={z},X] - "
            f"{1.0/b_minus:.12g} E[(Q-Y)_+|T={treatment_value},Z={z},X]"
        )

    def endpoint_expressions(self) -> tuple[str, str]:
        z = self.exposure_value
        lower = f"E_X[mu^-(1,{z},X)-mu^+(0,{z},X)]"
        upper = f"E_X[mu^+(1,{z},X)-mu^-(0,{z},X)]"
        return lower, upper

    def to_text(self) -> str:
        lower, upper = self.endpoint_expressions()
        return f"[{lower}, {upper}] under b^-={self.b_minus():.12g}, b^+={self.b_plus():.12g}"

    def required_population_objects(self) -> list[str]:
        t, y, z = self.treatment, self.outcome, self.exposure_value
        return [
            f"F_obs({y}|{t}=1,Z={z},X)",
            f"F_obs({y}|{t}=0,Z={z},X)",
            "P_obs(X)",
        ]


BoundProgram = Union[
    ManskiBinaryATEBoundsProgram,
    OneArmATEBoundsProgram,
    NetworkDirectEffectSensitivityBoundsProgram,
]


class TraceStep(StrictModel):
    step: str
    outcome: Literal["PASS", "FAIL", "INFO"]
    detail: str


class IdentificationResult(StrictModel):
    status: IdentificationStatus
    query: QuerySpec
    backend: str
    identified_functional: PointProgram | None = None
    bound_program: BoundProgram | None = None
    set_program: SetProgram | None = None
    identified_set: FiniteUnionClosedIntervalsV1 | dict[str, Any] | None = None
    network_policy_mixture_proof: NetworkPolicyMixtureProofBundleV1 | None = None
    network_exposure: NetworkStructureSpec | None = None
    exposure_uncertainty: ExposureUncertaintySpec | None = None
    required_population_objects: list[str] = Field(default_factory=list)
    estimation_nuisance_objects: list[str] = Field(default_factory=list)
    known_design_objects: list[str] = Field(default_factory=list)
    assumptions_used: list[str] = Field(default_factory=list)
    validity_domain: dict[str, Any] = Field(default_factory=dict)
    guarantee: Literal[
        "point_identified",
        "sharp",
        "certified_outer",
        "trivial",
        "none",
    ] = "none"
    certificate: dict[str, Any] = Field(default_factory=dict)
    trace: list[TraceStep] = Field(default_factory=list)
    reason_code: str | None = None
    message: str = ""
    verification_status: VerificationStatus = VerificationStatus.UNSUPPORTED
    verification_message: str = ""


class PointEstimationRequest(StrictModel):
    request_type: Literal["POINT"] = "POINT"
    estimand: Literal["ATE"]
    identification_status: Literal[IdentificationStatus.POINT]
    treatment: str
    outcome: str
    program: DifferenceFunctional
    required_population_objects: list[str]
    validity_domain: dict[str, Any]
    assumptions: list[str]
    guarantee: str
    identification_backend: str
    verification_status: Literal[VerificationStatus.VERIFIED]


class PolicyValueContextContract(StrictModel):
    """Finite-sample representation required to estimate/evaluate the identified value.

    Identification fixes the population target here to the context distribution of
    the experimental regime.  Downstream code must make the finite set of contexts
    and their normalized weights explicit rather than silently assuming row order or
    uniform weighting.
    """

    population_distribution: Literal["experimental_regime"] = "experimental_regime"
    context_axis: Literal["snapshot"] = "snapshot"
    context_id_field: Literal["context_ids"] = "context_ids"
    target_context_weight_field: Literal["target_context_weights"] = "target_context_weights"
    target_context_weight_semantics: str = (
        "finite nonnegative weights aligned with context_ids and normalized to sum to one; "
        "their statistical construction belongs to Estimation"
    )
    policy_action_field: Literal["policy_actions"] = "policy_actions"
    policy_action_axes: list[Literal["snapshot", "node"]] = Field(
        default_factory=lambda: ["snapshot", "node"]
    )
    neighbor_count_semantics: str = (
        "K_i(pi(W_s)) is computed from policy_actions[s,:] and the typed fixed network "
        "using the declared treated_neighbor_count_1hop exposure mapping"
    )
    estimation_scope_note: str = (
        "node-specific mu_i(a,k,W,A) requires repeated experimental contexts/snapshots or an explicit "
        "cross-node/structural sharing model; Identification does not claim nonparametric finite-sample "
        "estimability from a single fixed-network snapshot"
    )

    @model_validator(mode="after")
    def validate_context_contract(self):
        if self.policy_action_axes != ["snapshot", "node"]:
            raise ValueError("policy_action_axes must be exactly ['snapshot','node']")
        return self


class PolicyValueTensorContract(StrictModel):
    """Array semantics expected by a downstream network-policy estimator."""

    axes: list[Literal["snapshot", "node", "own_treatment", "treated_neighbor_count"]] = Field(
        default_factory=lambda: ["snapshot", "node", "own_treatment", "treated_neighbor_count"]
    )
    node_ids: list[str]
    reachable_neighbor_counts: dict[str, list[int]]
    max_neighbor_count: int
    outcome_mean_semantics: str
    local_state_propensity_semantics: str
    unreachable_entries: Literal["null_with_reachable_mask"] = "null_with_reachable_mask"

    @model_validator(mode="after")
    def validate_tensor_contract(self):
        expected_axes = ["snapshot", "node", "own_treatment", "treated_neighbor_count"]
        if self.axes != expected_axes:
            raise ValueError(f"axes must be exactly {expected_axes}")
        if len(set(self.node_ids)) != len(self.node_ids) or not self.node_ids:
            raise ValueError("tensor_contract.node_ids must be nonempty and unique")
        if set(self.reachable_neighbor_counts) != set(self.node_ids):
            raise ValueError("reachable_neighbor_counts keys must match tensor node_ids exactly")
        if self.max_neighbor_count < 0:
            raise ValueError("max_neighbor_count must be nonnegative")
        return self


class PolicyValueEstimationRequest(StrictModel):
    contract_version: Literal["policy-value-v1"] = "policy-value-v1"
    request_type: Literal["POLICY_VALUE_POINT"] = "POLICY_VALUE_POINT"
    estimand: Literal["POLICY_VALUE"] = "POLICY_VALUE"
    identification_status: Literal[IdentificationStatus.POINT]
    treatment: str
    outcome: str
    program: NetworkPolicyValueProgram
    network: NetworkExposureSpec
    network_exposure_fingerprint: str
    context_contract: PolicyValueContextContract = Field(default_factory=PolicyValueContextContract)
    required_population_objects: list[str]
    estimation_nuisance_objects: list[str] = Field(default_factory=list)
    known_design_objects: list[str]
    known_local_state_propensities: dict[str, dict[str, float]]
    tensor_contract: PolicyValueTensorContract
    validity_domain: dict[str, Any]
    assumptions: list[str]
    guarantee: str
    identification_backend: str
    verification_status: Literal[VerificationStatus.VERIFIED]

    @model_validator(mode="after")
    def validate_cross_field_contract(self):
        if self.program.network_id != self.network.network_id:
            raise ValueError("program.network_id must match network.network_id")
        if self.program.exposure_mapping != self.network.exposure_mapping:
            raise ValueError("program exposure mapping must match the network exposure contract")
        if self.program.target_context_distribution != self.context_contract.population_distribution:
            raise ValueError("program target-context distribution must match context_contract")
        expected_fp = self.network.semantic_fingerprint()
        if self.network_exposure_fingerprint != expected_fp:
            raise ValueError("network_exposure_fingerprint does not match the typed network/exposure contract")
        if self.tensor_contract.node_ids != self.network.node_ids:
            raise ValueError("tensor node order must match network.node_ids exactly")
        expected_reachable = self.network.reachable_neighbor_counts()
        if self.tensor_contract.reachable_neighbor_counts != expected_reachable:
            raise ValueError("tensor reachable_neighbor_counts must match the network degrees exactly")
        if self.tensor_contract.max_neighbor_count != self.network.max_degree():
            raise ValueError("tensor max_neighbor_count must equal the network maximum degree")
        if set(self.known_local_state_propensities) != set(self.network.node_ids):
            raise ValueError("known local-state propensity nodes must match network.node_ids exactly")

        p = self.validity_domain.get("assignment_probability")
        mechanism = self.validity_domain.get("assignment_mechanism")
        if mechanism != "independent_bernoulli" or p is None or not 0.0 < float(p) < 1.0:
            raise ValueError("policy-value-v1 requires validity_domain independent Bernoulli assignment with 0<p<1")
        p = float(p)
        if self.validity_domain.get("network_id") != self.network.network_id:
            raise ValueError("validity_domain.network_id must match the typed network")
        if self.validity_domain.get("node_ids") != self.network.node_ids:
            raise ValueError("validity_domain.node_ids must preserve the typed network node order")
        if self.validity_domain.get("exposure_mapping") != self.network.exposure_mapping:
            raise ValueError("validity_domain exposure_mapping must match the typed network")
        if self.validity_domain.get("target_context_distribution") != "experimental_regime":
            raise ValueError("policy-value-v1 identifies the experimental-regime context population only")

        degrees = self.network.degree_map()
        for node in self.network.node_ids:
            row = self.known_local_state_propensities[node]
            expected_keys = {f"a={a},k={k}" for a in (0, 1) for k in range(degrees[node] + 1)}
            if set(row) != expected_keys:
                raise ValueError(f"known local-state propensity keys are incomplete/extra for node {node}")
            total = 0.0
            for a in (0, 1):
                own = p if a == 1 else 1.0 - p
                for k in range(degrees[node] + 1):
                    value = float(row[f"a={a},k={k}"])
                    if not math.isfinite(value) or value <= 0.0:
                        raise ValueError("reachable local-state propensities must be finite and strictly positive")
                    expected = own * math.comb(degrees[node], k) * (p ** k) * ((1.0 - p) ** (degrees[node] - k))
                    if not math.isclose(value, expected, rel_tol=0.0, abs_tol=1e-12):
                        raise ValueError(f"known local-state propensity does not match Bernoulli design for node {node}")
                    total += value
            if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError(f"known local-state propensities for node {node} must sum to one")
        return self

    @property
    def known_local_state_probabilities(self) -> dict[str, dict[str, float]]:
        """Backward-compatible Python alias; JSON uses known_local_state_propensities."""
        return self.known_local_state_propensities


class NetworkDirectEffectPointEstimationRequest(StrictModel):
    contract_version: Literal["network-direct-effect-v2"] = "network-direct-effect-v2"
    request_type: Literal["NETWORK_DIRECT_EFFECT_POINT"] = "NETWORK_DIRECT_EFFECT_POINT"
    estimand: Literal["DIRECT_EFFECT"] = "DIRECT_EFFECT"
    identification_status: Literal[IdentificationStatus.POINT]
    treatment: str
    outcome: str
    reference_exposure_definition: Literal["treated_neighbor_share_threshold_1hop"]
    target_exposure_semantics: Literal["true_sufficient_exposure_state"]
    exposure_value: Literal[0, 1]
    program: NetworkDirectEffectPointProgram
    network: ThresholdNetworkExposureSpec
    network_exposure_fingerprint: str
    required_population_objects: list[str]
    validity_domain: dict[str, Any]
    assumptions: list[str]
    guarantee: str
    identification_backend: str
    verification_status: Literal[VerificationStatus.VERIFIED]

    @model_validator(mode="after")
    def validate_cross_field_contract(self):
        if self.program.network_id != self.network.network_id:
            raise ValueError("program.network_id must match network.network_id")
        if self.reference_exposure_definition != self.network.exposure_mapping:
            raise ValueError("request reference exposure definition must match network exposure mapping")
        if self.target_exposure_semantics != "true_sufficient_exposure_state":
            raise ValueError("point request must preserve the true sufficient exposure target semantics")
        if self.program.reference_exposure_mapping != self.reference_exposure_definition:
            raise ValueError("program reference exposure mapping must match request semantics")
        if self.program.target_exposure_semantics != self.target_exposure_semantics:
            raise ValueError("program target exposure semantics must match request semantics")
        if self.program.exposure_value != self.exposure_value:
            raise ValueError("program exposure value must match request exposure_value")
        if self.network_exposure_fingerprint != self.network.semantic_fingerprint():
            raise ValueError("network/exposure fingerprint mismatch")
        if self.required_population_objects != self.program.required_population_objects():
            raise ValueError("required_population_objects must match the point program")
        if self.guarantee != "point_identified":
            raise ValueError("network-direct-effect-v2 requires point_identified guarantee")
        expected_validity = {
            "regime": "observational_fixed_network_interference",
            "network_id": self.network.network_id,
            "node_ids": self.network.node_ids,
            "reference_exposure_mapping": self.reference_exposure_definition,
            "reference_threshold": self.network.threshold,
            "target_exposure_semantics": self.target_exposure_semantics,
            "target_exposure_value": self.exposure_value,
            "target_context_distribution": "observational_regime",
            "network_exposure_fingerprint": self.network_exposure_fingerprint,
        }
        if self.validity_domain != expected_validity:
            raise ValueError("validity_domain must exactly match the point theorem contract")
        return self


class NetworkDirectEffectBoundEstimationRequest(StrictModel):
    contract_version: Literal["network-direct-effect-bounds-v2"] = (
        "network-direct-effect-bounds-v2"
    )
    request_type: Literal["NETWORK_DIRECT_EFFECT_BOUND"] = "NETWORK_DIRECT_EFFECT_BOUND"
    estimand: Literal["DIRECT_EFFECT"] = "DIRECT_EFFECT"
    identification_status: Literal[IdentificationStatus.PARTIAL]
    treatment: str
    outcome: str
    reference_exposure_definition: Literal["treated_neighbor_share_threshold_1hop"]
    target_exposure_semantics: Literal["true_sufficient_exposure_state"]
    exposure_value: Literal[0, 1]
    program: NetworkDirectEffectSensitivityBoundsProgram
    network: ThresholdNetworkExposureSpec
    network_exposure_fingerprint: str
    exposure_uncertainty: ExposurePropensityRatioSensitivitySpec
    required_population_objects: list[str]
    validity_domain: dict[str, Any]
    assumptions: list[str]
    guarantee: str
    identification_backend: str
    verification_status: Literal[VerificationStatus.VERIFIED]

    @model_validator(mode="after")
    def validate_cross_field_contract(self):
        if self.program.network_id != self.network.network_id:
            raise ValueError("program.network_id must match network.network_id")
        if self.reference_exposure_definition != self.network.exposure_mapping:
            raise ValueError("request reference exposure definition must match network exposure mapping")
        if self.target_exposure_semantics != "true_sufficient_exposure_state":
            raise ValueError("partial request must preserve the true sufficient exposure target semantics")
        if self.program.reference_exposure_mapping != self.reference_exposure_definition:
            raise ValueError("program reference exposure mapping must match request semantics")
        if self.program.target_exposure_semantics != self.target_exposure_semantics:
            raise ValueError("program target exposure semantics must match request semantics")
        if self.program.exposure_value != self.exposure_value:
            raise ValueError("program exposure value must match request exposure_value")
        if not math.isclose(
            self.program.sensitivity_gamma, self.exposure_uncertainty.gamma, rel_tol=0.0, abs_tol=1e-12
        ):
            raise ValueError("program sensitivity gamma must match exposure_uncertainty")
        if self.network_exposure_fingerprint != self.network.semantic_fingerprint():
            raise ValueError("network/exposure fingerprint mismatch")
        if self.required_population_objects != self.program.required_population_objects():
            raise ValueError("required_population_objects must match the bound program")
        if self.guarantee not in {"sharp", "certified_outer"}:
            raise ValueError(
                "network-direct-effect-bounds-v2 requires a verified sharp or certified_outer population guarantee"
            )
        if self.validity_domain.get("network_id") != self.network.network_id:
            raise ValueError("validity_domain network_id must match network")
        if self.validity_domain.get("reference_exposure_mapping") != self.network.exposure_mapping:
            raise ValueError("validity_domain reference exposure mapping must match network")
        if self.validity_domain.get("reference_threshold") != self.network.threshold:
            raise ValueError("validity_domain reference threshold must match network")
        if self.validity_domain.get("target_exposure_semantics") != "true_sufficient_exposure_state":
            raise ValueError("validity_domain must state that the causal target uses the true sufficient exposure state")
        if self.validity_domain.get("target_exposure_value") != self.exposure_value:
            raise ValueError("validity_domain target exposure value must match request")
        if self.validity_domain.get("sensitivity_gamma") != self.exposure_uncertainty.gamma:
            raise ValueError("validity_domain sensitivity_gamma must match exposure_uncertainty")
        if not math.isclose(float(self.validity_domain.get("b_minus")), self.program.b_minus(), rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("validity_domain b_minus must match the program")
        if not math.isclose(float(self.validity_domain.get("b_plus")), self.program.b_plus(), rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("validity_domain b_plus must match the program")
        if self.validity_domain.get("target_context_distribution") != "observational_regime":
            raise ValueError("network-direct-effect-bounds-v2 targets observational_regime contexts")
        if self.validity_domain.get("network_exposure_fingerprint") != self.network_exposure_fingerprint:
            raise ValueError("validity_domain network/exposure fingerprint must match request fingerprint")
        if self.guarantee == "sharp" and self.validity_domain.get("discrete_exposure_sharpness_condition") is not True:
            raise ValueError("sharp guarantee requires the discrete-exposure sharpness applicability condition")
        if self.guarantee == "certified_outer" and self.validity_domain.get("discrete_exposure_sharpness_condition") is True:
            raise ValueError("certified_outer must not be used when this contract declares the sharpness condition certified")
        return self


class BoundEstimationRequest(StrictModel):
    request_type: Literal["BOUND"] = "BOUND"
    estimand: Literal["ATE"]
    identification_status: Literal[IdentificationStatus.PARTIAL]
    treatment: str
    outcome: str
    program: BoundProgram
    required_population_objects: list[str]
    validity_domain: dict[str, Any]
    assumptions: list[str]
    guarantee: str
    identification_backend: str
    verification_status: Literal[VerificationStatus.VERIFIED]


class NetworkPolicyMixtureEstimationRequestV2(StrictModel):
    """Portable, self-checking Identification -> Estimation work specification.

    The reference o/proof are an audit example, NOT estimates from a new dataset.
    New finite-sample objects require a separate estimation/inference procedure.
    """
    contract_version: Literal["network-policy-mixture-estimation-v2"] = "network-policy-mixture-estimation-v2"
    request_type: Literal["NETWORK_POLICY_MIXTURE_SET"] = "NETWORK_POLICY_MIXTURE_SET"
    estimand: Literal["POLICY_VALUE"] = "POLICY_VALUE"
    identification_status: Literal[IdentificationStatus.POINT, IdentificationStatus.PARTIAL]
    program: NetworkPolicyFiniteMixtureSetProgram
    required_population_objects: list[str]
    known_design_objects: list[str]
    validity_domain: dict[str, Any]
    assumptions: list[Assumption]
    provenance: dict[str, str]
    guarantee: str
    query_confirmation_fingerprint: str
    source_spec: IdentificationSpec
    reference_population_truth: NetworkPolicyBinaryMeanPopulationTruthV1
    reference_identification_result: IdentificationResult
    verification_status: Literal[VerificationStatus.VERIFIED] = VerificationStatus.VERIFIED
    finite_sample_estimation: Literal["NOT_RUN"] = "NOT_RUN"
    policy_optimization: Literal["NOT_RUN"] = "NOT_RUN"
    reuse_boundary: Literal["REFERENCE_PROOF_IS_NOT_A_CERTIFICATE_FOR_NEW_EMPIRICAL_DATA"] = "REFERENCE_PROOF_IS_NOT_A_CERTIFICATE_FOR_NEW_EMPIRICAL_DATA"

    @model_validator(mode="after")
    def verify_portable_request(self):
        from .network_policy_mixture import verify_network_policy_mixture
        from .query_confirmation import query_confirmation_fingerprint
        checked=verify_network_policy_mixture(self.source_spec,self.reference_population_truth,self.reference_identification_result)
        if checked.verification_status != VerificationStatus.VERIFIED:
            raise ValueError("portable handoff certificate replay failed: "+str(checked.reason_code))
        if (self.identification_status != checked.status or self.program != checked.set_program
            or self.guarantee != checked.guarantee or self.validity_domain != checked.validity_domain
            or self.required_population_objects != checked.required_population_objects
            or self.known_design_objects != checked.known_design_objects
            or self.assumptions != self.source_spec.assumptions or self.provenance != self.source_spec.provenance
            or self.query_confirmation_fingerprint != query_confirmation_fingerprint(self.source_spec.query)):
            raise ValueError("portable handoff fields do not match the replayed specification/result")
        # Trace and verification prose are not proof inputs; retain only the
        # verifier's regenerated presentation, never an untrusted claimed verdict.
        self.reference_identification_result = checked
        return self


class NetworkMajorityResponseEstimationRequestV1(StrictModel):
    """Portable symbolic task; verifies rule applicability, NOT estimator accuracy."""
    contract_version: Literal["network-majority-response-estimation-v1"] = "network-majority-response-estimation-v1"
    request_type: Literal["NETWORK_MAJORITY_RESPONSE"] = "NETWORK_MAJORITY_RESPONSE"
    estimand: Literal["NETWORK_RESPONSE_SURFACE"] = "NETWORK_RESPONSE_SURFACE"
    identification_status: Literal[IdentificationStatus.POINT] = IdentificationStatus.POINT
    program: NetworkMajorityResponseProgram
    source_spec: IdentificationSpec
    reference_identification_result: IdentificationResult
    required_population_objects: list[str]
    known_design_objects: list[str]
    query_confirmation_fingerprint: str
    verification_status: Literal[VerificationStatus.VERIFIED] = VerificationStatus.VERIFIED
    finite_sample_guarantee: Literal["none"] = "none"
    policy_compatibility: Literal["majority_surrogate_only_not_deterministic_policy_value"] = "majority_surrogate_only_not_deterministic_policy_value"

    @model_validator(mode="after")
    def replay_source(self):
        from .majority_response import verify_majority_response
        from .query_confirmation import query_confirmation_fingerprint
        checked = verify_majority_response(self.source_spec, self.reference_identification_result)
        if checked.verification_status != VerificationStatus.VERIFIED:
            raise ValueError("Majority response handoff replay failed: " + checked.verification_message)
        if (self.program != checked.identified_functional
            or self.required_population_objects != checked.required_population_objects
            or self.known_design_objects != checked.known_design_objects
            or self.query_confirmation_fingerprint != query_confirmation_fingerprint(self.source_spec.query)):
            raise ValueError("Majority response handoff does not match the verified source")
        self.reference_identification_result = checked
        return self


class NetworkMajorityScoreEstimationRequestV1(StrictModel):
    """Identified score program plus its separately verified response dependency."""
    contract_version: Literal["network-majority-score-estimation-v1"] = "network-majority-score-estimation-v1"
    request_type: Literal["NETWORK_MAJORITY_POLICY_SCORE"] = "NETWORK_MAJORITY_POLICY_SCORE"
    estimand: Literal["NETWORK_MAJORITY_RESPONSE_POLICY_SCORE"] = "NETWORK_MAJORITY_RESPONSE_POLICY_SCORE"
    identification_status: Literal[IdentificationStatus.POINT] = IdentificationStatus.POINT
    program: NetworkMajorityPolicyScoreProgram
    source_spec: IdentificationSpec
    reference_identification_result: IdentificationResult
    response_request: NetworkMajorityResponseEstimationRequestV1
    required_population_objects: list[str]
    known_design_objects: list[str]
    query_confirmation_fingerprint: str
    verification_status: Literal[VerificationStatus.VERIFIED] = VerificationStatus.VERIFIED
    finite_sample_guarantee: Literal["none"] = "none"
    policy_compatibility: Literal["identified_majority_response_score"] = "identified_majority_response_score"

    @model_validator(mode="after")
    def replay_score(self):
        from .majority_score import verify_majority_score, response_dependency
        from .query_confirmation import query_confirmation_fingerprint
        from .strict_json import canonical
        checked = verify_majority_score(self.source_spec, self.reference_identification_result)
        if checked.verification_status != VerificationStatus.VERIFIED:
            raise ValueError("Majority score handoff replay failed: " + checked.verification_message)
        dependency = response_dependency(self.source_spec)
        if (canonical(self.program.model_dump(mode="json")) != canonical(checked.identified_functional.model_dump(mode="json"))
            or self.required_population_objects != checked.required_population_objects
            or self.known_design_objects != checked.known_design_objects
            or self.query_confirmation_fingerprint != query_confirmation_fingerprint(self.source_spec.query)
            or canonical(self.response_request.source_spec.model_dump(mode="json")) != canonical(dependency.model_dump(mode="json"))
            or canonical(self.response_request.reference_identification_result.model_dump(mode="json")) != canonical(checked.certificate["response_identification_result"])):
            raise ValueError("Majority score dependency or program mismatch")
        self.reference_identification_result = checked
        return self


EstimationRequest = Union[
    NetworkMajorityScoreEstimationRequestV1,
    NetworkMajorityResponseEstimationRequestV1,
    NetworkPolicyMixtureEstimationRequestV2,
    PointEstimationRequest,
    PolicyValueEstimationRequest,
    BoundEstimationRequest,
    NetworkDirectEffectPointEstimationRequest,
    NetworkDirectEffectBoundEstimationRequest,
]


class PointEstimationResult(StrictModel):
    result_type: Literal["POINT"] = "POINT"
    estimand: Literal["ATE"]
    estimator: str
    estimate: float
    treated_mean: float
    control_mean: float
    standard_error: float
    wald_interval_95: tuple[float, float]
    finite_sample_guarantee: str = (
        "approximate 95% Wald interval; no exact/randomization-based coverage guarantee is claimed"
    )
    n_treated: int
    n_control: int
    requested_population_objects: list[str]
    executed_program: str

    @property
    def ci_95(self) -> tuple[float, float]:
        """Backward-compatible alias; prefer `wald_interval_95`."""
        return self.wald_interval_95


class BoundEstimationResult(StrictModel):
    result_type: Literal["BOUND"] = "BOUND"
    estimand: Literal["ATE"]
    estimator: str
    estimated_lower_endpoint: float | None
    estimated_upper_endpoint: float | None
    estimated_width: float | None
    n: int
    estimated_population_objects: dict[str, float]
    requested_population_objects: list[str]
    executed_program: str
    endpoint_target: Literal["population_identified_set_endpoints"] = "population_identified_set_endpoints"
    finite_sample_guarantee: Literal["none"] = "none"
    interpretation: str = (
        "Plug-in estimates of the endpoints of the population identified set; "
        "no finite-sample coverage guarantee is claimed."
    )

    @property
    def lower(self) -> float | None:
        return self.estimated_lower_endpoint

    @property
    def upper(self) -> float | None:
        return self.estimated_upper_endpoint

    @property
    def width(self) -> float | None:
        return self.estimated_width


EstimationResult = Union[PointEstimationResult, BoundEstimationResult]


class PolicyRequest(StrictModel):
    action: str = "activate_strategy"
    cost_per_unit: float
    value_per_outcome_unit: float = 1.0
    objective: str = "incremental_outcome_value_minus_cost"


class PolicyDecision(StrictModel):
    decision: Literal["ROLL_OUT", "DO_NOT_ROLL_OUT", "ABSTAIN"]
    decision_basis: Literal["point_estimate", "estimated_lower_endpoint", "no_finite_lower_endpoint"]
    estimated_causal_gain: float | None = None
    estimated_causal_lower: float | None = None
    estimated_causal_upper: float | None = None
    estimated_gross_value: float | None
    cost_per_unit: float
    estimated_net_value: float | None
    objective: str
    finite_sample_guarantee: str = "none"


class ValidationReference(StrictModel):
    """Simulation-only reference values that are never exposed to Identification/Estimation."""

    target_scope: Literal["fixed_finite_population", "superpopulation_dgp"]
    target_ate: float
    finite_population_realized_ate: float | None = None
    population_identified_bounds: tuple[float | None, float | None] | None = None
    population_cell_probabilities: dict[str, float] = Field(default_factory=dict)
    notes: str = ""
