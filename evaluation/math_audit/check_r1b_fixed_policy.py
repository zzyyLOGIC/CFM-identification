"""Check R1b assignment probability, formula, and certificate replay."""

from dataclasses import replace
from fractions import Fraction
from itertools import product

NODES = ("a", "b", "c", "d")
ASSIGNMENT = (1, 0, 1, 0)
WEIGHTS = ("2/3", "0", "1/3", "0")
CONTEXT = "W:business"


def reference_probability():
    """Count equally likely draws for propensities 1/3, 1/2, 2/3, 1/4."""
    hits = total = 0
    for a, b, c, d in product(range(3), range(2), range(3), range(4)):
        assignment = (int(a < 1), int(b < 1), int(c < 2), int(d < 1))
        total += 1
        if assignment == ASSIGNMENT:
            hits += 1
    return Fraction(hits, total), hits, total

def reference_policy_and_observables():
    """Build a synthetic population and compute the two sides separately."""
    types = range(4)  # Four equally likely outcome types.

    def potential_outcomes(assignment, kind):
        a, b, c, _ = assignment
        # Outcomes can depend on another node's treatment.
        return (
            int(a == 1 and c == 1 and kind < 3),
            int(c == 1 and b == 0 and kind == 0),
        )

    # Direct route: intervene first, then average the weighted outcomes.
    direct_value = sum(
        Fraction(2, 3) * y_a + Fraction(1, 3) * y_c
        for y_a, y_c in (potential_outcomes(ASSIGNMENT, kind) for kind in types)
    ) / len(types)

    # Observable route: draw treatment independently of outcome type.
    target_count = successes_a = successes_c = 0
    for a, b, c, d, kind in product(
        range(3), range(2), range(3), range(4), types
    ):
        assignment = (int(a < 1), int(b < 1), int(c < 2), int(d < 1))
        if assignment == ASSIGNMENT:
            y_a, y_c = potential_outcomes(assignment, kind)
            target_count += 1
            successes_a += y_a
            successes_c += y_c

    observed_means = (
        Fraction(successes_a, target_count),
        Fraction(successes_c, target_count),
    )
    return direct_value, observed_means

def main():
    from pfn_pipeline.identification_a4_shadow import _sha
    from pfn_pipeline.identification_policy_r1b import (
        R1bPolicyUnavailable,
        _result_payload,
        identify_verified_fixed_policy,
        replay_verified_fixed_policy,
    )
    from tests.test_verified_fixed_policy_r1b import a4, assumptions, make_study, target

    expected_probability, hits, total = reference_probability()
    expected_observables = (
        "E[Y_{a}^obs | W=W:business, T_vector=(1,0,1,0)]",
        "E[Y_{c}^obs | W=W:business, T_vector=(1,0,1,0)]",
    )
    a_mean, c_mean = expected_observables
    expected_formula = f"2/3 * {a_mean} + 1/3 * {c_mean}"

    study = make_study("D1")
    policy = target(study, weights=WEIGHTS)
    if (tuple(study.node_order), tuple(policy.policy_assignment), policy.context) != (
        NODES, ASSIGNMENT, CONTEXT
    ):
        raise AssertionError("The fixture no longer matches the reference case")

    source = a4(study, nodes=("a", "c"))
    result = identify_verified_fixed_policy(
        study, policy, (source,), assumptions=assumptions()
    )

    actual_probability = Fraction(result.assignment_probability)
    if actual_probability != expected_probability:
        raise AssertionError(f"Unexpected assignment probability: {actual_probability}")
    if tuple(result.required_observables) != expected_observables:
        raise AssertionError(f"Unexpected observables: {result.required_observables}")
    if result.identified_functional != expected_formula:
        raise AssertionError(f"Unexpected formula: {result.identified_functional}")
    direct_value, observed_means = reference_policy_and_observables()
    means_by_term = dict(zip(expected_observables, observed_means, strict=True))

    formula_value = Fraction(0)
    for term in result.identified_functional.split(" + "):
        coefficient, observable = term.split(" * ", 1)
        formula_value += Fraction(coefficient) * means_by_term[observable]

    if formula_value != direct_value:
        raise AssertionError(
            f"Direct policy value {direct_value} != formula value {formula_value}"
        )

    print(f"Observed target means: a={observed_means[0]}, c={observed_means[1]}")
    print(f"Direct policy value: {direct_value}")
    print(f"Project formula evaluated on population means: {formula_value} - match")
    if not replay_verified_fixed_policy(result):
        raise AssertionError("Original certificate failed replay")

    changed = replace(
        result, identified_functional=f"1/3 * {a_mean} + 2/3 * {c_mean}"
    )
    changed = replace(changed, certificate_sha256=_sha(_result_payload(changed)))

    try:
        replay_verified_fixed_policy(changed)
    except R1bPolicyUnavailable as exc:
        if exc.reason_code != "POLICY_CERTIFICATE_REPLAY_MISMATCH":
            raise
    else:
        raise AssertionError("Replay accepted swapped node coefficients")

    print(f"Assignment probability: {hits}/{total} = {actual_probability} - match")
    print("Formula and required observables: match")
    print("Original replay: accepted")
    print("Swapped coefficients after rehash: rejected")


if __name__ == "__main__":
    main()