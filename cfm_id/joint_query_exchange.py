"""Target-preserving transfer of newly source-reviewed native functionals.

Registration is not estimator execution or proof of scientific truth. The
recipient rebuilds the packet from audited sources and replayed mathematics.
"""
from copy import deepcopy
from fractions import Fraction as F
from cfm_id_llm.compact_study import digest

VERSION='joint-natural-handoff/1'

def operator(report, *, revision=4):
    e=report['joint_entry']
    if e.get('operation')=='NETWORK_LOCAL_BUNDLE':
        if revision!=5:raise ValueError('LOCAL_BUNDLE_QUERY_REVISION_REQUIRED')
        from .local_bundle_exchange import operator as bundle_operator
        return bundle_operator(report)
    c=e['native_result']['certificate'];s=e['reading']
    queries=[];weights=[]
    if c.get('kind')=='DAG_SINGLE_SOURCE':
        if c['native']['state']!='POINT':raise ValueError('NONIDENTIFIABLE_DISTRIBUTION_NOT_ESTIMABLE')
        return dict(mode='REGISTER_CAUSAL_DISTRIBUTION',target=c['target'],
            queries=[dict(id='population_joint',kind='population_joint_law',variables=c['problem']['nodes'])],
            operator_spec=dict(version='dag-single-functional/1',certificate=deepcopy(c)))
    if c.get('kind')=='BINARY_IV_SOURCE':
        return dict(mode='REGISTER_CERTIFIED_FUNCTIONAL',target=c['target'],queries=[],
            operator_spec=dict(version='native-functional/1',certificate=deepcopy(c)),identified_functional=c['answer']['functional'])
    def mean(coef,**coordinates):
        coef=F(coef)
        if not coef:return
        key='q_'+digest(coordinates)[:24]
        if any(q['id']==key for q in queries):
            i=next(i for i,q in enumerate(queries) if q['id']==key);weights[i]=str(F(weights[i])+coef)
        else:queries.append(dict(id=key,**coordinates));weights.append(str(coef))
        return key
    if c.get('kind')=='EXISTING_OBSERVATIONAL_EFFECT':
        result=c['native_outcome']['result'];p=result['proofs'][0];study=result['study'];target=c['target']
        for index,t in enumerate(p['terms']):
            common=dict(kind='conditional_outcome_mean',unit=t['node_id'],own=t['own_treatment'],exposure=t['exposure_state'],
                study=study,signature=result['signature'],target_fingerprint=p['target_fingerprint'])
            if target['averaging']=='OBSERVED_ALLOCATION_CONDITIONAL':
                if F(p['arm_support'][index])<=0:raise ValueError('HANDOFF_NONPOSITIVE_SUPPORT')
                mean(t['coefficient'],**common,conditioning={'fixed_context':target['fixed_context']})
            elif target['averaging']=='SHARED_PRETREATMENT_STRATUM':
                supports=dict(p['support_by_stratum'])
                for row in result['source']['strata']:
                    if F(supports[row['label']][index])<=0:raise ValueError('HANDOFF_NONPOSITIVE_SUPPORT')
                    mean(F(t['coefficient'])*F(row['mass']),**common,conditioning=dict(
                        fixed_context=target['fixed_context'],stratum=row['label'],adjustment_variable=result['source']['adjustment_variable']))
            else:
                record=p['support_by_term'][index]
                if list(record[:3])!=[t['node_id'],t['own_treatment'],t['exposure_state']]:raise ValueError('HANDOFF_TERM_SCOPE_MISMATCH')
                for row in record[3]:
                    if F(row[-1])<=0 or F(row[-2])<=0:raise ValueError('HANDOFF_NONPOSITIVE_SUPPORT')
                    conditioning=dict(fixed_context=target['fixed_context'])
                    if target['averaging']=='SHARED_PRETREATMENT_STRATUM':conditioning.update(stratum=row[0],adjustment_variable=result['source']['adjustment_variable'])
                    else:conditioning.update(own_feature=row[0],neighbor_feature_count=row[1],feature=result['source']['feature_name'])
                    mean(F(t['coefficient'])*F(row[-2]),**common,conditioning=conditioning)
        return dict(mode='ESTIMATE_POINT',target=target,queries=queries,
            operator_spec=dict(version='population-query/1',forms=[weights]),identified_functional=c['identified_functional'])
    if c.get('kind')=='EXISTING_NETWORK_POLICY_COMPOSITION':
        for coefficient,child in zip(c['coefficients'],c['components']):
            child_report=deepcopy(report);child_report['joint_entry']['native_result']['certificate']=child
            part=operator(child_report,revision=revision)
            if part['mode']!='ESTIMATE_POINT':
                return dict(mode='REGISTER_CERTIFIED_FUNCTIONAL',target=c['target'],queries=[],
                    operator_spec=dict(version='native-functional/1',certificate=deepcopy(c)),identified_functional=c['identified_functional'])
            for q,w in zip(part['queries'],part['operator_spec']['forms'][0]):
                if revision==1:
                    mean(F(coefficient)*F(w),**{k:v for k,v in q.items() if k!='id'})
                    continue
                # A policy's fingerprint is provenance, not a coordinate of
                # its conditional mean. Keep every source target while merging
                # only identical study/signature/unit/state/conditioning queries.
                coordinates={k:v for k,v in q.items() if k not in ('id','target_fingerprint','source_target_fingerprints')}
                key=mean(F(coefficient)*F(w),**coordinates)
                targets=([q['target_fingerprint']] if 'target_fingerprint' in q else [])+q.get('source_target_fingerprints',[])
                if key and targets:
                    query=next(x for x in queries if x['id']==key)
                    query['source_target_fingerprints']=sorted(set(query.get('source_target_fingerprints',[])+targets))
        if revision>=3:
            # Exact rational cancellation changes the required data, not the
            # certified functional. Old wire revisions retain their coordinates.
            active=[(q,w) for q,w in zip(queries,weights) if F(w)]
            queries=[q for q,w in active];weights=[w for q,w in active]
        return dict(mode='ESTIMATE_POINT',target=c['target'],queries=queries,
            operator_spec=dict(version='population-query/1',forms=[weights]),identified_functional=c['identified_functional'])
    if c.get('kind')=='EXISTING_NETWORK_POLICY':
        result=c['native_outcome']['result'];parts=result.get('components') or [result]
        probabilities=result.get('policy_probabilities') or ['1']
        for p,prob in zip(parts,probabilities):
            if c['native_outcome'].get('route')=='R2_MEAN_SIGNATURE':
                cells=p['policy_node_classes'];support=p['node_class_support'];node_weights=p['node_weights']
                if not (len(cells)==len(support)==len(node_weights)):raise ValueError('HANDOFF_SIGNATURE_LENGTH_MISMATCH')
                for (node,own,exposure),mass,w in zip(cells,support,node_weights):
                    if F(mass)<=0:raise ValueError('HANDOFF_NONPOSITIVE_SIGNATURE_SUPPORT')
                    mean(F(prob)*F(w),kind='conditional_outcome_mean',unit=node,own=own,exposure=exposure,
                        study=p['study'],signature=p['signature'],target_fingerprint=p['target_fingerprint'],
                        conditioning=dict(fixed_context=p['study']['context_reference']))
                continue
            # A mean-signature proof has a distinct operator. Do not turn it
            # into a full-assignment query with zero support.
            if 'SIGNATURE' in p.get('route',''):
                return dict(mode='REGISTER_CERTIFIED_FUNCTIONAL',target=c['target'],queries=[],
                    operator_spec=dict(version='native-functional/1',certificate=deepcopy(c)),identified_functional=c['identified_functional'])
            t=p['target']
            for node,w in zip(p['study']['node_order'],t['unit_weights']):
                mean(F(prob)*F(w),kind='full_assignment_outcome_mean',unit=node,
                    assignment=t['policy_assignment'],study=p['study'])
        return dict(mode='ESTIMATE_POINT',target=c['target'],queries=queries,
            operator_spec=dict(version='population-query/1',forms=[weights]),identified_functional=c['identified_functional'])
    if c.get('version')=='finite-mean-joint-1':
        return dict(mode='EXACT_BOUNDS' if c['status'] in ('POINT','PARTIAL') else 'INCOMPATIBLE',target=e['problem']['target_description'],queries=[],
            operator_spec=dict(version='exact-bounds/1',lower=c.get('lower'),upper=c.get('upper'),sharp=c.get('sharp',False)))
    if c.get('version')=='symbolic-mean-joint-1':
        queries=[dict(id=x['id'],kind='population_parameter',description=x['description'],lower=x['lower'],upper=x['upper'],source_ids=x['source_ids']) for x in e['problem']['parameters']]
        if e.get('operation')=='NETWORK_OBSERVATIONAL_BOUNDS':
            coordinates={x['id']:x for x in e['projection']['parameter_queries']}
            for query in queries:
                row=coordinates[query['id']]
                query.update(kind='full_assignment_outcome_mean',unit=row['unit'],assignment=row['assignment'],
                    observed_assignment_probability=row['probability'],study=s['study']['value'])
        return dict(mode='ESTIMATE_SYMBOLIC_BOUNDS',target=e['problem']['target_description'],queries=queries,
            operator_spec=dict(version='symbolic-mean-operator/1',problem=e['problem'],certificate=c))
    if c.get('version') in ('dag-joint-id-1','dag-joint-id-2') and c.get('status')=='POINT':
        target=deepcopy(c['target']);query=dict(id='population_joint',kind='population_joint_law',variables=c['graph']['nodes'])
        if revision>=4:
            # ID returns a functional for arbitrary intervention values. Keep
            # the source's requested substitution in the downstream target.
            target['intervention_values']=deepcopy(s['dag_target']['value']['intervention_values'])
        spec=dict(version='dag-functional/1',functional=c['functional'],graph=c['graph'],target=target)
        if c['version']=='dag-joint-id-2':
            target['intervention_values']=deepcopy(s['dag_target']['value']['intervention_values'])
            query.update(numeric_value_available=False,observed_data=deepcopy(c['information_basis']))
            spec.update(version='dag-functional/2',output_kind='SYMBOLIC_FUNCTIONAL_ONLY')
        return dict(mode='REGISTER_CAUSAL_DISTRIBUTION',target=target,queries=[query],operator_spec=spec)
    raise ValueError('CERTIFIED_OPERATOR_NOT_CONNECTED')

