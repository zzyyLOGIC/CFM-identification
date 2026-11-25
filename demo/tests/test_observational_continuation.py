from copy import deepcopy
import pytest
from cfm_id_llm import network_source_route as route,observational_effect_source as reader
from test_observational_effect_entry import fixture,prepared
from test_observational_reader_selection import source_scope


def context():
    old,wire=fixture('nodewise')
    wire['assumptions']['potential_outcome_exposure_sufficiency']['value']=None
    report=prepared(old,wire)
    report['reader_selection']={'reader':reader.FAMILY,'source_scope':source_scope(old)}
    case=deepcopy(old);case['sources'].append(dict(source_id='reply',kind='OTHER',text='本次采用。'))
    return old,case,report,route.continuation(case,old,report)


def test_audited_intent_is_carried_but_not_scientific_permission():
    old,case,report,h=context()
    assert h and h['target']==report['joint_entry']['reading']['facts']['target']
    assert not h['scientific_approval']
    raw=source_scope(case)
    raw['target_changed_by_reply']=dict(value=False,evidence=[dict(source_id='reply',quote='本次采用。')])
    assert route.select(route.check(case,raw,h))==reader.FAMILY
    raw['target']['value']='FIXED_POLICY_CONTRAST'
    with pytest.raises(ValueError,match='UNCHANGED_QUESTION_TARGET_DRIFT'):route.check(case,raw,h)


def test_real_target_changes_are_not_overridden():
    old,case,report,h=context()
    case['sources'][-1]['text']='改问全体使用减全体不使用。'
    h=route.continuation(case,old,report)
    raw=source_scope(case,'FIXED_POLICY_CONTRAST')
    raw['target_changed_by_reply']=dict(value=True,evidence=[dict(source_id='reply',quote=case['sources'][-1]['text'])])
    assert route.check(case,raw,h)['target']['value']=='FIXED_POLICY_CONTRAST'
    changed=deepcopy(case);changed['business_question']+=' changed'
    assert route.continuation(changed,old,report) is None


def test_optional_scope_and_row_sources_remain_audited():
    case,wire=fixture('nodewise')
    source=wire['information'][0]['source_ids']
    for cell in wire['information'][0]['covered_cells']:cell['source_ids']=source
    d=wire['assumptions']['consistency'];d.update(covered_nodes=wire['target']['population'],scope='ALL_BINARY_ASSIGNMENTS')
    s=reader.inspect(case,wire)
    assert s['facts']['assumptions']['consistency']['covered_nodes']==wire['target']['population']
    assert any(k.startswith('facts.information.0.covered_cells.') for k in reader.fields(case,s))
    d['covered_nodes']=[]
    with pytest.raises(ValueError,match='DECLARATION_DOES_NOT_COVER_TARGET'):reader.inspect(case,wire)
    d['covered_nodes']=wire['target']['population']
    wire['information'][0]['covered_cells'][0]['source_ids']=['nonexistent']
    with pytest.raises(ValueError):reader.inspect(case,wire)
