# 内部目标迁移与专用入口清单

更新日期：2026-11-24。核对依据是当前 [capability_registry](../cfm_id/capability_registry.py) 的业务登记及网页 [math_library](../demo/backend/math_library.py) 的操作登记。本表是维护清单，不用于给用户选择定理，也不增加支持范围。

**已迁移**指实际执行由有明确职责的目标属性构造原生输入；不是只有文档归类。**保留专用实现**指继续使用已有合同与验证器，并非功能未接入或待重写。分类整理到此不要求所有方法强行使用同一种目标对象。

目标属性迁移与执行共享分开验收：本表的目标迁移状态保持不变。固定政策均值／两政策之差复用 `policy_methods` 与 `policy_execution`；单局部均值／随机化局部效应复用 `local_methods` 与 `local_execution`；观察性政策／局部效应复用 `observational_methods`；有限政策混合复用 `finite_policy_methods`；三种充分图方法共用 `dag_methods`。布尔型业务结果的原生调用及重放生命周期由 `native_outcome_execution` 共用；图路线沿用 `research_route_workflow`。单端、具名效应、反向线性和各观察性平均方式继续保留区别；均值顺序沿用原专用审核和提交实现。八种共同业务读取的方法绑定均已集中维护，但没有合并不同目标或证明方式。详见[执行职责及分批迁移](EXECUTION_ARCHITECTURE_ZH.md)。

## 8 类维护中的业务读取

| 读取入口 | 目标构造状态 | 实际维护位置与理由 |
|---|---|---|
| `NETWORK_FIXED_POLICY_FACTS` | 已迁移 | `PolicyQuestion`；完整政策均值；R1b/R2 及已接有限模型求界保留各自信息与科学合同 |
| `NETWORK_POLICY_CONTRAST_FACTS` | 已迁移 | 共享研究下的 `PolicyQuestion` 两端；联合求界、均值顺序与 POINT 比较保留原方法 |
| `NETWORK_RANDOMIZED_EFFECT_FACTS` | 已迁移 | `LocalQuestion`；原分配设计条件平均的直接／同伴／局部总效应 |
| `NETWORK_OBSERVATIONAL_POLICY_FACTS` | 已迁移 | `ObservationalPolicyQuestion`；固定 W 单独保存；完整名单与条件均值标签两方法保持各自前提 |
| `NETWORK_OBSERVATIONAL_EFFECT_FACTS` | 已迁移 | `ObservationalEffectQuestion`；实际采用律、共同分层、节点特征三种平均方式分开 |
| `NETWORK_RANDOMIZED_ARM_FACTS` | 保留专用实现 | `network_extended_dispatch` → `ArmInquiryV21`；问一个状态的均值，没有第二端，不能人为制造相减 |
| `NETWORK_FINITE_POLICY_FACTS` | 保留专用实现 | `network_extended_dispatch` → `FinitePolicyInquiryV21`；目标是政策分布，逐个组成政策证明后组合，不能丢掉选择概率 |
| `VARIABLE_DAG_FACTS` | 保留专用实现 | `dag_method_dispatch` 及图研究适配；节点是变量、目标是干预分布，与单位网络的暴露坐标不同 |

5 类已迁移、3 类保留专用实现，是目标构造的工程状态，不是成功率或识别能力的占比。所有 8 类仍执行原来的读取与科学审核。

## 默认首页、紧凑入口和上传规格

| 入口 | 当前状态 |
|---|---|
| 默认直答核验的政策 PARTIAL／均值顺序 | 已使用 `PolicyQuestion`；原材料核对、条件审核、求界与证书保持原实现 |
| 默认直答核验及关系文件的 `original_local` | 已使用 `LocalQuestion` 构造局部坐标；原事件概率、证明和交接验证器保留 |
| 默认其他网络 POINT 资料分支 | 保留各自的 `direct_network`、`network_policy_handoff` 等专用来源与证明合同；不能泛称默认首页所有分支都迁移了 |
| 默认 DAG／IV | 保留 `direct_dag`、IV 证据与研究适配；原答核验不等于自动获得估计权限 |
| 默认普通 ATE／二元 Manski | 已接 `population_ate_entry` 专用适配；所声明完整人群的无条件 1−0，经来源核对、科学确认、原生公式／界限核验。单组情况由原单组后端处理，不增设共同网络事实类别；不自动交接估计 |
| 紧凑网络政策／局部对比 | 分别已接入 `PolicyQuestion`／`LocalQuestion` |
| 紧凑 DAG／IV | 保留变量图、工具变量的专用目标、审核与计算 |
| 上传 `causal-id.math-request/1` | 保留原生规格，由 `study_math` 绑定本次原问、附件、版本及独立审核；不强制反向转换成某个业务读取合同 |

观察性新目标已接入经典审核执行。默认自由文本是否能够到达这些路线，仍取决于原有材料绑定和入口；上传原生规格可按原权限使用。此次没有以内部重构为由新增无审核的自动分派。

## 12 类原生操作：均保留原合同

| 操作 | 保留原因 |
|---|---|
| `population`、`task` | 原总体规格／任务规格包含其他已实现模型，不限于本轮目标子集 |
| `batch`、`linear`、`effects` | 批量臂、任意线性系数及多目标；不能缩成单一均值差 |
| `business`、`r3_pair` | 原生类型化研究及两份观察性研究核对，保留各自范围与证书 |
| `signature_support`、`quota_support` | 支持诊断，不是另一种效应目标或完整识别证明 |
| `legacy_bridge`、`legacy_compare` | 保留已有证书的重放与比对；兼容用途明确，不参与新业务分类 |
| `requirements` | 查看方法的要求；不构造目标、不批准条件 |

`requirements` 保留旧 `route`／`design_kind` 查询，同时增加 `method` 查询和统一说明目录；原 v27 的八条网络路线不是全库清单。[方法条件、实际入口及验证方式](METHOD_CONDITIONS_AND_VERIFICATION_ZH.md)引用真实函数登记，区分同实现重算、单独支持检查、图推导核验和端点／对偶证据。表中的方法、组合和结论分支不应按行数解释为独立定理数量。

## 6 条研究路线：均保留专用审核和证明

经典后门、指定调整集、经典前门、一般图 ID、二元 IV、均值顺序，分别对应 `DAG_CLASSICAL_BACKDOOR`、`DAG_ADJUSTMENT`、`DAG_CLASSICAL_FRONTDOOR`、`DAG_GENERAL_ID`、`BINARY_IV_LATE_ATE`、`MEAN_ORDER_D2_E1`。

其中均值顺序从业务入口进入时，目标部分已经迁移；直接提交研究规格时保留原 `MeanOrderProblem`。这两个入口不是两种相冲突的分类。同样，观察性业务目标迁移不要求删掉底层原生研究接口。

## 验收与下一步

本地 `reviews/observational-model-migration-20261124/entry-inventory.json` 从真实登记导出完整映射，检查 8 类读取无漏项；`entry-acceptance.json` 记录覆盖 12 类原生操作和 6 条研究路线的 26 份原规格执行。未审核时的阻断、原生结果／证书和不自动交接估计的边界均保留。

这轮目标层迁移可以按本清单收尾。[信息与科学条件交接](RESEARCH_SPEC_INFORMATION_SCIENCE_HANDOFF_ZH.md)已另行核对并修复资料缺项误分派、信息格子归属漏检等问题，保护了既有科学审核和证书。后续读取合同减负仍须有实测证据，不要求把保留的专用入口强行改成统一对象；本轮内部等价测试也不代替真实模型验收。
