# CFM-identification

本仓库是 **CFM 项目的 Identification 组件仓库**。当前开发重点不是同时维护
Estimation 与 Policy，而是把 population-level causal identification 做成一个稳定、可扩展、
可验证的独立模块，并通过一个共享的 ER300 demo 验证它能够正确向下游 Estimation / Policy
交付结果。

当前核心链路是：

```text
Formalized study specification
        ↓
TaskSpec + identification_spec
        ↓
assumptions + query-specific support
        ↓
theorem-backed Identification
        ↓
IdentificationResult
        ↓
Estimation handoff
```

> **重要：** 仓库中保留部分 Estimation / Policy 源码，仅为了让共享的全链路 demo 和
> compatibility smoke test 可以运行。它们不是本仓库的主要开发对象，也不代表
> Estimation / Policy 在这里共同维护。

## 1. 当前 Identification baseline

当前稳定 baseline 是 randomized-network POINT Identification。代码围绕一个已知、处理前固定的
unit-level network，显式 treatment assignment design、exposure rule、causal target、assumptions
与 support 进行验证。

当前 ER300 路线的核心目标是 design-standardized four-arm means。对节点 `i`，固定自身处理
`t`，让其他节点按照实验设计随机化，并在 exposure 状态为 `s` 的随机化情形中平均其潜在结果：

```text
mu_i(t,s) = E_design[ Y_i(t, T_-i) | S_i(t,T_-i)=s, pretreatment context ]
```

在当前已支持的 randomized-network setting 中，只有在必要 assumptions 被明确承认且目标 arm
具有 population support 时，Identification 才生成可执行的 Estimation handoff。未知或未解决的
assumptions 不会被自动当作 PARTIAL。

当前实现细节以代码为准，主要入口是：

- `pfn_pipeline/identification.py`
- `pfn_pipeline/_internal/identification/`
- `pfn_pipeline/contracts.py`
- `tests/test_identification_integration.py`

> **接口命名说明：** 设计讨论中我们有时把统一语义层称作“CausalTaskSpec”，但当前代码中
> **不存在名为 `CausalTaskSpec` 的类**。公共 runtime contract 是 `TaskSpec`，其中携带
> `identification_spec`；后者会被验证为内部严格的 `IdentificationSpec`。详见
> [`docs/IDENTIFICATION_INTERFACE.md`](docs/IDENTIFICATION_INTERFACE.md)。

## 2. Repository scope

### Identification-owned code（主要开发区域）

```text
pfn_pipeline/identification.py
pfn_pipeline/_internal/identification/
tests/test_identification_integration.py
```

`pfn_pipeline/contracts.py` 是 Identification 与下游共用的 contract。可以修改，但 PR 必须说明
为什么该修改是必要的、是否保持 backward compatibility、以及会怎样影响 Estimation handoff。

### Integration-only downstream snapshot

下面这些模块保留在仓库中，是为了运行共享 demo / smoke test：

```text
pfn_pipeline/estimation.py
pfn_pipeline/policy.py
pfn_pipeline/pfn.py
pfn_pipeline/simulation.py
pfn_pipeline/evaluation.py
pfn_pipeline/visualization.py
pfn_pipeline/_internal/estimation/
pfn_pipeline/_internal/policy/
```

除非任务明确要求修复 Identification 与下游的接口兼容性，否则学生 PR 不应修改这些路径。
一般性的 Estimation / Policy feature development 应在对应项目中完成。

更详细的 ownership 与 merge 规则见 [`REPO_SCOPE.md`](REPO_SCOPE.md)。

## 3. Repository layout

```text
.
├── pfn_pipeline/
│   ├── identification.py                 # public Identification entry point
│   ├── contracts.py                      # shared TaskSpec / result contracts
│   ├── _internal/identification/         # theorem / verifier / handoff implementation
│   ├── _internal/estimation/             # integration snapshot
│   └── _internal/policy/                 # integration snapshot
│
├── notebooks/
│   ├── Shared_ER_Identification_Estimation_Policy_Demo.ipynb
│   ├── er300_tutorial_helpers.py
│   └── shared_er_demo_helpers.py
│
├── examples/
│   └── run_pipeline.py                   # code-based integration demo
│
├── tests/
│   ├── test_identification_integration.py
│   └── test_pipeline_smoke.py
│
├── student_work/                         # Task-1 review workspace; not automatically merged
├── tools/run_student_tests.py            # run each student task's tests independently
├── REPO_SCOPE.md
├── CONTRIBUTING.md
├── .github/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── workflows/ci.yml                   # PR regression checks
├── docs/
│   ├── IDENTIFICATION_INTERFACE.md
│   └── student_tasks/
└── requirements.txt
```

## 4. Installation

建议使用 Python 3.10+。在仓库根目录：

