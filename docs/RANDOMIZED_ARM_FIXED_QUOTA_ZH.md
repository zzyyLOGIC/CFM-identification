# Randomized-Network POINT Family：第一条正式新增路线（D2 × E1）

本页记录早期配额识别方法。现行个人版交付识别和交接，文中的拟合、模拟与策略快照在[历史版本](https://github.com/zzyyLOGIC/CFM-identification/tree/cb322b4061fe981a8b5fd6fbd39660209c433911)。

本文件只描述已经接入生产 `IdentificationEngine` 的能力，不是九题全部完成集成的声明。
本次改动保留原来的 ER300 `NETWORK_RESPONSE_SURFACE` / majority-score 路线以及 Estimation/Policy 快照。

## 1. 当前支持的 query

- **设计 D2**：已知完整随机化律，`N` 人中恰好均匀随机选 `m` 人，`0 <= m <= N`。
- **暴露 E1**：`S_i(u) = 1{sum_{j∈N(i)}u_j > floor(d_i/2)}`，偶数度数平票归 0。
- **Target**：明确给出一个节点 `i` 和 arm `(a,s)`；只识别这一项，而不是默认要求全部节点四臂都具有正 support。
- **条件化信息**：完整、固定的处理前 `W`（含已知 unit network `G`）；不需要变量层 causal DAG。

使用原始联合随机分配律 `q(u|W)`：

\[
\pi_i(a,s|W)=\sum_{u:u_i=a,g_i(u,W)=s}q(u|W).
\]

当 `π>0` 时，定义 design-standardized target：

\[
\mu_i^q(a,s|W)=\sum_{u:u_i=a,g_i(u,W)=s}
\frac{q(u|W)}{\pi_i(a,s|W)}\,E[Y_i(u)|W].
\]

已承认 **known assignment law、full-vector randomization、consistency、fixed pretreatment network、finite conditional first moments** 时：

\[
\boxed{\mu_i^q(a,s|W)=E[Y_i^{obs}\mid W,T_i=a,S_i=s].}
\]

没有使用 `Y_i(u)=Y_i(u_i,S_i(u))` 的 exposure sufficiency 假设。
如果 `π=0`，这一个条件 arm 目标在原设计下未定义，返回 `UNSUPPORTED / ZERO_ARM_SUPPORT`；它不是 PARTIAL 区间。

## 2. 精确 support（无需枚举所有分配）

`N` 人中固定选 `m` 人，节点 `i` 度数为 `d`，本人处理为 `a`：

\[
P(T_i=a)=(m/N)^a\,((N-m)/N)^{1-a},
\quad
K_i\mid T_i=a\sim\mathrm{Hypergeom}(N-1,d,m-a).
\]

对 `k=0,...,d`，

\[
P(K_i=k\mid T_i=a)
=\frac{\binom d k\binom{N-1-d}{m-a-k}}{\binom{N-1}{m-a}}.
\]

再将 `k` 按严格多数归入 `s`，乘上 `P(T_i=a)` 得到 **联合** support。
不以小浮点阈值判零，使用 `Fraction` 和整数二项式系数。

生产代码有两条计算路径：proposer 用条件超几何；verifier 用

\[
\pi_i(a,s)=\frac{\sum_{k:1\{k>\lfloor d/2\rfloor\}=s}
\binom d k\binom{N-1-d}{m-a-k}}{\binom N m}
\]

进行独立重算。测试再使用第三条路径，即列举小网络所有 `C(N,m)` 个合法分配。

## 3. 调用示例

在仓库根目录执行：

```python
from pfn_pipeline import (
    identify, make_complete_randomization_arm_task,
    replay_population_identification,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec

network = NetworkExposureSpec(
    network_id="three-person-fixture",
    node_ids=["0", "1", "2"],
    undirected_edges=[("0", "1")],
)

task = make_complete_randomization_arm_task(
    network,
    m=2, node_id="0", own_treatment_value=1, exposure_value=1,
    source="synthetic protocol", evidence="documented complete randomization",
    synthetic=True, admitted=True, query_authority="TRUSTED_FIXTURE",
)

result = identify(task)
assert result.status == "POINT"
assert result.verification_status == "VERIFIED"
assert result.result["certificate"]["joint_arm_support_probability"] == "1/3"
assert result.estimation_request is None
verified = replay_population_identification(result)
```

**非合成研究**不得用 `TRUSTED_FIXTURE`；须由研究协议与人工确认明确 `query_authority="HUMAN_CONFIRMED"`、假设来源及其证据。传入 `admitted=True` 只是记录研究者的假设承认，不是程序从数据中证明这些假设真实。

## 4. 与 Estimation / Policy 的边界

新路线已接入 `TaskSpec → IdentificationSpec → IdentificationEngine → IdentificationVerifier → IdentificationResult`，返回：

- `status=POINT`, `verification_status=VERIFIED`；
- 包含 `{node, a, s, m, network, target fingerprint}` 的符号化可观测函数；
- 精确 `joint_arm_support_probability` 和可重算的 proof certificate；
- **`estimation_request=None`**，`diagnostics.workflow_status="IDENTIFIED_NO_ESTIMATION_ADAPTER"`。

这是刻意保持的安全边界：原 PFN 只支持冻结的 Bernoulli majority response 四臂接口，不能将它悄悄复用为固定配额设计的估计器。`replay_population_identification()` 可以验证新 POINT 证书；`replay_handoff()` 必须因为没有估计请求而拒绝。

这也不保证有限样本内观测到相应 arm，更不推出固定分配 `z` 的真实政策收益 `E[Y_i(z)]`。

## 5. 当前未实现与下一步

本次**没有**实现：D1/D3、E2/E3、多节点全 arm 列表批量输出、可执行估计器、确定分配政策 welfare、LLM/UniCo 或 PARTIAL backend。

下一步可以单独添加 `D3×E1` 或 `D2×E2`，检验新设计是否能复用同一个 `RandomizedNetworkArmMeanProgram`，但不能提前声称这些组合已纳入正式 route。设计与 exposure 的插件接口仍需在更多真实案例下审查。

## 6. 验收

```bash
python -m pytest -q tests/test_randomized_network_arm_integration.py
python -m pytest -q tests/test_identification_integration.py tests/test_pipeline_smoke.py
```

第一组包含独立全分配枚举、零 support、退化 quota、孤立节点、assumption gate、指纹篡改、证明 replay 以及 N=300 计算测试。第二组用于保护原有 ER300 全链路。
