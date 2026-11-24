"""Estimation-side adapter. Register the scoped ID queries without starting model fitting."""
from fractions import Fraction
from cfm_id.network_query_exchange import QueryInbox, atomic_json, check_packet
from cfm_id import classic_query_exchange, direct_policy_exchange
from cfm_id_llm.compact_study import digest
from estimand_contract import Estimand


class EstimateIntake(QueryInbox):
    def receive(self,run_id,packet):
        if packet.get('version') in direct_policy_exchange.VERSIONS:
            receipt=direct_policy_exchange.check_packet(run_id,packet)
            receipt.update(consumer='autocfm_estimation_query_intake',typed_estimand=False,registration_version=packet['version'])
            atomic_json(self.path_for(run_id),dict(receipt=receipt,packet=packet,estimand=None))
            return receipt
        if packet.get('version')==classic_query_exchange.VERSION:
            receipt=classic_query_exchange.check_packet(run_id,packet)
            handoff=packet['estimate_handoff']
            study=packet['evidence']['materials'].get('study')
            if study:
                roster=study['nodes']
                if roster!=handoff['target']['node_order'] or any(
                    q['unit'] not in roster or 'assignment' in q and len(q['assignment'])!=len(roster)
                    for q in handoff['queries']):
                    raise ValueError('ESTIMATE_QUERY_ROSTER_MISMATCH')
            receipt.update(state='RECEIVED',consumer='autocfm_estimation_query_intake',
                           typed_estimand=False,registration_version=classic_query_exchange.VERSION)
            # Most reviewed functionals are outside the fitted Estimand schema. Register
            # their actual queries/operators or exact endpoints in the same durable inbox.
            atomic_json(self.path_for(run_id),dict(receipt=receipt,packet=packet,estimand=None))
            return receipt
        if packet["condition_review"]["case_id"]!=run_id:
            raise ValueError("NETWORK_RUN_MISMATCH")
        receipt=check_packet(packet)
        proof=packet["source_proof"]
        law=proof["assignment"]
        population=proof["population"]
        manifest=packet["network_manifest"]
        from cfm_id.network_event_handoff import native_support
        ordered=[tuple(map(int,e.split(','))) for e in proof['ordered_events']]
        recomputed=native_support(dict(basis='edges',nodes=manifest['nodes'],edges=manifest['edges'],
            complete_for=manifest['nodes'],roster_complete=True),law,dict(kind=proof['exposure']),population,ordered)
        if recomputed is None or recomputed!=proof['joint_probabilities'] or recomputed!=packet['estimate_handoff'].get('support'):
            raise ValueError('ESTIMATE_SUPPORT_DIFFERS_FROM_RANDOMIZATION')
        neighbors={n:set() for n in manifest["nodes"]}
        for u,v in manifest["edges"]:
            neighbors[u].add(v)
            neighbors[v].add(u)
        for query in packet["estimate_handoff"]["queries"]:
            peers=query["neighbors"]
            if len(set(peers))!=len(peers) or set(peers)!=neighbors[query["unit"]]:
                raise ValueError("QUERY_NEIGHBORS_DIFFER_FROM_UPLOADED_GRAPH")
        target=None
        if (proof["exposure"]=="majority" and law["kind"]=="independent"
                and all(Fraction(p)==Fraction(1,2) for p in law["p"].values())):
            a,b=[tuple(map(int,e.split(","))) for e in proof["ordered_events"]]
            kind=("SPILLOVER_EFFECT" if a[0]==b[0] else "DIRECT_EFFECT" if a[1]==b[1] else "LOCAL_TOTAL_EFFECT")
            scope=set(population)
            coordinates=dict(kind=kind,node_ids=manifest["nodes"],population=population,first=a,second=b,
                operation="FIRST_MINUS_SECOND",remaining_assignment="ORIGINAL_DESIGN_CONDITIONAL",
                assignment=dict(kind="INDEPENDENT_BERNOULLI",probabilities=law["p"]),
                exposure="STRICT_MAJORITY_TIES_LOW",treatment=law["variable"],outcome=packet["target"]["outcome"],
                context=packet["target"]["time"],unit_weights=[str(Fraction(1,len(scope))) if n in scope else "0" for n in manifest["nodes"]])
            edges=sorted(sorted(edge) for edge in manifest["edges"])
            target=Estimand(**coordinates,target_fingerprint=digest(["population-query-target/1",coordinates,edges])).model_dump(mode="json")
        receipt.update(run_id=run_id,mode=packet["estimate_handoff"]["mode"],consumer="autocfm_estimation_query_intake",typed_estimand=target is not None,
                       data_review="PENDING",estimator_executed=False)
        atomic_json(self.path_for(run_id),dict(receipt=receipt,packet=packet,estimand=target))
        return receipt
