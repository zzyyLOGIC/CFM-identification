"""Web contracts for existing business bindings, not theorem applicability.

Every registered business method must have a presentation owner. Science is
still admitted by the original worksheets and rechecked by the original Core.
"""
from copy import deepcopy
import json
from functools import lru_cache

CONTRACT = 'registered-web-review-1'
METHODS = {
 'network.randomized.local_mean':'原分配设计下一个局部暴露状态的平均结果',
 'network.randomized.finite_policy_mean':'有限随机政策的平均结果',
 'network.observational.observed_law_contrast':'按实际采用规律平均的观察性网络效应',
 'network.observational.shared_stratum_contrast':'共同处理前分层调整后的网络效应',
 'network.observational.local_covariate_contrast':'对象自身及邻居协变量调整后的网络效应',
 'network.randomized.local_contrast': '原分配设计下局部暴露状态的均值对比',
 'network.randomized.full_policy_mean': '按有支持的完整名单求政策均值',
 'network.randomized.signature_policy_mean': '按同一单位的暴露标签及均值充分性求政策均值',
 'BOUNDED_POLICY_MEAN_D2_E4':'同伴人数模型中的政策均值界限',
 'BOUNDED_POLICY_CONTRAST_D2_E4':'同伴人数模型中的两政策联合界限',
 'BOUNDED_POLICY_MEAN_FINITE':'有限网络模型中的政策均值界限',
 'BOUNDED_POLICY_CONTRAST_FINITE':'有限网络模型中的两政策联合界限',
 'BOUNDED_POLICY_MEAN_D2_E1': '有限模型中的政策均值界限',
 'network.randomized.full_policy_contrast': '按两份有支持的完整名单求政策均值差',
 'network.randomized.signature_policy_contrast': '按暴露标签及均值充分性求两政策均值差',
 'BOUNDED_POLICY_CONTRAST_D2_E1': '有限模型中的两政策联合界限',
 'MEAN_ORDER_D2_E1': '均值顺序条件下的两政策界限',
 'network.observational.full_policy_mean': '观察性分配下按固定背景和完整名单求政策均值',
 'network.observational.signature_policy_mean': '观察性分配下按固定背景、暴露标签和条件均值充分性求政策均值',
 'DAG_CLASSICAL_BACKDOOR': '经典后门',
 'DAG_ADJUSTMENT': 'DAG 调整',
 'DAG_CLASSICAL_FRONTDOOR': '经典前门',
}

SCIENCE = {
 'target_averaging_and_population_information_scope':'按目标声明的方式平均，使用同一研究、背景及覆盖范围的总体信息',
 'potential_outcome_exposure_sufficiency':'评价对象在所有完整安排下的个体潜在结果，只依赖本人处理和所定义的同伴状态',
 'exposure_level_conditional_exchangeability':'在共同处理前分层和固定背景内，暴露潜在结果均值不随实际本人处理及同伴状态改变',
 'local_covariate_exposure_mean_exchangeability':'在本人处理前特征、所有邻居中特征为1的人数和固定背景内，暴露潜在结果均值不随实际本人处理及同伴状态改变',
 'known_assignment_law':'按材料中完整、已知的随机分配规则',
 'full_vector_randomization':'完整安排与各对象的潜在结果独立',
 'assignment_outcome_independence':'完整安排与各对象的潜在结果独立',
 'consistency':'观察结果对应实际执行的完整安排',
 'fixed_pretreatment_network':'关系网络在处理前固定',
 'finite_conditional_first_moments':'所需条件平均结果存在且有限',
 'finite_conditional_means':'所需条件平均结果存在且有限',
 'full_vector_conditional_exchangeability':'在所述固定处理前背景下，完整使用安排与全部潜在结果条件独立',
 'mean_sufficiency_all_assignments_and_weighted_nodes':'评价对象在所有完整安排下的平均结果，只依赖本人处理和所述同伴状态',
 'conditional_mean_sufficiency_all_assignments_and_weighted_nodes':'固定背景下，评价对象在所有完整安排下的条件平均结果，只依赖本人处理和所述同伴状态',
 'mean_sufficiency_all_assignments_and_all_model_nodes':'全部模型对象、所有完整安排上的均值暴露充分性',
 'exact_a4_values_and_complete_information_scope':'所列信息是总体条件均值，数值或符号形式与材料一致，并且已列尽本模型可用的总体信息',
 'scientific_bounds_kind_scope_units_and_all_nodes':'采用下列科学界限及其结果定义、期间与适用范围',
 'no_additional_coupling_constraints':'除已列条件和界限外，没有额外的跨对象或跨安排约束',
 'only_declared_mean_orders_and_bounds':'除已列基础条件、界限和均值顺序外，没有其他限制',
 'mean_order_outcome_axes_scope_and_assumption_basis':'均值顺序是本研究另行采用的科学假设，适用于已列对象及所有完整安排',
 'a4_population_operator':'所述观测总体信息可用于本次研究，有限记录不自动替代总体信息',
 'a4_operator_scope_and_provenance':'总体信息的来源和覆盖范围与本题一致；有限记录不替代总体信息',
 'complete_positive_assignment_support':'给定表列全该背景下所有正概率完整安排',
 'means_for_all_positive_assignments':'总体结果均值覆盖该表所有正概率安排及所述对象',
 'same_study_and_conditioning':'总体信息与目标来自同一研究及同一固定背景',
 'target_and_variable_roles':'干预、结果和观察变量按本题定义',
 'complete_causal_graph_and_latents':'所列直接因果边完整，未观察共同原因也已明确列出',
 'recursive_scm_and_perfect_intervention':'采用无反馈的结构因果模型、独立结构噪声及只改变指定变量的理想干预',
 'population_law_and_strict_positivity':'可用所列观察变量的联合总体分布，且满足本方法要求的严格正支持',
 'first_stage_profile_no_direct_outcome_effect':'最终完整处理名单相同时，第一阶段名额方案本身不再直接影响结果',
 'conditioning_is_only_fixed_pretreatment_study_background':'所固定的背景在处理前确定；不替换为跨背景平均',
}


