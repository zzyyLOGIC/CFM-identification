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
    return result
