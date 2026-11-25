"""Select a reading contract from source attributes, never from answer success."""
import json
from typing import Generic,Literal,TypeVar
from pydantic import Field
from .population_ate_reading import Strict
from . import joint_reading as source
from .compact_study import digest

T=TypeVar('T')
class Claim(Strict,Generic[T]):
    value:T
    evidence:list[source.Citation]

class Scope(Strict):
    binding:str
    scientific_approval:Literal[False]
    single_question:Claim[bool | None]
    target:Claim[Literal['LOCAL_CONTRAST','FIXED_POLICY_LEVEL','FIXED_POLICY_CONTRAST','FINITE_POLICY_MIXTURE_MEAN','FINITE_POLICY_MIXTURE_CONTRAST','OTHER','UNKNOWN']]
    assignment:Claim[Literal['RANDOMIZED','SELF_SELECTED','OTHER','UNKNOWN']]
    mean_constraints:Claim[Literal['DECLARED','NOT_STATED','UNKNOWN']]
    policy_information:Claim[Literal['FULL_ASSIGNMENT_INFORMATION','SIGNATURE_MEANS','BOUNDED_MEAN_MODEL','OTHER','UNKNOWN']] | None = None
    target_changed_by_reply: Claim[bool | None] | None = None

RULES='''从全部原文和附件核对问题的形状，输出JSON，不解题，不选择更容易识别的目标，不批准科学条件。
LOCAL_CONTRAST是比较本人/同伴状态，未固定其他对象的完整安排；即使关系图只有几个节点，也不能改成两份全网固定名单。
FIXED_POLICY_LEVEL/CONTRAST是一份完整安排的均值/两份完整安排之差；FINITE_POLICY_MIXTURE_MEAN是未来按给定概率选择多份完整政策求平均；FINITE_POLICY_MIXTURE_CONTRAST是两套这种政策混合的平均结果之差。
assignment只读实际处理怎样产生：由抽签分配RANDOMIZED；对象自行选择SELF_SELECTED。已知实际联合概率、某种因子分解或声明可比较性，均不能证明实施过随机抽签。资料内的混合构成项也不一定是未来政策混合。
mean_constraints指明确提到的额外均值等式、不等式或均值顺序，包括待定/不采用的声明；只说需要求均值、已知条件均值表或可比较性不是额外均值约束。
policy_information只读政策问题已有资料的形式：FULL_ASSIGNMENT_INFORMATION为完整安排的总体律或对应条件均值；SIGNATURE_MEANS为本人和同伴状态的总体条件均值；BOUNDED_MEAN_MODEL为明确给出了结果/均值范围的有限均值模型。单纯二元结果定义或希望求界不足以认定完整有限模型。mean_sufficiency（本人和同伴状态决定平均结果）是充分性前提，不是这里的额外均值等式或顺序。多种资料并存须在引用中保留；明确有限模型或额外均值约束优先送联合均值读取；否则保留实际资料形式。每次新读取均填写policy_information，不能从模型答案的POINT/PARTIAL反推。
未知留UNKNOWN/null；未声明额外均值关系可填NOT_STATED。单一问题single_question=true，多问题false，不明确null。除UNKNOWN/null/NOT_STATED外均给原文片段引用。可以引用多段。'''

def binding(case):return digest(['network-source-route/1',case])

def request(case,feedback=None,continuation=None):
    schema=Scope.model_json_schema()
    schema['properties']['binding']['const']=binding(case)
    schema['$defs']['Citation']['properties']['source_id']['enum']=list(source.sources(case))
    schema.setdefault('required',[]).append('policy_information')
    return dict(system_prompt=RULES,user_prompt=json.dumps(dict(binding=binding(case),
        source_catalog=source.sources(case),source_descriptions=source.source_descriptions(case),
        output_schema=schema,format_feedback_not_evidence=feedback,
        clarification_handoff_not_evidence=continuation),ensure_ascii=False)+(
        '\n这是用户回答追问后的同一研究。对照原问题、上次已审核的目标和新增回答；仅确认一项科学前提不改变比较对象。target_changed_by_reply必须给出当前判断；若改变目标须引用本次回答中改变目标的原话。保留真实修改，不能为了沿旧路线忽略用户的新目标。' if continuation else ''))

