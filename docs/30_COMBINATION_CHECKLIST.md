# 30 种 D×E 组合 × 2 种目标逐项检查表

> 任务3：将有限 PARTIAL 推广至全部 30 种 D1–D6 × E1–E5 组合
> 每种组合包含两个目标：(A) 单政策均值界限；(B) 第一政策减第二政策对比界限

## 核心求解路径

求解路径统一使用 `mean_order_solver.solve()` 或增强的 `general_bounded_*_solver`：

1. **验证模型**：validate_model / validate_pair → 确认信息与假设兼容
2. **枚举单元格**：根据 D/E 类型枚举 (n, a, e) 三元组
3. **计算支持**：SupportEngine.evaluate() 或独立 verifier 验证
4. **构建 LP**：mean_order_solver 对每个节点构建 box + order 约束
5. **求解区间**：枚举所有可行基解，输出 [min cᵀm, max cᵀm]
6. **生成证书**：primal/dual 证据证明端点可达

---

## 检查表（30 行，每行 2 个目标）

| # | 组合 | 起始状态 | 目标 A（均值界） | 目标 B（对比界） | E2 孤立点 | D6 两阶段 | 完成条件 |
|---|------|---------|----------------|----------------|-----------|-----------|---------|
| 1 | D1_E1 | ✅ POINT 已验证 (test_a4: 186) | ✅ 可推广 | ✅ 可推广 | N/A (E1) | N/A (D1) | 参数化 solver 通过 |
| 2 | D1_E2 | ✅ POINT 已验证 (test_a4: 186) | ✅ 可推广 | ✅ 可推广 | ⚠ 需处理 | N/A (D1) | 孤立点检查 + 三值暴露枚举 |
| 3 | D1_E3 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A | N/A (D1) | core_collaborators 元数据（必需） |
| 4 | D1_E4 | ⬜ 未完成 | ✅ 可推广 | ✅ 可推广 | N/A (E4) | N/A (D1) | degree+1 值暴露枚举 |
| 5 | D1_E5 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A (E5) | N/A (D1) | 简单二元暴露枚举 |
| 6 | D2_E1 | ✅ POINT 已验证 (原有 D2/E1) | ✅ **已完成的基准** | ✅ **已完成的基准** | N/A (E1) | N/A (D2) | 无需额外修改 |
| 7 | D2_E2 | ✅ POINT 已验证 (test_a4: 186) | ✅ 可推广 | ✅ 可推广 | ⚠ 需处理 | N/A (D2) | 孤立点检查 |
| 8 | D2_E3 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A | N/A (D2) | core_collaborators 元数据（必需） |
| 9 | D2_E4 | ✅ D2+E4 已完成样板验证 (task3) | ✅ E4 exact_count 已实现 | ✅ E4 exact_count 已实现 | N/A (E4) | N/A (D2) | degree+1 值暴露枚举 + exact_count (非多数) |
| 10 | D2_E5 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A (E5) | N/A (D2) | 简单二元暴露枚举 |
| 11 | D3_E1 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A (E1) | N/A (D3) | TwoGroup 支持 + SupportEngine |
| 12 | D3_E2 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | ⚠ 需处理 | N/A (D3) | 孤立点检查 + TwoGroup 支持 |
| 13 | D3_E3 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A | N/A (D3) | core_collaborators 元数据（必需） |
| 14 | D3_E4 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A | N/A (D3) | degree+1 值暴露枚举 |
| 15 | D3_E5 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A (E5) | N/A (D3) | 简单二元暴露枚举 |
| 16 | D4_E1 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A (E1) | N/A (D4) | ClusterBernoulli 支持 |
| 17 | D4_E2 | ⬜ 未完成 | ⚠ 二阶暴露组合 | ⚠ 二阶暴露组合 | ⚠ 需处理 | N/A (D4) | 簇化 + 三分位；求解器需处理权重 |
| 18 | D4_E3 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A | N/A (D4) | core_collaborators 元数据（必需） |
| 19 | D4_E4 | ⬜ 未完成 | ✅ 可推广 | ✅ 可推广 | N/A (E4) | N/A (D4) | degree+1 值暴露枚举 |
| 20 | D4_E5 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A (E5) | N/A (D4) | ClusterBernoulli 支持 |
| 21 | D5_E1 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A (E1) | N/A (D5) | MultiGroup 支持 |
| 22 | D5_E2 | ⬜ 未完成 | ⚠ 二阶暴露组合 | ⚠ 二阶暴露组合 | ⚠ 需处理 | N/A (D5) | 多组 + 三分位 |
| 23 | D5_E3 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A | N/A (D5) | core_collaborators 元数据（必需） |
| 24 | D5_E4 | ⬜ 未完成 | ✅ 可推广 | ✅ 可推广 | N/A (E4) | N/A (D5) | degree+1 值暴露枚举 |
| 25 | D5_E5 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A (E5) | N/A (D5) | MultiGroup 支持 |
| 26 | D6_E1 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A (E1) | ⚠ A5 准入先决 | 先运行 two_stage_a5.py 检查 |
| 27 | D6_E2 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | ⚠ 需处理 | ⚠ A5 准入先决 | 先检查 + 孤立点处理 |
| 28 | D6_E3 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A | ⚠ A5 准入先决 | core_collaborators 元数据（必需） |
| 29 | D6_E4 | ⬜ 未完成 | ✅ 可推广 | ✅ 可推广 | N/A (E4) | ⚠ A5 准入先决 | degree+1 值暴露枚举 |
| 30 | D6_E5 | ⬜ 未完成 | ✅ 可取 | ✅ 可取 | N/A (E5) | ⚠ A5 准入先决 | 先运行 two_stage_a5.py |

