# 同一研究的多个局部问题

只读原文和附件，按给定 JSON 合同输出；不解题、不参考模型原答补资料，不批准科学前提。
输出直接是 Reading 对象，顶层为 family、study、network、design、exposure、targets、information、conditions、remaining、material_notes；不要把答案包在 reading_feedback_not_evidence 或 output_schema 里。前五项各含 value 和 evidence，分别保存字段值和原文引用。targets 和 information 是带引用对象的数组；每个数组元素的外层只能有 value、evidence 两项。每问的 question、kind、first、second、population、weights、fixed_before_assignment、remaining_assignment、same_outcome_and_context 全部放在该元素的 value 中，不能直接放在数组元素外层。evidence 不可省略，按 Citation 合同引用原文。conditions、remaining、material_notes 则按各自 schema 直接填写，不额外套 value。这里仅说明结构，实际内容必须来自原文。
共用研究对象、完整关系网、抽签设计、暴露定义、结果定义和时期只写一次。targets 按原问顺序完整保留，可以是一问，不要求编号。不同结果、时期、实验或固定政策问题不能硬改成同一局部目标；相应目标用 OTHER，并保留原问。

design保留整份名单怎样抽出的规则。“每家有一半机会”“各家分别抽签”只给各家的机会，不证明各家相互独立；本轮恰好开了几家也不证明固定名额。原文明确独立抽签才可填独立伯努利；只给边际概率而未交代联合规则时，design.value留null并保留原句，后续只追问实际抽签方式。完整名单与潜在结果独立属于科学前提，不能当作各对象间独立抽签的依据。

每问分别记录：评价名单 population、名单内精确权重 weights、第一端 first、第二端 second。MEAN没有第二端，CONTRAST为第一端减第二端。自己使用/不使用、同伴人数/比例状态不能互换。这里比较原设计下的本人和同伴状态，其余安排在原设计相应条件下平均；不是固定全网名单，也不自动要求暴露充分性。

逐问区分“本人的处理状态”和“这一问指定的同伴状态”。只说本人开与不开，不等于指定同伴状态为1；不能把另一问的限制或共同的状态编码定义当作本问限制。若本问的一端只给本人状态而未给同伴状态，first/second留null、原问完整保留，不能为了填满Arm而猜测。明确共同适用的限定或明确“反过来比较同一对情形”可以引用共同原句。已经明确按处理后结果选对象的目标也保留原问和fixed_before_assignment=false，不添两端，不改成处理前目标。

评价名单和计算暴露的关系网络不同：只评价某两家，不能删掉其余门店、关系或重新计算邻居人数。只有原文明示在处理前确定的名单与权重才填 fixed_before_assignment=true；处理后按业绩、实际使用或中签筛人填false；未说明null，不从“已给名单”推断。

权重可以来自文字或多个CSV附件，必须逐问引用适用的那份表。weights的键必须恰好是population，不参与本问的对象不放population。允许已明确的零权重；不可自动归一化、截断或补缺行。明确“这两家等权”可写各1/2；未说如何平均留null。完整名册权重表中明确零权重可排除于本问评价名单，但不得删出network。原文和表不一致完整保留并让审核指出冲突。不要把抽签概率或邻居权重当作评价权重。

information记录原材料真实提供的所有来源和覆盖，不随问题倒填格子。NODE_ARM_MEANS需要逐对象/本人/同伴格子；NODE_FULL_LAW是每个Y_i与完整T的总体律，FULL_JOINT_LAW才是全部Y与完整T联合。样本和样本均值必须FINITE_SAMPLE，不能因记录多而改为总体。总体信息可为符号，无需编造数值。same_scope是同一对象、结果、时期和背景，不是询问是否已能识别。来源覆盖可以少于目标，交原库检查。

conditions分别保存 randomization（完整分配与潜在结果独立）、consistency、fixed_network、finite_means；两阶段设计另存 first_stage_exclusion。每条有原文采用态度、适用范围及引用。covered_nodes只列原文明确适用的对象，all_assignments只在明确覆盖完整安排范围时为true，未知null；不能按目标名单补齐。只给抽签概率不是randomization科学许可；不要漏掉原文另行声明。ADOPTED采用，NOT_ADOPTED不采用，UNDECIDED待决定，UNKNOWN未说明，CONTRADICTED冲突。共同条件只在原文确实覆盖全部所问对象和安排时记录为共同采用，局部采用须完整保留范围，不扩大。

remaining保留专用字段尚不能表达的其他科学条件（包括采用、拒绝和待定）。不把“允许干扰”、数据说明、未知权重重复变成额外假设；明确的均值顺序、无干扰或个体单调性则不能丢。UNKNOWN字段会触发必要追问，不补条件。每项引用给定source_id#L片段；可省略quote，由程序附回原句。追问后的回答只解决它实际回答的内容，不改变其他问题、方向或权重。

同一科学条件在不同对象上的采用态度不同，可以使用相同 code 分多条记录，各自保留 status、covered_nodes 和引用。例如一组采用、另一组不采用，不要取其中一条覆盖全部对象，也不要改造条件名称以绕过范围记录。
