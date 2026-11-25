"""One read-only envelope for dedicated and common entries. Never an admission record."""
from copy import deepcopy
from hashlib import sha256
import json
from cfm_id_bridge.scientific_binding import canonical_data

VERSION='entry-diagnostics-1'
LABELS={
    'NETWORK_OBSERVATIONAL_BOUNDS':('观察性政策界限','在完整二元模型下，以一致性分解潜在均值，再复用有限均值求界与独立证书'),
    'NETWORK_OBSERVATIONAL_EFFECTS':('观察性网络局部效应','沿原目标的平均方式，复用观察律、共同分层或局部特征调整方法'),
    'NETWORK_FINITE_POLICY':('有限政策混合','分别核验各完整政策，再按原题给定的方案概率组合'),
    'NETWORK_OBSERVATIONAL_POLICY':('观察性网络政策','核对完整分配的观察概率、可比较性和目标政策支持'),
    'DAG_GENERAL_ID':('一般图 ID','对已声明的因果图和干预目标执行图推导'),
    'DAG_JOINT_ID':('联合干预 ID','一次固定所列全部干预变量；使用集合目标的图推导'),
    'FINITE_MEAN_JOINT':('有限均值联合约束求界','在同一有限均值模型中保留全部已采用等式和线性不等式'),
    'SYMBOLIC_MEAN_JOINT':('符号联合均值界限','固定有理系数、保留参数域与仿射限制，核对各最优分段及其适用区域'),
    'BINARY_IV_LATE_ATE':('二元工具变量','分别核对工具、实际处理、目标人群及总体概率表'),
    'population':('总体 ATE 或界限','按总体规格中的目标和信息准备原生候选'),
    'business':('网络研究规格','使用已声明的网络目标、信息和科学许可'),
    'effects':('批量局部效应','逐问保留目标、对象和权重'),
    'linear':('局部均值线性组合','保留每个非零系数所对应的均值及支持'),
    'DIRECT_ANSWER':('模型直答与独立核验','核验本次原问与材料；模型的自报结论不作为数学证据'),
    'COMMON_READING':('研究字段匹配的候选方法','按已读取的目标、设计、信息和采用的条件准备候选，各自保留原审核'),
    'DAG_CLASSICAL_BACKDOOR':('后门调整','核对完整图、处理与结果、后门条件及所需总体信息'),
    'DAG_CLASSICAL_FRONTDOOR':('经典前门','检查中介路径和相应混杂阻断条件；不将前门失败当作不可识别'),
    'DAG_ADJUSTMENT':('指定调整集','检查研究者指定的变量集是否符合调整条件'),
    'MEAN_ORDER_D2_E1':('有限均值顺序求界','在原有限模型中共同使用明确采用的均值顺序'),
    'task':('原生任务规格','按该任务的目标和信息准备原生方法，并保留交接检查'),
    'batch':('逐对象与暴露臂','逐个检查目标事件支持，不以部分通过代替全部通过'),
    'r3_pair':('观察性目标与信息对照','保留两个原目标各自的结果，再检查是否可以共同交接'),
    'signature_support':('目标签名支持诊断','仅计算声明设计下的支持；本项不证明因果假设'),
    'quota_support':('固定名额支持诊断','检查目标与名额的兼容性；本项不单独生成识别结论'),
    'legacy_bridge':('旧证书逐臂核验','按原始目标重建并核验，不自动扩大旧证书的范围'),
    'legacy_compare':('指定臂与旧结果对照','先分别复算，再比较是否回答同一个目标'),
    'requirements':('条件目录查询','展示方法所需条件，查询目录本身不代表条件已满足'),
}
REASONS={
    'OBSERVED_VARIABLE_COVERAGE_NOT_CONNECTED':'样本共同记录的变量与图变量不一致，未自行删变量或改变因果图。',
    'JOINT_OBSERVATIONS_NOT_AVAILABLE':'资料未共同记录全部所需变量，不能把分开的边际信息拼成联合分布。',
    'BOUNDS_SYMBOLIC_PROJECTION_LIMIT':'需表达的均值或参数超过现有精确符号求界规模，未输出截断后的界限。',
    'BOUNDED_EXPOSURE_RESTRICTION_NOT_PROJECTED':'原文采用了均值充分性，当前观察性界限转换尚不能共同表达，未忽略。',
    'SYMBOLIC_BASIS_ENUMERATION_LIMIT':'需要核对的参数分段超过当前计算上限；未将不完整枚举当作完整界限。',
    'INFORMATION_IS_NOT_A_POPULATION_LAW':'缺少这条方法需要的总体联合分布说明；有限样本不能直接代替。',
    'SAMPLE_IS_NOT_POPULATION_INFORMATION':'当前提供的是样本或未定信息，尚不能作为精确总体均值。',
    'POPULATION_LAW_VARIABLE_COVERAGE_MISMATCH':'总体分布覆盖的变量与本次图不一致。',
    'STRICT_POSITIVITY_NOT_ESTABLISHED':'尚未建立这条入口所需的正概率条件。',
    'GRAPH_NOT_CONFIRMED_BY_RESEARCHER':'因果图还没有确认。',
    'UNRESOLVED_MATERIAL_ITEMS':'原材料还有未确定的内容。',
    'SCIENTIFIC_DECISION_UNRESOLVED':'有科学条件尚未决定，不能按已采用计算。',
    'FINITE_MEAN_MODEL_NOT_COMPLETE':'还没有明确有限均值模型是否列全。',
    'ADDITIONAL_RESTRICTIONS_NOT_EXPRESSED':'还有本入口不能表达的额外限制，已保留并停止。',
    'EXACT_VERTEX_SEARCH_LIMIT':'联合约束超过当前精确计算规模，未据此判定不可识别。',
    'EXACT_DUAL_SEARCH_LIMIT':'最优性证据搜索达到上限，尚未核准界限。',
    'NODE_COUNT_OUT_OF_RANGE':'图的节点数超过当前重放规模。',
    'MODEL_SIZE_OUT_OF_RANGE':'图和隐藏共同原因超过当前重放规模。',
    'STALE_JOINT_ID_REVIEW':'材料或目标已变化，原确认不再适用。',
    'STALE_JOINT_MEAN_REVIEW':'材料、目标或约束已变化，原确认不再适用。',
    'ZERO_OBSERVATIONAL_FULL_ASSIGNMENT_SUPPORT':'目标完整安排在所声明的观察分配律中没有支持；不能只凭局部状态有支持就替换方法。',
    'SCIENTIFIC_CONDITION_PENDING':'科学条件尚未确认，尚未调用数学求解。',
    'SCIENTIFIC_CONDITION_REJECTED':'本次有科学条件未被接受，不能按已采用计算。',
    'INVALID_ROUTE_PROBLEM_OR_REVIEW':'问题规格或审核记录不符合所选方法的合同，未进入数学计算。',
}


