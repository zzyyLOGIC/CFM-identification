"""Closed bindings for three distinct views of existing Identification capability.

Registration never establishes applicability, supplies a review, or enables a
fallback. Only audited structure/target fields select a reader; its existing
inspector, native contracts and independent verifiers retain all authority.
"""
from dataclasses import asdict, dataclass
from typing import Callable
from .research_route_workflow import RouteCapability


class RegistryError(ValueError):
    """A wiring error, not a scientific coverage or identification conclusion."""


@dataclass(frozen=True)
class MethodBinding:
    method_id: str
    native_route_ids: tuple[str, ...]
    producers: tuple[Callable, ...]
    replayers: tuple[Callable, ...]


@dataclass(frozen=True)
class BusinessBinding:
    reader_id: str
    structure: str
    target_kinds: tuple[str, ...]
    scope: str
    methods: tuple[MethodBinding, ...]
    inspect: Callable
    decode_reviews: Callable
    execute: Callable
    note_review: bool = False
    information_evidence_review: bool = False
    assignment_family: str | None = None


def business_bindings():
    # Static imports only. Caller text can never choose an import or function.
    from . import network_policy_dispatch as mean, network_contrast_dispatch as contrast
    from . import dag_method_dispatch as dag
    from . import network_effect_dispatch as effects
    from . import network_observational_policy_dispatch as observational
    from . import network_extended_dispatch as extended
    from cfm_id_llm import network_extended_reading as extended_reading
    from . import policy_methods, local_methods, observational_methods, finite_policy_methods, dag_methods
    def policy_bindings(operation):
        return tuple(MethodBinding(m.method_id, m.native_route_ids, m.producers, m.replayers)
                     for m in policy_methods.methods(operation))
    def local_bindings(operation):
        return tuple(MethodBinding(m.method_id, m.native_route_ids, m.producers, m.replayers)
                     for m in local_methods.methods(operation))
    def observational_bindings(operation):
        return tuple(MethodBinding(m.method_id, m.native_route_ids, m.producers, m.replayers)
                     for m in observational_methods.methods(operation))
    bindings = (
        BusinessBinding(mean.FAMILY, 'UNIT_NETWORK', ('FIXED_POLICY_VALUE',),
            'One complete fixed policy, declared evaluation population and equal mean; native scope checks remain required.',
            policy_bindings(policy_methods.MEAN),
            mean.inspect_methods, mean.native_reviews_from_json, mean._execute_plan, True, True),
        BusinessBinding(contrast.FAMILY, 'UNIT_NETWORK', ('TOTAL_EFFECT',),
            'Only first minus second of two complete fixed policies with one population, outcome and context; not arbitrary total effects.',
            policy_bindings(policy_methods.DIFFERENCE),
            contrast.inspect_methods, contrast.native_reviews_from_json, contrast._execute_plan, True, True),
        BusinessBinding('VARIABLE_DAG_FACTS', 'VARIABLE_DAG', ('INTERVENTIONAL_DISTRIBUTION',),
            'Existing finite variable DAG contracts only; no network/DAG composition.',
            tuple(MethodBinding(m.method_id, m.native_route_ids, m.producers, m.replayers)
                  for m in dag_methods.methods()),
            dag.inspect_methods, dag.native_reviews_from_json, dag._execute_plan),
        BusinessBinding(effects.FAMILY, 'UNIT_NETWORK', effects.TARGET_KINDS,
            'Direct, spillover and local total contrasts under the original conditional design; explicit fixed evaluation population and reviews. D1/strict-majority supports external review; other native D1-D6/E1-E5 combinations retain synthetic-only admission. Complete-policy TOTAL_EFFECT uses the separate contrast reader.',
            local_bindings(local_methods.DIFFERENCE),
            effects.inspect_methods,effects.native_reviews_from_json,effects._execute_plan,True),
        BusinessBinding(observational.FAMILY, 'UNIT_NETWORK', ('FIXED_POLICY_VALUE',),
            'Finite observational policy mean at fixed pretreatment W; explicit population law and conditional exchangeability. Full-policy support, or separately reviewed all-assignment mean sufficiency and signature support. Synthetic research review.',
            observational_bindings(observational_methods.MEAN),
            observational.inspect_methods,observational.native_reviews_from_json,observational._execute_plan,
            note_review=True,assignment_family='OBSERVATIONAL'),
    ) + tuple(BusinessBinding(family,'UNIT_NETWORK',kinds,scope,
        local_bindings(local_methods.ARM_MEAN) if family == extended_reading.ARM else
        observational_bindings(observational_methods.DIFFERENCE) if family == extended_reading.OBS else
        tuple(MethodBinding(m.method_id,m.native_route_ids,m.producers,m.replayers)
              for m in finite_policy_methods.methods()),
        extended.inspect_methods,extended.native_reviews_from_json,extended._execute_plan,
        note_review=True,assignment_family=regime)
        for family,kinds,scope,regime in (
            (extended_reading.ARM,('NETWORK_DESIGN_STANDARDIZED_ARM_MEAN',),
             'One explicit node-arm mean under original conditional design; D1-D6/E1-E5, synthetic review.',None),
            (extended_reading.MIX,('STOCHASTIC_POLICY_VALUE',),
             'Explicit finite complete policies and positive weights; each complete policy independently verified; synthetic review.',None),
            (extended_reading.OBS,effects.TARGET_KINDS,
             'Fixed-W observed-law standardized effects or separately licensed shared-stratum/local-binary-covariate exposure effects; native A4 and scope guards retained; synthetic review.','OBSERVATIONAL')))
    keys = [(b.structure, kind, b.assignment_family) for b in bindings for kind in b.target_kinds]
    if len(set(keys)) != len(keys) or len({b.reader_id for b in bindings}) != len(bindings):
        raise RegistryError('DUPLICATE_BUSINESS_REGISTRATION')
    for b in bindings:
        if not b.target_kinds:
            raise RegistryError('EMPTY_TARGET_REGISTRATION')
        ids = [m.method_id for m in b.methods]
        if not ids or len(set(ids)) != len(ids):
            raise RegistryError('DUPLICATE_OR_EMPTY_METHOD_REGISTRATION')
        if not all(callable(f) for f in (b.inspect, b.decode_reviews, b.execute)):
            raise RegistryError('MISSING_BUSINESS_HANDLER')
        for m in b.methods:
            if not m.native_route_ids or not m.producers or not m.replayers or not all(
                    callable(f) for f in (*m.producers, *m.replayers)):
                raise RegistryError('MISSING_NATIVE_PRODUCER_OR_REPLAYER')
    return bindings


