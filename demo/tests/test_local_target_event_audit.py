"""Independent per-question audit facts must agree with candidate arms.

Fixtures below are offline contract inputs, not claims of LLM accuracy.
"""
from copy import deepcopy
import json
import pytest
from cfm_id_llm import local_bundle_reading as reader, local_target_event_audit as event
from cfm_id_llm.compact_study import digest
from cfm_id import local_bundle_entry as entry, joint_natural_entry as flow
from demo.tests.test_local_bundle_entry import fixture, approved, planned


def event_fields(reading):
    return dict(local_target_event_version=event.VERSION,local_target_events=[
        dict(field=f'targets.{i}',peer_basis='THIS_QUESTION',evidence=t['evidence'],
             **{arm+'_'+key:(t['value'][arm] or {}).get(key)
                for arm in ('first','second') for key in ('own','exposure')})
        for i,t in enumerate(reading['targets'])])


def current(case,s):
    from demo.tests.test_information_scope_audit import source_audit
    return source_audit(case,s)


def unspecified_second(a):
    a['local_target_events'][1].update(peer_basis='NOT_STATED',first_own=1,
        second_own=0,first_exposure=None,second_exposure=None)


def test_match_cannot_borrow_peer_state_from_another_question(tmp_path):
    c,d,t,s=fixture(tmp_path);s=reader.inspect(c,s);before=deepcopy(s)
    a=current(c,s);unspecified_second(a)
    checked=reader.check_audit_current(c,s,a)
    f=next(x for x in checked['findings'] if x['field']=='targets.1')
    assert f['verdict']=='READING_ERROR' and f['question'] is None
    assert s==before and a['findings']!=checked['findings']
    assert reader.check_audit(c,s,checked)==checked


def test_partial_source_arm_preserves_known_own_without_inventing_peer(tmp_path):
    c,d,t,s=fixture(tmp_path);s['targets'][1]['value'].update(first=None,second=None)
    s=reader.inspect(c,s);a=current(c,s);unspecified_second(a)
    checked=reader.check_audit_current(c,s,a)
    assert all(f['verdict']=='MATCH' for f in checked['findings'])
    assert checked['local_target_events'][1]['first_own']==1
    p=entry.plan(c,flow.base(dict(draft=d,draft_sha256=digest(d)),c,s,checked))
    assert p['joint_entry']['state']=='NEEDS_INPUT'
    assert p['joint_entry']['parts'][1]['target']['first'] is None


def test_explicit_shared_reverse_comparison_and_mean_are_supported(tmp_path):
    c,d,t,s=fixture(tmp_path);s['targets'][0]['value'].update(kind='MEAN',second=None)
    s=reader.inspect(c,s);a=current(c,s)
    a['local_target_events'][1]['peer_basis']='EXPLICIT_SHARED'
    assert all(f['verdict']=='MATCH' for f in reader.check_audit_current(c,s,a)['findings'])


def test_current_contract_requires_per_target_scope_but_old_reports_replay(tmp_path):
    c,d,t,s=fixture(tmp_path);s=reader.inspect(c,s);a=current(c,s)
    a.pop('local_target_event_version');a.pop('local_target_events')
    assert reader.check_audit(c,s,a)
    with pytest.raises(ValueError,match='LOCAL_TARGET_EVENT_AUDIT_REQUIRED'):
        reader.check_audit_current(c,s,a)
    schema=json.loads(reader.audit_request(c,s)['user_prompt'])['output_schema']
    assert 'local_target_events' in schema['required']
    assert schema['properties']['local_target_events']['minItems']==2
    legacy=planned(c,d,s,t);legacy=entry.complete(c,legacy,approved(legacy))
    assert flow.replay(c,d,legacy)


@pytest.mark.parametrize('error',['inconsistent_unknown','missing','duplicate','quote'])
def test_invalid_event_audit_cannot_pass(tmp_path,error):
    c,d,t,s=fixture(tmp_path);s=reader.inspect(c,s);a=current(c,s)
    if error=='inconsistent_unknown':a['local_target_events'][1]['peer_basis']='NOT_STATED'
    if error=='missing':a['local_target_events'].pop()
    if error=='duplicate':a['local_target_events'][1]['field']='targets.0'
    if error=='quote':a['local_target_events'][1]['evidence'][0]['quote']='SOURCE DOES NOT SAY THIS'
    with pytest.raises(ValueError):reader.check_audit_current(c,s,a)


def test_post_outcome_selection_stops_only_that_question_without_extra_questions(tmp_path):
    c,d,t,s=fixture(tmp_path)
    s['targets'][1]['value'].update(kind='OTHER',remaining_assignment='OTHER',
        fixed_before_assignment=False,population=None,weights=None,first=None,second=None)
    s=reader.inspect(c,s);a=current(c,s);unspecified_second(a)
    a=reader.check_audit_current(c,s,a)
    p=entry.plan(c,flow.base(dict(draft=d,draft_sha256=digest(d)),c,s,a))
    assert not p.get('clarification_questions')
    assert [x['state'] for x in p['joint_entry']['parts']]==['READY','UNSUPPORTED']
    assert '处理后的信息选择对象' in p['joint_entry']['parts'][1]['message']
    r=entry.complete(c,p,approved(p))
    assert [x['state'] for x in r['joint_entry']['parts']]==['POINT','UNSUPPORTED']
    assert r['joint_entry']['state']=='BUNDLE_INCOMPLETE' and flow.replay(c,d,r)
    assert not r['estimation_handoff_allowed']
    corrupt=deepcopy(r)
    corrupt['joint_entry']['audit']['local_target_events'][0]['first_exposure']=0
    assert not flow.replay(c,d,corrupt)


def test_existing_objection_not_erased_by_scope_decomposition(tmp_path):
    c,d,t,s=fixture(tmp_path);s=reader.inspect(c,s);a=current(c,s)
    f=next(x for x in a['findings'] if x['field']=='targets.1')
    f.update(verdict='READING_ERROR',reason='Another independently found source mismatch')
    checked=reader.check_audit_current(c,s,a)
    assert next(x for x in checked['findings'] if x['field']=='targets.1')['reason']==f['reason']


def test_invented_event_is_reread_before_confirming_any_science(tmp_path):
    c,d,t,wrong=fixture(tmp_path);correct=deepcopy(wrong)
    correct['targets'][1]['value'].update(first=None,second=None,fixed_before_assignment=False,
        population=None,weights=None,kind='OTHER',remaining_assignment='OTHER')
    wrong['targets'][1]['value'].update(fixed_before_assignment=False,
        population=None,weights=None,kind='OTHER',remaining_assignment='OTHER')
    calls=[]
    def call(request,stage):
        calls.append(stage);s=correct if stage.endswith('retry1') else wrong
        if stage.startswith('joint_source_read'):return deepcopy(s)
        assert stage.startswith('joint_source_audit')
        a=current(c,reader.inspect(c,s));unspecified_second(a);return a
    p=entry.prepare(c,dict(draft=d,draft_sha256=digest(d),checks=[]),call)
    assert calls==['joint_source_read','joint_source_audit','joint_source_read_retry1','joint_source_audit_retry1']
    assert p['joint_entry']['state']=='REVIEW_REQUIRED'
    assert [x['state'] for x in p['joint_entry']['parts']]==['READY','UNSUPPORTED']
    assert p['joint_entry']['attempts'][0]['reading']['targets'][1]['value']['first'] is not None
    assert p['joint_entry']['reading']['targets'][1]['value']['first'] is None
    assert not p.get('proof') and not p.get('estimation_handoff_allowed')
