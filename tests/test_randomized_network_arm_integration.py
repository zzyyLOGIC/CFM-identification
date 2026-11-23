"""Independent checks for the first production D2xE1 randomized-network arm route.

The ground-truth oracle enumerates legal COMPLETE allocations, not the
production hypergeometric code or its combinatorial verifier. Tests also use
public TaskSpec -> identify -> (optional) replay of the population proof.
"""
from __future__ import annotations

import copy
import random
import unittest
from dataclasses import replace
from fractions import Fraction
from itertools import combinations
from math import comb

import numpy as np

from pfn_pipeline import (
    identify, make_complete_randomization_arm_task, replay_handoff,
    replay_population_identification,
)
from pfn_pipeline._internal.identification.randomized_network_arm import (
    RandomizedNetworkArmBackend, _verify_joint_support_independently,
    joint_support, make_complete_randomization_arm_spec,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec
from pfn_pipeline._internal.identification.verifier import IdentificationVerifier


def network(n: int, edges: list[tuple[int, int]], network_id="fixture") -> NetworkExposureSpec:
    return NetworkExposureSpec(
        network_id=network_id,
        node_ids=[str(i) for i in range(n)],
        undirected_edges=[(str(i), str(j)) for i, j in edges],
    )


def brute_force_joint_support(n: int, m: int, edges: list[tuple[int, int]], i: int, a: int, s: int) -> Fraction:
    """Enumerate original q(u) over C(N,m) allocations; no hypergeom."""
    neighbors = set()
    for left, right in edges:
        if left == i:
            neighbors.add(right)
        elif right == i:
            neighbors.add(left)
    degree = len(neighbors)
    hits = 0
    for treated in combinations(range(n), m):
        treated = set(treated)
        exposure = int(sum(v in treated for v in neighbors) > degree // 2)
        hits += int((i in treated) == bool(a) and exposure == s)
    return Fraction(hits, comb(n, m))


def demo_task(net: NetworkExposureSpec, m: int, i="0", a=1, s=0, *, admitted=True):
    return make_complete_randomization_arm_task(
        net, m=m, node_id=i,
        own_treatment_value=a, exposure_value=s,
        source="documented synthetic protocol",
        evidence="known m-treated assignment fixture and finite potential outcomes",
        admitted=admitted, synthetic=True,
        query_authority="TRUSTED_FIXTURE",
    )


class RandomizedNetworkArmIntegrationTests(unittest.TestCase):
    def test_public_verified_point_without_estimation_handoff(self):
        net = network(3, [(0, 1)])
        task = demo_task(net, 2, a=1, s=1)
        result = identify(task)
        self.assertEqual(result.status, "POINT")
        self.assertEqual(result.verification_status, "VERIFIED")
        self.assertEqual(result.diagnostics["workflow_status"], "IDENTIFIED_NO_ESTIMATION_ADAPTER")
        self.assertIn("no matching estimator", result.diagnostics["handoff_gap"])
        self.assertIsNone(result.estimation_request)
        self.assertEqual(result.result["certificate"]["joint_arm_support_probability"], "1/3")
        self.assertEqual(result.result["certificate"]["treated_quota"], 2)
        self.assertEqual(result.result["identified_functional"]["node_id"], "0")
        self.assertEqual(result.result["identified_functional"]["own_treatment_value"], 1)
        self.assertEqual(result.result["identified_functional"]["exposure_value"], 1)
        self.assertEqual(replay_population_identification(result).verification_status, "VERIFIED")
        with self.assertRaisesRegex(ValueError, "verified estimation handoff"):
            replay_handoff(result)

    def test_small_graph_support_against_independent_allocation_enumeration(self):
        rng = random.Random(20261013)
        cases = 0
        for n in range(2, 9):
            graphs = [[], [(0, 1)]]
            for _ in range(7):
                edges = [(u, v) for u in range(n) for v in range(u + 1, n)
                         if rng.random() < rng.choice((0.10, 0.35, 0.85))]
                graphs.append(edges)
            for edges in graphs:
                degrees = [sum(i in edge for edge in edges) for i in range(n)]
                for m in range(n + 1):
                    for i, degree in enumerate(degrees):
                        for a in (0, 1):
                            for s in (0, 1):
                                with self.subTest(n=n, m=m, i=i, a=a, s=s, graph=edges[:3]):
                                    expected = brute_force_joint_support(n, m, edges, i, a, s)
                                    actual = joint_support(n, m, degree, a, s)
                                    independently_replayed = _verify_joint_support_independently(n, m, degree, a, s)
                                    self.assertEqual(actual, expected)
                                    self.assertEqual(independently_replayed, expected)
                                    cases += 1
        self.assertGreater(cases, 1000)

    def test_arm_specific_zero_support_does_not_mean_partial(self):
        # N=5, quota m=1, center with 4 neighbors; if center is treated,
        # no neighbor can be, hence its high-exposure arm is impossible.
        net = network(5, [(0, 1), (0, 2), (0, 3), (0, 4)])
        zero = identify(demo_task(net, 1, a=1, s=1))
        self.assertEqual(zero.status, "UNSUPPORTED")
        self.assertEqual(zero.result["reason_code"], "ZERO_ARM_SUPPORT")
        self.assertIsNone(zero.estimation_request)
        positive = identify(demo_task(net, 1, a=1, s=0))
        self.assertEqual(positive.status, "POINT")
        self.assertEqual(positive.result["certificate"]["joint_arm_support_probability"], "1/5")

    def test_isolate_is_valid_for_positive_low_arm(self):
        net = network(4, [(1, 2), (2, 3)])
        low = identify(demo_task(net, 2, i="0", a=1, s=0))
        self.assertEqual((low.status, low.verification_status), ("POINT", "VERIFIED"))
        self.assertEqual(low.result["certificate"]["joint_arm_support_probability"], "1/2")
        high = identify(demo_task(net, 2, i="0", a=1, s=1))
        self.assertEqual(high.result["reason_code"], "ZERO_ARM_SUPPORT")

    def test_empty_and_full_quotas_are_valid_designs_with_zero_arms(self):
        net = network(3, [(0, 1), (0, 2), (1, 2)])
        for m, a_good, s_good, a_bad in [(0, 0, 0, 1), (3, 1, 1, 0)]:
            with self.subTest(m=m):
                positive = identify(demo_task(net, m, a=a_good, s=s_good))
                self.assertEqual(positive.status, "POINT")
                self.assertEqual(positive.result["certificate"]["joint_arm_support_probability"], "1")
                zero = identify(demo_task(net, m, a=a_bad, s=s_good))
                self.assertEqual(zero.result["reason_code"], "ZERO_ARM_SUPPORT")

    def test_unresolved_and_rejected_assumptions_are_not_promoted(self):
        net = network(3, [(0, 1), (1, 2)])
        for admitted, status, expected in (
            (False, None, "NEEDS_INPUT"),
            (True, "NOT_ADMITTED", "UNSUPPORTED"),
            (True, "CONTRADICTED", "UNSUPPORTED"),
        ):
            with self.subTest(status=status):
                task = demo_task(net, 1, admitted=admitted)
                if status is not None:
                    src = copy.deepcopy(task.identification_spec)
                    for item in src["assumptions"]:
                        if item["name"] == "full_vector_randomization":
                            item.update(status=status, confirmed=False, source="human_confirmation")
                    task = replace(task, identification_spec=src)
                result = identify(task)
                self.assertEqual(result.status, "UNSUPPORTED")
                self.assertEqual(result.diagnostics["workflow_status"], expected)
                self.assertIsNone(result.estimation_request)

    def test_llm_proposal_cannot_cause_point(self):
        net = network(4, [(0, 1), (0, 2), (0, 3)])
        task = make_complete_randomization_arm_task(
            net, m=2, node_id="0", own_treatment_value=1,
            exposure_value=0, source="human study proposal", evidence="LLM proposal",
            admitted=True, query_authority="PROPOSED",
        )
        result = identify(task)
        self.assertEqual(result.status, "UNSUPPORTED")
        self.assertEqual(result.result["reason_code"], "QUERY_NOT_CONFIRMED")

    def test_query_and_design_fingerprint_changes_block(self):
        net = network(5, [(0, 1), (0, 2), (0, 3), (0, 4)])
        task = demo_task(net, 2, a=1, s=0)
        self.assertEqual(identify(task).status, "POINT")
        with self.assertRaisesRegex(ValueError, "differs"):
            replace(task, assignment_design={"design_type": "randomized_experiment",
                                             "assignment_scheme": "complete_randomization", "treated_quota": 1})
        with self.assertRaisesRegex(ValueError, "differs"):
            replace(task, exposure_definition="treated_neighbor_count_1hop")
        spec = copy.deepcopy(task.identification_spec)
        spec["query"]["own_treatment_value"] = 0
        # TaskSpec carries the exact declared query; a stale-expression edit is
        # rejected at the envelope boundary rather than being trusted by ID.
        with self.assertRaisesRegex(ValueError, "query differs"):
            identify(replace(task, identification_spec=spec))
        spec2 = copy.deepcopy(task.identification_spec)
        spec2["randomized_network_arm_theorem_contract"]["design"]["m"] = 3
        with self.assertRaisesRegex(ValueError, "differs"):
            replace(task, identification_spec=spec2)

    def test_tampered_certificate_is_rejected_by_independent_verifier(self):
        net = network(5, [(0, 1), (0, 2), (0, 3), (0, 4)])
        task = demo_task(net, 2, a=0, s=0)
        original = identify(task)
        self.assertEqual(original.status, "POINT")
        payload = copy.deepcopy(original.result)
        payload["certificate"]["joint_arm_support_probability"] = "999/1000"
        tampered = replace(original, result=payload)
        with self.assertRaisesRegex(ValueError, "proof replay failed"):
            replay_population_identification(tampered)
        spec = make_complete_randomization_arm_spec(
            net, m=2, node_id="0", own_treatment_value=0, exposure_value=0,
            source="documented synthetic protocol",
            evidence="known m-treated assignment fixture and finite potential outcomes",
            admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE",
        )
        self.assertEqual(IdentificationVerifier().verify(
            spec, RandomizedNetworkArmBackend().solve(spec)
        ).verification_status, "VERIFIED")

    def test_out_of_range_design_and_query_rejected(self):
        net = network(3, [(0, 1)])
        for bad_m in (-1, 4, True, 1.5):
            with self.subTest(m=bad_m), self.assertRaises((ValueError, TypeError)):
                demo_task(net, bad_m)
        for bad_a, bad_s in [(2, 0), (0, 2), (True, 0), (1, True)]:
            with self.subTest(a=bad_a, s=bad_s), self.assertRaises(ValueError):
                demo_task(net, 1, a=bad_a, s=bad_s)
        with self.assertRaises(ValueError):
            demo_task(net, 1, i="missing")

    def test_node_specific_target_and_network_fingerprints_differ(self):
        net = network(4, [(0, 1), (0, 2), (1, 3)])
        f = []
        for i, a, s, m in [("0", 1, 0, 2), ("1", 1, 0, 2), ("0", 0, 0, 2), ("0", 1, 1, 2), ("0", 1, 0, 1)]:
            f.append(demo_task(net, m, i=i, a=a, s=s).target_fingerprint)
        self.assertEqual(len(set(f)), len(f))

    def test_same_arm_can_contain_different_potential_outcomes(self):
        # It is legal to have Y_i(u) different for two allocations with the
        # same (T_i,S_i): exposure is a bin for target standardization only.
        net = network(4, [(0, 1), (0, 2)])
        task = demo_task(net, m=2, a=1, s=0)
        result = identify(task)
        self.assertEqual(result.status, "POINT")
        self.assertNotIn("exposure_sufficiency", result.result["assumptions_used"])
        # Potential outcomes depend on WHICH neighbor receives treatment,
        # even if the strict-majority arm is unchanged.
        outcomes = {}
        for tr in combinations(range(4), 2):
            treated = set(tr)
            outcomes[tr] = 10 * int(1 in treated) + 3 * int(2 in treated) + 2 * int(3 in treated)
        arm_outcomes = [value for tr, value in outcomes.items()
                        if 0 in tr and int(len(set(tr) & {1, 2}) > 1) == 0]
        self.assertEqual(len(arm_outcomes), 3)
        self.assertGreater(len(set(arm_outcomes)), 1)
        self.assertEqual(Fraction(sum(arm_outcomes), len(arm_outcomes)), Fraction(15, 3))
        self.assertEqual(Fraction(result.result["certificate"]["joint_arm_support_probability"]), Fraction(3, 6))

    def test_real_study_requires_explicit_human_query_confirmation(self):
        net = network(3, [(0, 1)])
        task = make_complete_randomization_arm_task(
            net, m=2, node_id="0", own_treatment_value=1, exposure_value=1,
            source="written experiment protocol", evidence="signed quota plan and domain assumption declaration",
            synthetic=False, admitted=True, query_authority="HUMAN_CONFIRMED",
        )
        result = identify(task)
        self.assertEqual((result.status, result.verification_status), ("POINT", "VERIFIED"))
        with self.assertRaisesRegex(ValueError, "TRUSTED_FIXTURE"):
            make_complete_randomization_arm_task(
                net, m=2, node_id="0", own_treatment_value=1, exposure_value=1,
                source="uploaded study", evidence="unverified", synthetic=False,
                admitted=True, query_authority="TRUSTED_FIXTURE",
            )

    def test_shared_er300_fixed_graph_can_be_reused_without_downstream_adapter(self):
        from fixed_network_fixture import DEFAULT_GRAPH, load_graph
        a = load_graph(DEFAULT_GRAPH)
        self.assertEqual(a.shape, (300, 300))
        edges = [(i, j) for i in range(300) for j in range(i + 1, 300) if a[i, j]]
        net = network(300, edges, "shared-er300-unit-network")
        point = identify(demo_task(net, 150, i="23", a=1, s=1))
        self.assertEqual((point.status, point.verification_status), ("POINT", "VERIFIED"))
        self.assertGreater(Fraction(point.result["certificate"]["joint_arm_support_probability"]), 0)
        self.assertEqual(point.diagnostics["workflow_status"], "IDENTIFIED_NO_ESTIMATION_ADAPTER")
        self.assertIsNone(point.estimation_request)

    def test_large_er300_no_exponential_enumeration(self):
        # Random graph fixture generated deterministically; no PFN checkpoint.
        rng = np.random.default_rng(20261013)
        x = rng.uniform(size=(300, 300)) < 0.3
        a = np.triu(x, 1)
        a = a | a.T
        edges = [(i, j) for i in range(300) for j in range(i + 1, 300) if a[i, j]]
        net = network(300, edges)
        point = identify(demo_task(net, 150, i="17", a=1, s=1))
        self.assertEqual((point.status, point.verification_status), ("POINT", "VERIFIED"))
        self.assertIsNone(point.estimation_request)
        self.assertGreater(Fraction(point.result["certificate"]["joint_arm_support_probability"]), 0)


if __name__ == "__main__":
    unittest.main()
