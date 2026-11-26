from copy import deepcopy
import json
from types import SimpleNamespace

import pytest
from demo.backend import fact_wire_recovery as wire
from demo.backend.engine import Engine, Run
from cfm_id_llm.providers.base import ProviderError


def candidate():
    return dict(study={'nodes':['a','b','c']}, target={'own':1},
                assignment=dict(kind='INDEPENDENT_BERNOULLI', probabilities=None, source_ids=['s1']),
                scientific_statements={'randomization':'UNDECIDED'}, additional_restrictions=['keep'])


def entry():
    schema=dict(type='object',properties={'assignment':{'$ref':'#/$defs/Assignment'},
        'study':{'type':'object'},'target':{'type':'object'}},
        **{'$defs':{'Assignment':{'type':'object','properties':{'probabilities':{'type':['object','null']}}}}})
    return dict(request_sha256='reviewed-request',request=dict(system='Original Skill stays.',
        user=json.dumps(dict(question='Original question',source_catalog={'s1':{'text':'An explicit rule'}},output_schema=schema))))


def feedback():
    return {'issues':[{'field_path':'/assignment','reason':'Check the source, not a replacement value.'}]}


def test_uniform_expansion_keeps_all_other_fields_and_missing_values_missing():
    raw=candidate();raw['assignment']['probabilities']={'each_study_node':True,'value':'2/5'}
    got=wire.expand(raw)
    assert got['assignment']['probabilities']=={'a':'2/5','b':'2/5','c':'2/5'}
    assert raw['assignment']['probabilities']=={'each_study_node':True,'value':'2/5'}
    for key in raw.keys()-{'assignment'}:assert got[key]==raw[key]
    assert wire.expand(candidate())['assignment']['probabilities'] is None
    partial=candidate();partial['assignment']['probabilities']={'a':'1/3'}
    assert wire.expand(partial)==partial
    named=candidate();named['assignment']['probabilities']={'each_study_node':'1/3','value':'2/5'}
    assert wire.expand(named)==named


@pytest.mark.parametrize('change', ['wrong_design','uncited','unknown_scope','invalid_probability','empty'])
def test_uniform_rejects_invalid_scope_or_invented_design(change):
    raw=candidate();raw['assignment']['probabilities']={'each_study_node':True,'value':'2/5'}
    if change=='wrong_design':raw['assignment']['kind']='UNIFORM_FIXED_QUOTA'
    if change=='uncited':raw['assignment']['source_ids']=[]
    if change=='unknown_scope':raw['study']['nodes']=[]
    if change=='invalid_probability':raw['assignment']['probabilities']['value']='3/2'
    if change=='empty':raw['assignment']['probabilities']={}
    with pytest.raises(wire.FactWireError):wire.expand(raw)


def test_field_patch_is_bound_and_cannot_change_target_or_drop_restrictions():
    original=candidate();request,receipt=wire.field_request(wire.prepare(entry()),original,feedback())
    body=json.loads(request['request']['user'])
    assert body['source_catalog']==json.loads(entry()['request']['user'])['source_catalog']
    assert request['request']['system'].startswith('Original Skill stays.')
    assert set(body['output_schema']['properties']['fields']['properties'])=={'assignment'}
    answer={'binding_sha256':receipt['binding_sha256'],'fields':{'assignment':{**original['assignment'],'probabilities':{'a':'2/5','b':'2/5','c':'2/5'}}}}
    got=wire.merge(answer,receipt)
    assert got['target']==original['target'] and got['scientific_statements']==original['scientific_statements']
    assert got['additional_restrictions']==['keep']
    bad=deepcopy(answer);bad['fields']['target']={'own':0}
    with pytest.raises(wire.FactWireError):wire.merge(bad,receipt)
    bad=deepcopy(answer);bad['binding_sha256']='stale'
    with pytest.raises(wire.FactWireError):wire.merge(bad,receipt)
    assert wire.field_request(entry(),original,{'issues':[{'field_path':'/unknown'}]}) is None


