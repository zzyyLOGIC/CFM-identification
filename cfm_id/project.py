"""Student/public starting point with one maintained reading configuration.

This prepares requests, never supplies model replies or scientific approvals.
Existing business_intake APIs retain their historical explicit defaults.
"""
from importlib.resources import files
import argparse
import json
from pathlib import Path
from . import business_intake
from .business_reading_config import ReadingConfig
from .business_dispatch import prepare_reader, inspect_methods, execute
from .method_matching import explain as explain_method_plan
from .business_case import prepare_case, execute_case
from .intake_conflict_review import review_conflict


def reading_config():
    return ReadingConfig.model_validate_json(files('cfm_id').joinpath('configuration/reading.json').read_text('utf8'))


def start(case):
    return business_intake.start_configured(case, reading_config())


def direct_then_verify(case, call, *, network=None, network_focus=False, population_ate=False, clarification_handoff=None):
    """Preserve the draft; optionally source-audit plain ATE before native dispatch."""
    from cfm_id_llm.schemas import BusinessCase
    from cfm_id_llm.direct_answer import network_request
    from .direct_verification import verify
    if isinstance(case,BusinessCase):
        case=case.model_dump(mode="json")
    # An explicitly imported network is stronger routing evidence than wording
    # heuristics (e.g. "合作站" need not contain the keyword "邻居"). This only
    # chooses the existing response contract; it grants no scientific license.
    draft = call(network_request(case, network_focus=network_focus or network is not None), "direct_draft")
    report=verify(case, draft, network=network, network_focus=network_focus)
    if population_ate:
        from . import joint_natural_entry
        from . import iv_natural_entry
        if iv_natural_entry.proposed(case,draft):
            prepared=iv_natural_entry.prepare(case,report,call)
            if prepared is not None:return prepared
        from cfm_id_llm import network_source_route
        network_readers={'NETWORK_OBSERVATIONAL_EFFECTS','NETWORK_OBSERVATIONAL_POLICY',
                         'NETWORK_FINITE_POLICY','NETWORK_JOINT_MEANS','NETWORK_LOCAL_BUNDLE'}
        hints=joint_natural_entry.route_hints(draft)
        symbolic_fallback=None
        if 'SYMBOLIC_MEAN_JOINT' in hints:
            from . import symbolic_mean_entry
            prepared=symbolic_mean_entry.prepare(case,report,call)
            entry=(prepared or {}).get('joint_entry',{})
            if network is None or entry.get('reason_code')!='ADDITIONAL_RESTRICTIONS_NOT_EXPRESSED':
                return prepared
            # An imported object network may have been sent to the abstract
            # mean reader by a mistaken draft hint. Inspect source attributes
            # before treating its network premises as unsupported restrictions.
            # Keep the stopped attempt; a new reader must recover and audit
            # every premise from the unchanged sources, never discard extras.
            symbolic_fallback=prepared
        if symbolic_fallback is not None or hints.intersection(network_readers) or report.get('local_targets') or (network is not None and not hints.difference({'OTHER'})):
            # A draft can solve a different target and hint at the wrong reader.
            # Independently read scope attributes before exposing its gaps.
            scope=None;feedback=None;route_attempts=[]
            for number in range(2):
                try:
                    raw=call(network_source_route.request(case,feedback,clarification_handoff),
                             'network_source_route'+('_retry1' if number else ''))
                    scope=network_source_route.check(case,raw,clarification_handoff)
                    route_attempts.append(dict(scope=scope));break
                except (ValueError,TypeError,KeyError) as exc:
                    feedback=str(exc)[:2000];route_attempts.append(dict(error=feedback))
            selected=network_source_route.select(scope) if scope else None
            if (selected is None and scope and not report.get('independent_replay')
                    and (report.get('clarification_questions') or any(
                        c.get('code')=='ANSWER_CONTRACT' and c.get('state')=='CONFLICT'
                        for c in report.get('checks',[])))
                    and scope['single_question']['value'] is True
                    and scope['target']['value']=='LOCAL_CONTRAST'
                    and scope['assignment']['value']=='RANDOMIZED'):
                # A draft-level gap or malformed answer is not a source verdict.
                # The independent scope found an actual randomized local study;
                # use the existing full reader to audit the design and remaining
                # gaps before asking the user to repeat a fact already supplied.
                # This neither repairs the draft nor grants scientific approval.
                selected='NETWORK_LOCAL_BUNDLE'
            if selected is None:
                if symbolic_fallback is not None:
                    symbolic_fallback['reader_selection']=dict(reader='SYMBOLIC_MEAN_JOINT',
                        reason='NO_SOURCE_SUPPORTED_NETWORK_REPLACEMENT',source_scope=scope,
                        attempts=route_attempts,scientific_approval=False)
                    return symbolic_fallback
                if scope and scope['single_question']['value'] is True and scope['target']['value']=='LOCAL_CONTRAST' and scope['assignment']['value']=='RANDOMIZED':
                    # This is the existing direct-verification network route,
                    # not one of the additional dedicated reading contracts.
                    # Keep its real verdict; do not ask finite-model questions.
                    report['reader_selection']=dict(reader='DIRECT_NETWORK_VERIFICATION',source_scope=scope,
                        attempts=route_attempts,scientific_approval=False)
                    return report
                if not hints.intersection(network_readers) and scope:
                    # An uploaded network is only a reason to inspect scope.
                    # It does not invalidate a different existing native path.
                    report['reader_selection']=dict(reader=None,source_scope=scope,
                        attempts=route_attempts,scientific_approval=False)
                    return report
                r=joint_natural_entry.stop(joint_natural_entry.base(report,case),
                    'READING_RECHECK_REQUIRED','SOURCE_READER_SCOPE_UNRESOLVED',
                    '后台尚未将原问题对应到合适的读取入口，未执行识别；不需要为入口选择问题补写研究条件。')
                r['reader_selection']=dict(source_scope=scope,attempts=route_attempts,scientific_approval=False)
                return r
            from . import observational_effect_entry,network_existing_entry,local_bundle_entry
            module=(local_bundle_entry if selected=='NETWORK_LOCAL_BUNDLE' else
                    observational_effect_entry if selected=='NETWORK_OBSERVATIONAL_EFFECTS' else
                    network_existing_entry if selected in network_existing_entry.FAMILIES else joint_natural_entry)
            def scoped_call(request,stage):
                if clarification_handoff and stage.startswith(('joint_source_read','joint_source_format','joint_source_audit','joint_audit_format')):
                    request=dict(request);body=json.loads(request['user_prompt'])
                    body['clarification_handoff_not_evidence']=clarification_handoff
                    request['user_prompt']=json.dumps(body,ensure_ascii=False)
                    request['system_prompt']+='\n对照上次已审核的目标及本次回答。仅回答科学条件不能变更原目标；真实目标变更仍按新原文读取。旧读稿不作为原文证据或科学批准，全部新读稿仍须审核。'
                if stage.startswith('joint_source_audit') or stage=='joint_audit_format_retry':
                    request=dict(request);body=json.loads(request['user_prompt'])
                    body['reader_scope_to_verify']=scope
                    body['reader_scope_contract']=network_source_route.RULES
                    body['fields']['coverage']['reader_scope_to_verify']=scope
                    if clarification_handoff:body['fields']['coverage']['clarification_handoff_not_evidence']=clarification_handoff
                    request['user_prompt']=json.dumps(body,ensure_ascii=False)
                    request['system_prompt']+='\n独立核对reader_scope_to_verify与原文及当前候选是否一致，包含实际分配方式和局部状态/完整名单的区别；路线提示不是证据，不要沿错误入口改问或索要该题不需要的材料。范围不符在coverage中判READING_ERROR。'
                return call(request,stage)
            prepared=module.prepare(case,report,scoped_call)
            recovery=None
            # A source auditor can identify that the chosen contract cannot
            # express the question. Reconsider source attributes once; never
            # try methods until one happens to identify a different target.
            entry=(prepared or {}).get('joint_entry',{})
            disputes=[f for attempt in entry.get('attempts',[]) for f in attempt.get('audit',{}).get('findings',[])
                if f['verdict']=='READING_ERROR' and f['field'] in ('family','coverage','target','facts.target','target_scope_crosscheck')]
            if prepared is None or (entry.get('state')=='READING_RECHECK_REQUIRED' and disputes):
                recovery=dict(original_reader=selected,original_scope=scope,source_disputes=disputes,
                    previous_attempts=entry.get('attempts',[]))
                try:
                    raw=call(network_source_route.request(case,dict(
                        selected_reader=selected,source_disputes=disputes,
                        instruction='来源审核认为当前入口无法完整表达原问题。重新只按原文判定目标和实际安排；先前分类及审核意见都不是证据。不得改问一个较易识别的问题。'),clarification_handoff),
                        'network_source_route_recovery')
                    new_scope=network_source_route.check(case,raw,clarification_handoff)
                    new_selected=network_source_route.select(new_scope)
                    recovery.update(rechecked_scope=new_scope,rechecked_reader=new_selected)
                    # Corrected attributes can still select the same reader
                    # (one subgroup question was mistaken for multiple ones).
                    # Re-audit under the corrected scope once, rather than
                    # leaving the obsolete scope attached to a sound reading.
                    attributes=lambda value:{k:v.get('value') for k,v in value.items()
                        if isinstance(v,dict) and 'value' in v}
                    if new_selected and (new_selected!=selected or attributes(new_scope)!=attributes(scope)):
                        selected=new_selected;scope=new_scope
                        module=(local_bundle_entry if selected=='NETWORK_LOCAL_BUNDLE' else
                            observational_effect_entry if selected=='NETWORK_OBSERVATIONAL_EFFECTS' else
                            network_existing_entry if selected in network_existing_entry.FAMILIES else joint_natural_entry)
                        def recovered_call(request,stage):
                            return scoped_call(request,stage+'_rerouted')
                        prepared=module.prepare(case,report,recovered_call)
                except (ValueError,TypeError,KeyError) as exc:
                    recovery['error']=str(exc)[:2000]
            if prepared is None:
                prepared=joint_natural_entry.stop(joint_natural_entry.base(report,case),
                    'READING_RECHECK_REQUIRED','SOURCE_READER_SCOPE_MISMATCH',
                    '原问题与本次读取入口不一致，尚未执行识别；不要求补写该入口的研究条件。')
            prepared['reader_selection']=dict(reader=selected,reason='INDEPENDENT_SOURCE_ATTRIBUTES',
                original_hints=sorted(joint_natural_entry.route_hints(draft)),source_scope=scope,
                attempts=route_attempts,scientific_approval=False)
            if recovery is not None:prepared['reader_selection']['recovery']=recovery
            if symbolic_fallback is not None:
                prepared['reader_selection']['previous_symbolic_entry']=symbolic_fallback['joint_entry']
            return prepared
        from . import observational_effect_entry
        if observational_effect_entry.proposed(case,draft):
            prepared=observational_effect_entry.prepare(case,report,call)
            if prepared is not None:
                prepared['reader_selection']=observational_effect_entry.reader_selection(draft)
                return prepared
        from . import network_existing_entry
        if network_existing_entry.proposed(case,draft):
            prepared=network_existing_entry.prepare(case,report,call)
            if prepared is not None:return prepared
        from . import joint_natural_entry
        if joint_natural_entry.proposed(case,draft):
            prepared=joint_natural_entry.prepare(case,report,call)
            if prepared is not None:return prepared
    if population_ate and not network_focus:
        from . import population_ate_entry
        if population_ate_entry.eligible(report,network):
            prepared=population_ate_entry.prepare(case,report,call)
            if prepared is not None:return prepared
    return report


