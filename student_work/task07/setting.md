# Task 07：D3 × E1 的 population 识别说明

## 1. 业务场景

公司给一批销售员随机开放 AI 助手。销售员共享客户线索，所以一个人的业绩既可能受
**自己是否开放 AI**（`T_i`）影响，也可能受 **合作同事是否大量使用 AI**（暴露状态 `S_i`）影响。
Identification 要回答：在当前实验设计与假设下，四个 arm mean 能否被总体观测分布唯一确定。

## 2. 与 shared baseline 的区别

shared baseline 用 D1（每人独立 `Bernoulli(1/2)`）配 E1（严格多数）。本任务只改 **assignment
design**，exposure 仍是严格多数 **E1**：

- **D3（两组分别固定 treated 名额）**：处理前把全部单位划分成两个互不重叠的组 `B1, B2`
  （`B1 ∪ B2 = V`，`B1 ∩ B2 = ∅`），网络边可以跨组。独立且均匀地
  在 `B1` 中抽恰好 `m1` 个 treated、在 `B2` 中抽恰好 `m2` 个 treated：

  ```
  q(t) = 1 / ( C(|B1|,m1) · C(|B2|,m2) )   若 Σ_{i∈B1} t_i = m1 且 Σ_{i∈B2} t_i = m2
       = 0                                  否则
  ```

- **E1（严格多数）**：`K_i(t) = Σ_{j∈N(i)} t_j`，
  `S_i(t) = 1{ K_i(t) > ⌊d_i/2⌋ }`，`d_i = |N(i)|`。
  majority 标签只是 target 的分组标准化，不假设它是 outcome 的真实充分暴露映射。

## 3. Target

对每个节点 `i`，四个按实验设计标准化的 arm mean：

```
μ_i(t,s) = E[ Y_obs_i | A, X, T_i = t, S_i = s ],     (t,s) ∈ {0,1}²
```

并由此形成对比 `τ_i^Direct = μ_i(1,0) − μ_i(0,0)`、`τ_i^Spillover = μ_i(1,1) − μ_i(1,0)`、
`τ_i^Total = μ_i(1,1) − μ_i(0,0)`。

## 4. 采用的 assumptions

1. 处理前结构固定：`A, X` 在 assignment 前确定，相关潜在结果条件一阶矩有限；
2. Consistency：`T = t` 时 `Y_obs_i = Y_i(t)`；
3. Full-vector randomization：`T ⊥ {Y_i(t)} | A, X`（来自实验协议与已知分配律 `q`）；
4. Query support：`π_i(t,s) = P(T_i=t, S_i=s | A,X) > 0`。

## 5. Query-specific support `π_i(t,s)`

设节点 `i` 在组 `g ∈ {B1,B2}`，其邻居按组拆成 `d_own`（同组）与 `d_oth`（另一组）。
给定 `T_i = t` 后，组 `g` 中还需从剩余 `|B_g|−1` 人里抽 `m_g − t` 个 treated，故

```
约定 Hypergeometric(N, K, n) = 总体 N、成功 K、抽取 n（次序：population, successes, draws）

K_own ~ Hypergeometric(|B_g|−1, m_g − t, d_own)
K_oth ~ Hypergeometric(|B_oth|,   m_oth,     d_oth)      两者独立
K_i   = K_own + K_oth
π_i(t,s) = P(T_i=t) · Σ_{k : 1{k > ⌊d_i/2⌋} = s} P(K_i = k)
```

其中 `P(T_i=t) = C(|B_g|−1, m_g−t) / C(|B_g|, m_g)`（即 `t=1` 时为 `m_g/|B_g|`）。
`π_i(t,s)` 由已知设计精确计算（有理数），**不读取任何观测 outcome**，也与 `N = 300` 无关。

### 5.1 具体算例（用于说明“哪些 arm 真的可能出现”）

取 `N=6`：`B1={a,b,c}`，`B2={d,e,f}`（各 3 人，`m1=m2=2`），边
`{a-b, a-c, a-d, d-e, d-f, b-e, c-f}`（含跨组边）。

**节点 b**（`b∈B1`，邻居 `a∈B1` 与 `e∈B2`，`d=2`，`S=1 ⟺ K>1 ⟺ K=2`）：

```
P(T_b=1)=2/3, P(T_b=0)=1/3
t=1: K_own~Hypergeom(2,1,1), K_oth~Hypergeom(3,2,1)  ⇒ P(S=1|T_b=1)=1/2·2/3=1/3
t=0: K_own=1（b 不在 B1 时，B1 剩 2 个名额给 2 人，a 必 treated）, K_oth~Hypergeom(3,2,1)
     ⇒ P(S=1|T_b=0)=2/3

π_b(0,0)=1/9, π_b(0,1)=2/9, π_b(1,0)=4/9, π_b(1,1)=2/9     四个 arm 全部 > 0（都可识别）
```