def business_binding(reader_id):
    if type(reader_id) is str:
        for b in business_bindings():
            if b.reader_id == reader_id:
                return b
    raise RegistryError('UNREGISTERED_BUSINESS_READER')


def reader_for(structure, target_kind, *, assignment_family=None):
    """Select reading only, after the caller has checked the business review."""
    # OBSERVATIONAL is already an A0 fact label, not a theorem or a license.
    # Never send an explicitly observational target to a randomized contract.
    regime = 'OBSERVATIONAL' if structure=='UNIT_NETWORK' and assignment_family=='OBSERVATIONAL' else None
    for b in business_bindings():
        if b.structure == structure and target_kind in b.target_kinds and b.assignment_family==regime:
            return b
    return None


def plan_binding(plan, *, reader_id=None):
    """Reject unknown/cross-family plans before decoding or executing reviews.

    Legacy DAG plans omit fact_family. Accept that format only when every
    planned method is a registered DAG method; never default an unknown family
    or a network plan to the DAG decoder. This check does not approve the plan.
    """
    if type(plan) is not dict or type(plan.get('methods')) is not list or not plan['methods']:
        raise RegistryError('NONEMPTY_REGISTERED_METHOD_PLAN_REQUIRED')
    family = plan.get('fact_family', 'VARIABLE_DAG_FACTS')
    b = business_binding(family)
    if reader_id is not None and reader_id != b.reader_id:
        raise RegistryError('READER_AND_PLAN_FAMILY_MISMATCH')
    methods = [r.get('method') if type(r) is dict else None for r in plan['methods']]
    allowed = {m.method_id for m in b.methods}
    if any(type(m) is not str or m not in allowed for m in methods) or len(set(methods)) != len(methods):
        raise RegistryError('UNREGISTERED_OR_DUPLICATE_PLANNED_METHOD')
    return b


