"""Independent source typing must veto a missed conditioning-object change."""
from copy import deepcopy
import json
import pytest
from cfm_id import observational_effect_entry as entry, joint_natural_entry as flow
from cfm_id_llm import observational_effect_source as reader, observational_condition_evidence as semantics
from cfm_id_llm.compact_study import digest
from test_observational_effect_entry import fixture, prepared


def mocked_inventory(case, wire):
    """Mock agreement for tests of later, unrelated gates (not a source oracle)."""
    s=reader.inspect(case,wire); statements=[]
    for code,(kind,conditioning) in {**semantics.SIGNATURES,**semantics.BASIC_SIGNATURES}.items():
        a=s['facts']['assumptions'][code]
        if a['value'] is None:continue
        statements.append(dict(kind=kind,conditioning=conditioning,conditioning_definition='test source definition',
            status='ADOPTED' if a['value'] else 'NOT_ADOPTED',question=None,explanation='mocked independent reading',
            evidence=reader.fields(case,s)['facts.assumptions.'+code]['evidence']))
    return dict(schema_version=2,binding=semantics.binding(case,s),scientific_approval=False,statements=statements)


def local_inventory(case, s, *, shared=False, status='ADOPTED'):
    evidence=[dict(source_id='question',quote=case['business_question'])]
    statements=[dict(kind=kind,conditioning=conditioning,conditioning_definition='',status='ADOPTED',
        evidence=reader.fields(case,s)['facts.assumptions.'+code]['evidence'],explanation='basic premise mock',question=None)
        for code,(kind,conditioning) in semantics.BASIC_SIGNATURES.items()]
    statements += [dict(kind='RESULT_SUFFICIENCY',conditioning='NONE',conditioning_definition='',status='ADOPTED',
        evidence=evidence,explanation='same state, same result',question=None),
        dict(kind='EXPOSURE_MEAN_EXCHANGEABILITY',conditioning='LOCAL_C_AND_W',conditioning_definition='own binary feature and neighbors feature count',
        status=status,evidence=evidence,explanation='conditional on local C',question='Which declaration applies?' if status=='CONFLICT' else None)]
    if shared:statements.append(dict(statements[-1],conditioning='SHARED_B_AND_W',conditioning_definition='explicit shared stratum'))
    return dict(schema_version=2,binding=semantics.binding(case,s),scientific_approval=False,statements=statements)


@pytest.mark.parametrize('persistent',[False,True])
def test_local_condition_cannot_also_approve_shared_stratum(persistent):
    from test_observational_contract_recovery import audit
    case,wire=fixture('nodewise')
    for code in ('full_vector_conditional_exchangeability','exposure_level_conditional_exchangeability'):
        wire['assumptions'][code]['value']=None
    bad=deepcopy(wire);bad['assumptions']['exposure_level_conditional_exchangeability']['value']=True
    original=deepcopy(bad);current=bad;stages=[]
    def call(req,stage):
        nonlocal current
        stages.append(stage)
        if stage=='joint_source_read':return bad
        if stage=='joint_source_read_retry1':
            assert 'SHARED_B_AND_W' in req['user_prompt']
            current=bad if persistent else wire;return current
        if stage.startswith('joint_source_audit'):return audit(case,current)
        assert stage.startswith('joint_condition_semantics') or stage=='joint_condition_reconcile'
        body=json.loads(req['user_prompt']);assert 'candidate' not in body
        return local_inventory(case,reader.inspect(case,current))
    r=entry.prepare(case,dict(draft={},draft_sha256=digest({}),checks=[]),call)
    assert bad==original and not r['backend_called'] and not r['clarification_questions']
    assert stages.count('joint_source_read_retry1')==1
    assert stages.count('joint_condition_reconcile')==1
    assert r['joint_entry']['state']==('READING_RECHECK_REQUIRED' if persistent else 'REVIEW_REQUIRED')
    first=r['joint_entry']['attempts'][0]
    assert all(f['verdict']=='MATCH' for f in first['original_audit']['findings'])
    assert any(f['verdict']=='READING_ERROR' and f['field'].endswith('exposure_level_conditional_exchangeability') for f in first['audit']['findings'])


def test_two_genuinely_declared_conditions_are_preserved():
    case,wire=fixture('nodewise');wire['assumptions']['full_vector_conditional_exchangeability']['value']=None
    wire['assumptions']['exposure_level_conditional_exchangeability']['value']=True
    s=reader.inspect(case,wire)
    receipt,findings=semantics.check(case,s,local_inventory(case,s,shared=True))
    assert all(f['verdict']=='MATCH' for f in findings)
    assert len(receipt['statements'])==6


