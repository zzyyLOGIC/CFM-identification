"""Scope audit contradictions and live-contract enforcement, without an API."""
from copy import deepcopy
import json
import pytest
from cfm_id_llm import information_scope_audit as scope, local_bundle_reading as reader
from cfm_id import local_bundle_entry as entry
from cfm_id_llm.compact_study import digest
from demo.tests.test_local_bundle_entry import fixture


def source_audit(case, reading, fields=None):
    fields = fields or reader.fields(reading)
    from demo.tests.test_design_scope_audit import audit_fields
    from demo.tests.test_local_target_event_audit import event_fields
    return dict(**audit_fields(reading),**event_fields(reading),binding=reader.binding(case,reading),scientific_approval=False,
        findings=[dict(field=k,verdict='MATCH',reason='Offline source audit fixture',question=None,
                       evidence=v.get('evidence',[])) for k,v in fields.items()],
        information_scope_version=scope.VERSION,
        information_scopes=[dict(field='information.0',nature='POPULATION',statistic='DISTRIBUTION',
            results='SEPARATE_OUTCOMES',treatments='FULL_ASSIGNMENT',
            outcome_nodes=list(reading['network']['value']['nodes']), evidence=reading['information'][0]['evidence'])])


@pytest.mark.parametrize('mutation,dimension',[
    ('joint','results'),('sample','总体/样本性质'),('means','statistic'),
    ('own_only','treatments'),('missing_node','结果对象覆盖')])
def test_match_cannot_override_explicit_source_scope(tmp_path,mutation,dimension):
    c,d,t,s=fixture(tmp_path);s=reader.inspect(c,s);a=source_audit(c,s)
    if mutation=='joint':s['information'][0]['value']['operator']='FULL_JOINT_LAW'
    if mutation=='sample':a['information_scopes'][0].update(nature='FINITE_SAMPLE',statistic='RECORDS')
    if mutation=='means':a['information_scopes'][0]['statistic']='MEANS'
    if mutation=='own_only':a['information_scopes'][0]['treatments']='OTHER'
    if mutation=='missing_node':a['information_scopes'][0]['outcome_nodes'].pop()
    a['binding']=reader.binding(c,s)
    checked=reader.check_audit_current(c,s,a)
    finding=next(x for x in checked['findings'] if x['field']=='information.0')
    assert finding['verdict']=='READING_ERROR' and finding['question'] is None
    assert dimension in finding['reason']
    assert reader.check_audit(c,s,checked)==checked


def test_new_request_requires_scope_old_report_remains_replayable(tmp_path):
    c,d,t,s=fixture(tmp_path);s=reader.inspect(c,s);a=source_audit(c,s)
    a.pop('information_scopes');a.pop('information_scope_version')
    assert reader.check_audit(c,s,a)
    with pytest.raises(ValueError,match='INFORMATION_SCOPE_AUDIT_REQUIRED'):
        reader.check_audit_current(c,s,a)
    request=reader.audit_request(c,s);schema=json.loads(request['user_prompt'])['output_schema']
    assert 'information_scopes' in schema['required']
    assert schema['properties']['information_scopes']['items']['properties']['field']['enum']==['information.0']


def test_conflicting_reading_gets_one_fresh_reread_before_science_review(tmp_path):
    c,d,t,correct=fixture(tmp_path);wrong=deepcopy(correct)
    wrong['information'][0]['value']['operator']='FULL_JOINT_LAW';calls=[]
    def call(request,stage):
        calls.append(stage)
        if stage.startswith('joint_source_read'):return deepcopy(correct if stage.endswith('retry1') else wrong)
        body=json.loads(request['user_prompt'])
        current=correct if stage.endswith('retry1') else wrong
        a=source_audit(c,reader.inspect(c,current),body['fields'])
        return a
    r=entry.prepare(c,dict(draft=d,draft_sha256=digest(d),checks=[]),call)
    assert r['joint_entry']['state']=='REVIEW_REQUIRED'
    assert calls==['joint_source_read','joint_source_audit','joint_source_read_retry1','joint_source_audit_retry1']
    first=r['joint_entry']['attempts'][0]
    assert first['reading']['information'][0]['value']['operator']=='FULL_JOINT_LAW'
    assert next(f for f in first['audit']['findings'] if f['field']=='information.0')['verdict']=='READING_ERROR'
    assert r['joint_entry']['reading']['information'][0]['value']['operator']=='NODE_FULL_LAW'
    assert not r.get('proof') and not r.get('estimation_handoff_allowed')


