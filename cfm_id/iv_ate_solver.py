"""Sharp binary-IV ATE bounds with exact primal and dual certificates."""
from .iv_contract import validate_observed, IVInputError
from .iv_types import observed_constraint_system, model_descriptor
from .iv_exact_transport import problem, contradiction, endpoint
from networkx import NetworkXException


def build_lp(observed, *, monotonicity=False):
    return observed_constraint_system(observed,monotonicity=monotonicity)


def solve_ate_bounds(observed, *, monotonicity=False):
    try:
        law=validate_observed(observed)
        types,edges,masses=problem(law,monotonicity)
        model=model_descriptor(monotonicity,"ATE")
        cut=contradiction(edges,masses)
        if cut:
            return dict(status="INCOMPATIBLE",reason_code="OBSERVED_LAW_CONFLICTS_WITH_ACCEPTED_IV_TYPE_MODEL",
                        type_count=len(types),model=model,certificate=cut)
        lower=endpoint(types,edges,masses,1)
        upper=endpoint(types,edges,masses,-1)
        bounds=[lower[0],upper[0]]
        result=dict(status="SHARP_BOUNDS",estimand="ATE=E[Y(1)-Y(0)]",
                    target=dict(kind="ATE",outcome_domain="BINARY",treatment_domain="BINARY"),
                    bounds=list(map(float,bounds)),monotonicity=monotonicity,model=model,
                    types=list(map(list,types)),type_count=len(types),
                    solver="integer min-cost binary-IV transport",exact={"bounds":list(map(str,bounds))},
                    certificate=dict(kind="PRIMAL_DUAL_ENDPOINT_CERTIFICATE",independent_replay_required=True))
        for name,(value,witness,dual) in zip(("lower","upper"),(lower,upper)):
            result[name+"_objective"]=float(value)
            for suffix,vec in (("_witness",witness),("_dual",dual)):
                result[name+suffix]=list(map(float,vec))
                result["exact"][name+suffix]=list(map(str,vec))
        return result
    except (IVInputError, TypeError, ValueError, ArithmeticError, NetworkXException) as exc:
        return dict(status="CHECK_BLOCKED",reason_code=getattr(exc,"code","ATE_LP_NUMERICAL_FAILURE"),certificate=None)
