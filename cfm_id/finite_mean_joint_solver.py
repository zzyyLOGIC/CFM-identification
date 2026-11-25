"""Exact bounded LP, decomposed by coupled coordinates; each block has a work limit.

Vertex and dual enumeration is a producer only. No optimizer status is a proof.
Certificates contain attained endpoints and exact dual/Farkas multipliers.
"""
from fractions import Fraction as F
from itertools import combinations
from math import comb
from cfm_id_bridge.scientific_binding import sha
from .finite_mean_joint_contract import VERSION, MODEL, rational as Q, validate
from .dag_backdoor_contract import fail

MAX_SYSTEMS = 100000


def linear(columns, target):
    n = len(columns)
    if not n: return [] if not any(target) else None
    a = [[col[i] for col in columns] + [v] for i,v in enumerate(target)]
    row = 0
    for j in range(n):
        pivot = next((i for i in range(row,len(a)) if a[i][j]), None)
        if pivot is None: return None
        a[row],a[pivot] = a[pivot],a[row]
        d = a[row][j]; a[row] = [v/d for v in a[row]]
        for i in range(len(a)):
            if i != row:
                d = a[i][j]; a[i] = [v-d*w for v,w in zip(a[i],a[row])]
        row += 1
    if any(not any(r[:n]) and r[n] for r in a): return None
    return [a[i][-1] for i in range(n)]


def dot(a,b): return sum((x*y for x,y in zip(a,b)), F(0))


def compile_rows(p):
    ids = [c.id for c in p.coordinates]
    rows = []
    def add(tag, values, rhs):
        rows.append((tag, [values.get(k,F(0)) for k in ids], rhs))
    for c in p.coordinates:
        lo,hi = Q(c.lower),Q(c.upper)
        if p.outcome_domain == 'BINARY': lo,hi = max(lo,F(0)),min(hi,F(1))
        add('lower:'+c.id,{c.id:F(-1)},-lo); add('upper:'+c.id,{c.id:F(1)},hi)
        if c.known is not None:
            add('known+:'+c.id,{c.id:F(1)},Q(c.known)); add('known-:'+c.id,{c.id:F(-1)},-Q(c.known))
    for c in p.constraints:
        if c.adoption != 'ADOPTED': continue
        a = {k:Q(v) for k,v in c.coefficients.items()}
        if c.relation in ('EQ','LE'): add('constraint+:'+c.id,a,Q(c.rhs))
        if c.relation in ('EQ','GE'): add('constraint-:'+c.id,{k:-v for k,v in a.items()},-Q(c.rhs))
    return ids, rows, [Q(p.target.get(k,'0')) for k in ids]


def _blocks(ids, rows, objective):
    groups = [{i} for i in range(len(ids))]
    for _,a,_ in rows:
        touched = {i for i,v in enumerate(a) if v}
        hits = [g for g in groups if g & touched]
        if hits:
            merged = set.union(*hits)
            groups = [g for g in groups if not g & merged] + [merged]
    for group in sorted(groups,key=min):
        indices = sorted(group)
        rr = [(tag,[a[i] for i in indices],b) for tag,a,b in rows if any(a[i] for i in indices)]
        yield indices,rr,[objective[i] for i in indices]


def _positive_combination(rows, objective, *, farkas=False):
    target = [*objective,F(-1)] if farkas else objective
    count = 0
    for size in range(1,min(len(target),len(rows))+1):
        for basis in combinations(rows,size):
            count += 1
            if count > MAX_SYSTEMS: fail('RESOURCE_LIMIT','EXACT_DUAL_SEARCH_LIMIT')
            columns = [[*a,b] if farkas else a for _,a,b in basis]
            weights = linear(columns,target)
            if weights is not None and all(w>=0 for w in weights):
                return {tag:str(w) for (tag,_,_),w in zip(basis,weights) if w}
    return None


def solve(problem):
    p = validate(problem)
    ids,rows,c = compile_rows(p)
    common = dict(version=VERSION, model=MODEL, problem_sha256=sha(p),
                  scientific_approval=False, production_admission=False, estimation_handoff_allowed=False)
    def done(**values):
        result = dict(common,**values); result['certificate_sha256'] = sha(result); return result
    for tag,a,b in rows:
        if not any(a) and b < 0:
            return done(status='INCOMPATIBLE',farkas={tag:str(-1/b)})
    worlds = [{},{}]; duals = [{},{}]
    for indices,rr,cc in _blocks(ids,rows,c):
        n = len(indices)
        if comb(len(rr),n) > MAX_SYSTEMS:
            fail('RESOURCE_LIMIT','EXACT_VERTEX_SEARCH_LIMIT')
        lo = hi = None
        for basis in combinations(rr,n):
            columns = [[a[j] for _,a,_ in basis] for j in range(n)]
            world = linear(columns,[b for _,_,b in basis])
            if world is None or any(dot(a,world)>b for _,a,b in rr): continue
            value = dot(cc,world)
            if lo is None or value<lo[0]: lo = value,world
            if hi is None or value>hi[0]: hi = value,world
        if lo is None:
            proof = _positive_combination(rr,[F(0)]*n,farkas=True)
            if proof is None: fail('CHECK_BLOCKED','INFEASIBILITY_CERTIFICATE_NOT_FOUND')
            return done(status='INCOMPATIBLE',farkas=proof)
        for side,extreme in enumerate((lo,hi)):
            world = extreme[1]
            direction = [-v for v in cc] if side==0 else cc
            active = [r for r in rr if dot(r[1],world)==r[2]]
            proof = {} if not any(direction) else _positive_combination(active,direction)
            if proof is None: fail('CHECK_BLOCKED','OPTIMALITY_CERTIFICATE_NOT_FOUND')
            duals[side].update(proof)
            worlds[side].update({ids[i]:str(v) for i,v in zip(indices,world)})
    endpoints = [Q(p.target_offset)+sum((Q(p.target.get(k,'0'))*Q(w[k]) for k in ids),F(0)) for w in worlds]
    return done(status='POINT' if endpoints[0]==endpoints[1] else 'PARTIAL',lower=str(endpoints[0]),upper=str(endpoints[1]),
                sharp=True,lower_world=worlds[0],upper_world=worlds[1],lower_dual=duals[0],upper_dual=duals[1],
                realization='BERNOULLI_PER_COORDINATE' if p.outcome_domain=='BINARY' else 'DETERMINISTIC_PER_COORDINATE')
