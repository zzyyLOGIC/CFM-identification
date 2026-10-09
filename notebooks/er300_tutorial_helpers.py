"""Presentation helpers for the ER300 tutorial; no model fitting or hidden oracle use.

The scoring function deliberately spells out the notebook's Q(z) formula. Policy
selection itself uses pfn_pipeline.optimize_offline. Truth is only accepted by
functions whose arguments explicitly name it, for after-the-fact evaluation.
"""
from __future__ import annotations

import hashlib
from math import comb

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import networkx as nx
import numpy as np
import pandas as pd

BLUE = "#4263A3"
ORANGE = "#DC8240"
TEAL = "#167F80"
INK = "#25364A"
MUTED = "#64748B"
RED = "#BA4F58"
ARM_NAMES = ("00", "01", "10", "11")
EFFECT_NAMES = ("直接效应", "溢出效应", "总效应")


def configure_style():
    available = {item.name for item in font_manager.fontManager.ttflist}
    candidates = ("Microsoft YaHei", "Noto Sans CJK SC", "SimHei", "PingFang SC")
    chosen = next((name for name in candidates if name in available), "DejaVu Sans")
    plt.rcParams.update({
        "font.family": chosen, "axes.unicode_minus": False,
        "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
        "axes.labelcolor": INK, "text.color": INK, "axes.edgecolor": "#CBD5E1",
        "axes.spines.top": False, "axes.spines.right": False,
        "figure.facecolor": "white", "axes.facecolor": "#FAFBFD",
        "savefig.facecolor": "white", "figure.dpi": 110,
    })
    return chosen


def parameter_digest(model):
    digest = hashlib.sha256()
    for name, value in model.model.state_dict().items():
        digest.update(name.encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def exposure(adjacency, allocation):
    degree = adjacency.sum(axis=1).astype(int)
    count = adjacency @ np.asarray(allocation, dtype=int)
    return count, count / degree, (count > degree // 2).astype(int)


def score(adjacency, mu, allocation):
    """Mean majority-response score, never called actual rollout welfare."""
    z = np.asarray(allocation, dtype=int)
    if z.shape != (len(adjacency),) or not np.isin(z, [0, 1]).all():
        raise ValueError("allocation must be a binary vector following the graph order")
    s = exposure(adjacency, z)[2]
    return float(np.asarray(mu, dtype=float)[np.arange(len(z)), z, s].mean())


def top_k(values, budget):
    order = np.lexsort((np.arange(len(values)), -np.asarray(values, dtype=float)))
    result = np.zeros(len(values), dtype=int)
    result[order[:budget]] = 1
    return result


def node_frame(task):
    counts, ratios, states = exposure(task.adjacency, task.treatment)
    return pd.DataFrame({
        "node_id": task.node_ids,
        "员工": [f"E{i + 1:03d}" for i in range(task.n_nodes)],
        "X_任务难度": task.x[:, 0], "T_历史培训": task.treatment,
        "Y_表现得分": task.outcome, "degree": task.adjacency.sum(1).astype(int),
        "K_参训邻居数": counts, "E_参训邻居比例": ratios, "S_严格多数": states,
    })


def plot_flow():
    fig, ax = plt.subplots(figsize=(13, 3.1))
    ax.set(xlim=(0, 13), ylim=(0, 3.1))
    ax.axis("off")
    boxes = [
        (0.1, "模拟数据", "图、X、T、Y\nTaskSpec"),
        (3.35, "因果识别", "目标 + 假设 → 证明\nIdentificationResult"),
        (6.6, "PFN 估计", "前向计算四臂响应\nEstimateBundle"),
        (9.85, "预算分配", "重算暴露与评分\nPolicyResult"),
    ]
    for i, (left, title, sub) in enumerate(boxes):
        ax.add_patch(FancyBboxPatch((left, 1.15), 2.95, 1.5,
            boxstyle="round,pad=0.04,rounding_size=0.12", ec="#D7E1EB", fc="#EFF4F9"))
        ax.text(left + 1.475, 2.22, title, ha="center", fontsize=13, weight="bold")
        ax.text(left + 1.475, 1.62, sub, ha="center", va="center", fontsize=9.5)
        if i < 3:
            ax.add_patch(FancyArrowPatch((left + 2.99, 1.9), (left + 3.25, 1.9),
                arrowstyle="-|>", mutation_scale=13, color=MUTED))
    ax.text(6.5, .42, "独立 reference → 只在事后评估时揭示真值", ha="center", color=TEAL, fontsize=12)
    fig.tight_layout()
    return fig


def plot_data(frame):
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.5), layout="constrained")
    axes[0].hist(frame["X_任务难度"], bins=22, color=BLUE, alpha=.85)
    axes[0].set(title="历史任务难度", xlabel="标准化 X", ylabel="员工数")
    axes[1].hist(frame["Y_表现得分"], bins=24, color=TEAL, alpha=.85)
    axes[1].axvline(0, color=MUTED, lw=1, ls="--")
    axes[1].set(title="表现得分可以为负", xlabel="相对基准的得分", ylabel="员工数")
    counts = frame["T_历史培训"].value_counts().reindex([0, 1], fill_value=0)
    bars = axes[2].bar(["未参训", "参训"], counts, color=[BLUE, ORANGE], width=.55)
    axes[2].bar_label(bars, padding=4)
    axes[2].set(title="历史随机试验中的处理", ylabel="员工数", ylim=(0, max(counts) * 1.2))
    return fig


