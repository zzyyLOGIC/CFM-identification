"""Opt-in meaning of complete information, not a complete table of outcomes.

Only request descriptions change. The source-selection wire, parsing, review,
scientific admission, planning and native mathematics remain unchanged.
"""
import json

CONTRACT = 'network-source-selections-information-2'
LOCAL_CONTRACT = 'network-source-selections-information-3'

INFORMATION_SCOPE = '''listed_means_are_complete_information只问：原文是否明确“除information中逐格给出的精确总体均值外，没有其他可用总体信息”。它不问是否已经知道每个对象每种安排的全部均值，也不问能否求出目标。原文明确只有这些精确格子时可为true，即使表只覆盖部分格子；有另外已知的总体区间、聚合方程或更强分布信息时为false，且额外信息不能丢弃。没有明确交代信息是否完整时为null。有限样本不是这份精确总体均值表；另行采用的科学界限则属于模型条件，不是额外观测总体信息。不能只因材料说“已知信息全部写在这里”，就把本字段填true：还要核对这些信息是否全由精确均值格子表达。'''

FREE_MEANS = '''先按原文判断“信息的范围是否确定”，再判断“每个量的数值是否已知”。这两个问题不同。原文明确只掌握所列精确总体格子，其他格子没有另给信息，同时说明所采用的模型条件时，未列均值仍是模型中的未知量；不能为了生成识别答案而补值，也不能仅因此向用户索要所有目标签名均值或在unresolved标为材料缺项。结果可能唯一、只能定界或仍无法确定，都交数学模块。如果原文说某些已有信息、界限范围、条件采用状态或评价口径尚待确认，则是真实未定，仍逐项保留在相应字段及unresolved，不能借“模型未知量”消除它。是否已接受均值充分性等科学条件仍独立读取和审核。'''

INCOMPLETE_INFORMATION = '''可观察总体量的真实区间是已知但不完全的总体信息；它不等于样本置信区间，也不是另外采用的潜在结果科学界限。现有精确value字段不能表达区间时，不填中点、端点或任意有理数；以允许的非精确字段状态保留覆盖范围，并把区间原文和引用完整保留在additional_restrictions。它不能成为bounded_model.bounds，不能声称精确已列均值已穷尽信息。有限样本仍遵循FINITE_SAMPLE规则；原文性质不明则保留疑点。'''


def make_request(bundle, *, binding, assignment_semantics=None):
    from .network_information_contract import make_request as previous
    request = previous(bundle, binding=binding, assignment_semantics=assignment_semantics)
    body = json.loads(request['user'])
    schema = body['output_schema']
    bounded = schema['$defs']['BoundedModel']['properties']
    bounded['listed_means_are_complete_information']['description'] = INFORMATION_SCOPE
    schema['properties']['unresolved']['description'] = FREE_MEANS
    schema['$defs']['Information']['description'] += '\n' + INCOMPLETE_INFORMATION
    for name in ('outcome_definition', 'outcome_unit', 'outcome_period'):
        bounded[name]['description'] = (
            '保留与study相同的结果口径及原文明示内容；bounded_model.source_ids也须覆盖本项的定义、单位或期间，'
            '跨段陈述则引用相关各段，不仅引用上下界数字。未知保持null，不猜测。')
    # These refine existing fields, never override their types or parser rules.
    system = request['system'] + '\n\n总体信息完整性与未知量：\n' + INFORMATION_SCOPE + '\n' + FREE_MEANS + '\n' + INCOMPLETE_INFORMATION
    return dict(system=system, user=json.dumps(body, ensure_ascii=False))


def make_local_request(bundle, *, binding, assignment_semantics=None):
    """Expose existing wire spellings and source-domain limits; no repair."""
    request = make_request(bundle, binding=binding, assignment_semantics=assignment_semantics)
    body = json.loads(request['user'])
    schema = body['output_schema']
    def annotate(node):
        if isinstance(node, dict):
            if 'enum' in node and node.get('type') == 'string':
                node['description'] = (node.get('description','') + ' 枚举字符串须逐字选用，不能翻译或改写拼写：' + '、'.join(node['enum']) + '。').strip()
            for child in tuple(node.values()):annotate(child)
        elif isinstance(node,list):
            for child in node:annotate(child)
    annotate(schema)
    info = schema['$defs']['Information']
    info['description'] += ('\n精确均值表的source_ids指向该表的原文及其格子定义；'
        '仅给评价期或结果单位的背景材料放在study或bounded_model对应来源，不作为另一份均值表来源。'
        '均值格子须来自同一份原始表，配套文档可说明该表的对象、编码、暴露或期间。'
        '保留全部必要引用，后续按既有来源角色合同审核；不能把需要来源审核写成unresolved中的材料缺项。'
        '确有另一份总体信息、额外等式或约束时仍分别完整保留，不能归作表格说明或合并进该表。')
    schema['properties']['target']['description'] = (
        '记录原问题的完整政策、评价范围和汇总方式；source_ids同时覆盖这些要求及实际写入的对象名称、处理编码。'
        '不能只引用问题却展开问题中没有的名单或编码，也不能用别的字段引用补足。')
    return dict(system=request['system']+'\n字段自己的source_ids须共同覆盖其全部内容；枚举按Schema原样填写。未定条件保留，不能为进入数学模块改写。',
                user=json.dumps(body, ensure_ascii=False))
