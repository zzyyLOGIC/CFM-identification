"""Project a source-bound policy to the existing estimation operators and replay it at intake."""
from copy import deepcopy
from fractions import Fraction
from math import comb

from cfm_id_bridge.scientific_binding import sha
from cfm_id_llm.compact_study import digest
from . import bounded_policy_solver, bounded_policy_verify
from .bounded_policy_contract import BoundedMeanInformation, VERSION as BOUNDS_VERSION
from .classic_query_exchange import project_handoff, require
from .network_policy_materials import read

VERSION='source-policy-registration/1'


def mixture(materials, target):
    from pfn_pipeline._internal.identification.randomized_arm_family.assignment import AssignmentSpec
    from pfn_pipeline._internal.identification.schemas import CompleteRandomizationDesignV1, NetworkExposureSpec
    nodes=materials['nodes']
    # The quota probability depends only on roster membership. No edges are inferred or exposed as study facts.
    coordinates=NetworkExposureSpec(network_id='roster_'+digest(nodes),node_ids=nodes,undirected_edges=[])
    design=AssignmentSpec(CompleteRandomizationDesignV1(m=materials['quota']))
    policies=[];support=[]
    for weight,z in materials['policies']:
        mass=design.full_assignment_probability(coordinates,dict(zip(nodes,z)))
        if not mass or mass!=Fraction(1,comb(len(nodes),materials['quota'])):
            return None
        policies.append(dict(assignment=z,weight=weight))
        support.append(dict(assignment=z,policy_probability=weight,experimental_assignment_probability=str(mass)))
    target.update(kind='FINITE_POLICY_MEAN',policies=policies)
    formula='Σ_z π(z) Σ_i w_i E[Y_i | Z=z]，名单取原设计的条件均值，各单位等权。'
    claim=dict(kind='POINT',representation='FINITE_POLICY_OBSERVED_FUNCTIONAL',target=target,
               target_fingerprint=digest(target),expression=formula)
    cert=dict(status='POINT',policy_support=support,target_fingerprint=digest(target),identified_functional=formula)
    return claim,cert


