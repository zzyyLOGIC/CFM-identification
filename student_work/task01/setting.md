# 任务 01 Setting 说明：D1（每人不同 p_i 的独立 Bernoulli）+ E1（严格多数暴露）

## 1. 业务场景

公司向一批销售员随机开放 AI 助手。销售员之间通过固定的合作关系共享客户线索，因此一个个体的业绩既可能受**自己是否有 AI** 影响，也可能受**合作同事中 AI 使用情况**影响（干扰 / spillover）。Identification 要回答：在当前实验设计和假设下，四个 arm mean 能否被总体观测分布唯一确定（POINT）？

本 setting 与 shared baseline 的业务场景完全相同，**唯一区别在随机化协议**：公司不再对所有人用同一个 1/2，而是实验前为每位销售员给定一个**已知的、因人而异的开放概率** $p_i$（例如按地区、工龄、历史业绩分层设定的配额概率），每个人仍然被独立随机开放。

## 2. Setting 定义

- **处理前结构固定**：合作网络 $G=(V,A)$（ER 图）与处理前特征 $X$ 在 assignment 之前确定，$N=|V|$；$d_i=|N(i)|$。
- **Assignment（D1）**：$T_i \sim \mathrm{Bernoulli}(p_i)$，跨个体独立，$0 < p_i < 1$，$p_i$ 实验前已知。邻居的 $p_j$ 不同，因此 $K_i$ 不再是普通 Binomial。
- **Exposure（E1，与 baseline 相同）**：
  $$K_i(t) = \sum_{j \in N(i)} t_j, \qquad S_i(t) = \mathbb{1}\{K_i(t) > \lfloor d_i/2 \rfloor\}$$
  $S_i=1$ 表示"合作同事中严格多数被开放 AI"；正好一半归入 $S_i=0$。
- **Target（design-standardized arm mean，形式与 baseline 相同）**：
  $$\mu_i(t,s) = \mathbb{E}\big[Y_i((t, T_{-i})) \,\big|\, S_i((t,T_{-i})) = s,\; A, X\big], \qquad t\in\{0,1\},\; s\in\{0,1\}$$
  即固定个体 $i$ 自己的处理状态为 $t$，让其他人的处理状态按原实验设计（D1）随机变化，只保留使 $i$ 的暴露状态为 $s$ 的情形再取平均。这是定义的查询分组，不要求"过半状态"是 outcome 的真实充分暴露映射。

## 3. 采用的 Assumptions

| # | 假设 | 来源 |
|---|---|---|
| A1 | 处理前结构固定：$A, X$ 在 assignment 前确定 | 实验设计 |
| A2 | Consistency：$T=t$ 时 $Y_i^{obs} = Y_i(t)$ | 定义 |
| A3 | Full-vector randomization：$T \perp \{Y_i(t): i, t\} \mid A, X$ | 实验协议（不从数据检验） |
| A4 | Query support：$\pi_i(t,s) = P(T_i=t, S_i=s \mid A, X) > 0$ | 代码数值检查 |

## 4. Support：$\pi_i(t,s)$ 怎么来的

因为 D1 下 $T_i$ 与 $T_{-i}$ 独立：

$$\pi_i(t,s) = P(T_i=t)\,P(S_i=s) = p_i^{\,t}(1-p_i)^{1-t}\, q_i(s)$$

其中 $K_i = \sum_{j\in N(i)} T_j$ 是**每个邻居成功概率都不同**的独立 Bernoulli 之和，即 Poisson Binomial：

$$P(K_i=k) = \sum_{A \subseteq N(i),\, |A|=k} \prod_{j\in A} p_j \prod_{j \notin A} (1-p_j), \qquad q_i(1) = P\big(K_i > \lfloor d_i/2 \rfloor\big),\quad q_i(0)=1-q_i(1).$$

代码用 $O(d_i^2)$ 动态规划计算该 PMF（`support.py: poisson_binomial_pmf`）。

**哪些状态可能为 0：**

