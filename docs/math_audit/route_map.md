# 任务7：七类审查导航表

基线提交：7a4cb948ee28c74e4bbf1f2f561de74ff4ce6d6a

导航来源：
literature_support/mathematical_contracts.json

说明：
所有路径相对于仓库根目录。
索引定位完成不等于文件内容已核查，
也不等于数学正确性或测试通过已得到确认。

## 一、七类数学文档

| 审查对象 | 优先阅读的项目数学文档 |
|---|---|
| R1a | docs/ABSTRACTION_RANDOMIZED_ARM_ZH.md；docs/R1A_VERIFIED_TARGET_COMPOSITION_ZH.md |
| R1b | docs/R1B_VERIFIED_FULL_ASSIGNMENT_POLICY_ZH.md；docs/NETWORK_CONTRAST_DISPATCH_ZH.md |
| R2 | docs/R2_VERIFIED_MEAN_SIGNATURE_POLICY_ZH.md；docs/R2_POLICY_DIFFERENCE_CONTRACT_ZH.md |
| R3-Full | docs/R3_OBSERVATIONAL_FINITE_POLICY_AND_SIGNATURE_DIAGNOSTICS_ZH.md；docs/R3_POLICY_ENTRY_CONTRACT_ZH.md |
| D2/E1 单政策界 | docs/BOUNDED_POLICY_MATH_ZH.md |
| 两政策联合差值界 | docs/BOUNDED_CONTRAST_MATH_ZH.txt |
| 均值顺序差值界 | docs/MEAN_ORDER_RESEARCH_ZH.txt |

范围提醒：
索引条目可能同时包含多个子路线或组合能力。
本表收录相关文档，不表示其中所有能力均纳入任务7。
R3 仅审指定的 R3-Full，其他 R3 子路线及 DAG 不在本批范围。

## 二、数学实现及相关组合文件

以下路径来自索引；具体职责仍需阅读确认。

### R1a

- pfn_pipeline/_internal/identification/randomized_network_arm.py
- pfn_pipeline/identification_composition.py

待确认：局部均值求解、组合检查、证书验证分别位于哪些函数。
#### 单节点、单 arm 合同初读

- 目标：指定节点在指定 `(自身处理, 同伴暴露)` 状态下，
  按原试点分配律 `q` 在该状态内归一化后的潜在结果加权均值。
- 识别式：在完整向量随机化和一致性等条件下，目标等于
  `E[Y_i^obs | W, T_i=a, S_i=s]`。
- 支持条件：`P_q(T_i=a, S_i=s | W) > 0`。联合支持概率可拆成
  本人接受指定处理的概率，乘以给定本人处理后的指定暴露概率。
- A5：已知联合分配律、完整向量随机化、一致性、
  固定处理前网络及有限一阶矩。单 arm 目标无需均值暴露充分性。
- A4：识别式需要相应的可观测总体条件均值。
  当前实现接受的 A4 来源类型及其校验规则待查。
- 文档中的 D2/D3 × E1/E2 是本次抽象所述范围。
  当前代码的完整支持范围、验证器调用路径及线性组合分支待查。
#### 已有专项测试运行

测试文件：`tests/test_randomized_arm_abstraction.py`。

```powershell
.\.venv-task7\Scripts\python.exe -B -m unittest discover -s tests -p 'test_randomized_arm_abstraction.py' -v
```

实际运行 5 项，耗时 `0.140s`，全部通过。

- [x] 审读 `test_all_combinations_against_original_design_enumeration`
  及其 `oracle`。参考端直接枚举 D2 固定名额名单或 D3 两组名单的组合，
  从网络边独立计算 E1/E2 暴露档，用 arm 命中次数除以全部合法名单数，
  得到联合支持概率，再与 `SupportEngine` 的输出逐项比较。
  两端使用同一份网络和设计输入，参考端不调用生产端的支持计算、
  分配概率计算或暴露分箱方法。此结论限于该测试覆盖的 D2/D3 × E1/E2。
- [x] 审读 `test_verifier_catches_proposer_support_corruption`。
  四节点 D2/E1 用例中，节点 `0` 的 `(1,0)` arm 手算联合支持概率为 `1/2`。
  正常结果为 `VERIFIED`。测试临时让 `SupportEngine.evaluate` 返回
  `(1/2, 1/2, 99/100)`，生成的错误结果被判为 `REJECTED`。
  这组注入值也违反联合概率的乘积关系，测试只断言了最终拒绝状态。
