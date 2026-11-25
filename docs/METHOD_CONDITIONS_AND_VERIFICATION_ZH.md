# 方法条件、实际入口与验证方式

本表由 cfm_id.method_catalog 从实际能力登记及原生条件目录生成。只作维护说明，不参与方法分派、科学批准或数学判定。

六项研究属性共同描述问题；方法可以同时适用。现用网络方法使用可读标识，不从编号或名称前缀决定适用性。旧证书及原生接口标识仅由 method_compat 转换比较，证书本身不改写。D/E 参数与数学支持范围不变。

## 基础方法、操作与实现

基础方法描述识别依据；差值和有限混合是操作；设计特例与求解版本是实现。下表登记已有能力，不自动开放新组合。二元 IV 的两个目标共用实现但分别保留原生条件，单臂 ATE 的不同结果域也保留原合同。

| 基础方法 | 名称 | 识别依据（概要，完整条件见下文） |
| --- | --- | --- |
| network.randomized.local | 原设计条件平均的局部均值识别 | 完整安排随机化；不由暴露定义推定充分性 |
| network.randomized.full_policy | 随机化下的完整政策均值识别 | 完整安排随机化与目标完整安排支持 |
| network.randomized.signature_policy | 随机化与均值暴露充分性下的政策均值识别 | 完整安排随机化、已采用的均值充分性及目标签名支持 |
| network.observational.full_policy | 条件交换性下的完整政策均值识别 | 完整向量条件交换性与完整安排支持 |
| network.observational.signature_policy | 条件交换性与均值暴露充分性下的政策均值识别 | 完整向量条件交换性、已采用的均值充分性及签名支持 |
| network.observational.observed_law | 按观测分配律平均的局部效应识别 | 完整向量条件交换性 |
| network.observational.shared_stratum | 共同分层调整的局部效应识别 | 暴露充分性及给定共同分层的局部均值交换性 |
| network.observational.local_covariate | 局部协变量调整的局部效应识别 | 暴露充分性及给定局部特征的均值交换性 |
| network.bounds.mean_box | 有限均值模型求界 | 完整声明的有限均值模型及结果界 |
| network.bounds.mean_order | 带均值顺序约束的有限模型求界 | 有限均值模型及实际采用的顺序限制 |
| graph.backdoor | 后门调整 | 后门准则 |
| graph.adjustment | 指定调整集识别 | 对应调整集准则 |
| graph.frontdoor | 经典前门识别 | 经典前门准则 |
| graph.id | 一般图 ID | 半马尔可夫模型下的图识别推导 |
| iv.binary.late | 二元工具变量 LATE 识别 | 工具独立性、排除、单调性等原生条件及非零第一阶段 |
| iv.binary.ate_bounds | 二元工具变量 ATE 求界 | 二元响应类型模型及实际采用的限制 |
| population.randomized_ate | 随机试验 ATE 识别 | 随机化、一致性、无干扰、有限均值及双臂支持 |
| population.one_arm_ate | 单处理组 ATE 求界 | 单臂支持下的完整声明模型；不得忽略额外限制 |
| population.binary_ate_bounds | 二元结果 Manski 界 | 一致性、无干扰及完整声明的二元完成模型 |

