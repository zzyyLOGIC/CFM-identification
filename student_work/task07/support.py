"""Task 07 的 query-specific population support：D3 × E1。

分配设计 D3（两组分别固定 treated 名额）
----------------------------------------
处理前把全部单位划分成两个互不重叠的组 ``B1`` 与 ``B2``。
独立且均匀地：从 ``B1`` 抽恰好 ``m1`` 个 treated，从 ``B2`` 抽恰好 ``m2`` 个 treated。
网络边可以跨两组。由此得到的完整分配律为：

    q(t) = 1 / ( C(|B1|, m1) * C(|B2|, m2) )   若 sum_{i in B1} t_i = m1
                                                且 sum_{i in B2} t_i = m2
         = 0                                   否则

暴露定义 E1（严格多数）
----------------------------------------
对节点 ``i``，邻居集合为 ``N(i)``，度数 ``d_i = |N(i)|``：

    K_i(t) = sum_{j in N(i)} t_j,        S_i(t) = 1{ K_i(t) > floor(d_i / 2) }.

多数标签只是 target 的分组标准化，*不是* 声称它构成充分的暴露映射。

本模块返回什么
------------------------
对每个节点 ``i`` 与每个 arm ``(t, s) ∈ {0,1} × {0,1}``，返回

    pi_i(t, s) = P( T_i = t, S_i = s | A, X )

结果以 ``fractions.Fraction`` **精确** 表示。实现与图规模无关：
既不写死任何节点，也不写死 ``N = 300``。
"""
from __future__ import annotations

from fractions import Fraction
from math import comb
from typing import Dict, Iterable, Sequence, Tuple


def hypergeometric_pmf(population: int, successes: int, draws: int, observed: int) -> Fraction:
    """超几何分布精确 pmf：P(X = observed)，其中 X ~ Hypergeometric(N, K, n)。"""
    if draws < 0 or observed < 0:
        return Fraction(0)
    if observed > draws or observed > successes:
        return Fraction(0)
    if draws - observed > population - successes:
        return Fraction(0)
    return Fraction(
        comb(successes, observed) * comb(population - successes, draws - observed),
        comb(population, draws),
    )


