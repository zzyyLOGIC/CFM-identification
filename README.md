# Causal-IDFM · Identification

本项目从研究材料推导可识别的目标、公式或界，并为估计端登记所需的总体查询。网络干扰是主要应用。

默认网页入口只请求一次模型起草完整答案，随即用同一研究的原材料在本机核验。每次用户主动补交材料会启动新一轮读取，前后两版均可审查。

```text
业务问题、方案、附件 → 模型原答 → 绑定原题与材料 → 本地求解、核验
                                          ├─ 证据充分 → 公式、假设、估计交接草案
                                          ├─ 有具体材料缺口 → 追问 → 保存补充后重算
                                          └─ 未覆盖 → 保留模型草案并标出待核对项
```

当前可核验的内容包括部分网络设计下的暴露与逐人联合支持、部分有向图的前门三条件、后门调整、一般 ID 及已有的二元工具变量声明。越出已实现的输入格式时，页面仍能显示原答。材料已给出等价暴露信息时，可以核对相应的事件记录。原始边表无法重算的部分会标为待核查。只给了无条件总体平均时，还需要确认可达比较端各自的结局信息。真实研究条件须由研究者确认，审核通过后，收件器登记总体查询及其适用范围，合成审核标记为 SYNTHETIC_TEST。另可选择一次读取多方法匹配或原有分阶段审核流程。

## 个人版直接体验网页

下载完整个人仓库，在仓库根执行：

```powershell
python -m pip install -e ".[documents]"
python demo/serve.py
```

网页默认在 `http://127.0.0.1:8772/` 打开，内置 12 个可编辑示例。另一入口 `python serve.py` 默认端口 8796，手动打开浏览器。两个命令使用相同的数学核验和收件器，支持 `--data-dir` 指定本地记录目录。

支持独立上传对象名单、关系表、字段说明表及 CSV／Excel 记录，并先在本地预览。按对象编号关联，保留孤立对象及实际结果覆盖；不会把有限记录当精确总体信息。格式、用途和边界见[文件输入说明](docs/FILE_INPUT_ZH.md)。

## 唯一源码与起点

本仓库采用平铺布局。网页入口在 `demo/`，收件器在 `estimate_intake.py`。默认将运行记录保存至 `web_runs/runs/`，通过重放的估计查询包和收据保存在 `web_runs/estimation_inbox/`。

经典分阶段读题的编程入口是 `cfm_id.project`，配置为 `cfm_id/configuration/reading.json`。它读取目标、审核来源和科学条件，再交由数学库求解。网页的默认入口先取得完整直答，再就同一份原材料独立核验。详见[配置指南](docs/BUSINESS_READING_CONFIG_ZH.md)与[意图交接](docs/REVIEWED_INTENT_HANDOFF_ZH.md)。

固定政策均值和两政策差值现采用共同定义事实合同。10份冻结业务中，LongCat两轮完整链路通过9/10和8/10；DeepSeek两种设置均4/10。受测范围、失败与审核条件见[真实验收](docs/SHARED_DEFINITION_ACCEPTANCE_ZH.md)，不能将其外推为所有能力的准确率。

## 安装，运行三个完整示例

