# 原文摘录与边界：Alatas et al. (2016)

> 场景改编声明：本文件记录场景改编案例所依据的原文位置与边界。论文未提出本题；案例中的两村八户、两套核实安排、判定规则与家底被摸清的比例这一目标均为项目自建。下列摘录只用于说明借用了论文的哪两层机制，以及论文不支撑哪些外推。网络进入目标：删去边集后邻居无法确定，题目不能计算。

## 1. 本案例实际用到的原文位置

- Abstract（p. 1663）：研究问题、半贝叶斯学习模型、社区定向瞄准应用。
- Introduction（pp. 1664–1665）：社区掌握分散贫困信息、网络结构影响信息聚合的动机。
- Section II 开头（p. 1672）与 Section IIA（pp. 1673–1679）：信息分布与网络位置的描述性证据，含 Table 1 的网络统计量与 Table 4 的距离与错误率关系。
- Section V（pp. 1697–1701）：瞄准应用，Table 10 与 Table 11 的扩散性交互结果。
- Section VI（p. 1702）：结论中对政策含义的表述。
- 未逐页核对：Section III 的模型推导与结构估计细节、Section IV 的跨村比较、在线附录 A 至 F。

## 2. 案例目标

两村共八户：

```text
村甲：户1 ── 户2        村乙：户5 ── 户6 ── 户7 ── 户8
      │  ╲  │
      │   ╲ │
     户3 ── 户4
```

村甲四户两两相连，共六条边；村乙四户成一条链，共三条边。无其他边，无自环。

入户调查已经逐户核准各家底细，该结论只用于说明“摸清”指什么，不进入结果计算。

两套核实安排，各 1/2 概率：

- 方案 a（核实 {1, 5}）；
- 方案 b（核实 {1, 3, 5, 6}）。

判定规则：本户被核实，或本户的邻居中至少有一户被核实，家底算被摸清；否则按没摸清计。

目标：

\[
\frac{1}{8}\sum_{i=1}^{8}
\left[
\frac{1}{2}C_i(a)+\frac{1}{2}C_i(b)
\right],\qquad
C_i(s)=\mathbf{1}\{\, i\in s \ \text{或}\ N(i)\cap s\neq\varnothing \,\}.
\]

其中 \(N(i)\) 为户 \(i\) 的邻居集合。这是有限随机政策下的平均摸清率，不是论文 Table 10 的交互系数，也不是“扩散度对瞄准效果的因果影响”。

逐户结果：方案 a 下村甲四户全部摸清、村乙只有户5 与户6 摸清，合计 6/8；方案 b 下村甲仍四户全部摸清、村乙户5 至户7 摸清，合计 7/8。目标值 \(13/16\)，端点差 \(1/8\)。

## 3. 论文不支撑

- 不支撑把“距离 1 即完全知道”当作论文结论。论文的 Table 4 给的是概率性的错误率差（2.5 至 3.8 个百分点），本题把它压成 0 与 1；
- 不支撑把摸清与否当作确定性事实。论文的户层面错误率是 0.52（消费）与 0.46（自评），don't know 占 0.19，本题未建模噪声；
- 不支撑把本题读作论文半贝叶斯学习模型或结构估计的复现；
- 不支撑把本题读作 Table 10 交互回归的复现，本题不估计 β_C，也不以回归系数为答案；
- 不支撑把八户两村当作论文的 631 个社区；村甲用完全图是有意放大的极端结构；
- 不支撑从本案例推断真实村庄的最优核实安排。

## 3.5 实际摘录

Abstract（p. 1663）：

> “citizens chose households to receive aid, and show that the networks”

> “that the model predicts to be more diffusive differentially benefit from”

Section II 开头（p. 1672）：

> “Note that these are descriptive regressions and not causal estimates.”

Section IIA（p. 1679，Table 4 正文）：

> “Average inverse distance is highly predictive of ranking accuracy.”

Section IIA（p. 1673，Table 1 正文）：

> “fraction of nodes in the giant component of only 0.51”

Section V（p. 1698，Table 10 Panel B 正文）：

> “we find positive and significant estimates of βC and βH”

说明：PDF 提取文本在上述 Abstract 两处及连通分量一句处有换行，本文件按行截取，未改动词序。

本案例只借用“信息随网络距离衰减”与“网络扩散性影响聚合”两层机制的业务含义，不复制 631 个社区数据、半贝叶斯学习模型、结构估计或 Table 10 的回归结果。

## 4. 阅读级别

`selected_full_text_sections`。已核对正式版 PDF 的 Abstract、Section I、Section IIA 与 Table 1 至 Table 4、Section V 与 Table 10、Table 11、Section VI；Section III 的模型推导与结构估计细节、Section IV 的跨村比较、在线附录 A 至 F 未逐页核验。
