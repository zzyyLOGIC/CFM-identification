# CFM-identification · Student Task 06

**D2 固定恰好 m 人被处理 × E3 核心合作伙伴严格多数。** 不修改仓库共用 `pfn_pipeline`、Estimation 或 Policy。理论定义参见 `setting.md`。

## 文件与接口

- `setting.md`：setting、target、assumptions、support 公式及 POINT 证明。
- `support.py`：通过 `Task06Setting.create(adjacency, core_partners, m)` 校验固定无向图和预先指定的各节点核心伙伴；`support_probabilities(adjacency, core_partners, m)` 返回 `{node: {(t,s): Fraction}}`；`positive_support_from_bounds` 给出独立可行性判定。
- `rule.py`：`identify_arm(setting, node, treatment, exposure, assumptions=...)` 输出本地 `IdentificationResult`（POINT / UNSUPPORTED、支持概率、可观测泛函、原因码）；`identify_all` 一次检查全部节点及四个 arm。
- `demo.ipynb`：按**业务问题 → setting → support → POINT 推导 → IdentificationResult** 展示，再执行穷举验证、异常条件演示。
- `test_rule.py`：正常情况、零支持、非法参数、假设门禁、边界名额、N≤8 合法完整处理向量穷举对拍、N=300 规模独立性。


## 运行

仓库根目录（：

```bash
python -B -m pytest -q student_work/task06/test_rule.py
python -B tools/run_student_tests.py
```

本文件夹目录下：

```bash
jupyter notebook demo.ipynb
```


## 设计原则与边界

1. 仅使用 Python 标准库计算全部支持概率：组合数 + `fractions.Fraction`，不枚举 N=300 的全部 `2^N` 个向量。
2. 只有测试中的独立 oracle 才穷举 N≤8 的**合法**固定名额向量；模拟结果与 outcome truth 不参与识别。
3. 正支持返回 POINT 泛函，不返回任何数值因果效应；零支持和未确认假设均拒绝，且不被误标为 PARTIAL。
4. 要求每个 $C_i$ 非空、包含于节点的处理前邻居集合；孤立节点不能满足 E3，需要更改研究设定，不能悄悄给它一个 $S_i=0$。

## 验收要求与结果

### 1. Task 06 与 shared baseline 有什么不同？

| 维度 | Shared baseline | Task 06（D2 + E3） |
| --- | --- | --- |
| Assignment | $T_i\overset{iid}{\sim}\operatorname{Bernoulli}(1/2)$，各人独立 | 从 $N$ 人中均匀选取**恰好 $m$ 人**，$\sum_i T_i=m$，个体处理状态通常相关 |
| Exposure | 依据所有合作邻居 $\mathcal N(i)$ 是否严格过半被处理 | 仅依据**处理前指定**的核心伙伴 $C_i\subseteq\mathcal N(i)$ 是否严格过半被处理 |
| 随机变量分布 | 邻居 treated 数服从二项分布 | 给定本人处理状态后，核心伙伴 treated 数服从超几何分布 |
| Target | 按已知 assignment law 标准化的 arm mean | 仍是设计标准化 arm mean；不额外假设 exposure mapping 是潜在结果的充分表示 |

Task 06 的合法完整分配空间为 $\Omega_m=\{\mathbf u\in\{0,1\}^N:\sum_j u_j=m\}$，每个合法分配的概率 $q(\mathbf u)=1/\binom Nm$。

### 2. $\pi_i(t,s)$ 如何得到？哪些状态可能为零？

令 $h_i=|C_i|>0$、$K_i=\sum_{j\in C_i}T_j$，并定义 $S_i=\mathbf 1\{K_i>\lfloor h_i/2\rfloor\}$。固定 $T_i=t$ 后，其他 $N-1$ 人中还需选取 $m-t$ 人，其中核心伙伴有 $h_i$ 人、其他人有 $N-1-h_i$ 人。因此：

$$
P(T_i=t,K_i=k)=\frac{\binom{h_i}{k}\binom{N-1-h_i}{m-t-k}}{\binom Nm},
$$

