"""Previously shared study inputs, exclusively for reviewed synthetic ID tests."""
from pfn_pipeline import make_heterogeneous_bernoulli_arm_task, make_complete_randomization_arm_task
from pfn_pipeline._internal.identification.schemas import Assumption, NetworkExposureSpec
from pfn_pipeline._internal.identification.randomized_network_arm import REQUIRED
from pfn_pipeline.network_inquiry_shadow import declare_network_study
from fixed_network_fixture import DEFAULT_GRAPH, load_graph


def legacy_task(er300=False, fixed_quota=False):
    if er300:
        import numpy as np
        adj=load_graph(DEFAULT_GRAPH)
        nodes=tuple('node-'+str(i) for i in range(adj.shape[0]))
        edges=[(nodes[int(i)],nodes[int(j)]) for i,j in zip(*np.where(np.triu(adj,1)==1))]
        net=NetworkExposureSpec(network_id='a4-shadow-shared-ER300', node_ids=list(nodes),undirected_edges=edges)
    else:
        net=NetworkExposureSpec(network_id='route-v15-toy3',node_ids=['0','1','2'],
                                undirected_edges=[('0','1'),('0','2')])
    kw=dict(node_id=net.node_ids[0],own_treatment_value=1,exposure_value=1,
            source='reviewed experimental protocol', evidence='admitted randomized design',
            admitted=True,synthetic=True,query_authority='TRUSTED_FIXTURE')
    if fixed_quota:
        return make_complete_randomization_arm_task(net,m=2,**kw)
    return make_heterogeneous_bernoulli_arm_task(net,propensities={n:'1/2' for n in net.node_ids},**kw)


def network(er300=False):
    if not er300:
        return 'route-v15-toy3',('0','1','2'),(('0','1'),('0','2'))
    import numpy as np
    adjacency=load_graph(DEFAULT_GRAPH)
    ids=tuple(f'node-{i}' for i in range(adjacency.shape[0]))
    edges=tuple((ids[int(i)],ids[int(j)]) for i,j in zip(*np.where(np.triu(adjacency,1)==1)))
    return 'a4-shadow-shared-ER300',ids,edges


def make_study(*,er300=False,observational=False):
    name,nodes,edges=network(er300)
    return declare_network_study(
        network_id=name,node_order=nodes,undirected_edges=edges,
        treatment_variable='treatment',outcome_variable='outcome',outcome_kind='continuous',
        context_reference='W',
        observation_regime='observational' if observational else 'experimental',
        assignment_design=None if observational else {
            'kind':'heterogeneous_bernoulli_binary_v1',
            'propensities':{n:'1/2' for n in nodes}},
        protocol_provenance=('research fixture: observational design not certified'
                             if observational else 'reviewed synthetic iid Bernoulli(.5) protocol fixture'),
        network_provenance='fixed graph fixture for testing, not a factual certification',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')


def assumptions():
    return tuple(Assumption(name=name,source='demo_specification',confirmed=True,
                            evidence=['reviewed synthetic fixture']) for name in REQUIRED)


def r2_assumptions():
    return tuple(Assumption(name=n,source='demo_specification',confirmed=True,
            evidence=['independently reviewed synthetic experimental protocol']) for n in REQUIRED)


def star_study():
    nodes=('hub','leaf1','leaf2','leaf3','leaf4')
    return declare_network_study(
        network_id='r2-star5-offsupport',node_order=nodes,
        undirected_edges=tuple(('hub',n) for n in nodes[1:]),
        treatment_variable='AI',outcome_variable='sales',outcome_kind='continuous',
        context_reference='W',observation_regime='experimental',
        assignment_design={'kind':'complete_randomization_binary_v1','m':4},
        protocol_provenance='hypothetical fixed-quota toy fixture, NOT an actual experiment',
        network_provenance='declared fixed star network',
        graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
