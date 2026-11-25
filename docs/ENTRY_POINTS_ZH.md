# 入口、Prompt 与审核边界

完整的输入／审核／证据及适用域对照见 [统一框架合同](FRAMEWORK_CONTRACT_ZH.md)，固定检查见 [框架验收清单](FRAMEWORK_ACCEPTANCE_ZH.md)。业务用户从原问题开始，九种内部会话配置不是用户菜单。

| 用途 | 模块 / 命令 |
|---|---|
| 无路线选择的业务读取会话 | cfm_id.business_intake；cfm-id-intake；见 BUSINESS_INTAKE_ZH.md |
| 审核后的事实读取与方法检查 | cfm_id.business_dispatch；cfm-id-dispatch；变量 DAG 与已登记网络读取共八种；实际入口与保留的专用实现见 RESEARCH_SPEC_ENTRY_STATUS_ZH.md |
| 内部专门研究会话与恢复 | cfm_id.research_session；cfm-id-session；见 RESEARCH_SESSION_ZH.md |
| 逐项科学声明审核与撤回 | cfm_id.review_items；research_session.begin_item_review / decide_item / finalize_item_review；不生成原生许可 |
| 固定政策均值／差值会话适配 | cfm_id.session_policy_routes；显式选择公式 POINT 或有限界限入口，均复用原数学与审核 |
| 同一目标的条件版本对照 | cfm_id.research_versions：fork_version / plan_comparison / compare_versions；三条有限路线的声明包含检查，每版独立审核与重放 |
| 框架离线验收与逐项报告 | scripts/check_framework.py --output 新目录；清单 evaluation/framework_acceptance.json 只用于测试 |
| 网络业务读取 | cfm_id.business_entry：prepare / preview / variant |
| A0 多问题读取 | cfm_id_llm.quality_cli；cfm-id-read --help |
| 主业务 Prompt | cfm_id_llm.quality_prompts |
| 未认证候选 Prompt | cfm_id_llm.candidate_query_prompts |
| 可信 Core 适配 | cfm_id_llm.trusted_core 和 cfm_id_bridge |
| 固定名单与追问 | cfm_id.fixed_assignment、question_bound_assignment、question_clarification |
| 有限均值顺序工作流 | evaluation.mean_order_workflow |
| DAG 读取 | cfm_id_llm.dag_reading、dag_frontdoor_reading |
| DAG 业务审核 | cfm_id.dag_business |
| 显式数学路线 | evaluation.research_routes_cli：list / schema / prepare / submit / acceptance |
| NBIB 语义评测 | evaluation.nbib_semantic_eval |

业务表述、声明与科学批准是三件事。prepare 只导出请求；preview 只检查候选；submit 仍需目标和科学协议分别绑定的审核。
原合同选择符和类型名称保留，不把路径改名当成协议升级。

~~~powershell
python -m cfm_id.business_entry --help
python -m evaluation.research_routes_cli --help
python -m cfm_id_llm.quality_cli --help
~~~

在线 Provider 是显式选项，使用 CFM_ID_LLM_API_KEY 环境变量；不要把密钥写进源码或 Prompt。
离线检查不会读取密钥或调用任何模型。除接口回归必需的两份冻结读取候选外，真实历史回答档案不随包分发；合成 reference 只用于离线验收，不得进入被测模型请求。

## 命名与兼容

源码文件及 Python 模块去掉历史发布后缀。旧实现仍被依赖时按职责命名，例如 business_materials_whole_clause_evidence。
没有把不同校验层压成一个文件，也没有改动数学求解逻辑。

证书、序列化协议、模型类型和部分内部函数保留原标识；下游及第三方快照原样保留。
这些内容参与兼容或出处验证，不应批量删除其中的数字。未来修改协议需要独立迁移和负例验收。