@pytest.mark.parametrize('status,value,verdict', [('NOT_ADOPTED',False,'MATCH'),('NOT_INFERRED',None,'MATCH'),('NOT_INFERRED',False,'READING_ERROR'),('NOT_INFERRED',True,'READING_ERROR'),('PENDING',None,'MATCH'),('PENDING',False,'READING_ERROR'),('CONFLICT',None,'NEEDS_CLARIFICATION')])
def test_adoption_states_remain_distinct(status,value,verdict):
    case,wire=fixture('nodewise');wire['assumptions']['local_covariate_exposure_mean_exchangeability']['value']=value
    s=reader.inspect(case,wire);_,fs=semantics.check(case,s,local_inventory(case,s,status=status))
    assert next(f for f in fs if f['field'].endswith('local_covariate_exposure_mean_exchangeability'))['verdict']==verdict


def test_pending_known_condition_cannot_be_silently_relabelled_extra():
    case,wire=fixture('nodewise')
    wire['assumptions']['local_covariate_exposure_mean_exchangeability']['value']=None
    refs=wire['assumptions']['local_covariate_exposure_mean_exchangeability']['source_ids']
    wire['additional_restrictions']=[dict(text='该既有条件尚未决定',source_ids=refs)]
    s=reader.inspect(case,wire);before=deepcopy(s)
    inventory=local_inventory(case,s,status='PENDING')
    _,fs=semantics.check(case,s,inventory)
    assert any(f['field']=='coverage' and f['verdict']=='READING_ERROR' for f in fs)
    assert s==before  # no automatic deletion or adoption
    # A separate scientific restriction sharing the same source fragment must
    # remain a restriction; source overlap alone cannot prove redundancy.
    inventory['statements'].append(dict(inventory['statements'][0],kind='OTHER',conditioning='OTHER',
        status='ADOPTED',explanation='另有科学限制'))
    _,fs=semantics.check(case,s,inventory)
    assert not any(f['field']=='coverage' for f in fs)
    assert s==before


@pytest.mark.parametrize('raw',[None,[],{'statements':None}])
def test_malformed_inventory_has_bounded_recheck_request(raw):
    case,wire=fixture('nodewise');s=reader.inspect(case,wire)
    req=semantics.reconcile_request(case,s,raw,[],error='invalid inventory')
    body=json.loads(req['user_prompt'])
    assert body['source_passages_to_recheck']==[]
    assert 'candidate' not in body


def test_new_receipt_is_bound_but_old_saved_results_still_replay():
    case,wire=fixture('observed');r=prepared(case,wire)
    old=deepcopy(r)
    r['joint_entry']['condition_evidence']=semantics.check(case,r['joint_entry']['reading'],mocked_inventory(case,wire))[0]
    r=entry.plan(case,r)
    review=lambda x:dict(binding=x['condition_review']['binding'],authority='SYNTHETIC_TEST',decisions={i['code']:'ADOPTED' for i in x['condition_review']['items']})
    for saved in (r,old):
        result=entry.complete(case,saved,review(saved));assert flow.replay(case,{},result)
    changed=deepcopy(r);changed['joint_entry'].pop('condition_evidence')
    with pytest.raises(ValueError,match='PLAN_CHANGED'):entry.complete(case,changed,review(r))
    changed=deepcopy(r);changed['joint_entry']['condition_evidence']['binding']='stale'
    with pytest.raises(ValueError,match='EVIDENCE_STALE'):entry.complete(case,changed,review(r))


def test_pending_question_does_not_ask_about_an_unused_premise():
    case,wire=fixture('nodewise');wire['assumptions']['local_covariate_exposure_mean_exchangeability']['value']=None
    s=reader.inspect(case,wire);receipt=local_inventory(case,s,status='PENDING')
    receipt['statements'][-1]['question']='本次是否采用？'
    _,findings=semantics.check(case,s,receipt)
    finding=next(x for x in findings if x['field'].endswith('local_covariate_exposure_mean_exchangeability'))
    assert finding['verdict']=='MATCH' and finding['question'] is None
    receipt['statements'][-1].update(status='UNSTATED',question=None,evidence=[])
    semantics.check(case,s,receipt)
    receipt['statements'][-1]['status']='ADOPTED'
    with pytest.raises(ValueError,match='EVIDENCE_REQUIRED'):semantics.check(case,s,receipt)


