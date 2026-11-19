"""Run LIT-NET-11 group information-coverage policy mean through the extended entry.

Four meeting groups of ten firms each, forty firms in total. Groups one and two are
competitor groups; groups three and four are mixed-industry groups. Two complete
information lists (five firms per group, eight firms per group) with known
probabilities. Group members exchange information, so the outcome of a firm depends on
whether at least one group member was informed; the same channel is weakened inside
competitor groups. No LLM call. The A0 draft and the fact candidate are hand-authored
reference fixtures, not a measurement of any model's reading.
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
CASE = ROOT / "evaluation" / "literature_cases" / "public" / "LIT-NET-11"
OUT = None
NODES = [f"企{i}" for i in range(1, 41)]
GROUPS = [NODES[0:10], NODES[10:20], NODES[20:30], NODES[30:40]]
# Within a meeting group every pair of firms can exchange information.
EDGES = [[a, b] for g in GROUPS for i, a in enumerate(g) for b in g[i + 1:]]
PLAN_A = {n: 1 for g in GROUPS for n in g[:5]}
PLAN_B = {n: 1 for g in GROUPS for n in g[:8]}
COMPETITOR_GROUPS = GROUPS[0] + GROUPS[1]

QUOTES = {
    "original": {
        "goal": "四十家企业的平均申请概率在两种投放方案各一半机会时是多少",
        "population": "四十家企业",
        "aggregation": "每家等权",
        "policy": "两种投放方案各以一半概率被采用，这就是全部候选方案",
        "law": "未来政策只含问题中列出的两份完整投放名单，各占 1/2",
    },
    "missing_condition": {
        "goal": "四十家企业的平均申请概率在明年采用其中一种投放方案时是多少",
        "population": "四十家企业",
        "aggregation": "每家等权",
        "policy": "明年会从这两种投放方案里选一种执行",
        "law": "未来只执行一份投放名单，问题没有说明两份方案各自被采用的机会",
    },
    "changed_target": {
        "goal": "这二十家企业的平均申请概率在两种投放方案各一半机会时是多少",
        "population": "二十家同行业企业",
        "aggregation": "每家等权",
        "policy": "两种投放方案各以一半概率被采用，这就是全部候选方案",
        "law": "未来政策只含问题中列出的两份完整投放名单，各占 1/2",
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
            analysis_unit=claim("企业是研究单位", "proposal"),
            treatment=claim("被直接告知记 1", "proposal"),
            outcome=claim("是否申请补助", "proposal"),
        ),
        structure=StructureDraft(unit_network=claim("同一会议组内企业之间存在信息交流", "proposal")),
        information_design=InformationDesignDraft(
            assignment_family=AssignmentFamily.CLUSTER_RANDOMIZATION,
            assignment_law=claim(q["law"], "proposal"),
            population_information_level=PopulationInformationLevel.NODE_FULL_LAW,
            population_observable_operator=claim("符号总体分布", "proposal"),
            sample_data_description=claim("不是四十条样本记录", "proposal"),
        ),
    )
    sem = QuerySemanticsV010(
        target_population=claim(q["population"], "business_question"),
        intervention=claim(q["policy"], "business_question"),
        comparator=claim("不与某个对照方案相减", "proposal"),
        neighbor_exposure=claim("组内是否至少有一名被告知者", "proposal"),
        aggregation=claim(q["aggregation"], "business_question"),
        time_horizon=claim("评价时点为下一季度", "proposal"),
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
        treatment="被直接告知记1，未被直接告知记0",
        outcome="该企业是否申请补助，申请记1、未申请记0",
        outcome_kind="BINARY",
        context="下一季度；四十家企业分属四个会议组，组内彼此交流，组间不构成邻居",
        source_ids=ids,
    )
    raw["assignment"].update(probabilities={n: "1/2" for n in NODES}, source_ids=ids)
    population = list(COMPETITOR_GROUPS) if variant == "changed_target" else list(NODES)
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
        case_id=f"LIT-NET-11-{variant}",
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
