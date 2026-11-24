"""Source-bound local contrasts under an explicitly stated randomization target.

Shared network/source records, separate effect coordinates. No theorem imports,
fixed-policy projection, invented A4 cells, or scientific approval.
"""
from copy import deepcopy
from fractions import Fraction
import json
from typing import Literal
from pydantic import Field, StrictInt, StrictStr, model_validator
from .network_policy_reading import Record, Cited, Declaration, Study, Assignment, Exposure, FirstStageExclusion, Note, documents, DataDescription, DATA_DESCRIPTION_RULE
from . import network_design_reading as components
from .network_statement_reading import DesignFacts, SelectedScienceStatements
from .source_reference_wire import catalog, expand
from . import effect_information_rules as information_rules
from . import assumption_choices as choice_contract
from . import network_population_contract as population_contract

VERSION = 'network-randomized-effect-reading-1'

# Public semantic duties, shared by field descriptions and the request. These
# guide reading; no string matching, candidate rewriting or science approval.
RESIDUAL_ROLES_VERSION = 'effect-residual-propositions-1'
RESIDUAL_ROLES = {
    'information': (
        '逐项记录材料实际提供的信息类型、可用性、对象及状态范围。样本、符号总体信息、没有提供具体数值等，'
        '若已由这些字段完整表达，就在这里结束该项记录，不再将同一内容复制为额外限制。独立来源分别保留。'),
    'additional_restrictions': (
        '仅保存结构化字段尚未表达的剩余主张，不是材料摘抄区。按主张判断，不按整段判断：'
        '一段话同时给出信息范围和一个均值上界时，范围进入information，只把上界及其适用对象/状态放这里。'
        '真正新增的界、相等关系、单调性、无法由字段表达的科学条件或限定识别方法的要求均须保留，包括当前不支持的条件。'
        '资料须审核、样本不能升级为总体、估计模型须核验适用性等流程说明，属于对应information的data_description，不是新增数学限制。科学条件未决定仍在其专门字段保留，不能改成流程说明。'
        '没有总体信息属于缺项，不是新增科学限制。原文中的“另有”“补充”“声明”不决定字段归属。'
        '所有内容已被其他字段完整表达时返回空列表；空列表不是对科学模型完整性的批准。'),
    'unresolved': (
        '只记录专门结构化字段尚未完整表达的缺项或冲突。scientific_statements或assumption_choices已经完整记录同一条件的未知、未决定、拒绝或冲突态度及来源时，不在这里重复。'
        '这些专门字段的状态和来源必须保留；unresolved为空不表示条件已解决或已获批准，必要条件仍由其专门字段触发追问或阻断。尚未表达的额外对象、作用范围或限制不能省略。'
        '对于需要在本列表补充的缺项，相关结构化字段仍保留UNKNOWN/null或实际缺少的范围；若原文明说未提供、尚未决定或存在不同说法，text写明具体缺项/冲突，source_ids引用作出这些声明的原文。'
        '只有材料完全未提及某项内容时，才可用空source_ids表示无可引用的声明；不得给未出现的话编造来源。'
        '未给出符号总体均值的数值不是缺项。没有另需说明的缺项或冲突时返回空列表。'),
}

# Public field responsibilities, independent of case text and mathematical route.
CITATION_GROUPS = {
    'Study': {'source_ids': ['nodes','edges','graph_kind','edge_list_complete','treatment','outcome','outcome_kind','context']},
    'Assignment': {'source_ids': ['kind',*components.ASSIGNMENT_FIELDS]},
    'EffectTarget': {'source_ids': ['kind','operation','population','aggregation'],
                     'remaining_source_ids': ['remaining_assignment']},
    'LocalArm': {'source_ids': ['own','exposure']},
    'Declaration': {'source_ids': ['value']},
    'Exposure': {'source_ids': ['kind','core_collaborators','weights','mode','groups']},
    'FirstStageExclusion': {'source_ids': ['status']},
    'SelectedStatement': {'source_ids': ['status']},
    'AssumptionChoice': {'source_ids': ['condition', 'status', 'scope']},
    'EffectInformation': {'source_ids': ['operator','availability','outcome_nodes','arm_cells']},
    'Note': {'source_ids': ['text']},
    'DataDescription': {'source_ids': ['text']},
}


class LocalArm(Cited):
    own: StrictInt | None
    # int for E1-E5; canonical string coordinate for weighted/grouped exposure.
    exposure: StrictInt | StrictStr | None