**节点 a**（`a∈B1`，邻居 `b∈B1`、`c∈B1`、`d∈B2`，`d=3`，`S=1 ⟺ K>1 ⟺ K≥2`）：

```
t=0 ⇒ B1 两个名额全给 {b,c}（a 未 treated），K_own=2，恒有 K≥2 ⇒ S=1 必成立
⇒ π_a(0,0)=0          <-- 该 arm 是空设计单元
π_a(0,1)=1/3, π_a(1,0)=2/9, π_a(1,1)=4/9   其余三个 arm > 0
```

因此 `a` 的 `(0,0)`（以及 `τ_a^Total` 这类用到该 arm 的对比）**不可识别**，`rule.py` 必须拒绝，
而不能对 `π=0` 继续套式(3)。`demo.ipynb` 与 `test_rule.py` 均对此做了断言。

## 6. 为什么是 POINT

对有 support 的 `(i,t,s)`，从可观测总体条件均值出发，按 `w(t_-i) = q((t,t_-i))/π_i(t,s)` 加权：

```
E[Y_obs_i | A,X,T_i=t,S_i=s]
  = Σ_{t_-i : S_i((t,t_-i))=s} E[Y_obs_i | A,X,T=(t,t_-i)] · w(t_-i)
  = Σ_{t_-i : S_i((t,t_-i))=s} E[Y_i((t,t_-i)) | A,X] · w(t_-i)
  = μ_i(t,s)
```

第二行用 consistency 与 randomization，最后一行即定义。右端只依赖总体观测分布
`P(T, Y_obs | A, X)`，故满足点识别 `P_M = P_{M'} ⇒ Q(M) = Q(M')`。

**若 `π_i(t,s) = 0`**：该 arm 是空设计单元，式(3)不成立，必须显式拒绝该 query，而不是套公式。
有限实验中某 arm 恰未出现只是 estimation 困难，不等于 population support 为 0。

## 7. 验证方式

在 `N ≤ 8` 的小图上枚举全部合法 assignment `t`（`B1` 恰 `m1` 个、`B2` 恰 `m2` 个），
按 `q(t)` 对每个 `(T_i, S_i)` 加权求和，与 `support.py` 的解析结果逐格对拍。
`test_rule.py` 覆盖正常例、zero-support / 非法参数例、以及上述 brute-force 对拍。

## 8. 文件

```text
setting.md    本说明
support.py    D3 × E1 的 π_i(t,s)（精确有理数，图规模无关）
rule.py       support>0 且 assumptions 确认 → 返回 POINT functional；否则拒绝该 query
demo.ipynb    业务问题→setting→support→POINT 推导→IdentificationResult，Run All 可跑
test_rule.py  正常 / zero-support / 非法参数 / N≤8 brute-force 对拍
```

未修改 Estimation / Policy，未使用 simulator 的 outcome 真值，未把 `N = 300` 写进识别逻辑。

## 9. 与 shared demo 的对应与结果标注

本任务与 `notebooks/Shared_ER_Identification_Estimation_Policy_Demo.ipynb` 属于同一
randomized-network POINT 家族：目标 `μ_i(t,s)`、五个 assumptions（`known_assignment_law`、
`full_vector_randomization`、`consistency`、`fixed_pretreatment_network`、
`finite_conditional_first_moments`）与严格多数约定（`K_i > ⌊d_i/2⌋`，平局归 0）完全一致。

区别只在 assignment design：shared demo 是 D1（每人独立 `Bernoulli(1/2)`，
`K_i ~ Binomial(d_i, 1/2)`），本任务是 D3（两组各自固定名额，`K_i` 为两个超几何的卷积）。
因此 demo 中“四格概率一定 > 0”的结论在 D3 下不再成立——本任务节点 a 的 `(0,0)=0`
正是 D3 特有的空设计单元。shared demo 的 exposure 约定见 `er300_tutorial_helpers.exposure`
（`count > degree // 2`），与本任务 `support.py` 完全一致。

`rule.py` 的 `IdentificationResult` 采用与仓库一致的字段：

- `status ∈ {POINT, UNSUPPORTED}`
- `verification_status ∈ {VERIFIED, REJECTED}`
- `diagnostics["workflow_status"] ∈ {COMPLETE, NEEDS_INPUT, UNSUPPORTED}`
- `estimation_request` 仅在可执行（POINT）时非 None

状态映射：

| 情形 | status | verification | workflow_status |
|---|---|---|---|
| 有 support 且五个 assumptions 齐备 | POINT | VERIFIED | COMPLETE |
| 未提供假设（`assumptions=None`） | UNSUPPORTED | UNSUPPORTED | NEEDS_INPUT |
| 假设不完整 | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED |
| `π_i(t,s)=0`（空设计单元） | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED |
| 非法 query | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED |
