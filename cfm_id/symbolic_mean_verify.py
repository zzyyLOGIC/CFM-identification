"""Independent exact verification of affine primal/dual identities and coverage.

No producer imports. Every invertible active set is checked for dual feasibility
to establish completeness, including degenerate and lower-dimensional cases.
"""
from fractions import Fraction as F
from itertools import combinations
from math import comb
from cfm_id_bridge.scientific_binding import sha
from .symbolic_mean_contract import VERSION,MODEL,Q,validate,vector,numeric_problem

def require(ok):
    if not ok:raise ValueError('SYMBOLIC_CERTIFICATE_INVALID')

def inverse(a):
    n=len(a);m=[list(row)+[F(i==j) for j in range(n)] for i,row in enumerate(a)]
    for j in range(n):
        pivot=next((i for i in range(j,n) if m[i][j]),None)
        if pivot is None:return None
        m[j],m[pivot]=m[pivot],m[j];v=m[j][j];m[j]=[x/v for x in m[j]]
        for i in range(n):
            if i!=j:
                v=m[i][j];m[i]=[x-v*y for x,y in zip(m[i],m[j])]
    return [row[n:] for row in m]

def original_rows(p):
    ids=[x.id for x in p.coordinates];names=[x.id for x in p.parameters];rr=[]
    zero=[F(0)]*(len(names)+1)
    def insert(name,k,sign,rhs):
        a=[F(0)]*len(ids);a[ids.index(k)]=F(sign);rr.append((name,a,rhs))
    for c in p.coordinates:
        insert('lower:'+c.id,c.id,-1,[-x for x in vector(c.lower,names)])
        insert('upper:'+c.id,c.id,1,vector(c.upper,names))
        if p.outcome_domain=='BINARY':
            insert('binary_lower:'+c.id,c.id,-1,zero.copy())
            insert('binary_upper:'+c.id,c.id,1,[F(1)]+zero[1:])
        if c.known is not None:
            insert('known+:'+c.id,c.id,1,vector(c.known,names))
            insert('known-:'+c.id,c.id,-1,[-x for x in vector(c.known,names)])
    for c in p.constraints:
        if c.adoption!='ADOPTED':continue
        a=[Q(c.coefficients.get(k,'0')) for k in ids];b=vector(c.rhs,names)
        if c.relation in ('LE','EQ'):rr.append(('constraint+:'+c.id,a,b))
        if c.relation in ('GE','EQ'):rr.append(('constraint-:'+c.id,[-v for v in a],[-v for v in b]))
    return ids,names,rr

def replay(cert,problem):
    try:_check(cert,validate(problem));return True
    except (ValueError,TypeError,KeyError,IndexError,AttributeError,ArithmeticError):return False

def _check(cert,p):
    keys={'version','model','problem_sha256','status','parameters','parameter_domain','lower','upper','enumerated_bases','invertible_bases',
        'sharp','scientific_approval','production_admission','estimation_handoff_allowed','interpretation','certificate_sha256'}
    require(set(cert)==keys and cert['version']==VERSION and cert['model']==MODEL and cert['status']=='SYMBOLIC_BOUNDS')
    require(cert['problem_sha256']==sha(p) and cert['certificate_sha256']==sha({k:v for k,v in cert.items() if k!='certificate_sha256'}))
    require(cert['sharp'] is True and all(cert[k] is False for k in ('scientific_approval','production_admission','estimation_handoff_allowed')))
    ids,names,rr=original_rows(p);n=len(ids);d=len(names)+1;c=[Q(p.target.get(k,'0')) for k in ids]
    require(cert['parameters']==names and cert['parameter_domain']==[dict(id=x.id,lower=x.lower,upper=x.upper) for x in p.parameters])
    require(comb(len(rr),n)<=100000 and cert['enumerated_bases']==comb(len(rr),n))
    lookup={};rowmap={row[0]:row for row in rr}
    for side in ('lower','upper'):
        lookup[side]={tuple(cell['basis']):cell for cell in cert[side]}
        require(len(lookup[side])==len(cert[side]))
    expected={side:set() for side in lookup};nonsingular=0
    for indices in combinations(range(len(rr)),n):
        base=[rr[i] for i in indices];a=[r[1] for r in base];inv=inverse(a)
        if inv is None:continue
        nonsingular+=1;nameset=tuple(r[0] for r in base)
        for side,sign in (('lower',-1),('upper',1)):
            dual=[sum((sign*c[i]*inv[i][j] for i in range(n)),F(0)) for j in range(n)]
            if any(v<0 for v in dual):continue
            expected[side].add(nameset);require(nameset in lookup[side]);cell=lookup[side][nameset]
            require(set(cell)=={'basis','world','dual','region','value'} and set(cell['world'])==set(ids))
            require(list(map(Q,cell['dual']))==dual)
            world=[list(map(Q,cell['world'][k])) for k in ids];require(all(len(w)==d for w in world))
            # Affine identity A_I x(theta) == b_I(theta), independent of solver.
            for _,normal,rhs in base:
                require(all(sum((normal[i]*world[i][j] for i in range(n)),F(0))==rhs[j] for j in range(d)))
            regions=[]
            for tag,normal,rhs in rr:
                residual=[sum((normal[i]*world[i][j] for i in range(n)),F(0))-rhs[j] for j in range(d)]
                if any(residual[1:]) or residual[0]>0:regions.append(dict(row=tag,le_zero=list(map(str,residual))))
            require(cell['region']==regions)
            value=[vector(p.target_offset,names)[j]+sum((c[i]*world[i][j] for i in range(n)),F(0)) for j in range(d)]
            require(list(map(Q,cell['value']))==value)
    require(cert['invertible_bases']==nonsingular)
    require(all(set(lookup[side])==expected[side] for side in expected))

def evaluate(cert,problem,parameters):
    """Instantiate certified pieces; no statistical estimate is asserted."""
    require(replay(cert,problem));p=validate(problem);numeric_problem(p,parameters)
    v=[F(1),*(Q(parameters[k]) for k in cert['parameters'])]
    calc=lambda a:sum((Q(x)*y for x,y in zip(a,v)),F(0))
    active={s:[cell for cell in cert[s] if all(calc(r['le_zero'])<=0 for r in cell['region'])] for s in ('lower','upper')}
    if not active['lower'] and not active['upper']:return dict(status='INCOMPATIBLE',parameters=parameters)
    require(bool(active['lower']) and bool(active['upper']))
    values={s:{calc(cell['value']) for cell in active[s]} for s in active}
    require(all(len(x)==1 for x in values.values()))
    lo,hi=(next(iter(values[s])) for s in ('lower','upper'));require(lo<=hi)
    return dict(status='POINT' if lo==hi else 'PARTIAL',lower=str(lo),upper=str(hi),sharp=True,parameters=parameters,
        lower_world={k:str(calc(w)) for k,w in active['lower'][0]['world'].items()},
        upper_world={k:str(calc(w)) for k,w in active['upper'][0]['world'].items()})
