# Task 06：D2 固定总名额 × E3 核心伙伴严格多数（POINT）

**Setting：** 公司在处理前固定的无向图 $G=(V,A)$（$|V|=N$）上实验，**恰好**向 $m$ 人开放 AI。与 shared baseline不同，本任务采用**均匀完全随机化（D2）**与**预先指定的核心伙伴** $\varnothing\neq C_i\subseteq\mathcal N(i)$（E3）。

令 $h_i=|C_i|$，$K_i(\mathbf u)=\sum_{j\in C_i}u_j$，$S_i(\mathbf u)=\mathbf1\{K_i(\mathbf u)>\lfloor h_i/2\rfloor\}$；恰好一半归入 $S_i=0$。已知分配律为

$$
\Omega_m=\{\mathbf u\in\{0,1\}^N:\sum_j u_j=m\},\qquad q(\mathbf u\mid W)=\frac{\mathbf1\{\mathbf u\in\Omega_m\}}{\binom Nm},\quad W=(A,X,C).
$$

**Target：** 对 $\mathcal U_{i,t,s}=\{\mathbf u\in\Omega_m:u_i=t,S_i(\mathbf u)=s\}$，令 $\pi_i(t,s)=\sum_{\mathbf u\in\mathcal U_{i,t,s}}q(\mathbf u\mid W)$。仅当 $\pi_i(t,s)>0$ 时，目标定义为

$$
\mu_i(t,s)=\sum_{\mathbf u\in\mathcal U_{i,t,s}}\frac{q(\mathbf u\mid W)}{\pi_i(t,s)}\mathbb E[Y_i(\mathbf u)\mid W].
$$

它按原实验设计平均组内的**完整处理分配**，不要求 $S_i$ 是结果机制的充分 exposure。

**Assumptions：** 

(1) $A,X,C$ 均在处理前固定，$C_i$ 非空且为邻居子集；

(2) 潜在结果相关条件一阶绝对矩有限；

(3) consistency：$Y_i^{obs}=Y_i(\mathbf T)$；

(4) full-vector randomization：$\mathbf T\perp\{Y_i(\mathbf u):i,\mathbf u\in\Omega_m\}\mid W$；

(5) 被查询 arm 的 $\pi_i(t,s)>0$。

**Support：** 条件于 $T_i=t$，余下 $N-1$ 人中还有 $m-t$ 个名额，且 $h_i$ 人属于核心伙伴。

因此 $K_i\mid T_i=t,W\sim\operatorname{Hypergeom}(N-1,h_i,m-t)$，从组合计数得

$$
\pi_i(t,s)=\frac{\displaystyle\sum_{k\in I_s}\binom{h_i}{k}\binom{N-1-h_i}{m-t-k}}{\binom Nm},\quad
I_0=\{0,\ldots,\lfloor h_i/2\rfloor\},\quad I_1=\{\lfloor h_i/2\rfloor+1,\ldots,h_i\}.
$$

无效组合数视作零。正支持**充要条件**为：

$$
\pi_i(t,0)>0\iff 0\le m-t\le N-1-\lceil h_i/2\rceil;\qquad
\pi_i(t,1)>0\iff \lfloor h_i/2\rfloor+1\le m-t\le N-1.
$$

**POINT：** 对每个正支持 arm，使用完整分配上的全期望公式，再由 consistency 与 full-vector randomization：

$$
\mathbb E[Y_i^{obs}\mid W,T_i=t,S_i=s]
=\sum_{\mathbf u\in\mathcal U_{i,t,s}}\frac{q(\mathbf u\mid W)}{\pi_i(t,s)}\mathbb E[Y_i(\mathbf u)\mid W]
=\mu_i(t,s).
$$

右侧由总体观测分布唯一确定，故该 arm **POINT**。$\pi_i(t,s)=0$ 时目标未定义，必须拒绝查询；关键假设未确认时返回 **UNSUPPORTED**，并不自动等于 PARTIAL。D2 下跨 arm 差值是**设计特定**因果对比，不等于固定其他人的处理不变时的纯直接效应。详细推导、$N=8,m=3,h_i=3$ 的 $(22,13,18,3)/56$ 算例及逐项枚举验证见 `demo.ipynb`、`test_rule.py`。
