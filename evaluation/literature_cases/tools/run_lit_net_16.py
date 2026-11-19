"""Run LIT-NET-16 (six-team chain, bounded PARTIAL) through the bounded entry.

No LLM call. The case is a project-built finite mean model; Imbens & Manski
(2004) is background for the identification region [mu*p, mu*p+(1-p)], not the
source of the numeric [1/6, 5/6] interval.

Public-side files follow the LIT-NET-03 bounded-family format (11 files per
variant, LF line endings).
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from cfm_id import business_dispatch as dispatch, business_intake as intake
from cfm_id_llm.schemas import (BusinessCase, SourceDocument, SemanticClaim,
                                TargetDraft, UnitsVariablesDraft, StructureDraft,
                                DraftProblemSpec)
from cfm_id_llm.quality import BusinessInquiryV010, MultiQueryDraftV010, QuerySemanticsV010
from cfm_id_llm.network_policy_reading import reference_catalog, VERSION
from examples.network_dispatch_reference import approval_records
from examples.business_dispatch_reference import approve


ROOT = Path(__file__).resolve().parents[3]
CASE = ROOT / "evaluation" / "literature_cases" / "public" / "LIT-NET-16"
OUT = None  # Explicit new destination required; never overwrite submitted evidence.

NODES = ["团队1", "团队2", "团队3", "团队4", "团队5", "团队6"]
EDGES = [["团队1", "团队2"], ["团队2", "团队3"], ["团队3", "团队4"],
         ["团队4", "团队5"], ["团队5", "团队6"]]
QUOTA = 2

KNOWN = [NODES[0], NODES[-1]]   # chain endpoints revealed by the pilot
MISSING = NODES[1:-1]           # interior teams; full-exposure cell never occurs

Q_ORIGINAL = ("如果这6个团队都启用练习计划，评价全部这些团队、每个团队权重相同，"
              "平均完成率能否由现有总体信息唯一确定？")
Q_CHANGED = ("如果这6个团队都启用练习计划，只评价试点数据里已知完成均值的团队1和团队6、"
             "每个团队权重相同，平均完成率能否由现有总体信息唯一确定？")


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf8")


def docs(missing_scope: bool = False, question: str = Q_ORIGINAL) -> dict:
    d = {}
    d["study"] = ("考核周共有6个团队参与练习计划推广，名单为" + "、".join(NODES) +
                  "。每个团队启用练习计划记1、不启用记0；结果是该团队在考核周内是否完成全部练习，"
                  "完成记1、未完成记0。")
    d["network"] = ("协作网络为固定的处理前简单无向网络，完整边为" +
                    "、".join(a + "—" + b for a, b in EDGES) + "，没有其他边。")
    d["assignment"] = "原试点每轮均匀随机抽取恰好2个团队启用练习计划；所有同人数名单等概率。"
    d["science"] = ("研究明确采用：已知上述完整分配律；完整处理向量与所有团队在所有完整安排下的潜在结果独立；"
                    "一致性，即观察结果等于实际安排下的潜在结果；处理前固定网络；所需条件一阶矩有限。")
    d["information"] = ("以下是季度末按试点整理出的精确总体条件均值，不是有限样本估计：\n" + "\n".join(
        f"{n}，自身处理=1、同伴暴露=1时，考核周完成全部练习的总体条件均值=1/2。" for n in KNOWN))
    d["exposure"] = "同伴暴露定义为协作邻居中严格超过一半启用练习计划时为1，否则为0；平票为0，孤立节点为0。"
    d["sufficiency"] = ("研究另行拟采用：对全部团队、所有完整二元安排，每个团队的潜在结果均值只依赖自身处理与上述同伴暴露。")
    d["bounds"] = ("界限与上文研究背景相同，对每个团队、每一种完整二元安排均成立，限制潜在结果均值。"
                   "结果定义为考核周内完成全部练习记1、未完成记0；单位为0/1指标，期间为考核周。\n" +
                   "\n".join(n + "的下界为0，上界为1。" for n in NODES))
    d["complete_model"] = ("研究暂未确认是否还有其他总体信息或耦合条件。" if missing_scope else
        "本研究明确约定：总体信息只有以上逐项列出的精确总体均值，不包含完整联合分布、其他总体信息或额外聚合均值；"
        "除前述随机化、一致性、固定网络、有限矩、全安排均值暴露充分性以及上述界限外，没有跨团队、跨情境的额外耦合限制。")
    return d


def make_business(missing_scope: bool = False, question: str = Q_ORIGINAL):
    d = docs(missing_scope=missing_scope, question=question)
    business = BusinessCase(case_id="network_D2_6_2_bounded_partial", business_question=question,
                            sources=[SourceDocument(source_id=k, text=v) for k, v in d.items()])
    cells = [dict(node=n, own=1, exposure=1, value="1/2") for n in KNOWN]
    return business, cells, d


def intake_mock(business: BusinessCase, d: dict):
    def claim(text, source):
        return SemanticClaim(value=text, basis="EXPLICIT_TEXT",
                             evidence=[dict(source_id=source, quote=text)])
    goal = claim(business.business_question, "business_question")
    target = TargetDraft(kind="FIXED_POLICY_VALUE", description=goal)
    shared = DraftProblemSpec(target=target, units_variables=UnitsVariablesDraft(
        analysis_unit=claim(d["study"], "study"),
        treatment=claim("启用练习计划", "study"),
        outcome=claim("考核周内是否完成全部练习", "study")),
        structure=StructureDraft(unit_network=claim(d["network"], "network")))
    query = BusinessInquiryV010(query_id="q1", business_goal=goal, target=target,
        semantics=QuerySemanticsV010(target_population=goal, intervention=goal,
                                     policy_assignment=goal, aggregation=goal))
    s = intake.start(business, reading_format="canonical", fact_format="short_refs")
    return intake.receive_candidate(s, MultiQueryDraftV010(
        shared_draft=shared, primary_query_id="q1", queries=[query]).model_dump(mode="json"),
        request_sha256=s.request_sha256)


def candidate(entry, population=None, missing_scope: bool = False):
    refs = reference_catalog(entry["bundle"], binding=entry["fact_binding_sha256"])
    def ids(doc):
        return [k for k, r in refs["aliases"].items() if r["doc_id"] == doc]
    pop = list(population) if population else list(NODES)
    cells = [dict(node=n, own=1, exposure=1, value="1/2") for n in KNOWN]
    raw = dict(version=VERSION, reference_context=refs["context"],
        study=dict(nodes=list(NODES), edges=[list(e) for e in EDGES], graph_kind="SIMPLE_UNDIRECTED",
            edge_list_complete=True, treatment="启用练习计划", outcome="考核周内是否完成全部练习",
            outcome_kind="BINARY", context="考核周练习计划推广", source_ids=ids("study") + ids("network")),
        assignment=dict(kind="UNIFORM_FIXED_QUOTA", probabilities=None, fixed_count=QUOTA,
            source_ids=ids("assignment")),
        target=dict(kind="FIXED_POLICY_MEAN", assignment={x: 1 for x in NODES}, population=pop,
            aggregation="EQUAL_MEAN", source_ids=ids("__question__")),
        assumptions={k: dict(value=True, source_ids=ids("science")) for k in (
            "known_assignment_law", "full_vector_randomization", "consistency",
            "fixed_pretreatment_network", "finite_conditional_first_moments")},
        exposure=dict(kind="STRICT_MAJORITY_TIES_LOW", source_ids=ids("exposure")),
        mean_sufficiency=dict(value=True, scope="ALL_BINARY_ASSIGNMENTS", covered_nodes=list(NODES),
            source_ids=ids("sufficiency")),
        information=[dict(operator="NODE_SIGNATURE_MEANS", availability="EXACT_POPULATION_VALUE",
            outcome_nodes=list(KNOWN), assignment_cells=[], signature_cells=cells,
            source_ids=ids("information"))],
        additional_restrictions=[], unresolved=[])
    raw["bounded_model"] = dict(source_ids=ids("bounds"), bounds_kind="CONDITIONAL_MEAN",
        bounds_scope="ALL_BINARY_ASSIGNMENTS_CONDITIONAL_ON_STUDY_CONTEXT",
        outcome_definition="考核周内完成全部练习记1、未完成记0", outcome_unit="0/1指标", outcome_period="考核周",
        bounds=[dict(node=n, lower="0", upper="1", source_ids=ids("bounds")) for n in NODES],
        listed_means_are_complete_information=dict(value=None if missing_scope else True,
            source_ids=ids("complete_model")),
        no_additional_coupling_constraints=dict(value=None if missing_scope else True,
            source_ids=ids("complete_model")))
    return raw


def write_public(variant: str, case: BusinessCase, cells: list[dict]) -> None:
    folder = CASE / variant
    folder.mkdir(parents=True, exist_ok=True)
    docs_by_id = {s.source_id: s.text for s in case.sources}
    (folder / "business_question.md").write_text(case.business_question, encoding="utf8")
    protocol = "\n\n".join(docs_by_id[k] for k in ("study", "network", "assignment", "exposure", "science"))
    (folder / "study_protocol.md").write_text(protocol, encoding="utf8")
    (folder / "information.md").write_text(docs_by_id["information"], encoding="utf8")
    (folder / "bounds.md").write_text(docs_by_id["bounds"], encoding="utf8")
    model = "\n\n".join(docs_by_id[k] for k in ("sufficiency", "complete_model") if k in docs_by_id)
    (folder / "model.md").write_text(model, encoding="utf8")
    (folder / "data_dictionary.md").write_text(
        "# 数据字典\n\n"
        "| 字段 | 含义 |\n|---|---|\n"
        "| `unit_id` | 团队编号：团队1–团队6 |\n"
        "| `unit_a`, `unit_b` | 无向协作边 |\n"
        "| `quota` | 原试点每轮均匀抽取的固定名额 |\n\n"
        "结果：考核周内是否完成全部练习，完成记 1、未完成记 0。\n"
        "同伴暴露：协作邻居中严格超过一半启用练习计划为 1，否则为 0；平票和孤立点为 0。\n"
        "试点只揭示两个端点在「自身启用、同伴暴露=1」情形下的均值：端点与唯一邻居同时启用恰好用满 2 个名额；"
        "内部团队出现同一情形需要 3 个名额，试点给不出。\n",
        encoding="utf8")
    with (folder / "units.csv").open("w", newline="", encoding="utf8") as fh:
        w = csv.writer(fh); w.writerow(["unit_id"]); w.writerows([[n] for n in NODES])
    with (folder / "network_edges.csv").open("w", newline="", encoding="utf8") as fh:
        w = csv.writer(fh); w.writerow(["unit_a", "unit_b"]); w.writerows(EDGES)
    with (folder / "design.csv").open("w", newline="", encoding="utf8") as fh:
        w = csv.writer(fh); w.writerow(["design", "quota"]); w.writerow(["UNIFORM_FIXED_QUOTA", QUOTA])
    write_json(folder / "information_cells.json", cells)
    write_json(folder / "submission_manifest.json", {
        "case_id": "LIT-NET-16",
        "variant": variant,
        "paper_id": "imbens_manski2004_confidence_intervals",
        "title": "六团队练习计划推广：平均完成率能确定到什么范围？",
        "synthetic": True,
        "gold_oracle_location": "OUTSIDE_PUBLIC_CASE_DIRECTORY",
        "llm_access_scope": "PUBLIC_CASE_FILES_ONLY",
        "business_question_file": "business_question.md",
        "supporting_files": ["study_protocol.md", "information.md", "bounds.md", "model.md",
                             "data_dictionary.md", "units.csv", "network_edges.csv", "design.csv",
                             "information_cells.json"],
        "heldout": False,
        "adapted": True,
        "adaptation_note": "场景改编自 Imbens 与 Manski (2004) 部分识别置信区间框架下的项目推广评估；"
                           "六个团队、试点与全面推广两套安排、完成率均值与区间均为项目自建",
        "notes": "Econometrica 改编：合成业务材料，改编自 Imbens 与 Manski (2004) 的部分识别置信区间框架；"
                 "项目自建有限均值模型，不是论文的数值答案。公式背景取自其第 3 节（p. 1847）。",
        "network_upload": {
            "nodes_file": "units.csv",
            "edges_file": "network_edges.csv",
            "declaration": {
                "kind": "UNDIRECTED",
                "completeness": "COMPLETE",
                "description": "协作网络为固定的处理前简单无向网络，完整边为团队1—团队2、团队2—团队3、"
                               "团队3—团队4、团队4—团队5、团队5—团队6，没有其他边。",
            },
            "declaration_source": {
                "file": "study_protocol.md",
                "quote": "协作网络为固定的处理前简单无向网络，完整边为团队1—团队2、团队2—团队3、"
                         "团队3—团队4、团队4—团队5、团队5—团队6，没有其他边。",
            },
        },
    })


def run_variant(variant: str, population=None, **kwargs) -> dict:
    if OUT is None:
        raise ValueError("REFERENCE_FIXTURE_OUTPUT_REQUIRED")
    case, cells, d = make_business(**kwargs)
    s = intake_mock(case, d)
    review = approve(dispatch.prepare_reader(s, "q1")["query_worksheet"])
    entry = dispatch.prepare_reader(s, "q1", query_review=review)
    raw = candidate(entry, population=population, missing_scope=kwargs.get("missing_scope", False))
    options = dict(query_review=review, candidate=raw, request_sha256=entry["request_sha256"])
    plan = dispatch.inspect_methods(s, "q1", **options)
    if plan["state"] == "REVIEW_REQUIRED":
        result = dispatch.execute(s, "q1", **options, **approval_records(plan))
    else:
        result = plan
    folder = OUT / variant
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "business.json", case.model_dump(mode="json"))
    write_json(folder / "plan.json", plan)
    write_json(folder / "result.json", result)
    mc = result.get("mathematical_claim") or {}
    return dict(
        variant=variant,
        plan_state=plan.get("state"),
        final_state=result.get("state"),
        reason=result.get("reason_code"),
        independent_replay=result.get("independent_replay"),
        interval=mc.get("interval"),
        sharp=mc.get("sharp"),
        width=mc.get("width"),
        target_sha256=mc.get("target_sha256"),
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["original", "missing_condition", "changed_target", "all"], default="all")
    parser.add_argument("--write-public", action="store_true",
                        help="Generate the 11 public-side files per variant, then exit.")
    parser.add_argument("--reference-fixture", action="store_true",
                        help="Run a hand-authored reference, NOT a business/LLM test.")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.write_public:
        payloads = {
            "original": dict(),
            "missing_condition": dict(missing_scope=True),
            "changed_target": dict(question=Q_CHANGED),
        }
        for name, kw in payloads.items():
            case, cells, _ = make_business(**kw)
            write_public(name, case, cells)
        print(json.dumps({"written": sorted(payloads)}, ensure_ascii=False))
        return 0
    global OUT
    from . import reference_fixture
    OUT = reference_fixture.output(args, ROOT)
    data = {
        "original": {},
        "missing_condition": {"missing_scope": True},
        "changed_target": {"population": KNOWN, "question": Q_CHANGED},
    }
    names = list(data) if args.variant == "all" else [args.variant]
    rows = [run_variant(n, **data[n]) for n in names]
    summary = dict(evidence_kind="HAND_AUTHORED_REFERENCE_FIXTURE", automatic_business_reading=False,
                   api_calls=0, synthetic_reviews=True, rows=rows)
    write_json(OUT / "SUMMARY.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
