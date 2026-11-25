"""Source-bound homepage integration for two existing dedicated math entries."""
from copy import deepcopy
import json
import re
from cfm_id_bridge.scientific_binding import sha
from cfm_id_llm import joint_reading as reader
from cfm_id_llm.compact_study import digest
from . import dag_joint, finite_mean_joint
from .population_ate_entry import check_review

VERSION='joint-natural-entry/1'
LABELS={
 'graph_complete':'图中直接关系和未观测共同原因已列全',
 'recursive_scm':'采用材料所述的无环因果模型',
 'perfect_intervention':'同时设定指定变量，其他机制不变',
 'strict_positivity':'所列变量的每种联合取值都有正的总体概率',
 'no_between_unit_interference':'不同研究对象之间没有相互影响',
 'randomization':'完整抽签安排不受各对象潜在结果影响',
 'consistency':'实际结果对应实际执行的完整安排',
 'fixed_network':'使用干预前固定的关系网',
 'mean_sufficiency':'相同本人状态和同伴状态对应相同平均结果',
 'finite_mean_model_complete':'已列全均值、范围及限制，没有其他约束',
 'first_stage_exclusion':'第一阶段名额方案不直接影响结果'}
DAG_REQUIRED=('graph_complete','recursive_scm','perfect_intervention','strict_positivity')
NET_REQUIRED=('randomization','consistency','fixed_network','mean_sufficiency','finite_mean_model_complete')


def route_hints(draft):
    """Reader hints may be nested in a malformed draft; never repair its answer.

    Choosing a source reader grants no admission. That reader and its separate
    audit must recover the actual question from original materials again.
    """
    found=set();pending=[draft];count=0
    while pending and count<500:
        value=pending.pop();count+=1
        if isinstance(value,dict):
            hint=value.get('verification_route')
            if isinstance(hint,str):found.add(hint)
            pending.extend(value.values())
        elif isinstance(value,list):pending.extend(value)
    return found


def proposed(case,draft):
    """A hint only selects a source reader; it cannot approve or compile anything."""
    if route_hints(draft).intersection(('DAG_JOINT','DAG_GENERAL','NETWORK_JOINT_MEANS')):return True
    text='\n'.join(reader.sources(case).values())
    return bool(re.search(r'联合干预|同时.{0,50}(设定|干预|控制)|joint intervention|do\([^)]*,',text,re.I) or
        re.search(r'(均值|平均).{0,60}(等于|相等|不低于|不超过|不小于|不少于|之和|线性约束|等式|不等式)',text))


def base(report,case,reading=None,audit=None):
    r=deepcopy(report)
    for key in ('proof','effective_answer','conditional_answer','condition_review','review_record','clarification_questions'):
        r.pop(key,None)
    r.update(decision='WITHHELD',estimation_handoff_allowed=False,production_admission=False,
        scientific_approval=False,independent_replay=False,backend_called=False)
    r['joint_entry']=dict(version=VERSION,case_sha256=digest(case),reading=reading,audit=audit)
    return r


def stop(r,state,reason,message,questions=None):
    r['joint_entry'].update(state=state,reason_code=reason,message=message)
    # Two audited fields may point to the same ambiguity. Preserve every
    # finding in the audit, but ask the identical question only once.
    r['clarification_questions']=list(dict.fromkeys(questions or []))
    return r


def record_review_decisions(r,review):
    """Keep a bound user decision distinct from absent scientific approval."""
    check_review(r['condition_review'],review)
    r['review_record']=deepcopy(review)
    labels={x['code']:x['label'] for x in r['condition_review']['items']}
    declined=[labels[k] for k,v in review['decisions'].items() if v=='DECLINED']
    if declined:
        r['joint_entry']['completed']=True
        stop(r,'UNSUPPORTED','REVIEW_PREMISE_DECLINED',
            '本次不采用：'+'；'.join(declined)+'。此路线已停止，未生成识别结论或向估计端交接。')
        return True
    if any(v!='ADOPTED' for v in review['decisions'].values()):
        stop(r,'REVIEW_REQUIRED','PREMISES_NOT_CONFIRMED','已保存“暂不确定”的选择；本题尚未执行识别。')
        return True
    return False


def active_graph_restrictions(s):
    def describe(c):
        q=c['quantity'];pairs=lambda d:'、'.join(k+'='+v for k,v in d.items())
        return ('材料给出 '+pairs(q['intervention'])+' 时 '+pairs(q['event'])+' 的概率数值 '+c['value']+
            '；对象：'+q['population']+'；时期：'+q['period'])
    given=[dict(c,description=describe(c)) for c in s.get('given_probabilities',[])]
    return [c for c in [*s.get('constraints',[]),*s.get('mean_orders',[]),*given] if c['status']!='NOT_ADOPTED']


