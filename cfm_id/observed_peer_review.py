"""Conditional nodewise exposure adjustment from an explicit observational protocol."""
import re
from fractions import Fraction

from pfn_pipeline._internal.identification.schemas import Assumption
from pfn_pipeline.identification_composition import EffectQueryV18
from pfn_pipeline.identification_observational_nodewise_adjustment import (
    admit_nodewise_adjustment_a5_v28, declare_nodewise_local_arm_population_v28,
    identify_observational_nodewise_effects_v28, replay_observational_nodewise_effects_v28)
from pfn_pipeline.identification_observational_r3 import R3Unavailable
from pfn_pipeline.identification_policy_r2 import declare_policy_signature
from pfn_pipeline.network_inquiry_shadow import declare_network_study
from .network_estimate_handoff import delivery, make_handoff
from .network_query_binding import RATE, read_rate
from .source_network_review import MissingFacts, ORD, count, evidence, one

PEER=r"(?:朋友|伙伴|邻居|同伴)"
ID=r"[\w\u3400-\u9fff]{1,14}?"
DENIAL=r"不采用|未采用|未承诺|拒绝|撤回|不能确认|尚未确认|无法保证|不成立|不再假定"
EXCHANGE=r"交换性|交换|均值充分|潜在结果均值"
NEEDS="材料未给出可采用的联合暴露条件均值交换性。即使各端有正支持，观察条件均值仍无法据此替代干预均值。"


def event(side):
    if re.search(PEER+r"(?:都|全|均)(?:不|未)|没有(?:任何|一个)?"+PEER,side):return 0
    if re.search(r"(?:至少一(?:位|个|名)?|有)"+PEER+r"|"+PEER+r"中(?:有人|至少一)",side):return 1
    return None


def direction(q):
    ends=[]
    for part in re.split(r"[，,。！？?\n]",q):
        m=re.search(r"(.+?)(?:相对于|相比于|相比|减去|减)(.+)",part)
        if m:
            pair=(event(m[1]),event(m[2]))
            if None not in pair:
                ends.append(pair)
    if len(set(ends))!=1 or ends[0][0]==ends[0][1]:
        raise MissingFacts("请说明本人状态固定为何值，以及朋友暴露两端按什么方向相减。")
    return ends[0]


def study_profile(rows,nodes,feature):
    profiles=[]
    for row in rows:
        s=row["quote"]
        flat=re.search(r"(?:全部|均)为([01])[，,]\s*(?:占|概率为)("+RATE+r")",s)
        vec=re.search(r"(?:配置|向量)\s*[(（]([01](?:\s*[,，、]\s*[01])+)[)）][，,]?\s*(?:占|概率为)("+RATE+r")",s)
        if flat:
            v=[int(flat[1])]*len(nodes);prob=read_rate(flat[2])
        elif vec:
            v=list(map(int,re.split(r"\s*[,，、]\s*",vec[1])));prob=read_rate(vec[2])
        else:
            continue
        if len(v)!=len(nodes) or any(p[0]==v for p in profiles) or prob<=0:
            raise MissingFacts("请提供顺序与研究名单一致、互异且有正质量的完整处理前配置。")
        profiles.append((v,prob,row))
    if not profiles or sum(p for _,p,_ in profiles)!=1:
        raise MissingFacts("请补齐处理前配置及其总体概率。")
    law=one(rows,r"给定.{0,10}完整"+re.escape(feature)+r"配置.{0,45}联合总体分布.{0,15}分解",message="需核对各完整背景配置下的联合观察分布，才能逐层检查两端支持。")
    m=re.search(r"(?:每人|每个单位|各人).{0,10}概率(?:均?为|是)("+RATE+r")",law["quote"])
    if not m:
        raise MissingFacts("请给出该观察分解中各单位适用的参加概率。")
    p=read_rate(m[1])
    for row in rows:
        if row==law:continue
        other=re.search(r"(?:每人|每个单位|各人).{0,10}概率(?:均?为|是)("+RATE+r")",row["quote"])
        if other and read_rate(other[1])!=p:
            raise MissingFacts("材料中的观察参加概率有分歧，请确认各背景层所用的联合观察规律。")
    return [(f"x{i}",str(w),tuple(v),(str(p),)*len(nodes)) for i,(v,w,_) in enumerate(profiles)], [r for _,_,r in profiles]+[law]


