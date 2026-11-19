"""Real-LLM reading runs for the LIT-NET case bank (LIT-NET-09 to LIT-NET-17).

The model performs the fact-reading step only. It reads the public business
materials through the same wire the web entries use and returns the typed
candidate; that candidate is checked structurally, then confirmed against the
approved reading field by field (network, design, exposure, target, declared
assumptions). Only a confirmed reading is dispatched, and what is dispatched is
the approved reading itself -- the same gate as examples/dag_id_llm_reading.py,
where the model confirms the graph and the solver runs on the reviewed problem.
Notes the model adds beyond the structured fields are recorded, never adopted;
the engine's own policy routes extra restrictions to a separate adapter. The
identification result still comes from the solver and is replayed by the
independent checker; the scientific worksheets are approved by the frozen
reference approvals, and every record discloses that. The model's answer is
never the source of its own approval, and the question is never changed to make
a run succeed.

Per case the record keeps the prompt digest, the first answer, the structural
check, an optional single re-read whose user prompt carries the validator's own
message (form correction only), and the final solver state separately.

Two modes:

- --provider mock (default): a deterministic provider echoes the hand-authored
  alias-form fact candidate from each runner module. This exercises the whole
  chain end to end without network access and must reproduce the hand-authored
  results.
- --provider online: one OpenAI-compatible call per case variant. Needs
  CFM_ID_LLM_API_KEY (or OPENAI_API_KEY); CFM_ID_LLM_BASE_URL selects the
  gateway (default follows examples/dag_id_llm_reading.py); CFM_ID_LLM_MODEL
  skips model discovery.

Records go to outputs/net_llm_reading/ (override with CFM_ID_LLM_SAVE_DIR or
--save-dir). outputs/ is excluded from version control; these are run
products, not deliverables.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
import time
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from cfm_id import business_dispatch as dispatch, business_intake as intake
from cfm_id_llm import network_extended_reading as rd
from cfm_id_llm import network_policy_reading as nw
from cfm_id_bridge.scientific_binding import sha
from cfm_id_llm.providers.base import ProviderError
from cfm_id_llm.schemas import BusinessCase, SourceDocument
from examples.business_dispatch_reference import approve
from examples.network_dispatch_reference import approval_records
from examples import network_extended_reference as ext

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "evaluation" / "literature_cases" / "public"

EXTENDED_CASES = ("09", "10", "11", "12", "13", "14", "15")
BOUNDED_POPULATION = {"16": "KNOWN", "17": "MIDDLE"}
CASE_NUMBERS = EXTENDED_CASES + tuple(BOUNDED_POPULATION)
VARIANTS = ("original", "missing_condition", "changed_target")


def variant_kwargs(case_number: str, variant: str, module) -> dict:
    if variant == "missing_condition":
        return dict(missing_scope=True)
    if variant == "changed_target":
        population = getattr(module, BOUNDED_POPULATION[case_number])
        return dict(population=population, question=module.Q_CHANGED)
    return {}


def build_state(case_number: str, variant: str, module):
    """Reproduce the hand-authored runners' intake state up to the reader entry."""
    if case_number in EXTENDED_CASES:
        folder = PUBLIC / ("LIT-NET-" + case_number) / variant
        question = (folder / "business_question.md").read_text(encoding="utf8").strip()
        protocol = (folder / "study_protocol.md").read_text(encoding="utf8")
        case = BusinessCase(
            case_id="LIT-NET-{}-{}".format(case_number, variant),
            business_question=question,
            sources=[SourceDocument(source_id="proposal", text=protocol)],
        )
        state = intake.start(case, reading_format="canonical", fact_format="short_refs")
        if case_number == "09":
            draft = module.a0_draft(variant, question, protocol)
        else:
            draft = module.a0_draft(variant)
        state = intake.receive_candidate(state, draft, request_sha256=state.request_sha256)
        return case, state
    kwargs = variant_kwargs(case_number, variant, module)
    business, _cells, docs = module.make_business(
        **{k: v for k, v in kwargs.items() if k in ("missing_scope", "question")})
    state = module.intake_mock(business, docs)
    return business, state


