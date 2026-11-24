"""Run an original uploaded math specification in its own study-bound review."""
import json
from cfm_id.direct_iv_evidence import unique_keys
from cfm_id_llm.compact_study import digest
from . import math_library

FORMAT = 'causal-id.math-request/1'


def offered(case):
    if not case:
        return None
    found = []
    for source in case['sources']:
        text = source['text'].strip()
        if not text.startswith('{') or FORMAT not in text:
            continue
        try:
            doc = json.loads(text,object_pairs_hook=unique_keys)
        except (ValueError, RecursionError):
            return dict(error='附件中的数学规格无法完整解析。')
        if not isinstance(doc,dict) or doc.get('format')!=FORMAT:
            continue
        if (set(doc)!={'format','question','operation','problem'} or doc['question']!=case['business_question'] or
            not isinstance(doc['operation'],str) or not isinstance(doc['problem'],dict)):
            return dict(error='请核对规格中的原问、方法和问题字段。每次审核都须重新提交。')
        op=doc['operation']
        if op not in math_library.OPERATIONS and op not in math_library.catalog()['research']:
            return dict(error='所选方法不在本机数学库的登记范围内。')
        found.append(dict(source_id=source['source_id'],operation=op,problem=doc['problem'],
                          binding=digest([case,source['source_id'],op,doc['problem']])))
    if len(found)>1:
        return dict(error='本次有多份数学规格，请明确要审核的那一份。')
    return found[0] if found else None


def authorities(value):
    if isinstance(value,dict):
        for k,v in value.items():
            if k=='authority' and isinstance(v,str):
                yield v
            if k=='synthetic_fixture' and v is True or k=='source' and v=='demo_specification':
                yield 'SYNTHETIC_TEST'
            yield from authorities(v)
    elif isinstance(value,list):
        for v in value:
            yield from authorities(v)


def submit(engine, owner, value):
    parent=engine.get(owner,value['source_run'])
    with parent.lock:
        item=offered(parent.case)
        receipt=(parent.attachment_report or {}).get('receipt') or {}
        if (parent.busy or not parent.result or not receipt.get('ready') or not item or item.get('error')
                or set(value)-{'source_run','source_binding','source_confirmed','review'}):
            raise ValueError('CURRENT_UPLOADED_MATH_PROBLEM_REQUIRED')
        if item['binding']!=value.get('source_binding') or value.get('source_confirmed') is not True:
            raise ValueError('ORIGINAL_TARGET_AND_ALL_MATERIALS_REVIEW_REQUIRED')
        review=value.get('review')
        roles=set(authorities([item['problem'],review]))
        if (not parent.synthetic and roles.intersection({'SYNTHETIC_TEST','TRUSTED_FIXTURE'}) or
                parent.synthetic and review and 'EXTERNAL_RESEARCH_REVIEW' in set(authorities(review))):
            raise ValueError('MATH_REVIEW_AUTHORITY_SCOPE_MISMATCH')
        result=math_library.run(dict(operation=item['operation'],problem=item['problem'],review=review))
        record=dict(operation=item['operation'],source_id=item['source_id'],source_binding=item['binding'],
                    source_confirmed=True,review=review,result=result,estimation_handoff_allowed=False)
        engine.save(parent,'uploaded_math_review',record)
        return result
