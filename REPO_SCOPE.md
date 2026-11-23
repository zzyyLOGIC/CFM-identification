# 仓库范围

本仓库交付因果识别的读题、审核、数学求解、识别证书重放，以及面向估计端的总体查询。网络干扰是主要应用。图识别和二元工具变量按照各自的输入合同运行。[能力范围](docs/CURRENT_SCOPE_ZH.md) · [已知限制](docs/KNOWN_LIMITATIONS_ZH.md)

`demo/` 默认先读取完整答案，再核对材料中的焦点人群、比较两端、暴露映射和分配规则。用户也可选择完整分阶段读题。取得与原研究目标一致的证书和所需审核后，两个启动入口都会登记估计查询。真实研究的科学前提需研究者确认。合成审核仅对相应演示有效。[网页用法](demo/README.md)

`pfn_pipeline/` 提供原生网络识别、固定政策值或界的识别、多个目标的组合，以及证书重放。训练、拟合和策略优化属于全流程工程。较早版本的源码与实验示例可在固定提交查阅。[历史版本](https://github.com/zzyyLOGIC/CFM-identification/tree/cb322b4061fe981a8b5fd6fbd39660209c433911)

经典流程的编程入口为 `cfm_id.project`。[开发入口](docs/DEVELOPMENT_ENTRY_ZH.md) · [目录布局](docs/REPOSITORY_LAYOUT_ZH.md)
