# 原文摘录与边界：Conley & Udry (2010)

> 场景改编声明：AER 2010 改编。本文件记录场景改编案例所依据的原文位置与边界。论文未提出本题；八名农户、三个村的信息邻里划分、上一季化肥强度表、两套抽签安排的示范与「下一期化肥强度相对上一季的平均变化」这一目标均为项目自建。下列摘录只用于说明借用了论文的哪几层事实，以及论文不支撑哪些外推。网络进入目标：删去边集，谁观察示范无从确定，题目不能计算。

## 1. 本案例实际用到的原文位置

- Abstract（p. 35）：农户把自己的投入调向信息邻里里意外成功者的水平。
- Introduction（pp. 35–38）：主结论列表——好消息在高水平处带动上调、低水平处带动下调；新手的反应远大于老兵。
- Section II（pp. 40–43）：M 的构造；好消具新闻接近自己上一期水平时 M 近零；M 绝对值与经验成反比。
- p. 51：M 的带符号定义逐句展开。
- Table 4 注（p. 55）：信息邻里按「问过农艺建议」定义；样本 107。
- Section IV 正文（pp. 56–58）：1 个标准差约 4 对 4 塞迪每株；老兵无反应；财务邻居不显著；向下与向上同样真实；自己地块与他人地块无差异。
- Table 5（p. 57）：M 1.05（0.20）；M×新手 1.07（0.22）；M×老兵 −0.46（0.34）。
- Table 6（p. 59）：自己地块 1.46（0.56）对信息邻里 1.22（0.31）。
- p. 60：maize-cassava 无学习效应。
- 未逐页核对：Appendix A、Table A1 与 Γ 控制变量的构造细节。

## 2. 案例目标

八名农户，两条信息网络：

```text
甲村：1、2、3、4 号，信息边 1—2、1—3、2—3、2—4（四条）
乙村：5、6、7 号，信息边 5—6、6—7（两条）
表亲：1 号与 8 号；8 号在丙村，丙村没有其他研究对象
```

信息邻里按「互相问过农艺建议」的口径（论文 Table 4 注 p. 55 的问卷定义）。

上一季化肥强度（塞迪每株）：1 号 2、2 号 4、3 号 6、4 号 2、5 号 3、6 号 5、7 号 3、8 号 5。3 号是老兵，其余七户是新手。

两套示范安排，各以 1/2 概率被采用：

- 方案 a：1 号把自家强度调到 4，收成高于预期；
- 方案 b：6 号把自家强度调到 2，同样高于预期。

结果规则。设示范户为 d、示范水平为 ℓ，N(d) 为 d 的信息邻里。对每户 i：

\[
g_i = (\ell - x_{i,\text{prev}})\cdot\mathbf{1}\{i \text{ 为新手},\ i\in N(d)\cup\{d\},\ \ell\neq x_{i,\text{prev}}\},
\]

老兵恒为 0。

目标：

\[
\frac{1}{8}\sum_{i=1}^{8}\left[\frac{1}{2}g_i(a)+\frac{1}{2}g_i(b)\right].
\]

这是有限随机政策下下一期化肥强度相对上一季的平均变化（单位：塞迪每株，可正可负），不是论文的回归系数，也不是 M 指数。

逐户结果。方案 a：N(1)={2,3,8}。1 号 4−2=+2；2 号示范水平 4 恰等于上一季 4，为 0；3 号老兵，为 0；8 号 4−5=−1；其余为 0。合计 +1，平均 1/8。方案 b：N(6)={5,7}。6 号 2−5=−3；5 号 2−3=−1；7 号 2−3=−1；其余为 0。合计 −5，平均 −5/8。目标值 \(-\frac14\)，即 −0.25；两方案平均之差 3/4 只作为示范落点不同这一事实的记录，不是目标量。

目标变化版只评乙村 5、6、7 号，权重各 1/3：方案 a 乙村无人示范也无人观察，合计 0；方案 b 合计 −5，平均 −5/3；目标值 \(-\frac56\)，即 −0.8333…。

## 3. 论文不支撑

- 不支撑把 1.05 读成精确倍数：正文口径是「约 4 对 4」（p. 56），本题取整为 1，系数 1.05 同时记录，二者不冲突但不可混用；
- 不支撑把 M 的经验归一化搬进题面：论文的 M 绝对值与经验成反比（p. 43），本题只保留符号含义与新手的规模口径，老兵改用独立规则表达，按论文归一化重算答案会变；
- 不支撑把示范当作论文里的实验：论文的实验是农户自发选择化肥水平（p. 51 附近），本题改为协会抽签安排，示范水平是政策参数；
- 不支撑把「收成高于预期」当作估计结果：论文靠 growing conditions 控制识别好消具新闻，本题直接规定示范收成高于预期，是设定；
- 不支撑用地理或财务邻里替代信息邻里：财务邻居系数不显著（Table 5 p. 57），地理邻居由控制变量 Γ 承担（p. 56），都不是题面的学习渠道；
- 不支撑把八户当作论文样本：107 是种植者数（Table 4 注 p. 55），上一季强度的八个数是自建；
- 不支撑外推到其他作物：玉米木薯这一成熟技术上没有学习效应（p. 60），本题不外推。

