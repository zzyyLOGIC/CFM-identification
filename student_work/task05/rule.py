"""Standalone Task05 identification rule.

IdentificationResult is the task-local result type, separate from the public
class in pfn_pipeline.contracts. It reports a symbolic population functional.
Core verifier registration and Estimation handoff are outside this module.
"""
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from fractions import Fraction

if __package__:
    from .support import integer, support_by_degree, validate_design
else:
    from support import integer, support_by_degree, validate_design


REQUIRED_ASSUMPTIONS = (
    "known_assignment_law",
    "full_vector_randomization",
    "consistency",
    "fixed_pretreatment_network",
    "finite_conditional_first_moments",
)
ACCEPTED = {"ADMITTED", "CERTIFIED", "DERIVED"}
PENDING = {"UNRESOLVED", "PROPOSED"}
REJECTED = {"NOT_ADMITTED", "CONTRADICTED"}


@dataclass(frozen=True)
class ConditionalMeanFunctional:
    """An expression in the population law; does not compute sample averages."""
    node: int
    treatment: int
    exposure: int

    @property
    def expression(self):
        return (f"E[Y_{self.node}^obs | A, X, "
                f"T_{self.node}={self.treatment}, S_{self.node}={self.exposure}]")


@dataclass(frozen=True)
class IdentificationResult:
    """Task-local result; NOT_RUN refers to the unregistered core verifier."""
    node: int
    treatment: int
    exposure: int
    n: int
    quota: int
    adjacency: tuple
    assumptions: tuple
    support: Fraction | None
    status: str
    workflow_status: str
    reason_code: str
    functional: ConditionalMeanFunctional | None = None
    verification_status: str = "NOT_RUN"
    estimation_request: None = None

    def to_dict(self):
        result = asdict(self)
        result["support"] = None if self.support is None else str(self.support)
        result["functional"] = None if self.functional is None else self.functional.expression
        result["scope"] = "standalone_task05_not_registered_with_core_verifier"
        return result


def identify(adjacency, m, node, t, s, *, assumptions=None):
    """Identify ONE arm under the explicitly admitted D2 x E2 experiment.

    assumptions maps each REQUIRED_ASSUMPTIONS name to an explicit status.
    ADMITTED/CERTIFIED/DERIVED are caller declarations, not facts inferred from
    outcomes or verified by this function. Missing keys mean UNRESOLVED.
    Invalid inputs raise ValueError. Unsupported queries return a clear reason.
    """
    graph, m = validate_design(adjacency, m)
    node = integer(node, "node", 0, len(graph) - 1)
    t = integer(t, "t", 0, 1)
    s = integer(s, "s", 0, 2)
    if assumptions is None:
        assumptions = {}
    if not isinstance(assumptions, Mapping):
        raise ValueError("assumptions must be a mapping of names to explicit statuses")
    if set(assumptions) - set(REQUIRED_ASSUMPTIONS):
        raise ValueError("unknown assumption name")
    if any(not isinstance(v, str) or v not in ACCEPTED | PENDING | REJECTED
           for v in assumptions.values()):
        raise ValueError("invalid assumption status; use explicit status strings")
    records = tuple((name, assumptions.get(name, "UNRESOLVED")) for name in REQUIRED_ASSUMPTIONS)
    table = support_by_degree(len(graph), m, sum(graph[node]))
    probability = None if table is None else table[t, s]
    fields = dict(node=node, treatment=t, exposure=s, n=len(graph), quota=m,
                  adjacency=graph, assumptions=records, support=probability)
    if table is None:
        return IdentificationResult(**fields, status="UNSUPPORTED", workflow_status="UNSUPPORTED",
                                    reason_code="EXPOSURE_UNDEFINED_ISOLATE")
    if probability == 0:
        return IdentificationResult(**fields, status="UNSUPPORTED", workflow_status="UNSUPPORTED",
                                    reason_code="ZERO_POPULATION_SUPPORT")
    if any(status in REJECTED for _, status in records):
        return IdentificationResult(**fields, status="UNSUPPORTED", workflow_status="UNSUPPORTED",
                                    reason_code="REQUIRED_ASSUMPTION_REJECTED")
    if any(status not in ACCEPTED for _, status in records):
        return IdentificationResult(**fields, status="UNSUPPORTED", workflow_status="NEEDS_INPUT",
                                    reason_code="REQUIRED_ASSUMPTIONS_NOT_ADMITTED")
    return IdentificationResult(**fields, status="POINT", workflow_status="COMPLETE",
                                reason_code="DESIGN_STANDARDIZED_ARM_IDENTIFIED",
                                functional=ConditionalMeanFunctional(node, t, s))
