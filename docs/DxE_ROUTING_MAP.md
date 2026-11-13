# D×E 路由映射 — 任务3：30种组合的完整参数化方案

## 设计 D1–D6 规格

| 编号 | 类名 | 简要描述 | 关键参数 | 源文件引用 |
|------|------|---------|---------|-----------|
| D1 | `HeterogeneousBernoulliDesignV1` | 异质伯努利（各节点独立概率） | `propensities: dict[str, str]` | `support_verifier.py:156` |
| D2 | `CompleteRandomizationDesignV1` | 完全随机化（固定配额） | `m: int` (配额) | `support_verifier.py:164` |
| D3 | `TwoGroupFixedQuotaDesignV1` | 两组固定名额 | `groups: (list[str], list[str])`, `treated_quotas: (int, int)` | `support_verifier.py:168` |
| D4 | `ClusterBernoulliDesignV24` | 簇伯努利（簇内同质） | `clusters: list[list[str]]`, `cluster_probabilities: list[str]` | `support_verifier.py:179` |
| D5 | `MultiGroupFixedQuotaDesignV25` | 多组固定配额 | `groups: list[list[str]]`, `treated_quotas: list[int]` | `support_verifier.py:181` |
| D6 | `TwoStageQuotaMixtureDesignV27` | 两阶段配额混合 | `groups: list[list[str]]`, `quota_profiles: list[list[int]]`, `profile_probabilities: list[str]` | `support_verifier.py:181` |

## 暴露 E1–E5 规格

| 编号 | 分组名 | 简要描述 | classify 逻辑 | 关键参数 |
|------|--------|---------|-------------|---------|
| E1 | `strict_majority_ties_low` | 严格多数：超过一半邻居为1 | `int(count > degree // 2)` 孤立点 e=0 | (无) |
| E2 | `three_level_treated_neighbor_fraction` | 三分位邻居比例：低/中/高 | `0 if 3*count<degree, 1 elif 3*count<2*degree, else 2` | 孤立点：不支持 |
| E3 | `pretreatment_core_collaborator_majority` | 核心合作者多数 | `int(count > degree // 2)` 但只计算 `core_collaborators[node]` | `core_collaborators: dict[str, list[str]]` |
| E4 | `exact_treated_neighbor_count` | 精确邻居个数 | `count` 本身（0..degree） | (无) |
| E5 | `any_treated_neighbor` | 至少一个邻居被处理 | `int(count > 0)` 孤立点 e=0 | (无) |

## 30 种组合的完整路由表

每个组合有唯一的 `route_id = f"{design}_{exposure}"`，例如 `D2_E1`。

```
┌──────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│      │   E1     │   E2     │   E3     │   E4     │   E5     │
├──────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│  D1  │  ✦ D1_E1 │  ✅ D1_E2│  ✅ D1_E3│  ✅ D1_E4│  ✅ D1_E5│
│  D2  │  ✦ D2_E1 │  ✅ D2_E2│  ✅ D2_E3│  ✅ D2_E4│  ✅ D2_E5│
│  D3  │  ✅ D3_E1│  ✅ D3_E2│  ✅ D3_E3│  ✅ D3_E4│  ✅ D3_E5│
│  D4  │  ✅ D4_E1│  ⚠ D4_E2│  ✅ D4_E3│  ✅ D4_E4│  ✅ D4_E5│
│  D5  │  ✅ D5_E1│  ⚠ D5_E2│  ✅ D5_E3│  ✅ D5_E4│  ✅ D5_E5│
│  D6  │  ✅ D6_E1│  ⚠ D6_E2│  ✅ D6_E3│  ✅ D6_E4│  ✅ D6_E5│
└──────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```

图例：
- ✦ = 已有 D2/E1 验证通过基础（原始代码）
- ✅ = 合法组合，可求解
- ⚠ = E2 在孤立节点上无定义（degree=0 时 three_level 未定义），需要额外处理

## 每个组合的单元格模式

### 暴露 E1（严格多数，暴露值域 {0,1}）
对每个节点 `n`，单元格为：
- `(n, 0, 0)`, `(n, 0, 1)`: 自己未处理，邻居数未超过半数 / 超过半数
- `(n, 1, 0)`, `(n, 1, 1)`: 自己已处理，邻居数未超过半数 / 超过半数
- 孤立点（degree=0）：只有 `(n, 0, 0)`, `(n, 1, 0)`

### 暴露 E2（三分位，暴露值域 {0,1,2}）
对每个节点 `n`，单元格为：
- `(n, 0, 0)`, `(n, 0, 1)`, `(n, 0, 2)`: 自己未处理，低/中/高暴露
- `(n, 1, 0)`, `(n, 1, 1)`, `(n, 1, 2)`: 自己已处理，低/中/高暴露
- 孤立点：不支持（`support_verifier.py:69` 明确报错）

### 暴露 E3（核心合作者多数，暴露值域 {0,1}）
与 E1 类似，但只计算 `core_collaborators` 中的节点：
- `(n, 0, 0)`, `(n, 0, 1)`, `(n, 1, 0)`, `(n, 1, 1)`（degree>0）
- 孤立点或无核心合作者：只有 `(n, 0, 0)`, `(n, 1, 0)`

### 暴露 E4（精确邻居个数，暴露值域 {0, 1, ..., degree}）
对每个节点 `n`，单元格为：
- `(n, 0, k)`, `(n, 1, k)` for k in range(degree+1)
- 孤立点：`degree=0` → 只有 `(n, 0, 0)`, `(n, 1, 0)`（0个邻居被处理）

### 暴露 E5（至少1个邻居处理，暴露值域 {0,1}）
E1 的特例（阈值为 count>0）：
- `(n, 0, 0)`, `(n, 0, 1)`, `(n, 1, 0)`, `(n, 1, 1)`
- 孤立点（degree=0）：只有 `(n, 0, 0)`, `(n, 1, 0)`

## 支持概率计算（核心决策）

对于非 D2 设计，`bounded_policy_solver.py:24-31` 中使用的 `comb` 计数公式（`_compile()` 中的 combinatorial counting）是 D2 特有的。对于其他设计，必须使用 `SupportEngine.evaluate()` (生产路径) 或 `support_verifier.verify_joint_support()` (独立验证路径) 来计算支持概率。

### 决策矩阵：使用哪种支持概率计算方法

| 设计 | 生产路径 (SupportEngine) | 独立验证 (support_verifier) |
|------|------------------------|---------------------------|
| D1 | ✅ Bernoulli 支持 | ✅ N≤8 时验证 |
| D2 | ✅ `comb` 公式 + `comb(len(nodes), quota)` | ✅ N≤8 时验证 |
| D3 | ✅ TwoGroup 支持 | ✅ N≤8 时验证 |
| D4 | ✅ Cluster Bernoulli 支持 | ✅ N≤8 时验证 |
| D5 | ✅ MultiGroup 支持 | ✅ N≤8 时验证 |
| D6 | ✅ TwoStage 支持 | ✅ N≤8 时验证 |