$$
\pi_i(t,s)=\frac{1}{\binom Nm}\sum_{k\in I_s}\binom{h_i}{k}\binom{N-1-h_i}{m-t-k},
$$

其中 $I_0=\{0,\ldots,\lfloor h_i/2\rfloor\}$，$I_1=\{\lfloor h_i/2\rfloor+1,\ldots,h_i\}$；越界的组合数记为 0。由可行整数范围 $\max(0,m-t-(N-1-h_i))\le k\le\min(h_i,m-t)$ 可得**充要条件**：

$$
\begin{aligned}
\pi_i(t,0)>0&\iff 0\le m-t\le N-1-\lceil h_i/2\rceil,\\
\pi_i(t,1)>0&\iff \lfloor h_i/2\rfloor+1\le m-t\le N-1.
\end{aligned}
$$

例如 $N=6,m=2,h_i=3$ 时，若本人已获得 AI，则其他人只剩一个名额，不可能让三名核心伙伴中至少两人获得 AI，故 $\pi_i(1,1)=0$。`positive_support_from_bounds()` 检查上述范围，`joint_arm_probability()` 计算精确概率。

### 3. 为什么 Randomization + Consistency + Positive Support 可以得到 POINT？

在网络、特征与核心伙伴集合均于处理前确定，相关潜在结果一阶矩有限，已知完整分配律，满足 **Consistency**（$Y_i^{obs}=Y_i(\mathbf T)$）、**Full-vector randomization**（$\mathbf T\perp\{Y_i(\mathbf u)\}_{i,\mathbf u}\mid A,X,C$）且 $\pi_i(t,s)>0$ 的前提下，目标定义为：

$$
\mu_i(t,s)=\sum_{\mathbf u\in\mathcal U_{i,t,s}}\frac{q(\mathbf u)}{\pi_i(t,s)}E[Y_i(\mathbf u)\mid A,X,C],
$$

其中 $\mathcal U_{i,t,s}=\{\mathbf u\in\Omega_m:u_i=t,S_i(\mathbf u)=s\}$。利用全期望公式、Consistency 与随机化依次替换，得到：

$$
\mu_i(t,s)=E[Y_i^{obs}\mid A,X,C,T_i=t,S_i=s].
$$

右侧由总体观测分布唯一确定，故对**具有正支持且必要假设已确认**的 arm 为 POINT。`rule.py` 并非自行发现或重新证明识别定理，而是检查其适用前提，并返回该 POINT functional；它不估计 $\mu_i(t,s)$ 的数值。D2 下跨 arm 差值须解释为**设计特定的因果对比**，一般不能视为保持其他所有人处理状态不变的纯直接效应。

### 4. 若某个 arm 的 support = 0，为什么不能继续套用识别公式？

当 $\pi_i(t,s)=0$ 时，该 arm 在实验设计中不可能出现：标准化权重 $q(\mathbf u)/\pi_i(t,s)$ 无定义，对应的零概率条件事件上的观测均值也不能由总体观测分布确定。因此当前任务定义下必须**拒绝该查询**。`rule.py` 返回 `status="UNSUPPORTED"`、`reason_code="ZERO_POPULATION_SUPPORT"`，不会伪造 POINT functional，也不会擅自改判 PARTIAL。有限样本中没有观测到某 arm 与 **population support 为零**不是一回事。

### 5. 小图 brute-force 是否与解析公式 / 算法一致？

**一致。** 以 $N=8,m=3,h_i=3$ 为例，穷举 $\binom83=56$ 种等概率的**合法**完整处理分配，对每种分配逐节点计算 $(T_i,S_i)$ 并计数，结果为：

| Arm $(t,s)$ | 枚举计数 | Brute-force 概率 | `support.py` 精确结果 |
| --- | ---: | ---: | ---: |
| $(0,0)$ | 22 | $22/56$ | $22/56$ |
| $(0,1)$ | 13 | $13/56$ | $13/56$ |
| $(1,0)$ | 18 | $18/56$ | $18/56$ |
| $(1,1)$ | 3 | $3/56$ | $3/56$ |

四项和为 1，且 $\pi_i(1,0)+\pi_i(1,1)=m/N=3/8$。


