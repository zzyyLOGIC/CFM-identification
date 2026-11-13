# BOUNDED_POLICY_MATH_ZH.md — 有限签名均值界：推广到 30 种 D×E 组合的数学框架

> 对应任务3输出物：`docs/BOUNDED_POLICY_MATH_ZH.md`

---

## 1. 问题形式化

对于有限无向简单图 $G = (V, E)$，每个节点 $i \in V$ 接受二元处理 $t_i \in \{0,1\}$。
处理向量 $\mathbf{t} \in \{0,1\}^{|V|}$ 按某个已知的**设计**分布 $q(\mathbf{t})$ 随机产生。

对于每个节点 $i$，**暴露映射** $S_i(\mathbf{t})$ 将完整处理向量映射到一个暴露空间 $\mathcal{E}_i$。
暴露只依赖于节点 $i$ 的邻居集合 $N(i) = \{j : (i,j) \in E\}$ 和 $i$ 自己的处理值。

给定设计 $q$ 和暴露 $S$，在每个节点 $i$ 定义**签名单元格** $(a_i, e_i)$，其中：

- $a_i \in \{0,1\}$ = 节点 $i$ 自己的处理值
- $e_i \in \mathcal{E}_i$ = 节点 $i$ 的暴露值（依赖于处理向量和暴露定义）


### 目标 1：单政策均值界

给定固定政策 $\mathbf{p} \in \{0,1\}^{|V|}$，目标是识别：

$$\mu(\mathbf{p}) = \sum_{i \in V} w_i \cdot \mathbb{E}[Y_i \mid \mathbf{t} = \mathbf{p}] = \sum_{i \in V} w_i \cdot m_i(a_i, e_i)$$

其中 $w_i$ 是节点权重，$m_i(a_i, e_i) = \mathbb{E}[Y_i \mid t_i = a_i, S_i = e_i]$ 是未知的条件均值。

### 目标 2：两政策对比界

给定两个政策 $\mathbf{p}^{(1)}$ 和 $\mathbf{p}^{(2)}$（共享相同的背景/模型），目标是：

$$\Delta = \mu(\mathbf{p}^{(1)}) - \mu(\mathbf{p}^{(2)}) = \sum_{i \in V} w_i \cdot \bigl(m_i(a_i^{(1)}, e_i^{(1)}) - m_i(a_i^{(2)}, e_i^{(2)})\bigr)$$

两者共享**相同的均值集合** $\{m_i(a,e)\}$，通过**相同的单元格集合**（同一网络、设计、暴露）连接。

---

## 2. 核心：均值集合 $M$ 与可行区域

每个节点的条件均值 $m_i(a,e)$ 受两类约束：

### 2.1 边界约束（Scientific Bounds）

对于每个节点 $i$，有已知区间 $[L_i, U_i]$ 使得对所有 $(a,e)$：

$$L_i \leq m_i(a,e) \leq U_i$$

边界类型可以是：
- `CONDITIONAL_MEAN`：$L_i, U_i$ 是条件均值的（可能宽松的）界
- `ALMOST_SURE_OUTCOME`：$L_i, U_i$ 是结果变量的支撑集

### 2.2 等式约束（A4 Source）

对于部分被**已知 A4 源**覆盖的单元格 $(a_i, e_i)$，均值为精确已知值：

$$m_i(a_i, e_i) = v_{i,a,e}$$

### 2.3 顺序约束（Declared Orders）

对于节点 $i$ 和两个单元格 $c_1, c_2$，已知：

$$m_i(c_1) \leq m_i(c_2)$$

顺序关系由 `NodeOrder` 声明，模式为：

- `OWN`：同暴露值下 $(a=1, e) \geq (a=0, e)$
- `PEERS`：同处理值下 $(a, e=1) \geq (a, e=0)$
- `BOTH`：两者都有

### 2.4 可行均值集

综合所有约束，节点 $i$ 的可行均值集是一个**紧凸多面体** $\mathcal{M}_i \subseteq \mathbb{R}^{|\mathcal{C}_i|}$，
其中 $\mathcal{C}_i = \{(a,e) : a \in \{0,1\}, e \in \mathcal{E}_i\}$ 是节点 $i$ 的单元格集合。

由于所有约束是线性的且单元格之间没有跨节点约束，总可行集是笛卡尔积：

$$\mathcal{M} = \prod_{i \in V} \mathcal{M}_i \subseteq \mathbb{R}^{|\mathcal{C}|}$$

---

## 3. D×E 组合的单元格模式

对于每种 D×E 组合，单元格集合 $\mathcal{C}_i$ 不同：

### E1：strict_majority_ties_low（严格多数）

$$\mathcal{E}_i = \{0, 1\}, \quad e_i = \mathbb{1}\bigl(\sum_{j \in N(i)} t_j > \frac{|N(i)|}{2}\bigr)$$

