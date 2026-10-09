"""CPU smoke test of migrated public APIs, with no permanent experiment outputs.

From research/: python -B -m unittest discover -s tests -p test_pipeline_smoke.py -v
An intentionally tiny random-DGP model is trained in a temporary directory. This
checks plumbing/checkpoint compatibility, not trained-model quality or coverage.
"""
from copy import deepcopy
from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import torch

from pfn_pipeline import (
    TaskSpec, IdentificationResult, EstimateBundle, PolicyResult,
    simulate_task, identify, load_checkpoint, train_model, build_model,
    estimate_effects, optimize_offline, evaluate_estimates, evaluate_policy,
    plot_response_surface, plot_effects, plot_policy, evaluate_checkpoint,
)


class PipelineSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        cls.temporary = tempfile.TemporaryDirectory(prefix="pfn-pipeline-smoke-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.previous_threads = torch.get_num_threads()
        cls.addClassCleanup(torch.set_num_threads, cls.previous_threads)
        torch.set_num_threads(1)
        directory = Path(cls.temporary.name)
        checkpoint = train_model(directory / "training", cache_dir=str(directory / "cache"),
            dgp="random_functions",
            train_tasks=2, validation_tasks=1, epochs=1, batch_size=1,
            num_layers=1, d_model=16, num_heads=2, device="cpu", threads=1)
        cls.model = load_checkpoint(checkpoint)
        cls.checkpoint = checkpoint
        cls.task, cls.reference = simulate_task(seed=2026, budget=5, dgp="random_functions", return_reference=True)
        cls.identified = identify(cls.task)
        cls.estimates = estimate_effects(cls.task, cls.identified, cls.model)
        cls.policy = optimize_offline(cls.task, cls.estimates)

    def test_full_chain_and_named_arms(self):
        self.assertIsInstance(self.task, TaskSpec)
        self.assertIsInstance(self.identified, IdentificationResult)
        self.assertIsInstance(self.estimates, EstimateBundle)
        self.assertIsInstance(self.policy, PolicyResult)
        self.assertEqual((self.identified.status, self.identified.verification_status), ("POINT", "VERIFIED"))
        self.assertEqual(self.estimates.center.shape, (self.task.n_nodes, 2, 2))
        self.assertTrue(np.isfinite(self.estimates.center).all())
        marginal = self.estimates.diagnostics["marginal_gmms"]
        self.assertEqual(marginal["arm_order"], ("mu00", "mu01", "mu10", "mu11"))
        means = np.sum(marginal["gmm_pi"] * marginal["gmm_mu"], axis=-1)
        for j, (t, s) in enumerate(((0,0),(0,1),(1,0),(1,1))):
            np.testing.assert_allclose(self.estimates.center[:, t, s], means[:, j])
        self.assertTrue(self.policy.feasible)
        self.assertLessEqual(self.policy.budget_used, 5)
        self.assertFalse(self.policy.abstain)
        self.assertIsNone(self.estimates.sampling_lower)

    def test_reference_optimizer_matches_and_exact_budget(self):
        other = optimize_offline(self.task, self.estimates, method="greedy_reference")
        np.testing.assert_array_equal(other.allocation, self.policy.allocation)
        self.assertAlmostEqual(other.predicted_value, self.policy.predicted_value)
        task = simulate_task(seed=2027, budget=3, budget_mode="exact", dgp="random_functions")
        result = optimize_offline(task, estimate_effects(task, identify(task), self.model))
        self.assertEqual(result.budget_used, 3)

    def test_oracle_is_separate_and_inference_does_not_update_parameters(self):
        before = {key: value.clone() for key, value in self.model.model.state_dict().items()}
        estimate = estimate_effects(self.task, self.identified, self.model)
        np.testing.assert_allclose(estimate.center, self.estimates.center)
        for key, value in self.model.model.state_dict().items():
            torch.testing.assert_close(value, before[key], rtol=0, atol=0)
        self.assertFalse(hasattr(self.task, "oracle_mu"))
        self.assertNotIn("mu", self.task.metadata)
        self.assertNotIn("outcome_seed", self.task.metadata)
        self.assertEqual(self.task.factual_tokens().shape, (self.task.n_nodes,5))

    def test_metrics_and_plots_in_memory(self):
        report = evaluate_estimates(self.estimates, self.reference)
        self.assertTrue(np.isfinite(report["response_surface"]["rmse"]))
        self.assertEqual(set(report["ite"]), {"direct", "spillover", "total"})
        report = evaluate_policy(self.policy, self.reference)
        self.assertEqual(report["actual_rollout_welfare"], "not_evaluated")
        import matplotlib.pyplot as plt
        for function, arg in ((plot_response_surface,self.estimates),
                              (plot_effects,self.estimates),(plot_policy,self.policy)):
            figure = function(arg)
            figure.canvas.draw()
            plt.close(figure)

    def test_invalid_data_and_tampered_handoff_are_rejected(self):
        fractional = self.task.treatment.astype(float).copy()
        fractional[0] = .4
        with self.assertRaises(ValueError):
            replace(self.task, treatment=fractional)
        request = deepcopy(self.identified.estimation_request)
        request["program"]["target_fingerprint"] = "tampered"
        altered = replace(self.identified, estimation_request=request)
        with self.assertRaises(ValueError):
            estimate_effects(self.task, altered, self.model)
        with self.assertRaises(ValueError):
            optimize_offline(self.task, self.estimates, budget=4)

    def test_missing_spec_has_explicit_abstention(self):
        task = replace(self.task, identification_spec=None, assumptions=())
        identified = identify(task)
        estimates = estimate_effects(task, identified, self.model)
        policy = optimize_offline(task, estimates)
        self.assertEqual(identified.status, "UNSUPPORTED")
        self.assertEqual(estimates.kind, "unavailable")
        self.assertTrue(policy.abstain)
        self.assertIsNone(policy.allocation)

    def test_wrong_model_and_graph_are_rejected(self):
        obsolete = Path(self.temporary.name) / "obsolete.pt"
        torch.save({"version": "causalfm_er_cepo_release_v3_four_arm",
                    "prediction_protocol": "majority_cepo_gmm_v2_four_arm"}, obsolete)
        with self.assertRaises(ValueError):
            load_checkpoint(obsolete)
        untrained = build_model(d_model=16, num_heads=2, num_layers=1, ffn_dim=32)
        with self.assertRaises(ValueError):
            estimate_effects(self.task, self.identified, untrained)
        graph = self.task.adjacency.copy()
        graph[0,1] = graph[1,0] = 1 - graph[0,1]
        task = simulate_task(adjacency=graph, dgp="random_functions")
        with self.assertRaises(ValueError):
            estimate_effects(task, identify(task), self.model)

    def test_migrated_checkpoint_evaluation(self):
        directory = Path(self.temporary.name)
        report = evaluate_checkpoint(self.checkpoint, directory / "evaluation", baselines=False,
            cache_dir=str(directory / "evaluation_cache"), test_tasks=1, test_seed=2047)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["n_test_datasets"], 1)
        self.assertEqual(len(report["mu_summary"]), 4)

    def test_imports_from_another_working_directory(self):
        research = Path(__file__).resolve().parents[1]
        environment = dict(os.environ, PYTHONPATH=str(research), PYTHONDONTWRITEBYTECODE="1")
        code = (
            "from pfn_pipeline import load_graph, simulate_task, identify; "
            "assert load_graph().shape == (300,300); "
            "assert identify(simulate_task()).status == 'POINT'; "
            "import sys; assert not any(x in sys.modules for x in "
            "['causal_idfm_demo','network_policy','cepo','train_local_network_interference'])"
        )
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=self.temporary.name,
            env=environment, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
