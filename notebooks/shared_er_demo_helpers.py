"""Figures and compact displays for the migrated shared-ER notebook."""
from __future__ import annotations

from html import escape

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from IPython.display import HTML, display

import er300_tutorial_helpers as viz


def cards(items):
    """Render short, escaped result cards; values come from the current run."""
    tiles = []
    for label, value, detail in items:
        tiles.append(
            '<div style="flex:1;min-width:170px;padding:16px;border:1px solid #dbe4ec;'
            'border-radius:10px;background:#f7fafc;color:#25364a">'
            f'<div style="font-size:13px">{escape(str(label))}</div>'
            f'<div style="font-size:23px;font-weight:650;margin:8px 0">{escape(str(value))}</div>'
            f'<div style="font-size:12px">{escape(str(detail))}</div></div>')
    display(HTML('<div style="display:flex;gap:12px;flex-wrap:wrap;margin:14px 0">'
                 + ''.join(tiles) + '</div>'))


def details(title, content):
    display(HTML(f'<details><summary>{escape(title)}</summary>'
                 f'<pre style="white-space:pre-wrap">{escape(content)}</pre></details>'))


def _mark_focus(ax, pos, focus):
    ax.annotate("甲", pos[focus], xytext=(13, 12), textcoords="offset points",
                weight="bold", fontsize=12, color=viz.INK,
                bbox=dict(boxstyle="round,pad=.2", fc="white", ec=viz.INK),
                arrowprops=dict(arrowstyle="-", color=viz.INK))


def plot_network(task, focus):
    graph = nx.from_numpy_array(task.adjacency)
    degree = task.adjacency.sum(1).astype(int)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), layout="constrained")
    if graph.number_of_edges() <= 3000:
        pos = nx.spring_layout(graph, seed=2026, iterations=70)
        viz.draw_network(axes[0], graph, pos, task.treatment,
                         viz.exposure(task.adjacency, task.treatment)[2],
                         title=f"完整协作网络：{task.n_nodes} 人 / {graph.number_of_edges()} 条边",
                         focus=focus)
        _mark_focus(axes[0], pos, focus)
        ego = nx.ego_graph(graph, focus)
        local_pos = nx.spring_layout(ego, seed=2026)
        viz.draw_network(axes[1], ego, local_pos, task.treatment,
                         viz.exposure(task.adjacency, task.treatment)[2],
                         title=f"放大甲 与他的 {degree[focus]} 位合作同事", focus=focus)
        states = viz.exposure(task.adjacency, task.treatment)[2]
        nx.draw_networkx_nodes(ego, local_pos, ax=axes[1], node_size=200,
            node_color=[viz.ORANGE if task.treatment[i] else viz.BLUE for i in ego.nodes],
            edgecolors=[viz.TEAL if states[i] else "white" for i in ego.nodes], linewidths=2)
        _mark_focus(axes[1], local_pos, focus)
        axes[0].text(.02, .01, "橙：有 AI；蓝：无 AI；绿圈：同事有 AI 严格过半", transform=axes[0].transAxes,
                     fontsize=8, bbox=dict(facecolor="white", edgecolor="none", alpha=.8))
    else:
        axes[0].imshow(task.adjacency, cmap="Blues", interpolation="nearest", vmin=0, vmax=1)
        axes[0].set(title=f"完整邻接矩阵：{graph.number_of_edges():,} 条边",
                    xlabel="节点顺序", ylabel="节点顺序")
        axes[1].hist(degree, bins=min(24, int(np.ptp(degree))+1), color=viz.BLUE, alpha=.85)
        axes[1].axvline(degree[focus], color=viz.ORANGE, label=f"甲有 {degree[focus]} 位合作同事")
        axes[1].set(title="稠密网络：每人的合作同事有多少？", xlabel="合作同事数", ylabel="销售员人数")
        axes[1].legend()
    return fig


