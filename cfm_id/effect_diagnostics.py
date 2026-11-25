"""Read-only local-effect evidence projection; no identification or replay.

The native staged executor and its named/linear proofs remain unchanged. Checks
here match saved record identities and ordered coordinates, not scientific truth.
"""
from copy import deepcopy
from .method_compat import native_id
from fractions import Fraction
from . import network_effect_dispatch as effects
from .business_dispatch import sha


def _last_stage(target):
    return ('LINEAR_COMPOSITION' if target['kind'] in ('DIRECT_EFFECT','LOCAL_TOTAL_EFFECT') and target['first'][0] == 0
            else 'COMPOSITION')


def attempts(plan, result, method_ids):
    recorded = result.get('attempts', [])
    if not recorded and result.get('backend_called') is not True:
        return {}
    if method_ids != {effects.METHOD}:
        raise ValueError('DIAGNOSTIC_EXACT_LOCAL_EFFECT_METHOD_REQUIRED')
    stages = ['ANCHOR', _last_stage(plan['proposed_target'])]
    actual = [r.get('stage') for r in recorded]
    if (actual != stages[:len(actual)] or len(actual) > len(stages)
            or any(r.get('method', effects.METHOD) != effects.METHOD for r in recorded)):
        raise ValueError('DIAGNOSTIC_INVALID_LOCAL_EFFECT_STAGES')
    # ANCHOR is one starting arm, not the whole population or effect.
    complete = actual == stages and all(r.get('state') == 'POINT' for r in recorded)
    state = ('POINT' if complete and result.get('state') == 'POINT' else
             'NOT_APPLICABLE' if result.get('state') == 'UNSUPPORTED' else 'NOT_ESTABLISHED')
    return {effects.METHOD: dict(state=state, stage_attempts=deepcopy(recorded),
        reason_code=result.get('reason_code') or (recorded[-1].get('reason_code') if recorded else None),
        origin='EXISTING_LOCAL_EFFECT_EXECUTOR_RECORD')}


def _terms(rows):
    coordinates = [(r['node_id'], r['own_treatment'], r['exposure_state']) for r in rows]
    if len(set(coordinates)) != len(rows):
        raise ValueError('duplicate local coordinates')
    return {k: Fraction(r['coefficient']) for k,r in zip(coordinates, rows)}