Python 3.11 或更新版本。在本目录执行：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m cfm_id.project config
.venv\Scripts\python -m examples.student_handoff --allow-synthetic-reviews --output outputs/first_run
```

Linux/macOS 将 `.venv\Scripts\python` 换成 `.venv/bin/python`。输出目录必须是新目录。以上**不联网调用模型、不需要 API Key、不需要 Torch**。

| 示例 | 业务目标与条件 | 实际输出 |
|---|---|---|
| `point` | 服务网点采用同一 AI 安排时的平均结果；已声明完整总体信息和所需科学条件 | `POINT`，识别表达式、证书、独立重放 |
| `partial` | 合作网络中一个固定推广方案的平均结果；有限总体均值和完整有界模型 | `PARTIAL`，相对该模型的 sharp 界 `[3/7, 4/7]`，证书、独立重放 |
| `missing_condition` | 与 PARTIAL 同类目标，但模型完整性条件未确认 | `NEEDS_INPUT`，列明缺项，不调用求解器 |

每个目录保存业务原文、两次读取请求与固定草稿、合成审核、计划、逐问结果及整题结果。**草稿是教学夹具，审核是显式合成审核，不是实时 LLM 结果或真实企业批准。** 源码见 [`examples/student_handoff.py`](examples/student_handoff.py)。

真实业务创建会话：

```python
from cfm_id import project
from cfm_id.business_intake import prepare_request
session = project.start(case)   # case 是含问题和材料的 BusinessCase / dict
request = prepare_request(session)  # 只准备请求；不调用模型、不自动审核
```

也可执行 `python -m cfm_id.project start --input case.json --output outputs/new_case`。后续接收回答、逐项审核、分派与执行见[会话操作](docs/BUSINESS_INTAKE_ZH.md)和[业务分派](docs/BUSINESS_DISPATCH_ZH.md)。

## 开发者按这个顺序阅读

先按[研究规格与方法](docs/IDENTIFICATION_STUDY_SPEC_ZH.md)记录目标、分配设计、暴露映射、总体信息和科学假设，再匹配同时成立的证明。文献依据与项目自定义边界见[分类与文献依据](literature_support/CLASSIFICATION_ZH.md)。内部任务分配不随源码发布。

1. [目录与代码地图](docs/DEVELOPMENT_ENTRY_ZH.md)：每个文件夹的职责，哪些文件属于数学 Core。
2. [读取配置](docs/BUSINESS_READING_CONFIG_ZH.md)：推荐起点、兼容默认和实验的边界。
3. [新增能力规则](docs/EXTENSION_MAINTENANCE_ZH.md)：能力登记、读取登记、原生证明和验收义务。
4. [当前范围](docs/CURRENT_SCOPE_ZH.md)、[数学与文献导航](docs/MATH_AND_EVIDENCE_ZH.md)：原生能力与自然语言接入并非同一范围。
5. [当前发布验收](docs/RELEASE_ACCEPTANCE_ZH.md)、[原交接验收](docs/DELIVERY_READINESS_ZH.md)、[未解决项](docs/KNOWN_LIMITATIONS_ZH.md)。

八类当前短引用读取家族已共用[读取组件登记](docs/FACT_READING_REGISTRY_ZH.md)：固定政策均值、两政策差值、局部效应、观察性网络政策、变量 DAG、随机化单臂、有限政策及观察性效应。它们各自保持目标与科学审核，登记不是数学求解器，也不会自动批准条件。

观察性固定政策均值另提供[均值签名读取配置](docs/R3_POLICY_ENTRY_CONTRACT_ZH.md)，连接固定背景下的暴露标签政策均值方法：完整政策无支持时，需要独立审核全安排条件均值充分性及其评价范围，并由原生后端验证目标签名正支持。默认读取配置保持不变；此接入的离线验收不代表LLM准确率。

已有计划可通过 `project.diagnose_methods` 查看[方法条件诊断](docs/METHOD_DIAGNOSTICS_ZH.md)。覆盖固定政策均值、两政策有向差值、局部直接效应与同伴效应、观察性固定背景完整政策均值，分开显示审核、数学检查与原执行证据；不改变执行规则、不自动补假设。固定政策示例：`python -m examples.method_diagnostics --allow-synthetic-reviews --output outputs/method_examples`；差值示例：`python -m examples.contrast_method_diagnostics --allow-synthetic-reviews --output outputs/contrast_method_examples`；局部效应示例：`python -m examples.effect_method_diagnostics --allow-synthetic-reviews --output outputs/effect_method_examples`。差值保留比较方向、共同评价范围及联合求界；局部效应保留自身/同伴两端状态、固定评价名单及原设计条件平均，局部状态成功不能替代完整效应证据。 观察性网络示例：`python -m examples.observational_method_diagnostics --allow-synthetic-reviews --output outputs/observational_method_examples`；固定背景、交换性审核和完整政策正支持分别显示。

## 修改后的检查

```powershell
python -m pip install -e ".[test,documents]"
python scripts/check_framework.py --suite quick --output outputs/quick_check
python scripts/check_framework.py --suite chain --output outputs/chain_check
python scripts/check_framework.py --suite full --output outputs/full_check
python scripts/check_offline.py
```

离线识别回归使用固定图、总体查询与证书；安装 `[test,documents]` 即可运行。在线模型准确率另行测量。[测试职责](docs/TESTING_ZH.md)

## 历史内容

当前操作指南在 `docs/`，分轮实验与旧状态记录移到 `docs/history/`。旧学生演示移到 `examples/legacy/`；其中两份模型回答是必要的冻结兼容夹具。大批在线输入输出仍保存在源码外，不随此包交付。`predevelopment/`、`research_partial/` 是保留旧导入的原型，正式 PARTIAL 位置见代码地图。协议内部标识不随文件整理更名，以保持请求、审核和证书兼容。

旧版的源代码、拟合及策略演示可按固定提交查阅。[旧版归档](https://github.com/zzyyLOGIC/CFM-identification/tree/cb322b4061fe981a8b5fd6fbd39660209c433911)
