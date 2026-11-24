"""Read-only, source-addressed views of existing records. No scientific authority.

This module does not validate a causal contract, select a method, infer a missing
field, or feed a new representation into a solver. All execution stays on the
unchanged original record. A view digest is NOT a scientific/review digest.
"""
from dataclasses import dataclass
import hashlib
import html
import json
import math


FACETS = (
    ('target', '目标'), ('assignment', '分配机制'), ('exposure', '暴露映射'),
    ('structure', '结构与模型'), ('information', '已有信息'), ('assumptions', '科学假设'),
)
EXTRA_SECTIONS = (('definitions', '共同定义与原始背景'), ('evidence', '来源与版本'),
                  ('unresolved', '原记录中的未知或缺项'), ('unmapped', '视图尚未归类的原字段'),
                  ('review', '原审核记录与权限'), ('result', '原计算结果与证书'),
                  ('handoff', '原交接内容与收件权限'), ('method', '方法、版本与流程记录'))
CONTRACTS = ('direct', 'compact', 'network-facts', 'dag-facts', 'mean-order',
             'native-study', 'native-target', 'dag-problem', 'iv-problem', 'bounded-information',
             'policy-materials', 'direct-report', 'policy-packet', 'math-request')


@dataclass(frozen=True)
class Rule:
    path: str
    facet: str
    role: str


def _rules(facet, role, *paths):
    return tuple(Rule(path, facet, role) for path in paths)


COMMON = (
    *_rules('target', '目标原记录', '/target'),
    *_rules('target', '单端函数或旧目标类型（不强制拆分）', '/target/kind', '/target/quantity'),
    *_rules('target', '评价人群', '/target/population', '/target/scope'),
    *_rules('target', '汇总权重', '/target/aggregation', '/target/unit_weights', '/target/weights'),
    *_rules('target', '有序比较与端点', '/target/operation', '/target/first', '/target/second',
            '/target/intervention', '/target/reference', '/target/comparison', '/target/assignment'),
    *_rules('target', '其余安排与平均方式', '/target/remaining_assignment', '/target/averaging'),
    *_rules('target', '时期及条件原文（不自动拆分）', '/target/context', '/target/time',
            '/target/shared_outcome_and_context', '/conditioning'),
    *_rules('definitions', '变量及其编码', '/study/treatment', '/study/outcome', '/study/outcome_kind'),
    *_rules('definitions', '完整名单及原顺序', '/study/nodes'),
    *_rules('definitions', '背景原记录（未自动成为目标条件）', '/study/context'),
    *_rules('structure', '对象关系及结构声明', '/study'),
    *_rules('assignment', '完整分配律及原参数', '/assignment', '/regime', '/design_facts'),
    *_rules('assignment', '现有设计模板', '/assignment/kind'),
    *_rules('assignment', '分层或整簇的名单', '/assignment/groups', '/assignment/clusters'),
    *_rules('assignment', '固定名额', '/assignment/fixed_count', '/assignment/treated_quotas'),
    *_rules('assignment', '概率律或权重原参数', '/assignment/probabilities', '/assignment/cluster_probabilities',
            '/assignment/treated_sets', '/assignment/set_probabilities', '/assignment/unit_weights'),
    *_rules('assignment', '第一阶段名额方案与概率', '/assignment/quota_profiles', '/assignment/profile_probabilities'),
    *_rules('assignment', '接受筛选规则', '/assignment/balance_covariates', '/assignment/balance_tolerance'),
    *_rules('exposure', '映射及原参数', '/exposure'),
    *_rules('exposure', '现有暴露模板及边界规则', '/exposure/kind'),
    *_rules('exposure', '参考对象', '/exposure/core_collaborators', '/exposure/groups'),
    *_rules('exposure', '加权统计量与计算方式', '/exposure/weights', '/exposure/mode'),
    *_rules('information', '总体信息及覆盖', '/information'),
    *_rules('information', '抽样、缺失及测量说明（原文）', '/information/data_description', '/information/*/data_description'),
    *_rules('assumptions', '命题原记录；采用与批准不互相代替', '/assumptions',
            '/scientific_statements', '/mean_sufficiency', '/first_stage_exclusion'),
    *_rules('assumptions', '采用态度的原记录（不是批准）', '/assumption_choices', '/first_stage_exclusion/status'),
    *_rules('assumptions', '额外限制原文（不删除、不自动采纳）', '/additional_restrictions', '/restrictions'),
    *_rules('assumptions', '有界模型及其范围', '/bounded_model'),
    *_rules('information', '已列信息的完整性声明', '/bounded_model/listed_means_are_complete_information'),
    *_rules('unresolved', '原记录的未知或缺项', '/unresolved', '/gaps'),
    *_rules('evidence', '原版本及引用上下文', '/version', '/reference_context'),
)

