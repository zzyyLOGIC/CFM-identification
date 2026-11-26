"""Reviewer protocol, not a test of model semantic accuracy."""
from copy import deepcopy
import json
import pytest
import jsonschema
from test_user_workflow import automatic_fixture
from test_live_demo import fixture_review
from demo.backend import automatic_review as audit

def issue(kind='READING_ERROR',question=None):
    return dict(kind=kind,field='f',reason='候选把原文的比较方向写反了',question=question,source_ids=['s'])

def answer(*issues):
    return dict(scientific_approval=False,findings=list(issues))


def focused_answer(field,source,*,matches=False):
    return dict(scientific_approval=False,assessments=[dict(field=field,source_ids=[source],
        comparison='原文的比较方向与当前候选不一致' if not matches else '原文两端与当前候选相符',
        matches_source=matches,question=None)])


def test_focused_error_keeps_ownership_diagnostic_but_cannot_silently_release_it():
    path='source:/additional_restrictions/0'
    first=dict(verdict='READING_ERROR',scientific_approval=False,issues=[dict(
        issue(),field=path,restriction_role='ALREADY_REPRESENTED')],confirmed=[])
    second=dict(verdict='READING_ERROR',scientific_approval=False,issues=[dict(issue(),field=path)],confirmed=[])
    combined=audit.reconcile(first,second,{path:{}})
    assert combined['verdict']=='READING_ERROR'
    assert combined['issues'][0]['prior_restriction_role']=='ALREADY_REPRESENTED'
    assert 'prior_restriction_role' not in second['issues'][0]
    # A genuine clarification stays a clarification, never a duplicate edit.
    uncertain=dict(second,verdict='NEEDS_CLARIFICATION',issues=[dict(
        issue('NEEDS_CLARIFICATION','这个条件是否适用于全部对象？'),field=path)])
    result=audit.reconcile(first,uncertain,{path:{}})
    assert result['verdict']=='NEEDS_CLARIFICATION'
    assert 'prior_restriction_role' not in result['issues'][0]

def test_current_contract_derives_status_without_asking_user_to_repair_model():
    assert audit.check(answer(),{}, {},require_current=True)['verdict']=='PASS'
    error=audit.check(answer(issue()),{'f':{}},{'s':{}},require_current=True)
    assert error['verdict']=='READING_ERROR' and error['issues'][0]['question'] is None
    unclear=issue('NEEDS_CLARIFICATION','本次评价全部设计师还是指定的小组？')
    assert audit.check(answer(unclear),{'f':{}},{'s':{}},require_current=True)['verdict']=='NEEDS_CLARIFICATION'
    assert audit.check(answer(unclear,issue()),{'f':{}},{'s':{}},require_current=True)['verdict']=='READING_ERROR'


def review_contract_fixture(candidate, raw_fields):
    from types import SimpleNamespace
    run=SimpleNamespace(review_kind='source',review_sheets={'source':dict(
        fields=raw_fields,source_catalog={'s':'完整原文，包含本题总体信息和条件。'})},
        review_templates={'source':dict(decisions={p:'PENDING' for p in raw_fields})},
        submission=dict(candidate=candidate),entry=None)
    request,fields,sources=audit.request(run)
    return json.loads(request['user_prompt']),fields,sources


def test_whole_reading_match_is_not_a_scientific_closure_assertion():
    body,fields,sources=review_contract_fixture({}, {
        '':dict(scope='WHOLE_READING_COMPLETENESS_NOT_A_SHARED_CITATION'),
        '/closure':dict(candidate=dict(value=True,source_ids=['s']))})
    match=dict(kind='MATCH',field='source:',reason='逐项核对原文，未发现遗漏。',question=None,source_ids=[])
    jsonschema.validate(answer(match),body['output_schema'])
    assert audit.check(answer(match),fields,sources,require_current=True)['verdict']=='PASS'
    # A root error must locate the omitted/misread source. A real closure claim
    # is still a claim even when the reviewer calls it a whole-reading match.
    for changed in (dict(match,kind='READING_ERROR'),dict(match,field='source:/closure')):
        with pytest.raises(jsonschema.ValidationError):jsonschema.validate(answer(changed),body['output_schema'])
        with pytest.raises(audit.AuditContractError) as exc:audit.check(answer(changed),fields,sources,require_current=True)
        assert exc.value.details['field']==changed['field']


