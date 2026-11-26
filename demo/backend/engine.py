"""Stateful browser adapter. A browser supplies reviews, never proofs or approvals by default."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4
import base64
import json
import threading
import time

from .runtime import PROJECT_ROOT, identification_modules
from .provider import PROVIDERS, make_provider, generate, provider_catalog, connection_options, public_connection

project, intake, dispatch = identification_modules()
from cfm_id import business_field_review
from cfm_id_llm.document_intake import create_intake, AttachmentRequestV07, MAX_ATTACHMENTS
from .review_summary import summarize
from . import capabilities

PUBLIC = PROJECT_ROOT / 'demo'
MAX_UPLOAD = 20 * 1024 * 1024
DEFAULT_OUTPUT_TOKENS = 16384
DEFAULT_LONGCAT_FACT_MAX_TOKENS = 32768
DEFAULT_MAX_API_CALLS = 1000


def plain(value):
    return value.model_dump(mode='json') if hasattr(value, 'model_dump') else value


def local_target_conflict(entry, candidate):
    """Report a disagreement for rereading; neither model output is evidence of intent."""
    if entry.get('reader_id') != 'NETWORK_RANDOMIZED_EFFECT_FACTS':
        return None
    target = candidate.get('target', {})
    ends = [target.get(side, {}) for side in ('first', 'second')]
    if any(not end.get('source_ids') or any(type(end.get(k)) is not int for k in ('own','exposure')) for end in ends):
        return None
    own_changes = ends[0]['own'] != ends[1]['own']
    peers_change = ends[0]['exposure'] != ends[1]['exposure']
    kinds = {(True,False):'DIRECT_EFFECT', (False,True):'SPILLOVER_EFFECT', (True,True):'LOCAL_TOTAL_EFFECT'}
    implied = kinds.get((own_changes, peers_change))
    a0 = entry['selected_query']['target']['kind']
    if implied is None or a0 not in kinds.values() or target.get('kind') not in kinds.values() or implied == a0:
        return None
    return dict(query_id=entry['query_id'], initial_kind=a0, fact_kind=target['kind'], endpoint_kind=implied,
                endpoints=[[end['own'],end['exposure']] for end in ends])


def pending(sheet, authority):
    value = {**capabilities.identity(sheet), **{k: deepcopy(sheet[k]) for k in ('decisions', 'material_decisions') if k in sheet}}
    value.update(authority=authority, reviewer='', evidence='')
    if sheet['version'].startswith(('network-information-evidence', 'network-contrast-information-evidence')):
        value.update(disposition='PENDING', table_source_ids=[], supporting_source_ids=[])
    return value


@dataclass
class Run:
    owner: str
    id: str = field(default_factory=lambda: uuid4().hex)
    created: float = field(default_factory=time.time)
    stage: str = 'PREPARING'
    busy: bool = False
    error: dict | None = None
    case: dict | None = None
    intake: object = None
    query_id: str | None = None
    query_review: dict | None = None
    entry: dict | None = None
    submission: dict | None = None
    plan: dict | None = None
    reviews: dict = field(default_factory=dict)
    dag_fact_audit: dict | None = None
    review_kind: str | None = None
    review_sheets: dict = field(default_factory=dict)
    review_templates: dict = field(default_factory=dict)
    result: dict | None = None
    estimate: dict | None = None
    queries: list = field(default_factory=list)
    events: list = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)
    attachment_report: dict | None = None
    data: object = None
    network: object = None
    synthetic: bool = False
    provider: str = 'longcat'
    model_settings: dict = field(default_factory=dict)
    pending_fact_recheck: dict | None = None
    automatic_fact_transport_retries: int = 0
    automatic_review: bool = False
    reading_mode: str = 'classic'
    automatic_rechecks: int = 0
    automatic_audit_repairs: int = 0
    automatic_a0_format_repairs: int = 0
    automatic_fact_format_repairs: int = 0
    automatic_focused_stages: set = field(default_factory=set)
    automatic_audit_length_retries: set = field(default_factory=set)
    automatic_direct_length_retries: set = field(default_factory=set)
    automatic_direct_transport_retries: int = 0
    user_question: dict | None = None
    clarification_handoff: dict | None = None
    lock: object = field(default_factory=threading.RLock)

    @property
    def authority(self):
        return 'SYNTHETIC_TEST' if self.synthetic else 'EXTERNAL_RESEARCH_REVIEW'


class Engine:
    def __init__(self, storage, *, max_api_calls=DEFAULT_MAX_API_CALLS, provider_factory=make_provider, longcat_fact_max_tokens=DEFAULT_LONGCAT_FACT_MAX_TOKENS, estimate_inbox=None):
        if type(longcat_fact_max_tokens) is not int or not 1<=longcat_fact_max_tokens<=262144:raise ValueError('Invalid output token limit')
        self.longcat_fact_max_tokens=longcat_fact_max_tokens
        self.connection_settings={}
        self.storage = Path(storage).resolve(); self.storage.mkdir(parents=True, exist_ok=True)
        from cfm_id.network_query_exchange import QueryInbox
        self.estimate_inbox=estimate_inbox if estimate_inbox is not None else QueryInbox(self.storage/"estimate_inbox")
        self.runs = {}; self.credentials = {}; self.calls = 0; self.max_api_calls = max_api_calls
        self.provider_factory = provider_factory; self.lock = threading.RLock()
        self.examples = json.loads((PUBLIC/'examples.json').read_text('utf8'))
        self.web_capabilities = capabilities.inventory()

    def credential(self, owner, provider, key, *, settings=None, reuse_key=False):
        if provider not in PROVIDERS: raise ValueError('UNKNOWN_PROVIDER')
        if type(reuse_key) is not bool: raise ValueError('MODEL_SETTINGS_INVALID')
        if not isinstance(key, str) or len(key)>2048 or any(c.isspace() for c in key):
            raise ValueError('INVALID_API_KEY')
        with self.lock:
            if reuse_key:
                current=self.credentials.get(owner)
                if key or current is None or time.time()-current[2]>8*3600:
                    raise ValueError('API_KEY_REQUIRED')
                if current[0]!=provider:raise ValueError('PROVIDER_CREDENTIAL_MISMATCH')
                key=current[1]
            if key:
                if any(r.owner==owner and r.busy for r in self.runs.values()):
                    raise ValueError('RUN_ALREADY_BUSY')
                options=connection_options(provider, settings)
                if reuse_key and options['base_url']!=self.connection_settings.get(owner,PROVIDERS[provider])['base_url']:
                    raise ValueError('PROVIDER_CREDENTIAL_MISMATCH')
                self.credentials[owner] = (provider, key, time.time())
                self.connection_settings[owner] = options
            else:
                self.credentials.pop(owner, None)
                self.connection_settings.pop(owner, None)
        return {'configured': bool(key), 'provider': provider, 'stored': 'PROCESS_MEMORY_ONLY'}

    def health(self, owner):
        from .coverage import summary as coverage_summary
        with self.lock:
            credential=self.credentials.get(owner)
            if credential and time.time()-credential[2]>8*3600:
                self.credentials.pop(owner,None); self.connection_settings.pop(owner,None); credential=None
            return dict(ready=True, configured=credential is not None,
                provider=credential[0] if credential else 'longcat', providers=provider_catalog(),
                model_settings=deepcopy(self.connection_settings.get(owner,{})) if credential else {},
                features=['fact_field_recovery','located_fact_recheck','background_reading_review','typed_assumption_choices','typed_reading_audit',
                          'information_data_descriptions','explicit_audit_findings','network_file_input','local_input_preview'],
                reading_config=capabilities.reading_config().model_dump(mode='json'),
                identification_capabilities=self.web_capabilities,
                coverage_summary=coverage_summary(),
                condition_terms=capabilities.presentation_catalog(),
                model_calls=self.calls, call_limit=self.max_api_calls,
                output_token_limits=dict(default=DEFAULT_OUTPUT_TOKENS,
                                         longcat_facts=self.longcat_fact_max_tokens))

    def get(self, owner, run_id):
        with self.lock:
            run=self.runs.get(run_id)
        if run is None or run.owner!=owner: raise ValueError('RUN_NOT_FOUND')
        return run

    def _clean(self, value, extra_keys=()):
        # Neither raw provider failures nor imported keys enter saved results.
        with self.lock: keys=[*extra_keys,*[c[1] for c in self.credentials.values()]]
        def clean(v):
            if isinstance(v,str):
                for key in keys: v=v.replace(key,'[REDACTED]')
                return v
            if isinstance(v,dict): return {str(k):clean(x) for k,x in v.items()}
            if isinstance(v,list): return [clean(x) for x in v]
            return v
        return clean(value)

    def save(self, run, name, value):
        value=self._clean(plain(value)); run.artifacts[name]=value
        folder=self.storage/run.id; folder.mkdir(exist_ok=True)
        (folder/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf8')

    def event(self, run, stage, message):
        run.stage=stage; run.events.append(dict(stage=stage,message=message,time=time.time()))

    def view(self, owner, run_id):
        run=self.get(owner,run_id)
        with run.lock:
            from . import recovery
            from .study_math import offered
            from cfm_id.entry_diagnostics import summarize as entry_diagnostics
            return deepcopy(dict(id=run.id,stage=run.stage,busy=run.busy,error=run.error,
                created=run.created,events=run.events,queries=run.queries,query_id=run.query_id,
                case=run.case,attachment_report=run.attachment_report,reading_mode=run.reading_mode,
                compact_plan=run.plan if run.reading_mode=='compact' and not run.result else None,
                review_kind=run.review_kind,review_sheets=run.review_sheets,review_templates=run.review_templates,
                plan=run.plan,result=run.result,estimate=run.estimate,
                entry_diagnostics=entry_diagnostics(run.result,plan=run.plan) if run.result else None,
                uploaded_math=offered(run.case),uploaded_math_review=run.artifacts.get('uploaded_math_review'),
                estimate_receipt=run.artifacts.get('estimate_intake_receipt'),
                synthetic=run.synthetic,provider=run.provider,review_summary=summarize(run),
                recheck_preview=recovery.public(recovery.prepare(run)),
                automatic_review=run.automatic_review,user_question=run.user_question,
                automatic_audit_repairs=run.automatic_audit_repairs,
                automatic_a0_format_repairs=run.automatic_a0_format_repairs,
                can_retry_reading=bool(run.automatic_review and run.error and run.review_kind in ('query','source','changes')),
                can_estimate=False,
                downloads=list(run.artifacts)))

    def launch(self, run, function, *args):
        with run.lock:
            if run.busy: raise ValueError('RUN_ALREADY_BUSY')
            run.busy=True; run.error=None
        def work():
            try:
                function(run,*args)
                if run.automatic_review:self._continue_automatically(run)
            except Exception as exc:
                code=getattr(exc,'code',None) or getattr(exc,'reason',None) or type(exc).__name__
                # Provider exceptions have deliberately bounded messages. Do not
                # serialize arbitrary exception text which may include credentials.
                message=str(exc)[:2000] if isinstance(exc,ValueError) else '本阶段未完成，请查看诊断后重试；不要为处理程序或模型接口错误补写研究条件。'
                http_status=getattr(exc,'diagnostics',{}).get('http_status')
                if code=='HTTP_ERROR' and type(http_status) is int:
                    explanation={
                        400:'模型服务不接受本次请求，请检查模型和连接参数',
                        401:'模型服务未接受当前 API 密钥，请核对所选厂商、接口地址和密钥是否对应',
                        403:'当前账户没有本次请求的访问权限，请检查模型及接口权限',
                        404:'模型或接口地址未找到，请检查当前连接配置',
                        429:'模型服务限制了本次请求，可能是请求过密或可用额度不足，请查看账户状态后再试',
                    }.get(http_status,'模型服务暂时未能完成请求，请稍后再试' if 500<=http_status<=599 else None)
                    if explanation:
                        message=explanation+'（HTTP '+str(http_status)+'）。原输入已保留，不需要为此补写研究条件。'
                if code=='TIMEOUT':
                    message='模型服务未在本次等待时限内返回，请稍后重试。已保留原输入；不需要补充研究条件。'
                if code=='INCOMPLETE_COMPLETION' and getattr(exc,'diagnostics',{}).get('finish_reason')=='length':
                    message='模型回复达到长度上限，未形成完整答复，本次没有据此执行识别。已保留输入和诊断；这不是研究条件缺失，不需要补写条件。'
                if isinstance(exc,ValueError) and str(exc) in ('JOINT_REPLAY_REQUIRED','JOINT_RESULT_REPLAY_REQUIRED'):
                    message='原材料、研究目标与核验结果未能对应，旧结果和回执已撤回。原输入与检查记录已保留，不需要为此补写研究条件。'
                run.error=self._clean(dict(code=code,message=message))
                if code=='HTTP_ERROR' and type(http_status) is int and 400<=http_status<=599:
                    run.error['http_status']=http_status
                self.event(run,'STOPPED','本阶段停止，未生成新的识别结论。')
                self.save(run,'error',run.error)
            finally:
                with run.lock:run.busy=False
        threading.Thread(target=work,daemon=True).start()

    def start(self, owner, payload):
        mode=payload.get('reading_mode','direct_verify')
        if mode not in ('direct_verify','network_direct_verify','network_local_review','classic','compact'):raise ValueError('INVALID_READING_MODE')
        if payload.get('use_example_data'):raise ValueError('ESTIMATION_NOT_IN_IDENTIFICATION_DEMO')
        if mode!='network_local_review' and payload.get('allow_send') is not True:raise ValueError('EXTERNAL_DOCUMENT_SHARING_CONSENT_REQUIRED')
        question=payload.get('question','')
        if not isinstance(question,str) or not 3<=len(question.strip())<=25000:raise ValueError('BUSINESS_QUESTION_REQUIRED')
        run=Run(owner=owner,reading_mode=mode,synthetic=payload.get('synthetic') is True,
                automatic_review=payload.get('automatic_review') is True)
        with self.lock:
            if any(other.owner==owner and other.busy for other in self.runs.values()):
                raise ValueError('RUN_ALREADY_BUSY')
            if len(self.runs)>=100:raise ValueError('LOCAL_RUN_LIMIT_RESTART_SERVER')
            credential=self.credentials.get(owner)
            selected=None if mode=='network_local_review' else payload.get('provider')
            if selected is not None:
                if selected not in PROVIDERS:raise ValueError('UNKNOWN_PROVIDER')
                if credential is None or time.time()-credential[2]>8*3600:raise ValueError('API_KEY_REQUIRED')
                if selected!=credential[0]:raise ValueError('PROVIDER_CREDENTIAL_MISMATCH')
            run.provider=selected or (credential[0] if credential else 'longcat')
            run.model_settings=deepcopy(self.connection_settings.get(owner,PROVIDERS[run.provider]))
            self.runs[run.id]=run
            # Reserve busy under the same owner lock before another start can enter.
            self.launch(run,self._start,deepcopy(payload))
        return run.id

    def preview_uploads(self, owner, payload):
        run=Run(owner=owner)
        self._start(run,payload,preview_only=True)
        return dict(receipt=run.attachment_report['receipt'],
            factual_data=run.attachment_report.get('factual_data'),
            table_import=run.artifacts.get('table_import_manifest'),
            network=run.attachment_report.get('network'),
            sources=run.case['sources'])

    def _start(self, run, payload, *, preview_only=False):
        self.event(run,'PREPARING','正在读取问题和附件')
        uploads=payload.get('files',[])
        if not isinstance(uploads,list) or len(uploads)>MAX_ATTACHMENTS:raise ValueError('AT_MOST_TEN_UPLOADS')
        folder=self.storage/run.id/'uploads';folder.mkdir(parents=True,exist_ok=True)
        from cfm_id_llm.shared_materials import DIRECT_MODES, append_sources, document_tables
        from hashlib import sha256
        share_rows = payload.get('share_table_rows', payload.get('reading_mode','direct_verify') in DIRECT_MODES)
        if type(share_rows) is not bool:raise ValueError('INVALID_TABLE_SHARING_SELECTION')
        shared_tables = [] if share_rows else None
        requests=[]; total=0; network_paths={}; table_path=None
        for i,item in enumerate(uploads):
            name=item.get('name','')
            if not isinstance(name,str) or name!=Path(name).name or any(c in name for c in '/\\:'):
                raise ValueError('UPLOAD_NAME_INVALID')
            raw=base64.b64decode(item['content'],validate=True);total+=len(raw)
            if total>MAX_UPLOAD or len(raw)>8*1024*1024:raise ValueError('UPLOAD_SIZE_LIMIT')
            path=folder/(str(i)+'_'+name);path.write_bytes(raw)
            role=item.get('role','document')
            if role in ('network_nodes','network_edges'):
                if role in network_paths:raise ValueError('每类网络表只上传一份；对象表和关系表各一份。')
                network_paths[role]=path
            elif role=='table_data':
                if table_path:raise ValueError('数值表格每次只上传一份。')
                table_path=path
            elif role=='data_dictionary':
                requests.append(AttachmentRequestV07(path=str(path),label=name,purpose='DATA_DICTIONARY',
                    sheet=item.get('sheet'),header_row=item.get('header_row',1)))
            elif role=='document':requests.append(AttachmentRequestV07(path=str(path),label=name))
            else:raise ValueError('IDENTIFICATION_DOCUMENT_UPLOAD_ONLY')
        report=create_intake(case_id=run.id,business_question=payload['question'].strip(),attachments=requests)
        case=report.case.model_dump(mode='json');run.attachment_report=report.model_dump(mode='json',exclude={'case'})
        if shared_tables is not None:
            for req, source, attachment in zip(requests, case['sources'], run.attachment_report['attachments']):
                if req.purpose != 'DATA_DICTIONARY' and attachment['mode'] == 'SCHEMA_ONLY':
                    text = document_tables(req.path)
                    source['text'] = text
                    attachment.update(mode='FULL_TABLE', extracted_chars=len(text),
                                      extracted_sha256=sha256(text.encode('utf8')).hexdigest(), warnings=[])
        example_id=payload.get('example_id'); network_declaration=payload.get('network')
        if example_id:
            example=next((x for x in self.examples if x['id']==example_id),None)
            if example is None:raise ValueError('EXAMPLE_NOT_FOUND')
            originals={s['source_id']:s for s in example['case']['sources']}
            selected=deepcopy(example['case']['sources'])
            if 'source_edits' in payload:
                edits=payload['source_edits']
                if not isinstance(edits,list) or len(edits)>len(originals):raise ValueError('INVALID_EXAMPLE_SOURCES')
                selected=[];seen=set();characters=0
                for edit in edits:
                    sid=edit.get('source_id');text=edit.get('text')
                    if sid not in originals or sid in seen or not isinstance(text,str) or not text.strip():
                        raise ValueError('INVALID_EXAMPLE_SOURCE_EDIT')
                    characters+=len(text)
                    if len(text)>25000 or characters>80000:raise ValueError('EXAMPLE_SOURCE_SIZE_LIMIT')
                    seen.add(sid);selected.append({**originals[sid],'text':text})
            case['sources']=selected+case['sources']
            use_network=payload.get('use_example_network', 'source_edits' not in payload)
            if type(use_network) is not bool:raise ValueError('INVALID_EXAMPLE_NETWORK_SELECTION')
            if use_network and example.get('network_files') and not network_paths:
                from .example_materials import selected_file
                for item in example['network_files']['files']:
                    path,name=selected_file(PROJECT_ROOT,example,item['role'])
                    target=folder/name;target.write_bytes(path.read_bytes());network_paths[item['role']]=target
                if network_declaration is None:network_declaration=deepcopy(example['network_files']['declaration'])
                self.save(run,'example_network_selection',dict(example_id=example_id,files=[p.name for p in network_paths.values()],declaration=network_declaration))
        if network_paths:
            if set(network_paths)!={'network_nodes','network_edges'}:raise ValueError('请同时上传对象表和关系表。')
            from cfm_id_llm.network_files import load_network
            run.network=load_network(network_paths['network_nodes'],network_paths['network_edges'],network_declaration,shared_tables=shared_tables)
        elif payload.get('network') is not None:raise ValueError('填写网络说明时，请同时上传对象表和关系表。')
        if table_path:
            from cfm_id_llm.record_files import read_records
            records=read_records(table_path,payload.get('table_mapping'),run.network,shared_tables=shared_tables)
            self.save(run,'table_import_manifest',records['manifest'])
            self.save(run,'factual_data_inventory',records['inventory'])
            for sid,label,value in (
                ('uploaded_data_schema','数据说明（用户提供）',records['schema']),
                ('uploaded_data_inventory','上传文件的实际记录范围（本地检查）',records['inventory'])):
                if any(x['source_id']==sid for x in case['sources']):raise ValueError('DATA_SOURCE_ID_COLLISION')
                case['sources'].append(dict(source_id=sid,kind='OTHER',label=label,text=json.dumps(value,ensure_ascii=False)))
            run.attachment_report['factual_data']=dict(nodes=len(records['schema']['node_ids']),
                features=len(records['schema']['feature_names']),observed=len(records['observed_indices']),
                note=('所选数据表的全部列及逐行记录供读取与审核共同使用。' if shared_tables is not None else '传递字段说明与实际记录范围。'))
        elif payload.get('table_mapping') is not None:raise ValueError('有列映射但没有表格数据，请重新选择文件。')
        if run.network:
            if any(x['source_id']=='uploaded_network' for x in case['sources']):raise ValueError('NETWORK_SOURCE_ID_COLLISION')
            case['sources'].append(run.network.source());self.save(run,'network_file_manifest',run.network.manifest())
            run.attachment_report['network']=dict(reference=run.network.token,nodes=len(run.network.nodes),
                edges=len(run.network.edges),completeness=run.network.completeness)
        if shared_tables is not None:
            append_sources(case, shared_tables)
        from cfm_id_llm.upload_receipt import receipt
        run.attachment_report['receipt']=receipt(run.attachment_report)
        run.case=case;self.save(run,'case',case)
        if preview_only:return
        if not run.attachment_report['receipt']['ready']:
            run.result=dict(state='NEEDS_INPUT',reason_code='ATTACHMENT_EXTRACTION_INCOMPLETE',backend_called=False,
                independent_replay=False,message='部分附件未读完整，请按上传回执修正文件，再开始读取。',
                clarification_questions=run.attachment_report['receipt']['issues'])
            self.event(run,'STOPPED','部分附件读取失败，请检查文件后重新提交。尚未调用模型。')
            return
        run.reading_mode=payload.get('reading_mode','direct_verify')
        if run.reading_mode in ('direct_verify','network_direct_verify','network_local_review'):
            self._direct_verify(run)
        elif run.reading_mode=='compact':
            self._compact_read(run)
        else:
            self._read_case(run)

    def _direct_verify(self,run,previous_draft=None):
        if run.reading_mode == 'network_local_review' or previous_draft is not None:
            from cfm_id.direct_verification import verify
            self.event(run,'READING','正在本机核验原材料与总体查询')
            report=verify(run.case,previous_draft or {},network=run.network,network_focus=True)
        else:
            self.event(run,'READING','模型正在按原题起草完整识别答案')
            from cfm_id_llm.providers.base import ProviderError
            focused=run.reading_mode=='network_direct_verify'
            try:
                report=project.direct_then_verify(run.case,lambda request,stage:self._call_direct(run,request,stage),
                                                  network=run.network,network_focus=focused,
                                                  population_ate=run.reading_mode=='direct_verify',
                                                  clarification_handoff=run.clarification_handoff)
            except ProviderError as exc:
                if exc.code!='MALFORMED_RESPONSE' or run.network is None:
                    raise
                from cfm_id.direct_verification import verify
                report=verify(run.case,{},network=run.network,network_focus=focused)
                from cfm_id.network_natural_sources import VERSION as natural_materials
                if (report.get('proof') or {}).get('binding_source') not in ('uploaded-materials/1',natural_materials):
                    raise
                self.save(run,'unparsed_model_answer',dict(code=exc.code,local_result_from='uploaded_materials'))
        self._finish_direct_verification(run,report)

    def _finish_direct_verification(self,run,report):
        from cfm_id import direct_policy_exchange
        if (report.get('joint_entry',{}).get('operation')=='NETWORK_LOCAL_BUNDLE' and report['joint_entry'].get('completed')
                and report['joint_entry'].get('state')!='BUNDLE_COMPLETE'):
            from cfm_id.joint_natural_entry import replay
            if report.get('proof') and not replay(run.case,report.get('draft'),report):
                self._withdraw_joint_result(run,report)
                raise ValueError('LOCAL_BUNDLE_REPLAY_REQUIRED')
        elif (report.get('joint_entry',{}).get('completed') and report.get('independent_replay')
                and report['joint_entry'].get('state') in ('POINT','PARTIAL','SYMBOLIC_BOUNDS','BUNDLE_COMPLETE')):
            from cfm_id import joint_query_exchange
            # Derive from the current source review and independently replayed
            # certificate. A prior inbox receipt can never authorize this run.
            try:
                packet=joint_query_exchange.packet(run.case,report)
                receipt=self.estimate_inbox.receive(run.id,packet)
                self.save(run,'identification_handoff',packet)
                self.save(run,'estimate_intake_receipt',receipt)
            except Exception:
                self._withdraw_joint_result(run,report)
                self.estimate_inbox.revoke(run.id)
                self.save(run,'estimate_intake_receipt',dict(run_id=run.id,state='DELIVERY_FAILED'))
                raise
            report=deepcopy(report)
            report.update(estimation_handoff_allowed=True,scientific_approval=run.authority=='EXTERNAL_RESEARCH_REVIEW')
        elif report.get('joint_entry') and (report.get('independent_replay') or report.get('proof')
                or report['joint_entry'].get('state') in ('POINT','PARTIAL','SYMBOLIC_BOUNDS','NONIDENTIFIABLE')):
            # Nonidentification witnesses and incompatible models are displayed
            # without estimation delivery, but require the same source binding.
            from cfm_id.joint_natural_entry import replay
            if not report.get('independent_replay') or not replay(run.case,report.get('draft'),report):
                self._withdraw_joint_result(run,report)
                raise ValueError('JOINT_RESULT_REPLAY_REQUIRED')
        if not report.get('estimation_handoff_allowed'):
            self._revoke_network_delivery(run)
        proof=report.get('proof') or {}
        answer = report.get('effective_answer') or {}
        stopped_on_assumption = (proof.get('method') == 'ORIGINAL_EVENT_ASSUMPTIONS_UNCONFIRMED'
                                 and answer.get('status') == 'NEEDS_INPUT'
                                 and (answer.get('estimate_handoff') or {}).get('mode') == 'STOP')
        native_policy=proof.get('binder') in direct_policy_exchange.VERSIONS
        if native_policy or proof.get('binder')=='uploaded-network-comparison/1':
            packet=dict(version='identification-handoff/1',target=answer['target'],status=answer['status'],
                value=answer['value'],assumptions=answer['assumptions'],estimate_handoff=answer['estimate_handoff'],
                source_proof=proof,scientific_approval=report['scientific_approval'],production_admission=False,
                estimation_handoff_allowed=report['estimation_handoff_allowed'])
            if report['estimation_handoff_allowed']:
                if native_policy:
                    packet=direct_policy_exchange.packet(run.case,report)
                else:
                    from cfm_id.network_query_exchange import ALIGNED_PACKET
                    if not (report.get('network_alignment') or {}).get('matched'):
                        raise ValueError('NETWORK_SOURCE_ALIGNMENT_REQUIRED')
                    packet.update(version=ALIGNED_PACKET,source_case=run.case,source_draft=report['draft'],
                                  network_focus=bool(report.get('network_focus')),network_alignment=report['network_alignment'])
                    if report.get('scope_choice'):
                        packet['scope_choice']=deepcopy(report['scope_choice'])
                    packet.update(review=report['review_record'],condition_review=report['condition_review'],release_scope=run.authority,
                                  network_manifest=report['network_manifest'])
                try:
                    receipt=self.estimate_inbox.receive(run.id,packet)
                    self.save(run,'identification_handoff',packet)
                    self.save(run,'estimate_intake_receipt',receipt)
                except Exception:
                    self.estimate_inbox.revoke(run.id)
                    self.save(run,'identification_handoff',dict(version='identification-handoff/1',status='RECHECK_REQUIRED',
                        estimate_handoff=dict(mode='STOP',queries=[]),estimation_handoff_allowed=False,scientific_approval=False))
                    self.save(run,'estimate_intake_receipt',dict(run_id=run.id,state='DELIVERY_FAILED'))
                    raise
            else:
                self.save(run,'identification_handoff',packet)
        elif (proof.get('method') in ('ORIGINAL_EVENT_MEANS','TWO_BINARY_POLICY_MARGINS','NAMED_FULL_PLAN_LEVEL',
                                      'OBSERVED_NODEWISE_STANDARDIZATION','OBSERVED_PEER_CONDITION_GAP','OBSERVED_REPORTED_STRATA',
                                      'FIXED_QUOTA_WHOLE_POLICY','LABELED_OBSERVATIONAL_ARMS','ANNOUNCED_TWO_STAGE_QUOTA',
                                      'POPULATION_WEIGHTED_SAVINGS') or stopped_on_assumption):
            self.save(run,'identification_handoff',dict(version='identification-handoff/1',target=answer['target'],
                status=answer['status'],value=answer['value'],assumptions=answer['assumptions'],
                estimate_handoff=answer['estimate_handoff'],source_proof=proof,
                scientific_approval=False,estimation_handoff_allowed=False))
        elif 'identification_handoff' in run.artifacts and not report.get('estimation_handoff_allowed'):
            self.save(run,'identification_handoff',dict(version='identification-handoff/1',status='RECHECK_REQUIRED',
                estimate_handoff={'mode':'STOP'},scientific_approval=False,estimation_handoff_allowed=False))
        self.save(run,'direct_verification',report)
        run.result=report
        questions=report.get('clarification_questions',[])
        if not questions and not report.get('population_ate') and not report.get('local_targets') and not report.get('joint_entry'):
            from .direct_questions import explicit_questions
            questions=explicit_questions(report)
            if questions:
                self.save(run,'direct_model_questions',dict(origin='model_explicit_request',
                    items=questions,scientific_approval=False,input_sha256=report.get('input_sha256'),
                    draft_sha256=report.get('draft_sha256')))
        run.user_question=None
        if report.get('joint_entry'):
            entry=report['joint_entry']
            if questions:
                run.user_question=dict(kind='NEEDS_CLARIFICATION',items=questions,message='请补充这些问题所缺的信息。')
            self.event(run,'RESULT' if entry.get('completed') else
                       'REVIEW_REQUIRED' if questions or report.get('condition_review') else 'STOPPED',entry['message'])
            return
        if report.get('local_targets'):
            entry=report['local_targets']
            if questions:
                run.user_question=dict(kind='NEEDS_CLARIFICATION',items=questions,message='请补充这些问题所缺的信息。')
            self.event(run,'RESULT' if entry['state'] in ('COMPLETED','INCOMPLETE') else
                       'REVIEW_REQUIRED' if questions or report.get('condition_review') else 'STOPPED',entry['message'])
            return
        if report.get('population_ate'):
            entry=report['population_ate']
            if questions:
                run.user_question=dict(kind='NEEDS_CLARIFICATION',items=questions,message='请确认以下研究信息。')
                self.event(run,'REVIEW_REQUIRED',entry['message'])
            elif entry['state']=='REVIEW_REQUIRED':
                self.event(run,'REVIEW_REQUIRED',entry['message'])
            else:
                self.event(run,'RESULT' if report.get('independent_replay') else 'STOPPED',entry['message'])
            return
        if report.get('review_scope')=='SYNTHETIC_TEST_ONLY' and not run.synthetic and report.get('review_record'):
            self.event(run,'RESULT','已记录研究者的判断。本路线提供条件结果，真实研究的估计交接待单独审核')
        elif report.get('condition_review') and not report['estimation_handoff_allowed']:
            self.event(run,'REVIEW_REQUIRED','请逐项核对原文所列科学前提，以便登记估计交接')
        elif report.get('estimation_handoff_allowed'):
            accepted=run.artifacts.get('estimate_intake_receipt',{}).get('consumer')=='autocfm_estimation_query_intake'
            self.event(run,'RESULT','估计端已收到本次确认的查询或上下界' if accepted else '本次确认的估计交接已登记')
        elif questions:
            run.user_question=dict(kind='NEEDS_CLARIFICATION',items=questions,message='请补充以下研究材料。')
            self.event(run,'REVIEW_REQUIRED','研究材料有具体缺口，补充后可重新核验同一问题')
        else:
            self.event(run,'RESULT','模型原答与程序核验结果已保存')
            # A retained model answer is not a certificate. Continue through
            # the existing semantic and scientific reviews, using exactly the
            # same sources. Never import the draft as evidence or approval.
            if (run.reading_mode == 'direct_verify' and run.automatic_review
                    and report.get('decision') == 'RETAINED' and not report.get('proof')
                    and not report.get('scientific_approval')
                    and not report.get('estimation_handoff_allowed')
                    and not report.get('condition_review') and not report.get('review_record')
                    and not any(c.get('state') == 'CONFLICT' for c in report.get('checks', []))):
                self.save(run,'reading_continuation',dict(from_mode='direct_verify',to_mode='classic',
                    reason='NO_CERTIFIED_DIRECT_RESULT',original_report='direct_verification',
                    input_sha256=report.get('input_sha256'),draft_sha256=report.get('draft_sha256'),
                    scientific_approval=False))
                run.reading_mode='classic'
                run.result=None
                self.event(run,'READING','原答已保存，正在按同一份材料继续审核并调用识别库')
                self._read_case(run)

    def _compact_read(self,run):
        from cfm_id.project import read_compact
        self.event(run,'READING','读取研究目标、总体信息和有来源的科学条件')
        prepared=read_compact(run.case,lambda request,stage:self.call(run,request,stage),
            on_disputes=lambda issues:self.save(run,'compact_disputed_fields',issues))
        self.save(run,'compact_plan',prepared)
        if prepared['state']=='REVIEW_REQUIRED':
            run.plan=prepared
            self.event(run,'REVIEW_REQUIRED','请核对引用、研究目标及各方法需要的科学条件')
        else:
            run.result=prepared
            self.save(run,'identification',prepared)
            self.event(run,'STOPPED','本次方法匹配的结果已保存')

    def _compact_finish(self,run,review):
        from cfm_id.project import confirm_compact
        if run.result is not None or not run.plan:raise ValueError('NO_PENDING_COMPACT_PLAN')
        approved=confirm_compact(run.plan,review,authority=run.authority)
        self.save(run,'compact_review',review)
        if approved['state']=='REVIEW_REQUIRED':
            self.event(run,'REVIEW_REQUIRED','存在尚未批准的项目，仍待核对')
            return
        run.result=approved
        self.save(run,'identification',approved)
        self.event(run,'RESULT','研究规格、方法结果及估计交接已保存')

    def _read_case(self,run, *, target_feedback=None):
        if run.automatic_review and self._check_material_counts(run):return
        config=capabilities.reading_config()
        run.intake=intake.start_configured(run.case,config);self.save(run,'reading_config',config)
        request=intake.prepare_request(run.intake)
        if target_feedback is not None:
            request=deepcopy(request)
            # Preserve the prior wire answer for a located reread. It is a
            # comparison aid, never evidence or a source of inherited approval.
            prior=run.artifacts.get('target_reread_prior',{}).get('artifacts',{}).get('a0_candidate')
            request['user_prompt']+='\n\n'+json.dumps(dict(
                reread_reason=target_feedback, previous_candidate=deepcopy(prior),
                instruction='后台在当前业务解释中定位到问题。previous_candidate是上一版待核对回答，反馈与候选均不是业务证据。请按原文和字段定义逐项核对，返回整份 A0。修正被指出的问题，同时检查其余字段，保留原文支持的目标、取值范围和未定内容；不能因修正某字段而改写其他字段的含义，也不能照抄错误。若涉及局部效应类别，分别核对两端本人与同伴的状态是否变化。不增加科学条件；新回答仍需完整审核。'),ensure_ascii=False)
        self.event(run,'READING','正在读取研究问题、比较方式和评价对象')
        candidate=self.call(run,request,'a0')
        run.intake=intake.receive_candidate(run.intake,candidate,request_sha256=request['request_sha256'])
        self.save(run,'intake',run.intake)
        inspected=intake.inspect(run.intake);self.save(run,'reading_inspection',inspected)
        if (run.automatic_review and inspected.get('reason_code') in ('COMPACT_SCHEMA_REJECTED','A0_SCHEMA_REJECTED','A0_REFERENCE_CONTEXT_MISMATCH')
                and run.automatic_a0_format_repairs<1):
            # Include canonical cross-field validation after wire projection.
            # A new model answer must pass the same contract and semantic review;
            # this never repairs the candidate or overrides a valid rejection.
            # Retain the original response and intake; no deterministic unwrapping,
            # source completion or change of the original business is performed.
            self.save(run,'a0_initial_intake',run.intake)
            self.save(run,'a0_initial_inspection',inspected)
            run.automatic_a0_format_repairs+=1
            repair=deepcopy(request)
            feedback=dict(code=inspected.get('reason_code'),diagnostics=inspected.get('diagnostics',{}),previous_response=candidate,
                instruction='上次输出未通过本次Schema。请按原输出合同重新返回完整答案，保持原材料中的目标、条件和未知状态。不要修改Schema或为了格式通过而删减业务内容；不批准科学条件。')
            repair['user_prompt']+='\n\n本次格式检查反馈（不是新的业务材料）：\n'+json.dumps(feedback,ensure_ascii=False)
            self.event(run,'READING','业务读取的输出格式有误，后台进行一次格式复查；原材料保持不变')
            candidate=self.call(run,repair,'a0_format_retry')
            run.intake=intake.receive_candidate(run.intake,candidate,request_sha256=request['request_sha256'])
            self.save(run,'intake',run.intake)
            inspected=intake.inspect(run.intake);self.save(run,'reading_inspection',inspected)
        if inspected['state']!='SEMANTIC_REVIEW_REQUIRED':
            if run.automatic_review and self._review_intake_stop(run,inspected):return
            run.result=inspected;self.event(run,'STOPPED','读取未通过程序检查；请查看具体原因。');return
        run.queries=inspected['report']['draft']['queries']
        self.event(run,'SELECT_QUERY','已读取研究问题，请选择本次分析的问题。')
        if len(run.queries)==1:self._select(run,run.queries[0]['query_id'])

    def call(self,run,request,stage):
        with self.lock:
            cred=self.credentials.get(run.owner)
            if cred is None or time.time()-cred[2]>8*3600:raise ValueError('API_KEY_REQUIRED')
            if cred[0]!=run.provider:raise ValueError('PROVIDER_CREDENTIAL_MISMATCH')
            options=deepcopy(self.connection_settings.get(run.owner,PROVIDERS[run.provider]))
            if run.model_settings and options!=run.model_settings:raise ValueError('MODEL_SETTINGS_CHANGED_NEW_RUN_REQUIRED')
            if not run.model_settings:run.model_settings=deepcopy(options)
            if self.calls>=self.max_api_calls:raise ValueError('LOCAL_API_CALL_LIMIT')
            alias,key,_=cred;self.calls+=1
        run.provider=alias
        self.save(run,stage+'_request',request)
        # Clearing a browser key during an in-flight request must not remove
        # that request's redaction boundary.
        def observe(text):self.save(run,stage+'_raw_response',self._clean({'content':text},(key,)))
        limit=self.longcat_fact_max_tokens if alias=='longcat' and stage=='facts' else DEFAULT_OUTPUT_TOKENS
        if alias=='longcat' and stage.endswith('_length_retry'):
            limit=max(DEFAULT_OUTPUT_TOKENS, self.longcat_fact_max_tokens)
        client=self.provider_factory(**options,api_key=key,timeout=300,max_tokens=limit,observer=observe)
        try:
            value=generate(client,request,fact=stage=='facts' or stage.startswith('facts_field_patch'))
            value=self._clean(value,(key,));self.save(run,stage+'_candidate',value);return value
        finally:
            self.save(run,stage+'_transport',dict(provider=alias,model=options['model'],base_url=options['base_url'],
                diagnostics=client.last_diagnostics,automatic_retries=0))
            client.api_key=None;key=None

    def _call_direct(self,run,request,stage):
        """One complete retry per direct workflow phase, including source audit.

        This path uses full-field audit contracts. The classic audit's sparse
        findings instruction must never be reused here. Truncated JSON and
        partial reasoning are not candidates and cannot enter a mathematical
        or scientific approval gate.
        """
        from cfm_id_llm.providers.base import ProviderError
        try:return self.call(run,request,stage)
        except ProviderError as exc:
            if exc.code == 'TIMEOUT' and run.automatic_direct_transport_retries < 1:
                run.automatic_direct_transport_retries += 1
                self.save(run,stage+'_transport_recovery',dict(reason='TIMEOUT',attempts=1,
                    same_request=True,possible_duplicate_provider_charge=True,scientific_approval=False))
                self.event(run,'READING','模型请求超时，后台按原请求重试一次。')
                return self.call(run,request,stage+'_timeout_retry')
            if exc.code!='INCOMPLETE_COMPLETION' or exc.diagnostics.get('finish_reason')!='length':raise
            scope=stage
            for phase in ('joint_source_read','joint_source_audit','joint_gap_review','joint_condition_semantics','network_source_route'):
                if stage.startswith(phase):scope=phase
            if stage=='joint_audit_format_retry':scope='joint_source_audit'
            if stage=='joint_source_format_retry':scope='joint_source_read'
            if scope in run.automatic_direct_length_retries:raise
            run.automatic_direct_length_retries.add(scope)
            self.save(run,stage+'_length_recovery',dict(scope=scope,reason='OUTPUT_TRUNCATED',
                attempts=1,scientific_approval=False,retry_stage=stage+'_length_retry'))
            retry=deepcopy(request)
            retry['system_prompt']+='\n上次回复因长度上限中断，整份未采用。请根据同一份原文和输出合同重新返回完整JSON。说明简短，但字段、审核项、引文、未知项和额外条件必须完整保留；不要续写半份JSON，也不要为了缩短输出改题或删条件。'
            self.event(run,'READING','模型回复未写完整，后台重新请求一次完整答复；无需重新提交或补条件。')
            return self.call(run,retry,stage+'_length_retry')

    def _call_audit(self,run,request,stage):
        """Recover one truncated review per phase; never accept partial JSON.

        A valid adverse review, refusal, missing finish reason or transport
        failure is not an output-length recovery. All original evidence and
        the full review scope remain in the retry, with a separate trace.
        """
        from cfm_id_llm.providers.base import ProviderError
        try:
            return self.call(run,request,stage)
        except ProviderError as exc:
            if exc.code!='INCOMPLETE_COMPLETION' or exc.diagnostics.get('finish_reason')!='length':
                raise
            scope=run.review_kind or stage
            if scope in run.automatic_audit_length_retries:raise
            run.automatic_audit_length_retries.add(scope)
            self.save(run,stage+'_length_recovery',dict(scope=scope,
                reason='OUTPUT_TRUNCATED',attempts=1,scientific_approval=False,
                retry_stage=stage+'_length_retry'))
            retry=deepcopy(request)
            retry['system_prompt']+='\n上次复核回复因输出长度中断，未被采用。本次仍核查全部原文和字段；仅输出合同要求的JSON，理由简短，不逐句复述材料。普通findings只列错误、待澄清及必答字段；assessments仍须逐项完整回答。不得为缩短输出遗漏异常、范围或来源。'
            self.event(run,'REVIEWING_READING','复核回复未写完整，后台正在重新核对；无需重新提交或补充条件。')
            return self.call(run,retry,stage+'_length_retry')

    def _set_review(self,run,kind,sheets):
        run.review_kind=kind;run.review_sheets=deepcopy(sheets)
        run.review_templates={name:pending(sheet,run.authority) for name,sheet in sheets.items()}
        self.event(run,'REVIEW_REQUIRED',{'query':'核对模型读到的问题与原文','source':'核对事实和实际引用',
            'notes':'处理模型提出的缺项或备注','information':'核对总体信息的来源范围',
            'science':'确认识别目标与本研究采用的科学条件','dag_source':'后台核对因果图、变量与原文来源','changes':'核对复查回答的全部变化',
            'saved_target':'按原始材料核对已导入读题的目标及范围'}[kind])

    def _select(self,run,qid):
        if qid not in [q['query_id'] for q in run.queries]:raise ValueError('UNKNOWN_QUERY')
        if run.submission is not None:raise ValueError('START_NEW_RUN_FOR_ANOTHER_COMPLETED_QUERY')
        run.query_id=qid
        sheet=business_field_review.prepare(run.intake,qid,authority=run.authority)['field_worksheet']
        self._set_review(run,'query',{'query':sheet})

    def action(self,owner,run_id,action,payload):
        run=self.get(owner,run_id)
        if action=='select':self.launch(run,self._select,payload['query_id'])
        elif action=='review':self.launch(run,self._review,payload)
        elif action=='estimate':raise ValueError('ESTIMATION_NOT_IN_IDENTIFICATION_DEMO')
        elif action=='retry_estimate_registration' and run.reading_mode=='classic':
            if (run.result or {}).get('estimate_registration',{}).get('state')!='DELIVERY_FAILED':
                raise ValueError('NO_FAILED_CLASSIC_DELIVERY')
            self.launch(run,self._register_classic_result)
        elif action=='compact_confirm' and run.reading_mode=='compact':
            self.launch(run,self._compact_finish,deepcopy(payload))
        elif action=='review_population_ate_conditions':
            from cfm_id.population_ate_entry import check_review
            with run.lock:
                if run.busy:raise ValueError('RUN_ALREADY_BUSY')
                sheet=(run.result or {}).get('condition_review')
                if (not sheet or sheet.get('kind')!='population_ate' or not isinstance(payload,dict)
                        or set(payload)!={'binding','decisions'}):
                    raise ValueError('POPULATION_ATE_REVIEW_NOT_AVAILABLE')
                record=dict(binding=payload['binding'],authority=run.authority,decisions=deepcopy(payload['decisions']))
                check_review(sheet,record)
                self.launch(run,self._review_population_ate,record)
        elif action=='review_joint_conditions':
            from cfm_id.joint_natural_entry import check_review
            with run.lock:
                sheet=(run.result or {}).get('condition_review')
                if (run.busy or not sheet or sheet.get('kind')!='joint_natural' or not isinstance(payload,dict)
                        or set(payload)!={'binding','decisions'}):raise ValueError('JOINT_REVIEW_NOT_AVAILABLE')
                record=dict(binding=payload['binding'],authority=run.authority,decisions=deepcopy(payload['decisions']))
                check_review(sheet,record)
                self.launch(run,self._review_joint,record)
        elif action=='choose_network_population':
            with run.lock:
                sheet=(run.result or {}).get('scope_worksheet')
                if (run.busy or not sheet or not isinstance(payload,dict) or set(payload)!={'binding','option'}
                        or payload['binding']!=sheet['binding'] or payload['option'] not in {o['id'] for o in sheet['options']}):
                    raise ValueError('INVALID_OR_STALE_POPULATION_CHOICE')
                if run.result.get('scope_choice')!=payload or run.error:
                    self.launch(run,self._choose_network_population,deepcopy(payload))
        elif action=='review_network_conditions':
            from cfm_id.uploaded_network_contrast import check_review
            with run.lock:
                if run.busy:
                    raise ValueError('RUN_ALREADY_BUSY')
                sheet=(run.result or {}).get('condition_review')
                if not sheet or not isinstance(payload,dict) or set(payload)!={'binding','decisions'}:
                    raise ValueError('NETWORK_REVIEW_NOT_AVAILABLE')
                record=dict(binding=payload['binding'],authority=run.authority,decisions=deepcopy(payload['decisions']))
                if sheet.get('kind')=='network_local_targets':
                    from cfm_id.network_local_targets import check_review
                check_review(sheet,record)
                if run.result.get('review_record')==record and not run.error:
                    return
                self.launch(run,self._review_network,record)
        elif action=='request_point':
            if (run.stage!='RESULT' or not ((run.result or {}).get('proof') or {}).get('point_optional')
                    or (run.result or {}).get('clarification_questions')):
                raise ValueError('POINT_REFINEMENT_NOT_AVAILABLE')
            self.launch(run,self._clarify,'我需要单一点值。')
        elif action=='clarify':
            text=payload.get('text','')
            from cfm_id.network_material_questions import DEGREE
            from cfm_id.sequential_policy_value import METHOD as two_stage_policy
            result=run.result or {}
            short_reply=result.get('clarification_questions') and (result.get('proof') or {}).get('method') in (DEGREE,two_stage_policy)
            if not isinstance(text,str) or not (1 if short_reply else 3)<=len(text.strip())<=8000:raise ValueError('CLARIFICATION_TEXT_REQUIRED')
            self.launch(run,self._clarify,text.strip())
        elif action=='retry_reading':
            if not run.automatic_review or not run.error or run.review_kind not in ('query','source','changes'):
                raise ValueError('NO_RETRYABLE_READING')
            self.launch(run,self._retry_reading)
        elif action=='recheck':
            from . import recovery
            with run.lock:
                if run.busy:raise ValueError('RUN_ALREADY_BUSY')
                entry,feedback=recovery.request(run,payload.get('binding_sha256'))
                self.launch(run,self._recheck,entry,feedback)
        else:raise ValueError('UNKNOWN_ACTION')

    def _review_joint(self,run,record):
        from cfm_id.joint_natural_entry import complete
        report=complete(run.case,run.result,record)
        self.save(run,'joint_scientific_review',record)
        self._finish_direct_verification(run,report)

    def _withdraw_joint_result(self,run,report):
        """Do not leave an earlier receipt/result visible after failed binding."""
        from cfm_id.joint_natural_entry import base,stop
        self._revoke_network_delivery(run)
        self.save(run,'rejected_direct_verification',report)
        cleared=stop(base(report,run.case),'RECHECK_REQUIRED','JOINT_RESULT_REPLAY_REQUIRED',
            '本次结果或交接未通过核对，旧回执已撤回；尚未交付可用结论。')
        run.result=cleared
        run.user_question=None
        self.save(run,'direct_verification',cleared)

    def _revoke_network_delivery(self,run):
        if run.artifacts.get('estimate_intake_receipt',{}).get('state') in ('RECEIVED','QUEUED','DELIVERY_FAILED'):
            self.estimate_inbox.revoke(run.id)
            self.save(run,'estimate_intake_receipt',dict(run_id=run.id,state='SUPERSEDED'))
            if run.result and 'estimate_registration' in run.result:
                run.result['estimate_registration']=deepcopy(run.artifacts['estimate_intake_receipt'])
                self.save(run,'identification',run.result)
            self.save(run,'identification_handoff',dict(version='identification-handoff/1',status='RECHECK_REQUIRED',
                estimate_handoff=dict(mode='STOP',queries=[]),estimation_handoff_allowed=False,scientific_approval=False))

    def _review_network(self,run,record):
        from cfm_id.direct_verification import verify
        try:
            report=verify(run.case,run.result['draft'],network=run.network,
                          network_focus=run.reading_mode=='network_direct_verify',science_review=record,
                          scope_choice=run.result.get('scope_choice'))
        except (ValueError, KeyError, TypeError):
            self._revoke_network_delivery(run)
            raise
        self._revoke_network_delivery(run)
        self._finish_direct_verification(run,report)

    def _review_population_ate(self,run,record):
        from cfm_id.population_ate_entry import complete
        self.event(run,'IDENTIFYING','正在按本次确认的条件调用数学库并独立重放')
        report=complete(run.case,run.result,record)
        self.save(run,'population_ate_review',record)
        self._finish_direct_verification(run,report)

    def _choose_network_population(self,run,choice):
        from cfm_id.direct_verification import verify
        self._revoke_network_delivery(run)
        report=verify(run.case,run.result['draft'],network=run.network,network_focus=run.reading_mode=='network_direct_verify',scope_choice=choice)
        self._finish_direct_verification(run,report)

    def _retry_reading(self,run):
        self.event(run,'PREPARING','正在重新核对原材料')
        if run.pending_fact_recheck is not None:
            pending=deepcopy(run.pending_fact_recheck)
            self._recheck(run,pending['entry'],pending['feedback'])

    def _clarify(self,run,text):
        self._revoke_network_delivery(run)
        previous=run.result or {}
        previous_case=deepcopy(run.case)
        number=1+sum(k.startswith('input_revision_') for k in run.artifacts)
        self.save(run,f'input_revision_{number}',dict(case=run.case,intake=plain(run.intake),
            submission=run.submission,reviews=run.reviews,plan=run.plan,result=run.result))
        run.case=deepcopy(run.case)
        from cfm_id.network_material_questions import DEGREE
        from cfm_id.sequential_policy_value import METHOD as policy_value
        label='用户补充说明'
        prompts=previous.get('clarification_questions') or []
        if (previous.get('proof') or {}).get('method') in (policy_value,DEGREE) and len(prompts)==1:
            label=prompts[0]
        run.case['sources'].append(dict(source_id=f'user_reply_{uuid4().hex[:8]}',kind='OTHER',label=label,text=text))
        from cfm_id_llm.network_source_route import continuation
        run.clarification_handoff=continuation(run.case,previous_case,previous)
        if run.clarification_handoff:self.save(run,'clarification_target_handoff',run.clarification_handoff)
        self.save(run,'case',run.case)
        run.intake=None;run.entry=None;run.submission=None;run.query_review=None;run.query_id=None
        run.queries=[];run.reviews={};run.plan=None;run.result=None;run.estimate=None
        run.review_kind=None;run.review_sheets={};run.review_templates={};run.user_question=None
        run.automatic_rechecks=0;run.automatic_audit_repairs=0;run.automatic_a0_format_repairs=0;run.automatic_fact_format_repairs=0
        run.automatic_focused_stages.clear()
        run.pending_fact_recheck=None;run.automatic_fact_transport_retries=0
        self.event(run,'PREPARING','已保存补充说明，正在重新检查')
        if run.reading_mode in ('direct_verify','network_direct_verify','network_local_review'):
            reuse=None
            if (previous.get('proof') or {}).get('method') in ('POPULATION_WEIGHTED_SAVINGS', DEGREE, policy_value):
                from cfm_id.direct_verification import verify
                report=verify(run.case,previous['draft'],network=run.network,network_focus=run.reading_mode=='network_direct_verify')
                self._finish_direct_verification(run,report)
                return
            if (run.reading_mode in ('direct_verify','network_direct_verify')
                    and (previous.get('proof') or {}).get('method')=='ANNOUNCED_TWO_STAGE_QUOTA'):
                from cfm_id.direct_verification import verify
                report=verify(run.case,previous.get('draft') or {},network=run.network,
                              network_focus=run.reading_mode=='network_direct_verify')
                self._finish_direct_verification(run,report)
                return
            if run.reading_mode=='network_direct_verify' and (previous.get('proof') or {}).get('method')=='TWO_BINARY_POLICY_MARGINS':
                from cfm_id.network_query_binding import source_result
                if source_result(run.case):
                    reuse=previous.get('draft')
            elif (run.reading_mode in ('direct_verify','network_direct_verify')
                  and (previous.get('proof') or {}).get('binder')=='source-grounded-contrast/1'
                  and previous['proof'].get('alternative_joint_probabilities')):
                from cfm_id.direct_verification import verify
                # Preserve the original answer only when the complete amended record
                # produces a new source-grounded proof, including every reply.
                draft=previous.get('draft') or {}
                report=verify(run.case,draft,network=run.network,network_focus=run.reading_mode=='network_direct_verify')
                if (report.get('proof') or {}).get('design_reply_sources'):
                    self.event(run,'READING','已按用户补充的抽签说明重新核验原问题')
                    self._finish_direct_verification(run,report)
                    return
            self._direct_verify(run,reuse)
        elif run.reading_mode=='compact':self._compact_read(run)
        else:self._read_case(run)

    def _recheck(self,run,entry,feedback):
        self._revoke_network_delivery(run)
        number=len(entry['reading_revision']['steps'])
        self.save(run,f'facts_before_recheck_{number}',run.submission)
        self.save(run,f'feedback_recheck_{number}',feedback)
        for name in ('facts_request','facts_candidate','facts_raw_response','facts_transport'):
            if name in run.artifacts:self.save(run,f'{name}_before_recheck_{number}',run.artifacts[name])
        self.event(run,'READING_RECHECK','正在核对标出的说明')
        run.pending_fact_recheck=dict(entry=deepcopy(entry),feedback=deepcopy(feedback))
        raw=self._read_facts(run,entry,feedback=feedback)
        # New candidate invalidates old source/science/change approvals.
        run.entry=entry
        run.submission=dict(query_review=run.query_review,candidate=raw,
            request_sha256=entry['request_sha256'],reading_revision=entry['reading_revision'])
        run.reviews={};run.result=None;run.estimate=None
        run.pending_fact_recheck=None
        self._plan(run)

    def _read_facts(self,run,entry,*,feedback=None):
        """One explicit schema retry; never edit candidate data or grant review."""
        from pydantic import ValidationError
        from cfm_id_llm.fact_wire_models import model_for
        from cfm_id_llm import file_coordinates as fact_coordinates
        from cfm_id_llm.network_design_reading import check_component_structure, ComponentStructureError
        from cfm_id_llm import network_file_binding
        from cfm_id_llm.network_files import NetworkFileError
        from . import fact_wire_recovery as field_wire
        from cfm_id_llm.providers.base import ProviderError
        tables=None
        if run.network is not None:
            entry,tables=fact_coordinates.prepare_for_graph(entry,list(run.network.nodes),run.network.edges)
        entry,network_binding=network_file_binding.prepare(entry,run.network)
        entry=field_wire.prepare(entry)
        previous=deepcopy((run.submission or {}).get('candidate')) if feedback else None
        field_feedback=feedback
        wire_feedback=None
        def read(request):
            patch=field_wire.field_request(request,previous,field_feedback,wire_feedback)
            if patch is None:
                answer=self.call(run,request,'facts')
            else:
                wire,receipt=patch
                attempt=1+sum(k.startswith('facts_field_patch_attempt_') and k.endswith('_request') for k in run.artifacts)
                for suffix in ('request','candidate','raw_response','transport'):
                    name='facts_field_patch_'+suffix
                    if name in run.artifacts:self.save(run,f'facts_field_patch_attempt_{attempt}_{suffix}',run.artifacts[name])
                self.save(run,'facts_field_recovery',dict(binding_sha256=receipt['binding_sha256'],
                    fields=receipt['fields'],previous_candidate_sha256=receipt['candidate_sha256'],
                    scientific_approval=False,requires_full_source_review=True))
                try:
                    answer=self.call(run,wire,'facts_field_patch')
                except ProviderError as exc:
                    if exc.code!='TIMEOUT' or run.automatic_fact_transport_retries>=1:raise
                    run.automatic_fact_transport_retries+=1
                    self.save(run,'facts_field_transport_recovery',dict(code='TIMEOUT',attempts=1,
                        same_request=True,scientific_approval=False))
                    self.event(run,'READING_RECHECK','这次字段重读未及时返回，后台重试一次；原问题和条件保持不变')
                    answer=self.call(run,wire,'facts_field_patch_timeout_retry')
                answer=field_wire.merge(answer,receipt)
                self.save(run,'facts_candidate',answer)
            candidate=fact_coordinates.expand(answer,tables)
            candidate=network_file_binding.expand(candidate,network_binding)
            candidate=field_wire.expand(candidate)
            if tables is not None or network_binding is not None or candidate!=answer:
                self.save(run,'facts_expanded',candidate)
            if network_binding is not None:
                self.save(run,'network_file_binding',dict(reference=run.network.token,
                    source_ids=network_binding['source_ids'],arrays_match=True,scientific_approval=False))
            return candidate
        model=model_for(entry)
        try:
            raw=read(entry)
            if model is not None:check_component_structure(model.model_validate(deepcopy(raw)))
            return raw
        except ComponentStructureError as exc:
            raw=run.artifacts['facts_candidate']
            diagnostics=exc.diagnostics
        except (fact_coordinates.CoordinateError,NetworkFileError) as exc:
            raw=run.artifacts['facts_candidate']
            diagnostics=[dict(code=str(exc),path='/study or /information/arm_cells')]
        except field_wire.FactWireError as exc:
            raw=run.artifacts.get('facts_candidate',previous)
            diagnostics=[dict(code=str(exc),path=exc.path)]
        except ValidationError as exc:
            if tables is not None or network_binding is not None:
                raw=run.artifacts['facts_candidate']
            diagnostics=[dict(path='/'+'/'.join(map(str,e['loc'])),code=e['type'],message=e['msg'])
                         for e in exc.errors(include_input=False,include_url=False)]
        self.save(run,'facts_format_validation',dict(valid=False,errors=diagnostics))
        if run.automatic_fact_format_repairs>=1:
            raise ValueError('FACT_READING_FORMAT_INVALID_AFTER_RETRY')
        run.automatic_fact_format_repairs+=1
        wire_feedback=dict(errors=diagnostics,previous_response=run.artifacts.get('facts_field_patch_candidate',raw))
        if field_feedback is None:
            previous=deepcopy(raw)
            field_feedback=dict(issues=[dict(field_path=d.get('path',d.get('field_path')),
                reason=d.get('message',d.get('constraint',d.get('code',d.get('error_code')))))
                for d in diagnostics])
        for name in ('facts_request','facts_candidate','facts_raw_response','facts_transport'):
            if name in run.artifacts:self.save(run,name+'_before_format_retry',run.artifacts[name])
        repair=deepcopy(entry);request=repair['request']
        key='user' if 'user' in request else 'user_prompt'
        request[key]+='\n\n'+json.dumps(dict(format_feedback=dict(errors=diagnostics,previous_response=raw,
            instruction='上次输出违反本次Schema/字段组合规则。请根据同一份原材料重新读取并输出完整候选；不添加条件、不自动补事实、不批准假设。后续来源与科学审核仍须执行。')),ensure_ascii=False)
        self.event(run,'READING_FACTS','读取输出存在字段组合错误，后台进行一次格式复查；原材料保持不变')
        raw=read(repair)
        if model is not None:check_component_structure(model.model_validate(deepcopy(raw)))
        self.save(run,'facts_format_retry_validation',dict(valid=True,scientific_approval=False))
        return raw

    def _continue_automatically(self,run):
        if run.reading_mode in ('direct_verify','network_direct_verify','compact'):return
        from . import automatic_review as audit
        from . import recovery
        from . import note_review
        # A classified input gap already has a source-bound user question.
        # Do not erase it when launch() continues after the initial read.
        if run.result is not None:return
        run.user_question=None
        for _ in range(8):
            # A query gate can stop before a fact reader is available. Do not
            # audit that already-final result again merely because the former
            # query worksheet is still present.
            if run.result is not None:return
            if run.review_kind=='dag_source':
                from . import dag_reading_review as dag_audit
                self.event(run,'REVIEWING_READING','正在核对变量、因果关系和资料来源')
                request,fields,sources=dag_audit.request(run)
                number=1+sum(k.startswith('dag_reading_audit_') and k.endswith('_request') for k in run.artifacts)
                stage=f'dag_reading_audit_{number}'
                raw=self._call_audit(run,request,stage)
                try:
                    answer=audit.check_focused(raw,fields,sources)
                except ValueError as exc:
                    if str(exc)=='READING_AUDIT_PERMISSION_INVALID' or run.automatic_audit_repairs>=1:raise
                    run.automatic_audit_repairs+=1
                    repair=deepcopy(request);body=json.loads(repair['user_prompt'])
                    body['audit_contract_feedback']=dict(code=str(exc),previous_response=raw,
                        instruction='原候选和原文未变。请按原output_schema完整核对，每项恰好一次，不得因格式修复默认通过或批准科学条件。')
                    repair['user_prompt']=json.dumps(body,ensure_ascii=False)
                    answer=audit.check_focused(self._call_audit(run,repair,stage+'_format_retry'),fields,sources)
                self.save(run,stage+'_validated',answer)
                if answer['verdict']=='PASS':
                    run.dag_fact_audit=dag_audit.accept(run,answer)
                    self.save(run,'dag_fact_audit',run.dag_fact_audit)
                    self._plan(run);continue
                if answer['verdict']=='READING_ERROR':
                    if dag_audit.reread(self,run,answer):continue
                    run.error=dict(code='READING_REVIEW_DISAGREEMENT',message='DAG facts do not match their sources after bounded recovery.')
                    self.event(run,'STOPPED','系统对因果关系或材料的解释仍有分歧，尚未进入识别；无需为模型错误补条件。');return
                run.user_question=dict(kind='NEEDS_CLARIFICATION',items=answer['issues'],message='请补充以下信息。')
                self.event(run,'REVIEW_REQUIRED','请说明原材料中尚未确定的内容');return
            if run.review_kind=='information':
                from . import information_review
                self.event(run,'REVIEWING_READING','正在核对均值表与配套说明，保留全部引用')
                request=information_review.request(run)
                number=1+sum(k.startswith('information_audit_') and k.endswith('_request') for k in run.artifacts)
                stage=f'information_audit_{number}'
                answer=information_review.check(run,self._call_audit(run,request,stage))
                self.save(run,stage+'_validated',answer)
                if answer['matches_source'] is True:
                    run.stage='REVIEW_REQUIRED'
                    self._review(run,dict(kind='information',records={'information':answer['record']}))
                    continue
                if answer['matches_source'] is False:
                    run.error=dict(code='READING_INFORMATION_REVIEW_DISAGREEMENT',message=answer['comparison'])
                    self.event(run,'STOPPED','均值表与说明尚未通过来源核对，未进入识别。')
                else:
                    run.user_question=dict(kind='NEEDS_CLARIFICATION',items=[answer['question']],message='请补充以下信息。')
                    self.event(run,'REVIEW_REQUIRED','均值表与配套说明有不明确的地方，请补充说明')
                return
            if run.review_kind=='notes':
                self.event(run,'REVIEWING_READING','正在检查尚未明确的说明')
                request,fields,sources=note_review.request(run)
                number=1+sum(k.startswith('note_audit_') and k.endswith('_request') for k in run.artifacts)
                stage=f'note_audit_{number}'
                answer=note_review.check(run,self._call_audit(run,request,stage),fields,sources)
                self.save(run,stage+'_validated',answer)
                if answer['reading_errors']:
                    # Keep a located model error distinct from missing material.
                    # Existing bounded re-reading retains the old candidate and
                    # invalidates previous source/science approvals.
                    preview=recovery.prepare(run,allow_busy=True)
                    if run.automatic_rechecks<1 and preview['available']:
                        entry,feedback=recovery.request(run,preview['binding_sha256'],allow_busy=True)
                        run.automatic_rechecks+=1;self._recheck(run,entry,feedback);continue
                    run.error=dict(code='READING_NOTE_RECHECK_REQUIRED',message='The note audit located a reading error; no scientific conditions were approved.')
                    self.event(run,'STOPPED','系统对材料的解释仍有分歧，尚未开始识别；不必补充条件来修复模型错误。')
                    return
                run.stage='REVIEW_REQUIRED'
                self._review(run,dict(kind='notes',records=answer['records']))
                if answer['questions']:
                    run.user_question=dict(kind='NEEDS_CLARIFICATION',items=answer['questions'],message='原材料还不能确定以下内容。')
                    self.event(run,'REVIEW_REQUIRED','请补充以下信息')
                    return
                continue
            if run.review_kind not in audit.STAGES:return
            # Audit first: residual notes can be genuine restrictions. Spend
            # the bounded reread only on a located model-reading error.
            self.event(run,'REVIEWING_READING','正在核对读取结果与原文')
            request,fields,sources=audit.request(run)
            number=1+sum(k.startswith('reading_audit_') and k.endswith('_request') for k in run.artifacts)
            stage=f'reading_audit_{number}'
            raw=self._call_audit(run,request,stage)
            try:
                answer=audit.check(raw,fields,sources,require_current=True)
            except ValueError as exc:
                # At most one explicit audit-contract retry per run. This does
                # not retry transport, repair the reading, or overturn a valid
                # adverse audit. Preserve both replies and all current evidence.
                code=str(exc)
                self.save(run,stage+'_validation',dict(valid=False,code=code,details=getattr(exc,'details',{})))
                if code=='READING_AUDIT_PERMISSION_INVALID' or run.automatic_audit_repairs>=1:raise
                run.automatic_audit_repairs+=1
                repair=deepcopy(request);body=json.loads(repair['user_prompt'])
                body['audit_contract_feedback']=dict(code=code,details=getattr(exc,'details',{}),previous_response=raw,
                    instruction='上次复核输出不符合本次合同。原材料和待审候选未变；请重新核对并按output_schema提交完整复核。不能因格式修复默认通过，不得改业务候选或批准科学条件。')
                repair['user_prompt']=json.dumps(body,ensure_ascii=False)
                self.event(run,'REVIEWING_READING','后台复核的回复格式有误，正在进行一次格式复查；业务材料保持不变')
                stage=f'reading_audit_{number+1}'
                answer=audit.check(self._call_audit(run,repair,stage),fields,sources,require_current=True)
            self.save(run,stage+'_validated',answer)
            prior=run.artifacts.get('target_reread_prior',{})
            changed_query=('intake_candidate' in prior and prior['intake_candidate']!=(plain(run.intake) or {}).get('candidate'))
            focus_scope = ('query_reread' if changed_query else 'query') if run.review_kind == 'query' else 'source'
            if answer['verdict']=='READING_ERROR' and focus_scope not in run.automatic_focused_stages:
                focused,disputed=audit.focused_request(request,fields,answer)
                # A0 has at most one reread; its replacement is a new candidate.
                # Each query version gets one source-bound follow-up, including
                # failures. Repeating an audit of the same version cannot reset it.
                run.automatic_focused_stages.add(focus_scope)
                focus_stage = 'focused_audit' if not run.artifacts.get('focused_audit_completed') else 'focused_audit_'+focus_scope
                self.save(run,focus_stage+'_completed',dict(started=True,scope=focus_scope,fields=list(disputed)))
                self.event(run,'REVIEWING_READING','正在检查有冲突的读取结果')
                followup=audit.check_focused(self._call_audit(run,focused,focus_stage),disputed,sources)
                self.save(run,focus_stage+'_validated',followup)
                answer=audit.reconcile(answer,followup,disputed)
                self.save(run,'reconciled_reading_audit',answer)
            if answer['verdict']=='PASS':
                run.stage='REVIEW_REQUIRED'
                self._review(run,audit.records(run,answer));continue
            if answer['verdict']=='READING_ERROR' and run.review_kind=='query':
                if self._reread_business(run,dict(source_located_issues=answer['issues'])):
                    continue
            # Reuse validated field/source locations, not a generic note sweep.
            # Feedback remains a request to reread, never a replacement answer.
            if answer['verdict']=='READING_ERROR' and run.automatic_rechecks<1:
                preview=recovery.prepare(run,allow_busy=True,audit_findings=answer['issues'])
                if preview['available']:
                    entry,feedback=recovery.request(run,preview['binding_sha256'],allow_busy=True,
                                                    audit_findings=answer['issues'])
                else:entry=None
                if entry:
                    run.automatic_rechecks+=1;self._recheck(run,entry,feedback);continue
            if answer['verdict']=='READING_ERROR':
                run.user_question=None
                run.error=dict(code='READING_REVIEW_DISAGREEMENT',message='Independent model review could not confirm the reading; see saved audit issues.')
                self.event(run,'STOPPED','系统对材料的解释仍有分歧，尚未开始识别；可重试复核，不必增加研究条件。')
                return
            questions=deepcopy(answer['issues'])
            for issue in questions:
                field=fields[issue['field']]
                path=field.get('change',{}).get('field_path',issue['field'])
                if 'additional_restrictions' in path:
                    issue['display_question']='下面这些说明是在描述已有资料与待确认事项，还是希望为本次计算另外增加条件？请说明你的原意。'
                issue['source_texts']=[sources[sid].get('text',sources[sid].get('quote',''))
                                      if isinstance(sources[sid],dict) else sources[sid] for sid in issue['source_ids']]
            run.user_question=dict(kind=answer['verdict'],items=questions,
                message='系统对下面的说明仍有理解分歧，请说明原意；不需要修改数据或为了通过而增加假设。' if answer['verdict']=='READING_ERROR' else '原材料还不能确定以下内容。')
            self.event(run,'REVIEW_REQUIRED','请补充以下信息')
            return
        raise ValueError('AUTOMATIC_REVIEW_STEP_LIMIT')

    def _review(self,run,payload):
        if run.stage not in ('REVIEW_REQUIRED','STOPPED') or not run.review_kind:raise ValueError('NO_CURRENT_REVIEW')
        if payload.get('kind')!=run.review_kind:raise ValueError('STALE_REVIEW_STAGE')
        records=payload['records']
        if set(records)!=set(run.review_templates):raise ValueError('EXACT_REVIEW_SET_REQUIRED')
        for name,sheet in run.review_sheets.items():
            r=records[name]
            if capabilities.identity(r)!=capabilities.identity(sheet) or r.get('authority')!=run.authority:
                raise ValueError('STALE_OR_WRONG_AUTHORITY_REVIEW')
        kind=run.review_kind;self.save(run,kind+'_review',records)
        if kind=='saved_target':
            from .library_reading import review_target
            review_target(self,run,records['query'])
        elif kind=='query':
            result=business_field_review.submit(run.intake,run.query_id,records['query'],authority=run.authority)
            if result['state']!='READY_TO_READ':
                self.save(run,'query_gate_result',result)
                if (run.automatic_review and result.get('reason_code')=='COMBINED_OR_AMBIGUOUS_GRAPH_REPRESENTATIONS'
                        and 'graph_conflict_check' not in run.artifacts):
                    from . import automatic_review as audit
                    request,fields,sources=audit.graph_conflict_request(run)
                    # Consume the bounded check before calling, including failures.
                    self.save(run,'graph_conflict_check',dict(started=True,fields=list(fields),scientific_approval=False))
                    self.event(run,'REVIEWING_READING','两类关系说明可能混在一起，后台正在对照原文核对。')
                    checked=audit.check_focused(self._call_audit(run,request,'graph_conflict_audit'),fields,sources)
                    self.save(run,'graph_conflict_validated',checked)
                    if checked['verdict']=='READING_ERROR':
                        if self._reread_business(run,dict(source_located_issues=checked['issues'])):return
                    elif checked['verdict']=='NEEDS_CLARIFICATION':
                        run.user_question=dict(kind='NEEDS_CLARIFICATION',items=checked['issues'],message='请说明材料中的关系。')
                        run.result=dict(state='NEEDS_INPUT',reason_code='SOURCE_CONFIRMED_GRAPH_AMBIGUITY',
                            clarification_questions=[i['question'] for i in checked['issues']],backend_called=False,
                            independent_replay=False,mathematical_claim=None)
                        self.event(run,'REVIEW_REQUIRED','请补充关系说明');return
                run.result=result;self.save(run,'query_gate_result',result)
                self.event(run,'STOPPED','当前读取尚不能进入后续方法；停止原因已保留，不重复调用后台复核。');return
            run.result=None
            run.query_review=result['query_review']
            run.entry=project.prepare_reader(run.intake,run.query_id,query_review=run.query_review)
            self.event(run,'READING_FACTS','正在读取研究安排、数据来源和假设')
            raw=self._read_facts(run,run.entry)
            conflict=local_target_conflict(run.entry,raw) if run.automatic_review else None
            if conflict:
                if not self._reread_business(run,conflict):
                    run.result=dict(state='READING_RECHECK_REQUIRED',reason_code='LOCAL_TARGET_CONFLICT_AFTER_REREAD',
                                    independent_replay=False,mathematical_claim=None)
                    self.save(run,'target_reread_unresolved',conflict)
                    self.event(run,'STOPPED','重新读取后，两阶段对比较目标仍有分歧，尚未进入识别。')
                return
            run.submission=dict(query_review=run.query_review,candidate=raw,request_sha256=run.entry['request_sha256'])
            self._plan(run)
        elif kind in ('source','notes','information','changes'):
            key={'source':'source_review','notes':'note_review','information':'information_evidence_review','changes':'change_review'}[kind]
            if kind=='notes' and set(records)<= {'first','second'}:
                run.submission[key]={side:records.get(side) for side in ('first','second')}
            else:run.submission[key]=records[kind]
            self._plan(run)
        elif kind=='science':
            confirmed_summary=summarize(run)
            from . import dag_reading_review as dag_audit
            if dag_audit.connected(run):
                if not dag_audit.valid(run):raise ValueError('CURRENT_DAG_SOURCE_REVIEW_REQUIRED')
                # Only user scientific records arrive here; source/plan records
                # come from the bound, successful independent background audit.
                records={**deepcopy(run.dag_fact_audit['records']),**records}
            run.reviews['plan_review']=records['plan']
            run.reviews['native_reviews']={row['method']:{name:records[row['method']+'.'+name]
                for name in ('reading_review','science_review')} for row in run.plan['methods']
                if 'reading_worksheet' in row and 'science_worksheet' in row}
            self.event(run,'IDENTIFYING','正在计算并验证识别结果')
            execution_reviews={**run.reviews,'native_reviews':dispatch.native_reviews_from_json(run.plan,run.reviews['native_reviews'])}
            run.result=project.execute(run.intake,run.query_id,**run.submission,**execution_reviews,research_protocol_selected=True)
            # Presentation metadata only; native claims and certificates stay intact.
            if run.result.get('independent_replay') is True and confirmed_summary.get('contract')==capabilities.CONTRACT:
                run.result['web_review_summary']=confirmed_summary
            self.save(run,'identification',run.result);run.review_kind=None;run.review_sheets={};run.review_templates={}
            self._register_classic_result(run)
            self.event(run,'RESULT','识别计算已结束，请查看结果。')
        else:raise ValueError('IDENTIFICATION_REVIEW_ONLY')

    def _register_classic_result(self,run):
        from . import classic_delivery
        from cfm_id.classic_query_exchange import UnsupportedRegistration
        from cfm_id_llm.compact_study import digest
        try:
            packet=classic_delivery.prepare(run)
            if packet is None:return
            self.save(run,'identification_handoff',packet)
            receipt=self.estimate_inbox.receive(run.id,packet)
            handoff=packet['estimate_handoff']
            if (receipt.get('binding')!=packet['binding'] or receipt.get('run_id')!=run.id
                    or receipt.get('query_id')!=run.query_id or receipt.get('release_scope')!=run.authority
                    or receipt.get('query_sha256')!=digest(handoff) or receipt.get('mode')!=handoff['mode']
                    or receipt.get('query_count')!=len(handoff['queries'])
                    or receipt.get('state') not in ('RECEIVED','QUEUED')):
                raise ValueError('CLASSIC_ESTIMATE_RECEIPT_MISMATCH')
        except UnsupportedRegistration:
            return
        except Exception as exc:
            self.estimate_inbox.revoke(run.id)
            receipt=dict(run_id=run.id,state='DELIVERY_FAILED',error=type(exc).__name__,estimator_executed=False)
        self.save(run,'estimate_intake_receipt',receipt)
        run.result['estimate_registration']=deepcopy(receipt)
        self.save(run,'identification',run.result)

    def _classic_uploaded_comparison(self,run):
        if (not run.network or run.reading_mode!='classic' or len(run.queries)!=1
                or (run.entry or {}).get('reader_id')!='NETWORK_RANDOMIZED_EFFECT_FACTS'):
            return False
        entry=run.entry
        submission=run.submission or {}
        if (entry.get('query_id')!=run.query_id or not entry.get('query_review')
                or submission.get('query_review')!=entry['query_review']
                or submission.get('request_sha256')!=entry['request_sha256']):
            return False
        from cfm_id.direct_verification import verify
        report=verify(run.case,{},network=run.network)
        proof=report.get('proof') or {}
        if proof.get('binding_source')!='uploaded-materials/1':return False
        a,b=(e.split(',') for e in proof['ordered_events'])
        kind=('SPILLOVER_EFFECT' if a[0]==b[0] else 'DIRECT_EFFECT' if a[1]==b[1] else 'LOCAL_TOTAL_EFFECT')
        if kind!=run.entry['selected_query']['target']['kind']:return False
        self.save(run,'classic_file_binding',dict(query_id=run.query_id,source=proof['binding_source'],
            network_reference=proof['network_reference'],request_sha256=run.entry['request_sha256']))
        run.review_kind=None;run.review_sheets={};run.review_templates={}
        self._finish_direct_verification(run,report)
        return True

    def _plan(self,run):
        if self._classic_uploaded_comparison(run):return
        run.result=None
        run.plan=project.inspect_methods(run.intake,run.query_id,**run.submission);self.save(run,'plan',run.plan)
        # A table may also cite definitions in another document. Ask for the
        # existing source-role review; never delete citations or approve roles.
        if (run.plan.get('reason_code')=='EXACT_SINGLE_SOURCE_TABLE_REQUIRED'
                and 'information_evidence_review' not in run.submission):
            from cfm_id.network_information_evidence import prepare
            try:
                sheet=prepare(run.entry,run.submission['candidate'])
            except ValueError:
                pass  # Unsupported evidence shapes keep their original stop.
            else:
                run.plan=dict(run.plan,state='REVIEW_REQUIRED',
                    reason_code='INFORMATION_SOURCE_ROLES_REQUIRED',
                    information_evidence_worksheet=sheet)
                self.save(run,'plan',run.plan)
        for key,kind in [('reading_change_worksheet','changes'),('source_review_worksheet','source')]:
            if key in run.plan:
                self._set_review(run,kind,{kind:run.plan[key]});return
        from .note_review import pending_sheets
        notes=pending_sheets(run.plan)
        if notes:
            self._set_review(run,'notes',notes);return
        if 'information_evidence_worksheet' in run.plan:
            self._set_review(run,'information',{'information':run.plan['information_evidence_worksheet']});return
        from . import dag_reading_review as dag_audit
        automatic_dag=dag_audit.connected(run)
        if automatic_dag and not dag_audit.valid(run):
            self._set_review(run,'dag_source',{'dag_source':dag_audit.worksheet(run)});return
        if 'plan_worksheet' in run.plan:
            sheets={} if automatic_dag else {'plan':run.plan['plan_worksheet']}
            for row in run.plan.get('methods',[]):
                for field,name in [('reading_worksheet','reading_review'),('science_worksheet','science_review')]:
                    if automatic_dag and field=='reading_worksheet':continue
                    if field in row:sheets[row['method']+'.'+name]=row[field]
            self._set_review(run,'science',sheets);return
        run.result=run.plan;run.review_kind=None;run.review_sheets={};run.review_templates={}
        self.event(run,'RESULT','识别未完成，原因见下方。')

    def _check_material_counts(self,run):
        from . import material_counts
        ctx=material_counts.context(run)
        if ctx is None:return False
        previous=run.artifacts.get('material_counts_validated')
        if previous and previous['binding_sha256']==ctx['binding_sha256']:
            checked=previous
        else:
            stopped=run.artifacts.get('material_counts_stop')
            if stopped and stopped['binding_sha256']==ctx['binding_sha256']:
                run.result=deepcopy(stopped['result'])
                self.event(run,'STOPPED','数量读取仍需复核；原业务材料和文件均未修改。')
                return True
            self.event(run,'REVIEWING_READING','正在核对业务文字与上传文件的记录范围')
            answer=self.call(run,material_counts.request(ctx),'material_counts')
            try:
                checked=material_counts.check(ctx,answer)
            except material_counts.CountReadingError as initial:
                self.save(run,'material_counts_initial_error',dict(binding_sha256=ctx['binding_sha256'],diagnostics=initial.diagnostics))
                # One explicit reread per unchanged input. Preserve the original
                # candidate; never edit a quote/count or bypass a failed check.
                receipt=run.artifacts.get('material_counts_recovery')
                if not receipt or receipt['binding_sha256']!=ctx['binding_sha256']:
                    receipt=dict(binding_sha256=ctx['binding_sha256'],attempts=1)
                    self.save(run,'material_counts_recovery',receipt)
                    self.event(run,'REVIEWING_READING','模型的数量引用或格式未通过检查，后台按原材料重读一次；无需修改业务人数')
                    answer=self.call(run,material_counts.recheck_request(ctx,answer,initial.diagnostics),'material_counts_recheck')
                errors=material_counts.diagnose(ctx,answer)
                if errors:
                    run.result=dict(state='READING_RECHECK_REQUIRED',reason_code='MATERIAL_COUNT_READING_INVALID',
                        scope='UPLOADED_FINITE_DATA',identification_status='NOT_EVALUATED',
                        backend_called=False,independent_replay=False,mathematical_claim=None,
                        diagnostics=errors,automatic_rereads=1,
                        processing_explanation='；'.join(d['message'] for d in errors[:3]))
                    self.save(run,'material_counts_stop',dict(binding_sha256=ctx['binding_sha256'],result=run.result))
                    self.event(run,'STOPPED','模型重读后仍未准确引用或表达数量，尚未进入识别；不需要为此修改真实人数。')
                    return True
                checked=material_counts.check(ctx,answer)
            self.save(run,'material_counts_validated',checked)
        if not checked['conflicts']:return False
        run.result=dict(state='NEEDS_INPUT',reason_code='UPLOADED_RECORD_COUNTS_CONFLICT',
            scope='UPLOADED_FINITE_DATA',identification_status='NOT_EVALUATED',
            backend_called=False,independent_replay=False,mathematical_claim=None,
            message='上传资料的记录范围需要说明；尚未判断因果目标能否识别。')
        run.user_question=dict(kind='NEEDS_CLARIFICATION',items=checked['conflicts'],
            message='文字与文件的记录范围不一致。请先说明资料对应关系；这不表示因果目标不可识别。')
        self.event(run,'REVIEW_REQUIRED','需要说明上传资料的记录范围，再继续本次分析')
        return True

    def _review_intake_stop(self,run,inspected):
        from . import intake_stop
        sheet=intake_stop.prepare(run,inspected)
        if sheet is None:return False
        self.save(run,'intake_stop_worksheet',sheet)
        feedback=intake_stop.contract_reread_feedback(sheet,inspected)
        if feedback is not None:
            self.save(run,'intake_contract_feedback',feedback)
            if not self._reread_business(run,feedback):
                run.result=dict(inspected,reason_code='TARGET_FIELD_CONTRACT_CONFLICT_AFTER_REREAD')
                self.event(run,'STOPPED','重读后，目标类别与比较方式仍不一致；尚未进入识别，无需为此补充研究条件。')
            return True
        self.event(run,'REVIEWING_READING','正在核对原文是否包含所需信息')
        answer=self.call(run,intake_stop.request(sheet),'intake_stop_audit')
        revised,checked,questions=intake_stop.apply(run,sheet,answer)
        run.intake=revised;self.save(run,'intake',run.intake)
        self.save(run,'intake_stop_validated',checked)
        if checked['state']=='BUSINESS_CLARIFICATION_REQUIRED':
            run.result=dict(checked,state='NEEDS_INPUT',reason_code='SOURCE_CONFIRMED_TARGET_GAP',
                backend_called=False,independent_replay=False)
            run.user_question=dict(kind='NEEDS_CLARIFICATION',items=questions,
                message='还需要明确下面的业务内容。已提供的安排和研究条件会保留。')
            self.event(run,'REVIEW_REQUIRED','请补充以下信息')
        elif not self._reread_business(run,dict(source_located_issues=checked['reading_stop_receipt']['queries'])):
            run.result=checked
            self.event(run,'STOPPED','读取复核仍有分歧，尚未进入识别；不必为此增加研究条件。')
        return True

    def _reread_business(self,run,feedback):
        if 'target_reread_prior' in run.artifacts:
            return False
        self.save(run,'target_reread_prior',dict(feedback=feedback,
            intake_candidate=deepcopy((plain(run.intake) or {}).get('candidate')),artifacts=deepcopy(run.artifacts)))
        run.query_id=run.query_review=run.entry=run.submission=run.plan=run.result=None
        run.review_kind=None
        run.review_sheets={};run.review_templates={};run.reviews={}
        self.event(run,'READING','后台定位到业务解释有误，按原材料重新读取并重新审核。')
        self._read_case(run,target_feedback=feedback)
        return True
