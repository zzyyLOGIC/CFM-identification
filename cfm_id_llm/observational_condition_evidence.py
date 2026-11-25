"""Read scientific statements independently, then compare their typed meaning.

The model does not return MATCH or copy the candidate's booleans. In particular,
a local-C mean assumption cannot also justify a shared-B mean assumption.
This is source review, not a proof of the truth of a scientific premise.
"""
import json
import re
from typing import Literal
from pydantic import Field
from .population_ate_reading import Strict
from . import joint_reading as source
from .compact_study import digest
from .network_extended_reading import DECLARATION_STATUS_GUIDANCE

SIGNATURES={
    'full_vector_conditional_exchangeability':('VECTOR_EXCHANGEABILITY','FIXED_W'),
    'potential_outcome_exposure_sufficiency':('RESULT_SUFFICIENCY','NONE'),
    'exposure_level_conditional_exchangeability':('EXPOSURE_MEAN_EXCHANGEABILITY','SHARED_B_AND_W'),
    'local_covariate_exposure_mean_exchangeability':('EXPOSURE_MEAN_EXCHANGEABILITY','LOCAL_C_AND_W'),
}
BASIC_SIGNATURES={
    'consistency':('CONSISTENCY','NONE'),
    'fixed_pretreatment_network':('PRETREATMENT_NETWORK','NONE'),
    'finite_conditional_first_moments':('FINITE_MEANS','NONE'),
}
LABELS={
    'consistency':'实际结果对应实际完整安排下的潜在结果',
    'fixed_pretreatment_network':'处理前确定并保持固定的关系网络',
    'finite_conditional_first_moments':'所需条件均值存在且有限',
    'full_vector_conditional_exchangeability':'给定固定背景后的完整安排可比较性',
    'potential_outcome_exposure_sufficiency':'相同本人及同伴状态对应相同潜在结果',
    'exposure_level_conditional_exchangeability':'给定共同处理前分层后的可比较性',
    'local_covariate_exposure_mean_exchangeability':'给定本人和邻居局部特征后的可比较性',
}

class Statement(Strict):
    kind: Literal['CONSISTENCY','PRETREATMENT_NETWORK','FINITE_MEANS','VECTOR_EXCHANGEABILITY','RESULT_SUFFICIENCY','EXPOSURE_MEAN_EXCHANGEABILITY','DISTRIBUTION_FACT','OTHER']
    conditioning: Literal['FIXED_W','SHARED_B_AND_W','LOCAL_C_AND_W','FULL_X_AND_W','NONE','OTHER']
    conditioning_definition: str
    status: Literal['ADOPTED','NOT_ADOPTED','NOT_INFERRED','UNSTATED','PENDING','CONFLICT']
    evidence: list[source.Citation]
    explanation: str = Field(min_length=1)
    question: str | None

class Review(Strict):
    schema_version: Literal[1,2] = 1
    binding: str
    scientific_approval: Literal[False]
    statements: list[Statement]

RULES='''只根据原始文字和附件整理当前科学声明，输出合同JSON；不解题，不批准科学假设，不判断候选是否正确。
schema_version=2。完整检查基本声明和下列交换性/充分性声明；一段原文确实包含多项时分别记录，各自保留准确引文。
CONSISTENCY：实际观察结果等于实际执行的完整安排下的潜在结果。它不是“两个完整安排具有相同本人/同伴状态时潜在结果相同”，后者只属于RESULT_SUFFICIENCY，不能互相引用代替。
PRETREATMENT_NETWORK：关系在处理前确定且研究期间保持固定。FINITE_MEANS：所需条件均值存在且有限。这三项conditioning=NONE；与交换性、充分性分别核对。
先核对关系的两个对象。资料中“各店是否使用相互独立”“给定人员配置后独立抽取”是实际安排的分布描述，记DISTRIBUTION_FACT；没有提到潜在结果，不能据此登记任何交换性。潜在结果是否只依赖本人和同伴状态，也不能由已知分布推得。
每项声明拆开记录“关系是什么、给定什么、当前是否采用”。未声明可省略或记UNSTATED，不能写成不采用；只有UNSTATED可以没有引文。
VECTOR_EXCHANGEABILITY：给定固定背景W，完整处理名单与各完整安排下的潜在结果独立。
RESULT_SUFFICIENCY：对所有完整安排，本人及定义的同伴状态相同，潜在结果本身相同；仅均值相同不能填此项。conditioning=NONE表示这是状态充分性，不是给定协变量的交换性。
EXPOSURE_MEAN_EXCHANGEABILITY：本人/同伴状态下的潜在平均结果在给定条件下不随实际本人/同伴状态变化。必须区分：SHARED_B_AND_W是共同的处理前分层B；LOCAL_C_AND_W是每个对象本人的二元特征和全部邻居正特征计数C_i；FULL_X_AND_W是完整特征配置X。这三项不能互相推导或重复登记同一原句为多种声明。
conditioning_definition用原文含义说明给定的对象；不得因所选方法需要B就把C_i改叫B。不是这三种声明的保留OTHER，不编造等价关系。
明确采用ADOPTED；明确不采用NOT_ADOPTED；尚未决定PENDING。用户补充可以解决此前待定，但不能覆盖原文已有的明确矛盾。矛盾保留CONFLICT并给一句易答问题；PENDING可附候选问题，是否需向用户询问由方法条件检查决定，不能为无关的未知条件增加追问；其他状态question=null。
同一声明只留当前一项状态，引用实际支持它的原文。全部引用使用给定#L片段编号，可省略quote。
只否认推导依据、没有另行采用或拒绝时记NOT_INFERRED；它不授予也不拒绝科学许可。'''+ '\n'+DECLARATION_STATUS_GUIDANCE

