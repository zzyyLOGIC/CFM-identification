"""Unapproved input contracts for maintained native network methods.

The model reads targets, information and declarations. It never chooses a
theorem or approves a declaration. All three families share the source wire.
"""
from copy import deepcopy
from functools import partial
from fractions import Fraction
from typing import Literal,Annotated,Union
from pydantic import Field, StrictInt, field_validator
from .network_policy_reading import (Record, Cited, Declaration, Study, Assignment,
    Exposure, FirstStageExclusion, Assumptions, Information, Note, documents, exact_number)
from .network_effect_reading import LocalArm, EffectInformation
from .network_observational_policy_reading import Regime, Conditioning, AssignmentMass, request_for_model
from .source_reference_wire import catalog, expand
from . import network_population_contract as population_contract

ARM='NETWORK_RANDOMIZED_ARM_FACTS'
MIX='NETWORK_FINITE_POLICY_FACTS'
OBS='NETWORK_OBSERVATIONAL_EFFECT_FACTS'
FAMILIES=(ARM,MIX,OBS)

class ArmTarget(Cited):
    population: list[str] | None
    first: LocalArm
    averaging: Literal['ORIGINAL_DESIGN_CONDITIONAL','OTHER','UNKNOWN']
    population_fixed_before_assignment: Declaration = Field(description=population_contract.RULE)

class PolicyComponent(Cited):
    assignment: dict[str,StrictInt]
    weight: str | None
    @field_validator('weight')
    @classmethod
    def probability(cls,v):
        exact_number(v)
        if v is not None and not 0<Fraction(v)<=1:raise ValueError('POSITIVE_POLICY_WEIGHT_REQUIRED')
        return v

class MixtureTarget(Cited):
    population: list[str] | None
    aggregation: Literal['EQUAL_MEAN','OTHER','UNKNOWN']
    components: list[PolicyComponent]
    policy_distribution_complete: Declaration

class BaseReading(Record):
    reference_context: str = Field(pattern=r'^c[0-9a-f]{12}$')
    study: Study
    additional_restrictions: list[Note]
    unresolved: list[Note] = Field(description='Genuine unresolved input or interpretation only. A declared symbolic population law or mean need not have numerical values for an identification formula; absent numeric estimates alone are not an unresolved identification condition.')

class ArmReading(BaseReading):
    version: Literal['network-arm-reading-1']
    assignment: Assignment
    exposure: Exposure
    first_stage_exclusion: FirstStageExclusion | None
    assumptions: Assumptions
    target: ArmTarget
    information: list[EffectInformation]

class FinitePolicyInformation(Cited):
    operator: Literal['NODE_FULL_LAW','FULL_JOINT_LAW','ASSIGNMENT_NODE_MEANS','FINITE_SAMPLE','OTHER','UNKNOWN'] = Field(description=(
        'NODE_FULL_LAW: each listed outcome jointly with the COMPLETE treatment vector; '
        'FULL_JOINT_LAW: ALL outcomes jointly with that vector; ASSIGNMENT_NODE_MEANS: conditional means at the explicitly listed complete assignments. '
        'Do not derive extra exposure-cell tables or strengthen a nodewise law to a joint outcome law. Other supplied information must remain OTHER and be described in additional_restrictions.'))
    availability: Literal['SYMBOLIC_POPULATION_OPERATOR','FINITE_SAMPLE','UNKNOWN']
    outcome_nodes: list[str]
    assignment_cells: list[list[StrictInt]] = Field(description='Only explicitly given assignment-cell means; empty for full laws and samples. Symbolic means need no invented numerical values.')

class MixtureReading(BaseReading):
    version: Literal['network-finite-policy-reading-1']
    assignment: Assignment
    first_stage_exclusion: FirstStageExclusion | None
    assumptions: Assumptions
    target: MixtureTarget
    information: list[FinitePolicyInformation]

class ObservationalTarget(Cited):
    kind: Literal['DIRECT_EFFECT','SPILLOVER_EFFECT','LOCAL_TOTAL_EFFECT','OTHER','UNKNOWN']
    operation: Literal['FIRST_MINUS_SECOND','OTHER','UNKNOWN']
    first: LocalArm
    second: LocalArm
    population: list[str] | None
    aggregation: Literal['SINGLE','EQUAL_MEAN','OTHER','UNKNOWN']
    population_fixed_before_treatment: Declaration
    shared_outcome_and_context: Declaration
    averaging: Literal['OBSERVED_ALLOCATION_CONDITIONAL','SHARED_PRETREATMENT_STRATUM','OWN_AND_NEIGHBOR_BINARY_FEATURE','OTHER','UNKNOWN'] = Field(description=(
        'Target definition, not a method choice: average remaining arrangements by the observed conditional law at fixed W; '
        'or average exposure potential outcomes over a common pretreatment stratum B; or over each object\'s local C_i=(own binary X, number of ALL graph neighbours with X=1). Unknown stays UNKNOWN.'))

class ScopedDeclaration(Declaration):
    covered_nodes: list[str]
    scope: Literal['ALL_BINARY_ASSIGNMENTS','OTHER','UNKNOWN'] = Field(description='处理安排的适用范围，不是协变量范围。ALL_BINARY_ASSIGNMENTS表示声明覆盖所定义的全部本人与同伴处理状态/完整二元安排；按声明给定W、B或C_i不使这个范围变成OTHER。仅在历史安排或部分处理状态成立为OTHER；未说明范围为UNKNOWN。保留原文的条件变量，不能扩大为无条件独立。')

class ObservationalAssumptions(Record):
    consistency: Declaration
    fixed_pretreatment_network: Declaration
    finite_conditional_first_moments: Declaration
    full_vector_conditional_exchangeability: Declaration
    potential_outcome_exposure_sufficiency: ScopedDeclaration = Field(description='Individual potential outcomes, not merely their means, depend only on own treatment and the specified exposure, on all binary assignments for covered_nodes. Exposure definition alone does not imply this.')
    exposure_level_conditional_exchangeability: ScopedDeclaration = Field(description='Exposure potential-outcome mean independence from (own treatment, exposure) given the shared pretreatment B and fixed W. A declaration conditioned only on object-specific C_i belongs to local_covariate_exposure_mean_exchangeability; do not duplicate it here or invent shared B.')
    local_covariate_exposure_mean_exchangeability: ScopedDeclaration = Field(description='Exposure potential-outcome mean independence from (own treatment, exposure) given C_i=(own X, all-neighbour positive-X count) and fixed W. Not exchangeability given the full X vector or shared B. Scope describes which treatment states the declaration covers, separately from conditioning on C_i.')

class BernoulliComponent(Cited):
    weight: str
    probabilities: dict[str,str]

class PopulationStratum(Cited):
    label: str
    mass: str
    probabilities: dict[str,str]

class FeatureProfile(Cited):
    label: str
    mass: str
    features: dict[str,StrictInt]
    probabilities: dict[str,str] | None = None
    mixture_components: list[BernoulliComponent] = Field(default_factory=list)

class ConditionalCell(Record):
    node: str
    own: StrictInt
    exposure: StrictInt
    stratum: str | None = None
    own_feature: StrictInt | None = None
    neighbor_feature_count: StrictInt | None = None

class ObservationalInformation(Cited):
    availability: Literal['SYMBOLIC_POPULATION_OPERATOR','FINITE_SAMPLE','UNKNOWN']
    outcome_nodes: list[str]
    complete_law_and_mean_scope: Declaration = Field(description='Explicit scope declaration for this population law and its conditional outcome means. For finite tables all positive-mass rows must be listed; does not mean no other scientific restrictions exist.')
    same_study_and_context: Declaration

class FiniteLaw(ObservationalInformation):
    operator: Literal['FINITE_ASSIGNMENT_LAW'] = Field(description='Complete table of actual treatment assignments at fixed W, not a table of pretreatment feature profiles.')
    assignment_masses: list[AssignmentMass] = Field(description='Complete positive-mass assignment table at fixed W, with outcome-node conditional means covering every positive row. Never construct a table from marginals without a stated joint law.')

class FactorizedLaw(ObservationalInformation):
    operator: Literal['FACTORIZED_ARM_LAW'] = Field(description='One observational factorized treatment law at fixed W, with unadjusted own/exposure outcome means. Not a law conditional on strata or feature profiles.')
    probabilities: dict[str,str] = Field(description='Stated observational joint law factorizes into the listed node Bernoulli probabilities at fixed W. This is the full assignment law, not merely unrelated marginals, and grants no randomization assumption.')
    covered_cells: list[ConditionalCell]

class MixtureLaw(ObservationalInformation):
    operator: Literal['MIXTURE_ARM_LAW']
    mixture_components: list[BernoulliComponent] = Field(description='Only an explicitly stated mixture of observational factorized laws; a factorized law does not require inventing several mixture components.')
    covered_cells: list[ConditionalCell]

class StratifiedLaw(ObservationalInformation):
    operator: Literal['STRATIFIED_ARM_LAW'] = Field(description='Shared pretreatment stratum B: its population masses, treatment law within each B, and outcome means indexed by B and own/exposure state.')
    adjustment_variable: str = Field(description='The shared pretreatment B, its definition and labels; different from fixed W.')
    strata: list[PopulationStratum]
    covered_cells: list[ConditionalCell]

