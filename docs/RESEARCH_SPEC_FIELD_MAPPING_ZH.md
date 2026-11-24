# 六项字段对应与兼容边界

更新日期：2026-11-24。对应[内部结构主说明](IDENTIFICATION_STUDY_SPEC_ZH.md)。本表是现行内部属性与旧接口的兼容说明，**不是新 LLM Schema**。

[属性模型与兼容检查](RESEARCH_SPEC_COMPATIBILITY_ZH.md)已经实现；实际读取校验、设计原生类型及构造入口改为使用同一份设计/暴露登记。旧字段和值域、Prompt、Skill、默认网页、数学 Core 和审核门槛保持不变。默认 PARTIAL 材料、直答核验报告、原交接包及上传规格均可查看和还原；未增加可执行组合。

固定政策、随机化局部比较及观察性网络目标现已使用值对象构造原生输入，不再只做旧字段还原。共享名单、结果、背景和权重由 `research_spec_coordinates` 唯一维护；观察性固定 W 与平均方式另行保存。实际接入路径见[固定政策](RESEARCH_SPEC_POLICY_EXECUTION_ZH.md)、[局部效应](RESEARCH_SPEC_LOCAL_EXECUTION_ZH.md)、[观察性目标](RESEARCH_SPEC_OBSERVATIONAL_EXECUTION_ZH.md)和[入口清单](RESEARCH_SPEC_ENTRY_STATUS_ZH.md)。原始时期/业务背景只有合并表达时仍原样保留，不虚构细分属性。

## 先确定哪些东西保留

保留当前直答读取方式、经典入口、方法标识、旧字段、各自的来源绑定与证书。下表描述怎样从现有记录观察六项职责；不把多个入口强行改成同一种 LLM 输出。

| 对应性质 | 处理原则 |
|---|---|
| 直接对应 | 保留原值、来源和版本；可在说明中归到相应项目 |
| 确定性展开 | 只有旧定义与全部参数足以唯一决定时，才可展开成属性；保留旧模板和原始记录 |
| 需要语义核对 | 混写、缺项、歧义或跨范围推断需回到原文；不能凭字段名补齐 |
| 尚不支持 | 可以记录，但现有执行器不能消费时仍报告未覆盖；不能绕过审核 |

“确定性展开”也不授予新的科学许可。字段视图与真正进入库的规格应分别标记，不能把视图完整当作研究资料完整。

## 已核对的源码位置

| 层次 | 源码 | 在本次对应表中的作用 |
|---|---|---|
| 默认直答 | [direct_answer.py](../cfm_id_llm/direct_answer.py) | `ANSWER_RULES`、`NETWORK_FACTS`：模型的答案和有证据的网络事实分开 |
| 紧凑读取 | [compact_study.py](../cfm_id_llm/compact_study.py) | `Reading`、`Target`、`Network`、`Graph`、`IV` |
| 分阶段目标字段 | [business_field_contract.py](../cfm_id_llm/business_field_contract.py) | `COMMON`、`SEMANTICS`、`QUERY`，其他配置可以另带条件字段 |
| 政策事实 | [network_policy_reading.py](../cfm_id_llm/network_policy_reading.py) | `Study`、`Assignment`、`Exposure`、`Information`、`BoundedModel` 等 |
| 局部效应 | [network_effect_reading.py](../cfm_id_llm/network_effect_reading.py) | `EffectTarget`、`EffectInformation` 及科学主张与采用记录 |
| 两政策比较 | [network_contrast_reading.py](../cfm_id_llm/network_contrast_reading.py) | `PolicyEndpoint`、`PolicyContrastTarget` |
| 原生研究 | [network_inquiry_shadow.py](../pfn_pipeline/network_inquiry_shadow.py) | `NetworkStudyContextV17`、`NetworkA4SourceV17` |
| 原生目标 | [identification_route_shadow.py](../pfn_pipeline/identification_route_shadow.py) | `TargetSemanticsV15`、`RequiredObservableV15` |
| 模型结构 | [schemas.py](../pfn_pipeline/_internal/identification/schemas.py) | `StructureSpec`、`VariableSemanticSpec`；不代表所有入口均通过此对象 |
| 有限界与均值顺序 | [bounded_policy_contract.py](../cfm_id/bounded_policy_contract.py) · [bounded_finite_contract.py](../cfm_id/bounded_finite_contract.py) · [mean_order_contract.py](../cfm_id/mean_order_contract.py) | 数值/符号信息、模型范围、顺序方向和独立审核绑定 |
| 图与 IV | [dag_id_contract.py](../cfm_id/dag_id_contract.py) · [iv_contract.py](../cfm_id/iv_contract.py) | 变量图问题及二元 IV 总体表；不按对象关系网解读 |