- [x] 运行自建四节点 D2/E1 反例。节点 `0` 的 `(1,0)` arm
  在 6 份合法名单中命中 3 份，联合支持概率为 `1/2`。
  临时将本人处理、条件暴露和联合概率分别设为 `(1/2,1/2,1/4)`。
  三项满足乘积关系，但与原设计不符。在替换生效期间，验证器对原结果
  返回 `VERIFIED`，对注入错误后生成的结果返回 `REJECTED`。

复跑脚本为 `evaluation/math_audit/check_r1a_arm_support.py`。
脚本独立枚举六份名单，核对节点 `0` 的 `(1,0)` 联合支持概率为 `1/2`。
临时注入自洽但与分配设计不符的概率后，原结果仍为 `VERIFIED`，
错误结果为 `REJECTED`。

已补做单 arm 目标值的独立数值对照。自建潜在结果为
`Y_0(t)=t_0*t_1`。节点 `0` 的 `(1,0)` arm 包含三份等概率名单，
潜在结果分别为 `1、0、0`，直接计算的设计标准化均值为 `1/3`。
独立枚举六份试点名单构造观测总体，再按程序返回的节点和 arm
取条件均值，同样得到 `1/3`。程序所需的总体可观测项也与预期一致。
已在 `evaluation/math_audit/check_r1a_arm_support.py` 中跑通。

#### 线性组合合同初读

- 目标：按预先指定的精确有理系数，组合设计标准化的单 arm 均值。
  例如 `DIRECT_i(0) = μ_i^q(1,0) − μ_i^q(0,0)`，
  对应系数为 `+1` 和 `−1`。
- 适用条件：各项共享分配律、暴露规则、背景和结果定义。
  每个非零项都需有正支持、可用的 A4 总体信息及源 Batch 的识别依据。
- A4：合同允许经认可的总体 `NODE_ARM_MEANS`，也允许按白名单
  从 `NODE_FULL_LAW` 或 `FULL_JOINT_LAW` 导出 arm 均值。
  直接提供 arm 均值时，须覆盖所有非零项。
- 四节点 D2/E1 手算参考：节点 `0` 的 `(1,0)` 支持为 `1/2`，
  `(0,0)` 支持为 `1/3`。DIRECT 固定暴露档，两项仍可在不同的完整安排上平均。
- 重放范围：文档说明组合层检查源 Batch 与锚点，并复算本次使用的
  非零项及组合公式。具体实现和拒绝行为待核查。

#### 线性组合专项测试运行

测试文件为 `tests/test_verified_target_composition.py`。

```powershell
.\.venv-task7\Scripts\python.exe -B -m unittest discover -s tests -p 'test_verified_target_composition.py' -v
```

实际运行 23 项，耗时 `0.561s`，全部通过。

- [x] 审读 `test_single_node_direct_spillover_total_are_exact_and_replayed`。
  测试显式列出 DIRECT、SPILLOVER、TOTAL 的预期 arm 与精确系数，
  将程序返回的组合项与手写预期分别代入同一个 `oracle_arm_mean`，
  比较加权总值，并核对重放后的证书摘要。
  该测试未逐项断言 `result.terms` 的坐标和系数。
  后续可直接比较 `(节点, 本人处理, 暴露, 系数)`，
  避免不同组合恰好给出同一总值。
- [x] 审读 `test_group_one_unsupported_arm_blocks_entire_composite`。
  该用例在 D2 设计下设 `m=0`，对节点 `0` 和 `1` 求等权 TOTAL。
  两个节点的 `(1,1)` 正项均为零支持，程序抛出 `CompositionUnavailable`。
  原测试只断言异常类型，未核对 `reason_code`。

  #### 组合项与拒绝原因补查

- DIRECT 逐项对照通过。按 `(节点, 本人处理, 暴露, 系数)` 记录，
  实际两项为 `("0", 0, 0, -1)` 和 `("0", 1, 0, +1)`，
  与手写预期一致，输出为 `DIRECT term match: True`。
- 复跑 D2 `m=0` 的组 TOTAL 用例，实际拒绝原因为 `ZERO_ARM_SUPPORT`。
  该用例中两个节点的正项均无支持，确认这种情况下整个组平均被拒绝。

### R1b

- 原生固定政策实现：`pfn_pipeline/identification_policy_r1b.py`。
- 相关比较实现：`cfm_id/fixed_comparison.py`。
- 示例入口：`examples.run_verified_r1b_fixed_policy`。

#### 已核查的实现与运行结果

- 已初读固定政策合同及 `identify_verified_fixed_policy`、
  `replay_verified_fixed_policy`、`_solve`、`_independent_q` 和 `_policy_formula`。
