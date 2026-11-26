from copy import deepcopy
import json
from fractions import Fraction as F
import pytest
from cfm_id import joint_query_exchange as exchange, joint_natural_entry as flow, local_bundle_entry as entry
from demo.tests.test_local_bundle_entry import fixture,planned,approved


def finished(tmp_path,shared=False):
    c,d,t,s=fixture(tmp_path)
    if shared:
        a=s['targets'][0]['value'];b=s['targets'][1]['value']
        b.update(population=deepcopy(a['population']),weights=deepcopy(a['weights']))
    r=planned(c,d,s,t)
    return c,entry.complete(c,r,approved(r))


@pytest.mark.parametrize('shared,queries',[(False,8),(True,4)])
def test_separate_outputs_exact_coefficients_and_shared_queries(tmp_path,shared,queries):
    c,r=finished(tmp_path,shared);p=exchange.packet(c,r);h=p['estimate_handoff']
    receipt=exchange.check_packet(c['case_id'],p)
    assert p['operator_revision']==5 and receipt['query_count']==queries and receipt['target_count']==2
    assert not receipt['estimator_executed'] and not p['production_admission']
    from cfm_id.method_catalog import homepage_entries
    advertised=next(x for x in homepage_entries() if x['entry_id']=='RANDOMIZED_LOCAL_BUNDLE_SOURCE')
    assert advertised['estimation_handoff_allowed'] and not advertised['estimator_execution']
    assert h['mode'] in advertised['handoff_scope']
    values={q['id']:str(q['own']) for q in h['queries']}
    assert exchange.evaluate(h,values)=={'q1':'1','q2':'-1'}  # Opposite questions must not cancel.
    assert h['operator_spec']['study']['network']==r['joint_entry']['reading']['network']['value']
    for output,part in zip(h['operator_spec']['outputs'],r['joint_entry']['parts']):
        assert output['target']==part['target'] and output['certificate_sha256']==part['native_evidence']['certificate_sha256']
    with pytest.raises(ValueError,match='REVISION'):exchange.packet(c,r,operator_revision=4)


@pytest.mark.parametrize('mutation',['weight','roster','direction','coefficient','study','source','review','run'])
def test_changed_scope_or_query_rejected(tmp_path,mutation):
    c,r=finished(tmp_path);p=exchange.packet(c,r);h=p['estimate_handoff']
    if mutation=='weight':h['operator_spec']['outputs'][0]['target']['weights']['谷口']='1'
    if mutation=='roster':h['operator_spec']['study']['network']['nodes'].pop()
    if mutation=='direction':h['operator_spec']['outputs'][0]['target']['first']['own']=0
    if mutation=='coefficient':h['operator_spec']['outputs'][0]['operands'][h['queries'][0]['id']]='9'
    if mutation=='study':h['operator_spec']['study']['study']['period']='another period'
    if mutation=='source':p['source_case']['business_question']='another question'
    if mutation=='review':p['source_report']['review_record']['decisions']['consistency']='UNSURE'
    if mutation=='run':p['run_id']='different-run'
    with pytest.raises(ValueError):exchange.check_packet(c['case_id'],p)


def test_incomplete_bundle_is_not_delivered(tmp_path):
    c,d,t,s=fixture(tmp_path);s['targets'][1]['value']['fixed_before_assignment']=False
    r=planned(c,d,s,t);r=entry.complete(c,r,approved(r))
    assert flow.replay(c,d,r) and r['joint_entry']['parts'][0]['state']=='POINT'
    with pytest.raises(ValueError):exchange.packet(c,r)


def test_engine_delivery_receipt_replay_and_revocation(tmp_path):
    from demo.backend.engine import Engine,Run
    c,r=finished(tmp_path);engine=Engine(tmp_path/'engine');run=Run(owner='test',id=c['case_id'],case=c,synthetic=True,reading_mode='direct_verify')
    engine.runs[run.id]=run;engine._finish_direct_verification(run,r)
    assert run.result['estimation_handoff_allowed'] and flow.replay(c,r['draft'],run.result)
    path=engine.estimate_inbox.path_for(run.id);saved=json.loads(path.read_text('utf8'))
    assert saved['receipt']['state']=='QUEUED' and saved['receipt']['target_count']==2
    review=deepcopy(r['review_record']);review['decisions']['consistency']='DECLINED'
    engine._finish_direct_verification(run,entry.complete(c,r,review))
    assert not run.result['estimation_handoff_allowed']
    assert json.loads(path.read_text('utf8'))['receipt']['state']=='SUPERSEDED'


def test_failed_replay_removes_previously_displayed_bundle_and_receipt(tmp_path):
    from demo.backend.engine import Engine,Run
    c,r=finished(tmp_path);engine=Engine(tmp_path/'engine');run=Run(owner='test',id=c['case_id'],case=c,synthetic=True,reading_mode='direct_verify')
    engine.runs[run.id]=run;engine._finish_direct_verification(run,r)
    forged=deepcopy(run.result);forged['joint_entry']['parts'][0]['native_evidence']['terms'][0]['coefficient']='99'
    with pytest.raises(ValueError,match='JOINT_REPLAY_REQUIRED'):
        engine._finish_direct_verification(run,forged)
    assert run.result['joint_entry']['state']=='RECHECK_REQUIRED'
    assert not run.result['joint_entry'].get('parts') and not run.result.get('proof')
    assert not run.result['estimation_handoff_allowed'] and not run.result['independent_replay']
    assert json.loads(engine.estimate_inbox.path_for(run.id).read_text('utf8'))['receipt']['state']=='SUPERSEDED'


def test_missing_mean_or_boolean_value_is_not_a_number(tmp_path):
    c,r=finished(tmp_path);h=exchange.packet(c,r)['estimate_handoff']
    with pytest.raises(ValueError):exchange.evaluate(h,{})
    with pytest.raises(ValueError):exchange.evaluate(h,{q['id']:True for q in h['queries']})
