# 任务 2：文献案例库说明

## 1. 范围

本目录实现任务 2 的文献案例库：

- 21 个情境；
- 每个情境包含原题、缺条件版、目标/条件变化版；
- 公开业务材料与隔离参考答案分离；
- 论文参考、软件预期、实际运行分开记录；
- 4 个 holdout。

## 2. 目录

```text
literature_support/cases/          来源卡、原文摘录、案例说明
evaluation/literature_cases/public/          公开业务材料
evaluation/literature_cases/research_only/   参考答案、实际输出、运行记录、复核表
evaluation/literature_cases/tools/           导出、运行、校验工具
evaluation/literature_cases/registry.json    案例登记
```

## 3. 21 个情境

| 编号 | 类型 | 论文/来源 | 原题状态 | 改动版 |
|---|---|---|---|---|
| LIT-NET-01 | 网络 | Aronow–Samii (2017) | POINT ×3 | 缺网络 `NEEDS_INPUT`；反向 POINT |
| LIT-NET-02 | 网络 | Hudgens–Halloran (2008) | POINT | 缺第一阶段排除 `NEEDS_INPUT`；反向 POINT |
| LIT-NET-03 | 网络 | Manski (2013) + 项目有限模型 | PARTIAL `[3/7,4/7]` | 缺模型 `NEEDS_INPUT`；额外限制 `ADAPTER_NOT_CONNECTED` |
| LIT-NET-04 | 网络 | Manski (2013) + 项目均值顺序模型 | PARTIAL `[1/5,1]` | 缺同伴顺序 `NEEDS_INPUT`；单对象 POINT `1/5` |
| LIT-NET-05 | 网络 | Paluck et al. (2016) / Aronow–Samii | POINT | 缺设计 `NEEDS_INPUT`；反向 POINT |
| LIT-NET-06 | 网络 | Beaman et al. (2021) | POINT | 缺概率 `NEEDS_INPUT`；换政策 POINT |
| LIT-NET-07 | 网络 | Forastiere et al. (2021) | POINT（holdout 历史保存） | 缺交换性 `NEEDS_INPUT`（holdout 未运行）；反向 POINT（holdout 未运行） |
| LIT-NET-08 | 网络 | Tchetgen et al. (2021) | UNSUPPORTED | UNSUPPORTED；UNSUPPORTED |
| LIT-NET-09 | 网络 | Alatas et al. (2016) | POINT | 缺条件 `NEEDS_INPUT`；目标变化 POINT |
| LIT-NET-10 | 网络 | Miguel–Kremer (2004) | POINT | 缺条件 `NEEDS_INPUT`；目标变化 POINT |
| LIT-NET-11 | 网络 | Cai–Szeidl (2018) | POINT | 缺条件 `NEEDS_INPUT`；目标变化 POINT |
| LIT-NET-12 | 网络 | Carrell et al. (2013) | POINT | 缺条件 `NEEDS_INPUT`；目标变化 POINT |
| LIT-NET-13 | 网络 | Dahl et al. (2014) | POINT | 缺条件 `NEEDS_INPUT`；目标变化 POINT |
| LIT-NET-14 | 网络 | Conley–Udry (2010) | POINT | 缺条件 `NEEDS_INPUT`；目标变化 POINT |
| LIT-NET-15 | 网络 | Manski (1993) + 项目有限模型 | POINT（社会均衡口径） | 缺条件 `NEEDS_INPUT`；目标变化 POINT |
| LIT-NET-16 | 网络 | Imbens–Manski (2004) + 项目有限模型 | PARTIAL `[1/6,5/6]` | 缺条件 `NEEDS_INPUT`；目标变化 POINT |
| LIT-NET-17 | 网络 | Chernozhukov–Hong–Tamer (2007) + 项目有限模型 | PARTIAL `[7/12,3/4]` | 缺条件 `NEEDS_INPUT`；目标变化 PARTIAL `[1/2,3/4]` |
| LIT-IV-01 | IV | Imbens–Angrist (1994) | UNSUPPORTED | UNSUPPORTED；UNSUPPORTED |
| LIT-IV-02 | IV | Balke–Pearl (1997) | UNSUPPORTED | UNSUPPORTED；UNSUPPORTED |
| LIT-DAG-01 | DAG | Pearl (1995) 后门 | POINT | 缺图 `NEEDS_INPUT`；控制中介 `UNSUPPORTED` |
| LIT-DAG-02 | DAG | Pearl (1995) 前门 | POINT | 缺中介 `NEEDS_INPUT`；加直接边 `UNSUPPORTED`（holdout） |

## 4. Holdout

4 个 holdout：

- `LIT-NET-07` 观察性网络；
- `LIT-NET-08` Auto-G；
- `LIT-IV-02` Balke–Pearl ATE 界限；
- `LIT-DAG-02` 前门。

它们的参考答案已冻结，开发时不能用来调材料。

