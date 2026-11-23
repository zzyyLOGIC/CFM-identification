# 独立 Identification 仓库：布局与同步

本仓库为 `https://github.com/zzyyLOGIC/CFM-identification`。它直接承载 Identification 源码；安装、运行示例和执行测试都在仓库根目录进行，不再嵌套全流程仓库的 `research/identification/causal_idfm/`。

## 开发与发布的关系

- 负责人在 `iCFM-identification/identification/` 维护读题、数学库及网页。发布时按平铺目录导出，根目录另含启动器和查询收件器。
- **本仓库**：独立 Git 发布与学生协作副本。学生 clone 后在自己的分支开发，向本仓库提交 PR。
- **同步方向**：负责人审核学生改动后合并回维护源码，验收后再同步到发布副本；避免两处各自长期演进。替换发布工作区前先备份，并核对未提交改动和待合并贡献。
- **文档差异**：发布副本的 README、学生入口、贡献规则及 CI 按仓库根目录使用。数学代码、Prompt、协议和推荐配置保持与本轮维护源码一致。
- **记录范围**：内部任务、旧发布日志和本机存储路径不随仓库分发；保留的验收摘要标明实际运行范围，不表示在本发布副本重新执行过。

## 根目录怎样安排

| 目录/文件 | 作用 |
|---|---|
| `cfm_id/` | 公共入口、业务审核与适配；也保留已有 PARTIAL/DAG 数学合同、求解和验证 |
| `cfm_id_llm/`、`skills/` | 有来源的业务读取、协议、Prompt、诊断、复查及可选 Skill |
| `cfm_id_bridge/` | 业务/科学声明与原生对象、证书的绑定 |
| `pfn_pipeline/` | 既有网络识别数学与独立验证；保留面向下游的查询与证书合同 |
| `literature_support/` | 分类依据、文献卡、数学合同与实现导航 |
| `examples/` | 可运行教学例；`legacy/` 为兼容夹具 |
| `evaluation/` | 业务 Benchmark、评分、实验工具；参考答案不能进入正式运行链 |
| `tests/`、`tests_gateway/` | 数学/兼容测试与读取/审核/链路测试 |
| `docs/` | 当前操作、数学合同与扩展规则 |
| `assets/` | 固定材料、Mock 和回归资源 |
| `demo/` | 独立 ID 网页：业务输入、上传、必要追问、公式、条件和证书；不依赖全流程项目 |
| `scripts/` | 构建、检查与测试薄入口 |
| `identification_only/`、`predevelopment/`、`research_partial/` | 历史接口及原型，保留兼容；不作为新正式能力开发起点 |
| `.github/` | 根目录 CI 与 PR 模板 |
| `pyproject.toml`、`requirements.txt` | 安装与依赖；先用 `pip install -e .` 运行教学示例 |

不创建独立 `estimation/`、`policy/` 项目层，也不为每个贡献者分别复制完整项目。`pfn_pipeline` 这个历史包名仍被导入、测试及证书代码使用；本次不为外观整齐而重命名。正式 Core 的具体文件见[代码地图](DEVELOPMENT_ENTRY_ZH.md)。

不把 API 密钥、虚拟环境、缓存、模型 checkpoint、批量在线结果、ZIP 备份或内部任务安排放进发布内容。少量已有模型回答如用于固定兼容回放，仍按现有夹具保留，来源元数据不包含个人本机存储路径。

版本信息分开处理：旧项目显示标题和安装指引已更新；协议标识、证书类型、依赖版本、第三方模块名称与文献版本仍保留原义，不用统一改号掩盖兼容要求。历史示例生成器可能沿用固定产物名，不应据此判断当前能力；新应用从公共入口开始。

## 开始使用

在仓库根目录按 [README](../README.md) 安装，运行 POINT、PARTIAL、缺条件阻断三个示例。推荐入口是 `cfm_id.project`，配置为 `cfm_id/configuration/reading.json`。开发规则见 [CONTRIBUTING](../CONTRIBUTING.md)。

CI 沿用团队 Identification 检查的依赖与命令，工作目录和产物路径改为本仓库根目录；不调用外部模型。远端 CI 结果需在真正提交后查看，不能用本地复制检查冒充。
