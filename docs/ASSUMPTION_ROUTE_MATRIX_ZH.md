# 识别条件目录：定理前提、信息要求与实现边界

跨入口的最新对照见 [方法条件、实际入口与验证方式](METHOD_CONDITIONS_AND_VERIFICATION_ZH.md)。该表从真实登记及下面的原生条件函数生成说明；本页保留条件的数学含义和兼容接口解释。证书重放不全部采用另一套独立求解实现，各方法的实际核验方式以该表为准。

> 更新：2026-11-24。`implemented_assumption_catalog_v27()` 保留原有八条网络 POINT 路线的兼容范围，**不是当前全库清单**；新增 `legacy_ate_condition_catalog()` 描述旧 ATE 的适用边界。两者都是说明目录，不授予科学许可。实际准入由各方法及证书重放检查决定。

“某方法采用的条件”不等于“任何可识别问题都必须满足的条件”。本文区分：科学前提是否明确采用、总体信息是否足够、概率／图／约束能否计算核对，以及当前代码的规模和格式限制。审核记录不能证明现实中的无混杂、随机化或排除限制成立。

## 1. “假设是有限的”应该怎么理解？

- **有限**：原 v27 兼容目录记录 **8 项**共同前提，并未声称覆盖所有已实现方法（其中 `known_assignment_law` 实质上是设计信息，不是独立的科学因果排除假设）。其他方法使用下面列出的专用合同。
- **不保证有限**：所有可能的因果研究假设并不存在由本系统已列举完毕的有限清单；每种网络映射、节点范围、目标总体、干预版本、W 条件层及假设参数，都可能产生不同的科学断言。
- **不等于可检验**：`CERTIFIED` / `ADMITTED` / `DERIVED` 是**来源与工作流状态**。即使独立 verifier 全绿，也仅表示「如果假设成立、A4/A6 合法，则 POINT 数学公式正确」，绝不是软件以数据证明假设成立。

## 2. v27 网络路线的八个共同前提名称

| 名称（源码） | 层级 | 含义与注意事项 |
|---|---|---|
| `known_assignment_law` | **A4/Design** | 已知完整实验分配律 `q(T\|W)`，不能用观察到的样本频率替代；具体设计范围由原生概率适配器决定，不以旧目录 D1–D6 为总上限 |
| `full_vector_randomization` | A5 | 实验完整处理向量与所有相关潜在结果在条件 `W` 下独立 |
| `consistency` | A5 | 真实观察到的 `Y_i^{obs}` 与实际完整干预版本对应的潜在结果一致 |
| `fixed_pretreatment_network` | A3/A5 | 图结构、暴露参考集合及处理前定义的网络坐标稳定 |
| `finite_conditional_first_moments` | A5/分析条件 | 各目标总体条件均值存在且有限 |
| `mean_signature_sufficiency` | A5/结构 | R2、R3-Signature 及已实现的有限均值 PARTIAL 使用；均值取决于 `(t_i,g_i(t,W),W)`，需绑具体签名与节点；不要求逐点潜在结果相等 |
| `full_vector_conditional_exchangeability` | A5/观测 | R3 要求给定 `W` 时，非随机的完整 treatment 向量与完整潜在结果条件独立；很强的科学假设 |
| `first_stage_profile_no_direct_outcome_effect` | A5/D6 | D6 第一阶段配额或公告 `U` 不能在固定最终 `T` 外直接影响结果；否则应建模 `Y_i(T,U)` |

**其它门禁不应塞进这个目录：** `A4` 的 typed population outcome 观测算子必须足够精细，`A6` 必须逐查询检验正支持、实验配额、孤立节点 exposure 定义等。支持概率是数学/分配律条件，不是一个可以点击「接受」的无混杂假设。

## 3. 保留的八条 v27 Route 要求

| Route | 数学目标 | 共同许可 | 额外 A5 | A4 粒度 / A6 支持 |
|---|---|---|---|---|
| `R1A_RANDOMIZED_ARM` | `q`-standardized node arm | `known q + full-vector randomization + consistency + stable graph + moments` | **不需要 exposure sufficiency** | typed arm / 合法强算子，joint arm 正支持 |
| `R1A_COMPOSITION` | 同一 q/g/W 下的 Direct、Spillover、Total、加权平均 | 与 R1a 相同 | **不需要 exposure sufficiency** | 每个非零线性项有 A4 且正支持 |
| `R1B_FULL_ASSIGNMENT` | 真实完整政策 `V(z)` | 与 R1a 相同 | **不需要 exposure sufficiency** | assignment-level A4，`q(z)>0` |
| `R1B_FINITE_POLICY` | 有限多个已认证 R1b 政策的正权混合 | 各 R1b 分量均合格 | **不需要 exposure sufficiency** | 每个非零分量的完整支持与 A4 |
| `R2_MEAN_SIGNATURE` | 完整政策 `V(z)`，允许 `q(z)=0` | 与 R1a 相同 | **另需签名均值充分性** | 目标节点签名 A4 与逐节点正支持 |
| `R3_FULL_ASSIGNMENT` | 观测完整政策 `V(z)` | full-vector conditional exchangeability + consistency + stable graph + moments | 不需要 exposure sufficiency | 有限明确 `p_obs`、assignment-level A4 与 `p_obs(z)>0` |
| `R3_MEAN_SIGNATURE` | 观测完整政策 `V(z)`，可 off-support | R3 交换性基础 | **另需签名均值充分性** | 目标签名正支持与匹配 A4 |
| `R3_P_STANDARDIZED_EFFECTS` | 观测 `p`-standardized Direct/Spillover/Total | R3 交换性基础 | **不需要 exposure sufficiency** | 对应 arm 的总体均值与正支持；已有有限联合律、乘积律和有限混合的专用表达 |

