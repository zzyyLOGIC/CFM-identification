"""Source/result consistency, separate from model-reading accuracy or math tests."""
from copy import deepcopy
from functools import lru_cache
import json

import pytest
from cfm_id import joint_natural_entry as workflow, joint_query_exchange as exchange
from test_joint_natural_entry import fixture as joint_fixture, finish as finish_joint
from test_network_existing_entry import fixture as policy_fixture, finish as finish_policy
from test_iv_natural_entry import fixture as iv_fixture, finish as finish_iv
from test_dag_single_source_entry import fixture as single_fixture
from test_joint_query_handoff import reviewed_effect


ROUTES=('joint_means','joint_dag','single_dag','nonid','policy','observational_policy',
        'observed','stratum','nodewise','iv_late','iv_ate')


@lru_cache(None)
def report_for(route):
    if route in ('observed','stratum','nodewise'):
        return reviewed_effect(route)
    if route.startswith('iv_'):
        case,s=iv_fixture('LATE' if route=='iv_late' else 'ATE')
        return case,finish_iv(case,s)
    if route in ('policy','observational_policy'):
        case,s=policy_fixture(route=='observational_policy')
        return case,finish_policy(case,s)
    if route in ('single_dag','nonid'):
        case,s=single_fixture(route=='nonid')
    else:
        case,s=joint_fixture('DAG_JOINT' if route=='joint_dag' else 'NETWORK_JOINT_MEANS')
    return case,finish_joint(case,s)


@pytest.mark.parametrize('route',ROUTES)
def test_saved_result_binds_conclusion_to_same_problem(route):
    case,report=report_for(route)
    saved=json.loads(json.dumps(report))
    assert workflow.replay(case,report['draft'],saved)
    changed=deepcopy(saved)
    changed['joint_entry']['state']='POINT' if saved['joint_entry']['state']!='POINT' else 'PARTIAL'
    assert not workflow.replay(case,report['draft'],changed)
    with pytest.raises(ValueError,match='JOINT_REPLAY_REQUIRED'):
        exchange.packet(case,changed)


@pytest.mark.parametrize('route',ROUTES)
def test_reusing_approval_after_question_or_source_changes_is_rejected(route):
    case,report=report_for(route)
    changed=deepcopy(case)
    changed['business_question']+=' 改为比较下一年且只评价其中一个对象。'
    assert not workflow.replay(changed,report['draft'],report)
    # Same source identifier is insufficient: source content must still match.
    changed=deepcopy(case)
    changed['sources'][0]['text']+=' 本表实际是样本，非总体。'
    assert not workflow.replay(changed,report['draft'],report)


@pytest.mark.parametrize('change',[
    'operation','completed','version','projection','decision','backend_called',
    'independent_replay','effective_answer','conditional_answer','scientific_approval',
    'production_admission','review'])
def test_valid_certificate_cannot_authorize_changed_outer_result(change):
    case,report=report_for('joint_means');bad=deepcopy(report)
    if change in ('operation','version'):bad['joint_entry'][change]='OTHER'
    elif change=='completed':bad['joint_entry'][change]=False
    elif change=='projection':bad['joint_entry'][change]['cells'][0]['support']='9'
    elif change=='decision':bad[change]='WITHHELD'
    elif change in ('backend_called','independent_replay'):bad[change]=False
    elif change in ('effective_answer','conditional_answer'):bad[change]={'status':'POINT','value':'9'}
    elif change in ('scientific_approval','production_admission'):bad[change]=True
    elif change=='review':bad['review_record']['decisions']['mean_sufficiency']='DECLINED'
    assert not workflow.replay(case,report['draft'],bad)


def test_receipt_cannot_launder_changed_source_report_status():
    case,report=report_for('joint_means');packet=exchange.packet(case,report)
    assert packet['status']=='PARTIAL'
    packet['source_report']['joint_entry']['state']='POINT'
    packet['status']='POINT'
    with pytest.raises(ValueError,match='JOINT_REPLAY_REQUIRED'):
        exchange.check_packet(case['case_id'],packet)