def packet(case,report,*,operator_revision=None):
    from .joint_natural_entry import replay
    if not report.get('independent_replay') or not replay(case,report['draft'],report):raise ValueError('JOINT_REPLAY_REQUIRED')
    review=report['review_record']
    if any(v!='ADOPTED' for v in review['decisions'].values()):raise ValueError('JOINT_EXPLICIT_REVIEW_REQUIRED')
    if operator_revision is None:
        operator_revision=5 if report['joint_entry'].get('operation')=='NETWORK_LOCAL_BUNDLE' else 4
    if operator_revision not in (1,2,3,4,5):raise ValueError('UNKNOWN_QUERY_OPERATOR_REVISION')
    handoff=operator(report,revision=operator_revision)
    if handoff['mode']=='INCOMPATIBLE':raise ValueError('INCOMPATIBLE_MODEL_NOT_ESTIMABLE')
    value=dict(version=VERSION,run_id=case['case_id'],source_case=deepcopy(case),source_report=deepcopy(report),
        target=handoff['target'],status=report['joint_entry']['state'],estimate_handoff=handoff,
        release_scope=review['authority'],scientific_approval=review['authority']=='EXTERNAL_RESEARCH_REVIEW',
        production_admission=False,estimation_handoff_allowed=True)
    if operator_revision!=1:value['operator_revision']=operator_revision
    return value

