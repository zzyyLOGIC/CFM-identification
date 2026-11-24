"""Bind an explicit focal-population decision to the original draft, roster and question."""
from copy import deepcopy
from fractions import Fraction
import re

from cfm_id_llm.compact_study import digest
from .direct_verification import answer_items, bound_network
from .network_protocol_terms import named_units
from .network_response import typed_fields, unpack


def worksheet(case,draft,network,result):
    alignment=result.get("network_alignment") or {}
    fields=alignment.get("fields") or {}
    if not alignment.get("source_target_complete") or set(fields)!={"population","ends","exposure","assignment"}:
        return None
    f=fields["population"]
    if f["state"]!="DISAGREEMENT" or any(fields[k]["state"]!="MATCH" for k in ("ends","exposure","assignment")):
        return None
    claimed=f.get("model")
    if not isinstance(claimed,dict) or claimed.get("scope")!="whole" or not isinstance(claimed.get("population"),str):
        return None
    table=bound_network(case,network)
    nodes=list(table.nodes)
    weights=f.get("source")
    if not isinstance(weights,dict) or not weights or any(v!=str(Fraction(1,len(weights))) for v in weights.values()):
        return None
    source=list(weights)
    names=named_units(re.split(r"[，,。]",claimed["population"])[0].strip(),nodes)
    normalized, _=unpack(draft)
    facts=typed_fields((normalized or {}).get("network_facts") or {})
    model=(facts.get("contrast") or {}).get("value") or {}
    items=answer_items(draft)
    if (not isinstance(model,dict) or not names or set(names)!=set(source) or set(source)==set(nodes)
            or len(items)!=1 or not isinstance(model.get("population"),list)
            or len(model["population"])!=len(names) or not all(isinstance(v,str) for v in model["population"])
            or set(model["population"])!=set(names)
            or any(k in item for item in (model,items[0].get("target") or {}) for k in ("weights","unit_weights"))):
        return None
    sheet=dict(question="本次平均要评价哪些对象？",
               options=[dict(id="named",members=source,label="、".join(source)+"，各对象等权"),
                        dict(id="whole",members=nodes,label="全体 "+str(len(nodes))+" 个对象，等权")],
               evidence=f["evidence"],case_sha256=digest(case),draft_sha256=digest(draft),network_reference=table.token)
    sheet["binding"]=digest(sheet)
    return sheet


def verify(case,draft,network,focus,review,choice,*,allow_index_ranges=False,multisource=True):
    from . import direct_verification as direct, network_source_alignment, uploaded_network_contrast
    base=direct.verify(case,draft,version="direct-verification/19",network=network,network_focus=focus,_index_ranges=allow_index_ranges,_multisource=multisource)
    sheet=worksheet(case,draft,network,base) if network is not None else None
    if choice is None:
        if sheet:
            if review is not None:
                raise ValueError("POPULATION_CHOICE_REQUIRED")
            base.update(scope_worksheet=sheet,clarification_questions=[sheet["question"]])
        elif review is not None:
            base=direct.verify(case,draft,version="direct-verification/19",network=network,network_focus=focus,
                               science_review=review,_index_ranges=allow_index_ranges,_multisource=multisource)
        return base
    if (not sheet or not isinstance(choice,dict) or set(choice)!={"binding","option"}
            or choice["binding"]!=sheet["binding"] or choice["option"] not in ("named","whole")):
        raise ValueError("INVALID_OR_STALE_POPULATION_CHOICE")
    option=next(o for o in sheet["options"] if o["id"]==choice["option"])
    resolved=dict(members=option["members"],option=option["id"],binding=sheet["binding"])
    report=direct.verify(case,draft,version="direct-verification/11",network=network,network_focus=focus)
    uploaded_network_contrast.apply(case,draft,network,report,review,source_first=True,extended=True,
                                    source_scope=True,natural_sources=True,scope_resolution=resolved)
    network_source_alignment.enforce(case,network,draft,report,review,source_scope=True,scope_resolution=resolved,
                                     allow_index_ranges=allow_index_ranges)
    report.update(scope_worksheet=sheet,scope_choice=deepcopy(choice))
    return report
