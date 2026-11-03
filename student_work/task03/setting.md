# Task 03：D1 × E3

## 基本设定

每个节点 i 独立接受 treatment：

T_i ~ Bernoulli(p_i)，其中 0 < p_i < 1。

每个节点 i 在实验前有固定的核心合作伙伴集合 C_i，且 C_i 是邻居集合 N(i) 的子集。满足：

C_i ⊆ N(i)，|C_i| > 0，i 不属于 C_i。

令：

h_i = |C_i|

K_i^core(t) = sum(t_j)，其中 j 属于 C_i

曝光状态定义为：

S_i(t) = 1{K_i^core(t) > floor(h_i / 2)}

目标是四个 arm mean：

mu_i(t, s)，其中 t ∈ {0, 1}，s ∈ {0, 1}

## 1. 业务背景

公司随机向员工提供 AI 工具。不同员工获得 AI 的概率可以不同，但这些概率在实验前已经确定，员工之间独立抽签。员工的工作表现可能受到核心合作伙伴是否使用 AI 的影响。

## 2. Treatment assignment

T_i ~ Bernoulli(p_i)，其中 0 < p_i < 1。

示例中的概率为：

~~~json
"probabilities": [0.2, 0.4, 0.6, 0.8]
~~~

## 3. Exposure

员工 i 是否被曝光，只取决于核心合作伙伴中是否有严格多数接受 AI：

S_i(t) = 1{sum(t_j, j ∈ C_i) > floor(h_i / 2)}

示例中的核心合作伙伴集合为：

~~~json
"core_sets": [[1, 2], [0, 2], [0, 1, 3], [1, 2]]
~~~

根据 p_i 和 C_i，可以计算核心伙伴 treated 人数的 Poisson-binomial 分布，并得到：

- exposure_zero_probability：没有严格多数核心伙伴接受 AI 的概率；
- exposure_one_probability：有严格多数核心伙伴接受 AI 的概率。

## 4. Target 定义

mu_i(t, s) = E[Y_i((t, T_-i)) | S_i((t, T_-i)) = s, A, X]

其中：

- t：员工 i 自己是否接受 treatment；
- s：核心合作伙伴中是否有严格多数接受 treatment；
- T_-i：其他员工按照原来的 D1 随机化设计分配；
- 只对能够产生曝光状态 s 的分配取平均。

## 5. Assumptions

~~~python
"assumptions": {
    "fixed_pretreatment_network": True,
    "fixed_pretreatment_core_sets": True,
    "known_assignment_law": True,
    "full_vector_randomization": True,
    "consistency": True,
    "finite_conditional_first_moments": True,
}
~~~

- fixed_pretreatment_network：实验开始前，每个员工的 treatment 概率已经确定。
- fixed_pretreatment_core_sets：实验开始前，每个员工的核心合作伙伴集合已经确定。
- known_assignment_law：我们知道每个人的 p_i、员工之间是否独立，以及每种完整分配结果出现的概率。
- full_vector_randomization：给定实验前信息 A、X 后，完整 treatment 向量 T 与所有潜在结果独立，即 T 与 {Y_i(z)} 相互独立。
- consistency：员工实际观察到的结果，就是其实际接受的 treatment 所对应的潜在结果。
- finite_conditional_first_moments：潜在结果的条件平均值存在且有限，例如 E[|Y_i(z)| | A, X] < ∞。

## 6. 有 support 时的 POINT identification

记 z = (t, T_-i)，s_i(z) 表示分配 z 下员工 i 的曝光状态。

如果：

pi_i(t, s | A, X) = P(T_i = t, S_i = s | A, X) > 0

则：

mu_i(t, s)
= sum over all T_-i satisfying s_i(t, T_-i) = s of

  E[Y_i(t, T_-i) | A, X]
  × P(T_-i | T_i = t, S_i = s, A, X)

又因为：

P(T_-i | T_i = t, S_i = s, A, X)
= P(T = (t, T_-i) | A, X) / pi_i(t, s | A, X)

所以：

mu_i(t, s)
= E[Y_i^obs | A, X, T_i = t, S_i = s]

这里：

1. consistency 把观察结果对应到实际分配下的潜在结果；
2. full-vector randomization 保证 treatment 分配与潜在结果独立；
3. known_assignment_law 给出各种分配的概率和权重；
4. positive support 保证 T_i = t 且 S_i = s 的情况确实可能发生。

因为 pi_i(t, s | A, X) > 0，数据中会出现满足该条件的样本，所以：

mu_i(t, s) = E[Y_i^obs | A, X, T_i = t, S_i = s]

因此 mu_i(t, s) 是 POINT identified。

直观地说，只要某个 arm 不是不可能发生的，就能找到属于这个 arm 的样本并计算平均表现。

## 7. 没有 support 时无法识别

如果：

P(T_i = t, S_i = s | A, X) = 0

说明实验中永远不会出现这种 arm。即使样本量无限大，也找不到对应样本，因此无法计算该 arm 的平均结果，mu_i(t, s) 也无法被 POINT identify。
