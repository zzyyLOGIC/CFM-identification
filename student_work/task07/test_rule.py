"""Task 07（D3 × E1）的测试：support、brute-force 标准答案与识别规则。

下面的 brute-force 标准答案刻意独立于 ``support.py``：
它自己从原始边表重建邻接、自己枚举完整分配，
因此 ``TwoGroupQuotaDesign`` 里的 bug 无法与标准答案“同错同对”。
"""
from __future__ import annotations

import unittest
from collections import defaultdict
from fractions import Fraction
from itertools import product
from math import comb

import rule
from support import (
    TwoGroupQuotaDesign,
    assignment_probability,
    legal_assignment_count,
)

ASSUMED = rule.EXPERIMENTAL_ASSUMPTIONS


def equal_group_spec(m1: int = 2, m2: int = 2) -> dict:
    return {
        "node_ids": ["a", "b", "c", "d", "e", "f"],
        "edges": [
            ("a", "b"), ("a", "c"), ("a", "d"),
            ("d", "e"), ("d", "f"),
            ("b", "e"), ("c", "f"),
        ],
        "group1": ["a", "b", "c"],
        "group2": ["d", "e", "f"],
        "m1": m1,
        "m2": m2,
    }


def unequal_group_spec(m1: int, m2: int) -> dict:
    return {
        "node_ids": ["a", "b", "c", "d", "e", "f"],
        "edges": [
            ("a", "e"), ("b", "f"), ("c", "e"), ("d", "f"),
            ("a", "b"), ("e", "f"),
        ],
        "group1": ["a", "b", "c", "d"],  # 4 人
        "group2": ["e", "f"],            # 2 人
        "m1": m1,
        "m2": m2,
    }


def build(spec: dict) -> TwoGroupQuotaDesign:
    return TwoGroupQuotaDesign(
        node_ids=spec["node_ids"],
        undirected_edges=spec["edges"],
        group1=spec["group1"],
        group2=spec["group2"],
        m1=spec["m1"],
        m2=spec["m2"],
    )


