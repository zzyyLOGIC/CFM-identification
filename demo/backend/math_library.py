"""Local website adapters for the published mathematical contracts outside classic dispatch."""
from dataclasses import fields
import json
from pydantic import TypeAdapter

from cfm_id import dag_id_route, research_route_catalog, research_route_entry
from cfm_id.capability_registry import registrations
from cfm_id_llm.compact_study import digest
import pfn_pipeline as native
from pfn_pipeline import identification_business as business
from pfn_pipeline._internal.identification.schemas import IdentificationSpec, NetworkPolicyBinaryMeanPopulationTruthV1
from pfn_pipeline._internal.identification.identification import IdentificationEngine
from pfn_pipeline._internal.identification.verifier import IdentificationVerifier
from .capabilities import METHODS


INQUIRIES={
    'fixed_policy':business.FixedPolicyInquiryV21,
    'finite_policy':business.FinitePolicyInquiryV21,
    'observational_policy':business.ObservationalPolicyInquiryV23,
    'observational_effect':business.ObservationalEffectsInquiryV26,
    'shared_stratum':business.ObservationalExposureAdjustedEffectsInquiryV27P2,
    'nodewise':business.ObservationalNodewiseAdjustedEffectsInquiryV28,
}
OPERATIONS={
    'population':('总体规格求解','随机与单臂 ATE、Manski 界、网络单臂、多数响应与得分、有限候选暴露模型。'),
    'task':('任务规格与交接审计','按 TaskSpec 重新识别，检查原库交接和可重放的估计请求。'),
    'batch':('逐对象、逐暴露臂','返回每个对象及每个局部臂的支持概率和核验状态。'),
    'linear':('自定义线性对比','按显式权重组合同一批已核验的局部臂。'),
    'effects':('个人、群体及多目标效应','一次核验多个直接、溢出或总效应，保留各自的权重和目标。'),
    'business':('具名及混合政策、观察性网络','可提交固定或有限政策、观察性名单、完整联合律、因子化或混合分配、共同或逐对象分层。'),
    'r3_pair':('观察性总体信息与目标对照','分别求解两份观察性规格，检查目标、总体信息及联合交接条件。'),
    'signature_support':('政策签名支持诊断','按原设计及暴露映射核算每个对象的目标支持。'),
    'quota_support':('固定名额多数签名诊断','查找固定名额下多数签名的支持障碍。'),
    'legacy_bridge':('旧多数响应的逐臂重放','由原响应证书重建并重放批量支持。'),
    'legacy_compare':('旧响应与指定臂比对','分别重算并对照同一研究的单臂任务和旧响应。'),
    'requirements':('识别假设和总体信息要求','查看指定方法、两阶段设计及观察性调整所需条件。'),
}


def catalog():
    routes={r.capability.route_id:METHODS.get(r.capability.route_id,'二元工具变量的 LATE 与总体 ATE') for r in registrations()}
    routes[dag_id_route.ROUTE]='一般变量图 ID 与不可识别见证'
    return dict(classic=METHODS,native={k:dict(label=v[0],description=v[1]) for k,v in OPERATIONS.items()},
                research=routes)


def schema(op):
    if op==dag_id_route.ROUTE:
        return dict(problem=dag_id_route.GeneralIdProblem.model_json_schema(),review=dag_id_route.GeneralIdReview.model_json_schema())
    if op in catalog()['research']:
        return research_route_catalog.schemas(op)
    if op=='population':
        return dict(spec=IdentificationSpec.model_json_schema(),population_truth=NetworkPolicyBinaryMeanPopulationTruthV1.model_json_schema(),
                    optional=['population_truth'])
    if op in ('business','r3_pair'):
        return dict(input=({'kind':'选择一种合同','inquiry':'填写该合同'} if op=='business' else {'left':'业务输入','right':'业务输入'}),
                    contracts={k:TypeAdapter(cls).json_schema() for k,cls in INQUIRIES.items()})
    if op in ('signature_support','quota_support'):
        return dict(study='declare_network_study',target=dict(assignment='按名册顺序的 0/1 数组',unit_weights='同序权重',
                     authority='目标来源'),signature=dict(grouping='暴露映射',core_collaborators='仅核心多数使用'))
    if op=='requirements':
        return dict(route_ids=native.implemented_assumption_catalog_v27()['route_ids'],optional=['route','design_kind'])
    if op not in OPERATIONS:
        raise ValueError('UNKNOWN_MATH_OPERATION')
    from pfn_pipeline.identification_a4_shadow import declare_a4_source
    import inspect
    return dict(task={f.name:str(f.type) for f in fields(native.TaskSpec)},spec=IdentificationSpec.model_json_schema(),
                a4_fields=list(inspect.signature(declare_a4_source).parameters)[1:] if op in ('linear','effects') else [],
                terms=[dict(node_id='对象',own_treatment='0/1',exposure_state='暴露坐标',coefficient='有理数')] if op=='linear' else [],
                requests={f.name:str(f.type) for f in fields(native.EffectQueryV18)} if op=='effects' else {},
                additional_task='legacy_task' if op=='legacy_compare' else None)


