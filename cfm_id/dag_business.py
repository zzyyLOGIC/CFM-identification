"""Business candidate -> explicit reading/science reviews -> existing DAG backend.

No causal edge, missing scientific premise or approval is supplied by this bridge.
"""
from copy import deepcopy
from typing import Literal
from pydantic import Field
from cfm_id_llm.dag_reading import parse,public_bundle,documents,StrictRecord
from .source_locations import build_catalog
from cfm_id_bridge.scientific_binding import sha
from .dag_backdoor_contract import BackdoorProblem,BackdoorReview
from .dag_backdoor import prepare as math_prepare
from .research_route_workflow import run_route
from .research_route_adapters import DagBackdoorRoute
from . import dag_methods

READING_DECISIONS=('target_meaning','variable_measurements_and_roles','relations_and_omissions','source_entailment_and_scope')
CLASSICAL_ROUTE=dag_methods.BACKDOOR
ADJUSTMENT_ROUTE=dag_methods.ADJUSTMENT
FRONTDOOR_ROUTE=dag_methods.FRONTDOOR
ROUTE_IDS=dag_methods.METHOD_IDS
FRONTDOOR_READING_DECISIONS=(*READING_DECISIONS,'requested_identification_roles')
SCOPE_QUESTIONS={
 'static_acyclic':'本次研究是否采用固定的、无时间反馈的有向无环因果模型？',
 'graph_complete':'所列直接因果关系是否完整？没有画出的边能否排除？',
 'latent_causes_accounted':'是否还有未列出的共同原因？如有，请明确其变量及影响关系。',
 'independent_errors':'给定图中变量后，是否采用各结构方程噪声相互独立的模型？',
 'perfect_intervention':'所问干预是否仅设定处理变量、保持其他结构机制不变？'}


class DagReadingReview(StrictRecord):
    version:Literal['dag-reading-review-1']
    bundle_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    candidate_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    problem_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    reviewer:str=Field(min_length=3)
    evidence:str=Field(min_length=12)
    authority:Literal['EXTERNAL_RESEARCH_REVIEW','SYNTHETIC_TEST']
    decisions:dict[str,Literal['ACCEPTED','PENDING','REJECTED']]


class DagFrontdoorReadingReview(DagReadingReview):
    version:Literal['dag-frontdoor-reading-review-2']


def reading_contract(route_id):
    """Route-specific reading version and review; old requests stay byte-identical."""
    route_contract(route_id)
    if route_id==FRONTDOOR_ROUTE:
        from cfm_id_llm.dag_frontdoor_reading import make_request,parse as parser
        return make_request,parser,DagFrontdoorReadingReview,FRONTDOOR_READING_DECISIONS,'dag-frontdoor-reading-review-2'
    from cfm_id_llm.dag_reading import make_request
    return make_request,parse,DagReadingReview,READING_DECISIONS,'dag-reading-review-1'


def route_contract(route_id):
    """Caller-selected route only; never infer a theorem from candidate wording."""
    return dag_methods.resolve(route_id).legacy_contract()


def _project(bundle,wire,c,problem_type,version):
    """Syntactic construction of a proposal after required declarations exist."""
    sources=build_catalog(documents(bundle))
    info=c.information
    law_evidence=[sources[i] for i in info.source_ids]
    selection=(dict(frontdoor_variable=c.frontdoor_choice.variable) if version=='dag-frontdoor-1'
               else dict(adjustment=c.adjustment))
    return problem_type.model_validate(dict(version=version,
        model='RECURSIVE_SCM_EXPLICIT_LATENTS_INDEPENDENT_ERRORS',variable_domain='BINARY',
        nodes=[v.name for v in c.variables],observed=[v.name for v in c.variables if v.observation=='OBSERVED'],
        latent=[v.name for v in c.variables if v.observation=='LATENT'],
        edges=[[e.cause,e.effect] for e in c.relations],graph_status='DECLARED',
        graph_source='Source-bound unapproved reading candidate '+sha(wire),materials_sha256=sha(bundle),
        context=c.target.context,treatment=c.target.treatment,outcome=c.target.outcome,**selection,
        information=dict(source_id='dag_law_'+sha(law_evidence),source_sha256=sha(law_evidence),
            variables=info.variables,availability='SYMBOLIC_POPULATION_LAW',strictly_positive_joint=True,
            provenance='Symbolic population-law declaration; original locations: '+','.join(info.source_ids)),
        additional_restrictions=[]))