def reference_candidate(case_number: str, variant: str, module, entry) -> dict:
    """The hand-authored alias-form candidate, i.e. the approved reading."""
    if case_number in EXTENDED_CASES:
        return module.fact_candidate(entry, variant)
    kwargs = variant_kwargs(case_number, variant, module)
    return module.candidate(entry, population=kwargs.get("population"),
                            missing_scope=kwargs.get("missing_scope", False))


def mock_reply(case_number: str, variant: str, module, entry) -> str:
    """The approved reading, echoed as the mock model's answer."""
    return json.dumps(reference_candidate(case_number, variant, module, entry),
                      ensure_ascii=False)


# Fields the confirmation gate compares. Free text (treatment/outcome/context
# wording) is recorded but not compared: two faithful readings may phrase it
# differently, and the approved reading is what the solver uses anyway.
COMPARED = (("study", "nodes"), ("study", "edges"), ("study", "graph_kind"),
            ("study", "edge_list_complete"), ("study", "outcome_kind"),
            ("exposure", "kind"),
            ("target", "population"), ("target", "kind"), ("target", "operation"),
            ("target", "aggregation"), ("target", "averaging"),
            ("regime", "kind"), ("conditioning", "kind"))

# The assignment law is compared through target.components when the case is a
# finite policy: there the two approved arrangements and their weights are the
# design, and the assignment-kind label is only a tag the engine needs. Without
# components the label itself is the design and is compared.
ASSIGNMENT_FIELDS = (("assignment", "kind"), ("assignment", "probabilities"),
                     ("assignment", "fixed_count"))

_TRAILING_INTEGER = re.compile(r"(\d+)\s*$")


def canonical_node(label) -> str:
    """Compare node labels by their trailing number: 户1 and 1 name the same unit."""
    match = _TRAILING_INTEGER.search(str(label))
    return "#" + match.group(1) if match else str(label)


def _field(facts: dict, path) -> object:
    current = facts
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _normalised(path, value):
    name = path[-1]
    if name in ("nodes", "population") and isinstance(value, list):
        return sorted(canonical_node(v) for v in value)
    if name == "edges" and isinstance(value, list):
        return sorted(tuple(sorted((canonical_node(a), canonical_node(b)))) for a, b in value)
    if name == "probabilities" and isinstance(value, list):
        return [round(float(v), 9) if isinstance(v, (int, float)) else v for v in value]
    return value


def _weight(value):
    if isinstance(value, str):
        try:
            return float(Fraction(value))
        except (ValueError, ZeroDivisionError):
            return value
    return float(value) if isinstance(value, (int, float)) else value


def _components(facts: dict):
    target = facts.get("target") or {}
    components = target.get("components")
    return components if isinstance(components, list) and components else None


def _normalised_components(components):
    out = []
    for component in components or []:
        assignment = component.get("assignment") or {}
        cells = tuple(sorted((canonical_node(k), int(v) if isinstance(v, int) else v)
                             for k, v in assignment.items()))
        out.append((cells, _weight(component.get("weight"))))
    return sorted(out)


