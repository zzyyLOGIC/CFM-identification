# 原文摘录与边界：Cai & Szeidl (2018)

> 场景改编声明：本文件记录场景改编案例所依据的原文位置与边界。论文未提出本题；案例中的四个会议组、四十家企业、零基线与政策概率均为项目自建。借用的这一层是论文 Section IV.A 用于验证学习机制的附加实验，不是论文的主干预与主结局。下列摘录只用于说明借用了论文的哪一层随机化与哪几个系数，以及论文不支撑哪些外推。

## 1. 本案例实际用到的原文位置

- Abstract（p. 1229）：2,820 家企业随机分成会议组与不开会控制组，会议提高收入 8.1%。
- Introduction（p. 1230）：一句概述样本筛选与随机化，写作“From 2,820 firms that expressed interest”。
- Section II.B（pp. 1236–1239）：样本筛选与会议组随机化（p. 1236）、四种组类型与 26 个 subregion 的随机排序（p. 1238）、组内信息投放 0%、50%、80% 三档的处理强度（p. 1239）。
- Section II.D（p. 1245）：样本自选择，效应只适用于对参加会议感兴趣的企业。
- Section III.B（p. 1256）：同伴效应，同伴规模高 10 log 点对应销售额多增 1.05 log 点。
- Section IV.A 与 Table IX（pp. 1265–1266）：信息扩散的三个系数；50% 与 80% 覆盖率下扩散率相近的说明见注 30（p. 1268）。
- 未逐页核对：Section IV.B（伙伴匹配）、Section V（结论与成本效益）、在线附录各表。

## 2. 案例目标

四个会议组，每组十名经理，共四十家小微企业。组一、组二为同行业组，组内多数企业互为竞争对手；组三、组四为混合行业组。

两种投放方案，对应论文组内 50% 与 80% 两档覆盖率：

- 方案 A：每组给 5 名经理投放，组内覆盖率 \(5/10\)；
- 方案 B：每组给 8 名经理投放，组内覆盖率 \(8/10\)。

记 \(I_i\) 表示经理 \(i\) 被直接告知，\(C_g\) 表示组 \(g\) 是同行业竞争组。组内覆盖率高于零时，未被告知者至少有一名知情同伴，故本案例中扩散项恒被激活。方案 \(k\) 下经理 \(i\) 的申请概率为

\[
P_i(k)=0.300\,I_i+(0.291-0.212\,C_g)\,(1-I_i).
\]

零基线对应"未被直接告知、组内也没有知情同伴时申请概率为 0"，是题目对论文"两款产品相对不为人知"这一描述的边界设定。

两种方案各以 \(1/2\) 概率被采用，目标是随机政策下四十家企业的等权平均：

\[
\theta=\frac{1}{40}\sum_{i=1}^{40}\Bigl[\tfrac12\,P_i(A)+\tfrac12\,P_i(B)\Bigr].
\]

分三步：

- 识别：组内投放名单随机，条件于组类型与片区后，谁被告知与谁未被告知是随机的；竞争属性由组构成决定，与投放名单正交。
- 估计：方案 A 下同行业组每家 0.1895、混合行业组 0.2955，四十家平均 0.2425；方案 B 下 0.2558 与 0.2982，平均 0.277。同行业组未被告知者的概率为 \(0.291-0.212=0.079\)，不是 0.08；中间值一律保留四位小数。
- 政策：\(\theta=\tfrac12\times0.2425+\tfrac12\times0.277=0.25975\)，即 \(1039/4000\)。两方案之差 0.0345 是扩大投放的边际效果，作为政策含义记在这里，不是本题目标量。

目标形式是随机政策均值，不是两个端点之差。两份投放名单各以 \(1/2\) 概率被采用，政策分布完整。

## 3. 论文不支撑

