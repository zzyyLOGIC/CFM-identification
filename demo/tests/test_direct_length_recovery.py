"""Default entry retries complete responses, without sparse-audit instructions."""
from copy import deepcopy
import pytest
from demo.backend.engine import Engine, Run
from cfm_id_llm.providers.base import ProviderError


@pytest.mark.parametrize('stage',['direct_draft','joint_source_read','joint_source_audit','joint_gap_review','network_source_route','joint_condition_semantics','joint_source_format_retry'])
def test_retry_keeps_source_schema_and_complete_adverse_answer(tmp_path,monkeypatch,stage):
    e=Engine(tmp_path);r=Run(owner='offline');seen=[]
    request=dict(system_prompt='All fields required',user_prompt='frozen sources and schema')
    before=deepcopy(request);adverse={'findings':[{'field':'x','verdict':'READING_ERROR'}]}
    def call(run,req,name):
        seen.append((deepcopy(req),name))
        if len(seen)==1:raise ProviderError('length',code='INCOMPLETE_COMPLETION',diagnostics={'finish_reason':'length'})
        return adverse
    monkeypatch.setattr(e,'call',call)
    assert e._call_direct(r,request,stage)==adverse
    assert request==before and seen[1][0]['user_prompt']==request['user_prompt']
    assert '只列错误' not in seen[1][0]['system_prompt']
    assert seen[1][1]==stage+'_length_retry' and not r.reviews and r.result is None


def test_shared_phase_limit_includes_source_reread_and_audit_format_retry(tmp_path,monkeypatch):
    e=Engine(tmp_path);r=Run(owner='offline');stages=[]
    def call(run,request,stage):
        stages.append(stage)
        raise ProviderError('length',code='INCOMPLETE_COMPLETION',diagnostics={'finish_reason':'length'})
    monkeypatch.setattr(e,'call',call)
    for stage in ('joint_source_audit','joint_source_audit_retry1','joint_audit_format_retry'):
        with pytest.raises(ProviderError):e._call_direct(r,dict(system_prompt='',user_prompt=''),stage)
    assert stages==['joint_source_audit','joint_source_audit_length_retry','joint_source_audit_retry1','joint_audit_format_retry']
    assert r.automatic_direct_length_retries=={'joint_source_audit'}


@pytest.mark.parametrize('code,reason',[
    ('INCOMPLETE_COMPLETION','content_filter'),('INCOMPLETE_COMPLETION',None),
    ('MODEL_REFUSAL','stop'),('HTTP_ERROR',None)])
def test_other_failures_not_retried(tmp_path,monkeypatch,code,reason):
    e=Engine(tmp_path);r=Run(owner='offline');calls=[]
    def call(*args):
        calls.append(1);raise ProviderError('bounded',code=code,diagnostics={'finish_reason':reason})
    monkeypatch.setattr(e,'call',call)
    with pytest.raises(ProviderError):e._call_direct(r,{},'direct_draft')
    assert len(calls)==1 and not r.automatic_direct_length_retries


def test_timeout_retries_exact_request_once_and_keeps_an_adverse_answer(tmp_path, monkeypatch):
    e=Engine(tmp_path);r=Run(owner='offline');seen=[]
    request=dict(system_prompt='Complete contract',user_prompt='Unchanged original materials')
    adverse={'status':'NEEDS_INPUT'}
    def call(run, req, stage):
        seen.append((deepcopy(req),stage))
        if len(seen)!=2:raise ProviderError('timeout',code='TIMEOUT')
        return adverse
    monkeypatch.setattr(e,'call',call)
    assert e._call_direct(r,request,'direct_draft')==adverse
    assert seen==[(request,'direct_draft'),(request,'direct_draft_timeout_retry')]
    with pytest.raises(ProviderError):e._call_direct(r,request,'joint_source_read')
    assert len(seen)==3 and r.automatic_direct_transport_retries==1
    assert not r.reviews and r.result is None


def test_default_workflow_callback_uses_recovery(tmp_path,monkeypatch):
    from demo.backend import engine as module
    e=Engine(tmp_path);r=Run(owner='offline',reading_mode='direct_verify');stages=[];finished=[]
    def call(run,request,stage):
        stages.append(stage)
        if len(stages)==1:
            raise ProviderError('length',code='INCOMPLETE_COMPLETION',diagnostics={'finish_reason':'length'})
        return {'complete_reply':True}
    def pipeline(case,request_callback,**kwargs):
        return request_callback(dict(system_prompt='complete contract',user_prompt='all sources'),'joint_source_audit')
    monkeypatch.setattr(e,'call',call)
    monkeypatch.setattr(module.project,'direct_then_verify',pipeline)
    monkeypatch.setattr(e,'_finish_direct_verification',lambda run,result:finished.append(result))
    e._direct_verify(r)
    assert stages==['joint_source_audit','joint_source_audit_length_retry']
    assert finished==[{'complete_reply':True}] and r.result is None


@pytest.mark.parametrize('code',['INCOMPLETE_COMPLETION','TIMEOUT'])
def test_exhausted_length_error_does_not_ask_for_business_conditions(tmp_path,code):
    import time
    e=Engine(tmp_path);r=Run(owner='offline')
    def fail(run):
        raise ProviderError('bounded',code=code,diagnostics={'finish_reason':'length'} if code=='INCOMPLETE_COMPLETION' else {})
    e.launch(r,fail)
    deadline=time.monotonic()+5
    while r.busy and time.monotonic()<deadline:time.sleep(.01)
    assert not r.busy and r.error['code']==code
    assert '不需要补' in r.error['message'] and r.result is None
