"""Generalized bounded contrast entry with dynamic routing for ALL D1-D6 × E1-E5.

Extends bounded_contrast.py by replacing hardcoded ROUTE='BOUNDED_POLICY_CONTRAST_D2_E1'
with D/E-aware routing.
"""
from copy import deepcopy
from typing import Literal
from pydantic import field_validator
from _crypto import _sha
from cfm_id import fixed_comparison as comparison
from cfm_id import question_bound_assignment as ids
from cfm_id.assignment_review import validate_assignment_review
from cfm_id.intent_submission import _context_snapshot, _validate_policy
from cfm_id.bounded_policy_contract import StrictRecord, Hash, Text, BoundedPolicyUnavailable, fail
from cfm_id.bounded_contrast_contract import VERSION, SIDES, validate_pair, target_coordinates
from cfm_id.general_bounded_contrast_solver import solve, analyze


def _resolve_design_kind(inquiry):
    """Read the design kind from the inquiry's assignment specification."""
    st = inquiry
    design = getattr(st, 'design', None)
    if design is None:
        return 'D2'
    mapping = {
        'HeterogeneousBernoulliDesignV1': 'D1',
        'CompleteRandomizationDesignV1': 'D2',
        'TwoGroupFixedQuotaDesignV1': 'D3',
        'ClusterBernoulliDesignV24': 'D4',
        'MultiGroupFixedQuotaDesignV25': 'D5',
        'TwoStageQuotaMixtureDesignV27': 'D6',
    }
    return mapping.get(type(design).__name__, 'D2')


def _resolve_exposure_kind(inquiry):
    """Read the exposure kind from the inquiry's exposure specification."""
    st = inquiry
    exposure = getattr(st, 'exposure', None)
    if exposure is None:
        return 'E1'
    grouping = getattr(exposure, 'grouping', '')
    mapping = {
        'strict_majority_ties_low': 'E1',
        'three_level_treated_neighbor_fraction': 'E2',
        'pretreatment_core_collaborator_majority': 'E3',
        'exact_treated_neighbor_count': 'E4',
        'any_treated_neighbor': 'E5',
    }
    return mapping.get(grouping, 'E1')


def _make_route(inquiry):
    dk = _resolve_design_kind(inquiry)
    ek = _resolve_exposure_kind(inquiry)
    return f'BOUNDED_POLICY_CONTRAST_{dk}_{ek}'


