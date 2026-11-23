# Identification 开发入口与代码地图

分类来源及自定义编号的边界见[文献依据](../literature_support/CLASSIFICATION_ZH.md)。

## 源码位置

本页路径相对识别包根目录。开发工作区是 `iCFM-identification`，包内源码和网页位于 `identification/`。个人发布副本在仓库根直接放置同一包。

历史验收文档中的目录名描述当时的实验位置，不是当前安装路径；运行产物和本地 API 记录不随源码发布。

## 三层流程，各自负责什么

| 层 | 输入 → 输出 | 主要维护点 |
|---|---|---|
| 读取 | 业务问题和材料 → 带来源的目标、事实草稿 | `cfm_id_llm/`；不批准科学条件 |
| 审核与连接 | 已审核的业务意图、A4 信息、A5 条件 → 原生数学问题 | `cfm_id/` 的业务模块；不因 LLM 声称成立就批准 |
| 数学与验证 | 原生合同 → 识别式、界或反例及证书 | 原生 solver / verify；结论只在其合同范围内成立 |

网页默认由 `demo/backend/engine.py` 发起一次完整读题，再以 `cfm_id.direct_verification` 核对，估计端独立复核查询包。经典分阶段路线的编程入口为 `cfm_id.project.start(case)`，使用 `cfm_id/configuration/reading.json`。

## 所有顶层目录

| 目录 | 职责 | 新同学应注意 |
|---|---|---|
| `cfm_id/` | 业务会话、审核、路由、恢复；历史布局还含有限 PARTIAL / DAG 数学模块 | 按下方模块地图区分适配与 Core，不能仅凭包名判断 |
| `cfm_id_llm/` | A0 / 事实读取协议、Prompt、Schema、解析、来源、诊断、重读说明 | `providers/` 只传输；`readers/` 是已归位的读取实现；共同配对归 `fact_reading_contracts` |
| `cfm_id_bridge/` | 业务/科学声明与原生对象、证书的绑定，以及兼容摘要工具 | 摘要检查内容一致，不证明审核者身份或科学假设真实 |
| `pfn_pipeline/` | 原生网络识别与独立验证；也保留下游兼容实现 | 网络 Core 在 identification 相关模块；Estimation / Policy 不在本轮修改范围 |
| `evaluation/` | Benchmark 材料、参考、评分、实验驱动及历史 CLI 包装 | 正式业务运行不得导入参考答案或合成审核；public 材料和 research 参考分开 |
| `examples/` | 可运行示例、固定草稿、显式合成审核 | 学生先运行 `student_handoff`；`legacy/` 是兼容回归资料，不是新路线模板 |
| `tests/` | 原生数学、图结构、历史整合检查 | 保留关键公式、反例和证书检查；下游集成测试另选 |
| `tests_gateway/` | 读取、来源、审核、分派、恢复、兼容与完整链路检查 | 按职责登记测试，不按每轮修改复制一套 |
| `assets/` | 固定材料、Mock、回归和历史展示资源 | 不是新算法的存放处，不接收密钥和新在线结果 |
| `literature_support/` | 文献卡、项目数学合同与实现的导航索引 | 文献支撑、项目推导、运行覆盖和测试结果是四件事；不建第二份能力登记 |
| `docs/` | 当前合同、操作与扩展规则 | 历史实验进入 `history/`；当前验收看 `RELEASE_ACCEPTANCE_ZH.md`；`DELIVERY_READINESS_ZH.md` 保留当时的安装记录 |
| `skills/` | 宿主操作说明及读取资源导航 | 模型实际使用的 A0 与网络事实 Skill 分别在 `cfm_id_llm/resources/causal_business_reading/`、`network_fact_reading/`；宿主说明不重复注入，不替代Schema与审核 |
| `demo/` | 纯 ID 网页、后端适配、示例及专门测试 | 输出公式、条件和重放；不提供估计或 Policy，不能导入其实现 |
| `scripts/` | 测试、构建、检查的薄入口 | 不放业务判定或定理 |
| `identification_only/` | 旧原生报告表达合同 | 兼容保留，不是所有识别能力的公共入口 |
| `predevelopment/` | 早期两阶段设计的探索原型 | 不代表已上线能力，保留导入兼容 |
| `research_partial/` | 早期特定有界演示 | 正式 PARTIAL 在 `cfm_id/bounded_*` / `mean_order_*`，不要在原型中扩展正式路线 |

`student_work/` 已移到 `examples/legacy/`。缓存、build、egg-info、运行 outputs 都是生成物，不是源码。无需制造带日期或版本号的第二套工作目录。

## cfm_id 内部要特别分清

