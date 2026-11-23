"""Generalized bounded-policy entry with dynamic routing for ALL D1-D6 × E1-E5.

Extends bounded_policy.py by replacing the hardcoded
route='BOUNDED_POLICY_MEAN_D2_E1' with parameterized
routing derived from the inquiry's design and exposure specifications.
"""
from copy import deepcopy

from _crypto import _sha
from cfm_id import question_bound_assignment as ids
from cfm_id.intent_submission import _context_snapshot, submit as submit_point
from cfm_id.bounded_policy_contract import (
    VERSION, BoundedMeanInformation, ReviewedBoundedPolicy,
    BoundedPolicyUnavailable, validate_model,
)
from cfm_id.general_bounded_policy_solver import solve

# Detect design/exposure kind from the inquiry.
def _resolve_design_kind(inquiry):
    """Read the design kind from the inquiry's assignment specification.

    Returns one of 'D1'..'D6' based on the declared design class name.
    """
    st = inquiry
    design = getattr(st, 'design', None)
    if design is None:
        return 'D2'  # default fallback

    name = type(design).__name__
    mapping = {
        'HeterogeneousBernoulliDesignV1': 'D1',
        'CompleteRandomizationDesignV1': 'D2',
        'TwoGroupFixedQuotaDesignV1': 'D3',
        'ClusterBernoulliDesignV24': 'D4',
        'MultiGroupFixedQuotaDesignV25': 'D5',
        'TwoStageQuotaMixtureDesignV27': 'D6',
    }
    return mapping.get(name, 'D2')


def _resolve_exposure_kind(inquiry):
    """Read the exposure kind from the inquiry's exposure specification.

    Returns one of 'E1'..'E5'.
    """
    st = inquiry
    exposure = getattr(st, 'exposure', None)
    if exposure is None:
        return 'E1'  # default fallback

    grouping = getattr(exposure, 'grouping', '')
    mapping = {
        'strict_majority_ties_low': 'E1',
        'three_level_treated_neighbor_fraction': 'E2',
        'pretreatment_core_collaborator_majority': 'E3',
        'exact_treated_neighbor_count': 'E4',
        'any_treated_neighbor': 'E5',
    }
    return mapping.get(grouping, 'E1')


def worksheet(bundle, raw, *, query_id, packet, context, information):
    """Unapproved fingerprints only, never a scientific approval generator.

    Identical to original but without D2/E1 assumption.
    """
    ids.resolve_reading(bundle, raw)
    if query_id not in bundle['question_slots']:
        raise ValueError('CURRENT_QUERY_REQUIRED')
    inquiry = context.core_port.bindings[query_id].inquiry
    return dict(version=VERSION, query_id=query_id, bundle_sha256=_sha(bundle),
        reading_sha256=_sha(raw), context_sha256=_sha(_context_snapshot(context)),
        packet_sha256=_sha(packet), inquiry_sha256=_sha(inquiry),
        information_sha256=_sha(information))


def _state(out, qid, state, reason):
    for view in out['query_views']:
        if view['query_id'] == qid:
            view.update(state=state, reason_code=reason, bounded_certificate_replayed=False)
    if 'point_assessment' in out:
        _result_row(out, qid, dict(query_id=qid, status=state, reason_code=reason,
            bounded_certificate_replayed=False))
    states = {v['state'] for v in out['query_views']}
    out['state'] = next(iter(states)) if len(states) == 1 else 'MIXED'
    out['reason_code'] = reason
    return out


def _result_row(out, qid, row):
    results = out.setdefault('identification', {}).setdefault('results', [])
    out['identification']['results'] = [row if r['query_id'] == qid else r for r in results]


def _make_route(inquiry):
    """Dynamically construct the route string for the given inquiry."""
    design_kind = _resolve_design_kind(inquiry)
    exposure_kind = _resolve_exposure_kind(inquiry)
    return f'BOUNDED_POLICY_MEAN_{design_kind}_{exposure_kind}'