- 签发与重放共用 `_solve`。支持概率由 `_independent_q`、
  `AssignmentSpec.full_assignment_probability` 和路线记录交叉核对。
  已静态核对 D1、D2 的概率算式，其余设计分支和共享依赖待查。
- 已运行 `tests/test_verified_fixed_policy_r1b.py`，28 项全部通过。
  已审读其中的参考计算、精确权重和错误证书测试。
  现有 oracle 的条件化一侧复用了 `oracle_policy`。
- 四节点 D1 用例中，独立枚举 72 种等可能抽签组合，
  6 种命中目标安排 `(1,0,1,0)`，概率 `1/12` 与证书一致。
- 同一用例的权重为 `(2/3,0,1/3,0)`。符号公式和所需可观测项
  与手写预期逐项一致，保留 `a`、`c` 两个节点，系数分别为 `2/3`、`1/3`。
- 交换公式中的两个节点系数并重算摘要后，重放以
  `POLICY_CERTIFICATE_REPLAY_MISMATCH` 拒绝。原证书重放通过。

- 新增自建总体的政策值数值对照。枚举独立抽签与四种等概率潜在结果类型，
  得到目标安排下 `a`、`c` 的观测总体条件均值分别为 `3/4`、`1/4`。
  从潜在结果直接计算与代入项目实际生成的符号公式均得到 `7/12`。
  该检查已在 `evaluation/math_audit/check_r1b_fixed_policy.py` 中跑通。
#### 复跑入口与后续审查范围

- D1 独立计数、公式对照和系数错配检查已归档至
  `evaluation/math_audit/check_r1b_fixed_policy.py`。
  脚本核对完整安排概率 `1/12`、公式及所需可观测项，
  并验证重算摘要后，错配的节点系数仍被重放拒绝。
- 有限政策混合及其重放、`cfm_id/fixed_comparison.py`、
  其他设计分支和共享依赖仍待审读。
- 详细运行记录见 `night1_notes.md` 的 R1b 部分。

### R2

- pfn_pipeline/identification_policy_r2.py
- cfm_id/workflows/policy_difference.py

待确认：原生政策均值求解和验证函数；
区分单端识别与有序差值组合检查。
#### 固定政策均值合同初读

- 目标：固定完整政策 `z` 下，各节点潜在结果均值的加权平均。
- 额外 A5：均值签名充分性须经实质审阅并明确采用。
  对每个正权重节点，在所有完整安排下，相同的
  `(本人处理, 同伴暴露)` 对应相同的潜在结果均值。
- 支持条件：原试点下，每个正权重节点的目标签名都须有正支持。
  完整目标安排的概率 `q(z)` 可以为零。
- A4：须提供或能导出每个正权重节点在目标签名下的总体条件均值。
  直接提供时须覆盖每个所需的 `(node,a,s)`。
- 手算参考：Star-5、D2 每轮选四个、目标为五个全选。
  `q(z)=0`，中心 `(1,1)` 的支持为 `4/5`，
  每个外围网点 `(1,1)` 的支持为 `3/5`。
  已与 Star-5 专项测试的逐项断言对照，结果一致。

#### 已有专项测试运行

测试文件为 `tests/test_verified_signature_policy_r2.py`。

```powershell
.\.venv-task7\Scripts\python.exe -B -m unittest discover -s tests -p 'test_verified_signature_policy_r2.py' -v
```

实际运行 18 项，耗时 `0.116s`，全部通过。

- [x] 审读 `test_star_off_support_majority_succeeds`。
  Star-5 全用政策的完整安排概率为 `0`，中心签名支持为 `4/5`，
  四个外围节点各为 `3/5`，测试逐项断言了这些值，与手算一致。
  R2 证书重放通过。同一政策交给 R1b 时抛出 `R1bPolicyUnavailable`，
  该用例未断言 R1b 的具体原因码。
- [x] 审读 `test_critical_zero_signature_class_support`。
  D2 配额为 `m=0`，全用政策所需的受处理签名无支持。
  测试明确断言 R2 拒绝原因为 `ZERO_POLICY_SIGNATURE_SUPPORT`。

#### 参考计算与证书修改测试审读

- `independent_oracle` 枚举完整二元安排，自行累加各签名的
  概率与加权结果。单份安排概率复用 `AssignmentSpec`，
  邻居选择及暴露分箱复用 `ExposureSpec`。该用例可核对构造模型
  中的政策均值关系，但对分配概率和暴露分箱的核查仍有共享依赖。
- `test_source_and_certificate_tampering_even_forged_digest` 覆盖
  多种证书修改。将 `identified_functional` 改为 `'1'` 并重算摘要后，
  测试明确断言重放以 `R2_CERTIFICATE_REPLAY_MISMATCH` 拒绝。

