# Identification → Estimation：Target & Handoff Contract v1

> 状态：v0.9 的**接口审计合同**；不是新识别定理、PFN 估计器或自动适配器。基于 v0.8 Randomized-Network POINT family 与冻结的 Estimation snapshot。

## 1. 要解决的实际问题

截至 v0.8，Identification 已有 D1/D2/D3 × E1/E2/E3 共九种可组合的 POINT 识别实例，但新的正式入口一次只识别**一个节点、一个 arm**。旧的 ER300 全链路则主要使用 `NETWORK_MAJORITY_RESPONSE_POLICY_SCORE` → 四臂 response dependency → `EstimationRequest` → PFN `[N,2,2]`。

这两个工作流都使用随机网络实验，却不能仅凭 `status=POINT`、`exposure=E1` 或张量形状相同便互相替换。原因是 **causal target 的分配权重、输出覆盖范围、Estimator 训练标签和运行条件必须同时匹配**。

最小原则：**Identification 先独立证明；Estimation 再声明可消费的目标与条件；只有两侧数学和运行合同匹配才能生成可执行请求。**

## 2. 统一的单 arm 因果目标

给定处理前信息 `W=(A,X,...)`、已知联合分配机制 `q_W(t)`、处理前定义的分组 `g_i(t,W)`，令

\[
\pi_i^q(a,s\mid W)=\sum_{\mathbf t}q_W(\mathbf t)\mathbf 1\{t_i=a,g_i(\mathbf t,W)=s\}.
\]

当 `π_i>0`，我们识别的 design-standardized target 为

\[
\mu_i^q(a,s\mid W)=\sum_{\mathbf t:t_i=a,g_i(\mathbf t,W)=s}
\frac{q_W(\mathbf t)}{\pi_i^q(a,s\mid W)}\;\mathbb E[Y_i(\mathbf t)\mid W].
\]

在 full-vector randomization、consistency、已知处理前 `W` 与有限一阶矩下：

\[
\boxed{\mu_i^q(a,s\mid W)=\mathbb E[Y_i^{obs}\mid W,T_i=a,S_i=s].}
\]

这里 `S_i` 是 target-standardization 分组，**不必假设** `Y_i(t)=Y_i(t_i,S_i(t))`。固定配额下的权重来自条件化后的**原联合分配律**；不能偷偷用 Bernoulli 的独立分配律替代。

此 theorem 只保证 **queried arm** 的总体识别；单 arm 的证书不能自动证明全网 `[N,2,S]` 的每个单元都可识别。

## 3. 当前代码中两种重要的任务形态

| 对比项 | 新 Randomized-Network arm family | 冻结 ER300 全链路 |
|---|---|---|
| 公共 query 类型 | `NETWORK_RANDOMIZED_ARM_MEAN` | `NETWORK_MAJORITY_RESPONSE_POLICY_SCORE`（依赖 `NETWORK_RESPONSE_SURFACE`） |
| 查询范围 | 单节点 `(i,a,s)` | 所有节点的四个 `(a,s)`，然后形成 policy score |
| Assignment | D1 异质 Bernoulli、D2 complete、D3 两组固定配额 | iid Bernoulli(1/2) |
| Exposure | E1 严格多数、E2 三档、E3 核心合作者多数 | E1 严格多数 |
| POINT 的总体意义 | 针对 queried arm 的 `μ_i^q(a,s\mid W)` | 四臂 design-standardized response surface |
| EstimationRequest | **当前不生成** | 现有 typed response request（可重放） |
| PFN 输出 | 尚无匹配的 estimator adapter | `[N,2,2]`，arm order `00,01,10,11` |
| Policy | 不自动推出任何 policy value | 使用四臂响应构成的**代理 score**，并非一般的真实 rollout welfare |

**尤其注意：** D1 中令每个 `p_i=1/2` 且使用 E1，会与旧 response *dependency* 有相同的形式化标准化目标（在相同固定 `W`、图、outcome 和分配律下），但是**新单 arm 的证明对象与旧全四臂 response request 仍是不同软件合同**。语义匹配只说明可以进一步设计 adapter，不能绕过现有 verifier/handoff。

## 4. 现在的 PFN 能力边界（根据代码审计）

冻结的 `pfn_pipeline/pfn.py::predict()` 实际要求：

- `outcome_kind == continuous`；
- `exposure_definition == strict_majority`；
- `assignment_probability == 0.5`；
- 四个 arm，输出顺序 `00,01,10,11`，并打包为 `[N,2,2]`；
- 使用实际输入 `X,T,Y` 的 token schema；当前 `TaskSpec.factual_tokens()` 要求一维 `X`，且禁止孤立节点；
- trained checkpoint、训练图匹配、protocol / prior 兼容等**另行在运行时核验**，不由总体 POINT 定理推断；
- GMM head 给出每个 arm 的边际分布，**不代表已得到联合后验或有保证的置信区间**。

