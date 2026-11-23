# LIT-NET-05 运行记录

## 环境

- 工作副本：学生本地开发副本（个人路径不公开）
- 分支：`task2-literature-cases`
- 代码版本：`992fdf9598b1b18a16aaa5887490174f6b6e5868`
- `api_calls = 0`

## 运行命令

```powershell
.venv\Scripts\python evaluation/literature_cases/tools/run_lit_net_05.py
```

## 结果

| 版本 | 状态 | 说明 |
|---|---|---|
| 原题 | POINT | 独立重放通过；目标指纹 `24af3817...a1e` |
| 缺条件版 | NEEDS_INPUT | `NETWORK_EFFECT_FACTS_INCOMPLETE`；附件已删除邀请名单产生规则 |
| 目标变化版 | POINT | 反向比较；目标指纹 `cfed596a...0ef`；表达式符号相反 |

性质：结构化输入 + 显式合成审核，不调用 LLM。原题也保留了 2026-11-04 demo 保存记录，但本记录以本轮结构化运行为准。

## 边界

- 不是论文 56 所学校数据复现；
- 不是真实 LLM 首答准确率；
- 老师复核前不能标正式验收。