#### Star-5 目标签名的独立计数核对

D2 每轮从五个节点中选四个，目标政策为五个节点全用。
参考端直接枚举漏选的节点，并按星形网络的严格多数规则计数。
按中心、四个外围节点的顺序，目标状态 `(1,1)` 的命中次数
为 `[4,3,3,3,3]`，支持概率为 `[4/5,3/5,3/5,3/5,3/5]`。

项目输出 `Full policy probability: 0` 和
`Signature and support match: True`。
本次逐项核对了节点、本人处理、暴露档及其支持概率。

复跑脚本为 `evaluation/math_audit/check_r2_star5_support.py`。
脚本独立枚举五份试点名单，逐项对照节点、目标签名和支持概率，
并核对完整政策概率为 `0`、原证书重放通过。

- 已补做 Star-5 政策值的独立数值对照。直接干预计算得到 `7/20`。
  从试点总体分别计算五个节点的目标签名均值，再按项目返回的
  签名坐标与权重加总，同样得到 `7/20`。
  该检查已在 `evaluation/math_audit/check_r2_star5_support.py` 中跑通。

#### 有序政策差值合同初读

- 目标为 `V(z_plus) - V(z_minus)`。两项政策都须指定完整处理安排。
  交换两项政策后，差值的符号应反转。
- 两端须使用同一研究、设计、固定处理前网络、背景、结果定义、
  评价权重、A4 来源、签名定义、均值充分性声明及基础假设。
- 两端均须通过原生 R2 识别与重放。完整政策安排可以是零支持，
  但每一端的正权重节点都须有目标签名正支持和对应的 A4 总体信息。
  只有一端通过时，不签发完整差值。
- 已审读 `cfm_id/workflows/policy_difference.py`。
  `_verified_endpoints` 重放两份 R2 端点证书，分别核对它们是否对应
  外部目标的第一、第二项政策，并检查两端使用共同的研究和科学模型。
  `compose` 给第一端正系数、第二端负系数。`replay` 从外部目标
  重建并核对有符号的逐项记录和差值公式。
- 已审读 `tests_gateway/test_contrast_method_diagnostics.py` 中的单端失败用例。
  R2 第二端为 `POINT`、第一端为 `UNSUPPORTED` 时，不报告差值证书，
  也未触发 PARTIAL 回退。同文件得到 `-1/5` 的反向测试属于联合差值界。
- [x] 运行 R2 正向与反向比较，并分别生成对应的审核记录。
  两项政策的安排不同，两个方向均返回 `POINT`。
  逐项核对确认：同一政策换边后，节点、处理安排、暴露和可观测项
  均对应一致，系数恰好反号。
- [x] 保持原比较目标和绑定，交换两份各自有效的 R2 端点证书。
  原证书重放返回 `True`，两项政策的安排确实不同。
  交换证书后，`compose` 以 `ENDPOINT_TARGET_MISMATCH` 拒绝，
  确认本例会检查有效证书是否放在了外部目标指定的位置。

  #### 有序差值实现初读

已读 `cfm_id/workflows/policy_difference.py`。

- `_verified_endpoints` 重放两端的 R2 POINT 证书，并分别核对
  各端处理安排、节点顺序和权重与外部比较目标一致。
  同时核对两端的研究、签名、均值充分性、A4 来源和假设一致。
- `compose` 将第一端各节点系数设为 `+weight`，第二端设为
  `-weight`，生成 `(第一端公式) - (第二端公式)`。
- `replay` 检查回执摘要与外部目标、绑定及两端摘要，再按外部
  目标的节点顺序和权重重建有符号项，比较保存的项及公式。
- 静态核查预期：只交换两份对应不同安排的有效证书、保留原目标时，
  `compose` 应抛出 `ENDPOINT_TARGET_MISMATCH`。


### R3-Full

- pfn_pipeline/identification_observational_r3.py

相关业务连接：

- cfm_id/network_observational_policy_dispatch.py
- cfm_id_llm/network_observational_policy_reading.py

已定位签发入口 identify_observational_policy_v23 和重放入口 replay_observational_policy_v23，并在固定背景代表案例中调用。其他实现分支待审。
业务分派、读取模块不直接视为数学求解器。
#### 固定背景下的观测政策均值合同初读

- 目标为给定 `W=w` 时，固定完整政策 `z` 下各节点潜在结果均值的加权平均。
  固定一个背景层，只对节点求和。
- A4 为同一经认可来源声明的完整条件分配总体分布，以及所有正质量安排下
  的节点条件均值算子。有限样本频数与均值不能替代该总体信息。