def independent_oracle(spec: dict, max_assignments: int = 2 ** 8):
    """枚举所有合法分配，累加 P(T_i=t, S_i=s)。

    只使用原始 ``spec``（边表、分组、名额）；无论分布还是图结构，
    都不调用 ``support.py``。
    """
    node_ids = list(spec["node_ids"])
    index = {node: position for position, node in enumerate(node_ids)}
    adjacency = defaultdict(set)
    for left, right in spec["edges"]:
        adjacency[left].add(right)
        adjacency[right].add(left)

    group1, group2 = set(spec["group1"]), set(spec["group2"])
    legal = [
        assignment
        for assignment in product((0, 1), repeat=len(node_ids))
        if sum(assignment[index[node]] for node in group1) == spec["m1"]
        and sum(assignment[index[node]] for node in group2) == spec["m2"]
    ]
    assert legal
    assert len(legal) == comb(len(group1), spec["m1"]) * comb(len(group2), spec["m2"])
    assert len(legal) <= max_assignments

    weight = Fraction(1, len(legal))
    accumulated = defaultdict(Fraction)
    for assignment in legal:
        for node in node_ids:
            own = assignment[index[node]]
            treated_neighbours = sum(assignment[index[j]] for j in adjacency[node])
            degree = len(adjacency[node])
            exposure = int(treated_neighbours > degree // 2)
            accumulated[(node, own, exposure)] += weight
    return accumulated


class SupportTest(unittest.TestCase):
    def test_support_is_a_probability_distribution_per_node(self):
        for spec in (equal_group_spec(2, 2), unequal_group_spec(3, 1)):
            design = build(spec)
            for node in design.node_ids:
                self.assertEqual(sum(design.support_table(node).values()), Fraction(1))

    def test_normal_case_has_all_four_arms_for_well_connected_node(self):
        design = build(equal_group_spec(2, 2))
        self.assertEqual(
            design.support_table("b"),
            {(0, 0): Fraction(1, 9), (0, 1): Fraction(2, 9),
             (1, 0): Fraction(4, 9), (1, 1): Fraction(2, 9)},
        )

    def test_node_a_has_a_zero_support_arm(self):
        design = build(equal_group_spec(2, 2))
        self.assertEqual(design.support("a", 0, 0), Fraction(0))
        self.assertNotIn((0, 0), design.supported_arms("a"))

    def test_brute_force_matches_analytic_support(self):
        for m1, m2 in [(3, 3), (3, 0), (0, 3), (2, 2), (1, 2), (0, 2), (2, 0), (1, 1), (0, 0)]:
            with self.subTest(m1=m1, m2=m2):
                spec = equal_group_spec(m1, m2)
                design, oracle = build(spec), independent_oracle(spec)
                for node in spec["node_ids"]:
                    for t in (0, 1):
                        for s in (0, 1):
                            self.assertEqual(design.support(node, t, s),
                                             oracle.get((node, t, s), Fraction(0)))

    def test_brute_force_matches_for_unequal_groups(self):
        for m1, m2 in [(3, 1), (4, 2), (0, 2), (4, 0), (2, 1)]:
            with self.subTest(m1=m1, m2=m2):
                spec = unequal_group_spec(m1, m2)
                design, oracle = build(spec), independent_oracle(spec)
                for node in spec["node_ids"]:
                    for t in (0, 1):
                        for s in (0, 1):
                            self.assertEqual(design.support(node, t, s),
                                             oracle.get((node, t, s), Fraction(0)))

    def test_assignment_law_is_uniform_on_legal_assignments(self):
        spec = equal_group_spec(2, 2)
        design = build(spec)
        self.assertEqual(legal_assignment_count(design), comb(3, 2) * comb(3, 2))
        total = Fraction(0)
        legal = 0
        for assignment in product((0, 1), repeat=len(spec["node_ids"])):
            probability = assignment_probability(design, assignment)
            total += probability
            if probability > 0:
                legal += 1
                self.assertEqual(probability, Fraction(1, 9))
        self.assertEqual(legal, legal_assignment_count(design))
        self.assertEqual(total, Fraction(1))

    def test_full_and_empty_quota_boundaries(self):
        for m1, m2 in [(0, 0), (3, 3), (0, 3), (3, 0)]:
            with self.subTest(m1=m1, m2=m2):
                spec = equal_group_spec(m1, m2)
                design, oracle = build(spec), independent_oracle(spec)
                expected = tuple(
                    (t, s) for t in (0, 1) for s in (0, 1)
                    if oracle.get(("b", t, s), Fraction(0)) > 0
                )
                self.assertEqual(len(expected), 1)
                self.assertEqual(design.supported_arms("b"), expected)

    def test_isolated_node_only_has_low_exposure(self):
        design = TwoGroupQuotaDesign(
            node_ids=["x", "y", "z"], undirected_edges=[("y", "z")],
            group1=["x", "y"], group2=["z"], m1=1, m2=1,
        )
        self.assertEqual(design.degree("x"), 0)
        self.assertEqual(design.support("x", 0, 1), Fraction(0))
        self.assertEqual(design.support("x", 1, 1), Fraction(0))
        self.assertEqual(design.support("x", 0, 0) + design.support("x", 1, 0), Fraction(1))

    def test_conditional_distribution_rejects_impossible_conditioning(self):
        design = build(equal_group_spec(3, 3))  # B1 的每个单位都被 treated
        with self.assertRaises(ValueError):
            design.conditional_count_distribution("a", 0)

    def test_invalid_quota_is_rejected(self):
        for m1, m2 in [(4, 2), (-1, 2), (2, 4), (2, -1)]:
            with self.assertRaises(ValueError):
                build(equal_group_spec(m1, m2))

    def test_invalid_query_arguments_are_rejected(self):
        design = build(equal_group_spec())
        for node, t, s in [("b", 2, 0), ("b", 0, 2), ("not-a-node", 0, 0)]:
            with self.assertRaises(ValueError):
                design.support(node, t, s)


class RuleTest(unittest.TestCase):
    def test_supported_arm_is_point_identified(self):
        result = rule.identify_arm(build(equal_group_spec()), "b", 1, 0, assumptions=ASSUMED)
        self.assertTrue(result.identified)
        self.assertIn("E[Y_obs_b", result.functional)
        self.assertEqual(result.support, Fraction(4, 9))
        self.assertEqual(result.assumptions_used, rule.REQUIRED_ASSUMPTIONS)

    def test_omitting_assumptions_is_refused(self):
        result = rule.identify_arm(build(equal_group_spec()), "b", 1, 0)
        self.assertFalse(result.identified)
        self.assertEqual(result.reason_code, "ASSUMPTIONS_NOT_SPECIFIED")

    def test_unadmitted_assumptions_stop_the_rule(self):
        result = rule.identify_arm(build(equal_group_spec()), "b", 1, 0,
                                   assumptions=["consistency"])
        self.assertFalse(result.identified)
        self.assertEqual(result.reason_code, "REQUIRED_ASSUMPTIONS_NOT_ADMITTED")
        self.assertIn("full_vector_randomization", result.message)

    def test_zero_support_arm_is_refused(self):
        result = rule.identify_arm(build(equal_group_spec(2, 2)), "a", 0, 0, assumptions=ASSUMED)
        self.assertFalse(result.identified)
        self.assertEqual(result.reason_code, "ZERO_POPULATION_SUPPORT")
        self.assertEqual(result.support, Fraction(0))
        self.assertEqual(result.functional, "")

    def test_invalid_query_is_refused_not_raised(self):
        result = rule.identify_arm(build(equal_group_spec()), "b", 5, 0, assumptions=ASSUMED)
        self.assertFalse(result.identified)
        self.assertEqual(result.reason_code, "INVALID_QUERY")

    def test_contrasts(self):
        design = build(equal_group_spec(2, 2))
        for kind in ("Direct", "Spillover", "Total"):
            with self.subTest(kind=kind):
                result = rule.identify_contrast(design, "b", kind, assumptions=ASSUMED)
                self.assertTrue(result.identified)
                self.assertIn(f"tau_{kind}_b", result.functional)
                self.assertIsNone(result.support)
        total_a = rule.identify_contrast(design, "a", "Total", assumptions=ASSUMED)
        self.assertFalse(total_a.identified)
        self.assertEqual(total_a.reason_code, "ARM_NOT_IDENTIFIED")
        with self.assertRaises(ValueError):
            rule.identify_contrast(design, "b", "NotAContrast", assumptions=ASSUMED)

    def test_supported_arms_helper_matches_rule(self):
        design = build(equal_group_spec())
        for node in design.node_ids:
            for arm in design.supported_arms(node):
                self.assertTrue(rule.identify_arm(design, node, *arm, assumptions=ASSUMED).identified)


if __name__ == "__main__":
    unittest.main()
