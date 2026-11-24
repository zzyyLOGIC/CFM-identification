"""Versioned internal study model with independent dimensions and source ownership.

This is the general internal read model, not an LLM output schema or executor.
Executable fixed-policy, randomized local-effect and observational target
subsets live in research_spec_policy, research_spec_local and
research_spec_observational with shared research_spec_coordinates. Their
boundary adapters construct native inputs without restoring this view.
Other families still use their existing native constructors. Unknown expressions
remain expressions; templates never grant scientific approval.
"""
from dataclasses import dataclass

from .research_spec_catalog import (FACET_DIMENSIONS, DESIGN_LOOKUP, EXPOSURE_LOOKUP,
                                    ASSUMPTION_ROLES, METHOD_NAVIGATION)
from .research_spec_projection import expand, Projection
from .research_spec_view import _load


VERSION = 'internal-study-model/1'


@dataclass(frozen=True)
class Definition:
    value: str
    label: str
    source_ref: str
    rule: str


@dataclass(frozen=True)
class Property:
    key: str
    label: str
    state: str
    source_refs: tuple[str, ...] = ()
    definitions: tuple[Definition, ...] = ()


@dataclass(frozen=True)
class Component:
    facet: str
    source_root: str
    properties: tuple[Property, ...]
    unsplit_refs: tuple[str, ...] = ()
    role_tags: tuple[str, ...] = ()

    def property(self, key):
        return next(p for p in self.properties if p.key == key)


@dataclass(frozen=True)
class InternalStudy:
    projection: Projection
    components: tuple[Component, ...]
    version: str = VERSION

    def resolve(self, ref):
        """One authoritative source slot per path, even when referenced twice."""
        return next(e.value for e in self.projection.entries if e.pointer == ref)

    def for_facet(self, facet):
        if facet not in FACET_DIMENSIONS:
            raise ValueError('UNKNOWN_FACET: ' + facet)
        return tuple(c for c in self.components if c.facet == facet)

    def to_legacy(self):
        # A consumer must not edit descriptors and silently execute stale inputs.
        if self.version != VERSION or self.components != _components(self.projection):
            raise ValueError('INTERNAL_MODEL_CHANGED: edit the native input and rebuild; old approval cannot migrate')
        return self.projection.restore_legacy()

    def as_dict(self):
        self.to_legacy()
        def prop(p):
            return dict(key=p.key,label=p.label,state=p.state,source_refs=list(p.source_refs),
                        definitions=[dict(value=d.value,label=d.label,source_ref=d.source_ref,rule=d.rule)
                                     for d in p.definitions])
        return dict(version=self.version,source_contract=self.projection.contract,
                    executable=False,scientific_approval=False,
                    facets={facet:[dict(source_root=c.source_root,properties=[prop(p) for p in c.properties],
                                        unsplit_refs=list(c.unsplit_refs),role_tags=list(c.role_tags),
                                        nested_components=[other.source_root for other in self.for_facet(facet)
                                                           if other.source_root.startswith(c.source_root+'/')])
                                   for c in self.for_facet(facet)] for facet in FACET_DIMENSIONS},
                    # Values exist only here. Internal properties reference this store.
                    source=self.projection.as_dict(),
                    method_identifiers=dict(METHOD_NAVIGATION),
                    not_recorded_meaning='not separately recorded; neither false nor not applicable')


OWNERS = {
    'target': ('target','targets','requests','query','target_semantics'),
    'assignment': ('assignment','assignment_design','design','base_design'),
    'exposure': ('exposure','signature','r2_signature'),
    'structure': ('study','graph','structure','network'),
    'information': ('information','r1b_sources','r2_sources','source','sources','a4','bounded_model'),
    'assumptions': ('assumptions','scientific_statements','assumption_choices','conditions','mean_sufficiency',
                    'first_stage_exclusion','sufficiency','r2_sufficiency','bounded_model','license'),
}


def _tokens(pointer):
    return [x.replace('~1','/').replace('~0','~') for x in pointer.split('/')[1:]]


def _owner(entry):
    """Locate an existing object, not a new study/target inferred from its values."""
    raw=entry.pointer.split('/')[1:]
    tokens=_tokens(entry.pointer)
    if entry.facet=='assumptions':
        flat={'bounds':('bounds','value'),'bounds_kind':('bounds','value'),'bounds_scope':('bounds','scope'),
              'node_orders':('node_orders','value'),'order_direction':('node_orders','value'),'order_scope':('node_orders','scope'),
              'monotonicity':('monotonicity','value'),'randomization_claim':('randomization_claim','value'),
              'consistency_claim':('consistency_claim','value'),'moments_claim':('moments_claim','value'),
              'mean_sufficiency_claim':('mean_sufficiency_claim','value'),
              'mean_sufficiency_scope':('mean_sufficiency_claim','scope')}
        for i,key in enumerate(tokens):
            if key in flat:
                concept,field=flat[key]
                return '/'+ '/'.join(raw[:i]+[concept]),[field]+tokens[i+1:]
    for i,key in enumerate(tokens):
        if key not in OWNERS[entry.facet]:
            continue
        end=i+1
        if end<len(tokens) and tokens[end].isdecimal():
            end+=1
        if entry.facet=='assignment' and end<len(tokens) and tokens[end]=='base_design':
            end+=1  # D8's base law is a related component, not another outer law.
        if entry.facet=='assumptions' and key in ('assumptions','assumption_choices') and end<len(tokens):
            # A named proposition, not a flat collection of all adoption statuses.
            fields={f for d in FACET_DIMENSIONS['assumptions'] for f in d.legacy_fields}
            if tokens[end] not in fields:
                end+=1
        return '/'+ '/'.join(raw[:end]),tokens[end:]
    # Flattened native contracts use their original enclosing record as owner.
    if 'materials' in tokens:
        end=tokens.index('materials')+1
        return '/'+ '/'.join(raw[:end]),tokens[end:]
    if 'problem' in tokens:
        end=tokens.index('problem')+1
        for i,key in enumerate(tokens[:-1]):
            if key in ('study','inquiry','task','spec','identification_spec'):
                end=i+1
            elif key=='components' and i+1<len(tokens) and tokens[i+1].isdecimal():
                end=i+2
        return '/'+ '/'.join(raw[:end]),tokens[end:]
    return '',tokens