@pytest.mark.parametrize('explicit_refusal',[False,True])
def test_inference_disclaimer_cannot_be_silently_promoted_to_refusal(explicit_refusal):
    case,wire=fixture('nodewise')
    sentence='不能由同伴状态的定义推出潜在结果相同。'
    if explicit_refusal:sentence+='本次明确不采用结果充分性。'
    case['sources'].append(dict(source_id='negation_scope',kind='OTHER',text=sentence))
    wire['reference_context']=reader.refs(case)['context']
    s=reader.inspect(case,wire)
    receipt=dict(binding=semantics.binding(case,s),scientific_approval=False,statements=[dict(
        kind='RESULT_SUFFICIENCY',conditioning='NONE',conditioning_definition='same own and peer state',
        status='NOT_ADOPTED',evidence=[dict(source_id='negation_scope',quote=sentence)],explanation='check negation scope',question=None)])
    if explicit_refusal:
        checked,fs=semantics.check(case,s,receipt)
        assert checked['statements'][0]['status']=='NOT_ADOPTED'
    else:
        with pytest.raises(ValueError,match='INFERENCE_DISCLAIMER'):semantics.check(case,s,receipt)


def test_consistency_cannot_cite_only_result_sufficiency():
    case,wire=fixture('observed')
    case['sources'] += [dict(source_id='actual',kind='OTHER',text='实际结果对应实际执行的完整安排。'),
                        dict(source_id='same_state',kind='OTHER',text='本人和同伴状态相同时潜在结果相同。')]
    catalog=reader.refs(case);wire['reference_context']=catalog['context']
    wrong=next(k for k,v in catalog['aliases'].items() if v['doc_id']=='same_state')
    right=next(k for k,v in catalog['aliases'].items() if v['doc_id']=='actual')
    wire['assumptions']['consistency']['source_ids']=[wrong]
    s=reader.inspect(case,wire);before=deepcopy(s);inventory=mocked_inventory(case,wire)
    next(x for x in inventory['statements'] if x['kind']=='CONSISTENCY')['evidence']=[dict(source_id='actual#L1')]
    _,findings=reader.check_semantics(case,s,inventory)
    assert next(x for x in findings if x['field']=='facts.assumptions.consistency')['verdict']=='READING_ERROR'
    assert s==before
    wire['assumptions']['consistency']['source_ids']=[right]
    fixed=reader.inspect(case,wire);inventory['binding']=semantics.binding(case,fixed)
    _,findings=reader.check_semantics(case,fixed,inventory)
    assert all(x['verdict']=='MATCH' for x in findings)


def test_current_inventory_requires_basic_conditions_and_version():
    case,wire=fixture('observed');s=reader.inspect(case,wire);inventory=mocked_inventory(case,wire)
    inventory['statements']=[x for x in inventory['statements'] if x['kind']!='CONSISTENCY']
    _,findings=reader.check_semantics(case,s,inventory)
    assert next(x for x in findings if x['field']=='facts.assumptions.consistency')['verdict']=='READING_ERROR'
    inventory.pop('schema_version')
    with pytest.raises(ValueError,match='VERSION_REQUIRED'):reader.check_semantics(case,s,inventory)
    # Historical receipt compatibility is explicit; no new premise is added.
    receipt,_=reader.check_semantics(case,s,inventory,historical=True)
    assert 'schema_version' not in receipt


def test_failed_semantic_recheck_consumes_its_budget_and_keeps_failure():
    from test_observational_contract_recovery import audit
    case,wire=fixture('observed');stages=[]
    def call(req,stage):
        stages.append(stage)
        if stage.startswith('joint_source_read'):return wire
        if stage.startswith('joint_source_audit'):return audit(case,wire)
        return None  # inventory and its one recheck both violate the contract
    r=entry.prepare(case,dict(draft={},draft_sha256=digest({}),checks=[]),call)
    assert stages.count('joint_condition_reconcile')==1
    assert stages.count('joint_source_read_retry1')==1
    assert r['joint_entry']['state']=='READING_RECHECK_REQUIRED' and not r['backend_called']
    assert len(r['joint_entry']['semantic_repairs'])==1
    assert r['joint_entry']['semantic_repairs'][0]['recheck_error']