- 不支撑四十家合成企业是论文的 2,820 家研究样本；
- 不支撑把 0.300、0.291、0.212 当作论文对单个企业概率的预测，这三个数是 Table IX 三个回归的系数，论文没有把它们拼成个体预测式；
- 不支撑把 0.300 与 0.291 当作同一人群的估计：0.300 来自全样本（含控制组）的 Info 系数（第 1 列），0.291 只来自会议组未被告知者的子样本（第 3 列）。本题把两者放进同一个式子相加，是可加性假设，不是论文的估计；
- 不支撑把“哪两组是竞争组”当作论文给出的分组，论文的 Competition 是组内平均自报竞争者数高于中位数的指示变量（p. 1265、注 28），本题直接指定组一、组二为同行业竞争组；
- 不支撑把申请补助的概率当作企业绩效，论文主结局是收入提高 8.1%，信息投放对收入没有报告效应；
- 不支撑外推到所有小微企业，样本是自愿报名、对参加会议感兴趣的企业；
- 不支撑把零基线与"完全不投放"当作论文的对照组，论文控制组同样有 40% 的经理被投放了信息；
- 不支撑把竞争组主效应 −0.150 纳入本题，论文报告了该系数，但它与扩散交互的语义部分重叠，且与 −0.212 同时置于零基线上会使同行业组未被告知者的概率成为负数；
- 不支撑把扩散写成按知情人数线性递增，论文注 30 报告 50% 与 80% 覆盖率的扩散率相近，线性形式与该事实矛盾。

## 3.5 实际摘录

Abstract（p. 1229）：

> "We randomized 2,820 firms into small groups whose managers held monthly meetings for one year, and into a "no-meetings" control group."

> "The meetings increased firm revenue by 8.1%, and also significantly increased profit, factors, inputs, the number of partners, borrowing, and a management score."

Introduction（p. 1230）：

> "From 2,820 firms that expressed interest, we randomly selected 1,500 and randomized their owner-managers into meetings groups with 10 managers each. We informed the remaining 1,320 firms—the control group—that there was no room for them in the meetings."

Section II.B（p. 1238）：

> "The randomization ensured that conditional on the firm's strata and subregion, the peers of the firm were random."

Section II.B（p. 1239）：

> "We distributed information about each product in February 2014 via phone calls and text messages to 0%, 50%, or 80% of the managers in each meeting group. We randomly assigned about one third of the meeting groups to each of these three treatment intensities."

Section II.D（p. 1245）：

> "Due to this self-selection, our treatment effect estimates apply not to the representative firm, but to firms interested in participating in business associations."

Section III.B（p. 1256）：

> "Column (1) implies that firms randomized into groups with 10 log points larger peers experienced an additional (significant) sales increase of 1.05 log points as a result of the treatment."

Section IV.A 与 Table IX（pp. 1265–1266）：

> "Column (1), which only includes Infoi, shows that being informed increased the likelihood of application by a highly significant 30 percentage points."

> "The significant coefficient of 0.291 in column (3) shows that having at least one informed group member increased the probability of application by 29.1 percentage points."

> "the significant and negative interaction effect of −0.212 suggests that competition reduced the strength of information diffusion about the firm funding product."

注 30（p. 1268）：

> "Online Appendix Table O7 shows that the diffusion rate was similarly high in the 50% and the 80% information treatment: there was no major increase in uninformed managers' probability of application when having 80% rather than 50% informed group members."

说明：PDF 提取文本在上述多处有换行断词（如 "random ized"、"ad ditional"、"diffu sion"）与行内公式下标（"Infoi"）；本文件按语义拼接还原为单词，未改动词序与标点。

本案例只借用组内信息投放的覆盖率结构与竞争调节，不复制 2,820 家样本、实际申请数据或会议对收入的主效应估计。

## 4. 阅读级别

`selected_full_text_sections`。已核对正式版 PDF 的 Abstract（p. 1229）、Introduction 的样本概述（p. 1230）、Section II.B 的样本筛选与组构成（pp. 1236–1239）、Section II.D 的自选择讨论（p. 1245）、Section III.B 的同伴效应（p. 1256）、Section IV.A 与 Table IX 的扩散系数（pp. 1265–1266）、注 30 的覆盖率比较（p. 1268）；Section IV.B、Section V 与在线附录各表未逐页核验。

其中"约 5,400 家报名、随机选 2,820 家作为研究样本"这一句，Introduction 与 Section II.B 的叙述略有差异：Introduction 写作"From 2,820 firms that expressed interest"，Section II.B 写作"约 5,400 家表达兴趣、随机选 2,820 家作为研究样本"。本卡与来源卡按 Section II.B 的口径记录。