def test_joint_information_not_downgraded_and_prior_objection_not_erased(tmp_path):
    c,d,t,s=fixture(tmp_path);s=reader.inspect(c,s);a=source_audit(c,s)
    a['information_scopes'][0]['results']='JOINT_OUTCOMES'
    checked=reader.check_audit_current(c,s,a)
    assert next(f for f in checked['findings'] if f['field']=='information.0')['verdict']=='READING_ERROR'
    s['information'][0]['value']['operator']='FULL_JOINT_LAW';a['binding']=reader.binding(c,s)
    f=next(f for f in a['findings'] if f['field']=='information.0');f.update(verdict='READING_ERROR',reason='A different source mismatch')
    assert next(f for f in reader.check_audit_current(c,s,a)['findings'] if f['field']=='information.0')['reason']=='A different source mismatch'


def test_sample_is_retained_as_sample_without_new_population_permission(tmp_path):
    c,d,t,s=fixture(tmp_path);s['information'][0]['value'].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE')
    s=reader.inspect(c,s);a=source_audit(c,s)
    a['information_scopes'][0].update(nature='FINITE_SAMPLE',statistic='RECORDS',results='UNSPECIFIED')
    assert all(f['verdict']=='MATCH' for f in reader.check_audit_current(c,s,a)['findings'])


def test_new_audit_is_bound_to_scientific_review_and_report_replay(tmp_path):
    from cfm_id import joint_natural_entry as flow
    from demo.tests.test_local_bundle_entry import approved
    c,d,t,s=fixture(tmp_path);s=reader.inspect(c,s)
    a=reader.check_audit_current(c,s,source_audit(c,s))
    r=entry.plan(c,flow.base(dict(draft=d,draft_sha256=digest(d)),c,s,a))
    final=entry.complete(c,r,approved(r))
    assert flow.replay(c,d,final)
    corrupted=deepcopy(final)
    corrupted['joint_entry']['audit']['information_scopes'][0]['results']='JOINT_OUTCOMES'
    assert not flow.replay(c,d,corrupted)


def test_sample_stop_avoids_unrelated_questions_but_not_source_disputes(tmp_path):
    from cfm_id import joint_natural_entry as flow
    c,d,t,s=fixture(tmp_path);s['information'][0]['value'].update(operator='FINITE_SAMPLE',availability='FINITE_SAMPLE')
    s=reader.inspect(c,s);a=source_audit(c,s)
    a['information_scopes'][0].update(nature='FINITE_SAMPLE',statistic='RECORDS',results='UNSPECIFIED')
    f=next(f for f in a['findings'] if f['field']=='design')
    f.update(verdict='NEEDS_CLARIFICATION',question='抽签是否独立？')
    a=reader.check_audit_current(c,s,a)
    r=entry.diagnose_sample_stop(c,flow.base(dict(draft=d,draft_sha256=digest(d)),c,s,a))
    assert r['joint_entry']['reason_code']=='LOCAL_SAMPLE_ONLY_INFORMATION'
    assert not r.get('clarification_questions') and not r.get('proof')
    f=next(f for f in a['findings'] if f['field']=='coverage')
    f.update(verdict='NEEDS_CLARIFICATION',question='另一份总体信息是否也适用于本题？')
    assert entry.diagnose_sample_stop(c,flow.base(dict(draft=d,draft_sha256=digest(d)),c,s,a)) is None


def test_lossless_weight_wrapper_keeps_values_and_original_response(tmp_path):
    c,d,t,s=fixture(tmp_path);expected=reader.inspect(c,s)
    s['targets'][0]['value']['weights']={'population':s['targets'][0]['value']['weights']}
    before=deepcopy(s);canonical=reader.inspect(c,s)
    assert canonical==expected and s==before
    notes=reader.wire_normalizations(s)
    assert notes[0]['action']=='UNWRAP_POPULATION_ONLY' and notes[0]['values_changed'] is False
    assert notes[0]['original']['population']==notes[0]['canonical']


@pytest.mark.parametrize('mutation',['extra_wrapper_content','missing_node','extra_node','numeric_value'])
def test_weight_wrapper_is_not_a_license_to_repair_content(tmp_path,mutation):
    c,d,t,s=fixture(tmp_path);target=s['targets'][0]['value'];w=target['weights']
    target['weights']={'population':w}
    if mutation=='extra_wrapper_content':target['weights']['normalization']='please normalize'
    if mutation=='missing_node':w.pop(target['population'][0])
    if mutation=='extra_node':w['not_in_target']='0'
    if mutation=='numeric_value':w[target['population'][0]]=0.75
    assert reader.wire_normalizations(s)==[]
    with pytest.raises(ValueError):reader.inspect(c,s)