def binding(case,reading):return digest(['observational-condition-evidence/1',case,reading])

def request(case,reading):
    schema=Review.model_json_schema()
    schema['properties']['schema_version']['const']=2
    schema['required']=list(dict.fromkeys([*schema['required'],'schema_version']))
    schema['properties']['binding']['const']=binding(case,reading)
    schema['$defs']['Citation']['properties']['source_id']['enum']=list(source.sources(case))
    return dict(system_prompt=RULES,user_prompt=json.dumps(dict(
        binding=binding(case,reading),source_catalog=source.sources(case),
        source_descriptions=source.source_descriptions(case),output_schema=schema),ensure_ascii=False))


def reconcile_request(case,reading,receipt,findings,error=None):
    """One bounded source recheck before a disputed inventory changes reading.

    No candidate booleans are supplied. The full candidate audit must still
    match, and the replacement inventory is checked by the same contract.
    """
    req=request(case,reading);body=json.loads(req['user_prompt'])
    body['disputed_statements']=[x['field'].split('.')[-1] for x in findings if x['verdict']!='MATCH']
    if error:body['contract_error_not_evidence']=str(error)
    # Do not anchor the second reader to the first reader's mistaken verdict.
    statements=receipt.get('statements',[]) if isinstance(receipt,dict) else []
    body['source_passages_to_recheck']=[s['evidence'] for s in statements if isinstance(s,dict) and s.get('evidence')] if isinstance(statements,list) else []
    body['recheck_instructions']='上一份声明清单与另一份原文读取存在分歧，两者都不视为正确答案。重新检查原文中的关系对象、给定条件和采用态度；区分实际分配之间的独立与潜在结果交换性。只输出根据原文重新核对后的完整声明清单，不能为通过核验改写原文；没有改变的真实分歧应继续保留。'
    return dict(req,user_prompt=json.dumps(body,ensure_ascii=False))