| 执行标识 | 基础方法 | 目标操作 | 实现 |
| --- | --- | --- | --- |
| network.randomized.local_mean | network.randomized.local | ARM_MEAN | native_arm |
| network.randomized.local_contrast | network.randomized.local | FIRST_MINUS_SECOND | native_local_composition |
| network.randomized.full_policy_mean | network.randomized.full_policy | MEAN | native_full_policy |
| network.randomized.finite_policy_mean | network.randomized.full_policy | FINITE_POLICY_MEAN | native_finite_mixture |
| network.randomized.full_policy_contrast | network.randomized.full_policy | FIRST_MINUS_SECOND | native_endpoint_composition |
| network.randomized.signature_policy_mean | network.randomized.signature_policy | MEAN | native_signature_policy |
| network.randomized.signature_policy_contrast | network.randomized.signature_policy | FIRST_MINUS_SECOND | native_endpoint_composition |
| network.observational.full_policy_mean | network.observational.full_policy | MEAN | native_fixed_background |
| network.observational.signature_policy_mean | network.observational.signature_policy | MEAN | native_fixed_background_signature |
| network.observational.observed_law_contrast | network.observational.observed_law | FIRST_MINUS_SECOND | native_observed_law |
| network.observational.shared_stratum_contrast | network.observational.shared_stratum | FIRST_MINUS_SECOND | native_shared_strata |
| network.observational.local_covariate_contrast | network.observational.local_covariate | FIRST_MINUS_SECOND | native_local_binary_features |
| BOUNDED_POLICY_MEAN_D2_E1 | network.bounds.mean_box | MEAN | d2_e1 |
| BOUNDED_POLICY_CONTRAST_D2_E1 | network.bounds.mean_box | FIRST_MINUS_SECOND | d2_e1 |
| BOUNDED_POLICY_MEAN_D2_E4 | network.bounds.mean_box | MEAN | d2_e4 |
| BOUNDED_POLICY_CONTRAST_D2_E4 | network.bounds.mean_box | FIRST_MINUS_SECOND | d2_e4 |
| BOUNDED_POLICY_MEAN_FINITE | network.bounds.mean_box | MEAN | finite |
| BOUNDED_POLICY_CONTRAST_FINITE | network.bounds.mean_box | FIRST_MINUS_SECOND | finite |
| MEAN_ORDER_D2_E1 | network.bounds.mean_order | FIRST_MINUS_SECOND | d2_e1_order |
| DAG_CLASSICAL_BACKDOOR | graph.backdoor | INTERVENTIONAL_DISTRIBUTION | native_backdoor |
| DAG_ADJUSTMENT | graph.adjustment | INTERVENTIONAL_DISTRIBUTION | native_adjustment |
| DAG_CLASSICAL_FRONTDOOR | graph.frontdoor | INTERVENTIONAL_DISTRIBUTION | native_frontdoor |
| DAG_GENERAL_ID | graph.id | INTERVENTIONAL_DISTRIBUTION | native_id |
| BINARY_IV_LATE_ATE | iv.binary.late<br>iv.binary.ate_bounds | EXPLICIT_IV_TARGETS | binary_response_types |
| RANDOMIZED_ATE_V3 | population.randomized_ate | FIRST_MINUS_SECOND | native_population_ate |
| ONE_ARM_ATE_BOUNDS_V2 | population.one_arm_ate | FIRST_MINUS_SECOND | bounded_outcome_domain |
| ONE_ARM_NO_OUTCOME_RESTRICTION_V2 | population.one_arm_ate | FIRST_MINUS_SECOND | unrestricted_outcome_domain |
| MANSKI_BINARY_ATE_V2 | population.binary_ate_bounds | FIRST_MINUS_SECOND | binary_outcome_domain |

## 条件与实现限制

科学条件是否符合现实仍由研究者判断；程序核对材料、采用状态及条件下的数学结论。支持概率、图准则和可行性由程序计算，不能靠勾选代替。

