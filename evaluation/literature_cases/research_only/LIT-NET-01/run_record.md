# LIT-NET-01 运行记录

## 1. 运行环境

- 工作副本：学生本地开发副本（个人路径不公开）
- 分支：`task2-literature-cases`
- 代码版本：`992fdf9598b1b18a16aaa5887490174f6b6e5868`
- Python：3.13（`.venv`）
- 环境冒烟检查：

```powershell
.venv\Scripts\python -m examples.student_handoff --allow-synthetic-reviews --output outputs/task2_first_run
```

结果：

- POINT：通过
- PARTIAL：通过
- NEEDS_INPUT：正确停止

## 2. 本轮结构化运行说明

运行入口：

```powershell
.venv\Scripts\python evaluation/literature_cases/tools/run_lit_net_01.py --variant all
```

性质：

- 走现有 `business_intake → business_dispatch → business_case` 流程；
- 使用显式合成审核（`SYNTHETIC_TEST`）；
- **不调用 LLM**，`api_calls = 0`；
- 不是真实 LLM 首答准确率，也不替代任务 6 的读取实验；
- 用来检查结构化输入、审核、方法分派、求解和证书重放。

输出目录：

```text
evaluation/literature_cases/research_only/LIT-NET-01/structured_runs/
  original/
  missing_condition/
  changed_target/
  SUMMARY.json
```

## 3. 原题运行结果

| 目标 | 状态 | 独立重放 | 目标指纹 |
|---|---|---|---|
| 直接效应 | POINT | 通过 | `c10f55d3...5738` |
| 溢出效应 | POINT | 通过 | `7b7a13b2...9e6d` |
| 局部总效应 | POINT | 通过 | `508fd811...4a4d` |

整体状态：`ALL_QUERIES_IDENTIFIED`。

直接效应表达式开头：

```text
-1/60*E[Y_node-0 | W,T_node-0=0,S_node-0=0]
+1/60*E[Y_node-0 | W,T_node-0=1,S_node-0=0] ...
```

溢出效应表达式开头：

```text
-1/60*E[Y_node-0 | W,T_node-0=1,S_node-0=0]
+1/60*E[Y_node-0 | W,T_node-0=1,S_node-0=1] ...
```

局部总效应表达式开头：

```text
-1/60*E[Y_node-0 | W,T_node-0=0,S_node-0=0]
+1/60*E[Y_node-0 | W,T_node-0=1,S_node-0=1] ...
```

说明：

- 三个目标都评价全部 60 家门店，权重为 `1/60`；
- 其余门店安排保留原设计条件平均，没有替换成全体使用/全体不使用的政策价值；
- 证书重放通过，但这认证的是本案例声明的目标，不是论文实地实验的数值复现。

## 4. 缺条件版运行结果

整体状态：`NEEDS_INPUT`。

| 目标 | 状态 | 停止原因 |
|---|---|---|
| 直接效应 | NEEDS_INPUT | `NETWORK_EFFECT_FACTS_INCOMPLETE` |
| 溢出效应 | NEEDS_INPUT | `NETWORK_EFFECT_FACTS_INCOMPLETE` |
| 局部总效应 | NEEDS_INPUT | `NETWORK_EFFECT_FACTS_INCOMPLETE` |

行为符合预期：

- 只给了 30 条边，没有补全 120 条边；
- 没有对全部门店计算同伴暴露；
- 没有生成证书；
- 这是材料缺口导致的停止，不是“已经证明不可识别”。

## 5. 目标变化版运行结果

整体状态：`ALL_QUERIES_IDENTIFIED`。

| 目标 | 状态 | 独立重放 | 目标指纹 |
|---|---|---|---|
| 反向溢出效应 | POINT | 通过 | `58385584...d8c1` |

反向溢出表达式开头：

```text
+1/60*E[Y_node-0 | W,T_node-0=1,S_node-0=0]
-1/60*E[Y_node-0 | W,T_node-0=1,S_node-0=1] ...
```

与原题溢出效应比较：

- 原题是 `(T=1,S=1) - (T=1,S=0)`；
- 改动版是 `(T=1,S=0) - (T=1,S=1)`；
- 两项表达式符号相反，目标指纹不同；
- 没有复用原题的正向证书。

## 6. 历史 demo 保存记录

仓库 `demo/examples.json` 还保存了 2026-11-03 LongCat-2.5 的 N60 运行结果：

- 三个目标均为 POINT；
- 独立重放通过；
- 目标指纹与本轮结构化运行不同，因为来源绑定不同；
- 完整内容保存在 `actual_outputs.json`。

这份历史记录只作为补充证据，**不与 2026-11-08 的结构化运行混算**。

## 7. 当前结论与边界

已完成：

- 原题：三个目标 POINT，证书重放通过；
- 缺条件版：三个目标正确停在 NEEDS_INPUT；
- 目标变化版：反向溢出 POINT，公式符号相反；
- 公开/隔离目录分离；
- 文件与网络完整性校验通过。

尚未完成：

- 老师复核；
- 真实 LLM 自然语言读取（不属于本样板的结构化运行，也不属于任务 2 的主要交付）；
- 扩到 3 个模板和 12 个情境。

因此当前状态是：**一个完整样板的结构化运行已完成，等待老师复核与扩量。**