- A5 为完整向量条件交换性、一致性、固定处理前网络及有限一阶矩。
  观察到正概率不能代替对交换性的独立确认。
- A6 要求完整目标安排的观测概率严格为正。
  由交换性和一致性，逐节点识别为 `E[Y_i^obs | T=z, W=w]`，再加权求和。
- 本次审查聚焦 R3-Full。最多 12 个节点、4096 个显式正质量安排格子
  是文档所述软件域限制。其余实现分支和拒绝场景待核查
  #### 已有专项测试运行

测试文件为 `tests/test_observational_r3_and_signature_diagnostics.py`。

```powershell
.\.venv-task7\Scripts\python.exe -B -m unittest tests.test_observational_r3_and_signature_diagnostics -v
```

实际运行 28 项，耗时 `0.126s`，全部通过。
该测试文件同时覆盖 R3-Full、R3-Signature 和配额诊断。

- [x] 审读 `test_full_observational_policy_success_and_replay`。
  目标 `(1,0,1)` 的观测概率为 `2/3`，签发走 `R3_FULL_ASSIGNMENT`，
  重放通过。测试确认有三个节点项，未逐项核对识别公式。
- [x] 审读 `test_observational_assumption_proposal_rejected`。
  目标 `(0,0,0)` 的观测概率为 `1`，但完整向量条件交换性仅为
  `PROPOSED`，测试核对了 `NEEDS_INPUT`。
- [x] 审读 `test_zero_full_support_without_sufficiency`。
  使用正例同款基础 A5，完整目标安排零支持时，测试核对了
  `ZERO_OBSERVATIONAL_FULL_ASSIGNMENT_SUPPORT`。


#### 固定背景下的识别公式逐项核对

复用 R3-Full 正例，目标安排为 `(1,0,1)`，背景标签为 `W=w0`。
程序生成三项，分别对应 `n0`、`n1`、`n2`，系数均为 `1/3`。
三项都条件于同一个完整处理安排和背景，与手写预期一致。

显示细节：公式中的 `W=W=w0` 来自 `W=` 前缀与背景标签 `W=w0` 的拼接。

- 已补做固定背景下的目标值独立数值对照。构造观测安排与潜在结果类型
  条件独立的合成总体，得到目标安排下三个节点的条件均值
  `3/4`、`3/8`、`1/8`。直接干预计算与代入项目实际输出的符号公式
  均得到 `5/12`。已在 `evaluation/math_audit/check_r3_full_policy.py` 中跑通。

#### 证书修改测试审读

已审读 `test_replay_catches_fingerprint_and_derived_formula_tampering`。
已有测试分别修改节点支持概率、识别公式和路线，检查重放是否拒绝。
其中一个用例把公式改为 `'fake'`，重算证书摘要后，
明确检查拒绝原因为 `R3_CERTIFICATE_REPLAY_MISMATCH`。

补查通过。原证书目标为 `(1,0,1)`，重放返回 `True`。
保持该目标不变，将公式三项的条件安排改为同一观测总体中
另一份有正支持的安排 `(0,0,0)`，并重算证书摘要。
修改版重放以 `R3_CERTIFICATE_REPLAY_MISMATCH` 拒绝。
本例确认重放能发现识别公式引用了与证书目标不一致的完整安排。

复跑脚本为 `evaluation/math_audit/check_r3_full_policy.py`。
脚本核对目标安排的观测概率 `2/3` 和三项符号公式，并确认
原证书重放通过。保留原目标，将公式改为另一份有正支持的安排
后重算摘要，修改版仍以 `R3_CERTIFICATE_REPLAY_MISMATCH` 被拒绝。

### D2/E1 单政策界

- 合同与输入校验：`cfm_id/bounded_policy_contract.py`。
- 求解：`cfm_id/bounded_policy_solver.py`。
- 验证：`cfm_id/bounded_policy_verify.py`。

#### 已核查的实现与运行结果

- 已初读数学合同，并审读验证器的 `replay`、`_check` 和共享的
  `validate_model`。`_check` 自行枚举 D2 合法名单，重算 E1 严格多数
  暴露及支持概率，检查两张端点均值表是否满足全部已声明 A4 和有效均值界，
  并将两张表分别代入政策目标核对端点。求解与重放共享输入和模型校验。
- 七网点全用案例中，独立枚举 35 份试点名单。中心的目标状态支持为 `0`，
  六个外围网点各为 `1/7`。七项支持概率及区间 `[3/7,4/7]`
  均与项目输出一致。
