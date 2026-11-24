"""Build typed inputs from original policy materials and replay the selected native certificate."""
from . import bounded_backends
from . import research_spec_policy_adapters as policy_attributes
from .bounded_policy_contract import BoundedMeanInformation, VERSION as BOX_VERSION
from .bounded_count_contract import CountMeanInformation, POLICY_VERSION as COUNT_VERSION
from .bounded_finite_contract import FiniteMeanInformation, POLICY_VERSION as FINITE_VERSION
from .bounded_mean_formula import mathematical_claim
from cfm_id_bridge.scientific_binding import sha


def box(m, target):
    from pfn_pipeline.identification_business import FixedPolicyInquiryV21
    from pfn_pipeline.identification_policy_r2 import (declare_policy_signature, admit_mean_signature_sufficiency,
                                                        declare_signature_population_source)
    from pfn_pipeline._internal.identification.schemas import Assumption
    question = policy_attributes.from_materials(m, target)
    nodes = question.study.node_order
    st = policy_attributes.native_study(question, network_id='network_'+sha([nodes,m['edges']]),
        edges=m['edges'], observation_regime='experimental',
        assignment_design=m['design'], protocol_provenance=m['design_source']['quote'],
        network_provenance=m['graph']['quote'], graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    sig = declare_policy_signature(st, grouping=m['grouping'])
    spans = {row['code']:row['quote'] for row in m['conditions']}
    def premise(name, evidence):
        # Only the conditional synthetic research calculation uses these objects.
        # Sending the result requires the separate bound review at the intake.
        return Assumption(name=name, source='demo_specification', confirmed=True, status='ADMITTED', evidence=[evidence])
    premises = tuple(premise(k,spans[k]) for k in ('known_assignment_law','full_vector_randomization','consistency',
                     'finite_conditional_first_moments')) + (premise('fixed_pretreatment_network',spans['fixed_network']),)
    suff = admit_mean_signature_sufficiency(st,sig,covered_nodes=nodes,assumption=premise('mean_signature_sufficiency',spans['signature']))
    src = declare_signature_population_source(st,sig,source_id=m['information']['source_id'],operator='NODE_SIGNATURE_MEANS',
        outcome_nodes=nodes,signature_cells=tuple((v['node'],v['own'],v['exposure']) for v in m['values']),
        admission='ADMITTED',availability='EXACT_POPULATION_VALUE',provenance=m['information']['quote'])
    cls, version = FiniteMeanInformation, FINITE_VERSION
    if m['design']['kind']=='complete_randomization_binary_v1':
        if m['grouping']=='strict_majority_ties_low':
            cls, version = BoundedMeanInformation, BOX_VERSION
        elif m['grouping']=='exact_treated_neighbor_count':
            cls, version = CountMeanInformation, COUNT_VERSION
    inquiries, information = {}, {}
    for side in ('first', 'second'):
        if m[side] is None:
            continue
        policy = policy_attributes.native_target(question, st, side=side, authority='TRUSTED_FIXTURE')
        inquiry = FixedPolicyInquiryV21(st,policy,premises,r2_signature=sig,r2_sufficiency=suff,r2_sources=(src,))
        inquiries[side] = inquiry
        information[side] = cls(version=version,inquiry_sha256=sha(inquiry),source_id=src.source_id,source_sha256=sha(src),
            information_scope='EXACT_LISTED_SIGNATURE_MEANS_ONLY',model_scope='SIGNATURE_MEANS_AND_NODE_BOUNDS_ONLY',
            availability='EXACT_POPULATION_VALUE',values=m['values'],bounds=m['bounds'],bounds_kind='CONDITIONAL_MEAN',
            bounds_scope='ALL_BINARY_ASSIGNMENTS_CONDITIONAL_ON_STUDY_CONTEXT',outcome_definition=m['outcome'],
            outcome_unit='0/1指标',outcome_period=m['period'],a4_provenance=m['information']['quote'],
            bounds_provenance=m['bounds_source']['quote'])
    if m['second'] is None:
        backend = bounded_backends.policy_backend(information['first'])
        args = dict(inquiry=inquiries['first'], information=information['first'])
    else:
        backend = bounded_backends.contrast_backend(information)
        args = dict(inquiries=inquiries, information=information)
    cert = backend.solve(**args)
    if not backend.replay(cert,**args):
        raise ValueError('INDEPENDENT_BOUNDS_REPLAY_FAILED')
    return mathematical_claim(cert,target),cert


def ordered(m, target):
    from . import mean_order_contract as contract, mean_order_solver, mean_order_verify
    question = policy_attributes.from_materials(m, target)
    if question.operation != 'FIRST_MINUS_SECOND':
        raise ValueError('MEAN_ORDER_COMPARISON_REQUIRED')
    s = question.study
    problem = contract.MeanOrderProblem(version=contract.VERSION,model_scope=contract.MODEL,
        node_order=list(s.node_order),undirected_edges=m['edges'],graph_scope='KNOWN_FIXED_PRETREATMENT_SIMPLE_UNDIRECTED',
        design='D2_UNIFORM_FIXED_QUOTA',quota=m['design']['m'],exposure='E1_STRICT_MAJORITY_TIES_LOW_ISOLATED_ZERO',
        context=s.context_reference,treatment_definition=s.treatment_definition,outcome_definition=s.outcome_definition,outcome_kind=s.outcome_domain,
        outcome_unit='0/1指标',outcome_period=m['period'],order_direction='NONDECREASING_NUMERIC_OUTCOME_MEAN',
        order_scope=contract.SCOPE,node_orders=[dict(node=n,mode='BOTH') for n in m['nodes']],
        randomization_claim='WHOLE_ASSIGNMENT_INDEPENDENT_OF_ALL_POTENTIAL_OUTCOMES_GIVEN_CONTEXT',
        consistency_claim='OBSERVED_OUTCOME_EQUALS_ASSIGNED_POTENTIAL_OUTCOME',moments_claim='FINITE_FIRST_MOMENTS',
        mean_sufficiency_scope=contract.SCOPE,mean_sufficiency_claim='NODE_OWN_AND_E1_SIGNATURE_DETERMINES_CONDITIONAL_MEAN',
        information_scope='EXACT_LISTED_SIGNATURE_MEANS_ONLY',availability='EXACT_POPULATION_VALUE',
        values=m['values'],a4_source=m['information']['source_id'],a4_provenance=m['information']['quote'],
        bounds=m['bounds'],bounds_kind='CONDITIONAL_MEAN',bounds_scope=contract.SCOPE,bounds_provenance=m['bounds_source']['quote'],
        first=list(question.first.assignment),second=list(question.second.assignment),weights=list(question.evaluation.unit_weights),
        operation=question.operation,scientific_provenance=m['protocol'])
    cert = mean_order_solver.solve(problem)
    if not mean_order_verify.replay(cert,problem=problem):
        raise ValueError('INDEPENDENT_ORDER_REPLAY_FAILED')
    claim = dict(kind=cert['status'], target=target)
    if cert['status'] != 'INCOMPATIBLE':
        claim.update(representation='EXACT_IDENTIFIED_INTERVAL', interval=[cert['lower'],cert['upper']], sharp=cert['sharp'],
                     bound_formula=dict(objective='FIRST_MINUS_SECOND',method='FINITE_MEAN_ORDER_PRIMAL_DUAL',
                                        certificate_sha256=cert['certificate_sha256']))
    return claim,cert
