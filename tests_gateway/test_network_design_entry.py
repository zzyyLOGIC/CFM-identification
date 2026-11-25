"""D/E entry integration, independent finite oracles, and fail-closed reviews.

The references are fixed synthetic readings, not measurements of LLM accuracy.
"""
from copy import deepcopy
from fractions import Fraction
from itertools import product, combinations
from math import comb
import json
import pytest
from jsonschema import Draft202012Validator
from cfm_id import business_dispatch as dispatch, method_diagnostics
from cfm_id_llm import network_design_reading as fields
from examples.network_design_exposure_reference import setup, DESIGNS, EXPOSURES, NODES, approval_records


def execute(s, options):
    plan=dispatch.inspect_methods(s,'q1',**options)
    return dispatch.execute(s,'q1',**options,**approval_records(plan)) if plan['state']=='REVIEW_REQUIRED' else plan


def full_probability(design, z):
    """Independent finite allocation law; no production design/support calls."""
    kind=design['kind']
    if kind=='INDEPENDENT_BERNOULLI':
        result=Fraction(1)
        for n,v in z.items():
            p=Fraction(design['probabilities'][n]);result*=p if v else 1-p
        return result
    if kind=='UNIFORM_FIXED_QUOTA':
        return Fraction(1,comb(len(z),design['fixed_count'])) if sum(z.values())==design['fixed_count'] else Fraction(0)
    if kind=='CLUSTER_BERNOULLI':
        result=Fraction(1)
        for members,p in zip(design['clusters'],design['cluster_probabilities']):
            if len({z[n] for n in members})!=1:return Fraction(0)
            result*=Fraction(p) if z[members[0]] else 1-Fraction(p)
        return result
    if kind in ('UNEQUAL_PROBABILITY_FIXED_QUOTA','RERANDOMIZED_BALANCED'):
        nodes=tuple(z);m=design['fixed_count']
        law={}
        for treated in combinations(nodes,m):
            treated=frozenset(treated)
            if design.get('unit_weights') is not None:
                weight=Fraction(1)
                for n in treated:weight*=Fraction(design['unit_weights'][n])
            else:
                weight=sum((Fraction(p) for members,p in zip(design['treated_sets'],design['set_probabilities'])
                            if frozenset(members)==treated),Fraction(0))
            if kind=='RERANDOMIZED_BALANCED':
                rest=set(nodes)-treated
                if not treated or not rest:weight=Fraction(0)
                else:
                    for values in design['balance_covariates'].values():
                        delta=sum(Fraction(values[n]) for n in treated)/len(treated)-sum(Fraction(values[n]) for n in rest)/len(rest)
                        if abs(delta)>Fraction(design['balance_tolerance']):weight=Fraction(0)
            law[treated]=weight
        total=sum(law.values(),Fraction(0))
        assert total>0
        return law.get(frozenset(n for n,v in z.items() if v),Fraction(0))/total
    def conditional(quotas):
        result=Fraction(1)
        for group,m in zip(design['groups'],quotas):
            if sum(z[n] for n in group)!=m:return Fraction(0)
            result/=comb(len(group),m)
        return result
    if kind=='TWO_STAGE_QUOTA_MIXTURE':
        return sum((Fraction(p)*conditional(q) for q,p in zip(design['quota_profiles'],design['profile_probabilities'])),Fraction(0))
    return conditional(design['treated_quotas'])


def arm_probability(c, node, own, exposure):
    nodes=c['study']['nodes']; neighbors={v if u==node else u for u,v in c['study']['edges'] if node in (u,v)}
    kind=c['exposure']['kind']
    if kind=='PRETREATMENT_CORE_COLLABORATOR_MAJORITY':neighbors=set(c['exposure']['core_collaborators'][node])
    result=Fraction(0)
    for bits in product((0,1),repeat=len(nodes)):
        z=dict(zip(nodes,bits));k=sum(z[v] for v in neighbors);degree=len(neighbors)
        if kind=='EXACT_TREATED_NEIGHBOR_COUNT': state=k
        elif kind=='ANY_TREATED_NEIGHBOR':state=int(k>0)
        elif kind=='THREE_LEVEL_TREATED_NEIGHBOR_FRACTION':state=0 if 3*k<degree else 1 if 3*k<2*degree else 2
        else:state=int(2*k>degree)
        if z[node]==own and state==exposure:result+=full_probability(c['assignment'],z)
    return result


@pytest.mark.parametrize('design',tuple(DESIGNS))
@pytest.mark.parametrize('exposure',tuple(EXPOSURES))
def test_complete_grid_effect_spillover_policy_and_contrast_with_replay(design,exposure):
    for family in ('effect','spillover','policy','contrast'):
        s,e,o,p=setup(design,exposure,family)
        raw=deepcopy(o['candidate']);body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
        Draft202012Validator(body['output_schema']).validate(raw)
        assert p['state']=='REVIEW_REQUIRED',(design,exposure,family,p.get('reason_code'))
        assert e['assignment_semantics']=='joint-assignment-law-1'
        assert '目前专门事实入口仅接' not in e['request']['system']
        assert all(kind in e['request']['system'] for kind in fields.DESIGN_FIELDS)
        r=dispatch.execute(s,'q1',**o,**approval_records(p))
        assert r['state']=='POINT' and r['independent_replay'],(design,exposure,family,r.get('reason_code'))
        # Existing D/E cases also exercise each connected diagnostic evidence shape.
        view=method_diagnostics.describe(p,result=r)
        reported={row['method']:row for row in view['methods']}
        assert all(reported[a['method']]['certificate']['state']=='REPLAY_REPORTED' for a in r['answers'])
        assert view['target']==p['proposed_target'] and not view['grants_execution']
        assert raw==o['candidate'] and not r['production_admission']
        if family in ('effect','spillover'):
            target=raw['target'];expected={}
            for n in target['population']:
                for side,sign in (('first',1),('second',-1)):
                    arm=target[side];expected[n,arm['own'],arm['exposure']]=Fraction(sign,len(target['population']))
            terms=r['certificate']['results'][0]['constituent_arms']
            assert {(a['node_id'],a['own_treatment'],a['exposure_state']):Fraction(a['coefficient']) for a in terms}==expected
            for a in terms:
                assert Fraction(a['joint_support'])==arm_probability(raw,a['node_id'],a['own_treatment'],a['exposure_state'])
        else:
            expected_methods=({'network.randomized.full_policy_mean','network.randomized.signature_policy_mean'} if family=='policy' else
                              {'network.randomized.full_policy_contrast','network.randomized.signature_policy_contrast'})
            assert {a['method'] for a in r['answers']}==expected_methods
            assert all(a['independent_replay'] for a in r['answers'])


@pytest.mark.parametrize('design',tuple(DESIGNS))
def test_parameter_gap_does_not_call_any_native_constructor(monkeypatch,design):
    s,e,o,_=setup(design,'E4');raw=o['candidate'];key=fields.DESIGN_FIELDS[raw['assignment']['kind']][-1]
    raw['assignment'][key]=None
    from cfm_id import network_design_adapter
    def forbidden(*args,**kwargs):raise AssertionError('native constructor called before complete reviewed facts')
    monkeypatch.setattr(network_design_adapter,'make_arm',forbidden)
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='NEEDS_INPUT' and not r['backend_called']


@pytest.mark.parametrize('missing', ['balance_covariates', 'balance_tolerance'])
def test_partial_balance_rule_is_missing_but_invalid_supplied_part_is_rejected(missing):
    s,e,o,_=setup('D8','E4')
    o['candidate']['assignment'][missing]=None
    body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
    Draft202012Validator(body['output_schema']).validate(o['candidate'])
    result=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert result['state']=='NEEDS_INPUT' and not result['backend_called']
    if missing=='balance_covariates':o['candidate']['assignment']['balance_tolerance']='-1'
    else:o['candidate']['assignment']['balance_covariates']={}
    result=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert result['state']=='CHECK_BLOCKED' and not result['backend_called']


@pytest.mark.parametrize('family',['effect','policy','contrast'])
def test_unavailable_assignment_is_missing_information_but_science_refusal_stays_distinct(monkeypatch,family):
    from cfm_id import network_effect_dispatch,network_policy_dispatch
    def forbidden(*a,**kw):raise AssertionError('No compilation while a declaration is missing or refused')
    monkeypatch.setattr(network_effect_dispatch,'_compile',forbidden)
    monkeypatch.setattr(network_policy_dispatch,'_compile',forbidden)
    # Both the legacy boolean record and the recommended source-statement wire.
    for profile in (None,'network-source-selections-alignment-1'):
        s,e,o,p=setup('D2','E4',family,profile=profile)
        approved=approval_records(p)
        initial=deepcopy(o['candidate'])
        for available in (False,None):
            for missing_quota in (False,True):
                c=deepcopy(initial);o['candidate']=c
                group,key=('design_facts','assignment_rule_available') if 'design_facts' in c else ('assumptions','known_assignment_law')
                c[group][key]['value']=available
                if missing_quota:c['assignment']['fixed_count']=None
                before=deepcopy(c)
                r=dispatch.execute(s,'q1',**o,**approved)
                assert r['state']=='NEEDS_INPUT',r.get('reason_code')
                assert r['clarification_questions'] and not r['backend_called'] and r['certificate'] is None
                assert c==before  # No null/false rewriting or recovered quota.
                if 'scientific_statements' in c:
                    c['scientific_statements']['assignment_outcome_independence']['status']='NOT_ADOPTED'
                else:c['assumptions']['full_vector_randomization']['value']=False
                r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
                assert r['state']=='ADAPTER_NOT_CONNECTED' and not r['backend_called']
                assert 'DECLARED_MODEL_EXCLUDES:' in r['reason_code']


@pytest.mark.parametrize('family',['effect','policy','contrast'])
@pytest.mark.parametrize('status,state',[(None,'NEEDS_INPUT'),('NOT_STATED','NEEDS_INPUT'),('UNDECIDED','NEEDS_INPUT'),
    ('NOT_ADOPTED','ADAPTER_NOT_CONNECTED'),('CONFLICTING','READING_RECHECK_REQUIRED')])
def test_d6_science_is_separate_from_design_and_never_inferred(family,status,state):
    s,e,o,_=setup('D6','E3',family)
    if status is None:o['candidate']['first_stage_exclusion']=None
    else:
        o['candidate']['first_stage_exclusion']['status']=status
        if status=='NOT_STATED':o['candidate']['first_stage_exclusion']['source_ids']=[]
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']==state,(r['state'],r.get('reason_code'))
    assert not r['backend_called'] and not r['independent_replay'] and r['mathematical_claim'] is None
    if family=='effect' and status=='NOT_ADOPTED':
        assert r['reason_code']=='DECLARED_MODEL_EXCLUDES:'+fields.D6_CONDITION
        assert '第一阶段配额方案' in r['processing_explanation']


@pytest.mark.parametrize('family',['effect','policy','contrast'])
def test_d6_review_cannot_omit_or_reject_added_scientific_decision(family):
    s,e,o,p=setup('D6','E4',family)
    # Endpoint review structure differs; local/mean cases cover exact worksheets,
    # and the contrast requires the same original endpoint reviews.
    reviews=approval_records(p)
    def mutate(value,mode):
        if isinstance(value,dict):
            if fields.D6_CONDITION in value.get('decisions',{}):
                if mode=='omit':value['decisions'].pop(fields.D6_CONDITION)
                else:value['decisions'][fields.D6_CONDITION]='REJECTED'
            for v in value.values():mutate(v,mode)
        elif isinstance(value,list):
            for v in value:mutate(v,mode)
    # Convert typed reviews to JSON recursively without changing their bindings.
    def plain(v):
        if hasattr(v,'model_dump'):return v.model_dump(mode='json')
        if isinstance(v,dict):return {k:plain(x) for k,x in v.items()}
        return v
    for mode in ('omit','reject'):
        altered=plain(reviews);mutate(altered,mode)
        r=dispatch.execute(s,'q1',**o,**altered)
        assert r['state']=='CHECK_BLOCKED' and not r['backend_called']


