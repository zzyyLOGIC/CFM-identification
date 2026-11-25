"""Candidate preparation from parsed attributes, before scientific admission.

These are the existing adapter decisions, not theorem tests. Keeping their
inputs explicit avoids dispatch on prose or on a historical method prefix.
Contracts still validate sources, domains, assumptions, support and proofs.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    method: str
    source_indices: tuple[int, ...] = ()
    reason_code: str | None = None
    unresolved: bool = False


def signature_scope_covers_target(scope, covered_nodes, target_nodes):
    """The existing signature method requires an all-assignment premise per target unit."""
    return scope == 'ALL_BINARY_ASSIGNMENTS' and set(target_nodes) <= set(covered_nodes)


def randomized_policy(facts, usable_sources):
    """Preserve original full-policy / signature preparation and exclusions.

``facts`` has already passed the reader's domain and source checks;
``usable_sources`` contains only its validated symbolic population sources.
No branch is a license, nor a check of positive support.
"""
    from .policy_methods import FULL_POLICY, SIGNATURE_POLICY
    from cfm_id_llm.network_design_reading import EXPOSURE_GROUPS, missing_exposure
    usable = tuple(usable_sources)
    sf = facts.mean_sufficiency
    signature_ready = (
        facts.exposure.kind in frozenset(EXPOSURE_GROUPS) - {'WEIGHTED_EXPOSURE', 'GROUPED_EXPOSURE'}
        and not missing_exposure(facts.exposure, facts.study.nodes) and bool(facts.exposure.source_ids)
        and sf.value is True and bool(sf.source_ids)
        and signature_scope_covers_target(sf.scope, sf.covered_nodes, facts.target.population))
    indices = {
        FULL_POLICY: tuple(i for i in usable if facts.information[i].operator != 'NODE_SIGNATURE_MEANS'),
        SIGNATURE_POLICY: tuple(i for i in usable if facts.information[i].operator != 'ASSIGNMENT_NODE_MEANS')
                         if signature_ready else (),
    }
    rows = []
    for method in (FULL_POLICY, SIGNATURE_POLICY):
        if indices[method]:
            rows.append(Candidate(method, indices[method]))
            continue
        reason = ('R2_ADDITIONAL_DECLARATIONS_NOT_ESTABLISHED'
                  if method == SIGNATURE_POLICY and not signature_ready
                  else 'POPULATION_INFORMATION_NOT_SUPPLIED_FOR_METHOD')
        unresolved = (not usable if method == FULL_POLICY else sf.value is None or
            (sf.value is True and (sf.scope == 'UNKNOWN' or facts.exposure.kind == 'UNKNOWN'
             or missing_exposure(facts.exposure, facts.study.nodes)
             or not set(facts.target.population) <= set(sf.covered_nodes))) or
            (signature_ready and not indices[SIGNATURE_POLICY]))
        rows.append(Candidate(method, reason_code=reason, unresolved=bool(unresolved)))
    return tuple(rows)


def bounded_mean_implementation(*, assignment_kind, exposure_kind, symbolic):
    """Choose an implementation only after the complete bounded model gates.

The three implementations share the same mean-box meaning. This choice alone
does not admit any D/E combination, extra constraint or scientific bound.
"""
    if assignment_kind == 'UNIFORM_FIXED_QUOTA' and not symbolic:
        if exposure_kind == 'EXACT_TREATED_NEIGHBOR_COUNT':
            return 'BOUNDED_POLICY_MEAN_D2_E4'
        if exposure_kind == 'STRICT_MAJORITY_TIES_LOW':
            return 'BOUNDED_POLICY_MEAN_D2_E1'
    return 'BOUNDED_POLICY_MEAN_FINITE'


def dag_roles(*, frontdoor_status, specified_adjustment):
    """Respect explicit method-role requests; no graph criterion is tested."""
    from . import dag_methods
    if frontdoor_status not in ('SPECIFIED', 'FORBIDDEN', 'UNSPECIFIED'):
        raise ValueError('UNRESOLVED_DAG_METHOD_ROLE')
    rows = []
    for method in dag_methods.METHOD_IDS:
        reason = None
        if method != dag_methods.FRONTDOOR and frontdoor_status == 'SPECIFIED':
            reason = 'EXPLICIT_FRONTDOOR_ROLE_MUST_BE_RESPECTED'
        if method == dag_methods.FRONTDOOR:
            if frontdoor_status == 'FORBIDDEN':
                reason = 'FRONTDOOR_USE_FORBIDDEN'
            elif specified_adjustment:
                reason = 'EXPLICIT_ADJUSTMENT_REQUEST_MUST_BE_RESPECTED'
        rows.append(Candidate(method, reason_code=reason))
    return tuple(rows)
