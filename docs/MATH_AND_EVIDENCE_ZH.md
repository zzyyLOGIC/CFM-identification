# 数学合同、文献与运行证据分别放在哪里

这是一份维护导航，不新增用户入口或互斥的业务分类。**文献背景、项目数学合同、程序实现、当前覆盖和测试成绩是五种不同材料，分别只有一个维护归属。**

| 要回答的问题 | 首要位置 | 不能代替什么 |
|---|---|---|
| 某项研究思路来自哪篇论文，实际读到了哪里？ | `literature_support/catalog.json` 的文献卡片 | 不能代替该业务的科学审核，也不能宣称论文逐字证明本项目所有变体 |
| 本项目采用什么目标、A4、A5、适用域、推导及 sharpness 定义？ | `literature_support/mathematical_contracts.json` 指向的项目数学合同 | 不在文献卡或接口说明中再维护另一份完整证明 |
| 哪些函数求解、验证，哪些只编译已审输入？ | 数学索引中的实现路径与 [cfm_id 模块职责](../cfm_id/MODULE_RESPONSIBILITIES.md) | 不能按文件名有“policy”或“verify”就跨层合并 |
| 哪个数学能力已接入共同入口？ | `cfm_id.capability_registry.inventory()` | 文献目录、旧发布说明和历史实验不得另作当前运行登记 |
| 这份代码实际上跑过哪些检查？ | 带日期的验收记录，入口为 [固定框架验收](FRAMEWORK_ACCEPTANCE_ZH.md) | 测试路径存在不等于通过；离线参考不是 LLM 准确率 |

`literature_support/designs/`中的实施前设计是历史研究材料，`routes/`连接选定文献与项目合同；已经实现的方法以运行登记核对，不能由设计稿日期推断。2026-10-31 已为原来五个 `literature_maps` 为空的条目补充来源/项目推导映射；这只补齐导航，不表示所有原始定理和证明都已复核。每张卡仍保留实际阅读范围及不适用边界。数学推导和原生验证并不因此移入文献目录。

分类来源与项目编号的依据见[分类说明](../literature_support/CLASSIFICATION_ZH.md)；机器导航 `classification_map.json` 分列研究规格字段、证明方法、历史合同、实现设置、数学结果和审核流程。新增能力见[扩展规则](EXTENSION_MAINTENANCE_ZH.md)，IV/一般ID的预研来源不能当作已实现能力。

## 数学实现为何暂不整体移动

原生网络实现位于 `pfn_pipeline`；新增有限界限和 DAG 实现目前位于 `cfm_id`。这反映历史物理布局，不是同一层已经完成重新分包。为了保证旧导入、证书及重放稳定，本轮不搬数学 Core。

`cfm_id` 中要按职责区分：`*_contract`、`*_solver`、`*_verify` 中的数学合同/算法，与 `network_*_dispatch`、`dag_method_dispatch` 中的业务编译和审核连接不是同一职责。新的跨结果组合放在 `cfm_id/workflows`；它调用已有原生证明并核对共同目标，不应复制定理求解器。

例如本轮 R2 比较：原生单端定理仍是 `pfn_pipeline.identification_policy_r2`；业务读取不变；`network_contrast_dispatch` 复用单端科学审核和编译；`workflows.policy_difference` 核对两个有效端点的有序相减。新组合代码不放在评测或文献目录。R3-Full 的原生数学仍在 `pfn_pipeline.identification_observational_r3`；新增业务适配归 `cfm_id.network_observational_policy_dispatch`，必要的事实 Schema／Prompt 归 `cfm_id_llm.network_observational_policy_reading`，参考材料和合成审核归 `examples`，真实验收记录在源码之外。

## 增加已有能力连接时

1. 在数学索引定位已有合同与独立重放，明确目标是否相同；不能只因函数可调用就推定业务已覆盖。
2. 在所属业务适配器和 `capability_registry` 接入，复用材料、会话、审核、重读与整题汇总；用户不用预选方法。
3. 若只是复合已有结论，单列组合合同和证据核对；若改变数学模型或结论，另行完成推导与独立验证，不借“适配”之名改 Core。
4. 新参考和模拟审核留在 `examples`，评测在 `evaluation`，证明/边界测试在 `tests` 或 `tests_gateway`；运行代码不能导入它们自动批准。
5. 数学索引的链接和能力 ID 有测试检查。索引只是导航，不影响运行分派；实际验收成绩写入本轮记录，不写成文献结论。

数学索引中的路径相对源码根目录。路线 JSON 的实现和测试路径也相对源码根；`derivation_path` 则相对该路线 JSON 所在目录，详见文献目录的路径约定。分发 wheel 时可能不包含完整 `docs`，阅读数学材料请使用源码包。当前项目的文献整理仍不完整，索引补齐导航不等于补齐所有文献评述。
