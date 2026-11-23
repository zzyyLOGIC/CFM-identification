"""E2 exposure extension: complete randomization, independent full-draw oracle.

The oracle enumerates actual size-m assignments, computes K_i/degree_i via
Fraction independently of the library's binning/support/replay functions.
"""
from __future__ import annotations

import copy
import random
import unittest
from dataclasses import replace
from fractions import Fraction
from itertools import combinations
from math import comb

from pfn_pipeline import (
    identify, make_complete_randomization_arm_task,
    make_two_group_quota_arm_task, replay_handoff, replay_population_identification,
)
from pfn_pipeline._internal.identification.randomized_network_arm import (
    GROUP_E2, RandomizedNetworkArmBackend,
    joint_support, joint_support_two_group,
    _verify_joint_support_independently, _verify_two_group_joint_support_independently,
    make_complete_randomization_arm_spec,
)
from pfn_pipeline._internal.identification.schemas import (
    NetworkExposureSpec, CompleteRandomizationDesignV1,
    TwoGroupFixedQuotaDesignV1, IdentificationResult as BackendResult,
)
from pfn_pipeline._internal.identification.verifier import IdentificationVerifier

EXPOSURE = "three_level_treated_neighbor_fraction"


def net(n, edges, network_id="d2-e2-independent-oracle"):
    return NetworkExposureSpec(
        network_id=network_id, node_ids=[str(x) for x in range(n)],
        undirected_edges=[(str(x), str(y)) for x, y in edges],
    )


def oracle_e2(n, m, edges, i):
    """Return all six joint arms, counting legal ORIGINAL full assignments."""
    nbrs = {v if u == i else u for u, v in edges if i in (u, v)}
    d = len(nbrs)
    if not d:
        raise ValueError("fraction undefined for isolate")
    counts = {(a, s): 0 for a in (0, 1) for s in (0, 1, 2)}
    for treated_tuple in combinations(range(n), m):
        treated = set(treated_tuple)
        a = int(i in treated)
        ratio = Fraction(sum(j in treated for j in nbrs), d)
        exposure = 0 if ratio < Fraction(1, 3) else 1 if ratio < Fraction(2, 3) else 2
        counts[(a, exposure)] += 1
    return {arm: Fraction(v, comb(n, m)) for arm, v in counts.items()}


def oracle_d3(n, groups, quotas, edges, i):
    nbrs = {v if u == i else u for u, v in edges if i in (u, v)}
    d = len(nbrs)
    if not d:
        raise ValueError("fraction undefined for isolate")
    counts = {(a, s): 0 for a in (0, 1) for s in (0, 1, 2)}
    denominator = comb(len(groups[0]), quotas[0]) * comb(len(groups[1]), quotas[1])
    for first in combinations(groups[0], quotas[0]):
        for second in combinations(groups[1], quotas[1]):
            treated = set(first) | set(second)
            a = int(str(i) in treated)
            ratio = Fraction(sum(str(j) in treated for j in nbrs), d)
            exposure = 0 if ratio < Fraction(1, 3) else 1 if ratio < Fraction(2, 3) else 2
            counts[(a, exposure)] += 1
    return {arm: Fraction(v, denominator) for arm, v in counts.items()}


def fixture(network, m=2, i="0", a=1, s=1, *, grouping=EXPOSURE, admitted=True, query_authority="TRUSTED_FIXTURE"):
    return make_complete_randomization_arm_task(
        network, m=m, node_id=i, own_treatment_value=a,
        exposure_value=s, exposure_definition=grouping,
        source="known synthetic fixed-size randomization protocol",
        evidence="known fixed graph, assignment quota and outcome integrability",
        admitted=admitted, synthetic=True, query_authority=query_authority,
    )


