"""Durable local delivery of explicitly reviewed population queries."""
import json
import re
from fractions import Fraction
from pathlib import Path
from uuid import uuid4
from cfm_id_llm.compact_study import digest

PREVIOUS_ALIGNED_PACKET = "aligned-network-handoff/1"
ALIGNED_PACKET = "aligned-network-handoff/5"
PACKET_REVISIONS = {PREVIOUS_ALIGNED_PACKET:"direct-verification/17", "aligned-network-handoff/2":"direct-verification/18",
                    "aligned-network-handoff/3":"direct-verification/19","aligned-network-handoff/4":"direct-verification/20",
                    ALIGNED_PACKET:"direct-verification/22"}


def atomic_json(path,value):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+"."+uuid4().hex+".tmp")
    try:
        tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n","utf8")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def check_packet(packet, *, historical=False):
    """Check target, per-unit weights, event probabilities and consumer scope together."""
    review=packet["review"]
    from .uploaded_network_contrast import check_review
    sheet=dict(packet["condition_review"])
    check_review(sheet,review)
    expected_binding=sheet.pop("binding")
    if digest([sheet,packet["source_proof"],packet["target"],packet["estimate_handoff"]])!=expected_binding:
        raise ValueError("NETWORK_PACKET_BINDING_MISMATCH")
    if not all(v=="ADOPTED" for v in review["decisions"].values()) or packet.get("status")!="POINT" or packet.get("estimation_handoff_allowed") is not True:
        raise ValueError("EXPLICIT_NETWORK_REVIEW_REQUIRED")
    if (packet.get("release_scope")!=review["authority"] or packet.get("scientific_approval") is not (review["authority"]=="EXTERNAL_RESEARCH_REVIEW")
            or packet.get("production_admission") is not False):
        raise ValueError("NETWORK_RELEASE_SCOPE_MISMATCH")
    proof=packet["source_proof"]
    handoff=packet["estimate_handoff"]
    graph=packet["network_manifest"]
    graph_fields={k:v for k,v in graph.items() if k not in ("reference","scientific_approval")}
    from cfm_id_llm.network_files import NetworkTable
    table=NetworkTable(**graph_fields)
    if table.token!=proof["network_reference"] or digest(table.manifest())!=digest(graph):
        raise ValueError("NETWORK_PACKET_GRAPH_MISMATCH")
    nodes=proof["population"]
    ends=proof["ordered_events"]
    expected=[(node,arm) for node in nodes for arm in ends]
    queries=handoff["queries"]
    if (proof.get("binder")!="uploaded-network-comparison/1" or packet["target"]["population"]!=nodes
            or handoff.get("population")!=nodes or handoff.get("mode")!="ESTIMATE_POINT"
            or len(ends)!=2 or len(nodes)!=len(set(nodes)) or not nodes or len(queries)!=len(expected)
            or any(q.get("kind")!="person_event_mean" or q.get("unit")!=n or f"{q['own']},{q['exposure']}"!=arm
                   or q.get("id")!=n+"|"+arm or q.get("exposure_rule")!=proof["exposure"]
                   or q.get("time")!=packet["target"]["time"] or q.get("outcome")!=packet["target"]["outcome"]
                   or q.get("treatment")!=proof["assignment"]["variable"] or not isinstance(q.get("neighbors"),list)
                   or Fraction(proof["joint_probabilities"][n][arm])<=0 for q,(n,arm) in zip(queries,expected))):
        raise ValueError("NETWORK_QUERIES_DIFFER_FROM_CONFIRMED_TARGET")
    operator=handoff["operator_spec"]
    if (operator.get("version")!="population-query/1" or len(operator["forms"])!=1
            or list(map(Fraction,operator["forms"][0])) != [Fraction(sign,len(nodes)) for _ in nodes for sign in (1,-1)]):
        raise ValueError("NETWORK_QUERY_OPERATOR_MISMATCH")
    aligned_versions=PACKET_REVISIONS
    if not historical or packet.get("version") in aligned_versions:
        from .direct_verification import verify
        if packet.get("version") not in aligned_versions:
            raise ValueError("SOURCE_ALIGNED_PACKET_REQUIRED")
        case = packet["source_case"]
        draft = packet["source_draft"]
        if (case.get("case_id") != sheet["case_id"] or digest(case) != sheet["case_sha256"]
                or digest(draft) != sheet["draft_sha256"] or digest(case["sources"]) != proof["source_sha256"]):
            raise ValueError("NETWORK_PACKET_SOURCE_MISMATCH")
        # Rebuild the worksheet and its scientific evidence, not just the packet's
        # self-consistent hash. This is a pure local solver call with no model transport.
        revision=PACKET_REVISIONS[packet["version"]] if historical else PACKET_REVISIONS[ALIGNED_PACKET]
        rebuilt = verify(case, draft, version=revision, network=table,
                         network_focus=packet.get("network_focus",False),scope_choice=packet.get("scope_choice"))
        aligned = rebuilt.get("network_alignment") or {}
        candidate = rebuilt.get("conditional_answer") or {}
        projected = ("target","status","value","assumptions","estimate_handoff")
        if (not aligned.get("matched") or aligned != packet.get("network_alignment")
                or digest(rebuilt.get("condition_review")) != digest(packet["condition_review"])
                or digest(rebuilt.get("proof")) != digest(proof)
                or any(k not in packet or digest(packet[k]) != digest(candidate.get(k)) for k in projected)):
            raise ValueError("NETWORK_PACKET_SOURCE_ALIGNMENT_FAILED")
    return dict(binding=review["binding"],query_count=len(queries),query_sha256=digest(handoff),
                release_scope=review["authority"],state="RECEIVED")


class QueryInbox:
    """One current delivery per run. Consumers distinguish synthetic and research receipts."""
    def __init__(self,root):
        self.root=Path(root)

    def path_for(self,run_id):
        if not isinstance(run_id,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}",run_id):
            raise ValueError("INVALID_NETWORK_RUN_IDENTIFIER")
        return self.root/(run_id+".json")

    def receive(self,run_id,packet):
        from . import classic_query_exchange, direct_policy_exchange
        if packet.get('version')==direct_policy_exchange.VERSION:
            receipt=direct_policy_exchange.check_packet(run_id,packet)
            receipt.update(state='QUEUED',consumer='identification_query_queue')
            atomic_json(self.path_for(run_id),dict(receipt=receipt,packet=packet))
            return receipt
        if packet.get('version')==classic_query_exchange.VERSION:
            receipt=classic_query_exchange.check_packet(run_id,packet)
            atomic_json(self.path_for(run_id),dict(receipt=receipt,packet=packet))
            return receipt
        if packet["condition_review"]["case_id"]!=run_id:
            raise ValueError("NETWORK_RUN_MISMATCH")
        receipt=check_packet(packet)
        receipt.update(run_id=run_id,consumer="identification_query_queue")
        path=self.path_for(run_id)
        record=dict(receipt=receipt,packet=packet)
        atomic_json(path,record)
        return receipt

    def revoke(self,run_id):
        path=self.path_for(run_id)
        if path.exists():
            atomic_json(path,dict(receipt=dict(run_id=run_id,state="SUPERSEDED"),packet=None))
