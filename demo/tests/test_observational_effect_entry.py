"""Reuse the same source wire, applicability checks and native methods."""
from copy import deepcopy
import json
import pytest
from examples import network_extended_reference as ref
from cfm_id import observational_effect_entry as entry,joint_natural_entry as flow
from cfm_id_llm import observational_effect_source as reader
from cfm_id_llm.compact_study import digest


def fixture(name):
    old,wire=ref.fixture(name);b=old['bundle']
    case=dict(case_id=b['case_id'],business_question=b['question'],sources=[dict(source_id=k,kind='OTHER',text=v) for k,v in b['documents'].items()],response_language='zh')
    wire['reference_context']=reader.refs(case)['context']
    return case,wire


def prepared(case,wire):
    s=reader.inspect(case,wire);fs=reader.fields(case,s)
    a=dict(binding=reader.binding(case,s),scientific_approval=False,findings=[dict(field=k,verdict='MATCH',evidence=v.get('evidence',[]),reason='offline source fixture',question=None) for k,v in fs.items()])
    a=reader.check_audit(case,s,a)
    return entry.plan(case,flow.base(dict(draft={},draft_sha256=digest({}),checks=[]),case,s,a))


@pytest.mark.parametrize('name',['observed','stratum','nodewise'])
def test_native_binding_replay_and_stale_source(name):
    case,wire=fixture(name);r=prepared(case,wire)
    assert r['joint_entry']['state']=='REVIEW_REQUIRED',r
    sheet=r['condition_review'];review=dict(binding=sheet['binding'],authority='SYNTHETIC_TEST',decisions={x['code']:'ADOPTED' for x in sheet['items']})
    out=entry.complete(case,r,review)
    assert out['independent_replay'],out
    assert not out['estimation_handoff_allowed']
    assert flow.replay(case,out['draft'],json.loads(json.dumps(out)))
    changed=deepcopy(out);changed['joint_entry']['reading']['wire']['target']['first']['own']=1-wire['target']['first']['own']
    assert not flow.replay(case,out['draft'],changed)


@pytest.mark.parametrize('name,condition',[('observed','full_vector_conditional_exchangeability'),('stratum','potential_outcome_exposure_sufficiency'),('nodewise','local_covariate_exposure_mean_exchangeability')])
def test_original_scientific_gate_still_required(name,condition):
    case,wire=fixture(name);wire['assumptions'][condition]['value']=None
    r=prepared(case,wire)
    assert r['joint_entry']['state']=='NEEDS_INPUT' and not r['backend_called']


def test_source_wrong_averaging_does_not_select_easier_method():
    case,wire=fixture('stratum');wire['target']['averaging']='OBSERVED_ALLOCATION_CONDITIONAL'
    r=prepared(case,wire)
    assert r['joint_entry']['state']=='UNSUPPORTED' and not r['backend_called']


def test_no_old_approval_is_fabricated_during_preparation():
    case,wire=fixture('observed');r=prepared(case,wire)
    p=r['joint_entry']['existing_plan']
    assert p['query_review']['authority']=='UNAPPROVED' and p['query_review']['scientific_approval'] is False
    assert not r['backend_called']


@pytest.mark.parametrize('operator',['FINITE_ASSIGNMENT_LAW','MIXTURE_ARM_LAW','NODEWISE_MIXTURE_ARM_LAW'])
def test_remaining_existing_information_operators_keep_native_replay(operator):
    from itertools import product
    case,wire=fixture('nodewise' if operator.startswith('NODEWISE') else 'observed')
    info=wire['information'][0];ids=info['source_ids'];nodes=wire['study']['nodes'];info['operator']=operator
    components=[dict(source_ids=ids,weight='1/2',probabilities={n:p for n in nodes}) for p in ('1/4','3/4')]
    if operator=='FINITE_ASSIGNMENT_LAW':
        info.pop('covered_cells');info.pop('probabilities')
        info['assignment_masses']=[dict(source_ids=ids,assignment=dict(zip(nodes,z)),probability='1/8') for z in product((0,1),repeat=3)]
    elif operator=='MIXTURE_ARM_LAW':
        info.pop('probabilities');info['mixture_components']=components
    else:
        for profile in info['profiles']:
            profile.pop('probabilities');profile['mixture_components']=components
    r=prepared(case,wire);s=r['condition_review']
    out=entry.complete(case,r,dict(binding=s['binding'],authority='SYNTHETIC_TEST',decisions={x['code']:'ADOPTED' for x in s['items']}))
    assert out['independent_replay'] and flow.replay(case,out['draft'],json.loads(json.dumps(out)))
    assert out['joint_entry']['reading']['wire']['information'][0]['operator']==operator