## 3.5 实际摘录

Abstract（p. 35）：

> “we find evidence that farmers adjust their inputs to align with those of their information neighbors who were surprisingly successful in previous periods”

Introduction（p. 37，主结论之二，方向规则）：

> “he increases (decreases) his use of fertilizer after his information neighbors achieve unexpectedly high profits when using more (less) fertilizer than he did”

Introduction（p. 37，主结论之三，新手异质性）：

> “his responsiveness to news about the productivity of fertilizer in his information neighborhood is much greater if he has only recently begun cultivating pineapple”

Section II（p. 43，经验归一化）：

> “M is constructed so that its absolute magnitude is inversely proportional to farmer i’s experience”

p. 51（M 的带符号定义）：

> “If planting j,t results in good news about an input level xj,t which is much higher than farmer i’s previously used level (xi,tp), Mi,tc is large and positive; if, instead, it contains good news about a level xj,t that is much lower than xi,tp, it is large and negative; and it will be near zero if good news concerns input levels near xi,tp (or zero in the absence of good news)”

Table 4 注（p. 55，信息邻里口径）：

> “Have you ever gone to farmer ____ for advice about your farm?”

Table 4 注（p. 55，样本量）：

> “Sample size = 107”

Section IV 正文（p. 56，规模口径）：

> “A one-standard-deviation increase in M (about four) is associated with an increase in fertilizer use of approximately four cedis per plant”

Section IV 正文（p. 56，老兵无反应）：

> “There is no evidence that veteran pineapple farmers respond at all to good news about alternative levels of fertilizer use”

Section IV 正文（p. 56，财务邻居）：

> “There is no evidence that changes in input use are significantly related to inputs used by financial neighbors”

Table 5（p. 57，表体逐格）：

> “Index of good news input levels (Mi,t ) 1.05 (0.20)”；“Mi,t × novice farmer 1.07 (0.22)”；“Mi,t × veteran farmer −0.46 (0.34)”

Section IV 正文（p. 58，向下同样真实）：

> “driven as much by farmers moving down in response to good news at lower levels of fertilizer use as by upward movement in response to good news at higher fertilizer levels”

Section IV 正文（p. 58，自己地块与他人地块）：

> “there is no important or statistically significant difference between the impact of good news on one’s own plot and that of good news on a neighbor’s plot”

Table 6（p. 59，表体逐格）：

> “M from own plots only 1.46 (0.56)”；“M from information neighbors 1.22 (0.31)”

p. 60（不外推）：

> “there is no evidence that maize-cassava farmers adjust labor inputs to information from the cultivation of their information neighbors”

说明一：PDF 提取文本在断词处会留下空格（如 “learn ing”、“asso ciated”），弯引号保留为 ’、下标保留为 xj,t 形式；本文件按语义还原空格，未改动词序与数字；上述引文均以去空白后的子串匹配核回原文，页码按 PDF 第 n 页为期刊第 34+n 页换算。

说明二：系数与规则的关系。论文 Table 5 A 列报 M 的系数 1.05（SE 0.20），正文口径「1 个标准差的 M（约 4）对应约 4 塞迪每株」（p. 56）等价于系数取 1；本题的「新手调到示范水平」取这一整数口径，并把老兵的 −0.46 不显著（p. 57）简化为「老兵不动」。两处都是取整或简化，出处与数值同时记录，不可混用。

说明三：论文的 M 绝对值与经验成反比（p. 43），本题没有搬运这个归一化；本题的规则表只保留符号含义，新手与老兵的差异改由两条独立规则表达。若按论文的归一化重算，答案会变。

本案例只借用「带符号的方向规则、新手与老兵的异质性、双向调整」三层事实的业务含义，不复制论文的 M 指数构造、Γ 控制变量、空间 GMM 估计与样本。

## 4. 阅读级别

`selected_full_text_sections`。已核对正式版 PDF 的 Abstract、Introduction、Section II 模型部分、p. 51 的 M 定义、Table 4 注、Section IV 正文、Table 5、Table 6 与 maize-cassava 对照段；Appendix A、Table A1 与 Γ 的构造细节未逐页核验。