@pytest.mark.parametrize('mutation',['duplicate_member','too_large_quota','misaligned_clusters','bad_profile_sum','duplicate_profile','bad_core','missing_core','invalid_state','wrong_source'])
def test_invalid_design_or_exposure_is_blocked(mutation):
    s,e,o,_=setup('D6','E3');c=o['candidate']
    if mutation=='duplicate_member':c['assignment']['groups'][1][0]=NODES[0]
    elif mutation=='too_large_quota':c['assignment']['quota_profiles'][0][0]=9
    elif mutation=='misaligned_clusters':
        c['assignment']=dict(DESIGNS['D4'],source_ids=c['assignment']['source_ids']);c['assignment']['cluster_probabilities']=['1/2'];c['first_stage_exclusion']=None
    elif mutation=='bad_profile_sum':c['assignment']['profile_probabilities']=['1/3','1/3']
    elif mutation=='duplicate_profile':c['assignment']['quota_profiles'][1]=c['assignment']['quota_profiles'][0]
    elif mutation=='bad_core':c['exposure']['core_collaborators'][NODES[0]]=[NODES[0]]
    elif mutation=='missing_core':c['exposure']['core_collaborators'].pop(NODES[0])
    elif mutation=='invalid_state':c['target']['first']['exposure']=2
    elif mutation=='wrong_source':c['first_stage_exclusion']['source_ids']=['s99999']
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']==('NEEDS_INPUT' if mutation=='missing_core' else 'CHECK_BLOCKED')
    assert not r['backend_called']


@pytest.mark.parametrize('design',tuple(DESIGNS))
def test_reverse_subset_local_target_and_changed_inputs_invalidate_review(design):
    s,e,o,p=setup(design,'E4',reverse=True,population=NODES[:2])
    r=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert r['state']=='POINT' and r['independent_replay']
    terms=r['certificate']['results'][0]['constituent_arms']
    assert len(terms)==4 and {a['node_id'] for a in terms}==set(NODES[:2])
    assert all(Fraction(a['coefficient'])==(Fraction(1,2) if a['own_treatment']==0 else Fraction(-1,2)) for a in terms)
    o['candidate']['exposure']['kind']='ANY_TREATED_NEIGHBOR'
    o['candidate']['target']['first']['exposure']=1;o['candidate']['target']['second']['exposure']=1
    stale=dispatch.execute(s,'q1',**o,**approval_records(p))
    assert stale['state']=='CHECK_BLOCKED' and not stale['backend_called']


@pytest.mark.parametrize('family',['policy','contrast'])
def test_recommended_policy_profile_preserves_all_new_parameters(family):
    from cfm_id_llm.network_fact_protocols import network_fact_profiles
    for profile in network_fact_profiles():
        s,e,o,p=setup('D6','E3',family,profile=profile)
        body=json.JSONDecoder().raw_decode(e['request']['user'])[0]
        Draft202012Validator(body['output_schema']).validate(o['candidate'])
        assert p['state']=='REVIEW_REQUIRED',(profile,p.get('reason_code'))
        r=dispatch.execute(s,'q1',**o,**approval_records(p))
        assert r['state']=='POINT' and r['independent_replay'] and len(r['answers'])==2,profile


@pytest.mark.parametrize('family',['effect','policy','contrast'])
def test_added_records_have_independent_source_review_and_located_reread(family):
    from cfm_id import fact_source_review as source
    from cfm_id.fact_reading_revision import prepare_recheck
    from tests_gateway.test_fact_source_review import record
    from tests_gateway.test_fact_reading_revision import feedback
    s,e,o,_=setup('D6','E3',family,profile='network-source-selections-alignment-1')
    w=source.prepare(e,o['candidate'])
    assert w['fields']['/first_stage_exclusion']['citation_groups']['source_ids']==o['candidate']['first_stage_exclusion']['source_ids']
    assert 'first_stage_exclusion' in json.dumps(w['fields'])
    rr=record(w);rr['decisions']['/first_stage_exclusion']['source_coverage']='REJECTED'
    r=dispatch.execute(s,'q1',**o,source_review=rr,research_protocol_selected=True)
    assert r['state']=='READING_RECHECK_REQUIRED' and not r['backend_called']
    sheet=prepare_recheck(s,'q1',**o)['feedback_worksheet']
    new=prepare_recheck(s,'q1',**o,feedback=feedback(sheet,path='/assignment/quota_profiles'))
    assert new['state']=='READY_TO_READ' and new['request_sha256']!=e['request_sha256']
    assert 'quota_profiles' in new['request']['system'] and 'first_stage_exclusion' in new['request']['system']
    assert 'PRIVATE_REASON_NOT_SENT' not in new['request']['user']
    body=json.JSONDecoder().raw_decode(new['request']['user'])[0]
    assert 'core_collaborators' in body['output_schema']['$defs']['Exposure']['properties']


