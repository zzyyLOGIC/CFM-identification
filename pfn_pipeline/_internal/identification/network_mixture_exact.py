"""Exact small-network compilation and algebraic certificate checking.

The proposer uses local-neighborhood enumeration. The verifier independently
recomputes conditional mixing probabilities by enumerating the *whole* treatment
vector, including own treatment. Verification imports no optimization routines.
Rationals are authoritative; floats are presentation, never a topology tolerance.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as F
from itertools import product
import hashlib
import json

from .rational_arithmetic import fraction, dot, matvec, transpose


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


@dataclass(frozen=True)
class RationalLP:
    candidate_id: str
    A: tuple[tuple[F, ...], ...]
    b: tuple[F, ...]
    q: tuple[F, ...]
    variable_order: tuple[str, ...]

    def bindings(self):
        return dict(candidate_id=self.candidate_id,
                    matrix_fingerprint=fingerprint([[str(x) for x in row] for row in self.A]),
                    rhs_fingerprint=fingerprint([str(x) for x in self.b]),
                    query_fingerprint=fingerprint([str(x) for x in self.q]),
                    variable_order_fingerprint=fingerprint(self.variable_order))


def local_kernel(network, candidate, w, node, p):
    """Proposer's local conditional mixture (iid design implies own-arm invariance)."""
    working = network.working_mapping.state_by_local_assignment[w][node]
    actual = candidate.state_by_local_assignment[w][node]
    sums = {c: {e: F(0) for e in candidate.state_labels} for c in network.working_mapping.state_labels}
    for bits, c in working.items():
        prob = p**bits.count('1') * (1-p)**bits.count('0')
        sums[c][actual[bits]] += prob
    return {c: {e: v/sum(row.values()) for e,v in row.items()} for c,row in sums.items()}


def full_assignment_kernels(network, candidate, w, p):
    """Verifier's separate whole-vector enumerator, conditioning on (T_i,C_i)."""
    ids = network.node_ids
    neighbors = {node: [] for node in ids}
    for left, right in network.undirected_edges:
        neighbors[left].append(right); neighbors[right].append(left)
    for node in ids:
        neighbors[node].sort(key=ids.index)
    counts = {(node,a,c): {e:F(0) for e in candidate.state_labels}
              for node in ids for a in ('0','1') for c in network.working_mapping.state_labels}
    for assignment in product((0,1), repeat=len(ids)):
        bits_by_node = dict(zip(ids,assignment))
        prob = p**sum(assignment) * (1-p)**(len(ids)-sum(assignment))
        for node in ids:
            bits = ''.join(str(bits_by_node[n]) for n in neighbors[node])
            c = network.working_mapping.state_by_local_assignment[w][node][bits]
            e = candidate.state_by_local_assignment[w][node][bits]
            counts[node,str(bits_by_node[node]),c][e] += prob
    return {k: {e:v/sum(row.values()) for e,v in row.items()} for k,row in counts.items()}


def compile_exact(spec, truth, candidate, *, global_replay=False):
    net = spec.network_exposure
    policy = spec.deterministic_policy_oracle
    p = fraction(spec.network_policy_mixture_assignment_design.p)
    keys = [(w,node,a,e) for w in policy.context_ids for node in net.node_ids
            for a in ('0','1') for e in candidate.state_labels]
    index = {key: 2*j for j,key in enumerate(keys)}
    order = tuple(label for w,node,a,e in keys for label in
                  (f'mu[{w},{node},{a},{e}]', f'slack[{w},{node},{a},{e}]'))
    rows=[]; rhs=[]
    for w in policy.context_ids:
        kernels = full_assignment_kernels(net,candidate,w,p) if global_replay else None
        for node in net.node_ids:
            kernel = None if global_replay else local_kernel(net,candidate,w,node,p)
            for a in ('0','1'):
                for c in net.working_mapping.state_labels:
                    row=[F(0)]*len(order)
                    weights = kernels[node,a,c] if global_replay else kernel[c]
                    for e in candidate.state_labels:
                        row[index[w,node,a,e]] = weights[e]
                    rows.append(tuple(row)); rhs.append(fraction(truth.conditional_means[w][node][a][c]))
    for key in keys:
        row=[F(0)]*len(order); j=index[key]; row[j]=row[j+1]=F(1)
        rows.append(tuple(row)); rhs.append(F(1))
    q=[F(0)]*len(order)
    # Independently enumerate policy exposure from the declared graph for replay.
    for w in policy.context_ids:
        actions = dict(zip(policy.node_ids,policy.actions_by_context[w]))
        for node in net.node_ids:
            if global_replay:
                nbrs = sorted([v if u==node else u for u,v in net.undirected_edges
                               if u==node or v==node], key=net.node_ids.index)
            else:
                nbrs = net.neighbor_order()[node]
            bits=''.join(str(actions[nbr]) for nbr in nbrs)
            e=candidate.state_by_local_assignment[w][node][bits]
            q[index[w,node,str(actions[node]),e]] = fraction(truth.context_weights[w])/len(net.node_ids)
    return RationalLP(candidate.mapping_id,tuple(rows),tuple(rhs),tuple(q),order)


