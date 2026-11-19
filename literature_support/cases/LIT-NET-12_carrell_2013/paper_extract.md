# 原文摘录与边界：Carrell, Sacerdote & West (2013)

> 场景改编声明：本文件记录场景改编案例所依据的原文位置与边界。论文未提出本题；八名学生、两个已排好的学习组及其相邻关系、两套带学人安排与平均 GPA 变化这一目标均为项目自建。下列摘录只用于说明借用了论文的哪两层机制，以及论文不支撑哪些外推。网络进入目标：删去相邻关系后「相邻」无法确定，题目不能计算。

## 1. 本案例实际用到的原文位置

- Abstract（p. 855）：把一半新生排进「最优化」同伴组、预期帮到低能力同学、实测为负、学生在组内重新抱团。
- Introduction（pp. 855–857）：预测 +0.053 与实测 −0.061、+0.082 的对比，内生同伴组形成作为政策失效的机制，高能力同学不受影响。
- Section 1（pp. 857–861）：USAFA 数据、GPA 的可比性、Table I 与 Table II 的非线性同伴效应估计（低能力同学的 SAT-V 同伴系数 0.464，p. 865 引 Table II 第 3 列）。
- Section 2（pp. 862–870）：20 个对照中队与 20 个处理中队、式 (3) 的整数规划、双峰组与同质组的界定（p. 865）、Table IV 的预测效应（p. 868）。
- Section 3（p. 871）：Table VI 的实测效应，−0.061、+0.082、−0.012。
- Section 4 与 Table VIII（pp. 874–879）：学习伙伴与朋友的选择证据，抱团与同质性，高 SAT-V 学习伙伴少 3.9 个百分点。
- Section 5（pp. 880–881）：结论与对「最优政策」的保留。
- 未逐页核对：Section 1.2 的式 (1) 与式 (2) 推导、补充材料表 A.X、Figure 1 至 Figure 5 的完整读数。

## 2. 案例目标

两组合计八名新生：

```text
甲组：1 号 ── 2 号        乙组：7 号 ── 5 号 ── 6 号 ── 8 号
      │  ╲  │
      │   ╲ │
     3 号 ── 4 号
```

甲组四人两两相连，共六条边；乙组四人为链，共三条边。无其他边，无自环。能力：1 号、2 号、5 号、6 号高表达能力；3 号、4 号低能力；7 号、8 号中等。

同组同学每天一起自习，但实际来往的只是其中相邻的几个，带学人只对相邻的同学起作用。

两套完整安排，各 1/2 概率：

- 方案 a：每组一名带学人，甲组 1 号、乙组 5 号；
- 方案 b：每组两名带学人，甲组 1 号与 2 号、乙组 5 号与 6 号。

判定规则，其中 \(N(i)\) 为与 \(i\) 相邻的同学集合，\(m_i(s)=\sum_{j\in N(i)}s_j\) 为 \(i\) 相邻的带学人人数：

\[
g_i(s)=
\begin{cases}
0, & i\ \text{高表达能力（含带学人）},\\[2pt]
0.053\cdot\mathbf{1}\{m_i(s)=1\}-0.061\cdot\mathbf{1}\{m_i(s)\ge 2\}, & i\ \text{低能力},\\[2pt]
0.082\cdot\mathbf{1}\{m_i(s)\ge 1\}, & i\ \text{中等}.
\end{cases}
\]

目标：

\[
\frac{1}{8}\sum_{i=1}^{8}
\left[
\frac{1}{2}g_i(a)+\frac{1}{2}g_i(b)
\right].
\]

这是有限随机政策下的平均 GPA 变化（单位：绩点分），不是论文 Table VI 的处理效应系数，也不是「排序对低能力同学的因果影响」。

逐人结果。方案 a：3 号、4 号相邻的带学人都只有 1 号一人，各 +0.053；7 号相邻 5 号，+0.082；8 号相邻 6 号，6 号这次不带学，故为 0；1、2、5、6 号为 0。合计 0.106+0.082=0.188，平均 0.0235。方案 b：3 号、4 号相邻 1 号与 2 号两人，各 −0.061；7 号仍相邻 5 号，8 号这次相邻 6 号，各 +0.082。合计 −0.122+0.164=0.042，平均 0.00525。目标值 \(23/1600\)，即 \(0.014375\)；两方案平均之差 0.01825 只作为加派带学人的边际效果记录，不是目标量。

同一套加派动作，在甲组的完全图里同时落到两名低能力同学身上，把他们一起推过阈值，方向反转；在乙组的链里只落到 8 号一人，把他从 0 抬到 +0.082。这就是两组结构差在答案里的位置。

目标变化版只评甲组 3 号与 4 号，权重各 1/2：方案 a 平均 0.053，方案 b 平均 −0.061，目标值 \(-0.004\)，即 \(-1/250\)。同一政策下评价对象换成受影响为负的那两个人，符号从正转负。

