"""Production D3×E1 contract, exact support and independent full-allocation oracle.

The oracle enumerates combinations of treated *members* of the two original
pretreatment groups and never calls the production hypergeometric routines.
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
    identify, make_two_group_quota_arm_task, make_complete_randomization_arm_task,
    replay_handoff, replay_population_identification,
)
from pfn_pipeline._internal.identification.randomized_network_arm import (
    _verify_two_group_joint_support_independently, joint_support_two_group,
    make_two_group_quota_arm_spec, RandomizedNetworkArmBackend,
)
from pfn_pipeline._internal.identification.schemas import (
    NetworkExposureSpec, TwoGroupFixedQuotaDesignV1, IdentificationSpec,
    IdentificationResult as BackendResult,
)
from pfn_pipeline._internal.identification.verifier import IdentificationVerifier


def network(n: int, edges: list[tuple[int, int]], network_id: str = "d3-e1-fixture") -> NetworkExposureSpec:
    return NetworkExposureSpec(
        network_id=network_id,
        node_ids=[str(j) for j in range(n)],
        undirected_edges=[(str(u), str(v)) for u, v in edges],
    )


def enumerate_joint(
    groups: tuple[tuple[str, ...], tuple[str, ...]],
    quotas: tuple[int, int],
    edges: list[tuple[int, int]],
    i: int, a: int, s: int,
) -> Fraction:
    """Third, independent oracle: enumerate all valid group treatment draws."""
    neighbors = set()
    for u, v in edges:
        if u == i:
            neighbors.add(str(v))
        elif v == i:
            neighbors.add(str(u))
    count, total = 0, comb(len(groups[0]), quotas[0]) * comb(len(groups[1]), quotas[1])
    for treated0 in combinations(groups[0], quotas[0]):
        for treated1 in combinations(groups[1], quotas[1]):
            treated = set(treated0) | set(treated1)
            k = sum(int(neighbor in treated) for neighbor in neighbors)
            count += int((str(i) in treated) == bool(a) and int(k > len(neighbors) // 2) == s)
    return Fraction(count, total)


def fixture_task(
    net, groups, quotas, i="0", a=1, s=0, admitted=True, authority="TRUSTED_FIXTURE",
):
    return make_two_group_quota_arm_task(
        net, groups=groups, treated_quotas=quotas, node_id=i,
        own_treatment_value=a, exposure_value=s,
        source="documented synthetic two-group fixed-quota experiment",
        evidence="known two-group membership and quotas, fixed graph and finite outcomes",
        synthetic=True, admitted=admitted, query_authority=authority,
    )


class TwoGroupQuotaArmIntegrationTests(unittest.TestCase):
    def test_five_person_cross_group_golden_case(self):
        net = network(5, [(0, 1), (0, 2), (0, 3)])
        groups = (("0", "1"), ("2", "3", "4"))
        for (a, s), support in {
            (0, 0): Fraction(1, 6), (0, 1): Fraction(1, 3),
            (1, 0): Fraction(1, 2), (1, 1): Fraction(0),
        }.items():
            with self.subTest(arm=(a, s)):
                task = fixture_task(net, groups, (1, 1), a=a, s=s)
                result = identify(task)
                self.assertIsNone(result.estimation_request)
                self.assertEqual(result.task.assignment_design["assignment_scheme"], "two_group_fixed_quotas")
                self.assertEqual(result.result["query"]["response_target_fingerprint"], task.target_fingerprint)
                if support:
                    self.assertEqual((result.status, result.verification_status), ("POINT", "VERIFIED"))
                    self.assertEqual(Fraction(result.result["certificate"]["joint_arm_support_probability"]), support)
                    self.assertEqual(result.result["certificate"]["rule_id"], "RANDOMIZED_NETWORK_ARM_MEAN_TWO_GROUP_V1")
                    self.assertEqual(result.result["identified_functional"]["assignment_kind"], "two_group_fixed_quotas")
                    self.assertEqual(result.result["identified_functional"]["group_treated_quotas"], (1, 1))
                    self.assertEqual(result.diagnostics["workflow_status"], "IDENTIFIED_NO_ESTIMATION_ADAPTER")
                    self.assertEqual(replay_population_identification(result).verification_status, "VERIFIED")
                    with self.assertRaisesRegex(ValueError, "verified estimation handoff"):
                        replay_handoff(result)
                else:
                    self.assertEqual(result.status, "UNSUPPORTED")
                    self.assertEqual(result.result["reason_code"], "ZERO_ARM_SUPPORT")

    def test_independent_small_graph_enumeration(self):
        rng = random.Random(20261013)
        cases = 0
        for n in range(2, 9):
            for iteration in range(8):
                nodes = [str(j) for j in range(n)]
                rng.shuffle(nodes)
                split = rng.randrange(1, n)
                groups = (tuple(nodes[:split]), tuple(nodes[split:]))
                quotas = (
                    rng.randrange(len(groups[0]) + 1),
                    rng.randrange(len(groups[1]) + 1),
                )
                # Explicit cross-group edges are allowed by the assignment design.
                p = rng.choice((0.03, 0.2, 0.5, 0.9, 1.0))
                edges = [(u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < p]
                net = network(n, edges)
                design = TwoGroupFixedQuotaDesignV1(groups=groups, treated_quotas=quotas)
                for i in range(n):
                    for a in (0, 1):
                        for s in (0, 1):
                            with self.subTest(n=n, run=iteration, i=i, a=a, s=s):
                                expected = enumerate_joint(groups, quotas, edges, i, a, s)
                                proposed = joint_support_two_group(net, design, str(i), a, s)
                                replayed = _verify_two_group_joint_support_independently(
                                    net, design, str(i), a, s
                                )
                                self.assertEqual(proposed, expected)
                                self.assertEqual(replayed, expected)
                                cases += 1
        self.assertGreater(cases, 800)

    def test_quotas_extreme_isolate_and_even_degree_tie(self):
        net = network(4, [(0, 1), (0, 2)])
        groups = (("0", "1"), ("2", "3"))
        for quotas in ((0, 0), (2, 2), (0, 2), (2, 0), (1, 1)):
            design = TwoGroupFixedQuotaDesignV1(groups=groups, treated_quotas=quotas)
            for i in range(4):
                for a in (0, 1):
                    masses = [joint_support_two_group(net, design, str(i), a, s) for s in (0, 1)]
                    self.assertEqual(sum(masses), Fraction(quotas[0] if a else 2 - quotas[0], 2)
                                     if i in (0, 1) else Fraction(quotas[1] if a else 2 - quotas[1], 2))
            # Node 3 has degree zero and can only be in the low exposure bin.
            self.assertEqual(joint_support_two_group(net, design, "3", 1, 1), Fraction(0))
        # With one treated neighbor out of two, strict majority is LOW.
        design = TwoGroupFixedQuotaDesignV1(groups=groups, treated_quotas=(1, 1))
        self.assertEqual(joint_support_two_group(net, design, "0", 1, 1), Fraction(0))

    def test_invalid_partition_quotas_and_queries_rejected(self):
        net = network(5, [(0, 1), (0, 2)])
        good = (("0", "1"), ("2", "3", "4"))
        for bad in (
            (("0", "1"), ("2", "3")),
            (("0", "1"), ("2", "3", "missing")),
            (("0", "1"), ("1", "2", "3", "4")),
            (("0", "1", "2", "3", "4"), ()),
        ):
            with self.subTest(groups=bad), self.assertRaises((ValueError, TypeError)):
                fixture_task(net, bad, (1, 1))
        for bad_quota in ((-1, 1), (3, 1), (1, 4), (True, 1), (0.5, 1), (1,)):
            with self.subTest(quotas=bad_quota), self.assertRaises((ValueError, TypeError)):
                fixture_task(net, good, bad_quota)
        for invalid_a, invalid_s in ((-1, 0), (0, 2), (1, True), (True, 0)):
            with self.assertRaises(ValueError):
                fixture_task(net, good, (1, 1), a=invalid_a, s=invalid_s)
        with self.assertRaises(ValueError):
            fixture_task(net, good, (1, 1), i="unknown")

    def test_unresolved_rejected_and_llm_only_assumptions(self):
        net = network(5, [(0, 1), (0, 2), (0, 3)])
        groups = (("0", "1"), ("2", "3", "4"))
        unresolved = identify(fixture_task(net, groups, (1, 1), admitted=False))
        self.assertEqual((unresolved.status, unresolved.diagnostics["workflow_status"]),
                         ("UNSUPPORTED", "NEEDS_INPUT"))
        proposed = identify(fixture_task(net, groups, (1, 1), authority="PROPOSED"))
        self.assertEqual(proposed.result["reason_code"], "QUERY_NOT_CONFIRMED")
        task = fixture_task(net, groups, (1, 1))
        source = copy.deepcopy(task.identification_spec)
        for assumption in source["assumptions"]:
            if assumption["name"] == "full_vector_randomization":
                assumption.update(status="CONTRADICTED", confirmed=False, source="human_confirmation")
        result = identify(replace(task, identification_spec=source))
        self.assertEqual(result.diagnostics["workflow_status"], "UNSUPPORTED")
        with self.assertRaisesRegex(ValueError, "TRUSTED_FIXTURE"):
            make_two_group_quota_arm_task(
                net, groups=groups, treated_quotas=(1, 1), node_id="0",
                own_treatment_value=1, exposure_value=0, source="real protocol",
                evidence="external", admitted=True, synthetic=False,
                query_authority="TRUSTED_FIXTURE",
            )

    def test_public_envelope_mismatch_and_fingerprint_security(self):
        net = network(5, [(0, 1), (0, 2), (0, 3)])
        groups = (("0", "1"), ("2", "3", "4"))
        task = fixture_task(net, groups, (1, 1), a=0, s=1)
        self.assertEqual(identify(task).status, "POINT")
        with self.assertRaisesRegex(ValueError, "differs"):
            replace(task, assignment_design={**task.assignment_design, "treated_quotas": [1, 2]})
        with self.assertRaisesRegex(ValueError, "differs"):
            replace(task, assignment_design={**task.assignment_design,
                                            "groups": [["0", "2"], ["1", "3", "4"]]})
        with self.assertRaisesRegex(ValueError, "differs"):
            replace(task, exposure_definition="treated_neighbor_count_1hop")
        # Changing the nested design and the public envelope together does NOT
        # authorize a stale target fingerprint as a new causal query.
        modified = copy.deepcopy(task.identification_spec)
        modified["randomized_network_arm_theorem_contract"]["design"]["treated_quotas"] = (0, 1)
        changed_assignment = copy.deepcopy(task.assignment_design)
        changed_assignment["treated_quotas"] = [0, 1]
        altered = replace(task, identification_spec=modified, assignment_design=changed_assignment)
        checked = identify(altered)
        self.assertEqual(checked.status, "UNSUPPORTED")
        self.assertEqual(checked.result["reason_code"], "DESIGN_DEPENDENT_TARGET_FINGERPRINT_MISMATCH")
        # Even where two designs happen to have equal arm support, the query
        # fingerprint must bind the entire original q and its target kernel.
        a = make_complete_randomization_arm_task(
            net, m=2, node_id="0", own_treatment_value=0, exposure_value=1,
            source="synthetic", evidence="uniform allocation", admitted=True,
            synthetic=True, query_authority="TRUSTED_FIXTURE",
        )
        self.assertNotEqual(a.target_fingerprint, task.target_fingerprint)

    def test_tampering_with_certificate_or_functional_rejected(self):
        net = network(5, [(0, 1), (0, 2), (0, 3)])
        task = fixture_task(net, (("0", "1"), ("2", "3", "4")), (1, 1), a=0, s=1)
        good = identify(task)
        for field, modified_value in (
            ("joint_arm_support_probability", "99/100"),
            ("group_treated_quotas", [2, 1]),
            ("source_spec_sha256", "fake"),
        ):
            with self.subTest(certificate_field=field):
                payload = copy.deepcopy(good.result)
                payload["certificate"][field] = modified_value
                with self.assertRaisesRegex(ValueError, "proof replay failed"):
                    replay_population_identification(replace(good, result=payload))
        payload = copy.deepcopy(good.result)
        payload["identified_functional"]["group_treated_quotas"] = (0, 1)
        with self.assertRaisesRegex(ValueError, "proof replay failed"):
            replay_population_identification(replace(good, result=payload))
        spec = make_two_group_quota_arm_spec(
            net, groups=(("0", "1"), ("2", "3", "4")), treated_quotas=(1, 1),
            node_id="0", own_treatment_value=0, exposure_value=1,
            source="documented synthetic two-group fixed-quota experiment",
            evidence="known two-group membership and quotas, fixed graph and finite outcomes",
            admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE",
        )
        raw = RandomizedNetworkArmBackend().solve(spec)
        self.assertEqual(IdentificationVerifier().verify(spec, raw).verification_status, "VERIFIED")

    def test_same_arm_outcomes_need_not_be_equal(self):
        # For the low arm of node zero with own treated, all three possible
        # B2 allocations lie in the same arm, but its potential outcome differs.
        edges = [(0, 1), (0, 2), (0, 3)]
        groups = (("0", "1"), ("2", "3", "4"))
        y_by_allocation = {}
        for tr0 in combinations(groups[0], 1):
            for tr1 in combinations(groups[1], 1):
                treated = set(tr0 + tr1)
                u = tuple(int(str(j) in treated) for j in range(5))
                y_by_allocation[u] = 10*u[2] + 4*u[3] + 7*u[4] + 2*u[1]
        target_values = [y for u, y in y_by_allocation.items()
                         if u[0] == 1 and int(u[1] + u[2] + u[3] > 1) == 0]
        self.assertEqual(len(target_values), 3)
        self.assertGreater(len(set(target_values)), 1)
        self.assertEqual(Fraction(sum(target_values), len(target_values)), Fraction(21, 3))

    def test_shared_er300_network_no_estimation_adapter(self):
        from fixed_network_fixture import DEFAULT_GRAPH, load_graph
        adjacency = load_graph(DEFAULT_GRAPH)
        self.assertEqual(adjacency.shape, (300, 300))
        edges = [(i, j) for i in range(300) for j in range(i + 1, 300) if adjacency[i, j]]
        net = network(300, edges, "shared-er300-d3-e1")
        task = fixture_task(
            net,
            (tuple(map(str, range(0, 150))), tuple(map(str, range(150, 300)))),
            (75, 75), i="23", a=1, s=1,
        )
        result = identify(task)
        self.assertEqual((result.status, result.verification_status), ("POINT", "VERIFIED"))
        self.assertGreater(Fraction(result.result["certificate"]["joint_arm_support_probability"]), 0)
        self.assertIsNone(result.estimation_request)
        self.assertEqual(result.diagnostics["workflow_status"], "IDENTIFIED_NO_ESTIMATION_ADAPTER")

    def test_legacy_d2_serialized_result_still_replays(self):
        # v0.3 persisted Program JSON did not have the optional D3 group fields.
        net = network(4, [(0, 1), (0, 2), (1, 3)])
        old_task = make_complete_randomization_arm_task(
            net, m=2, node_id="0", own_treatment_value=1, exposure_value=0,
            source="old fixture", evidence="complete randomization", admitted=True,
            synthetic=True, query_authority="TRUSTED_FIXTURE",
        )
        result = identify(old_task)
        payload = copy.deepcopy(result.result)
        payload["identified_functional"].pop("group_node_ids", None)
        payload["identified_functional"].pop("group_treated_quotas", None)
        saved_old = replace(result, result=payload)
        self.assertEqual(replay_population_identification(saved_old).verification_status, "VERIFIED")

    def test_source_annotation_requires_explicit_human_confirmation(self):
        net = network(3, [(0, 1), (0, 2)])
        result = identify(make_two_group_quota_arm_task(
            net, groups=(("0",), ("1", "2")), treated_quotas=(1, 1),
            node_id="0", own_treatment_value=1, exposure_value=0,
            source="signed randomization protocol", evidence="signed pretreatment groups",
            synthetic=False, admitted=True, query_authority="HUMAN_CONFIRMED",
        ))
        self.assertEqual((result.status, result.verification_status), ("POINT", "VERIFIED"))
        self.assertEqual(result.result["identified_functional"]["assignment_kind"], "two_group_fixed_quotas")


if __name__ == "__main__":
    unittest.main()
