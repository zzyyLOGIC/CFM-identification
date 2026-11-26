"""Export each replayed local target without mixing distinct questions."""
from copy import deepcopy
from fractions import Fraction as F
from cfm_id_llm.compact_study import digest
from .network_estimate_handoff import ratio

MODE = 'ESTIMATE_POINT_BUNDLE'
VERSION = 'population-query-bundle/1'


def operator(report):
    entry = report['joint_entry']; reading = entry['reading']; parts = entry['parts']
    if entry['state'] != 'BUNDLE_COMPLETE' or not parts or any(p['state'] != 'POINT' for p in parts):
        raise ValueError('LOCAL_BUNDLE_ALL_TARGETS_REQUIRED')
    study = {k: deepcopy(reading[k]['value']) for k in ('study', 'network', 'design', 'exposure')}
    scope = digest(study); queries = {}; outputs = []
    for part in parts:
        evidence = part['native_evidence']; terms = evidence['terms']; support = evidence['population_arm_support']
        if not part['independent_replay'] or len(terms) != len(support):
            raise ValueError('LOCAL_BUNDLE_PROOF_REQUIRED')
        operands = {}
        for term, probability in zip(terms, support):
            if not 0 < F(probability) <= 1:
                raise ValueError('LOCAL_BUNDLE_POSITIVE_SUPPORT_REQUIRED')
            coordinates = dict(kind='conditional_outcome_mean', study_binding=scope,
                unit=term['node_id'], own=term['own_treatment'], exposure=term['exposure_state'])
            key = 'q_' + digest(coordinates)[:24]
            query = dict(id=key, **coordinates, population_joint_support=probability)
            if key in queries and query != queries[key]:
                raise ValueError('LOCAL_BUNDLE_QUERY_CONFLICT')
            queries[key] = query
            operands[key] = operands.get(key, F(0)) + F(term['coefficient'])
        # Cancellation is per output, never between distinct business questions.
        operands = {key: str(value) for key, value in operands.items() if value}
        outputs.append(dict(id=part['id'], question=part['question'], target=deepcopy(part['target']),
            operands=operands, source_index=part['source_index'],
            source_binding=digest(reading['information'][part['source_index']]),
            target_fingerprint=evidence['target_fingerprint'], certificate_sha256=evidence['certificate_sha256'],
            identified_functional=evidence['identified_functional']))
    if len({x['id'] for x in outputs}) != len(outputs):
        raise ValueError('LOCAL_BUNDLE_DUPLICATE_TARGET')
    needed = {key for output in outputs for key in output['operands']}
    return dict(mode=MODE, target=[dict(id=x['id'], question=x['question'], target=deepcopy(x['target'])) for x in outputs],
        queries=[q for key,q in queries.items() if key in needed],
        operator_spec=dict(version=VERSION, study=study, study_binding=scope, outputs=outputs))


def evaluate(handoff, values):
    """Substitute supplied population means, not estimate them from records."""
    spec = handoff['operator_spec']
    if handoff['mode'] != MODE or spec['version'] != VERSION:
        raise ValueError('LOCAL_BUNDLE_OPERATOR_REQUIRED')
    names = [q['id'] for q in handoff['queries']]
    if len(set(names)) != len(names) or not set(names) <= values.keys():
        raise ValueError('LOCAL_BUNDLE_MEAN_UNAVAILABLE')
    results = {}
    for output in spec['outputs']:
        if output['id'] in results or not set(output['operands']) <= set(names):
            raise ValueError('LOCAL_BUNDLE_OUTPUT_BINDING')
        results[output['id']] = str(sum((ratio(w) * ratio(values[key]) for key,w in output['operands'].items()), F(0)))
    return results
