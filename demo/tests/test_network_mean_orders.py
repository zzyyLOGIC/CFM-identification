from copy import deepcopy
import pytest
from test_joint_natural_entry import fixture,prepared,finish
from cfm_id import joint_natural_entry as entry
from cfm_id.network_joint_projection import project,replay_projection
from cfm_id_llm import joint_reading as reader


def ordered(status='ADOPTED'):
    case,s=fixture();s['constraints']=[]
    s['mean_orders']=[dict(description='固定另一项时，平均结果不会随本人或同伴使用增加而下降',nodes=['甲','乙'],axis=axis,direction='NONDECREASING',all_other_states=True,status=status,evidence=s['family']['evidence']) for axis in ('OWN','PEER')]
    return case,s


def test_mean_order_bounds_and_replay():
    case,s=ordered();r=finish(case,s);c=r['joint_entry']['native_result']['certificate']
    assert (c['lower'],c['upper'])==('1/5','1')
    assert entry.replay(case,r['draft'],r)
    assert len(r['joint_entry']['problem']['constraints'])==8


@pytest.mark.parametrize('grouping',['strict_majority_ties_low','exact_treated_neighbor_count','any_treated_neighbor','three_level_treated_neighbor_fraction','pretreatment_core_collaborator_majority'])
def test_generic_order_cells_and_support_replay(grouping):
    case,s=ordered();s['mean_information']['value']['values']=[]
    s['exposure']['value']=dict(grouping=grouping,core_collaborators={'甲':['乙'],'乙':['甲']} if grouping.startswith('pretreatment') else None)
    p,m=project(s,reader.sources(case))
    assert replay_projection(s,reader.sources(case),p,m)
    assert len(p['constraints'])==8
    p['constraints'][0]['relation']='GE'
    assert not replay_projection(s,reader.sources(case),p,m)


def test_declined_mean_order_preserves_unrestricted_bounds():
    case,s=ordered('NOT_ADOPTED');r=finish(case,s);c=r['joint_entry']['native_result']['certificate']
    assert (c['lower'],c['upper'])==('0','1')
    assert len(r['joint_entry']['reading']['mean_orders'])==2


def test_nonincreasing_order_preserves_direction_and_named_scope():
    case,s=ordered()
    for row in s['mean_orders']:row.update(direction='NONINCREASING',nodes=['甲'])
    r=finish(case,s);c=r['joint_entry']['native_result']['certificate']
    # Only Jia's all-used mean is at most 1/5; Yi remains bounded by 1.
    assert (c['lower'],c['upper'])==('0','3/5') and entry.replay(case,r['draft'],r)
    for row in s['mean_orders']:row['nodes']=['甲','乙']
    c=finish(case,s)['joint_entry']['native_result']['certificate']
    assert (c['lower'],c['upper'])==('0','1/5')


def test_pending_or_unspecified_mean_order_requires_question():
    case,s=ordered('UNDECIDED');r=prepared(case,s)
    assert r['clarification_questions'] and not r['backend_called']
    case,s=ordered();s['mean_orders'][0]['all_other_states']=None;r=prepared(case,s)
    assert r['joint_entry']['reason_code']=='MEAN_ORDER_SCOPE_REQUIRED' and not r['backend_called']


def test_individual_monotonicity_is_not_converted_to_mean_only_model():
    case,s=ordered();s['remaining']=[dict(code='individual',statement='对每个对象每次结果都不下降',status='ADOPTED',evidence=s['family']['evidence'])]
    assert prepared(case,s)['joint_entry']['state']=='UNSUPPORTED'


def test_original_inequalities_are_jointly_retained():
    case,s=ordered();s['constraints']=fixture()[1]['constraints'];r=finish(case,s);c=r['joint_entry']['native_result']['certificate']
    assert (c['lower'],c['upper'])==('1/5','3/5')


def test_known_mean_substitution_retains_constant_contradiction():
    case,s=ordered()
    s['constraints']=[dict(description='已知为1/5的均值另被要求至少1/2',terms=[dict(node='甲',own=1,exposure=0,coefficient='1')],relation='GE',rhs='1/2',status='ADOPTED',evidence=s['family']['evidence'])]
    p,m=project(s,reader.sources(case))
    assert p['constraints'][0]['coefficients']=={} and p['constraints'][0]['rhs']=='3/10'
    assert len(p['coordinates'])==8 and replay_projection(s,reader.sources(case),p,m)
    r=finish(case,s)
    assert r['joint_entry']['state']=='INCOMPATIBLE' and r['independent_replay']


def test_substitution_is_same_inequality_on_known_coordinate_plane():
    from fractions import Fraction as F
    from itertools import product
    case,s=ordered();s['constraints']=fixture()[1]['constraints']
    p,m=project(s,reader.sources(case));coords=p['coordinates'];free=[c['id'] for c in coords if c['known'] is None]
    for values in product((F(0),F(1,5),F(3,5),F(1)),repeat=len(free)):
        world={c['id']:F(c['known']) for c in coords if c['known'] is not None};world.update(zip(free,values))
        for old,new in zip(m['before_known_mean_substitution'],p['constraints']):
            residual=lambda row:sum((F(v)*world[k] for k,v in row['coefficients'].items()),F(0))-F(row['rhs'])
            assert residual(old)==residual(new)
