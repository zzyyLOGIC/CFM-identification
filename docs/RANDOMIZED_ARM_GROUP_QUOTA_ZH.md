# Randomized-Network POINT family — （D2×E1 + D3×E1）

本页记录早期配额识别方法。现行个人版交付识别和交接，文中的拟合、模拟与策略快照在[历史版本](https://github.com/zzyyLOGIC/CFM-identification/tree/cb322b4061fe981a8b5fd6fbd39660209c433911)。

本文件记录**已进入正式 Identification 引擎**的两种设计。原 `RANDOMIZED_ARM_FIXED_QUOTA_ZH.md` 保留为 v0.3 的 D2 历史说明；v0.4 不修改旧 ER300 iid Bernoulli 的 four-arm PFN demo。

## 1. 同一目标、同一定理

固定处理前上下文 `W`（含 network `G`）。设计给出已知的完整分配律 `q(u|W)`，严格多数暴露为

\[
S_i(u)=\mathbf 1\bigl\{\textstyle\sum_{j\in\mathcal N(i)}u_j>\lfloor d_i/2\rfloor\bigr\}.
\]

针对**一个**节点 `i` 和 arm `(a,s)`，定义联合设计 support：

\[
\pi_i(a,s\mid W)=\sum_{u:u_i=a,S_i(u)=s}q(u\mid W).
\]

当 `π>0` 时，design-standardized arm mean 是

\[
\mu_i^q(a,s\mid W)=\sum_{u:u_i=a,S_i(u)=s}
\frac{q(u\mid W)}{\pi_i(a,s\mid W)}\,\mathbb E[Y_i(u)\mid W].
\]

若 full-vector randomization、consistency、固定处理前 network、已知设计、可积性得到研究者承认，则

\[
\boxed{\mu_i^q(a,s\mid W)=\mathbb E[Y_i^{obs}\mid W,T_i=a,S_i=s].}
\]

**不要求** `Y_i(u)=Y_i(u_i,S_i(u))`；两种设计共享一个 POINT theorem backend。`π=0` 则这一条件目标在原设计下未定义，返回 `UNSUPPORTED / ZERO_ARM_SUPPORT`，不是 PARTIAL。

## 2. D2 和 D3 的差异：只在分配律与 support

- **D2×E1**：从全体 `N` 人均匀抽取恰好 `m` 人，合法 `u` 的概率为 `1/C(N,m)`。
- **D3×E1**：处理前已知两个非空、不相交且覆盖全体的组 `B_1,B_2`；分别均匀抽取恰好 `m_1,m_2` 人，**两组抽样独立**，合法 `u` 的概率为 `1/[C(n_1,m_1)C(n_2,m_2)]`。合作网络的边可以跨组。

D3 下，若 `i∈B_r` 且固定 `T_i=a`，本组剩余 `n_r-1` 人、`m_r-a` 个 treated 名额；另一组配额不变。各组 treated-neighbor count 在条件下分别服从 Hypergeometric，条件独立后卷积，再乘 `P(T_i=a)` 得到**联合** `π_i(a,s)`。

生产 proposer 按此计算；生产 verifier 独立地对原始合法配额分配计数；测试用第三条路径——在小图中直接枚举两组所有合法完整分配。

## 3. 5 人 D3×E1 标准案例

- `B_1={0,1}, m_1=1`，`B_2={2,3,4}, m_2=1`。
- 员工 `0` 的邻居为 `{1,2,3}`，跨组存在网络边，`d_0=3`；只有 `K_0>=2` 才是高（`s=1`）。
- 六种合法完整分配等概率，各为 `1/6`。

| 员工 0 | 低暴露 s=0 | 高暴露 s=1 |
|---|---:|---:|
| 未接受处理 a=0 | 1/6 | 1/3 |
| 接受处理 a=1 | 1/2 | 0 |

`(1,1)` 零 support：员工 0 占了 B1 唯一的 treated 名额，员工 1 必须未处理，第二组又最多一人 treated，所以至多一个邻居 treated。

## 4. 公开调用

```python
from pfn_pipeline import identify, make_two_group_quota_arm_task, replay_population_identification
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec

net = NetworkExposureSpec(
    network_id="known-five-person-graph",
    node_ids=["0", "1", "2", "3", "4"],
    undirected_edges=[("0", "1"), ("0", "2"), ("0", "3")],
)
task = make_two_group_quota_arm_task(
    net,
    groups=(("0", "1"), ("2", "3", "4")),
    treated_quotas=(1, 1),
    node_id="0", own_treatment_value=0, exposure_value=1,
    source="documented synthetic assignment protocol",
    evidence="verified design and group membership",
    admitted=True, synthetic=True, query_authority="TRUSTED_FIXTURE",
)
result = identify(task)
assert (result.status, result.verification_status) == ("POINT", "VERIFIED")
assert result.result["certificate"]["joint_arm_support_probability"] == "1/3"
assert result.estimation_request is None
assert replay_population_identification(result).verification_status == "VERIFIED"
```

运行：`python -m examples.run_two_group_quota_arm`。

真实研究应基于实验协议提供分组和配额，并设置 `synthetic=False, query_authority="HUMAN_CONFIRMED"`；`admitted=True` 只记录研究者对假设的承认，**并不等于程序从数据中检验了假设**。

## 5. 安全边界与未覆盖的范围

- 公开输入 `TaskSpec.assignment_design`、内部 theorem contract、目标 fingerprint 要一致；分组、配额、arm 或 network 修改后不能沿用旧目标证书。
- `POINT / VERIFIED` 是总体识别结论，不代表有限样本中该 arm 有足够数据。
- D2 和 D3 都**没有**匹配的 Estimation/PFN adapter；当已识别时返回 `workflow_status=IDENTIFIED_NO_ESTIMATION_ADAPTER`、`estimation_request=None`。旧的 Bernoulli ER300 PFN demo 不受影响。
- 一个 design-standardized arm mean 不是固定其他人处理不变的 controlled effect；arm-based policy score 也不自动等于 deterministic allocation 的实际 welfare。
- 当前只实现**一个节点、一个二值 exposure arm**；D1、E2/E3、批量查询、PARTIAL、真实政策价值和 UniCo 不属于 v0.4 正式能力。
- 两组 support 的组合计算有资源上限（`MAX_TWO_GROUP_CONVOLUTION_CELLS`）；达到上限会拒绝执行，不会返回近似的 POINT 证书。

## 6. 验收

```bash
python -m pytest -q tests/test_randomized_network_arm_integration.py tests/test_two_group_quota_arm_integration.py
python -m pytest -q tests/test_identification_integration.py tests/test_pipeline_smoke.py
python -m examples.run_complete_randomization_arm
python -m examples.run_two_group_quota_arm
```