def prepare(case,report,call,*,reader_module=None,planner=None,gap_resolver=None,diagnose_stop=None):
    source_reader=reader_module or reader
    planner=planner or plan
    feedback=None; attempts=[];audit_repairs=[];reading_repairs=[];gap_reviews=[];semantic_repairs=[]
    for attempt in range(2):
        raw=None;semantic=None
        suffix='' if attempt==0 else '_retry1'
        try:
            raw=call(source_reader.request(case,feedback),'joint_source_read'+suffix)
            inspect_current=getattr(source_reader,'inspect_current',source_reader.inspect)
            try:s=inspect_current(case,raw)
            except (ValueError,TypeError,KeyError) as exc:
                if reading_repairs:raise
                reading_repairs.append(dict(raw=raw,error=str(exc)))
                repair_feedback=dict(format_error=str(exc)[:2000],prior_source_findings=feedback,
                    instruction='根据同一份原文重新提交完整合同。修正字段形状，不自行删条件、改目标或把重试说明当证据。')
                raw=call(source_reader.request(case,repair_feedback),'joint_source_format_retry')
                s=inspect_current(case,raw)
            request=source_reader.audit_request(case,s)
            audit_raw=call(request,'joint_source_audit'+suffix)
            try:a=source_reader.check_audit(case,s,audit_raw)
            except ValueError as exc:
                if audit_repairs:raise
                audit_repairs.append(dict(raw=audit_raw,error=str(exc)))
                body=json.loads(request['user_prompt'])
                body['format_feedback_not_evidence']=str(exc)+' 候选和原文未变，重新逐项核对，不允许默认MATCH。'
                request=dict(request,user_prompt=json.dumps(body,ensure_ascii=False))
                a=source_reader.check_audit(case,s,call(request,'joint_audit_format_retry'))
            original_audit=deepcopy(a)
            if not any(x['verdict']=='READING_ERROR' for x in a['findings']) and hasattr(source_reader,'semantic_request'):
                semantic_raw=call(source_reader.semantic_request(case,s),'joint_condition_semantics'+suffix)
                try:semantic,findings=source_reader.check_semantics(case,s,semantic_raw)
                except ValueError as exc:
                    if semantic_repairs or not hasattr(source_reader,'semantic_reconcile_request'):raise
                    item=dict(reading_binding=source_reader.binding(case,s),initial_inventory=semantic_raw,contract_error=str(exc))
                    semantic_repairs.append(item)
                    try:
                        semantic,findings=source_reader.check_semantics(case,s,call(
                            source_reader.semantic_reconcile_request(case,s,semantic_raw,[],str(exc)),'joint_condition_reconcile'))
                    except (ValueError,TypeError,KeyError) as recheck_error:
                        item['recheck_error']=str(recheck_error);raise
                    item.update(rechecked_inventory=semantic,rechecked_findings=findings)
                if (any(f['verdict']!='MATCH' for f in findings) and not semantic_repairs
                        and all(f['verdict']=='MATCH' for f in a['findings'])
                        and hasattr(source_reader,'semantic_reconcile_request')):
                    item=dict(reading_binding=source_reader.binding(case,s),initial_inventory=semantic,initial_findings=findings)
                    semantic_repairs.append(item)
                    try:
                        semantic,findings=source_reader.check_semantics(case,s,call(
                            source_reader.semantic_reconcile_request(case,s,semantic,findings),'joint_condition_reconcile'))
                    except (ValueError,TypeError,KeyError) as recheck_error:
                        item['recheck_error']=str(recheck_error);raise
                    item.update(rechecked_inventory=semantic,rechecked_findings=findings)
                # Supplemental evidence may add an objection, never overwrite
                # an adverse finding with approval or directly repair a value.
                objections={x['field']:x for x in findings if x['verdict']!='MATCH'}
                a['findings']=[objections.get(x['field'],x) for x in a['findings']]
                a=source_reader.check_audit(case,s,a)
            errors=[x for x in a['findings'] if x['verdict']=='READING_ERROR']
            questions=[x['question'] for x in a['findings'] if x['verdict']=='NEEDS_CLARIFICATION']
            attempts.append(dict(reading=s,audit=a))
            if semantic is not None:
                attempts[-1].update(original_audit=original_audit,condition_evidence=semantic)
            if errors:feedback=errors;continue
            # A source-audited unsupported restriction is already decisive for
            # stopping. Never approve a disputed field or run a solver here.
            # Keep unrelated questions in the audit rather than asking the user
            # to reconfirm conditions that cannot make this method applicable.
            if diagnose_stop is not None:
                stopped=diagnose_stop(case,base(report,case,s,a))
                if stopped is not None:
                    stopped['joint_entry'].update(attempts=attempts,audit_repairs=audit_repairs,
                        reading_repairs=reading_repairs,gap_reviews=gap_reviews,semantic_repairs=semantic_repairs)
                    return stopped
            if questions:
                from cfm_id_llm import source_gap_review
                proposed={f['field']:dict(candidate=s,reason_code='AUDITOR_REQUESTED_CLARIFICATION',
                    audit_finding=f,proposed_questions=[f['question']]) for f in a['findings'] if f['verdict']=='NEEDS_CLARIFICATION'}
                gap=source_gap_review.check(case,s,proposed,call(source_gap_review.request(case,s,proposed,
                    reading_contract=json.loads(request['user_prompt']).get('reading_contract')),'joint_audit_question_review'+suffix))
                gap_reviews.append(gap)
                if any(f['cause']=='READING_OMISSION' for f in gap['findings']):
                    feedback=dict(cause='READING_OR_AUDIT_ERROR',findings=gap['findings'],
                        instruction='原文已明确该内容，重新完整读取并独立审核；不能将某次复核判断当证据，不向用户重复索要已提供条件。')
                    continue
                questions=list(dict.fromkeys(f['question'] for f in gap['findings'] if f['question']))
                if not questions:
                    r=stop(base(report,case,s,a),'UNSUPPORTED','AUDITED_INFORMATION_NOT_SUPPORTED',
                        '已提供材料不符合当前入口的信息合同；保留原文，不重复索要已有内容。')
                    r['joint_entry'].update(attempts=attempts,gap_reviews=gap_reviews,semantic_repairs=semantic_repairs,
                        audit_repairs=audit_repairs,reading_repairs=reading_repairs)
                    return r
            if s['family']['value']=='OTHER' and not questions:return None
            r=base(report,case,s,a)
            if semantic is not None:r['joint_entry']['condition_evidence']=semantic
            if questions:r=stop(r,'NEEDS_INPUT','SOURCE_AMBIGUITY','请说明材料中这几处含糊的地方。',questions)
            else:
                r=planner(case,r)
                known_information_stop(r)
                gaps=(gap_resolver or proposed_gaps)(r)
                if gaps:
                    from cfm_id_llm import source_gap_review
                    gap=source_gap_review.check(case,s,gaps,call(
                        source_gap_review.request(case,s,gaps,reading_contract=json.loads(request['user_prompt']).get('reading_contract')),'joint_gap_review'+suffix))
                    gap_reviews.append(gap)
                    omissions=[x for x in gap['findings'] if x['cause']=='READING_OMISSION']
                    if omissions:
                        feedback=dict(cause='READING_OMISSION',findings=omissions,
                            instruction='只依据原文修复遗漏；重读完整候选后仍须重新独立复核，不能把本记录当审批。')
                        continue
                    r['clarification_questions']=list(dict.fromkeys(x['question'] for x in gap['findings'] if x['question']))
                    r['joint_entry']['input_diagnostics']=gap['findings']
                    if r['clarification_questions']:
                        stop(r,'NEEDS_INPUT','SOURCE_AMBIGUITY',
                            '请说明以下尚未明确的内容；已提供的材料会继续保留。',r['clarification_questions'])
                    if not r['clarification_questions'] and all(x['cause']=='INFORMATION_NOT_SUPPORTED' for x in gap['findings']):
                        reasons=list(dict.fromkeys(x['reason'].strip() for x in gap['findings'] if x['reason'].strip()))
                        stop(r,'UNSUPPORTED','INFORMATION_CONTRACT_NOT_CONNECTED',
                            '当前入口不能按这份资料核验。'+'；'.join(reasons[:2])+
                            '这是当前入口的资料要求，不是该因果问题不可识别的证明；不需要重复填写已经说明的内容。')
            r['joint_entry']['attempts']=attempts
            r['joint_entry']['audit_repairs']=audit_repairs
            r['joint_entry']['reading_repairs']=reading_repairs
            r['joint_entry']['gap_reviews']=gap_reviews
            r['joint_entry']['semantic_repairs']=semantic_repairs
            return r
        except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
            feedback=str(exc)[:2000];attempts.append(dict(error=feedback,raw_reading=raw))
    r=stop(base(report,case),'READING_RECHECK_REQUIRED','SOURCE_AUDIT_FAILED',
        '后台读取仍有分歧，尚未执行识别；不需要为模型错误补写研究条件。')
    r['joint_entry']['attempts']=attempts
    r['joint_entry']['audit_repairs']=audit_repairs
    r['joint_entry']['reading_repairs']=reading_repairs
    r['joint_entry']['gap_reviews']=gap_reviews
    r['joint_entry']['semantic_repairs']=semantic_repairs
    last=attempts[-1] if attempts else {}
    mismatches=[x for x in last.get('audit',{}).get('findings',[]) if x['verdict']=='READING_ERROR']
    r['joint_entry']['failure_details']=(
        [dict(kind='MODEL_SOURCE_MISMATCH',field=x['field'],reason=x['reason']) for x in mismatches] or
        ([dict(kind='MODEL_OUTPUT_CONTRACT',reason=last['error'])] if last.get('error') else []))
    if gap_reviews:
        r['joint_entry']['input_diagnostics']=gap_reviews[-1]['findings']
    return r


