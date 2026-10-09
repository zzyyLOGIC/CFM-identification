# Repository Scope

## 1. 本仓库负责什么

本仓库的主要职责是 **population-level causal Identification**：从一个已经形式化的
`TaskSpec`（其中包含 `identification_spec`，内部验证为 `IdentificationSpec`）出发，检查 theorem 所需 assumptions 与 query-specific support，
运行可验证的 Identification route，并生成 `IdentificationResult` 与必要的 Estimation handoff。

当前稳定工作重点是 randomized-network POINT Identification；未来可以在同一接口下继续增加
新的 assignment / exposure / theorem families。

## 2. Identification-owned paths

下列路径属于本仓库的主要开发区域：

```text
pfn_pipeline/identification.py
pfn_pipeline/_internal/identification/**
tests/test_identification_integration.py
```

学生任务如果要进入共享代码，原则上应优先围绕这些路径工作。

## 3. Shared contract

```text
pfn_pipeline/contracts.py
```

这是 Identification 与 Estimation / Policy 的共享数据契约。它不是普通内部实现文件。
修改该文件的 PR 必须回答：

1. 为什么现有 contract 不足以表达当前 Identification 需求？
2. 是否保持现有 demo / tests 的 backward compatibility？
3. Estimation handoff 是否需要同步变化？
4. 新字段是否属于 population Identification，而不是 finite-sample Estimation 细节？

## 4. Integration-only downstream snapshot

以下代码留在仓库中，是为了确保共享 ER demo 和接口回归测试可以运行：

```text
pfn_pipeline/estimation.py
pfn_pipeline/policy.py
pfn_pipeline/pfn.py
pfn_pipeline/simulation.py
pfn_pipeline/evaluation.py
pfn_pipeline/visualization.py
pfn_pipeline/_internal/estimation/**
pfn_pipeline/_internal/policy/**
```

这些目录不是本仓库日常 feature development 的 ownership 范围。

### Downstream snapshot record

当前仓库中的 Estimation / Policy 代码来自本次清理所基于的共享 `ProjectCode.zip` 快照：

```text
snapshot date: 2026-10-09
purpose: Identification handoff compatibility + shared ER300 demo only
```

Estimation / Policy 的新研究功能由对应负责人在本仓库之外维护。
上游 commit / release 记录可在以后同步版本时补充，不作为本轮学生任务启动的前提。

默认规则：

- Identification 任务 **不要** 顺手重构 Estimation / Policy；
- 不要为了让一个学生 setting 跑通而改写下游数学；
- 如果确实出现 interface compatibility bug，在 PR 中单独说明，并尽量保持修改最小；
- 一般性的 Estimation / Policy 新功能应提交到对应负责人的项目。

## 5. Interface documentation

当前真实接口、停止条件与 handoff 说明见：

```text
docs/IDENTIFICATION_INTERFACE.md
```

第一轮正式任务书已在群内发布，任务索引与提交位置见：

```text
docs/student_tasks/
```

## 6. Shared integration artifacts

本仓库保留：

```text
notebooks/Shared_ER_Identification_Estimation_Policy_Demo.ipynb
examples/run_pipeline.py
tests/test_pipeline_smoke.py
```

它们的作用是回答一个工程问题：

> Identification 的输出能否被现有下游正确消费？

它们不是 Identification theorem 的数学依据。

## 7. Task-1 student workspace

第一次任务主要用于熟悉 setting、support、POINT argument、验证代码与 GitHub workflow。
默认把 standalone deliverables 放在：

```text
student_work/taskXX/
```

例如：

```text
student_work/task01/
├── setting.md
├── support.py
├── rule.py
├── demo.ipynb
└── test_rule.py
```

这个目录首先是 review workspace，**不是 production API**。任务完成后 PR 可以：

- 合并：如果实现形成了稳定、可复用的 Identification functionality；
- 要求修改：如果数学正确但实现需要抽象；
- review 后关闭：如果它主要是学习/setting 验证、与现有主实现重复，或不适合进入共享代码。

## 8. Merge criteria

进入 `main` 的 Identification 修改至少应满足：

1. causal target 与 assumptions 写清楚；
2. support 计算与 theorem route 一致；
3. 不把 finite-sample empty cells 当成 population non-identification；
4. 不把 unresolved assumptions 自动当作 false 或 PARTIAL；
5. 有最小可验证测试（正常、边界、zero-support / invalid-input 等）；
6. 现有 Identification tests 通过；
7. 如修改 handoff，pipeline smoke test 通过；
8. 没有无关的 Estimation / Policy feature 变化；
9. 没有提交 outputs、checkpoints、缓存或 notebook checkpoint 文件。

## 9. Intentionally excluded from Git

以下属于本地运行产物或历史材料，不应进入主仓库：

```text
checkpoints/
outputs/
.cache/
.virtual_documents/
.ipynb_checkpoints/
stales/
```

生成的 notebook HTML 也不作为 source-of-truth 维护；正式 source 是 `.ipynb` 与 Python 模块。
