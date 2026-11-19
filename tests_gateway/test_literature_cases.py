"""Integrity checks for the task-2 literature case library.

These tests do not run identification. They protect the public/research-only
split, registry completeness, holdout count and manifest/file presence.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evaluation" / "literature_cases"
FORBIDDEN = {
    "reference.json",
    "paper_extract.md",
    "actual_outputs.json",
    "run_record.md",
    "review_teacher.md",
}


def load_registry():
    return json.loads((CASES / "registry.json").read_text(encoding="utf8"))


class LiteratureCaseLibraryTest(unittest.TestCase):
    def test_registry_has_unique_cases(self):
        registry = load_registry()
        ids = [c["case_id"] for c in registry["cases"]]
        self.assertEqual(len(ids), 21)
        self.assertEqual(len(set(ids)), 21)

    def test_public_has_no_reference_like_files(self):
        for case in load_registry()["cases"]:
            public = ROOT / case["public_directory"]
            self.assertTrue(public.is_dir(), public)
            for path in public.rglob("*"):
                if path.is_file():
                    self.assertNotIn(path.name, FORBIDDEN, path)

    def test_each_variant_has_manifest_and_supporting_files(self):
        for case in load_registry()["cases"]:
            public = ROOT / case["public_directory"]
            for variant in case["variants"]:
                folder = public / variant["name"]
                manifest = folder / "submission_manifest.json"
                self.assertTrue(manifest.is_file(), manifest)
                value = json.loads(manifest.read_text(encoding="utf8"))
                self.assertEqual(value["case_id"], case["case_id"])
                self.assertEqual(value["variant"], variant["name"])
                for name in value.get("supporting_files", []):
                    self.assertTrue((folder / name).is_file(), folder / name)

    def test_holdouts_stay_four_and_cover_all_families(self):
        # 案例库从 12 个扩到 21 个：09-17 是补充情境，都做了完整结构化运行并已入库，
        # 不宜倒签成 holdout；holdout 仍是原来的 4 个，覆盖三个能力族（网络两题）。
        cases = load_registry()["cases"]
        held = [c for c in cases if c.get("heldout")]
        self.assertEqual(len(held), 4)
        self.assertEqual({c["family"] for c in held}, {"NETWORK", "IV", "DAG"})

    def test_benchmark_has_63_public_rows_and_no_expected_status(self):
        rows = [
            json.loads(line)
            for line in (CASES / "benchmark" / "cases.jsonl").read_text(encoding="utf8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(rows), 63)
        self.assertTrue(all("expected_status" not in row for row in rows))
        self.assertTrue(all("reference_file" not in row for row in rows))

    def test_benchmark_references_are_isolated_and_match_holdouts(self):
        rows = [
            json.loads(line)
            for line in (CASES / "research_only" / "benchmark" / "references.jsonl").read_text(encoding="utf8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(rows), 63)
        held = {(r["case_id"], r["variant"]) for r in rows if r["holdout"]}
        self.assertEqual(len(held), 12)  # 4 held-out cases x 3 variants

    def test_benchmark_matches_registry_status_and_holdout(self):
        registry = load_registry()
        expected = {
            (c["case_id"], v["name"]): (v["expected_status"], bool(c["heldout"]))
            for c in registry["cases"] for v in c["variants"]
        }
        refs = [
            json.loads(line)
            for line in (CASES / "research_only" / "benchmark" / "references.jsonl").read_text(encoding="utf8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(refs), 63)
        for row in refs:
            key = (row["case_id"], row["variant"])
            self.assertEqual((row["expected_status"], bool(row["holdout"])), expected[key], key)

    def test_benchmark_public_files_exist(self):
        rows = [
            json.loads(line)
            for line in (CASES / "benchmark" / "cases.jsonl").read_text(encoding="utf8").splitlines()
            if line.strip()
        ]
        for row in rows:
            for name in row["files"]:
                self.assertTrue((ROOT / name).is_file(), name)

    def test_public_manifest_holdout_matches_registry(self):
        for case in load_registry()["cases"]:
            for variant in case["variants"]:
                manifest = json.loads(
                    (ROOT / case["public_directory"] / variant["name"] / "submission_manifest.json").read_text(encoding="utf8")
                )
                self.assertEqual(bool(manifest.get("heldout")), bool(case["heldout"]), case["case_id"])

    def test_each_case_has_reference_and_review(self):
        for case in load_registry()["cases"]:
            research = ROOT / case["research_directory"]
            self.assertTrue((research / "reference.json").is_file(), research)
            self.assertTrue((research / "run_record.md").is_file(), research)
            self.assertTrue((research / "review_teacher.md").is_file(), research)

    def test_public_manifests_do_not_mark_unrun_as_actual(self):
        for case in load_registry()["cases"]:
            for variant in case["variants"]:
                if variant.get("actual_status") == "NOT_RUN":
                    manifest = ROOT / case["public_directory"] / variant["name"] / "submission_manifest.json"
                    text = manifest.read_text(encoding="utf8")
                    self.assertNotIn("POINT", text)
                    self.assertNotIn("PARTIAL", text)
                    self.assertNotIn("UNSUPPORTED", text)

    def _attachment_changed(self, original: Path, variant: Path) -> bool:
        ignored = {"business_question.md", "submission_manifest.json", "data_dictionary.md"}
        names = {p.name for p in original.iterdir() if p.is_file()} & {
            p.name for p in variant.iterdir() if p.is_file()
        }
        for name in names - ignored:
            a, b = original / name, variant / name
            if a.is_file() and b.is_file() and a.read_bytes() != b.read_bytes():
                return True
        return False

    def test_changed_variants_change_question_or_attachment(self):
        for case in load_registry()["cases"]:
            public = ROOT / case["public_directory"]
            original = public / "original"
            changed = public / "changed_target"
            base = (original / "business_question.md").read_text(encoding="utf8")
            text = (changed / "business_question.md").read_text(encoding="utf8")
            self.assertTrue(
                base.strip() != text.strip() or self._attachment_changed(original, changed),
                f"{case['case_id']} changed variant did not change question or attachment",
            )

    def test_missing_variants_change_at_least_one_attachment(self):
        for case in load_registry()["cases"]:
            public = ROOT / case["public_directory"]
            self.assertTrue(
                self._attachment_changed(public / "original", public / "missing_condition"),
                f"{case['case_id']} missing variant changed only the question",
            )


if __name__ == "__main__":
    unittest.main()