def known_information_stop(report):
    """A reviewed, explicit sample is a contract limitation, not missing prose."""
    e=report['joint_entry'];s=e.get('reading') or {}
    key={'POPULATION_LAW_REQUIRED':'dag_information',
         'EXACT_MEAN_INFORMATION_REQUIRED':'mean_information',
         'NETWORK_INFORMATION_REQUIRED':'information'}.get(e.get('reason_code'))
    claim=s.get(key) if key else None
    value=(claim or {}).get('value') or {}
    if value.get('kind')!='FINITE_SAMPLE' and value.get('availability')!='FINITE_SAMPLE':return
    e['input_diagnostics']=[dict(field=key,cause='INFORMATION_NOT_SUPPORTED',
        evidence=claim['evidence'],reason='原文及来源复核已确认只有有限样本；不是用户漏写，也不能转换成已知总体信息。',question=None)]
    stop(report,'UNSUPPORTED','FINITE_SAMPLE_CONTRACT_NOT_CONNECTED',
        '已读到你提供的是有限样本。当前这条入口尚不能用该资料规格完成核验；不需要重复说明它是不是样本。这不表示该因果目标在数学上不可识别。')


def proposed_gaps(report):
    """Exact execution gaps; the source check decides whether to ask or reread."""
    e=report['joint_entry'];s=e['reading'];reason=e.get('reason_code')
    if not report.get('clarification_questions') or reason=='UNDECIDED_RESTRICTION':return {}
    fields={
        'POPULATION_LAW_REQUIRED':['dag_information'],
        'JOINT_OBSERVATIONS_REQUIRED':['dag_information'],
        'TARGET_DATA_SCOPE_REQUIRED':['dag_information'],
        'EXACT_MEAN_INFORMATION_REQUIRED':['mean_information'],
        'BOUND_SCOPE_REQUIRED':['bounds'],
        'TARGET_PERIOD_REQUIRED':['network_target'],
        'COMPLETE_UNDIRECTED_NETWORK_REQUIRED':['network'],
        'SCIENTIFIC_PREMISES_NOT_DECLARED':['conditions'],
        'MISSING_RESEARCH_FIELDS':[k for k in ('dag_target','graph','dag_information')
            if s['family']['value']=='DAG_JOINT' and not s.get(k)] +
            [k for k in ('network','exposure','design','network_target','mean_information','bounds')
             if s['family']['value']=='NETWORK_JOINT_MEANS' and (not s.get(k) or s[k].get('value') is None)]}
    return {k:dict(candidate=s.get(k),reason_code=reason,
        proposed_questions=report['clarification_questions']) for k in fields.get(reason,[])}