- 每个节点最多 $2 \times 2 = 4$ 个单元格
- 孤立点：$|N(i)| = 0 \implies e_i = 0$，仅 $2$ 个单元格

### E2：three_level_treated_neighbor_fraction（三分位邻居比例）

$$e_i = \begin{cases}
0 & \text{if } 3\sum t_j < |N(i)| \\
1 & \text{if } |N(i)| \leq 3\sum t_j < 2|N(i)| \\
2 & \text{if } 3\sum t_j \geq 2|N(i)|
\end{cases}$$

- 每个节点最多 $2 \times 3 = 6$ 个单元格
- 孤立点（$|N(i)| = 0$）：E2 在此节点上无定义

### E3：pretreatment_core_collaborator_majority（核心合作者多数）

类似 E1，但只计算预先定义的"核心合作者"集合 $C(i) \subseteq N(i)$：

$$e_i = \begin{cases}
\mathbb{1}\bigl(\sum_{j \in C(i)} t_j > \frac{|C(i)|}{2}\bigr) & \text{if } |C(i)| > 0 \\
0 & \text{if } |C(i)| = 0
\end{cases}$$

- 最多 $4$ 个单元格（同 E1）
- $C(i)$ 在预处理阶段固定声明

### E4：exact_treated_neighbor_count（精确邻居个数）

$$e_i = \sum_{j \in N(i)} t_j \in \{0, 1, \ldots, |N(i)|\}$$

- 每个节点最多 $2 \times (|N(i)|+1) \leq 2|V|$ 个单元格
- 孤立点：$|N(i)| = 0 \implies e_i = 0$，仅 $2$ 个单元格


### E5：any_treated_neighbor（至少一个邻居被处理）

$$e_i = \mathbb{1}\bigl(\sum_{j \in N(i)} t_j > 0\bigr)$$

- 最多 $4$ 个单元格（同 E1）
- 孤立点：$|N(i)| = 0 \implies e_i = 0$，仅 $2$ 个单元格

---

## 4. 支持概率 $q_i(a,e)$

$q_i(a,e) = P(t_i = a, S_i(\mathbf{t}) = e)$ 由设计和暴露共同决定。
对设计 D×暴露 E 的每种组合，不予同的支持概率计算公式：

### D1：HeterogeneousBernoulliDesignV1

$$q_i(a, e) = \sum_{\mathbf{t}: t_i=a, S_i(\mathbf{t})=e} \prod_{j \in V} p_j^{t_j}(1-p_j)^{1-t_j}$$

其中 $p_j$ 是节点 $j$ 的倾向分数。指数级复杂 — 使用 SupportEngine.evaluate() 计算。

### D2：CompleteRandomizationDesignV1

$$q_i(a, e) = \frac{1}{\binom{|V|}{m}} \sum_{\substack{\mathbf{t}: |\mathbf{t}|=m\\ t_i=a, S_i(\mathbf{t})=e}} 1$$

对于 E1 简化后可用组合公式（D2 特有）：

$$q_i(a, e) = \frac{1}{\binom{|V|}{m}} \sum_{k: \mathbb{1}(2k > d)=e} \binom{d}{k} \binom{|V|-d-1}{m-a-k}$$

其中 $d = |N(i)|$。

### D3：TwoGroupFixedQuotaDesignV1

$$q_i(a, e) = \frac{1}{\binom{|G_0|}{m_0} \binom{|G_1|}{m_1}} \sum_{\substack{\mathbf{t}: |\mathbf{t} \cap G_0|=m_0\\ |\mathbf{t} \cap G_1|=m_1\\ t_i=a, S_i(\mathbf{t})=e}} 1$$

如果 $i \in G_0$，则约束 $|\mathbf{t} \cap G_0| = m_0$ 且 $t_i = a$。

### D4：ClusterBernoulliDesignV24

$$q_i(a, e) = \sum_{\substack{\mathbf{t}: t_i=a, S_i(\mathbf{t})=e}} \prod_{C \in \text{clusters}} p_C^{\mathbb{1}(\text{all nodes in C treated})}(1-p_C)^{\mathbb{1}(\text{all nodes in C untreated})}$$

其中 $p_C$ 是簇 $C$ 的处理概率，且簇内所有节点同质处理。

### D5：MultiGroupFixedQuotaDesignV25

类似 D3 但扩展到 $K$ 组，每组有固定配额 $m_k$：

$$q_i(a, e) = \frac{1}{\prod_{k=1}^K \binom{|G_k|}{m_k}} \sum_{\substack{\mathbf{t}: |\mathbf{t} \cap G_k|=m_k \forall k\\ t_i=a, S_i(\mathbf{t})=e}} 1$$

### D6：TwoStageQuotaMixtureDesignV27

涉及多阶段配额混合：

$$q_i(a, e) = \sum_{\text{profiles } (m_1,\ldots,m_K)} \pi_{(m_1,\ldots,m_K)} \cdot q_{\text{MG}}(a, e \mid \text{profile})$$

