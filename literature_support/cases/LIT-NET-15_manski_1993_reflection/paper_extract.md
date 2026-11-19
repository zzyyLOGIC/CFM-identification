# 原文摘录与边界：Manski (1993)

> 场景改编声明：*Review of Economic Studies* 1993 改编。本文件记录场景改编案例所依据的原文位置与边界。论文未提出本题；六名学生、甲乙两班的参照组划分、两套抽签辅导安排、直接效应 4 分与内生效应系数 0.5，以及「成绩相对不推行计划时的平均提高」这一目标均为项目自建，论文全文没有经验数值。下列摘录只用于说明借用了论文的哪几层结构，以及论文不支撑哪些外推。参照组划分进入目标：删去班级划分，班平均无从确定，题目不能计算。

## 1. 本案例实际用到的原文位置

- Abstract（p. 531）：反射问题的定义与「推断需要参照组构成的先验信息」。
- Section 1（pp. 531–532）：镜子比喻；论文主题句。
- Section 2 开头（pp. 532–533）：线性模型与三类效应（内生、情境、相关）的定义；高中生成绩例子。
- p. 533：辅导例子与社会乘数段——直接帮助、间接帮助、回馈；情境与相关效应无乘数。
- p. 534：式 (2) 内生效应含义；式 (3) 社会均衡方程；β≠1 时式 (3) 有唯一解即式 (4)；Proposition 1（三类效应相互不可区分）。
- p. 535：Proposition 1 推论（情境变量线性依赖于分组变量时不可识别）；Section 3 非线性模型的识别条件；「实证研究通常假设」段。
- p. 536：参照组构成的给定是分析社会效应的先决条件。
- p. 537：空间自回归模型——个体行为随样本中其他人行为的加权平均变动。
- p. 541：结论——改进识别要靠更紧的理论或更富的数据；实验与主观数据将扮演重要角色。
- 未逐句核对：第 4 节动态模型、第 5 节消费者需求、各命题的证明。

## 2. 案例目标

六名学生，两个参照组（班）：

```text
甲班：学1、学2、学3、学4，班内互为参照组（完全图，六对）
乙班：学5、学6，班内互为参照组（一对）
班间无参照关系
```

参照组构成是题面给定的先验信息（论文 p. 536 说的那条先决条件）。

两套辅导安排，各以 1/2 概率被采用：

- 方案 a：辅导学1、学2、学5（三个名额）；
- 方案 b：辅导学3、学6（两个名额）。

成绩规则。设 d(i) 为学生 i 是否受辅导、C(i) 为其所在班、m(C) 为该班最终班平均提高，则：

\[
g_i = 4\, d(i) + 0.5\, m(C(i)),
\]

且班平均提高满足均衡条件：

\[
m(C) = \frac{4\, S_C + 0.5\, m(C)\, n_C}{n_C}
\iff
m(C) = \frac{4\, S_C}{n_C (1 - 0.5)} = \frac{2\, S_C}{n_C}\times 4,
\]

其中 S_C 为班内受辅导人数、n_C 为班人数。这就是论文式 (3) 社会均衡方程（p. 534）在两班上的代入，式 (4) 是它的唯一解（β=0.5≠1）。

目标：

\[
\frac{1}{6}\sum_{i=1}^{6}\left[\frac{1}{2}g_i(a)+\frac{1}{2}g_i(b)\right].
\]

这是有限随机政策下成绩相对不推行计划时的平均提高（单位：分），不是论文的识别区间，也不是任何估计量。

逐班逐人结果。方案 a：甲班 S=2、n=4，班平均提高 4·2/(4×0.5)=4；学1 = 4+0.5×4 = 6，学2 = 6，学3 = 0.5×4 = 2，学4 = 2，合计 16。乙班 S=1、n=2，班平均提高 4×1/(2×0.5)=4；学5 = 6，学6 = 2，合计 8。全体合计 24，平均 4。方案 b：甲班 S=1，班平均提高 2；学3 = 4+1 = 5，学1、学2、学4 各 1，合计 8。乙班 S=1，班平均提高 4；学6 = 6，学5 = 2，合计 8。全体合计 16，平均 8/3。目标值 \(\frac12(4+\frac83) = \frac{10}3\)，即 3.333…。

结构检验：每班合计恒等于该班直接效应合计的 1/(1−0.5)=2 倍（甲班 a：2×8=16；乙班 a：2×4=8；甲班 b：2×4=8；乙班 b：2×4=8），与班人数无关，这是线性均衡的直接推论。

目标变化版只评甲班学3 一人，权重 1：方案 a 得 2（纯溢出），方案 b 得 5（4 分直接加 1 分溢出）；目标值 \(\frac12(2+5)=\frac72\)，即 3.5。

## 3. 论文不支撑

