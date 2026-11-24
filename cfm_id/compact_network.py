"""Apply existing randomized-network routes to a reviewed target and exact outcome means."""
from fractions import Fraction as F
from pfn_pipeline import identification_policy_r1b as r1b, identification_policy_r2 as r2
from pfn_pipeline.network_inquiry_shadow import declare_network_a4_source
from pfn_pipeline._internal.identification.schemas import Assumption
from cfm_id_llm.compact_study import digest
from .compact_review import method_name, LOCAL_CONTRAST, FULL_POLICY, EXPOSURE_POLICY
from . import research_spec_policy_adapters as policy_attributes
from . import research_spec_local_adapters as local_attributes
from .research_spec_coordinates import native_study

GROUP={"majority":"strict_majority_ties_low","count":"exact_treated_neighbor_count","any":"any_treated_neighbor"}


def solve(s,method,review):
    route=method_name(method)
    if route not in (LOCAL_CONTRAST,FULL_POLICY,EXPOSURE_POLICY):
        raise ValueError("UNKNOWN_NETWORK_METHOD")
    n=s.network;t=s.target;nodes=tuple(n.nodes);weights=list(map(F,n.weights))
    design=(dict(kind="complete_randomization_binary_v1",m=n.quota) if n.design=="fixed_quota" else
            dict(kind="heterogeneous_bernoulli_binary_v1",propensities=n.probabilities))
    shared_study=dict(network_id="network_"+digest([nodes,n.edges]),
        observation_regime="experimental",assignment_design=design,protocol_provenance=n.quote,
        network_provenance=n.quote,graph_timing_claim="DECLARED_PRETREATMENT_FIXED")
    if route==LOCAL_CONTRAST:
        question=local_attributes.from_compact(s)
    else:
        question=policy_attributes.from_compact(s)
    st=native_study(question.study,edges=n.edges,**shared_study)
    weights=list(map(F,question.evaluation.unit_weights))
    synthetic=review["authority"]=="SYNTHETIC_TEST"
    def condition(name,evidence):
        return Assumption(name=name,source="demo_specification" if synthetic else "human_confirmation",confirmed=True,
                          status="ADMITTED",evidence=[evidence,review["evidence"],review["binding"]])
    base=tuple(condition(k,v) for k,v in [
        ("known_assignment_law",n.quote),("full_vector_randomization",s.assumptions["randomization"]),
        ("consistency",s.assumptions["consistency"]),("fixed_pretreatment_network",s.assumptions["fixed_network"]),
        ("finite_conditional_first_moments",s.assumptions.get("finite_means","Binary outcome bounds its first moment"))])
    local={(r["own"],r["peer"]):list(map(F,r["means"])) for r in n.local}
    variables=[t.treatment,t.outcome,"单位编号","完整处理名单"]
    try:
        if route==LOCAL_CONTRAST:
            sig=r2.declare_policy_signature(st,grouping=GROUP[n.exposure])
            exp=r2.ExposureSpec(sig.grouping,None);design=st.design();net=st.network()
            arm1,arm0=question.first.coordinates(),question.second.coordinates()
            if arm1 not in local or arm0 not in local:return dict(method=method,state="NOT_APPLICABLE",reason="缺少某一局部臂的总体条件均值")
            masses=[]
            for i,node in enumerate(nodes):
                if not weights[i]:continue
                dist=r2.SupportEngine.joint_support(network=net,assignment=r2.AssignmentSpec(design),exposure=exp,node_id=node)
                for a,e in (arm1,arm0):
                    p=dist.get((a,e),F(0))
                    check=r2._independent_support(net,design,sig,node,a,e,None)
                    if p!=check:raise ValueError("INDEPENDENT_SUPPORT_DISAGREEMENT")
                    if not p:return dict(method=method,state="NOT_APPLICABLE",reason="局部目标臂零支持")
                    masses.append([node,a,e,str(p)])
            val=sum(w*(x-y) for w,x,y in zip(weights,local[arm1],local[arm0]))
            separate=[sum(w*x for w,x in zip(weights,local[arm])) for arm in (arm1,arm0)]
            if separate[0]-separate[1]!=val:raise ValueError("NUMERIC_SUBSTITUTION_MISMATCH")
            cert=dict(method=method,scope="local mean contrast; dual support checks and exact substitution",
                      support=masses,weights=list(question.evaluation.unit_weights),
                      arms=[list(arm1),list(arm0)],means=n.local,arm_means=list(map(str,separate)))
            functional=f"Σ_i w_i (E_q[Y_i|own,g={arm1}]−E_q[Y_i|own,g={arm0}])"
            return dict(method=method,state="POINT",functional=functional,value=str(val),certificate=cert,
                        variables=variables+["邻接关系及局部暴露"],operators=[functional,"在原分配设计的两个局部臂内分层，按目标单位权重平均"])
        tgt=policy_attributes.native_target(question,st,side='first',
            authority="TRUSTED_FIXTURE" if synthetic else "HUMAN_CONFIRMED")
        common=dict(source_id="reviewed_outcome_means",outcome_nodes=nodes,admission="ADMITTED",
                    availability="EXACT_POPULATION_VALUE",provenance=n.quote+" / "+review["evidence"])
        if route==FULL_POLICY:
            full=next(row for row in n.full if row["z"]==n.policy)
            src=declare_network_a4_source(st,operator="ASSIGNMENT_NODE_MEANS",assignment_cells=(tuple(n.policy),),**common)
            proof=r1b.identify_verified_fixed_policy(st,tgt,(src,),assumptions=base)
            passed=r1b.replay_verified_fixed_policy(proof)
            means=list(map(F,full["means"]))
            functional=f"Σ_i w_i E[Y_i | Z={n.policy}]"
        else:
            sig=r2.declare_policy_signature(st,grouping=GROUP[n.exposure])
            src=r2.declare_signature_population_source(st,sig,operator="NODE_SIGNATURE_MEANS",
                signature_cells=tuple((node,a,e) for a,e in local for node in nodes),**common)
            suff=r2.admit_mean_signature_sufficiency(st,sig,covered_nodes=nodes,
                assumption=condition("mean_signature_sufficiency",s.assumptions["mean_sufficiency"]))
            proof=r2.identify_verified_signature_policy(st,tgt,sig,(src,),assumptions=base,sufficiency=suff)
            passed=r2.replay_verified_signature_policy(proof)
            means=[F(0)]*len(nodes)
            for node,a,e in proof.policy_node_classes:
                if (a,e) not in local:return dict(method=method,state="NOT_APPLICABLE",reason="缺少目标标签下的总体均值")
                i=nodes.index(node);means[i]=local[a,e][i]
            functional=f"Σ_i w_i E[Y_i | Z_i=z_i, g_i(Z)=g_i(z)]，z={n.policy}"
            variables.append("邻接关系及局部暴露")
        if passed is not True or proof.status!="POINT":raise ValueError("NETWORK_PROOF_REPLAY_FAILED")
        value=sum(w*y for w,y in zip(weights,means))
        return dict(method=method,state="POINT",functional=functional,value=str(value),
            certificate=dict(theorem=proof.summary(),node_order=nodes,weights=n.weights,means=list(map(str,means)),value=str(value)),
            variables=variables,operators=[functional])
    except (r1b.R1bPolicyUnavailable,r2.R2PolicyUnavailable) as exc:
        return dict(method=method,state="NOT_APPLICABLE",reason=exc.reason_code)