def plan(case,r):
    record=r['joint_entry'];s=record['reading'];family=s['family']['value']
    if family=='DAG_JOINT':
        from .given_probability_source import summarize
        supplied=summarize(case,s,record['audit'])
        if supplied:record['given_probability_source']=supplied
    if family not in ('DAG_JOINT','NETWORK_JOINT_MEANS'):
        return stop(r,'NEEDS_INPUT','TARGET_FAMILY_UNKNOWN','请说明要一起设定哪些变量，或要比较哪两份完整使用名单。',
            ['这次要回答的一个问题是什么？请说明要设定哪些变量，或比较哪些完整安排。'])
    record['operation']='DAG_JOINT_ID' if family=='DAG_JOINT' else 'FINITE_MEAN_JOINT'
    # Declared unsupported restrictions cannot be repaired by asking for more
    # graph premises. Preserve all of them and stop before unrelated questions.
    if family=='DAG_JOINT':
        active=active_graph_restrictions(s)
        extra=[c for c in s.get('remaining',[]) if c['status'] in ('ADOPTED','CONTRADICTED')]
        if active and all(c['status'] in ('ADOPTED','CONTRADICTED') for c in active):
            record['unhandled_declarations']=deepcopy(active+extra)
            return stop(r,'UNSUPPORTED','DAG_EXTRA_LINEAR_CONSTRAINT',
                '材料还给出了以下额外信息：'+'；'.join(c.get('description',c.get('statement','')) for c in active+extra)+
                '。当前图方法尚未联合核验这些信息，因此没有给出本题的可识别或不可识别结论。')
    keys=('dag_target','graph','dag_information') if family=='DAG_JOINT' else (
        'network','exposure','design','network_target','mean_information','bounds')
    if any(s[k] is None or s[k]['value'] is None for k in keys):
        labels={'dag_target':'这次一起设定哪些变量、关注哪个结果？','graph':'请提供变量之间的因果关系及是否存在未观测共同原因。',
            'dag_information':'已有资料包括哪些变量，是总体分布还是有限记录？','network':'请提供本次对象名单与它们之间的关系。',
            'exposure':'你怎样区分一个对象的同伴使用情况？','design':'实际试点是怎样决定谁使用的？',
            'network_target':'这次要评价哪份完整使用安排，哪些对象、什么时期的什么结果？',
            'mean_information':'已有平均数来自样本还是总体，分别对应哪些使用情况？','bounds':'对结果或平均结果，材料给出了什么范围？'}
        return stop(r,'NEEDS_INPUT','MISSING_RESEARCH_FIELDS','材料中尚缺明确的研究信息。',
            [labels[k] for k in keys if s[k] is None or s[k]['value'] is None])
    required=list(DAG_REQUIRED if family=='DAG_JOINT' else NET_REQUIRED)
    if family=='DAG_JOINT' and len(s['dag_target']['value']['treatments'])==1:required.append('no_between_unit_interference')
    if family=='NETWORK_JOINT_MEANS' and s['design']['value']['kind']=='two_stage_quota_mixture_binary_v2_7':required.append('first_stage_exclusion')
    conditions={x['code']:x for x in s['conditions']}
    if not set(required)<=conditions.keys():raise ValueError('COMPLETE_JOINT_CONDITION_INVENTORY_REQUIRED')
    # Shared wire slots can explicitly preserve absence of a premise belonging
    # to another model. An uncited UNKNOWN is not an extra scientific claim.
    # Never discard a declared, declined, pending or contradicted condition.
    unused=[c for c in s['conditions'] if c['code'] not in required and c['status']=='UNKNOWN' and not c['evidence']]
    record['unneeded_unknown_slots']=[c['code'] for c in unused]
    extra=[c for c in s['conditions'] if c['code'] not in required and c not in unused]+s['remaining']
    restrictions=[*s['constraints'],*s.get('mean_orders',[])]
    if any(c['status'] in ('UNDECIDED','UNKNOWN') for c in [*extra,*restrictions]):
        pending=[c for c in [*extra,*restrictions] if c['status'] in ('UNDECIDED','UNKNOWN')]
        return stop(r,'NEEDS_INPUT','UNDECIDED_RESTRICTION','有条件尚未决定，暂时不能将它忽略。',
            [('下面这项条件本次采用、不采用，还是尚未确定？ ' if c['status']=='UNDECIDED' or c in restrictions else
              '请补充这处说明；不清楚也可以直接说明：')+c.get('statement',c.get('description','')) for c in pending])
    if any(c['status'] in ('ADOPTED','CONTRADICTED') for c in extra) or any(c['status']=='CONTRADICTED' for c in restrictions):
        unhandled=[c for c in extra if c['status'] in ('ADOPTED','CONTRADICTED')]+[c for c in restrictions if c['status']=='CONTRADICTED']
        record['unhandled_declarations']=deepcopy(unhandled)
        return stop(r,'UNSUPPORTED','UNEXPRESSED_ADDITIONAL_RESTRICTION',
            '材料还包含：'+'；'.join(c.get('statement',c.get('description','')) for c in unhandled)+
            '。当前方法尚未连同这些信息一起核验，未忽略它们继续计算；这不是已证明不可识别。')
    rejected=[c for c in required if conditions[c]['status'] in ('NOT_ADOPTED','CONTRADICTED')]
    if rejected:
        return stop(r,'UNSUPPORTED','REQUIRED_PREMISE_NOT_ADOPTED',
            '原文不采用或否定了本方法需要的前提：'+'；'.join(LABELS[c] for c in rejected)+'。已保留这个决定，没有替换假设。')
    missing=[c for c in required if conditions[c]['status']!='ADOPTED']
    if missing:
        return stop(r,'NEEDS_INPUT','SCIENTIFIC_PREMISES_NOT_DECLARED','请明确本研究是否采用以下前提；不采用或不确定都可以说明。',
            [LABELS[c]+'：这是否是本研究采用的前提？' for c in missing])
    # Exact source declarations above authorize preparation only, not execution.
    if family=='DAG_JOINT':
        active=active_graph_restrictions(s)
        if active:
            record['unhandled_declarations']=deepcopy(active)
            return stop(r,'UNSUPPORTED','DAG_EXTRA_LINEAR_CONSTRAINT',
                '材料还给出了以下额外信息：'+'；'.join(c.get('description','') for c in active)+
                '。当前图方法尚未联合核验这些信息，因此没有给出本题的可识别或不可识别结论。')
        t=s['dag_target']['value'];g=s['graph']['value'];info=s['dag_information']['value']
        if t['query_kind']!='INTERVENTIONAL_DISTRIBUTION' or t['conditioned_on']:
            return stop(r,'UNSUPPORTED','JOINT_TARGET_FUNCTIONAL_NOT_CONNECTED',
                '当前入口核验联合干预后的分布；原问的条件筛选、均值或方案差值尚未接入，未把它改成另一个问题。')
        if not t['treatments'] or (len(t['treatments'])>1 and t['joint'] is not True):
            return stop(r,'UNSUPPORTED','NOT_ONE_JOINT_INTERVENTION','这不是一个同时设置多个变量的干预问题，不能将多个问题合并计算。')
        if g['finite_discrete'] is not True:return stop(r,'UNSUPPORTED','FINITE_DISCRETE_REQUIRED','当前联合干预入口要求有限离散变量。')
        constants=[n for n,v in g.get('variable_definitions',{}).items() if len(v['values'])==1]
        if constants:
            return stop(r,'UNSUPPORTED','DECLARED_CONSTANT_VARIABLE_NOT_CONNECTED',
                '材料把以下变量限定为唯一取值：'+'、'.join(constants)+'。当前图入口尚未按恒定变量化简，未忽略该定义继续计算。')
        if info['matches_target'] is not True:
            return stop(r,'NEEDS_INPUT','TARGET_DATA_SCOPE_REQUIRED','资料与本次问题的人群、结果、时期或背景尚未对齐。',
                ['这些记录对应本次要研究的人群、时期和结果吗？若不同，请说明区别。'])
        # The legacy reader represents exactly one treatment, one outcome and
        # an exact population law. Other supported set/sample inputs belong to
        # the existing joint contract, including singleton intervention sets.
        if len(t['treatments'])==1 and len(t['outcome'])==1 and info['kind']=='FULL_JOINT_POPULATION_LAW':
            from .dag_single_source_entry import plan_validated
            return plan_validated(case,r)
        sample = info['kind']=='FINITE_SAMPLE'
        if sample and info.get('jointly_observed') is not True:
            if info.get('jointly_observed') is False:
                return stop(r,'UNSUPPORTED','JOINT_OBSERVATIONS_NOT_AVAILABLE',
                    '当前资料没有共同记录全部图变量，不能把分开的记录或边际表当成联合分布；尚未交付本题公式。')
            return stop(r,'NEEDS_INPUT','JOINT_OBSERVATIONS_REQUIRED','还需核对这些变量是否一起记录。',
                ['图中的这些变量是否在同一批对象的同一份记录中共同测量？还是只有分开的汇总表？'])
        if info['kind'] not in ('FULL_JOINT_POPULATION_LAW','FINITE_SAMPLE'):
            return stop(r,'NEEDS_INPUT','POPULATION_LAW_REQUIRED','样本或边际表不能当作完整的总体联合分布。',
                ['现有资料是否提供本题所有观测变量的总体联合分布，还是只有样本或若干汇总表？'])
        if sample and set(info['variables'])!=set(g['nodes']):
            return stop(r,'UNSUPPORTED','OBSERVED_VARIABLE_COVERAGE_NOT_CONNECTED',
                '样本共同记录的变量与图中变量不一致，当前入口不能直接交付该图的公式；没有删除缺失变量或改画因果图。')
        problem=dict(version='dag-joint-id-2' if sample else 'dag-joint-id-1',model='RECURSIVE_SEMI_MARKOVIAN_DISCRETE',
            nodes=g['nodes'],directed=g['directed'],bidirected=g['bidirected'],treatments=t['treatments'],outcome=t['outcome'],
            context=t['context']+'；时期：'+t['period'],graph_status='RESEARCHER_CONFIRMED',graph_source='source-audited declaration; requires review',
            materials_sha256=digest(case),information=info['kind'],information_variables=info['variables'],
            strictly_positive_joint=True,unresolved=[],additional_restrictions=[])
        if sample:
            problem.update(joint_observations=True,sample_size=info.get('sample_size'),output_kind='SYMBOLIC_FUNCTIONAL_ONLY')
        result=dag_joint.prepare(problem);record['operation']='DAG_JOINT_ID';description=t['context']+'；同时设定 '+', '.join(t['treatments'])+'；结果 '+', '.join(t['outcome'])
    else:
        net=s['network']['value'];info=s['mean_information']['value'];bounds=s['bounds']['value']
        if not s['network_target']['value']['period'].strip():
            return stop(r,'NEEDS_INPUT','TARGET_PERIOD_REQUIRED','结果的评价时期尚未说明。',['这次要评价哪段时间的结果？'])
        if s['exposure']['value']['grouping'] in ('OTHER','UNKNOWN'):
            return stop(r,'UNSUPPORTED','EXPOSURE_NOT_EXPRESSED','同伴状态尚不能按现有规则明确计算；原定义已保留。')
        if net['complete'] is not True or net['undirected'] is not True:
            return stop(r,'NEEDS_INPUT','COMPLETE_UNDIRECTED_NETWORK_REQUIRED','请确认关系表的方向和覆盖范围。',
                ['关系表是否列出了本次全部对象之间的无向关系？若有遗漏或有方向，请说明。'])
        if info['kind']!='POPULATION_MEANS_ONLY' or info['matches_target'] is not True:
            return stop(r,'NEEDS_INPUT','EXACT_MEAN_INFORMATION_REQUIRED','不能把有限记录或更丰富的分布信息简化成已知均值表。',
                ['所列数字是本题同一时期的总体条件均值，还是样本平均数？是否还有其他总体信息？'])
        if (bounds['all_assignments'] is not True or bounds['kind']=='UNKNOWN' or bounds['outcome_domain']=='UNKNOWN'
                or set(bounds['by_node'])!=set(net['nodes']) or any(len(v)!=2 for v in bounds['by_node'].values())):
            return stop(r,'NEEDS_INPUT','BOUND_SCOPE_REQUIRED','需要知道给定范围约束的是结果还是均值，以及是否适用于全部安排。',
                ['给出的上下限约束每个结果，还是条件平均结果？是否适用于所有可能的使用名单？'])
        from .network_joint_projection import project,replay_projection
        if any(o['status']=='ADOPTED' and (not o['nodes'] or o['axis']=='UNKNOWN' or o['direction']=='UNKNOWN' or o['all_other_states'] is not True) for o in s.get('mean_orders',[])):
            return stop(r,'NEEDS_INPUT','MEAN_ORDER_SCOPE_REQUIRED','均值顺序的适用范围尚未明确。',
                ['这项平均结果不降（或不升）的条件适用于哪些对象？是在固定同伴情况时比较本人使用，还是固定本人情况时比较同伴使用？是否适用于另一项的全部情况？'])
        try:problem,projection=project(s,reader.sources(case))
        except ValueError as exc:
            if str(exc) not in ('NETWORK_ENUMERATION_LIMIT_12','FINITE_MEAN_COORDINATE_LIMIT_128',
                    'EXTENDED_DESIGN_EXACT_ENUMERATION_LIMIT_8','CONDITIONAL_MEAN_ON_ZERO_PROBABILITY_EVENT',
                    'MEAN_CELL_NOT_REALIZABLE','CONSTRAINT_CELL_NOT_REALIZABLE','EMPTY_BINARY_OUTCOME_SUPPORT'):
                raise
            return stop(r,'UNSUPPORTED',str(exc),'材料已保留，但当前完整转换不能继续：'+str(exc))
        if not replay_projection(s,reader.sources(case),problem,projection):raise ValueError('NETWORK_PROJECTION_REPLAY_FAILED')
        record['projection']=projection;record['operation']='FINITE_MEAN_JOINT'
        result=finite_mean_joint.prepare(problem);description=s['network_target']['value']['description']
    record['problem']=problem
    if result['state']!='REVIEW_REQUIRED':
        return stop(r,result['state'],result['reason_code'],'当前完整材料尚不满足该方法的要求：'+str(result['reason_code']))
    items=[dict(code='target',label='确认这次要回答的问题',quote=description)]
    if family=='DAG_JOINT' and sample:
        items.append(dict(code='observed_data_scope',label='共同记录的变量与公式用途',
            quote='现有材料是有限样本，共同记录 '+', '.join(info['variables'])+'。仅输出目标观测分布的符号公式；不把样本当已知总体，不保证样本估计准确。'))
    items.extend(dict(code=c,label=LABELS[c],quote=conditions[c]['statement']) for c in required)
    items.extend(dict(code='constraint_'+str(i),label='本次采用的均值关系',quote=c['description'])
        for i,c in enumerate(s['constraints']) if c['status']=='ADOPTED')
    items.extend(dict(code='mean_order_'+str(i),label='本次采用的平均结果顺序',quote=c['description'])
        for i,c in enumerate(s.get('mean_orders',[])) if c['status']=='ADOPTED')
    sheet=dict(kind='joint_natural',items=items,case_sha256=digest(case),reading_binding=reader.binding(case,s),
        problem_sha256=sha(problem),draft_sha256=r['draft_sha256'])
    sheet['binding']=digest([sheet.copy(),record['audit']])
    r['condition_review']=sheet
    return stop(r,'REVIEW_REQUIRED',None,'原文与字段已核对。请确认本次问题和材料中采用的科学前提。')