本表覆盖当前整理涉及的主要合同，不声称穷举所有专门研究接口。新增入口仍须单独登记读取、审核、执行和重放情况。

## 读取字段怎样对应六项

下文 `Direct` 指直答协议；`Compact` 指紧凑读取；其他类名均来自上表源码。共同定义不是要求模型重填一份名单：内部属性通过原路径引用同一份内容；缺定义则保留缺项，不能推断补全。

| 归属 | 现有字段 | 对应方式及不可丢失的含义 |
|---|---|---|
| 共同定义 | `Study.nodes`、`treatment`、`outcome`、`outcome_kind`；`NetworkStudyContextV17.node_order` | 名单顺序、处理编码与结果定义保留；不能按展示排序重编号 |
| 共同定义/逐问背景 | `Study.context`；`NetworkStudyContextV17.context_reference`；`Compact.Target.context` | 既有字符串原样保留。时期、叙述场景和固定条件若混写，不能直接拆成三个已确认字段 |
| 目标：两端与方向 | `Direct.target.intervention/reference`；`PolicyContrastTarget.operation/first/second` | 保留比较顺序；直接回答中的文字需要与有审核的端点对应 |
| 目标：结果形式 | `Direct.target.quantity`；`Compact.Target.kind`；`TargetSemanticsV15.kind` | 保存原值；紧凑 `kind` 同时包含目标族等含义，不能只改名为“均值/差值” |
| 目标：评价人群 | `Direct.target.scope/population`；`PolicyEndpoint.population`；`EffectTarget.population` | 全体、子集、依从者分别处理；评价名单不得覆盖完整网络名单 |
| 目标：局部比较 | `EffectTarget.first/second`、`remaining_assignment`、`remaining_source_ids` | 保留本人/同伴两端及其余安排如何平均；不能变成指定所有人处理的完整政策 |
| 目标：汇总 | `EffectTarget.aggregation`；`PolicyEndpoint.aggregation`；`TargetSemanticsV15.unit_weights` | 权重、评价范围与两端一致性分别保存；不能由“平均”默补任意名单的等权 |
| 目标：时期/共同条件 | `Direct.target.time`；`EffectTarget.shared_outcome_and_context`；`PolicyContrastTarget.shared_outcome_and_context` | 引用逐问的结果和背景；共同文件中有某个时期不表示所有问题采用它 |
| D：完整分配 | `Assignment.kind` 及其概率、分组、名额、方案和筛选参数；`NetworkStudyContextV17.assignment_design_json` | 可以按下表展开。实际接受处理与被抽签的邀请量不互换 |
| D：简述入口 | `Direct.network_facts.assignment.value`；`Compact.Network.design/quota/probabilities` | 这些简述并不承载全部 D1–D8 细节；缺分层或完整联合律时不得凭目标反推 |
| E：映射 | `Exposure.kind/core_collaborators/weights/mode/groups` | 逐模板展开参考集合、统计量和标签；保留边界规则 |
| E：简述入口 | `Direct.network_facts.exposure.value`；`Compact.Network.exposure` | `other` 或自然语言描述不是已经完成的数学映射；核对后才能进入相应原生合同 |
| 结构：对象网 | `Study.edges/graph_kind/edge_list_complete`；`Direct.network_facts.network.value` | 边方向、完整性和时间声明保留；不能把没提供边表当成空图 |
| 结构：变量图 | `Compact.Graph.nodes/directed/bidirected/x/y`；`StructureSpec.representation_type/directed_edges/bidirected_edges` | 变量节点和单位节点使用不同登记空间；不从合作关系推导因果箭头 |
| 结构：IV 角色 | `Compact.IV.z/d/y/binary` | 工具、实际处理和结果分开；工具随机不自动使实际处理随机 |
| 已有信息：总体对象 | `Information.operator/availability/outcome_nodes/assignment_cells/signature_cells` | 保留总体算子及其坐标；各签名值不是完整联合分布的替代品 |
| 已有信息：局部均值 | `EffectInformation.operator/availability/outcome_nodes/arm_cells` | 保留各单位的目标臂和来源；不能因同标签就把不同单位的均值合并 |
| 已有信息：样本说明 | `Information.data_description`；`EffectInformation.data_description` | 说明数据覆盖和用途；不把它自动升级为总体信息或额外科学限制 |
| 已有信息：图/IV | `Compact.Graph.info`；`Compact.IV.cells` | 图中的总体联合律声明与有限样本区分；IV 表保持既有二元格序和条件化约定 |
| 已有信息：绑定 | `NetworkA4SourceV17.operator/availability/shared_scope_digest/protocol_digest` | 原绑定继续使用；跨研究、名单、背景或设计不得沿用旧许可 |
| 科学假设：基础声明 | `NetworkPolicyReading.assumptions`；`Sufficiency.value/scope/covered_nodes`；`FirstStageExclusion.status` | 声明的值与科学批准分开；充分性范围不能从单一安排扩成所有安排 |
| 科学假设：采用记录 | `NetworkEffectReading.design_facts/scientific_statements/assumption_choices` | 三种职责分别保留；设计事实不自动成为科学采用，采用记录不覆盖原命题 |
| 科学假设：简述入口 | `Direct.assumptions`；`Compact.Reading.assumptions/restrictions/gaps` | 这些入口未统一编码所有状态；没有出现在 adopted 列表中，不足以区分未提及、不采用和未决定 |
| 信息/模型完整性 | `BoundedModel.listed_means_are_complete_information/no_additional_coupling_constraints` | 前者界定信息清单，后者界定模型限制；不能合并为一个“材料完整”开关 |
| 真正额外限制/未知项 | `NetworkPolicyReading.additional_restrictions/unresolved` | 逐项核对命题、归属和范围；不能为了进入求解器清空不支持的限制 |
| 模型上下界 | `BoundedModel.bounds_kind/bounds_scope/bounds` | 说明它约束哪些均值、哪些安排；不默认等于所有个体潜在结果的支持界 |
| 顺序与模型范围 | `MeanOrderProblem.order_direction/order_scope/node_orders/model_scope/information_scope` | 保留每条顺序轴、方向、覆盖安排及信息/模型闭合条件 |
| 来源与审核 | `source_ids`；`ReviewedMeanOrder.problem_sha256` 及各 `reviewed_*` 字段 | 来源支持、采用态度、审核范围各自绑定；不能把旧审核复制给改变后的规格 |

