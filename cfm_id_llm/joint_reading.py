"""Source-only reading for joint interventions and coupled network means.

The independent source audit is not a scientific approval. No formula is read
into the mathematical problem and no model result is used as source evidence.
"""
import json
from importlib.resources import files
from typing import Literal,Generic,TypeVar,Annotated
from pydantic import Field, TypeAdapter
from .population_ate_reading import (
    Strict, SourceAudit as PopulationSourceAudit, AuditFinding as PopulationAuditFinding,
    sources as original_sources,
)
from .compact_study import digest
from pfn_pipeline._internal.identification.schemas import (
    CompleteRandomizationDesignV1, HeterogeneousBernoulliDesignV1,
    TwoGroupFixedQuotaDesignV1, ClusterBernoulliDesignV24,
    MultiGroupFixedQuotaDesignV25, TwoStageQuotaMixtureDesignV27,
    UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1)

VERSION = 'joint-source-reading/1'
Design = Annotated[(CompleteRandomizationDesignV1 | HeterogeneousBernoulliDesignV1 |
          TwoGroupFixedQuotaDesignV1 | ClusterBernoulliDesignV24 |
          MultiGroupFixedQuotaDesignV25 | TwoStageQuotaMixtureDesignV27 |
          UnequalProbabilityFixedQuotaDesignV1 | RerandomizedBalancedDesignV1),Field(discriminator='kind')]
STATUS = Literal['ADOPTED','NOT_ADOPTED','UNDECIDED','UNKNOWN','CONTRADICTED']
T=TypeVar('T')


class Citation(Strict):
    source_id: str
    quote: str | None = Field(default=None,description='推荐只填写 #L 原文片段编号，quote省略或null，由程序附回原句。若引用完整文档编号，则必须给连续的逐字原文。')


class AuditFinding(PopulationAuditFinding):
    evidence: list[Citation]


class SourceAudit(PopulationSourceAudit):
    findings: list[AuditFinding]


class Claim(Strict,Generic[T]):
    value: T
    evidence: list[Citation]


class Condition(Strict):
    code: str
    statement: str
    status: STATUS
    evidence: list[Citation]


class MaterialNote(Strict):
    kind: Literal['DATA_DESCRIPTION','OUTPUT_REQUEST','STUDY_CONTEXT']
    statement: str
    evidence: list[Citation]


class CoreCondition(Condition):
    code: Literal['graph_complete','recursive_scm','perfect_intervention','strict_positivity',
        'randomization','consistency','fixed_network','mean_sufficiency','finite_mean_model_complete','first_stage_exclusion','no_between_unit_interference','finite_first_moments']


class DagTarget(Strict):
    query_kind: Literal['INTERVENTIONAL_DISTRIBUTION','CONDITIONAL_INTERVENTIONAL_DISTRIBUTION','MEAN','CONTRAST','OTHER','UNKNOWN']
    treatments: list[str]
    outcome: list[str]
    conditioned_on: list[str]
    joint: bool | None
    context: str
    period: str
    # Values are metadata for substitution after ID; not graph variable names.
    intervention_values: dict[str, str]


class VariableDefinition(Strict):
    description: str
    values: list[str] = Field(description='原文明确给出的离散编码；未说明则为空，不推测取值。')


class Graph(Strict):
    nodes: list[str]
    directed: list[list[str]]
    bidirected: list[list[str]]
    finite_discrete: bool | None
    variable_definitions: dict[str, VariableDefinition] = Field(default_factory=dict,
        description='原文提供的变量含义、编码和值域；这些是变量定义，不放入额外科学限制。')


class DagInformation(Strict):
    kind: Literal['FULL_JOINT_POPULATION_LAW','FINITE_SAMPLE','MARGINAL_STATISTICS','UNKNOWN']
    variables: list[str]
    matches_target: bool | None = Field(description='资料与目标是否为同一研究人群、结果定义、评价时期及背景；不是问资料能否已经识别目标。')
    sample_size: int | None = Field(default=None,ge=0,description='仅FINITE_SAMPLE时记录这份共同记录的样本条数；总体律填null。其他试验或某处理组的人数留在各自资料说明，不填到这里。')
    jointly_observed: bool | None = Field(default=None,description='有限样本是否在同一批记录中共同测量了variables全部变量；分别的边际表、不同人群拼表不算。仅从变量名单不能推断，未说明留null。')