def inspect_candidate(bundle,wire,*,route_id=CLASSICAL_ROUTE):
    out=dict(state='CHECK_BLOCKED',reason_code=None,backend_called=False,independent_replay=False,
        mathematical_claim=None,certificate=None,production_admission=False,estimation_handoff_allowed=False,
        clarification_questions=[],proposed_problem=None,reading_worksheet=None,science_worksheet=None,route_id=route_id)
    try:
        problem_type,_,prepare_route,_,version=route_contract(route_id)
        _,parser,_,reading_decisions,reading_version=reading_contract(route_id)
        b=public_bundle(bundle);c=parser(b,wire)
        out.update(bundle_sha256=sha(b),candidate_sha256=sha(wire),wire_candidate=deepcopy(wire),
            source_catalog=build_catalog(documents(b)),semantic_correctness_automatically_proved=False)
        missing=[];unsupported=[]
        if c.target.kind=='OTHER':unsupported.append('TARGET_OUTSIDE_INTERVENTIONAL_DISTRIBUTION')
        elif c.target.kind=='UNKNOWN':missing.append('请明确是干预后的结果分布，还是其他目标。')
        if c.target.treatment is None or c.target.outcome is None:missing.append('请明确要干预的变量及所问的结果变量。')
        if not c.target.context or not c.target.context.strip():missing.append('请明确研究对象、时期和背景。')
        if len(c.variables)<2:missing.append('请列出本研究中的因果变量及其观测方式。')
        for v in c.variables:
            if v.observation=='UNKNOWN' or v.domain=='UNKNOWN':missing.append('请明确变量“'+v.name+'”是否观测、是否仅取两个值。')
            if v.domain=='OTHER':unsupported.append('NONBINARY_VARIABLE_NOT_ADAPTED')
        for name in SCOPE_QUESTIONS:
            value=getattr(c.scope,name).value
            if value is None or (value is False and name in ('graph_complete','latent_causes_accounted')):
                missing.append(SCOPE_QUESTIONS[name])
            elif value is False:unsupported.append('MODEL_SCOPE_REJECTED:'+name)
        # Preserve an explicitly discussed unit-model boundary. The optional
        # extension does not alter old candidate hashes or the native SCM.
        interference=c.scope.no_between_unit_interference
        if interference is not None:
            if interference.value is False:unsupported.append('BETWEEN_UNIT_INTERFERENCE_NOT_ADAPTED')
            elif interference.value is None:
                missing.append('本次是否采用对象之间无干扰的模型？材料中对此尚未决定，不能自动按无干扰处理。')
        if any(e.kind!='DIRECT_CAUSE' for e in c.relations):missing.append('材料中的相关关系或不确定方向不能直接成为因果边，请确认这些关系。')
        if c.information.kind!='FULL_JOINT_POPULATION_LAW':missing.append('请明确可用的完整观测联合总体分布；样本表或边际统计不能替代。')
        if set(c.information.variables)!={v.name for v in c.variables if v.observation=='OBSERVED'}:
            missing.append('请明确总体联合分布包含的全部观测变量。')
        if c.information.positivity.value is None:missing.append('是否明确假设所有观测联合取值组合都有正总体概率？')
        elif c.information.positivity.value is False:unsupported.append('NONPOSITIVE_LAW_NOT_ADAPTED')
        if c.additional_restrictions:unsupported.append('ADDITIONAL_RESTRICTIONS_NOT_ADAPTED')
        if route_id==FRONTDOOR_ROUTE:
            if c.adjustment is not None:unsupported.append('FRONTDOOR_WITH_ADJUSTMENT_REQUEST_NOT_ADAPTED')
            if c.frontdoor_choice.status=='UNDECIDED':
                missing.append('请确认是否指定某个前门变量；也可以明确不指定，允许后端搜索，不能把尚未决定直接当成允许搜索。')
            elif c.frontdoor_choice.status=='FORBIDDEN':
                unsupported.append('FRONTDOOR_ROLE_PROHIBITED')
        missing.extend(n.text for n in c.unresolved)
        out['clarification_questions']=list(dict.fromkeys(missing));out['unsupported_reasons']=unsupported
        if unsupported:
            out.update(state='UNSUPPORTED',reason_code=unsupported[0]);return out
        if missing:
            out.update(state='NEEDS_INPUT',reason_code='MISSING_OR_AMBIGUOUS_DAG_DECLARATIONS');return out
        problem=_project(b,wire,c,problem_type,version);prepared=prepare_route(problem)
        out.update(state=prepared['state'],reason_code=prepared.get('reason_code'),proposed_problem=problem.model_dump(),
            science_worksheet=prepared.get('worksheet'))
        if prepared['state']=='REVIEW_REQUIRED':
            out['reading_worksheet']=dict(version=reading_version,bundle_sha256=sha(b),candidate_sha256=sha(wire),
                problem_sha256=sha(problem),decisions={k:'PENDING' for k in reading_decisions},is_approval=False)
        return out
    except (ValueError,TypeError,KeyError,AttributeError) as exc:
        # No raw validation inputs or arbitrary materials are echoed in errors.
        from cfm_id_llm.dag_reading import ReadingError
        out.update(state='CHECK_BLOCKED',reason_code=str(exc) if isinstance(exc,ReadingError) else 'INVALID_DAG_BUSINESS_INPUT')
        return out


