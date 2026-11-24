"""Internal dimensions, source ownership and legacy compatibility boundaries."""
from dataclasses import replace
import pytest

from cfm_id.research_spec_catalog import FACET_DIMENSIONS, METHOD_NAVIGATION, validate_catalog
from cfm_id.research_spec_model import build_internal_study, VERSION
from cfm_id.research_spec_view import build_view


def model(raw, contract='network-facts'):
    return build_internal_study(build_view(raw,contract=contract))


def meanings(component,key):
    return {d.value for d in component.property(key).definitions}


def test_design_classification_is_orthogonal_with_legacy_differences_retained():
    m3=model({'assignment':{'kind':'TWO_GROUP_FIXED_QUOTA','groups':[['a'],['b']],'treated_quotas':[1,0]}})
    m5=model({'assignment':{'kind':'MULTI_GROUP_FIXED_QUOTA','groups':[['a'],['b'],['c']],'treated_quotas':[1,0,0]}})
    d3,d5=m3.for_facet('assignment')[0],m5.for_facet('assignment')[0]
    assert meanings(d3,'joint_law')==meanings(d5,'joint_law')=={'product_uniform_within_strata'}
    assert meanings(d3,'stratification')=={'exactly_two'}
    assert meanings(d5,'stratification')=={'at_least_three'}
    assert m3.to_legacy()['assignment']['kind']=='TWO_GROUP_FIXED_QUOTA'


def test_exposure_reference_and_threshold_vary_independently():
    e1=model({'exposure':{'kind':'STRICT_MAJORITY_TIES_LOW'}}).for_facet('exposure')[0]
    e3=model({'exposure':{'kind':'PRETREATMENT_CORE_COLLABORATOR_MAJORITY','core_collaborators':{'a':['b']}}}).for_facet('exposure')[0]
    assert meanings(e1,'labels')==meanings(e3,'labels')=={'strict_majority_binary'}
    assert meanings(e1,'reference_set')=={'all_neighbors'}
    assert meanings(e3,'reference_set')=={'pretreatment_core_neighbors'}
    assert e3.property('reference_set').source_refs==('/exposure/core_collaborators/a/0',)


def test_target_function_operation_population_weights_and_label_are_separate():
    raw={'target':{'kind':'FIXED_POLICY_CONTRAST','operation':'FIRST_MINUS_SECOND',
                   'first':{'policy_assignment':[1,1]},'second':{'policy_assignment':[0,0]},
                   'population':['a'],'weights':['1'],'context':'下周，其他条件尚未决定'}}
    m=model(raw);t=m.for_facet('target')[0]
    assert meanings(t,'endpoint_function')=={'mean'}
    assert t.property('operation').source_refs==('/target/operation',)
    assert not t.property('operation').definitions  # the source operation owns direction
    assert t.property('population').source_refs==('/target/population/0',)
    assert t.property('aggregation').source_refs==('/target/weights/0',)
    assert t.property('time_context').state=='RECORDED_EXPRESSION'
    assert m.to_legacy()==raw


def test_multiple_questions_have_independent_owners():
    raw={'answers':[{'target':{'quantity':'mean','population':['a']}},
                    {'target':{'quantity':'distribution','population':['b']}}]}
    m=model(raw,'direct')
    assert [c.source_root for c in m.for_facet('target')]==['/answers/0/target','/answers/1/target']
    assert m.to_legacy()==raw


def test_unit_network_and_variable_graph_coexist_without_implied_solver():
    raw={'network':{'nodes':['a','b'],'edges':[['a','b']]},
         'graph':{'nodes':['X','Y'],'directed':[['X','Y']],'bidirected':[]}}
    m=model(raw,'compact')
    net,graph=m.for_facet('structure')
    assert net.property('unit_network').source_refs==('/network/edges/0/0','/network/edges/0/1')
    assert graph.property('variable_graph').source_refs==('/graph/directed/0/0','/graph/directed/0/1','/graph/bidirected')
    assert not m.as_dict()['executable'] and m.to_legacy()==raw


def test_information_level_coverage_and_closure_are_not_interchangeable():
    raw={'information':{'operator':'CONDITIONAL_MEAN','availability':'FINITE_RECORDS',
                        'outcome_nodes':['a'],'data_description':'只访问了两家店'},
         'bounded_model':{'listed_means_are_complete_information':False}}
    m=model(raw);info=m.for_facet('information')[0]
    assert info.property('level').source_refs==('/information/availability',)
    assert info.property('coverage').source_refs==('/information/outcome_nodes/0',)
    assert info.property('acquisition').source_refs==('/information/data_description',)
    assert m.to_legacy()==raw
    assert all('FINITE_RECORDS' not in [d.value for d in p.definitions] for p in info.properties)