@pytest.mark.parametrize('authority',['SYNTHETIC_TEST','EXTERNAL_RESEARCH_REVIEW'])
def test_post_delivery_flags_and_retry_notes_do_not_change_math(authority,tmp_path):
    from demo.backend.engine import Engine,Run
    case,report=reviewed_effect('stratum',authority)
    run=Run(owner='offline',id=case['case_id'],case=case,
            synthetic=authority=='SYNTHETIC_TEST',reading_mode='direct_verify')
    engine=Engine(tmp_path);engine.runs[run.id]=run
    engine._finish_direct_verification(run,report)
    assert run.result['estimation_handoff_allowed']
    assert workflow.replay(case,report['draft'],json.loads(json.dumps(run.result)))
    assert run.result['proof']==report['proof']
    assert run.result['joint_entry']['native_result']==report['joint_entry']['native_result']
    assert run.result['scientific_approval']==(authority=='EXTERNAL_RESEARCH_REVIEW')


@pytest.mark.parametrize('change',['state','source','completed'])
def test_rejected_replacement_revokes_previous_receipt_and_display(change,tmp_path):
    from demo.backend.engine import Engine,Run
    case,report=report_for('joint_means')
    run=Run(owner='offline',id=case['case_id'],case=deepcopy(case),synthetic=True,reading_mode='direct_verify')
    engine=Engine(tmp_path);engine.runs[run.id]=run
    engine._finish_direct_verification(run,report)
    assert run.artifacts['estimate_intake_receipt']['state'] in ('RECEIVED','QUEUED')
    bad=deepcopy(report)
    if change=='source':run.case['business_question']+=' changed'
    elif change=='completed':bad['joint_entry']['completed']=False
    else:bad['joint_entry']['state']='POINT'
    with pytest.raises(ValueError,match='JOINT_.*REPLAY_REQUIRED'):
        engine._finish_direct_verification(run,bad)
    assert run.artifacts['estimate_intake_receipt']['state'] in ('SUPERSEDED','DELIVERY_FAILED')
    assert run.artifacts['identification_handoff']['estimate_handoff']['mode']=='STOP'
    assert not run.result['estimation_handoff_allowed']
    assert not run.result['independent_replay'] and 'proof' not in run.result
    assert run.result['joint_entry']['state']=='RECHECK_REQUIRED'
    assert run.user_question is None


def test_nonidentification_display_also_rechecks_source(tmp_path):
    from demo.backend.engine import Engine,Run
    case,report=report_for('nonid')
    run=Run(owner='offline',id=case['case_id'],case=deepcopy(case),synthetic=True,reading_mode='direct_verify')
    engine=Engine(tmp_path);engine.runs[run.id]=run
    engine._finish_direct_verification(run,report)
    assert run.result['joint_entry']['state']=='NONIDENTIFIABLE'
    assert not run.result['estimation_handoff_allowed']
    run.case['sources'][0]['text']+=' extra adopted restriction'
    with pytest.raises(ValueError,match='JOINT_RESULT_REPLAY_REQUIRED'):
        engine._finish_direct_verification(run,report)
    assert not run.result['independent_replay']


@pytest.mark.parametrize('status',['POINT','PARTIAL','SYMBOLIC_BOUNDS','NONIDENTIFIABLE'])
def test_label_without_verified_proof_is_not_a_mathematical_conclusion(status,tmp_path):
    from demo.backend.engine import Engine,Run
    case,report=report_for('joint_means')
    run=Run(owner='offline',id=case['case_id'],case=case,synthetic=True,reading_mode='direct_verify')
    engine=Engine(tmp_path);engine.runs[run.id]=run
    bad=deepcopy(report);bad.pop('proof');bad['independent_replay']=False
    bad['joint_entry']['state']=status
    with pytest.raises(ValueError,match='JOINT_RESULT_REPLAY_REQUIRED'):
        engine._finish_direct_verification(run,bad)
    assert run.result['joint_entry']['state']=='RECHECK_REQUIRED'
    assert not run.result['estimation_handoff_allowed']