def test_residuals_require_explicit_judgment_without_automatic_deduplication():
    candidate=dict(closure=dict(value=True,source_ids=['s']),
        additional_restrictions=[dict(text='同句也包含另一项实际限制。',source_ids=['s'])])
    before=deepcopy(candidate)
    body,fields,sources=review_contract_fixture(candidate,{
        '/closure':dict(candidate=candidate['closure']),
        '/additional_restrictions/0':dict(candidate=candidate['additional_restrictions'][0])})
    path='source:/additional_restrictions/0';schema=body['output_schema']
    assert fields[path]['ownership_check']['related_typed_fields']==['/closure']
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(answer(),schema)
    with pytest.raises(audit.AuditContractError) as exc:audit.check(answer(),fields,sources,require_current=True)
    assert exc.value.details['fields']==[path]
    match=dict(kind='EXTRA_CONDITION',field=path,reason='另有真实限制，共用出处不等于重复。',question=None,source_ids=['source:s'])
    for kind,expected in [('EXTRA_CONDITION','PASS'),('ALREADY_REPRESENTED','READING_ERROR'),('NOT_A_CONDITION','READING_ERROR')]:
        response=answer(dict(match,kind=kind));jsonschema.validate(response,schema)
        assert audit.check(response,fields,sources,require_current=True)['verdict']==expected
    with pytest.raises(ValueError):audit.check(answer(dict(match,kind='MATCH')),fields,sources,require_current=True)
    with pytest.raises(ValueError):audit.check(answer(match,match),fields,sources,require_current=True)
    first=audit.check(answer(dict(match,kind='ALREADY_REPRESENTED')),fields,sources,require_current=True)
    request=dict(system_prompt=audit.SYSTEM,user_prompt=json.dumps(body))
    focused,disputed=audit.focused_request(request,fields,first)
    focused_body=json.loads(focused['user_prompt'])
    assert 'required_finding_fields' not in focused_body
    assert 'ALREADY_REPRESENTED' not in focused_body['fields'][path]['ownership_check']['rule']
    for matches in (False,True):
        response=focused_answer(path,'source:s',matches=matches)
        jsonschema.validate(response,focused_body['output_schema'])
        result=audit.check_focused(response,disputed,sources)
        assert result['verdict']==('PASS' if matches else 'READING_ERROR')
    assert candidate==before  # The checked scientific adapter still owns admission.

@pytest.mark.parametrize('bad',[
    issue(question='请确认系统是否读对'),issue('NEEDS_CLARIFICATION'),
    {**issue(),'source_ids':['missing']},{**issue(),'field':'missing'},
])
def test_incomplete_question_or_evidence_cannot_pass(bad):
    with pytest.raises(ValueError):audit.check(answer(bad),{'f':{}},{'s':{}},require_current=True)

def test_runtime_never_turns_self_withdrawn_prose_into_pass():
    # Even if prose says the candidate is correct, no text heuristic removes
    # the model's declared error. Independent semantic adjudication is required.
    response=answer({**issue(),'reason':'重新核对以后候选正确，但我仍然输出错误'})
    assert audit.check(response,{'f':{}},{'s':{}})['verdict']=='READING_ERROR'
    legacy=dict(verdict='PASS',scientific_approval=False,issues=[])
    assert audit.check(legacy,{}, {})==legacy
    with pytest.raises(ValueError):audit.check(legacy,{}, {},require_current=True)

