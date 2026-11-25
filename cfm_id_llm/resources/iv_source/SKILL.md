# 二元工具变量：读取原问题和总体概率表

只读材料，不解题，不采用科学条件，不生成审核。输出给定Schema的JSON。引用给定source_id#L片段；可省略quote，由程序附回。正文和附件共同读取，不要求用户使用特定句式或表头。

- family=BINARY_IV只适用于一个问题：二元工具Z、实际处理D和结果Y。邀请、抽签、资格可能是工具；实际接受服务是处理，不能把两者当成同一个变量。
- study保留总体、时期、固定背景及三个变量的业务含义；binary_coding固定使用instrument/treatment/outcome三个键，每个值写清该变量0和1各是什么。未说明留空，不能猜。
- target.kind=ATE是全体的实际处理1相对0的效果；LATE是因工具从0变1才接受处理者的效果。保留treated/reference及方向。工具对结果的ITT、ATT或多问题用OTHER，不能替换成LATE。
- information每一cell是P(D=d,Y=y | Z=z)，共八个坐标；按实际列含义读取，无论列名是什么。EXACT_POPULATION_CONDITIONAL_LAW必须原文明确为总体条件概率。样本频率即使合计1也仍是FINITE_SAMPLE。零概率需实际给出，不能补遗漏格子。same_scope只判断资料是否对应原人群、时期、变量，不要求已经能识别。
- conditions完整填写instrument_independence（Z与潜在处理和结果独立）、exclusion_restriction（Z只通过D影响Y）、consistency_and_binary_outcome（一致性及二元结果）、no_interference（对象间无干扰）、positive_instrument_support（两种Z都有正概率）、monotonicity_direction（D(1)≥D(0)，无违背者）和complete_model（本次所采用限制是否已经列全）。缺失用UNKNOWN，不能由“工具变量”几个字或概率表自行批准。
- ADOPTED采用；NOT_ADOPTED不采用但不声称为假；UNDECIDED尚未决定；CONTRADICTED明确矛盾；UNKNOWN未说明。ATE允许明确不施加单调性，LATE需要非递减单调性。不能从邀请随机推出实际参加也随机。
- 所有其他限制放remaining，逐条保留采用状态；完整性声明只放complete_model，不另造一条“无其他限制”。实际处理随机、个体单调响应、额外结果关系等都不能当普通备注删掉。material_notes仅保存资料说明、背景或输出要求。