class Network(Strict):
    nodes: list[str]
    edges: list[list[str]]
    complete: bool | None
    undirected: bool | None


class Exposure(Strict):
    grouping: Literal['strict_majority_ties_low','three_level_treated_neighbor_fraction',
        'pretreatment_core_collaborator_majority','exact_treated_neighbor_count','any_treated_neighbor','UNKNOWN','OTHER']
    core_collaborators: dict[str, list[str]] | None


class NetworkTarget(Strict):
    description: str
    context: str
    period: str
    outcome: str
    first: dict[str, int]
    second: dict[str, int] | None
    weights: dict[str, str]


class Mean(Strict):
    node: str
    own: int = Field(ge=0, le=1)
    exposure: int = Field(ge=0)
    value: str


class MeanInformation(Strict):
    kind: Literal['POPULATION_MEANS_ONLY','FINITE_SAMPLE','FULL_LAW','UNKNOWN']
    values: list[Mean]
    matches_target: bool | None = Field(description='资料与目标是否为同一批对象、结果定义、评价时期及背景。不是问资料是否含目标政策的全部均值格子，也不是目标政策是否有支持；PARTIAL正允许目标格子未知。')
    sample_size: int | None = Field(default=None,ge=0,description='原文给出的有限记录条数；不把样本均值变成总体均值。')


class Bounds(Strict):
    outcome_domain: Literal['BINARY','REAL','UNKNOWN']
    kind: Literal['CONDITIONAL_MEAN','ALMOST_SURE_OUTCOME','UNKNOWN']
    by_node: dict[str, list[str]] = Field(description='逐对象记录原文给定的[下限,上限]，覆盖完整研究名单。全体对象、所有安排的二元0/1结果已明确时，各对象仍填写["0","1"]，不能只写outcome_domain=BINARY而把本表留空；更紧的已给范围必须原样保留。')
    all_assignments: bool | None


class Term(Strict):
    node: str
    own: int = Field(ge=0, le=1)
    exposure: int = Field(ge=0)
    coefficient: str


class LinearConstraint(Strict):
    description: str
    terms: list[Term]
    relation: Literal['EQ','LE','GE']
    rhs: str
    status: STATUS
    evidence: list[Citation]


class MeanOrder(Strict):
    description: str
    nodes: list[str]
    axis: Literal['OWN','PEER','UNKNOWN']
    direction: Literal['NONDECREASING','NONINCREASING','UNKNOWN']
    all_other_states: bool | None
    status: STATUS
    evidence: list[Citation]


class ProbabilityQuantity(Strict):
    """A source-described probability, not an identified graph functional."""
    intervention: dict[str, str]
    event: dict[str, str]
    conditioned_on: dict[str, str]
    population: str
    period: str
    context: str


class GivenProbability(Strict):
    quantity: ProbabilityQuantity
    value: str
    information_kind: Literal['EXACT_POPULATION', 'SAMPLE_ESTIMATE', 'UNKNOWN']
    status: STATUS
    evidence: list[Citation]
    scope_matches_question: bool | None = Field(default=None,
        description='仅对EXACT_POPULATION核对是否为所问量的同一人群、时期、背景及条件。同义可true，不同false，未知null；样本数值不用于总体答案，此标记留null。独立来源审核不能推测可推广。')


