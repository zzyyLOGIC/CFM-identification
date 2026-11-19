"""Run LIT-NET-13 paternity-leave (birth-order) policy mean through the extended entry.

Eight fathers in two plants plus one brother outside the policy area. Two complete
start-date schedules with known probabilities, one covered father per plant in each.
A father's leave probability rises with the number of births between him and the
covered coworker in the same plant, so the same schedule shift changes the sum only
through the men who sit after the covered father. No LLM call. The A0 draft and the
fact candidate are hand-authored reference fixtures, not a measurement of any model's
reading.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cfm_id import business_dispatch as dispatch, business_intake as intake
from cfm_id_llm import network_extended_reading as rd
from cfm_id_llm.quality import BusinessInquiryV010, MultiQueryDraftV010, QuerySemanticsV010
from cfm_id_llm.schemas import (
    AssignmentFamily, BusinessCase, DraftProblemSpec, InformationDesignDraft,
    PopulationInformationLevel, SemanticClaim, SourceDocument, StructureDraft,
    TargetDraft, UnitsVariablesDraft,
)
from examples import network_extended_reference as e


ROOT = Path(__file__).resolve().parents[3]
CASE = ROOT / "evaluation" / "literature_cases" / "public" / "LIT-NET-13"
OUT = None
NODES = [f"父{i}" for i in range(1, 9)]
PLANT_A = NODES[0:4]
PLANT_B = NODES[4:7]
# Plant A is a complete graph on four men; plant B is a complete graph on three.
EDGES = (
    [[a, b] for i, a in enumerate(PLANT_A) for b in PLANT_A[i + 1:]]
    + [[a, b] for i, a in enumerate(PLANT_B) for b in PLANT_B[i + 1:]]
    + [["父1", "父8"]]
)
PLAN_A = {"父1": 1, "父5": 1}
PLAN_B = {"父3": 1, "父5": 1}
AFTER_FIRST = ["父2", "父3", "父4"]

QUOTES = {
    "original": {
        "goal": "八名父亲休假概率相对不推行这项政策时的平均提高在两种安排各一半机会时是多少",
        "population": "八名父亲",
        "aggregation": "每人等权",
        "policy": "两种安排各以一半概率被采用，这就是全部候选方案",
        "law": "未来政策只含问题中列出的两份完整生效安排，各占 1/2",
    },
    "missing_condition": {
        "goal": "八名父亲休假概率相对不推行这项政策时的平均提高在明年采用其中一套安排时是多少",
        "population": "八名父亲",
        "aggregation": "每人等权",
        "policy": "明年会从这两套安排里选一套执行",
        "law": "未来只执行一份生效安排，问题没有说明两套安排各自被采用的机会",
    },
    "changed_target": {
        "goal": "这三名父亲休假概率相对不推行这项政策时的平均提高在两种安排各一半机会时是多少",
        "population": "甲厂 2、3、4 号",
        "aggregation": "每人等权",
        "policy": "两种安排各以一半概率被采用，这就是全部候选方案",
        "law": "未来政策只含问题中列出的两份完整生效安排，各占 1/2",
    },
}


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf8")


def claim(text: str, source: str) -> SemanticClaim:
    return SemanticClaim(value=text, basis="EXPLICIT_TEXT", evidence=[dict(source_id=source, quote=text)])


def assignment_of(treated: dict) -> dict:
    return {n: treated.get(n, 0) for n in NODES}


def a0_draft(variant: str) -> dict:
    q = QUOTES[variant]
    goal = claim(q["goal"], "business_question")
    target = TargetDraft(kind="STOCHASTIC_POLICY_VALUE", description=goal)
    shared = DraftProblemSpec(
        target=target,
        units_variables=UnitsVariablesDraft(
            analysis_unit=claim("父亲是研究单位", "proposal"),
            treatment=claim("政策生效日之后生孩子的父亲记 1", "proposal"),
            outcome=claim("休带薪育儿假的概率相对不推行这项政策时的提高", "proposal"),
        ),
        structure=StructureDraft(unit_network=claim("同一家厂内的同事关系见题面列出的六对与三对", "proposal")),
        information_design=InformationDesignDraft(
            assignment_family=AssignmentFamily.CLUSTER_RANDOMIZATION,
            assignment_law=claim(q["law"], "proposal"),
            population_information_level=PopulationInformationLevel.NODE_FULL_LAW,
            population_observable_operator=claim("符号总体分布", "proposal"),
            sample_data_description=claim("不是八条样本记录", "proposal"),
        ),
    )
    sem = QuerySemanticsV010(
        target_population=claim(q["population"], "business_question"),
        intervention=claim(q["policy"], "business_question"),
        comparator=claim("不与某个对照方案相减", "proposal"),
        neighbor_exposure=claim("按与覆盖者的出生先后距离分档的规则", "proposal"),
        aggregation=claim(q["aggregation"], "business_question"),
        time_horizon=claim("评价时点为政策执行后", "proposal"),
        policy_assignment=claim(q["policy"], "business_question"),
        standardization_distribution=claim(q["aggregation"], "business_question"),
    )
    query = BusinessInquiryV010(query_id="q1", business_goal=goal, target=target, semantics=sem)
    return MultiQueryDraftV010(shared_draft=shared, primary_query_id="q1", queries=[query]).model_dump(mode="json")


def fact_candidate(entry, variant: str) -> dict:
    """Alias-form fact candidate for one variant; doubles as the mock reading reply."""
    refs = rd.reference_catalog(entry["bundle"], binding=entry["fact_binding_sha256"], family=rd.MIX)
    ids = list(refs["aliases"])
    _, raw = e.fixture("mixture")
    raw["reference_context"] = refs["context"]
    raw["study"].update(
        nodes=list(NODES),
        edges=[list(x) for x in EDGES],
        treatment="政策生效日之后生孩子记1，之前记0",
        outcome="休假概率相对不推行这项政策时的提高，单位为概率",
        outcome_kind="CONTINUOUS",
        context="政策执行后；八名父亲分属三个厂，甲厂与乙厂为同事关系，1 号与 8 号为兄弟，丙厂不推行这项政策",
        source_ids=ids,
    )
    raw["assignment"].update(probabilities={n: "1/2" for n in NODES}, source_ids=ids)
    population = list(AFTER_FIRST) if variant == "changed_target" else list(NODES)
    raw["target"].update(
        population=population,
        components=[
            dict(assignment=assignment_of(PLAN_A), weight="1/2", source_ids=ids),
            dict(assignment=assignment_of(PLAN_B), weight="1/2", source_ids=ids),
        ],
        source_ids=ids,
    )
    raw["information"][0].update(outcome_nodes=list(NODES), source_ids=ids)
    if variant == "missing_condition":
        raw["target"]["policy_distribution_complete"] = dict(value=None, source_ids=ids)
        raw["target"]["components"] = []
    return raw


def run_variant(variant: str) -> dict:
    if OUT is None:
        raise ValueError("REFERENCE_FIXTURE_OUTPUT_REQUIRED")
    question = (CASE / variant / "business_question.md").read_text(encoding="utf8").strip()
    protocol = (CASE / variant / "study_protocol.md").read_text(encoding="utf8")
    case = BusinessCase(
        case_id=f"LIT-NET-13-{variant}",
        business_question=question,
        sources=[SourceDocument(source_id="proposal", text=protocol)],
    )
    folder = OUT / variant
    folder.mkdir(parents=True, exist_ok=True)
    s = intake.start(case, reading_format="canonical", fact_format="short_refs")
    s = intake.receive_candidate(s, a0_draft(variant), request_sha256=s.request_sha256)
    initial = dispatch.prepare_reader(s, "q1")
    write_json(folder / "business.json", case.model_dump(mode="json"))
    if not initial.get("query_worksheet"):
        write_json(folder / "result.json", initial)
        return dict(variant=variant, plan_state=initial.get("state"), final_state=initial.get("state"),
                    reason=initial.get("reason_code"), independent_replay=False, target_fingerprint=None)
    review = e.approve(initial["query_worksheet"])
    entry = dispatch.prepare_reader(s, "q1", query_review=review)
    raw = fact_candidate(entry, variant)

    options = dict(query_review=review, candidate=raw, request_sha256=entry["request_sha256"])
    plan = dispatch.inspect_methods(s, "q1", **options)
    result = e.execute(plan) if plan.get("state") == "REVIEW_REQUIRED" else plan
    write_json(folder / "fact_candidate.json", raw)
    write_json(folder / "plan.json", plan)
    write_json(folder / "result.json", result)
    mc = result.get("mathematical_claim") or {}
    return dict(variant=variant, plan_state=plan.get("state"), final_state=result.get("state"),
                reason=result.get("reason_code"), independent_replay=result.get("independent_replay"),
                target_fingerprint=mc.get("target_fingerprint"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["original", "missing_condition", "changed_target", "all"], default="all")
    from . import reference_fixture
    reference_fixture.arguments(parser)
    args = parser.parse_args(argv)
    global OUT
    OUT = reference_fixture.output(args, ROOT)
    names = ["original", "missing_condition", "changed_target"] if args.variant == "all" else [args.variant]
    rows = [run_variant(n) for n in names]
    summary = dict(evidence_kind="HAND_AUTHORED_REFERENCE_FIXTURE", automatic_business_reading=False,
                   api_calls=0, synthetic_reviews=True, rows=rows)
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "SUMMARY.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
