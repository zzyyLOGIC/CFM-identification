"""Binary monotone-IV feasibility and exact Wald ratio on the declared law."""
from math import isfinite
from networkx import NetworkXException
from .iv_contract import validate_observed, IVInputError
from .iv_types import model_descriptor
from .iv_exact_transport import problem, contradiction, endpoint


def identify_late(observed, *, assumptions_accepted=False, tol=1e-9):
    try:
        if isinstance(tol,bool) or not isfinite(tol) or not 0<tol<=1e-6:
            return dict(status="CHECK_BLOCKED",reason_code="INVALID_TOLERANCE",certificate=None)
        if assumptions_accepted is not True:
            return dict(status="REVIEW_REQUIRED",reason_code="IV_SCIENTIFIC_ASSUMPTIONS_NOT_REVIEWED",certificate=None)
        law=validate_observed(observed)
        types,edges,masses=problem(law,True)
        model=model_descriptor(True,"LATE")
        cut=contradiction(edges,masses)
        if cut:
            return dict(status="INCOMPATIBLE",reason_code="OBSERVED_LAW_CONFLICTS_WITH_MONOTONE_IV_MODEL",certificate=cut,model=model)
        first=sum((1 if z else -1)*d*p for (z,d,y),p in law.items())
        effect=sum((1 if z else -1)*y*p for (z,d,y),p in law.items())
        if not first:
            return dict(status="UNSUPPORTED",reason_code="NO_POSITIVE_COMPLIER_MASS_LATE_UNDEFINED",model=model,certificate=None)
        if any(isinstance(v,float) for v in observed.values()) and first<=tol:
            return dict(status="CHECK_BLOCKED",reason_code="FIRST_STAGE_NUMERICALLY_AMBIGUOUS",model=model,certificate=None)
        _,x,_=endpoint(types,edges,masses,1)
        value=effect/first
        return dict(status="POINT",estimand="LATE_FOR_COMPLIERS",late=float(value),
                    itt_y=float(effect),first_stage=float(first),logical_range=[-1.0,1.0],
                    compatibility_checked=True,latent_type_count=12,model=model,
                    exact=dict(late=str(value),itt_y=str(effect),first_stage=str(first),witness=list(map(str,x))),
                    certificate=dict(kind="MONOTONE_IV_FEASIBILITY",types=list(map(list,types)),witness=list(map(float,x))),
                    scientific_assumptions_are_reviewed_not_empirically_proved=True)
    except (IVInputError, TypeError, ValueError, ArithmeticError, NetworkXException) as exc:
        return dict(status="CHECK_BLOCKED",reason_code=getattr(exc,"code","IV_INPUT_OR_SOLVER_FAILURE"),certificate=None)
