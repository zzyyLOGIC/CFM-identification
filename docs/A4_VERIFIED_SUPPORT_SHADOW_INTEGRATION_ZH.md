# Causal-IDFM — A4 VerifiedSupportAdapter + Randomized-Network Shadow Integration

**日期**：2026-10-15
**基础版本**：Identification v1.0 (Taxonomy + Batch + Estimation Handoff)
**状态**：可选 shadow 集成；**不是**生产强制门禁，**不是**新 theorem，**不影响**现有 Estimation/Policy。

## 1. 本次实际新增

- `pfn_pipeline/identification_a4_shadow.py`：显式 typed A4 source、`VerifiedSupportAdapter`、single-arm A4 matcher、可重验 receipts、与原始 `identify()` 的非权威差异评估。
- 历史独立演示检查三节点反例及 ER300 网络的单臂支持。[旧版脚本](https://github.com/zzyyLOGIC/CFM-identification/tree/cb322b4061fe981a8b5fd6fbd39660209c433911/examples/run_randomized_arm_a4_shadow.py)
- `tests/test_a4_shadow_integration.py`：20 个测试（其中 1 个覆盖全部 9 种 D×E 组合），涵盖边界、来源、篡改、独立对拍。
- `.github/workflows/ci.yml`：新增 shadow 测试步骤；其他原测试步骤保持原样。

核心 Identification 代码、原 `TaskSpec`、`IdentificationSpec`、`IdentificationResult`、原 `identify()`、Batch、旧 PFN bridge、Estimation 和 Policy 文件均未改动。**必须通过新的显式入口使用 A4 shadow**。

## 2. 先把数学职责说清楚

已知 `q(T|W)` 和固定 exposure `S_i=g_i(T,W)`。第一条 family 所需 A4 信息是

\[
R_i(a,s;W)=\mathbb E[Y_i^{obs}\mid T_i=a,S_i=s,W].
\]

A4 判断来源能否提供/推导 `R_i`；只有 A5 full-vector randomization、consistency 等因果条件以及 A6 有效域成立，原 theorem 才能将其识别为 design-standardized potential-outcome mean。A4 **不是**任何因果许可；即使观测性数据可推导 `R_i`，也不意味着已经 POINT identified。

### 本次支持的算子及规则

| Declared population operator | 判定 | 说明 |
|---|---|---|
| `NODE_ARM_MEANS`（含当前精确 `(i,a,s)`、绑定 q/g） | `SATISFIED / A4_DIRECT_NODE_ARM_V1` | 直接选择节点 arm 条件均值 |
| `NODE_FULL_LAW`（完整 `P(T_vector,Y_i^{obs}|W)`） | `SATISFIED / A4_NODE_FULL_LAW_TO_ARM_V1` | 从完整分配推导 S，条件化事件，取均值 |
| `FULL_JOINT_LAW`（完整 `P(T_vector,Y_vector^{obs}|W)`） | `SATISFIED / A4_FULL_JOINT_TO_ARM_V1` | 先边际化其他 outcome，再按 arm 条件化 |
| `PAIRWISE_MARGINALS` | `BLOCKED / OPERATOR_NOT_ENTAILED` | 变量出现不意味着三变量联合条件均值已知 |
| `ASSIGNMENT_NODE_MEANS` | `RULE_NOT_IMPLEMENTED` | 暂无可重现完整 `q(z)/pi` 权重覆盖证书，**不是**数学非识别结论 |

只支持当前 family 的**单节点、单 arm、单个声明的信息来源**。多源组合、跨进程签名、固定 policy value、一般 assignment-kernel 分配加权与通用家族路由不在本轮范围。`EXACT_POPULATION_VALUE` 与 `SYMBOLIC_POPULATION_OPERATOR` 有不同含义；有限样本估计不能冒充任何一个。

## 3. VerifiedSupportAdapter 为什么可信、为何不枚举 ER300

原 family 目前在 `SupportEngine.evaluate()` 通过 D1 Poisson-binomial、D2 超几何 / 组合数、D3 两组固定名额条件计数计算

\[
\pi_i^q(a,s\mid W)=P_q(T_i=a,S_i=s\mid W).
\]

新 adapter 调用 **相同的现有 proposer**，再调用该 family 的**独立 verifier 计数函数**：

- D1：平衡生成多项式（对应 `_verify_heterogeneous_joint_support_independently`）；
- D2：完整名额组合数（对应 `_verify_joint_support_independently`）；
- D3：两组名额组合数（对应 `_verify_two_group_joint_support_independently`）。

只有两条结果的精确 `Fraction` 完全一致时，才产出 `VerifiedArmSupportV1`。若旧 `identify()` 已是 `POINT/VERIFIED`，额外通过 `replay_population_identification()` 验证旧 theorem certificate，并对拍它的 `joint_arm_support_probability`。若旧 route 仅被过时的 A4 变量名检查拒绝，则**只**核验 support，不伪造一个新 POINT theorem。

receipt 严格绑定：原 `IdentificationSpec` 指纹、网络身份、q、g、target、完整 treatment-vector 节点顺序、节点 arm、精确支持概率和来源声明摘要。`replay_a4_shadow()` 从原 TaskSpec 和同一 typed source 重算；它不能验证外部来源声明的真伪。

**性能边界**：支持概率检查不枚举 `2^N` 种 assignment；真实 ER300 验证仍可能消耗数十秒（原图是密集 ER，涉及高阶精确分数）。不应让 A4 每次请求都重复验证完整批量 Batch。将来的缓存必须严格绑定可验证 spec digest。

## 4. Shadow 使用方法（明确 opt-in）

```python
from pfn_pipeline.identification_a4_shadow import (
    declare_a4_source, assess_a4_shadow, replay_a4_shadow,
)
# task 是已有官方 builder 生成且可信来源已经人工核对的 TaskSpec。
query = task.identification_spec['query']
# 这里不是自动从变量名单推断。操作者显式声明一个已审核的 population source。
typed_source = declare_a4_source(
    task, source_id='audited:population:arm:1',
    operator='NODE_ARM_MEANS',
    provenance='reviewed study population observable contract',
    admission='ADMITTED', availability='SYMBOLIC_POPULATION_OPERATOR',
    node_order=task.node_ids, outcome_nodes=task.node_ids,
    arm_cells=((query['target_node_id'], query['own_treatment_value'], query['exposure_value']),),
)
shadow = assess_a4_shadow(task, typed_source)
assert replay_a4_shadow(task, typed_source, shadow)
# shadow.legacy_identification 保持原识别输出，无强制 gate；
# shadow.receipt.information_status 仅报告 A4；
# shadow.difference 仅帮助识别旧门禁在 A4 的差异。
```

命令：

```bash
python -B -m unittest discover -s tests -p 'test_a4_shadow_integration.py' -q
python -m pytest tests/test_production_a4_and_business.py tests/test_randomized_network_arm_integration.py
```

## 5. 必须在下一阶段解决的迁移问题

1. **来源真实性与声明冲突**：typed source 是一个经人/协议审核后主动输入的声明，不能因为 user/LLM 写 `ADMITTED` 就成为事实。一个外部对象若与旧 `InformationObject` 冲突，需要显式冲突处理和审核机制。本轮 **没有**实现来源签名或强制门禁。
2. **准确绑定 W / outcome noise scope**：当前绑定到整个现有 `IdentificationSpec` 的指纹和 `W=full_pretreatment_network_context`，仍应在正式跨 family 接口中单独建模 population、W-value、outcome averaging 和数据源身份。
3. **跨进程证书**：本轮 shadow replay 绑定原 TaskSpec 对象身份，未定义 JSON 跨进程证书规范；迁移前必须制定安全的规范化和版本绑定。
4. **真正的多来源/多算子推导**：目前只对一个 source 进行信息匹配；若需多个数据源合并推导，需要明确 joint compatibility，而不是合并变量名单。
5. **Gate migration**：先观察 shadow mismatch，在审查者确认 typed sources 的来源可信、没有向下游错误放行后，才能针对受控 builder 进入强制阶段。强制阶段要由正式 theorem verifier 接纳 A4 receipt，而不是简单把它的状态字符串翻译成 POINT。
6. **D1 dense-ER exact Fraction 成本**：单臂可执行，但批量、反复 replay 的性能优化应利用已验证批量证书的轻量选择器，不能重复枚举或降低精度。
7. **Python 3.11 GitHub Actions**：本机使用 Python 3.13；CI 工作流增加了 shadow 测试步骤，远端运行尚未确认。

## 6. 本轮测试记录与结论级别

- 新模块 `tests/test_a4_shadow_integration.py`：**20/20 PASS**；含九组合 subtests。
- 旧第一条 family 及合同测试已分组通过：`test_randomized_network_arm_integration` 15，`test_two_group_quota_arm_integration` 11，`test_three_level_exposure_arm_integration` 12，`test_randomized_arm_abstraction` 5，`test_heterogeneous_bernoulli_arm_integration` 10，`test_core_collaborator_exposure_arm_integration` 9，`test_batch_identification` 10，`test_identification_estimation_contract` 8，合计 **80/80 PASS**。
- 原 `test_identification_integration` 与 `test_pipeline_smoke` 中较重的工作在本轮执行时限内没有完成；**不能**说 99 项原套件已经全部通过。重跑全量 `discover` 也超时，未发现因此应归因于 Shadow 的具体失败断言。
- 真实 ER300：`python -B -m examples.run_randomized_arm_a4_shadow --er300` 成功执行、POINT/VERIFIED + A4 SATISFIED + receipt replay PASS，单次记录约 16s；无 PFN 调用。
- 尚无外部源真实性验证、远端 3.11 CI 验证或正式 estimator 统计验证。

**定位结论**：v1.4 已进入 v1.0 代码仓库的可选 shadow 路线，但**没有**修改原 `identify()` 默认输出或授权数学上的新 POINT 路由。下一阶段可以考虑可信来源的官方 builder sidecar / gate 迁移，是否进入强制阶段需单独审定。
