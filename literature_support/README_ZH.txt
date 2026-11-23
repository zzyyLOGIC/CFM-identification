文献支撑与数学合同导航
维护更新：2026-11-09；各文献的实际阅读日期和范围仍见原卡片

这里保存可核查的文献卡片和研究追溯关系，不存放下载的论文原文。现补充网络综述、R1/R3 来源与分类导航，并保留有限 D2/E1 mean-box、政策差值、均值顺序、静态 DAG 后门/调整/前门的研究映射。二元 IV 已登记 BINARY_IV_LATE_ATE 显式结构化研究路线，支持独立读取/科学审核和证书重放；尚未开放自由文本自动入口或网页，真实模型验收仍待完成。一般 ID 仍属预研；全项目文献审查仍未完成。IV 来源卡片保留实际阅读范围，尚未完成的原定理正文核对不得写成已完成。

当前职责：文献卡只维护外部依据与阅读范围；mathematical_contracts.json 链接项目数学合同和对应实现，不参与运行。当前可调用能力以 cfm_id.capability_registry.inventory() 为准，路线 JSON 中带日期的研究状态是历史信息。详情见 ../docs/MATH_AND_EVIDENCE_ZH.md。本轮补齐所有已登记路线的导航，不声称已经完成全部文献综述。

从哪里看
0. CLASSIFICATION_ZH.md 与 classification_map.json：哪些分类来自综述/具体论文，哪些是项目整理；设计与暴露设置、历史方法合同和审核阶段各自的用途与限制。新增能力要求见 ../docs/EXTENSION_MAINTENANCE_ZH.md。
1. catalog.json：文献题名、作者、年份、发表载体、文章类型、原文链接、DOI，以及实际阅读级别。每张卡明确“支撑什么”与“不支撑什么”。
2. routes/bounded_policy_contrast.json：把文献对应到定义或假设，再对应项目推导、实现路径和验收义务。实现与测试路径不等于已验收；实际运行结果见其中的 verification_evidence。
3. ../docs/BOUNDED_CONTRAST_MATH_ZH.txt：本路线唯一的完整推导入口。文献卡片不重复整篇证明，避免出现两份互相漂移的数学文本。共用单政策模型的原始说明在 ../docs/BOUNDED_POLICY_MATH_ZH.md。
4. routes/mean_order_research.json 与 ../docs/MEAN_ORDER_RESEARCH_ZH.txt：均值偏序的来源、完整项目推导、同题假设阶梯和证书义务。独立数学后端见 ../docs/MEAN_ORDER_BACKEND_ZH.txt；合成业务审核连接与真实读取试测见 ../docs/MEAN_ORDER_BUSINESS_ZH.txt。少量试测不等于已注册的真实业务服务。
5. routes/dag_classical_backdoor.json 与 ../docs/DAG_BACKDOOR_RESEARCH_ZH.txt：经典后门充分判据、符号总体分布、图与正性审核，以及独立活动路径验证。该路线已有自然语言读取的受控小样本验收，不等于真实业务图已被科学批准。
6. routes/dag_adjustment.json 与 ../docs/DAG_ADJUSTMENT_RESEARCH_ZH.txt：文献DAG调整判据在二元合同下的充分识别路线；独立adapter已离线验收，现通过共享DAG读取和业务桥接显式接入。补充指定合法后代集合的检查；不宣称二元必要性或一般ID完备性。Textor与Liśkiewicz的最小集结果用于约束覆盖增量的解释。真实模型表现见路线business_interface中的本轮结果，不由文献引用推断准确率。
7. routes/dag_classical_frontdoor.json 与 ../docs/DAG_FRONTDOOR_CONTRACT_ZH.txt：经典单变量前门的合同、实现及独立验证。文献依据是 Pearl 的经典定理及 NeurIPS 2022 相关算法论文；已有显式研究入口与共同业务连接，不是一般 ID。designs/classical_frontdoor.json 保留实施前设计，当前运行状态以能力登记为准。

