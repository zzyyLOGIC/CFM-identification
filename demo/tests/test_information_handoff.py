"""Source-role clarification must be reachable from the ordinary web plan."""
from copy import deepcopy
import pytest
from demo.backend.engine import Engine, Run
from tests_gateway.test_network_information_evidence import fixture
from tests_gateway.test_network_bounded_dispatch import partition_table


def test_web_asks_source_roles_before_science_for_partitioned_table(tmp_path):
    session,entry,options,record=fixture()
    partition_table(options['candidate'])
    before=deepcopy(options['candidate'])
    run=Run(owner='test',synthetic=True,intake=session,query_id='q1',entry=entry,
        query_review=options['query_review'],submission=options)
    engine=Engine(tmp_path)
    engine._plan(run)
    assert run.review_kind=='information' and run.result is None
    sheet=run.review_sheets['information']
    assert len(sheet['entry_source_ids'])==7
    assert run.review_templates['information']['disposition']=='PENDING'
    assert run.submission['candidate']==before
    assert not run.plan['backend_called']
    record['binding_sha256']=sheet['binding_sha256']
    engine._review(run,dict(kind='information',records={'information':record}))
    assert run.review_kind=='science' and run.result is None
    assert run.submission['candidate']==before


def automatic_run(tmp_path):
    session,entry,options,_=fixture()
    run=Run(owner='test',synthetic=True,intake=session,query_id='q1',entry=entry,
        query_review=options['query_review'],submission=options,case=session.case.model_dump(mode='json'),automatic_review=True)
    engine=Engine(tmp_path);engine._plan(run)
    docs={s['doc_id'] for s in run.review_sheets['information']['source_catalog'].values()}
    answer=dict(scientific_approval=False,matches_source=True,table_document='information',
        supporting_documents=sorted(docs-{'information'}),comparison='表中格子逐项一致，配套文件仅说明对象及同伴分组，没有另一份总体信息。',question=None)
    return engine,run,answer


def test_background_source_roles_stop_at_science_without_changing_candidate(tmp_path,monkeypatch):
    engine,run,answer=automatic_run(tmp_path);before=deepcopy(run.submission['candidate']);calls=[]
    def call(r,request,stage):
        assert 'JSON' in request['system_prompt']  # Provider JSON-object mode requires this instruction.
        calls.append(stage);return answer
    monkeypatch.setattr(engine,'_call_audit',call)
    engine._continue_automatically(run)
    assert calls==['information_audit_1']
    assert run.review_kind=='science' and run.result is None and not run.reviews
    assert run.submission['candidate']==before
    assert run.submission['information_evidence_review']['disposition']=='ACCEPTED'


@pytest.mark.parametrize('same',[False,None])
def test_background_role_error_and_missing_input_are_distinct(tmp_path,monkeypatch,same):
    engine,run,answer=automatic_run(tmp_path)
    answer.update(matches_source=same,question='请说明这两份表是否来自同一次研究？' if same is None else None)
    monkeypatch.setattr(engine,'_call_audit',lambda *a:answer)
    engine._continue_automatically(run)
    assert 'information_evidence_review' not in run.submission
    assert run.result is None and not run.reviews
    assert bool(run.error)==(same is False)
    assert bool(run.user_question)==(same is None)


@pytest.mark.parametrize('change',[
    {'supporting_documents':[]},{'table_document':'foreign'},
    {'scientific_approval':True},{'question':'请批准科学条件'},
])
def test_role_review_rejects_missing_foreign_sources_or_scientific_approval(tmp_path,change):
    from demo.backend import information_review
    engine,run,answer=automatic_run(tmp_path)
    answer.update(change)
    with pytest.raises(Exception):information_review.check(run,answer)
