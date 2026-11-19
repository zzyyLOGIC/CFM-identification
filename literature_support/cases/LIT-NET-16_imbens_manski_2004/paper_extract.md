# 原文摘录与边界：Imbens & Manski (2004)

> 这不是论文全文，只保留本案例核对所需的部分。
>
> 版本：Imbens, G. W., and Manski, C. F. (2004), Confidence Intervals for Partially Identified Parameters, Econometrica 72(6):1845–1857，出版 PDF。
> 核对方式：全文提取为文本，下列摘录逐条以去空白子串匹配核回原页；页码为期刊页码。公式上下标在提取文本中有损坏，故涉及公式的句子只摘录文字部分，公式按式号引用。

## 1. 论文关注什么

部分识别参数的推断：参数只能定到一个识别区域 [θ_l, θ_u] 时，置信区间该覆盖真值还是覆盖整个区域。论文先给统一框架与引理 1（p. 1846），再在第 3 节用「缺失数据 + 已知倾向得分」的例子构造三类区间并比较（pp. 1847–1849），第 4 节推广到一般情形（pp. 1849–1851），附录给全部证明（pp. 1851–1857）。

## 2. 与本题直接相关的结构（论文第 3 节，p. 1847）

设结果有界，W 为观测指示，p = P(W=1) 已知，µ = E[Y|W=1]，λ = E[Y|W=0] 只知在 [0,1]。总体均值 θ = µ·p + λ·(1−p)，识别区域为 [µ·p, µ·p + (1−p)]，宽度恰为 1−p。p = 1 时点识别。第 4 节（p. 1850）在 p 需估计的一般情形下给出式 (6)、(7) 与引理 4。

本题的对应：两个端点团队扮演被观测子群（µ=1/2，权重质量 p=1/3），四个内部团队扮演缺失子群（λ 只知在 [0,1]）；原题答案是论文识别区域公式的逐字代入 [1/6, 5/6]；目标变化版只评被观测子群，即论文的 µ，点识别。

## 3. 逐字摘录与页码

以下 17 处均以去空白子串匹配核回 PDF 对应页。

1. p. 1845（摘要）：Recently a growing body of research has studied inference in settings where parameters of interest are partially identified
2. p. 1846：Many problems of partial identification have the following abstract structure
3. p. 1846（引理 1 的推论）：researchers face a substantive choice whether to report intervals
4. p. 1847（第 3 节开头）：In this section we construct CIs for the mean of a bounded random variable when some data are missing
5. p. 1847：assume initially that p is known. This will be relaxed in Section 4.
6. p. 1847（识别区域估计一行）：the identification region can be consistently estimated by
7. p. 1847（点识别情形）：In the point identified case with p = 1 we have
8. p. 1847：Note that as p → 1
9. p. 1848：has in large samples the appropriate confidence level for all values of p
10. p. 1848：this coverage probability approaches
11. p. 1849：It is interesting to compare the three intervals
12. p. 1849：Unless p = 1, this is strictly between the first two constants
13. p. 1849：which would give us the interval
14. p. 1849（第 4 节开头）：Here we develop a confidence interval that converges uniformly in more general settings
15. p. 1850：naturally estimated by its sample analog
16. p. 1851（附录，p 未知情形归到第 3 节区间）：equivalent to that obtained by substituting
17. p. 1851：Hence Assumption 1 is satisfied, and Lemma 4 can be used to construct a CI

## 4. 本案例与论文的关系

- 借用：第 3 节的识别区域公式 [µ·p, µ·p + (1−p)]（p. 1847）及其点识别极限；θ 与 µ 的区分（总体均值对被观测子群均值）。
- 不借用：三类置信区间的构造与比较（式 (2)、(3)、(4)、(5)，pp. 1847–1849）、第 4 节的一般区间（式 (6)、(7)）与引理 1–10 的全部推断内容——本题是确定性有限总体模型，无抽样噪声，这些内容没有对应物。
- 数值全部自建：论文没有经验数值；1/2、1/6、5/6、名额 2、链式网络、六团队名单都是项目自建。
- sharp 性由项目有限模型的求解与证书重放单独检查，不引用论文当作证明。

## 5. 没核对的内容

- 附录引理 5–10 的证明细节（pp. 1852–1857）只确认了存在与定位，未逐步复算；
- 提取文本中公式上下标的损坏处未逐一对照原版式；
- 出版版与其他来源版本的差异。
