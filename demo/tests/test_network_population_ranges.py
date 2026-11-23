import pytest
from cfm_id.direct_verification import verify
from cfm_id.network_source_alignment import population_matches
from cfm_id.network_material_questions import explicit_assignment_question


@pytest.mark.parametrize('claim, members, matches', [
    (['每家店（i=4..6）'], ['6','4','5'], True),
    (['j=9至10'], ['9','10'], True),
    (['i=1..3'], ['1','2','4'], False),
    (['i=1..2'], ['1','2','3'], False),
    (['i=1..2'], ['01','02'], False),
    (['i=1..2'], ['甲','乙'], False),
    (['i=1..2','1'], ['1','2'], False),
    (['已回访的门店（i=1..2）'], ['1','2'], False),
    (['i=1..2)'], ['1','2'], False),
])
def test_index_ranges_are_exact_unit_ids(claim,members,matches):
    assert population_matches(claim,members,allow_index_ranges=True) is matches
    assert not population_matches(claim,members)


def test_explicit_assignment_gap_respects_other_materials_and_replies():
    case=dict(business_question='推广名单是怎么选出的，我不清楚。',sources=[])
    def check(sources):
        report=dict(decision='WITHHELD',checks=[],clarification_questions=[],estimation_handoff_allowed=False)
        explicit_assignment_question(dict(case,sources=sources),report)
        return report['clarification_questions']
    assert len(check([]))==1
    assert not check([dict(source_id='protocol',text='每组等概率抽签。')])
    assert not check([dict(source_id='user_reply_1',text='已上传实际执行办法。')])


@pytest.mark.parametrize('as_list',[False,True])
def test_range_must_match_roster_in_either_draft_field(tmp_path,as_list):
    from demo.backend.engine import Engine, Run
    engine=Engine(tmp_path/'runs')
    example=next(row for row in engine.examples if row['id']=='n100')
    run=Run(owner='test',synthetic=True)
    engine._start(run,dict(question=example['case']['business_question'],example_id='n100',
                           use_example_network=True),preview_only=True)
    for end,match in ((99,True),(98,False)):
        value=f'每个对象（j=0..{end}）'
        claim=[value] if as_list else value
        for draft in (dict(network_facts=dict(contrast=dict(value=dict(population=claim)))),
                      dict(answers=[dict(target=dict(population=claim))])):
            result=verify(run.case,draft,network=run.network)
            assert result['network_alignment']['matched'] is match
            assert bool(result.get('condition_review')) is match
            assert not result['estimation_handoff_allowed']