def test_local_role_wire_compatibility_preserves_design_and_separate_d6_science():
    # Isolated projection compatibility; full role-review lifecycles are tested
    # in their existing suites. No model response is repaired by this helper.
    from cfm_id_llm import role_effect_reading as role,owned_effect_reading as owned,scoped_effect_reading as scoped
    for module in (role,owned,scoped):
        s,e,o,_=setup('D6','E3')
        raw=deepcopy(o['candidate']);raw['version']=module.VERSION;t=raw['target']
        t['evaluated']=t.pop('first');t['reference']=t.pop('second');t.pop('operation')
        if module is not role:
            raw['assignment']['definition_refs']=['study'];t['definition_refs']=['study']
            for arm in ('reference','evaluated'):t[arm]['definition_refs']=['study','exposure']
            for info in raw['information']:info['definition_refs']=['study']
        if module is scoped:
            t.pop('kind')
            for info in raw['information']:info.update(scope_status='DECLARED',scope_source_ids=info['source_ids'])
        reviewed=dict(kind='DIRECT_EFFECT',comparison_request=dict(quantity='INCREASE'),
            goal=dict(refs=list(raw['target']['source_ids'])))
        parsed=module.parse(e['bundle'],raw,binding=e['fact_binding_sha256'],reviewed_query=reviewed)
        for key in ('assignment','exposure','first_stage_exclusion'):
            assert parsed['facts'][key]==o['candidate'][key] or (
                # Canonical parsing adds declared null defaults and expands IDs.
                all(parsed['facts'][key][k]==v for k,v in o['candidate'][key].items() if k!='source_ids'))
        if module is not role:
            raw['assignment']['definition_refs']=[]
            with pytest.raises(ValueError,match='EXPLICIT_DEFINITION_DEPENDENCIES_REQUIRED'):
                module.parse(e['bundle'],raw,binding=e['fact_binding_sha256'],reviewed_query=reviewed)


def test_zero_support_stays_unavailable_without_partial_or_scientific_shortcut():
    s,e,o,_=setup('D2','E4');o['candidate']['assignment']['fixed_count']=0
    r=execute(s,o)
    assert r['state']=='UNSUPPORTED' and r['reason_code']=='ZERO_ARM_SUPPORT'
    assert not r['independent_replay'] and not r['partial_fallback_performed']


def test_newly_supported_exposure_still_requires_fresh_scientific_review():
    from examples.network_contrast_dispatch_reference import setup as bounded_setup
    s,e,o=bounded_setup('partial')
    o['candidate']['exposure']['kind']='ANY_TREATED_NEIGHBOR'
    r=dispatch.execute(s,'q1',**o,research_protocol_selected=True)
    assert r['state']=='REVIEW_REQUIRED' and not r['backend_called']


