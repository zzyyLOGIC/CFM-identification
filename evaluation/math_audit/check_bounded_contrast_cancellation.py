"""Check the shared-mean cancellation example with exact arithmetic."""

from fractions import Fraction


def reference_intervals():
    """Compute both policy ranges and their joint difference."""
    policy_a_values = []
    policy_b_values = []
    joint_differences = []

    # Both policy values are affine in the same x, so x=0 and x=1
    # suffice to find the extrema for this example.
    for x in (Fraction(0), Fraction(1)):
        value_a = x / 2 + Fraction(3, 10)
        value_b = x / 2 + Fraction(1, 10)
        policy_a_values.append(value_a)
        policy_b_values.append(value_b)
        joint_differences.append(value_a - value_b)

    a = (min(policy_a_values), max(policy_a_values))
    b = (min(policy_b_values), max(policy_b_values))
    separate = (a[0] - b[1], a[1] - b[0])
    joint = (min(joint_differences), max(joint_differences))
    return a, b, separate, joint


def main():
    from tests_gateway.test_bounded_contrast import BoundedContrastReference, run_payload

    a, b, separate, joint = reference_intervals()
    case = next(
        case for case in BoundedContrastReference().cases()
        if case.name == "different_policies_cancel_unknown"
    )
    result = run_payload(case.payload)
    bounds = result["bounded_result"]
    actual = (Fraction(bounds["lower"]), Fraction(bounds["upper"]))

    if result["state"] != "POINT" or actual != joint:
        raise AssertionError(
            f"Expected POINT with interval {joint}, "
            f"got {result['state']} with interval {actual}"
        )

    print(f"Policy A: [{a[0]}, {a[1]}]")
    print(f"Policy B: [{b[0]}, {b[1]}]")
    print(f"Separate subtraction: [{separate[0]}, {separate[1]}]")
    print(f"Joint difference: [{actual[0]}, {actual[1]}] - match")


if __name__ == "__main__":
    main()