def test_positive_findings_have_an_explicit_role_but_never_override_errors():
    matched={**issue(),'kind':'MATCH','reason':'候选的比较方向和两端均与原文一致'}
    result=audit.check(answer(matched),{'f':{}},{'s':{}},require_current=True)
    assert result['verdict']=='PASS' and result['issues']==[] and result['confirmed']==[matched]
    mixed=audit.check(answer(matched,issue()),{'f':{}},{'s':{}},require_current=True)
    assert mixed['verdict']=='READING_ERROR' and len(mixed['issues'])==1
    # Previously saved typed issues stay readable, but are not the live wire.
    saved=dict(scientific_approval=False,issues=[issue()])
    assert audit.check(saved,{'f':{}},{'s':{}})['verdict']=='READING_ERROR'
    with pytest.raises(ValueError):audit.check(saved,{'f':{}},{'s':{}},require_current=True)

def test_only_matching_unknown_may_have_no_statement_to_cite():
    fields={'f':dict(state='UNKNOWN',candidate='UNKNOWN')}
    match={**issue(),'kind':'MATCH','source_ids':[]}
    assert audit.check(answer(match),fields,{})['verdict']=='PASS'
    for row,definitions in [(issue(),fields), (match,{'f':dict(state='STATED',candidate='stated value')})]:
        row={**row,'source_ids':[]}
        with pytest.raises(ValueError):audit.check(answer(row),definitions,{})

def test_object_unknown_has_the_same_absence_citation_rule_as_string_unknown():
    claim=dict(state='UNKNOWN',value=None,refs=[])
    field=dict(state='UNKNOWN',candidate=claim,actual_citations=[])
    matched={**issue(),'kind':'MATCH','source_ids':[]}
    assert audit.check(answer(matched),{'f':field},{})['verdict']=='PASS'
    for changed in [dict(claim,value='a real restriction'),dict(claim,refs=['s']),
                    dict(claim,state='MISSING'),dict(claim,reason='undecided')]:
        with pytest.raises(ValueError):audit.check(answer(matched),{'f':dict(field,candidate=changed)},{})
    with pytest.raises(ValueError):audit.check(answer(matched),{'f':dict(field,actual_citations=['s'])},{})
    with pytest.raises(ValueError):audit.check(answer({**matched,'kind':'READING_ERROR'}),{'f':field},{})


def test_no_second_operand_is_citation_optional_only_for_single_level():
    field=dict(state='NOT_APPLICABLE',candidate='NOT_APPLICABLE',actual_citations=[],single_level_target=True)
    matched={**issue(),'kind':'MATCH','source_ids':[]}
    assert audit.check(answer(matched),{'f':field},{})['verdict']=='PASS'
    for changed in [dict(field,single_level_target=False),dict(field,candidate='UNKNOWN'),
                    dict(field,actual_citations=['s']),dict(field,state='MISSING')]:
        with pytest.raises(ValueError):audit.check(answer(matched),{'f':changed},{})
    with pytest.raises(ValueError):audit.check(answer({**matched,'kind':'READING_ERROR'}),{'f':field},{})


@pytest.mark.parametrize('kind',('FIXED_POLICY_VALUE','STOCHASTIC_POLICY_VALUE',
    'NETWORK_DESIGN_STANDARDIZED_ARM_MEAN','INTERVENTIONAL_DISTRIBUTION','DIRECT_EFFECT'))
def test_query_contract_single_level_annotation(kind):
    from types import SimpleNamespace
    base='queries.q1.'
    fields={base+'kind':dict(candidate=kind),
        base+'semantics.second_arrangement':dict(state='NOT_APPLICABLE',candidate='NOT_APPLICABLE',actual_citations=[])}
    run=SimpleNamespace(review_kind='query',review_sheets={'query':dict(fields=fields,source_catalog={})},
        review_templates={'query':dict(decisions={p:'PENDING' for p in fields})},submission=None,entry=None)
    request,actual,sources=audit.request(run)
    key='query:'+base+'semantics.second_arrangement'
    matched=dict(kind='MATCH',field=key,reason='原文只问一个水平，没有第二端。',question=None,source_ids=[])
    response=answer(matched);schema=json.loads(request['user_prompt'])['output_schema']
    if kind=='DIRECT_EFFECT':
        with pytest.raises(ValueError):audit.check(response,actual,sources)
        with pytest.raises(jsonschema.ValidationError):jsonschema.validate(response,schema)
    else:
        assert audit.check(response,actual,sources)['verdict']=='PASS'
        jsonschema.validate(response,schema)