def check_answer(plan, answer, attempt):
    """Check saved proof/summary agree on target and input, without certifying it."""
    try:
        target = plan['proposed_target']; first,second = target['first'],target['second']
        if (target['kind'] not in effects.TARGET_KINDS or target['operation'] != 'FIRST_MINUS_SECOND'
                or target['remaining_assignment'] != 'ORIGINAL_DESIGN_CONDITIONAL'
                or not attempt or attempt['state'] != 'POINT'):
            raise ValueError('target or execution')
        if ((target['kind'] == 'DIRECT_EFFECT' and not (first[0] != second[0] and first[1] == second[1]))
                or (target['kind'] == 'SPILLOVER_EFFECT' and not (first[0] == second[0] and first[1] != second[1]))
                or (target['kind'] == 'LOCAL_TOTAL_EFFECT' and not (first[0] != second[0] and first[1] != second[1]))):
            raise ValueError('effect kind')
        claim, certificate, native = (answer[k] for k in ('mathematical_claim','certificate','native_evidence'))
        if (claim['kind'] != 'POINT' or certificate['verification_status'] != 'VERIFIED'
                or len(certificate['results']) != 1):
            raise ValueError('one effect required')
        summary = certificate['results'][0]
        reverse = _last_stage(target) == 'LINEAR_COMPOSITION'
        if reverse:
            if certificate['contract_version'] != 'network-local-effect-linear-evidence-1':
                raise ValueError('linear envelope')
            proof = native; request = proof['recipe']['supplied_terms']; kind = 'CUSTOM_LINEAR'
        else:
            if (native['query_type'] != 'EFFECT_BUNDLE' or native['status'] != 'POINT'
                    or native['route'] != native_id(effects.METHOD)):
                raise ValueError('named effect envelope')
            bundle = native['result']
            if (len(bundle['results']) != 1 or len(bundle['requests']) != 1
                    or certificate['query_count'] != 1 or bundle['verification_status'] != 'VERIFIED'
                    or certificate['bundle_sha256'] != bundle['bundle_sha256']):
                raise ValueError('bundle')
            proof = bundle['results'][0]; request = bundle['requests'][0]
            kind = {'DIRECT_EFFECT':'DIRECT','SPILLOVER_EFFECT':'SPILLOVER','LOCAL_TOTAL_EFFECT':'TOTAL'}[target['kind']]
            if (sha(proof['source_batch']) != sha(bundle['source_batch'])
                    or sha(proof['a4_source']) != sha(bundle['a4_source']) or request['kind'] != kind):
                raise ValueError('bundle inputs')
        weights = dict(zip(target['node_order'], target['unit_weights']))
        # Signed target coordinates only; no support or identified formula calculation.
        expected = {(n, arm[0], arm[1]): sign*Fraction(weights[n])
                    for n in target['evaluation_population'] for arm,sign in ((first,1),(second,-1))}
        if (_terms(summary['constituent_arms']) != expected or _terms(proof['terms']) != expected
                or (reverse and _terms(request) != expected)
                or summary['kind'] != kind or proof['recipe']['kind'] != kind
                or summary['status'] != 'POINT' or proof['status'] != 'POINT'
                or summary['verification_status'] != 'VERIFIED' or proof['verification_status'] != 'VERIFIED'
                or summary['target_fingerprint'] != claim['target_fingerprint']
                or proof['target_fingerprint'] != claim['target_fingerprint']
                or summary['identified_functional'] != claim['expression']
                or proof['identified_functional'] != claim['expression']
                or summary['certificate_sha256'] != proof['certificate_sha256']
                or sha([proof['source_batch']['template'],proof['a4_source'],request]) != answer['reviewed_input_sha256']):
            raise ValueError('target, expression or input identity')
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError) as exc:
        raise ValueError('DIAGNOSTIC_INCOHERENT_LOCAL_EFFECT_RECORD') from exc


def effect_view(plan):
    facts = plan.get('facts') or {}; target = plan.get('proposed_target') or {}
    return dict(declared_target=deepcopy(facts.get('target')), ordered_target=deepcopy(target),
        target_kind_origin=deepcopy(plan.get('target_kind_origin')),
        origin='CURRENT_NATIVE_PLAN', checked_here=False,
        target_prepared=bool(target),
        definitions=dict(DIRECT_EFFECT='同伴状态相同，比较自身两种处理状态；保留第一端减第二端。',
                         SPILLOVER_EFFECT='自身处理相同，比较两种同伴状态；保留第一端减第二端。',
                         LOCAL_TOTAL_EFFECT='自身和同伴状态均改变的设计平均局部总效应，不是完整固定政策差值。'),
        averaging_note='本方法要求：其余完整安排在各端自身/同伴条件下按原试点概率平均；是否已声明见原生目标，不补填未知规则，也不假定均值仅依赖暴露。',
        population_note='评价全体、指定子集或单个对象均保留原声明；名单须在分配前固定。')


def decorate(item, plan, answer, result=None):
    target = plan.get('proposed_target') or {}
    item['calculation_contract'] = 'DESIGN_CONDITIONAL_LOCAL_ARM_COMPOSITION'
    item['target_kind'] = target.get('kind')
    item['anchor_is_complete_effect'] = False
    item['target_semantics_note'] = '原设计条件平均；不将局部效应替换为固定政策差值或均值充分性目标。'
    if answer:
        item['certificate']['calculation_reported'] = (('REVERSED_TOTAL_NATIVE_LINEAR_COMPOSITION'
            if target['kind']=='LOCAL_TOTAL_EFFECT' else 'REVERSED_DIRECT_NATIVE_LINEAR_COMPOSITION')
            if _last_stage(target) == 'LINEAR_COMPOSITION' else 'NATIVE_NAMED_EFFECT_COMPOSITION')
        item['certificate']['target_fingerprint'] = answer['mathematical_claim']['target_fingerprint']