def bounded(materials,target,*,externally_reviewed=False):
    from pfn_pipeline.network_inquiry_shadow import declare_network_study, fixed_policy_target_from_context
    from pfn_pipeline.identification_business import FixedPolicyInquiryV21
    from pfn_pipeline.identification_policy_r2 import (declare_policy_signature,
        admit_mean_signature_sufficiency,declare_signature_population_source)
    from pfn_pipeline._internal.identification.schemas import Assumption
    from .bounded_policy_contract import MAX_N
    nodes=tuple(materials['nodes'])
    if len(nodes)>MAX_N:
        return None
    spans={s['code']:s['quote'] for s in materials['conditions']}
    st=declare_network_study(network_id='network_'+digest([nodes,materials['edges']]),node_order=nodes,
        undirected_edges=tuple(map(tuple,materials['edges'])),treatment_variable=materials['treatment'],
        outcome_variable=materials['outcome'],outcome_kind='binary',context_reference=materials['period'],
        observation_regime='experimental',assignment_design=dict(kind='complete_randomization_binary_v1',m=materials['quota']),
        protocol_provenance=materials['protocol'],network_provenance=materials['graph']['quote'],graph_timing_claim='DECLARED_PRETREATMENT_FIXED')
    # This is a conditional calculation from stated materials. The permission to send it is checked separately.
    z=(1,)*len(nodes)
    t=fixed_policy_target_from_context(st,z,unit_weights=tuple(target['unit_weights']),
        authority='HUMAN_CONFIRMED' if externally_reviewed else 'TRUSTED_FIXTURE')
    sig=declare_policy_signature(st,grouping='strict_majority_ties_low')
    def premise(name,quote):
        return Assumption(name=name,source='human_confirmation' if externally_reviewed else 'demo_specification',
                          confirmed=True,status='ADMITTED',evidence=[quote])
    premises=tuple(premise(code,quote) for code,quote in [
        ('known_assignment_law',materials['protocol']),('fixed_pretreatment_network',materials['graph']['quote']),
        *[(c,spans[c]) for c in ('full_vector_randomization','consistency','finite_conditional_first_moments')]])
    suff=admit_mean_signature_sufficiency(st,sig,covered_nodes=nodes,assumption=premise('mean_signature_sufficiency',spans['signature']))
    info=materials['information'];values=materials['values']
    src=declare_signature_population_source(st,sig,source_id=info['source_id'],operator='NODE_SIGNATURE_MEANS',outcome_nodes=nodes,
        signature_cells=tuple((v['node'],v['own'],v['exposure']) for v in values),
        admission='ADMITTED',availability='EXACT_POPULATION_VALUE',provenance=info['quote'])
    inquiry=FixedPolicyInquiryV21(st,t,premises,r2_signature=sig,r2_sufficiency=suff,r2_sources=(src,))
    model=BoundedMeanInformation(version=BOUNDS_VERSION,inquiry_sha256=sha(inquiry),source_id=src.source_id,source_sha256=sha(src),
        information_scope='EXACT_LISTED_SIGNATURE_MEANS_ONLY',model_scope='SIGNATURE_MEANS_AND_NODE_BOUNDS_ONLY',
        availability='EXACT_POPULATION_VALUE',values=values,bounds=[dict(node=n,lower='0',upper='1') for n in nodes],
        bounds_kind='ALMOST_SURE_OUTCOME',bounds_scope='ALL_BINARY_ASSIGNMENTS_CONDITIONAL_ON_STUDY_CONTEXT',
        outcome_definition=materials['outcome'],outcome_unit='0或1',outcome_period=materials['period'],
        a4_provenance=materials['protocol'],bounds_provenance=spans['box'])
    cert=bounded_policy_solver.solve(inquiry,model)
    if cert['status']!='PARTIAL' or not bounded_policy_verify.replay(cert,inquiry=inquiry,information=model):
        return None
    target.update(kind='FIXED_POLICY_MEAN',assignment=list(z))
    return dict(kind='PARTIAL',representation='EXACT_IDENTIFIED_INTERVAL',target=target,interval=[cert['lower'],cert['upper']],
                sharp=True,bound_formula=cert['bound_terms']),cert


def derive(case,*,externally_reviewed=False):
    m=read(case)
    if not m:
        return None
    m['protocol']=case['sources'][0]['text']
    nodes=m['nodes']
    target=dict(node_order=nodes,population=nodes,unit_weights=[str(Fraction(1,len(nodes)))]*len(nodes),
                treatment=m['treatment'],outcome=m['outcome'],context=m['period'],quantity='level',scope='whole')
    if m['policy_period']:
        target['policy_period']=m['policy_period']
    value=mixture(m,target) if m['operator']=='FINITE_POLICY_MEAN' else bounded(m,target,externally_reviewed=externally_reviewed)
    if not value:
        return None
    claim,certificate=value
    return dict(method=m['operator'],claim=claim,certificate=certificate,materials=m,case_sha256=digest(case))