class Reading(Strict):
    family: Claim[Literal['DAG_JOINT','NETWORK_JOINT_MEANS','OTHER','UNKNOWN']]
    dag_target: Claim[DagTarget] | None
    graph: Claim[Graph] | None
    dag_information: Claim[DagInformation] | None
    network: Claim[Network] | None
    exposure: Claim[Exposure] | None
    design: Claim[Design | None] | None
    network_target: Claim[NetworkTarget] | None
    mean_information: Claim[MeanInformation] | None
    bounds: Claim[Bounds] | None
    conditions: list[CoreCondition]
    constraints: list[LinearConstraint]
    mean_orders: list[MeanOrder] = Field(default_factory=list,description='明确针对条件均值的顺序，分别记录本人或同伴状态轴；程序展开所有相邻状态。不能由逐人结果单调性替代。')
    remaining: list[Condition] = Field(description='只列尚未表达的真实额外限制或事实缺口；不列合成背景、仅求公式等任务说明，也不把没有其他限制记录成一条额外限制。')
    material_notes: list[MaterialNote] = Field(default_factory=list,description='需要保留但不属于科学限制的资料说明、输出要求或研究背景。不可放入任何约束潜在结果、模型或参数的声明；独立复核须检查有无错误降级。')
    requested_probability: Claim[ProbabilityQuantity] | None = Field(default=None,
        description='仅当图题原文另行给出干预概率数值时，记录用户所问的具体概率及全部范围；一般符号分布填null，不为此新增追问。')
    given_probabilities: list[GivenProbability] = Field(default_factory=list,
        description='图题材料明确给出的干预概率数值，不含模型推算的答案。逐项保留范围、总体/样本性质及采用状态；本字段已完整表达的同一概率不用在remaining重复，其他未表达限制仍保留。')