def test_typed_unknown_science_is_not_an_asserted_scope_or_adoption():
    candidate=dict(value=None,source_ids=[],covered_nodes=[],scope='UNKNOWN')
    field=dict(candidate=candidate,citation_groups={'source_ids':[]})
    matched={**issue(),'kind':'MATCH','source_ids':[]}
    assert audit.check(answer(matched),{'f':field},{})['verdict']=='PASS'
    for change in (dict(value=True),dict(value=False),dict(covered_nodes=['甲']),
                   dict(scope='ALL_BINARY_ASSIGNMENTS'),dict(source_ids=['s'])):
        with pytest.raises(ValueError):
            audit.check(answer(matched),{'f':dict(field,candidate={**candidate,**change})},{})
    with pytest.raises(ValueError):
        audit.check(answer({**matched,'kind':'READING_ERROR'}),{'f':field},{})

def test_query_worksheet_does_not_overwrite_current_skill_semantics(tmp_path,monkeypatch):
    from cfm_id_llm import target_first_skill as skill
    engine,run,_=automatic_fixture(tmp_path,monkeypatch)
    assert run.intake.a0_response_contract==skill.CONTRACT
    sheet=run.review_sheets['query']
    for name in ('neighbor_exposure','conditioning_context','aggregation'):
        definition=sheet['fields']['queries.q1.semantics.'+name]['definition']
        assert definition['meaning']==skill.REVIEW_RULES[name].meaning
        assert definition['excludes']==skill.REVIEW_RULES[name].excludes


def test_assignment_auditor_receives_the_complete_reader_enum(tmp_path,monkeypatch):
    from cfm_id_llm.schemas import AssignmentFamily
    engine,run,_=automatic_fixture(tmp_path,monkeypatch);before=deepcopy(run.intake)
    _,fields,_=audit.request(run)
    field=fields['query:common.assignment_family']
    assert field['allowed_values']==[item.value for item in AssignmentFamily]
    assert 'STRATIFIED_FIXED_QUOTAS' in field['allowed_values']
    assert run.intake==before and not run.reviews and run.result is None

def test_published_schema_and_checker_agree_on_question_roles(tmp_path,monkeypatch):
    engine,run,_=automatic_fixture(tmp_path,monkeypatch)
    request,fields,sources=audit.request(run);schema=json.loads(request['user_prompt'])['output_schema']
    error={**issue(),'field':next(iter(fields)),'source_ids':[next(iter(sources))]}
    for response in [answer(),answer(error),answer({**error,'kind':'NEEDS_CLARIFICATION','question':'请说明评价范围。'})]:
        jsonschema.validate(response,schema)
        audit.check(response,fields,sources,require_current=True)
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(answer({**error,'question':'错误地向用户提问'}),schema)

def test_source_auditor_receives_same_scientific_meanings_as_reader(tmp_path,monkeypatch):
    from cfm_id_llm.network_statement_reading import SelectedScienceStatements
    engine,run,_=automatic_fixture(tmp_path,monkeypatch)
    engine._review(run,fixture_review(run))
    request,_,_=audit.request(run);body=json.loads(request['user_prompt'])
    definitions=body['field_definitions']['SelectedScienceStatements']
    assert definitions=={k:v.description for k,v in SelectedScienceStatements.model_fields.items()}
    assert '潜在结果' in definitions['assignment_outcome_independence']
    assert '观察结果' in definitions['consistency']
    assert '不能因有定义而推断采用' in body['definition_usage']


