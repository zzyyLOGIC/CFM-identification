# 已有能力登记与实际入口

统一维护表见 [方法条件、入口与验证方式](METHOD_CONDITIONS_AND_VERIFICATION_ZH.md)，由 `cfm_id.method_catalog` 引用本登记及原生条件目录生成。它区分科学条件、信息要求、可计算检查和实现限制；同实现重算与独立检查分开说明，不另设科学准入规则。

固定政策均值和两政策之差的函数绑定统一来自 `cfm_id.policy_methods`；单局部均值和随机化局部效应来自 `cfm_id.local_methods`；观察性政策和局部效应来自 `cfm_id.observational_methods`；有限政策混合来自 `cfm_id.finite_policy_methods`；经典后门、指定调整集与经典前门来自 `cfm_id.dag_methods`。对应执行适配器也读取这些定义，避免登记与调用分别维护。`method_catalog` 仍只负责说明，不能作为审核或执行授权。八种读取协议不是八类互斥定理；当前整理范围见[识别执行层](EXECUTION_ARCHITECTURE_ZH.md)。

`NETWORK_OBSERVATIONAL_POLICY_FACTS` 绑定已有 `R3_FULL_ASSIGNMENT` 和 `R3_MEAN_SIGNATURE`。后者使用显式签名读取配置及单独的充分性审核；旧直接调用默认保持兼容；网页按家族显式选用签名合同，不能由“默认”推断其实际配置。相同固定政策目标按已审核的 `assignment_family=OBSERVATIONAL` 选择观察性事实家族，不是新目标类别，也不自动批准交换性。详见 [R3 合同与边界](R3_POLICY_ENTRY_CONTRACT_ZH.md)。

此前：`NETWORK_POLICY_CONTRAST_FACTS` 新增 `R2_ENDPOINT_DIFFERENCE` 方法绑定，仍使用原比较事实合同及两端原生 R2 证书。数学能力没有新增一种 R；该方法只是已有能力的业务组合。详情见 [接入验收](R2_CONTRAST_INTEGRATION_ZH.md)。数学材料索引在 `literature_support`，只作导航，不能成为第二个运行能力表。

`cfm_id.capability_registry` 是已有能力的封闭登记模块。它把数学能力、共同业务入口和内部研究会话的对应关系放在一起维护；这三个维度仍分别表示，不能合并成一组互斥业务类别。

用户仍从业务原问题开始。A0 提取目标和结构，经独立审核后，`business_dispatch.prepare_reader` 按结构、目标及必要的观察性／实验类别选择事实读取协议；专属适配器继续检查实际信息和科学条件，再提出方法计划。登记本身不证明适用性，不生成科学批准，也不调用 LLM。

运行目录整理后，`MEAN_ORDER_D2_E1` 的专门业务入口描述为 `cfm_id.workflows.mean_order`，与会话实际调用及 CLI 保持一致。旧 `evaluation.mean_order_workflow` 仍是兼容入口。此处只更新入口位置，路线 ID、审核合同、识别结论及证书协议不变；目录整理说明见[开发入口](DEVELOPMENT_ENTRY_ZH.md)。

## 三种视图分别负责什么

| 视图 | 登记内容 | 当前实际使用者 |
|---|---|---|
| 数学与原生研究能力 | 五个已登记的类型化研究适配器（含二元 IV）、原设计局部效应、实验政策均值与观察性网络方法、有限政策入口和独立候选研究入口 | `research_route_catalog` 使用该登记。一般图 ID 另有直接研究入口 |
| 共同业务入口 | 事实读取类别、允许提出的方法、实际检查／审核解析／执行函数，以及对应求解与重放函数 | `business_dispatch` 从登记取得实际函数，并核对生成的方法计划 |
| 内部研究会话 | 九个既有会话 ID 及所属适配组 | `session_routes` 和 `session_policy_routes` 从登记取得列表，保留原会话合同及执行流程 |

R1a/R1b/R2/R3 供历史规格、合同和已签证书查找。读者可从[研究目标、设计与证明方法对照](IDENTIFICATION_STUDY_SPEC_ZH.md)进入各项计算。D1–D8 描述分配设计，E1–E5 及固定权重、分组暴露描述同伴状态。九个会话 ID 对应内部研究配置。

## 共同业务入口当前接通什么

