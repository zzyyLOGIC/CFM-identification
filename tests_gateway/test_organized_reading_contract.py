"""New instructions, identical fields, evidence obligations and native results."""
from copy import deepcopy
import pytest
from cfm_id import business_intake as intake,business_dispatch as dispatch
from cfm_id_llm import organized_reading_contract as c,query_conditioning_contract as previous
from cfm_id_llm.compact_formulator import make_compact_request,CompactClaim
from cfm_id_llm.compact_inline_evidence_contract import MissingClaim
from cfm_id_llm.compact_reference_contract import split_user
from tests_gateway.test_query_conditioning_contract import draft
from tests_gateway.test_inline_evidence_slots import receive
from tests_gateway.test_business_field_review import sheet,record,submit
from examples.network_observational_policy_reference import fact_reference,approval_records


@pytest.mark.parametrize('refs',[None,'compact-source-selectors-1','compact-source-paragraphs-1'])
def test_only_instructions_and_request_binding_change(refs):
    case,_,_=draft()
    a=make_compact_request(case,a0_reference_contract=refs,a0_response_contract=previous.CONTRACT)
    b=make_compact_request(case,a0_reference_contract=refs,a0_response_contract=c.CONTRACT)
    pa,sa=split_user(a[1])[1:3];pb,sb=split_user(b[1])[1:3]
    if refs:
        assert pa.pop('reference_context')!=pb.pop('reference_context')
        sa['properties'].pop('reference_context');sb['properties'].pop('reference_context')
    assert pa==pb and sa==sb and a[2]==b[2]
    assert len(b[0])<len(a[0]) and b[0]!=a[0]


@pytest.mark.parametrize('example',c.EXAMPLES)
def test_demonstrated_claims_use_existing_types(example):
    cls=MissingClaim if example['output']['state']=='MISSING' else CompactClaim
    assert cls.model_validate(example['output']).model_dump(mode='json')==example['output']


def setup(**kw):
    case,data,raw=draft(**kw);s=receive(case,raw,profile=c.CONTRACT)
    query=submit(s,record(sheet(s)))['query_review']
    e=dispatch.prepare_reader(s,'q1',query_review=query)
    return s,e,dict(query_review=query,candidate=fact_reference(e,data),request_sha256=e['request_sha256'])


@pytest.mark.parametrize('case_kw,expected',[({},'POINT'),({'sample_only':True},'NEEDS_INPUT'),({'exchangeability':None},'NEEDS_INPUT'),({'exchangeability':False},'ADAPTER_NOT_CONNECTED'),({'zero_support':True},'UNSUPPORTED')])
def test_existing_r3_positive_and_negative_results(case_kw,expected):
    s,e,o=setup(**case_kw);before=deepcopy(o['candidate']);p=dispatch.inspect_methods(s,'q1',**o)
    a=approval_records(p) if p.get('methods') else dict(research_protocol_selected=True)
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']==expected and r['independent_replay']==(expected=='POINT')
    assert o['candidate']==before


@pytest.mark.parametrize('axis',['field_role','value_state','source_coverage'])
@pytest.mark.parametrize('decision',['REJECTED','PENDING'])
def test_same_independent_field_review_still_blocks(axis,decision):
    case,_,raw=draft();s=receive(case,raw,profile=c.CONTRACT);w=sheet(s);r=record(w)
    r['decisions']['queries.q1.semantics.conditioning_context'][axis]=decision
    reviewed=submit(s,r);e=dispatch.prepare_reader(s,'q1',query_review=reviewed['query_review'])
    assert e['request'] is None and not e['backend_called']


def test_changing_instructions_invalidates_checkpoint():
    case,_,raw=draft();s=receive(case,raw,profile=previous.CONTRACT)
    with pytest.raises(intake.IntakeError):intake.prepare_request(s.model_copy(update={'a0_response_contract':c.CONTRACT}))


def test_recheck_uses_same_fields_and_requires_new_reviews():
    from cfm_id.intake_reading_revision import prepare_recheck
    from tests_gateway.test_reading_review_guards import feedback
    case,_,raw=draft();s=receive(case,raw,profile=c.CONTRACT)
    w=prepare_recheck(s,authority='SYNTHETIC_TEST')['feedback_worksheet'];f=feedback(w)
    path='/queries/0/semantics/conditioning_context/value';f['issues'][0]['field_path']=path
    new=prepare_recheck(s,feedback=f,authority='SYNTHETIC_TEST')
    assert previous.DESCRIPTION in intake.prepare_request(new)['user_prompt']
    assert new.request_sha256!=s.request_sha256 and new.candidate is None


def test_example_source_cannot_be_borrowed_into_actual_answer():
    case,_,raw=draft();s=receive(case,raw,profile=c.CONTRACT)
    bad=deepcopy(s.candidate);bad['queries'][0]['semantics']['conditioning_context']['refs']=['example_2']
    s=intake.receive_candidate(s,bad,request_sha256=s.request_sha256)
    assert 'report' not in intake.inspect(s) and dispatch.prepare_reader(s,'q1')['request'] is None


def test_instruction_profile_retains_reviewed_condition_and_fact_instructions():
    s,e,o=setup()
    context=e['reviewed_target_context']
    assert context==previous.target_context(s.candidate['queries'][0],query_id='q1')
    assert previous.FACT_DESCRIPTION in e['request']['user']
    p=dispatch.inspect_methods(s,'q1',**o)
    assert p['target_conditioning_review']['reviewed_query']==context
    assert previous.MATCH_DECISION in p['methods'][0]['reading_worksheet']['decisions']


@pytest.mark.parametrize('decision,expected',[('PENDING','REVIEW_REQUIRED'),('REJECTED','CHECK_BLOCKED'),('MISSING','CHECK_BLOCKED')])
def test_native_condition_review_is_required_for_instruction_profile(decision,expected):
    s,e,o=setup();p=dispatch.inspect_methods(s,'q1',**o);a=approval_records(p)
    decisions=a['native_reviews']['network.observational.full_policy_mean']['reading_review'].decisions
    assert previous.MATCH_DECISION in decisions
    if decision=='MISSING':decisions.pop(previous.MATCH_DECISION)
    else:decisions[previous.MATCH_DECISION]=decision
    r=dispatch.execute(s,'q1',**o,**a)
    assert r['state']==expected and not r['backend_called'] and r['mathematical_claim'] is None


@pytest.mark.parametrize('condition,standardization,expected',[
    ('UNKNOWN','UNKNOWN','NEEDS_INPUT'),
    ('MISSING','UNKNOWN','NEEDS_INPUT'),
    ('STATED','STATED','ADAPTER_NOT_CONNECTED'),
    ('STATED','MISSING','NEEDS_INPUT'),
])
def test_instruction_profile_cannot_drop_condition_scope_admission(condition,standardization,expected):
    case,_,raw=draft()
    semantics=raw['queries'][0]['semantics']
    origin=deepcopy(semantics['conditioning_context'])
    for field,state in [('conditioning_context',condition),('standardization_distribution',standardization)]:
        semantics[field]=('UNKNOWN' if state=='UNKNOWN' else
            dict(state='MISSING',reason='The target context is explicitly undecided.',refs=origin['refs']) if state=='MISSING' else deepcopy(origin))
    s=receive(case,raw,profile=c.CONTRACT);q=submit(s,record(sheet(s)))['query_review']
    e=dispatch.prepare_reader(s,'q1',query_review=q)
    assert e['state']==expected and e['request'] is None and not e['backend_called']
