"""Default entry preserves evidence while taking the existing reviewed route."""
import base64
from copy import deepcopy
import json
import pytest
from demo.backend.engine import Engine, Run


def report(**changes):
    return dict(dict(decision='RETAINED',proof=None,checks=[],draft={'status':'POINT'},
        scientific_approval=False,estimation_handoff_allowed=False,clarification_questions=[],
        input_sha256='input',draft_sha256='draft'),**changes)


def test_uncertified_answer_continues_with_unchanged_sources_not_draft(tmp_path,monkeypatch):
    e=Engine(tmp_path);r=Run(owner='user',reading_mode='direct_verify',automatic_review=True,
        case={'business_question':'仅求公式','sources':[{'source_id':'csv','text':'x,y\n甲,1/4'}]})
    source=deepcopy(r.case);draft=report();seen=[]
    monkeypatch.setattr(e,'_read_case',lambda run:seen.append(deepcopy(run.case)))
    e._finish_direct_verification(r,draft)
    assert seen==[source] and r.case==source
    assert r.reading_mode=='classic' and r.result is None and not r.reviews
    assert r.artifacts['direct_verification']==draft
    assert r.artifacts['reading_continuation']['scientific_approval'] is False
    # Re-entering the finishing callback cannot create an automatic loop.
    e._finish_direct_verification(r,draft)
    assert len(seen)==1


@pytest.mark.parametrize('changes',[
    {'decision':'WITHHELD'}, {'proof':{'method':'UNSUPPORTED_TEST_PROOF'}},
    {'checks':[{'state':'CONFLICT'}]}, {'clarification_questions':['请说明抽签规则。']},
    {'review_record':{'pending':True}},
])
def test_conflict_proof_or_question_does_not_take_unreviewed_shortcut(tmp_path,monkeypatch,changes):
    e=Engine(tmp_path);r=Run(owner='user',reading_mode='direct_verify',automatic_review=True)
    monkeypatch.setattr(e,'_read_case',lambda _:pytest.fail('Unexpected continuation'))
    e._finish_direct_verification(r,report(**changes))
    assert r.reading_mode=='direct_verify' and not r.reviews


@pytest.mark.parametrize('mode,automatic',[('direct_verify',False),('network_local_review',True),('network_direct_verify',True)])
def test_explicit_mode_and_automation_choice_are_respected(tmp_path,monkeypatch,mode,automatic):
    e=Engine(tmp_path);r=Run(owner='user',reading_mode=mode,automatic_review=automatic)
    monkeypatch.setattr(e,'_read_case',lambda _:pytest.fail('Unexpected continuation'))
    e._finish_direct_verification(r,report())
    assert r.reading_mode==mode


@pytest.mark.parametrize('mode',['classic','direct_verify'])
@pytest.mark.parametrize('share',[True,False])
def test_table_sharing_is_explicit_and_independent_of_reading_route(tmp_path,mode,share):
    e=Engine(tmp_path);r=Run(owner='user')
    data='site,mean\n甲,0.1234567\n乙,0.7654321\n'
    e._start(r,dict(question='求全推广平均结果',reading_mode=mode,share_table_rows=share,
        files=[dict(name='means.csv',content=base64.b64encode(data.encode()).decode())]),preview_only=True)
    sent=json.dumps(r.case,ensure_ascii=False)
    assert ('0.1234567' in sent)==share and ('0.7654321' in sent)==share
    assert r.attachment_report['attachments'][0]['mode']==('FULL_TABLE' if share else 'SCHEMA_ONLY')


def test_output_preference_ownership_survives_focused_review(tmp_path,monkeypatch):
    from test_user_workflow import automatic_fixture
    from test_live_demo import fixture_review
    from demo.backend import automatic_review as audit
    e,r,_=automatic_fixture(tmp_path,monkeypatch)
    e._review(r,fixture_review(r));before=deepcopy(r.submission)
    request,fields,sources=audit.request(r);body=json.loads(request['user_prompt'])
    owner=body['output_request_ownership']
    assert owner['business_question']==r.case['business_question']
    assert '未知算子不得' in owner['boundary']
    focused,_=audit.focused_request(request,fields,{'issues':[{'field':'source:','kind':'READING_ERROR'}]})
    assert json.loads(focused['user_prompt'])['output_request_ownership']==owner
    assert r.submission==before and not r.result
