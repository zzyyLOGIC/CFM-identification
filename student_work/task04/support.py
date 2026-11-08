"""
support.py

Calculate pi_i(t,s) under D2 assignment and E1 exposure.

D2:
Exactly m nodes receive treatment.

E1:
S_i(t)=1{K_i(t)>floor(d_i/2)}
"""

from itertools import combinations
from math import floor



def generate_assignments(nodes, m):
    """
    Generate all valid treatment assignments.

    Exactly m nodes are treated.
    """

    if m < 0 or m > len(nodes):
        raise ValueError(
            "m must be between 0 and number of nodes"
        )


    assignments = []


    # choose m treated nodes
    for group in combinations(nodes, m):

        assignment = {}

        for node in nodes:

            if node in group:
                assignment[node] = 1
            else:
                assignment[node] = 0


        assignments.append(assignment)


    return assignments



def calculate_exposure(graph, assignment, node):
    """
    Calculate exposure status S_i(t).

    K_i(t)=sum(A_j), j in N(i)

    S_i(t)=1{K_i(t)>floor(d_i/2)}
    """

    neighbors = graph[node]


    # calculate K_i(t)
    K = 0

    for neighbor in neighbors:
        K += assignment[neighbor]


    # d_i=|N(i)|
    degree = len(neighbors)


    if K > floor(degree / 2):
        return 1

    else:
        return 0



def get_arm(graph, assignment, node):
    """
    Return joint arm:

    (T_i,S_i)
    """

    T_i = assignment[node]

    S_i = calculate_exposure(
        graph,
        assignment,
        node
    )


    return (T_i, S_i)



def calculate_support(graph, m, node):
    """
    Calculate pi_i(t,s).

    Return:

    {
        (1,1): probability,
        (1,0): probability,
        (0,1): probability,
        (0,0): probability
    }
    """

    nodes = list(graph.keys())


    assignments = generate_assignments(
        nodes,
        m
    )


    arm_count = {
        (1,1):0,
        (1,0):0,
        (0,1):0,
        (0,0):0
    }


    for assignment in assignments:

        arm = get_arm(
            graph,
            assignment,
            node
        )

        arm_count[arm] += 1



    total = len(assignments)


    if total == 0:
        raise ValueError(
            "No valid treatment assignment"
        )


    pi = {}

    for arm,count in arm_count.items():

        pi[arm] = count / total


    return pi