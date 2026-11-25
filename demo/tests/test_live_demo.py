"""Browser adapter contracts. Reference replies are fixtures, not LLM scores."""
from copy import deepcopy
import base64
import http.client
import json
import threading
import time

import pytest

from demo.backend.engine import Engine, Run, project, intake
from demo.backend.server import make_server
from reference import fixture, a0_candidate, fact_candidate


def wait(run):
    deadline=time.monotonic()+15
    while run.busy and time.monotonic()<deadline:time.sleep(.01)
    assert not run.busy
    return run


def fixture_review(run):
    """Only used for the independently stipulated fictional regression fixture."""
    records=deepcopy(run.review_templates)
    for name,record in records.items():
        record.update(reviewer='Offline fixture reviewer',evidence='Fictional original conditions checked for software regression only.')
        sheet=run.review_sheets[name]
        for path,decision in record.get('decisions',{}).items():
            if isinstance(decision,dict):
                decision.update(field_role='ACCEPTED',value_state='ACCEPTED',source_coverage='ACCEPTED',
                    reason='Compared to independently written fictional materials; no real scientific approval.',
                    source_ids=list(sheet['source_catalog']))
            else:record['decisions'][path]='ACCEPTED'
    return dict(kind=run.review_kind,records=records)


def reading_fixture(tmp_path, monkeypatch, *, missing=False):
    engine=Engine(tmp_path/'runs');case,info=fixture()
    run=Run(owner='tester',synthetic=True,case=case.model_dump(mode='json'))
    engine.runs[run.id]=run;run.intake=project.start(case)
    request=intake.prepare_request(run.intake)
    run.intake=intake.receive_candidate(run.intake,a0_candidate(run.intake,info),request_sha256=request['request_sha256'])
    run.queries=intake.inspect(run.intake)['report']['draft']['queries']
    def reply(run,request,stage):
        assert stage=='facts'
        raw=fact_candidate(request,info)
        if missing:raw['scientific_statements']['consistency']={'status':'NOT_STATED','source_ids':[]}
        return raw
    monkeypatch.setattr(engine,'call',reply)
    engine._select(run,'q1')
    return engine,run


def test_browser_reference_chain_point_and_replay(tmp_path,monkeypatch):
    engine,run=reading_fixture(tmp_path,monkeypatch)
    visited=[]
    for _ in range(8):
        if not run.review_kind:break
        visited.append(run.review_kind)
        engine._review(run,fixture_review(run))
    assert visited==['query','source','science']
    assert run.result['state']=='POINT'
    assert run.result['independent_replay'] is True
    assert run.result['mathematical_claim']['target']['kind']=='DIRECT_EFFECT'
    assert not engine.view('tester',run.id)['can_estimate']  # No data was supplied.


@pytest.mark.parametrize('status',['PENDING','REJECTED'])
def test_browser_pending_or_rejected_target_never_calls_model(tmp_path,monkeypatch,status):
    engine,run=reading_fixture(tmp_path,monkeypatch)
    def forbidden(*args):pytest.fail('Model called before approval')
    monkeypatch.setattr(engine,'call',forbidden)
    review=fixture_review(run)
    next(iter(review['records']['query']['decisions'].values()))['value_state']=status
    engine._review(run,review)
    assert run.result['state']!='READY_TO_READ'
    assert run.submission is None


def test_browser_missing_science_never_certifies(tmp_path,monkeypatch):
    engine,run=reading_fixture(tmp_path,monkeypatch,missing=True)
    for _ in range(8):
        if not run.review_kind:break
        engine._review(run,fixture_review(run))
    assert run.result['state']=='NEEDS_INPUT'
    assert run.result.get('independent_replay') is not True


def test_browser_review_binding_cannot_be_reused(tmp_path,monkeypatch):
    engine,run=reading_fixture(tmp_path,monkeypatch)
    review=fixture_review(run);review['records']['query']['binding_sha256']='0'*64
    with pytest.raises(ValueError,match='STALE_OR_WRONG_AUTHORITY'):engine._review(run,review)


def test_key_not_persisted_and_owner_isolation(tmp_path):
    engine=Engine(tmp_path/'runs');key='test-only-not-a-real-key'
    engine.credential('a','longcat',key)
    run=Run(owner='a');engine.runs[run.id]=run
    engine.save(run,'receipt',{'message':'prefix '+key})
    assert key not in json.dumps(engine.health('a'))
    assert key not in (engine.storage/run.id/'receipt.json').read_text('utf8')
    with pytest.raises(ValueError,match='RUN_NOT_FOUND'):engine.view('b',run.id)
    engine.credential('a','longcat','');assert not engine.health('a')['configured']