def draw_network(ax, graph, pos, allocation, states, *, title, focus=None, labels=False):
    nodes = list(graph.nodes)
    nx.draw_networkx_edges(graph, pos, ax=ax, edge_color="#94A3B8" if labels else "#B8C5D3",
                           alpha=.8 if labels else .32, width=1.3 if labels else .65)
    nx.draw_networkx_nodes(graph, pos, ax=ax, nodelist=nodes,
        node_color=[ORANGE if allocation[i] else BLUE for i in nodes],
        edgecolors=[TEAL if states[i] else "white" for i in nodes],
        linewidths=[2.1 if states[i] else .5 for i in nodes],
        node_size=260 if labels else 31)
    if focus is not None and focus in nodes:
        nx.draw_networkx_nodes(graph, pos, ax=ax, nodelist=[focus], node_size=440,
            node_color="none", edgecolors=INK, linewidths=1.8)
    if labels:
        nx.draw_networkx_labels(graph, pos, ax=ax,
            labels={i: f"{i + 1}" for i in nodes}, font_size=8, font_color="white")
    ax.set_title(title, pad=12)
    ax.margins(.12)
    ax.axis("off")


def network_legend(fig):
    handles = [
        Line2D([], [], marker="o", ls="", color=BLUE, label="未参训"),
        Line2D([], [], marker="o", ls="", color=ORANGE, label="参训"),
        Line2D([], [], marker="o", ls="", markerfacecolor="white",
               markeredgecolor=TEAL, markeredgewidth=2, label="绿圈：严格多数邻居参训"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False)


def plot_network_overview(task, graph, pos, focus):
    states = exposure(task.adjacency, task.treatment)[2]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.3))
    draw_network(axes[0], graph, pos, task.treatment, states,
                 title=f"历史试验：{task.n_nodes} 名员工 / {graph.number_of_edges()} 条协作边")
    ego = nx.ego_graph(graph, focus)
    draw_network(axes[1], ego, nx.spring_layout(ego, seed=2026), task.treatment, states,
                 title=f"放大 E{focus + 1:03d} 的一阶邻域（仅显示局部）", focus=focus, labels=True)
    fig.subplots_adjust(bottom=.13, wspace=.08)
    network_legend(fig)
    return fig