def complete(case,report,review):
    if report['joint_entry'].get('operation')=='DAG_SINGLE_SOURCE':
        from .dag_single_source_entry import complete as complete_single
        return complete_single(case,report,review)
    if report['joint_entry'].get('operation')=='BINARY_IV_SOURCE':
        from .iv_natural_entry import complete as complete_iv
        return complete_iv(case,report,review)
    if report['joint_entry'].get('operation')=='NETWORK_OBSERVATIONAL_BOUNDS':
        from .observational_policy_bounds import complete as complete_bounds
        return complete_bounds(case,report,review)
    if report['joint_entry'].get('operation')=='SYMBOLIC_MEAN_JOINT':
        from .symbolic_mean_entry import complete as complete_symbolic
        return complete_symbolic(case,report,review)
    if report['joint_entry'].get('operation')=='NETWORK_OBSERVATIONAL_EFFECTS':
        from .observational_effect_entry import complete as complete_observed
        return complete_observed(case,report,review)
    if report['joint_entry'].get('operation') in ('NETWORK_FINITE_POLICY','NETWORK_OBSERVATIONAL_POLICY'):
        from .network_existing_entry import complete as complete_existing
        return complete_existing(case,report,review)
    entry=report['joint_entry']
    if entry['case_sha256']!=digest(case) or report['draft_sha256']!=digest(report['draft']):raise ValueError('JOINT_SOURCE_CHANGED')
    s=reader.inspect(case,entry['reading']);a=reader.check_audit(case,s,entry['audit'])
    if any(x['verdict']!='MATCH' for x in a['findings']):raise ValueError('JOINT_SOURCE_NOT_REVIEWED')
    r=plan(case,base(report,case,s,a));record=r['joint_entry']
    if 'attempts' in entry:record['attempts']=deepcopy(entry['attempts'])
    if 'audit_repairs' in entry:record['audit_repairs']=deepcopy(entry['audit_repairs'])
    if 'gap_reviews' in entry:record['gap_reviews']=deepcopy(entry['gap_reviews'])
    if r.get('condition_review')!=report.get('condition_review') or record.get('problem')!=entry.get('problem'):
        raise ValueError('JOINT_PROBLEM_OR_REVIEW_CHANGED')
    if record_review_decisions(r,review):return r
    op=record['operation'];problem=record['problem'];module=dag_joint if op=='DAG_JOINT_ID' else finite_mean_joint
    native=module.submit(problem,dict(version=problem['version'],problem_sha256=sha(problem),authority=review['authority'],
        reviewer='homepage researcher',evidence='source-bound reading audit and explicit current user scientific confirmation',
        decisions={k:'ACCEPTED' for k in (dag_joint.decisions_for(dag_joint.validate(problem)) if op=='DAG_JOINT_ID' else module.DECISIONS)}))
    record.update(native_result=native,completed=True,state=native['state'],reason_code=native.get('reason_code'),
        message='数学库已计算并独立核验证书。' if native.get('independent_replay') else '数学库已返回检查结果；尚未交付估计。')
    r.update(independent_replay=native.get('independent_replay',False),backend_called=native.get('backend_called',False),
        decision='CONDITIONAL_RESULT' if native.get('independent_replay') else 'WITHHELD')
    if native.get('independent_replay'):
        r['proof']=dict(method=op,binder=VERSION,certificate=native['certificate'],source_binding=reader.binding(case,s),
            review_binding=review['binding'],projection=record.get('projection'))
    return r