@dataclass(frozen=True)
class SessionBinding:
    lane_id: str
    group: str


def session_bindings():
    # Internal, explicit research sessions, not categories a business user selects.
    return (
        SessionBinding('NETWORK_D1_EFFECTS', 'NETWORK_EFFECTS'),
        SessionBinding('MEAN_ORDER_D2_E1', 'MEAN_ORDER'),
        SessionBinding('DAG_CLASSICAL_BACKDOOR', 'DAG'),
        SessionBinding('DAG_ADJUSTMENT', 'DAG'),
        SessionBinding('DAG_CLASSICAL_FRONTDOOR', 'DAG'),
        SessionBinding('NETWORK_FIXED_POLICY', 'POLICY'),
        SessionBinding('NETWORK_FIXED_COMPARISON', 'POLICY'),
        SessionBinding('BOUNDED_POLICY_MEAN_D2_E1', 'POLICY'),
        SessionBinding('BOUNDED_POLICY_CONTRAST_D2_E1', 'POLICY'),
    )


def session_lanes(group=None):
    return tuple(s.lane_id for s in session_bindings() if group is None or s.group == group)


def _name(f):
    return f.__module__ + '.' + f.__qualname__


def inventory():
    """Fresh descriptive JSON. Editing it never changes executable bindings."""
    from .method_catalog import homepage_entries
    from .dedicated_entries import inventory as dedicated_inventory
    bindings = business_bindings()
    readers = [dict(reader_id=b.reader_id, structure=b.structure, target_kinds=list(b.target_kinds), scope=b.scope,
        **(dict(assignment_family=b.assignment_family) if b.assignment_family is not None else {}),
        inspect=_name(b.inspect), decode_reviews=_name(b.decode_reviews), execute=_name(b.execute),
        methods=[dict(method_id=m.method_id, native_route_ids=list(m.native_route_ids),
            producers=[_name(f) for f in m.producers], replayers=[_name(f) for f in m.replayers]) for m in b.methods])
        for b in bindings]
    connected = {r for b in bindings for m in b.methods for r in m.native_route_ids}
    native = [dict(r, common_business_routes=[x for x in r['route_ids'] if x in connected],
        native_only_routes=[x for x in r['route_ids'] if x not in connected]) for r in separate_entries()]
    return dict(version='identification-capability-registry-2',
        scope='Maintained capabilities only; not an inventory of all historical backends.',
        formal_research_adapters=[r.describe() for r in registrations()],
        dedicated_entries=dedicated_inventory(),
        separate_native_entries=native, common_business_readers=readers,
        homepage_adapters=homepage_entries(),
        method_description_catalog='cfm_id.method_catalog.catalog',
        internal_research_sessions=[dict(lane_id=s.lane_id, group=s.group) for s in session_bindings()],
        registration_is_applicability=False, creates_reviews=False, automatic_fallback=False,
        production_admission=False, estimation_handoff_allowed=False)


# Native registration records also feed the legacy research catalog.

@dataclass(frozen=True)
class Registration:
    adapter_type:type
    problem_type:type
    review_type:type
    version:str
    review_scope:str
    review_form:str
    claim_kinds:tuple[str,...]
    business_entry:str|None
    @property
    def capability(self)->RouteCapability:return self.adapter_type.capability
    def describe(self):
        return dict(**asdict(self.capability),problem_version=self.version,
            problem_type=self.problem_type.__name__,review_type=self.review_type.__name__,
            review_scope=self.review_scope,review_form=self.review_form,claim_kinds=list(self.claim_kinds),
            callable_here=True,requires_explicit_selection=True,creates_reviews=False,
            business_entry=self.business_entry,
            business_reading_checked_by_this_entry=False,production_admission=False,
            estimation_handoff_allowed=False)

