from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from serve import integrated_engine
from cfm_id import stratified_savings
from cfm_id.direct_verification import verify
from test_natural_network_intake import harbor


def study(question):
    rules=['两案由公平抽签决定，独立于所有潜在结果，结果按抽中方案记录。','两类成员固定、互斥且穷尽。',
           '所列均值均为精确总体量。','全体成员每人等权。','两种方案均有支持。','未知两类人数。',
           '长期类在银案和铜案平均为8和3元，短期类在铜案和银案平均为7和5元。']
    return dict(business_question=question,sources=[dict(source_id='rules',text=''.join(rules))])


@pytest.mark.parametrize('question,number,bounds',[
    ('铜方案相比银方案，全体成员平均能节省多少元？',['5','-2'],['-2','5']),
    ('银方案相对于铜方案在所有用户中的平均节约元数是多少？',['-5','2'],['-5','2'])])
def test_signed_savings_binds_both_plans(question,number,bounds):
    c=study(question)
    def report():
        r={'checks':[]};stratified_savings.apply(c,{},r);return r
    r=report();p=r['proof']
    assert p['differences']==number and p['closure']==bounds
    a=r['effective_answer']
    assert a['value'] is None and a['status']=='NEEDS_INPUT' and len(r['clarification_questions'])==1
    c['sources'].append(dict(source_id='user_reply_1',text='p=1/0'))
    assert report()['effective_answer']['value'] is None
    c['sources'].append(dict(source_id='user_reply_2',text='长期类1人，短期类1人'))
    assert report()['effective_answer']['value']==('3/2' if number[0]=='5' else '-3/2')
    c['sources'][0]['text']+='仅为样本。'
    assert 'proof' not in report()


def test_changed_scope_requires_new_scientific_review(tmp_path):
    case,draft,network=harbor(tmp_path)
    draft['answers'][0]['target']['scope']='whole'
    sheet=verify(case,draft,network=network)['scope_worksheet']
    named=dict(binding=sheet['binding'],option='named')
    r=verify(case,draft,network=network,scope_choice=named)
    assert not r['estimation_handoff_allowed'] and r['scope_choice']==named
    assert r['network_alignment']['matched'] and len(r['condition_review']['items'])==3
    stale=deepcopy(case);stale['business_question']+='请注明来源。'
    with pytest.raises(ValueError,match='STALE'):
        verify(stale,draft,network=network,scope_choice=named)
    absent=dict(binding=r['condition_review']['binding'],decisions={},authority='SYNTHETIC_TEST')
    with pytest.raises(ValueError):
        verify(case,draft,network=network,scope_choice=dict(named,option='whole'),science_review=absent)
