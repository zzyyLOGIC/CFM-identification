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
from .business_case import prepare_case, execute_case
from .intake_conflict_review import review_conflict


def reading_config():
    return ReadingConfig.model_validate_json(files('cfm_id').joinpath('configuration/reading.json').read_text('utf8'))


def start(case):
    return business_intake.start_configured(case, reading_config())


def direct_then_verify(case, call, *, network=None, network_focus=False):
    """Draft once using the supplied transport, then check the same answer locally."""
    from cfm_id_llm.schemas import BusinessCase
    from cfm_id_llm.direct_answer import network_request
    from .direct_verification import verify
    if isinstance(case,BusinessCase):
        case=case.model_dump(mode="json")
    # An explicitly imported network is stronger routing evidence than wording
    # heuristics (e.g. "合作站" need not contain the keyword "邻居"). This only
    # chooses the existing response contract; it grants no scientific license.
    draft = call(network_request(case, network_focus=network_focus or network is not None), "direct_draft")
    return verify(case, draft, network=network, network_focus=network_focus)


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