---

## 检查表图例

**起始状态**：
- ✅ = 已有 `test_a4_shadow_integration.py` 的 arm support 验证通过
- ⬜ = 未在现有测试中出现

**可行判断**：
- ✅ 可推广 = 数学模式与已有已验证组合相同
- ✅ 可取 = 求解器技术路线明确，可立即实施
- ⚠ = 存在额外条件（孤立点 / A5准入 / 多值暴露）需要特别处理

**目标 A（单政策均值界）**：
- 求解路径：`validate_model → _enumerate_cells → _compute_support → _build_mean_bounds → _compute_interval`
- 对每个设计，`SupportEngine.evaluate()` 提供支持概率
- 对每个暴露，`exposure.classify()` 确定暴露值

**目标 B（两政策对比界）**：
- 求解路径：`validate_pair → _enumerate_cells → _compute_support → _coefficients → _solve_contrast`
- signed-box 优化，共享均值集合下求解差异

**E2 孤立点**：
- E2 (`three_level_treated_neighbor_fraction`) 在 degree=0 时无定义
- 处理方式：要么拒绝此组合，要么将孤立点的暴露视为 N/A
- 实际策略：包含孤立点的网络 + E2 → 需要设计后备方案

**D6 两阶段**：
- D6 需要先检查 A5 profile exclusion assumption
- `two_stage_a5.py` 提供了 `check_exclusion` 或等效接口
- 完成 A5 检查后才能进入 PARTIAL 求解流程

---

## 实施顺序建议

按依赖关系分组：

### Phase A：核基（D1-3 × E1-5, D2 × E1-5 已验证）
1. D2_E1（基准完成）— 不需要修改
2. D1_E1 → D2_E1 的推广（验证支持概率公式替换为 SupportEngine）
3. D3_E1（TwoGroup 设计）
4. D2_E2（E2 三分位暴露扩展）
5. D2_E5（简单 E5 暴露扩展）
6. D2_E3（E3 值域扩展）
7. D1_E2–E5（D1 × 全部暴露）
8. D3_E2–E5（D3 × 全部暴露）

### Phase B：高级设计（D4-5 × E1-5）
9. D4_E1（簇伯努利 × 严格多数）
10. D4_E5（簇伯努利 × 至少一个）
11. D4_E3（簇伯努利 × 精确计数）
12. D5_E1（多组配额 × 严格多数）
13. D5_E5（多组配额 × 至少一个）
14. D4-E4（簇伯努利 × 核心合作者多数）
15. D4_E2 / D5_E2（与三分位结合的复杂组合）

### Phase C：两阶段设计（D6 × E1-5）
16. D6_E1（先运行 two_stage_a5.py 检查）
17. D6_E5（两阶段 × 至少一个）
18. D6_E3（两阶段 × 精确计数）
19. D6_E3（两阶段 × 核心合作者多数）
20. D6_E2（两阶段 × 三分位）

### Phase D：E3 core_collaborators 所有组合
21-25. {D1,D2,D3,D4,D5,D6} × E3（需要 core_collaborators 元数据）

---

## 每组合的关键检查点

每个组合完成时需验证：

| 检查点 | 描述 | 验证方法 |
|--------|------|---------|
| 单元格枚举 | 枚举了所有合法 (n,a,e) 组合 | 与支持概率 >0 的单元格对比 |
| 支持概率正确 | 所有单元格支持概率正确 | 独立 verifier（N≤8）交叉验证 |
| 已知 A4 均在合法单元格中 | 声明的 A4 都是可实现的 | 在单元格集合中检查 |
| 无零概率已知 A4 | 已知 A4 单元格支持概率 >0 | verifier 检查 |
| 材料完整 | 政策单元格有已知 A4 或 bounds | 求解器完整性检查 |
| 区间可达 | lower ≤ upper | 证书证明 |
| sharp 性 | 端点可达 | primal/dual 证据 |
| 终点可验证 | replay 函数通过 | bounded_policy_verify/bounded_contrast_verify |

---

## 异常情形汇总

| 情形 | 处理方式 | 举例 |
|------|---------|------|
| 已知 A4 在不可实现单元格中 | `INCOMPATIBLE: A4_SIGNATURE_NOT_REALIZABLE` | D2/E1 中节点5的 (0,0) 但 node5 不在网络中 |
| 已知 A4 单元格支持概率为零 | `INCOMPATIBLE: A4_CONDITIONAL_EVENT_HAS_ZERO_PROBABILITY` | D2 中 (n, 1, 1) 但 m=0 |
| 政策目标单元格缺已知 A4 | `NEEDS_INPUT: SUPPORTED_TARGET_A4_MEAN_MISSING` | 政策单元格没有 A4 且 bounds 未包含 |
| E2 孤立点 | 需在枚举前预检查 | degree=0 时 E2 未定义 |
| 模型矛盾（不可行） | `INCOMPATIBLE: MODEL_INCOMPATIBLE` | 节点 n 声明了 (a,0) < (a,1) 但 bounds 相反 |
| D6 准入未通过 | 在 A5 check 阶段即返回 | two_stage_a5.check_exclusion 未通过 |