@lru_cache(maxsize=1)
def presentation_catalog():
 """Names for existing review requirements, never scientific assertions."""
 from .runtime import PROJECT_ROOT
 terms=json.loads((PROJECT_ROOT/'demo/condition_terms.json').read_text('utf8'))
 explanations=json.loads((PROJECT_ROOT/'demo/condition_explanations.json').read_text('utf8'))
 from cfm_id.network_contrast_context import SCIENCE_REQUIREMENTS
 descriptions={**SCIENCE,**SCIENCE_REQUIREMENTS,'a4_source':'采用材料中声明的总体信息及其对象、处理和同伴状态覆盖范围'}
 return {key:dict(key=key,term=row[0],label=row[1],category=row[2],text=descriptions.get(key,''),explanation=explanations.get(key))
         for key,row in terms.items()}

def inventory():
 from cfm_id.capability_registry import business_bindings
 bindings=business_bindings()
 registered={m.method_id for b in bindings for m in b.methods}
 if registered != set(METHODS):
  raise ValueError('WEB_CAPABILITY_REGISTRY_MISMATCH')
 return [dict(reader=b.reader_id,methods=[dict(id=m.method_id,label=METHODS[m.method_id]) for m in b.methods],scope=b.scope) for b in bindings]

def reading_config():
 from cfm_id import project
 from cfm_id.business_reading_config import ReadingConfig
 from cfm_id_llm.network_observational_definitions import PROFILE
 # Existing reader, including full-policy and signature targets. No user route
 # selection and no modification of historical intake/review checkpoints.
 return ReadingConfig.model_validate({**project.reading_config().model_dump(mode='json'),
                                     'observational_fact_profile':PROFILE})

def identity(sheet):
 # Common worksheets contain auxiliary digests which are not review fields.
 # DAG contracts instead bind their native materials/problem digests directly.
 keys=('version','binding_sha256') if 'binding_sha256' in sheet else ('version','bundle_sha256','candidate_sha256','problem_sha256')
 return {k:deepcopy(sheet[k]) for k in keys if k in sheet}

def bindings(run):
 return {name:dict(identity=identity(sheet),decisions=sorted(sheet.get('decisions',{})))
         for name,sheet in run.review_sheets.items()}

def _science_label(key):
 if key in SCIENCE:return SCIENCE[key]
 from cfm_id.network_contrast_context import SCIENCE_REQUIREMENTS
 if key in SCIENCE_REQUIREMENTS:return SCIENCE_REQUIREMENTS[key]
 if key.startswith('a4_source_') and key.removeprefix('a4_source_').isdigit():
  return '采用材料中声明的总体信息及其对象、处理和同伴状态覆盖范围'
 if key.startswith('mean_order_axis:'):
  node,axis=json.loads(key.split(':',1)[1])
  if axis not in ('OWN','PEERS'):raise ValueError('WEB_UNKNOWN_ORDER_AXIS')
  return None  # The actual node/axis/relation list is displayed together below.
 raise ValueError('WEB_SCIENCE_EXPLANATION_MISSING:'+key)