**D6 条件附加**：若使用 `two_stage_quota_mixture_binary_v2_7`，R1a/R1b/R2 还必须单独接受 `first_stage_profile_no_direct_outcome_effect`。不是 R3 的假设，也不是从 D6 概率法则自然推出的属性。

## 4. 三个容易弄错的科学问题

1. **随机化不等于无干扰**：R1a 可以在完全一般的跨节点干扰潜在结果下识别设计标准化 arm，且**不要求**均值暴露充分性；定义 E1/E5 并不说明潜在结果只受该暴露影响。
2. **更粗的 exposure 能增加支持，但未必科学合理**：例如 E5 Any-treated 的支持较 E4 Exact Count 宽，也意味着在 R2 中接受了**另一种可能更强的均值等同性断言**；不可自动把 E4 的 A5 许可换成 E5。
3. **R3 观测交换性 ≠ 已观测所有相关变量就自然成立**：即使 `p_obs(T|W)` 与 node outcomes 的总体算子全部声明合法，交换性仍是需独立审查的外生科学主张。

## 5. 已实现、但不属于原八条目录的方法

| 方法 | 主要条件与程序检查 | 当前范围与合同来源 |
| --- | --- | --- |
| 观察性共同分层／节点协变量调整 | 个体暴露充分性、给定指定协变量的局部均值交换性、逐层正支持、条件总体均值 | 有限分层／指定节点特征，非任意协变量；`identification_observational_exposure_adjustment.py`、`identification_observational_nodewise_adjustment.py` |
| 有限网络政策均值／政策差 PARTIAL | 随机化、均值充分性、已知总体均值与界；完整保留限制，验证端点可达 | D1–D8/E1–E5 的有限合同，规模和枚举限制独立存在；`bounded_policy_contract.py`、`bounded_finite_contract.py` |
| 均值顺序 PARTIAL | 上述基础加逐节点明确采用的均值顺序；检查可行性、端点和对偶证据 | 当前 D2/E1；`mean_order_contract.py` |
| DAG 后门／广义调整／前门 | 完整图与干预语义；分别计算相应图准则，检查总体分布与支持 | 专用有限二元合同；`dag_backdoor_contract.py` 及各方法 solver；不是无条件覆盖所有 DAG |
| 一般图 ID | 半马尔可夫模型、观测联合律、干预目标；逐步推导及 hedge 证据检查 | 有限离散、单处理和重放资源限制；`dag_id_contract.py`、`dag_id_verify.py` |
| 二元 IV LATE／ATE 界 | 独立性、排除、一致性、无干扰；LATE 另需单调性及非零第一阶段；ATE 界不要求非零第一阶段 | 二元完整条件总体概率，单独科学审核与精确证书；`iv_route_contract.py`、`iv_exact_verify.py` |
| 旧原生 ATE／Manski | 均值存在；sharp 完成模型不能忽略额外限制 | 见下一节和 [旧 ATE 条件说明](LEGACY_ATE_CONDITIONS_ZH.md) |

这些方法的接入状态以 `cfm_id/capability_registry.py` 及各专用入口为准；登记、可读取、数学可执行和允许估计交接是不同状态。

## 6. 旧 ATE 与 Manski 的条件修复

| 规则 | 均值条件 | 不可忽略的模型限制 |
| --- | --- | --- |
| 普通随机 ATE | 有限数值结果域可推出均值存在；否则须明确采用 `finite_conditional_first_moments` 并提供非空依据 | 不补默认假设，未知均值存在性时不返回 POINT |
| 单组 ATE 界／无有效界结论 | 同样需要均值存在；仅有单侧界不够 | 不支持的额外限制、信息或结构应停止；不能通过 p=0/1 绕开均值检查 |
| 二元 Manski 界 | 二元域保证有限均值 | 只对当前完整的基础模型声称 sharp；额外已采用或待定限制应停止；明确不采用的提议不加入模型；较窄二元域也不能沿用原完成见证 |

执行检查与独立重放分别实现；已保存证书不能绕过新增条件。适用性失败返回当前旧接口的 `UNSUPPORTED` 和具体原因，**不作不可识别证明**。数学公式、目标及边界表达式未改变。

## 7. 仍不应宣称覆盖的范围

- 任意高维网络协变量调整、任意额外跨节点限制及任意网络 PARTIAL 模型。
- 动态或处理诱发网络、第一阶段公告直接效应 `Y_i(t,u)`、一般多值连续处理及跨总体迁移。
- 一般选择偏差／缺失数据、代理变量识别等未由专用合同支持的情况。
- 根据有限样本自动证明科学前提成立，或自动训练覆盖所有方法的估计器。

目录用于说明已实现方法；不能通过新增名称、复用别的方法的许可或缩小原文条件来扩大支持范围。
