from copy import deepcopy
import json
import pytest
from cfm_id_llm import design_scope_audit as scope, local_bundle_reading as reader
from demo.tests.test_local_bundle_entry import fixture


def audit_fields(reading):
    """Explicit fixture declarations only; never used by production code."""
    if not isinstance(reading.get('design'),dict):return {}
    d=reading['design']; value=d.get('value')
    return dict(design_scope_version=scope.VERSION,design_scope=dict(
        basis='EXPLICIT_JOINT_RULE' if value else 'NOT_STATED',
        rule=scope.KINDS[value['kind']] if value else 'UNKNOWN',evidence=d['evidence']))


@pytest.mark.parametrize('text',[
    '每家有一半机会使用，每家分别抽签。',
    '这次四家恰好选中两家。',
    '完整分配与各家的潜在结果独立。',
    '各站不是独立抽签，先选一个总名额。',
    '尚未确定各站是否独立抽签。',
    'Assignments are not independent.',
    '不假设各家独立抽签。',
    '没有说明各站独立分配。',
    'We do not know whether stores are assigned independently.',
])
def test_marginal_realization_and_randomization_do_not_declare_independence(text):
    assert not scope.explicit_independence([dict(quote=text)])


@pytest.mark.parametrize('text',[
    '每个网点在6月前独立抽签，各有1/2概率。',
    '各店的抽签相互独立，概率不一定相同。',
    '独立伯努利分配。',
    'Each store is assigned independently.',
    '各家独立掷公平硬币决定是否启用，四家的硬币相互独立。',
    '还没确定是否明天开通，各站的抽签相互独立。',
])
def test_explicit_joint_rule_anchor(text):
    assert scope.explicit_independence([dict(quote=text)])


def test_false_match_with_marginal_only_quote_cannot_approve_design(tmp_path):
    from demo.tests.test_information_scope_audit import source_audit
    case,d,t,s=fixture(tmp_path)
    law=next(x for x in case['sources'] if x['source_id']=='law')
    law['text']='每家分别抽签，各有1/3机会。完整安排独立于潜在结果。'
    s['design']['evidence']=[dict(source_id='law',quote=law['text'])]
    s=reader.inspect(case,s); a=source_audit(case,s)
    checked=reader.check_audit_current(case,s,a)
    finding=next(f for f in checked['findings'] if f['field']=='design')
    assert finding['verdict']=='READING_ERROR' and finding['question'] is None
    # A source auditor that acknowledges the missing joint rule asks one concrete question.
    a['design_scope'].update(basis='MARGINAL_CHANCES_ONLY',rule='UNKNOWN')
    checked=reader.check_audit_current(case,s,a)
    finding=next(f for f in checked['findings'] if f['field']=='design')
    assert finding['verdict']=='NEEDS_CLARIFICATION' and finding['question']==scope.QUESTION
    assert s['design']['value']['kind']=='heterogeneous_bernoulli_binary_v1'  # Never edit model facts to pass.


def test_design_contract_current_required_historical_preserved_and_shared(tmp_path):
    from demo.tests.test_information_scope_audit import source_audit
    from cfm_id_llm import joint_reading,network_existing_reading
    c,d,t,s=fixture(tmp_path);s=reader.inspect(c,s);a=source_audit(c,s)
    a.pop('design_scope');a.pop('design_scope_version')
    assert reader.check_audit(c,s,a)
    with pytest.raises(ValueError,match='DESIGN_SCOPE_AUDIT_REQUIRED'):reader.check_audit_current(c,s,a)
    for module in (reader,joint_reading):
        request=joint_reading.audit_request(c,s,field_catalog=reader.fields(s)) if module is joint_reading else module.audit_request(c,s)
        assert 'design_scope' in json.loads(request['user_prompt'])['output_schema']['required']
    from demo.tests.test_network_existing_entry import fixture as policy_fixture
    c,s=policy_fixture()
    request=network_existing_reading.audit_request(c,s)
    assert 'design_scope' in json.loads(request['user_prompt'])['output_schema']['required']


def test_explicit_source_rule_different_from_candidate_and_prior_error_preserved(tmp_path):
    from demo.tests.test_information_scope_audit import source_audit
    c,d,t,s=fixture(tmp_path);s=reader.inspect(c,s);a=source_audit(c,s)
    a['design_scope']['rule']='FIXED_TOTAL'
    assert next(x for x in reader.check_audit_current(c,s,a)['findings'] if x['field']=='design')['verdict']=='READING_ERROR'
    f=next(x for x in a['findings'] if x['field']=='design');f.update(verdict='READING_ERROR',reason='Another source mismatch')
    assert next(x for x in reader.check_audit_current(c,s,a)['findings'] if x['field']=='design')['reason']=='Another source mismatch'


def test_fixed_quota_does_not_require_or_infer_independence(tmp_path):
    from demo.tests.test_information_scope_audit import source_audit
    c,d,t,s=fixture(tmp_path)
    law=next(x for x in c['sources'] if x['source_id']=='law')
    law['text']='四站每次等概率抽取恰好两站，不是各站独立抽签。'
    s['design']=dict(value=dict(kind='complete_randomization_binary_v1',m=2),
        evidence=[dict(source_id='law',quote=law['text'])])
    s=reader.inspect(c,s);a=source_audit(c,s)
    assert next(x for x in reader.check_audit_current(c,s,a)['findings'] if x['field']=='design')['verdict']=='MATCH'
    assert a['design_scope']['rule']=='FIXED_TOTAL'