RULES = '''只恢复原材料，不回答数学问题，不生成审批或证明。返回所附schema的完整JSON。
family=DAG_JOINT：一个问题要求设置一个或多个变量后的干预分布。单变量问题treatments保留单元素，joint=false；不要人为增加第二个处理。多个变量共同设定时joint=true，先后发生的变量也可在同一个do集合里；分别问两个干预不是联合干预。只问联合分布时保留结果变量集合。intervention_values只记录明确指定取值；求一般公式时为{}。不得把业务对象当图变量。
query_kind区分干预分布（某个事件的概率也属于分布）、给定其他变量的条件干预分布、均值和差值；conditioned_on只放目标另行要求给定的变量，普通研究背景不自动变成条件变量。不能把条件目标藏进context，不能把两个方案之差改成一份干预分布。
family=NETWORK_JOINT_MEANS：网络固定政策均值或两个固定政策均值之差，包含跨均值的等式或线性不等式。变量级DAG不是对象关系网。其他问题family=OTHER，不相关块填null。
每个Claim与每条条件/约束都附逐字原文evidence，source_id严格使用source_catalog的键。不能引用模型原答。缺事实留UNKNOWN/null/空项，不补常用假设。数学式中的数字用精确分数字符串。
DAG条件恰好记录graph_complete（直接关系及未观测共同原因完整）、recursive_scm（无环结构模型/独立外生噪声及所列潜在共同原因）、perfect_intervention（同时设定指定变量，其余机制不变）、strict_positivity（所有观测变量联合取值的总体概率严格为正）。没说用UNKNOWN。显式未观测共同原因记bidirected；不能从相关猜因果；有限样本不升级为总体联合律。有限记录保留kind=FINITE_SAMPLE、sample_size，并按原文填写jointly_observed：全部变量在同一批记录中共同测量为true；只有独立边际汇总或不同对象的记录为false；未明确为null。没有取得总体概率的精确数字，不等于不能讨论以观测联合分布为参数的符号公式；勿为得到公式伪造总体信息或正性。
单变量一般ID还要记录no_between_unit_interference：不同研究对象之间没有相互影响，未说明用UNKNOWN；变量因果图本身不能证明这项条件。单变量和多变量都要保留图中的全部观测变量，未观测共同原因用bidirected表示，不可并入已知观测联合分布。用户指定调整集时仍保留为额外要求，不能偷偷交一般ID改用别的公式。
graph.variable_definitions按原文记录各变量含义、编码与离散值域；只填写已给内容，不把二元定义或0/1编码写为remaining科学限制。一个处理可对应多个结果的联合分布，保留完整outcome集合；单处理的共同样本也不因此变成额外限制。
区分混杂背景与额外数学限制：解释处理选择和结果为何有关、为何不能直接比较两组的定性研究背景，在原文明列因果边后可保留于material_notes的STUDY_CONTEXT，不据此新建ADOPTED限制。图边不表达效应正负，也不能从“更容易/更好”等观察关联自行推出逐人潜在结果单调性或干预均值顺序。若原文独立声明本次采用某个均值顺序、逐人单调性、概率等式/不等式、效应符号或数值限制，仍须完整保留为科学限制；不能因为涉及同一组变量就说图已覆盖。
网络条件恰好记录randomization（完整随机安排独立于全部潜在结果）、consistency（实际结果对应实际完整安排）、fixed_network（处理前固定网络）、mean_sufficiency（每个对象在所有完整安排下的均值只取决于自身处理及所定义的同伴状态）、finite_mean_model_complete（只有所列均值、界和线性限制，没有其他个体层或分布限制）。D6另记first_stage_exclusion。暴露的定义不推出均值充分性。
网络材料若明确声明本题所需均值存在且有限，另在conditions用finite_first_moments保留采用状态和引用；未说明则不新增。这是已有有限均值模型的有定义条件，不重复写入remaining。不能用它代替范围、均值顺序或更强的分布限制；仅局部均值存在而未覆盖本题所需范围时，仍保留范围缺口。
finite_mean_model_complete审核的是允许的均值模型是否还受未表达的限制，不要求用户逐字复述字段定义。结合全部材料中“只有哪些总体信息”、取值域、界限和耦合限制的范围判断；不能把没有取得完整联合分布误作闭合声明缺失。单个二元结果的一阶分布由其均值决定，不凭空要求另补这种分布信息；跨对象、跨安排的联合或个体限制并不由均值决定，若明确采用必须保留，闭合范围确实不清时仍留未知。
网络节点和边按名册/关系文件完整读取；first/second是整个网络的0/1安排，weights覆盖全部节点，未评价节点用0，不能把局部事件改成全网安排。只问一个政策时second=null。方向严格first减second。
mean_information只记录已给条件总体均值及覆盖；样本平均数用FINITE_SAMPLE。只有符号总体分布用FULL_LAW或UNKNOWN，不能伪造均值数值。bounds区分均值范围和每个结果的范围，保留全安排范围。
information.matches_target只检查对象、结果、时期及背景口径是否一致。目标政策无支持或其均值格子未知，不代表口径不一致；这些支持问题由程序求界，不要求模型提前判断识别成败。
constraints各项为有限均值的线性关系：例如甲的某格均值等于乙的某格均值+0.2，terms记甲1、乙-1，EQ rhs=1/5。多个对象分别有关系时展开每项，不合成跨对象平均。必须保留节点、本人处理、邻居状态、常数、方向和采用态度。
mean_orders记录明确的条件均值顺序：nodes为原文适用的对象；axis=OWN表示固定同伴状态时比较本人0与1，PEER表示固定本人状态时同伴状态增加；direction保留平均结果不降或不升；all_other_states表示该顺序适用于另一轴的全部状态。两个轴分别一项，不枚举成constraints，不重复填remaining。未明确的属性留UNKNOWN/null，不自行扩大范围。逐个人结果单调性、非线性以及只有笼统“效果不会更差”的话仍写remaining，不能近似成均值顺序。
ADOPTED=本次明确采用；NOT_ADOPTED=本次不采用，不表示为假；UNDECIDED=尚未决定；UNKNOWN=未说明；CONTRADICTED=明确否定或矛盾。未定限制不得删除。remaining仅记录上述字段无法表达的额外条件或仍未解决的事实缺口；conditions/constraints已记录的关系，无论采用、不采用或待定，均不在remaining重复。已表示的设计、数据和闭合声明也不重复。
information.sample_size保留已给样本条数；material_notes保留非科学性的数据描述、输出要求及背景，不带采用状态。资料只有样本是information的类型，不是额外科学约束；只求公式是输出要求。任何约束潜在结果、模型、参数的条件不能移入material_notes。
若用户补充已回答此前的未知项，字段引用补充说明，不把历史未知继续作为remaining阻断；可在material_notes保留处理经过及两处来源。补充与既有明确事实冲突时仍须追问，不能仅因时间较新就覆盖事实或批准假设。
若图题材料另给了干预概率数值，用given_probabilities逐项保留，并用requested_probability记录所问事件。二者分别从原文读取干预取值、事件取值、条件、人群、时期、背景；含义完全相同可使用相同名称，不同人群/时期不可统一。未知范围用空字符串或空字典，不猜测。只问一般分布公式、未指定事件时requested_probability=null。精确总体概率才是EXACT_POPULATION；试验样本比例、估计值、区间不是精确总体概率。只有原文明确采用才用ADOPTED。这些字段只用于展示材料中已有的数值，不产生科学审批或证书。已经完整保留的同一概率不在remaining重复；其他未表达限制必须继续保留。
scope_matches_question只对EXACT_POPULATION记录原文已说明的范围对应：同义表达可true，不同人群/时期/背景false，未明确null；不能推测可推广。样本概率已经由information_kind排除总体数值展示，不要求填写该对齐标记或为此追问。dag_information.sample_size只能属于该FINITE_SAMPLE共同记录；不能把其他试验的人数填到完整总体联合律中。
不要为让软件运行修改材料。字段空不等于原文没有约束。'''
AUDIT = '''独立核对源材料与候选，检查字段语义及遗漏，不批准科学假设。
逐项覆盖fields，返回{binding,scientific_approval:false,findings:[{field,verdict,evidence,reason,question}]}。
MATCH=忠实原文，包括正确保留未知；READING_ERROR=漏读/误读，question=null；NEEDS_CLARIFICATION=材料本身矛盾或含糊，question写一句具体追问。引文存在不证明支持字段。
按source_descriptions核对用户后续回答：初始“未说明”与后续明确提供同一事实是补齐信息，不是已知事实冲突。回答已补齐却继续留null/UNKNOWN属于READING_ERROR，指出遗漏的回答与字段；后续只覆盖局部、仍不清楚或与先前明确事实矛盾则不能覆盖。历史缺项句仍在来源目录不表示它仍未解决，也不提供科学批准。
特别检查联合干预是不是被拆成多个问题、处理集合和结果集合是否交换；全部图边/潜在共同原因、信息范围、否定条件是否保留。
网络的均值存在且有限声明由conditions.finite_first_moments保留状态、范围和引用，不要求再造remaining限制。未说明不得补造，局部声明不得扩展到全部所需均值；范围、均值顺序及分布限制仍须在各自字段完整核对。
变量含义和离散编码在graph.variable_definitions核对，不当成额外科学限制。原文“没有其他限制”可以由已完整列出的条件加空remaining/constraints表示，不要求新建一条采用声明或重复文字。仍须逐项核对原文是否确有未表达的限制；空列表本身不证明没有遗漏。
特别核对背景是否被升级为假设：解释混杂或处理选择的定性研究动机，可由图边加STUDY_CONTEXT保留，不要求另造ADOPTED条件；把这种背景升级成干预均值顺序或逐人单调性是READING_ERROR。反之，原文独立声明采用的概率关系、均值顺序、逐人单调性或效应符号限制，图边并未表达，移入备注或删除也是READING_ERROR。不能仅凭引文出现“更容易”等词判断是否为额外限制，应核对其研究角色与采用声明。
若有requested_probability/given_probabilities，独立核对干预值、事件值、条件、人群、时期、背景及总体/样本性质；不得把不同范围统一成同一量，也不得以模型自行算出的数值作为材料已给定。仍检查所有额外限制是否保留在完整研究记录中。
given_probabilities已完整保留的信息不要求在remaining重复。scope_matches_question只评价EXACT_POPULATION与所问量的范围对应；对SAMPLE_ESTIMATE不要求该标记，不将null或未判断当作读取错误，样本仍绝不能进入总体答案。其样本性质、原文给定的具体范围和其他信息仍须如实核对。
网络必须核对完整节点边、状态算法、政策方向、权重、全部已知均值、界、等式/不等式每个系数和范围；coverage检查任何遗漏的额外限制。constraints已完整保留的关系不必在remaining重复，不能因没有重复而报遗漏。material_notes只可保留非科学性说明，科学限制放进去是READING_ERROR；反过来把数据条数、只求公式等说明写成remaining科学限制也是READING_ERROR。同一数据事实在information和DATA_DESCRIPTION中一致重复本身不是错误；只有矛盾、遗漏或把科学条件降为备注才是不通过理由。不要要求用户修模型错误。所附reading_contract规定字段职责。
区分允许干扰与限制干扰：仅说明可以相互影响、未限制影响形式，不会缩小允许的模型集合，网络研究可在STUDY_CONTEXT保留；不能因未另列ADOPTED条件而报遗漏。无干扰、仅限某些关系的影响、同一状态下均值相等等声明则是限制，仍须逐项审核。完整安排政策未采用充分性时不需要暴露分组，不能为未使用的定义制造缺项。原文已给信息范围和缺项须在专用字段核对，不得把逐对象分布扩大为全体结果联合分布，也不得将design的未知重复成待采用假设。'''