def summarize(result, *, operation=None, plan=None, problem=None):
    r=result if isinstance(result,dict) else {}
    plan=plan if isinstance(plan,dict) else {}
    joint=r.get('joint_entry') or {}
    method=operation or r.get('route_id') or r.get('method_id') or joint.get('operation') or (r.get('proof') or {}).get('method')
    method=method if isinstance(method,str) else 'COMMON_READING' if plan else 'DIRECT_ANSWER'
    label,basis=LABELS.get(method,(method,'使用该入口已有的目标与条件检查；此处只汇总检查记录'))
    native=r.get('native_state') or r.get('state') or r.get('status')
    if native is None:
        native=joint.get('state') or (r.get('local_targets') or {}).get('state') or r.get('decision') or 'NOT_CHECKED'
    inner=r.get('result') if isinstance(r.get('result'),dict) else {}
    reason=r.get('reason_code') or joint.get('reason_code') or r.get('reason') or inner.get('reason_code') or inner.get('reason')
    reason=reason if isinstance(reason,str) else None
    questions=[q for q in r.get('clarification_questions',[]) if isinstance(q,str)]
    input_diagnostics=deepcopy(joint.get('input_diagnostics',[]))
    sheet=r.get('worksheet') or {}
    if isinstance(sheet,dict): questions+= [q for q in sheet.get('clarification_questions',[]) if isinstance(q,str)]
    candidates=deepcopy(joint.get('candidate_findings',[]))
    preparation=plan.get('method_preparation_report') or r.get('method_preparation_report')
    # Preserve exact original candidate findings instead of inventing why alternatives fail.
    if isinstance(preparation,dict):
        for key in ('candidates','methods'):
            rows=preparation.get(key)
            if isinstance(rows,list): candidates=deepcopy(rows);break
    proof=r.get('certificate') or r.get('proof') or {}
    verified=r.get('independent_replay') is True
    outcome=('VERIFIED' if verified else 'NONIDENTIFICATION_PROVED' if r.get('nonidentification_proved') is True
             else 'CONDITIONAL_EVIDENCE' if proof else 'NO_VERIFIED_RESULT')
    missing=list(dict.fromkeys(questions))
    if reason: missing.append(REASONS.get(reason,'本入口返回：'+reason))
    if native=='REVIEW_REQUIRED' and not missing: missing.append('需要确认本题列出的科学条件和来源。')
    if native in ('NEEDS_INPUT','UNSUPPORTED','CHECK_BLOCKED','RESOURCE_LIMIT') and not missing:
        missing.append('本入口尚未核准结果；原方法的逐项停止记录保留在结果详情中。')
    details=[]
    p=problem if isinstance(problem,dict) else joint.get('problem') or {}
    unconfirmed=[]
    condition_labels={'exposure_level_conditional_exchangeability':'按所列背景分层后，局部处理状态与潜在结果可比较',
                      'local_covariate_conditional_exchangeability':'按本人与邻居特征调整后的可比较性',
                      'potential_outcome_exposure_sufficiency':'本人和同伴状态足以描述相关处理影响',
                      'full_vector_conditional_exchangeability':'给定背景后，完整处理安排与潜在结果可比较',
                      'mean_signature_sufficiency':'本人与同伴状态足以决定条件平均结果'}
    def scan(value,path='problem'):
        if isinstance(value,dict):
            if isinstance(value.get('name'),str) and value.get('confirmed') is False:
                unconfirmed.append(dict(field=path,name=value['name'],status=value.get('status'),
                                        description=condition_labels.get(value['name'],value['name'])))
            for k,v in value.items():scan(v,path+'.'+k)
        elif isinstance(value,list):
            for i,v in enumerate(value):scan(v,path+'['+str(i)+']')
    scan(p)
    if native in ('NEEDS_INPUT','REVIEW_REQUIRED','CHECK_BLOCKED'):
        missing.extend('规格中尚未确认：'+x['description']+'。' for x in unconfirmed)
    if not candidates and isinstance(inner.get('attempted_routes'),list):
        candidates=deepcopy(inner['attempted_routes'])
    if method=='DAG_JOINT_ID' and p:
        details=[dict(field='treatments',value=p.get('treatments'),meaning='同时设定这一组变量；不是分别做两次单变量干预'),
                 dict(field='outcome',value=p.get('outcome'),meaning='本次请求的结果变量'),
                 dict(field='model',value=p.get('model'),meaning='按已声明的因果模型检查图推导'),
                 dict(field='information',value=p.get('information'),meaning='v2有限共同记录只用于声明观测变量范围，输出总体分布的符号公式；v1保留已知总体信息合同')]
    if method=='FINITE_MEAN_JOINT' and p:
        rows=p.get('constraints',[])
        details=[dict(field='target',value=p.get('target'),meaning='在同一组均值上共同求这个线性目标'),
                 dict(field='adopted_constraints',value=[c.get('id') for c in rows if c.get('adoption')=='ADOPTED'],meaning='求界时共同保留'),
                 dict(field='undecided_constraints',value=[c.get('id') for c in rows if c.get('adoption')=='UNDECIDED'],meaning='尚未决定时停止，不自动采用'),
                 dict(field='not_adopted_constraints',value=[c.get('id') for c in rows if c.get('adoption')=='NOT_ADOPTED'],meaning='保留原声明，不用于缩小界限')]
    snapshot=json.dumps(dict(result=r,plan=plan,operation=operation,problem=p),sort_keys=True,ensure_ascii=False,
                        allow_nan=False,separators=(',',':'),default=canonical_data)
    return dict(version=VERSION,source_snapshot_sha256=sha256(snapshot.encode('utf8')).hexdigest(),
        method=dict(id=method,label=label,preparation_basis=basis,
                    selection='EXPLICIT_ENTRY' if operation else 'EXISTING_DISPATCH_RECORD',input_facts=details),native_state=native,reason_code=reason,
        result_evidence=outcome,missing_or_stopping=missing,candidate_findings=candidates,
        unconfirmed_declarations=unconfirmed,input_diagnostics=input_diagnostics,
        alternative_methods='仅列原记录实际检查的候选；未检查的方法不判为不适用。',
        scientific_approval=False,production_admission=False,estimation_handoff_allowed=False)
