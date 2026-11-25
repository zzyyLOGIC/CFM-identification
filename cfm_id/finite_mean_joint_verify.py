"""Independent rational primal/dual and Farkas replay. No solver imports."""
from fractions import Fraction as F
from cfm_id_bridge.scientific_binding import sha
from .finite_mean_joint_contract import VERSION, MODEL, validate, rational as Q


def replay(cert, problem):
    try:
        _check(cert,validate(problem))
        return True
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, ArithmeticError):
        return False


def require(ok):
    if not ok: raise ValueError('JOINT_MEAN_CERTIFICATE_INVALID')


def _check(cert,p):
    common = {'version','model','problem_sha256','scientific_approval','production_admission',
              'estimation_handoff_allowed','status','certificate_sha256'}
    extra = {'farkas'} if cert.get('status')=='INCOMPATIBLE' else {
        'lower','upper','sharp','lower_world','upper_world','lower_dual','upper_dual','realization'}
    require(set(cert)==common|extra and cert['version']==VERSION and cert['model']==MODEL)
    require(cert['problem_sha256']==sha(p) and cert['certificate_sha256']==sha({k:v for k,v in cert.items() if k!='certificate_sha256'}))
    require(all(cert[k] is False for k in ('scientific_approval','production_admission','estimation_handoff_allowed')))
    ids = {c.id for c in p.coordinates}; rows = {}
    # Reconstruct sparse inequalities directly from the original problem, not producer rows.
    for c in p.coordinates:
        low,high = Q(c.lower),Q(c.upper)
        if p.outcome_domain=='BINARY': low,high = max(low,F(0)),min(high,F(1))
        rows['lower:'+c.id] = ({c.id:F(-1)},-low)
        rows['upper:'+c.id] = ({c.id:F(1)},high)
        if c.known is not None:
            rows['known+:'+c.id] = ({c.id:F(1)},Q(c.known))
            rows['known-:'+c.id] = ({c.id:F(-1)},-Q(c.known))
    for c in p.constraints:
        if c.adoption!='ADOPTED': continue
        normal = {k:Q(v) for k,v in c.coefficients.items()}
        if c.relation!='GE': rows['constraint+:'+c.id] = (normal,Q(c.rhs))
        if c.relation!='LE': rows['constraint-:'+c.id] = ({k:-v for k,v in normal.items()},-Q(c.rhs))
    def combine(proof):
        require(type(proof) is dict and proof.keys() <= rows.keys())
        normal = dict.fromkeys(ids,F(0)); rhs = F(0)
        for name,value in proof.items():
            w = Q(value); require(w>0)
            a,b = rows[name]; rhs += w*b
            for k,v in a.items(): normal[k] += w*v
        return normal,rhs
    if cert['status']=='INCOMPATIBLE':
        normal,rhs = combine(cert['farkas'])
        require(not any(normal.values()) and rhs<0)
        return
    require(cert['status'] in ('POINT','PARTIAL') and cert['sharp'] is True)
    lower,upper = Q(cert['lower']),Q(cert['upper'])
    require(lower<=upper and cert['status']==('POINT' if lower==upper else 'PARTIAL'))
    require(cert['realization']==('BERNOULLI_PER_COORDINATE' if p.outcome_domain=='BINARY' else 'DETERMINISTIC_PER_COORDINATE'))
    offset = Q(p.target_offset)
    for side,endpoint,sign in (('lower',lower,-1),('upper',upper,1)):
        raw=cert[side+'_world']; require(type(raw) is dict and raw.keys()==ids)
        world={k:Q(v) for k,v in raw.items()}
        for normal,rhs in rows.values(): require(sum((v*world[k] for k,v in normal.items()),F(0))<=rhs)
        value=offset+sum((Q(v)*world[k] for k,v in p.target.items()),F(0))
        require(value==endpoint)
        normal,rhs=combine(cert[side+'_dual'])
        require(all(normal[k]==sign*Q(p.target.get(k,'0')) for k in ids))
        require(rhs==sign*(endpoint-offset))
