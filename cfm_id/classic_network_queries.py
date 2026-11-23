"""Estimation queries from replayed network certificates and their ordered targets."""
from cfm_id_llm.compact_study import digest
from .classic_query_exchange import require, _positive
from .network_estimate_handoff import probability, ratio


def _weights(target):
    nodes=target['node_order']
    weights=list(map(ratio,target['unit_weights']))
    require(len(weights)==len(nodes)==len(set(nodes)) and min(weights)>=0 and sum(weights)==1,
            'INVALID_POPULATION_WEIGHTS')
    return {node:w for node,w in zip(nodes,weights) if w}


def _policy(certificate, target, method, allocation):
    weights=_weights(target)
    require(len(allocation)==len(target['node_order']), 'INVALID_POLICY_COORDINATES')
    own=dict(zip(target['node_order'],allocation))
    if method=='R1B_FULL_ASSIGNMENT':
        require(allocation==certificate['fixed_policy_treatment'] and
                weights=={k:ratio(v) for k,v in certificate['nonzero_node_weights'].items()},'FULL_POLICY_TARGET_MISMATCH')
        for node,w in weights.items():
            yield dict(kind='person_assignment_mean',unit=node,assignment=allocation,
                       design_probability=_positive(certificate['assignment_probability'])),w
        return
    observational=method.startswith('R3_')
    if not observational:
        require(allocation==certificate['policy_assignment'],'SIGNATURE_POLICY_TARGET_MISMATCH')
    rows=certificate['classes' if observational else 'node_classes']
    require(len(rows)==len(weights) and {r['node']:ratio(r['weight']) for r in rows}==weights,
            'CERTIFIED_POLICY_WEIGHTS_MISMATCH')
    for row in rows:
        unit=row['node']
        require(row['treatment']==own[unit],'CERTIFIED_POLICY_TREATMENT_MISMATCH')
        if method=='R3_FULL_ASSIGNMENT':
            require(row['signature'] is None and probability(row['support'])==probability(certificate['target_observational_probability']),
                    'FULL_OBSERVATIONAL_SUPPORT_MISMATCH')
            query=dict(kind='person_assignment_mean',unit=unit,assignment=allocation)
        else:
            query=dict(kind='person_event_mean',unit=unit,own=own[unit],exposure=row['signature'],exposure_rule=certificate['signature'])
        if observational:
            query.update(conditional_support=_positive(row['support']),source_id=certificate['source_id'],operator=certificate['source_operator'])
        else:
            query['joint_support']=_positive(row['joint_support'])
        yield query,weights[unit]


def _contrast(evidence):
    cert=evidence['certificate']
    target=evidence['claim']['target']
    require(target['operation']=='first_minus_second' and all(cert['target'][k]==target[k] for k in cert['target']),
            'ORDERED_ENDPOINT_TARGET_MISMATCH')
    method={'R1B_ENDPOINT_DIFFERENCE':'R1B_FULL_ASSIGNMENT','R2_ENDPOINT_DIFFERENCE':'R2_MEAN_SIGNATURE'}[evidence['method']]
    expected=[]
    for side,sign in (('first',1),('second',-1)):
        end=evidence['endpoints'][side]
        require(end['route']==method and end['status']=='POINT' and digest(end)==cert['endpoint_sha256'][side],
                'ENDPOINT_CERTIFICATE_MISMATCH')
        for query,weight in _policy(end['identification'],target,method,target[side]):
            expected.append((side,query['unit'],target[side],query.get('own'),query.get('exposure'),weight*sign))
            yield dict(query,endpoint=side),weight*sign
    signed=[(r['side'],r['node'],r['assignment'],r.get('own'),r.get('exposure'),ratio(r['coefficient'])) for r in cert['terms']]
    require(sorted(expected)==sorted(signed),'SIGNED_ENDPOINT_TERMS_MISMATCH')


def _finite_assignment_terms(evidence,events):
    """Expand event means when the available operator supplies means by complete allocation."""
    from pfn_pipeline._internal.identification.randomized_arm_family import ExposureSpec
    from pfn_pipeline.identification_policy_r2 import SignatureSpecV20
    meta=evidence['finite_observation']
    info=evidence['materials']['information'][meta['source_index']]
    study=evidence['materials']['study']
    nodes=study['nodes']
    require(nodes==evidence['claim']['target']['node_order'] and
            info['operator'] in ('FINITE_ASSIGNMENT_LAW','OBSERVATIONAL_ASSIGNMENT_NODE_CONDITIONAL_MEANS') and
            meta['operator']=='OBSERVATIONAL_ASSIGNMENT_NODE_CONDITIONAL_MEANS','FULL_OBSERVATIONAL_OPERATOR_REQUIRED')
    signature=meta['signature']
    cores={k:tuple(v) for k,v in signature['core_collaborators']}
    checked=SignatureSpecV20(**dict(signature,core_collaborators=tuple(sorted(cores.items()))))
    exposure=ExposureSpec(checked.grouping,cores or None)
    neighbors={u:[] for u in nodes}
    for u,v in study['edges']:
        neighbors[u].append(v)
        neighbors[v].append(u)
    law={}
    for row in info['assignment_masses']:
        allocation=row['assignment']
        require(set(allocation)==set(nodes) and set(allocation.values())<={0,1},'FINITE_OBSERVED_ALLOCATION_COORDINATES')
        z=tuple(allocation[u] for u in nodes)
        require(z not in law,'DUPLICATE_OBSERVED_ALLOCATION')
        law[z]=ratio(_positive(row['probability']))
    require(sum(law.values())==1,'INVALID_OBSERVED_ALLOCATION_MASS')
    for q,weight in events:
        u=q['unit']
        require(u in info['outcome_nodes'],'OBSERVED_UNIT_MEAN_UNAVAILABLE')
        focal=nodes.index(u)
        peers=[nodes.index(v) for v in cores.get(u,neighbors[u])]
        selected={z:m for z,m in law.items() if z[focal]==q['own'] and
                  exposure.classify(sum(z[i] for i in peers),len(peers))==q['exposure']}
        support=sum(selected.values())
        require(support>0 and support==ratio(q['conditional_support']),'OBSERVATIONAL_EVENT_SUPPORT_MISMATCH')
        for z,mass in selected.items():
            yield dict(kind='person_assignment_mean',unit=u,assignment=list(z),source_id=meta['source_id'],
                       operator=meta['operator'],conditional_assignment_probability=str(mass),
                       fixed_context=q.get('fixed_context',evidence['claim']['target']['context'])),weight*mass/support