def _worksheet(op,problem):
    items={'target':'核对目标、评价对象、顺序、时间和权重','source':'核对分配、暴露和每项可用总体信息的实际来源'}
    def collect(x,path):
        if isinstance(x,dict):
            if 'name' in x and ('confirmed' in x or 'status' in x and 'evidence' in x):
                items[path]=str(x['name'])+'  '+json.dumps(x,ensure_ascii=False)
            elif path.endswith(('.license','.r2_sufficiency','.population_truth')):
                items[path]='核对材料及适用范围  '+path
            for k,v in x.items():
                collect(v,path+'.'+k)
        elif isinstance(x,list):
            for i,v in enumerate(x):
                collect(v,path+'['+str(i)+']')
    collect(problem,'problem')
    return dict(binding=digest([op,problem,items]),items=items)


def _business(problem):
    from pfn_pipeline.identification_business import identify_network_business_query, replay_verified_business_outcome
    cls=INQUIRIES[problem['kind']]
    adapter=TypeAdapter(cls)
    typed=adapter.validate_json(json.dumps(problem['inquiry'],allow_nan=False))
    def check_keys(supplied,parsed):
        if isinstance(supplied,dict) and isinstance(parsed,dict):
            if supplied.keys()-parsed.keys():
                raise ValueError('UNREPRESENTED_INPUT_FIELD')
            for key,value in supplied.items():
                check_keys(value,parsed[key])
        elif isinstance(supplied,list) and isinstance(parsed,list):
            for a,b in zip(supplied,parsed,strict=True):
                check_keys(a,b)
    check_keys(problem['inquiry'],adapter.dump_python(typed,mode='json'))
    result=identify_network_business_query(typed)
    if result.status=='POINT' and replay_verified_business_outcome(result) is not True:
        raise ValueError('BUSINESS_REPLAY_FAILED')
    return result


def _diagnostic(op,p):
    from pfn_pipeline.network_inquiry_shadow import declare_network_study,fixed_policy_target_from_context
    if op=='requirements':
        return dict(catalog=native.implemented_assumption_catalog_v27(),shared_catalog=native.implemented_assumption_catalog_v27p2(),
                    nodewise_catalog=native.implemented_assumption_catalog_v28(),shared_stratum=native.requirements_for_exposure_adjustment_v27p2(),
                    nodewise=native.requirements_for_nodewise_adjustment_v28(),required=native.requirements_for_route_v27(
                    p['route'],design_kind=p.get('design_kind')) if p.get('route') else None)
    study=declare_network_study(**p['study'])
    target=fixed_policy_target_from_context(study,**p['target'])
    if op=='quota_support':
        return native.diagnose_majority_quota_policy_v23(study,target).summary()
    signature=native.declare_policy_signature(study,**p['signature'])
    result=native.diagnose_policy_signature_support_v25(study,target,signature)
    native.replay_policy_signature_support_v25(result,study,target,signature)
    return result.summary()


