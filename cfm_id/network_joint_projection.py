"""Deterministic, complete network mean projection, outside the frozen Core.

Only declared signature-mean models are projected. All realizable coordinates,
not merely target cells, are retained. A source audit and scientific review must
precede execution; this conversion itself grants neither.
"""
from fractions import Fraction as F
from copy import deepcopy
from itertools import product
from pydantic import TypeAdapter
from cfm_id_bridge.scientific_binding import sha
from cfm_id_llm.joint_reading import Design
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec
from pfn_pipeline._internal.identification.randomized_arm_family import AssignmentSpec, ExposureSpec, SupportEngine
from .finite_mean_joint_contract import VERSION, MODEL, validate


def project(reading, source_catalog):
    s=reading; net=s['network']['value']; nodes=net['nodes']
    if not 1<=len(nodes)<=12:raise ValueError('NETWORK_ENUMERATION_LIMIT_12')
    network=NetworkExposureSpec(network_id='source-bound-joint-means',node_ids=nodes,
        undirected_edges=[tuple(e) for e in net['edges']])
    exposure=ExposureSpec(**s['exposure']['value'])
    design=TypeAdapter(Design).validate_python(s['design']['value'])
    if design.kind in ('unequal_probability_fixed_quota_binary_v1','rerandomized_balanced_binary_v1') and len(nodes)>8:
        raise ValueError('EXTENDED_DESIGN_EXACT_ENUMERATION_LIMIT_8')
    assignment=AssignmentSpec(design)
    neighbors={n:set() for n in nodes}
    for a,b in network.undirected_edges:neighbors[a].add(b);neighbors[b].add(a)
    peers={n:exposure.reference_nodes(network,n) for n in nodes}
    peers={n:neighbors[n] if peers[n] is None else peers[n] for n in nodes}
    cells=[(n,a,e) for n in nodes for a in (0,1) for e in sorted({
        exposure.classify(k,len(peers[n])) for k in range(len(peers[n])+1)})]
    if len(cells)>128:raise ValueError('FINITE_MEAN_COORDINATE_LIMIT_128')
    ids={c:'m'+str(i+1) for i,c in enumerate(cells)}
    tables={n:SupportEngine.joint_support(network=network,assignment=assignment,exposure=exposure,node_id=n) for n in nodes}
    support={c:tables[c[0]].get(c[1:],F(0)) for c in cells}
    target=s['network_target']['value']; bounds=s['bounds']['value']
    if set(target['weights'])!=set(nodes) or any(F(w)<0 for w in target['weights'].values()) or sum(map(F,target['weights'].values()))!=1:
        raise ValueError('COMPLETE_NORMALIZED_TARGET_WEIGHTS_REQUIRED')
    if set(bounds['by_node'])!=set(nodes):raise ValueError('ALL_NODE_BOUNDS_REQUIRED')
    coefficients={c:F(0) for c in cells}
    for sign,policy in ((1,target['first']),(-1,target['second'])):
        if policy is None:continue
        if set(policy)!=set(nodes) or any(type(a) is not int or a not in (0,1) for a in policy.values()):
            raise ValueError('COMPLETE_BINARY_POLICY_REQUIRED')
        for n in nodes:
            c=(n,policy[n],exposure.classify(sum(policy[p] for p in peers[n]),len(peers[n])))
            coefficients[c]+=sign*F(target['weights'][n])
    known={}
    for m in s['mean_information']['value']['values']:
        c=(m['node'],m['own'],m['exposure'])
        if c not in ids:raise ValueError('MEAN_CELL_NOT_REALIZABLE')
        if c in known:raise ValueError('DUPLICATE_KNOWN_MEAN')
        if support[c]<=0:raise ValueError('CONDITIONAL_MEAN_ON_ZERO_PROBABILITY_EVENT')
        known[c]=F(m['value'])
    evidence_ids=list(source_catalog)
    coordinates=[]
    for c in cells:
        raw=bounds['by_node'][c[0]]
        if len(raw)!=2:raise ValueError('TWO_FINITE_BOUNDS_REQUIRED')
        lo,hi=map(F,raw)
        if bounds['outcome_domain']=='BINARY':
            if bounds['kind']=='ALMOST_SURE_OUTCOME':
                allowed=[v for v in (F(0),F(1)) if lo<=v<=hi]
                if not allowed:raise ValueError('EMPTY_BINARY_OUTCOME_SUPPORT')
                lo,hi=min(allowed),max(allowed)
            else:lo,hi=max(F(0),lo),min(F(1),hi)
        coordinates.append(dict(id=ids[c],description=f'{c[0]}: own={c[1]}, exposure={c[2]}',
            lower=str(lo),upper=str(hi),known=str(known[c]) if c in known else None,source_ids=evidence_ids))
    constraints=[]
    for i,r in enumerate(s['constraints']):
        terms={}
        for t in r['terms']:
            c=(t['node'],t['own'],t['exposure'])
            if c not in ids:raise ValueError('CONSTRAINT_CELL_NOT_REALIZABLE')
            terms[ids[c]]=terms.get(ids[c],F(0))+F(t['coefficient'])
        constraints.append(dict(id='c'+str(i+1),coefficients={k:str(v) for k,v in terms.items()},
            relation=r['relation'],rhs=str(F(r['rhs'])),adoption=r['status'],source_ids=[e['source_id'] for e in r['evidence']]))
    from .network_mean_orders import expand
    constraints.extend(expand(s.get('mean_orders',[]),cells,ids))
    original_constraints=deepcopy(constraints)
    # Exact substitution of already declared constants, not a relaxed model.
    # Keep every coordinate (including its known-value equality and bounds),
    # every row ID and adoption state; preserve even constant contradictions.
    # This avoids connecting fixed coordinates into unnecessarily huge blocks.
    if s.get('mean_orders'):
        constants={ids[c]:v for c,v in known.items()}
        for row in constraints:
            row['rhs']=str(F(row['rhs'])-sum((F(v)*constants[k] for k,v in row['coefficients'].items() if k in constants),F(0)))
            row['coefficients']={k:v for k,v in row['coefficients'].items() if k not in constants}
    problem=dict(version=VERSION,model=MODEL,outcome_domain=bounds['outcome_domain'],
        context=target['context']+'；时期：'+target['period'],target_description=target['description'],
        target={ids[c]:str(v) for c,v in coefficients.items()},target_offset='0',coordinates=coordinates,
        constraints=constraints,sources=source_catalog,information='POPULATION_MEANS',model_complete=True,
        unresolved=[],additional_restrictions=[])
    validate(problem)
    projection=dict(version='network-joint-projection/1',reading_sha256=sha(reading),
        problem_sha256=sha(problem),cells=[dict(id=ids[c],cell=list(c),support=str(support[c])) for c in cells],
        semantics='ALL_REALIZABLE_NODE_SIGNATURE_MEANS_WITH_DECLARED_LINEAR_CONSTRAINTS',
        realization='BERNOULLI_PER_SIGNATURE' if bounds['outcome_domain']=='BINARY' else 'CONSTANT_PER_SIGNATURE')
    if s.get('mean_orders'):projection['before_known_mean_substitution']=original_constraints
    return problem,projection


