"""Task03 identification rule."""
from support import compute_support

REQUIRED_ASSUMPTIONS = (
    "fixed_pretreatment_network",
    "fixed_pretreatment_core_sets",
    "known_assignment_law",
    "full_vector_randomization",
    "consistency",
    "finite_conditional_first_moments",
)

def identify_task(setting,tolerance=1e-12):
    assumptions = setting.get("assumptions",{})
    missing_assumptions = [
        name
        for name in REQUIRED_ASSUMPTIONS
        if assumptions.get(name) is not True
    ]
    if missing_assumptions:
        return {
            "status":"NEEDS_INPUT",
            "missing_assumptions":missing_assumptions,
            "support":None
        }
    

    support = compute_support(setting)
    missing_support = []
    for node_id ,arms in support.items():
        for arm, probability in arms.items():
            if probability <= tolerance:
                missing_support.append(
                    {
                        "node_id":node_id,
                        "arm":arm,
                        "probability":probability,
                    }
                )

    if missing_support:
        return {
            "status": "UNSUPPORTED",
            "reason": (
                "至少有一个 arm 的 support 为 0；对应条件事件不会发生，"
                "因此 E[Y_i_obs | A, X, T_i=t, S_i=s] 没有定义。"
            ),
            "missing_support": missing_support,
            "support":support
        }
    return {
        "status":"POINT",
        "identified_arms": [(0,0),(0,1),(1,0),(1,1)],
        "functional":(
            "mu_i(t,s) = "
            "E[Y_i_obs | A, X,T_i = t,S_i = s]"
        ),
        "support":support,
        "assumptions_used": list(REQUIRED_ASSUMPTIONS),
    }
