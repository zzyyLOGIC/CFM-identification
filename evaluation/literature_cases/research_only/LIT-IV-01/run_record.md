# LIT-IV-01 运行记录

## 1. 运行环境

- 工作副本：学生本地开发副本（个人路径不公开）
- 分支：`task2-literature-cases`
- 代码版本：`992fdf9598b1b18a16aaa5887490174f6b6e5868`
- Python：3.13（`.venv`）
- `api_calls = 0`

## 2. 系统能力检查

命令：

```powershell
.venv\Scripts\python -c "from cfm_id.research_route_catalog import inventory; ..."
```

结果：

```text
route_id = IV
status = NO_REGISTERED_CONTRACT_IN_THIS_ENTRY
callable_here = false
```

当前已登记的可调用路线只有：

```text
DAG_CLASSICAL_BACKDOOR
DAG_ADJUSTMENT
MEAN_ORDER_D2_E1
DAG_CLASSICAL_FRONTDOOR
```

因此：

- 没有 IV 读取入口；
- 没有 IV 数学后端；
- 不能把本案例转交给网络或 DAG 方法；
- 系统状态应记为 `UNSUPPORTED`，不是 `POINT`，也不是 `PARTIAL`。

完整输出见 `capability_check.json`。

## 3. 为什么没有实际业务运行

本案例没有可用的 IV 读取器和 IV 求解器，所以没有伪造一次“运行”。

明确记录：

```text
status = UNSUPPORTED
reason = 当前仓库没有登记 IV 合同/读取器/数学后端
```

这符合任务 2 的要求：

> 论文能识别，但我们的 IV 尚未实现时，可以同时记录“论文给出公式”和“软件当前未支持”。

`UNSUPPORTED` 不等于“论文不可识别”，也不等于“已经证明不可识别”。

## 4. 论文参考的手工核对

公开计数表：

| Z | D | Y | count |
|---|---|---|---:|
| 0 | 1 | 1 | 8 |
| 0 | 1 | 0 | 12 |
| 0 | 0 | 1 | 16 |
| 0 | 0 | 0 | 64 |
| 1 | 1 | 1 | 20 |
| 1 | 1 | 0 | 20 |
| 1 | 0 | 1 | 18 |
| 1 | 0 | 0 | 42 |

计算：

```text
E[Y|Z=1] = 38/100 = 0.38
E[Y|Z=0] = 24/100 = 0.24
E[D|Z=1] = 40/100 = 0.40
E[D|Z=0] = 20/100 = 0.20
```

所以样本 analog：

```text
LATE_hat = (0.38 - 0.24) / (0.40 - 0.20)
         = 0.14 / 0.20
         = 0.70
```

这是**样本 analog**，用来核对公式和分母方向，不是论文数据，也不是总体 LATE。

## 5. 三个版本的预期

| 版本 | 论文参考 | 软件预期 |
|---|---|---|
| 原题 | Condition 1 + 2 下 LATE 可识别，公式给出 0.70 的样本 analog | `UNSUPPORTED` |
| 缺条件版 | 没有单调性，LATE 不识别；IV 比值不能解释为遵从者效应 | `UNSUPPORTED` |
| 目标变化版 | 论文识别 LATE，不识别全体 ATE | `UNSUPPORTED` |

## 6. 当前结论与边界

已完成：

- 来源卡、原文摘录和 LATE 公式核对；
- 公开业务材料三版；
- 手工计算样本 analog；
- 系统能力检查；
- 论文参考与软件预期分开。

未完成：

- 老师复核；
- 任务 4 的 IV 数学后端（不属于任务 2）；
- ATE 界限（Balke–Pearl 1997，另做 LIT-IV-02）。

因此当前状态是：**IV 模板的论文参考和“未支持”运行记录完成，等待老师复核。**