def obtain_farkas(lp):
    """Exact phase-I separation, using the same bounded basis-search budget.

    min 1^T v subject to S A z + v = S b, z,v >= 0.
    Here S makes b nonnegative, so z=0,v=S b is feasible. A positive
    optimum and its dual give y with A^T y>=0 and b^T y=-1.
    """
    m,n=len(lp.b),len(lp.q)
    signs=tuple(F(1) if b>=0 else F(-1) for b in lp.b)
    augmented=tuple(tuple(signs[i]*x for x in lp.A[i])+tuple(F(int(i==j)) for j in range(m)) for i in range(m))
    rhs=tuple(signs[i]*lp.b[i] for i in range(m))
    cost=(F(0),)*n+(F(1),)*m
    z,dual=_optimize_block(augmented,rhs,cost,phase_one=True)
    value=dot(cost,z)
    if value<=0:
        raise ValueError('FARKAS_NOT_ESTABLISHED')
    y=tuple(-signs[i]*dual[i]/value for i in range(m))
    check_farkas(lp,y)
    return y


def check_endpoint(lp,z,y,value,side):
    if side not in {'LOWER','UPPER'}:
        raise ValueError('INVALID_CERTIFICATE_SIDE')
    if len(z)!=len(lp.q) or len(y)!=len(lp.b):
        raise ValueError('CERTIFICATE_DIMENSION_MISMATCH')
    if any(x<0 for x in z) or matvec(lp.A,z)!=lp.b:
        raise ValueError('INVALID_PRIMAL_CERTIFICATE')
    lhs=matvec(transpose(lp.A),y)
    if (side=='LOWER' and any(l>r for l,r in zip(lhs,lp.q))) or (side=='UPPER' and any(l<r for l,r in zip(lhs,lp.q))):
        raise ValueError('INVALID_DUAL_CERTIFICATE')
    if not dot(lp.q,z)==dot(lp.b,y)==value:
        raise ValueError('PRIMAL_DUAL_GAP')


def check_farkas(lp,y):
    if len(y)!=len(lp.b):
        raise ValueError('CERTIFICATE_DIMENSION_MISMATCH')
    if any(x<0 for x in matvec(transpose(lp.A),y)) or dot(lp.b,y)!=-1:
        raise ValueError('INVALID_FARKAS_CERTIFICATE')


def union(intervals):
    """Exact finite union; no epsilons, clipping, hull substitution, or grid search."""
    merged=[]
    for lo,hi in sorted(intervals):
        if lo>hi:
            raise ValueError('ENDPOINT_ORDER_FAILURE')
        if not merged or lo>merged[-1][1]:
            merged.append((lo,hi))
        else:
            merged[-1]=(merged[-1][0],max(merged[-1][1],hi))
    return tuple(merged)

# The v0.2.19 proposer uses a small exact basis search, not floating LP status
# or the equality-handling heuristics of an external simplex implementation.
class ExactInfeasibleError(ValueError):
    def __init__(self, y):
        super().__init__('EXACT_INFEASIBLE_WITH_FARKAS')
        self.y = tuple(y)


