"""Integer min-cost transportation on the two Z strata of a binary IV law."""
from fractions import Fraction
from itertools import combinations
from math import lcm
import networkx as nx
from .iv_types import enumerate_types


def problem(law, monotonicity):
    types=enumerate_types(monotonicity)
    # Each response type sends mass from the observed (D,Y) cell under Z=0
    # to its observed cell under Z=1. Parallel edges keep both potential outcomes.
    endpoints=[]
    for t in types:
        left=2*t.d0+t[2+t.d0]
        right=4+2*t.d1+t[2+t.d1]
        endpoints.append((left,right))
    masses=[law[z,d,y] for z in (0,1) for d in (0,1) for y in (0,1)]
    return types,endpoints,masses


def contradiction(endpoints,masses):
    """Weighted Hall cut. All allowed edges from S enter its neighbourhood N(S)."""
    for size in range(1,5):
        for left in combinations(range(4),size):
            right={b for a,b in endpoints if a in left}
            gap=sum(masses[i] for i in left)-sum(masses[j] for j in right)
            if gap>0:
                norm=len(left)+len(right)
                lam=[Fraction(int(i in right)-int(i in left),norm) for i in range(8)]
                return dict(kind="FARKAS_INCOMPATIBILITY", **{"lambda":list(map(float,lam))},
                            normalization_l1=1.0,contradiction_margin=float(gap/norm),
                            exact_lambda=list(map(str,lam)),exact_margin=str(gap/norm))
    return None


def endpoint(types,endpoints,masses,sign):
    scale=lcm(*(mass.denominator for mass in masses))
    graph=nx.MultiDiGraph()
    for i,mass in enumerate(masses):
        graph.add_node(i,demand=(-1 if i<4 else 1)*int(mass*scale))
    costs=[sign*(t.y1-t.y0) for t in types]
    for k,((a,b),cost) in enumerate(zip(endpoints,costs)):
        graph.add_edge(a,b,key=k,weight=cost)
    cost,flow=nx.network_simplex(graph)
    x=[Fraction(flow[a][b][k],scale) for k,(a,b) in enumerate(endpoints)]
    # Residual shortest-path potentials yield dual inequalities, with equality
    # on every edge carrying mass. The verifier independently checks all types.
    residual=nx.DiGraph()
    residual.add_edges_from((8,i,{"weight":0}) for i in range(8))
    for (a,b),c,mass in zip(endpoints,costs,x):
        residual.add_edge(a,b,weight=min(c,residual.get_edge_data(a,b,{"weight":c})["weight"]))
        if mass:
            residual.add_edge(b,a,weight=-c)
    h=nx.single_source_bellman_ford_path_length(residual,8)
    dual=[sign*(-h[i] if i<4 else h[i]) for i in range(8)]
    return Fraction(sign*cost,scale),x,dual