def plot_exposure(task, focus):
    d = task.adjacency.sum(1).astype(int)
    k, e, s = exposure(task.adjacency, task.treatment)
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.7), layout="constrained")
    axes[0].hist(d, bins=np.arange(d.min()-.5, d.max()+1.5), color=BLUE)
    axes[0].set(title="度数：协作同事有多少？", xlabel="degree", ylabel="员工数")
    axes[1].scatter(d, e, c=np.where(s == 1, TEAL, BLUE), s=17, alpha=.5)
    axes[1].axhline(.5, color=ORANGE, ls="--", label="严格 > 0.5 才进入 S=1")
    axes[1].scatter([d[focus]], [e[focus]], s=140, facecolors="none", edgecolors=INK)
    axes[1].set(title="连续比例 E 与二元状态 S", xlabel="degree", ylabel="E = K / degree")
    axes[1].legend(fontsize=8, loc="lower right")
    counts = [np.sum((task.treatment == t) & (s == state)) for t in (0, 1) for state in (0, 1)]
    bars = axes[2].bar(ARM_NAMES, counts, color=[BLUE, TEAL, ORANGE, RED])
    axes[2].bar_label(bars, padding=3)
    axes[2].set(title="本次样本的 (T,S) 计数", xlabel="状态：自身处理 / 多数暴露", ylabel="员工数",
                ylim=(0, max(counts)*1.2))
    return fig


def plot_count_weights(degree):
    k = np.arange(degree + 1)
    mass = np.array([comb(degree, int(i)) * .5**degree for i in k])
    mask = k > degree // 2
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.7), layout="constrained")
    axes[0].bar(k, mass, color=np.where(mask, TEAL, BLUE))
    axes[0].set(title=f"degree={degree}：K ~ Binomial(degree, 0.5)",
                xlabel="K：参训邻居数", ylabel="设计概率", xticks=k)
    for state, color in [(0, BLUE), (1, TEAL)]:
        chosen = mask == state
        weights = mass * chosen / mass[chosen].sum()
        axes[1].bar(k, weights, color=color, alpha=.85, label=f"S={state} 内归一化")
    axes[1].set(title="同一个 S 包含多个 K", xlabel="K：参训邻居数", ylabel="条件设计权重", xticks=k)
    axes[1].legend()
    return fig


def plot_prior(frame):
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.6), layout="constrained")
    axes[0].scatter(frame["a"], frame["mean_Y"], color=BLUE, s=65, edgecolors="white")
    for row in frame.itertuples():
        axes[0].annotate(str(row.task_id), (row.a, row.mean_Y), xytext=(4, 4),
                         textcoords="offset points", fontsize=8)
    axes[0].set(title="每个点是一整个模拟任务", xlabel="任务级系数 a（仅教学/评估可见）", ylabel="该任务平均观测 Y")
    axes[1].scatter(frame["mean_X"], frame["treated_fraction"], color=TEAL, s=65)
    axes[1].axhline(.5, color=MUTED, ls="--")
    axes[1].set(title="图固定，X / T / 噪声 / a 随任务变化", xlabel="该任务平均 X", ylabel="该任务参训比例")
    return fig


def plot_model_flow():
    fig, ax = plt.subplots(figsize=(13, 3.2))
    ax.set(xlim=(0, 13), ylim=(0, 3.2)); ax.axis("off")
    entries = [(0.15, 3.5, "事实 + 图", "[300,5] tokens\n[300,300] adjacency"),
               (4.3, 3.4, "已训练 Transformer", "四臂查询 (t,s)\n推断不更新参数"),
               (8.35, 4.4, "四个边际 GMM / 节点", "每臂 π、m、σ → Σ πm\n响应面 [300,2,2]")]
    for left, width, title, body in entries:
        ax.add_patch(FancyBboxPatch((left, .55), width, 2,
            boxstyle="round,pad=0.04,rounding_size=0.12", fc="#EFF4F9", ec="#D7E1EB"))
        ax.text(left+width/2, 2.1, title, ha="center", fontsize=12, weight="bold")
        ax.text(left+width/2, 1.25, body, ha="center", va="center", fontsize=10)
    for x in (3.7, 7.8):
        ax.add_patch(FancyArrowPatch((x, 1.55), (x+.5, 1.55), arrowstyle="-|>", mutation_scale=16, color=MUTED))
    fig.tight_layout()
    return fig


