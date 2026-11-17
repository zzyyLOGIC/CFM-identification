from support import (
    calculate_support
)

from rule import identify_arm

from itertools import combinations
from math import floor



graph = {
    1:[2,3,4],
    2:[1],
    3:[1],
    4:[1]
}



# =================================
# Test 1: normal support case
# =================================

result = calculate_support(
    graph,
    2,
    1
)


print("normal case:")
print(result)


# probabilities sum to 1

assert abs(sum(result.values()) - 1) < 1e-10



# =================================
# Test 2: illegal parameter
# =================================

try:

    calculate_support(
        graph,
        5,
        1
    )

    assert False


except ValueError:

    print("illegal parameter test passed")



# =================================
# Test 3: zero-support in support.py
# =================================

zero_result = calculate_support(
    graph,
    1,
    1
)


print("zero support case:")
print(zero_result)


assert zero_result[(1,1)] == 0


print("zero-support test passed")



# =================================
# Test 4: brute-force comparison
# =================================

def brute_force(graph, m, node):

    nodes = list(graph.keys())


    count = {
        (1,1):0,
        (1,0):0,
        (0,1):0,
        (0,0):0
    }


    total = 0


    for group in combinations(nodes,m):

        assignment = {}


        for n in nodes:

            if n in group:
                assignment[n]=1
            else:
                assignment[n]=0



        # independent calculation of arm

        T_i = assignment[node]


        neighbors = graph[node]


        K = 0

        for j in neighbors:
            K += assignment[j]


        d = len(neighbors)


        S_i = 1 if K > floor(d/2) else 0


        arm=(T_i,S_i)


        count[arm]+=1

        total+=1



    return {
        arm:c/total
        for arm,c in count.items()
    }



brute_result = brute_force(
    graph,
    2,
    1
)


print("brute force:")
print(brute_result)

for arm in result:

    assert abs(
        result[arm]-brute_result[arm]
    ) < 1e-10

print("brute-force test passed")



# =================================
# Test 5: rule.py POINT identification
# =================================

point_result = identify_arm(
    result,
    1,
    0
)


print("POINT result:")
print(point_result)


assert point_result["status"] == "POINT"



# =================================
# Test 6: rule.py reject zero support
# =================================

reject_result = identify_arm(
    zero_result,
    1,
    1
)


print("reject result:")
print(reject_result)


assert reject_result["status"] == "NOT IDENTIFIED"



print("all tests passed")