"""Source-slot reconstruction, semantic boundaries and old execution after projection."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from cfm_id.research_spec_view import build_view, from_json, to_html, Entry
from cfm_id.research_spec_projection import expand, DESIGN_ALIASES


def wire(value):
    return json.loads(json.dumps(value,ensure_ascii=False,allow_nan=False))


def projected(raw, contract):
    p=expand(build_view(raw,contract=contract))
    assert p.compare(raw)['equivalent']
    assert p.as_dict()['executable'] is False
    return p.restore_legacy()


def test_slots_reconstruct_without_original_values_and_detect_missing_containers():
    raw={'study':{'nodes':['乙','甲']},'future/key~':{'a':[],'b':{},'c':None,'d':1,'e':1.0,'f':True}}
    p=expand(from_json(json.dumps(raw),contract='network-facts'))
    assert not hasattr(p,'record_json')
    assert p.restore_legacy()==raw
    for path in ('/future~1key~0/a','/future~1key~0/c'):
        with pytest.raises(ValueError,match='MISSING_SLOT'):
            replace(p,entries=tuple(e for e in p.entries if e.pointer!=path)).restore_legacy()
    with pytest.raises(ValueError,match='DUPLICATE_SLOT'):
        replace(p,entries=p.entries+(p.entries[0],)).restore_legacy()
    with pytest.raises(ValueError,match='EXTRA_SLOT'):
        replace(p,entries=p.entries+(Entry('unmapped','extra','/unknown','3'),)).restore_legacy()
    altered=replace(p,entries=tuple(replace(e,value_json='false') if e.pointer=='/future~1key~0/c' else e for e in p.entries))
    assert altered.compare(raw)['changed_paths']==['/future~1key~0/c']


@pytest.mark.parametrize('design,exposure', [('D1','E1'),('D2','E2'),('D3','E3'),('D4','E4'),('D5','E5'),('D6','E4'),('D7','E1'),('D8','E2')])
def test_six_attributes_reconstruct_original_design_probability_and_certificate(design,exposure):
    from examples.finite_mean_box_reference import setup,approval_records
    from cfm_id import business_dispatch as dispatch
    s,options,spec,_=setup(design,exposure)
    raw=options['candidate'];p=expand(build_view(raw,contract='network-facts'))
    kinds={a['facet']:a['attributes']['template_id'] for a in p.attributes if 'template_id' in a['attributes']}
    assert kinds=={'assignment':design,'exposure':exposure}
    assert not any(i['code']=='TEMPLATE_PARAMETERS_INCOMPLETE' for i in p.issues)
    plan=dispatch.inspect_methods(s,'q1',**options)
    approvals=approval_records(plan)
    before=dispatch.execute(s,'q1',**options,**approvals)
    after=dispatch.execute(s,'q1',**dict(options,candidate=p.restore_legacy()),**approvals)
    assert before==after and after['independent_replay']
    assert raw==p.restore_legacy()


@pytest.mark.parametrize('state',['NOT_ADOPTED','UNDECIDED','NOT_STATED','CONFLICTING'])
def test_refusal_unknown_and_conflict_keep_original_stop(state):
    from examples.finite_mean_box_reference import setup
    from cfm_id import business_dispatch as dispatch
    s,options,_,_=setup('D6','E4');raw=options['candidate']
    raw['first_stage_exclusion']['status']=state
    if state=='NOT_STATED':raw['first_stage_exclusion']['source_ids']=[]
    p=expand(build_view(raw,contract='network-facts'))
    before=dispatch.inspect_methods(s,'q1',**options)
    after=dispatch.inspect_methods(s,'q1',**dict(options,candidate=p.restore_legacy()))
    assert before==after and not after['backend_called']
    assert p.restore_legacy()['first_stage_exclusion']['status']==state


def test_unspecified_context_parameter_and_new_template_never_gain_defaults():
    raw={'target':{'context':'下周；旺季门店，是否只评价老店未定'},
         'assignment':{'kind':'TWO_GROUP_FIXED_QUOTA','groups':None},
         'exposure':{'kind':'FUTURE_VECTOR_MAPPING'},'assumptions':{'consistency':{'value':False}}}
    p=expand(build_view(raw,contract='network-facts'))
    codes={i['code'] for i in p.issues}
    assert {'TEXT_SCOPE_UNSPLIT','TEMPLATE_PARAMETERS_INCOMPLETE','EXPOSURE_NOT_EXPANDED','LEGACY_BOOLEAN_STANCE'}<=codes
    assert p.restore_legacy()==raw
    assert not any(a['facet']=='exposure' for a in p.attributes)


@pytest.mark.parametrize('method',['partial_mean','partial_contrast','mean_order','count_mean','count_contrast','finite_mean','finite_contrast'])
def test_new_source_materials_report_review_and_packet_retain_original_bounds(method):
    from demo.tests.test_homepage_capabilities import study,cited_answer,adopt
    from cfm_id.direct_verification import verify,replay
    from cfm_id import direct_policy_exchange as exchange
    c=study(method);a=cited_answer(method,c)
    r=verify(c,a)
    assert not r['estimation_handoff_allowed']
    v=build_view(r,contract='direct-report');p=expand(v)
    assert not any(e.facet=='assumptions' and e.pointer.startswith('/draft') for e in v.entries)
    assert any(e.facet=='target' and '/materials/first/' in e.pointer for e in v.entries) or method=='partial_mean'
    assert any(e.facet=='review' and e.pointer.startswith('/condition_review') for e in v.entries)
    assert replay(c,a,p.restore_legacy())
    e=r['proof']['evidence'];m=e['materials']
    restored=projected(m,'policy-materials')
    if method!='partial_mean':
        from cfm_id import source_bounds_solver
        fn=source_bounds_solver.ordered if m['operator']=='MEAN_ORDER' else source_bounds_solver.box
        claim,cert=fn(restored,deepcopy(e['claim']['target']))
        assert claim==e['claim'] and cert==e['certificate']
    accepted=verify(c,a,science_review=adopt(r))
    packet=exchange.packet(c,accepted)
    assert exchange.check_packet(c['case_id'],packet)==exchange.check_packet(c['case_id'],projected(packet,'policy-packet'))
    assert projected(accepted,'direct-report')==accepted
    assert replay(c,a,projected(accepted,'direct-report'))
    old=adopt(r);changed=deepcopy(c);changed['business_question']+='另一个时期。'
    with pytest.raises(ValueError):verify(changed,a,science_review=old)


EXAMPLES=json.loads((Path(__file__).parents[1]/'demo/math-library-examples.json').read_text(encoding='utf-8'))
OPERATIONS=['population','task','batch','linear','effects','business','r3_pair','signature_support','quota_support',
            'legacy_bridge','legacy_compare','requirements','DAG_CLASSICAL_BACKDOOR','DAG_CLASSICAL_FRONTDOOR',
            'DAG_ADJUSTMENT','DAG_GENERAL_ID','BINARY_IV_LATE_ATE','MEAN_ORDER_D2_E1']


@pytest.mark.parametrize('op',OPERATIONS)
def test_every_registered_math_operation_keeps_problem_and_original_gate(op):
    from demo.backend import math_library
    doc=dict(format='causal-id.math-request/1',question='按原材料核对附件里的问题。',operation=op,problem=EXAMPLES[op])
    restored=projected(doc,'math-request')
    assert restored==doc
    before=math_library.run(dict(operation=op,problem=doc['problem']))
    after=math_library.run(dict(operation=op,problem=restored['problem']))
    assert wire(before)==wire(after)
    assert not after.get('estimation_handoff_allowed')
    assert any(i['code']=='QUESTION_EQUIVALENCE_NOT_INFERRED' for i in expand(build_view(doc,contract='math-request')).issues)
    if op in ('population','task','batch','linear','effects','business','r3_pair','legacy_bridge','legacy_compare'):
        sheet=before['worksheet']
        review={'binding':sheet['binding'],'decisions':dict.fromkeys(sheet['items'],'ACCEPTED'),
                'reviewer':'Synthetic test reviewer','evidence':'Original synthetic specification independently stipulated'}
        b=math_library.run(dict(operation=op,problem=doc['problem'],review=review))
        c=math_library.run(dict(operation=op,problem=restored['problem'],review=review))
        assert wire(b)==wire(c) and not c['estimation_handoff_allowed']


def test_registry_coverage_is_explicit_and_unknown_operations_remain_opaque():
    from demo.backend.math_library import catalog
    assert set(OPERATIONS)==set(catalog()['native'])|set(catalog()['research'])
    raw={'format':'causal-id.math-request/1','question':'下一版问题','operation':'NEW_METHOD',
         'problem':{'target':{'kind':'NEW_KIND'},'assumptions':['a']}}
    v=build_view(raw,contract='math-request')
    assert all(e.facet=='unmapped' for e in v.entries if e.pointer.startswith('/problem/'))
    assert expand(v).restore_legacy()==raw


def test_user_supplied_review_and_solver_admission_do_not_become_a_new_approval():
    raw={'version':'direct-verification/24','draft':{'status':'POINT','functional':'<script>bad()</script>'},
         'proof':{'evidence':{'materials':{'conditions':[{'code':'consistency','status':'ADMITTED','quote':'拟采用'}],
                                         'synthetic_review_only':True}}},
         'review_record':{'authority':'SYNTHETIC_TEST','decisions':{'consistency':'UNDECIDED'}},
         'scientific_approval':False,'estimation_handoff_allowed':False}
    v=build_view(raw,contract='direct-report');p=expand(v)
    assert p.restore_legacy()==raw and not p.as_dict()['scientific_approval']
    bypath={e.pointer:e.facet for e in v.entries}
    assert bypath['/proof/evidence/materials/conditions/0/status']=='assumptions'
    assert bypath['/review_record/decisions/consistency']=='review'
    assert bypath['/proof/evidence/materials/synthetic_review_only']=='review'
    assert bypath['/draft/status']=='model_answer'
    rendered=to_html(v)
    assert '<script>' not in rendered and '&lt;script&gt;' in rendered


def test_native_design_aliases_are_real_existing_schema_literals():
    from pfn_pipeline._internal.identification import schemas
    classes=[schemas.IndependentBernoulliDesignV1,schemas.HeterogeneousBernoulliDesignV1,
             schemas.CompleteRandomizationDesignV1,schemas.TwoGroupFixedQuotaDesignV1,
             schemas.ClusterBernoulliDesignV24,schemas.MultiGroupFixedQuotaDesignV25,
             schemas.TwoStageQuotaMixtureDesignV27,schemas.UnequalProbabilityFixedQuotaDesignV1,schemas.RerandomizedBalancedDesignV1]
    assert {c.model_fields['kind'].default for c in classes}=={k for k in DESIGN_ALIASES if k[0].islower()}
    iid = expand(build_view({'assignment': {'kind': 'iid_bernoulli_binary_v1', 'p': '1/2'}}, contract='network-facts'))
    assert '同概率' in iid.attributes[0]['attributes']['joint_law']
    assert iid.restore_legacy()['assignment']['p'] == '1/2'


def test_policy_mixture_probability_is_target_not_original_assignment():
    doc={'format':'causal-id.math-request/1','question':'评价两份政策的混合', 'operation':'business',
         'problem':{'kind':'finite_policy','inquiry':{'policy_probabilities':['1/3','2/3'],
            'components':[{'study':{'assignment_design_json':'{ "kind": "complete_randomization_binary_v1", "m": 1 }'},
                           'target':{'policy_assignment':[1,0]},'r1b_sources':[{'availability':'SYMBOLIC_POPULATION_OPERATOR'}]}]}}}
    v=build_view(doc,contract='math-request');p=expand(v)
    slots={e.pointer:e.facet for e in v.entries}
    assert slots['/problem/inquiry/policy_probabilities/0']=='target'
    assert slots['/problem/inquiry/components/0/study/assignment_design_json']=='assignment'
    assert slots['/problem/inquiry/components/0/r1b_sources/0/availability']=='information'
    assert p.restore_legacy()==doc
    assert any('decoded_original_parameters' in a['attributes'] for a in p.attributes)


@pytest.mark.parametrize('field,value', [('first',[0,0]),('weights',['0','1']),('bounds',[{'lower':'-1'}]),
                                         ('conditions',[{'code':'consistency','status':'NOT_ADOPTED'}])])
def test_changed_target_or_restriction_is_visible_in_compatibility_comparison(field,value):
    raw={'first':[1,1],'second':[0,0],'weights':['1/2','1/2'],'bounds':[{'lower':'0'}],
         'conditions':[{'code':'consistency','status':'UNDECIDED'}]}
    p=expand(build_view(raw,contract='policy-materials'))
    changed=deepcopy(raw);changed[field]=value
    result=p.compare(changed)
    assert not result['equivalent'] and all(path.startswith('/'+field) for path in result['changed_paths'])


def test_local_arm_other_assignments_do_not_become_a_fixed_policy():
    raw={'target':{'kind':'LOCAL_EXPOSURE_CONTRAST','first':{'own':1,'peer':0},'second':{'own':0,'peer':0},
                   'remaining_assignment':'DESIGN_CONDITIONAL_AVERAGE','population':['甲'],
                   'aggregation':'EQUAL_MEAN','shared_outcome_and_context':'本周，保持原问背景'}}
    p=expand(build_view(raw,contract='network-facts'))
    assert p.restore_legacy()==raw
    assert not any(a['attributes'].get('operation')=='IDENTITY' for a in p.attributes)
    assert any(e.pointer=='/target/remaining_assignment' and e.facet=='target' for e in p.entries)