def replay(case,draft,report):
    try:
        if report['draft']!=draft:return False
        entry=report['joint_entry'];source_reader=reader
        if entry.get('operation')=='BINARY_IV_SOURCE':
            from cfm_id_llm import iv_source_reading as source_reader
        if entry.get('operation')=='SYMBOLIC_MEAN_JOINT':
            from cfm_id_llm import symbolic_mean_reading as source_reader
        if entry.get('operation')=='NETWORK_OBSERVATIONAL_EFFECTS':
            from cfm_id_llm import observational_effect_source as source_reader
        if entry.get('operation') in ('NETWORK_FINITE_POLICY','NETWORK_OBSERVATIONAL_POLICY','NETWORK_OBSERVATIONAL_BOUNDS'):
            from cfm_id_llm import network_existing_reading as source_reader
        s=source_reader.inspect(case,entry['reading']);a=source_reader.check_audit(case,s,entry['audit'])
        if any(x['verdict']!='MATCH' for x in a['findings']):return False
        rebuilt=complete(case,report,report['review_record'])
        # Native graph edges can be tuples in memory and lists after JSON
        # storage. Compare their canonical wire content; complete() above
        # still rebuilds the exact bound problem and independently checks its
        # native certificate. Do not mistake JSON round-tripping for tampering.
        return (digest(rebuilt.get('proof'))==digest(report.get('proof')) and
                digest(rebuilt['joint_entry'].get('native_result'))==digest(entry.get('native_result')))
    except (KeyError,ValueError,TypeError,ArithmeticError):return False