def plot_surfaces(task, predicted, truth):
    order = np.argsort(task.x[:, 0], kind="stable")
    matrices = [predicted[order].reshape(-1, 4), truth[order].reshape(-1, 4)]
    error = matrices[0] - matrices[1]
    low, high = min(m.min() for m in matrices), max(m.max() for m in matrices)
    limit = max(float(np.abs(error).max()), 1e-8)
    fig, axes = plt.subplots(1, 3, figsize=(12, 6), layout="constrained")
    for ax, matrix, title in zip(axes[:2], matrices, ["PFN 估计", "独立模拟真值"]):
        im = ax.imshow(matrix, aspect="auto", cmap="viridis", vmin=low, vmax=high)
        ax.set(title=title, xticks=range(4), xticklabels=ARM_NAMES,
               xlabel="(t,s)", ylabel="按 X 排序的员工（展示顺序）")
    fig.colorbar(im, ax=axes[:2], shrink=.75, label="得分")
    im2 = axes[2].imshow(error, aspect="auto", cmap="RdBu_r", vmin=-limit, vmax=limit)
    axes[2].set(title="估计 − 真值", xticks=range(4), xticklabels=ARM_NAMES, xlabel="(t,s)")
    fig.colorbar(im2, ax=axes[2], shrink=.75, label="误差（分）")
    return fig


def plot_effects(task, predicted_effects, true_effects):
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.2), layout="constrained")
    x = task.x[:, 0]
    for j, name in enumerate(EFFECT_NAMES):
        axes[0, j].scatter(x, true_effects[:, j], s=15, color=TEAL, alpha=.65, label="模拟真值")
        axes[0, j].scatter(x, predicted_effects[:, j], s=13, color=ORANGE, alpha=.5, label="PFN 估计")
        axes[0, j].set(title=name, xlabel="X：任务难度", ylabel="效应（分）")
        axes[0, j].axhline(0, color=MUTED, lw=.8)
        axes[0, j].legend(fontsize=8)
        axes[1, j].scatter(true_effects[:, j], predicted_effects[:, j], color=BLUE, s=16, alpha=.5)
        low = min(true_effects[:, j].min(), predicted_effects[:, j].min())
        high = max(true_effects[:, j].max(), predicted_effects[:, j].max())
        axes[1, j].plot([low, high], [low, high], "--", color=MUTED, lw=1)
        axes[1, j].set(xlabel="模拟真值", ylabel="PFN 估计", title=f"{name}：与 y=x 比较")
    return fig


def plot_marginals(estimates, focus, truth):
    marginal = estimates.diagnostics["marginal_gmms"]
    pi, means, sigma = [marginal[key][focus] for key in ("gmm_pi", "gmm_mu", "gmm_sigma")]
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.4), layout="constrained")
    for j, ax in enumerate(axes):
        grid = np.linspace(np.min(means[j]-3*sigma[j]), np.max(means[j]+3*sigma[j]), 350)
        density = np.sum(pi[j] * np.exp(-.5*((grid[:, None]-means[j])/sigma[j])**2)
                         / (np.sqrt(2*np.pi)*sigma[j]), axis=1)
        ax.plot(grid, density, color=BLUE)
        ax.fill_between(grid, density, color=BLUE, alpha=.14)
        ax.axvline(np.sum(pi[j]*means[j]), color=ORANGE, label="模型均值")
        ax.axvline(truth[focus].reshape(4)[j], color=TEAL, ls="--", label="真值")
        ax.set(title=f"E{focus+1:03d} / μ{ARM_NAMES[j]}", xlabel="响应均值（分）", ylabel="模型密度")
    axes[0].legend(fontsize=8)
    return fig


def plot_policy_pair(task, graph, pos, result):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.4))
    observed_s = exposure(task.adjacency, task.treatment)[2]
    draw_network(axes[0], graph, pos, task.treatment, observed_s,
                 title=f"历史试验 T：{int(task.treatment.sum())} 人参训")
    draw_network(axes[1], graph, pos, result.allocation, result.resulting_exposure,
                 title=f"候选计划 z：{result.budget_used}/{result.budget} 个名额")
    fig.subplots_adjust(bottom=.13, wspace=.08)
    network_legend(fig)
    return fig