class NodewiseLaw(ObservationalInformation):
    operator: Literal['NODEWISE_ARM_LAW','NODEWISE_MIXTURE_ARM_LAW'] = Field(description='Complete pretreatment feature profiles X and their population masses; outcome means indexed by local C_i. NODEWISE_ARM_LAW has a factorized treatment law within each X profile. NODEWISE_MIXTURE_ARM_LAW has an explicitly stated mixture within each X profile. Several X profiles alone do not imply the latter.')
    adjustment_variable: str = Field(description='Each object\'s binary pretreatment X and coding. C_i uses own X and the count of ALL undirected graph neighbours with X=1, even when treatment exposure uses only core partners.')
    profiles: list[FeatureProfile]
    covered_cells: list[ConditionalCell]

class OtherInformation(Cited):
    operator: Literal['FINITE_SAMPLE','OTHER','UNKNOWN']
    availability: Literal['FINITE_SAMPLE','SYMBOLIC_POPULATION_OPERATOR','UNKNOWN']
    outcome_nodes: list[str]
    description: str = Field(description='What is actually supplied or still unknown; no invented population model. OTHER information is retained and blocks this adapter.')

PopulationInformation=Annotated[Union[FiniteLaw,FactorizedLaw,MixtureLaw,StratifiedLaw,NodewiseLaw,OtherInformation],Field(discriminator='operator')]

class ObservationalEffectsReading(BaseReading):
    version: Literal['network-observational-effects-reading-1']
    regime: Regime
    conditioning: Conditioning = Field(description='The fixed pretreatment background W held constant across the target. Do not include B or C_i/X being averaged over: those are the adjustment variables in target.averaging and information. Fixed background and averaging distribution are separate target dimensions.')
    exposure: Exposure
    target: ObservationalTarget
    assumptions: ObservationalAssumptions
    information: list[PopulationInformation]

# Model-facing fields contain only coordinates used by that declared operator.
# The canonical record above still accepts historical explicit null/empty slots;
# _information_shape rejects any nonempty slot belonging to another operator.
# Absence only fills nonassertions, never probabilities, cells or assumptions.
class ArmCellWire(Record):
    node: str
    own: StrictInt
    exposure: StrictInt

class StratumCellWire(ArmCellWire):
    stratum: str

class NodewiseCellWire(ArmCellWire):
    own_feature: StrictInt
    neighbor_feature_count: StrictInt

class ProfileWire(Cited):
    source_ids: list[str] = Field(description='本条完整X配置、总体质量和该配置内处理联合分布的共同来源。必须覆盖本条features、mass以及probabilities/mixture_components；上层information的引用不自动成为本条引用。引用对象名单/特征分布不能代替处理概率来源。')
    label: str
    mass: str
    features: dict[str,StrictInt]

class FactorizedProfileWire(ProfileWire):
    probabilities: dict[str,str]

class MixtureProfileWire(ProfileWire):
    mixture_components: list[BernoulliComponent]

class FactorizedLawWire(FactorizedLaw):
    covered_cells: list[ArmCellWire]

class MixtureLawWire(MixtureLaw):
    covered_cells: list[ArmCellWire]

class StratifiedLawWire(StratifiedLaw):
    covered_cells: list[StratumCellWire]

class NodewiseLawWire(NodewiseLaw):
    operator: Literal['NODEWISE_ARM_LAW']
    profiles: list[FactorizedProfileWire]
    covered_cells: list[NodewiseCellWire]

class NodewiseMixtureLawWire(NodewiseLaw):
    operator: Literal['NODEWISE_MIXTURE_ARM_LAW']
    profiles: list[MixtureProfileWire]
    covered_cells: list[NodewiseCellWire]

class ObservationalReadingWire(ObservationalEffectsReading):
    information: list[Annotated[Union[FiniteLaw,FactorizedLawWire,MixtureLawWire,
        StratifiedLawWire,NodewiseLawWire,NodewiseMixtureLawWire,OtherInformation],
        Field(discriminator='operator')]]

