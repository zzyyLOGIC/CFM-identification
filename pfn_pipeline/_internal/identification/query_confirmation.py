from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from .schemas import QuerySpec, QueryType, VariableSemanticSpec


QUERY_FINGERPRINT_VERSION = "qf2"


def query_execution_payload(query: QuerySpec) -> dict[str, Any]:
    """Return the complete query semantics that can affect backend execution.

    Evidence, confidence, and prose rationale remain visible audit material but
    do not alter the formal causal query. The payload deliberately includes all
    execution-relevant slots, not only the query-family label.

    Revalidate a serialized copy first so the canonical expression is derived
    from the *current* structured fields. This closes a subtle mutation hazard:
    direct attribute edits or ``model_copy(update=...)`` cannot leave a stale
    expression that would be hashed alongside different exposure semantics.
    """

    normalized = QuerySpec.model_validate(query.model_dump(mode="python"))
    payload = {
        "type": normalized.type,
        "treatment": normalized.treatment,
        "outcome": normalized.outcome,
        "target_population": normalized.target_population,
        "conditioning_variables": list(normalized.conditioning_variables),
        "reference_exposure_definition": normalized.reference_exposure_definition,
        "target_exposure_semantics": normalized.target_exposure_semantics,
        "policy_description": normalized.policy_description,
        "canonical_expression": normalized.expression,
    }
    # qf2 binds both the observed/reference exposure mapping and the causal target
    # exposure semantics so POINT/PARTIAL cannot silently change the estimand.
    if normalized.response_target_fingerprint is not None:
        payload["response_target_fingerprint"] = normalized.response_target_fingerprint
    if normalized.policy_fingerprint is not None:
        payload["policy_fingerprint"] = normalized.policy_fingerprint
    if normalized.exposure_value is not None:
        payload["exposure_value"] = normalized.exposure_value
    return payload


def query_confirmation_fingerprint(query: QuerySpec) -> str:
    canonical = json.dumps(
        query_execution_payload(query),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(
        f"{QUERY_FINGERPRINT_VERSION}\n{canonical}".encode("utf-8")
    ).hexdigest()
    return f"{QUERY_FINGERPRINT_VERSION}-{digest}"


def apply_human_semantic_confirmation(
    spec: VariableSemanticSpec,
    *,
    expected_query_type: QueryType,
    expected_fingerprint: str,
) -> VariableSemanticSpec:
    """Confirm the exact execution-relevant query, never only its family.

    A user first reviews the structured proposal and its fingerprint. A later
    run is promoted only if the newly produced formal query is an exact match.
    This prevents a changed treatment, outcome, target population, conditioning
    set, exposure, or policy slot from inheriting an earlier confirmation.
    """

    confirmed = spec.model_copy(deep=True)
    query = confirmed.query
    actual_fingerprint = query_confirmation_fingerprint(query)
    exact_match = hmac.compare_digest(
        actual_fingerprint,
        expected_fingerprint.strip().lower(),
    )
    eligible = (
        query.authority == "PROPOSED"
        and query.type == expected_query_type
        and exact_match
        and query.resolution == "RESOLVED"
        and bool(query.evidence)
        and not query.alternatives
        and not confirmed.unresolved
    )
    if eligible:
        query.authority = "HUMAN_CONFIRMED"
        confirmed.normalization_notes.append(
            "A human explicitly confirmed the complete execution-relevant query semantics "
            f"using fingerprint {actual_fingerprint}."
        )
    else:
        mismatch_reasons: list[str] = []
        if query.type != expected_query_type:
            mismatch_reasons.append(
                f"type expected={expected_query_type}, actual={query.type}"
            )
        if not exact_match:
            mismatch_reasons.append("query fingerprint mismatch")
        if query.resolution != "RESOLVED":
            mismatch_reasons.append(f"resolution={query.resolution}")
        if not query.evidence:
            mismatch_reasons.append("no validated evidence")
        if query.alternatives:
            mismatch_reasons.append("semantic alternatives remain")
        if confirmed.unresolved:
            mismatch_reasons.append("unresolved semantic items remain")
        if query.authority != "PROPOSED":
            mismatch_reasons.append(f"authority={query.authority}")
        confirmed.normalization_notes.append(
            "Human semantic confirmation was not applied: "
            + ("; ".join(mismatch_reasons) or "proposal was not eligible")
            + f". Current fingerprint={actual_fingerprint}."
        )
    return confirmed