def test_source_auditor_uses_active_profile_schema_not_legacy_model(tmp_path,monkeypatch):
    engine,run,_=automatic_fixture(tmp_path,monkeypatch)
    engine._review(run,fixture_review(run));before=deepcopy(run.submission)
    request=run.entry['request'];body,offset=json.JSONDecoder().raw_decode(request['user'].lstrip())
    body['output_schema']['properties']['profile_note']={'type':'null','description':'Active profile definition; not a scientific approval.'}
    request['user']=json.dumps(body)+'\n\nReviewed target context follows.'
    review,_,_=audit.request(run);payload=json.loads(review['user_prompt'])
    assert payload['field_definitions']['root']['profile_note']=='Active profile definition; not a scientific approval.'
    assert run.submission==before and payload['output_schema']['properties']['scientific_approval']=={'const':False}


def test_auditor_resolves_order_relation_and_closure_by_field_role():
    from cfm_id_llm.network_mean_order_reading import NetworkMeanOrderModel
    schema=NetworkMeanOrderModel.model_json_schema();before=deepcopy(schema)
    claim=audit.schema_contract(schema,'/order_reading/claims/0')
    relation=json.dumps(claim['properties']['relation'],ensure_ascii=False)
    assert '不是批准状态' in relation and '尚未决定' in relation
    closure=audit.schema_contract(schema,'/no_additional_constraints_beyond_declared_orders')
    text=json.dumps(closure,ensure_ascii=False)
    assert '已列顺序' in text and 'PROPOSED' not in text
    assert audit.schema_contract(schema,'/not_a_field')['properties']=={}
    assert schema==before  # Definitions provide context, not new evidence or approval.


def test_field_contract_does_not_mix_same_named_values_and_handles_refs():
    schema={'type':'object','properties':{
        'a':{'$ref':'#/$defs/A'},'b':{'anyOf':[{'$ref':'#/$defs/B'},{'type':'null'}]}},
        '$defs':{'A':{'properties':{'value':{'description':'no extra constraints'}}},
                 'B':{'properties':{'value':{'description':'no constraints beyond listed orders'}}}}}
    assert audit.schema_contract(schema,'/a/value')['definitions']==['no extra constraints']
    assert audit.schema_contract(schema,'/b/value')['definitions']==['no constraints beyond listed orders']


def test_fact_schema_retry_keeps_both_answers_and_still_requires_review(tmp_path,monkeypatch):
    engine,run,_=automatic_fixture(tmp_path,monkeypatch)
    engine._review(run,fixture_review(run))
    good=deepcopy(run.submission['candidate']);bad=deepcopy(good)
    bad['assignment']['kind']='NOT_A_DESIGN';requests=[]
    def reply(r,e,stage):
        requests.append(deepcopy(e))
        raw=bad if len(requests)==1 else good
        if stage=='facts_field_patch':
            body=json.loads(e['request']['user'])
            return dict(binding_sha256=body['output_schema']['properties']['binding_sha256']['const'],
                fields={name:deepcopy(raw[name]) for name in body['fields_to_reread']})
        engine.save(r,'facts_candidate',raw)
        return deepcopy(raw)
    monkeypatch.setattr(engine,'call',reply)
    before=deepcopy(run.entry);result=engine._read_facts(run,run.entry)
    assert result==good and run.entry==before and len(requests)==2
    assert run.artifacts['facts_candidate_before_format_retry']==bad
    assert run.artifacts['facts_format_retry_validation']['scientific_approval'] is False
    assert run.automatic_fact_format_repairs==1 and not run.reviews and run.result is None
    assert 'format_feedback' in requests[1]['request']['user']
    monkeypatch.setattr(engine,'call',lambda *a:deepcopy(bad))
    with pytest.raises(ValueError,match='FACT_READING_FORMAT_INVALID_AFTER_RETRY'):
        engine._read_facts(run,run.entry)

