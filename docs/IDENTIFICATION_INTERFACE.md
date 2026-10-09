# Identification Interface

这份文档只说明**当前代码真实存在的接口**，方便第一次进入仓库的学生知道输入从哪里来、
`identify()` 做什么、什么时候应该停止，以及结果怎样交给下游。

## 1. 当前没有名为 `CausalTaskSpec` 的 Python 类

在设计讨论中，我们用“causal task specification”表示统一的因果任务语义；但当前实现中，
实际公共类是：

```python
from pfn_pipeline import TaskSpec
```

`TaskSpec` 是公共任务 contract，其中可以包含一个已经形式化的 `identification_spec`。
`identify()` 会把该 payload 验证为内部的严格 schema：

```python
pfn_pipeline._internal.identification.schemas.IdentificationSpec
```

所以当前关系可以理解为：

```text
TaskSpec                         # public runtime contract
└── identification_spec         # serialized population-ID specification
    └── IdentificationSpec      # strict internal theorem input
```

未来是否把这些层收敛为一个更统一的 canonical `CausalTaskSpec`，要等 assignment / exposure /
support 接口经过更多 setting 验证后再决定；第一轮学生任务不要自行做这一重构。

## 2. Public entry point

当前 Identification 的公共入口是：

```python
from pfn_pipeline import identify

identified = identify(task)
```

其中 `task` 必须是一个 `TaskSpec`。如果 `task.identification_spec` 缺失，系统不会从有限样本
或自然语言中自行猜 causal assumptions，而是返回需要补输入的结果。

一个最直接的已有用法是：

```python
from pfn_pipeline import simulate_task, identify

# shared ER300 demo task；模拟器只负责构造测试/演示输入
# Identification 仍然只读取 TaskSpec 中允许使用的信息。
task = simulate_task(seed=2026, budget=5)
identified = identify(task)

print(identified.status)
print(identified.verification_status)
print(identified.diagnostics)
```

## 3. `identify()` 实际做什么

当前公共入口的主要流程是：

```text
TaskSpec
  ↓
validate IdentificationSpec
  ↓
IdentificationEngine route selection
  ↓
theorem backend
  ↓
IdentificationVerifier
  ↓
IdentificationResult
  ↓
compile Estimation request (only when executable)
```

这里的核心原则是：**LLM、finite-sample pattern 或 PFN 输出都不是 causal authority**；
Identification 由显式 assumptions、support 和 theorem-backed route 决定。

## 4. Assumption 状态：不要把“不知道”当成“假”

当前内部 schema 支持的主要状态包括：

```text
CERTIFIED
DERIVED
ADMITTED
PROPOSED
UNRESOLVED
NOT_ADMITTED
CONTRADICTED
```

第一轮任务最需要记住的是：

```text
UNRESOLVED / PROPOSED  → 需要更多输入，不应自动推成 PARTIAL
NOT_ADMITTED / CONTRADICTED → 当前 theorem route 不可用
```

公共结果中，工作流层面的停止原因可以从：

```python
identified.diagnostics["workflow_status"]
```

读取。当前常见值包括：

```text
COMPLETE
NEEDS_INPUT
UNSUPPORTED
```

## 5. 当前 randomized-network POINT baseline

当前 shared ER300 route 的目标是 design-standardized network arm mean。对节点 `i`：

```text
mu_i(t,s)
```

表示固定节点自身 treatment 为 `t`，让其他节点按原 assignment design 随机变化，并只在节点
暴露状态为 `s` 的随机化情形中对潜在结果取平均。

当前 POINT route 依赖的核心条件包括：

- treatment 前固定、已知的 network；
- consistency；
- full-vector randomization / known assignment law；
- finite conditional first moments；
- query-specific positive population support。

当前实现**不要求**：

```text
Y_i(T) = Y_i(T_i, S_i)
```

也就是说，strict-majority `S_i` 在当前 baseline 中是 target-standardization grouping，不必被当成
真实 outcome mechanism 的充分 exposure mapping。

## 6. Population support 与 finite sample 必须区分

Identification 检查的是 population design support，例如：

```text
P(T_i=t, S_i=s | pretreatment context) > 0
```

当前某一次实验样本中某个 cell 没有观测值，并不自动改变 population POINT status。
有限样本的不确定性属于后续 Estimation，不应被解释成 partial identification。

## 7. 怎么读 `IdentificationResult`

公共结果类型是：

```python
from pfn_pipeline import IdentificationResult
```

常用字段包括：

```python
identified.status
identified.verification_status
identified.result
identified.diagnostics
identified.estimation_request
```

建议首先看：

```python
print(identified.status)
print(identified.verification_status)
print(identified.diagnostics.get("workflow_status"))
```

只有 theorem result 可执行且 verification 通过时，才应期待：

```python
identified.estimation_request is not None
```

## 8. Estimation handoff

Identification 与 Estimation 的边界不是“把一个 POINT 字符串直接交下去”，而是编译一个可
重放验证的 handoff。下游可以使用：

```python
from pfn_pipeline import replay_handoff

request = replay_handoff(identified)
```

它会重新验证 source specification、query / graph binding 和 proof result；如果保存的 handoff 与
重新编译的结果不同，会拒绝继续执行。

因此本仓库的责任到这里为止：

```text
population specification
→ theorem-backed Identification
→ VERIFIED IdentificationResult
→ Estimation handoff
```

PFN 的训练、finite-sample estimation accuracy 和 Policy optimization 不属于当前 Identification
学生任务的主要修改范围。

## 9. 第一轮学生应该改什么

第一轮九个 setting 的主要目标是用不同 assignment / exposure 定义 stress-test 当前设计，而不是
直接重写架构。默认先把独立成果放在：

```text
student_work/taskXX/
```

只有当某个实现确实形成可复用的公共规律时，才建议在 PR 中修改：

```text
pfn_pipeline/_internal/identification/
pfn_pipeline/identification.py
pfn_pipeline/contracts.py    # shared contract，修改需要额外解释
```

当前尤其值得后续从九个任务中总结、而不是现在凭空预设计的三个接口是：

```text
AssignmentSpec
ExposureSpec
SupportEngine
```

这些名称目前是设计目标，不代表仓库里已经存在同名稳定公共类。
