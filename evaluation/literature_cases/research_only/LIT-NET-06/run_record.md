# LIT-NET-06 运行记录

## 环境

- 工作副本：学生本地开发副本（个人路径不公开）
- 分支：`task2-literature-cases`
- 代码版本：`992fdf9598b1b18a16aaa5887490174f6b6e5868`
- `api_calls = 0`

## 运行命令

```powershell
.venv\Scripts\python evaluation/literature_cases/tools/run_lit_net_06.py
```

## 结果

| 版本 | 状态 | 说明 |
|---|---|---|
| 原题 | POINT | 有限随机政策均值；独立重放通过；目标指纹 `16cc9b13...3736` |
| 缺条件版 | NEEDS_INPUT | `EXTENDED_NETWORK_FACTS_INCOMPLETE`；附件已删除两份政策方案的概率 |
| 目标变化版 | POINT | 换成“培训甲乙”与“培训丙丁”；目标指纹 `101ab75f...d336` |

性质：结构化输入 + 显式合成审核，不调用 LLM。原题也保留 demo 保存记录，但本记录以本轮结构化运行为准。

## 边界

- 不是论文数据复现；
- 不是真实 LLM 首答准确率；
- 老师复核前不能标正式验收。