| 已审核的目标 | 事实读取协议类别 | 可以提出的方法计划 | 仍需满足的范围 |
|---|---|---|---|
| 单个固定政策的均值 | `NETWORK_FIXED_POLICY_FACTS` | R1b 完整安排、R2 均值签名、有限 D1–D8/E1–E5 政策均值界（保留旧 E1/count 协议） | 完整政策、明确评价总体及等权均值；各自 A4、A5、支持条件须继续审核／计算 |
| 观察性固定 W 下单个完整政策的均值 | `NETWORK_OBSERVATIONAL_POLICY_FACTS` | R3_FULL_ASSIGNMENT / R3_MEAN_SIGNATURE | 完整观测总体律、逐对象条件均值覆盖、独立完整向量交换性；最多12节点，仅固定W；签名另有全安排条件均值充分性及范围审核，支持由原生后端检查 |
| 第一政策均值减第二政策均值 | `NETWORK_POLICY_CONTRAST_FACTS` | 两个同方法 R1b／R2 端点的有符号组合、联合有限 D1–D8/E1–E5 差值界、D2/E1 数值均值顺序模型 | 两个完整政策、共同评价总体／结果／情境及明确差值方向；不是所有 `TOTAL_EFFECT` 都已接通 |
| 原设计条件平均下的直接／同伴效应 | `NETWORK_RANDOMIZED_EFFECT_FACTS` | 既有 R1a 局部均值的组合 | 合成研究接 D1–D8、E1–E5 及固定权重／分组暴露。外部研究审核限 D1/E1 及完整批次信息。评价名单、方向、其余安排规则与正支持逐项检查 |
| DAG 干预分布 | `VARIABLE_DAG_FACTS` | 经典后门、调整、单变量经典前门 | 各自有限变量 DAG 合同；不自动组合对象网络与变量 DAG |
| 原设计下单个对象、单个局部状态的均值 | `NETWORK_RANDOMIZED_ARM_FACTS` | R1A_RANDOMIZED_ARM | 明确节点、本人状态和同伴暴露，按原设计条件平均。合成研究范围含 D7/D8 及固定权重／分组暴露。[扩展范围](TASK1_LIMITATIONS_ZH.md) |
| 有限个完整政策的加权均值 | `NETWORK_FINITE_POLICY_FACTS` | R1B_FINITE_POLICY | 明确各完整政策及正权重，各分量分别检查支持并重放；合成研究审核 |
| 观察性直接／同伴／局部总效应 | `NETWORK_OBSERVATIONAL_EFFECT_FACTS` | R3_P_STANDARDIZED_EFFECTS、R3_EXPOSURE_ADJUSTED_EFFECTS、R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS | 区分观测律条件平均、共同处理前分层和本人与邻居二元特征调整；各自总体信息、交换性、充分性及支持条件独立审核，合成研究范围 |

共同业务入口的有限均值盒 PARTIAL 覆盖 D1–D8/E1–E5，D1–D6最多12节点、D7/D8最多8节点；需要明确的数值或符号总体均值、科学界限、全安排均值充分性及信息／约束完整性声明。符号路径输出参数域内经重放的公式，不填造总体数值；均值顺序仍限 D2/E1 数值合同。sharp 相对于审核后的模型，详见 [有限均值模型](FINITE_MEAN_BOX_MATH_ZH.md)。仅因一个 POINT 方法失败，不会自动改成 PARTIAL。方法计划可以包含多个尚未检验支持条件的方法，登记或进入计划均不等于识别成功。

`BOUNDED_POLICY_MEAN_D2_E4` 与 `BOUNDED_POLICY_CONTRAST_D2_E4` 最初作为专用研究入口加入，目前已分别接到共同政策均值和政策差读取；实际登记中的 `common_business_routes` 已包含它们。仍使用 `CountMeanInformation` 及单独审核类型，不能向旧 E1 会话传入 E4 信息。具体网页是否可执行仍由原材料绑定、科学审核及原生适用域决定，不能仅凭已登记就放行。数学合同、示例与命令见 [D2/E4 有限均值模型](BOUNDED_COUNT_MATH_ZH.md)。