def science_summary(run):
 """Use the checked plan's normalized objects; never parse prose or supply facts."""
 from .review_summary import policy_text,peer_text
 from cfm_id.capability_registry import plan_binding
 plan=run.plan or {}
 if run.review_kind!='science' or not plan.get('plan_sha256'):return None
 attention=[];conditions=[];condition_items=[];info_brief=[];notes_resolved=False
 def add_condition(text,key=None,*,term='',label='',category='science'):
  if text in conditions:return
  conditions.append(text)
  lookup='a4_source' if key and key.startswith('a4_source_') and key.removeprefix('a4_source_').isdigit() else key
  entry=deepcopy(presentation_catalog().get(lookup,{}))
  entry.update(key=key,text=text)
  if not entry.get('term'):entry.update(term=term,label=label or text,category=category)
  condition_items.append(entry)
 try:
  inventory();binding=plan_binding(plan)
  if plan.get('state')!='REVIEW_REQUIRED':raise ValueError('WEB_PLAN_NOT_REVIEWABLE')
  for row in plan['methods']:
   for key in row['science_worksheet']['decisions']:
    label=_science_label(key)
    if label:add_condition(label,key)
  for name,sheet in run.review_sheets.items():
   record=run.review_templates.get(name,{})
   if identity(record)!=identity(sheet) or set(record.get('decisions',{}))!=set(sheet.get('decisions',{})):
    raise ValueError('WEB_REVIEW_BINDING_MISMATCH')
   if any(v not in ('PENDING','ACCEPTED') for v in record['decisions'].values()):
    raise ValueError('WEB_REVIEW_NOT_CONFIRMABLE')
  facts=plan.get('facts') or plan.get('endpoint_readings',{}).get('first',{}).get('facts') or {}
  target=plan.get('proposed_target') or {}
  if binding.structure=='VARIABLE_DAG':
   problem=plan['methods'][0]['proposed_problem']
   first=[f"设定“{problem['treatment']}”，查看“{problem['outcome']}”的干预分布",problem['context']]
   values=plan.get('query_scope',{})
   if values:first.append('干预取值：'+('全部取值' if values['kind']=='ALL_TREATMENT_VALUES' else '、'.join(map(str,values.get('values',[])))))
   first.append('这是变量间因果图，不是对象之间的关系网络。')
   add_condition('直接因果关系：'+'；'.join(a+' → '+b for a,b in problem['edges']),
       term='Causal graph',label='本次声明的因果边',category='information')
   add_condition('未观察变量：'+('、'.join(problem['latent']) or '方案声明没有'),
       term='Latent variables',label='未观察变量：'+('、'.join(problem['latent']) or '方案声明没有'),category='information')
   declared=plan.get('reading_candidate',{}).get('scope',{}).get('no_between_unit_interference')
   if declared and declared.get('value') is True:add_condition('本次采用对象之间没有干扰的变量因果模型','no_between_unit_interference')
   info=['观察变量：'+'、'.join(problem['observed']),'所述符号总体分布；未代入样本估计或数值。']
  else:
   nodes=target.get('node_order',facts.get('study',{}).get('nodes',[]))
   weights=target.get('unit_weights',[])
   population=[n for n,w in zip(nodes,weights) if str(w) not in ('0','0/1')] if weights else facts.get('target',{}).get('population',nodes)
   if target.get('kind')=='SINGLE_ARM_MEAN':
    compare=('本人接受处理' if target['first'][0] else '本人不接受处理')+'，'+peer_text(target['exposure'],target['first'][1])+'时的平均结果；其余安排按原试点条件概率平均'
   elif target.get('kind')=='FINITE_POLICY_MEAN':
    compare='；'.join('概率 '+x['weight']+'：'+policy_text(dict(zip(nodes,x['assignment']))) for x in target['policies'])
   elif isinstance(target.get('assignment'),list):
    compare=policy_text(dict(zip(nodes,target['assignment'])))
   elif target.get('kind') in ('DIRECT_EFFECT','SPILLOVER_EFFECT','LOCAL_TOTAL_EFFECT'):
    def arm(v):return ('本人接受处理' if v[0] else '本人不接受处理')+'，'+peer_text(target['exposure'],v[1])
    compare=arm(target['first'])+'；减去：'+arm(target['second'])
   elif isinstance(target.get('first'),list) and isinstance(target.get('second'),list):
    compare='第一方案：'+policy_text(dict(zip(nodes,target['first'])))+'；减去第二方案：'+policy_text(dict(zip(nodes,target['second'])))
   else:raise ValueError('WEB_TARGET_PRESENTATION_MISSING')
   first=[compare,'评价：'+('、'.join(population) if len(population)<=8 else str(len(population))+'个对象')+'；按本次明确的权重平均',target.get('outcome',facts.get('study',{}).get('outcome',''))]
   avg=target.get('averaging')
   if avg in ('OBSERVED_ALLOCATION_CONDITIONAL','SHARED_PRETREATMENT_STRATUM','OWN_AND_NEIGHBOR_BINARY_FEATURE'):
    first.append({'OBSERVED_ALLOCATION_CONDITIONAL':'剩余安排按固定背景下实际采用规律的条件概率平均。',
     'SHARED_PRETREATMENT_STRATUM':'按共同处理前分层的总体占比平均调整后的效应。',
     'OWN_AND_NEIGHBOR_BINARY_FEATURE':'每个对象按自身特征与所有邻居中特征为1的人数的总体分布平均。'}[avg])
   context=facts.get('conditioning',{}).get('definition') or facts.get('study',{}).get('context') or target.get('context')
   if context:first.append('期间与背景：'+str(context))
   bounds=facts.get('bounded_model')
   if bounds:
    bound_kind='结果界限' if bounds['bounds_kind']=='ALMOST_SURE_OUTCOME' else '均值界限'
    add_condition(bound_kind+'：'+'；'.join(f"{x['node']} [{x['lower']}, {x['upper']}]" for x in bounds['bounds']),term='Scientific bounds',label=bound_kind)
    add_condition('界限适用于所有完整二元安排；'+bounds['outcome_definition']+'，单位 '+bounds['outcome_unit']+'，期间 '+bounds['outcome_period'],term='Scope',label='界限的对象、期间与安排范围',category='information')
   orders=plan.get('reading_candidate',{}).get('mean_order_model')
   if orders:
    for c in orders.get('order_reading',{}).get('claims',[]):
     relation={'NONDECREASING':'不降低','NONINCREASING':'不增加','NONE':'不施加顺序','UNDECIDED':'尚未决定'}.get(c.get('relation'),c.get('relation'))
     add_condition('、'.join(c['nodes'])+'：'+('本人从不使用改为使用' if c['axis']=='OWN' else '同伴状态提高')+'时，条件均值'+str(relation),term='Mean monotonicity',label=('本人' if c['axis']=='OWN' else '同伴')+'变化：均值'+str(relation))
   info=[]
   for source in facts.get('information',[]):
    if source.get('availability')=='FINITE_SAMPLE':
     info.append('有限样本记录仅用于后续估计，不当作精确总体信息。');info_brief.append('有限样本仅用于后续估计');continue
    cells=source.get('signature_cells',[])
    if cells and source.get('availability')=='EXACT_POPULATION_VALUE':
     info.append('精确总体均值：'+'；'.join(f"{x['node']}（本人{x['own']}，同伴{x['exposure']}）={x['value']}" for x in cells))
     info_brief.append(f'精确总体均值表：{len(cells)} 个坐标')
    else:
     info.append('所述总体信息覆盖：'+'、'.join(source.get('outcome_nodes',[]))+'；具体条件范围与原材料一致。')
     info_brief.append('总体信息：'+('符号形式，未代入数值' if source.get('availability')=='SYMBOLIC_POPULATION_OPERATOR' else '以材料声明为准'))
   if not info:raise ValueError('WEB_INFORMATION_PRESENTATION_MISSING')
  if facts.get('additional_restrictions'):raise ValueError('WEB_UNRESOLVED_DECLARATIONS')
  if facts.get('unresolved'):
   from .note_review import released_for_plan
   if not released_for_plan(plan):raise ValueError('WEB_UNRESOLVED_DECLARATIONS')
   notes_resolved=True
  if plan.get('rejected_fields'):raise ValueError('WEB_REJECTED_DECLARATIONS')
 except (ValueError,KeyError,TypeError) as exc:
  attention.append(str(exc));first=['当前条件尚不能形成完整确认摘要。'];info=['请保留当前材料并查看具体停止原因。']
 return dict(contract=CONTRACT,plan_sha256=plan.get('plan_sha256'),review_bindings=bindings(run),
  reading_notes_resolved=not attention and notes_resolved,
  methods=[r['method'] for r in plan.get('methods',[])],
  cards=[dict(title='要回答什么',lines=first),dict(title='本次需确认的条件',lines=conditions or ['条件尚未明确']),dict(title='依据什么信息',lines=info)],
  condition_items=condition_items,information_brief=list(dict.fromkeys(info_brief)) or info,
  compact_confirmation_available=not attention,needs_individual_attention=attention,is_approval=False,
  confirmation_label='确认采用上述条件并识别')
