"""Check the D2/E1 star7 policy bound and its lower-endpoint witness."""

from copy import deepcopy
from fractions import Fraction
from itertools import combinations


def reference():
    """Count target-state support and compute the bounds independently."""
    leaves = tuple(f"L{i}" for i in range(1, 7))
    nodes = ("H", *leaves)
    neighbors = {"H": set(leaves)}
    neighbors.update({leaf: {"H"} for leaf in leaves})

    allocations = list(combinations(nodes, 3))
    hits = dict.fromkeys(nodes, 0)
    for allocation in allocations:
        treated = set(allocation)
        for node, adjacent in neighbors.items():
            high_exposure = 2 * len(adjacent & treated) > len(adjacent)
            if node in treated and high_exposure:
                hits[node] += 1

    support = {
        (node, 1, 1): Fraction(hits[node], len(allocations))
        for node in nodes
    }

    # The six leaf means are 1/2. The unknown center mean is in [0, 1].
    leaf_total = len(leaves) * Fraction(1, 2)
    interval = (leaf_total / len(nodes), (leaf_total + 1) / len(nodes))
    return support, interval


def main():
    from cfm_id_bridge.scientific_binding import sha
    from tests_gateway.test_bounded_policy import model, replay, solve

    expected_support, expected_interval = reference()
    inquiry, information = model("star7", None)
    certificate = solve(inquiry, information)

    cells = {tuple(row["cell"]): row for row in certificate["cells"]}
    actual_support = {
        cell: Fraction(cells[cell]["support"]) for cell in expected_support
    }
    actual_interval = (
        Fraction(certificate["lower"]),
        Fraction(certificate["upper"]),
    )

    if actual_support != expected_support:
        raise AssertionError(f"Unexpected support: {actual_support}")
    if certificate["status"] != "PARTIAL" or actual_interval != expected_interval:
        raise AssertionError(f"Unexpected policy interval: {actual_interval}")
    if not replay(certificate, inquiry=inquiry, information=information):
        raise AssertionError("Original certificate failed replay")

    changed = deepcopy(certificate)
    center = next(row for row in changed["cells"] if row["cell"] == ["H", 1, 1])
    if center["a4_value"] is not None or Fraction(center["lower_world"]) != 0:
        raise AssertionError("Unexpected center row in the original certificate")

    # The changed world stays feasible but gives policy value 1/2, not 3/7.
    center["lower_world"] = "1/2"
    changed.pop("certificate_sha256")
    changed["certificate_sha256"] = sha(changed)

    if replay(changed, inquiry=inquiry, information=information):
        raise AssertionError("Replay accepted a world that misses the lower bound")

    print("Target-state support: all seven nodes match")
    print(f"Policy interval: [{actual_interval[0]}, {actual_interval[1]}] - match")
    print("Original replay: accepted")
    print("Changed lower-endpoint witness: rejected")


if __name__ == "__main__":
    main()