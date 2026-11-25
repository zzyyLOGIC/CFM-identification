"""Enumerate parametric optimal bases. Original numeric solvers are unchanged."""
from fractions import Fraction as F
from itertools import combinations
from math import comb
from cfm_id_bridge.scientific_binding import sha
from .symbolic_mean_contract import VERSION,MODEL,validate,vector,Q
from .finite_mean_joint_solver import linear
from .dag_backdoor_contract import fail

MAX_BASES=100000

def rows(p):
    names=[x.id for x in p.parameters];ids=[c.id for c in p.coordinates];rr=[]
    def add(tag,a,b):rr.append((tag,[a.get(k,F(0)) for k in ids],b))
    for c in p.coordinates:
        add('lower:'+c.id,{c.id:F(-1)},[-v for v in vector(c.lower,names)])
        add('upper:'+c.id,{c.id:F(1)},vector(c.upper,names))
        if p.outcome_domain=='BINARY':
            add('binary_lower:'+c.id,{c.id:F(-1)},[F(0)]*(len(names)+1))
            add('binary_upper:'+c.id,{c.id:F(1)},[F(1)]+[F(0)]*len(names))
        if c.known is not None:
            v=vector(c.known,names);add('known+:'+c.id,{c.id:F(1)},v);add('known-:'+c.id,{c.id:F(-1)},[-b for b in v])
    for c in p.constraints:
        if c.adoption!='ADOPTED':continue
        a={k:Q(v) for k,v in c.coefficients.items()};b=vector(c.rhs,names)
        if c.relation!='GE':add('constraint+:'+c.id,a,b)
        if c.relation!='LE':add('constraint-:'+c.id,{k:-v for k,v in a.items()},[-v for v in b])
    return ids,names,rr

def solve(problem):
    p=validate(problem);ids,names,rr=rows(p);n=len(ids);d=len(names)+1
    if comb(len(rr),n)>MAX_BASES:fail('RESOURCE_LIMIT','SYMBOLIC_BASIS_ENUMERATION_LIMIT')
    objective=[Q(p.target.get(k,'0')) for k in ids];offset=vector(p.target_offset,names)
    cells={'lower':[],'upper':[]};invertible=0
    for indices in combinations(range(len(rr)),n):
        base=[rr[i] for i in indices];matrix=[r[1] for r in base]
        columns=list(map(list,zip(*matrix)))
        solutions=[linear(columns,[r[2][j] for r in base]) for j in range(d)]
        if solutions[0] is None:continue
        invertible+=1;world=list(map(list,zip(*solutions)))
        # Only omit constant true inequalities. All parameter regions remain,
        # including empty ones; no guessed feasibility pruning is permitted.
        region=[]
        for tag,a,b in rr:
            residual=[sum((a[i]*world[i][j] for i in range(n)),F(0))-b[j] for j in range(d)]
            if any(residual[1:]) or residual[0]>0:region.append(dict(row=tag,le_zero=list(map(str,residual))))
        value=[offset[j]+sum((objective[i]*world[i][j] for i in range(n)),F(0)) for j in range(d)]
        for side,sign in (('lower',-1),('upper',1)):
            dual=linear(matrix,[sign*c for c in objective])
            if dual is not None and all(y>=0 for y in dual):
                cells[side].append(dict(basis=[r[0] for r in base],world={k:list(map(str,w)) for k,w in zip(ids,world)},
                    dual=list(map(str,dual)),region=region,value=list(map(str,value))))
    cert=dict(version=VERSION,model=MODEL,problem_sha256=sha(p),status='SYMBOLIC_BOUNDS',parameters=names,
        parameter_domain=[dict(id=x.id,lower=x.lower,upper=x.upper) for x in p.parameters],
        lower=cells['lower'],upper=cells['upper'],enumerated_bases=comb(len(rr),n),invertible_bases=invertible,
        sharp=True,scientific_approval=False,production_admission=False,estimation_handoff_allowed=False,
        interpretation='Each region gives an attained exact endpoint. No active region means incompatible model; outside the declared parameter domain no result is asserted.')
    cert['certificate_sha256']=sha(cert)
    return cert
