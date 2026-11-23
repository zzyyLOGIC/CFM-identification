"""Expose established native reading and scientific decisions to the compact user interface."""
from .business_dispatch import QUERY_DECISIONS, PLAN_DECISIONS
from .dag_backdoor_contract import DECISIONS as GRAPH
from .iv_route_contract import READING_DECISIONS as IV_READING
from . import network_policy_dispatch as policy
from . import network_effect_dispatch as effect

LOCAL_CONTRAST = "DESIGN_CONDITIONAL_LOCAL_CONTRAST"
FULL_POLICY = "FULL_ASSIGNMENT_POLICY_MEAN"
EXPOSURE_POLICY = "EXPOSURE_SUFFICIENT_POLICY_MEAN"
LEGACY_NETWORK_METHODS = {"R1a": LOCAL_CONTRAST, "R1b": FULL_POLICY, "R2": EXPOSURE_POLICY}

def method_name(identifier):
    """Historical identifiers remain valid inside already bound review records."""
    return LEGACY_NETWORK_METHODS.get(identifier, identifier)

IV_SCIENCE={
    "instrument_independence":"iv_independence","exclusion_restriction":"exclusion",
    "monotonicity_direction":"monotonicity","no_interference":"no_interference",
    "positive_instrument_support":"instrument_support","consistency_and_binary_outcome":"consistency",
}
LABELS={
    "business_target_and_population":"研究对象、干预目标与人群",
    "research_structure":"研究设计、变量角色和资料结构",
    "source_entailment":"原文支持规格中的每一项声明，包括取值与方向",
    "selected_query_matches_native_target":"所选研究问题与方法使用的目标一致",
    "complete_model_and_constraints_preserved":"所有相关模型限制、否定和未知均已核对",
    "method_requests_and_projections_preserved":"各候选方法使用的变量和信息投影符合原问题",
    "target_and_variable_roles":"干预、结果、层次和取值已逐项核对",
    "complete_causal_graph_and_latents":"全部有向边、双向边和未测共同原因均已核对",
    "recursive_scm_and_perfect_intervention":"采纳所述无环模型、误差结构与指定的完全干预",
    "population_law_and_strict_positivity":"确认目标总体联合律及分层正性",
    "target_and_variable_coding":"IV目标人群、方向及Z、D、Y的二元编码",
    "complete_observed_conditional_law":"核对两层条件律的8个坐标、精确数值及来源",
    "source_and_population_scope":"条件概率表覆盖所述工具试验的目标总体",
    "consistency_and_binary_outcome":"确认一致性、二元结果及其潜在状态的解释",
    "target_policy_population_and_weights":"政策名单、单位、顺序及权重",
    "network_assignment_and_variable_meaning":"固定网络、原分配律和变量含义",
    "all_information_and_restrictions_preserved":"总体信息及采用、未采用和待定条件完整",
    "known_assignment_law":"确认完整原分配律及其参数",
    "full_vector_randomization":"完整名单独立于所有相关潜在结果",
    "fixed_pretreatment_network":"网络为处理前固定网络",
    "finite_conditional_first_moments":"本题所需条件均值有限",
    "mean_sufficiency_all_assignments_and_weighted_nodes":"各正权单位在全部安排上同一暴露标签的潜在均值相等",
    "local_states_and_first_minus_second_direction":"局部两臂及第一端减第二端的方向",
    "evaluation_population_fixed_before_assignment_and_weights":"评价人群与权重在分配前固定",
    "remaining_assignments_follow_original_conditional_design":"其余单位按原设计的条件分配平均",
    "native_symbols_match_business_variables_and_context":"数学符号与实际处理、结果及时间一致",
    "a4_operator_scope_and_provenance":"局部臂总体算子、来源与覆盖范围",
}

def reading_items(method, spec):
    identifier = method
    method = method_name(method)
    keys=[*QUERY_DECISIONS,*PLAN_DECISIONS]
    if method in ("BACKDOOR","GENERAL_ID"):
        keys.extend(GRAPH)
    elif method.startswith("IV_"):
        keys.extend((*IV_READING,"consistency_and_binary_outcome"))
    elif method==LOCAL_CONTRAST:
        keys.extend((*effect.READING_DECISIONS,*effect.SCIENCE_DECISIONS))
    else:
        keys.extend((*policy.READING_DECISIONS,*policy.BASE_CONDITIONS))
        if method==EXPOSURE_POLICY:
            keys.extend(policy.R2_SCIENCE_DECISIONS)
    labels={"review_"+k:LABELS.get(k,k) for k in keys if k!="consistency"}
    if method in (LOCAL_CONTRAST,FULL_POLICY,EXPOSURE_POLICY):
        rows=spec.network.full if method==FULL_POLICY else spec.network.local
        for row in rows:
            coord=str(row["z"]) if method==FULL_POLICY else str((row["own"],row["peer"]))
            labels[identifier+"_source_"+coord]="核对 "+coord+" 所给各单位总体均值、顺序、权重与原文"
    return labels

def external_scope(method, spec):
    if method_name(method)!=LOCAL_CONTRAST:
        return None
    n=spec.network
    if n.design!="independent" or n.exposure!="majority":
        return "EXTERNAL_EFFECT_DESIGN_NOT_CONNECTED"
    if not {(a,e) for a in (0,1) for e in (0,1)}<={(r["own"],r["peer"]) for r in n.local}:
        return "EXTERNAL_EFFECT_FULL_BATCH_INFORMATION_REQUIRED"
    return None