class ThreeLevelExposureTests(unittest.TestCase):
    def test_six_arms_golden_case_and_public_contract(self):
        network = net(5, [(0, 1), (0, 2), (0, 3)])
        expected = {
            (0, 0): Fraction(0), (0, 1): Fraction(3, 10), (0, 2): Fraction(3, 10),
            (1, 0): Fraction(1, 10), (1, 1): Fraction(3, 10), (1, 2): Fraction(0),
        }
        self.assertEqual(oracle_e2(5, 2, [(0, 1), (0, 2), (0, 3)], 0), expected)
        for (a, s), target_support in expected.items():
            with self.subTest(a=a, s=s):
                task = fixture(network, a=a, s=s)
                self.assertEqual(task.exposure_definition, EXPOSURE)
                self.assertEqual(task.assignment_design["treated_quota"], 2)
                self.assertEqual(task.identification_spec["randomized_network_arm_theorem_contract"]["grouping"], GROUP_E2)
                result = identify(task)
                self.assertIsNone(result.estimation_request)
                self.assertEqual(result.result["query"]["reference_exposure_definition"], "treated_neighbor_fraction_three_level")
                if target_support:
                    self.assertEqual((result.status, result.verification_status), ("POINT", "VERIFIED"))
                    self.assertEqual(result.diagnostics["workflow_status"], "IDENTIFIED_NO_ESTIMATION_ADAPTER")
                    self.assertEqual(Fraction(result.result["certificate"]["joint_arm_support_probability"]), target_support)
                    self.assertEqual(result.result["identified_functional"]["exposure_value"], s)
                    self.assertIn("3K<d", result.result["identified_functional"]["grouping"])
                    self.assertEqual(replay_population_identification(result).verification_status, "VERIFIED")
                    with self.assertRaisesRegex(ValueError, "verified estimation handoff"):
                        replay_handoff(result)
                else:
                    self.assertEqual(result.status, "UNSUPPORTED")
                    self.assertEqual(result.result["reason_code"], "ZERO_ARM_SUPPORT")

    def test_full_enumeration_independent_vs_proposer_and_verifier(self):
        rng = random.Random(20261014)
        cases = 0
        for n in range(2, 10):
            graphs = [[(0, i) for i in range(1, n)],
                      [(x, y) for x in range(n) for y in range(x + 1, n)]]
            for _ in range(5):
                p = rng.choice((0.1, 0.35, 0.7))
                graphs.append([(u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < p])
            for edges in graphs:
                for m in range(n + 1):
                    for i in range(n):
                        degree = sum(i in edge for edge in edges)
                        if not degree:
                            continue
                        reference = oracle_e2(n, m, edges, i)
                        self.assertEqual(sum(reference.values()), 1)
                        for (a, s), expected in reference.items():
                            with self.subTest(n=n, m=m, i=i, arm=(a, s), d=degree):
                                actual = joint_support(n, m, degree, a, s, GROUP_E2)
                                replayed = _verify_joint_support_independently(n, m, degree, a, s, GROUP_E2)
                                self.assertEqual(actual, expected)
                                self.assertEqual(replayed, expected)
                                cases += 1
        self.assertGreater(cases, 8000)

    def test_boundaries_are_exact_and_middle_can_be_empty(self):
        # degree 3: count k=0 low, k=1 middle, k>=2 high.
        self.assertEqual(oracle_e2(4, 1, [(0, 1), (0, 2), (0, 3)], 0), {
            (0, 0): Fraction(0), (0, 1): Fraction(3, 4), (0, 2): Fraction(0),
            (1, 0): Fraction(1, 4), (1, 1): Fraction(0), (1, 2): Fraction(0),
        })
        # degree 1: low at k=0 and high at k=1; medium is structurally impossible.
        small = net(3, [(0, 1)])
        for a in (0, 1):
            zero_mid = identify(fixture(small, m=1, a=a, s=1))
            self.assertEqual(zero_mid.result["reason_code"], "ZERO_ARM_SUPPORT")
        # d=6: exactly k=2 is medium; k=4 is high.
        edges = [(0, j) for j in range(1, 7)]
        probs = oracle_e2(7, 2, edges, 0)
        self.assertEqual(probs[(0, 1)], Fraction(15, 21))
        self.assertEqual(probs[(0, 0)], Fraction(0))

    def test_isolated_node_is_unsupported_not_silently_low(self):
        network = net(3, [(1, 2)])
        for a in (0, 1):
            for s in (0, 1, 2):
                answer = identify(fixture(network, i="0", a=a, s=s))
                self.assertEqual(answer.result["reason_code"], "EXPOSURE_UNDEFINED_FOR_ISOLATED_NODE")
                self.assertIsNone(answer.estimation_request)
        # The old E1 zero-degree rule retains its original meaning.
        old = identify(fixture(network, i="0", a=0, s=0, grouping="strict_majority"))
        self.assertEqual((old.status, old.verification_status), ("POINT", "VERIFIED"))

    def test_invalid_e2_states_or_definition_fail_closed(self):
        network = net(4, [(0, 1), (0, 2), (0, 3)])
        for bad in (True, -1, 3, "high", 1.0):
            with self.subTest(bad=bad), self.assertRaises((ValueError, TypeError)):
                fixture(network, s=bad)
        with self.assertRaises((ValueError, TypeError)):
            fixture(network, grouping="unknown")
        # Old majority E1 still rejects exposure state s=2.
        with self.assertRaises((ValueError, TypeError)):
            fixture(network, s=2, grouping="strict_majority")

    def test_target_fingerprint_binds_exposure_and_design(self):
        network = net(5, [(0, 1), (0, 2), (0, 3)])
        e1 = fixture(network, a=1, s=0, grouping="strict_majority")
        e2 = fixture(network, a=1, s=0)
        self.assertNotEqual(e1.target_fingerprint, e2.target_fingerprint)
        self.assertNotEqual(e1.target_id, e2.target_id)
        self.assertNotEqual(e1.identification_spec["query"]["reference_exposure_definition"], e2.identification_spec["query"]["reference_exposure_definition"])
        with self.assertRaisesRegex(ValueError, "assignment/exposure/target differs"):
            replace(e2, exposure_definition="strict_majority")
        with self.assertRaisesRegex(ValueError, "assignment/exposure/target differs"):
            replace(e1, exposure_definition=EXPOSURE)
        with self.assertRaisesRegex(ValueError, "assignment/exposure/target differs"):
            replace(e2, target_fingerprint=e1.target_fingerprint)
        # Even coordinated edits of public and internal grouping cannot reuse stale fingerprint.
        mutated = copy.deepcopy(e2.identification_spec)
        mutated["randomized_network_arm_theorem_contract"]["grouping"] = "strict_majority_ties_low"
        task = replace(e2, identification_spec=mutated, exposure_definition="strict_majority")
        result = identify(task)
        self.assertEqual(result.result["reason_code"], "EXPOSURE_QUERY_CONTRACT_MISMATCH")

    def test_proof_certificate_and_program_tampering_rejected(self):
        network = net(5, [(0, 1), (0, 2), (0, 3)])
        original = identify(fixture(network, a=0, s=2))
        self.assertEqual((original.status, original.verification_status), ("POINT", "VERIFIED"))
        alterations = [
            ("certificate", "joint_arm_support_probability", "99/100"),
            ("certificate", "exposure_grouping", "strict_majority_ties_low"),
            ("certificate", "source_spec_sha256", "stale"),
            ("identified_functional", "grouping", "K_i>floor(degree_i/2);ties=0"),
            ("identified_functional", "exposure_value", 1),
        ]
        for section, field, replacement in alterations:
            with self.subTest(section=section, field=field):
                changed = copy.deepcopy(original.result)
                changed[section][field] = replacement
                # A tampered grouping with an incompatible arm can be rejected
                # already by typed deserialization, before proof replay starts.
                if field == "grouping":
                    with self.assertRaises(ValueError):
                        replay_population_identification(replace(original, result=changed))
                else:
                    with self.assertRaisesRegex(ValueError, "proof replay failed"):
                        replay_population_identification(replace(original, result=changed))
        spec = make_complete_randomization_arm_spec(
            network, m=2, node_id="0", own_treatment_value=0, exposure_value=2,
            exposure_definition=EXPOSURE, source="synthetic", evidence="design",
            admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE",
        )
        raw = RandomizedNetworkArmBackend().solve(spec)
        self.assertEqual(IdentificationVerifier().verify(spec, raw).verification_status, "VERIFIED")

    def test_unresolved_and_untrusted_do_not_produce_point(self):
        network = net(5, [(0, 1), (0, 2), (0, 3)])
        needs = identify(fixture(network, admitted=False))
        self.assertEqual(needs.diagnostics["workflow_status"], "NEEDS_INPUT")
        proposed = identify(fixture(network, query_authority="PROPOSED"))
        self.assertEqual(proposed.result["reason_code"], "QUERY_NOT_CONFIRMED")
        trusted = fixture(network)
        tamper = copy.deepcopy(trusted.identification_spec)
        for item in tamper["assumptions"]:
            if item["name"] == "full_vector_randomization":
                item.update(status="CONTRADICTED", source="human_confirmation", confirmed=False)
        res = identify(replace(trusted, identification_spec=tamper))
        self.assertEqual(res.diagnostics["workflow_status"], "UNSUPPORTED")

    def test_no_exposure_sufficiency_needed_for_point(self):
        # Under m=2, node 0 treated, E2-middle means 1 treated neighbor. The
        # full treated allocation may differ while the arm label stays fixed.
        n, edges, m = 5, [(0, 1), (0, 2), (0, 3)], 2
        potential = []
        for treated_tuple in combinations(range(n), m):
            treated = set(treated_tuple)
            if 0 in treated and sum(j in treated for j in (1, 2, 3)) == 1:
                potential.append(100*int(1 in treated) + 20*int(2 in treated) + 3*int(3 in treated))
        self.assertEqual(len(potential), 3)
        self.assertEqual(len(set(potential)), 3)
        self.assertEqual(Fraction(sum(potential), len(potential)), Fraction(123, 3))
        result = identify(fixture(net(n, edges), a=1, s=1))
        self.assertEqual((result.status, result.verification_status), ("POINT", "VERIFIED"))
        self.assertEqual(result.result["certificate"]["joint_arm_support_probability"], "3/10")

    def test_d3_e2_reuses_the_same_backend(self):
        network = net(5, [(0, 1), (0, 2), (0, 3)])
        groups = (("0", "1"), ("2", "3", "4"))
        quotas = (1, 1)
        ref = oracle_d3(5, groups, quotas, [(0, 1), (0, 2), (0, 3)], 0)
        self.assertEqual(ref, {
            (0, 0): Fraction(0), (0, 1): Fraction(1, 6), (0, 2): Fraction(1, 3),
            (1, 0): Fraction(1, 6), (1, 1): Fraction(1, 3), (1, 2): Fraction(0),
        })
        design = TwoGroupFixedQuotaDesignV1(groups=groups, treated_quotas=quotas)
        for (a, s), expected in ref.items():
            with self.subTest(arm=(a, s)):
                self.assertEqual(joint_support_two_group(network, design, "0", a, s, GROUP_E2), expected)
                self.assertEqual(_verify_two_group_joint_support_independently(network, design, "0", a, s, GROUP_E2), expected)
                task = make_two_group_quota_arm_task(
                    network, groups=groups, treated_quotas=quotas,
                    node_id="0", own_treatment_value=a, exposure_value=s,
                    exposure_definition=EXPOSURE, source="synthetic", evidence="full design",
                    admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE",
                )
                answer = identify(task)
                self.assertEqual(answer.status, "POINT" if expected else "UNSUPPORTED")
                if expected:
                    self.assertEqual(answer.verification_status, "VERIFIED")
                    self.assertEqual(Fraction(answer.result["certificate"]["joint_arm_support_probability"]), expected)
                    self.assertIsNone(answer.estimation_request)

    def test_d3_e2_randomized_two_group_convolution_vs_full_enumeration(self):
        rng = random.Random(20261014)
        cases = 0
        for n in range(3, 9):
            for group_split in (1, n // 2, n - 1):
                groups = (tuple(map(str, range(group_split))),
                          tuple(map(str, range(group_split, n))))
                for quotas in ((0, 0), (len(groups[0]), len(groups[1])),
                               (len(groups[0]) // 2, len(groups[1]) // 2),
                               (1, min(1, len(groups[1])))):
                    if quotas[0] > len(groups[0]):
                        continue
                    design = TwoGroupFixedQuotaDesignV1(groups=groups, treated_quotas=quotas)
                    for _ in range(3):
                        edges = [(u, v) for u in range(n) for v in range(u + 1, n)
                                 if rng.random() < 0.45]
                        network = net(n, edges)
                        for i in range(n):
                            if not sum(i in edge for edge in edges):
                                continue
                            ref = oracle_d3(n, groups, quotas, edges, i)
                            self.assertEqual(sum(ref.values()), 1)
                            for (a, s), expected in ref.items():
                                with self.subTest(n=n, split=group_split, quotas=quotas, i=i, arm=(a,s)):
                                    self.assertEqual(
                                        joint_support_two_group(network, design, str(i), a, s, GROUP_E2), expected
                                    )
                                    self.assertEqual(
                                        _verify_two_group_joint_support_independently(network, design, str(i), a, s, GROUP_E2), expected
                                    )
                                    cases += 1
        self.assertGreater(cases, 1000)

    def test_er300_e2_no_claim_of_estimation(self):
        from fixed_network_fixture import DEFAULT_GRAPH, load_graph
        import numpy as np
        adjacency = load_graph(DEFAULT_GRAPH)
        self.assertEqual(adjacency.shape, (300, 300))
        edges = [(i, j) for i in range(300) for j in range(i+1,300) if adjacency[i, j]]
        network = net(300, edges, "shared-er300-e2")
        degree = network.degree_map()["23"]
        self.assertGreater(degree, 0)
        # Explicitly use a positive arm, not a finite-sample cell count.
        task = fixture(network, m=150, i="23", a=1, s=1)
        result = identify(task)
        self.assertEqual((result.status, result.verification_status), ("POINT", "VERIFIED"))
        self.assertGreater(Fraction(result.result["certificate"]["joint_arm_support_probability"]), 0)
        self.assertEqual(result.diagnostics["workflow_status"], "IDENTIFIED_NO_ESTIMATION_ADAPTER")
        self.assertIsNone(result.estimation_request)


if __name__ == "__main__":
    unittest.main()