def submit_reviewed(bundle,wire,*,reading_review=None,science_review=None,research_protocol_selected=False,route_id=CLASSICAL_ROUTE):
    out=inspect_candidate(bundle,wire,route_id=route_id)
    if out['state']!='REVIEW_REQUIRED' or research_protocol_selected is not True:return out
    if reading_review is None or science_review is None:
        out['reason_code']='INDEPENDENT_READING_AND_SCIENCE_REVIEWS_REQUIRED';return out
    try:
        problem_type,review_type,_,adapter_type,_=route_contract(route_id)
        _,_,reading_type,reading_decisions,_=reading_contract(route_id)
        if type(reading_review) is not reading_type:raise ValueError('TYPED_READING_REVIEW_REQUIRED')
        r=reading_type.model_validate(reading_review.model_dump())
        if not r.reviewer.strip() or not r.evidence.strip():raise ValueError('NONBLANK_REVIEW_REQUIRED')
        for field in ('bundle_sha256','candidate_sha256','problem_sha256'):
            if getattr(r,field)!=out['reading_worksheet'][field]:raise ValueError('STALE_DAG_READING_REVIEW')
        if set(r.decisions)!=set(reading_decisions):raise ValueError('EXACT_READING_DECISIONS_REQUIRED')
        if 'REJECTED' in r.decisions.values():raise ValueError('READING_REVIEW_REJECTED')
        if 'PENDING' in r.decisions.values():out['reason_code']='READING_REVIEW_PENDING';return out
        if type(science_review) is not review_type:raise ValueError('TYPED_DAG_SCIENCE_REVIEW_REQUIRED')
        if r.authority!=science_review.authority:raise ValueError('REVIEW_AUTHORITY_MISMATCH')
        p=problem_type.model_validate(out['proposed_problem'])
        result=run_route(adapter_type(),p,review=science_review,research_protocol_selected=True)
        out['route_result']=result
        for key in ('state','reason_code','backend_called','independent_replay','mathematical_claim','certificate'):
            out[key]=deepcopy(result.get(key))
        out['review_records']=dict(reading=r.model_dump(),science=science_review.model_dump())
        return out
    except (ValueError,TypeError,KeyError,AttributeError) as exc:
        out.update(state='CHECK_BLOCKED',reason_code=str(exc) if type(exc) is ValueError else 'INVALID_READING_REVIEW',
            mathematical_claim=None,certificate=None,independent_replay=False)
        return out