class EffectTarget(Cited):
    kind: Literal['DIRECT_EFFECT', 'SPILLOVER_EFFECT', 'LOCAL_TOTAL_EFFECT', 'OTHER', 'UNKNOWN']
    operation: Literal['FIRST_MINUS_SECOND', 'OTHER', 'UNKNOWN']
    first: LocalArm
    second: LocalArm
    population: list[str] | None
    aggregation: Literal['SINGLE', 'EQUAL_MEAN', 'OTHER', 'UNKNOWN']
    population_fixed_before_assignment: Declaration = Field(description=population_contract.RULE)
    remaining_assignment: Literal['ORIGINAL_DESIGN_CONDITIONAL', 'OTHER', 'UNKNOWN']
    remaining_source_ids: list[str]
    shared_outcome_and_context: Declaration


class ArmCell(Record):
    node: str
    own: StrictInt
    exposure: StrictInt | StrictStr


class EffectInformation(Cited):
    operator: Literal['NODE_ARM_MEANS', 'NODE_FULL_LAW', 'FULL_JOINT_LAW', 'FINITE_SAMPLE', 'OTHER', 'UNKNOWN'] = Field(
        description='Population information type, or FINITE_SAMPLE for observations and sample summaries. '
        'FINITE_SAMPLE must pair with availability=FINITE_SAMPLE and empty arm_cells. Separate independent sources remain separate records.')
    availability: Literal['SYMBOLIC_POPULATION_OPERATOR', 'FINITE_SAMPLE', 'EXACT_POPULATION_VALUE', 'UNKNOWN'] = Field(
        description='How this same source is available. FINITE_SAMPLE pairs only with operator=FINITE_SAMPLE. '
        'Neither sample size nor sample means establish population information.')
    outcome_nodes: list[str] = Field(description=(
        'Objects actually covered by this information source, independently of the evaluation population. '
        'Do not filter available information to the selected target or expand it to all study objects.'))
    arm_cells: list[ArmCell] = Field(description=(
        'For NODE_ARM_MEANS, enumerate exactly the node/own/exposure combinations explicitly declared available '
        'by this source, including those not used by the target. A symbolic operator has no numerical values, '
        'but its declared coordinate scope still belongs here. Partial scope stays partial. Pending conditions '
        'and extra restrictions do not erase known scope. Never invent undeclared cells. '
        'For other operators this list is empty; this does not erase their own operator or node scope.'))
    data_description: list[DataDescription] = Field(default_factory=list, description=DATA_DESCRIPTION_RULE)


class NetworkEffectReading(Record):
    version: Literal['network-randomized-effect-reading-1']
    reference_context: str = Field(pattern=r'^c[0-9a-f]{12}$')
    study: Study
    assignment: Assignment
    first_stage_exclusion: FirstStageExclusion | None = None
    target: EffectTarget
    exposure: Exposure
    design_facts: DesignFacts
    scientific_statements: SelectedScienceStatements
    assumption_choices: list[choice_contract.AssumptionChoice] = Field(default_factory=list, description=choice_contract.RULE)
    information: list[EffectInformation] = Field(description=RESIDUAL_ROLES['information'])
    additional_restrictions: list[Note] = Field(description=RESIDUAL_ROLES['additional_restrictions'])
    unresolved: list[Note] = Field(description=RESIDUAL_ROLES['unresolved'])