## 3. 论文不支撑

- 不支撑把 +0.053 当作「加派一名带学人」的效应。它是论文用历史数据对「整组按算法重排、低能力组相对随机分组」的预测值（Table IV p. 868），干预与对照都不是本题的；
- 不支撑把 −0.061 与 +0.082 当作个体层面的处理效应。两者是组层面回归中处理组虚拟变量的系数（Table VI p. 871），本题把它们改写成按相邻带学人数分档的确定性规则；
- 不支撑把本题读作论文排序算法的复现。式 (3) 的整数规划（p. 865）不进入题目，本题的两个组早已分好，政策只决定派几名带学人；
- 不支撑把相邻关系当作论文估计出来的网络。论文只报告了学习伙伴与朋友的选择比例（Table VIII p. 878），没有逐人的邻接表；本题的六条边与三条边是自建的示意结构；
- 不支撑把抱团当作确定的外生事实。论文写「We cannot know with certainty the exact cause of our unexpected treatment effects」（p. 880），对中等同学的 0.082 只给出一句带保留的解释（「evidence suggests」）——这些学生被排进同质组后不再与低能力同学来往（p. 881）；
- 不支撑把八名学生当作论文的实测样本：Table VI（p. 871）报的 4,834 是两届各两个学期的学生-学期观测数（注 a 说明回归对象为「own first and second semester GPA」），不是人数；也不支撑外推到 20 个中队或 USAFA 整体；
- 不支撑把本项目标读作全体学生的福利变化：本题只结算成绩增量，不含挂科、退学、转专业等结果。

## 3.5 实际摘录

Abstract（p. 855）：

> “We find a negative and significant treatment effect for the students we intended to help.”

Abstract（p. 855）：

> “students avoided the peers with whom we intended them to interact and instead formed more homogeneous subgroups.”

Introduction（p. 856）：

> “The reduced form coefficients (using the pre-treatment data) predicted a Pareto-improving allocation in which grades of students in the bottom third of the academic distribution would rise, on average, 0.053 grade points while students with higher predicted achievement would be unaffected.”

Introduction（p. 856）：

> “For the lowest ability students, we observe a negative and statistically significant treatment effect of −0.061 (p = 0.055).”

Section 2（p. 865，两类组的界定）：

> “The first type of squadron groups low ability students with a large number of peers with high SAT Verbal scores. We refer to these as bimodal squadrons. The second type of treatment squadron consists largely of middle ability students without high SAT Verbal scores, which we call homogeneous squadrons.”

Section 2（p. 865，被实测推翻的那个假设）：

> “Assuming that students in the treatment group would choose among available study partners in the same way that students in the pre-treatment groups did, changing the composition of a low ability student’s squadron to include a larger proportion of students with high SAT Verbal scores should be beneficial.”

Section 3（p. 871）：

> “The magnitude of the effect (−0.061) indicates that the treatment was of the approximate magnitude predicted but the opposite sign”

Section 4（p. 878，Table VIII 正文）：

> “This is evidence of homophily; low predicted GPA students in the treatment squadrons actively sought out other low predicted GPA students as their study partners (relative to control squadrons) beyond what would have occurred as a result of random selection.”

Section 4（p. 878，同页正文，相邻关系那条证据的出处）：

> “low predicted GPA students in the treatment squadrons purposefully selected high SAT Verbal study partners with less frequency (−3.9 percentage points) than in the control squadrons”

说明一：PDF 提取文本中 ﬁ 连字与「GPA」「Table」「Variables」等词有空格插入，本文件按语义还原为正常拼写，未改动词序；负数前的减号在原文为短横，本文件照原样保留。

说明二：论文 Table IV 的注 a 写「We use the regression coefficients in Table II, Column 2」，而 Table IV 正文与 p. 865 均写 Column 3。两处指认的列号不一致，本卡按正文与 p. 865 的记录采用第 3 列，该处不影响 0.053 的取值，但引用时应以正文为准。

本案例只借用「双峰组与同质组两类结构」「组内实际来往少于被排进的组」与「排得更集中反而伤到低能力同学」三层机制的业务含义，不复制 USAFA 的 2,653 人平衡性样本与 4,834 个学生-学期观测、整数规划排序、逐人邻接表与 Table VI 的回归结果。

## 4. 阅读级别

`selected_full_text_sections`。已核对正式版 PDF 的 Abstract、Introduction、Section 1 与 Table I、Table II、Section 2 与式 (3)、Table III、Table IV、Section 3 与 Table VI、Section 4 与 Table VIII、Section 5；Section 1.2 的式 (1) 与式 (2) 推导、补充材料表 A.X 与各图完整读数未逐页核验。