class ReviewedBoundedContrast(StrictRecord):
    version: Literal['bounded-policy-contrast-1']
    query_id: str
    bundle_sha256: Hash
    reading_sha256: Hash
    ordered_target_sha256: Hash
    endpoint_bindings_sha256: Hash
    information_sha256: Hash
    reviewer: Text
    evidence: Text
    reviewed_direction_and_common_population: Literal[True]
    reviewed_complete_common_a4_model: Literal[True]
    reviewed_scientific_bounds_and_no_extra_constraints: Literal[True]
    synthetic_fixture: Literal[True]

    @field_validator('reviewed_direction_and_common_population',
        'reviewed_complete_common_a4_model', 'reviewed_scientific_bounds_and_no_extra_constraints',
        'synthetic_fixture', mode='before')
    @classmethod
    def explicit_true(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError('EXPLICIT_JOINT_SCIENTIFIC_REVIEW_REQUIRED')
        return value


def _inquiries(context):
    if type(context) is not dict or set(context) != set(SIDES):
        fail('CHECK_BLOCKED', 'EXACT_TWO_ENDPOINT_CONTEXTS_REQUIRED')
    return context


def worksheet(bundle, raw, *, query_id, packet, context, information):
    """Unapproved bindings only; original comparison and both endpoints retained."""
    if set(bundle['question_slots']) != {query_id}:
        fail('UNSUPPORTED', 'SINGLE_ORDERED_COMPARISON_REQUIRED')
    _, _, _, targets = comparison.project(bundle, raw)
    if query_id not in targets:
        fail('NEEDS_INPUT', 'COMPLETE_ORDERED_COMPARISON_REQUIRED')
    _inquiries(context)
    if type(packet) is not dict or set(packet) != set(SIDES):
        fail('CHECK_BLOCKED', 'EXACT_TWO_ENDPOINT_PACKETS_REQUIRED')
    inquiries = {s: context[s].core_port.bindings[query_id].inquiry for s in SIDES}
    validate_pair(inquiries, information)
    if targets[query_id] != target_coordinates(inquiries):
        fail('CHECK_BLOCKED', 'ACTUAL_COMPARISON_AND_REVIEWED_TARGETS_DIFFER')
    return dict(version=VERSION, query_id=query_id, bundle_sha256=_sha(bundle),
        reading_sha256=_sha(raw), ordered_target_sha256=_sha(targets[query_id]),
        endpoint_bindings_sha256=_sha({s:dict(packet=packet[s],context=_context_snapshot(context[s])) for s in SIDES}),
        information_sha256=_sha(information))


def prepare(bundle, raw, *, query_id, packet=None, context=None, information=None):
    out = comparison.preview(bundle, raw)
    out.update(entry='general_bounded', bounded_version=VERSION, bounded_backend_called=False,
        bounded_certificate_replayed=False, scientific_approval=False,
        production_admission=False, estimation_handoff_allowed=False)
    if set(bundle['question_slots']) != {query_id}:
        return dict(out, state='UNSUPPORTED', reason_code='SINGLE_ORDERED_COMPARISON_REQUIRED')
    if out['state'] != 'REVIEW_REQUIRED':
        return out
    if packet is None or context is None or information is None:
        return dict(out, reason_code='SEPARATE_COMMON_MODEL_AND_REVIEW_REQUIRED')
    try:
        out['worksheet'] = worksheet(bundle, raw, query_id=query_id, packet=packet,
                                      context=context, information=information)
    except BoundedPolicyUnavailable as exc:
        out.update(state=exc.state, reason_code=exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError):
        out.update(state='CHECK_BLOCKED', reason_code='INVALID_CONTRAST_BINDING')
    return out


def submit(bundle, raw, *, query_id, packet=None, context=None, information=None,
           assignment_review=None, joint_review=None, synthetic_protocol_selected=False,
           design_kind=None, exposure_kind=None):
    """Generalized contrast submit with optional explicit design/exposure override."""
    out = prepare(bundle, raw, query_id=query_id, packet=packet, context=context, information=information)
    if out['state'] != 'REVIEW_REQUIRED':
        return out
    if (synthetic_protocol_selected is not True or 'worksheet' not in out
            or joint_review is None or assignment_review is None):
        return out
    try:
        if type(joint_review) is not ReviewedBoundedContrast:
            fail('CHECK_BLOCKED', 'SEPARATE_TYPED_CONTRAST_REVIEW_REQUIRED')
        reviewed = ReviewedBoundedContrast.model_validate(joint_review.model_dump())
        if any(getattr(reviewed, k) != v for k, v in out['worksheet'].items()):
            fail('CHECK_BLOCKED', 'CONTRAST_REVIEW_STALE')
        if type(assignment_review) is not dict or set(assignment_review) != set(SIDES):
            fail('CHECK_BLOCKED', 'BOTH_ORIGINAL_ASSIGNMENT_REVIEWS_REQUIRED')
        resolved, _, _, targets = comparison.project(bundle, raw)
        fact_receipts = {}
        for side in SIDES:
            fact_receipts[side] = validate_assignment_review(bundle, raw, packet[side], context[side],
                assignment_review[side], contract=ids.CONTRACT)
            _validate_policy(bundle, resolved['reading'], packet[side], context[side],
                comparison._endpoint_targets(targets, side))
        inquiries = {s: context[s].core_port.bindings[query_id].inquiry for s in SIDES}

        # Resolve design/exposure kinds.
        dk = design_kind or _resolve_design_kind(next(iter(inquiries.values())))
        ek = exposure_kind or _resolve_exposure_kind(next(iter(inquiries.values())))

        analyze(inquiries, information, design_kind=dk, exposure_kind=ek)
        endpoint_assessment = {}
        for side in SIDES:
            c = context[side]
            coverage = c.core_port.lookup(case=c.case, quality=c.quality, review=c.business_review, query_id=query_id)
            row = deepcopy(c.core_port.last_real_results[query_id])
            out['core_called'] = True
            allowed = (coverage.status == 'POINT' and row['route'] == 'R2_MEAN_SIGNATURE'
                       and row['verification_level'] == 'CORE_REPLAY_VERIFIED') or (
                coverage.status in ('UNSUPPORTED', 'NEEDS_INPUT') and row['reason_code'] in
                ('ZERO_POLICY_SIGNATURE_SUPPORT', 'A4_SIGNATURE_INFORMATION_INSUFFICIENT'))
            if not allowed:
                fail('CHECK_BLOCKED', 'ENDPOINT_SCIENTIFIC_CHAIN_NOT_ADMITTED')
            endpoint_assessment[side] = row
        out.update(point_assessment=endpoint_assessment, assignment_fact_review_receipts=fact_receipts)
        out['bounded_backend_called'] = True
        certificate = solve(inquiries, information, design_kind=dk, exposure_kind=ek)
        if not _replay(certificate, inquiries=inquiries, information=information):
            fail('CHECK_BLOCKED', 'INDEPENDENT_CONTRAST_REPLAY_FAILED')
        route = _make_route(next(iter(inquiries.values())))
        out.update(state=certificate['status'], reason_code=None, bounded_result=certificate,
            bounded_certificate_replayed=True, joint_review_sha256=sha(reviewed))
        for view in out['query_views']:
            view.update(state=certificate['status'], reason_code=None, route=route,
                identified_interval=[certificate['lower'], certificate['upper']],
                sharp=True, informative=certificate['informative'], bounded_certificate_replayed=True)
        out['identification'] = dict(results=[dict(query_id=query_id, status=certificate['status'], route=route,
            identified_interval=[certificate['lower'], certificate['upper']],
            bounded_certificate_sha256=certificate['certificate_sha256'], bounded_certificate_replayed=True)])
    except BoundedPolicyUnavailable as exc:
        out.update(state=exc.state, reason_code=exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        out.update(state='CHECK_BLOCKED', reason_code='CONTRAST_OR_SCIENCE_REVIEW_REJECTED')
    if not out['bounded_certificate_replayed']:
        for view in out.get('query_views', []):
            view.update(state=out['state'], reason_code=out.get('reason_code'), bounded_certificate_replayed=False)
    return out


def _replay(certificate, inquiries, information):
    """Verify the certificate is self-consistent."""
    from cfm_id.bounded_contrast_verify import replay
    return replay(certificate, inquiries=inquiries, information=information)