def submit(bundle, raw, *, query_id, packet=None, context=None, information=None,
           bounded_review=None, submission_review=None, assignment_review=None,
           synthetic_protocol_selected=False, design_kind=None, exposure_kind=None):
    """Generalized submit with optional explicit design/exposure override."""
    out = ids.preview(bundle, raw)
    out.update(bounded_version=VERSION, bounded_backend_called=False,
               bounded_certificate_replayed=False)
    if 'question_binding' not in out or out['assignment_review']['state'] != 'REVIEW_REQUIRED':
        return out
    view = next((v for v in out['query_views'] if v['query_id'] == query_id), None)
    if view is None:
        out.update(state='CHECK_BLOCKED', reason_code='CURRENT_QUERY_REQUIRED')
        return out
    if view['state'] != 'REVIEW_REQUIRED':
        return out
    if synthetic_protocol_selected is not True or packet is None or context is None:
        return _state(out, query_id, 'REVIEW_REQUIRED', 'INDEPENDENT_SCIENTIFIC_CONTEXT_REQUIRED')
    if information is None:
        return _state(out, query_id, 'NEEDS_INPUT', 'EXPLICIT_A4_VALUES_AND_BOUNDS_REQUIRED')
    if bounded_review is None or submission_review is None or assignment_review is None:
        return _state(out, query_id, 'REVIEW_REQUIRED', 'SEPARATE_BOUNDED_AND_EXISTING_REVIEWS_REQUIRED')
    try:
        if type(information) is not BoundedMeanInformation or type(bounded_review) is not ReviewedBoundedPolicy:
            raise ValueError('SEPARATE_TYPED_BOUNDED_REVIEW_REQUIRED')
        reviewed = ReviewedBoundedPolicy.model_validate(bounded_review.model_dump())
        expected = worksheet(bundle, raw, query_id=query_id, packet=packet,
                              context=context, information=information)
        if any(getattr(reviewed, k) != v for k, v in expected.items()):
            raise ValueError('BOUNDED_REVIEW_STALE')
        inquiry = context.core_port.bindings[query_id].inquiry
        validate_model(inquiry, information)
    except BoundedPolicyUnavailable as exc:
        return _state(out, query_id, exc.state, exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError, ZeroDivisionError):
        return _state(out, query_id, 'CHECK_BLOCKED', 'BOUNDED_INFORMATION_OR_REVIEW_REJECTED')

    base = submit_point(bundle, raw, 'FIXED_POLICY', packet=packet, context=context,
        submission_review=submission_review, assignment_review=assignment_review,
        synthetic_protocol_selected=True, contract=ids.CONTRACT)
    out.update(base)
    out['point_assessment'] = deepcopy(base)
    selected = next(v for v in base['query_views'] if v['query_id'] == query_id)
    allowed = (selected['state'] == 'CORE_POINT' and selected.get('route') == 'R2_MEAN_SIGNATURE'
        or selected['state'] == 'UNSUPPORTED' and selected.get('reason_code') == 'ZERO_POLICY_SIGNATURE_SUPPORT')
    if not base.get('core_called') or not allowed:
        return out

    # Resolve design/exposure kinds.
    dk = design_kind or _resolve_design_kind(inquiry)
    ek = exposure_kind or _resolve_exposure_kind(inquiry)

    out['bounded_backend_called'] = True
    try:
        certificate = solve(inquiry, information, design_kind=dk, exposure_kind=ek)
        if not _replay(certificate, inquiry=inquiry, information=information):
            raise ValueError('INDEPENDENT_BOUNDED_REPLAY_FAILED')
    except BoundedPolicyUnavailable as exc:
        return _state(out, query_id, exc.state, exc.reason)
    except (ValueError, TypeError, KeyError, AttributeError, ZeroDivisionError):
        return _state(out, query_id, 'CHECK_BLOCKED', 'BOUNDED_PROOF_REJECTED')

    route = _make_route(inquiry)
    out['bounded_certificate_replayed'] = True
    out['bounded_result'] = certificate
    out['bounded_review_receipt'] = dict(expected, review_sha256=_sha(reviewed),
        approval_kind='SEPARATE_SYNTHETIC_ASSERTION_NOT_IDENTITY_AUTHENTICATION')
    _result_row(out, query_id, dict(query_id=query_id, status=certificate['status'],
        route=route, identified_interval=[certificate['lower'], certificate['upper']],
        bounded_certificate_sha256=certificate['certificate_sha256'],
        bounded_certificate_replayed=True, verification_level='FINITE_MEAN_MODEL_REPLAY'))
    for view in out['query_views']:
        if view['query_id'] == query_id:
            view.update(state=certificate['status'], route=route,
                reason_code=None, bounded_certificate_replayed=True,
                identified_interval=[certificate['lower'], certificate['upper']],
                sharp=True, informative=certificate['informative'])
    states = {v['state'] for v in out['query_views']}
    out['state'] = next(iter(states)) if len(states) == 1 else 'MIXED'
    out['reason_code'] = None
    return out


def _replay(certificate, inquiry, information):
    """Verify the certificate is self-consistent. Uses bounded_policy_verify.replay."""
    from cfm_id.bounded_policy_verify import replay
    return replay(certificate, inquiry=inquiry, information=information)