def read_compact(case, call, *, on_disputes=None):
    """Read once, then recheck only disputed fields. The caller supplies the model transport."""
    from cfm_id_llm import compact_study as reader
    from cfm_id_llm.schemas import BusinessCase
    from .compact_entry import plan
    if isinstance(case,BusinessCase):
        case=case.model_dump(mode="json")
    raw=call(reader.request(case),"compact_read")
    issues=reader.inspect(raw,case)
    if issues:
        if on_disputes is not None:
            on_disputes(issues)
        focused=reader.focus(case,raw,issues)
        if focused is not None:
            raw=reader.apply_focus(raw,call(focused,"compact_focus"),issues)
    return plan(case,raw)


def confirm_compact(prepared, review, *, authority):
    """Apply only the methods admitted by a source-bound independent review."""
    from .compact_entry import complete
    return complete(prepared,review,authority=authority)


def diagnose_methods(intake, query_id, **options):
    """Read-only method view through the usual reading/source/model gates."""
    from .method_diagnostics import inspect
    return inspect(intake, query_id, **options)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    commands=p.add_subparsers(dest='command',required=True)
    commands.add_parser('config',help='Print the single maintained reading configuration')
    create=commands.add_parser('start',help='Prepare A0 from a BusinessCase JSON; makes no API call')
    create.add_argument('--input',type=Path,required=True)
    create.add_argument('--output',type=Path,required=True)
    args=p.parse_args(argv)
    if args.command=='config':
        print(reading_config().model_dump_json(indent=2));return 0
    session=start(business_intake.read_json(args.input));args.output.mkdir(parents=True,exist_ok=False)
    business_intake.save(session,args.output/'intake.json')
    business_intake.write_json(args.output/'request.json',business_intake.prepare_request(session))
    business_intake.write_json(args.output/'reading_config.json',reading_config().model_dump(mode='json'))
    print(json.dumps(dict(state='REQUEST_PREPARED',api_calls=0,output=str(args.output)),ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
