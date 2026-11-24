"""Source changes must change admission, even when the model answer stays fixed."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from cfm_id.direct_verification import verify, replay
from cfm_id import direct_policy_exchange as exchange
from demo.tests.test_post_answer_network_dag import graph_case, draft
from demo.tests.test_uploaded_network_contrast import fixture_case, decisions


def edit(case, sid, before, after):
    s = next(s for s in case['sources'] if s['source_id'] == sid)
    assert before in s['text']
    s['text'] = s['text'].replace(before, after)


@pytest.mark.parametrize('sid,before,after', [
    ('information.md', '分布已给定', '分布没有给定'),
    ('information.md', '分布已给定', '分布未给出'),
    ('information.md', '概率严格为正', '概率并不都严格为正'),
    ('model.md', '边表列出了', '边表没有列出'),
    ('model.md', '其他机制保持不变', '无法保证其他机制保持不变'),
    ('model.md', '剩余噪声相互独立', '是否采用剩余噪声相互独立尚未决定'),
    ('model.md', '剩余噪声相互独立', '剩余噪声相互独立不作为本次假设'),
    ('model.md', '所有共同原因均已列出', '不能确认所有共同原因均已列出'),
])
def test_negative_or_undecided_declaration_never_becomes_a_dag_proof(sid, before, after):
    c = graph_case(); edit(c, sid, before, after)
    r = verify(c, draft())
    assert r['decision'] == 'WITHHELD'
    assert r['proof']['method'] == 'DAG_INPUT' and 'certificate' not in r['proof']
    assert r['effective_answer']['status'] in {'NEEDS_INPUT', 'NOT_COVERED'}
    assert not r['estimation_handoff_allowed'] and replay(c, draft(), r)


@pytest.mark.parametrize('sid,separator', [('model.md', '。'), ('model.md', '，'), ('information.md', '。')])
def test_extra_assumption_cannot_be_dropped_to_prove_nonidentification(sid, separator):
    c = graph_case(); c['sources'][1]['text'] += '开课直接影响到课。'
    assert verify(c, draft())['proof']['method'] == 'ID_HEDGE'
    s = next(s for s in c['sources'] if s['source_id'] == sid)
    s['text'] = s['text'].rstrip('。') + separator + '本次额外假定：每个人无论是否开课，到课结果完全相同。'
    r = verify(c, draft())
    assert r['effective_answer']['status'] == 'NOT_COVERED'
    assert r['proof']['additional_restrictions'] and r['proof']['method'] == 'DAG_INPUT'
    assert not r['estimation_handoff_allowed'] and replay(c, draft(), r)


def partial_case():
    examples = json.loads((Path(__file__).parents[1] / 'examples.json').read_text('utf8'))
    return deepcopy(next(x['case'] for x in examples if x['id'] == 'partial_policy'))


def policy_draft(case,status='POINT',mode='ESTIMATE_POINT'):
    from demo.tests.test_homepage_capabilities import cited_answer
    return dict(draft(status,mode),network_facts=cited_answer('partial_mean',case)['network_facts'])


def test_default_partial_replays_source_bounds_and_requires_fresh_review():
    c = partial_case(); a = policy_draft(c)  # correct target but deliberately wrong point conclusion
    r = verify(c, a)
    assert r['decision'] == 'PREMISES_REQUIRED'
    assert r['conditional_answer']['value'] == ['3/7', '4/7']
    assert not r['estimation_handoff_allowed'] and replay(c, a, r)
    denied = verify(c, a, science_review=decisions(r, 'DECLINED'))
    assert not denied['estimation_handoff_allowed']
    accepted = verify(c, a, science_review=decisions(r))
    assert accepted['effective_answer']['status'] == 'PARTIAL' and replay(c, a, accepted)
    packet = exchange.packet(c, accepted)
    assert exchange.check_packet(c['case_id'], packet)['interval'] == ['3/7', '4/7']
    changed = deepcopy(packet); changed['evidence']['claim']['interval'] = ['0', '1']
    with pytest.raises(ValueError): exchange.check_packet(c['case_id'], changed)


def test_partial_does_not_depend_on_example_id_roster_names_or_saved_answer():
    c = partial_case(); c['case_id'] = 'unseen'; c['sources'].reverse()
    c = json.loads(json.dumps(c, ensure_ascii=False).replace('中心', '甲站').replace('网点', '分站'))
    # Nouns used by the material contract stay "网点"; unit IDs are arbitrary.
    for s in c['sources']:
        s['text'] = s['text'].replace('个分站', '个网点')
    d = exchange.derive(c)
    assert d and d['claim']['interval'] == ['3/7', '4/7']
    assert d['claim']['target']['node_order'][0] == '甲站'
    edit(c, 'information', '总体条件均值=1/2', '总体条件均值=1/3')
    assert exchange.derive(c)['claim']['interval'] == ['2/7', '3/7']


@pytest.mark.parametrize('definition', [
    '合作邻居中严格超过一半未使用AI',
    '本区所有网点中严格超过一半使用AI',
    '合作邻居中严格超过一半参加培训',
    '合作邻居中至少一半使用AI',
])
def test_distinct_exposures_cannot_inherit_the_treated_neighbor_certificate(definition):
    c = partial_case()
    a = policy_draft(c, 'PARTIAL', 'ESTIMATE_BOUNDS')
    a['value'] = ['3/7', '4/7']
    original = verify(c, a)
    edit(c, 'exposure', '合作邻居中严格超过一半使用AI', definition)
    r = verify(c, a)
    assert r['draft'] == a and r['effective_answer']['status'] == 'NOT_COVERED'
    assert r['proof'] is None and r['conditional_answer'] is None and not r.get('condition_review')
    assert not r['estimation_handoff_allowed'] and not r['clarification_questions'] and replay(c, a, r)
    with pytest.raises(ValueError, match='NETWORK_REVIEW_NOT_AVAILABLE'):
        verify(c, a, science_review=decisions(original))


def test_equivalent_word_order_replays_and_a_conflicting_question_blocks_handoff():
    c = partial_case()
    edit(c, 'exposure', '合作邻居中严格超过一半使用AI', '超过半数的合作邻居使用AI')
    r = verify(c, policy_draft(c))
    assert r['conditional_answer']['value'] == ['3/7', '4/7'] and r['decision'] == 'PREMISES_REQUIRED'
    c['business_question'] += '本题同伴暴露定义为超过半数的合作邻居未使用AI时为1，否则为0。'
    r = verify(c, draft())
    assert r['effective_answer']['status'] == 'NOT_COVERED' and not r['estimation_handoff_allowed']
    assert r['checks'][-1]['evidence'][0]['source_id'] == 'question'


def test_peer_mapping_in_single_protocol_binds_the_action_and_the_population():
    from cfm_id.network_protocol_terms import treated_neighbor_majority
    assert treated_neighbor_majority('超过一半邻区启用时暴露为1，平票为0', '启用照明')
    for description in ('超过一半邻区未启用', '超过一半全区站点启用', '超过一半邻区启用风机'):
        assert not treated_neighbor_majority(description + '时暴露为1，平票为0', '启用照明')


@pytest.mark.parametrize('change', ['negative', 'unknown', 'missing', 'extra', 'inline_extra', 'conflicting'])
def test_partial_cannot_certify_missing_or_stronger_model(change):
    c = partial_case()
    if change in ('negative', 'unknown'):
        edit(c, 'sufficiency', '研究另行拟采用', '研究不采用' if change == 'negative' else '尚未决定是否采用')
    elif change == 'missing':
        c['sources'] = [s for s in c['sources'] if s['source_id'] != 'sufficiency']
    elif change == 'extra':
        c['sources'].append(dict(source_id='extra', label='补充', kind='OTHER', text='中心与网点1的潜在结果均值相等。'))
    elif change == 'inline_extra':
        edit(c, 'science', '所需条件一阶矩有限', '所需条件一阶矩有限，同时要求中心和网点1的均值相等')
    else:
        c['sources'].append(dict(source_id='amendment', label='修订', kind='OTHER', text='不采用全安排均值充分性。'))
    r = verify(c, draft('PARTIAL', 'ESTIMATE_BOUNDS'))
    assert r['decision'] == 'WITHHELD'
    assert r['effective_answer']['status'] in {'NOT_COVERED', 'NEEDS_INPUT'}
    assert r['proof'] is None and not r['estimation_handoff_allowed']


def test_independent_draw_paraphrase_keeps_same_probability_and_operator(tmp_path):
    c, a, table = fixture_case(tmp_path, rule='majority')
    baseline = verify(c, a, network=table)
    phrase = '每个站点分别抽签，互不影响，开放的概率都是三分之一，抽中就开放。'
    edit(c, 'law', '各站独立抽签，各有1/3概率开放，按签执行。', phrase)
    a['network_facts']['assignment']['evidence'][0]['quote'] = phrase
    r = verify(c, a, network=table)
    assert r['decision'] == 'PREMISES_REQUIRED' and r['network_alignment']['matched']
    assert r['proof']['joint_probabilities'] == baseline['proof']['joint_probabilities']
    assert replay(c, a, r)
    for bad in ('每个站点分别抽签，是否互不影响尚未决定，开放的概率都是三分之一。',
                phrase + '谷口的开放概率为1/2。'):
        edited = deepcopy(c); edit(edited, 'law', phrase, bad)
        out = verify(edited, a, network=table)
        assert not out['estimation_handoff_allowed'] and not out.get('condition_review')


@pytest.mark.parametrize('before,after', [('按时完成率','总营业额'), ('七家都用','八家都用'), ('平均按时完成率','下周平均按时完成率')])
def test_changed_partial_question_cannot_inherit_old_answer(before,after):
    c=partial_case();c['business_question']=c['business_question'].replace(before,after)
    r=verify(c,draft('PARTIAL','ESTIMATE_BOUNDS'))
    assert r['decision']=='WITHHELD' and r['effective_answer']['value'] is None
    assert not r['estimation_handoff_allowed'] and r['clarification_questions']


def test_extra_dag_assumption_in_question_is_not_lost():
    c=graph_case();c['sources'][1]['text']+='开课直接影响到课。'
    c['business_question']+='本次额外假定：每个人无论是否开课，到课结果完全相同。'
    r=verify(c,draft())
    assert r['proof']['method']=='DAG_INPUT' and r['effective_answer']['status']=='NOT_COVERED'
