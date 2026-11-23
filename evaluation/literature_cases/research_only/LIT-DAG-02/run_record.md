# LIT-DAG-02 运行记录

## 环境

- 工作副本：学生本地开发副本（个人路径不公开）
- 分支：`task2-literature-cases`
- 代码版本：`992fdf9598b1b18a16aaa5887490174f6b6e5868`
- `api_calls = 0`

## 运行命令

```powershell
.venv\Scripts\python evaluation/literature_cases/tools/run_lit_dag_02.py
```

## 结果

| 版本 | 状态 | 说明 |
|---|---|---|
| 原题 | POINT | 前门公式，证书重放通过 |
| 缺条件版 | NEEDS_INPUT | `CAUSAL_GRAPH_NOT_DECLARED`；图完整性未确认 |
| 目标变化版 | UNSUPPORTED | `SPECIFIED_VARIABLE_FAILS_FRONTDOOR`；加入吸烟→肺癌直接边 |

性质：原生 front-door 入口 + 显式合成审核，不调用 LLM。原题也保留 2026-11-04 demo 保存记录，但本记录以本轮结构化运行为准。

## 边界

- 不是医学事实；
- 不是真实 LLM 首答准确率；
- 老师复核前不能标正式验收。
