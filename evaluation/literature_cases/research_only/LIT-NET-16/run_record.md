# LIT-NET-16 运行记录

## 1. 运行环境

- 工作副本：`d:\因果推断项目\cfm-branch`
- 分支：`New-Task`
- 代码版本：`708a22cc4a49a1c18a6620d1bfeaa8e59406f5fd`
- Python：`D:\python\python.exe`
- `api_calls = 0`

## 2. 运行命令

```powershell
D:\python\python.exe -m evaluation.literature_cases.tools.run_lit_net_16 --variant all --reference-fixture --output <新目录>
```

性质：

- 走现有 bounded-policy 有限均值入口（与老师 LIT-NET-03、04 同一家族）；
- 显式合成审核；
- 不调用 LLM；
- 不是 Imbens & Manski (2004) 的实证复现；
- 公开侧 33 份文件由 `--write-public` 从 runner 的同一套文档函数生成，保证题面与运行输入逐字一致。

## 3. 原题运行结果

- 状态：`PARTIAL`
- 区间：`["1/6", "5/6"]`
- 宽度：`2/3`
- sharp：`true`
- 独立重放：通过
- 目标 SHA256：`7b5f6c392aa7783df0736ca79cfa94acb39ac696a8939a7accc173f2e1d8a93c`
- 证书：`FINITE_SIGNATURE_MEAN_BOX`，status PARTIAL

结构：

- 六个团队等权 `1/6`，目标政策为全启用（政策向量 `[1,1,1,1,1,1]`）；
- 团队1、团队6 在「自身处理=1、同伴暴露=1」时均值 `1/2`；
- 团队2–5 的同一格子均值只知在 `[0,1]`（该情形在名额 2 下概率为零：需要自己加两个邻居共 3 个名额）。

下界：

```text
(2 × 1/2 + 0) / 6 = 1/6
```

上界：

```text
(2 × 1/2 + 1) / 6 = 5/6
```

与论文公式的对应：µ = 1/2，p = 2/6 = 1/3，识别区域 [µ·p, µ·p + (1−p)] = [1/6, 1/6 + 2/3] = [1/6, 5/6]。宽度恰为 1 − p = 2/3，与论文第 3 节（p. 1847）逐符号同构。

## 4. 缺条件版运行结果

- 状态：`NEEDS_INPUT`
- 原因：`BOUNDED_MODEL_DECLARATIONS_INCOMPLETE`
- 行为：删除完整模型声明后，系统没有继续给区间，也没有生成证书。

## 5. 目标变化版：只评试点揭示的两个端点

- 只评价团队1、团队6，各 1/2，目标政策不变（全启用）。
- 状态：`POINT`
- 区间：`["1/2", "1/2"]`
- 宽度：`0`
- sharp：`true`
- 独立重放：通过
- 目标 SHA256：`e110bb6a66266b8183014de2f90d246b8796c30b35f40b39ae3cc44d6bf168c2`

含义：两个端点在目标格子的均值都已知，目标坍缩成点识别。这是论文第 3 节 µ 与 θ 的对照——被观测子群的均值 µ 点识别，加进缺失人群后的总体均值 θ 只能定到 [µ·p, µ·p + (1−p)]。

## 6. 参考答案复核

- 下界 `(2×1/2+0)/6 = 1/6`：分数精确；
- 上界 `(2×1/2+1)/6 = 5/6`：分数精确；
- 宽度 `4/6 = 2/3 = 1 − p`：与论文公式一致；
- 两端可达：四个内部团队的均值可独立取到 0 与 1（完整有限均值模型、无额外耦合限制），引擎报 sharp=true；
- `numeric_value` 为空是框架统一行为：PARTIAL/POINT 表示识别出泛函，数值由上述手算复核与独立重放核对。

## 7. 设计与框架的两处要点

- 框架相容性规则：目标情形在分配律下概率为正就必须给出该情形的精确均值；概率为零的格子才允许落在逐对象界限里。本题的缺失因此是设计性的（名额 2 永远点不亮内部团队的满暴露情形），与论文的随机缺失在机制上不同、在识别区域的数学结构上同构。这条已写进来源卡第 4 节与 review_teacher.md。
- 顺序/规则类文本信息（谁是端点、暴露怎么算）进不了 fact 层的结构化字段之外的部分：识别层核到的是链式边表、名额 2、两个签名格子与逐对象界限；「内部团队该情形概率为零」由引擎从边表与名额自行推出（A4_CONDITIONAL_EVENT_HAS_ZERO_PROBABILITY 的对偶面），不依赖题面文字。

## 8. 运行输出

- `structured_runs/original/`、`structured_runs/missing_condition/`、`structured_runs/changed_target/`：各含 result.json（读题与计划的中间文件不随仓库交付，重跑即可再生成）；
- `structured_runs/SUMMARY.json`：三行汇总，evidence_kind 为 HAND_AUTHORED_REFERENCE_FIXTURE。

## 9. 真实 LLM 读题（2026-11-18）

`deepseek-chat` 按有限政策读题合同读同一套材料，三个变体各一次请求。原题 `PARTIAL`、区间 `[1/6, 5/6]`，缺条件版 `NEEDS_INPUT`（`BOUNDED_MODEL_DECLARATIONS_INCOMPLETE`），目标变化版 `POINT`、区间 `[1/2, 1/2]`，与上面的结构化运行逐项一致。确认门比对的是两套名额安排与权重、逐格子的均值档案、以及目标所用的端点，没有出现矛盾。

本轮记录见 `actual_outputs.json`（三个变体各一份，2026-11-18 20:15 全量重跑）；20:15 之前的记录、13 号题面修订前与 14 号修订前的 33 份只在本地留档，不随仓库交付。
