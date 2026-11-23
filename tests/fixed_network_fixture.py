"""Fixed graph inputs for identification tests. No simulator or model is needed."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path

import numpy as np

from pfn_pipeline.contracts import TaskSpec
from pfn_pipeline._internal.identification.majority_response import make_majority_response_spec
from pfn_pipeline._internal.identification.majority_score import make_majority_score_spec
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec


FIXTURES = Path(__file__).parent / 'fixtures'
DEFAULT_GRAPH = FIXTURES / 'fixed_er_N300_p0.5_seed12345.json'


def load_graph(path):
    record = json.loads(Path(path).read_bytes())
    n = record['n_units']
    first, second = np.triu_indices(n, 1)
    packed = bytes.fromhex(record['upper_hex'])
    if len(packed) != (len(first) + 7) // 8:
        raise ValueError('Unexpected fixed graph length')
    bits = np.unpackbits(np.frombuffer(packed, dtype=np.uint8))
    graph = np.zeros((n, n), dtype=np.uint8)
    graph[first, second] = graph[second, first] = bits[:len(first)]
    if bits[len(first):].any() or hashlib.sha256(graph.tobytes()).hexdigest() != record['adjacency_sha256']:
        raise ValueError('Fixed graph checksum mismatch')
    return graph


def make_score_task(*, adjacency=None, budget=5, treatment_prob=0.5):
    graph = load_graph(DEFAULT_GRAPH) if adjacency is None else adjacency
    n = len(graph)
    nodes = tuple(f'node-{i}' for i in range(n))
    edges = [(nodes[i], nodes[j]) for i, j in zip(*np.nonzero(np.triu(graph, 1)))]
    checksum = hashlib.sha256(np.asarray(graph, dtype=np.uint8).tobytes()).hexdigest()
    network = NetworkExposureSpec(network_id=f'shared-fixed-network-{n}-{checksum[:12]}',
                                  node_ids=list(nodes), undirected_edges=edges)
    response = make_majority_response_spec(network, assignment_probability=str(Fraction(str(treatment_prob))),
        source='synthetic fixed-network regression', evidence='Fixed graph and iid Bernoulli protocol supplied by this test.',
        admitted=True, query_authority='TRUSTED_FIXTURE', synthetic=True)
    spec = make_majority_score_spec(response, budget=budget, budget_mode='at_most')
    spec.query.authority = 'TRUSTED_FIXTURE'
    return TaskSpec(name='Fixed graph score', target_id='synthetic/' + checksum, estimand=spec.query.type,
        target_semantics='design_averaged_majority_response_score_not_rollout_welfare', node_ids=nodes, adjacency=graph,
        assignment_design={'design_type':'randomized_experiment', 'assignment_probability':treatment_prob},
        exposure_definition='strict_majority', outcome_kind='continuous', x=np.zeros((n, 1)),
        treatment=np.arange(n) % 2, outcome=np.arange(n, dtype=float), budget=budget, budget_mode='at_most',
        assumptions=tuple(a.model_dump(mode='python') for a in spec.assumptions),
        identification_spec=spec.model_dump(mode='python'), metadata={'source':'synthetic', 'graph_sha256':checksum})
