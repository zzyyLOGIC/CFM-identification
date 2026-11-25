"""Opt-in typed mathematical entry over a fixed registry; no business autoapproval."""
from copy import deepcopy
from .research_route_catalog import resolve,separate_entries
from .research_route_workflow import run_route

def _blocked(route_id,reason,*,state='CHECK_BLOCKED',model_family=None):
    return dict(route_id=route_id,model_family=model_family,state=state,reason_code=reason,
        mathematical_claim=None,certificate=None,independent_replay=False,backend_called=False,
        production_admission=False,estimation_handoff_allowed=False)

def _typed(cls,value):
    if type(value) is dict:return cls.model_validate(deepcopy(value))
    if type(value) is not cls:raise ValueError('EXACT_ROUTE_CONTRACT_TYPE_REQUIRED')
    # Frozen records may still contain mutated lists.
    return cls.model_validate(value.model_dump())

def run_registered_route(route_id,problem,*,review=None,research_protocol_selected=False):
    from . import dedicated_entries
    if dedicated_entries.resolve(route_id) is not None:
        try:
            result=dedicated_entries.run(route_id,problem,review if research_protocol_selected is True else None)
        except (ValueError,TypeError,KeyError,AttributeError):
            result=_blocked(route_id,'INVALID_ROUTE_PROBLEM_OR_REVIEW')
            from .entry_diagnostics import summarize
            result['entry_diagnostics']=summarize(result,operation=route_id)
        return dict(result,route_id=route_id,input_level='EXPLICIT_MATHEMATICAL_PROBLEM',business_reading_checked=False)
    try:registration=resolve(route_id)
    except ValueError:
        known=type(route_id) is str and any(route_id in [r['entry_id'],*r['route_ids']] for r in separate_entries())
        result=_blocked(route_id if type(route_id) is str else None,
            'SEPARATE_BUSINESS_ENTRY_REQUIRED' if known else 'ROUTE_NOT_REGISTERED_IN_THIS_ENTRY',
            state='UNSUPPORTED' if known else 'CHECK_BLOCKED')
    else:
        family=registration.capability.model_family
        try:
            p=_typed(registration.problem_type,problem)
            r=None if review is None else _typed(registration.review_type,review)
        except (ValueError,TypeError,KeyError,AttributeError):
            # No validation traceback containing user data in a published reason.
            result=_blocked(route_id,'INVALID_ROUTE_PROBLEM_OR_REVIEW',model_family=family)
        else:
            result=run_route(registration.adapter_type(),p,review=r,
                research_protocol_selected=research_protocol_selected)
    result.update(input_level='EXPLICIT_MATHEMATICAL_PROBLEM',business_reading_checked=False)
    from .entry_diagnostics import summarize
    result['entry_diagnostics']=summarize(result,operation=route_id)
    return result