def sources(case):
    # Lossless line-ending convention at the presentation boundary; no words,
    # row numbers or whitespace are deleted. Original case hash is also bound.
    catalog={k:v.replace('\r\n','\n').replace('\r','\n') for k,v in original_sources(case).items()}
    for sid,text in list(catalog.items()):
        for i,line in enumerate(text.split('\n'),1):
            if not line.strip():continue
            key=f'{sid}#L{i}'
            if key in catalog:raise ValueError('SOURCE_FRAGMENT_ID_COLLISION')
            catalog[key]=line
    return catalog


def source_descriptions(case):
    return {s['source_id']:s.get('label','') for s in case.get('sources',[])}


def check_citations(items, catalog):
    """Validate joint-reader evidence, including full source-table fragments.

    Plain ATE's short-quote wire limit is not this reader's contract. Exact
    fragment resolution can legitimately attach a longer original table.
    Source identity, nonempty content and verbatim inclusion still apply.
    """
    for item in items:
        citation = Citation.model_validate(item)
        if citation.source_id not in catalog:
            raise ValueError('JOINT_CITATION_UNKNOWN_SOURCE_ID: ' + citation.source_id)
        if not citation.quote or not citation.quote.strip() or citation.quote not in catalog[citation.source_id]:
            raise ValueError('JOINT_CITATION_NOT_IN_SOURCE')


