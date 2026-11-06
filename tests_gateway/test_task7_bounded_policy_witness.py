"""Audit regression for a feasible witness that misses the claimed bound."""

from copy import deepcopy
from fractions import Fraction
import unittest

from cfm_id.bounded_policy_solver import solve
from cfm_id.bounded_policy_verify import replay
from cfm_id_bridge.scientific_binding import sha
from tests_gateway.test_bounded_policy import model


class Task7BoundedPolicyWitnessTests(unittest.TestCase):
    def test_feasible_world_missing_claimed_lower_bound_is_rejected(self):
        inquiry, information = model("star7", None)
        original = solve(inquiry, information)
        self.assertEqual(Fraction(original["lower"]), Fraction(3, 7))
        self.assertTrue(replay(original, inquiry=inquiry, information=information))

        changed = deepcopy(original)
        center = next(row for row in changed["cells"] if row["cell"] == ["H", 1, 1])
        self.assertIsNone(center["a4_value"])
        self.assertEqual(Fraction(center["lower_world"]), 0)
        center["lower_world"] = "1/2"

        # Recompute the digest so replay must check the witness itself.
        changed.pop("certificate_sha256")
        changed["certificate_sha256"] = sha(changed)

        target_rows = [
            row for row in changed["cells"] if row["cell"][1:] == [1, 1]
        ]
        self.assertEqual(len(target_rows), 7)
        changed_value = sum(Fraction(row["lower_world"]) for row in target_rows) / 7
        self.assertEqual(changed_value, Fraction(1, 2))
        self.assertNotEqual(changed_value, Fraction(changed["lower"]))
        self.assertFalse(replay(changed, inquiry=inquiry, information=information))