| 方法（当前执行标识） | 科学条件 | 已有信息与可计算检查 | 当前实现限制 |
| --- | --- | --- | --- |
| 原设计局部均值及效应<br>network.randomized.local_mean<br>network.randomized.local_contrast | 完整安排随机化、一致性、处理前固定网络、所需均值有限；D6 另审第一阶段无直接作用。不要求均值暴露充分性。 | 已知分配律及所需局部状态的总体结果信息。<br>每个非零项的联合局部状态正支持、信息覆盖、共同研究和系数。 | 设计、暴露及权限以实际入口为准；外部研究与合成研究的范围不同。 |
| 完整政策、有限混合与两政策差<br>network.randomized.full_policy_mean<br>network.randomized.finite_policy_mean<br>network.randomized.full_policy_contrast | 随机化、一致性、处理前固定网络、均值有限；D6 另审第一阶段无直接作用。不要求均值暴露充分性。 | 已知分配律、目标完整安排的总体结果信息。<br>每个非零政策分量的完整安排正支持；混合权重／差值方向及共同总体。 | 有限显式完整政策；两端组合不构成一种新定理，也不能只识别一端。 |
| 均值签名政策及两政策差<br>network.randomized.signature_policy_mean<br>network.randomized.signature_policy_contrast | 随机化基础条件，加覆盖全部相关完整安排的均值签名充分性；不能由暴露定义自动推出。 | 已知分配律及目标节点签名的总体均值。<br>逐对象目标签名正支持、信息覆盖；两端使用同一研究与科学模型。 | 当前受支持的签名与设计；不要求完整目标政策本身有正概率。 |
| 固定背景下的观察性政策<br>network.observational.full_policy_mean<br>network.observational.signature_policy_mean | 完整向量条件交换性、一致性、处理前固定网络、均值有限；签名方法另需全安排均值充分性。 | 同一固定 W 下的观测总体安排律及条件均值。<br>完整政策或逐对象目标签名正支持；不以边际支持替代联合支持。 | 共同读取入口限有限总体表、最多12节点和固定 W；不自动跨 W 平均。 |
| 观测律条件平均的局部效应<br>network.observational.observed_law_contrast | 完整向量条件交换性、一致性、处理前固定网络、均值有限；不要求暴露充分性。 | 观测总体分配律和对应局部状态均值。<br>非零局部项正支持、信息与同一 W 的匹配。 | 按原观测律作条件平均；有限联合律、乘积律和混合律各有专用合同。 |
| 共同处理前分层调整<br>network.observational.shared_stratum_contrast | 一致性、固定网络、均值有限；个体暴露充分性及给定分层变量的局部均值交换性。 | 分层总体权重、逐层分配与局部结果均值。<br>每个正权重层的目标局部状态正支持。 | 有限共同分层，不是任意高维协变量调整。 |
| 节点及邻居特征调整<br>network.observational.local_covariate_contrast | 一致性、固定网络、均值有限；个体暴露充分性及局部协变量条件均值交换性。 | 总体特征律、给定特征的因子化处理律及节点条件均值。<br>每个正质量节点特征层的目标局部状态正支持。 | 指定的二元本人特征与邻居计数合同，不是一般网络混杂消除器。 |
| 有限均值盒政策界限<br>BOUNDED_POLICY_MEAN_D2_E1<br>BOUNDED_POLICY_CONTRAST_D2_E1<br>BOUNDED_POLICY_MEAN_D2_E4<br>BOUNDED_POLICY_CONTRAST_D2_E4<br>BOUNDED_POLICY_MEAN_FINITE<br>BOUNDED_POLICY_CONTRAST_FINITE | 随机化基础条件、全安排均值充分性及所声明的科学界；模型中没有未纳入的额外耦合限制。 | 完整信息清单、数值或符号总体均值及界；样本极值不能代替科学界。<br>有限模型可行性、目标联合系数、端点可达；sharp 只相对于完整声明的模型。 | 有限 D1–D8/E1–E5；D1–D6最多12节点，D7/D8最多8；旧 E1/count 合同保留。合成研究审核。 |
| 有均值顺序限制的联合政策差<br>MEAN_ORDER_D2_E1 | 有限均值模型基础条件，加逐对象明确采用的本人／同伴均值顺序；保留完整限制清单。 | 数值总体均值、结果界和明确的顺序方向与范围。<br>共同模型可行性、端点可达、最优性或不可行对偶证据。 | 当前 D2/E1、最多12对象、数值合同；不能泛化到任意额外不等式。合成研究审核。 |
| DAG 后门、调整集及经典前门<br>DAG_CLASSICAL_BACKDOOR<br>DAG_ADJUSTMENT<br>DAG_CLASSICAL_FRONTDOOR | 完整因果图与干预语义、对应结构模型、观察总体信息；图的科学正确性由研究者承担。 | 合同所需的观测联合总体分布及严格支持。<br>分别检查后门、指定调整集或前门准则；不是用一个准则替代三个。 | 专用有限二元变量合同；经典前门的目标与中介范围受原合同限制。 |
| 一般图 ID<br>DAG_GENERAL_ID | 声明的半马尔可夫模型、观测总体律及明确的干预目标。 | 对应有限离散观测联合律与变量定义。<br>递归识别推导或不可识别 hedge 见证及其适用条件。 | 有限离散、单处理合同和资源上限；资源停止不能报告为不可识别。 |
| 二元工具变量 LATE／ATE 界<br>BINARY_IV_LATE_ATE | 工具独立性、排除、一致性、无干扰；LATE 另需单调性。 | 二元完整条件总体概率表。<br>总体表一致性与响应类型可行性；LATE 另需非零第一阶段，ATE 界无此要求。 | 二元专用模型、独立科学审核；自由文本核验不自动下发估计查询。 |
| 普通随机 ATE<br>RANDOMIZED_ATE_V3 | 随机化、一致性、无干扰；所用均值存在且有限，有限数值域可提供该依据。 | 同一人群和时期的实验总体 P(T,Y)。<br>两种处理均有正概率，目标和结果定义符合原合同。 | 默认网页限完整声明人群的无条件 1−0 公式；不自动交接估计。 |
| 只观测一个处理组的 ATE<br>ONE_ARM_ATE_BOUNDS_V2<br>ONE_ARM_NO_OUTCOME_RESTRICTION_V2 | 随机化、一致性、无干扰、均值有限；有界／无有效界结论均不得忽略额外限制。 | 实验总体 P(T,Y)，完整声明的结果域及信息。<br>处理概率为0或1；检查闭合模型、结果界和完成见证。 | 单侧界不保证均值存在；不支持的已采用或待定限制会停止。 |
| 二元结果的 Manski 界<br>MANSKI_BINARY_ATE_V2 | 一致性、无干扰；二元结果保证均值有限。不默认随机化或无混杂。 | 观测总体 P(T,Y)；T/Y 的0、1均保留在模型域中。<br>基础完成模型完整，界限和见证一致；额外已采用或待定条件不能被忽略。 | 不支持任意额外限制；明确不采用的提议不加入模型。默认网页输出公式，不自动估计。 |

