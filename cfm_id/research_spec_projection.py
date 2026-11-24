"""Lossless display projection plus explicit template meanings, never an input contract.

Reconstruction uses classified slots and the original container structure, not a
hidden copy of the original values. It grants no review or execution authority.
Derived descriptions are not used to reconstruct or select a mathematical route.
"""
from dataclasses import dataclass
import hashlib
import json

from .research_spec_view import Entry, _dump, _load, _escape


# Compatibility exports are derived from the single internal attribute registry.
from .research_spec_catalog import ASSIGNMENT_TEMPLATES, EXPOSURE_TEMPLATES, DESIGN_LOOKUP, EXPOSURE_LOOKUP

DESIGNS = {t.legacy_id: tuple(dict((axis, label) for axis, _, label in t.attributes)[key]
    for key in ('randomization_unit','joint_law','stages','acceptance')) for t in ASSIGNMENT_TEMPLATES}
DESIGN_ALIASES = {alias:t.legacy_id for alias,t in DESIGN_LOOKUP.items()}
EXPOSURES = {t.legacy_id: tuple(label for _,_,label in t.attributes) for t in EXPOSURE_TEMPLATES}
EXPOSURE_ALIASES = {alias:t.legacy_id for alias,t in EXPOSURE_LOOKUP.items()}


def _shape(value, pointer=''):
    if type(value) in (dict,list) and not value:
        return {'slot':pointer, 'empty':'object' if type(value) is dict else 'array'}
    if type(value) is dict:
        return {'object': [[k, _shape(v, pointer+'/'+_escape(k))] for k,v in value.items()]}
    if type(value) is list:
        return {'array': [_shape(v, pointer+'/'+str(i)) for i,v in enumerate(value)]}
    return {'slot': pointer}


def _restore(shape, slots, used):
    if 'object' in shape:
        return {k: _restore(v,slots,used) for k,v in shape['object']}
    if 'array' in shape:
        return [_restore(v,slots,used) for v in shape['array']]
    path=shape['slot']
    if path not in slots:
        raise ValueError('PROJECTION_MISSING_SLOT: '+path)
    used.add(path)
    value=slots[path].value
    if 'empty' in shape and (type(value) is not (dict if shape['empty']=='object' else list) or value):
        raise ValueError('PROJECTION_CONTAINER_CHANGED: '+path)
    return value


def _diff(a,b,path=''):
    if type(a) is not type(b):
        return [path]
    if type(a) is dict:
        paths=[path+'/'+_escape(k) for k in a.keys() ^ b.keys()]
        return paths+[p for k in a.keys() & b.keys() for p in _diff(a[k],b[k],path+'/'+_escape(k))]
    if type(a) is list:
        if len(a)!=len(b): return [path]
        return [p for i,(x,y) in enumerate(zip(a,b)) for p in _diff(x,y,path+'/'+str(i))]
    return [] if _dump(a)==_dump(b) else [path]


@dataclass(frozen=True)
class Projection:
    contract: str
    shape_json: str
    entries: tuple[Entry, ...]
    attributes_json: str
    issues_json: str
    source_digest: str

    @property
    def attributes(self): return _load(self.attributes_json)

    @property
    def issues(self): return _load(self.issues_json)

    def restore_legacy(self):
        slots={e.pointer:e for e in self.entries}
        if len(slots)!=len(self.entries):
            raise ValueError('PROJECTION_DUPLICATE_SLOT')
        used=set()
        value=_restore(_load(self.shape_json),slots,used)
        if slots.keys()-used:
            raise ValueError('PROJECTION_EXTRA_SLOT: '+sorted(slots.keys()-used)[0])
        return value

    def compare(self, original):
        _dump(original)
        restored=self.restore_legacy()
        differences=sorted(_diff(original,restored))
        return {'equivalent':not differences,'changed_paths':differences,
                'scientific_approval':False,'executable':False}

    def as_dict(self):
        return {'version':'research-spec-projection-1','contract':self.contract,
                'executable':False,'scientific_approval':False,'source_digest':self.source_digest,
                'container_shape':_load(self.shape_json),
                'slots':[{'facet':e.facet,'role':e.role,'pointer':e.pointer,'value':e.value} for e in self.entries],
                'attributes':self.attributes,'issues':self.issues}


