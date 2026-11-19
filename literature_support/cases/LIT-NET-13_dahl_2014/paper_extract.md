# 原文摘录与边界：Dahl, Løken & Mogstad (2014)

> 场景改编声明：AER 2014 改编。本文件记录场景改编案例所依据的原文位置与边界。论文未提出本题；八名父亲、两个厂的同事关系与出生顺序、一条兄弟边、两套生效日安排与「相对不推行政策时的平均提高」这一目标均为项目自建。下列摘录只用于说明借用了论文的哪几层事实，以及论文不支撑哪些外推。网络进入目标：删去边集，同厂与先后都无从确定，题目不能计算。

## 1. 本案例实际用到的原文位置

- Abstract（p. 2049）：同事与兄弟分别高 11 与 15 个百分点；最可能的机制是信息传递；效应随时间滚雪球。
- Introduction（pp. 2049–2051）：改革的 3% 到 35%、第一阶段 32 个百分点、同事 reduced form 3.5 个百分点、兄弟 4.7 个百分点；首批参与者决定后续路径的政策含义。
- Section I（pp. 2052–2053）：以 1993 年 4 月 1 日为断点的识别策略，同事与兄弟的资格不随断点变化。
- Section IV 与 Table 1（pp. 2058–2063，Table 1 在 p. 2060）：第一阶段 0.317 与 0.304、reduced form 0.035 与 0.047、二阶段 0.110 与 0.153。
- Section V 与 Table 3（pp. 2063–2066）：机制证据，经理、低工会化、私营、低任期四组效应更大。
- Section VI 与式 (6)–(9)（pp. 2066–2070）：顺序排序与可加可分假设；Coworker 2 只承载直接效应；Table 4 Panel B 的 0.026、0.037、0.060 与 0%、30%、57% 的雪球占比；第五位及以后观测不足。
- Section VII（pp. 2071–2072）：结论与对政策设计的含义。
- 未逐页核对：online Appendix 的衰减参数构造（r₂=0.27、r₃=0.04、r₄=−0.18、r₅=−0.71 只在正文 p. 2069 读到）、Figure A5、Section II 的样本限制细节。

## 2. 案例目标

八名父亲，两条网络，一条先后顺序：

```text
甲厂：1 号、2 号、3 号、4 号，两两互为同事（六条边）；当爸爸的先后 1 → 2 → 3 → 4
乙厂：5 号、6 号、7 号，两两互为同事（三条边）；当爸爸的先后 5 → 6 → 7
兄弟：1 号与 8 号；8 号在丙厂上班，丙厂没有其他研究对象，也不推行这项政策
```

同事之间互相知道对方休没休，但只有排在前面的人生效，排在后面的人不反过来影响前面的人（论文的 sequential ordering，p. 2067）。

两套生效日安排，各以 1/2 概率被采用：

- 方案 a：甲厂生效日定在 1 号之前（1 号被覆盖），乙厂定在 5 号之前（5 号被覆盖）；
- 方案 b：甲厂生效日推到 2 号与 3 号之间（1、2 号在生效日之前，不被覆盖；3 号被覆盖），乙厂不变。

结果规则。设 \(s\) 为被覆盖的父亲集合，每套安排里每个厂恰好一位。把 \(i\) 所在厂的员工按出生先后排开，被覆盖的那位的名次记作 \(p\)，\(i\) 的名次记作 \(q\)，令 \(d_i(s)=q-p\)；当 \(q\le p\)、或本厂无人被覆盖时，这一项不生效。

\[
g_i(s)=0.32\cdot\mathbf{1}\{i\in s\}+a_{d_i(s)}\cdot\mathbf{1}\{1\le d_i(s)\le 3\}+0.047\cdot\mathbf{1}\{i=8,\ 1\in s\},
\qquad a=(0.026,\ 0.037,\ 0.060).
\]

目标：

\[
\frac{1}{8}\sum_{i=1}^{8}\left[\frac{1}{2}g_i(a)+\frac{1}{2}g_i(b)\right].
\]

这是有限随机政策下休假概率相对不推行政策时的平均提高（单位：概率，取值在 0 与 1 之间），不是论文 Table 1 的二阶段系数，也不是挪威改革的政策效应。

逐人结果。方案 a：1 号 0.32，2 号 0.026，3 号 0.037，4 号 0.060，5 号 0.32，6 号 0.026，7 号 0.037，8 号 0.047，合计 0.873，平均 0.109125。方案 b：1 号、2 号不在生效之后，为 0；3 号 0.32，4 号 0.026；乙厂同方案 a，合计 0.383；8 号为 0。全部合计 0.729，平均 0.091125。目标值 \(801/8000\)，即 \(0.100125\)；两方案平均之差 0.018 只作为推迟生效的边际效果记录，不是目标量。

顺序在答案里的位置：方案 a 中甲厂四位都在覆盖者之后，名次差分别为 1、2、3，拿到 0.026、0.037、0.060；方案 b 中只有 4 号在 3 号之后，名次差为 1，只拿到 0.026，1 号与 2 号在生效前，为 0。同一批人、同一条同事关系，只因为生效日往后挪了两位，甲厂合计从 0.443 落到 0.346。