## 证据怎样核验

以下方式不能混称“完全独立重放”。输入绑定防止错用材料；同实现重算可以查出记录不一致，但可能重复同一实现错误；另写的检查器也不证明现实假设成立。

| 方法组 | 实际验证方式 | 检查边界与源码 |
| --- | --- | --- |
| 原设计局部均值及效应 | 逐臂核验与组合重放 | 检查输入、单臂证明和非零系数；组合重算与单独支持概率核对并存，不称整条链路有第二套独立求解器。<br>[identification_batch](../pfn_pipeline/identification_batch.py)<br>[identification_composition](../pfn_pipeline/identification_composition.py) |
| 完整政策、有限混合与两政策差 | 同实现重算＋单独概率检查 | 由已绑定输入再次调用政策求解实现，并用另一段概率计算核对支持；有限混合另核对分量和权重。<br>[identification_policy_r1b](../pfn_pipeline/identification_policy_r1b.py)<br>[fixed_comparison](../cfm_id/fixed_comparison.py) |
| 均值签名政策及两政策差 | 同实现重算 | 签名方法 replay 再次调用 _solve 并比较完整结果；不据此声称存在独立实现的签名公式证明器。<br>[identification_policy_r2](../pfn_pipeline/identification_policy_r2.py)<br>[policy_difference](../cfm_id/workflows/policy_difference.py) |
| 固定背景下的观察性政策 | 同实现重算＋单独支持检查 | 重算已绑定的观察性结果，再执行单独的完整安排／局部支持审计；不把两者合称独立求解。<br>[identification_observational_r3](../pfn_pipeline/identification_observational_r3.py) |
| 观测律条件平均的局部效应 | 同实现重算＋单独支持检查 | 重算已绑定的观察性结果，再执行单独的完整安排／局部支持审计；不把两者合称独立求解。<br>[identification_observational_effects](../pfn_pipeline/identification_observational_effects.py) |
| 共同处理前分层调整 | 同实现重算＋单独支持检查 | 重算已绑定的观察性结果，再执行单独的完整安排／局部支持审计；不把两者合称独立求解。<br>[identification_observational_exposure_adjustment](../pfn_pipeline/identification_observational_exposure_adjustment.py) |
| 节点及邻居特征调整 | 同实现重算＋单独支持检查 | 重算已绑定的观察性结果，再执行单独的完整安排／局部支持审计；不把两者合称独立求解。<br>[identification_observational_nodewise_adjustment](../pfn_pipeline/identification_observational_nodewise_adjustment.py) |
| 有限均值盒政策界限 | 独立有限模型端点核验 | 验证器核对完整安排、支持、已知均值、目标系数及可达端点；符号路径另查参数域，不声称所有界都使用对偶证书。<br>[bounded_policy_contract](../cfm_id/bounded_policy_contract.py)<br>[bounded_count_contract](../cfm_id/bounded_count_contract.py)<br>[bounded_finite_contract](../cfm_id/bounded_finite_contract.py)<br>[bounded_policy_verify](../cfm_id/bounded_policy_verify.py)<br>[bounded_contrast_verify](../cfm_id/bounded_contrast_verify.py)<br>[bounded_count_verify](../cfm_id/bounded_count_verify.py)<br>[bounded_finite_verify](../cfm_id/bounded_finite_verify.py) |
| 有均值顺序限制的联合政策差 | 独立端点与对偶核验 | 验证可行端点及最优性对偶证据；不可行时检查 Farkas 证据，不重新调用生产端优化器。<br>[mean_order_contract](../cfm_id/mean_order_contract.py)<br>[mean_order_verify](../cfm_id/mean_order_verify.py) |
| DAG 后门、调整集及经典前门 | 独立图准则与公式核验 | 按对应图准则重新检查路径／调整集和证书中的公式；仍共享输入合同，不验证现实中的图是否正确。<br>[dag_backdoor_contract](../cfm_id/dag_backdoor_contract.py)<br>[dag_adjustment_contract](../cfm_id/dag_adjustment_contract.py)<br>[dag_frontdoor_contract](../cfm_id/dag_frontdoor_contract.py)<br>[dag_backdoor_verify](../cfm_id/dag_backdoor_verify.py)<br>[dag_adjustment_verify](../cfm_id/dag_adjustment_verify.py)<br>[dag_frontdoor_verify](../cfm_id/dag_frontdoor_verify.py) |
| 一般图 ID | 图推导／hedge 核验 | 检查递归 ID 推导或 hedge 见证；另有数值一致性检查。资源耗尽或未产生公式不等于不可识别证明。<br>[dag_id_contract](../cfm_id/dag_id_contract.py)<br>[dag_id_verify](../cfm_id/dag_id_verify.py) |
| 二元工具变量 LATE／ATE 界 | 精确见证、比值与对偶核验 | 用有理数核对响应类型见证、LATE 比值、ATE 端点和对偶约束；不相容时核对 Farkas 证据。<br>[iv_route_contract](../cfm_id/iv_route_contract.py)<br>[iv_exact_verify](../cfm_id/iv_exact_verify.py) |
| 普通随机 ATE | 原生公式／界限独立核验 | 原验证器另查条件、公式或完成见证；网页整份报告还会重走适配过程，两种重放不混为一种。<br>[legacy_ate_contract](../pfn_pipeline/_internal/identification/legacy_ate_contract.py)<br>[verifier](../pfn_pipeline/_internal/identification/verifier.py) |
| 只观测一个处理组的 ATE | 原生公式／界限独立核验 | 原验证器另查条件、公式或完成见证；网页整份报告还会重走适配过程，两种重放不混为一种。<br>[legacy_ate_contract](../pfn_pipeline/_internal/identification/legacy_ate_contract.py)<br>[verifier](../pfn_pipeline/_internal/identification/verifier.py) |
| 二元结果的 Manski 界 | 原生公式／界限独立核验 | 原验证器另查条件、公式或完成见证；网页整份报告还会重走适配过程，两种重放不混为一种。<br>[legacy_ate_contract](../pfn_pipeline/_internal/identification/legacy_ate_contract.py)<br>[verifier](../pfn_pipeline/_internal/identification/verifier.py) |