SYSTEM = '''你是网络干扰业务的事实读取助手。只按原文读取，不选择识别定理、不判断POINT、不授予科学许可。返回符合Schema的JSON。
先记录用户要比较什么，再记录比较所需条件是否给齐。不要因为条件缺失而改写明确的业务目标。source_ids只使用本次source_catalog的s编号，reference_context照抄；此前助手提示不是事实来源。
study保留完整对象名单、明确列出的无向边、处理和结果名称及其编码、期间与背景。没有明确完整边表时edge_list_complete=null，不自行补边。处理编码不附加到结果定义中。study.source_ids支持本记录实际写出的全部事实；如果context写入共同期间、共同背景或共同结果口径，需要把声明这些事实的原文也列入，不能仅引用介绍业务或列出网络的段落。
target.first、second分别记录被减数、减数的自身处理own和同伴暴露exposure；开启为1、未开启为0。DIRECT_EFFECT比较同一暴露下自身开启与未开启，SPILLOVER_EFFECT比较自身状态相同时两种同伴暴露，LOCAL_TOTAL_EFFECT比较本人和同伴状态均改变的两端；不按句子出现顺序决定方向，不把未说明坐标补成0。first减second时operation=FIRST_MINUS_SECOND。
population是事先固定的评价名单，不是本轮实际中签者或实际未中签者的名单。明确全体时展开完整名册，明确子集或单个对象时只列对应编号，未说明为null。aggregation分别保留SINGLE、EQUAL_MEAN或未知；population_fixed_before_assignment按原文独立填写，不能由名单存在推定。
remaining_assignment只有原文明确在满足本人与同伴条件的完整安排中，按原试点抽签概率平均时才为ORIGINAL_DESIGN_CONDITIONAL，并用remaining_source_ids引用目标中的这项约定。试点曾经随机抽签，不代表用户已经选择这项目标；未说明为UNKNOWN，固定其他人、全员推广或另一个随机规则用OTHER，保留原意。它不是暴露充分性假设。
target.source_ids共同支持kind、operation、population、aggregation：既包括比较目的与减法方向，也包括评价谁和怎样汇总。指定名单及平均方式可能在另一段材料中，必须在这里引用；population_fixed_before_assignment子记录中的引用不代替它。first和second各自引用用户要求该端自身状态、同伴状态的原文；只介绍工具、处理编码或分组定义的材料不足以说明用户选择了哪一端，必要时同时引用比较问题和编码/分组定义。shared_outcome_and_context独立记录两端是否明确使用同一结果定义、期间及研究背景；未说明为null，明确不同为false。
design_facts分别记录原文是否提供完整分配规则、是否明确网络在处理前固定。scientific_statements逐项记录完整处理向量与全部潜在结果独立、一致性、有限条件一阶矩的原文状态：已采用ADOPTED、明确拟采用PROPOSED、不采用NOT_ADOPTED、未决定UNDECIDED、未提NOT_STATED、冲突CONFLICTING。NOT_STATED的source_ids为空，其余状态必须有来源；这些状态都不是审核批准。对象之间独立抽签不自动证明与潜在结果独立。
information保留每份信息的来源及覆盖范围，读取的是“材料提供什么”，不是“当前目标需要什么”。NODE_ARM_MEANS是给定本人处理与同伴暴露的逐对象总体条件均值，要逐格列明node/own/exposure。不能从目标所需格子推定材料已经提供，也不能丢掉原文明示可用但当前目标没有用到的对象或状态。原文明示某定义下的全部状态可用时，按该暴露定义展开原文所指对象和实际状态；明确只给部分对象或状态时，只列该部分，不补成全表。没有数值不等于没有格子：SYMBOLIC_POPULATION_OPERATOR仍须保留明确声明的坐标范围。
逐份材料完整读取后再结束回答。某项科学条件未定、背景未确认、有额外限制，均不允许提前省略其他已知事实；这些缺项或限制照常分别记录，information仍完整记录原文已经提供的范围。真正没说明的范围保持缺失，不能由这条要求猜出格子。NODE_FULL_LAW是逐对象(Y_i,完整T)的总体联合分布；FULL_JOINT_LAW是全部Y和完整T的总体联合分布，二者arm_cells应为空，但仍记录其各自的operator和outcome_nodes。有限样本记录、分组样本均值和其他样本估计，同一记录的operator与availability都填FINITE_SAMPLE，arm_cells为空，保留原文明确覆盖的outcome_nodes和来源；不能因为样本按本人/同伴状态分组就填NODE_ARM_MEANS或总体均值格子。若另有独立声明可用的总体信息，另建记录保留其类型和范围，不得因存在样本而丢掉总体信息，也不得用总体信息覆盖样本记录。只有明确声明可用的总体均值才用NODE_ARM_MEANS；未明确总体信息时不得升级。如果原文给出具体总体均值数值，而本Schema的信息字段没有数值位置，只将该数值与对应坐标保留在additional_restrictions；仍在information完整记录其可用性和范围。不能为了接入当前方法而删除具体数值或更强限制。
最后按residual_field_contract逐项核对主张归属，不按原文段落整段复制。information已完整表达的类型、可用性、对象和状态范围，不再成为additional_restrictions；不能仅因原文说“另有信息”就追加一条限制。同段内还有真正未表达的科学限制或具体数值时，只摘出这项剩余主张及其适用范围、引用，不能连同限制一起丢掉。
unresolved的引用由缺项是怎样得知的决定：原文明说“未提供”“未决定”时引用这段原文；材料完全没提时才保留空来源，不制造证据。保留实际未知、未提供的范围与冲突，不把符号信息没有数值当作缺项。各字段无相应主张时用规定的null/UNKNOWN/空列表，不填职责口号或自评。格式正确和引用存在不代表语义正确，仍须独立审核。'''
SYSTEM += "\n" + components.ASSIGNMENT_GUIDANCE + "\n" + components.EXPOSURE_GUIDANCE + "\n" + components.STAGE_GUIDANCE
SYSTEM += "\n" + choice_contract.RULE
SYSTEM = SYSTEM.replace(
    'population_fixed_before_assignment按原文独立填写，不能由名单存在推定。',
    'population_fixed_before_assignment：'+population_contract.RULE)