def resolve_evidence(case, evidence):
    catalog=sources(case);original=original_sources(case);out=[]
    for item in evidence:
        e=Citation.model_validate(item).model_dump()
        if e['quote'] is None:
            if e['source_id'] in original or e['source_id'] not in catalog:
                raise ValueError('EXACT_SOURCE_FRAGMENT_ID_REQUIRED: '+json.dumps(dict(source_id=e['source_id'],instruction='未提供quote时，只能引用source_catalog中实际存在的#L行片段；文档总编号不能自动代表某一句原文。'),ensure_ascii=False))
            e['quote']=catalog[e['source_id']]
        try:check_citations([e],catalog)
        except ValueError as exc:
            # Keep the repair instruction ahead of bounded excerpts. A copied
            # edge table can otherwise consume the entire feedback allowance.
            raise ValueError('JOINT_CITATION_NOT_IN_SOURCE: '+json.dumps(dict(
                source_id=e['source_id'],
                instruction='quote不是该编号下连续的逐字原文。请核对实际片段编号；引用source_catalog中的#L编号时可省略quote，由程序附回完整原句。不要重复抄写长表、拼接或改写原文。原来的错误引用仍被拒绝。',
                submitted_quote_excerpt=e['quote'][:240],submitted_quote_length=len(e['quote']),
                actual_source_excerpt=catalog.get(e['source_id'],'')[:400]),ensure_ascii=False)) from exc
        out.append(e)
    return out


def fragment_citation_schema(schema, case):
    """New requests select exact original fragments, without recopying tables.

    Persisted quoted answers remain checked by _citations, including rejection
    of changed quotes. This changes the requested wire shape, not the evidence.
    """
    schema['$defs']['Citation'] = dict(type='object', additionalProperties=False,
        required=['source_id'], properties={'source_id': dict(type='string',
            enum=sorted(set(sources(case))-set(original_sources(case))),
            description='选择本轮原文片段编号；程序取回该片段的完整逐字原文，不复制或改写quote。')})
    return schema


def request(case, feedback=None):
    schema=Reading.model_json_schema()
    fragment_citation_schema(schema,case)
    skill=files('cfm_id_llm').joinpath('resources/joint_reading/SKILL.md').read_text('utf8')
    return dict(system_prompt=skill+'\n'+RULES+'\n本轮evidence只填系统给出的#L原文片段source_id，不输出quote；程序按该编号取完整原句。可以同时引用多段。不能自造编号。',user_prompt=json.dumps(dict(source_catalog=sources(case),source_descriptions=source_descriptions(case),
        output_schema=schema,reading_feedback_not_evidence=feedback),ensure_ascii=False))


