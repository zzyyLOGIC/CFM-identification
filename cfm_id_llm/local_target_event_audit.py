"""Per-question source grounding of local arms, inside the existing audit.

Separate own treatment from peer state. A definition of a peer-state code does
not declare which state a particular question compares. This decomposition is
checked for contradictions, not treated as scientific approval or source truth.
"""
from copy import deepcopy
import json
from typing import Literal
from pydantic import Field, StrictInt
from . import joint_reading as shared

VERSION = 'local-target-event-audit/1'


class Scope(shared.Strict):
    field: str
    first_own: StrictInt | None
    first_exposure: StrictInt | None
    second_own: StrictInt | None
    second_exposure: StrictInt | None
    peer_basis: Literal['THIS_QUESTION', 'EXPLICIT_SHARED', 'NOT_STATED', 'NOT_APPLICABLE', 'CONFLICTING']
    evidence: list[shared.Citation] = Field(min_length=1)


def augment(request, reading):
    request=deepcopy(request);body=json.loads(request['user_prompt']);schema=body['output_schema']
    item=Scope.model_json_schema();item.pop('$defs',None)
    item['properties']['field']['enum']=[f'targets.{i}' for i in range(len(reading['targets']))]
    schema['properties'].update(local_target_event_version=dict(type='string',const=VERSION),
        local_target_events=dict(type='array',items=item,minItems=len(reading['targets']),maxItems=len(reading['targets'])))
    schema['required']+=['local_target_event_version','local_target_events']
    request['system_prompt']+='''
另按schema输出local_target_event_version、local_target_events，每问恰好一条。先独立读该问的原句及明确适用的共同说明，再核对候选两端；不可按候选或另一问倒填。
first_own/second_own是本人的两种处理状态；first_exposure/second_exposure是该问实际指定的同伴状态。自己开与不开只确定own，不决定exposure。说明“有邻居开记1”只是编码定义，不能推出每问都限定邻居状态为1；第一问的限定也不自动适用于第二问。
peer_basis：本问明确指定用THIS_QUESTION；原文明确共同适用或明确反向比较同一对情形用EXPLICIT_SHARED；没说用NOT_STATED，非局部状态目标用NOT_APPLICABLE，相互矛盾用CONFLICTING。后面三种的exposure字段均留null。引用本问及适用范围的原句，不引用别问作为本问依据。
已知own但同伴状态未知时，源分解可保留own，候选first/second可留null（当前Arm合同不能填半个事件），原问必须保留。候选填写任何没有原文支持的状态，判READING_ERROR并重读，不默认批准，也不要求用户认可模型猜测。已明确超出入口范围的目标也不能编造两端或删去原问；由规划器解释已知边界，不为用不到的字段追问。
'''
    request['user_prompt']=json.dumps(body,ensure_ascii=False)
    return request


def check(case, reading, audit, version, raw, *, current=False):
    if version is None and raw is None and not current:
        return audit
    if version!=VERSION or not isinstance(raw,list):
        raise ValueError('LOCAL_TARGET_EVENT_AUDIT_REQUIRED')
    expected={f'targets.{i}':x['value'] for i,x in enumerate(reading['targets'])}
    if sorted(x.get('field','') for x in raw)!=sorted(expected):
        raise ValueError('LOCAL_TARGET_EVENT_AUDIT_COVERAGE')
    checked=[]
    for item in raw:
        scope=Scope.model_validate(item).model_dump(mode='json')
        scope['evidence']=shared.resolve_evidence(case,scope['evidence'])
        shared.check_citations(scope['evidence'],shared.sources(case))
        unknown=scope['peer_basis'] in ('NOT_STATED','NOT_APPLICABLE','CONFLICTING')
        if unknown and any(scope[k] is not None for k in ('first_exposure','second_exposure')):
            raise ValueError('LOCAL_TARGET_EVENT_UNKNOWN_PEER_HAS_VALUE')
        t=expected[scope['field']];errors=[]
        for arm in ('first','second'):
            wanted={k:scope[arm+'_'+k] for k in ('own','exposure')};got=t[arm]
            if got is not None and any(got[k]!=wanted[k] for k in wanted):errors.append(arm)
            elif got is None and all(v is not None for v in wanted.values()):errors.append(arm)
        finding=next(f for f in audit['findings'] if f['field']==scope['field'])
        if errors and finding['verdict']=='MATCH':
            finding.update(verdict='READING_ERROR',question=None,evidence=scope['evidence'],
                reason='本问原文的本人/同伴状态与候选两端不一致（'+','.join(errors)+'）；不得借用另一问的同伴条件或把编码定义当作本问限定。按原文重读，未知保留空值，不补条件。')
        checked.append(scope)
    audit.update(local_target_event_version=VERSION,local_target_events=checked)
    return audit