| 模块组 | 所属责任 |
|---|---|
| `project`、`configuration/reading.json` | 唯一推荐起点与配置 |
| `business_intake`、`business_field_review`、`business_dispatch`、`business_case` | 业务读取生命周期、审核、逐问及整题执行 |
| `cfm_id_llm/reviewed_intent_handoff`（读取包内） | 已审核意图到网络事实读取的交接、两种来源目录的原文位置映射和一致性审核要求；不把自然语言自动变成数学坐标 |
| `capability_registry` | 当前数学能力与可调用入口的唯一运行登记 |
| `method_requirements`、`method_diagnostics`及`contrast_diagnostics`/`effect_diagnostics`/`observational_diagnostics` | 从原生工作表、审核、执行记录生成[方法诊断](METHOD_DIAGNOSTICS_ZH.md)；已接政策均值、有向差值、局部直接/同伴效应、R3观察性固定背景政策，专用模块只适配证据形状，不新增数学能力或审核许可 |
| `network_*_dispatch`、`dag_method_dispatch` | 业务适配器；将审核后的事实交给已有数学合同，不能把这些文件当 solver |
| `network_design_adapter` | 已审 D1–D6/E1–E5 参数到现有原生构造器的共同转换；Task 1 另接 D7 不等概率固定名额 / D8 重随机化平衡（`task1_design` + `make_arm` 路由）；不推断设计、不计算支持、不自动批准条件 |
| `bounded_policy_contract/solver/verify`、`bounded_contrast_contract/solver/verify`、`mean_order_contract/solver/verify` | 正式有限数学模型与独立验证，属于 Core |
| `bounded_count_*`、`bounded_finite_*` | D2/E4 数值协议和 D1–D8/E1–E5 的有限均值盒模型：类型合同、数值/符号求界、独立枚举重放；业务接入复用 `network_bounded_dispatch` / `network_contrast_dispatch`。展示公式统一在 `bounded_mean_formula`，不授予审核。不要把新约束塞进盒模型，详见 FINITE_MEAN_BOX_MATH_ZH.md |
| `dag_backdoor_contract/solver/verify`、`dag_adjustment_contract/solver/verify`、`dag_frontdoor_contract/solver/verify` | DAG 数学合同与独立验证，属于 Core |
| `workflows/` | 专门研究流程与既有证书的组合；`legacy_network/` 保持旧运行接口 |
| `research_session*`、`session_*`、`research_versions` | 显式研究会话、条件版本与审核生命周期 |
| `business_entry`、`intent_submission` | 兼容接口，新应用从 `project` 进入 |
| `materials.py` | 材料与来源处理；它是运行模块，不是放数据的文件夹 |
| `web/` | 历史展示资源 |

网络原生数学还在 `pfn_pipeline/_internal/identification/` 与公开 `identification_*` 模块。物理布局没有全面重排：保留这些位置是为了维持导入和证书兼容，不能宣称已经形成完全单向依赖。更细地图见 [cfm_id 模块职责](../cfm_id/MODULE_RESPONSIBILITIES.md)。

## 扩展从哪里下手

**新业务题**改 `evaluation` / `examples`；**读取字段**改 `cfm_id_llm` 及审核合同；**已有能力接入**改业务适配器和两个登记；**新定理**先补文献、数学合同、独立验证，再接业务。不要复制整条流程。

完整要求见[扩展维护规则](EXTENSION_MAINTENANCE_ZH.md)、[读取配套](FACT_READING_REGISTRY_ZH.md)、[数学与证据](MATH_AND_EVIDENCE_ZH.md)。已知未完成项单独记录在[限制清单](KNOWN_LIMITATIONS_ZH.md)，不隐藏在目录说明中。

随机化设计/暴露的接入样板见[设计与暴露入口](NETWORK_DESIGN_EXPOSURE_ENTRY_ZH.md)：字段规则统一在 `cfm_id_llm/network_design_reading.py`，独立科学声明仍进入各目标适配器的审核。已有 D/E 的四类目标无需学生再复制一套读取、审核和求解流程。

## Task 1（网络拓展 / POINT 拓展）

任务 1 扩展了不等概率固定名额 D7、重随机化平衡 D8、固定权重与分组暴露。局部直接、同伴效应及正式单臂／批量／组合研究入口支持相应暴露。R1b 和 R2 的政策均值与差值接入新设计，R2 的均值签名仍限 E1–E5。D4–D6 上 W/G 的分配质量现已独立复算。新设计超过八个节点的解析支持、PFN 估计和默认路线策略分别列于 U1–U6。[数学合同](TASK1_POINT_EXTENSION_MATH_ZH.md) · [逐项状态与验收](TASK1_LIMITATIONS_ZH.md)
