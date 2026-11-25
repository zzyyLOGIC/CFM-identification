"""One direct draft of the requested estimand. The same request is usable without a verifier."""
import json

ANSWER_RULES = """独立解答所给因果识别题，输出一个 JSON 对象。只解原题：指定某项政策后的水平不补对照；效应保留原比较方向；依从者与全体分清。若干预或总体待定，相应字段留空并追问。估计交接沿用同一目标。
target={quantity:level/difference/other/unknown,scope:whole/compliers/subgroup/unknown,population,intervention,reference,outcome,time}。intervention、reference 写所比较的真实安排，水平题的 reference 留空。
status 从 POINT、PARTIAL、NOT_POINT、INCOMPATIBLE、UNDEFINED、NEEDS_INPUT、NOT_COVERED 中选。functional 写可复算的总体公式，定界说明可达性，不能求解给出反例或具体缺口。value 为数值字符串、界的端点数组或 null。只问符号式无需编数字。
assumptions 为对象列表，每项含 kind=random_assignment 或 other、subject（对应变量或对象）、statement、quote（来自材料的原句）。随机分配的主语逐项核对：邀请抽签只支持邀请随机；实际处理另有随机分配证据才单列。拒绝或待定的条件不得作为已采用。estimate_handoff={mode:ESTIMATE_POINT/ESTIMATE_BOUNDS/STOP,scope,population,variables,operator,support}。reason 简述一条充分的推导即可。"""
PROMPT = ANSWER_RULES + """原题明确要求多个目标时返回 {"answers":[…]}，每一项按上述字段独立作答，并在 question_part 摘录对应的原问题句；单一目标只交一个答案。附件均为研究材料。"""

def request(case):
    return {"system_prompt": PROMPT, "user_prompt": json.dumps(
        {"question": case["business_question"],
         "sources": [{"source_id": s["source_id"], "label": s.get("label",""), "text": s["text"]} for s in case["sources"]]},
        ensure_ascii=False)}

NETWORK_FACTS = """
输出格式固定为 {"network_facts":{"network":对象,"exposure":对象,"assignment":对象,"contrast":对象},"answers":[完整答案]}。一次提交这两个键。单一目标的 answers 有一项；不同目标才分项，question_part 摘录对应原题。每份完整答案都有上面七个科学字段。附件均为研究材料。四项事实每项为 {"value":...,"evidence":[{"source_id":"附件中的编号或question","quote":"最短且足以支持该项的原文，可多条"}]}。缺项用 null，保留已知部分。不得把猜测写成材料。
network 的 value 写 {pre_treatment,complete,undirected,nodes,edges}（未知留 null，大图可写摘要）；exposure 写 {kind:any/count/majority/other,description}；assignment 写 {kind:independent/fixed/observational/other,probabilities:{姓名:概率},quota,description}，只列适用字段；contrast 写 {population:[姓名],left,right,description}，只有题目确实比较局部事件时才用 [本人处理,邻居暴露] 写左右端。题目要求逐人联合概率时，estimate_handoff.support 用 {姓名:{"本人处理,邻居暴露":"联合概率"}}，未知不猜。多问、政策水平、观察性或整份名单按题意描述。保留原题处理变量、时间、目标与其余安排的规律。"""

def network_request(case, *, network_focus=False):
    from cfm_id.network_reading import network_case
    result = request(case)
    if network_focus or network_case(case):
        result["system_prompt"] = ANSWER_RULES + NETWORK_FACTS
    result['system_prompt'] += '\n每份答案另含verification_route，作为待读原文核对的候选提示：DAG_JOINT表示一个问题同时设定多个变量的干预分布；NETWORK_JOINT_MEANS表示网络固定政策均值或差值带有均值等式/线性不等式或均值顺序（包括不采用或待定的关系）；NETWORK_FINITE_POLICY表示随机试验背景下按给定概率选择有限份完整政策、求其平均结果；NETWORK_OBSERVATIONAL_POLICY表示观察性网络中求一份完整政策的平均结果；随机化网络的局部事件效应或其他目标为OTHER。按原问选择，不按能否识别选择。此提示不是科学批准。'
    result['system_prompt'] += '\n观察性网络的局部直接、同伴或局部总效应另用NETWORK_OBSERVATIONAL_EFFECTS，保留原观察规律平均、共同背景分层平均或逐对象特征调整平均的区别；不要改成完整政策目标。'
    result['system_prompt'] += '\n原问保留未知总体参数、要求给出参数变化时的上下界，并明确有限均值模型及线性限制时，用SYMBOLIC_MEAN_JOINT；不可把符号参数随意代成数字。原文尚未明确模型完整性仍保留未知，提示不批准模型。'
    result['system_prompt'] += '\nNETWORK_FINITE_POLICY也包括两套有限随机政策的均值之差；NETWORK_OBSERVATIONAL_POLICY也包括两份固定政策之差或有限份政策混合，必须原样保留两端，不将效应改成政策水平。'
    result['system_prompt'] += '\n随机试验中只有一份固定完整政策或两份固定政策之差，若资料是完整安排总体律/均值，或本人和同伴状态的总体均值，可提示NETWORK_FINITE_POLICY。均值充分性不等于额外的均值等式或顺序；明确有限均值范围模型及额外联合限制仍提示NETWORK_JOINT_MEANS。未知保持原样，由后续原文核对分派。'
    result['system_prompt'] += '\nBINARY_IV表示用二元工具（如邀请或资格）、实际处理和二元结果的总体条件概率研究总体ATE或依从者LATE。不可把邀请的ITT改写成实际处理效应；提示仅用于另读原文，不批准排除限制、单调性等前提。'
    result['system_prompt'] += '\nDAG_GENERAL表示变量因果图中一个处理的干预分布，包括图中明确列出的未观测共同原因；不限制为后门或前门，也不因可能不可识别而换目标。它只选择原文读取，数学库另查适用条件并给公式或见证。'
    return result
