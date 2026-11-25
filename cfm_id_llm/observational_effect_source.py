"""Default-page source audit around the existing observational reading wire."""
from copy import deepcopy
import json
from importlib.resources import files
from . import network_extended_reading as old,joint_reading as shared
from .compact_study import digest

FAMILY='NETWORK_OBSERVATIONAL_EFFECTS'

def bundle(case):
    return dict(case_id=case['case_id'],question=case['business_question'],documents={x['source_id']:x['text'] for x in case['sources']})

def refs(case):return old.reference_catalog(bundle(case),binding=digest(case),family=old.OBS)

def contract():
    return old.SYSTEM+'\n'+old.GUIDANCE[old.OBS]+'\n'+old.OBSERVATIONAL_OPERATOR_SEMANTICS+'\n'+files('cfm_id_llm').joinpath('resources/observational_effect/SKILL.md').read_text('utf8')

def request(case,feedback=None):
    req=old.make_request(bundle(case),binding=digest(case),family=old.OBS)
    body=json.loads(req['user']);body['reading_feedback_not_evidence']=feedback
    return dict(system_prompt=req['system']+'\n'+files('cfm_id_llm').joinpath('resources/observational_effect/SKILL.md').read_text('utf8')+'\n后续回复可解决未定项，不能覆盖原文明确矛盾。',user_prompt=json.dumps(body,ensure_ascii=False))

def inspect(case,raw):
    wire=raw.get('wire',raw)
    decoded=old.parse(bundle(case),wire,binding=digest(case),family=old.OBS)
    if 'wire' in raw and (raw.get('facts')!=decoded['facts'] or raw.get('family')!=dict(value=FAMILY)):
        raise ValueError('OBSERVATIONAL_CANONICAL_READING_CHANGED')
    return dict(family=dict(value=FAMILY),wire=deepcopy(wire),facts=decoded['facts'])

def fields(case,s):
    locations={v['source_id']:v for v in refs(case)['aliases'].values()}
    out={}
    def walk(x,path):
        if isinstance(x,dict):
            if x.get('source_ids') is not None:
                evidence=[dict(source_id='question' if locations[k]['doc_id']=='__question__' else locations[k]['doc_id'],quote=locations[k]['text']) for k in x['source_ids']]
                out[path]=dict(value=x,evidence=evidence)
            for k,v in x.items():
                if k!='source_ids':walk(v,path+'.'+k)
        elif isinstance(x,list):
            for i,v in enumerate(x):walk(v,path+'.'+str(i))
    walk(s['facts'],'facts')
    # Keep the existing coverage field and historical audit receipt shape.
    # The cross-field question is explicit context, not another semantic claim
    # or a new permission that would invalidate previously replayable receipts.
    out['coverage']=dict(candidate=s['facts'],scientific_declarations_crosscheck=dict(
        assumptions=s['facts']['assumptions'],additional_restrictions=s['facts']['additional_restrictions'],
        unresolved=s['facts']['unresolved'],
        check='将采用态度与全部原文一起核对：同一条件不能一处已采用、另一处待定或不采用。已表达的未知状态不重复成为额外限制。引用不同句子不能掩盖这种冲突；原文已有明确含义而候选错填时判READING_ERROR，不要求用户补条件。'))
    out['target_scope_crosscheck']=dict(candidate=s['facts']['target'],study=s['facts']['study'],conditioning=s['facts']['conditioning'])
    return out

def audit_request(case,s):return shared.audit_request(case,s,field_catalog=fields(case,s),reading_contract=contract())
def check_audit(case,s,raw):return shared.check_audit(case,s,raw,field_catalog=fields(case,s))

def semantic_request(case,s):
    from . import observational_condition_evidence
    return observational_condition_evidence.request(case,s)

def check_semantics(case,s,raw,*,historical=False):
    from . import observational_condition_evidence
    if not historical and (not isinstance(raw,dict) or raw.get('schema_version')!=2):
        raise ValueError('CONDITION_EVIDENCE_VERSION_REQUIRED: 本次独立来源清单须为schema_version=2，完整核对一致性、网络固定、均值存在、交换性及充分性，各项分开引用。')
    return observational_condition_evidence.check(case,s,raw)

def semantic_reconcile_request(case,s,receipt,findings,error=None):
    from . import observational_condition_evidence
    return observational_condition_evidence.reconcile_request(case,s,receipt,findings,error)

binding=shared.binding