- 复用七网点测试用例，原证书重放通过。把中心 `(1,1)` 的 `lower_world`
  从 `0` 改为 `1/2`，保留声称的下界 `3/7` 并重算摘要。
  修改后的均值表仍满足 A4 和有效均值界，但代入目标得到 `1/2`，
  修改版重放返回 `False`。
- 二元结果边界对照中，将中心的 `[1/4,3/4]` 设为条件均值界时，
  求解得到 `[13/28,15/28]`。改为逐结果界时，求解器以
  `EMPTY_BINARY_OUTCOME_SUPPORT` 拒绝。

#### 复跑入口与后续审查范围
- 求解器内部及共享输入校验的其他边界仍待核查。
- 详细运行记录见 `night1_notes.md` 的 PARTIAL 部分第 12–15 小节。

- 七网点枚举和下界见证反例已归档至
  `evaluation/math_audit/check_bounded_policy_star7.py`。
  脚本重新生成证书，核对七个节点的支持概率与区间 `[3/7,4/7]`，
  并确认原证书通过重放、修改版被拒绝。
- 二元边界类型对照的运行结果见 `night1_notes.md`，对应脚本待归档。

### 两政策联合差值界

- cfm_id/bounded_contrast_contract.py
- cfm_id/bounded_contrast_solver.py
- cfm_id/bounded_contrast_verify.py

待确认：共同模型、共享未知量、比较方向及端点检查。

#### 联合差值数学合同初读

- 目标为同一研究、背景和评价权重下的 `V(A) - V(B)`。
  两项政策共用一张潜在结果均值表。合并坐标时必须同时匹配
  节点、本人处理和暴露档，并依赖覆盖全部安排的均值充分性。
- 先合并净系数，再求界。正系数求下界时取均值下界，
  负系数求下界时取均值上界。求上界时反过来。
- 净系数为零的坐标无需为计算差值补 A4；所有已经提交的 A4
  仍须与科学界相容。非零净系数坐标若有正支持，则须提供精确 A4。
- 手算参考：`V(A)=x/2+3/10`、`V(B)=x/2+1/10`，其中 `x∈[0,1]`。
  共享项抵消后，差值识别集为 `{1/5}`。
  分别求单政策区间再相减，只得到外界 `[-3/10,7/10]`。
- sharp 性要求两张完整均值表分别达到上下界，并满足全部 A4 与科学界。
  在本合同的直积区间模型下，两张端点表的凸组合覆盖中间值。

#### 已有专项测试运行

测试文件为 `tests_gateway/test_bounded_contrast.py` 和
`tests_gateway/test_bounded_contrast_replay.py`。

```powershell
.\.venv-task7\Scripts\python.exe -B -m unittest tests_gateway.test_bounded_contrast tests_gateway.test_bounded_contrast_replay -v
```

实际运行 22 项，耗时 `6.016s`，全部通过。

- [x] 审读 `test_two_uncertain_policies_have_identified_difference`。
  联合差值为 `POINT`，上下界均为 `1/5`，证书重放通过。
  两项单政策的点识别评估为 `UNSUPPORTED`。
  此测试未单独求两项政策值各自的 sharp 区间。
- [x] 审读 `test_negative_coefficient_world_must_achieve_shared_endpoint`。
  原证书中，负系数项在差值下界世界取该均值上界，
  在差值上界世界取该均值下界。交换两张表中的这一对值并重算摘要后，
  重放返回 `False`。

#### 共享未知均值的独立复算

四节点案例中，两项政策共用 `x∈[0,1]`，政策值分别为
`V(A)=x/2+3/10` 和 `V(B)=x/2+1/10`。

- 独立算得政策 A 的区间为 `[3/10,4/5]`，政策 B 的区间为 `[1/10,3/5]`。
- 两个区间直接相减得到外界 `[-3/10,7/10]`。
- 在同一张均值表中计算差值，共享的 `x/2` 抵消。
  枚举 `x=0,1` 后，联合参考区间为 `[1/5,1/5]`。
- 项目 `different_policies_cancel_unknown` 用例同样返回 `[1/5,1/5]`，
  实际输出为 `Joint match: True`。

复跑脚本为 `evaluation/math_audit/check_bounded_contrast_cancellation.py`。
从仓库根目录运行 `python -m evaluation.math_audit.check_bounded_contrast_cancellation`。
脚本打印两项单政策的参考区间和区间相减的外界，并核对项目返回
`POINT` 且联合差值区间为 `[1/5,1/5]`。
### 均值顺序差值界

- cfm_id/mean_order_contract.py
- cfm_id/mean_order_solver.py
- cfm_id/mean_order_verify.py

相关业务连接：

- cfm_id/network_mean_order_dispatch.py

