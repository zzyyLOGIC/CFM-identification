"""Population operators for a source-bound identification handoff."""
from fractions import Fraction


def ratio(value):
    if isinstance(value, bool):
        raise ValueError("EXPECTED_RATIONAL")
    return Fraction(str(value))


def probability(value):
    p = ratio(value)
    if not 0 <= p <= 1:
        raise ValueError("INVALID_PROBABILITY")
    return p


def execute_handoff(handoff, population_values):
    """Evaluate the exported operator against the supplied population-query interface."""
    if handoff.get("mode") not in ("ESTIMATE_POINT", "ESTIMATE_BOUNDS"):
        raise ValueError("NO_ESTIMABLE_OPERATOR")
    op = handoff["operator_spec"]
    if op.get("version") != "population-query/1" or not op["forms"]:
        raise ValueError("UNKNOWN_POPULATION_OPERATOR")
    names = [q["id"] for q in handoff["queries"]]
    if len(set(names)) != len(names) or not set(names) <= population_values.keys():
        raise ValueError("POPULATION_QUERY_UNAVAILABLE")
    results = []
    for form in op["forms"]:
        if len(form) != len(names):
            raise ValueError("UNBOUND_POPULATION_OPERAND")
        results.append(sum(ratio(w) * ratio(population_values[k]) for w,k in zip(form,names)))
    if handoff["mode"] == "ESTIMATE_POINT":
        if min(results) != max(results):
            raise ValueError("POINT_EQUALITY_NOT_PRESERVED")
        return str(results[0])
    return [str(min(results)), str(max(results))]


def evaluate_from_catalog(handoff, lookup):
    """The consumer can reject every unadvertised population query before evaluating the formula."""
    if handoff.get("mode") not in ("ESTIMATE_POINT", "ESTIMATE_BOUNDS"):
        raise ValueError("NO_ESTIMABLE_OPERATOR")
    return execute_handoff(handoff,{q["id"]:lookup(q) for q in handoff["queries"]})


def make_handoff(target, mode, variables, queries, forms, operator, support):
    h = dict(mode=mode, scope=target["scope"], population=target["population"],
             variables=variables, queries=queries, operator=operator, support=support)
    if mode != "STOP":
        h["operator_spec"] = dict(version="population-query/1",
                                  forms=[[str(w) for w in row] for row in forms])
    return h


def target_for(contrast, quantity):
    return dict(quantity=quantity, scope=contrast["scope"], population=contrast["population"],
                intervention=contrast["intervention"], reference=contrast.get("reference",""),
                outcome=contrast["outcome"], time=contrast["time"], remaining=contrast.get("remaining",""))


def delivery(target, status, formula, value, conditions, handoff, reason, proof, questions=()):
    answer = dict(target=target, status=status, functional=formula, value=value, assumptions=conditions,
                  estimate_handoff=handoff, reason=reason)
    return dict(answer=answer, proof=proof, questions=list(questions))