MODELS={ARM:ArmReading,MIX:MixtureReading,OBS:ObservationalEffectsReading}
GUIDANCE={
 ARM:'本题只问一个对象在本人处理和同伴状态确定时的平均结果，不作两端相减。target.population只记录明确评价对象。averaging记录其余安排是否按原随机试点条件分布平均；不能把指定的其他平均分布换成原设计。',
 MIX:'本题问随机政策的平均结果。target.components逐个记录未来完整处理方案和选择该方案的概率，不是过去试点的分配律。政策分布完整性另读；不能将随机政策换成固定政策、把权重重新归一化或补未提及对象。',
 OBS:'本题是观察性网络的局部效应。target保留第一端减第二端、共同评价范围和averaging的真实含义。OBSERVED_ALLOCATION_CONDITIONAL是在固定W下按实际采用规律对剩余安排平均，不是跨背景平均。另两种averaging问的是暴露潜在结果经过共同B或各自C_i调整后的平均效应，需要分别读取更强的个体暴露充分性与条件均值交换性，不能由暴露定义或其他交换性声明推出。信息中的factorized是观察分布的因子分解，不是随机实验许可。',
}
SYSTEM='''读取所选业务目标与原始材料，只返回符合Schema的JSON，不选择数学定理、不判断识别、不批准假设。
每个有source_ids的对象，其引用须共同支持全部语义字段；只用本次source_catalog的s编号，照抄reference_context。上游定位和模型回答不是证据。
研究单位的关系网络不是变量DAG；study保留完整对象/边、处理编码、结果及时期。固定背景与调整变量不同；明确的条件不能删掉。
Declaration.value=true仅指明确采用或拟采用；明确不采用为false，未声明或未决定为null。作用域和采用态度独立。已有专门字段完整表达的内容不重复到additional_restrictions；真正未表达的约束必须保留。unresolved保留未表达的缺项和冲突，不填写助手职责说明。
information逐来源记录范围。有限记录、样本频率和拟合概率只能是FINITE_SAMPLE，不升级为总体律。总体算子可为符号，不要求编造均值数值。概率和质量用精确有理数字符串；只有原文明确完整时才声明完整，不能补零或重新归一化。表行、覆盖范围和定义均需原文依据。
未用的列表为空、对象或数值为null，未知类别用UNKNOWN；不为了适配填默认值。'''

def reference_catalog(bundle, *, binding, family):
    return catalog(bundle,documents(bundle),binding=binding,version=MODELS[family].model_fields['version'].annotation.__args__[0])

def make_request(bundle, *, binding, family):
    from .network_design_reading import ASSIGNMENT_GUIDANCE,EXPOSURE_GUIDANCE,STAGE_GUIDANCE
    refs=reference_catalog(bundle,binding=binding,family=family)
    result=request_for_model(bundle,refs,ObservationalReadingWire if family==OBS else MODELS[family])
    result['system']=SYSTEM+'\n'+GUIDANCE[family]+'\n'+EXPOSURE_GUIDANCE
    if family!=OBS:result['system']+='\n'+ASSIGNMENT_GUIDANCE+'\n'+STAGE_GUIDANCE
    return result

def parse(bundle, raw, *, binding, family):
    refs=reference_catalog(bundle,binding=binding,family=family);model=MODELS[family]
    wire=model.model_validate(deepcopy(raw))
    if wire.reference_context!=refs['context']:raise ValueError('STALE_QUERY_REFERENCE_CONTEXT')
    c=model.model_validate(expand(wire.model_dump(),refs));nodes=c.study.nodes
    if len(nodes)!=len(set(nodes)) or any(not n.strip() for n in nodes):raise ValueError('INVALID_NODE_ROSTER')
    if any(len(e)!=2 or e[0]==e[1] or not set(e)<=set(nodes) for e in c.study.edges):raise ValueError('INVALID_NETWORK_EDGE')
    if len({frozenset(e) for e in c.study.edges})!=len(c.study.edges):raise ValueError('DUPLICATE_NETWORK_EDGE')
    if c.target.population is not None and (len(set(c.target.population))!=len(c.target.population) or not set(c.target.population)<=set(nodes)):
        raise ValueError('INVALID_TARGET_POPULATION')
    for s in c.information:
        if len(set(s.outcome_nodes))!=len(s.outcome_nodes) or not set(s.outcome_nodes)<=set(nodes):raise ValueError('INVALID_INFORMATION_ROSTER')
        if (s.operator=='FINITE_SAMPLE')!=(s.availability=='FINITE_SAMPLE'):raise ValueError('SAMPLE_POPULATION_PAIR_MISMATCH')
        if family==ARM:
            from .effect_information_rules import require_scope
            require_scope(s,nodes=nodes,exposure=c.exposure,edges=c.study.edges)
        elif family==MIX:
            from .information_field_rules import require_assignment_scope
            require_assignment_scope(s,nodes)
    return dict(facts=c.model_dump(),reference_binding=dict(context=refs['context'],context_sha256=refs['context_sha256'],aliases={k:r['source_id'] for k,r in refs['aliases'].items()}))

def contracts():
    from .fact_reading_contracts import FactReadingContract,TargetContextHandoff
    from . import query_conditioning_contract as context
    return tuple(FactReadingContract(reader_id=f,reference_format='short_refs',version_field='extended_fact_contract',
        wire_version=m.model_fields['version'].annotation.__args__[0],make_request=partial(make_request,family=f),
        parse=partial(parse,family=f),reference_catalog=partial(reference_catalog,family=f),model=m,documents=documents,
        target_context=TargetContextHandoff(context.preserve_contrast_request,context.contrast_conditioning_constraints,
            context.MATCH_DECISION,context.CONTRAST_DESCRIPTION)) for f,m in MODELS.items())
