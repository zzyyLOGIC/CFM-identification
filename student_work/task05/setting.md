# Task05：固定总处理人数 × 低/中/高三档暴露

## 场景与目标

公司在处理前固定的合作网络上，从 N 名员工中均匀抽取恰好 m 人获得 AI，其他人不获得；
与独立 Bernoulli 基线不同，本人的处理与其他人的处理相关。令 A、X 为给定的完整处理前背景，
d_i 为邻居数，K_i 为被处理邻居数。E2 将 K_i/d_i 分为低（<1/3）、中（[1/3,2/3)）、高（>=2/3），
分别记为 s=0,1,2。恰好 1/3 属于中档，恰好 2/3 属于高档；d_i=0 时暴露未定义，报告不适用。
每个非孤立节点有六个候选 (t,s) 组合，但不保证全部有支持。

完整实验分配律与目标为：

$$q(u)=\frac{\mathbf 1\{\sum_j u_j=m\}}{\binom Nm},\qquad
\mathcal U_{i,t,s}=\{u:u_i=t,S_i(u)=s\},\qquad
\pi_i(t,s)=\sum_{u\in\mathcal U_{i,t,s}}q(u).$$

$$\mu_i(t,s)=\sum_{u\in\mathcal U_{i,t,s}}\frac{q(u)}{\pi_i(t,s)}
\mathbb E[Y_i(u)\mid A,X],\qquad \pi_i(t,s)>0.$$

这是按**完整分配律**在 arm 内标准化的目标；不能独立重抽 T_-i，也不能将联合支持写成
P(T_i=t)P(S_i=s)。E2 是查询分组，不要求 Y_i(u) 只由 (u_i,S_i(u)) 决定。
不同 arm 的差值是该设计下的对照，不自动等同于保持其他人处理不变的直接效应。

## 支持概率

固定 T_i=t 后，还需从其余 N-1 人中抽取 m-t 人。若 k 人在邻居集合中，则剩余
m-t-k 人必须在 N-1-d_i 个非邻居中。令

$$B_0(d)=\{k\in\mathbb Z:0\le k\le d,3k<d\},\quad
B_1(d)=\{k\in\mathbb Z:0\le k\le d,d\le3k<2d\},\quad
B_2(d)=\{k\in\mathbb Z:0\le k\le d,3k\ge2d\}.$$

$$\boxed{\pi_i(t,s)=\frac{1}{\binom Nm}
\sum_{k\in B_s(d_i)}\binom{d_i}{k}\binom{N-1-d_i}{m-t-k}}.$$

非法组合数视为零。等价的可行整数范围是
max(0,m-t-(N-1-d_i)) <= k <= min(d_i,m-t)。某个分档与该范围无交集时，支持为零。
当 P(T_i=t)>0 时，条件邻居计数服从 Hypergeometric(N-1,m-t,d_i)，但代码直接算联合概率，
因此 m=0 或 m=N 时也不需要除以零。`Fraction` 保留精确概率，避免将小正概率误判为零。
例如 N=6,m=2,d_i=3 时，按低、中、高排序：t=0 的概率为 (1,6,3)/15，t=1 为 (2,3,0)/15。

## 假设与 POINT 推导

要求：已知上述均匀分配律；处理前网络及背景固定；完整分配向量与全部潜在结果在 A,X 条件下独立；
consistency（Y_i^obs=Y_i(T)）；目标涉及的条件绝对一阶矩有限；所查询 arm 的支持为正。
这些是实验协议/领域声明，不能从有限样本中推断出来。完整向量随机化不要求各 T_j 相互独立。

由全期望、consistency 和完整向量随机化，对 q(u)>0 的完整分配逐项替换：

$$\begin{aligned}
\mathbb E[Y_i^{obs}\mid A,X,T_i=t,S_i=s]
&=\sum_{u\in\mathcal U_{i,t,s}:q(u)>0}\frac{q(u)}{\pi_i(t,s)}
\mathbb E[Y_i^{obs}\mid A,X,T=u]\\
&=\sum_{u\in\mathcal U_{i,t,s}:q(u)>0}\frac{q(u)}{\pi_i(t,s)}
\mathbb E[Y_i(u)\mid A,X]=\mu_i(t,s).
\end{aligned}$$

右端目标等于总体可观测条件均值，因此 POINT。若 pi=0，该条件均值和上述归一化目标在此定义下均不可用，
明确拒绝该 query；不是返回数值零，也不是自动报告 PARTIAL。
一次实验没有观察到某 arm 只是估计问题，不改变正的总体设计支持。

## 实现、运行与边界

- `support.py`：输入整数 0/1 对称无自环邻接矩阵与整数 0<=m<=N；返回每个节点六个精确概率。
  孤立节点返回 `None`，其余节点照常计算；节点编号为矩阵行号，不硬编码 N=300。
- `rule.py`：单查询入口 `identify(graph,m,node,t,s,assumptions=...)`。
  五个必要假设逐项显式声明；缺失/UNRESOLVED/PROPOSED 返回 NEEDS_INPUT，拒绝/矛盾状态停止规则。
- `demo.ipynb`：按业务问题、设定、支持、证明、识别结果展示，可 Run All；仅用标准库，不训练模型。
- `test_rule.py`：独立枚举合法完整分配并等权求和；覆盖所有 N<=4 的简单无向图和所有配额，
  以及 N=5..8 的完整图、路径、星形、环形和固定种子随机图，另测边界、非法输入、假设与 N=300。

**接口范围：**成果隔离在 `student_work/task05/`。`rule.IdentificationResult` 是本任务的本地结果类型，
不是 `pfn_pipeline.contracts.IdentificationResult`。现有 core 的 Bernoulli/二档 theorem、verifier 和下游
四臂 handoff 尚未注册本任务；因此本地结果明确保留 `verification_status="NOT_RUN"`、
`estimation_request=None`。POINT 表示上述数学规则的条件结论；主仓库 verifier 尚未接入此规则。
本任务不修改共享 contracts、Estimation 或 Policy，不读取 simulator outcome truth。

在仓库根目录运行（Python 3.10+）：

```bash
python -B -m unittest discover -s student_work/task05 -p "test_*.py" -v
python -B tools/run_student_tests.py
python -B -m unittest discover -s tests -p "test_identification_integration.py" -v
```

第一条仅需要标准库；第二条需要 pytest；第三条依赖仓库环境。Notebook 用 Python 3 内核 Run All，
从仓库根目录或 task05 目录均能找到模块。完整依赖见仓库 `requirements.txt`。
