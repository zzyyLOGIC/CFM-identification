"""Source-bound adapter checks; these fixtures are not LLM acceptance results."""
from copy import deepcopy
import json
import pytest
from cfm_id import network_existing_entry as entry,joint_natural_entry as workflow
from cfm_id_llm import network_existing_reading as reader
from cfm_id_llm.compact_study import digest


def fixture(observational=False):
    text='仅供适配器测试：完整网络、政策概率、总体信息与科学前提均在原材料声明。'
    case=dict(case_id='adapter',business_question='政策平均结果',sources=[dict(source_id='s',text=text,kind='OTHER')],response_language='zh')
    ev=[dict(source_id='s',quote=text)];claim=lambda v:dict(value=v,evidence=ev)
    conditions=['consistency','fixed_network','finite_means','full_vector_exchangeability' if observational else 'randomization']
    s=dict(family=claim('NETWORK_OBSERVATIONAL_POLICY' if observational else 'NETWORK_FINITE_POLICY'),
        study=claim(dict(treatment='助手0/1',outcome='准时0/1',outcome_kind='binary',period='下周',fixed_background='同一处理前背景',regime='OBSERVATIONAL' if observational else 'EXPERIMENTAL')),
        network=claim(dict(nodes=['A','B'],edges=[['A','B']],complete=True,undirected=True)),
        design=None if observational else claim(dict(kind='heterogeneous_bernoulli_binary_v1',propensities={'A':'1/2','B':'1/2'})),exposure=None,
        target=claim(dict(description='全用政策平均数' if observational else '1/4全用加3/4全不用的政策均值',quantity='MEAN',
            components=[dict(assignment={'A':1,'B':1},probability=None)] if observational else [dict(assignment={'A':1,'B':1},probability='1/4'),dict(assignment={'A':0,'B':0},probability='3/4')],
            weights={'A':'1/2','B':'1/2'},distribution_complete=True)),
        information=claim(dict(availability='SYMBOLIC_POPULATION_OPERATOR',operator='OBSERVATIONAL_ASSIGNMENT_NODE_CONDITIONAL_MEANS' if observational else 'ASSIGNMENT_NODE_MEANS',outcome_nodes=['A','B'],
            assignment_cells=[] if observational else [{'A':0,'B':0},{'A':1,'B':1}],
            assignment_masses=[dict(assignment={'A':a,'B':b},probability='1/4') for a,b in [(0,0),(0,1),(1,0),(1,1)]] if observational else [],same_scope=True,complete=True)),
        conditions=[dict(code=k,statement=text,status='ADOPTED',evidence=ev) for k in conditions],remaining=[],material_notes=[])
    return case,s


def prepared(case,s):
    s=reader.inspect(case,s)
    audit=dict(binding=reader.binding(case,s),scientific_approval=False,findings=[dict(field=k,verdict='MATCH',evidence=v.get('evidence',[]),reason='unit fixture',question=None) for k,v in reader.fields(s).items()])
    reader.check_audit(case,s,audit)
    r=dict(version='test',draft={},draft_sha256=digest({}),checks=[])
    return entry.plan(case,workflow.base(r,case,s,audit))


def finish(case,s):
    r=prepared(case,s);sheet=r['condition_review']
    return entry.complete(case,r,dict(binding=sheet['binding'],authority='SYNTHETIC_TEST',decisions={x['code']:'ADOPTED' for x in sheet['items']}))


@pytest.mark.parametrize('observational',[False,True])
def test_original_native_result_and_saved_replay(observational):
    case,s=fixture(observational);r=json.loads(json.dumps(finish(case,s)))
    assert r['independent_replay'] and r['joint_entry']['state']=='POINT'
    assert workflow.replay(case,r['draft'],r)
    assert not r['estimation_handoff_allowed']
    r['joint_entry']['reading']['target']['value']['components'][0]['assignment']['A']=0
    assert not workflow.replay(case,r['draft'],r)


def test_mixture_component_without_support_is_not_silently_dropped():
    case,s=fixture();s['design']['value']=dict(kind='complete_randomization_binary_v1',m=1)
    r=finish(case,s)
    assert not r['independent_replay'] and r['backend_called']
    assert len(r['joint_entry']['native_result']['certificate']['native_inputs'])==1


def test_observational_target_without_support_is_not_local_arm_target():
    case,s=fixture(True);s['information']['value']['assignment_masses']=[dict(assignment={'A':a,'B':1-a},probability='1/2') for a in (0,1)]
    r=finish(case,s);assert not r['independent_replay']
    assert r['joint_entry']['state']!='POINT'


@pytest.mark.parametrize('status,expected',[('UNDECIDED','NEEDS_INPUT'),('NOT_ADOPTED','NEEDS_INPUT')])
def test_no_observational_exchangeability_is_not_randomized(status,expected):
    case,s=fixture(True);s['conditions'][-1]['status']=status
    r=prepared(case,s);assert r['joint_entry']['state']==expected and not r['backend_called']


def test_unknown_unused_standard_premise_is_not_a_new_restriction():
    case,s=fixture();ev=s['family']['evidence']
    s['conditions'].append(dict(code='full_vector_exchangeability',statement='未说明观察性完整向量交换性',status='UNKNOWN',evidence=ev))
    r=finish(case,s)
    assert r['independent_replay'] and r['joint_entry']['reading']['conditions'][-1]['status']=='UNKNOWN'
    assert 'full_vector_exchangeability' not in r['review_record']['decisions']
    # An explicit decision pending about this premise is different.
    s['conditions'][-1]['status']='UNDECIDED'
    assert prepared(case,s)['clarification_questions']
    # Unknown additional restrictions are not discarded either.
    s['conditions'].pop();s['remaining']=[dict(code='extra',statement='另一个额外限制待说明',status='UNKNOWN',evidence=ev)]
    assert prepared(case,s)['clarification_questions']


def test_extra_science_is_not_discarded():
    case,s=fixture();s['remaining']=[dict(code='individual',statement='每个人都不能变差',status='ADOPTED',evidence=s['family']['evidence'])]
    r=prepared(case,s);assert r['joint_entry']['reason_code']=='UNEXPRESSED_ADDITIONAL_RESTRICTION'
    assert r['joint_entry']['unhandled_declarations']==s['remaining']
    assert '每个人都不能变差' in r['joint_entry']['message']
    assert not r['backend_called']


def test_explicit_sample_has_no_repeated_source_question():
    case,s=fixture(True);s['information']['value']['availability']='FINITE_SAMPLE'
    r=prepared(case,s);workflow.known_information_stop(r)
    assert r['joint_entry']['reason_code']=='FINITE_SAMPLE_CONTRACT_NOT_CONNECTED'
    assert not r['clarification_questions'] and not entry.gaps(r)


def test_malformed_draft_hint_only_selects_unapproved_source_reader():
    case,s=fixture();raw=dict(network_facts=dict(network=dict(answers=[dict(verification_route='NETWORK_FINITE_POLICY',status='POINT')])))
    before=deepcopy(raw)
    assert entry.proposed(case,raw) and raw==before
    assert prepared(case,s)['joint_entry']['state']=='REVIEW_REQUIRED'


def test_fixed_policy_does_not_need_another_policy_distribution_and_same_scope_can_repeat():
    case,s=fixture(True);s['target']['value']['distribution_complete']=None
    s['information']['value']['assignment_cells']=[x['assignment'] for x in s['information']['value']['assignment_masses']]
    assert finish(case,s)['independent_replay']
    s['information']['value']['assignment_cells'].pop()
    with pytest.raises(ValueError,match='SCOPE_DISAGREES'):prepared(case,s)