def derive(q,rows):
    text="。".join(r["quote"] for r in rows)
    if not (re.search(r"观察分布|观察性(?:总体|分布)",text) and re.search(r"完整.{1,6}配置",text)
            and re.search(r"调整变量.{0,18}自身.{0,18}"+PEER,text) and re.search(PEER,q)):
        return None
    focusrow=one(rows,r"只评价"+ID+r"[，,].{0,10}名单.{0,10}前固定",message="请明确处理前指定的评价对象。")
    focus=re.search(r"只评价("+ID+r")[，,]",focusrow["quote"])[1]
    outcome=one(rows,r"结果(?:是|为).{1,30}(?:连续|二元)",message="请核对同一背景下的结果变量。")
    y=re.search(r"结果(?:是|为)([^，,]+)",outcome["quote"])[1]
    context=one(rows,r"固定背景.{1,6}(?:是|为).{1,40}(?:不包括|不含)",message="请明确固定的处理前背景以及用于标准化的可变特征。")
    w=re.search(r"(?:是|为)([^，,]+)",context["quote"])[1]
    denials=[r for r in rows+[{"source_id":"question","quote":q,"start":0,"end":len(q)}]
             if re.search(DENIAL,r["quote"]) and re.search(EXCHANGE,r["quote"])]
    if denials:
        target=dict(quantity="difference",scope="subgroup",population=[focus],intervention="原题的同伴状态比较",reference="按原题方向",
                    time=w,outcome=y)
        hand=make_handoff(target,"STOP",[],[],[],NEEDS,{})
        return delivery(target,"NEEDS_INPUT",NEEDS,None,[evidence(denials[0],"未获采用的交换性")],hand,
                        NEEDS+" 该版本只回指原目标，保留其焦点对象和研究背景。继续识别需要其他有依据的科学条件。",
                        dict(method="OBSERVED_PEER_CONDITION_GAP",source_spans=[focusrow,outcome,context,*denials]))
    if re.search(r"总体变更|外推到|换人群|不再固定|另一个(?:目标|背景)|后者减前者|再问|第二问|次周|来年|下学期|改为.{0,12}(?:结局|成绩|指标)",q):
        raise MissingFacts("请明确本次所问的人群、背景、结果及相减方向是否与总体资料一致。")
    focal=re.findall(r"只评价("+ID+r")(?=[，,。？\s]|$)",q)
    if not focal or set(focal)!={focus}:
        raise MissingFacts("请确认原题所评的焦点对象，附件的条件只覆盖其中指定的人。")
    own=re.search(re.escape(focus)+r"(?:同学|本人)?(?:自己|本人)(不|未|已)?(?:参加|参与)时",q)
    if not own:raise MissingFacts("请确认固定的本人参加状态。")
    a=int(own[1] not in ("不","未"))
    left,right=direction(q)
    graph=one(rows,r"名单顺序(?:为|是).{1,180}(?:无其他边|没有其他边)",message="请给出处理前无向图的完整名单与边。")
    gm=re.search(r"名单顺序(?:为|是)([^，,]+)[，,].{0,8}关系(?:是|为)([^，,]+)[，,]",graph["quote"])
    if not gm or not re.search(r"处理前固定的无向|事前固定的无向",graph["quote"]):
        raise MissingFacts("请核对关系图的方向、完整性及记录时间。")
    nodes=tuple(re.split(r"[、和与]",gm[1])); edges=tuple(tuple(re.split(r"[—↔\-]",s)) for s in gm[2].split("、"))
    if focus not in nodes or len(nodes)!=len(set(nodes)) or any(len(e)!=2 or e[0]==e[1] or not set(e)<=set(nodes) for e in edges):
        raise MissingFacts("边表和焦点对象与研究名单不一致。")
    if re.sub(r"^(?:本周|本月|当期|本期|本学期)","",y) not in q:
        raise MissingFacts("原题的结果与资料库的指标尚未对应，请核对结果和时期。")
    tr=one(rows,r"(?:参加|参与).{1,20}记1[，,]不(?:参加|参与)记0",message="请核对实际观察的处理变量。")
    variable=tr["quote"].split("记1")[0]
    mapping=one(rows,r"(?:同伴|邻居|朋友)状态定义为至少一.{0,14}(?:为1|记1).{0,10}(?:为0|记0)",message="请核对同伴暴露的二元映射。")
    feature=one(rows,r"(?:活动|处理|干预|分配)前.{1,20}记[A-Za-z]\w*[，,]",message="请给出处理前二元特征的定义。")
    x=re.search(r"记([A-Za-z]\w*)[，,]",feature["quote"])[1]
    cov=one(rows,re.escape(focus)+r"的调整变量.{0,10}自身"+re.escape(x)+r".{0,8}全部"+PEER+r"中"+re.escape(x)+r"=1的人数",message="请核对焦点对象自己的特征和所有朋友中特征为 1 的人数。")
    defs=[("consistency",r"(?:观察|观测)结果对应实际完整", "完整名单一致性"),
          ("fixed_pretreatment_network",r"处理前固定的无向|事前固定的无向", "处理前固定网络"),
          ("finite_conditional_first_moments",r"所需条件均值有限|条件一阶矩有限","有限条件一阶矩"),
          ("potential_outcome_exposure_sufficiency",r"对"+re.escape(focus)+r"[，,].{0,12}所有完整.{0,15}安排下.{0,25}本人和同伴状态相同.{0,18}潜在结果就相同","潜在结果的暴露映射充分性"),
          ("local_covariate_exposure_mean_exchangeability",r"给定"+re.escape(focus)+r"自身"+re.escape(x)+r".{0,8}"+PEER+r"中"+re.escape(x)+r"=1的人数.{0,15}固定背景.{1,9}后.{0,35}潜在结果均值.{0,15}不随实际本人和同伴状态改变","给定本人及邻居特征的联合暴露均值交换性")]
    cond={code:one(rows,pat,message="请说明能否在所问对象及背景下采用"+name+"。") for code,pat,name in defs}
    contrary=r"(?:不采用|拒绝|撤回|无法保证|不成立).{0,40}(?:一致性|有限|充分性|相同|固定)|(?:均值|一阶矩)不有限|不同名单.{0,20}仍会改变|(?:只有|仅有)样本|(?:没有|不提供|不覆盖).{0,16}(?:分层均值|总体均值算子)|(?:生效|处理|干预)后才(?:建立|登记)|(?:只覆盖|只提供|仅覆盖|仅提供).{0,18}(?:一端|部分|一层)"
    if re.search(contrary,text+"。"+q):
        raise MissingFacts("材料对科学条件、观察期或总体均值覆盖存在分歧，请核对。")
    profiles,profrows=study_profile(rows,nodes,x)
    means=one(rows,r"提供"+re.escape(focus)+r".{0,20}每种背景组合.{0,55}(?:全部|所有).{0,8}条件总体均值算子",message="请明确各正质量层能查询所问两端的总体条件均值。")
    if not re.search(r"自己(?:参加或不参加|不参加或参加).{0,10}朋友(?:有人参加或都不参加|都不参加或有人参加)",means["quote"]):
        raise MissingFacts("需核对均值算子覆盖的本人和同伴状态。")
    positions={n:i for i,n in enumerate(nodes)}
    friends={b if f==focus else f for f,b in edges if focus in (f,b)}
    strata={(v[positions[focus]],sum(v[positions[j]] for j in friends)) for _,_,v,_ in profiles}
    n_cells=re.search(r"全部("+ORD+r")个条件总体均值",means["quote"])
    if n_cells and count(n_cells[1])!=4*len(strata):
        raise MissingFacts("资料声明的总体均值数量与背景分层和两种处理状态不相符。")
    study=declare_network_study(network_id="source-observational-network",node_order=nodes,undirected_edges=edges,
        treatment_variable=variable,outcome_variable=y,outcome_kind="continuous" if "连续" in outcome["quote"] else "binary",
        context_reference=w,observation_regime="observational",assignment_design=None,protocol_provenance=means["quote"],
        network_provenance=graph["quote"],graph_timing_claim="DECLARED_PRETREATMENT_FIXED")
    sig=declare_policy_signature(study,grouping="any_treated_neighbor")
    cellset=[(focus,v,k,b,s) for v,k in strata for b in (0,1) for s in (0,1)]
    src=declare_nodewise_local_arm_population_v28(study,sig,source_id=means["source_id"],provenance=means["quote"],
        feature_name=x,profiles=profiles,covered_cells=cellset)
    # These are premises of a conditional derivation, never user or production approvals.
    assumptions={k:Assumption(name=k,source="demo_specification",confirmed=True,
                        evidence=["条件推导，真实研究待核准。"+cond[k]["quote"]]) for k,_,_ in defs}
    lic=admit_nodewise_adjustment_a5_v28(study,sig,feature_name=x,covered_nodes=(focus,),
        potential_outcome_exposure_sufficiency=assumptions[defs[3][0]],local_covariate_exposure_mean_exchangeability=assumptions[defs[4][0]])
    req=EffectQueryV18(kind="SPILLOVER",node_weights=((focus,1),),reference_exposure=right,comparison_exposure=left,spillover_own_treatment=a)
    try:
        native=identify_observational_nodewise_effects_v28(study,src,sig,assumptions=tuple(assumptions[k] for k,_,_ in defs[:3]),license=lic,requests=(req,))
    except R3Unavailable as exc:
        raise MissingFacts("目前不能按所列观察层交付该公式，请核对逐层正支持和均值覆盖（"+exc.reason_code+"）。") from exc
    if not replay_observational_nodewise_effects_v28(native):
        raise MissingFacts("观察性识别证书重放未通过。")
    result=native.proofs[0]
    target=dict(quantity="difference",scope="subgroup",population=[focus],intervention=f"本人={a}, 同伴={left}",
                reference=f"本人={a}, 同伴={right}",outcome=y,time=w)
    queries=[];weights=[]
    for side,sign in ((left,1),(right,-1)):
        record=next(v for n,own,s,v in result.support_by_term if (n,own,s)==(focus,a,side))
        for v,k,mass,support in record:
            queries.append(dict(id=f"{focus}|{a},{side}|{v},{k}",kind="node_covariate_exposure_population_mean",unit=focus,
                own=a,exposure=side,own_feature=v,neighbor_feature_count=k,feature=x,outcome=y,time=w,
                neighbors=sorted(friends),treatment=variable,arm_probability=support))
            weights.append(sign*Fraction(mass))
    h=make_handoff(target,"ESTIMATE_POINT",[variable,"至少一位朋友参加",x,"朋友中特征为1的人数",w,y],
                   queries,[weights],result.identified_functional,result.summary()["support_by_term"])
    proof=dict(method="OBSERVED_NODEWISE_STANDARDIZATION",native_theorem=native.theorem_id,native_certificate=native.certificate_sha256,
               scientific_use="CONDITIONAL_ON_STATED_PREMISES",
               native_replay=True,observation_regime="observational",ordered_events=[[a,left],[a,right]],
               source_spans=[graph,focusrow,outcome,context,tr,mapping,feature,cov,means,*profrows,*cond.values()])
    why="若采用所列科学前提，各层内本人和同伴联合暴露可交换，且两端均有正支持。按焦点对象的背景总体分布对观察条件均值标准化。总体算子已提供，数值待估计；本次为条件推导。"
    return delivery(target,"POINT",result.identified_functional,None,[evidence(cond[k],name) for k,_,name in defs],
                    h,why,proof)
