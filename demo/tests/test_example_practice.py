from demo.backend.engine import Engine, Run


def test_example_practice_reply_enters_case_only_after_user_clarifies(tmp_path, monkeypatch):
    engine = Engine(tmp_path/'runs')
    calls = []
    monkeypatch.setattr(engine, '_read_case', lambda run: calls.append(run.id))
    example = next(x for x in engine.examples if x.get('clarification_practice'))
    reply = example['clarification_practice']['answer']
    run = Run(owner='test')
    engine._start(run, dict(example_id=example['id'], reading_mode='classic',
        question=example['case']['business_question'],
        source_edits=[dict(source_id=s['source_id'], text=s['text'])
                      for s in example['case']['sources']]))
    assert run.case['sources'] == example['case']['sources']
    assert reply not in str(run.case)
    assert 'clarification_practice' not in run.case
    engine._clarify(run, reply)
    assert run.case['sources'][:-1] == example['case']['sources']
    assert run.case['sources'][-1]['text'] == reply
    assert len(calls) == 2 and engine.calls == 0
