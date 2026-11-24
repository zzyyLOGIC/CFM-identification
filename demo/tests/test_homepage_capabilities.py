"""Source/target/receipt invariants of the default website, with no provider transport."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import pytest

from cfm_id import direct_policy_exchange as exchange
from cfm_id.direct_verification import verify,replay
from cfm_id_llm.network_files import load_network
from demo.tests.test_web_capabilities import setup
from demo.tests.test_post_answer_network_dag import graph_case,draft


def study(method):
    return setup(method)[0].case.model_dump(mode='json')


def cited_answer(method, case, *, reverse=False, weights=None):
    candidate=setup(method)[1]['candidate']
    texts={s['source_id']:s['text'] for s in case['sources']}
    texts['question']=case['business_question']
    def fact(key,value):
        return dict(value=value,evidence=[dict(source_id=key,quote=texts[key])])
    network=candidate['study']
    nodes=network['nodes']
    source='network' if 'network' in texts else 'uploaded_network'
    law=candidate['assignment']
    design=(dict(kind='fixed',quota=law['fixed_count']) if law.get('fixed_count') is not None
            else dict(kind='stratified',groups=law['groups'],treated_quotas=law['treated_quotas']))
    exposure={'STRICT_MAJORITY_TIES_LOW':'majority','EXACT_TREATED_NEIGHBOR_COUNT':'count'}.get(candidate['exposure']['kind'],'other')
    target=candidate['target']
    def vector(end):
        return [end['assignment'][node] for node in nodes]
    left=vector(target.get('first',target))
    right=vector(target['second']) if 'second' in target else None
    if reverse:
        left,right=right,left
    contrast=dict(left=left,right=right,population=nodes)
    if weights:
        contrast.update(unit_weights=weights,population=[n for n,w in zip(nodes,weights) if Fraction(w)])
    return dict(answers=[dict(status='NEEDS_INPUT')],network_facts=dict(
        network=fact(source,dict(nodes=nodes,edges=network['edges'],complete=True,pre_treatment=True,undirected=True)),
        exposure=fact('exposure',dict(kind=exposure,description=texts['exposure'])),
        assignment=fact('assignment',design),contrast=fact('question',contrast)))


def adopt(report,authority='SYNTHETIC_TEST'):
    sheet=report['condition_review']
    return dict(binding=sheet['binding'],authority=authority,decisions={i['code']:'ADOPTED' for i in sheet['items']})


def change(c,key,old,new):
    row=next(r for r in c['sources'] if r['source_id']==key)
    assert old in row['text']
    row['text']=row['text'].replace(old,new)


def test_original_uploaded_spec_requires_current_source_review(tmp_path):
    from demo.backend.engine import Engine, Run
    from demo.backend.study_math import FORMAT, offered, submit

    engine=Engine(tmp_path/'runs')
    problem=json.loads((Path(__file__).resolve().parents[1]/'math-library-examples.json').read_text('utf8'))['effects']
    question='请核对附件中的多个局部效应。'
    spec=dict(format=FORMAT,question=question,operation='effects',problem=problem)
    sources=[dict(source_id='spec',text=json.dumps(spec,ensure_ascii=False)),dict(source_id='notes',text='同一期研究。')]
    original={'draft':{'status':'NEEDS_INPUT'}}
    parent=Run(owner='reader',synthetic=True,case=dict(business_question=question,sources=sources),
               result=deepcopy(original),attachment_report={'receipt':{'ready':True}})
    engine.runs[parent.id]=parent
    request=dict(source_run=parent.id,source_binding=offered(parent.case)['binding'],source_confirmed=True)

    with pytest.raises(ValueError,match='CURRENT_UPLOADED'):
        submit(engine,'reader',dict(request,problem={}))
    with pytest.raises(ValueError,match='ORIGINAL_TARGET'):
        submit(engine,'reader',dict(request,source_confirmed=False))
    pending=submit(engine,'reader',request)
    assert pending['state']=='REVIEW_REQUIRED' and not pending['backend_called']
    sheet=pending['worksheet']
    review=dict(binding=sheet['binding'],decisions=dict.fromkeys(sheet['items'],'ACCEPTED'),reviewer='Reviewer',evidence='逐项核对合成材料')
    decline=deepcopy(review)
    decline['decisions']['source']='DECLINED'
    assert not submit(engine,'reader',dict(request,review=decline))['backend_called']
    assert submit(engine,'reader',dict(request,review=review))['state']=='COMPUTED'
    assert parent.result==original and not engine.estimate_inbox.path_for(parent.id).exists()
    parent.synthetic=False
    with pytest.raises(ValueError,match='AUTHORITY_SCOPE'):
        submit(engine,'reader',dict(request,review=dict(review,authority='SYNTHETIC_TEST')))
    parent.case['sources'][1]['text']='改为另一期。'
    with pytest.raises(ValueError,match='ORIGINAL_TARGET'):
        submit(engine,'reader',dict(request,review=review))


def test_draw_independence_is_bound_to_its_subject_and_clause():
    from cfm_id.network_protocol_terms import independent_draw
    law='各点相互独立抽签，每点以1/2的概率启用。'
    assert independent_draw(law+'请写出识别式或不能比较的原因。一次样本不能证明抽签的独立性。')
    assert independent_draw(law+'不根据门店在任何安排下可能取得的评分来决定谁中签。')
    assert not independent_draw('实际使用人数不能证明随机分配方式或概率。')
    assert not independent_draw('不同门店的潜在结果相互独立。')
    for negation in ('各点是否独立抽签未知。','各次共用同一枚签。','独立性尚未确认。','抽签相关。','分配规则，尚未确认。','抽签可能相关。'):
        assert not independent_draw(law+negation)


@pytest.mark.parametrize('method,interval',[
    ('partial_mean',['3/7','4/7']),('partial_contrast',['-1','1']),('mean_order',['1/5','1']),
    ('count_mean',['1/4','3/4']),('count_contrast',['-1/2','1/2']),
    ('finite_mean',['1/4','3/4']),('finite_contrast',['-1/2','1/2'])])
def test_default_source_to_independent_certificate_and_confirmed_receipt(method,interval):
    c=study(method)
    answer=cited_answer(method,c)
    r=verify(c,answer)
    assert r['conditional_answer']['value']==interval and not r['estimation_handoff_allowed']
    refusal=adopt(r);refusal['decisions'][next(iter(refusal['decisions']))]='UNSURE'
    assert not verify(c,answer,science_review=refusal)['estimation_handoff_allowed']
    final=verify(c,answer,science_review=adopt(r))
    assert final['estimation_handoff_allowed'] and replay(c,answer,final)
    packet=exchange.packet(c,final)
    assert exchange.check_packet(c['case_id'],packet)['interval']==interval
    changed=deepcopy(packet);changed['estimate_handoff']['upper']='7'
    with pytest.raises(ValueError):
        exchange.check_packet(c['case_id'],changed)
    changed=deepcopy(packet);changed['source_draft']={'status':'POINT'}
    with pytest.raises(ValueError,match='POLICY_DRAFT_SOURCE_MISMATCH'):
        exchange.check_packet(c['case_id'],changed)
    if method!='partial_mean':
        assert not verify(c,answer,science_review=adopt(r,'EXTERNAL_RESEARCH_REVIEW'))['estimation_handoff_allowed']
        changed=deepcopy(packet);changed['review']['authority']=changed['release_scope']='EXTERNAL_RESEARCH_REVIEW'
        with pytest.raises(ValueError):
            exchange.check_packet(c['case_id'],changed)


def test_reversal_weighted_target_singleton_and_impossibility():
    c=study('mean_order')
    c['business_question']=c['business_question'].replace('增加多少','降低多少')
    assert verify(c,cited_answer('mean_order',c,reverse=True))['conditional_answer']['value']==['-1','-1/5']
    c=study('count_mean')
    c['business_question']=c['business_question'].replace('四家店等权','评价权重为甲店=1/2、乙店=1/2、丙店=0、丁店=0')
    r=verify(c,cited_answer('count_mean',c,weights=['1/2','1/2','0','0']))
    assert r['conditional_answer']['target']['population']==['甲店','乙店']
    assert r['conditional_answer']['target']['unit_weights']==['1/2','1/2','0','0']
    c['business_question']=c['business_question'].replace('乙店=1/2','乙店=3/4')
    assert not verify(c,{}).get('proof')
    c=study('partial_contrast')
    change(c,'bounds','下界为0，上界为1','下界为1/2，上界为1/2')
    answer=cited_answer('partial_contrast',c)
    r=verify(c,answer)
    assert r['conditional_answer']['status']=='POINT' and Fraction(r['conditional_answer']['value'])==0
    packet=exchange.packet(c,verify(c,answer,science_review=adopt(r)))
    assert packet['estimate_handoff']['value']=='0' and exchange.check_packet(c['case_id'],packet)['query_count']==0
    c=study('mean_order')
    change(c,'bounds','下界为0，上界为1','下界为0，上界为1/4')
    answer=cited_answer('mean_order',c)
    r=verify(c,answer)
    assert r['effective_answer']['status']=='INCOMPATIBLE' and r['proof']['evidence']['certificate']['farkas']
    assert not r.get('condition_review') and not r['estimation_handoff_allowed'] and replay(c,answer,r)


@pytest.mark.parametrize('source,old,new',[
    ('assignment','每组独立地均匀','每组相关地均匀'),('science','潜在结果独立','潜在结果尚未确定是否独立'),
    ('sufficiency','均值仅依赖','均值可能还依赖'),('information','精确总体均值','样本均值'),
    ('complete_model','没有跨对象','另有跨对象'),('exposure','至少2/3记2','严格超过2/3记2')])
def test_source_mutations_never_inherit_an_interval(source,old,new):
    c=study('finite_contrast')
    answer=cited_answer('finite_contrast',c)
    r=verify(c,answer)
    change(c,source,old,new)
    stopped=verify(c,answer)
    assert not stopped['proof'] and not stopped['estimation_handoff_allowed'] and not stopped.get('condition_review')
    with pytest.raises(ValueError):
        verify(c,answer,science_review=adopt(r))


def test_uploaded_graph_controls_actual_computation_and_receipt(tmp_path):
    c=study('partial_contrast')
    nodes=['甲店','乙店','丙店','丁店']
    edges=[(a,b) for i,a in enumerate(nodes) for b in nodes[i+1:]]
    n=tmp_path/'n.csv';e=tmp_path/'e.csv'
    n.write_text('node_id\n'+'\n'.join(nodes),encoding='utf8')
    e.write_text('source,target\n'+'\n'.join(a+','+b for a,b in edges),encoding='utf8')
    tables=[]
    table=load_network(n,e,dict(kind='UNDIRECTED',completeness='COMPLETE',description='处理前固定的无向合作关系'),shared_tables=tables)
    c['sources']=[s for s in c['sources'] if s['source_id']!='network']+[table.source(),*tables]
    answer=cited_answer('partial_contrast',c)
    r=verify(c,answer,network=table)
    assert r['conditional_answer']['value']==['-1','1']
    final=verify(c,answer,network=table,science_review=adopt(r))
    assert replay(c,answer,final) and exchange.check_packet(c['case_id'],exchange.packet(c,final))['interval']==['-1','1']
    next(s for s in c['sources'] if s['source_id']=='shared_edges')['text']+='甲店,丁店\n'
    assert not verify(c,answer,network=table).get('proof')


def test_extra_science_and_mismatched_or_absent_model_facts_preserve_boundaries():
    c=study('partial_contrast')
    empty=verify(c,{})
    assert empty['decision']=='RETAINED' and not empty.get('condition_review') and not empty['estimation_handoff_allowed']
    raw={'answers':[dict(draft(),question_part=c['business_question'])]}
    r=verify(c,raw);assert r['effective_answer']==raw and not r.get('proof') and not r['estimation_handoff_allowed']
    c['sources'][0]['text']+='另要求甲店的均值等于乙店的两倍。'
    r=verify(c,{})
    assert r['effective_answer']['status']=='NOT_COVERED' and r['checks'][-1]['evidence'][0]['quote'].endswith('两倍')


def test_source_bounds_do_not_endorse_conflicting_model_coordinates():
    c=study('partial_mean')
    answer=cited_answer('partial_mean',c)
    for field,key,value in [('assignment','probabilities',{'中心':'1'}),('contrast','left','七家均不使用AI'),
                             ('exposure','description','合作邻居至少一半使用时记1。')]:
        other=deepcopy(answer)
        other['network_facts'][field]['value'][key]=value
        r=verify(c,other)
        assert r['effective_answer']==other and not r.get('condition_review') and not r['estimation_handoff_allowed']
    answer['answers'][0]['target']={'quantity':'level','scope':'whole','intervention':'七家均不使用AI'}
    r=verify(c,answer)
    assert r['effective_answer']==answer and not r.get('condition_review') and not r['estimation_handoff_allowed']


def test_localized_graph_edges_and_prescribed_adjustment():
    c=graph_case()
    for s,label in zip(c['sources'],['变量','边表','模型声明','总体信息']):
        s['label']=label+'.md'
    c['sources'][1]['text']=c['sources'][1]['text'].replace('直接影响',' → ')
    assert verify(c,draft())['proof']['method']=='FRONTDOOR'
    c['business_question']+='请按指定的控制变量“练习”检查调整方案，不要改用其他控制变量。'
    r=verify(c,draft())
    assert r['proof']['specified_adjustment']==['练习'] and r['effective_answer']['status']=='NOT_COVERED'
    assert not r['estimation_handoff_allowed'] and replay(c,draft(),r)
    c['sources'][1]['text']='开课 → 练习。开课 → 到课。研究背景：全班本学期。'
    r=verify(c,draft())
    assert r['proof']['method']=='DAG_ADJUSTMENT' and r['proof']['certificate']['adjustment']==['练习']
    c['sources'][1]['text']+='\n## 额外限制\n尚未核对。'
    assert not verify(c,draft()).get('proof')


def test_iv_original_protocol_plus_cells_and_reversed_target():
    c=dict(case_id='binary',business_question='所有居民在实际 A=1 相对 A=0 下的达标风险差？',
           sources=[dict(source_id='note',text='研究总体为居民。结果时期为次日。工具变量 T（资格）。实际处理 A（使用）。结果变量 O（达标）。三个变量均为二元0/1。'
                      'T与全部潜在处理和潜在结果独立。T仅通过A影响O。本研究采用一致性和无干扰。T的两个取值均有正概率。'
                      '不假定A随机分配。采用无违背者单调性。所附表为精确总体条件概率，不是样本频率。以上是本题的全部条件，没有其他限制。'),
                    dict(source_id='table',text='T,A,O,条件概率\n0,0,0,.75\n0,0,1,.25\n0,1,0,0\n0,1,1,0\n1,0,0,0\n1,0,1,0\n1,1,0,.45\n1,1,1,.55')])
    for d,expected in [(c,'3/10'),(dict(c,business_question=c['business_question'].replace('A=1 相对 A=0','A=0 相对 A=1')),'-3/10')]:
        r=verify(d,draft());assert r['conditional_answer']['value']==expected and replay(d,draft(),r)
        assert r['proof']['source_spans'] and not r['estimation_handoff_allowed']
    change(c,'note','T与全部潜在','A与全部潜在')
    assert not verify(c,draft()).get('proof')