def test_recommended_public_entry_all_four_targets_keep_d6_e3_and_replay():
    from cfm_id import project,business_intake as intake,fact_source_review as source
    from cfm_id_llm.compact_reference_contract import catalog,request_context
    from cfm_id_llm.evidence_refs import build_catalog
    from examples.network_design_exposure_reference import material,a0_reference,fact_reference
    from tests_gateway.test_business_field_review import sheet,record,submit
    from tests_gateway.test_fact_source_review import record as source_record
    for family in ('effect','spillover','policy','contrast'):
        case,data=material('D6','E3',family);s=project.start(case)
        raw=a0_reference(case,data)
        originals={r['ref']:r['source_id'] for r in build_catalog(case)}
        current=catalog(case,s.a0_reference_contract)
        def remap(v):
            if isinstance(v,dict):
                return {k:list(dict.fromkeys(r['ref'] for ref in x for r in current if r['source_id']==originals[ref]))
                    if k=='refs' else remap(x) for k,x in v.items()}
            if isinstance(v,list):return [remap(x) for x in v]
            return v
        raw=remap(raw);raw['reference_context']=request_context(intake.prepare_request(s)['user_prompt'])
        q=raw['queries'][0];sem=q['semantics']
        # Same calendar week is ordinary study context, not a selected W stratum.
        sem['conditioning_context']='UNKNOWN'
        def goal_claim(value):return dict(state='STATED',value=value,refs=list(q['goal']['refs']))
        # Fixture follows the recommended target-first wire. No returned model
        # answer is migrated or repaired here.
        if family in ('effect','spillover'):
            for key in ('intervention','comparator','neighbor_exposure','policy_assignment'):sem.pop(key,None)
            first,second,shared=(('本店启用','本店未启用','核心合作店严格过半启用') if family=='effect' else
                ('核心合作店严格过半启用','核心合作店至多一半启用','本店不启用'))
            sem.update(first_arrangement=goal_claim(first),second_arrangement=goal_claim(second),neighbor_exposure=goal_claim(shared))
            q['comparison_order']=dict(operation='FIRST_MINUS_SECOND',refs=list(q['goal']['refs']))
        else:
            def policy_label(values):return '、'.join(n for n,v in zip(NODES,values) if v)+'启用，其余门店不启用'
            for key in ('intervention','comparator','policy_assignment'):sem.pop(key,None)
            sem['first_arrangement']=goal_claim(policy_label(data['first']))
            sem['second_arrangement']=goal_claim(policy_label(data['second'])) if family=='contrast' else 'NOT_APPLICABLE'
            q['comparison_order']=dict(operation='NOT_APPLICABLE' if family=='policy' else 'FIRST_MINUS_SECOND',refs=list(q['goal']['refs']))
        from cfm_id_llm.target_first_reading import COMMON_FIELDS
        raw['common']={k:raw['common'].get(k,'UNRESOLVED' if k=='assignment_family' else 'UNKNOWN') for k in COMMON_FIELDS}
        sem.update(outcome=deepcopy(raw['common']['outcome']),decision_constraints='UNKNOWN')
        sem.setdefault('neighbor_exposure','UNKNOWN')
        sem.setdefault('standardization_distribution','UNKNOWN')
        s=intake.receive_candidate(s,raw,request_sha256=s.request_sha256)
        review=submit(s,record(sheet(s)))['query_review']
        e=dispatch.prepare_reader(s,'q1',query_review=review)
        assert e['state']=='READY_TO_READ',e
        facts=fact_reference(e,data)
        if family in ('effect','spillover') and e.get('effect_fact_contract')=='network-scoped-effect-reading-1':
            t=facts['target'];t['evaluated']=t.pop('first');t['reference']=t.pop('second');t.pop('operation');t.pop('kind')
            facts['version']=e['effect_fact_contract'];facts['assignment']['definition_refs']=['study'];t['definition_refs']=['study']
            for arm in ('reference','evaluated'):t[arm]['definition_refs']=['study','exposure']
            for info in facts['information']:
                info.update(definition_refs=['study'],scope_status='DECLARED',scope_source_ids=list(info['source_ids']))
        Draft202012Validator(json.JSONDecoder().raw_decode(e['request']['user'])[0]['output_schema']).validate(facts)
        options=dict(query_review=review,candidate=facts,request_sha256=e['request_sha256'],source_review=source_record(source.prepare(e,facts)))
        p=dispatch.inspect_methods(s,'q1',**options)
        assert p['state']=='REVIEW_REQUIRED',(family,p.get('reason_code'))
        result=dispatch.execute(s,'q1',**options,**approval_records(p))
        assert result['state']=='POINT' and result['independent_replay'],family