def _compute(op,p):
    if op=='population':
        spec=IdentificationSpec.model_validate(p['spec'])
        truth=p.get('population_truth')
        if truth is not None:
            if spec.network_policy_mixture_theorem_contract is None:
                raise ValueError('TRUTH_REQUIRES_FINITE_MIXTURE_CONTRACT')
            truth=NetworkPolicyBinaryMeanPopulationTruthV1.model_validate(truth)
        verifier=IdentificationVerifier()
        result=IdentificationEngine().solve_verified(spec,verifier,population_truth=truth)
        if result.verification_status=='VERIFIED':
            result=verifier.verify(spec,result,population_truth=truth)
        return result.model_dump(mode='json',exclude_none=True)
    if op=='business':
        result=_business(p)
        out=result.summary()
        if result.status=='POINT':
            out['handoff_audit']=native.inspect_verified_business_handoff_v27(result)
        return out
    if op=='r3_pair':
        a,b=(_business(p[k]) for k in ('left','right'))
        return dict(left=native.inspect_r3_target_a4_v28p0(a).summary(),right=native.inspect_r3_target_a4_v28p0(b).summary(),
                    comparison=native.compare_r3_target_a4_v28p0(a,b).summary(),joint=native.inspect_r3_joint_handoff_v28p0((a,b)))
    task=native.TaskSpec(**p['task'])
    if op in ('task','legacy_bridge','legacy_compare'):
        result=native.identify(task)
        if op=='task':
            audit=native.inspect_identification_estimation(result)
            if result.estimation_request is not None:
                native.replay_handoff(result)
            return dict(status=result.status,result=result.result,handoff=result.estimation_request,audit=audit)
        if op=='legacy_compare':
            return native.compare_arm_with_legacy_response(result,native.identify(native.TaskSpec(**p['legacy_task'])))
        bridge=native.replay_legacy_response_batch_bridge(native.bind_legacy_response_batch(result))
        return dict(bridge=bridge.binding_sha256,batch=bridge.batch.batch_sha256,status=bridge.batch.coverage_status)
    batch=native.replay_network_arm_batch(native.identify_randomized_network_batch(task))
    if op=='batch':
        return dict(nodes=batch.node_ids,states=batch.exposure_states,support=batch.population_joint_support,
                    statuses=batch.arm_status,reasons=batch.arm_reason,coverage=batch.coverage_status,binding=batch.batch_sha256)
    from pfn_pipeline.identification_a4_shadow import declare_a4_source
    args=dict(p['a4'])
    for key in ('arm_cells','assignment_cells'):
        if key in args:
            args[key]=tuple(map(tuple,args[key]))
    source=declare_a4_source(task,**args)
    if op=='linear':
        terms=tuple(native.ArmLinearTerm(**r) for r in p['terms'])
        return native.replay_verified_composition(native.identify_verified_linear_target(batch,source,terms)).summary()
    requests=tuple(native.EffectQueryV18(**dict(r,node_weights=tuple(map(tuple,r['node_weights'])))) for r in p['requests'])
    return native.replay_verified_effect_bundle(native.identify_verified_effect_bundle(batch,source,requests)).summary()


def run(value):
    op,p=value['operation'],value['problem']
    if not isinstance(p,dict):
        raise ValueError('STRUCTURED_PROBLEM_REQUIRED')
    review=value.get('review')
    if op==dag_id_route.ROUTE:
        problem=dag_id_route.GeneralIdProblem.model_validate(p)
        return dag_id_route.prepare(problem) if review is None else dag_id_route.submit(problem,dag_id_route.GeneralIdReview.model_validate(review))
    if op in catalog()['research']:
        return research_route_entry.run_registered_route(op,p,review=review,research_protocol_selected=review is not None)
    if op not in OPERATIONS:
        raise ValueError('UNKNOWN_MATH_OPERATION')
    allowed={'population':{'spec','population_truth'},'business':{'kind','inquiry'},'r3_pair':{'left','right'},
             'requirements':{'route','design_kind'},'signature_support':{'study','target','signature'},
             'quota_support':{'study','target'},'linear':{'task','a4','terms'},'effects':{'task','a4','requests'},
             'legacy_compare':{'task','legacy_task'}}.get(op,{'task'})
    if p.keys()-allowed:
        raise ValueError('UNREPRESENTED_INPUT_FIELD')
    if op in ('requirements','signature_support','quota_support'):
        return dict(state='DIAGNOSTIC',result=_diagnostic(op,p),estimation_handoff_allowed=False)
    sheet=_worksheet(op,p)
    if review is None or review.get('decisions')!=dict.fromkeys(sheet['items'],'ACCEPTED'):
        return dict(state='REVIEW_REQUIRED',worksheet=sheet,backend_called=False,estimation_handoff_allowed=False)
    if review.get('binding')!=sheet['binding'] or not all(isinstance(review.get(k),str) and review[k].strip() for k in ('reviewer','evidence')):
        raise ValueError('CURRENT_REVIEW_AND_SOURCE_REQUIRED')
    result=_compute(op,p)
    return dict(state=result.get('status') or result.get('coverage') or 'COMPUTED',result=result,
                input_binding=sheet['binding'],estimation_handoff_allowed=False)