def registrations():
    # Fixed imports only. Neither material text nor route IDs choose a module path.
    from .research_route_adapters import MeanOrderRoute
    from . import dag_methods
    from .iv_route_contract import IVProblem,IVReview
    from .iv_research_adapter import BinaryIVRoute
    from .mean_order_contract import MeanOrderProblem,ReviewedMeanOrder
    def dag_registration(method_id):
        m=dag_methods.resolve(method_id)
        return Registration(m.adapter_type,m.problem_type,m.review_type,m.version,
            'EXTERNAL_DECLARATIVE_RESEARCH_OR_SYNTHETIC_TEST','PER_CONDITION_ACCEPTED_PENDING_REJECTED',
            ('POINT',),'evaluation.dag_business_workflow')
    return (
        dag_registration(dag_methods.BACKDOOR),
        dag_registration(dag_methods.ADJUSTMENT),
        Registration(MeanOrderRoute,MeanOrderProblem,ReviewedMeanOrder,'mean-order-d2-e1-1',
            'SYNTHETIC_TEST_ONLY','EXPLICIT_TRUE_SYNTHETIC_ATTESTATIONS',
            ('POINT','PARTIAL','INCOMPATIBLE'),'cfm_id.workflows.mean_order'),
        dag_registration(dag_methods.FRONTDOOR),
        Registration(BinaryIVRoute,IVProblem,IVReview,'binary-iv-research-1',
            'SEPARATE_SOURCE_READING_AND_SCIENTIFIC_REVIEW','PER_CONDITION_ACCEPTED_PENDING_REJECTED',
            ('POINT','PARTIAL','INCOMPATIBLE'),None),
    )

def separate_entries():
    # Current maintained lanes, not an exhaustive inventory of historical backends.
    from .method_compat import native_network_routes
    return [
        dict(entry_id='NETWORK_POINT_EXISTING_BUSINESS',route_ids=native_network_routes(),
            entry='pfn_pipeline.identification_business',
            reason='Native business/scientific context and route-specific reviews remain required.'),
        dict(entry_id='BOUNDED_POLICY_MEAN_D2_E1',route_ids=['BOUNDED_POLICY_MEAN_D2_E1'],
            entry='cfm_id.bounded_policy',
            reason='Preserve original POINT admission, assignment review and separately bound bounded-policy review.'),
        dict(entry_id='BOUNDED_POLICY_CONTRAST_D2_E1',route_ids=['BOUNDED_POLICY_CONTRAST_D2_E1'],
            entry='cfm_id.bounded_contrast',
            reason='Preserve both endpoint contexts, assignment reviews and joint contrast review.'),
        dict(entry_id='BOUNDED_POLICY_MEAN_D2_E4',route_ids=['BOUNDED_POLICY_MEAN_D2_E4'],
            entry='cfm_id.bounded_policy',
            reason='CountMeanInformation and separate ReviewedCountPolicy; common business reader connected, synthetic review only.'),
        dict(entry_id='BOUNDED_POLICY_CONTRAST_D2_E4',route_ids=['BOUNDED_POLICY_CONTRAST_D2_E4'],
            entry='cfm_id.bounded_contrast',
            reason='Common exact-count model and ReviewedCountContrast; common reader connected, both endpoint reviews remain required.'),
        dict(entry_id='BOUNDED_POLICY_MEAN_FINITE',route_ids=['BOUNDED_POLICY_MEAN_FINITE'],
            entry='cfm_id.bounded_policy',
            reason='D1-D8/E1-E5 finite mean boxes: D1-D6 <=12 nodes, D7/D8 <=8; complete reviewed information and no extra coupling. Numeric legacy sessions; symbolic formulas through common business dispatch only. Synthetic only.'),
        dict(entry_id='BOUNDED_POLICY_CONTRAST_FINITE',route_ids=['BOUNDED_POLICY_CONTRAST_FINITE'],
            entry='cfm_id.bounded_contrast',
            reason='Same finite model, ordered policies and shared coordinates; exact joint signed objective, synthetic only.'),
        dict(entry_id='LLM_UNVERIFIED_RESEARCH',route_ids=[],
            entry='evaluation.business_candidate_feedback',
            reason='Restricted existing research lane; unverified prose is never a certified mathematical claim.'),
    ]