def test_balance_axes_get_one_located_retry_without_silent_repair(tmp_path,monkeypatch):
    from cfm_id_llm.network_design_reading import component_diagnostics, ComponentStructureError
    from cfm_id_llm.fact_wire_models import model_for
    from cfm_id_llm.wire_type_diagnostics import diagnose
    engine,run,_=automatic_fixture(tmp_path,monkeypatch)
    engine._review(run,fixture_review(run))
    good=deepcopy(run.submission['candidate']);nodes=good['study']['nodes']
    good['assignment']=dict(kind='RERANDOMIZED_BALANCED',fixed_count=1,probabilities=None,
        unit_weights={n:'1' for n in nodes},balance_covariates={'scale':{n:str(i) for i,n in enumerate(nodes)}},
        balance_tolerance='1',source_ids=good['assignment']['source_ids'])
    bad=deepcopy(good);bad['assignment']['balance_covariates']={n:{'scale':str(i)} for i,n in enumerate(nodes)}
    model=model_for(run.entry)
    assert component_diagnostics(model.model_validate(good))==[]
    rows=diagnose(run.entry,bad)
    assert rows[0]['field_path']=='/assignment/balance_covariates'
    assert rows[0]['error_code']=='BALANCE_COVARIATES_COMPLETE_NODE_SCOPE_REQUIRED'
    unknown=deepcopy(good);unknown['assignment']['balance_covariates']=None
    assert component_diagnostics(model.model_validate(unknown))==[]  # missing stays missing
    before=deepcopy(run.entry);calls=[]
    def reply(r,e,stage):
        calls.append(deepcopy(e));raw=bad if len(calls)==1 else good
        if stage=='facts_field_patch':
            body=json.loads(e['request']['user'])
            return dict(binding_sha256=body['output_schema']['properties']['binding_sha256']['const'],
                fields={name:deepcopy(raw[name]) for name in body['fields_to_reread']})
        engine.save(r,'facts_candidate',raw);return deepcopy(raw)
    monkeypatch.setattr(engine,'call',reply)
    assert engine._read_facts(run,run.entry)==good
    assert len(calls)==2 and run.artifacts['facts_candidate_before_format_retry']==bad
    assert run.artifacts['facts_format_validation']['errors']==rows
    assert run.entry==before and run.result is None and not run.reviews
    assert run.artifacts['facts_format_retry_validation']['scientific_approval'] is False
    # A second invalid answer remains blocked, never transposed by the program.
    run.automatic_fact_format_repairs=0;calls.clear()
    def always_bad(r,e,stage):
        calls.append(e)
        if stage=='facts_field_patch':
            body=json.loads(e['request']['user'])
            return dict(binding_sha256=body['output_schema']['properties']['binding_sha256']['const'],
                fields={name:deepcopy(bad[name]) for name in body['fields_to_reread']})
        engine.save(r,'facts_candidate',bad);return deepcopy(bad)
    monkeypatch.setattr(engine,'call',always_bad)
    with pytest.raises(ComponentStructureError):engine._read_facts(run,run.entry)
    assert len(calls)==2 and run.result is None


def test_unaccepted_coordinate_glossary_is_not_enabled(tmp_path,monkeypatch):
    engine,run,_=automatic_fixture(tmp_path,monkeypatch)
    original=deepcopy(run.intake)
    request,_,_=audit.request(run);body=json.loads(request['user_prompt'])
    assert 'local_effect_coordinate_definition' not in body
    assert run.intake==original  # Review context never rewrites the reading.

def test_one_audit_format_retry_preserves_input_and_is_not_a_semantic_override(tmp_path,monkeypatch):
    # This unit isolates audit decisions; bounded target rereading is checked separately.
    monkeypatch.setattr("demo.backend.engine.Engine._reread_business", lambda *args: False)
    engine,run,_=automatic_fixture(tmp_path,monkeypatch)
    original=deepcopy(run.intake);calls=[]
    def reply(run,request,stage):
        calls.append(stage);body=json.loads(request['user_prompt'])
        if len(calls)==1:return dict(verdict='PASS',scientific_approval=False,issues=[])
        if len(calls)==2:assert body['audit_contract_feedback']['code']=='READING_AUDIT_FORMAT_INVALID'
        if stage=='focused_audit':return focused_answer(next(iter(body['fields'])),next(iter(body['source_catalog'])))
        return answer(dict(kind='READING_ERROR',field=next(iter(body['fields'])),
            reason='读取对明确比较方向的解释与原文相反',question=None,source_ids=[next(iter(body['source_catalog']))]))
    monkeypatch.setattr(engine,'call',reply);engine._continue_automatically(run)
    assert len(calls)==3 and run.automatic_audit_repairs==1
    assert run.intake==original and run.submission is None and run.result is None
    assert run.user_question is None and run.error['code']=='READING_REVIEW_DISAGREEMENT'
    assert run.artifacts['reading_audit_1_validation']['valid'] is False