待确认：顺序约束、目标差值、求解与验证的具体函数。
#### 均值顺序数学合同初读

- 目标仍为同一研究和评价权重下的 `V(A) - V(B)`。先合并同一
  节点、同一签名的系数，再在共同均值表上优化差值。
- `OWN` 固定暴露，限制本人使用后的均值非减。`PEERS` 固定本人
  处理，限制同伴暴露升高后的均值非减。`BOTH` 同时采用两者，
  但不规定 `h10` 和 `h01` 的相互顺序。
- 顺序是额外的科学假设，作用域须覆盖所有完整二元安排。
  顺序限制会耦合同一节点的不同签名，不能沿用逐坐标独立取端点的
  mean-box 算法。
- 手算参考：K4、D2 每轮选四组中的两组，目标为全用减全不用。
  固定 A4 为 `h10=3/5`、`h01=2/5`。在 `BOTH` 下，
  `h11≥3/5`、`h00≤2/5`，且两端可达，sharp 区间为 `[1/5,1]`。
- 证书须核对端点表满足全部约束、代入目标达到所报值，
  并证明界外不可能。研究文档给出了精确有理数对偶证书的方案。
  当前实现和已接入范围待与专项测试及后端说明核对。

#### 已有专项测试运行

测试文件为 `tests_gateway/test_mean_order.py`。

```powershell
.\.venv-task7\Scripts\python.exe -B -m unittest tests_gateway.test_mean_order -v
```

实际运行 31 项，耗时 `1.270s`，全部通过。

- [x] 审读 `test_same_problem_relaxation_ladder`。
  测试逐层比较排除 `node_orders` 后的完整模型输入，确认政策目标、
  A4 及其余字段保持一致。`BOTH`、`OWN`、`NONE` 的预期区间依次为
  `[1/5,1]`、`[-1/5,1]`、`[-1,1]`，与合同推导一致。
  `informative_relative_to_bounds_only` 在前两层为 `True`，
  在 `NONE` 层为 `False`。
- [x] 审读 `tests_gateway/test_mean_order_replay.py` 的对偶与端点反例。
  保留原端点表、仅改坏对偶证据并重算摘要时，重放拒绝。
  将两张端点表取中点，并把可达的 `3/5` 冒充最优下界或上界时，
  重算摘要后重放也拒绝。测试分别核查了可达性与最优性。

重放专项测试命令：

```powershell
.\.venv-task7\Scripts\python.exe -B -m unittest tests_gateway.test_mean_order_replay -v
```

实际运行 14 项，耗时 `1.675s`，全部通过。

#### 固定目标与 A4 的顺序阶梯独立复算

沿用 K4、D2 每轮选两组、四组等权的案例。目标固定为全用减全不用，
A4 固定为每个节点的 `h01=2/5`、`h10=3/5`。

参考端用精确分数枚举 `h00` 和 `h11` 的候选端点，
按各层顺序限制筛选可行组合，再计算 `h11-h00` 的最小值与最大值。

| 顺序假设 | 独立参考区间 | 项目区间 |
|---|---|---|
| BOTH | `[1/5,1]` | `[1/5,1]` |
| OWN | `[-1/5,1]` | `[-1/5,1]` |
| NONE | `[-1,1]` | `[-1,1]` |

三层均输出 `match: True`。本次复算覆盖该固定案例。
对偶证据和端点表的拒绝行为另见上面的重放专项测试。

复跑脚本为 `evaluation/math_audit/check_mean_order_ladder.py`。
从仓库根目录运行 `python -m evaluation.math_audit.check_mean_order_ladder`，
三层区间均与独立参考值一致。
## 三、文献映射入口

| 审查对象 | 路线映射文件 |
|---|---|
| R1a | literature_support/routes/network_r1a.json |
| R1b | literature_support/routes/network_r1b.json |
| R2 | literature_support/routes/network_r2_policy_difference.json |
| R3-Full | literature_support/routes/network_r3_policy.json |
| D2/E1 单政策界 | literature_support/routes/bounded_policy_contrast.json |
| 两政策联合差值界 | literature_support/routes/bounded_policy_contrast.json |
| 均值顺序差值界 | literature_support/routes/mean_order_research.json |

路径提醒：
路线 JSON 中的 derivation_path 相对于该路线 JSON 所在目录，
不能一律按仓库根目录解释。

## 四、当前进度

