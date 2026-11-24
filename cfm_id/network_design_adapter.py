"""Reviewed business D/E records -> existing native constructors.

No design inference, theorem implementation, support calculation or automatic
scientific admission. Call constructors only after the dispatch reviews pass.
"""
from cfm_id_llm import network_design_reading as fields
from .research_spec_catalog import BUSINESS_NATIVE_DESIGNS, DESIGN_PROTOCOLS


NATIVE_DESIGNS = dict(BUSINESS_NATIVE_DESIGNS)


def design_payload(assignment, *, nodes=None):
    if assignment.kind not in NATIVE_DESIGNS:
        raise ValueError('COMPLETE_SUPPORTED_DESIGN_REQUIRED')
    if assignment.kind in ('UNEQUAL_PROBABILITY_FIXED_QUOTA', 'RERANDOMIZED_BALANCED'):
        if nodes is None:
            raise ValueError('TASK1_DESIGN_REQUIRES_NODE_ORDER')
        law = assignment.treated_sets is not None and assignment.set_probabilities is not None
        weights = assignment.unit_weights is not None
        if not (law ^ weights):
            raise ValueError('COMPLETE_SUPPORTED_DESIGN_REQUIRED')
        base = dict(kind='unequal_probability_fixed_quota_binary_v1',
                    nodes=tuple(nodes), m=assignment.fixed_count,
                    treated_sets=(tuple(tuple(s) for s in assignment.treated_sets)
                                  if assignment.treated_sets is not None else None),
                    set_probabilities=(tuple(assignment.set_probabilities)
                                       if assignment.set_probabilities is not None else None),
                    unit_weights=(dict(assignment.unit_weights)
                                  if assignment.unit_weights is not None else None))
        if assignment.kind == 'UNEQUAL_PROBABILITY_FIXED_QUOTA':
            return base
        return dict(kind=NATIVE_DESIGNS[assignment.kind], base_design=base,
                    balance_rule=dict(tolerance=assignment.balance_tolerance,
                                      covariates=dict(assignment.balance_covariates)))
    if any(getattr(assignment, name) is None for name in fields.DESIGN_FIELDS[assignment.kind]):
        raise ValueError('COMPLETE_SUPPORTED_DESIGN_REQUIRED')
    result = dict(kind=NATIVE_DESIGNS[assignment.kind])
    aliases = {'probabilities':'propensities', 'fixed_count':'m'}
    for name in fields.DESIGN_FIELDS[assignment.kind]:
        value = getattr(assignment, name)
        if isinstance(value, list):
            value = tuple(tuple(v) if isinstance(v,list) else v for v in value)
        result[aliases.get(name,name)] = value
    return result


def exposure_payload(exposure):
    """Reviewed exposure record -> native constructor kwargs.

    E1-E5 -> {grouping, core_collaborators}; Task-1 weighted/grouped exposures
    carry their exact weights+mode or groups, and the grouping label selects the
    exact enumeration path in the native constructor.
    """
    cores = exposure.core_collaborators
    if exposure.kind == 'WEIGHTED_EXPOSURE':
        grouping = ('weighted_exposure_sum' if exposure.mode == 'sum'
                    else 'weighted_exposure_proportion')
        return dict(grouping=grouping, core_collaborators=None,
                    exposure_weights=dict(exposure.weights))
    if exposure.kind == 'GROUPED_EXPOSURE':
        return dict(grouping='grouped_exposure', core_collaborators=None,
                    exposure_groups={k: tuple(v) for k, v in exposure.groups.items()})
    return dict(grouping=fields.EXPOSURE_GROUPS[exposure.kind],
                core_collaborators=None if cores is None else {n: tuple(v) for n, v in cores.items()})


def component_gaps(c, *, local_effect=False):
    """Return material gaps and explicit exclusions; never approve conditions."""
    missing = fields.missing_assignment(c.assignment, c.study.nodes)
    excluded = []
    statement = c.first_stage_exclusion
    if c.assignment.kind == 'TWO_STAGE_QUOTA_MIXTURE':
        if statement is None or statement.status in ('NOT_STATED','UNDECIDED'):
            missing.append('first_stage_exclusion')
        elif statement.status == 'NOT_ADOPTED':
            excluded.append('DECLARED_MODEL_EXCLUDES:'+fields.D6_CONDITION)
        elif statement.status == 'CONFLICTING':
            excluded.append('CONFLICTING_FIRST_STAGE_EXCLUSION')
    elif statement is not None and statement.status != 'NOT_STATED':
        excluded.append('FIRST_STAGE_CONDITION_REQUIRES_D6_DESIGN')
    if local_effect:
        missing += fields.missing_exposure(c.exposure, c.study.nodes)
    return missing, excluded


def assignment_availability_question(declaration):
    """Unavailable design information is a gap, not a rejected causal premise.

    Keep false/null unchanged. Concrete parameters, source review and scientific
    admission are still checked separately; this helper never infers a law.
    """
    if declaration.value is not True:
        return '请核对并补充完整历史分配规则及其参数；规则资料不完整不等于当前数学方法未覆盖。'
    return None


