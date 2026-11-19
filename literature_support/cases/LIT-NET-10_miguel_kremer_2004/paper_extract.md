# 原文摘录与边界：Miguel & Kremer (2004)

> 场景改编声明：本文件记录场景改编案例所依据的原文位置与边界。论文未提出本题；案例中的九所学校、两种覆盖方案、基线出勤率与效应参数均为项目自建。下列摘录只用于说明借用了论文的哪个应用场景，以及论文不支撑哪些外推。

## 1. 本案例实际用到的原文位置

- Abstract（p. 159）：个体层面随机化会双重低估收益、学校层面随机分批可估计整体项目效应、未发现成绩改善。
- Introduction（pp. 159–161）：驱虫与出勤、外部性的研究动机。
- Section 3（p. 165）：PSDP 项目背景，75 所学校分层后按每三所取一所随机分入三组，各组 25 所，分批覆盖的时间表。
- Section 4.1（p. 175）：估计策略，学校层面随机化可识别整体效应与跨校溢出，处理校效应的直接与校内溢出分解需依赖非实验方法；方程 (1)。
- 未逐页核对：实证表、Section 5 之后的稳健性检验、成本效益测算。

## 2. 案例目标

三个片区，每片区三所学校，共九所。片区内随机一所进甲组、一所进乙组、一所进丙组。

两种覆盖方案，对应论文第一组与第三组的发药状态：

- 方案 A：每片区发甲组和乙组，片区内发药学校数 \(n_A=2\)，全校共六所；
- 方案 B：九所全部发药，片区内发药学校数 \(n_B=3\)，全校共九所。

记 \(D_i(k)=1\) 表示学校 \(i\) 在方案 \(k\) 的发药名单内，\(b=0.80\) 为基线出勤率，\(d=0.06\) 为本校发药效应，\(s=0.03\) 为片区内每多一所发药学校带来的溢出效应。方案 \(k\) 下学校 \(i\) 的出勤率为

\[
Y_i(k)=b+d\,D_i(k)+s\,\bigl(n_k-D_i(k)\bigr).
\]

两种方案各以 \(1/2\) 概率被采用，案例目标是随机政策下的九校等权平均：

\[
\theta=\frac{1}{9}\sum_{i=1}^{9}\Bigl[\tfrac12\,Y_i(A)+\tfrac12\,Y_i(B)\Bigr].
\]

分三步：

- 识别：学校层面整群分组，使方案差异不与学校特征混淆；片区内发药学校数在方案间由 2 变到 3，跨校溢出通过这一变化进入结果。
- 估计：方案 A 下九校平均 \(0.88\)，方案 B 下 \(0.92\)。
- 政策：\(\theta=\tfrac12\times0.88+\tfrac12\times0.92=0.90\)。两个相位之差 \(0.92-0.88=0.04\) 是扩大覆盖的边际效果，作为政策含义记在这里，不是本题目标量。

目标形式是随机政策均值，不是两个端点之差。原因是两份名单的覆盖规模不同（六所与九所），端点相减要求两端属于同一配额支持，本题不满足；改用混合均值表达，论文的整群分组结构因此保持不变。

## 3. 论文不支撑

- 不支撑九所合成学校是论文的 75 所学校数据；
- 不支撑把 6 个百分点、3 个百分点当作论文的估计值；
- 不支撑把处理校效应分解为直接效应与校内溢出，论文明确说这一分解依赖非实验方法；
- 不支撑把出勤率提升推成考试成绩提升，论文明确未发现成绩改善证据；
- 不支撑从九所合成学校外推到 Busia 地区；
- 不支撑把两个相位之差 0.04 当作论文识别的政策效应：论文只在 1998 年 1 月做了一次整群分组，第二组与第三组开始发药的年份不同，相位之差混入年份因素，本题之所以能算这个差，靠的是“无年度共同冲击、潜在结果只由发药状态决定”这条合成假设；
- 不支撑把甲、乙两组的直接效应当作相同：论文中第一组连服 1998、1999 两年，第二组 1999 年首服，两组服药年数不同。本案例不区分服药年数，把两份名单当作静态覆盖名单，这一条是合成设定，论文未给出服药年数不影响直接效应的结论。

## 3.5 实际摘录

Abstract（p. 159）：

> “Studies in which medical treatment is randomized at the individual level potentially doubly underestimate the benefits of treatment, missing externality benefits to the comparison group from reduced disease transmission, and therefore also underestimating benefits for the treatment group.”

> “We evaluate a Kenyan project in which school-based mass treatment with deworming drugs was randomly phased into schools, rather than to individuals, allowing estimation of overall program effects.”

> “Yet we do not find evidence that deworming improved academic test scores.”

Section 3（p. 165）：

> “Group 1 schools received free deworming treatment in both 1998 and 1999, Group 2 schools in 1999, while Group 3 schools began receiving treatment in 2001. Thus in 1998, Group 1 schools were treatment schools, while Group 2 and Group 3 schools were comparison schools, and in 1999, Group 1 and Group 2 schools were treatment schools and Group 3 schools were comparison schools.”

Section 4.1（p. 175）：

> “Randomization of deworming treatment across schools allows estimation of the overall effect of the program by comparing treatment and comparison schools, even in the presence of within-school externalities.”

> “Although randomization across schools makes it possible to experimentally identify both the overall program effect and cross-school externalities, we must rely on non-experimental methods to decompose the effect on treated schools into a direct effect and within-school externality effect.”

本案例只借用“以学校为单位随机分批发药”的业务背景，不复制 75 校样本、实际虫卵与出勤数据或跨校溢出估计。

## 4. 阅读级别

`selected_full_text_sections`。已核对正式版 PDF 的 Abstract、Introduction 动机段、Section 3 随机分组描述、Section 4.1 估计策略与方程 (1)；实证表、Section 5 之后的稳健性检验与成本效益测算未逐页核验。其中分层变量（行政分区、是否参与其他援助项目）与“每三所取一所”的分组细节，是对 Section 3 的转述，第 3.5 节只逐字摘录了三个组服药年份那一段，未摘录分组程序的原句。