其中 $\pi$ 是分配概要概率，$q_{\text{MG}}$ 是给定概要下的 D5 类配额概率。

---

## 5. 区间求解方法

### 5.1 均值界问题

对于单政策均值 $\sum w_i m_i(a_i, e_i)$ 和联合约束集，求解：

$$\text{lower} = \min_{m \in \mathcal{M}} \sum_{i} w_i \cdot m_i(\text{target}_i)$$

$$\text{upper} = \max_{m \in \mathcal{M}} \sum_{i} w_i \cdot m_i(\text{target}_i)$$

由于 $\mathcal{M} = \prod_i \mathcal{M}_i$，问题按节点分解：每个节点的单元格独立满足其 box/order/A4 约束，
目标函数中每个节点只有一个单元格有非零权重。

求解策略（derived from `mean_order_solver.py`）：

1. **可行域构建**：对每个节点 $i$，枚举其单元格集合 $\{c_1, \ldots, c_k\}$
2. **边界约束**：$L_i \leq m(c_j) \leq U_i$ 对每个 $j$（两个不等式）
3. **A4 等式**：若已知，$m(c_j) = v_j$（两个不等式等价）
4. **顺序约束**：$m(c_p) \leq m(c_q)$ 对声明的顺序对
5. **锚点枚举**：所有可行顶点是锚点集 $\{L_i, U_i\} \cup \{v_j\}$ 的组合
6. **求值**：对每个可行顶点计算目标函数值，取最小/最大

### 5.2 对比界问题

对于第一政策减第二政策 $\sum w_i (m(c_i^{(1)}) - m(c_i^{(2)}))$：

$$\text{lower} = \min_{m \in \mathcal{M}} \sum_i w_i \cdot (m(c_i^{(1)}) - m(c_i^{(2)}))$$

$$\text{upper} = \max_{m \in \mathcal{M}} \sum_i w_i \cdot (m(c_i^{(1)}) - m(c_i^{(2)}))$$

关键区别：同一节点 $i$ 的两个单元格 $c_i^{(1)}$ 和 $c_i^{(2)}$ 属于**同一个** $\mathcal{M}_i$，
因此系数可以**抵消**。如果两个单元格相同则系数为 0；如果它们共享 A4 已知值则贡献确定。

这不同于分别求两个均值界后相减——分别求会丢失共享信息带来的收缩。

### 5.3 sharp 性证明

如果 lower 和 upper 都由可行解达到，则区间是 sharp 的。
证明方法：

- **Primal 证据**：构造达到 lower（或 upper）的可行均值赋值
- **Dual 证据**：构造非负对偶乘子，证明 lower（或 upper）是最优的
（详见 `mean_order_solver.py` 的 `_dual()` 函数 — 枚举基解并求解对偶乘子）

---

## 6. 端点可达性证明

对每个组合，必须证明端点（lower 和 upper）是可达到的。

### 6.1 孤立点的可达性

对于 E1, E3, E4, E5，孤立点只产生 2 个单元格。只要这些单元格有支持概率 >0
且无矛盾顺序约束，端点可达。

对于 E2，孤立点无定义 → 包含孤立点的网络 + E2 组合需特殊处理。

### 6.2 全零支持概率的处理

如果政策单元格的支持概率为 0，则：
- 对于 POINT：返回 `UNSUPPORTED: ZERO_POLICY_SIGNATURE_SUPPORT`
- 对于 PARTIAL：该政策单元格不参与均值计算

### 6.3 跨组合共享端点

对于对比目标，两个政策共享均值集合。端点可达性等价于存在可行均值赋值
同时满足两个政策的约束。signed-box 处理正是利用这一共享约束来收紧区间。

---

## 7. 无额外资料支持的证明

所有 30 种 D×E 组合的数学框架已完整定义。证明要点如下：

1. **单元格枚举**：对于每种组合，单元格集合 $\mathcal{C}_i$ 由暴露定义和节点度数决定
2. **支持概率**：$q_i(a,e)$ 由设计的分配规律和暴露的分类函数决定 — SupportEngine 对任何设计/暴露都能计算
3. **可行性**：每个 $\mathcal{M}_i$ 是紧多面体（box 约束保证有界，顺序约束只增加 facet）
4. **可达性**：端点因 $\mathcal{M}_i$ 的紧性可达；对偶乘子提供证明
5. **sharp 性**：锚点枚举保证顶点被找到（不存在非顶点使目标函数严格更优而未发现）

### 唯一需要补充的资料

- `bounded_policy_contract.py` 中的 `ExactMean`, `NodeBounds`, `StrictRecord` 等类型
- `bounded_contrast_contract.py` 中的 `VERSION`, `validate_pair`
- `bounded_policy_verify.py` 中的 `replay()` 函数

这些在已提供的 14 个文件中被 import 但未提供源码。如需理解完整接口需要它们。