8. mathematical_contracts.json：所有已登记路线的项目数学文档和实现位置。routes/network_r2_policy_difference.json 说明已有 R2 恒等式有向相减的依据；不能将背景文献误写为该组合的逐字定理或新数学发现。
9. routes/network_r1a.json、network_r1b.json、network_r3_policy.json、network_r3_standardization.json、network_r3_exposure.json：本次补齐原缺少映射的五个条目。文献背景与项目特化证明分别标记；不能把 Forastiere 的局部调整目标等同全部 R3。
10. routes/binary_iv_late_ate.json：二元 IV 的 LATE 与 ATE 文献映射、实现位置和验证义务；直接推导见 ../docs/IV_MATH_ZH.md，研究接口运行及后续业务验收要求见 ../docs/IV_ACCEPTANCE_ZH.md。能力登记和合成回归不证明科学假设，也不代表真实业务验收已完成。

必须保留的几个区别
- 名刊发表信息与数学适用性是两件事。Manski (1990) 属于 American Economic Review 的 Papers and Proceedings，不省略这一文章类型。
- 读到题录、摘要、选定章节、通读全文是不同阅读级别。Manski (1997) 本轮只读到出版学会官方摘要与书目，不能写成全文或全部定理已核验。
- 本项目 signed mean-box contrast 的界、相消与 sharpness 是在明确合同下直接推导的。它不是声称某篇文献已经逐字提供了项目这条定理，也不宣称数学创新。
- 文献是科学依据和研究路线的来源，不会自动接受某条业务假设。业务理解、目标绑定、A4 来源、A5 审核和独立证书重放仍各负其责。
- 相同 mean-box 下的政策差值是第二种目标形式，尚未验证一般耦合约束的所有扩展。单调性、撤回均值充分性、其他设计/暴露及 DAG/IV 各有后续合同和证明义务。
- Kim、Kwon、Kwon和Lee (2018) 的正式全文已核对所列均值单调章节。其smooth-monotone不等于Manski (2013) 的semi-monotone；本项目不默认接受平滑性，也不将均值非减升级为逐结果非减。
- sharp 有效界与 sharp 无信息逻辑界都可能是 PARTIAL；它们不是无界或系统不支持。假设阶梯要固定问题、目标和 A4，明确究竟改变哪一条假设。

阅读级别约定
metadata_and_indexed_first_page_excerpt：原刊题录与可检索首页片段，不声称全文已读。
publisher_abstract_and_metadata：出版机构摘要与书目，不导入未读的具体定理。
abstract_and_metadata：作者稿摘要与书目。
selected_full_text_sections：实际核对了列出的正文部分，未把其余内容宣称已复核。
full_text_verified 目前均为 false：这不否认部分正文确实已读，而是防止将局部核对升级为整篇核验。
metadata_and_indexed_abstract / abstract_and_indexed_selected_sections：本次部分原文访问受限，只记录实际可读摘要、题录或指定索引片段；新方法实现前仍须完成原定理阅读。文献卡上的“source支持”与“软件已证明”分别管理。

新增路线时的最小维护方式
先给文献新增稳定 source_id，并保留实际 read_scope 和不适用边界。然后为路线新增独立 JSON：列明模型、目标、信息、科学限制、直接推导路径、实现位置和测试证据来源。不要用一条泛泛引用替代 sharpness、端点可达性或独立验证的证明。改变科学合同或证书版本时，检查映射是否仍成立；无需为每个同类型业务复制一套文献。

当前文件的用途是让后续研究者迅速回答：
“这个假设为什么可以研究？它是不是已被该业务接受？哪一步是项目自己的推导？哪段代码负责？哪项测试检查？”
不能把此资料夹当成科学审批结果、自动认证服务、代码运行报告或论文全文库。

路径约定
catalog.json 中 routes/... 相对当前资料夹。
route JSON 中 implementation 和 tests 列表均相对源码根目录；derivation_path 相对 route JSON 所在的 routes 目录。
verification_evidence 和 results_directory 中的历史运行记录只作开发追溯，不随本源码包分发。可用根目录 README 的离线命令重新验收；不要把缺少的历史记录当成本次运行结果。