- 不支撑把 0.5 与 4 读成论文的数：论文全文没有经验数值，两个参数自建，只受 β≠1 的均衡唯一性约束（p. 534）；
- 不支撑把本题当作识别结论的演示：论文的结论是观测数据下内生、情境、相关效应相互分不开（Proposition 1, p. 534），本题规则全部已知，是政策计算，不从数据反推参数；
- 不支撑把抽签安排当作论文的设计：辅导在论文里是设想的政策例子（p. 533），没有名额分配与抽签，两套安排自建；
- 不支撑加入情境效应或相关效应：论文证明它们与内生效应观测上分不开（p. 534），本题按论文 2.3 节的简化只保留内生效应（p. 535），加了情境效应的全班总额仍只由名额总数决定，但题目含义会变；
- 不支撑把六名学生当作论文样本：论文没有数据，名单与划分全部自建。

## 3.5 实际摘录

Abstract（p. 531）：

> “This paper examines the reflection problem that arises when a researcher observing the distribution of behaviour in a population tries to infer whether the average behaviour in some group influences the behaviour of the individuals that comprise the group”

Section 1（p. 532，镜子比喻）：

> “The term reflection is appropriate because the problem is similar to that of interpreting the almost simultaneous movements of a person and his reflection in a mirror.”

Section 2（p. 533，内生效应定义）：

> “There is an endogenous effect if, all else equal, individual achievement tends to vary with the average achievement of the students in the youth's school, ethnic group, or other reference group.”

Section 2（p. 533，成绩例子）：

> “An example may help to clarify the distinction. Consider the high school achievement of a teenage youth.”

Section 2（p. 533，辅导例子）：

> “Consider, for example, an educational intervention providing tutoring to some of the students in a school but not to the others.”

Section 2（p. 533，社会乘数）：

> “an effective tutoring programme not only directly helps the tutored students but, as their achievement rises, indirectly helps all students in the school, with a feedback to further achievement gains by the tutored students”

Section 2（p. 533，另两类效应无乘数）：

> “Exogenous effects and correlated effects do not generate this”

p. 534（均衡方程的来路）：

> “The reflection problem arises out of the presence of E (y Ix) as a regressor in (2).”

p. 534（社会均衡方程）：

> “solves the "social equilibrium" equation”

p. 534（均衡唯一性）：

> “equation (3) has a unique solution, namely”

p. 534（Proposition 1）：

> “Endogenous effects cannot be distinguished from exogenous effects or from correlated effects.”

p. 535（实证惯例）：

> “Empirical studies of endogenous effects typically assume that”

p. 535（非线性模型的识别条件）：

> “inference is possible only if E (z Ix) varies non-linearly with x and Var (z Ix) > o.”

p. 536（参照组先决条件）：

> “informed specification of reference groups is a necessary prelude to analysis of social effects.”

p. 537（空间自回归形式）：

> “the behaviour of each person in the sample varies with a weighted average of the behaviours of the other sample members”

p. 541（结论之一）：

> “The only ways to improve the prospects for identification are to develop tighter theory or to collect richer data.”

p. 541（结论之二）：

> “experimental and subjective data will have to play an important role in future efforts to learn about social effects.”

说明一：PDF 提取文本在断词处会留下空格，数学符号有损坏（β 印作 f3、≠ 印作 :¢: 等），弯引号保留为 ’、下标保留为 E(y Ix) 形式；本文件按语义还原空格与符号，未改动词序与数字；上述引文均以去空白后的子串匹配核回原文，页码按 PDF 第 n 页为期刊第 530+n 页换算。含损坏符号的句子（如式 (2)、(3)、(4) 本体）不逐字摘录，改在本文第 2 节用自建记号复述并标注式号。

说明二：本题与论文数值的关系。论文没有任何数值，本题的 β=0.5 与直接效应 4 分是自建参数；β≠1 取自均衡唯一性的条件（p. 534），0.5 使乘数恰为 2、手算干净，4 分使逐人结果为整数。两个参数与论文的关系是「结构来自式 (3)、(4)，数值自建」，来源卡与参考文件均写明，不可把数值说成论文的。

说明三：论文的均衡式 (4) 是总体均值回归的解，本题把同一结构用在两个有限班级上：班平均提高由班内直接效应合计与人数决定，个体提高 = 直接 + 0.5×班平均提高。这是对论文机制的有限总体代入，不是论文的定理内容本身。

本案例只借用「均衡结构、乘数机制、参照组先验给定」三层结构的业务含义，不复制论文的识别推导、非线性与动态模型，也不把自建数值说成论文的结果。

## 4. 阅读级别

`selected_full_text_sections`。已核对正式版 PDF 的 Abstract、Section 1、Section 2 模型与例子、p. 534 均衡方程与 Proposition 1、p. 535 推论与非线性条件、p. 536 参照组段、p. 537 空间自回归段与 p. 541 结论；第 4、5 节与各证明未逐句核验。