def _observed(claim,cert,*,operator):
    item,=cert['results']
    require(claim['expression']==item['identified_functional'] and claim['target_fingerprint']==item['target_fingerprint'],
            'OBSERVATIONAL_EFFECT_TARGET_MISMATCH')
    target=claim['target']
    arms=item['arm_terms']
    def query(arm):
        require(arm['node_id'] in target['population'],'OBSERVATIONAL_EFFECT_POPULATION_MISMATCH')
        return dict(kind='person_event_mean',unit=arm['node_id'],own=arm['own_treatment'],exposure=arm['exposure_state'],
                    exposure_rule=target['exposure'],fixed_context=target.get('fixed_context'),operator=operator)
    if cert['route']=='R3_P_STANDARDIZED_EFFECTS':
        for arm in arms:
            yield dict(query(arm),source_id=cert.get('A4_source_id'),law_kind=cert.get('A4_law_kind'),
                       conditional_support=_positive(arm['population_support'])),ratio(arm['coefficient'])
        return
    masses={s['label']:probability(s['mass']) for s in cert['strata']}
    rows=item['support_by_stratum']
    require(sum(masses.values())==1 and len(masses)==len(rows) and set(masses)=={s['stratum'] for s in rows},'STRATUM_MASS_MISMATCH')
    for row in rows:
        mass=masses[row['stratum']]
        for arm,support in zip(arms,row['nonzero_term_support'],strict=True):
            yield dict(query(arm),kind='person_stratum_event_mean',stratum=row['stratum'],stratum_mass=str(mass),
                       adjustment_variable=cert['adjustment_variable'],conditional_support=_positive(support),
                       source_id=cert['source_id']),mass*ratio(arm['coefficient'])


def network_terms(evidence):
    method=evidence['method']
    c,a=evidence['certificate'],evidence['claim']
    t=a['target']
    if method in ('R3_P_STANDARDIZED_EFFECTS','R3_EXPOSURE_ADJUSTED_EFFECTS'):
        finite=evidence.get('finite_observation')
        if finite:
            return _finite_assignment_terms(evidence,_observed(a,c,operator=finite['operator']))
        require(c.get('A4_operator') and (method!='R3_P_STANDARDIZED_EFFECTS' or c.get('A4_law_kind') and c.get('A4_source_id')),
                'OBSERVATIONAL_OPERATOR_UNSPECIFIED')
        return _observed(a,c,operator=c['A4_operator'])
    if c.get('identified_functional')!=a.get('expression'):
        return None
    if method=='R1A_RANDOMIZED_ARM':
        row=c['certificate']
        require(t['first']==row['query_arm'] and t['population']==[row['query_node_id']] and
                _weights(t)=={row['query_node_id']:1},'SINGLE_ARM_TARGET_MISMATCH')
        return [(dict(kind='person_event_mean',unit=row['query_node_id'],own=t['first'][0],exposure=t['first'][1],
                      exposure_rule=t['exposure'],joint_support=_positive(row['joint_arm_support_probability'])),1)]
    if method in ('R1B_FULL_ASSIGNMENT','R2_MEAN_SIGNATURE','R3_FULL_ASSIGNMENT','R3_MEAN_SIGNATURE'):
        require(a['target_fingerprint']==c['target_fingerprint'],'POLICY_TARGET_FINGERPRINT_MISMATCH')
        events=_policy(c,t,method,t['assignment'])
        if method=='R3_MEAN_SIGNATURE' and c.get('source_operator')=='OBSERVATIONAL_ASSIGNMENT_NODE_CONDITIONAL_MEANS':
            require(evidence.get('finite_observation') and c['source_id']==evidence['finite_observation']['source_id'],
                    'OBSERVATIONAL_ASSIGNMENT_MEANS_REQUIRED')
            return _finite_assignment_terms(evidence,events)
        return events
    if method in ('R1B_ENDPOINT_DIFFERENCE','R2_ENDPOINT_DIFFERENCE'):
        return _contrast(evidence)
