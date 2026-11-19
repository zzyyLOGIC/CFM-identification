# 任务 2 总报告

## 1. 交付范围

- 21 个文献/数学情境；
- 每个情境 3 个版本：原题、缺条件、目标/条件变化；
- 来源卡、公开业务材料、隔离参考答案、运行记录、老师复核表；
- 4 个 holdout；
- 案例校验工具和单元测试。

## 2. 状态汇总

### 完整结构化运行

- `LIT-NET-01`：POINT ×3；缺条件 `NEEDS_INPUT`；反向 POINT。
- `LIT-NET-02`：疫苗 POINT；缺第一阶段排除 `NEEDS_INPUT`；反向 POINT。
- `LIT-NET-03`：PARTIAL `[3/7,4/7]`；缺模型 `NEEDS_INPUT`；额外限制 `ADAPTER_NOT_CONNECTED`。
- `LIT-NET-04`：PARTIAL `[1/5,1]`；缺同伴顺序 `NEEDS_INPUT`；单对象 POINT `1/5`。
- `LIT-NET-05`：校园邀请 POINT；缺设计 `NEEDS_INPUT`；反向 POINT。
- `LIT-NET-06`：示范农户 POINT；缺概率 `NEEDS_INPUT`；换政策 POINT。
- `LIT-DAG-01`：后门 POINT；缺图 `NEEDS_INPUT`；控制中介 `UNSUPPORTED`。
- `LIT-DAG-02`：前门 POINT；缺中介 `NEEDS_INPUT`；加直接边 `UNSUPPORTED`（holdout）。
- `LIT-NET-09`：抽查核实 POINT；缺条件 `NEEDS_INPUT`；目标变化 POINT。
- `LIT-NET-10`：覆盖方案 POINT；缺条件 `NEEDS_INPUT`；目标变化 POINT。
- `LIT-NET-11`：投放方案 POINT；缺条件 `NEEDS_INPUT`；目标变化 POINT。
- `LIT-NET-12`：带学人 POINT；缺条件 `NEEDS_INPUT`；目标变化 POINT。
- `LIT-NET-13`：父亲休假 POINT；缺条件 `NEEDS_INPUT`；目标变化 POINT。
- `LIT-NET-14`：示范农户 POINT；缺条件 `NEEDS_INPUT`；目标变化 POINT。
- `LIT-NET-15`：辅导安排 POINT（社会均衡口径）；缺条件 `NEEDS_INPUT`；目标变化 POINT。
- `LIT-NET-16`：PARTIAL `[1/6,5/6]`；缺条件 `NEEDS_INPUT`；目标变化 POINT。
- `LIT-NET-17`：PARTIAL `[7/12,3/4]`；缺条件 `NEEDS_INPUT`；目标变化 PARTIAL `[1/2,3/4]`。

以上均为 `api_calls=0`，显式合成审核，不是 LLM 准确率。

### 历史保存运行（holdout）

- `LIT-NET-07`：观察性网络 POINT；缺交换性 `NEEDS_INPUT`；反向 POINT。

原题来自历史 demo 保存运行；改动版刻意未运行，以保持 holdout。

### 当前软件未支持

- `LIT-NET-08`：Auto-G，三个版本 `UNSUPPORTED`。
- `LIT-IV-01`：LATE，三个版本 `UNSUPPORTED`。
- `LIT-IV-02`：Balke–Pearl ATE bounds，三个版本 `UNSUPPORTED`。

均保存能力检查，没有伪造 IV/Auto-G 结果。

## 2.5 LLM 评测底座

- `benchmark/cases.jsonl`：63 条公开输入，不含答案；
- `research_only/benchmark/references.jsonl`：63 条参考答案索引；
- `tools/export_benchmark.py` / `score_benchmark.py`：导出与评分；
- API Key 不进仓库，评分分开 development / holdout。

## 3. Holdout

- `LIT-NET-07`
- `LIT-NET-08`
- `LIT-IV-02`
- `LIT-DAG-02`

共 4/21，占 19%。原来的“至少 1/3”配额是按 12 个案例的库设计的；新增的 9 个情境（09–17）都在建库期间完成结构化运行并登记，不适合倒签成盲测，因此没有增设 holdout。若老师要求全库仍不低于 1/3，需要再指定 3 个情境冻结参考答案，请在复核时确认。

holdout 范围是“开发 holdout”：不用于调材料；部分来源材料在 demo 历史中存在，因此不是对仓库历史的盲测。

## 4. 运行与校验

```powershell
.venv\Scripts\python evaluation/literature_cases/tools/validate_cases.py
.venv\Scripts\python -m unittest tests_gateway.test_literature_cases -v
```

实际结果：

- `validate_cases.py`：`errors: []`；
- 13 项任务 2 单元测试通过；
- 全仓库 quick：`110 passed`；
- 全仓库 chain：`1086 passed`；
- 21 个案例、4 个 holdout、public 无参考答案。

## 5. 主要边界

- `LIT-NET-07` 的改动版尚未实际运行，作为 holdout 保留；
- 当前没有真实 LLM 首答准确率；2026-11-18 有同一材料、同一合同下的两轮 27 变体真实 LLM 读题运行（首轮 22 个跑通、5 个停在读题阶段；20:15 全量重跑 20 个跑通、7 个停在读题，POINT 11、PARTIAL 3、NEEDS_INPUT 6），两轮记录都保留，入库八题为 20:15 那轮；`LIT-NET-14` 因题面在 21:15 补了一句把处理取值与结果变量分开的说明，21:17 单题重跑后入库该轮（原题与目标变化版 `POINT`，缺条件版被结构检查拒收）；按入库记录合计 22 个变体过确认门（POINT 13、PARTIAL 3、NEEDS_INPUT 6）、5 个停在读题（4 个 `READING_NOT_CONFIRMED`、1 个 `READING_REJECTED`），其余轮次只在本地留档，属逐条记录而非准确率，逐题的读法与矛盾点见各题 `research_only/<案例>/run_record.md` 与 `review_teacher.md`；
- `UNSUPPORTED` 不等于不可识别；
- 论文参考与软件结果分开；
- sharp 只相对于声明的有限模型；
- 老师复核全部为 `PENDING_TEACHER`。

## 6. 后续

1. 老师复核 21 个案例；
2. 最终评测时再运行 `LIT-NET-07` 的 holdout；
3. 真实 LLM 读取实验由任务 6 单独负责；
4. 最终 PR 前再跑 full 套件和安装检查；quick/chain 已通过。
