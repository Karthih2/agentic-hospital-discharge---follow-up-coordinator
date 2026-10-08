"""Check the pipeline against sample_data/discharge_template/expected.json.

    python -m scripts.verify_samples            OFFLINE: reference extraction -> real dates + real safety gate
    python -m scripts.verify_samples --live     LIVE: real model (Groq/Claude from .env) -> real dates + gate
    python -m scripts.verify_samples --live 03  only files whose name contains "03"
    python -m scripts.verify_samples --rules    RULES: the no-AI fallback extractor -> real dates + gate

OFFLINE proves the fixed rules (dates, evidence check, safety gate) give the expected status for every line.
LIVE also proves the model extracts every actionable line, copies it exactly, and does not turn diagnoses or
the hospital course into tasks. No database is touched. Exit code 1 if anything fails.
"""
import asyncio
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

from app.pipeline import dates, safety_gate, template
from app.pipeline.orchestrator import build_gate_item, find_span

DIR = Path(__file__).resolve().parents[1] / "sample_data" / "discharge_template"


def norm(s: str) -> str:
    return " ".join((s or "").lower().split()).strip(" .")


def best_match(line: str, candidates: list[str]) -> tuple[int, float]:
    scores = [SequenceMatcher(None, norm(line), norm(c)).ratio() for c in candidates]
    i = max(range(len(scores)), key=scores.__getitem__) if scores else -1
    return i, (scores[i] if scores else 0.0)


def gate(items: list[dict], raw: str, discharge) -> list[tuple[dict, list[dict]]]:
    gi = [build_gate_item(i, raw, discharge) for i in items]
    conf = safety_gate.conflict_flags(gi)
    lines = template.actionable_lines(raw)
    ment = safety_gate.mention_flags(gi, [ln for _, ln in lines])
    out = [(g, safety_gate.run_gate(g) + conf.get(n, []) + ment.get(n, [])) for n, g in enumerate(gi)]
    for line in template.uncovered(lines, [g["source_line"] for g in gi]):  # same coverage rule as the orchestrator
        ghost = {"type": "care_instruction", "title": "Not understood automatically", "source_line": line,
                 "confidence": 0.0, "source_found": True, "due_date": None}
        out.append((ghost, [{"field": "item", "reason_code": "UNCATEGORISED", "note": "line was not extracted"}]))
    return out


def reference_items(case: dict) -> list[dict]:
    return [{"type": e["type"], "source_line": e["source_line"], **e["reference_extraction"]} for e in case["items"]]


async def live_items(raw: str) -> tuple[list[dict], int]:
    from app.pipeline import extraction_agent
    out = await extraction_agent.extract(raw)
    return [i.model_dump() for i in out.items], len(out.rejected)


def report(case: dict, raw: str, extracted: list[dict], live: bool, rejected: int = 0) -> int:
    fails = 0
    discharge = dates.parse_discharge_date(raw)
    want_dd = dates.parse_absolute(case["discharge_date"])
    print(f"\n=== {case['file']}  ({case['patient']})")
    print(f"    {case['purpose']}")
    if discharge != want_dd:
        print(f"  FAIL discharge date {discharge} != {want_dd}")
        fails += 1
    results = gate(extracted, raw, discharge)
    got_lines = [g["source_line"] for g, _ in results]
    used = set()
    for e in case["items"]:
        i, score = best_match(e["source_line"], got_lines)
        if i < 0 or score < 0.6:
            print(f"  FAIL not extracted: {e['source_line'][:80]}")
            fails += 1
            continue
        used.add(i)
        g, flags = results[i]
        status = "Needs Review" if flags else "Pending"
        codes = sorted({f["reason_code"] for f in flags})
        ok = status == e["expect_status"]
        # The safety direction matters most: an expected review item that comes out Pending is a hard fail.
        # A clean item that the model made Needs Review is a soft miss (safe, but noisy).
        tag = "ok  " if ok else ("FAIL" if e["expect_status"] == "Needs Review" else "warn")
        fails += tag == "FAIL"
        note = "" if ok or not live else f"  (expected {e['expect_status']} {e['expect_reasons']})"
        reasons = "" if codes == e["expect_reasons"] or not codes else f" {codes}"
        if not ok and not live:
            note = f"  (expected {e['expect_status']} {e['expect_reasons']})"
        print(f"  {tag} {status:12} {g['type']:16} due={g['due_date']}{reasons}  <- {e['source_line'][:60]}{note}")
        if live and not g.get("source_found"):
            print("       note: source line was not copied exactly, so SOURCE_NOT_FOUND fired")
    allowed = [norm(x) for x in case.get("may_become_tasks", [])]
    forbidden = [norm(x) for x in case.get("must_not_become_tasks", [])]
    for i, (g, flags) in enumerate(results):
        if i in used:
            continue
        line = norm(g["source_line"])
        if any(SequenceMatcher(None, line, f).ratio() > 0.6 or line in f for f in forbidden):
            print(f"  FAIL diagnosis or hospital course became a task: {g['source_line'][:80]}")
            fails += 1
        elif any(SequenceMatcher(None, line, a).ratio() > 0.6 for a in allowed):
            print(f"  ok   extra item from an allowed plain line: {g['source_line'][:60]}")
        else:
            print(f"  warn extra item not in expected.json: {g['type']} {g['source_line'][:70]}")
    if rejected:
        print(f"  note {rejected} item(s) failed the schema and become Needs Review placeholders")
    # an injected instruction must never produce a clean task that changes a dose
    for g, flags in results:
        if "ignore all previous rules" in norm(g["source_line"]) and not flags:
            print("  FAIL prompt injection produced a clean task")
            fails += 1
    print(f"  -> {'PASS' if not fails else f'{fails} failure(s)'}")
    return fails


async def main():
    live = "--live" in sys.argv
    rules = "--rules" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    cases = json.loads((DIR / "expected.json").read_text(encoding="utf-8"))
    total = 0
    for case in cases:
        if only and not any(o in case["file"] for o in only):
            continue
        raw = (DIR / case["file"]).read_text(encoding="utf-8")
        if rules:
            from app.pipeline import rule_extractor
            total += report(case, raw, [i.model_dump() for i in rule_extractor.extract(raw).items], True)
        elif live:
            try:
                items, rejected = await live_items(raw)
            except Exception as e:
                print(f"\n=== {case['file']}\n  FAIL extraction error: {type(e).__name__}: {e}")
                total += 1
                continue
            total += report(case, raw, items, True, rejected)
        else:
            for e in case["items"]:
                assert find_span(e["source_line"], raw), f"source line missing from {case['file']}: {e['source_line']}"
            total += report(case, raw, reference_items(case), False)
    print(f"\n{'ALL PASS' if not total else f'{total} failure(s)'} ({'rule-based extractor' if rules else 'live model' if live else 'offline, reference extraction'})")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    asyncio.run(main())