def extra_science(c):
    return (fields.D6_CONDITION,) if c.assignment.kind == 'TWO_STAGE_QUOTA_MIXTURE' else ()


def task1_design(assignment, network):
    """Build the serializable task-1 design object from reviewed business fields.

    The network supplies the complete node ordering; the review layer has
    already validated treated-set alignment, unit-weight scope and balance-rule
    completeness. Constructs the native pydantic design for exact enumeration.
    """
    from pfn_pipeline._internal.identification.schemas import (
        UnequalProbabilityFixedQuotaDesignV1, RerandomizedBalancedDesignV1, CovariateBalanceRuleV1)
    nodes = tuple(network.node_ids)
    if assignment.kind == 'UNEQUAL_PROBABILITY_FIXED_QUOTA':
        return UnequalProbabilityFixedQuotaDesignV1(
            nodes=nodes, m=assignment.fixed_count,
            treated_sets=tuple(tuple(s) for s in assignment.treated_sets) if assignment.treated_sets is not None else None,
            set_probabilities=tuple(assignment.set_probabilities) if assignment.set_probabilities is not None else None,
            unit_weights=dict(assignment.unit_weights) if assignment.unit_weights is not None else None)
    if assignment.kind == 'RERANDOMIZED_BALANCED':
        base = UnequalProbabilityFixedQuotaDesignV1(
            nodes=nodes, m=assignment.fixed_count,
            treated_sets=tuple(tuple(s) for s in assignment.treated_sets) if assignment.treated_sets is not None else None,
            set_probabilities=tuple(assignment.set_probabilities) if assignment.set_probabilities is not None else None,
            unit_weights=dict(assignment.unit_weights) if assignment.unit_weights is not None else None)
        rule = CovariateBalanceRuleV1(
            tolerance=assignment.balance_tolerance, covariates=assignment.balance_covariates)
        return RerandomizedBalancedDesignV1(base_design=base, balance_rule=rule)
    raise ValueError('TASK1_DESIGN_KIND_REQUIRED')


def make_arm(c, network, *, source, evidence, authority='SYNTHETIC_TEST', local_question=None):
    if authority not in ('SYNTHETIC_TEST', 'EXTERNAL_RESEARCH_REVIEW'):
        raise ValueError('EXPLICIT_RESEARCH_AUTHORITY_REQUIRED')
    synthetic = authority == 'SYNTHETIC_TEST'
    if local_question is None:
        # Existing single-arm research entry; no second arm is manufactured.
        node, own, exposure = c.target.population[0], c.target.first.own, c.target.first.exposure
        outcome_kind = 'continuous' if c.study.outcome_kind=='COUNT' else c.study.outcome_kind.lower()
    else:
        from .research_spec_local import LocalQuestion
        if not isinstance(local_question, LocalQuestion) or tuple(network.node_ids) != local_question.study.node_order:
            raise ValueError('LOCAL_STUDY_NETWORK_COORDINATES_REQUIRED')
        node = local_question.evaluation.population[0]
        own, exposure = local_question.first.coordinates()
        kind = local_question.study.outcome_domain
        if kind is None:
            raise ValueError('LOCAL_NATIVE_OUTCOME_DOMAIN_REQUIRED')
        outcome_kind = 'continuous' if kind == 'count' else kind
    from pfn_pipeline import identification as native
    makers = {p.business_kind:getattr(native,p.constructor) for p in DESIGN_PROTOCOLS}
    signature = exposure_payload(c.exposure)
    grouping = signature.pop('grouping')
    exposure_definition = 'strict_majority' if grouping == 'strict_majority_ties_low' else grouping
    if c.assignment.kind in ('UNEQUAL_PROBABILITY_FIXED_QUOTA', 'RERANDOMIZED_BALANCED'):
        design = task1_design(c.assignment, network)
        return makers[c.assignment.kind](network, design=design, **signature,
            node_id=node, own_treatment_value=own,
            exposure_value=exposure, exposure_definition=exposure_definition,
            source=source, evidence=evidence, admitted=True, synthetic=synthetic,
            query_authority='TRUSTED_FIXTURE' if synthetic else 'HUMAN_CONFIRMED',
            outcome_kind=outcome_kind)
    design = design_payload(c.assignment); design.pop('kind')
    if c.assignment.kind == 'TWO_STAGE_QUOTA_MIXTURE':
        if c.first_stage_exclusion is None or c.first_stage_exclusion.status not in ('ADOPTED','PROPOSED'):
            raise ValueError('REVIEWABLE_D6_EXCLUSION_REQUIRED')
        # The caller has independently checked the D6-specific science decision.
        design['profile_exclusion_admitted'] = True
    return makers[c.assignment.kind](network, **design, **signature,
        node_id=node, own_treatment_value=own,
        exposure_value=exposure,
        exposure_definition=exposure_definition,
        source=source, evidence=evidence, admitted=True, synthetic=synthetic,
        query_authority='TRUSTED_FIXTURE' if synthetic else 'HUMAN_CONFIRMED',
        outcome_kind=outcome_kind)