def expand(view):
    """Attribute meanings and references only; never infer missing scientific values."""
    record=view.original_record()
    attrs=[]; issues=[]
    def issue(code,path,detail):
        issues.append({'code':code,'pointer':path,'detail':detail})
    def attribute(facet,path,value,definition,meaning):
        attrs.append({'facet':facet,'source_pointer':path,'original_value':value,
                      'definition':definition,'attributes':meaning,'is_approval':False})
    def lookup(path):
        node=record
        for part in path.split('/')[1:]:
            key=part.replace('~1','/').replace('~0','~')
            node=node[int(key)] if type(node) is list else node[key]
        return node
    for entry in view.entries:
        p,v=entry.pointer,entry.value
        if entry.facet=='assignment' and type(v) is str and p.rsplit('/',1)[-1] in ('kind','design'):
            design=DESIGN_ALIASES.get(v)
            if design:
                unit,law,stages,accept=DESIGNS[design]
                if v == 'iid_bernoulli_binary_v1':
                    law = '独立同概率 Bernoulli；所有单位采用原标量 p'
                attribute('assignment',p,v,'existing-design-template/'+design,
                          {'template_id':design,'randomization_unit':unit,'joint_law':law,'stages':stages,'acceptance':accept,
                           'parameters':'保留同一分配记录的原参数；模板展开不表示参数完整或设计已批准'})
                parent=p.rsplit('/',1)[0]
                obj=lookup(parent) if parent else record
                groups={
                    'D1':(('probabilities','propensities','p'),),
                    'D2':(('fixed_count','m','quota'),),
                    'D3':(('groups',),('treated_quotas',)), 'D5':(('groups',),('treated_quotas',)),
                    'D4':(('clusters',),('cluster_probabilities',)),
                    'D6':(('groups',),('quota_profiles',),('profile_probabilities',)),
                    'D7':(('fixed_count','m'),('unit_weights','treated_sets')),
                    'D8':(('base_design','fixed_count'),('balance_rule','balance_covariates'),),
                }[design]
                missing=[list(g) for g in groups if not any(k in obj and obj[k] is not None for k in g)]
                if missing:
                    issue('TEMPLATE_PARAMETERS_INCOMPLETE',parent,'模板已知但参数未完整记录：'+json.dumps(missing,ensure_ascii=False))
            else:
                issue('DESIGN_NOT_EXPANDED',p,'未登记的精确模板，保留原值；不从设计简述推断完整联合律')
        if entry.facet=='exposure' and type(v) is str and p.rsplit('/',1)[-1] in ('kind','grouping','exposure'):
            code=EXPOSURE_ALIASES.get(v)
            if code:
                ref,stat,labels,boundary=EXPOSURES[code]
                attribute('exposure',p,v,'existing-exposure-template/'+code,
                          {'template_id':code,'reference_set':ref,'statistic':stat,'labels':labels,'boundary':boundary,
                           'mean_sufficiency':'未推定；仍须原假设及范围'})
            elif v in ('WEIGHTED_EXPOSURE','GROUPED_EXPOSURE'):
                parent=p.rsplit('/',1)[0]
                obj=lookup(parent) if parent else record
                keys=('weights','mode') if v=='WEIGHTED_EXPOSURE' else ('groups',)
                attribute('exposure',p,v,'existing-exposure-template/'+v,
                          {'reference_and_statistic_parameters':{k:parent+'/'+k for k in keys if k in obj},
                           'labels':'保留原统计量或原向量；没有额外分档',
                           'boundary':'按原合同检查分母、权重或组定义；视图不提供默认值',
                           'mean_sufficiency':'未推定；仍须原假设及范围'})
                if any(obj.get(k) is None for k in keys):
                    issue('TEMPLATE_PARAMETERS_INCOMPLETE',parent,'映射参数尚未完整记录：'+','.join(keys))
            else:
                issue('EXPOSURE_NOT_EXPANDED',p,'保留原映射和参数；不从简写推断阈值、参考对象或充分性')
        if entry.facet in ('target','definitions') and type(v) is str and p.rsplit('/',1)[-1] in (
                'context','context_reference','shared_outcome_and_context') and v.strip():
            issue('TEXT_SCOPE_UNSPLIT',p,'时期、叙述背景与固定条件保持原文；需语义核对才能拆分')
        if entry.facet=='unmapped':
            issue('UNMAPPED_FIELD',p,'视图没有登记此字段的职责；保留原值，不等于资料缺失')
        if entry.facet in ('target','assignment','exposure','information','assumptions') and (
                v is None or type(v) is str and v in ('UNKNOWN','UNDECIDED','NOT_STATED','CONFLICTING')):
            issue('ORIGINAL_UNRESOLVED_VALUE',p,'保留原未知、待定或冲突值；是否必填仍由原合同决定')
        if entry.facet=='assumptions' and p.endswith('/value') and type(v) is bool:
            issue('LEGACY_BOOLEAN_STANCE',p,'旧布尔声明未分别编码命题极性与采用态度；不能自动补出两者')
        if entry.facet=='target' and type(v) is str and p.endswith('/kind'):
            if v in ('FIXED_POLICY_MEAN','policy_mean'):
                attribute('target',p,v,'existing-target-kind',{'endpoint_function':'MEAN','operation':'IDENTITY'})
            elif v=='FIXED_POLICY_CONTRAST':
                attribute('target',p,v,'existing-target-kind',{'endpoint_function':'MEAN','operation':'见原 operation 字段；不从名称补方向'})
            elif v in ('late','ate','LATE','ATE','local_difference'):
                issue('TARGET_NAME_NOT_FULL_DEFINITION',p,'名称不能替代人群、两端方向、其余安排及背景的原记录')
        if entry.facet=='assignment' and p.endswith('/assignment_design_json') and type(v) is str:
            try:
                decoded=_load(v)
            except ValueError:
                issue('SERIALIZED_DESIGN_NOT_EXPANDED',p,'原字符串不是严格 JSON；不修补内容')
            else:
                if type(decoded) is dict:
                    attribute('assignment',p,v,'existing-json-design-serialization',
                              {'decoded_original_parameters':decoded,'note':'仅查看原 JSON 参数，原字符串及其摘要不变'})
                else:
                    issue('SERIALIZED_DESIGN_NOT_EXPANDED',p,'原字符串未表达分配对象；不补成新设计')
    if view.contract=='policy-materials':
        # These attributes come from the intermediate material contract, not its prose.
        if record.get('operator') in ('FINITE_MEAN_BOX','MEAN_ORDER') and all(k in record for k in ('first','second','weights')):
            attribute('target','/first',record['first'],'source-policy-materials/1',
                      {'endpoint_function':'MEAN','operation':'IDENTITY' if record['second'] is None else 'FIRST_MINUS_SECOND',
                       'second_ref':'/second','weights_ref':'/weights','roster_ref':'/nodes',
                       'zero_weights':'保留零权重及完整名单；不删除节点'})
        if 'conditions' in record:
            issue('OUTER_REVIEW_REQUIRED','/conditions','材料内条件仅用于描述条件性计算；本对象不包含独立审核结论')
    if view.contract=='math-request':
        if record.get('format')!='causal-id.math-request/1':
            issue('UNSUPPORTED_ENVELOPE','/format','未知上传版本；原问题保持未展开')
        issue('QUESTION_EQUIVALENCE_NOT_INFERRED','/question','相同原问绑定不证明上传数学目标忠实于业务意图；沿用原审核')
    shape=_shape(record)
    projection=Projection(view.contract,_dump(shape),view.entries,_dump(attrs),_dump(issues),
                          hashlib.sha256(view.record_json.encode('utf-8')).hexdigest())
    if not projection.compare(record)['equivalent']:
        raise ValueError('INTERNAL_PROJECTION_CHANGED_SOURCE')
    return projection