def check_packet(run_id,value):
    if value.get('version')!=VERSION or value.get('run_id')!=run_id:raise ValueError('JOINT_HANDOFF_RUN_MISMATCH')
    rebuilt=packet(value['source_case'],value['source_report'],operator_revision=value.get('operator_revision',1))
    if digest(value)!=digest(rebuilt):raise ValueError('JOINT_HANDOFF_REPLAY_MISMATCH')
    h=value['estimate_handoff']
    receipt=dict(run_id=run_id,state='RECEIVED',binding=value['source_report']['review_record']['binding'],
        query_sha256=digest(h),query_count=len(h['queries']),mode=h['mode'],release_scope=value['release_scope'],
        estimator_executed=False,estimator_status='NOT_SELECTED',production_admission=False)
    if h['mode']=='ESTIMATE_POINT_BUNDLE':
        receipt['targets']=[dict(id=o['id'],query_count=len(o['operands'])) for o in h['operator_spec']['outputs']]
        receipt['target_count']=len(receipt['targets'])
    return receipt

def evaluate(handoff,values):
    """Evaluate a declared functional, not fit an estimator to finite records."""
    mode=handoff['mode']
    if mode=='ESTIMATE_POINT_BUNDLE':
        from .local_bundle_exchange import evaluate as evaluate_bundle
        return evaluate_bundle(handoff,values)
    if mode=='ESTIMATE_POINT':
        from .network_estimate_handoff import execute_handoff
        return execute_handoff(handoff,values)
    if mode=='ESTIMATE_SYMBOLIC_BOUNDS':
        from .symbolic_mean_verify import evaluate as bounds
        op=handoff['operator_spec'];return bounds(op['certificate'],op['problem'],values)
    if mode=='EXACT_BOUNDS':return deepcopy(handoff['operator_spec'])
    raise ValueError('ESTIMATOR_OPERATOR_ADAPTER_REQUIRED')
