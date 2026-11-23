"""Exact independent replay. Reconstruct the eight observations from latent types."""
from fractions import Fraction
from itertools import product
from math import isfinite
from .iv_contract import CELLS, rational, validate_observed
from .iv_types import model_descriptor


def actual_number(value, expected):
    return type(value) in (float,int) and isfinite(value) and value==float(expected)


def vector(display, exact, size):
    if not isinstance(display,list) or len(display)!=size:
        raise ValueError("IV_WITNESS_LENGTH")
    if exact is None:
        return [rational(x) for x in display]
    if not isinstance(exact,list) or len(exact)!=size:
        raise ValueError("IV_EXACT_WITNESS_LENGTH")
    values=[rational(x) for x in exact]
    if not all(actual_number(shown,x) for shown,x in zip(display,values)):
        raise ValueError("IV_PRESENTATION_DOES_NOT_MATCH_PROOF")
    return values


def verify(observed,result,monotonicity,target,tol):
    if not isinstance(result,dict) or type(monotonicity) is not bool or isinstance(tol,bool) or not isfinite(tol) or not 0<tol<=1e-6:
        return False
    law=validate_observed(observed)
    if result.get("model")!=model_descriptor(monotonicity,target):return False
    # Define the observation map directly from consistency, without the transport graph.
    types=[t for t in product((0,1),repeat=4) if not monotonicity or t[0]<=t[1]]
    cells=[(t[z],t[2+t[z]]) for t in types for z in (0,1)]
    def coordinates(k):
        return (2*cells[2*k][0]+cells[2*k][1],4+2*cells[2*k+1][0]+cells[2*k+1][1])
    b=[law[k] for k in CELLS]
    def feasible(x):
        prediction=[Fraction(0)]*8
        for k,mass in enumerate(x):
            for j in coordinates(k):prediction[j]+=mass
        return min(x)>=0 and prediction==b and sum(x)==1
    def linear(dual):
        return [sum(dual[j] for j in coordinates(k)) for k in range(len(types))]
    def dot(u,v):return sum(a*b for a,b in zip(u,v))
    cert=result["certificate"]
    if result["status"]=="INCOMPATIBLE":
        lam=vector(cert["lambda"],cert.get("exact_lambda"),8)
        margin=-dot(b,lam)
        norm=sum(map(abs,lam))
        return (cert["kind"]=="FARKAS_INCOMPATIBILITY" and min(linear(lam))>=0 and margin>0 and norm<=1
                and actual_number(cert["normalization_l1"],norm) and actual_number(cert["contradiction_margin"],margin)
                and ("exact_margin" not in cert or rational(cert["exact_margin"])==margin))
    exact=result.get("exact",{})
    if target=="LATE":
        witness=vector(cert["witness"],exact.get("witness"),len(types))
        dy=sum(law[1,d,1]-law[0,d,1] for d in (0,1))
        first=sum(law[1,1,y]-law[0,1,y] for y in (0,1))
        if first<=0 or not feasible(witness):return False
        vals=dict(late=dy/first,itt_y=dy,first_stage=first)
        return (result["status"]=="POINT" and result["estimand"]=="LATE_FOR_COMPLIERS"
                and result["compatibility_checked"] is True and result["latent_type_count"]==12
                and result["logical_range"]==[-1,1] and cert["kind"]=="MONOTONE_IV_FEASIBILITY"
                and cert["types"]==list(map(list,types)) and all(actual_number(result[k],x) for k,x in vals.items())
                and (not exact or all(rational(exact[k])==x for k,x in vals.items())))
    if not (result["status"]=="SHARP_BOUNDS" and result["estimand"]=="ATE=E[Y(1)-Y(0)]"
            and result["target"]==dict(kind="ATE",treatment_domain="BINARY",outcome_domain="BINARY")
            and cert==dict(kind="PRIMAL_DUAL_ENDPOINT_CERTIFICATE",independent_replay_required=True)
            and result["monotonicity"] is monotonicity and result["type_count"]==len(types)
            and result["types"]==list(map(list,types))):return False
    bounds=vector(result["bounds"],exact.get("bounds"),2)
    costs=[t[3]-t[2] for t in types]
    for label,bound,sign in zip(("lower","upper"),bounds,(1,-1)):
        x=vector(result[label+"_witness"],exact.get(label+"_witness"),len(types))
        lam=vector(result[label+"_dual"],exact.get(label+"_dual"),8)
        if not (feasible(x) and dot(costs,x)==bound==dot(b,lam) and actual_number(result[label+"_objective"],bound)
                and all(sign*(v-c)<=0 for v,c in zip(linear(lam),costs))):return False
    return bounds[0]<=bounds[1]


def replay(observed,result,monotonicity,target,tol):
    try:
        ok=verify(observed,result,monotonicity,target,tol)
    except (TypeError,KeyError,AttributeError,ArithmeticError,ValueError,IndexError):
        ok=False
    return dict(valid=ok,reason_code=None if ok else "EXACT_IV_CERTIFICATE_REPLAY_FAILED")