def inspect(case, raw):
    value=Reading.model_validate(raw).model_dump(mode='json')
    # Historical bindings must not change merely because a new source field exists.
    for key in ('requested_probability','given_probabilities'):
        if key not in raw:value.pop(key,None)
    for item,original in zip(value.get('given_probabilities',[]),raw.get('given_probabilities',[])):
        if 'scope_matches_question' not in original:item.pop('scope_matches_question',None)
    if value.get('graph') and 'variable_definitions' not in raw['graph']['value']:
        value['graph']['value'].pop('variable_definitions',None)
    if value.get('dag_information') and 'jointly_observed' not in raw['dag_information']['value']:
        value['dag_information']['value'].pop('jointly_observed',None)
    def walk(x,path='reading'):
        if isinstance(x,dict):
            if 'evidence' in x:
                try:x['evidence']=resolve_evidence(case,x['evidence'])
                except ValueError as exc:raise ValueError(path+'.evidence: '+str(exc)) from exc
                for e in x['evidence']:
                    try:check_citations([e],sources(case))
                    except ValueError as exc:
                        raise ValueError('JOINT_CITATION_NOT_IN_SOURCE: '+json.dumps(dict(
                            source_id=e['source_id'],quote=e['quote'],
                            actual_source_excerpt=sources(case).get(e['source_id'],'')[:800],
                            instruction='保留实际行号，或逐行引用连续原文；不要合并改写多行。'),ensure_ascii=False)) from exc
                if not x['evidence'] and x.get('status')!='UNKNOWN' and ('status' in x or x.get('value') is not None):
                    raise ValueError('JOINT_READING_EVIDENCE_REQUIRED')
            for k,v in x.items():walk(v,path+'.'+k)
        elif isinstance(x,list):
            for i,v in enumerate(x):walk(v,path+'.'+str(i))
    walk(value)
    keys=[c['code'] for c in value['conditions']]
    if len(keys)!=len(set(keys)):raise ValueError('JOINT_DUPLICATE_CONDITION')
    return value


def fields(reading):
    result={k:v for k,v in reading.items() if v is not None and not isinstance(v,list)}
    required={'DAG_JOINT':('dag_target','graph','dag_information'),
              'NETWORK_JOINT_MEANS':('network','exposure','design','network_target','mean_information','bounds')}
    for k in required.get(reading['family']['value'],()):
        # An omitted block must itself be checked against the source, rather
        # than disappearing from the audit and becoming a question to users.
        result.setdefault(k,dict(value=None,evidence=[],check='原文是否确实未提供这一项？若已有明确内容，判为漏读。'))
    for k in ('conditions','constraints','mean_orders','remaining','material_notes','given_probabilities'):
        result.update({f'{k}.{i}':v for i,v in enumerate(reading.get(k,[]))})
    for i,row in enumerate(reading.get('given_probabilities',[])):
        if 'scope_matches_question' in row and row['information_kind']=='EXACT_POPULATION':
            result[f'given_probability_alignment.{i}']=dict(
                requested=reading.get('requested_probability'),dag_target=reading.get('dag_target'),provided=row,
                evidence=row['evidence'],question='独立对照原问题及全部材料，核对scope_matches_question是否正确：人群、时期、背景和条件是否指同一量？同义表达不因字面不同判错；不得默认外推或把不同范围视为同一量。标记不忠实原文是READING_ERROR。')
    target=reading.get('network_target') or reading.get('dag_target')
    if target:
        result['target_scope_crosscheck']={'target':target,
            'evidence':target['evidence'],
            'question':'对照原问题与全部附件独立核对时期、完整名单、比较方向、结果定义和信息覆盖；不能仅检查候选自己的描述是否一致。'}
    result['coverage']={'candidate':reading}
    return result


def binding(case, reading):return digest([VERSION,sources(case),reading])