### D 模板的确定性展开范围

| 旧模板 | 内部归属 | 必须完整保留的现有参数/语义 |
|---|---|---|
| D1 独立 Bernoulli | 独立单位分配 | `probabilities`；独立性与各自概率 |
| D2 全体固定名额 | 等概率固定名额 | `fixed_count`、完整名单；在合法名单间均匀分配 |
| D3 两组固定名额 | 分层等概率固定名额 | `groups`、`treated_quotas`；保留两组合同 |
| D4 簇 Bernoulli | 整簇独立分配 | `clusters`、`cluster_probabilities`；簇内共同分配 |
| D5 多组固定名额 | 分层等概率固定名额 | `groups`、`treated_quotas`；保留现有至少三组合同 |
| D6 名额方案混合 | 两阶段分配 | `groups`、`quota_profiles`、`profile_probabilities`；方案内分配规则；第一阶段排除限制另审 |
| D7 不等概率固定名额 | 加权或显式联合律的固定名额 | `fixed_count`；`treated_sets/set_probabilities` 或 `unit_weights` 按原合同提供，不把边际概率当完整名单概率 |
| D8 平衡筛选 | 基础设计条件于接受事件 | D7 基础律、`balance_covariates`、`balance_tolerance`；保留原接受规则、基础支持与重新归一化 |

D8 不能只保留接受后的几个名单，却删除原基础设计和筛选依据。D3/D5 的分组目录也不能直接挪作 E 的伙伴分组：两者可以不同。

### E 模板的确定性展开范围

| 旧模板 | 参考对象 | 统计及标签 | 必须保留的边界 |
|---|---|---|---|
| E1 | 全部邻居 | 人数是否严格超过邻居数的一半 | 平票为低档，孤立点为 0；不能用未定义的 0/0 代替 |
| E2 | 全部邻居 | 处理比例的三档：`[0,1/3)`、`[1/3,2/3)`、`[2/3,1]` | 标签依次为 0、1、2；孤立点未定义 |
| E3 | 预先登记的核心伙伴 | 核心伙伴中严格过半 | 核心集合非空且是实际邻居的子集 |
| E4 | 全部邻居 | 精确处理人数 | 孤立点计 0 |
| E5 | 全部邻居 | 至少一人接受处理 | 孤立点为 0 |
| 加权暴露 W | 合同规定的邻居及权重 | `mode` 指定加权和或比例 | 保留权重作用在哪个单位或哪条边，及分母规则 |
| 分组暴露 G | 预先登记的组与邻居 | 按组排列的处理人数向量 | 保留组顺序、成员归属和每一分量 |

