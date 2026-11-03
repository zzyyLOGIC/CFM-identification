"""Independent finite-design oracles and query-level behavior tests.

Run from the repository root:
    python -B -m unittest discover -s student_work/task05 -p 'test_*.py' -v
    python -B tools/run_student_tests.py
"""
from fractions import Fraction
from itertools import combinations
import json
from pathlib import Path
import random
import unittest

if __package__:
    from .support import compute_support, exposure_state, support_by_degree
    from .rule import identify, REQUIRED_ASSUMPTIONS
else:
    from support import compute_support, exposure_state, support_by_degree
    from rule import identify, REQUIRED_ASSUMPTIONS


def graph_from_edges(n, edges):
    graph = [[0] * n for _ in range(n)]
    for a, b in edges:
        graph[a][b] = graph[b][a] = 1
    return graph


def example_graph():
    return graph_from_edges(6, [(0, 1), (0, 2), (0, 3), (1, 4), (2, 5)])


def admitted_assumptions():
    # Explicit declarations for a synthetic randomized experiment only.
    return dict.fromkeys(REQUIRED_ASSUMPTIONS, "ADMITTED")


def enumerate_support(graph, m):
    """Oracle: enumerate full legal allocations, with independent exposure logic.

    Deliberately does not call any production support/exposure helper and
    uses exact Fraction thresholds instead of production integer comparisons.
    """
    n = len(graph)
    allocations = list(combinations(range(n), m))
    weight = Fraction(1, len(allocations))
    result = {i: None if sum(graph[i]) == 0 else
              {(t, s): Fraction(0) for t in (0, 1) for s in (0, 1, 2)} for i in range(n)}
    for selected in allocations:
        selected = set(selected)
        for i, row in enumerate(graph):
            if result[i] is None:
                continue
            share = Fraction(sum(row[j] for j in selected), sum(row))
            s = 0 if share < Fraction(1, 3) else (1 if share < Fraction(2, 3) else 2)
            result[i][int(i in selected), s] += weight
    return result