D2/D3 即使 E1 形状仍为四臂，也不是 Bernoulli(1/2) 的目标；D1（非均匀 `p_i`）与 E2/E3 同理，不能直接调用旧 PFN。

## 5. 新增只读能力审计接口（）

```python
from pfn_pipeline import (
    identify, inspect_identification_estimation,
    compare_arm_with_legacy_response,
)

identified = identify(task)
report = inspect_identification_estimation(identified)
print(report['identification'])
print(report['estimation'])
```

返回 `contract_version`, `query_type`, `target_semantics`, `target_fingerprint`, `node_count`, `identification`, `estimation`。对于新 family，还包含正式 specification 中的 assignment、exposure、单 arm、正的 population support、`observable_functional` 和**仅供设计接口使用的候选张量形状**；不会宣称整个张量已被一张单 arm 证书覆盖。

`estimation.status` 的三个主要值：

- `NOT_IDENTIFIED`：关键假设、support 或当前 query 证明尚未通过；不能交给 Estimation。
- `NO_ADAPTER`：**总体识别已独立验证**，但缺少目标匹配的正式 EstimationRequest；不代表无法估计，也不能把其当作 PARTIAL。
- `REQUEST_DEFINED_RUNTIME_UNCHECKED`：已有经 replay 的 typed EstimationRequest；**尚未检查**实际模型是否训练、输入样本是否齐全、checkpoint 是否匹配、运行结果是否可靠。

`compare_arm_with_legacy_response(arm, legacy)` 仅检查**一个限定情形**：同一 W/网络下，新 D1 全部 `p_i=legacy p`、E1 的 queried arm，是否与旧四臂 response dependency 的数学语义、联合 support 相符；返回 `aligned=True` **不**发出 `EstimationRequest`。

安全规则：已标记 VERIFIED 的结果会在报告前重新 replay 原 theorem/proof。该审计层不读取 PFN 权重、不改任何 EstimateBundle、不发明 estimator adapter；实际 Estimation 仍调用原 `estimate_effects()` 及 `replay_handoff()`。

## 6. 下一次与 Estimation 负责人对齐时要签字确认的最小合同

| 项目 | 必须明确到什么程度 |
|---|---|
| 目标语义 | 是 `μ_i^q(a,s\mid W)` 还是 `Y_i(z)`，或 policy score？是否按原 `q` 加权？ |
| Assignment | 支持 D1/D2/D3 哪些具体设计？概率/配额是否进入模型输入与训练标签？ |
| Exposure | 支持 E1/E2/E3 中哪些？是否要求处理前 `C_i`？ |
| Arm coverage | 单 arm、完整四臂、六臂还是动态状态集合？有效 support mask 如何表达？ |
| 数据协议 | 输入 `X,T,Y,A` 及 graph order 是否一致？训练数据与在线上下文是否同一目标定义？ |
| Checkpoint | 训练 prior / prediction protocol / graph 适用范围 / outcome scale / OOD 诊断 |
| 不确定性 | 估计后验、采样区间、identified set 必须不同字段，不能混称 partial-ID |
| 停止行为 | 已 POINT 但无适配器、零 population support、缺少样本、checkpoint mismatch 分别如何停止？ |

**首个真正完整 setting 仍推荐：已知固定 ER 网络 + iid Bernoulli(1/2) + E1 + 全四臂 design-standardized response。** 对这条已有运行成功的路径做 target/method/provenance 交叉审核，并以其为新 family 的桥梁；不要先把 D2/D3/E2/E3 塞入未重新训练的 PFN。

## 7. 本次 有意不做的事

- 不训练 PFN、不改 Estimation/Policy snapshot；
- 不从单 arm 结果自动生成 `[N,2,S]` 的 point estimates；
- 不直接让已对齐的 D1×E1 单 arm 复用旧 PFN 请求；
- 不创建第二套公共 `CausalTaskSpec` 或重写九个 theorem contracts；
- 不将旧 Policy 的代理目标等同于真实确定分配 welfare。

现行审计代码为 `pfn_pipeline/identification_handoff_audit.py`。可运行 `python -m pytest tests/test_identification_estimation_contract.py` 复核当前接口。[历史整链演示](https://github.com/zzyyLOGIC/CFM-identification/tree/cb322b4061fe981a8b5fd6fbd39660209c433911/examples/audit_identification_estimation_handoff.py)