| 审查对象 | 复跑脚本（位于 `evaluation/math_audit/`） | 脚本覆盖的检查 |
|---|---|---|
| R1a | `check_r1a_arm_support.py` | 四节点 D2/E1 单 arm 支持概率为 `1/2`，单 arm 均值为 `1/3`。内部一致但概率错误的结果被拒绝。 |
| R1b | `check_r1b_fixed_policy.py` | D1 完整安排概率为 `1/12`，固定政策值为 `7/12`。符号公式与所需可观测项一致，交换节点系数并重算摘要后仍被拒绝。 |
| R2 | `check_r2_star5_support.py` | Star-5 全用政策的完整安排概率为 `0`，各节点目标签名均有正支持。政策值为 `7/20`，原证书通过重放。 |
| R3-Full | `check_r3_full_policy.py` | 目标安排的观测概率为 `2/3`，固定背景下的政策值为 `5/12`。三项公式均匹配，改用另一份有正支持的安排并重算摘要后仍被拒绝。 |
| D2/E1 单政策界 | `check_bounded_policy_star7.py` | 七网点的目标状态支持逐项匹配，政策区间为 `[3/7, 4/7]`。原证书通过重放，修改后的下界见证被拒绝。 |
| 两政策联合差值界 | `check_bounded_contrast_cancellation.py` | 共享未知项抵消后，联合差值区间为 `[1/5, 1/5]`。分别求界再相减得到外界 `[-3/10, 7/10]`。 |
| 均值顺序差值界 | `check_mean_order_ladder.py` | 固定目标和 A4，`BOTH`、`OWN`、`NONE` 三层区间依次为 `[1/5, 1]`、`[-1/5, 1]`、`[-1, 1]`，均与独立参考值一致。 |

在提交 `d2a8149` 上，从仓库根目录统一复跑更新后的七份代表案例脚本，全部通过。新增下界见证回归测试也通过（1 项）。各路线的其他测试、证书检查及待审范围见对应小节。

缺条件教学例中，模型完整性声明未确认时，入口返回 `NEEDS_INPUT`，且 `backend_called=false`。具体检查函数仍待定位。

## 五、提交前检查与后续审查范围

### 本次提交前

- [x] 统一复跑更新后的七份代表案例脚本，四份 POINT 脚本的目标值对照均通过。
- [x] 运行新增的下界见证回归测试，确认可行但达不到所报下界的见证会被拒绝。
- [ ] 核对本轮文档修改的文件清单及 Git 格式检查，再提交并推送到任务分支。

### 后续审查范围

- 当前结论限于各路线列出的代表案例和已运行的专项测试。
- 尚未追踪的实现分支、共享依赖和边界用例见各路线小节。

## 六、任务 7 提交前验收记录

审查基线为 `7a4cb948ee28c74e4bbf1f2f561de74ff4ce6d6a`。
七类路线的目标、所需总体信息、假设、检查结果和待审范围见各路线小节。

- POINT 代表案例的独立数值对照均已跑通。R1a 的单 arm 均值为 `1/3`，
  R1b 的固定政策值为 `7/12`，R2 的 Star-5 全用政策值为 `7/20`，
  R3-Full 的固定背景政策值为 `5/12`。参考值由自建潜在结果与总体信息
  算出，并与项目返回的公式、政策项或 arm 坐标对照。
- 三类界限的代表案例均已复算。D2/E1 单政策界为 `[3/7,4/7]`；
  联合差值的共享未知项抵消后为 `[1/5,1/5]`；均值顺序阶梯在固定
  目标和 A4 下依次得到 `[1/5,1]`、`[-1/5,1]`、`[-1,1]`。
- 证书检查包括原证书对照和错误输入拒绝。自建检查覆盖了错误概率、
  权重错配、错误安排、端点证书错位和下界见证失配。联合差值的
  负系数见证、均值顺序的对偶证据及替代合法见证，另有已运行的仓库测试。
- 新增回归测试 `tests_gateway/test_task7_bounded_policy_witness.py`。
  在保留目标、A4 和下界声明的情况下，只修改中心节点的下界见证并重算
  摘要。原证书通过，修改版被拒绝。实际运行 1 项，结果为 `OK`。

代表案例脚本位于 `evaluation/math_audit/`，模块名见“四、当前进度”。
从仓库根目录运行对应的 `python -B -m evaluation.math_audit.<模块名>`。

新增回归测试的复现命令：

```powershell
.\.venv-task7\Scripts\python.exe -B -m unittest tests_gateway.test_task7_bounded_policy_witness -v
```

审查边界：本次结论覆盖上述代表案例和列出的专项测试。
未逐一覆盖所有设计与暴露组合，也未完成各路线全部实现分支的审读。
R1b 签发与重放共用 `_solve`，D2/E1 单政策界的求解与重放共享模型输入校验。
这些共享路径可能让同一错误影响两端，独立参考计算用于补充检查。