class SupportTests(unittest.TestCase):
    def test_known_six_arm_example(self):
        self.assertEqual(compute_support(example_graph(), 2)[0], {
            (0, 0): Fraction(1, 15), (0, 1): Fraction(6, 15), (0, 2): Fraction(3, 15),
            (1, 0): Fraction(2, 15), (1, 1): Fraction(3, 15), (1, 2): Fraction(0)})

    def test_all_graphs_up_to_four_nodes_all_quotas(self):
        for n in range(1, 5):
            edges = list(combinations(range(n), 2))
            for mask in range(1 << len(edges)):
                graph = graph_from_edges(n, [e for bit, e in enumerate(edges) if mask & (1 << bit)])
                for m in range(n + 1):
                    with self.subTest(n=n, mask=mask, m=m):
                        self.assertEqual(compute_support(graph, m), enumerate_support(graph, m))

    def test_five_to_eight_nodes_multiple_topologies_all_quotas(self):
        rng = random.Random(20261015)
        for n in range(5, 9):
            all_edges = list(combinations(range(n), 2))
            families = [all_edges, [(i, i+1) for i in range(n-1)],
                        [(0, i) for i in range(1, n)],
                        [(i, (i+1) % n) for i in range(n)]]
            families += [[e for e in all_edges if rng.random() < p] for p in (0.2, 0.5, 0.8)]
            for family, edges in enumerate(families):
                graph = graph_from_edges(n, edges)
                for m in range(n+1):
                    with self.subTest(n=n, family=family, m=m):
                        self.assertEqual(compute_support(graph, m), enumerate_support(graph, m))

    def test_normalization_and_marginals(self):
        for n in range(2, 14):
            for m in range(n+1):
                for d in range(1, n):
                    table = support_by_degree(n, m, d)
                    self.assertEqual(sum(table.values()), 1)
                    self.assertTrue(all(0 <= p <= 1 for p in table.values()))
                    self.assertEqual(sum(table[1, s] for s in range(3)), Fraction(m, n))
                    self.assertEqual(sum(table[0, s] for s in range(3)), Fraction(n-m, n))

    def test_thirds_boundaries(self):
        self.assertEqual([exposure_state(k, 6) for k in range(7)], [0, 0, 1, 1, 2, 2, 2])
        self.assertEqual([exposure_state(k, 3) for k in range(4)], [0, 1, 2, 2])
        self.assertEqual([exposure_state(k, 4) for k in range(5)], [0, 0, 1, 2, 2])

    def test_degree_one_has_no_middle_bin(self):
        table = support_by_degree(5, 2, 1)
        self.assertEqual(table[0, 1], 0)
        self.assertEqual(table[1, 1], 0)

    def test_extreme_quotas(self):
        for m, supported in [(0, (0, 0)), (6, (1, 2))]:
            for table in compute_support(example_graph(), m).values():
                self.assertEqual(table[supported], 1)
                self.assertEqual(sum(p for arm, p in table.items() if arm != supported), 0)

    def test_isolates_are_undefined_not_zero(self):
        graph = graph_from_edges(3, [(0, 1)])
        table = compute_support(graph, 1)
        self.assertIsNone(table[2])
        self.assertEqual(sum(table[0].values()), 1)
        self.assertEqual(compute_support([[0]], 0), {0: None})
        with self.assertRaises(ValueError):
            exposure_state(0, 0)

    def test_own_and_neighbor_treatment_are_not_independent(self):
        table = compute_support(example_graph(), 2)[0]
        p_high = table[0, 2] + table[1, 2]
        self.assertNotEqual(table[1, 2], Fraction(2, 6) * p_high)

    def test_complete_graph_count_depends_on_own_treatment(self):
        graph = graph_from_edges(7, combinations(range(7), 2))
        table = compute_support(graph, 2)[0]
        self.assertEqual(table[0, 1], Fraction(5, 7))  # k=2 of 6
        self.assertEqual(table[1, 0], Fraction(2, 7))  # k=1 of 6
        self.assertEqual(sum(p > 0 for p in table.values()), 2)

    def test_invalid_graphs(self):
        for graph in [[], [[0, 1]], [[0, 1], [0, 0]], [[1]],
                      [[0, 2], [2, 0]], [[0, 0.5], [0.5, 0]], None]:
            with self.subTest(graph=graph), self.assertRaises(ValueError):
                compute_support(graph, 0)

    def test_invalid_quota(self):
        for m in [-1, 7, 1.5, True, "2", None]:
            with self.subTest(m=m), self.assertRaises(ValueError):
                compute_support(example_graph(), m)

    def test_invalid_exposure_arguments(self):
        for k, d in [(-1, 3), (4, 3), (1.0, 3), (True, 3), (0, -1), (0, 2.5), (0, True)]:
            with self.subTest(k=k, d=d), self.assertRaises(ValueError):
                exposure_state(k, d)

    def test_node_relabeling(self):
        graph = example_graph()
        order = [5, 2, 0, 4, 1, 3]
        relabeled = [[graph[i][j] for j in order] for i in order]
        before, after = compute_support(graph, 2), compute_support(relabeled, 2)
        self.assertEqual(after, {new: before[old] for new, old in enumerate(order)})

    def test_same_degree_tables_do_not_alias(self):
        table = compute_support(graph_from_edges(3, [(0, 1), (1, 2), (0, 2)]), 1)
        table[0][0, 0] = "changed"
        self.assertIsInstance(table[1][0, 0], Fraction)

    def test_three_hundred_nodes_without_enumeration(self):
        graph = graph_from_edges(300, [(i, (i+1) % 300) for i in range(300)])
        table = compute_support(graph, 120)
        self.assertEqual(len(table), 300)
        self.assertTrue(all(sum(row.values()) == 1 for row in table.values()))