@pytest.mark.parametrize('state',['NOT_ADOPTED','UNDECIDED','ADOPTED','CONFLICTING'])
def test_scientific_adoption_is_not_proposition_polarity_or_approval(state):
    raw={'assumptions':{'consistency':{'value':True,'status':state,'source_ids':['s1']}}}
    m=model(raw);a=m.for_facet('assumptions')[0]
    assert a.property('proposition').source_refs==('/assumptions/consistency/value',)
    assert a.property('adoption').source_refs==('/assumptions/consistency/status',)
    assert a.property('polarity').state==a.property('review').state=='NOT_SEPARATELY_RECORDED'
    assert a.property('evidence').source_refs==('/assumptions/consistency/source_ids/0',)
    assert a.role_tags==('observation_intervention_bridge',)
    assert not m.as_dict()['scientific_approval'] and m.to_legacy()==raw


def test_no_hidden_execute_of_changed_internal_attributes():
    m=model({'assignment':{'kind':'UNIFORM_FIXED_QUOTA','fixed_count':1}})
    c=m.for_facet('assignment')[0]
    p=c.property('joint_law')
    changed=replace(p,definitions=(replace(p.definitions[0],value='independent_bernoulli'),))
    c2=replace(c,properties=tuple(changed if x.key==p.key else x for x in c.properties))
    with pytest.raises(ValueError,match='INTERNAL_MODEL_CHANGED'):
        replace(m,components=(c2,)).to_legacy()
    with pytest.raises(ValueError,match='INTERNAL_MODEL_CHANGED'):
        replace(m,version='future-version').to_legacy()


def test_d8_base_law_kept_separate_from_acceptance_conditioned_law():
    raw={'assignment':{'kind':'rerandomized_balanced_binary_v1','base_design':{
        'kind':'unequal_probability_fixed_quota_binary_v1','fixed_count':1,'unit_weights':{'a':'1','b':'2'}},
        'balance_rule':{'covariates':{'a':[0],'b':[1]},'max_abs_mean_difference':'1'}}}
    m=model(raw);outer,base=m.for_facet('assignment')
    assert meanings(outer,'joint_law')=={'base_law_conditioned_on_acceptance'}
    assert meanings(base,'joint_law')=={'explicit_or_product_weight_fixed_quota'}
    assert m.as_dict()['facets']['assignment'][0]['nested_components']==['/assignment/base_design']
    assert m.to_legacy()==raw


def test_unknown_subfields_remain_explicit_and_have_one_authoritative_copy():
    raw={'target':{'kind':'CATE','unknown_future_field':['text']},'extra':{'kind':'R1a'}}
    m=model(raw);t=m.for_facet('target')[0]
    assert '/target/unknown_future_field/0' in t.unsplit_refs
    assert not t.property('endpoint_function').definitions
    slots=m.as_dict()['source']['slots']
    assert len({s['pointer'] for s in slots})==len(slots)
    assert all('value' not in p for c in m.as_dict()['facets']['target'] for p in c['properties'])
    assert m.resolve('/target/unknown_future_field/0')=='text' and m.to_legacy()==raw


def test_catalog_methods_do_not_become_study_categories():
    assert validate_catalog()
    assert set(FACET_DIMENSIONS)=={'target','assignment','exposure','structure','information','assumptions'}
    assert set(METHOD_NAVIGATION)=={'R1a','R1b','R2','R3'}
    assert VERSION=='internal-study-model/1'


def test_mixture_component_designs_keep_their_separate_study_ownership():
    raw={'format':'causal-id.math-request/1','question':'政策混合','operation':'business',
         'problem':{'kind':'finite_policy','inquiry':{'policy_probabilities':['1/2','1/2'],
           'components':[{'study':{'assignment_design_json':'{"kind":"complete_randomization_binary_v1","m":1}'}},
                         {'study':{'assignment_design_json':'{"kind":"complete_randomization_binary_v1","m":2}'}}]}}}
    m=model(raw,'math-request')
    owners=[c.source_root for c in m.for_facet('assignment')]
    assert owners==['/problem/inquiry/components/0/study','/problem/inquiry/components/1/study']
    assert all(meanings(c,'joint_law')=={'uniform_fixed_quota'} for c in m.for_facet('assignment'))
    assert m.to_legacy()==raw


def test_flat_order_direction_and_bounds_keep_separate_scientific_declarations():
    raw={'bounds':[{'lower':'0','upper':'1'}],'bounds_scope':'ALL_ASSIGNMENTS',
         'node_orders':[['a','b']],'order_direction':'NONDECREASING','order_scope':'ORIGINAL_SCOPE'}
    m=model(raw,'mean-order')
    bounds,order=m.for_facet('assumptions')
    assert bounds.source_root=='/bounds' and order.source_root=='/node_orders'
    assert bounds.property('scope').source_refs==('/bounds_scope',)
    assert order.property('scope').source_refs==('/order_scope',)
    assert order.property('adoption').state=='NOT_SEPARATELY_RECORDED'
    assert m.to_legacy()==raw
