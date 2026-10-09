"""Figures for notebooks; functions return figures and never save files implicitly."""
import numpy as np

__all__ = ["plot_response_surface", "plot_effects", "plot_policy"]


def plot_response_surface(estimates):
    import matplotlib.pyplot as plt
    if estimates.center is None or estimates.kind != "response_surface":
        raise ValueError("Plotting requires an available point response surface")
    fig, ax = plt.subplots(figsize=(6, 5))
    matrix = np.column_stack([estimates.center[:, t, s] for t, s in ((0,0),(0,1),(1,0),(1,1))])
    image = ax.imshow(matrix, aspect="auto", cmap="viridis")
    ax.set_xticks(range(4), ["mu00", "mu01", "mu10", "mu11"])
    ax.set_ylabel("Node (task order)")
    ax.set_title("Estimated majority-response surface")
    fig.colorbar(image, ax=ax, label="Original outcome scale")
    fig.tight_layout()
    return fig


def plot_effects(estimates):
    import matplotlib.pyplot as plt
    from .evaluation import effect_table
    if estimates.center is None or estimates.kind != "response_surface":
        raise ValueError("Plotting requires an available point response surface")
    values = effect_table(estimates.center)
    fig, ax = plt.subplots(figsize=(7, 4))
    for index, name in enumerate(("Direct", "Spillover", "Total")):
        ax.plot(values[:, index], label=name)
    ax.set(xlabel="Node (task order)", ylabel="Effect on original outcome scale")
    ax.legend()
    fig.tight_layout()
    return fig


def plot_policy(result, *, seed=0):
    import matplotlib.pyplot as plt
    import networkx as nx
    if result.abstain or result.allocation is None:
        raise ValueError("An abstention has no allocation to plot")
    fig, ax = plt.subplots(figsize=(6, 5))
    graph = nx.from_numpy_array(result.task.adjacency)
    nx.draw_networkx(graph, pos=nx.spring_layout(graph, seed=seed), ax=ax,
        node_color=result.allocation, cmap=plt.get_cmap("coolwarm"), vmin=0, vmax=1,
        with_labels=True, node_size=180, font_size=8)
    ax.set_title(f"Allocation: {result.budget_used}/{result.budget}; {result.budget_mode}")
    ax.set_axis_off()
    fig.tight_layout()
    return fig
