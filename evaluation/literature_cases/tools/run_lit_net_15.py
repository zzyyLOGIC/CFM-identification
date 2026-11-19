"""Run LIT-NET-15 tutoring social-multiplier (Manski 1993 equilibrium) policy mean through the extended entry.

Six students in two classes with within-class reference groups (class A is a complete
graph of four, class B is a pair; no cross-class reference). Two complete tutoring
arrangements with known probabilities. A tutored student gains 4 points directly and
every student gains 0.5 points per point of final class-mean gain, so the answer solves
the social-equilibrium equation (Manski 1993, eqs. (3)-(4)). No LLM call. The A0 draft
and the fact candidate are hand-authored reference fixtures, not a measurement of any
model's reading.
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
CASE = ROOT / "evaluation" / "literature_cases" / "public" / "LIT-NET-15"
OUT = None
NODES = [f"学{i}" for i in range(1, 7)]
CLASS_A = NODES[0:4]
CLASS_B = NODES[4:6]
# Class A is a complete graph (1-2, 1-3, 1-4, 2-3, 2-4, 3-4); class B is a pair (5-6).
EDGES = (
    [["学1", "学2"], ["学1", "学3"], ["学1", "学4"],
     ["学2", "学3"], ["学2", "学4"], ["学3", "学4"]]
    + [["学5", "学6"]]
)
PLAN_A = {"学1": 1, "学2": 1, "学5": 1}
PLAN_B = {"学3": 1, "学6": 1}

QUOTES = {
    "original": {
        "goal": "六名学生成绩相对不推行计划时的平均提高在两种安排各一半机会时是多少",
        "population": "六名学生",
        "aggregation": "每人等权",
        "policy": "两种安排各以一半概率被采用，这就是全部候选方案",
        "law": "未来辅导安排只含问题中列出的两套，各占 1/2",
    },
    "missing_condition": {
        "goal": "六名学生成绩相对不推行计划时的平均提高在明年采用其中一套安排时是多少",
        "population": "六名学生",
        "aggregation": "每人等权",
        "policy": "明年会从这两套安排里选一套执行",
        "law": "未来只执行一套辅导安排，问题没有说明两套安排各自被采用的机会",
    },
    "changed_target": {
        "goal": "学3 成绩相对不推行计划时的平均提高在两种安排各一半机会时是多少",
        "population": "甲班学3",
        "aggregation": "只有他一名学生，权重为 1",
        "policy": "两种安排各以一半概率被采用，这就是全部候选方案",
        "law": "未来辅导安排只含问题中列出的两套，各占 1/2",
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
            analysis_unit=claim("学生是研究单位", "proposal"),
            treatment=claim("受辅导的学生按安排接受辅导", "proposal"),
            outcome=claim("成绩相对不推行计划时的提高，单位为分", "proposal"),
        ),
        structure=StructureDraft(unit_network=claim("同一班内的参照关系覆盖题面列出的甲班六对与乙班一对，班间无参照关系", "proposal")),
        information_design=InformationDesignDraft(
            assignment_family=AssignmentFamily.CLUSTER_RANDOMIZATION,
            assignment_law=claim(q["law"], "proposal"),
            population_information_level=PopulationInformationLevel.NODE_FULL_LAW,
            population_observable_operator=claim("成绩提高的总体分布", "proposal"),
            sample_data_description=claim("不是六条样本记录", "proposal"),
        ),
    )
    sem = QuerySemanticsV010(
        target_population=claim(q["population"], "business_question"),
        intervention=claim(q["policy"], "business_question"),
        comparator=claim("不与某个对照方案相减", "proposal"),
        neighbor_exposure=claim("受辅导者直接提高 4 分、班平均每提高 1 分班里每名学生再提高 0.5 分的规则对每名学生一致适用", "proposal"),
        aggregation=claim(q["aggregation"], "business_question"),
        time_horizon=claim("评价时点为辅导执行后的期末", "proposal"),
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
        treatment="被辅导记1，其余记0",
        outcome="成绩相对不推行计划时的提高，单位为分",
        outcome_kind="CONTINUOUS",
        context="辅导执行后的期末；六名学生分属甲乙两班，甲班四名学生互为参照组，乙班两名学生互为参照组，班间无参照关系",
        source_ids=ids,
    )
    raw["assignment"].update(probabilities={n: "1/2" for n in NODES}, source_ids=ids)
    population = ["学3"] if variant == "changed_target" else list(NODES)
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
        case_id=f"LIT-NET-15-{variant}",
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