def replay_projection(reading, catalog, problem, projection):
    """Rebuild binding, independently enumerate exposure cells and target weights.

Full-assignment probabilities reuse the existing native law, independently of
the analytic neighbor-support engine used for the proposed projection.
"""
    try:
        rebuilt,receipt=project(reading,catalog)
        if sha(rebuilt)!=sha(problem) or sha(receipt)!=sha(projection):return False
        if reading.get('mean_orders'):
            # Check the affine identity separately from the projection builder:
            # old lhs-rhs == new lhs-rhs on the declared known coordinates.
            old=projection['before_known_mean_substitution']
            if len(old)!=len(problem['constraints']):return False
            constants={c['id']:F(c['known']) for c in problem['coordinates'] if c['known'] is not None}
            for a,b in zip(old,problem['constraints']):
                if any(a[k]!=b[k] for k in ('id','relation','adoption','source_ids')):return False
                delta={k:F(a['coefficients'].get(k,0))-F(b['coefficients'].get(k,0)) for k in set(a['coefficients'])|set(b['coefficients'])}
                if any(v and k not in constants for k,v in delta.items()):return False
                if sum((v*constants[k] for k,v in delta.items() if k in constants),F(0))!=F(a['rhs'])-F(b['rhs']):return False
        net=reading['network']['value']; nodes=net['nodes']; pos={n:i for i,n in enumerate(nodes)}
        neighbors={n:set() for n in nodes}
        for a,b in net['edges']:neighbors[a].add(b);neighbors[b].add(a)
        exp=reading['exposure']['value'];kind=exp['grouping']
        if kind=='pretreatment_core_collaborator_majority':neighbors={n:set(exp['core_collaborators'][n]) for n in nodes}
        def cell(n,z):
            k=sum(z[pos[j]] for j in neighbors[n]);d=len(neighbors[n])
            if kind in ('strict_majority_ties_low','pretreatment_core_collaborator_majority'):e=int(2*k>d)
            elif kind=='exact_treated_neighbor_count':e=k
            elif kind=='any_treated_neighbor':e=int(k>0)
            elif kind=='three_level_treated_neighbor_fraction':
                if not d:raise ValueError('UNDEFINED_ISOLATE')
                e=0 if 3*k<d else 1 if 3*k<2*d else 2
            else:raise ValueError('UNSUPPORTED_EXPOSURE')
            return n,z[pos[n]],e
        network=NetworkExposureSpec(network_id='replay',node_ids=nodes,undirected_edges=[tuple(e) for e in net['edges']])
        assignment=AssignmentSpec(TypeAdapter(Design).validate_python(reading['design']['value']))
        mass={}; total=F(0)
        for z in product((0,1),repeat=len(nodes)):
            q=assignment.full_assignment_probability(network,dict(zip(nodes,z)))
            total+=q
            for n in nodes:
                c=cell(n,z);mass[c]=mass.get(c,F(0))+q
        if total!=1:return False
        proposed={tuple(row['cell']):F(row['support']) for row in projection['cells']}
        if mass!=proposed:return False
        ids={tuple(row['cell']):row['id'] for row in projection['cells']}
        target=reading['network_target']['value'];coeff={v:F(0) for v in ids.values()}
        for sign,policy in ((1,target['first']),(-1,target['second'])):
            if policy is None:continue
            z=tuple(policy[n] for n in nodes)
            for n in nodes:coeff[ids[cell(n,z)]]+=sign*F(target['weights'][n])
        return coeff=={k:F(v) for k,v in problem['target'].items()}
    except (ValueError,TypeError,KeyError,ArithmeticError):return False