def check(case,reading,raw):
    receipt=Review.model_validate(raw).model_dump(mode='json')
    version=receipt['schema_version']
    # Preserve historical receipt bytes and confirmation bindings. New source
    # requests require v2; replaying v1 never fabricates a new basic audit.
    if 'schema_version' not in raw:receipt.pop('schema_version')
    signatures={**SIGNATURES,**BASIC_SIGNATURES} if version==2 else SIGNATURES
    if receipt['binding']!=binding(case,reading):raise ValueError('CONDITION_EVIDENCE_STALE')
    indexed={}
    for s in receipt['statements']:
        s['evidence']=source.resolve_evidence(case,s['evidence'])
        if s['status']=='NOT_ADOPTED':
            passages='\n'.join(e['quote'] for e in s['evidence'])
            disclaimer=re.search(r'不据此假定|不能(?:仅)?由.{0,30}推出|不(?:能|应)据此(?:推断|认定)',passages)
            direct=re.search(r'(?:本次|本研究|此次|方案)(?:明确)?(?:不|拒绝)(?:采用|接受|假设)|明确不采用',passages)
            if disclaimer and not direct:
                raise ValueError('INFERENCE_DISCLAIMER_NEEDS_SCOPE_RECHECK: 引文否认从资料推出条件，尚不支持“本次不采用”。重新核对否定对象；若没有独立采用或拒绝声明，应保留NOT_INFERRED。不能自动批准该条件。')
        if s['status']=='CONFLICT' and not (s['question'] or '').strip():raise ValueError('CONDITION_EVIDENCE_QUESTION')
        if s['status'] not in ('CONFLICT','PENDING') and s['question'] is not None:raise ValueError('CONDITION_EVIDENCE_QUESTION')
        if s['status']!='UNSTATED' and not s['evidence']:raise ValueError('CONDITION_EVIDENCE_REQUIRED')
        if s['conditioning'] not in ('NONE','OTHER') and not s['conditioning_definition'].strip():
            raise ValueError('CONDITIONING_DEFINITION_REQUIRED')
        key=(s['kind'],s['conditioning'])
        if key in signatures.values():
            if key in indexed:raise ValueError('CONDITION_EVIDENCE_DUPLICATE_CURRENT_STATEMENT')
            indexed[key]=s
    findings=[]
    for code,key in signatures.items():
        candidate=reading['facts']['assumptions'][code]
        s=indexed.get(key);status=s['status'] if s else 'UNSTATED'
        expected={'ADOPTED':True,'NOT_ADOPTED':False,'NOT_INFERRED':None,'PENDING':None,'UNSTATED':None,'CONFLICT':None}[status]
        conflict=status=='CONFLICT'
        verdict='NEEDS_CLARIFICATION' if conflict else 'MATCH' if candidate['value'] is expected else 'READING_ERROR'
        citation_disagreement=False
        if version==2 and verdict=='MATCH' and expected is not None:
            from . import observational_effect_source
            claimed=observational_effect_source.fields(case,reading)['facts.assumptions.'+code]['evidence']
            def overlaps(a,b):
                root=lambda x:re.sub(r'#L\d+$','',x['source_id'])
                left=a['quote'].replace('\r\n','\n').replace('\r','\n').strip()
                right=b['quote'].replace('\r\n','\n').replace('\r','\n').strip()
                return root(a)==root(b) and bool(left and right) and (left in right or right in left)
            # Agreement in truth value alone does not validate a swapped
            # citation. A disagreement triggers a reread, never citation repair.
            citation_disagreement=not any(overlaps(a,b) for a in claimed for b in s['evidence'])
            if citation_disagreement:verdict='READING_ERROR'
        # A mismatch may be the absence of a matching declaration. Cite the
        # actual differently-conditioned statement without treating it as support.
        evidence=(s['evidence'] if s else [e for x in receipt['statements'] for e in x['evidence']])
        if not evidence and candidate['source_ids']:
            from . import observational_effect_source
            evidence=observational_effect_source.fields(case,reading)['facts.assumptions.'+code]['evidence']
        findings.append(dict(field='facts.assumptions.'+code,verdict=verdict,evidence=evidence,
            reason=LABELS[code]+'：原文独立核对状态为'+status+'；给定条件为'+key[1]+
                ('。候选引用与这项条件的独立原文依据不一致，须重新核对引用；不能用另一项条件的原句替代。' if citation_disagreement else
                 '。候选采用状态与该声明不一致，须重新读取；不得把其他给定条件的声明复制到此处。' if verdict=='READING_ERROR' else '。'),
            question=s['question'] if conflict else None))
    # The source-only inventory can expose a duplicate known declaration in
    # the catch-all restriction field. Ask for a complete reread, never delete
    # the restriction or promote its adoption status in program code.
    restrictions=reading['facts'].get('additional_restrictions',[])
    if restrictions:
        from . import observational_effect_source
        locations={v['source_id']:v for v in observational_effect_source.refs(case)['aliases'].values()}
        duplicates=[]
        for restriction in restrictions:
            quotes=[locations[k]['text'] for k in restriction['source_ids'] if k in locations]
            matched=[s for s in receipt['statements'] if any(e['quote'] in quotes for e in s['evidence'])]
            if matched and all((s['kind'],s['conditioning']) in signatures.values() for s in matched):
                duplicates.extend(e for s in matched for e in s['evidence'])
        if duplicates:
            findings.append(dict(field='coverage',verdict='READING_ERROR',evidence=duplicates,
                reason='额外限制引用的原句在独立声明清单中只对应已有条件字段。请核对是否重复放置：尚未决定、未说明或不据此推断须保留在对应条件，不是另一个额外约束。若原文另有真实限制，应完整保留并在独立清单中明确其不同含义；不能直接删除或批准。',question=None))
    return receipt,findings
