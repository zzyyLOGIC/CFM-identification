"""Set-root proof replay using the existing independent ID rule algebra.

Does not invoke the producer. Checks every child, every rule, the reconstructed
expression, and joint-intervention numerical oracles. Old certificates are untouched.
"""
from itertools import product
from cfm_id_bridge.scientific_binding import sha
from . import dag_id_verify as rules
from .dag_joint_contract import VERSION, SYMBOLIC_SAMPLE_VERSION, validate, information_basis


def derivation(cert, p):
    steps = cert['derivation']
    if not steps or len(steps) > 10000:
        return False
    children = [[] for _ in steps]
    stack = []
    for i, step in enumerate(steps):
        d = step.get('depth')
        if type(d) is not int or d < 0 or d > len(stack) or (d == 0 and i != 0):
            return False
        if d:
            children[stack[d - 1]].append(i)
        stack = stack[:d] + [i]
    first = steps[0]
    if not rules._same_graph(first['graph'], p.as_graph()):
        return False
    if sorted(first['treatment']) != sorted(p.treatments) or sorted(first['outcome']) != sorted(p.outcome):
        return False
    for i, step in enumerate(steps):
        nodes, directed, bidirected = rules._step_graph(step)
        y, x = step['outcome'], step['treatment']
        line, condition, derived = rules._line_of(nodes, directed, bidirected, y, x)
        if step['line'] != line or line == 5 or any(step.get('condition', {}).get(k) != v for k, v in condition.items()):
            return False
        expected = rules._expected_children(line, derived, nodes, directed, bidirected, y, x)
        if len(expected) != len(children[i]):
            return False
        for child in children[i]:
            match = next((j for j, want in enumerate(expected) if rules._step_matches(steps[child], want)), None)
            if match is None:
                return False
            expected.pop(match)
    return rules._canonical(rules._rebuild(steps, children)) == rules._canonical(cert['functional'])


def _joint_do(graph, fixed, seed):
    scm = rules._build_scm(graph, seed)
    rest = [n for n in scm['nodes'] if n not in fixed]
    table = {}
    for latent_combo in product(rules.DOMAIN, repeat=len(scm['latents'])):
        latent = dict(zip(scm['latents'], latent_combo))
        for combo in product(rules.DOMAIN, repeat=len(rest)):
            assignment = {**fixed, **dict(zip(rest, combo))}
            key = tuple(sorted(assignment.items()))
            table[key] = table.get(key, 0.) + 0.5 ** len(latent) * rules._probability(scm, assignment, latent, set(fixed))
    return table


def replay(cert, problem, seeds=(7, 11, 23)):
    try:
        p = validate(problem)
        expected_fields = {'version','status','theorem','problem_sha256','target','graph','functional','positivity','derivation','certificate_sha256'}
        if p.version == SYMBOLIC_SAMPLE_VERSION:
            expected_fields.add('information_basis')
            if cert.get('information_basis') != information_basis(p):return False
        if set(cert) != expected_fields or cert['version'] != p.version or cert['status'] != 'POINT' or cert['theorem'] != 'SHPITSER_PEARL_2006_ID':
            return False
        if cert['certificate_sha256'] != sha({k:v for k,v in cert.items() if k != 'certificate_sha256'}) or cert['problem_sha256'] != sha(p):
            return False
        if cert['target'] != dict(treatments=p.treatments, outcome=p.outcome, context=p.context):
            return False
        if not rules._same_graph(cert['graph'], p.as_graph()) or not derivation(cert, p):
            return False
        free = rules._free_variables(cert['functional'])
        if not free <= set(p.treatments + p.outcome) or not rules._trace(cert['functional'], p.nodes)[0]:
            return False
        # Metadata is checked independently from the expression, not trusted as evidence.
        denominators = set()
        def walk(e):
            if e['operation'] == 'CONDITIONAL' and e['given']:
                denominators.add(tuple(e['given']))
            for key in ('of','operand'):
                if isinstance(e.get(key), dict): walk(e[key])
            for item in e.get('operands', []): walk(item)
        walk(cert['functional'])
        expected_positivity = dict(conditional_denominators=[list(d) for d in sorted(denominators)],
            requirement='EVERY_CONDITIONING_EVENT_HAS_POSITIVE_PROBABILITY', overlapping_events=len(denominators))
        if cert['positivity'] != expected_positivity:
            return False
        for seed in seeds:
            nodes, observed = rules.observed_joint(p.as_graph(), seed)
            for xvalues in product(rules.DOMAIN, repeat=len(p.treatments)):
                fixed = dict(zip(p.treatments, xvalues))
                direct = _joint_do(p.as_graph(), fixed, seed)
                for yvalues in product(rules.DOMAIN, repeat=len(p.outcome)):
                    asked = dict(zip(p.outcome, yvalues))
                    truth = sum(v for key, v in direct.items() if all(dict(key)[n] == a for n,a in asked.items()))
                    actual = rules.probability_of(cert['functional'], nodes, observed, asked, env=fixed)
                    if abs(actual - truth) > rules.TOLERANCE:
                        return False
        return True
    except (ValueError, KeyError, TypeError, IndexError, AttributeError, ArithmeticError, RecursionError):
        return False
