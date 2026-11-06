"""Independently check R1a arm support and reject a wrong probability."""

from fractions import Fraction
from itertools import combinations
from unittest.mock import patch


def reference_support():
    """Count the D2/E1 arm (1, 0) for node 0 across legal assignments."""
    allocations = list(combinations(("0", "1", "2", "3"), 2))
    hits = 0
    for allocation in allocations:
        treated = set(allocation)
        high_exposure = 2 * len(treated & {"1", "2"}) > 2
        if "0" in treated and not high_exposure:
            hits += 1
    return Fraction(hits, len(allocations)), hits, len(allocations)

def reference_arm_mean_and_observables():
    """Compute the arm target and observed conditional means separately."""
    nodes = ("0", "1", "2", "3")

    def potential_outcome(treated):
        return int("0" in treated and "1" in treated)

    # The three equally likely assignments in the target arm.
    arm_assignments = ({"0", "1"}, {"0", "2"}, {"0", "3"})
    direct_value = Fraction(
        sum(potential_outcome(treated) for treated in arm_assignments),
        len(arm_assignments),
    )

    # Construct observed outcomes for all six equally likely trial lists.
    counts = {}
    successes = {}
    for allocation in combinations(nodes, 2):
        treated = set(allocation)
        own = int("0" in treated)
        exposure = int(len(treated & {"1", "2"}) > 1)
        cell = ("0", own, exposure)
        counts[cell] = counts.get(cell, 0) + 1
        successes[cell] = successes.get(cell, 0) + potential_outcome(treated)

    observed_means = {
        cell: Fraction(successes[cell], count)
        for cell, count in counts.items()
    }
    return direct_value, observed_means

def main():
    from tests.test_randomized_arm_abstraction import (
        ArmSupportEvidence,
        AssignmentSpec,
        CompleteRandomizationDesignV1,
        ExposureSpec,
        IdentificationVerifier,
        NetworkExposureSpec,
        RandomizedNetworkArmBackend,
        SupportEngine,
        make_complete_randomization_arm_spec,
    )

    expected, hits, total = reference_support()
    network = NetworkExposureSpec(
        network_id="proof-gate",
        node_ids=["0", "1", "2", "3"],
        undirected_edges=[("0", "1"), ("0", "2")],
    )
    evidence = SupportEngine.evaluate(
        network=network,
        assignment=AssignmentSpec(CompleteRandomizationDesignV1(m=2)),
        exposure=ExposureSpec("strict_majority_ties_low"),
        node_id="0",
        own_treatment_value=1,
        exposure_value=0,
    )
    if evidence.joint_probability != expected:
        raise AssertionError(f"Expected {expected}, got {evidence.joint_probability}")

    spec = make_complete_randomization_arm_spec(
        network, m=2, node_id="0", own_treatment_value=1, exposure_value=0,
        source="synthetic protocol", evidence="known complete randomization",
        admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE",
    )
    backend = RandomizedNetworkArmBackend()
    verifier = IdentificationVerifier()
    original = backend.solve(spec)
    direct_value, observed_means = reference_arm_mean_and_observables()
    query = original.query
    actual_cell = (
        query.target_node_id,
        query.own_treatment_value,
        query.exposure_value,
    )
    if actual_cell != ("0", 1, 0):
        raise AssertionError(f"Unexpected result arm: {actual_cell}")

    expected_observable = (
        f"E_exp[{spec.query.outcome}_i^obs | W,G,"
        f"{spec.query.treatment}_i=1,S_i=0], i=0"
    )
    if list(original.required_population_objects) != [expected_observable]:
        raise AssertionError(
            f"Unexpected observables: {original.required_population_objects}"
        )

    observed_value = observed_means[actual_cell]
    if observed_value != direct_value:
        raise AssertionError(
            f"Direct arm value {direct_value} != observed mean {observed_value}"
        )

    print(f"Direct design-standardized arm mean: {direct_value}")
    print(f"Observed mean for the returned arm: {observed_value} - match")
    # These probabilities multiply correctly but disagree with the design.
    wrong_support = ArmSupportEvidence(
        Fraction(1, 2), Fraction(1, 2), Fraction(1, 4)
    )
    with patch.object(SupportEngine, "evaluate", return_value=wrong_support):
        changed = backend.solve(spec)
        original_status = verifier.verify(spec, original).verification_status
        changed_status = verifier.verify(spec, changed).verification_status

    if original_status != "VERIFIED" or changed_status != "REJECTED":
        raise AssertionError(f"Unexpected replay results: {original_status}, {changed_status}")

    print(f"Arm support: {hits}/{total} = {expected} - match")
    print("Original result during patch: VERIFIED")
    print("Internally consistent but wrong probability: REJECTED")


if __name__ == "__main__":
    main()