def _definitions(entry):
    """Only exact existing machine templates imply normalized attribute values."""
    v=entry.value
    if type(v) is not str:
        return ()
    leaf=_tokens(entry.pointer)[-1] if entry.pointer else ''
    lookup=DESIGN_LOOKUP if entry.facet=='assignment' else EXPOSURE_LOOKUP
    serialized=False
    if entry.facet=='assignment' and leaf=='assignment_design_json':
        try:
            decoded=_load(v)
        except ValueError:
            return ()
        if type(decoded) is not dict or type(decoded.get('kind')) is not str:
            return ()
        v=decoded['kind'];leaf='kind';serialized=True
    if entry.facet in ('assignment','exposure') and leaf in ('kind','design','exposure','grouping'):
        template=lookup.get(v)
        if template:
            attrs=template.attributes
            if v=='iid_bernoulli_binary_v1':
                attrs=tuple((key,'independent_iid_bernoulli','独立同概率 Bernoulli；保留原标量 p')
                            if key=='joint_law' else (key,value,label) for key,value,label in attrs)
            rule=('serialized-template/' if serialized else 'template/')+template.key
            return tuple((key,Definition(value,label,entry.pointer,rule))
                         for key,value,label in attrs)
    if entry.facet=='target' and leaf=='kind':
        known={
            'FIXED_POLICY_MEAN':(('endpoint_function','mean','每端总体均值'),('operation','identity','单端原值')),
            'policy_mean':(('endpoint_function','mean','每端总体均值'),('operation','identity','单端原值')),
            'FIXED_POLICY_CONTRAST':(('endpoint_function','mean','每端总体均值'),),
        }
        return tuple((key,Definition(value,label,entry.pointer,'target-kind/'+v))
                     for key,value,label in known.get(v,()))
    return ()


def _is_unknown(entry):
    v=entry.value
    return v is None or type(v) is str and v in ('UNKNOWN','UNDECIDED','NOT_STATED','CONFLICTING')


def _components(projection):
    groups={}
    raw_record=projection.restore_legacy()
    dag_contract=(projection.contract in ('dag-problem','dag-facts') or
                  projection.contract=='math-request' and str(raw_record.get('operation','')).startswith('DAG_'))
    for e in projection.entries:
        if e.facet not in FACET_DIMENSIONS:
            continue
        root,relative=_owner(e)
        group=groups.setdefault((e.facet,root),{'fields':{},'definitions':{},'unsplit':[],'roles':set()})
        field=relative[0] if relative else (_tokens(e.pointer)[-1] if e.pointer else '')
        axes=[d.key for d in FACET_DIMENSIONS[e.facet] if field in d.legacy_fields]
        # A source condition retains its proposition/attitude/scope independently.
        if e.facet=='assumptions':
            code=e.value if field=='code' and type(e.value) is str else root.rsplit('/',1)[-1]
            group['roles'].update(ASSUMPTION_ROLES.get(code,()))
            if not axes and not relative:
                axes=['proposition']
        # A generic edge key in a graph object denotes variable edges, not units.
        if e.facet=='structure' and field=='edges' and ('graph' in _tokens(root) or dag_contract):
            axes=['variable_graph']
        for axis in axes:
            group['fields'].setdefault(axis,[]).append(e)
        if not axes:
            group['unsplit'].append(e.pointer)
        for axis,definition in _definitions(e):
            group['definitions'].setdefault(axis,[]).append(definition)
    result=[]
    for (facet,root),group in groups.items():
        # Attach source pointers to the same declaration; do not copy approval.
        if facet=='assumptions' and root:
            group['fields']['evidence']=[e for e in projection.entries
                if e.facet=='evidence' and e.pointer.startswith(root+'/')]
        properties=[]
        for axis in FACET_DIMENSIONS[facet]:
            entries=group['fields'].get(axis.key,[])
            defs=tuple(group['definitions'].get(axis.key,()))
            if len({d.value for d in defs})>1:
                state='CONFLICTING_DEFINITIONS'
            elif any(_is_unknown(e) for e in entries):
                state='UNRESOLVED_OR_PARTLY_UNRESOLVED'
            elif defs:
                state='DEFINED_BY_ORIGINAL_TEMPLATE'
            elif entries:
                state='RECORDED_EXPRESSION'
            else:
                state='NOT_SEPARATELY_RECORDED'
            properties.append(Property(axis.key,axis.label,state,tuple(e.pointer for e in entries),defs))
        result.append(Component(facet,root,tuple(properties),tuple(group['unsplit']),tuple(sorted(group['roles']))))
    return tuple(result)


def from_projection(projection):
    """Internal dimensions reference original fields; no new authoritative copies."""
    model=InternalStudy(projection,_components(projection))
    model.to_legacy()
    return model


def build_internal_study(view):
    return from_projection(expand(view))
