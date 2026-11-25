"""Expand source-declared mean order, not individual-outcome monotonicity.

Adjacent inequalities suffice on each finite ordered axis by transitivity.
No statistical assumption is added here and the native LP is unchanged.
"""
def expand(orders,cells,ids):
    rows=[];nodes={c[0] for c in cells}
    for i,o in enumerate(orders):
        if o['status']=='NOT_ADOPTED':continue
        if o['status']!='ADOPTED':raise ValueError('MEAN_ORDER_ADOPTION_REQUIRED')
        if not o['nodes'] or not set(o['nodes'])<=nodes or len(o['nodes'])!=len(set(o['nodes'])):raise ValueError('MEAN_ORDER_NODE_SCOPE_INVALID')
        if o['all_other_states'] is not True or o['axis'] not in ('OWN','PEER') or o['direction'] not in ('NONDECREASING','NONINCREASING'):raise ValueError('MEAN_ORDER_SCOPE_REQUIRED')
        pairs=[]
        for n in o['nodes']:
            states=sorted({e for node,a,e in cells if node==n})
            if o['axis']=='OWN':pairs.extend(((n,0,e),(n,1,e)) for e in states)
            else:pairs.extend(((n,a,lo),(n,a,hi)) for a in (0,1) for lo,hi in zip(states,states[1:]))
        for j,(low,high) in enumerate(pairs):
            rows.append(dict(id=f'order{i+1}_{j+1}',coefficients={ids[low]:'1',ids[high]:'-1'},
                relation='LE' if o['direction']=='NONDECREASING' else 'GE',rhs='0',adoption='ADOPTED',
                source_ids=[e['source_id'] for e in o['evidence']]))
    return rows
