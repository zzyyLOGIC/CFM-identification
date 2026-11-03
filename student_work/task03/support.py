from itertools import product
"""Task03 (D1* E3) population support calculation"""
from math import isfinite

def assignment_probability(treatment,p):
    prob = 1.0
    for j ,t_j in enumerate(treatment):
        prob *= p[j] if t_j ==1 else (1-p[j])
    return prob

def validate_setting(setting):
    """检查网络,概率和核心伙伴集合是否合法"""
    adjacency = setting["adjacency"]
    probabilities = setting["probabilities"]
    core_sets = setting["core_sets"]

    n = len(probabilities)
    if n == 0:
        raise ValueError("至少需要一个节点")
    if len(adjacency) != n:
        raise ValueError("adjacency 的行数必须等于节点数")
    if len(core_sets) != n:
        raise ValueError("每个节点都必须有一个 core set")
    for i ,p_i in enumerate(probabilities):
        if not isinstance(p_i,(int,float)) or not isfinite(p_i):
            raise ValueError(f"p[{i}必须是有限数值]")
        if not 0 <= p_i <=1:
            raise ValueError(f"p[{i}]必须位于[0,1]")

    for i,row in enumerate(adjacency):
        if len(row) != n:
            raise ValueError("adjacency 必须是n*n")
        if row[i] != 0:
            raise ValueError("网络不能包含self-loop")
        for value in row:
            if value not in (0,1,False,True):
                raise ValueError("adjacency 只能包含0/1")

    for i ,core_set in enumerate(core_sets):
        if len(core_set) == 0:
            raise ValueError(f"节点{i}的核心伙伴集合不能为空")
        if len(set(core_set)) != len(core_set):
            raise ValueError(f"节点{i}的核心伙伴不能重复")
        for j in core_set:
            if not isinstance(j,int) or not 0<=j<n:
                raise ValueError(f"节点{i}的核心伙伴编号{j}非法")
            if j== i :
                raise ValueError(f"节点{i}不能把自己作为核心伙伴")
            if not adjacency[i][j]:
                raise ValueError(
                    f"节点{j}不是节点{i}的网络邻居，不能放进C_{i}"
                )

def exposure_for_node(treatment,core_set):
    h = len(core_set)
    treated_count = sum(treatment[j] for j in core_set)
    return int( treated_count > h//2)

def possion_binomial_pmf(probabilities):
    """
    返回不同bernoulli概率之和的概率质量函数
    返回值 pmf[k]表示恰好k人接受treatment的概率
    """
    pmf = [1.0]
    for probability in probabilities:
        updated = [0.0]* (len(pmf)+1)
        for treated_count,old_probability in enumerate(pmf):
            updated[treated_count] += old_probability * (1 - probability)
            updated[treated_count + 1] += old_probability * probability
        pmf = updated

    return pmf

def node_support(node_id,probabilities,core_set):
    """计算一个节点四个(T_i,S_i)arm的总体概率。"""
    core_probabilities = [probabilities[j] for j in core_set]
    pmf = possion_binomial_pmf(core_probabilities)
    threshold = len(core_set) //2 + 1
    exposure_zero_probability = sum(pmf[:threshold])
    exposure_one_probability = sum(pmf[threshold:])

    own_zero_probability = 1 - probabilities[node_id]
    own_one_probability = probabilities[node_id]
    return {
        (0,0): own_zero_probability * exposure_zero_probability,
        (0,1): own_zero_probability * exposure_one_probability,
        (1,0): own_one_probability * exposure_zero_probability,
        (1,1): own_one_probability * exposure_one_probability,
    }

def compute_support(setting):
    """计算所有节点的query-specific population support"""
    validate_setting(setting)
    probabilities = setting["probabilities"]
    core_sets = setting["core_sets"]
    support = {}
    for node_id , core_set in enumerate(core_sets):
        support[node_id] = node_support(
            node_id = node_id,
            probabilities= probabilities,
            core_set = core_set,
        )
    return support

if __name__ == "__main__":

    probabilities = [0.5,0.5,0.5]
    result = possion_binomial_pmf(probabilities)
    print(probabilities)
    print("result:")
    print(result)


    n = 4
    p = [0.1,0.2,0.4,0.3]
    i = 0
    core_set_i = [0,1,2]
    support = {(0,0):0.0, (0,1):0.0, (1,0):0.0,(1,1):0.0}
    for treatment in product([0,1], repeat = n):
        # print(treatment)
        prob = assignment_probability(treatment,p)
        t_i = treatment[i]
        s_i = exposure_for_node(treatment,core_set_i)
        if prob <=0:
            print((t_i,s_i))
        else:
            support[(t_i,s_i)] += prob
    print("support:")
    for (ti, si), val in support.items():
        print(f"({ti}, {si}): {val:.3f}")

    # 校验总和
    total = sum(support.values())
    print(f"\n总概率 = {total:.3f}")