def test_valid_negative_gets_only_one_focused_check_not_a_loop_until_pass(tmp_path,monkeypatch):
    # This unit isolates audit decisions; bounded target rereading is checked separately.
    monkeypatch.setattr("demo.backend.engine.Engine._reread_business", lambda *args: False)
    engine,run,_=automatic_fixture(tmp_path,monkeypatch);calls=[]
    def reply(run,request,stage):
        calls.append(stage);body=json.loads(request['user_prompt'])
        if stage=='focused_audit':return focused_answer(next(iter(body['fields'])),next(iter(body['source_catalog'])))
        return answer(dict(kind='READING_ERROR',field=next(iter(body['fields'])),
            reason='明确的原文范围没有在当前读取中保留',question=None,source_ids=[next(iter(body['source_catalog']))]))
    monkeypatch.setattr(engine,'call',reply);engine._continue_automatically(run)
    assert len(calls)==2 and run.automatic_audit_repairs==0 and run.result is None
    assert run.error['code']=='READING_REVIEW_DISAGREEMENT'

def test_focused_check_requires_explicit_complete_findings():
    first=audit.check(answer(issue()),{'f':{}},{'s':{}})
    with pytest.raises(ValueError,match='EXACT_COVERAGE'):
        audit.reconcile(first,audit.check(answer(),{},{}),{'f':{}})
    match=audit.check(answer({**issue(),'kind':'MATCH'}),{'f':{}},{'s':{}})
    assert audit.reconcile(first,match,{'f':{}})['verdict']=='PASS'
    assert audit.reconcile(first,first,{'f':{}})['verdict']=='READING_ERROR'
    # A genuine remaining question is not erased by resolution of another field.
    first['issues'].append({**issue('NEEDS_CLARIFICATION','请说明本次评价谁。'),'field':'g'})
    assert audit.reconcile(first,match,{'f':{}})['verdict']=='NEEDS_CLARIFICATION'

def test_one_focused_match_resolves_audit_only_not_science(tmp_path,monkeypatch):
    engine,run,_=automatic_fixture(tmp_path,monkeypatch);original=deepcopy(run.intake)
    prior=engine.call;calls=[]
    def reply(run,request,stage):
        calls.append(stage)
        body=json.loads(request['user_prompt']) if 'user_prompt' in request else None
        if stage=='reading_audit_1':
            return answer(dict(kind='READING_ERROR',field='query:queries.q1.kind',
                reason='待核对比较类型与原文的对应关系',question=None,source_ids=[next(iter(body['source_catalog']))]))
        if stage=='focused_audit':
            assert list(body['fields'])==['query:queries.q1.kind']
            assert body['other_reading_context'] and body['source_catalog']
            return focused_answer('query:queries.q1.kind',next(iter(body['source_catalog'])),matches=True)
        return prior(run,request,stage)
    monkeypatch.setattr(engine,'call',reply);engine._continue_automatically(run)
    assert run.intake==original and calls.count('focused_audit')==1
    assert run.review_kind=='science' and run.result is None
    assert run.artifacts['reading_audit_1_validated']['verdict']=='READING_ERROR'
    assert run.artifacts['reconciled_reading_audit']['verdict']=='PASS'

def test_permission_failure_has_no_automatic_retry(tmp_path,monkeypatch):
    engine,run,_=automatic_fixture(tmp_path,monkeypatch);calls=[]
    def reply(*args):calls.append(1);return dict(scientific_approval=True,findings=[])
    monkeypatch.setattr(engine,'call',reply)
    with pytest.raises(ValueError,match='PERMISSION'):engine._continue_automatically(run)
    assert len(calls)==1 and not run.reviews


