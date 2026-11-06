"""Independently check the K4 mean-order relaxation ladder."""

from fractions import Fraction
from itertools import product


def reference_interval(mode):
    """Compute the exact interval for the fixed K4 example."""
    h01 = Fraction(2, 5)
    h10 = Fraction(3, 5)
    candidates = (Fraction(0), h01, h10, Fraction(1))
    differences = []

    # All four nodes have the same constraints and equal weights.
    # The same feasible endpoint pair can be used for all four nodes.
    for h00, h11 in product(candidates, repeat=2):
        own_ok = h00 <= h10 and h01 <= h11
        peers_ok = h00 <= h01 and h10 <= h11

        if mode in ("BOTH", "OWN") and not own_ok:
            continue
        if mode == "BOTH" and not peers_ok:
            continue

        differences.append(h11 - h00)

    return min(differences), max(differences)


def main():
    from cfm_id.mean_order_solver import solve
    from examples.mean_order_fixture import make_problem

    for mode in ("BOTH", "OWN", "NONE"):
        expected = reference_interval(mode)
        certificate = solve(make_problem(mode=mode))
        actual = (
            Fraction(certificate["lower"]),
            Fraction(certificate["upper"]),
        )

        if actual != expected:
            raise AssertionError(
                f"{mode}: expected {expected}, got {actual}"
            )

        lower, upper = actual
        print(f"{mode}: [{lower}, {upper}] — match")


if __name__ == "__main__":
    main()