目标变化版只评甲厂后三位（2、3、4 号），权重各 1/3：方案 a 合计 0.123，平均 0.041；方案 b 合计 0.346，平均 \(173/1500\)；目标值 \(469/6000\)，即 \(0.078166\ldots\)。

## 3. 论文不支撑

- 不支撑把 0.32 当作被覆盖者的休假率：论文的 35% 是改革后全体父亲的参与率（p. 2050），本题只用相对不推行政策时的提高幅度，不涉及水平值；
- 不支撑把 0.026、0.037、0.060 读成「每一位上游休假者各加一次」：这三个数是相对最初那位覆盖者的 reduced form 总量（Table 4 Panel B p. 2069），雪球已含在内；
- 不支撑把断点日期当作内生的：论文的日期由政策规定（p. 2052），本题把它当作可选排期，等于把识别设计改成政策设计；
- 不支撑把这套规则当作式 (6)–(9) 的复现：论文没有报告结构系数 β，本题直接用 reduced form，不做反解；
- 不支撑把兄弟效应读成会继续传导：论文没有检验「兄弟再影响他的同事」，本题不设这条路径；
- 不支撑把八名父亲当作论文的样本：26,851 与 12,495 是同事与兄弟的观测数（Table 1 p. 2060），不是人数；也不支撑外推到挪威全国或 2006 年 70% 的参与率；
- 不支撑把休假概率的提高读成收入、职业发展或性别平等的改善：论文的结局只有是否休假这一项。

## 3.5 实际摘录

Abstract（p. 2049）：

> “Coworkers and brothers are 11 and 15 percentage points, respectively, more likely to take paternity leave if their peer was exogenously induced to take up leave.”

Abstract（p. 2049）：

> “The estimated peer effect snowballs over time, as the first peer interacts with a second peer, the second peer with a third, and so on.”

Introduction（p. 2050，改革前后的参与率）：

> “There is a sharp increase in fathers taking paternity leave immediately after the reform, from a pre-reform take-up of 3 percent to a post-reform take-up of 35 percent.”

Introduction（p. 2050，第一阶段与同事效应）：

> “Since the first-stage estimate on take-up is 32 percentage points, this implies a peer effect estimate of 11 percentage points.”

Introduction（p. 2050，兄弟效应）：

> “For the family network, we find that brothers of reform-window fathers who were eligible for leave are 4.7 percentage points more likely to take paid leave after the birth of their first child.”

Introduction（p. 2051，本题政策问题的来路）：

> “the initial group of participants can play a large and lasting role in the evolution of take-up patterns.”

Introduction（p. 2051，雪球占比）：

> “snowball effects account for over 50 percent of the total peer effect for the third and higher-order coworkers in a firm.”

Section I（p. 2052，断点设定）：

> “a reform was passed which made fathers of children born in Norway after April 1, 1993 eligible for one month of governmental paid paternity leave, while fathers of children born before this cutoff were not.”

Section VI（p. 2067，顺序排序假设）：

> “The assumption of sequential ordering implies that fathers who already have births influence fathers who subsequently have births, and not the other way around.”

Section VI（p. 2067，为什么第一位更有影响）：

> “the first coworker to take leave is likely to reveal more novel information and therefore be a more influential peer than the second or third coworker to take leave.”

Section VI（p. 2068，直接效应的识别）：

> “The second coworker identifies the direct effect”

Section VI（p. 2069，Table 4 Panel B 的读法）：

> “For coworker group 3, the decay adjusted reduced form peer effect is 0.037, with the snowball effect accounting for 30 percent of the total peer”

Section VI（p. 2069，第五位及以后不外推的理由）：

> “we do not have enough observations to separately estimate effects within the firm for fifth and later coworkers”

说明一：PDF 提取文本在断行处会把连字符留在行尾（如 “decay- adjusted”），本文件按语义还原为 “decay adjusted”，未改动词序；Table 4 表体内的数字由表头与行标逐格核对，正文对 coworker group 3 与 group 4 的复述（0.037、0.060）与表体一列一列对得上。

说明二：正文 p. 2050 把第一阶段写作 32 个百分点，Table 1（p. 2060）报的是 0.317；本题取 0.32 这两个口径中较整的一个，并在参考文件里同时记下 0.317，二者不冲突但不可混用。

说明三：Table 4 分三个面板，Panel A 未做衰减调整（0.033、0.039、0.049），Panel B 为三次衰减调整（0.026、0.037、0.060），Panel C 为四次衰减调整（0.024、0.034、0.055）。论文写「key results」在 Panel B 与 Panel C（p. 2069），本题取 Panel B；换成 Panel A 或 C，四个数会变，答案随之改变。

本案例只借用「断点式政策与第一阶段的方向」「同事效应随出生顺序递增」「兄弟效应大于同事」三层事实的业务含义，不复制论文的断点估计、衰减参数构造、结构参数反解与样本。

## 4. 阅读级别

`selected_full_text_sections`。已核对正式版 PDF 的 Abstract、Introduction、Section I、Section IV 与 Table 1、Figure 3、Section V 与 Table 3、Section VI 与式 (6)–(9)、Table 4、Section VII；online Appendix 的衰减参数构造、Figure A5 与 Section II 的样本限制细节未逐页核验。
