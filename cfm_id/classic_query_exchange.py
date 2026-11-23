"""Project replayed identification certificates to estimation intake. No estimators run here."""
from copy import deepcopy
from fractions import Fraction
from itertools import product

from cfm_id_llm.compact_study import digest
from .network_estimate_handoff import probability, ratio


VERSION = 'classic-estimation-registration/1'
SCOPES = ('SYNTHETIC_TEST', 'EXTERNAL_RESEARCH_REVIEW')


class UnsupportedRegistration(ValueError):
    """The verified formula has no registered projection."""


def require(test, reason):
    if not test:
        raise ValueError(reason)


def _positive(value):
    p=probability(value)
    require(p>0,'CLASSIC_QUERY_ZERO_SUPPORT')
    return str(p)


def _linear(evidence, terms):
    target=evidence['claim']['target']
    study_ref=digest(evidence['materials'])
    queries=[]
    weights=[]
    for definition,weight in terms:
        definition=dict(definition,study_ref=study_ref,treatment=target['treatment'],
                        outcome=target['outcome'],context=target['context'])
        queries.append(dict(definition,id=digest(definition)))
        weights.append(str(weight))
    require(queries and len({q['id'] for q in queries})==len(queries),'CLASSIC_QUERY_KEY_COLLISION')
    return dict(mode='ESTIMATE_POINT',target=target,study_ref=study_ref,queries=queries,
                operator_spec=dict(version='population-query/1',forms=[weights]))


def _event_terms(claim,certificate):
    target=claim['target']
    require(len(certificate['results'])==1,'MULTIPLE_CLASSIC_EFFECTS')
    item=certificate['results'][0]
    require(item['identified_functional']==claim['expression'] and item['target_fingerprint']==claim['target_fingerprint'],
            'CLASSIC_EFFECT_CERTIFICATE_MISMATCH')
    for arm in item['constituent_arms']:
        yield dict(kind='person_event_mean',unit=arm['node_id'],own=arm['own_treatment'],exposure=arm['exposure_state'],
                   exposure_rule=target['exposure'],joint_support=_positive(arm['joint_support'])),ratio(arm['coefficient'])


def _policy_terms(claim,certificate):
    t=claim['target']
    require(certificate['identified_functional']==claim['expression'] and certificate['target_fingerprint']==claim['target_fingerprint'],
            'CLASSIC_POLICY_CERTIFICATE_MISMATCH')
    policies={tuple(p['assignment']):probability(p['weight']) for p in t['policies']}
    supported=certificate['policy_support']
    require(len(policies)==len(supported) and
            {tuple(s['assignment']):probability(s['policy_probability']) for s in supported}==policies,
            'CLASSIC_POLICY_SUPPORT_MISMATCH')
    require(len(t['node_order'])==len(t['unit_weights']) and sum(map(ratio,t['unit_weights']))==1,'CLASSIC_POLICY_WEIGHTS')
    for s in supported:
        allocation=s['assignment']
        require(len(allocation)==len(t['node_order']),'CLASSIC_POLICY_COORDINATES')
        for unit,w in zip(t['node_order'],t['unit_weights']):
            if ratio(w):
                require(unit in t['population'],'CLASSIC_POLICY_POPULATION')
                yield dict(kind='person_assignment_mean',unit=unit,assignment=allocation,
                           design_probability=_positive(s['experimental_assignment_probability'])),ratio(w)*policies[tuple(allocation)]


def _adjusted_terms(claim,certificate):
    require(len(certificate['results'])==1,'MULTIPLE_CLASSIC_EFFECTS')
    item=certificate['results'][0]
    require(item['identified_functional']==claim['expression'] and item['target_fingerprint']==claim['target_fingerprint'],
            'CLASSIC_OBSERVATIONAL_CERTIFICATE_MISMATCH')
    signs={(a['node_id'],a['own_treatment'],a['exposure_state']):ratio(a['coefficient']) for a in item['arm_terms']}
    strata=item['support_by_term']
    require(set(signs)=={(a['node'],a['own_treatment'],a['exposure']) for a in strata},'CLASSIC_OBSERVATIONAL_ARMS')
    for arm in strata:
        key=arm['node'],arm['own_treatment'],arm['exposure']
        require(sum(probability(s['population_mass']) for s in arm['local_strata'])==1,'CLASSIC_STRATUM_MASS')
        for s in arm['local_strata']:
            yield dict(kind='person_stratum_event_mean',unit=key[0],own=key[1],exposure=key[2],
                       own_feature=s['own_pretreatment_covariate'],neighbor_feature_count=s['neighbor_covariate_count'],
                       stratum_mass=str(probability(s['population_mass'])),conditional_support=_positive(s['arm_support'])),(
                       signs[key]*probability(s['population_mass']))