这里的加权暴露编号 W 与背景变量记号 W 不是一回事。内部视图应使用清楚的名称，证书中的旧标识仍原样保存。某个原生接口允许边权也不代表当前网页合同已经支持任意边权。

E1–E5 的边界依据为现有 [ExposureSpec](../pfn_pipeline/_internal/identification/randomized_arm_family/exposure.py)。本次仅转述，未更改该实现。

## 不能通过“换字段”解决的地方

1. **直答和紧凑读取没有编码全部六项细节。** 没有类型化表达的内容可能仍在原文中，需继续核对，不能视为不存在。
2. **时期、背景、协变量和标准化不是同一字段。** 不从 `context` 里的文字自动批准条件化目标，沿用[逐问条件职责](TARGET_CONDITIONING_OWNERSHIP_ZH.md)。
3. **同一目标可以有多种方法。** R1b 与 R2 可能证明同一政策目标；R1a 的原设计条件平均不能因此改成完整政策比较。R3 内不同目标和调整方式也不能压成一个开关。
4. **复合结构不自动得到复合定理。** 能同时记下网络、变量图和随机工具，不代表已有“网络＋IV＋一般 ID”的求解器。
5. **可表达的组件不自动扩展求界模型。** 有限均值盒、均值顺序和 IV 界各自有模型合同，额外耦合条件必须进入支持它的求解器或报告不支持。

## 对其他内容会有什么影响

| 内容 | 本次文档整理 | 以后真正迁移字段时必须做的事 |
|---|---|---|
| D/E 组合与 R 方法 | 不改变可执行范围，不删旧编号 | 对新视图与旧规格逐项比较；新组合另验定理和入口 |
| Prompt、Skill 和 Schema | 不修改，不要求模型重复填写 | 同步修改请求、Schema、解析和引用责任；禁止只改提示文字 |
| 后台复核与追问 | 不修改 | 未知、拒绝、明确否定和缺失分开；问用户原意，不让用户选择内部编号 |
| 科学审核 | 原规则保持 | 新对象仍绑定完整来源、目标和假设；旧批准不能跨语义改动复用 |
| 数学 Core | 不修改 | 通过现有适配器送入原生合同；转换不负责增加假设 |
| 证书与恢复 | 原字节与版本保持 | 旧证书走旧解析/重放；有新绑定的规格重新审核并生成相应证书 |
| 估计/Policy 交接 | 不修改 | 保留目标、方向、人群、权重、时期、条件和算子，不能静默改成其他效应 |
| 网页 | 不新增六个强制表单 | 可用六项做可展开摘要；用户只处理真正缺项或科学决定 |

不同摘要算法的允许类型和历史字节约定不同，不能用一个“统一 hash”替代，详见[维护入口](EXTENSION_MAINTENANCE_ZH.md#公共工具的归属)。即使改写前后数学等价，改变了签认所绑定的内容也不能继续声称是原票据。

## 属性对应阶段的边界和验收

本阶段完成内部属性模型、共享组件登记、查看工具与兼容适配，没有让 LLM 改填新合同。适配保留旧记录，标出无法可靠拆分的内容，原审核继续使用旧规格。它不根据字段齐不齐给出业务理解通过率。

验收采用固定的少量记录，检查：

1. 同一研究经视图展开后，设计支持、暴露值、目标方向/范围、计算结果及原证书重放不变。
2. E1 平票/孤立点、E2 阈值、D3/D5 分层、D6 第一阶段、D8 基础律与接受筛选均未丢失。
3. 未决定不转成已采用；“不采用”不转成命题为假；额外限制不能消失。
4. 时间混写、名单缺失、信息缺坐标时明确报告无法直接转换，不靠默认值通过。
5. 更改目标、信息或假设后，旧审核与交接不能沿用。

本文件的源码核对仅说明字段存在及职责对应；本轮实际运行范围和局限见[兼容验收记录](RESEARCH_SPEC_COMPATIBILITY_ZH.md)。本阶段没有新调用 LLM，也没有把六项视图接到默认网页。