- $t=0$ / $t=1$：因设计约束 $0<p_i<1$ 恒有正概率；若 $p_i$ 取 0 或 1 则违反 D1 设计，对应 arm support 为 0，查询非法。
- $s=1$（严格多数）：每个 $p_j\in(0,1)$ 使 $K_i$ 在 $\{0,\dots,d_i\}$ 上全支撑，故 $d_i \ge 1$ 时 $q_i(1)>0$；**$d_i=0$（孤立点）时 $K_i \equiv 0$，$S_i \equiv 0$，$\pi_i(\cdot,1)=0$**。
- $s=0$：恒有正概率（$K_i=0$ 的概率 $\prod_{j\in N(i)}(1-p_j) > 0$）。

即本 setting 的零 support arm 恰好是孤立节点的 $(t,1)$。

## 5. 为什么有 support 的 arm 是 POINT

对 $\pi_i(t,s) > 0$，从可观测总体条件均值出发：

$$\begin{aligned}
\mathbb{E}\big[Y_i^{obs} \mid A, X, T_i=t, S_i=s\big]
&= \sum_{t_{-i}:\, S_i((t,t_{-i}))=s} \mathbb{E}\big[Y_i^{obs} \mid A, X, T=(t,t_{-i})\big]\, w(t_{-i}) \\
&= \sum_{t_{-i}:\, S_i((t,t_{-i}))=s} \mathbb{E}\big[Y_i((t,t_{-i})) \mid A, X\big]\, w(t_{-i}) \\
&= \mu_i(t,s) \;=\; \mathbb{E}\big[Y_i^{obs} \mid A, X, T_i=t, S_i=s\big],
\end{aligned}$$

第一行是全概率公式（在 $T_{-i}$ 上分解）；第二行用 consistency（A2）+ full-vector randomization（A3）；第三行即 target 定义。其中 $w(t_{-i}) = P(T_{-i}=t_{-i} \mid A,X,T_i=t,S_i=s)$ 是设计诱导的权重——**D1 下不再均摊，而按各 $p_j$ 倾斜**（这是与 baseline 的唯一实质差别，但不改变识别结论）。右侧只依赖总体观测分布 $P_M(T, Y^{obs}\mid A,X)$，满足 POINT 定义（式 (2)）。

## 6. 与 shared baseline 的差异

只改了随机化设计：$K_i$ 从 $\mathrm{Binomial}(d_i, 1/2)$ 变为 $\mathrm{PoissonBinomial}(\{p_j\}_{j\in N(i)})$，$\pi_i$ 与 $w(\cdot)$ 的具体数值随之改变；POINT 逻辑（式 (3) 的推导）与 support 结构（非孤立点四个 arm 全可达、孤立点只有 $(t,0)$）和 baseline 完全相同。

## 7. 如果某个 arm support = 0

条件事件概率为零时，观测分布不决定该条件均值：全概率公式中的 $w$ 不再是合法条件分布，$\mu_i(t,s)$ 作为"概率零事件上的条件期望"本身也未定义。此时必须**明确拒绝该 query**（`rule.py` 返回 `identified=False` 并给出原因），不能套用上面的 functional；这不是 PARTIAL——是查询未定义。

## 8. 代码验证

`test_rule.py` 包含三类验证：

1. **正常例子**：N=20 ER 图 + 异构 $p_i$，非孤立点四个 arm 全 POINT；DP 计算的 Poisson binomial PMF 与直接枚举邻居子集的独立算法逐项一致；
2. **zero-support / 非法参数**：孤立点 $(t,1)$ 被明确拒绝；$p_i\in\{0,1\}$、$t/s/i$ 越界抛 `ValueError`；缺少 A1/A2/A3 任一条不返回 POINT；
3. **N=7 brute-force 对拍**：枚举全部 $2^7$ 个合法 assignment，按设计概率 $P(T=t)=\prod_i p_i^{t_i}(1-p_i)^{1-t_i}$ 加权，直数每个 $(T_i,S_i)$ 状态频率，与 `support.py` 的 DP 公式逐格一致（含孤立点严格为 0 的格子）。
