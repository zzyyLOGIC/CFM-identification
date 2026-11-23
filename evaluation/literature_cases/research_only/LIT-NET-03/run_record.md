# LIT-NET-03 运行记录

## 1. 运行环境

- 工作副本：学生本地开发副本（个人路径不公开）
- 分支：`task2-literature-cases`
- 代码版本：`992fdf9598b1b18a16aaa5887490174f6b6e5868`
- Python：3.13（`.venv`）
- `api_calls = 0`

## 2. 运行命令

```powershell
.venv\Scripts\python evaluation/literature_cases/tools/run_lit_net_03.py
```

性质：

- 走现有 bounded-policy 有限均值入口；
- 显式合成审核；
- 不调用 LLM；
- 不是 Manski (2013) 的实证复现。

## 3. 原题运行结果

- 状态：`PARTIAL`
- 区间：`["3/7", "4/7"]`
- 宽度：`1/7`
- sharp：`true`
- informative：`true`
- 独立重放：通过
- 目标 SHA256：`fd50019f12c0745ebbf72721697ffc043042c1ebc88fbbdba2c234780f64dd01`

结构：

- 七个网点等权 `1/7`；
- 六个叶网点在“自身处理=1、同伴暴露=1”时均值 `1/2`；
- 中心在“自身处理=0、同伴暴露=0”时均值 `1/2`；
- 中心在完整政策 cell 的均值只知在 `[0,1]`。

下界：

```text
(6 × 1/2 + 0) / 7 = 3/7
```

上界：

```text
(6 × 1/2 + 1) / 7 = 4/7
```

## 4. 缺条件版运行结果

- 状态：`NEEDS_INPUT`
- 原因：`BOUNDED_MODEL_DECLARATIONS_INCOMPLETE`
- 行为：删除完整模型声明后，系统没有继续给区间，也没有生成证书。

## 5. 改动版：额外单调性

- 状态：`ADAPTER_NOT_CONNECTED`
- 原因：`ADDITIONAL_INFORMATION_OR_RESTRICTIONS_REQUIRE_SEPARATE_ADAPTER`
- 行为：额外自身处理单调性没有被忽略，也没有套用原区间；系统明确报告当前适配器未接入这个耦合限制。

这是如实停止，不是“已证明不可识别”。

## 6. 结论与边界

已完成：

- PARTIAL 和 sharp 区间；
- 单政策均值；
- 完整有限模型；
- 缺模型完整性时停止；
- 额外耦合限制不被静默忽略；
- 证书重放通过。

未完成：

- 老师复核；
- 第二个 PARTIAL 案例（两政策差值/均值顺序）；
- 扩到 12 个情境。

因此当前状态是：**PARTIAL 模板完成，等待老师复核。**
