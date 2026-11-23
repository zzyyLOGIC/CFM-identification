from fractions import Fraction
from itertools import product

import pytest

from cfm_id.direct_verification import verify
from test_uploaded_network_contrast import fixture_case


def draft():
    return {'answers':[{'status':'POINT','target':{'outcome':'每个站的客流分数','time':'这一周','quantity':'difference'},
                        'functional':'以原试点条件分布分别求均值再相减','estimate_handoff':{'mode':'ESTIMATE_POINT'}}]}


@pytest.mark.parametrize('rule,reverse,fixed,subgroup',[
    ('majority',False,False,False),('any',True,False,False),('count',True,False,True),('any',False,True,True)])
def test_read_files_without_model_fields(tmp_path,rule,reverse,fixed,subgroup):
    c,_,table=fixture_case(tmp_path,rule=rule,reverse=reverse,fixed=fixed,subgroup=subgroup)
    baseline=verify(c,{},network=table)
    assert baseline['decision']=='PREMISES_REQUIRED',baseline['clarification_questions']
    proof=baseline['proof']
    assert proof['binding_source']=='uploaded-materials/1'
    assert verify(c,draft(),network=table)['proof']==proof
    assert baseline['conditional_answer']['target']['outcome']=='到站量'
    assert baseline['conditional_answer']['target']['time']=='本周'
    pop=[table.nodes[0]] if subgroup else list(table.nodes)
    assert proof['population']==pop
    for node in pop:
        neighbors={v for e in table.edges if node in e for v in e if v!=node}
        law={key:Fraction() for key in proof['ordered_events']}
        for z in product((0,1),repeat=4):
            if fixed and sum(z)!=2:continue
            active=sum(z[table.nodes.index(v)] for v in neighbors)
            exp={'majority':int(2*active>len(neighbors)),'any':int(active>0),'count':active}[rule]
            key=f'{z[table.nodes.index(node)]},{exp}'
            if key in law:
                law[key]+=Fraction(1,6) if fixed else Fraction(1,3)**sum(z)*Fraction(2,3)**(4-sum(z))
        assert law=={key:Fraction(v) for key,v in proof['joint_probabilities'][node].items()}


@pytest.mark.parametrize('note',[
    '关系表共有9条边。','完整边表：[["山南","西湾"]]。','本期各站独立抽签，各有1/4概率开放。',
    '研究另称平票记1。','关系表不完整。','本期需按营收比例加权。','结果期间为下周。',
    '只有全体均值，逐站均值无法查询。','实际参加由自己决定，可拒绝。',
])
def test_material_disagreements_survive_correct_looking_draft(tmp_path,note):
    c,_,table=fixture_case(tmp_path,rule='majority')
    c['sources'].append(dict(source_id='memo',kind='OTHER',label='原始备忘录',text=note))
    result=verify(c,draft(),network=table)
    assert result['decision']=='RETAINED' and result['effective_answer']==draft()
    assert not result['network_alignment']['matched'] and result['proof'] is None
    assert not result.get('condition_review') and not result['estimation_handoff_allowed']


def test_zero_support_includes_whole_original_evaluation_roster(tmp_path):
    c,_,table=fixture_case(tmp_path,isolated=True)
    report=verify(c,draft(),network=table)
    assert report['effective_answer']['status']=='UNDEFINED'
    assert report['proof']['population']==list(table.nodes)
    assert set(report['proof']['joint_probabilities']['西湾'].values())=={'0'}
    assert not report['estimation_handoff_allowed']


def test_joint_law_not_imputed_from_equal_marginals(tmp_path):
    c,_,table=fixture_case(tmp_path)
    next(row for row in c['sources'] if row['source_id']=='law')['text']=(
        '四站共用一枚公平硬币，正面全部开放、反面全部不开放。分配变量为开放。')
    report=verify(c,draft(),network=table)
    assert report['effective_answer']['status']=='UNDEFINED'
    assert all(v=={'1,1':'1/2','0,1':'0'} for v in report['proof']['joint_probabilities'].values())
    assert not report['estimation_handoff_allowed']
