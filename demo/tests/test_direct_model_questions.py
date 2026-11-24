from copy import deepcopy
import pytest
from demo.backend.direct_questions import explicit_questions
from demo.backend.engine import Engine,Run


def report():
    return dict(decision='RETAINED',proof=None,clarification_questions=[],scientific_approval=False,
        estimation_handoff_allowed=False,effective_answer=dict(answers=[dict(status='NOT_POINT',
        estimate_handoff={'mode':'STOP'},reason='各完整安排的概率未知。请提供三个点抽签安排的联合概率。')]))


def test_question_surfaces_without_changing_result_or_granting_review(tmp_path):
    r=report();before=deepcopy(r);engine=Engine(tmp_path);run=Run(owner='test')
    engine._finish_direct_verification(run,r)
    assert r==before and run.result==before
    assert run.stage=='REVIEW_REQUIRED'
    assert run.user_question['items']==['请提供三个点抽签安排的联合概率。']
    assert run.artifacts['direct_model_questions']['scientific_approval'] is False
    assert not run.result['estimation_handoff_allowed']


@pytest.mark.parametrize('change',[
    lambda r:r.update(decision='WITHHELD'),
    lambda r:r.update(proof={'method':'existing-proof'}),
    lambda r:r.update(estimation_handoff_allowed=True),
    lambda r:r.update(clarification_questions=['已有绑定追问']),
    lambda r:r['effective_answer']['answers'][0].update(status='POINT'),
    lambda r:r['effective_answer']['answers'][0]['estimate_handoff'].update(mode='ESTIMATE_BOUNDS'),
    lambda r:r['effective_answer']['answers'][0].update(reason='若需要更窄界限，可以考虑增加条件。'),
])
def test_no_question_inferred_from_formula_or_completed_answer(change):
    r=report();change(r);assert explicit_questions(r)==[]


def test_scientific_question_remains_a_question():
    r=report();r['effective_answer']['answers'][0]['reason']='一致性尚未决定。请问是否采用“实际记录的结果就是实际完整安排下的结果”？'
    before=deepcopy(r)
    assert explicit_questions(r)==['请问是否采用“实际记录的结果就是实际完整安排下的结果”？']
    assert r==before
