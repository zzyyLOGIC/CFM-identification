# 原文摘录与边界：Chernozhukov, Hong & Tamer (2007)

> 这不是论文全文，只保留本案例核对所需的部分。
>
> 版本：Chernozhukov, V., Hong, H., and Tamer, E. (2007), Estimation and Confidence Regions for Parameter Sets in Econometric Models, Econometrica 75(5):1243–1284，用户提供的出版 PDF。
> 核对方式：全文提取为文本，下列摘录逐条以「去空白、并还原换行连字符」后的子串匹配核回原页；页码为期刊页码（= PDF 页 + 1242）。公式上下标在提取文本中有损坏，故涉及公式的句子只摘录公式外的文字部分，公式按式号引用。

## 1. 论文关注什么

论文给出一套统一写法：参数满足可检验约束当且仅当某个非负准则函数取到最小值，识别集合就是准则函数的零集或等值集；估计量与置信区域都取样本准则函数的等值集。第 1 节给动机与文献位置（pp. 1243–1246），第 2 节给问题定义、矩不等式与矩等式两类模型、四个例子和结果概览（pp. 1246–1252），第 3 节给一般估计与推断理论（一致性、收敛速率、退化性质、置信区域、次抽样、统计量渐近，pp. 1252–1261），第 4 节把条件逐条验到矩条件模型上，第 5 节处理区域内单个点的置信区域，结论在第 1270 页。

## 2. 与本题直接相关的结构

（1）识别集合 = 准则函数的零集。p. 1246：Q(θ) 非负，模型满足约束当且仅当 Q(θ) = 0，Θ_I = {θ ∈ Θ : Q(θ) = 0}，且一般多值。

（2）矩不等式与半空间。p. 1246 式 (2.1)：E_P[m_i(θ)] ≤ 0，Θ_I = {θ : E_P[m_i(θ)] ≤ 0}；矩函数对参数线性时，Θ_I 是若干线性半空间的交集，可能是三角形、梯形或多面体。

（3）矩等式的写法。p. 1247 式 (2.4)–(2.6)：E_P[m_i(θ)] = 0 时 Θ_I 是超平面与参数空间的交；准则函数取 GMM 形式，样本类似为 Q_n。

（4）例 1（p. 1248）：Y 不可观测，被 Y1 与 Y2 从下上夹住，θ = E[Y]，矩函数 m_i(θ) = (Y1i − θ, θ − Y2i)′，准则函数 Q(θ) = (E[Y1] − θ)²₊ + (θ − E[Y2])²₋，识别集合是区间 Θ_I = {θ : E[Y1] ≤ θ ≤ E[Y2]}；样本类似把期望换成样本均值即可。这个式子的两个拐点正好落在两个端点上。

（5）等值集与推断统计量。p. 1250 定义 C_n(c) := {θ ∈ Θ : a_n Q_n(θ) ≤ c}，p. 1253 式 (3.1) 定义 C_n = sup_{θ∈Θ_I} a_n Q_n(θ)、式 (3.2) 重述等值集；ĉ 的选取与临界值估计在 pp. 1256–1261。

本题只用到（1）—（4）：把每个门店在「自身=1、暴露=1」的均值看成 Θ_I 的一个坐标约束，试点揭示的两家给等式、档案覆盖的四家给双边夹逼，目标 θ 是六个坐标的等权线性组合，于是 Θ_I 是这组约束截出的线段，两个端点各由一条绑定约束决定。

## 3. 逐字摘录与页码

以下 17 处均以去空白、还原换行连字符后的子串匹配核回 PDF 对应页。

1. p. 1243（摘要）：This paper develops a framework for performing estimation and inference in econometric models with partial identification
2. p. 1243（摘要）：we provide estimators and confidence regions for the set of minimizers
3. p. 1243（摘要）：Interest therefore focuses on the set of minimizers, called the identified set.
4. p. 1243（摘要）：We use the inversion of the sample analog
5. p. 1244：We focus the analysis on moment condition models defined by either moment inequalities or moment equalities.
6. p. 1246：Suppose that we have a collection of empirical restrictions on economic models.
7. p. 1246：the set ΘI is given by an intersection of linear half-spaces
8. p. 1246：it could be a triangle, a trapezoid, or a polyhedron
9. p. 1246：The set ΘI can be characterized as the set of minimizers of the criterion function
10. p. 1247：Therefore, inference on ΘI may be based on the empirical analog of Q
11. p. 1247：This normalization is useful in cases where Qn does not attain the population value zero in finite samples.
12. p. 1248：The first example is motivated by missing data problems
13. p. 1248：bracketed below by Y1 and above by Y2
14. p. 1248：Hence the identified set is an interval
15. p. 1248：This example falls in the moment-inequality framework with moment function
16. p. 1250：The sets constructed take the form of a contour set of level c
17. p. 1253：The contour sets of anQn form the class of estimators considered here.

补充定位（未逐字摘录，只按式号与节号引用）：式 (2.1) p. 1246；式 (2.2)、(2.3) p. 1247；例 1 的矩函数 p. 1248；式 (3.1)、(3.2) p. 1253；第 3.3 节置信区域 p. 1256；第 3.4 节次抽样 p. 1257；第 3.5 节渐近 p. 1259；结论 p. 1270。

## 4. 本案例与论文的关系

- 借用：Θ_I 作为准则函数零集 / 矩约束集合的写法（pp. 1246–1247）；线性矩函数下 Θ_I 为半空间交的表述（p. 1246）；例 1 的区间数据结构（p. 1248）。
- 不借用：第 3 节的估计与推断机器——等值集的 ĉ 选取（p. 1250、p. 1256）、次抽样（p. 1257）、统计量 C_n 的渐近（p. 1259）、Hausdorff 距离下的收敛速率与退化性质（pp. 1251、1254）。本题是确定性有限总体模型，没有抽样噪声，这些内容没有对应物。
- 数值全部自建：论文没有经验数值；3/4、1/2、名额 2、链式网络、六家门店名单都是项目自建。
- sharp 性由项目有限模型的求解与证书重放单独检查，不引用论文当作证明。论文定义 Θ_I 时并未主张其 sharp，sharp 是本题有限模型相对于声明约束的全域可达性。

## 5. 没核对的内容

- 第 4 节把条件逐条验到矩条件模型的推导（约 pp. 1261–1269）只确认了存在与定位，未逐步复算；
- 第 5 节区域内单点置信区域未细读；
- 提取文本中公式上下标的损坏处未逐一对照原版式；
- 出版版与其他来源版本的差异。
