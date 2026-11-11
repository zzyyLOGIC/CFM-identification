from itertools import product

import pytest

from rule import identify_task
from support import (
    assignment_probability,
    compute_support,
    exposure_for_node
)

def normal_setting():
    return {
        "adjacency":[
            [0,1,1,1],
            [1,0,1,1],
            [1,1,0,1],
            [1,1,1,0],
        ],
        "probabilities":[0.2,0.4,0.6,0.8],
        "core_sets":[
            [1,2],
            [0,2],
            [0,1,3],
            [1,2],
        ],
        "assumptions":{
            "fixed_pretreatment_network":True,
            "fixed_pretreatment_core_sets":True,
            "known_assignment_law":True,
            "full_vector_randomization":True,
            "consistency":True,
            "finite_conditional_first_moments":True,
        },
    }

def brute_force_support(setting):
    probabilities = setting["probabilities"]
    core_sets = setting["core_sets"]
    n = len(probabilities)
    support = {
        i:{
            (0,0):0.0,
            (0,1):0.0,
            (1,0):0.0,
            (1,1):0.0
        }
        for i in range(n)
    }
    for treatment in product((0,1),repeat = n):
        probability = assignment_probability(treatment,probabilities)
        for node_id, core_set in enumerate(core_sets):
            exposure = exposure_for_node(treatment, core_set)
            arm = (treatment[node_id],exposure)
            support[node_id][arm] += probability
    return support

def test_normal_setting_is_point():
    result = identify_task(normal_setting())
    assert result["status"] == "POINT"
    assert result["identified_arms"] == [
        (0,0),
        (0,1),
        (1,0),
        (1,1),
    ]

def test_each_nodes_arm_probabilities_sum_to_one():
    support = compute_support(normal_setting())
    for arms in support.values():
        assert sum(arms.values()) == pytest.approx(1.0)
        assert all(probability > 0 for probability in arms.values())

def test_dynamic_programming_matches_brute_force():
    setting = normal_setting()
    calculated = compute_support(setting)  
    expected = brute_force_support(setting)
    for node_id in calculated:
        for arm in calculated[node_id]:
            assert calculated[node_id][arm] == pytest.approx(
                expected[node_id][arm]
            )

def test_zero_support_is_rejected():
    setting = normal_setting()
    setting["probabilities"] = [0.2,0.0,0.0,0.8]
    result = identify_task(setting)
    assert result["status"] == "UNSUPPORTED"
    missing = {
        (item["node_id"],item["arm"])
        for item in result["missing_support"]
    }
    assert (0,(0,1)) in missing
    assert (0,(1,1)) in missing

def test_zero_support_does_not_return_point_functional():
    setting = normal_setting()
    setting["probabilities"] = [0.2, 0.0, 0.0, 0.8]

    result = identify_task(setting)

    assert result["status"] == "UNSUPPORTED"
    assert "functional" not in result
    assert "条件事件不会发生" in result["reason"]

def test_missing_assumption_needs_input():
    setting = normal_setting()
    setting["assumptions"]["consistency"] = False
    result = identify_task(setting)
    assert result["status"] == "NEEDS_INPUT"   
    assert "consistency" in result["missing_assumptions"]

def test_core_set_cannot_contain_the_node_itself():
    setting = normal_setting()
    setting["core_sets"][0] = [0,1]
    with pytest.raises(ValueError,match = "不能把自己"):
        compute_support(setting)

def test_probability_outside_unit_interval_is_invalid():
    setting = normal_setting()
    setting["probabilities"][0] = 1.2
    with pytest.raises(ValueError,match =r"\[0,1\]" ):
        compute_support(setting)    

def test_treatment_zero_creates_zero_arms():
    setting = normal_setting()
    setting["probabilities"][0] = 0.0
    support = compute_support(setting)
    assert support[0][(1,0)] == pytest.approx(0.0)
    assert support[0][(1,1)] == pytest.approx(0.0)

def test_impossible_exposure_creates_zero_arms():
    setting =normal_setting()
    setting["probabilities"][1] = 0.0
    setting["probabilities"][2] = 0.0
    support = compute_support(setting)
    assert support[0][(0,1)] == pytest.approx(0.0)
    assert support[0][(1,1)] == pytest.approx(0.0)

def print_zero_support(setting):
    support = compute_support(setting)

    for node_id, arms in support.items():
        for arm, probability in arms.items():
            if probability <= 1e-12:
                print(
                    f"节点 {node_id} 的 arm {arm} "
                    f"support 为 0"
                )

if __name__ == "__main__":
    tests = [
        test_normal_setting_is_point,
        test_each_nodes_arm_probabilities_sum_to_one,
        test_dynamic_programming_matches_brute_force,
        test_zero_support_is_rejected,
        test_missing_assumption_needs_input,
        test_core_set_cannot_contain_the_node_itself,
        test_probability_outside_unit_interval_is_invalid,
        test_treatment_zero_creates_zero_arms,
        test_impossible_exposure_creates_zero_arms
    ]

    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")

    print(f"\n全部 {len(tests)} 个测试通过。")
    print_zero_support(normal_setting())