def test_classic_upload_csv_does_not_send_outcome_rows(tmp_path,monkeypatch):
    engine=Engine(tmp_path/'runs')
    def stop(*args):raise ValueError('STOP_BEFORE_REAL_MODEL')
    monkeypatch.setattr(engine,'call',stop)
    text='store,outcome\na,987654321\nb,123456789\n'
    rid=engine.start('a',dict(question='比较门店使用工具与不使用的结果',allow_send=True,reading_mode='classic',files=[
        dict(name='sample.csv',role='document',content=base64.b64encode(text.encode()).decode())]))
    run=wait(engine.get('a',rid));sent=json.dumps(run.case)
    assert '987654321' not in sent and '123456789' not in sent
    assert run.attachment_report['attachments'][0]['mode']=='SCHEMA_ONLY'
    assert run.error['message']=='STOP_BEFORE_REAL_MODEL'


@pytest.mark.parametrize('name,role,content,expected',[
    ('../escape.txt','document',b'ok','UPLOAD_NAME_INVALID'),
    ('schema.json','data_schema',b'{}','IDENTIFICATION_DOCUMENT_UPLOAD_ONLY'),
    ('run.py','document',b'print(1)','unsupported'),
])
def test_invalid_uploads_stop_without_provider(tmp_path,monkeypatch,name,role,content,expected):
    engine=Engine(tmp_path/'runs');monkeypatch.setattr(engine,'call',lambda *a:pytest.fail('Unexpected API call'))
    rid=engine.start('a',dict(question='完整的门店业务问题',allow_send=True,files=[
        dict(name=name,role=role,content=base64.b64encode(content).decode())]))
    run=wait(engine.get('a',rid))
    assert run.stage=='STOPPED' and run.error is not None
    assert expected.lower() in run.error['message'].lower()


def test_explicit_document_consent_required(tmp_path):
    engine=Engine(tmp_path/'runs')
    with pytest.raises(ValueError,match='CONSENT'):engine.start('a',dict(question='测试业务问题'))
    assert not engine.runs


def test_edited_example_sources_are_new_input_not_saved_result(tmp_path,monkeypatch):
    engine=Engine(tmp_path/'runs')
    def stop(*args):raise ValueError('STOP_BEFORE_REAL_MODEL')
    monkeypatch.setattr(engine,'call',stop)
    rid=engine.start('a',dict(question='只评价第一家门店的结果。',allow_send=True,example_id='n100',
        source_edits=[dict(source_id='science',text='负责人尚未决定是否采用一致性。')]))
    run=wait(engine.get('a',rid))
    assert [s['source_id'] for s in run.case['sources']]==['science']
    assert run.case['sources'][0]['text']=='负责人尚未决定是否采用一致性。'
    assert run.result is None and not run.reviews and not run.synthetic


def test_http_csrf_and_static_isolation(tmp_path):
    engine=Engine(tmp_path/'runs');server=make_server(engine,0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
    try:
        connection.request('GET','/');response=connection.getresponse();cookie=response.headers['Set-Cookie'].split(';')[0]
        assert response.status==200;homepage=response.read()
        assert b'/vendor/katex/katex.min.js' in homepage and b'/model-math.js' in homepage
        assert b'/symbolic-bounds.js' in homepage
        for asset in ('/model-math.js','/symbolic-bounds.js','/vendor/katex/katex.min.js'):
            connection.request('GET',asset);response=connection.getresponse()
            assert response.status==200 and 'text/javascript' in response.headers['Content-Type']
            assert "script-src 'self'" in response.headers['Content-Security-Policy']
            assert len(response.read())>1000
        connection.request('GET','/vendor/katex/../backend/engine.py',headers={'Cookie':cookie})
        response=connection.getresponse();assert response.status==404;response.read()
        connection.request('GET','/api/health',headers={'Cookie':cookie});response=connection.getresponse()
        health=json.loads(response.read());assert health['reading_config']['a0_response_contract']=='target-first-skill-1'
        connection.request('POST','/api/credentials','{}',headers={'Cookie':cookie,'Content-Type':'application/json'})
        response=connection.getresponse();assert response.status==403;response.read()
        connection.request('GET','/../input/case.json',headers={'Cookie':cookie})
        response=connection.getresponse();assert response.status==404;response.read()
        connection.request('POST','/api/credentials',json.dumps({'provider':'longcat','key':'fixture-key'}),
            headers={'Cookie':cookie,'Content-Type':'application/json','X-CSRF-Token':health['csrf']})
        response=connection.getresponse();body=response.read();assert response.status==200 and b'fixture-key' not in body
    finally:connection.close();server.shutdown();server.server_close();thread.join(2)