def _dag_queries(evidence):
    """Bind the certified binary probability expression to concrete cells, deduplicated across intervention levels."""
    claim=evidence['claim']
    f=claim['functional']
    view=evidence['query_view']
    if not view:
        raise UnsupportedRegistration('REQUESTED_INTERVENTION_VALUES_UNCONFIRMED')
    info=evidence['materials']['information']
    require(f==evidence['certificate']['functional'] and view['kernel_view_checked'] and view['target']==claim['target']
            and f['source_id']==info['source_id'] and info['strictly_positive_joint'],'CLASSIC_DAG_BINDING')
    observed=set(info['variables'])
    queries={}

    def lookup(outcomes,given):
        require(set(outcomes).isdisjoint(given) and (set(outcomes)|set(given))<=observed and outcomes,
                'CLASSIC_DAG_OBSERVED_QUERY')
        definition=dict(kind='observed_probability',outcomes=outcomes,given=given,source_id=f['source_id'])
        key=digest(definition)
        queries[key]=dict(definition,id=key)
        return dict(query=key)

    def compile_expr(expr,env):
        op=expr['operation']
        if op=='SUM':
            b=expr['bind']
            return dict(sum=[compile_expr(expr['summand'],{**env,b['role']:(b['variable'],v)}) for v in b['domain']])
        if op=='PRODUCT':
            return dict(product=[compile_expr(child,env) for child in expr['factors']])
        require(op in ('CONDITIONAL_PROBABILITY','PROBABILITY'),'UNKNOWN_DAG_PROBABILITY_EXPRESSION')
        def resolve(variables):
            values={}
            for item in variables:
                var,value=env[item['value_role']]
                require(var==item['variable'] and var not in values,'CLASSIC_DAG_VARIABLE_BINDING')
                values[var]=value
            return values
        return lookup(resolve(expr['outcomes']),resolve(expr.get('given',[])))

    xname,yname=claim['target']['treatment'],claim['target']['outcome']
    cells=[]
    for x,y in product(view['intervention_values'],view['outcome_values']):
        if f['operation'] in ('BACKDOOR_ADJUSTMENT','COVARIATE_ADJUSTMENT'):
            zs=f['sum_over']
            require(f['treatment']==xname and f['outcome']==yname and f['conditional']['outcomes']==[yname]
                    and set(f['conditional']['given'])=={xname,*zs} and f['marginal']['variables']==zs,
                    'CLASSIC_ADJUSTMENT_BINDING')
            summands=[]
            for config in product((0,1),repeat=len(zs)):
                z=dict(zip(zs,config))
                outcome=lookup({yname:y},{xname:x,**z})
                summands.append(dict(product=[outcome,lookup(z,{})]) if z else outcome)
            expression=dict(sum=summands)
        elif f['operation']=='CLASSICAL_FRONTDOOR':
            expression=compile_expr(f['expression'],dict(intervention_value=(xname,x),outcome_value=(yname,y)))
        else:
            raise UnsupportedRegistration('UNCONNECTED_CLASSIC_DAG_FUNCTIONAL')
        cells.append(dict(intervention={xname:x},outcome={yname:y},expression=expression))
    require(cells and queries,'EMPTY_CLASSIC_DAG_QUERY')
    return dict(mode='ESTIMATE_POINT',target=claim['target'],queries=list(queries.values()),
                operator_spec=dict(version='discrete-probability-kernel/1',cells=cells))


def project_handoff(evidence):
    claim,cert=evidence['claim'],evidence['certificate']
    if claim['kind']=='PARTIAL' and claim.get('representation')=='EXACT_IDENTIFIED_INTERVAL':
        lo,hi=claim['interval']
        require(cert['status']=='PARTIAL' and claim['sharp'] and cert['sharp'] and
                (ratio(lo),ratio(hi))==(ratio(cert['lower']),ratio(cert['upper'])) and ratio(lo)<=ratio(hi),
                'CLASSIC_BOUND_CERTIFICATE_MISMATCH')
        return dict(mode='ESTIMATE_BOUNDS',target=claim['target'],queries=[],lower=str(ratio(lo)),upper=str(ratio(hi)),
                    sharp=True,scope=cert['model_scope'],bound_formula=deepcopy(claim.get('bound_formula')))
    if claim['kind']!='POINT':
        raise UnsupportedRegistration('UNCONNECTED_CLASSIC_RESULT')
    if claim['representation']=='OBSERVED_DISTRIBUTION_FUNCTIONAL':
        return _dag_queries(evidence)
    if claim['representation']=='DESIGN_STANDARDIZED_EFFECT_OBSERVED_FUNCTIONAL':
        return _linear(evidence,_event_terms(claim,cert))
    if claim['target']['kind']=='FINITE_POLICY_MEAN' and 'policy_support' in cert:
        return _linear(evidence,_policy_terms(claim,cert))
    if cert.get('route')=='R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS':
        return _linear(evidence,_adjusted_terms(claim,cert))
    from .classic_network_queries import network_terms
    terms=network_terms(evidence)
    if terms is not None:
        return _linear(evidence,terms)
    raise UnsupportedRegistration('UNCONNECTED_CLASSIC_RESULT')


def check_packet(run_id,packet):
    require(packet['version']==VERSION and packet['case_id']==run_id and
            packet['release_scope'] in SCOPES and packet['purpose']=='REGISTER_FOR_DATA_REVIEW',
            'CLASSIC_REGISTRATION_SCOPE')
    require(digest({k:v for k,v in packet.items() if k!='binding'})==packet['binding'],'CLASSIC_PACKET_BINDING')
    reviews=packet['reviews']
    require(set(reviews)=={'plan','reading','science'} and all(
        r['authority']==packet['release_scope'] and r['decisions'] and set(r['decisions'].values())=={'ACCEPTED'}
        and r['reviewer'] and r['evidence'] for r in reviews.values()),'CLASSIC_APPROVED_REVIEWS_REQUIRED')
    handoff=project_handoff(packet['evidence'])
    require(digest(handoff)==digest(packet['estimate_handoff']),'CLASSIC_QUERY_PROJECTION_MISMATCH')
    return dict(state='QUEUED',run_id=run_id,binding=packet['binding'],query_id=packet['query_id'],
                mode=handoff['mode'],query_count=len(handoff['queries']),query_sha256=digest(handoff),
                release_scope=packet['release_scope'],data_review='PENDING',estimator_executed=False,
                interval=[handoff['lower'],handoff['upper']] if handoff['mode']=='ESTIMATE_BOUNDS' else None)