def plot_support(support, task, focus):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout="constrained")
    colors = (viz.BLUE, viz.TEAL, viz.ORANGE, viz.RED)
    rows = support[support.node_id == task.node_ids[focus]].set_index("arm").loc[list(viz.ARM_NAMES)]
    bars = axes[0].bar(viz.ARM_NAMES, rows.probability, color=colors)
    axes[0].bar_label(bars, labels=[f"{p:.1%}" for p in rows.probability], padding=4)
    axes[0].set(title="实验设计：甲 落入每一格的概率", xlabel="(本人 AI, 同事过半)",
                ylabel="设计概率", ylim=(0, max(rows.probability)*1.25))
    states = viz.exposure(task.adjacency, task.treatment)[2]
    counts = [int(np.sum((task.treatment == t) & (states == s)))
              for t in (0, 1) for s in (0, 1)]
    bars = axes[1].bar(viz.ARM_NAMES, counts, color=colors)
    axes[1].bar_label(bars, padding=3)
    axes[1].set(title="这一次实验：300 人各落在哪一格", xlabel="观测 (T,S)",
                ylabel="销售员人数", ylim=(0, max(counts)*1.22))
    return fig


def plot_focus_estimates(predicted, truth, focus):
    fig, ax = plt.subplots(figsize=(10, 3.8), layout="constrained")
    x = np.arange(4)
    for offset, values, color, label in [(-.18, predicted[focus], viz.BLUE, "PFN 估计"),
                                         (.18, truth[focus], viz.TEAL, "独立模拟真值")]:
        bars = ax.bar(x + offset, values.reshape(4), .36, color=color, label=label)
        ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=9)
    ax.axhline(0, color=viz.MUTED, lw=.7)
    ax.set(xticks=x, xticklabels=["00\n无 AI / 未过半", "01\n无 AI / 过半",
                                  "10\n有 AI / 未过半", "11\n有 AI / 过半"],
           ylabel="平均业绩（分数）", title="同一个销售员甲：四个预测与真值相差多少？")
    ax.margins(y=.25)
    ax.legend(loc="upper left", ncol=2)
    return fig


def plot_policy(task, result, focus):
    degree = task.adjacency.sum(1).astype(int)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout="constrained")
    graph = nx.from_numpy_array(task.adjacency)
    title = f"最终分配：{result.budget_used}/{result.budget} 人（橙色入选）"
    if graph.number_of_edges() <= 3000:
        pos = nx.spring_layout(graph, seed=2026, iterations=70)
        viz.draw_network(axes[0], graph, pos, result.allocation, result.resulting_exposure,
                         title=title, focus=focus)
        _mark_focus(axes[0], pos, focus)
        axes[0].text(.02, .01, "与历史网络位置相同；绿圈：同事有 AI 严格过半",
                     transform=axes[0].transAxes, fontsize=8,
                     bbox=dict(facecolor="white", edgecolor="none", alpha=.8))
    else:
        node = np.arange(task.n_nodes)
        axes[0].scatter(node, degree, c=np.where(result.allocation, viz.ORANGE, viz.BLUE),
                        s=18, alpha=.7)
        exposed = result.resulting_exposure.astype(bool)
        axes[0].scatter(node[exposed], degree[exposed], s=45, facecolors="none",
                        edgecolors=viz.TEAL, label="同事有 AI 过半")
        axes[0].set(title=title, xlabel="原始节点顺序", ylabel="合作同事数")
        axes[0].legend()
    if result.trace:
        steps = [r["step"] for r in result.trace]
        axes[1].plot([0, *steps], [result.initial_value, *[r["objective_after"] for r in result.trace]],
                     color=viz.TEAL, lw=2)
    else:
        axes[1].scatter([0], [result.initial_value], color=viz.TEAL)
    axes[1].set(title="贪心过程：预测多数响应评分", xlabel="加入节点的步数", ylabel=r"$\widehat{Q}(z)$")
    return fig
