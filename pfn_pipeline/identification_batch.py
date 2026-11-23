"""Verified full-network randomized-arm batch and legacy ER response bridge.

The batch is a compact *population-identification* certificate, not estimated
response values.  Each (node, own treatment, exposure) cell is checked against
an independent exact allocation-counting method. It never constructs a new PFN
request.  A separate legacy bridge can reuse ONLY a replayed, already-existing
four-arm EstimationRequest bound to the same original TaskSpec.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from math import comb

from .contracts import IdentificationResult, TaskSpec
from ._internal.identification.randomized_network_arm import arm_a4_information_reason
from ._internal.identification.schemas import (
    CompleteRandomizationDesignV1, HeterogeneousBernoulliDesignV1,
    IdentificationSpec, TwoGroupFixedQuotaDesignV1, ClusterBernoulliDesignV24, MultiGroupFixedQuotaDesignV25, TwoStageQuotaMixtureDesignV27,
    UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1,
)
from ._internal.identification.randomized_arm_family import AssignmentSpec, ExposureSpec, SupportEngine
from ._internal.identification.randomized_arm_family.assignment import as_design_dataclass
from ._internal.identification.randomized_arm_family.assignment_extensions import MAX_EXACT_ENUMERATION_N
from ._internal.identification.randomized_arm_family.support_verifier import verify_joint_support as _verify_joint_support
from ._internal.identification.randomized_network_arm import (
    GROUP_E1, GROUP_E2, GROUP_E3, GROUP_E4, GROUP_E5,
    MAX_BERNOULLI_DP_CELLS, MAX_TWO_GROUP_CONVOLUTION_CELLS,
    _group_neighbor_counts, _verify_joint_support_independently,
    _verify_two_group_joint_support_independently, _verify_multi_group_joint_support_independently, _verifier_matches_exposure,
    arm_target_fingerprint, spec_fingerprint,
    exposure_object, exposure_state_str, W_G_GROUPINGS,
)
from ._internal.identification.randomized_arm_family.exposure_extensions import (
    WeightedExposureSpec, GroupedExposureSpec)
from ._internal.identification.randomized_arm_family.cluster_verifier import verify_cluster_joint_support
from ._internal.identification.randomized_arm_family.two_stage_verifier import independent_joint_support as _verify_d6_joint_support
from .identification import identify, replay_handoff, replay_population_identification, make_heterogeneous_bernoulli_arm_task

__all__ = [
    'BatchIdentificationResult', 'identify_randomized_network_batch',
    'replay_network_arm_batch', 'LegacyResponseBatchBridge',
    'bind_legacy_response_batch', 'replay_legacy_response_batch_bridge',
    'estimate_bound_legacy_response',
]

_VERSION = 'randomized-network-full-arm-batch-v1'


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class BatchIdentificationResult:
    """Immutable coordinates and cell-level POINT proof summary.

    Shape convention [N, 2, S], ordered by source TaskSpec.node_ids, own
    treatment 0/1, and exposure 0/1(/2). A status of UNSUPPORTED is NOT
    a partially-identified causal target. The seed query alone is not treated
    as a certificate for the entire surface: every cell's support is checked.
    """
    template: TaskSpec
    anchor: IdentificationResult
    node_ids: tuple[str, ...]
    exposure_states: tuple[int, ...]
    population_joint_support: tuple[tuple[tuple[str | None, ...], ...], ...]
    arm_status: tuple[tuple[tuple[str, ...], ...], ...]
    arm_reason: tuple[tuple[tuple[str | None, ...], ...], ...]
    target_fingerprints: tuple[tuple[tuple[str, ...], ...], ...]
    source_spec_sha256: str
    batch_sha256: str
    coverage_status: str
    verification_status: str = 'VERIFIED'
    contract_version: str = _VERSION
    estimation_request: None = None

    @property
    def shape(self) -> tuple[int, int, int]:
        return len(self.node_ids), 2, len(self.exposure_states)

    @property
    def population_support_mask(self) -> tuple[tuple[tuple[bool, ...], ...], ...]:
        return tuple(tuple(tuple(status == 'POINT' for status in treatment)
                           for treatment in node) for node in self.arm_status)

    def cell(self, node_id: str, a: int, s: int) -> dict:
        if node_id not in self.node_ids or type(a) is not int or a not in (0, 1) or s not in self.exposure_states:
            raise ValueError('Requested node or arm is outside this batch')
        row, col = self.node_ids.index(node_id), self.exposure_states.index(s)
        return {
            'node_id': node_id, 'own_treatment': a, 'exposure': s,
            'status': self.arm_status[row][a][col],
            'reason_code': self.arm_reason[row][a][col],
            'joint_support': self.population_joint_support[row][a][col],
            'target_fingerprint': self.target_fingerprints[row][a][col],
        }


def _independent_count_masses(design: HeterogeneousBernoulliDesignV1, neighbors) -> tuple[Fraction, ...]:
    """Independent replay: divide-and-conquer generating-product coefficients.

    Unlike the proposer, this is NOT sequential Poisson-binomial DP. For the
    common equal-p case the binomial closed form avoids dense-ER overhead.
    """
    probabilities = [Fraction(design.propensities[n]) for n in sorted(neighbors)]
    if not probabilities:
        return (Fraction(1),)
    polys = [(1-p, p) for p in probabilities]
    while len(polys) > 1:
        merged = []
        for ix in range(0, len(polys), 2):
            if ix + 1 == len(polys):
                merged.append(polys[ix])
                continue
            left, right = polys[ix], polys[ix+1]
            out = [Fraction(0)] * (len(left) + len(right) - 1)
            for i, l in enumerate(left):
                if l:
                    for j, r in enumerate(right):
                        if r:
                            out[i+j] += l*r
            merged.append(tuple(out))
        polys = merged
    return tuple(polys[0])


def _support_comparison(design, network, node: str, a: int, states: tuple[int, ...],
                        grouping: str, reference_nodes, independent_counts) -> dict[int, Fraction]:
    degree = len(reference_nodes) if reference_nodes is not None else network.degree_map()[node]
    if isinstance(design, CompleteRandomizationDesignV1):
        return {s: _verify_joint_support_independently(len(network.node_ids), design.m, degree, a, s, grouping)
                for s in states}
    if isinstance(design, TwoGroupFixedQuotaDesignV1):
        return {s: _verify_two_group_joint_support_independently(
            network, design, node, a, s, grouping, reference_nodes=reference_nodes) for s in states}
    if isinstance(design, TwoStageQuotaMixtureDesignV27):
        return {s:_verify_d6_joint_support(network,design,node,a,s,grouping,
                    _verifier_matches_exposure,reference_nodes=reference_nodes) for s in states}
    if isinstance(design, MultiGroupFixedQuotaDesignV25):
        return {s: _verify_multi_group_joint_support_independently(
            network,design,node,a,s,grouping,reference_nodes=reference_nodes) for s in states}
    if isinstance(design, ClusterBernoulliDesignV24):
        return {s: verify_cluster_joint_support(
            network, design, node, a, s, grouping, _verifier_matches_exposure,
            reference_nodes=reference_nodes) for s in states}
    p = Fraction(design.propensities[node])
    own = p if a else 1 - p
    return {s: own * sum((v for k, v in enumerate(independent_counts)
                          if _verifier_matches_exposure(k, degree, s, grouping)), Fraction(0))
            for s in states}


def _compute_wg(template, anchor, spec, network, contract, assignment, nodes) -> BatchIdentificationResult:
    """Batch over a weighted/grouped (W/G) exposure.

    W/G exposure states are per-node and non-integer (exact rationals / grouped
    tuples). The batch state axis is the union of the nodes' reachable states,
    serialized to the same canonical strings the wire query uses; a per-node
    unreachable cell is explicitly UNSUPPORTED (never POINT). Every cell is
    checked against the independent enumeration oracle.
    """
    exposure = exposure_object(contract)
    node_data = {}
    all_states = set()
    for node in nodes:
        joint = SupportEngine.joint_support(
            network=network, assignment=assignment, exposure=exposure, node_id=node)
        oracle = _verify_joint_support(
            network=network, design=assignment,
            exposure=exposure, node_id=node, proposed={})["oracle"]
        produced = {}
        for (a, s), p in joint.items():
            key = exposure_state_str(exposure, s)
            produced[(a, key)] = p
            if p:
                all_states.add(key)
        independent = {(a, exposure_state_str(exposure, s)): p for (a, s), p in oracle.items()}
        node_data[node] = (produced, independent)
    states = tuple(sorted(all_states, key=str))
    if any(arm_a4_information_reason(spec, node_id=node, a=a, s=s) is not None
           for node in nodes for a in (0, 1) for s in states):
        raise ValueError('BATCH_A4_ARM_COVERAGE_INCOMPLETE')
    support_rows, status_rows, reason_rows, fp_rows = [], [], [], []
    for node in nodes:
        produced, independent = node_data[node]
        sr, tr, rr, fr = [], [], [], []
        for a in (0, 1):
            arm_support, arm_status, arm_reason, arm_fps = [], [], [], []
            for s in states:
                calculated = produced.get((a, s), Fraction(0))
                if independent.get((a, s), Fraction(0)) != calculated:
                    raise ValueError(f'Independent batch support mismatch at {(node, a, s)}')
                arm_support.append(str(calculated))
                arm_status.append('POINT' if calculated > 0 else 'UNSUPPORTED')
                arm_reason.append(None if calculated > 0 else 'ZERO_ARM_SUPPORT')
                arm_fps.append(arm_target_fingerprint(network, contract, node, a, s))
            sr.append(tuple(arm_support)); tr.append(tuple(arm_status))
            rr.append(tuple(arm_reason)); fr.append(tuple(arm_fps))
        if sum((Fraction(v) for t in sr for v in t), Fraction(0)) != 1:
            raise ValueError('Joint arm probabilities do not sum to one for node ' + node)
        support_rows.append(tuple(sr)); status_rows.append(tuple(tr))
        reason_rows.append(tuple(rr)); fp_rows.append(tuple(fr))
    support = tuple(support_rows); statuses = tuple(status_rows)
    reasons = tuple(reason_rows); fingerprints = tuple(fp_rows)
    source = spec_fingerprint(spec)
    content = {'version': _VERSION, 'source_spec_sha256': source,
               'node_ids': nodes, 'exposure_states': states,
               'joint_support': support, 'arm_status': statuses,
               'arm_reason': reasons, 'target_fingerprints': fingerprints}
    coverage = ('ALL_POINT_IDENTIFIED' if all(s == 'POINT' for n in statuses
                                              for arm in n for s in arm)
                else 'SOME_ARMS_UNSUPPORTED')
    return BatchIdentificationResult(
        template=template, anchor=anchor, node_ids=nodes, exposure_states=states,
        population_joint_support=support, arm_status=statuses, arm_reason=reasons,
        target_fingerprints=fingerprints, source_spec_sha256=source,
        batch_sha256=_digest(content), coverage_status=coverage)


def _compute(template: TaskSpec, anchor: IdentificationResult) -> BatchIdentificationResult:
    spec = IdentificationSpec.model_validate(template.identification_spec)
    network = spec.network_exposure
    contract = spec.randomized_network_arm_theorem_contract
    if template.estimand != 'NETWORK_RANDOMIZED_ARM_MEAN' or network is None or contract is None:
        raise ValueError('Batch requires the typed randomized-network single-arm family')
    assignment = AssignmentSpec(contract.design)
    assignment._validate_network(network)
    # The anchor is independently verified before entering this function; E3
    # core collaborators were checked by its canonical theorem contract.
    nodes = tuple(network.node_ids)
    if isinstance(contract.design, (UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1)):
        if len(nodes) > MAX_EXACT_ENUMERATION_N:
            raise ValueError('RANDOMIZED_NETWORK_RESOURCE_LIMIT: task-1 design enumeration')
    if contract.grouping in W_G_GROUPINGS:
        return _compute_wg(template, anchor, spec, network, contract, assignment, nodes)
    # Batch certificate claims all POINT cells are identifiable. A single
    # node-arm A4 declaration cannot authorize the entire N-by-arm batch.
    # Conservative check includes zero/undefined cells too, because the
    # official all-arm information contract covers all query coordinates.
    def node_states(node):
        degree = (len(contract.core_collaborators[node]) if contract.grouping == GROUP_E3
                  else network.degree_map()[node])
        return ExposureSpec(contract.grouping,contract.core_collaborators).states_for_degree(degree)
    if any(arm_a4_information_reason(spec, node_id=node, a=a, s=s) is not None
           for node in network.node_ids for a in (0, 1) for s in node_states(node)):
        raise ValueError('BATCH_A4_ARM_COVERAGE_INCOMPLETE')
    exposure = ExposureSpec(contract.grouping, contract.core_collaborators)
    if contract.grouping == GROUP_E4:
        # Batch has a rectangular public tensor; individual node degree varies.
        # Pad impossible coordinates explicitly as UNSUPPORTED (never POINT).
        # Restrict state-axis size for the batch; single-arm E4 has no such cap.
        if network.max_degree() > 64:
            raise ValueError('BATCH_EXACT_COUNT_AXIS_LIMIT: use per-node E4 arm inquiries')
        states = tuple(range(network.max_degree()+1))
    else:
        states = exposure.states
    support_rows, status_rows, reason_rows, fp_rows = [], [], [], []
    # Under homogeneous neighbor Bernoulli probabilities, the *same exact*
    # count polynomial is shared by all nodes with identical (degree, p).
    # Cache independently checked polynomial coefficients, not unverified
    # single-arm results. Heterogeneous propensities keep the original path.
    independent_bernoulli_cache: dict[tuple[int, Fraction], tuple[Fraction, ...]] = {}
    for node in nodes:
        neighbors = (frozenset(contract.core_collaborators[node]) if contract.grouping == GROUP_E3
                     else None)
        degree = len(neighbors) if neighbors is not None else network.degree_map()[node]
        if isinstance(contract.design, (HeterogeneousBernoulliDesignV1,ClusterBernoulliDesignV24)) and degree*(degree+1)//2 > MAX_BERNOULLI_DP_CELLS:
            raise ValueError('RANDOMIZED_NETWORK_RESOURCE_LIMIT: batch D1 node degree')
        if isinstance(contract.design, TwoStageQuotaMixtureDesignV27):
            if len(contract.design.quota_profiles)*degree*(degree+1)//2>2_000_000:
                raise ValueError('RANDOMIZED_NETWORK_RESOURCE_LIMIT: batch D6 node degree')
        if isinstance(contract.design, MultiGroupFixedQuotaDesignV25):
            if degree*(degree+1)//2>MAX_TWO_GROUP_CONVOLUTION_CELLS:
                raise ValueError('RANDOMIZED_NETWORK_RESOURCE_LIMIT: batch D5 node degree')
        if isinstance(contract.design, TwoGroupFixedQuotaDesignV1):
            c0, c1 = _group_neighbor_counts(network, contract.design, node)
            if (c0+1)*(c1+1) > MAX_TWO_GROUP_CONVOLUTION_CELLS:
                raise ValueError('RANDOMIZED_NETWORK_RESOURCE_LIMIT: batch D3 node degree')
        independent_counts = None
        independent_neighbor_ids = None
        iid_neighbors_p = None
        if isinstance(contract.design, HeterogeneousBernoulliDesignV1):
            from ._internal.identification.randomized_arm_family.assignment import neighbor_set
            independent_neighbor_ids = neighbors if neighbors is not None else neighbor_set(network, node)
            distinct_p = {Fraction(contract.design.propensities[j]) for j in independent_neighbor_ids}
            if len(distinct_p) == 1:
                iid_neighbors_p = next(iter(distinct_p))
                key = (degree, iid_neighbors_p)
                if key not in independent_bernoulli_cache:
                    verified = _independent_count_masses(contract.design, independent_neighbor_ids)
                    closed = tuple(Fraction(comb(degree,k))*iid_neighbors_p**k
                                   *(1-iid_neighbors_p)**(degree-k) for k in range(degree+1))
                    if verified != closed:
                        raise ValueError('Independent binomial/polynomial count law mismatch')
                    independent_bernoulli_cache[key] = verified
                independent_counts = independent_bernoulli_cache[key]
            else:
                independent_counts = _independent_count_masses(contract.design, independent_neighbor_ids)
        if contract.grouping == GROUP_E2 and degree == 0:
            support_rows.append(tuple(tuple(None for _ in states) for _ in (0, 1)))
            status_rows.append(tuple(tuple('UNSUPPORTED' for _ in states) for _ in (0, 1)))
            reason_rows.append(tuple(tuple('EXPOSURE_UNDEFINED_FOR_ISOLATED_NODE' for _ in states) for _ in (0, 1)))
            fp_rows.append(tuple(tuple(arm_target_fingerprint(network, contract, node, a, s)
                                       for s in states) for a in (0, 1)))
            continue
        joint_support = None
        support_oracle = None
        if isinstance(contract.design, (UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1)):
            joint_support = SupportEngine.joint_support(
                network=network, assignment=assignment, exposure=exposure, node_id=node)
            support_oracle = _verify_joint_support(
                network=network, design=as_design_dataclass(contract.design), exposure=exposure,
                node_id=node, proposed={})["oracle"]
        sr, tr, rr, fr = [], [], [], []
        for a in (0, 1):
            # Exact binomial closed form for equal neighbor propensities. This
            # saves a quadratic Fraction DP on dense ER networks; the replay
            # independently multiplies Bernoulli generating polynomials.
            if joint_support is not None:
                law = None
            elif (isinstance(contract.design, HeterogeneousBernoulliDesignV1)
                    and iid_neighbors_p is not None):
                from ._internal.identification.randomized_arm_family.assignment import NeighborCountLaw
                p = iid_neighbors_p
                own_p = Fraction(contract.design.propensities[node]); own = own_p if a else 1-own_p
                law = NeighborCountLaw(own, tuple(Fraction(comb(degree,k)) * p**k * (1-p)**(degree-k)
                                                 for k in range(degree+1)) if own else
                                       tuple(Fraction(0) for _ in range(degree+1)), degree)
            else:
                law = assignment.conditional_neighbor_count_law(network, node, a, reference_nodes=neighbors)
            if support_oracle is not None:
                independently = {s: support_oracle.get((a, s), Fraction(0)) for s in states}
            else:
                independently = _support_comparison(contract.design, network, node, a, states,
                                                    contract.grouping, neighbors, independent_counts)
            arm_support, arm_status, arm_reason, arm_fps = [], [], [], []
            for s in states:
                if contract.grouping == GROUP_E4 and s > degree:
                    if independently[s] != 0:
                        raise ValueError('Independent verifier assigned mass outside node degree')
                    arm_support.append(None)
                    arm_status.append('UNSUPPORTED')
                    arm_reason.append('EXPOSURE_STATE_OUTSIDE_NODE_DEGREE')
                    arm_fps.append(arm_target_fingerprint(network,contract,node,a,s))
                    continue
                calculated = (joint_support.get((a, s), Fraction(0)) if joint_support is not None
                              else SupportEngine.from_count_law(law, exposure, s).joint_probability)
                if independently[s] != calculated:
                    raise ValueError(f'Independent batch support mismatch at {(node, a, s)}')
                arm_support.append(str(calculated))
                arm_status.append('POINT' if calculated > 0 else 'UNSUPPORTED')
                arm_reason.append(None if calculated > 0 else 'ZERO_ARM_SUPPORT')
                arm_fps.append(arm_target_fingerprint(network, contract, node, a, s))
            sr.append(tuple(arm_support)); tr.append(tuple(arm_status))
            rr.append(tuple(arm_reason)); fr.append(tuple(arm_fps))
        if sum((Fraction(v) for treatment in sr for v in treatment if v is not None), Fraction(0)) != 1:
            raise ValueError('Joint arm probabilities do not sum to one for node ' + node)
        support_rows.append(tuple(sr)); status_rows.append(tuple(tr))
        reason_rows.append(tuple(rr)); fp_rows.append(tuple(fr))
    support = tuple(support_rows); statuses = tuple(status_rows)
    reasons = tuple(reason_rows); fingerprints = tuple(fp_rows)
    source = spec_fingerprint(spec)
    content = {'version': _VERSION, 'source_spec_sha256': source,
               'node_ids': nodes, 'exposure_states': states,
               'joint_support': support, 'arm_status': statuses,
               'arm_reason': reasons, 'target_fingerprints': fingerprints}
    coverage = ('ALL_POINT_IDENTIFIED' if all(status == 'POINT' for node in statuses
                                              for arm in node for status in arm)
                else 'SOME_ARMS_UNSUPPORTED')
    return BatchIdentificationResult(
        template=template, anchor=anchor, node_ids=nodes, exposure_states=states,
        population_joint_support=support, arm_status=statuses, arm_reason=reasons,
        target_fingerprints=fingerprints, source_spec_sha256=source,
        batch_sha256=_digest(content), coverage_status=coverage,
    )


def identify_randomized_network_batch(template: TaskSpec) -> BatchIdentificationResult:
    """Certify all arms for the *same* design, grouping and pretreatment W.

    A trusted, explicitly admitted single-arm TaskSpec is the anchor. This does
    not infer assumptions from outcomes, create a PFN adapter, or use the sampled
    arm counts to determine population identification.
    """
    if not isinstance(template, TaskSpec) or template.estimand != 'NETWORK_RANDOMIZED_ARM_MEAN':
        raise TypeError('A randomized-network arm TaskSpec is required')
    anchor = identify(template)
    if anchor.verification_status != 'VERIFIED' or anchor.status != 'POINT':
        raise ValueError('Cannot certify batch: the reference arm is not POINT/VERIFIED; '
                         + str(anchor.result.get('reason_code')))
    replay_population_identification(anchor)
    return _compute(template, anchor)


def replay_network_arm_batch(batch: BatchIdentificationResult) -> BatchIdentificationResult:
    """Recompute all cell proofs and reject modified source, support or masks."""
    if not isinstance(batch, BatchIdentificationResult) or batch.estimation_request is not None:
        raise ValueError('Expected population-only BatchIdentificationResult')
    if batch.contract_version != _VERSION or batch.verification_status != 'VERIFIED':
        raise ValueError('Batch contract or verifier status is invalid')
    if batch.anchor.task is not batch.template:
        raise ValueError('Batch anchor is not bound to its source TaskSpec')
    replay_population_identification(batch.anchor)
    fresh_anchor = identify(batch.template)
    if (fresh_anchor.verification_status != 'VERIFIED'
        or fresh_anchor.result != batch.anchor.result):
        raise ValueError('Saved anchor differs from independently re-solved theorem')
    expected = _compute(batch.template, fresh_anchor)
    compared = ('node_ids', 'exposure_states', 'population_joint_support',
                'arm_status', 'arm_reason', 'target_fingerprints',
                'source_spec_sha256', 'batch_sha256', 'coverage_status')
    if any(getattr(expected, name) != getattr(batch, name) for name in compared):
        raise ValueError('Batch cell support, target, or certificate differs from replay')
    return expected


@dataclass(frozen=True)
class LegacyResponseBatchBridge:
    """Batch-to-Estimation linkage using ONLY the existing verified response request."""
    legacy_identification: IdentificationResult
    batch: BatchIdentificationResult
    legacy_source_spec_sha256: str
    binding_sha256: str
    estimation_status: str = 'REQUEST_DEFINED_RUNTIME_UNCHECKED'


def _response_result(legacy: IdentificationResult):
    if legacy.task.estimand == 'NETWORK_MAJORITY_RESPONSE_POLICY_SCORE':
        return legacy.result['certificate']['response_identification_result']
    if legacy.task.estimand == 'NETWORK_RESPONSE_SURFACE':
        return legacy.result
    raise ValueError('Legacy bridge requires a verified E1 four-arm response dependency')


def _legacy_template(legacy: IdentificationResult) -> TaskSpec:
    """Bind a fresh batch seed to exactly the *same* verified legacy protocol."""
    from ._internal.identification.schemas import IdentificationSpec, NetworkExposureSpec
    spec = IdentificationSpec.model_validate(legacy.task.identification_spec)
    response = _response_result(legacy)
    net = NetworkExposureSpec.model_validate(spec.network_exposure)
    program = response['identified_functional']
    p = Fraction(program['assignment_probability_rational'])
    if p != Fraction(1, 2) or legacy.task.exposure_definition != 'strict_majority':
        raise ValueError('Frozen PFN bridge supports only Bernoulli(1/2) + strict majority')
    if legacy.task.outcome_kind != 'continuous':
        raise ValueError('Frozen PFN bridge supports only continuous outcomes')
    if tuple(net.node_ids) != legacy.task.node_ids:
        raise ValueError('Legacy graph/node order differs from formal protocol')
    from ._internal.identification.majority_response import spec_fingerprint as legacy_fingerprint
    synthetic = spec.query.authority == 'TRUSTED_FIXTURE'
    return make_heterogeneous_bernoulli_arm_task(
        net, propensities={node: str(p) for node in net.node_ids},
        node_id=net.node_ids[0], own_treatment_value=0, exposure_value=0,
        source='verified_legacy_protocol:' + legacy_fingerprint(spec),
        evidence='Derived from the same replay-verified original response TaskSpec; no new domain assumptions',
        admitted=True, synthetic=synthetic,
        query_authority='TRUSTED_FIXTURE' if synthetic else 'HUMAN_CONFIRMED',
        outcome_kind=legacy.task.outcome_kind,
    )


def _verify_bridge_support(batch: BatchIdentificationResult, legacy: IdentificationResult) -> None:
    import numpy as np
    if batch.coverage_status != 'ALL_POINT_IDENTIFIED' or batch.exposure_states != (0, 1):
        raise ValueError('Legacy PFN requires complete, POINT-identified four-arm coverage')
    if batch.node_ids != legacy.task.node_ids or not np.array_equal(batch.template.adjacency, legacy.task.adjacency):
        raise ValueError('Legacy and batch networks, or node order, differ')
    response = _response_result(legacy)
    by_degree = response['certificate']['design_by_degree']
    for i, node in enumerate(batch.node_ids):
        degree = int(legacy.task.adjacency[i].sum())
        joint = by_degree[str(degree)]['joint_own_treatment_arm_probabilities']
        for a in (0, 1):
            for s in (0, 1):
                if Fraction(batch.population_joint_support[i][a][s]) != Fraction(joint[f'{a},{s}']):
                    raise ValueError('Batch-vs-legacy full response support mismatch: ' + node)


def bind_legacy_response_batch(legacy: IdentificationResult) -> LegacyResponseBatchBridge:
    """Derive a certified full arm batch from the *same* old response TaskSpec.

    No new PFN request is made. The legacy identification keeps ownership of its
    original verified, replayable EstimationRequest and factual observations.
    """
    if not isinstance(legacy, IdentificationResult):
        raise TypeError('Expected an IdentificationResult from the existing response route')
    replay_handoff(legacy)
    template = _legacy_template(legacy)
    batch = identify_randomized_network_batch(template)
    _verify_bridge_support(batch, legacy)
    from ._internal.identification.majority_response import spec_fingerprint as legacy_fingerprint
    source = legacy_fingerprint(IdentificationSpec.model_validate(legacy.task.identification_spec))
    return LegacyResponseBatchBridge(legacy_identification=legacy, batch=batch,
                                    legacy_source_spec_sha256=source,
                                    binding_sha256=_digest({'legacy_spec': source, 'batch': batch.batch_sha256}))


def replay_legacy_response_batch_bridge(bridge: LegacyResponseBatchBridge) -> LegacyResponseBatchBridge:
    if not isinstance(bridge, LegacyResponseBatchBridge):
        raise TypeError('Expected a bound legacy batch bridge')
    replay_handoff(bridge.legacy_identification)
    template = _legacy_template(bridge.legacy_identification)
    if template.identification_spec != bridge.batch.template.identification_spec:
        raise ValueError('Batch seed not derived from the exact verified legacy response protocol')
    replay_network_arm_batch(bridge.batch)
    _verify_bridge_support(bridge.batch, bridge.legacy_identification)
    from ._internal.identification.majority_response import spec_fingerprint as legacy_fingerprint
    source = legacy_fingerprint(IdentificationSpec.model_validate(
        bridge.legacy_identification.task.identification_spec))
    if bridge.legacy_source_spec_sha256 != source or bridge.binding_sha256 != _digest(
            {'legacy_spec': source, 'batch': bridge.batch.batch_sha256}):
        raise ValueError('Legacy-to-batch provenance fingerprint differs from replay')
    return bridge


def estimate_bound_legacy_response(bridge: LegacyResponseBatchBridge, model=None, **kwargs):
    """Validate the legacy handoff before referring a fitting request to the full project."""
    replay_legacy_response_batch_bridge(bridge)
    raise NotImplementedError("Fitting a legacy PFN response requires the full autoCFM project. "
                              "Use bridge.legacy_identification.estimation_request for the verified identification handoff.")