COMPACT = (
    *_rules('structure', '对象关系原记录', '/network'),
    *_rules('definitions', '完整名单及原顺序', '/network/nodes'),
    *_rules('definitions', '结果取值域', '/network/outcome_kind'),
    *_rules('assignment', '分配律及名额', '/network/design', '/network/quota', '/network/probabilities'),
    *_rules('exposure', '暴露类型原值', '/network/exposure'),
    *_rules('target', '完整政策、局部两端及权重', '/network/policy', '/network/arms', '/network/weights'),
    *_rules('information', '完整名单/局部状态的总体均值', '/network/full', '/network/local'),
    *_rules('structure', '变量因果图', '/graph'),
    *_rules('target', '干预及事件坐标', '/graph/x', '/graph/y', '/graph/x_value', '/graph/y_value'),
    *_rules('information', '总体律或样本的原声明', '/graph/info'),
    *_rules('structure', '工具与实际处理、结果的角色', '/iv'),
    *_rules('information', '二元 IV 总体条件表（原格序）', '/iv/cells'),
)

DIRECT = (
    *_rules('structure', '有证据的网络摘录', '/network_facts/network'),
    *_rules('assignment', '有证据的分配摘录', '/network_facts/assignment'),
    *_rules('exposure', '有证据的暴露摘录', '/network_facts/exposure'),
    *_rules('target', '有证据的比较摘录', '/network_facts/contrast'),
    *_rules('definitions', '完整名单及原顺序', '/network_facts/network/value/nodes'),
    *_rules('target', '逐问目标原记录', '/answers/*/target'),
    *_rules('assumptions', '逐问假设原记录；不是批准', '/answers/*/assumptions'),
)

DAG = (
    *_rules('definitions', '变量及取值域', '/variables', '/nodes', '/variable_domain', '/observed', '/latent'),
    *_rules('structure', '变量因果关系', '/relations', '/common_causes', '/directed', '/bidirected',
            '/edges', '/model', '/graph_status'),
    *_rules('assumptions', '结构声明及适用范围（不是自动批准）', '/scope'),
    *_rules('target', '干预、结果与背景', '/treatment', '/outcome', '/context'),
    *_rules('evidence', '原调整记录；非重新选择的方法', '/adjustment', '/adjustment_source_ids'),
)

NATIVE = (
    *_rules('definitions', '完整名单及原顺序', '/node_order'),
    *_rules('definitions', '变量定义及原始背景', '/treatment_variable', '/outcome_variable',
            '/outcome_kind', '/context_reference'),
    *_rules('structure', '对象网与模型范围', '/undirected_edges', '/network_id', '/graph_timing_claim'),
    *_rules('assignment', '分配律原序列化内容（不猜写）', '/assignment_design_json', '/observation_regime'),
    *_rules('evidence', '原来源及绑定', '/network_provenance', '/protocol_provenance',
            '/network_fingerprint', '/assignment_law_fingerprint', '/exposure_fingerprint', '/target_digest'),
)

