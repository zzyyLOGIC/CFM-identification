"""Explain actual candidate preparation, without changing an executable plan.

Every common business reader uses this format. Dedicated direct-answer,
population and explicit-specification paths keep their own admission contracts;
being outside this entry is never evidence that a theorem cannot identify.
"""
from copy import deepcopy

from . import capability_registry, method_definitions
from .method_compat import canonical_id
from cfm_id_bridge.scientific_binding import sha

VERSION = 'method-preparation-report/1'
REPORT_KEY = 'method_preparation_report'


def _pointer(parts):
    return '/' + '/'.join(str(p).replace('~', '~0').replace('/', '~1') for p in parts)


def _attributes(plan):
    """Reference exact parsed objects. Do not reconstruct them from labels."""
    refs = []
    roots = [('', plan)]
    for side, endpoint in plan.get('endpoint_plans', {}).items():
        roots.append((f'/endpoint_plans/{side}', endpoint))
    for prefix, source in roots:
        for key in ('proposed_target', 'contrast_target', 'query_scope'):
            if key in source:
                refs.append(dict(role='target', pointer=prefix + '/' + key))
        facts = source.get('facts') or {}
        for role, keys in (
            ('target', ('target',)), ('assignment', ('assignment', 'regime')),
            ('exposure', ('exposure',)), ('structure', ('study', 'conditioning')),
            ('information', ('information',)),
            ('scientific_declaration', ('assumptions', 'mean_sufficiency', 'bounded_model', 'first_stage_exclusion')),
        ):
            for key in keys:
                if key in facts:
                    refs.append(dict(role=role, pointer=prefix + '/facts/' + key))
    # DAG projections have their own validated graph/target/model objects.
    for i, row in enumerate(plan.get('methods', [])):
        if row.get('proposed_problem') is not None:
            refs.append(dict(role='dedicated_problem', pointer=f'/methods/{i}/proposed_problem'))
    return refs


def _rows(rows, allowed):
    result = {}
    for i, row in enumerate(rows):
        method = canonical_id(row['method'])
        if method not in allowed or method in result:
            raise ValueError('MATCH_REPORT_UNKNOWN_OR_DUPLICATE_METHOD')
        result[method] = (i, row)
    return result


def explain(plan, *, reader_id):
    """Return a non-authoritative report tied to the exact plan contents.

No solver, LLM or approval is called. Pending worksheet decisions are not
approved assumptions. Native exclusion codes are retained without inventing
a theorem explanation for an aggregate or undocumented stop.
"""
    binding = capability_registry.business_binding(reader_id)
    if plan.get('fact_family', reader_id) != reader_id:
        raise ValueError('MATCH_REPORT_READER_PLAN_MISMATCH')
    allowed = {m.method_id for m in binding.methods}
    planned = _rows(plan.get('methods', []), allowed)
    excluded = _rows(plan.get('exclusions', []), allowed)
    if set(planned) & set(excluded):
        raise ValueError('MATCH_REPORT_CONTRADICTORY_PLAN')
    clean = {k: v for k, v in plan.items() if k != REPORT_KEY}
    candidates = []
    for method in (m.method_id for m in binding.methods):
        shape = method_definitions.describe_binding(method)
        item = dict(method_id=method, **shape, status='NOT_ASSESSED',
            reason_code='NO_PREPARATION_DECISION_RECORDED', reason_origin='NO_RECORD',
            reason_scope='PREPARATION_ONLY', evidence_refs=[], required_reviews=[],
            theorem_applicability='NOT_ESTABLISHED', grants_execution=False)
        if method in planned:
            i, row = planned[method]
            ready = bool(row.get('reading_worksheet') and row.get('science_worksheet'))
            item.update(status='CANDIDATE_REQUIRES_REVIEW' if ready else 'PREPARATION_STOPPED',
                reason_code=row.get('reason_code') or 'CURRENT_INSPECTOR_PREPARED_THIS_METHOD',
                reason_origin='CURRENT_INSPECTOR', evidence_refs=[f'/methods/{i}'])
            for stage in ('reading', 'science'):
                sheet = row.get(stage + '_worksheet')
                if sheet:
                    item['required_reviews'].append(dict(stage=stage,
                        worksheet_sha256=sha(sheet),
                        native_binding={k: v for k, v in sheet.items() if k.endswith('_sha256')},
                        worksheet_ref=f'/methods/{i}/{stage}_worksheet',
                        condition_keys=list(sheet.get('decisions', {})), approval_checked_here=False))
        elif method in excluded:
            i, row = excluded[method]
            item.update(status='DECLARATION_OR_INFORMATION_UNRESOLVED'
                if row.get('unresolved') else 'EXCLUDED_BY_PREPARATION',
                reason_code=row['reason_code'], reason_origin='CURRENT_INSPECTOR',
                evidence_refs=[f'/exclusions/{i}'])
        elif plan.get('endpoint_plans'):
            # Both endpoints must use a common method/model. Preserve exact
            # endpoint reasons; do not pretend that intersecting IDs proves it.
            from .policy_methods import resolve, DIFFERENCE
            endpoint_method = resolve(method, DIFFERENCE).endpoint_method
            evidence = []
            for side, endpoint in plan['endpoint_plans'].items():
                for i, row in enumerate(endpoint.get('exclusions', [])):
                    if canonical_id(row['method']) == endpoint_method:
                        evidence.append(dict(endpoint=side, reason_code=row['reason_code'],
                            unresolved=row.get('unresolved', False),
                            pointer=_pointer(('endpoint_plans', side, 'exclusions', i))))
            if evidence:
                item.update(status='ENDPOINT_PREPARATION_INCOMPLETE',
                    reason_code='COMMON_ENDPOINT_METHOD_NOT_PREPARED', reason_origin='ENDPOINT_INSPECTORS',
                    endpoint_reasons=evidence, evidence_refs=[r['pointer'] for r in evidence])
        candidates.append(item)
    return dict(version=VERSION, reader_id=reader_id, source_plan_sha256=plan.get('plan_sha256'),
        source_record_sha256=sha(clean), source_state=plan.get('state'),
        source_reason_code=plan.get('reason_code'), attribute_refs=_attributes(plan),
        common_review_ref='/plan_worksheet' if plan.get('plan_worksheet') else None,
        clarification_questions=deepcopy(plan.get('clarification_questions', [])),
        unsupported_reasons=deepcopy(plan.get('unsupported_reasons', [])),
        candidates=candidates, scope='CURRENT_REGISTERED_READER_ONLY',
        other_entries='NOT_ASSESSED_USE_CAPABILITY_REGISTRY',
        is_approval=False, is_certificate=False, grants_execution=False,
        mathematical_applicability_checked=False, nonidentification_proved=False,
        automatic_fallback=False)


def attach(plan, *, reader_id):
    return dict(plan, **{REPORT_KEY: explain(plan, reader_id=reader_id)})


def verify_report(plan, report, *, reader_id):
    """Check only the descriptive record, not a proof or scientific approval."""
    try:
        return report == explain(plan, reader_id=reader_id)
    except (ValueError, KeyError, TypeError):
        return False