def test_patch_uses_current_source_context_without_editing_business_content():
    original=candidate();original['reference_context']='old-source-context'
    e=entry();body=json.loads(e['request']['user']);body['reference_context']='current-source-context'
    e['request']['user']=json.dumps(body)
    request,receipt=wire.field_request(wire.prepare(e),original,feedback())
    got=wire.merge({'binding_sha256':receipt['binding_sha256'],
        'fields':{'assignment':original['assignment']}},receipt)
    assert got=={**original,'reference_context':'current-source-context'}
    assert original['reference_context']=='old-source-context'
    assert wire.field_request(entry(),original,feedback()) is None


def test_located_reread_retries_only_timeout_once_then_preserves_review(tmp_path,monkeypatch):
    engine=Engine(tmp_path);run=Run(owner='offline',submission={'candidate':candidate()})
    calls=[]
    def send(r,request,stage):
        calls.append(stage)
        if len(calls)==1:raise ProviderError('timeout',code='TIMEOUT')
        body=json.loads(request['request']['user'])
        return {'binding_sha256':body['output_schema']['properties']['binding_sha256']['const'],
                'fields':{'assignment':{**candidate()['assignment'],'probabilities':{'each_study_node':True,'value':'2/5'}}}}
    monkeypatch.setattr(engine,'call',send)
    result=engine._read_facts(run,entry(),feedback=feedback())
    assert calls==['facts_field_patch','facts_field_patch_timeout_retry']
    assert result['assignment']['probabilities']=={'a':'2/5','b':'2/5','c':'2/5'}
    assert run.automatic_fact_transport_retries==1 and run.reviews=={} and run.result is None
    assert run.artifacts['facts_field_recovery']['requires_full_source_review'] is True
    assert run.artifacts['facts_field_recovery']['scientific_approval'] is False


@pytest.mark.parametrize('code', ['HTTP_ERROR','MODEL_REFUSAL','TIMEOUT'])
def test_nonretryable_or_exhausted_failures_are_not_silently_accepted(tmp_path,monkeypatch,code):
    engine=Engine(tmp_path);run=Run(owner='offline',submission={'candidate':candidate()},automatic_fact_transport_retries=1)
    calls=[]
    def send(*args):calls.append(args[-1]);raise ProviderError('stop',code=code)
    monkeypatch.setattr(engine,'call',send)
    with pytest.raises(ProviderError):engine._read_facts(run,entry(),feedback=feedback())
    assert calls==['facts_field_patch'] and run.result is None and not run.reviews


def test_field_stage_uses_fact_request_envelope(tmp_path):
    captured=[]
    class Client:
        last_diagnostics={}
        api_key=None
        def generate_json(self,**kwargs):captured.append(kwargs);return {'ok':True}
    engine=Engine(tmp_path,provider_factory=lambda **kw:Client())
    engine.credential('offline','longcat','offline-key')
    run=Run(owner='offline',provider='longcat')
    assert engine.call(run,entry(),'facts_field_patch')=={'ok':True}
    assert captured==[{'system_prompt':entry()['request']['system'],'user_prompt':entry()['request']['user']}]


def test_retry_resumes_pending_field_request_not_old_review(tmp_path,monkeypatch):
    engine=Engine(tmp_path)
    run=Run(owner='offline',pending_fact_recheck={'entry':entry(),'feedback':feedback()})
    calls=[]
    monkeypatch.setattr(engine,'_recheck',lambda r,e,f:calls.append((r.id,e,f)))
    engine._retry_reading(run)
    assert calls==[(run.id,entry(),feedback())]
    assert run.result is None


def test_successful_patch_invalidates_old_reviews_and_keeps_full_plan(tmp_path,monkeypatch):
    engine=Engine(tmp_path);before=candidate();e=entry();e['reading_revision']={'steps':[{}]}
    run=Run(owner='offline',submission={'candidate':before},query_review={'kept':True},reviews={'old':'not-reusable'})
    after=deepcopy(before);after['assignment']['probabilities']={'a':'2/5','b':'2/5','c':'2/5'}
    monkeypatch.setattr(engine,'_read_facts',lambda r,req,feedback:after)
    planned=[]
    monkeypatch.setattr(engine,'_plan',lambda r:planned.append(deepcopy(r.submission)))
    engine._recheck(run,e,feedback())
    assert planned[0]['candidate']==after and planned[0]['query_review']=={'kept':True}
    assert run.reviews=={} and run.result is None and run.pending_fact_recheck is None
