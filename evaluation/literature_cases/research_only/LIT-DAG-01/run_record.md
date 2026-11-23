# LIT-DAG-01 运行记录

## 1. 运行环境

- 工作副本：学生本地开发副本（个人路径不公开）
- 分支：`task2-literature-cases`
- 代码版本：`992fdf9598b1b18a16aaa5887490174f6b6e5868`
- Python：3.13（`.venv`）
- `api_calls = 0`

## 2. 运行命令

```powershell
.venv\Scripts\python evaluation/literature_cases/tools/run_lit_dag_01.py
```

性质：

- 走现有 DAG 业务读取、后门检查、科学审核和证书重放；
- 使用显式合成审核（`SYNTHETIC_TEST`）；
- 不调用 LLM；
- 不是现实医学/管理事实的批准。

## 3. 原题运行结果

- 状态：`POINT`
- 独立重放：通过
- 调整集合：`["资深员工"]`
- 公式操作：`BACKDOOR_ADJUSTMENT`
- 求和变量：`["资深员工"]`
- 条件项：`p(业绩达标 | 参加培训, 资深员工)`
- 边际项：`p(资深员工)`
- 目标：`p(业绩达标 | do(参加培训=x))`

证书摘要：

```text
theorem = CLASSICAL_BACKDOOR_SUFFICIENT
status = POINT
problem_sha256 = 3927701c8c386c02c2b72a9ab04c4af240ad6851f76bce855117338db81970dd
certificate_sha256 = 2d1d9c24e6ab5bb6689e85b01c2cb684a3e9c9f5289d4e11aa6cb0e5879f6b9d
```

对应论文式 (6)：

\[
p(y\mid do(x))=\sum_z p(y\mid x,z)p(z).
\]

## 4. 缺条件版运行结果

- 状态：`NEEDS_INPUT`
- 原因：`MISSING_OR_AMBIGUOUS_DAG_DECLARATIONS`

行为符合预期：

- 删除了“图完整 / 所有共同原因均已列出”的声明；
- 系统没有默认图完整；
- 没有生成证书；
- 要求补充 DAG 的完整声明。

## 5. 目标变化版运行结果

- 状态：`UNSUPPORTED`
- 原因：`ADJUSTMENT_CONTAINS_TREATMENT_DESCENDANT`

行为符合预期：

- 业务方要求控制“培训之后是否取得资深资格”；
- 这个变量是处理的后代；
- 不满足后门准则；
- 系统拒绝把控制中介后的公式当作总效应。

## 6. 结论与边界

已完成：

- 原题 POINT，公式与 Pearl 式 (6) 一致；
- 缺图条件版正确停止；
- 控制治疗后中介版正确拒绝；
- 证书重放通过；
- 论文参考与软件结果分开。

未完成：

- 老师复核；
- 前门案例（可以作为第二个 DAG 情境）；
- 扩到 12 个情境。

因此当前状态是：**DAG 模板完成，等待老师复核。**