class RuleTests(unittest.TestCase):
    def test_positive_query_returns_population_functional(self):
        result = identify(example_graph(), 2, 0, 0, 1, assumptions=admitted_assumptions())
        self.assertEqual(result.status, "POINT")
        self.assertEqual(result.workflow_status, "COMPLETE")
        self.assertEqual(result.support, Fraction(2, 5))
        self.assertEqual(result.functional.expression, "E[Y_0^obs | A, X, T_0=0, S_0=1]")

    def test_zero_support_refuses_functional(self):
        result = identify(example_graph(), 2, 0, 1, 2, assumptions=admitted_assumptions())
        self.assertEqual(result.reason_code, "ZERO_POPULATION_SUPPORT")
        self.assertEqual(result.status, "UNSUPPORTED")
        self.assertIsNone(result.functional)

    def test_isolate_refuses_query(self):
        result = identify([[0]], 0, 0, 0, 0, assumptions=admitted_assumptions())
        self.assertEqual(result.reason_code, "EXPOSURE_UNDEFINED_ISOLATE")
        self.assertIsNone(result.support)

    def test_each_missing_or_pending_assumption_needs_input(self):
        for name in REQUIRED_ASSUMPTIONS:
            for status in [None, "UNRESOLVED", "PROPOSED"]:
                assumptions = admitted_assumptions()
                if status is None:
                    del assumptions[name]
                else:
                    assumptions[name] = status
                with self.subTest(name=name, status=status):
                    result = identify(example_graph(), 2, 0, 0, 1, assumptions=assumptions)
                    self.assertEqual((result.status, result.workflow_status), ("UNSUPPORTED", "NEEDS_INPUT"))
                    self.assertIsNone(result.functional)

    def test_default_assumptions_are_not_silently_admitted(self):
        self.assertEqual(identify(example_graph(), 2, 0, 0, 1).workflow_status, "NEEDS_INPUT")

    def test_each_rejected_assumption_stops_rule(self):
        for name in REQUIRED_ASSUMPTIONS:
            for status in ["NOT_ADMITTED", "CONTRADICTED"]:
                assumptions = admitted_assumptions()
                assumptions[name] = status
                result = identify(example_graph(), 2, 0, 0, 1, assumptions=assumptions)
                self.assertEqual(result.reason_code, "REQUIRED_ASSUMPTION_REJECTED")
                self.assertIsNone(result.functional)

    def test_invalid_assumption_declarations(self):
        for assumptions in [True, [], {"typo": "ADMITTED"}, {"consistency": True}, {"consistency": "yes"}]:
            with self.subTest(assumptions=assumptions), self.assertRaises(ValueError):
                identify(example_graph(), 2, 0, 0, 1, assumptions=assumptions)

    def test_invalid_query(self):
        for node, t, s in [(-1, 0, 0), (6, 0, 0), (0, 2, 0), (0, 0, 3), (0, True, 0), (0, 0, 1.0)]:
            with self.subTest(node=node, t=t, s=s), self.assertRaises(ValueError):
                identify(example_graph(), 2, node, t, s, assumptions=admitted_assumptions())

    def test_result_serialization_preserves_context_without_core_handoff(self):
        result = identify(example_graph(), 2, 0, 0, 1, assumptions=admitted_assumptions())
        payload = json.loads(json.dumps(result.to_dict()))
        self.assertEqual(payload["support"], "2/5")
        self.assertEqual(payload["quota"], 2)
        self.assertEqual(payload["adjacency"], example_graph())
        self.assertEqual(payload["verification_status"], "NOT_RUN")
        self.assertIsNone(payload["estimation_request"])

    def test_result_copies_mutable_inputs(self):
        graph, assumptions = example_graph(), admitted_assumptions()
        result = identify(graph, 2, 0, 0, 1, assumptions=assumptions)
        graph[0][1] = 0
        assumptions["consistency"] = "CONTRADICTED"
        self.assertEqual(result.adjacency[0][1], 1)
        self.assertEqual(dict(result.assumptions)["consistency"], "ADMITTED")

    def test_population_proof_with_insufficient_exposure_mapping(self):
        # Synthetic oracle exists ONLY in tests, never in identify/support.
        graph, m, i = example_graph(), 2, 0
        allocations = list(combinations(range(6), m))
        schedule = []
        for selected in allocations:
            u = [int(j in selected) for j in range(6)]
            share = Fraction(sum(graph[i][j] * u[j] for j in range(6)), sum(graph[i]))
            s = 0 if share < Fraction(1, 3) else (1 if share < Fraction(2, 3) else 2)
            # Depends on neighbor identity and a non-neighbor; E2 is not sufficient.
            mean = 2*u[0] + 3*u[1] - 5*u[2] + 7*u[4] + 11*u[1]*u[5]
            schedule.append((u[0], s, mean))
        found_unequal = False
        for t in (0, 1):
            for s in range(3):
                result = identify(graph, m, i, t, s, assumptions=admitted_assumptions())
                means = [y for own, state, y in schedule if (own, state) == (t, s)]
                if not means:
                    self.assertEqual(result.status, "UNSUPPORTED")
                    continue
                target = sum(Fraction(y, len(allocations)) / result.support for y in means)
                # In repeated randomized experiments add independent centered +/-1 noise.
                observations = [y+noise for y in means for noise in (-1, 1)]
                population_observed_mean = Fraction(sum(observations), len(observations))
                self.assertEqual(target, population_observed_mean)
                found_unequal |= len(set(means)) > 1
        self.assertTrue(found_unequal)

    def test_notebook_structure_and_no_saved_errors(self):
        nb = json.loads(Path(__file__).with_name("demo.ipynb").read_text(encoding="utf-8"))
        self.assertEqual(nb["nbformat"], 4)
        self.assertTrue(any(cell["cell_type"] == "code" for cell in nb["cells"]))
        for cell in nb["cells"]:
            self.assertFalse(any(out["output_type"] == "error" for out in cell.get("outputs", [])))


if __name__ == "__main__":
    unittest.main()