## 实际登记的入口

共同业务读取、专用研究入口和默认网页适配是不同入口。专用研究入口存在不等于默认网页已支持任意自然问法；任何入口均不得省略来源审核或科学条件。

| 方法 | 共同读取 | 专用研究入口 | 普通 ATE 默认网页适配 |
| --- | --- | --- | --- |
| network.randomized.local_mean | NETWORK_RANDOMIZED_ARM_FACTS | — | — |
| network.randomized.local_contrast | NETWORK_RANDOMIZED_EFFECT_FACTS | — | — |
| network.randomized.full_policy_mean | NETWORK_FIXED_POLICY_FACTS | — | 已接入；不自动交接估计 |
| network.randomized.finite_policy_mean | NETWORK_FINITE_POLICY_FACTS | — | 已接入；不自动交接估计 |
| network.randomized.full_policy_contrast | NETWORK_POLICY_CONTRAST_FACTS | — | 已接入；不自动交接估计 |
| network.randomized.signature_policy_mean | NETWORK_FIXED_POLICY_FACTS | — | 已接入；不自动交接估计 |
| network.randomized.signature_policy_contrast | NETWORK_POLICY_CONTRAST_FACTS | — | 已接入；不自动交接估计 |
| network.observational.full_policy_mean | NETWORK_OBSERVATIONAL_POLICY_FACTS | — | 已接入；不自动交接估计 |
| network.observational.signature_policy_mean | NETWORK_OBSERVATIONAL_POLICY_FACTS | — | 已接入；不自动交接估计 |
| network.observational.observed_law_contrast | NETWORK_OBSERVATIONAL_EFFECT_FACTS | — | 已接入；不自动交接估计 |
| network.observational.shared_stratum_contrast | NETWORK_OBSERVATIONAL_EFFECT_FACTS | — | 已接入；不自动交接估计 |
| network.observational.local_covariate_contrast | NETWORK_OBSERVATIONAL_EFFECT_FACTS | — | 已接入；不自动交接估计 |
| BOUNDED_POLICY_MEAN_D2_E1 | NETWORK_FIXED_POLICY_FACTS | — | — |
| BOUNDED_POLICY_CONTRAST_D2_E1 | NETWORK_POLICY_CONTRAST_FACTS | — | — |
| BOUNDED_POLICY_MEAN_D2_E4 | NETWORK_FIXED_POLICY_FACTS | — | — |
| BOUNDED_POLICY_CONTRAST_D2_E4 | NETWORK_POLICY_CONTRAST_FACTS | — | — |
| BOUNDED_POLICY_MEAN_FINITE | NETWORK_FIXED_POLICY_FACTS | — | — |
| BOUNDED_POLICY_CONTRAST_FINITE | NETWORK_POLICY_CONTRAST_FACTS | — | — |
| MEAN_ORDER_D2_E1 | NETWORK_POLICY_CONTRAST_FACTS | MEAN_ORDER_D2_E1 | — |
| DAG_CLASSICAL_BACKDOOR | VARIABLE_DAG_FACTS | DAG_CLASSICAL_BACKDOOR | — |
| DAG_ADJUSTMENT | VARIABLE_DAG_FACTS | DAG_ADJUSTMENT | — |
| DAG_CLASSICAL_FRONTDOOR | VARIABLE_DAG_FACTS | DAG_CLASSICAL_FRONTDOOR | — |
| DAG_GENERAL_ID | — | DAG_GENERAL_ID | 已接入；不自动交接估计 |
| BINARY_IV_LATE_ATE | — | BINARY_IV_LATE_ATE | 已接入；不自动交接估计 |
| RANDOMIZED_ATE_V3 | — | — | 已接入；不自动交接估计 |
| ONE_ARM_ATE_BOUNDS_V2 | — | — | 已接入；不自动交接估计 |
| ONE_ARM_NO_OUTCOME_RESTRICTION_V2 | — | — | 已接入；不自动交接估计 |
| MANSKI_BINARY_ATE_V2 | — | — | 已接入；不自动交接估计 |