def _undeclared(value) -> bool:
    """A field the reading left open; the engine treats this as a question, not a conflict."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() in ("", "UNKNOWN")
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def confirm_reading(facts: dict, approved: dict):
    """Confirm the model's reading against the approved one.

    Only a contradiction -- both sides declaring different values -- blocks. A
    field the model left open is recorded as not declared: the engine's own
    missing-input path would ask about it, and the frozen reference approvals,
    not the model, are the scientific authority here. Content the model adds
    where the approved reading has none is recorded as extra and never adopted.
    """
    contradictions, not_declared, extra, compared = [], [], [], []
    components = _components(facts) or _components(approved)
    paths = list(COMPARED) + ([] if components else list(ASSIGNMENT_FIELDS))
    for path in paths:
        compared.append(".".join(path))
        mine, theirs = _normalised(path, _field(facts, path)), _normalised(path, _field(approved, path))
        if _undeclared(mine) and _undeclared(theirs):
            continue
        if _undeclared(theirs):
            extra.append({"field": ".".join(path), "reading": mine})
        elif _undeclared(mine):
            not_declared.append({"field": ".".join(path), "approved": theirs})
        elif mine != theirs:
            contradictions.append({"field": ".".join(path), "reading": mine, "approved": theirs})
    if components is not None:
        compared.append("target.components")
        mine, theirs = _normalised_components(_components(facts)), _normalised_components(_components(approved))
        if not mine and not theirs:
            pass
        elif not theirs:
            extra.append({"field": "target.components", "reading": _components(facts)})
        elif not mine:
            not_declared.append({"field": "target.components",
                                 "approved": _components(approved)})
        elif mine != theirs:
            contradictions.append({"field": "target.components",
                                   "reading": _components(facts),
                                   "approved": _components(approved)})
    compared.append("assumptions.*")
    approved_assumptions = approved.get("assumptions") or {}
    declared = facts.get("assumptions") or {}
    for name, spec in approved_assumptions.items():
        want = spec.get("value") if isinstance(spec, dict) else spec
        got = declared.get(name)
        have = got.get("value") if isinstance(got, dict) else None
        if _undeclared(have) and _undeclared(want):
            continue
        if _undeclared(want):
            extra.append({"field": "assumptions." + name, "reading": have})
        elif _undeclared(have):
            not_declared.append({"field": "assumptions." + name, "approved": want})
        elif have != want:
            contradictions.append({"field": "assumptions." + name,
                                   "reading": have, "approved": want})
    return (not contradictions), contradictions, not_declared, extra, compared


class MockProvider:
    """Deterministic offline stand-in; never certified, always disclosed."""

    def __init__(self) -> None:
        self.name = "mock:hand-authored-candidate-echo"
        self.base_url = "offline"
        self.model = "hand-authored-fixture"
        self.api_key = None
        self.last_diagnostics = dict(mock=True)
        self._pending = None

    def stage(self, payload: str) -> None:
        self._pending = payload

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        if self._pending is None:
            raise RuntimeError("mock reply not staged")
        payload, self._pending = self._pending, None
        return json.loads(payload)


def available_models(base_url: str, key: str):
    import urllib.request
    request = urllib.request.Request(
        base_url.rstrip("/") + "/models", headers={"Authorization": "Bearer " + key})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [entry["id"] for entry in payload.get("data", []) if entry.get("id")]


def online_provider():
    """Build the configured provider, or explain what is missing and stop."""
    key = os.getenv("CFM_ID_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        print("CFM_ID_LLM_API_KEY is not set.")
        print("Set it in your own shell, then rerun with --provider online:")
        print("   export CFM_ID_LLM_API_KEY=<your token>")
        print("   export CFM_ID_LLM_BASE_URL=https://api.deepseek.com/v1   (any OpenAI-compatible endpoint)")
        print("   export CFM_ID_LLM_MODEL=deepseek-chat   (skips model discovery)")
        print("Nothing was sent anywhere.")
        return None
    base_url = os.getenv("CFM_ID_LLM_BASE_URL", "https://newapi.sufe.edu.cn/v1")
    model = os.getenv("CFM_ID_LLM_MODEL")
    if not model:
        try:
            served = available_models(base_url, key)
        except Exception as error:
            print("Could not list models at {}: {}".format(base_url, error))
            print("Set CFM_ID_LLM_MODEL explicitly and rerun.")
            return None
        if not served:
            print("The gateway returned no model list; set CFM_ID_LLM_MODEL explicitly.")
            return None
        model = served[0]
        print("gateway serves {} models; using {}".format(len(served), model))
        print("available:", ", ".join(served[:10]))
    from cfm_id_llm.providers.openai_chat import OpenAICompatibleChatProvider
    print("endpoint : {} | model: {}".format(base_url, model))
    timeout = float(os.getenv("CFM_ID_LLM_TIMEOUT", "180"))
    json_mode = os.getenv("CFM_ID_LLM_JSON_MODE", "1").lower() not in ("0", "false", "no")
    return OpenAICompatibleChatProvider(model=model, base_url=base_url, timeout=timeout,
                                        json_mode=json_mode)


def diagnostics(provider) -> dict:
    observed = getattr(provider, "last_diagnostics", None)
    return dict(observed) if isinstance(observed, dict) else {}


def redact(text: str, provider) -> str:
    key = getattr(provider, "api_key", None)
    if isinstance(key, str) and key and key in text:
        text = text.replace(key, "***")
    return text[:600]


def wire_request(entry, case_number: str) -> dict:
    if case_number in EXTENDED_CASES:
        return rd.make_request(entry["bundle"], binding=entry["fact_binding_sha256"],
                               family=rd.MIX)
    return nw.make_request(entry["bundle"], binding=entry["fact_binding_sha256"])


def wire_parse(entry, case_number: str, raw: dict) -> dict:
    if case_number in EXTENDED_CASES:
        return rd.parse(entry["bundle"], raw, binding=entry["fact_binding_sha256"],
                        family=rd.MIX)
    return nw.parse(entry["bundle"], raw, binding=entry["fact_binding_sha256"])


def run_one(provider, case_number: str, variant: str, module) -> dict:
    """One case variant: first answer, structural check, optional re-read, final result."""
    record = {
        "case_id": "LIT-NET-" + case_number,
        "variant": variant,
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "provider": {"name": provider.name, "base_url": provider.base_url,
                     "model": provider.model},
        "reading_source": ("real_llm" if provider.name.startswith("openai-chat-compatible")
                           else "mock_echo_of_hand_authored_candidate"),
        "reviews": {"authority": "FROZEN_REFERENCE_APPROVALS",
                    "note": "Scientific worksheets are approved by the frozen reference "
                            "approvals, exactly as in the hand-authored runners; disclosed here. "
                            "The model's answer is never the source of its own approval."},
        "api_calls": 0,
    }
    case, state = build_state(case_number, variant, module)
    record["question"] = case.business_question
    initial = dispatch.prepare_reader(state, "q1")
    if not initial.get("query_worksheet"):
        record["observed"] = initial.get("state")
        record["outcome"] = dict(state=initial.get("state"), reason_code=initial.get("reason_code"))
        return record
    review = approve(initial["query_worksheet"])
    entry = dispatch.prepare_reader(state, "q1", query_review=review)
    request = wire_request(entry, case_number)
    record["prompt"] = {
        "contract": ("network-extended-reading" if case_number in EXTENDED_CASES
                     else "network-policy-reading-bounded"),
        "system_sha256": sha(request["system"]),
        "system_characters": len(request["system"]),
        "user_characters": len(request["user"])}

    final_raw = None
    for pass_index in (0, 1):
        label = "first answer" if pass_index == 0 else "re-read"
        print("-- pass  :", label)
        if pass_index == 0:
            record["reread"] = {"performed": False,
                                "reason": "first answer used as-is; a re-read is a separate call"}
        else:
            feedback = ("你上一次的回答没有通过结构检查：{}。"
                        "请重新阅读材料原文，修正该问题后给出完整回答；"
                        "只有材料本身确实没有依据时才维持原判。".format(attempt))
            record["reread"] = {"performed": True, "trigger": attempt, "feedback": feedback}
        if isinstance(provider, MockProvider):
            provider.stage(mock_reply(case_number, variant, module, entry))
        user_prompt = request["user"]
        if pass_index == 1:
            user_prompt = user_prompt + "\n\n" + feedback
        started = time.monotonic()
        wire, provider_error = None, None
        for call_index in range(2):
            try:
                wire = provider.generate_json(system_prompt=request["system"],
                                              user_prompt=user_prompt)
            except ProviderError as error:
                provider_error = error
                receipt = dict(error.diagnostics or {})
                # An empty body means no answer arrived at all (connection reset,
                # gateway hiccup): retry the same request once. A body that did
                # arrive but failed to parse is an answer and is never re-asked.
                if receipt.get("response_bytes") == 0 and call_index == 0:
                    record.setdefault("transport_retries", []).append(
                        {"code": error.code or "UNSPECIFIED", "diagnostics": receipt})
                    print("provider : EMPTY BODY", error.code, "| retrying the same request once")
                    time.sleep(1.0)
                    continue
                break
            provider_error = None
            break
        if wire is None:
            print("provider : FAILED", provider_error.code or "UNSPECIFIED", "|", provider_error)
            record["answer_seconds"] = round(time.monotonic() - started, 3)
            record["provider_error"] = {"code": provider_error.code or "UNSPECIFIED",
                                        "message": redact(str(provider_error), provider),
                                        "raised_diagnostics": dict(provider_error.diagnostics or {})}
            record["transport"] = diagnostics(provider)
            record["observed"] = "PROVIDER_ERROR"
            record["outcome"] = dict(state="PROVIDER_ERROR",
                                     reason_code=provider_error.code or "UNSPECIFIED")
            return record
        record["api_calls"] += 1
        record["answer_seconds"] = round(time.monotonic() - started, 3)
        record["first_answer" if pass_index == 0 else "reread_answer"] = wire
        record["transport"] = diagnostics(provider)
        print("answered : {:.1f}s, {} characters".format(
            record["answer_seconds"], len(json.dumps(wire, ensure_ascii=False))))
        try:
            parsed = wire_parse(entry, case_number, wire)
        except Exception as error:  # structural check; its message drives the re-read
            attempt = redact(str(error), provider)
            print("reading  : REJECTED", attempt)
            record["reading_rejected"] = attempt
            if pass_index == 1:
                record["observed"] = "READING_REJECTED"
                record["outcome"] = dict(state="READING_REJECTED", reason_code="READING_REJECTED")
                return record
            continue
        binding = parsed.get("reference_binding", {})
        record["parsed_reference_context_sha256"] = binding.get("context_sha256")
        facts = parsed.get("facts") or {}
        approved = reference_candidate(case_number, variant, module, entry)
        confirmed, contradictions, not_declared, extra, compared = confirm_reading(facts, approved)
        record["confirmation"] = {
            "confirmed": confirmed,
            "compared": compared,
            "not_compared": ["study.treatment", "study.outcome", "study.context",
                             "free-text notes"],
            "contradictions": contradictions[:12],
            "not_declared": not_declared[:12],
            "extra": extra[:12]}
        record["declared_notes"] = {
            "additional_restrictions": [n.get("text") for n
                                        in (facts.get("additional_restrictions") or [])
                                        if isinstance(n, dict)],
            "unresolved": [n.get("text") for n in (facts.get("unresolved") or [])
                           if isinstance(n, dict)],
            "adopted": False,
            "reason": ("Recorded, not adopted: the engine routes additional restrictions "
                       "to a separate adapter, and the frozen reference approvals are the "
                       "only scientific approval in this run.")}
        print("confirm  :", "MATCH" if confirmed else "CONTRADICTS",
              "| contradictions:", len(contradictions),
              "| not declared:", len(not_declared), "| extra:", len(extra))
        if not confirmed:
            # The gate stops here: a reading nobody can confirm must not be turned
            # into a designation by the caller filling in the blanks.
            for contradiction in contradictions[:6]:
                print("           ", contradiction["field"],
                      "| reading:", contradiction["reading"],
                      "| approved:", contradiction["approved"])
            record["observed"] = "READING_NOT_CONFIRMED"
            record["outcome"] = dict(state="READING_NOT_CONFIRMED",
                                     reason_code="READING_DIFFERS_FROM_APPROVED_READING")
            return record
        # Only a confirmed reading is dispatched, and what is dispatched is the
        # approved reading itself -- the same gate as examples/dag_id_llm_reading.py.
        final_raw = approved
        break

    options = dict(query_review=review, candidate=final_raw,
                   request_sha256=entry["request_sha256"])
    try:
        plan = dispatch.inspect_methods(state, "q1", **options)
    except Exception as error:
        attempt = redact(str(error), provider)
        print("plan     : REJECTED", attempt)
        record["plan_rejected"] = attempt
        record["observed"] = "PLAN_REJECTED"
        record["outcome"] = dict(state="PLAN_REJECTED", reason_code=None)
        return record
    record["plan_state"] = plan.get("state")
    record["plan_reason"] = plan.get("reason_code")
    if plan.get("state") == "REVIEW_REQUIRED":
        if case_number in EXTENDED_CASES:
            result = ext.execute(plan)
        else:
            result = dispatch.execute(state, "q1", **options, **approval_records(plan))
    else:
        result = plan
    mc = result.get("mathematical_claim") or {}
    record["observed"] = result.get("state")
    record["reason_code"] = result.get("reason_code")
    record["independent_replay"] = result.get("independent_replay")
    record["mathematical_claim"] = {k: mc.get(k) for k in
                                    ("interval", "point", "sharp", "width", "target_fingerprint")
                                    if k in mc}
    record["outcome"] = dict(state=result.get("state"), reason_code=result.get("reason_code"),
                             independent_replay=result.get("independent_replay"))
    return record


def save_directory(cli_override) -> Path:
    override = cli_override or os.getenv("CFM_ID_LLM_SAVE_DIR")
    return Path(override) if override else ROOT / "outputs" / "net_llm_reading"


def main(argv=None) -> int:
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="all",
                        help="all, or a two-digit case number such as 09 or 17")
    parser.add_argument("--variant", default="all", choices=["all", *VARIANTS])
    parser.add_argument("--provider", choices=["mock", "online"], default="mock")
    parser.add_argument("--save-dir", default=None)
    args = parser.parse_args(argv)

    provider = MockProvider() if args.provider == "mock" else online_provider()
    if provider is None:
        return 2

    numbers = list(CASE_NUMBERS)
    if args.case != "all":
        if args.case not in numbers:
            parser.error("--case must be one of: " + ", ".join(numbers))
        numbers = [args.case]

    out = save_directory(args.save_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    for case_number in numbers:
        module = importlib.import_module(
            "evaluation.literature_cases.tools.run_lit_net_" + case_number)
        variants = list(VARIANTS) if args.variant == "all" else [args.variant]
        for variant in variants:
            print("=" * 72)
            print("LIT-NET-{} | {} | {}".format(case_number, variant, provider.name))
            record = run_one(provider, case_number, variant, module)
            path = out / "{}_{}_{}.json".format(record["case_id"], record["variant"],
                                                time.strftime("%H%M%S") + str(len(summary_rows)))
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n",
                            encoding="utf8")
            print("record   :", path)
            summary_rows.append(dict(case_id=record["case_id"], variant=variant,
                                     observed=record.get("observed"),
                                     reason_code=record.get("reason_code"),
                                     confirmed=(record.get("confirmation") or {}).get("confirmed"),
                                     independent_replay=record.get("independent_replay"),
                                     api_calls=record.get("api_calls", 0)))
    summary = dict(
        evidence_kind=("REAL_LLM_READING_RUN" if args.provider == "online"
                       else "MOCK_CHAIN_SELF_CHECK"),
        provider=dict(name=provider.name, base_url=provider.base_url, model=provider.model),
        reviews="FROZEN_REFERENCE_APPROVALS (disclosed per record)",
        api_calls_total=sum(r["api_calls"] for r in summary_rows),
        rows=summary_rows)
    (out / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2,
                                                 default=str) + "\n", encoding="utf8")
    print("=" * 72)
    for row in summary_rows:
        print("{:<12} {:<18} {:<16} replay={}".format(
            row["case_id"], row["variant"], str(row["observed"]), row["independent_replay"]))
    print("api_calls :", summary["api_calls_total"])
    print("records   :", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
