"""No target-driven projection, invented scope, or scientific short circuit."""
import json
from copy import deepcopy
from fractions import Fraction
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_dispatch as dispatch,network_effect_dispatch as effects
from cfm_id_llm import network_effect_reading as reading
from examples.network_effect_dispatch_reference import approval_records
from evaluation.network_effect_a4_cases import CASES,EXPECTED,setup


@pytest.mark.parametrize('name',CASES)
def test_complete_prose_preserves_actual_a4_and_scientific_admission(name):
    s,e,data,raw=setup(name);before=deepcopy(raw)
    Draft202012Validator(json.JSONDecoder().raw_decode(e['request']['user'])[0]['output_schema']).validate(raw)
    cells={(x['node'],x['own'],x['exposure']) for x in raw['information'][0]['arm_cells']}
    assert cells=={(n,a,x) for n in data['scope_nodes'] for a,x in data['scope_arms']}
    opts=dict(query_review=e['query_review'],candidate=raw,request_sha256=e['request_sha256'])
    p=dispatch.inspect_methods(s,'q1',**opts)
    a=approval_records(p) if EXPECTED[name]=='POINT' else dict(research_protocol_selected=True)
    r=dispatch.execute(s,'q1',**opts,**a)
    assert r['state']==EXPECTED[name] and raw==before
    if EXPECTED[name]=='POINT':
        assert r['independent_replay']
        assert r['mathematical_claim']['target']['evaluation_population']==data['members']
        for term in r['certificate']['results'][0]['constituent_arms']:
            sign=1 if (term['own_treatment'],term['exposure_state'])==data['arms'][0] else -1
            assert Fraction(term['coefficient'])==Fraction(sign,len(data['members']))
    else:assert not r['backend_called'] and r['mathematical_claim'] is None


def test_unknown_arm_scope_stays_empty_instead_of_expanding_from_target_or_nodes():
    s,e,data,raw=setup('cleaning_full');raw['information'][0]['arm_cells']=[];before=deepcopy(raw)
    parsed=reading.parse(e['bundle'],raw,binding=e['fact_binding_sha256'])
    assert parsed['facts']['information'][0]['arm_cells']==[]
    r=dispatch.execute(s,'q1',query_review=e['query_review'],candidate=raw,request_sha256=e['request_sha256'],research_protocol_selected=True)
    assert r['state']=='NEEDS_INPUT' and not r['backend_called'] and raw==before


@pytest.mark.parametrize('distortion',['drop_non_target_scope','invent_other_cells','upgrade_sample'])
def test_source_semantics_rejection_blocks_even_when_wrong_scope_covers_target(distortion,monkeypatch):
    name={'drop_non_target_scope':'cleaning_full','invent_other_cells':'cleaning_target_only','upgrade_sample':'linen_sample'}[distortion]
    s,e,data,raw=setup(name);source=raw['information'][0]
    if distortion=='drop_non_target_scope':
        source['outcome_nodes']=data['members']
        source['arm_cells']=[x for x in source['arm_cells'] if x['node'] in data['members'] and (x['own'],x['exposure']) in data['arms']]
    else:
        source.update(operator='NODE_ARM_MEANS',availability='SYMBOLIC_POPULATION_OPERATOR',outcome_nodes=data['nodes'],
            arm_cells=[dict(node=n,own=a,exposure=x) for n in data['nodes'] for a in (0,1) for x in (0,1)])
    before=deepcopy(raw);opts=dict(query_review=e['query_review'],candidate=raw,request_sha256=e['request_sha256'])
    plan=dispatch.inspect_methods(s,'q1',**opts);assert plan['state']=='REVIEW_REQUIRED'
    a=approval_records(plan);v=a['native_reviews']['network.randomized.local_contrast']['reading_review'].model_dump(mode='json')
    v['decisions']['all_information_and_restrictions_preserved']='REJECTED'
    v['decisions']['source_entailment']='REJECTED'
    v['evidence']='Explicit synthetic source audit rejects loss or invention of declared A4 scope; covering target cells alone does not establish faithful source reading.'
    a['native_reviews']['network.randomized.local_contrast']['reading_review']=dispatch.DispatchReview.model_validate(v)
    monkeypatch.setattr(effects,'_compile',lambda *a,**kw:pytest.fail('Rejected information must not reach math'))
    r=dispatch.execute(s,'q1',**opts,**a)
    assert r['state']=='CHECK_BLOCKED' and not r['backend_called'] and raw==before
