"""Independently check R2 target-signature support in the Star-5 example."""

from itertools import product
from fractions import Fraction

NODES = ("hub", "l1", "l2", "l3", "l4")
FULL_POLICY = (1, 1, 1, 1, 1)


def reference_support():
    """Count signature matches across the five equally likely trial lists."""
    leaves = set(NODES[1:])
    neighbors = {"hub": leaves}
    neighbors.update({leaf: {"hub"} for leaf in leaves})
    hits = dict.fromkeys(NODES, 0)

    # Each trial list omits exactly one node.
    for omitted in NODES:
        treated = set(NODES) - {omitted}
        for node, adjacent in neighbors.items():
            high_exposure = 2 * len(adjacent & treated) > len(adjacent)
            if node in treated and high_exposure:
                hits[node] += 1

    return sorted(
        ((node, 1, 1), Fraction(hits[node], len(NODES)))
        for node in NODES
    )

def reference_policy_and_means():
    """Compute the Star-5 policy value and signature means independently."""
    leaves = set(NODES[1:])
    neighbors = {"hub": leaves}
    neighbors.update({leaf: {"hub"} for leaf in leaves})
    thresholds = dict(zip(NODES, (4, 1, 2, 3, 4), strict=True))
    types = range(8)

    def signature(node, treated):
        adjacent = neighbors[node]
        return (
            int(node in treated),
            int(2 * len(adjacent & treated) > len(adjacent)),
        )

    def potential_outcome(node, treated, kind):
        own, exposure = signature(node, treated)
        return int(own == 1 and exposure == 1 and kind < thresholds[node])

    # Intervene with all five treated, then average across nodes and types.
    all_treated = set(NODES)
    direct_total = sum(
        potential_outcome(node, all_treated, kind)
        for node, kind in product(NODES, types)
    )
    direct_value = Fraction(direct_total, len(NODES) * len(types))

    # Construct the trial population independently of the full intervention.
    totals = dict.fromkeys(NODES, 0)
    successes = dict.fromkeys(NODES, 0)
    for omitted, kind in product(NODES, types):
        treated = set(NODES) - {omitted}
        for node in NODES:
            if signature(node, treated) == (1, 1):
                totals[node] += 1
                successes[node] += potential_outcome(node, treated, kind)

    means = {
        (node, 1, 1): Fraction(successes[node], totals[node])
        for node in NODES
    }
    return direct_value, means

def main():
    from tests.test_verified_signature_policy_r2 import (
        get,
        replay_verified_signature_policy,
        study,
    )

    expected = reference_support()

    edges = tuple(("hub", leaf) for leaf in NODES[1:])
    context = study("D2", nodes=NODES, edges=edges)
    result = get(context, FULL_POLICY)

    actual = sorted(
        (tuple(cell), Fraction(support))
        for cell, support in zip(
            result.policy_node_classes, result.node_class_support, strict=True
        )
    )

    if Fraction(result.policy_assignment_probability) != 0:
        raise AssertionError("The full policy should have zero trial probability")
    if actual != expected:
        raise AssertionError(f"Expected signature supports {expected}, got {actual}")
    if not replay_verified_signature_policy(result):
        raise AssertionError("Original certificate failed replay")

    direct_value, observed_means = reference_policy_and_means()
    formula_value = sum(
        Fraction(weight) * observed_means[tuple(cell)]
        for cell, weight in zip(
            result.policy_node_classes, result.node_weights, strict=True
        )
    )

    if formula_value != direct_value:
        raise AssertionError(
            f"Direct policy value {direct_value} != formula value {formula_value}"
        )

    print("Observed signature means:",
          tuple(str(observed_means[(node, 1, 1)]) for node in NODES))
    print(f"Direct policy value: {direct_value}")
    print(f"Project policy terms evaluated on population means: {formula_value} - match")
    print("Full policy probability: 0")
    for (node, own, exposure), support in actual:
        print(f"{node} ({own}, {exposure}): {support} - match")
    print("Original replay: accepted")


if __name__ == "__main__":
    main()