MEAN_ORDER = (
    *_rules('definitions', '名单、变量与时期定义', '/node_order', '/treatment_definition',
            '/outcome_definition', '/outcome_kind', '/outcome_unit', '/outcome_period'),
    *_rules('target', '有序两政策、权重及背景', '/first', '/second', '/weights', '/operation', '/context'),
    *_rules('structure', '对象网及数学适用域', '/undirected_edges', '/graph_scope', '/model_scope'),
    *_rules('assignment', '设计模板与名额', '/design', '/quota'),
    *_rules('information', '精确或符号信息及其完整性', '/values', '/information_scope', '/availability'),
    *_rules('assumptions', '有范围的结果界', '/bounds', '/bounds_kind', '/bounds_scope'),
    *_rules('assumptions', '均值顺序及方向', '/node_orders', '/order_scope', '/order_direction'),
    *_rules('assumptions', '基础命题与充分性范围', '/randomization_claim', '/consistency_claim',
            '/moments_claim', '/mean_sufficiency_claim', '/mean_sufficiency_scope'),
    *_rules('evidence', '原来源', '/a4_source', '/a4_provenance', '/bounds_provenance', '/scientific_provenance'),
)

IV = (
    *_rules('definitions', '工具、处理和结果的变量定义', '/instrument', '/treatment', '/outcome'),
    *_rules('target', '评价人群及背景', '/population', '/context'),
    *_rules('information', '总体条件格表（原坐标）', '/cells'),
    *_rules('assumptions', '原单调性开关（不推出相反命题）', '/monotonicity'),
)

_ADDITIONAL = {
    'direct': DIRECT, 'compact': COMPACT, 'network-facts': (), 'dag-facts': DAG,
    'mean-order': MEAN_ORDER, 'native-study': NATIVE,
    'native-target': (*NATIVE, *_rules('target', '原生目标及平均方式', '/kind', '/outcome',
        '/context', '/averaging_scope', '/node_id', '/arm', '/policy_assignment', '/unit_weights'),
        *_rules('evidence', '原权限与解析记录（不授予新权限）', '/authority', '/query_resolution')),
    'dag-problem': DAG, 'iv-problem': IV,
    'bounded-information': (*MEAN_ORDER, *_rules('evidence', '原信息与研究绑定', '/inquiry_sha256',
        '/source_id', '/source_sha256')),
}


def _strict(value):
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for x in value:
            _strict(x)
        return
    if type(value) is dict and all(type(k) is str for k in value):
        for x in value.values():
            _strict(x)
        return
    raise ValueError('Only strict JSON values are accepted; serialize typed records explicitly')