def reference_catalog(bundle, *, binding):
    return catalog(bundle, documents(bundle), binding=binding, version=VERSION)


def make_request(bundle, *, binding, assignment_semantics=None):
    from .assignment_semantics import guidance
    from .source_coverage_contract import annotate, INSTRUCTION
    refs = reference_catalog(bundle, binding=binding)
    schema,coverage = annotate(NetworkEffectReading.model_json_schema(),CITATION_GROUPS)
    information_rules.annotate(schema)
    schema['properties']['reference_context']['const'] = refs['context']
    schema['$defs']['SourceId'] = dict(type='string', enum=list(refs['aliases']))
    for item in schema['$defs'].values():
        for name, prop in item.get('properties', {}).items():
            if name.endswith('source_ids'):
                prop.update(items={'$ref': '#/$defs/SourceId'}, uniqueItems=True)
    return dict(system=SYSTEM + '\n' + INSTRUCTION + guidance(assignment_semantics), user=json.dumps(dict(
        case_id=bundle['case_id'], question=bundle['question'], fact_contract=VERSION,
        information_combination_contract=information_rules.VERSION,
        residual_field_contract=dict(version=RESIDUAL_ROLES_VERSION, fields=RESIDUAL_ROLES,
                                     unit='proposition_not_paragraph', automatic_repair=False),
        source_coverage_contract=coverage,
        reference_context=refs['context'], source_catalog={k:dict(doc_id=v['doc_id'],text=v['text'])
            for k,v in refs['aliases'].items()}, output_schema=schema),ensure_ascii=False))


def parse(bundle, raw, *, binding):
    wire = NetworkEffectReading.model_validate(deepcopy(raw))
    refs = reference_catalog(bundle, binding=binding)
    if wire.reference_context != refs['context']:
        raise ValueError('STALE_EFFECT_REFERENCE_CONTEXT')
    c = NetworkEffectReading.model_validate(expand(wire.model_dump(),refs))
    nodes, edges, a, t = c.study.nodes, c.study.edges, c.assignment, c.target
    if any(not n.strip() for n in nodes) or len(set(nodes)) != len(nodes):
        raise ValueError('UNIQUE_NETWORK_NODES_REQUIRED')
    if any(len(e)!=2 or e[0]==e[1] or not set(e)<=set(nodes) for e in edges) or len({frozenset(e) for e in edges})!=len(edges):
        raise ValueError('SIMPLE_GRAPH_COORDINATES_REQUIRED')
    components.validate_components(a, c.exposure, nodes, edges)
    if a.probabilities is not None and (not set(a.probabilities)<=set(nodes) or
            any(not 0<=Fraction(p)<=1 for p in a.probabilities.values())):
        raise ValueError('INVALID_ASSIGNMENT_PROBABILITIES')
    if a.fixed_count is not None and not 0<=a.fixed_count<=len(nodes):
        raise ValueError('INVALID_FIXED_QUOTA')
    if (a.kind=='INDEPENDENT_BERNOULLI' and a.fixed_count is not None or
            a.kind=='UNIFORM_FIXED_QUOTA' and a.probabilities is not None):
        raise ValueError('CONFLICTING_ASSIGNMENT_FIELDS')
    if t.population is not None and (not set(t.population)<=set(nodes) or len(set(t.population))!=len(t.population)):
        raise ValueError('INVALID_EVALUATION_POPULATION')
    for arm in (t.first,t.second):
        if (arm.own is not None and arm.own not in (0,1)
                or (type(arm.exposure) is int and arm.exposure<0)):
            raise ValueError('INVALID_LOCAL_ARM')
        if arm.exposure is not None:
            for node in t.population or []:
                components.validate_exposure_coordinate(c.exposure, node, arm.exposure, edges)
    for source in c.information:
        information_rules.require_scope(source, nodes=nodes, exposure=c.exposure, edges=edges)
    return dict(facts=c.model_dump(mode='json'), reference_binding=refs)