def check(case,raw,continuation=None):
    result=Scope.model_validate(raw).model_dump(mode='json')
    if result['binding']!=binding(case):raise ValueError('NETWORK_SOURCE_ROUTE_STALE')
    for key in ('single_question','target','assignment','mean_constraints'):
        c=result[key];c['evidence']=source.resolve_evidence(case,c['evidence'])
        if c['value'] not in (None,'UNKNOWN','NOT_STATED') and not c['evidence']:
            raise ValueError('NETWORK_SOURCE_ROUTE_EVIDENCE:'+key)
    info=result.get('policy_information')
    if info is not None:
        info['evidence']=source.resolve_evidence(case,info['evidence'])
        if info['value']!='UNKNOWN' and not info['evidence']:
            raise ValueError('NETWORK_SOURCE_ROUTE_EVIDENCE:policy_information')
    else:result.pop('policy_information',None)  # Saved pre-extension route records remain readable.
    change=result.get('target_changed_by_reply')
    if continuation:
        if not change or change['value'] is None:raise ValueError('CLARIFICATION_TARGET_CHANGE_UNRESOLVED')
        change['evidence']=source.resolve_evidence(case,change['evidence'])
        reply_ids=set(continuation['reply_source_ids'])
        if not any(e['source_id'].split('#L')[0] in reply_ids for e in change['evidence']):
            raise ValueError('CLARIFICATION_REPLY_EVIDENCE_REQUIRED')
        if change['value'] is False and result['target']['value']!=continuation['source_scope']['target']['value']:
            raise ValueError('UNCHANGED_QUESTION_TARGET_DRIFT: 核对用户补充是否改变原目标；不能把仅确认前提改成完整政策比较')
    elif change is None:result.pop('target_changed_by_reply',None)
    return result

def continuation(case,previous_case,report):
    """Carry audited intent, not approval, across an append-only clarification."""
    from copy import deepcopy
    from . import observational_effect_source as reader
    if not previous_case or not report:return None
    before=deepcopy(case);before['sources']=previous_case['sources']
    if before!=previous_case or case['sources'][:len(previous_case['sources'])]!=previous_case['sources']:return None
    added=case['sources'][len(previous_case['sources']):]
    e=report.get('joint_entry') or {};sel=report.get('reader_selection') or {}
    if not added or e.get('case_sha256')!=digest(previous_case) or sel.get('reader')!=reader.FAMILY:return None
    s=reader.inspect(previous_case,e['reading']);a=reader.check_audit(previous_case,s,e['audit'])
    if any(f['verdict']!='MATCH' for f in a['findings'] if f['field'] in ('target_scope_crosscheck','facts.target')):return None
    if not sel.get('source_scope') or not report.get('clarification_questions'):return None
    return dict(previous_case_sha256=digest(previous_case),previous_reading_binding=reader.binding(previous_case,s),
        source_scope=deepcopy(sel['source_scope']),target=deepcopy(s['facts']['target']),
        study=deepcopy(s['facts']['study']),conditioning=deepcopy(s['facts']['conditioning']),
        questions=deepcopy(report['clarification_questions']),reply_source_ids=[x['source_id'] for x in added],
        scientific_approval=False)

def select(scope):
    if scope['single_question']['value'] is not True:return None
    t=scope['target']['value'];a=scope['assignment']['value']
    if t=='LOCAL_CONTRAST' and a=='SELF_SELECTED':return 'NETWORK_OBSERVATIONAL_EFFECTS'
    if t in ('FIXED_POLICY_LEVEL','FIXED_POLICY_CONTRAST','FINITE_POLICY_MIXTURE_MEAN','FINITE_POLICY_MIXTURE_CONTRAST') and a=='SELF_SELECTED':return 'NETWORK_OBSERVATIONAL_POLICY'
    if t in ('FINITE_POLICY_MIXTURE_MEAN','FINITE_POLICY_MIXTURE_CONTRAST') and a=='RANDOMIZED':return 'NETWORK_FINITE_POLICY'
    # A bounded finite model need not have additional equalities or orders.
    # Its supported information, completeness and scientific gates remain in
    # the selected reader and native planner, not in this routing inventory.
    if t in ('FIXED_POLICY_LEVEL','FIXED_POLICY_CONTRAST') and a=='RANDOMIZED':
        info=(scope.get('policy_information') or {}).get('value')
        if scope['mean_constraints']['value']=='NOT_STATED' and info in ('FULL_ASSIGNMENT_INFORMATION','SIGNATURE_MEANS'):
            return 'NETWORK_FINITE_POLICY'
        return 'NETWORK_JOINT_MEANS'
    return None
