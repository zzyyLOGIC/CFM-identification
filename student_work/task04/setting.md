# Task 04: D2 × E1

## 1. Business Scenario（业务场景）

公司向一批销售员开放 AI
助手。销售员共享客户线索，因此员工绩效可能同时受到本人是否使用
AI，以及合作同事使用 AI 情况的影响。

设共有 $N$ 名员工，处理前合作网络为 $G=(V,A)$，其中 $V=[N]$。$N(i)$
表示员工 $i$ 的邻居集合，$d_i=|N(i)|$。

对于完整分配 $\mathbf u$，$Y_i(\mathbf u)$ 表示员工 $i$
在该分配下的潜在结果；实际观察结果定义为：

$$Y_i^{obs}=Y_i(\mathbf T).$$

## 与 Shared Baseline Setting 的区别

传统的 Shared Baseline Setting 假设个体结果只受到自身 treatment 的影响：

$$
Y_i(T_i)
$$

即员工 i 的结果只取决于自己是否接受 AI training。

但在本项目中，考虑员工之间存在合作网络，因此存在 network interference。

员工 i 的结果可能同时受到自身 treatment 以及合作邻居 treatment 状态的影响：

$$
Y_i(\mathbf T)
$$

其中：

- $T_i$ 表示员工 i 自身是否接受 AI training；
- $\mathbf T$ 表示所有员工的 treatment assignment。

因此，本项目引入 exposure mapping：

$$
S_i(\mathbf T)
$$

用于描述合作网络中其他员工的影响。

## 3. Assignment Design（D2）

令 $\mathbf T=(T_1,...,T_N)$，其中 $T_i=1$ 表示员工获得 AI。

D2 为固定人数随机分配：

$$\sum_iT_i=m.$$

完整分配概率：

$$
q(\mathbf u)=P(\mathbf T=\mathbf u|A,X)
=
\begin{cases}
\binom Nm^{-1},&\sum_j u_j=m,\\
0,&\text{otherwise}.
\end{cases}
$$

## 4. Exposure Mapping（E1）

定义：

$$K_i(\mathbf u)=\sum_{j\in N(i)}u_j.$$

严格多数暴露：

$$
S_i(\mathbf u)=
\mathbf1\{K_i(\mathbf u)>\lfloor d_i/2\rfloor\}.
$$

因此 arm 为：

$$(T_i,S_i(\mathbf T))\in\{(0,0),(0,1),(1,0),(1,1)\}.$$

## 5. Target Causal Quantity

定义：

$$
\mathcal U_{i,t,s}=\{\mathbf u:u_i=t,S_i(\mathbf u)=s\}.
$$

并令：

$$
\pi_i(t,s)=\sum_{\mathbf u\in\mathcal U_{i,t,s}}q(\mathbf u).
$$

当 $\pi_i(t,s)>0$ 时：

$$
\mu_i(t,s)=
\sum_{\mathbf u\in\mathcal U_{i,t,s}}
\frac{q(\mathbf u)}{\pi_i(t,s)}
E[Y_i(\mathbf u)|A,X].
$$

## 6. Assumptions

1.  处理前网络 $A$ 与协变量 $X$ 固定。

2.  Consistency:

$$Y_i^{obs}=Y_i(\mathbf u),\quad \mathbf T=\mathbf u.$$

3.  Full-vector randomization:

$$
\mathbf T\perp\{Y_i(\mathbf u)\}|A,X.
$$

该假设来自随机分配机制，不要求不同员工的 $T_i$ 相互独立。

4.  Positive support:

只讨论 $\pi_i(t,s)>0$ 的 arm。

## 7. Support

令：

$$h_i=\lfloor d_i/2\rfloor.$$

给定 $T_i=t$，邻居中接受 AI 人数 $k$ 满足：

$$
L_t=\max\{0,m-t-(N-1-d_i)\},
$$

$$
U_t=\min\{d_i,m-t\}.
$$

联合概率：

$$
\pi_i(t,s)=
\frac1{\binom Nm}
\sum_{k=L_t}^{U_t}
\mathbf1\{\mathbf1(k>h_i)=s\}
\binom{d_i}{k}
\binom{N-1-d_i}{m-t-k}.
$$

若存在满足 exposure 条件的合法 $k$，则该 arm 有 support。
### Support 为 0 的情况

某些 joint arm 在当前 assignment design 下可能无法出现，因此：

$$
\pi_i(t,s)=0
$$

例如：

$$
m=1
$$

表示只有一个员工接受 AI training。

若研究员工 i，并且：

$$
T_i=1
$$

则唯一的 treatment 名额已经被员工 i 使用。

此时：

$$
K_i(\mathbf T)=0
$$

无法满足 strict majority exposure：

$$
K_i(\mathbf T)>\lfloor d_i/2\rfloor
$$

因此：

$$
\pi_i(1,1)=0
$$

说明该 joint arm 在当前实验设计下不存在。

## 8. POINT Identification

### 当 $\pi_i(t,s)>0$：

$$
\begin{aligned}
E[Y_i^{obs}|A,X,T_i=t,S_i=s]
&=
\sum_{\mathbf u\in\mathcal U_{i,t,s}}
\frac{q(\mathbf u)}{\pi_i(t,s)}
E[Y_i^{obs}|A,X,\mathbf T=\mathbf u]\\
&=
\sum_{\mathbf u\in\mathcal U_{i,t,s}}
\frac{q(\mathbf u)}{\pi_i(t,s)}
E[Y_i(\mathbf u)|A,X]\\
&=\mu_i(t,s).
\end{aligned}
$$
上述识别过程依赖三个关键条件：

1. Randomization：

保证 treatment assignment 与潜在结果独立。

2. Consistency：

保证观测结果等于实际 assignment 下对应的潜在结果。

3. Positive support：

保证目标 joint arm：

$$
(T_i=t,S_i=s)
$$

在实验设计中具有正概率。

因此：

$$
\pi_i(t,s)>0
$$

时，条件期望：

$$
E[Y_i^{obs}|A,X,T_i=t,S_i=s]
$$

可以由观测数据唯一确定，因此 causal query 达到 POINT identification。


### 当 $\pi_i(t,s)=0$：

不能继续使用上述条件期望形式。

原因是：

$$
(T_i=t,S_i=s)
$$

这一事件在当前 assignment mechanism 下不会发生。

因此：

$$
P(T_i=t,S_i=s)=0
$$

对应的条件分布：

$$
E[Y_i^{obs}|A,X,T_i=t,S_i=s]
$$

不存在。

因此不能通过观测数据恢复该 causal quantity，
该 arm 不是 POINT identified。