def plot_trace(result):
    trace = pd.DataFrame(result.trace)
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.8), layout="constrained")
    axes[0].plot([0, *trace["step"]], [result.initial_value, *trace["objective_after"]],
                 color=TEAL, marker="o", ms=3)
    axes[0].set(title="从全零候选分配出发", xlabel="已加入的员工数", ylabel=r"预测评分 $\widehat{Q}$")
    axes[1].bar(trace["step"], trace["own_gain"], color=BLUE, label="本人贡献")
    axes[1].bar(trace["step"], trace["neighbor_gain"], color=ORANGE, label="邻居贡献", alpha=.9)
    axes[1].plot(trace["step"], trace["marginal_gain"], color=INK, lw=1, label="净增益")
    axes[1].axhline(0, color=MUTED, lw=.7)
    axes[1].set(title="局部改变如何汇总为网络平均增益", xlabel="贪心步数", ylabel=r"$\Delta\widehat{Q}$（已除以 N）")
    axes[1].legend(fontsize=8)
    return fig


def plot_one_step(task, graph, result):
    trace = result.trace
    index = max(range(len(trace)), key=lambda j: len(trace[j]["newly_high_exposure_nodes"]))
    selected = int(trace[index]["selected_node"])
    before = np.zeros(task.n_nodes, dtype=int)
    for item in trace[:index]:
        before[item["selected_node"]] = 1
    after = before.copy(); after[selected] = 1
    shown = {selected, *graph.neighbors(selected)}
    for node in trace[index]["newly_high_exposure_nodes"]:
        shown.update(graph.neighbors(node))
    subgraph = graph.subgraph(sorted(shown))
    subpos = nx.spring_layout(subgraph, seed=2026)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    for ax, z, title in zip(axes, [before, after], ["加入前", "加入后"]):
        draw_network(ax, subgraph, subpos, z, exposure(task.adjacency, z)[2],
                     title=f"第 {index+1} 步：{title} E{selected+1:03d}", focus=selected, labels=True)
    fig.subplots_adjust(bottom=.14)
    network_legend(fig)
    return fig, index


def comparison_frame(task, estimates, result, *, draws=100, seed=2026):
    """Choose baselines using only graph/estimates; return allocations for later scoring."""
    mu = estimates.center
    candidates = {
        "不安排培训": np.zeros(task.n_nodes, dtype=int),
        "PFN + 网络贪心": result.allocation.copy(),
        "度数优先": top_k(task.adjacency.sum(1), task.budget),
        "直接效应优先": top_k(mu[:, 1, 0]-mu[:, 0, 0], task.budget),
    }
    rng = np.random.default_rng(seed)
    random_z = []
    for _ in range(draws):
        z = np.zeros(task.n_nodes, dtype=int)
        z[rng.choice(task.n_nodes, task.budget, replace=False)] = 1
        random_z.append(z)
    return candidates, random_z


def plot_comparison(frame):
    fig, ax = plt.subplots(figsize=(11, 4.2), layout="constrained")
    x = np.arange(len(frame))
    ax.bar(x-.18, frame["预测评分"], .36, color=BLUE, label="PFN 预测评分")
    ax.bar(x+.18, frame["真值评分"], .36, color=TEAL, label="所选分配的真值评分")
    random_rows = np.flatnonzero(frame["策略"].str.startswith("随机").to_numpy())
    for i in random_rows:
        ax.errorbar(x[i]+.18, frame.iloc[i]["真值评分"],
                    yerr=frame.iloc[i]["随机真值标准差"], fmt="none", color=INK, capsize=4)
    ax.set(xticks=x, xticklabels=frame["策略"], ylabel="多数响应评分 Q", title="同一预算上限下的策略比较")
    ax.legend()
    return fig


def plot_frontier(frame):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout="constrained")
    for key, label, color in [("predicted", "贪心计划：预测评分", BLUE),
                               ("reference", "贪心计划：真值评分", TEAL),
                               ("random_reference", "随机计划：真值评分均值", MUTED)]:
        axes[0].plot(frame["budget"], frame[key], "o-", color=color, label=label, ms=4)
    axes[0].set(title="预算增加后，评分怎样变化？", xlabel="名额上限 B", ylabel="多数响应评分 Q")
    axes[0].legend(fontsize=8)
    axes[1].plot(frame["budget"], frame["used"], "o-", color=BLUE, label="实际使用名额")
    axes[1].plot(frame["budget"], frame["exposed"], "s-", color=ORANGE, label="S(z)=1 的员工数")
    axes[1].set(title="直接处理与网络暴露同时变化", xlabel="名额上限 B", ylabel="员工数")
    axes[1].legend(fontsize=8)
    return fig