> holdout 范围是“开发 holdout”：不用于调材料，但部分来源材料在 demo 历史中出现过，因此不是对仓库历史的盲测。

## 5. 运行性质

- `LIT-NET-01/02/03/04/05/06`、`LIT-DAG-01/02`：2026-11-08/09 结构化运行，`api_calls=0`，显式合成审核；
- `LIT-NET-09` 到 `LIT-NET-17`：2026-11-10 至 11-17 结构化运行，`api_calls=0`，显式合成审核；其中 `LIT-NET-16`、`LIT-NET-17` 的答案是识别区间；
- `LIT-NET-09` 到 `LIT-NET-17` 另有 2026-11-18 的真实 LLM 读题运行（`deepseek-chat`），同一材料同一读题合同下跑了两轮：首轮 27 个变体中 22 个跑通完整识别链路并与上面的结构化运行状态逐项一致、5 个停在读题阶段；20:15 的全量重跑 27 个变体中 20 个跑通、7 个停在读题（POINT 11、PARTIAL 3、NEEDS_INPUT 6）。`LIT-NET-14` 的题面在 21:15 补了一句把处理取值与结果变量分开的说明，21:17 单题重跑三个变体：原题与目标变化版 `POINT`，缺条件版被结构检查拒收（模型多写一个 `type` 字段）。按入库记录合计，27 个变体中 22 个过确认门（POINT 13、PARTIAL 3、NEEDS_INPUT 6），5 个停在读题（4 个 `READING_NOT_CONFIRMED`、1 个 `READING_REJECTED`）。`LIT-NET-13` 题面修订前的三份、`LIT-NET-14` 修订前的三份与首轮的全部记录共 33 个文件只在本地留档，不随仓库交付。记录见 `evaluation/literature_cases/research_only/<案例>/actual_outputs.json`（三个变体合一份），逐题的读法、矛盾点与轮次对照写在该题 `run_record.md` 与 `review_teacher.md`；
- `LIT-NET-07`：holdout，原题保留历史保存运行，改动版刻意未运行；
- `LIT-NET-08`、`LIT-IV-01/02`：当前软件无对应后端，全部 `UNSUPPORTED`，并保存能力检查；
- 真实 LLM 只跑过单模型、未固定采样温度，同一材料与合同跑了两轮（首轮 22/27、20:15 那轮 20/27、14 号题面修订后按入库记录合计 22/27，各有进退）；本库不据此声称首答准确率，读题结论逐条按记录披露，两轮记录都保留，入库的是最新一轮。

## 6. 复现

```powershell
.venv\Scripts\python evaluation/literature_cases/tools/validate_cases.py
.venv\Scripts\python -m unittest tests_gateway.test_literature_cases -v
.venv\Scripts\python scripts/check_framework.py --suite quick --output outputs/final_quick_20261111
.venv\Scripts\python scripts/check_framework.py --suite chain --output outputs/final_chain_20261111
```

当前结果：`errors: []`、13 项任务 2 测试通过、quick 110 passed、chain 1086 passed。

各结构化案例的运行脚本：

```text
evaluation/literature_cases/tools/run_lit_net_01.py
evaluation/literature_cases/tools/run_lit_net_02.py
evaluation/literature_cases/tools/run_lit_net_03.py
evaluation/literature_cases/tools/run_lit_net_04.py
evaluation/literature_cases/tools/run_lit_dag_01.py
evaluation/literature_cases/tools/run_lit_net_09.py
evaluation/literature_cases/tools/run_lit_net_10.py
evaluation/literature_cases/tools/run_lit_net_11.py
evaluation/literature_cases/tools/run_lit_net_12.py
evaluation/literature_cases/tools/run_lit_net_13.py
evaluation/literature_cases/tools/run_lit_net_14.py
evaluation/literature_cases/tools/run_lit_net_15.py
evaluation/literature_cases/tools/run_lit_net_16.py
evaluation/literature_cases/tools/run_lit_net_17.py
```


## 6.5 LLM 评测底座

```text
evaluation/literature_cases/benchmark/cases.jsonl     63 条公开输入，不含答案
evaluation/literature_cases/benchmark/schema.json     尝试记录字段
evaluation/literature_cases/research_only/benchmark/references.jsonl  63 条参考答案索引
evaluation/literature_cases/tools/export_benchmark.py 重新导出
evaluation/literature_cases/tools/score_benchmark.py  对尝试记录评分
```

公开 JSONL 不含 `expected_status`、参考文件路径或证书；参考答案索引只在 `research_only/`。  
API Key 只走环境变量，不写进仓库。

## 7. 边界

- `UNSUPPORTED` 不是“已证明不可识别”；
- 样本不等于总体；
- 论文参考不等于软件结果；
- sharp 只相对于声明的有限模型；
- 合成案例不是论文数据复现；
- 老师复核通过前不能标成正式验收；
- `LIT-NET-07` 是 holdout，改动版未运行；最终评测时再跑。
