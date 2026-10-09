# Student Task 1

第一轮任务的正式定义、编号和验收要求，以群内发布的任务书为准。任务书不放入本仓库；
本页只提供任务索引和代码提交位置。

这一轮的目的首先是熟悉 randomized-network Identification、query-specific support、POINT 推导、
小图 exact / brute-force 验证和 GitHub PR workflow；**任务完成不等于实现一定进入 `main`**。

## Task matrix

三种 assignment design：

- **D1**：heterogeneous independent Bernoulli，节点有已知 pretreatment probability `p_i`；
- **D2**：complete randomization，固定 `sum_i T_i = m`；
- **D3**：两个 pretreatment groups，各自固定 treated quota `m_1, m_2`，允许跨组网络边。

三种 exposure definition：

- **E1**：strict majority；
- **E2**：treated-neighbor fraction 的 low / medium / high 三档；
- **E3**：pretreatment core-collaborator strict majority。

对应九个独立任务：

```text
Task01 = D1 × E1
Task02 = D1 × E2
Task03 = D1 × E3
Task04 = D2 × E1
Task05 = D2 × E2
Task06 = D2 × E3
Task07 = D3 × E1
Task08 = D3 × E2
Task09 = D3 × E3
```

默认 standalone deliverables 放在：

```text
student_work/taskXX/
├── setting.md
├── support.py
├── rule.py
├── demo.ipynb
└── test_rule.py
```

每个任务至少要解释 target / changed setting、计算 query-specific population support、说明 supported
arms 为什么在 randomization + consistency 下为 POINT，并使用小图 exact enumeration / brute-force
进行验证。详细要求以群内发布的任务书为准。