```bash
python -m venv .venv
```

激活环境后：

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

本仓库不跟踪训练 checkpoint；`checkpoints/` 被 `.gitignore` 排除。

## 5. 先验证 Identification

第一次 clone 后，建议先只运行 Identification regression tests：

```bash
python -B -m unittest discover -s tests -p "test_identification_integration.py" -v
```

这组测试直接检查当前 Identification route、assumption 状态、support / handoff 以及跨网络兼容性。

如果还希望检查 Identification → Estimation → Policy 的接口没有被破坏，可以运行：

```bash
python -B -m unittest discover -s tests -p "test_pipeline_smoke.py" -v
```

`test_pipeline_smoke.py` 会在临时目录训练一个极小模型，仅用于验证 plumbing / contract
compatibility，不用于评估正式 Estimation 性能。

## 6. Shared ER300 end-to-end demo

展示 notebook：

```text
notebooks/Shared_ER_Identification_Estimation_Policy_Demo.ipynb
```

它展示：

```text
Task / network experiment
→ Identification
→ Estimation
→ Policy
```

Notebook 已保存使用预训练权重运行后的图表和中间结果，可直接阅读。默认模式为：

```python
MODE = "checkpoint"
```

本次展示沿用预训练权重对应的固定 ER300 网络（连边概率 0.02、905 条边）和数据生成设置。
权重不进入 Git；重新 `Run All` 前，需要将匹配的 `model_best.pt` 放到
`checkpoints/er_estimation_demo/`，或通过 `CHECKPOINT` / 环境变量 `CAUSALCFM_CHECKPOINT`
指定权重路径。阅读已保存的结果不需要本地权重。

没有预训练权重时，可选择 `MODE = "dense_smoke"` 验证流程。该模式使用另一张连边概率 0.5
的固定 ER300 图，现场训练极小模型（2 个训练任务、1 个 epoch），再完成估计与决策。
它仅用于接口检查，不能复现本次预训练展示的数值，也不代表正式模型精度。
Estimation 源码仍保留在 `pfn_pipeline/estimation.py`、`pfn_pipeline/pfn.py` 和
`pfn_pipeline/_internal/estimation/`。运行产生的 `outputs/` 不进入 Git。

> Notebook 中的 Estimation / Policy 结果是 integration demonstration；Identification 的数学
> 正确性仍由 theorem-backed code 与 tests 负责，而不是由 PFN 输出决定。

## 7. Pull Request 自动检查

`.github/workflows/ci.yml` 会在 Pull Request 和 `main` push 时自动运行：

```text
Identification regression tests
+ end-to-end compatibility smoke tests
+ student_work/taskXX/test_*.py
```

学生任务测试通过 `python -B tools/run_student_tests.py` 逐个任务运行。没有任务目录时跳过；
已有任务目录缺少测试、未收集到测试或测试失败时，CI 失败。CI 不执行完整展示 notebook；
原有 compatibility smoke test 仍会在临时目录训练极小模型。

建议在 GitHub 的 `main` branch protection 中把该 CI 设为 required status check。CI 只检查
代码与接口回归，不替代 theorem / assumptions 的人工 review。

## 8. Student contribution workflow

本仓库使用：

```text
Issue / assigned task
    ↓
branch from frozen baseline
    ↓
development + local tests
    ↓
Draft Pull Request
    ↓
review
    ├── request changes
    ├── approve + merge
    └── review complete + close without merge
```

学生不得直接 push `main`。第一次任务主要用于熟悉 Identification 与协作流程，因此
**完成任务不等于 PR 一定进入 main**。只有数学正确、测试充分、并且对共享 Identification
代码具有复用价值的修改才会 merge。

第一轮任务推荐把独立的学习/验证产物放在：

```text
student_work/taskXX/
```

如果任务确实发现了需要进入共享实现的通用抽象，再在同一个 PR 中明确说明为什么要修改
Identification core。

完整流程见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。
正式任务书已在群内发布；仓库中的 `docs/student_tasks/` 仅保留任务索引与提交位置。

## 9. 建议的 GitHub 初始化方式

整理好的目录可以直接执行：

```bash
git init
git add .
git commit -m "Initialize CFM-identification baseline"
git branch -M main
git remote add origin <YOUR_GITHUB_REPOSITORY_URL>
git push -u origin main
```

然后冻结第一轮学生共同起点：

```bash
git tag student-task1-baseline
git push origin student-task1-baseline
```

建议在 GitHub 的 `main` branch protection 中至少启用：

- Require a pull request before merging
- Require at least 1 approval
- Require status checks before merging（有 CI 后启用）
- Block force pushes
- Block deletion

维护者建议使用 **Squash and merge**，避免把学生调试过程中的大量小 commit 带入 `main`。
