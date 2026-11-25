from copy import deepcopy
from fractions import Fraction as F
from itertools import product
import pytest
from cfm_id_bridge.scientific_binding import sha
from cfm_id import symbolic_mean_joint as route,finite_mean_joint
from cfm_id.symbolic_mean_contract import numeric_problem

def aff(const='0',**co):return dict(constant=const,coefficients=co)

def fixture():
    return dict(version=route.VERSION,model=route.MODEL,outcome_domain='BINARY',context='same population and time',
        target_description='mean x subject to x+y=p',target={'x':'1'},target_offset=aff(),
        parameters=[dict(id='p',description='reported population sum',lower='0',upper='2',source_ids=['s'])],
        coordinates=[dict(id=k,description='binary outcome mean '+k,lower=aff(),upper=aff('1'),known=None,source_ids=['s']) for k in ('x','y')],
        constraints=[dict(id='sum',coefficients={'x':'1','y':'1'},relation='EQ',rhs=aff(p='1'),adoption='ADOPTED',source_ids=['s'])],
        sources={'s':'Binary outcomes, exact population means x+y=p, both in [0,1]. These are all restrictions.'},
        information='POPULATION_MEANS',model_complete=True,unresolved=[],additional_restrictions=[])

def approved(p):
    return dict(version=p['version'],problem_sha256=sha(p),authority='SYNTHETIC_TEST',reviewer='test researcher',
        evidence='Explicit finite model and all adopted constraints reviewed',decisions={k:'ACCEPTED' for k in route.DECISIONS})

def test_symbolic_endpoints_against_numeric_core_for_entire_grid():
    p=fixture();out=route.submit(p,approved(p));assert out['independent_replay']
    c=out['certificate'];assert route.replay(c,p)
    for i in range(17):
        theta=F(i,8);v=route.evaluate(c,p,{'p':str(theta)})
        assert F(v['lower'])==max(0,theta-1) and F(v['upper'])==min(1,theta)
        q=numeric_problem(p,{'p':str(theta)});n=finite_mean_joint.submit(q,approved(q))
        assert n['independent_replay'] and (n['certificate']['lower'],n['certificate']['upper'])==(v['lower'],v['upper'])

def test_two_parameters_infeasibility_and_degenerate_domain():
    p=fixture();p['parameters']+=[dict(id='d',description='known difference',lower='-1',upper='1',source_ids=['s'])]
    p['constraints']+=[dict(id='difference',coefficients={'x':'1','y':'-1'},relation='EQ',rhs=aff(d='1'),adoption='ADOPTED',source_ids=['s'])]
    c=route.submit(p,approved(p))['certificate']
    for a,b in product(('0','1/2','1','3/2','2'),('-1','0','1')):
        v=route.evaluate(c,p,{'p':a,'d':b});x=(F(a)+F(b))/2;y=(F(a)-F(b))/2
        assert v['status']==('POINT' if 0<=x<=1 and 0<=y<=1 else 'INCOMPATIBLE')
        if v['status']=='POINT':assert F(v['lower'])==x
    p['parameters'][0].update(lower='1',upper='1');c=route.submit(p,approved(p))['certificate']
    assert route.evaluate(c,p,{'p':'1','d':'0'})['lower']=='1/2'
    with pytest.raises(ValueError,match='OUTSIDE'):route.evaluate(c,p,{'p':'0','d':'0'})

@pytest.mark.parametrize('mutation',['omit_cell','weaken_region','wrong_dual','wrong_world','domain','target'])
def test_tampering_cannot_be_fixed_by_rehash(mutation):
    p=fixture();c=route.submit(p,approved(p))['certificate'];bad=deepcopy(c)
    if mutation=='omit_cell':bad['lower'].pop()
    if mutation=='weaken_region':bad['upper'][0]['region']=[]
    if mutation=='wrong_dual':bad['lower'][0]['dual']=['0']*len(bad['lower'][0]['dual'])
    if mutation=='wrong_world':bad['upper'][0]['world']['x']=['7','0']
    if mutation=='domain':bad['parameter_domain'][0]['upper']='3'
    if mutation=='target':p['target']={'y':'1'};bad['problem_sha256']=sha(p)
    bad['certificate_sha256']=sha({k:v for k,v in bad.items() if k!='certificate_sha256'})
    assert not route.replay(bad,p)

@pytest.mark.parametrize('change,reason',[
    ({'additional_restrictions':['individual monotonicity']},'ADDITIONAL_RESTRICTIONS_NOT_EXPRESSED'),
    ({'information':'FINITE_SAMPLE'},'SAMPLE_IS_NOT_POPULATION_INFORMATION'),
    ({'model_complete':None},'FINITE_MEAN_MODEL_NOT_COMPLETE')])
def test_missing_science_and_real_extra_restrictions_block(change,reason):
    p=fixture();p.update(change);out=route.submit(p,approved(p))
    assert out['reason_code']==reason and not out['backend_called']

def test_pending_declined_review_and_resource_budget():
    p=fixture();p['constraints'][0]['adoption']='UNDECIDED'
    assert route.prepare(p)['state']=='NEEDS_INPUT'
    p['constraints'][0]['adoption']='NOT_ADOPTED';c=route.submit(p,approved(p))['certificate']
    assert route.evaluate(c,p,{'p':'1/2'})['upper']=='1'
    p=fixture();r=approved(p);r['decisions']['adopted_constraints_and_sources']='REJECTED'
    assert not route.submit(p,r)['backend_called']


def test_resource_limit_cannot_issue_partial_certificate():
    p=fixture()
    p['coordinates']=[dict(p['coordinates'][0],id='m'+str(i)) for i in range(12)]
    p['target']={'m0':'1'};p['constraints']=[]
    out=route.submit(p,approved(p))
    assert out['state']=='RESOURCE_LIMIT' and not out['independent_replay']
    assert not out.get('certificate')


def test_parameter_dependent_bounds_and_zero_objective_against_native():
    p=fixture();p['coordinates'][0]['lower']=aff(p='1/4');p['coordinates'][1]['upper']=aff('1',p='-1/4')
    for target in ({'x':'-2','y':'3'},{}):
        p['target']=target;p['target_offset']=aff('1/3',p='1/5');c=route.submit(p,approved(p))['certificate']
        for i in range(9):
            par={'p':str(F(i,4))};got=route.evaluate(c,p,par);numeric=numeric_problem(p,par)
            out=finite_mean_joint.submit(numeric,approved(numeric));n=out['certificate']
            assert got['status']==n['status']
            if n['status']!='INCOMPATIBLE':assert (got['lower'],got['upper'])==(n['lower'],n['upper'])