def _dump(value):
    _strict(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('Duplicate JSON key: '+key)
        out[key] = value
    return out


def _load(text):
    obj = json.loads(text, object_pairs_hook=_pairs)
    _strict(obj)
    return obj


def _escape(token):
    return str(token).replace('~', '~0').replace('/', '~1')


def _leaves(value, tokens=()):
    if isinstance(value, dict) and value:
        for key, child in value.items():
            yield from _leaves(child, (*tokens, _escape(key)))
    elif isinstance(value, list) and value:
        for index, child in enumerate(value):
            yield from _leaves(child, (*tokens, str(index)))
    else:
        yield tokens, value


def _matches(rule, tokens):
    parts = tuple(rule.path.split('/')[1:])
    return len(parts) <= len(tokens) and all(a == b or (a == '*' and b.isdecimal())
                                            for a, b in zip(parts, tokens))


@dataclass(frozen=True)
class Entry:
    facet: str
    role: str
    pointer: str
    value_json: str

    @property
    def value(self):
        return _load(self.value_json)


@dataclass(frozen=True)
class ResearchSpecView:
    contract: str
    record_json: str
    review_json: str | None
    result_json: str | None
    entries: tuple[Entry, ...]

    @property
    def snapshot_sha256(self):
        """Display snapshot only; NEVER a substitute for an existing review hash."""
        return hashlib.sha256(self.record_json.encode('utf-8')).hexdigest()

    def original_record(self):
        return _load(self.record_json)

    def original_review(self):
        return None if self.review_json is None else _load(self.review_json)

    def original_result(self):
        return None if self.result_json is None else _load(self.result_json)

    def assert_current(self, record):
        # Compare typed JSON values, including bool vs int and absent vs null.
        _strict(record)
        opts = dict(ensure_ascii=False, sort_keys=True, allow_nan=False)
        if json.dumps(record, **opts) != json.dumps(self.original_record(), **opts):
            raise ValueError('VIEW_SOURCE_CHANGED: rebuild the view; never reuse it as approval')

    def as_dict(self):
        return dict(version='research-spec-view-1', contract=self.contract,
                    is_approval=False, executable=False, snapshot_sha256=self.snapshot_sha256,
                    sections={key: [dict(role=e.role, pointer=e.pointer, value=e.value)
                                    for e in self.entries if e.facet == key]
                              for key, _ in (*FACETS, *EXTRA_SECTIONS)},
                    proposed_answers=[dict(role=e.role, pointer=e.pointer, value=e.value)
                                      for e in self.entries if e.facet == 'model_answer'],
                    review=self.original_review(), result=self.original_result())


def from_json(text, *, contract, review=None, result=None):
    """Preserve original JSON text; do not run parsers that insert defaults."""
    if type(text) is not str:
        raise ValueError('JSON text must be decoded explicitly before viewing')
    if contract not in CONTRACTS:
        raise ValueError('Unknown view contract; choose an explicitly supported format')
    record = _load(text)
    if type(record) is not dict:
        raise ValueError('The source record must be a JSON object')
    from .research_spec_adapters import record_rules
    rules = record_rules(record, contract)
    entries = []
    for tokens, value in _leaves(record):
        candidates = [r for r in rules if _matches(r, tokens)]
        best = max(reversed(candidates), key=lambda r: len(r.path.split('/')), default=None)
        facet, role = (best.facet, best.role) if best else ('unmapped', '未归类原字段；不等于研究资料有缺失')
        source_tokens = tokens
        if contract == 'direct-report' and tokens[:2] == ('proof', 'evidence'):
            source_tokens = tokens[2:]
        elif contract == 'policy-packet' and tokens[:1] == ('evidence',):
            source_tokens = tokens[1:]
        if (facet not in ('review', 'result', 'handoff', 'method', 'model_answer') and
                any(t in ('source_ids', 'source_id', 'quote', 'evidence') for t in source_tokens)):
            facet, role = 'evidence', '原文依据（定位存在不表示语义已通过）'
        # Direct model answers must never appear as approved scientific inputs.
        direct_answer_field = (tokens[:1] in [(x,) for x in ('status','functional','value','reason','estimate_handoff')]
                               or (len(tokens) >= 3 and tokens[0] == 'answers' and tokens[1].isdecimal()
                                   and tokens[2] not in ('target','assumptions')))
        if contract == 'direct' and direct_answer_field:
            facet, role = 'model_answer', '模型原答（视图没有验证或批准）'
        entries.append(Entry(facet, role, '/'+ '/'.join(tokens) if tokens else '', _dump(value)))
    return ResearchSpecView(contract, text, None if review is None else _dump(review),
                            None if result is None else _dump(result), tuple(entries))


def build_view(record, *, contract, review=None, result=None):
    return from_json(_dump(record), contract=contract, review=review, result=result)


def to_html(view, *, title='研究规格：六项只读视图'):
    """Standalone escaped HTML. No scripts, remote assets, or approve/run controls."""
    def block(label, value):
        return '<details><summary>'+html.escape(label)+'</summary><pre>'+html.escape(
            json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))+'</pre></details>'
    parts = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width">',
        '<title>'+html.escape(title)+'</title><style>body{font:16px/1.65 system-ui;margin:32px auto;padding:0 20px;max-width:1120px;color:#183747;background:#f4f7f8}h1{font-size:27px}h2{font-size:21px}section{padding:20px;background:white;border:1px solid #d8e3e7;border-radius:12px;margin:16px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;max-height:420px;overflow:auto}summary{cursor:pointer;color:#126d61}small{color:#546a75}</style>',
        '<style>.component + .component{border-top:1px solid #d8e3e7;margin-top:18px;padding-top:18px}.component>small{display:block;margin:8px 0}</style>',
        '<h1>'+html.escape(title)+'</h1><p>这是已有记录的分类视图。没有重新读题、补值或批准假设；计算继续使用原记录。</p>',
        '<p>未记录、null、空列表分别保留。没有出现在某一栏，不表示该条件不适用或已满足。</p>']
    from .research_spec_model import build_internal_study
    model = build_internal_study(view)
    state_labels = {'DEFINED_BY_ORIGINAL_TEMPLATE':'来自已登记模板',
                    'RECORDED_EXPRESSION':'保留原字段表达',
                    'UNRESOLVED_OR_PARTLY_UNRESOLVED':'含未知或待定内容',
                    'CONFLICTING_DEFINITIONS':'定义存在分歧'}
    for facet, label in FACETS:
        parts.append('<section><h2>'+html.escape(label)+'</h2>')
        components = model.for_facet(facet)
        if not components:
            parts.append('<p>本记录未单独提供这一项；未作补全或适用性判断。</p>')
        for component in components:
            parts.append('<div class="component">')
            parts.append('<small>原对象：'+html.escape(component.source_root or '根记录')+'</small>')
            unrecorded=[]
            for prop in component.properties:
                if prop.state=='NOT_SEPARATELY_RECORDED':
                    unrecorded.append(prop.label)
                    continue
                details={}
                if prop.definitions:
                    details['内部属性']=[{'含义':d.label,'属性值':d.value,'定义':d.rule,'依据字段':d.source_ref}
                                         for d in prop.definitions]
                if prop.source_refs:
                    details['原参数']={ref:model.resolve(ref) for ref in prop.source_refs}
                parts.append(block(prop.label+' · '+state_labels[prop.state],details))
            if component.unsplit_refs:
                parts.append(block('保留而未拆分的字段',{ref:model.resolve(ref) for ref in component.unsplit_refs}))
            if unrecorded:
                parts.append('<small>未单独记录（不等于不适用）：'+html.escape('；'.join(unrecorded))+'</small>')
            parts.append('</div>')
        parts.append('</section>')
    for facet, label in (*EXTRA_SECTIONS, ('model_answer','模型原答，与库的结果分开')):
        grouped = {}
        for e in view.entries:
            if e.facet == facet:
                grouped.setdefault(e.role, {})[e.pointer] = e.value
        parts.append('<section><h2>'+html.escape(label)+'</h2>')
        parts.extend(block(role, values) for role, values in grouped.items())
        if not grouped:
            parts.append('<p>本记录未单独提供这一项；未作补全或适用性判断。</p>')
        parts.append('</section>')
    from .research_spec_projection import expand
    projection = expand(view)
    parts += ['<section><h2>确定性属性展开与待核对项</h2><p>以下属性仅来自明确的旧模板；不增加假设，不作为新的执行输入。</p>',
              block('展开属性（含原字段和定义依据）', projection.attributes),
              block('未展开或需原文核对', projection.issues), '</section>']
    parts += ['<section><h2>原审核与原结果</h2><p>原样附列，不新增权限，也不重新认证。</p>',
              block('已有审核记录', view.original_review()), block('已有结果', view.original_result()),
              block('完整原记录', view.original_record()), '</section>',
              '<small>视图格式：'+html.escape(view.contract)+'；快照摘要仅供比对，不是科学审核摘要：'+view.snapshot_sha256+'</small></html>']
    return '\n'.join(parts)


def main():
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description='Export an existing JSON record as a read-only six-facet view; no LLM or solver calls.')
    parser.add_argument('record', type=Path)
    parser.add_argument('--contract', required=True, choices=CONTRACTS)
    parser.add_argument('--html', type=Path)
    args = parser.parse_args()
    if args.html and args.html.resolve() == args.record.resolve():
        parser.error('Output must not overwrite the input record')
    view = from_json(args.record.read_text(encoding='utf-8'), contract=args.contract)
    if args.html:
        args.html.write_text(to_html(view), encoding='utf-8')
    else:
        print(json.dumps(view.as_dict(), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
