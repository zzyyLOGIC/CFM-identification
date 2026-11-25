"""Compare a supplied probability with the question; never issue an ID proof.

This source comparison does not remove restrictions, check graph feasibility,
or authorize an estimation handoff.
"""
from copy import deepcopy
from fractions import Fraction
from cfm_id_llm import joint_reading as reader


def canonical_values(values):
    result={}
    for key,value in values.items():
        if not key.strip() or not value.strip():return None
        try:result[key]=str(Fraction(value))
        except (ValueError,ZeroDivisionError):result[key]=value
    return result


def quantity_key(q):
    if not q['population'].strip() or not q['period'].strip() or not q['context'].strip():return None
    if not q['intervention'] or not q['event']:return None
    parts=[canonical_values(q[k]) for k in ('intervention','event','conditioned_on')]
    if any(p is None for p in parts):return None
    return tuple(tuple(sorted(p.items())) for p in parts)+(q['population'],q['period'],q['context'])


def summarize(case,reading,audit):
    request=reading.get('requested_probability');given=reading.get('given_probabilities',[])
    if not request or not given or reading['family']['value']!='DAG_JOINT':return None
    checked=reader.check_audit(case,reading,audit)
    if any(f['verdict']!='MATCH' for f in checked['findings']):return None
    q=request['value'];key=quantity_key(q)
    target=(reading.get('dag_target') or {}).get('value')
    if not key or not target:return None
    if (target['query_kind']!='INTERVENTIONAL_DISTRIBUTION' or target['conditioned_on']
            or q['conditioned_on'] or set(q['event'])!=set(target['outcome'])
            or set(q['intervention'])!=set(target['treatments'])
            or canonical_values(q['intervention'])!=canonical_values(target['intervention_values'])):return None
    matches=[]
    for row in given:
        if row['status']!='ADOPTED' or row['information_kind']!='EXACT_POPULATION':continue
        supplied_key=quantity_key(row['quantity'])
        if supplied_key is None or supplied_key[:3]!=key[:3] or row.get('scope_matches_question') is False:continue
        literal_scope=supplied_key[3:]==key[3:] and q['period']==target['period']
        # Equivalent prose needs an explicit correspondence, separately audited
        # against the sources. Never infer it with business-specific synonyms.
        if not literal_scope and row.get('scope_matches_question') is not True:continue
        try:value=Fraction(row['value'])
        except (ValueError,ZeroDivisionError):continue
        if not 0<=value<=1:continue
        matches.append((str(value),row['evidence']))
    if not matches:return None
    values=sorted(set(value for value,_ in matches))
    result=dict(version='given-probability-source/1',state='MATCHED_SOURCE_VALUE' if len(values)==1 else 'CONFLICTING_SOURCE_VALUES',
        source_binding=reader.binding(case,reading),quantity=deepcopy(q),
        evidence=deepcopy([e for _,citations in matches for e in citations]),
        mathematical_verification=False,estimation_handoff_allowed=False)
    if len(values)==1:result['value']=values[0]
    else:result['values']=values
    return result