def _rref_rows(A, b):
    """Return row-echelon equalities and the exact left transformation H."""
    m,n=len(A),len(A[0]); R=[list(row) for row in A]; d=list(b)
    H=[[F(int(i==j)) for j in range(m)] for i in range(m)]
    rank=0
    for col in range(n):
        pivot=next((i for i in range(rank,m) if R[i][col]),None)
        if pivot is None:continue
        R[rank],R[pivot]=R[pivot],R[rank];d[rank],d[pivot]=d[pivot],d[rank];H[rank],H[pivot]=H[pivot],H[rank]
        v=R[rank][col]
        R[rank]=[x/v for x in R[rank]];d[rank]/=v;H[rank]=[x/v for x in H[rank]]
        for i in range(m):
            if i==rank or not R[i][col]:continue
            v=R[i][col]
            R[i]=[a-v*c for a,c in zip(R[i],R[rank])]
            d[i]-=v*d[rank];H[i]=[a-v*c for a,c in zip(H[i],H[rank])]
        rank+=1
        if rank==m:break
    return R,d,H,rank


def _square_solve(A,b):
    R,d,_,rank=_rref_rows(A,b)
    return tuple(d) if rank==len(A) else None


def _blocks(lp):
    """Find independent equality/variable blocks from matrix sparsity only."""
    supports=[{j for j,x in enumerate(row) if x} for row in lp.A]
    varrows=[set() for _ in lp.q]
    for i,S in enumerate(supports):
        for j in S:varrows[j].add(i)
    unseen=set(range(len(lp.q)))
    while unseen:
        todo=[min(unseen)];vs=set();rs=set()
        while todo:
            j=todo.pop()
            if j in vs:continue
            vs.add(j)
            for i in varrows[j]-rs:
                rs.add(i);todo.extend(supports[i]-vs)
        unseen-=vs
        yield tuple(sorted(rs)),tuple(sorted(vs))


def _optimize_block(A,b,c, *, phase_one=False):
    from itertools import combinations
    from math import comb
    R,d,H,r=_rref_rows(A,b)
    m,n=len(A),len(A[0])
    for i in range(r,m):
        if d[i]:
            raise ExactInfeasibleError([-x/d[i] for x in H[i]])
    if comb(n,r)>20000:
        raise ValueError('EXACT_BASIS_RESOURCE_LIMIT')
    feasible_seen=False
    for S in combinations(range(n),r):
        B=tuple(tuple(R[i][j] for j in S) for i in range(r))
        small=_square_solve(B,d[:r])
        if small is None or any(v<0 for v in small):continue
        feasible_seen=True
        z=[F(0)]*n
        for j,v in zip(S,small):z[j]=v
        if not any(c):
            u=(F(0),)*r
        else:
            u=_square_solve(transpose(B),tuple(c[j] for j in S))
            assert u is not None
        y=tuple(sum((H[i][j]*u[i] for i in range(r)),F(0)) for j in range(m))
        if all(a<=v for a,v in zip(matvec(transpose(A),y),c)):
            return tuple(z),y
    if feasible_seen:
        raise ValueError('EXACT_OPTIMAL_BASIS_NOT_FOUND')
    if phase_one:
        raise ValueError('PHASE_I_BASIS_NOT_FOUND')
    # Obtain an exact separating multiplier; no numerical solver status is trusted.
    local=RationalLP('block',tuple(A),tuple(b),tuple(c),tuple(str(i) for i in range(n)))
    y=obtain_farkas(local)
    raise ExactInfeasibleError(y)


def optimize_endpoint(lp, side):
    if side not in {'LOWER','UPPER'}:
        raise ValueError('INVALID_CERTIFICATE_SIDE')
    sign=F(1) if side=='LOWER' else F(-1)
    z=[F(0)]*len(lp.q); y=[F(0)]*len(lp.b)
    for rows,cols in _blocks(lp):
        A=tuple(tuple(lp.A[i][j] for j in cols) for i in rows)
        b=tuple(lp.b[i] for i in rows);c=tuple(sign*lp.q[j] for j in cols)
        try:
            zb,yb=_optimize_block(A,b,c)
        except ExactInfeasibleError as exc:
            fy=[F(0)]*len(lp.b)
            for i,v in zip(rows,exc.y):fy[i]=v
            check_farkas(lp,fy)
            raise ExactInfeasibleError(fy) from exc
        for j,v in zip(cols,zb):z[j]=v
        for i,v in zip(rows,yb):y[i]=sign*v
    v=dot(lp.q,z)
    check_endpoint(lp,z,y,v,side)
    return v,tuple(z),tuple(y)
