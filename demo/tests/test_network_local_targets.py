from copy import deepcopy
from fractions import Fraction
import pytest

from cfm_id.direct_verification import verify,replay
from cfm_id.network_target_scope import ScopeGap,weights
from demo.tests.test_uploaded_network_contrast import fixture_case,decisions


def weighted(tmp_path):
    case,draft,table=fixture_case(tmp_path)
    case['business_question']=case['business_question'].replace('全部4个站点等权','按评价权重表计算平均效果')
    next(s for s in case['sources'] if s['source_id']=='pop')['text']='评价名单和权重在抽签前确定。按评价权重表计算平均效果。'
    case['sources'].append(dict(source_id='weights',kind='OTHER',label='评价权重.csv',
                               text='node_id,evaluation_weight\n谷口,1/2\n江岸,1/3\n山南,1/6\n西湾,0\n'))
    return case,draft,table


def test_weights_native_certificate_and_original_are_preserved(tmp_path):
    case,draft,table=weighted(tmp_path);original=deepcopy(draft)
    pending=verify(case,draft,network=table)
    assert pending['local_targets']['state']=='REVIEW_REQUIRED',pending
    assert not pending['independent_replay'] and not pending['proof']
    result=verify(case,draft,network=table,science_review=decisions(pending))
    assert result['local_targets']['state']=='COMPLETED',result
    part=result['local_targets']['parts'][0]
    assert result['draft']==draft==original and result['independent_replay'] and replay(case,draft,result)
    terms=part['native']['summary']['constituent_arms']
    assert {(t['node_id'],t['own_treatment']):Fraction(t['coefficient']) for t in terms}=={
        (n,a):s*w for n,w in [('谷口',Fraction(1,2)),('江岸',Fraction(1,3)),('山南',Fraction(1,6))] for a,s in ((1,1),(0,-1))}
    assert '西湾' in part['native']['evidence']['source_batch']['node_ids']
    assert not result['estimation_handoff_allowed']
    changed=deepcopy(result);changed['local_targets']['parts'][0]['native']['summary']['constituent_arms'][0]['coefficient']='1'
    assert not replay(case,draft,changed)
    case['sources'][-1]['text']=case['sources'][-1]['text'].replace('谷口,1/2','谷口,1/3')
    with pytest.raises(ValueError):verify(case,draft,network=table,science_review=decisions(pending))


@pytest.mark.parametrize('old,new',[
 ('谷口,1/2','谷口,-1/2'),('谷口,1/2','谷口,2'),('谷口,1/2','未知,1/2'),
 ('江岸,1/3','谷口,1/3'),('西湾,0\n',''),('谷口,1/2','谷口,0.5,其他'),
 ('谷口,1/2','谷口,True'),('谷口,1/2','谷口,1/0')])
def test_invalid_weight_table_never_defaults_to_equal(tmp_path,old,new):
    case,draft,table=weighted(tmp_path);case['sources'][-1]['text']=case['sources'][-1]['text'].replace(old,new)
    r=verify(case,draft,network=table)
    assert r['local_targets']['state']=='NEEDS_INPUT' and not r['proof'] and not r.get('condition_review')


def test_whole_batch_keeps_all_questions_and_original_graph(tmp_path):
    case,draft,table=fixture_case(tmp_path)
    common,question=case['business_question'].rsplit('。',1)
    reverse=question.replace('本站开放相比本站未开放','本站未开放相比本站开放')
    case['business_question']=common+'。\n1. '+question+'\n2. '+reverse
    draft={'answers':[{'status':'POINT','question_part':question}]} # omitted second model answer is not authority
    pending=verify(case,draft,network=table)
    assert len(pending['local_targets']['parts'])==2
    assert pending['local_targets']['state']=='REVIEW_REQUIRED',pending
    result=verify(case,draft,network=table,science_review=decisions(pending))
    assert result['local_targets']['state']=='COMPLETED',result
    a,b=[p['native']['summary']['constituent_arms'] for p in result['local_targets']['parts']]
    assert {(t['node_id'],t['own_treatment'],t['exposure_state']):Fraction(t['coefficient']) for t in a}=={
        (t['node_id'],t['own_treatment'],t['exposure_state']):-Fraction(t['coefficient']) for t in b}
    assert replay(case,draft,result)
    case['business_question']+='\n3. 哪家门店最适合先开放？'
    r=verify(case,draft,network=table)
    final=verify(case,draft,network=table,science_review=decisions(r))
    assert len(final['local_targets']['parts'])==3 and final['local_targets']['state']=='INCOMPLETE'
    assert not final['independent_replay'] and not final['estimation_handoff_allowed']


def test_extra_constraint_and_unconfirmed_science_not_approved(tmp_path):
    case,draft,table=weighted(tmp_path)
    pending=verify(case,draft,network=table)
    assert not verify(case,draft,network=table,science_review=decisions(pending,'UNSURE'))['proof']
    case['sources'].append(dict(source_id='extra',kind='OTHER',text='另采用单调性：开放不会降低任何站点的到站量。'))
    r=verify(case,draft,network=table)
    assert r['local_targets']['state']=='NOT_COVERED' and not r.get('condition_review')


def test_historical_equal_weight_path_unchanged(tmp_path):
    case,draft,table=fixture_case(tmp_path,subgroup=True)
    assert verify(case,draft,network=table)==verify(case,draft,network=table,version='direct-verification/24')


@pytest.mark.parametrize('change',[
 '本次按实际使用情况筛选评价对象。','两店等权。','仅评价【谷口、江岸】。',
 '全部对象平均评价。'])
def test_weight_scope_conflicts_do_not_change_target(tmp_path,change):
    case,draft,table=weighted(tmp_path)
    case['sources'].append(dict(source_id='change',text=change))
    r=verify(case,draft,network=table)
    assert r['local_targets']['state']=='NEEDS_INPUT' and not r.get('condition_review')


def test_actual_spreadsheet_wrapper_is_lossless_and_checked(tmp_path):
    case,draft,table=weighted(tmp_path)
    text=case['sources'][-1]['text']
    case['sources'][-1]['text']='工作表 CSV（第一列为原文件行号）\n'+''.join(f'{i},{row}\n' for i,row in enumerate(text.splitlines(),1))
    assert verify(case,draft,network=table)['local_targets']['state']=='REVIEW_REQUIRED'
    case['sources'][-1]['text']=case['sources'][-1]['text'].replace('3,江岸','8,江岸')
    assert verify(case,draft,network=table)['local_targets']['state']=='NEEDS_INPUT'


def test_unresolved_mean_condition_cannot_be_approved(tmp_path):
    case,draft,table=weighted(tmp_path)
    src=next(s for s in case['sources'] if s['source_id']=='science')
    src['text']=src['text'].replace('各端条件均值有限','各端条件均值是否有限尚未决定')
    r=verify(case,draft,network=table)
    assert r['local_targets']['state']=='NEEDS_INPUT' and not r.get('condition_review')


def test_question_projection_has_no_unassigned_trailing_paragraph(tmp_path):
    case,draft,table=fixture_case(tmp_path)
    q=case['business_question'];case['business_question']='1. '+q+'\n2. '+q+'\n另外还想知道整体推广的效果。'
    r=verify(case,draft,network=table)
    assert r['local_targets']['state']=='NEEDS_INPUT' and not r['proof']