def apply(case,draft,report,review):
    from .uploaded_network_contrast import check_review
    from .direct_verification import answer_items
    if report.get('proof') or len(answer_items(draft))!=1:
        return
    try:
        evidence=derive(case)
    except (ArithmeticError,ValueError,KeyError,TypeError):
        evidence=None
    if not evidence:
        return
    h=project_handoff(evidence)
    claim=evidence['claim'];cert=evidence['certificate'];m=evidence['materials']
    sheet=dict(kind='source_policy',case_id=case['case_id'],case_sha256=digest(case),draft_sha256=report['draft_sha256'],
               items=m['conditions'])
    sheet['binding']=digest([sheet.copy(),evidence,h])
    report['condition_review']=sheet
    if review is not None:
        check_review(sheet,review)
        report['review_record']=deepcopy(review)
    allowed=bool(review and all(v=='ADOPTED' for v in review['decisions'].values()))
    if claim['kind']=='POINT':
        terms='、'.join(f"{p['assignment']} 占 {p['policy_probability']}（试行支持 {p['experimental_assignment_probability']}）" for p in cert['policy_support'])
        formula=claim['expression']+' '+terms
        reason='完整名单的随机分配与一致性识别各名单结果均值，再按政策概率和单位权重求和。'
        value=None
    else:
        value=claim['interval']
        terms='，'.join(f"{r['coefficient']}×{r['cell'][0]}[{r['lower']},{r['upper']}]" for r in cert['bound_terms'])
        formula=f"逐项加权 {terms}，可达锐界 [{value[0]}, {value[1]}]。"
        mass={tuple(r['cell']):r['support'] for r in cert['cells']}
        supports='、'.join(t['cell'][0]+' '+mass[tuple(t['cell'])] for t in cert['bound_terms'])
        reason=f"按每次随机抽 {m['quota']} 个及严格过半的暴露规则，目标事件的联合概率分别是{supports}。没有支持的单元格保留原界。令自由均值同时取下端或上端，可实现两个端点。"
    answer=dict(status=claim['kind'],target=claim['target'],value=value,functional=formula,
        assumptions=[dict(statement=v['label'],quote=v['quote'],source=v['source_id']) for v in m['conditions']],
        source_facts=m['facts'],reason=reason,estimate_handoff=h)
    report.pop('parts',None)
    report.update(proof=dict(binder=VERSION,evidence=evidence),conditional_answer=answer,effective_answer=deepcopy(answer),
        clarification_questions=[],estimation_handoff_allowed=allowed,scientific_approval=bool(allowed and review['authority']=='EXTERNAL_RESEARCH_REVIEW'),
        decision='CONDITIONAL_RESULT' if allowed else 'PREMISES_REQUIRED')
    if not allowed:
        report['effective_answer'].update(status='NEEDS_INPUT',value=None,estimate_handoff=dict(mode='STOP',queries=[]),
            reason='原文条件下的结果见条件答复。交接前须确认所列前提。')
    report['checks'].append(dict(code='REPLAYED_SOURCE_POLICY',state='CHECKED',detail='已从业务原文重建完整名单、权重或暴露均值约束，按原设计复算估计交接。'))


def packet(case,report):
    e=report['proof']['evidence']
    return dict(version=VERSION,case_id=case['case_id'],source_case=deepcopy(case),
                release_scope=report['review_record']['authority'],review=report['review_record'],condition_review=report['condition_review'],
                production_admission=False,evidence=e,estimate_handoff=project_handoff(e))


def check_packet(run_id,packet):
    from .uploaded_network_contrast import check_review
    case=packet['source_case'];sheet=packet['condition_review'];review=packet['review']
    require(packet['version']==VERSION and packet.get('production_admission') is False and case['case_id']==run_id==packet['case_id']==sheet['case_id']
            and sheet['kind']=='source_policy' and digest(case)==sheet['case_sha256'],'POLICY_RUN_BINDING')
    e=derive(case)
    require(e is not None and digest(e)==digest(packet['evidence']),'POLICY_SOURCE_REPLAY_FAILED')
    h=project_handoff(e)
    require(digest(h)==digest(packet['estimate_handoff']) and sheet['items']==e['materials']['conditions'],'POLICY_QUERY_CHANGED')
    require(sheet['binding']==digest([{k:v for k,v in sheet.items() if k!='binding'},e,h]),'POLICY_REVIEW_BINDING')
    check_review(sheet,review)
    require(review['authority']==packet['release_scope'] and set(review['decisions'].values())=={'ADOPTED'},'POLICY_REVIEW_REQUIRED')
    if review['authority']=='EXTERNAL_RESEARCH_REVIEW':
        confirmed=derive(case,externally_reviewed=True)
        require(confirmed is not None and project_handoff(confirmed)==h,'POLICY_REVIEWED_PROJECTION_CHANGED')
    return dict(state='RECEIVED',run_id=run_id,mode=h['mode'],binding=sheet['binding'],query_count=len(h['queries']),
                query_sha256=digest(h),interval=[h['lower'],h['upper']] if h['mode']=='ESTIMATE_BOUNDS' else None,
                release_scope=review['authority'],data_review='PENDING',estimator_executed=False)
