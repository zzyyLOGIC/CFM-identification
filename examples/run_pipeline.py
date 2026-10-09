"""Run the public pipeline on one simulated fixed-network task.

From research/:
    python -m examples.run_pipeline --output outputs/inference_001 --plots
    python -m examples.run_pipeline --smoke --output outputs/smoke_001 --plots
    python -m examples.run_pipeline --checkpoint er_estimation_demo/model_best.pt \
        --output outputs/inference_001
"""
import argparse
import json
from pathlib import Path

import numpy as np

from pfn_pipeline import (
    estimate_effects, evaluate_estimates, evaluate_policy, identify,
    load_checkpoint, load_graph, optimize_offline, simulate_task, train_model,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--smoke", action="store_true",
                        help="Train a tiny CPU-compatible model to check the workflow only.")
    source.add_argument("--checkpoint", help="Absolute path or name under checkpoints/; default: er_estimation_demo/model_best.pt.")
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory.")
    parser.add_argument("--device", default="cpu", help="cpu, cuda or musa; default: cpu.")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--graph", type=Path,
                        help="Explicit fixed graph; smoke defaults to ER300 p=0.5, inference to the checkpoint graph.")
    parser.add_argument("--budget", type=int, default=5)
    parser.add_argument("--budget-mode", choices=("at_most", "exact"), default="at_most")
    parser.add_argument("--plots", action="store_true", help="Save three PNG figures.")
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error("--output must be a new or empty directory; choose another run name.")

    import matplotlib
    matplotlib.use("Agg")
    import torch
    torch.set_num_threads(1)

    # Preserve the checkpoint's graph and prior for inference. Smoke training
    # and simulation share the explicit graph, or the repository default.
    from pfn_pipeline._internal.paths import DEFAULT_GRAPH
    from pfn_pipeline._internal.estimation.priors import DEFAULT_DGP
    model = None if args.smoke else load_checkpoint(args.checkpoint, device=args.device)
    graph_file = args.graph.expanduser().resolve() if args.graph else (
        DEFAULT_GRAPH if model is None else None)
    adjacency = load_graph(graph_file if graph_file is not None else model.graph_record)
    if model is not None and not np.array_equal(adjacency, load_graph(model.graph_record)):
        parser.error("--graph differs from the checkpoint training graph; use matching weights or --smoke.")
    dgp = DEFAULT_DGP if model is None else model.provenance["dgp"]
    noise_sd = 4.0 if model is None else model.provenance["training_noise_sd"]

    # Validate the task/identification before training. Oracle values are returned
    # separately and are only passed to evaluation, never to estimation/policy.
    task, reference = simulate_task(seed=args.seed, budget=args.budget,
                                   budget_mode=args.budget_mode, adjacency=adjacency,
                                   dgp=dgp, noise_sd=noise_sd, return_reference=True)
    identified = identify(task)
    if identified.status != "POINT" or identified.verification_status != "VERIFIED":
        raise RuntimeError(f"Synthetic task identification failed: {identified.result}")

    if args.smoke:
        print("SMOKE RUN: two training tasks and one epoch; metrics do not establish model quality.",
              flush=True)
        checkpoint = train_model(
            output / "training", cache_dir=str(output / "cache"), device=args.device,
            train_tasks=2, validation_tasks=1, epochs=1, batch_size=1,
            num_layers=1, d_model=16, num_heads=2, threads=1,
            dgp=dgp, graph_file=str(graph_file),
        )
        model = load_checkpoint(checkpoint, device=args.device)
    evaluation_scope = "smoke_only" if args.smoke else "matched_training_prior"
    estimates = estimate_effects(task, identified, model)
    policy = optimize_offline(task, estimates)
    if policy.abstain:
        raise RuntimeError(f"Policy abstained: {policy.stop_reason}")

    output.mkdir(parents=True, exist_ok=True)
    np.save(output / "mu.npy", estimates.center)
    np.save(output / "allocation.npy", policy.allocation)
    report = {
        "run_mode": "smoke" if args.smoke else "checkpoint_inference",
        "evaluation_scope": evaluation_scope,
        "simulation_dgp": dgp,
        "simulation_reference_metadata": reference["metadata"],
        "seed": args.seed,
        "target_id": task.target_id,
        "target_semantics": task.target_semantics,
        "node_ids": list(task.node_ids),
        "graph": {"file": str(graph_file) if graph_file is not None else None,
                  "source": "graph_file" if graph_file is not None else "checkpoint",
                  "n_nodes": task.n_nodes, "edge_count": int(task.adjacency.sum() // 2),
                  "adjacency_sha256": task.metadata["graph_sha256"]},
        "checkpoint": model.provenance,
        "identification": {"status": identified.status,
                           "verification_status": identified.verification_status,
                           "workflow_status": identified.diagnostics["workflow_status"],
                           "assumptions_used": identified.result["assumptions_used"],
                           "arm_mean_count": 4 * task.n_nodes,
                           "node_contrast_count": 3 * task.n_nodes},
        "response_shape": list(estimates.center.shape),
        "arm_order": ["mu00", "mu01", "mu10", "mu11"],
        "estimate_metrics": evaluate_estimates(estimates, reference),
        "policy_metrics": evaluate_policy(policy, reference),
        "policy": {"budget": policy.budget, "budget_mode": policy.budget_mode,
                   "stop_reason": policy.stop_reason,
                   "selected_node_ids": [task.node_ids[i] for i in policy.selected_nodes]},
    }
    (output / "summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    if args.plots:
        import matplotlib.pyplot as plt
        from pfn_pipeline import plot_effects, plot_policy, plot_response_surface
        for name, function, value in (
            ("response_surface", plot_response_surface, estimates),
            ("effects", plot_effects, estimates),
            ("policy", plot_policy, policy),
        ):
            figure = function(value)
            figure.savefig(output / f"{name}.png", dpi=150)
            plt.close(figure)
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    print(f"Saved results to {output}")


if __name__ == "__main__":
    main()