## 保留的 population 后端

以下列表读取原引擎登记，并单独标出停用、隔离和保守停止分支。登记存在不等于规则可执行；不是新增的同层定理分类，也不是自由文本覆盖承诺。

| 后端 | 执行状态 | 说明 |
| --- | --- | --- |
| randomized_network_arm_mean_v1 | ACTIVE_CANDIDATE | 可参与原生候选选择，仍须通过本题条件、信息与证书核验。 |
| network_majority_score_composition_v1 | ACTIVE_CANDIDATE | 可参与原生候选选择，仍须通过本题条件、信息与证书核验。 |
| network_majority_design_average_v1 | ACTIVE_CANDIDATE | 可参与原生候选选择，仍须通过本题条件、信息与证书核验。 |
| randomized_ate_v3 | ACTIVE_CANDIDATE | 可参与原生候选选择，仍须通过本题条件、信息与证书核验。 |
| one_arm_ate_support_v2 | ACTIVE_CANDIDATE | 可参与原生候选选择，仍须通过本题条件、信息与证书核验。 |
| manski_binary_ate_v2 | ACTIVE_CANDIDATE | 可参与原生候选选择，仍须通过本题条件、信息与证书核验。 |
| network_direct_effect_sensitivity_bounds_v2 | QUARANTINED | 暴露概率比不足以推出所需结果密度比桥接；仅返回未覆盖，不给因果界限。 |
| network_direct_effect_threshold_point_v2 | RETIRED | 旧规则已停用：supports 始终为 false，不能计入当前能力。 |
| network_policy_value_bernoulli_v1 | RETIRED | 旧规则已停用：supports 始终为 false，不能计入当前能力。 |
| conservative_ate_fallback_v2 | STOP_ONLY | 保守停止分支，不提供新的识别公式或界限。 |
| conservative_policy_value_fallback_v1 | STOP_ONLY | 保守停止分支，不提供新的识别公式或界限。 |
| conservative_network_direct_effect_fallback_v1 | STOP_ONLY | 保守停止分支，不提供新的识别公式或界限。 |

## 维护与结论边界

- 原 v27 条件接口仍只描述原八条网络路线；完整维护清单使用本表。旧接口输出保持兼容。
- POINT、PARTIAL 需要对应证据通过；PARTIAL 的 sharp 性仅针对完整声明的模型。
- 缺材料、待确认、UNSUPPORTED、资源停止、尚未找到公式及验证失败各保留原原因，均不自动升级为不可识别证明。
- 单独的原生条件字典通过 catalog() 返回；没有现成字典的方法引用各自合同，不在这里复制准入逻辑。
- 图与普通 ATE/Manski 的默认入口核验结论不等于估计交接授权。各入口权限继续由原合同控制。
- 文献及定理含义参见 [条件目录](ASSUMPTION_ROUTE_MATRIX_ZH.md) 和 [六项结构](IDENTIFICATION_STUDY_SPEC_ZH.md)。本次没有新增数学定理。

当前逐方法覆盖、文献对应及缺口优先级见 [数学覆盖核对](MATHEMATICAL_COVERAGE_AUDIT_ZH.md)。

更新命令：python -m cfm_id.method_catalog --write-doc docs/METHOD_CONDITIONS_AND_VERIFICATION_ZH.md