@pytest.mark.parametrize('source_matches',[True,False])
def test_query_followup_does_not_consume_distinct_fact_audit_followup(tmp_path,monkeypatch,source_matches):
    engine,run,_=automatic_fixture(tmp_path,monkeypatch)
    prior=engine.call;calls=[];original=deepcopy(run.intake)
    def reply(run,request,stage):
        calls.append(stage)
        body=json.loads(request['user_prompt']) if 'user_prompt' in request else None
        if stage.startswith('reading_audit_'):
            return answer(dict(kind='READING_ERROR',field=next(iter(body['fields'])),
                reason='需对照原文核对本阶段候选',question=None,source_ids=[next(iter(body['source_catalog']))]))
        if stage.startswith('focused_audit'):
            return focused_answer(next(iter(body['fields'])),next(iter(body['source_catalog'])),
                matches=(True if run.review_kind=='query' else source_matches))
        return prior(run,request,stage)
    monkeypatch.setattr(engine,'call',reply);engine._continue_automatically(run)
    assert run.intake==original
    assert [s for s in calls if s.startswith('focused_audit')]==['focused_audit','focused_audit_source']
    assert run.automatic_focused_stages=={'query','source'}
    assert run.result is None
    if source_matches:assert run.review_kind=='science' and run.error is None
    else:assert run.error['code']=='READING_REVIEW_DISAGREEMENT'


def test_undeclared_assignment_enum_does_not_require_invented_citation():
    field=dict(state='ENUM',candidate='UNRESOLVED',actual_citations=[],
        definition=dict(name='assignment_family'))
    finding=dict(kind='MATCH',field='f',reason='原文未声明历史分配规则，保持未确定。',question=None,source_ids=[])
    assert audit.check(answer(finding),{'f':field},{})['verdict']=='PASS'
    for changed in ({'candidate':'INDEPENDENT_BERNOULLI'},
                    {'actual_citations':[{'source_id':'s'}]},
                    {'definition':{'name':'some_other_field'}}):
        with pytest.raises(ValueError):audit.check(answer(finding),{'f':dict(field,**changed)},{})
    with pytest.raises(ValueError):audit.check(answer(dict(finding,kind='READING_ERROR')),{'f':field},{})


def test_focused_boolean_contract_preserves_negative_and_requires_every_field(tmp_path,monkeypatch):
    engine,run,_=automatic_fixture(tmp_path,monkeypatch)
    req,fields,sources=audit.request(run);path=next(iter(fields));source=next(iter(sources))
    first=audit.check(answer({**issue(),'field':path,'source_ids':[source]}),fields,sources)
    focused,disputed=audit.focused_request(req,fields,first)
    schema=json.loads(focused['user_prompt'])['output_schema']
    assert 'findings' not in schema['properties']
    for same,expected in [(True,'PASS'),(False,'READING_ERROR'),(None,'NEEDS_CLARIFICATION')]:
        wire=focused_answer(path,source,matches=same)
        if same is None:wire['assessments'][0]['question']='请说明本次评价哪些对象。'
        jsonschema.validate(wire,schema)
        assert audit.check_focused(wire,disputed,sources)['verdict']==expected
    # Positive prose cannot override an explicit false, and Python 1 is not True on wire.
    wire=focused_answer(path,source);wire['assessments'][0]['comparison']='候选正确但是模型仍然错误地否定'
    assert audit.check_focused(wire,disputed,sources)['verdict']=='READING_ERROR'
    for bad in [1,'true','MATCH']:
        wire['assessments'][0]['matches_source']=bad
        with pytest.raises(ValueError):audit.check_focused(wire,disputed,sources)
    for records in [[],[focused_answer(path,source)['assessments'][0]]*2]:
        with pytest.raises(ValueError):audit.check_focused(dict(scientific_approval=False,assessments=records),disputed,sources)
    with pytest.raises(ValueError):audit.check_focused(answer(),disputed,sources)