class TwoGroupQuotaDesign:
    """处理前固定网络，加上 D3 的两组固定名额分配律。"""

    def __init__(
        self,
        node_ids: Sequence[str],
        undirected_edges: Iterable[Tuple[str, str]],
        group1: Iterable[str],
        group2: Iterable[str],
        m1: int,
        m2: int,
    ) -> None:
        nodes = tuple(node_ids)
        if not nodes:
            raise ValueError("node_ids must be nonempty")
        if len(set(nodes)) != len(nodes):
            raise ValueError("node_ids must be unique")
        self._node_ids = nodes
        self._index = {node: position for position, node in enumerate(nodes)}

        canonical: list = []
        seen = set()
        for left, right in undirected_edges:
            if left not in self._index or right not in self._index:
                raise ValueError(f"edge endpoint {left!r}/{right!r} is not a declared node")
            if left == right:
                raise ValueError("self-loops are not allowed")
            edge = (left, right) if self._index[left] < self._index[right] else (right, left)
            if edge in seen:
                raise ValueError(f"duplicate undirected edge {edge}")
            seen.add(edge)
            canonical.append(edge)
        canonical.sort(key=lambda pair: (self._index[pair[0]], self._index[pair[1]]))
        self._edges = tuple(canonical)

        neighbours: Dict[str, list] = {node: [] for node in nodes}
        for left, right in self._edges:
            neighbours[left].append(right)
            neighbours[right].append(left)
        for node in neighbours:
            neighbours[node].sort(key=self._index.__getitem__)
        self._neighbours = {node: tuple(items) for node, items in neighbours.items()}

        group1 = tuple(group1)
        group2 = tuple(group2)
        if not group1 or not group2:
            raise ValueError("both groups must be nonempty")
        if set(group1) & set(group2):
            raise ValueError("the two groups must be disjoint")
        if set(group1) | set(group2) != set(nodes):
            raise ValueError("the two groups must partition all node_ids")
        if len(set(group1)) != len(group1):
            raise ValueError("group1 must not contain duplicates")
        if len(set(group2)) != len(group2):
            raise ValueError("group2 must not contain duplicates")
        self._group1 = group1
        self._group2 = group2
        self._group_of = {node: 1 for node in group1}
        self._group_of.update({node: 2 for node in group2})

        if not isinstance(m1, int) or not isinstance(m2, int) or isinstance(m1, bool) or isinstance(m2, bool):
            raise ValueError("m1 and m2 must be integers")
        if not 0 <= m1 <= len(group1):
            raise ValueError(f"m1={m1} is infeasible for a group of size {len(group1)}")
        if not 0 <= m2 <= len(group2):
            raise ValueError(f"m2={m2} is infeasible for a group of size {len(group2)}")
        self._m1 = m1
        self._m2 = m2

    # -- 基本访问器 --------------------------------------------------------
    @property
    def node_ids(self) -> Tuple[str, ...]:
        return self._node_ids

    @property
    def group1(self) -> Tuple[str, ...]:
        return self._group1

    @property
    def group2(self) -> Tuple[str, ...]:
        return self._group2

    @property
    def m1(self) -> int:
        return self._m1

    @property
    def m2(self) -> int:
        return self._m2

    def group_of(self, node: str) -> int:
        self._require_node(node)
        return self._group_of[node]

    def neighbours(self, node: str) -> Tuple[str, ...]:
        self._require_node(node)
        return self._neighbours[node]

    def degree(self, node: str) -> int:
        return len(self.neighbours(node))

    def _require_node(self, node: str) -> None:
        if node not in self._index:
            raise ValueError(f"unknown node {node!r}")

    def _quota(self, node: str) -> Tuple[int, int, int]:
        """返回 ``node`` 的 (本组人数, 本组名额, 另一组名额)。"""
        if self._group_of[node] == 1:
            return len(self._group1), self._m1, self._m2
        return len(self._group2), self._m2, self._m1

    # -- 分布计算部分 ------------------------------------------------------
    def own_treatment_probability(self, node: str, t: int) -> Fraction:
        """D3 设计下 P(T_i = t | A, X)。"""
        self._require_node(node)
        if t not in (0, 1):
            raise ValueError("own treatment must be 0 or 1")
        own_size, own_quota, _ = self._quota(node)
        remaining = own_quota - t
        if remaining < 0 or remaining > own_size - 1:
            return Fraction(0)
        return Fraction(comb(own_size - 1, remaining), comb(own_size, own_quota))

    def _neighbour_group_counts(self, node: str) -> Tuple[int, int]:
        """(节点的本组邻居数, 另一组邻居数)。"""
        group_id = self._group_of[node]
        own = other = 0
        for neighbour in self._neighbours[node]:
            if self._group_of[neighbour] == group_id:
                own += 1
            else:
                other += 1
        return own, other

    def conditional_count_distribution(self, node: str, t: int) -> Dict[int, Fraction]:
        """P(K_i = k | T_i = t, A, X)，其中 k = 0 .. degree(node)。

        只有在事件 {T_i = t} 具有正概率时条件分布才有定义；
        否则抛出 ``ValueError``，而不是静默返回一个空分布。
        """
        self._require_node(node)
        if t not in (0, 1):
            raise ValueError("own treatment must be 0 or 1")
        if self.own_treatment_probability(node, t) == 0:
            raise ValueError(
                f"cannot condition on T_{node}={t}: it has zero probability under this design"
            )
        own_size, own_quota, other_quota = self._quota(node)
        other_size = len(self._group2) if self._group_of[node] == 1 else len(self._group1)
        draws_own, draws_other = self._neighbour_group_counts(node)

        # 本组邻居中签数：总体 n_g-1、成功 m_g-t、抽取 d_own
        own_pmf = [
            hypergeometric_pmf(own_size - 1, own_quota - t, draws_own, k)
            for k in range(draws_own + 1)
        ]
        # 另一组邻居中签数：总体 n_oth、成功 m_oth、抽取 d_oth
        other_pmf = [
            hypergeometric_pmf(other_size, other_quota, draws_other, k)
            for k in range(draws_other + 1)
        ]

        # 两组独立 -> 卷积
        distribution: Dict[int, Fraction] = {}
        for k_own, p_own in enumerate(own_pmf):
            if p_own == 0:
                continue
            for k_other, p_other in enumerate(other_pmf):
                if p_other == 0:
                    continue
                key = k_own + k_other
                distribution[key] = distribution.get(key, Fraction(0)) + p_own * p_other
        return distribution

    # -- 真正的 support 计算 -----------------------------------------------
    def support(self, node: str, t: int, s: int) -> Fraction:
        """pi_i(t, s) = P(T_i = t, S_i = s | A, X)，E1 严格多数暴露。"""
        self._require_node(node)
        if t not in (0, 1) or s not in (0, 1):
            raise ValueError("query (t, s) must have t in {0,1} and s in {0,1}")
        probability = self.own_treatment_probability(node, t)
        if probability == 0:
            return Fraction(0)
        degree = self.degree(node)
        mass = Fraction(0)
        for count, count_probability in self.conditional_count_distribution(node, t).items():
            if int(count > degree // 2) == s:
                mass += count_probability
        return probability * mass

    def support_table(self, node: str) -> Dict[Tuple[int, int], Fraction]:
        """``node`` 的全部四个 E1 arm，形如 {(t, s): pi_i(t, s)}。"""
        return {(t, s): self.support(node, t, s) for t in (0, 1) for s in (0, 1)}

    def supported_arms(self, node: str) -> Tuple[Tuple[int, int], ...]:
        """支持严格为正的 arm，按固定顺序排列。"""
        return tuple(
            arm
            for arm in ((t, s) for t in (0, 1) for s in (0, 1))
            if self.support(node, *arm) > 0
        )


def support(design: TwoGroupQuotaDesign, node: str, t: int, s: int) -> Fraction:
    """模块级别名，等价于 :meth:`TwoGroupQuotaDesign.support`。"""
    return design.support(node, t, s)


def support_table(design: TwoGroupQuotaDesign, node: str) -> Dict[Tuple[int, int], Fraction]:
    """模块级别名，等价于 :meth:`TwoGroupQuotaDesign.support_table`。"""
    return design.support_table(node)


def supported_arms(design: TwoGroupQuotaDesign, node: str) -> Tuple[Tuple[int, int], ...]:
    """模块级别名，等价于 :meth:`TwoGroupQuotaDesign.supported_arms`。"""
    return design.supported_arms(node)


def legal_assignment_count(design: TwoGroupQuotaDesign) -> int:
    """合法完整分配的个数：C(|B1|, m1) * C(|B2|, m2)。"""
    return comb(len(design.group1), design.m1) * comb(len(design.group2), design.m2)


def assignment_probability(design: TwoGroupQuotaDesign, assignment) -> Fraction:
    """D3 的完整分配律 ``q(t)``。

    ``assignment`` 既可以是映射 ``{节点: 0/1}``，也可以是和 ``design.node_ids``
    对齐的序列。当 ``B1`` 与 ``B2`` 的 treated 数分别等于 ``m1``、``m2`` 时返回
    ``1 / [C(|B1|,m1) C(|B2|,m2)]``，否则返回 ``0``。
    """
    if isinstance(assignment, dict):
        values = [assignment[node] for node in design.node_ids]
    else:
        values = list(assignment)
        if len(values) != len(design.node_ids):
            raise ValueError("assignment length must match node_ids")
    if any(value not in (0, 1) for value in values):
        raise ValueError("assignment entries must be 0 or 1")
    index = {node: position for position, node in enumerate(design.node_ids)}
    if sum(values[index[node]] for node in design.group1) != design.m1:
        return Fraction(0)
    if sum(values[index[node]] for node in design.group2) != design.m2:
        return Fraction(0)
    return Fraction(1, legal_assignment_count(design))