def audit_request(case, reading, *, field_catalog=None, reading_contract=None):
    skill=files('cfm_id_llm').joinpath('resources/joint_reading/SKILL.md').read_text('utf8')
    schema=SourceAudit.model_json_schema()
    schema['properties']['binding'].update(const=binding(case,reading),
        description='Copy input_binding exactly. This identifier is supplied by the caller; do not calculate or invent one.')
    schema['$defs']['Citation']=Citation.model_json_schema()
    schema['$defs']['Citation']['properties']['source_id']['enum']=sorted(sources(case))
    checked_fields=fields(reading) if field_catalog is None else field_catalog
    schema['$defs']['AuditFinding']['properties']['field']['enum']=list(checked_fields)
    # Encode the same verdict/question rule enforced below. Correctly retaining
    # an unknown value can MATCH; the planner will ask about required gaps.
    schema['$defs']['AuditFinding']['allOf']=[dict(
        **{'if':dict(properties=dict(verdict=dict(const='NEEDS_CLARIFICATION'))),
           'then':dict(properties=dict(question=dict(type='string',minLength=1,pattern=r'\S'))),
           'else':dict(properties=dict(question=dict(type='null')))})]
    schema['properties']['findings'].update(minItems=len(checked_fields),maxItems=len(checked_fields))
    request = dict(system_prompt=AUDIT+'\nMATCH和READING_ERROR的question均须为null。候选准确保留原文未说明的null时，可以MATCH，不在该条同时追问；后续适用条件检查会提出必要问题。候选已经误填时用READING_ERROR，先后台重读，不请用户修候选。只有原文本身的歧义需要澄清时用NEEDS_CLARIFICATION，并填写具体问题。'
        +'\n引用证据推荐只填系统提供的#L片段source_id，quote省略或null；程序会附回该片段原文。'
        +'\n区分文字含义冲突与数学不可行：若原文明确定量条件且明确均采用，候选逐项正确保留，即使联立后可能无解也应判MATCH，交数学库核验不可行；不要求用户再次确认是否采用。只有原文对同一条件的取值、范围或采用态度互相矛盾/不明确时才追问。',user_prompt=json.dumps(dict(input_binding=binding(case,reading),
        source_catalog=sources(case),source_descriptions=source_descriptions(case),reading_contract=reading_contract or skill+'\n'+RULES,fields=checked_fields,
        output_schema=schema),ensure_ascii=False))
    from .design_scope_audit import augment
    return augment(request, reading)


def check_audit(case, reading, raw, *, field_catalog=None, current=False):
    from copy import deepcopy
    raw=deepcopy(raw)
    design_version=raw.pop('design_scope_version',None)
    design_scope=raw.pop('design_scope',None)
    if isinstance(raw,dict) and isinstance(raw.get('findings'),list):
        for f in raw['findings']:
            if isinstance(f,dict) and isinstance(f.get('evidence'),list):f['evidence']=resolve_evidence(case,f['evidence'])
    audit=SourceAudit.model_validate(raw).model_dump(mode='json')
    if audit['binding']!=binding(case,reading):raise ValueError('JOINT_AUDIT_STALE')
    expected=fields(reading) if field_catalog is None else field_catalog
    if sorted(x['field'] for x in audit['findings'])!=sorted(expected):
        raise ValueError('JOINT_AUDIT_COVERAGE: field必须逐字等于'+json.dumps(list(expected))+'，不能用条件名称替换数字下标，也不要增加未列出的字段。')
    for x in audit['findings']:
        check_citations(x['evidence'],sources(case))
        if expected[x['field']].get('evidence') and not x['evidence']:raise ValueError('JOINT_AUDIT_EVIDENCE')
        if ((x['verdict']=='NEEDS_CLARIFICATION') != bool(x['question'])
                or (x['verdict']=='NEEDS_CLARIFICATION' and not x['question'].strip())):
            expected_question='一句具体、非空的追问' if x['verdict']=='NEEDS_CLARIFICATION' else 'null'
            raise ValueError('JOINT_AUDIT_QUESTION: field='+x['field']+', verdict='+x['verdict']+
                ', question应为'+expected_question+'。重新对照原文决定判定；不要为了格式通过把读取错误改成MATCH。')
    from .design_scope_audit import check
    return check(case,reading,audit,design_version,design_scope,current=current)


def check_audit_current(case, reading, raw):
    return check_audit(case, reading, raw, current=True)
