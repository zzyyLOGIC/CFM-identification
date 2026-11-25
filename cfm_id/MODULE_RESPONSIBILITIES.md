# cfm_id 模块职责

本目录兼有历史数学模块与业务运行模块；以下区分维护归属，不改变公开导入。完整目录地图见 [开发入口](../docs/DEVELOPMENT_ENTRY_ZH.md)，数学与文献来源见 [证据导航](../docs/MATH_AND_EVIDENCE_ZH.md)。

| 模块 | 实际职责 | 新改动的边界 |
|---|---|---|
| `project`、`configuration/reading.json` | 新应用与学生唯一推荐起点；复用底层会话 | 旧默认只保留兼容，配置不包含科学批准 |
| `business_intake`、`business_field_review`、`business_dispatch`、`business_case` | 共同材料、意图审核、分派和整题结果 | 不求数学结论，不生成科学批准 |
| `capability_registry` | 当前可调用函数、方法与接口配对 | 唯一可执行能力登记；不是定理或用户选项菜单 |
| `policy_methods`、`local_methods`、`observational_methods`、`finite_policy_methods`、`dag_methods` | 供登记和实际执行共同使用的方法合同 | 目标操作与原生函数对应；不批准条件，不混用不同平均方式，不自动回退 |
| `policy_execution`、`local_execution`、`native_outcome_execution`、`native_evidence` | 复用原生调用、输入／证据不变性核对及既有快照编码 | 保留各验证器、原有证书和审核摘要；不改数学公式 |
| `research_route_workflow` | 图、IV 和均值顺序的既有类型化研究执行与核验 | 各适配器保留自己的合同、审核、结论类型和证据；不强行套用网络业务结果 |
| `method_requirements`、`method_diagnostics`、`contrast_diagnostics`、`effect_diagnostics`、`observational_diagnostics` | 原生条件说明、当前审核缺项及已有执行证据的只读视图；专用模块适配有向政策差值、局部效应或R3观察性完整政策的证据形状 | 不审批、不求解、不签发证书；已接政策均值、两政策差值、局部直接/同伴效应、R3固定背景政策均值，复用原共同审核与执行权限 |
| `network_policy_dispatch`、`network_contrast_dispatch`、`network_effect_dispatch`、`network_bounded_dispatch`、`network_mean_order_dispatch`、`network_observational_policy_dispatch`、`dag_method_dispatch` | 将来源明确且已审的业务编译成相应原生合同，并核对返回证据 | 保留每个方法的 A4/A5 与适用域；不复制数学求解器 |
| `reading_*`、`fact_reading_revision`、`intake_reading_revision` | 读取一致性、完整变更审核、显式复查 | 不补答案、不替模型批准来源；Prompt 定义归 `cfm_id_llm` |
| `bounded_policy_contract/solver/verify`、`bounded_contrast_contract/solver/verify`、`mean_order_contract/solver/verify` | 有限数学模型、算法与独立验证 | 属于数学 Core；改动需要推导与数学验收，不以业务调整为由修改 |
| `bounded_count_*`、`bounded_finite_*`、`bounded_backends`、`bounded_mean_formula` | D2/E4 兼容及 D1–D8/E1–E5 有限均值盒合同、求界、重放、公式表达与类型分派 | 同一求界目标复用设计和暴露；D1–D6限12节点、D7/D8限8节点。符号入口需显式声明及独立重放；额外联合约束不在盒模型内 |
| `dag_backdoor_contract/solver/verify`、`dag_adjustment_contract/solver/verify`、`dag_frontdoor_contract/solver/verify` | 图模型、识别与独立验证 | 属于数学 Core；对象合作网络不能当变量 DAG |
| `bounded_policy`、`bounded_contrast`、`dag_backdoor`、`dag_adjustment`、`dag_frontdoor` 及对应 adapter | 原生合同的公开执行或研究连接 | 查对应合同，不能与同名前缀的 solver 混同 |
| `workflows/` | 专门运行工作流、准入适配、已有证书的组合核对 | 新增组合放这里；不存评分、金标准或自动合成批准 |
| `research_session*`、`session_*`、`research_versions` | 显式研究会话、审核版本与材料生命周期 | 内部会话配置不是业务用户必须选的类别 |
| `business_entry`、`intent_submission`、`fixed_assignment`、`fixed_comparison` 等旧接口 | 保留兼容的历史连接；部分旧文件仍同时含审核与组合逻辑 | 保持兼容；新能力优先复用共同入口，按需提取运行职责，避免继续堆入旧大文件 |
| `materials.py` | 读取原材料与来源摘要 | 当前是单个运行模块，不是资料目录；不自动寻找 Benchmark 或参考答案 |
| `web/` | 历史展示资源 | 不作为当前运行能力或数学合同的依据 |

并非所有包已形成完全单向依赖。本轮解决的是维护入口和新增代码归属，保留必要的历史兼容债务；不宣称物理布局已全面重构。