普通随机 ATE、单组 ATE 和二元 Manski 另由默认网页的 `population_ate_entry` 接入，列在 `inventory().homepage_adapters`。它不是第九种网络事实家族，不改变 `reader_for('UNIT_NETWORK', 'ATE')` 的原行为，也不增加五个研究适配器或九个会话的数量。该入口限定所声明完整人群的无条件 1−0；来源核对、科学确认和原生验证保留，当前不自动交接估计。见 [ATE／Manski 交接边界](LEGACY_ATE_CONDITIONS_ZH.md)。

R1a 的直接效应支持两个比较方向。正向沿用原生具名效应合同，反向调用线性目标生产与重放函数。[局部效应入口](NETWORK_EFFECT_DISPATCH_ZH.md) · [原批设计／暴露验收](NETWORK_DESIGN_EXPOSURE_ENTRY_ZH.md) · [后续扩展](TASK1_LIMITATIONS_ZH.md)

单个局部均值、有限政策混合及 R3 的标准化效应／暴露调整由 `network_extended_dispatch` 接入各自的事实家族。R3 固定背景政策均值支持完整安排与显式签名，两者分别检查支持及科学条件。D2/E1 数值均值顺序两政策差值同时保留共同入口和专门入口。库外候选研究另有专门入口。[均值顺序接入与验收](NETWORK_MEAN_ORDER_ENTRY_ZH.md)

登记描述协议现为 `identification-capability-registry-2`，将单值 `target_kind` 改为 `target_kinds` 列表，避免为共用事实协议复制两套直接／同伴效应登记。内部九个会话 ID、原生研究目录和数学证书协议保持不变。

当前修复与发布检查见[收尾记录](RELEASE_ACCEPTANCE_ZH.md)。以下原登记验收保留其当时范围，不代表本轮模型准确率。

## 一致性检查与兼容性

- 新登记可用 `assignment_family` 细化同一目标的事实合同；旧调用的默认参数仍兼容。明确观察性但尚未连接的目标返回覆盖缺口，不送进随机化读取。DAG 分派不受这项网络分配类别影响。
- 登记直接绑定现有函数，不从业务文本导入模块或执行函数。方法 ID 读取实际适配器的常量。
- 共同分派核对所选读取类别与方法计划的类别、方法集合及重复项。未知类别、错误类别、未知／重复方法和空执行计划均阻断，返回 `CAPABILITY_REGISTRATION_MISMATCH`；这是程序接线错误，不是科学覆盖缺口。
- 历史 DAG 计划没有 `fact_family`，仅当全部方法均属于登记的 DAG 方法时保留其兼容格式；未知类别或缺少类别的网络计划不会默认转给 DAG。
- `inventory()` 每次生成独立的描述副本；修改副本不能增加路线、审批条件或运行权限。实际数学适用性仍由原合同、求解器和独立验证器检查。
- 原 `research_route_catalog` JSON 协议、九个会话 ID 与顺序、Prompt、审核摘要和证书协议保持兼容。数学 Core、求解器和独立验证器未改动。

本次局部验收使用已有完整合成材料和显式 `SYNTHETIC_TEST` 审核，不调用真实模型，不代表 LLM 准确率或无人审核的生产准入。固定会话 ID 的提交前后对照覆盖 14 个案例（12 个网络、2 个 DAG），逐项比较请求、方法计划、审核绑定和正式结果；所有内容一致。测试还注入错配方法与重放失败，检查是否阻断。

可直接检查登记内容：

```python
from cfm_id.capability_registry import inventory
data = inventory()
```

针对性检查：

```text
python -m pytest tests_gateway/test_capability_registry.py tests_gateway/test_network_dispatch.py tests_gateway/test_network_bounded_dispatch.py tests_gateway/test_network_contrast_dispatch.py -q
python -m evaluation.framework_acceptance --output /new/output/directory
```

## 后续扩展规则

先明确是新的读取协议、已有数学能力接入，还是新数学机制。实现／复用原生合同和独立验证后，登记实际函数及目标范围；共同入口若尚未接通，必须如实保留为原生能力。适配器自行检查全部信息和条件，不把科学判定复制到登记层。

更新后须以实际计划和执行验收对应关系，并覆盖缺项、拒绝／待定审核、错误绑定、原生不适用及重放失败。固定框架检查包含本次登记一致性义务。新增数学路线需要单独的数学审查，本次登记不能替代它。

事实请求的构造仍由既有 `_fact_request` 和版本化读取协议负责；新增读取类别时也须提供对应请求合同及兼容性检查。登记不自动生成 Prompt 或新的模型 Schema。
