"""Orchestrator. A plain function that runs the steps in order and writes the status after every step.
Any failure sets a visible status. Nothing stops silently."""
import re

from app.core.config import settings
from app.core.db import get_db
from app.pipeline import dates, extraction_agent, planner, safety_gate, template
from app.pipeline.llm import AgentError
from app.core.security.crypto import dec, enc, enc_map
from app.modules.notifications import service as notify
from app.core.util import d2dt, dt2d, now


def find_span(source_line: str, raw_text: str):
    """Exact evidence check. Whitespace/line-break differences are ignored. Returns (verbatim text, span) or None."""
    toks = source_line.split()
    if not toks:
        return None
    m = re.search(r"\s+".join(re.escape(t) for t in toks), raw_text)
    return (m.group(0), {"start": m.start(), "end": m.end()}) if m else None


def build_gate_item(it: dict, raw_text: str, discharge) -> dict:
    """it: ExtractedItem as a dict. Adds evidence, resolved date and flags for the gate."""
    hit = find_span(it["source_line"], raw_text)
    res = dates.resolve(it.get("due_date_text"), discharge)
    due = res.date
    if it["type"] == "medicine" and due is None and not res.ambiguous:
        due = discharge  # a medicine course starts at discharge
    line = hit[0] if hit else it["source_line"]
    # appointment details must be visible in the source line, or they are dropped (the model never invents them)
    time_, loc, phone = (it.get(k) for k in ("due_time", "location", "phone"))
    flat = " ".join(line.split()).casefold()
    time_ = time_ if time_ and dates.parse_time(time_) and " ".join(time_.split()).casefold() in flat else None
    loc = loc if loc and " ".join(loc.split()).casefold() in flat else None
    phone = phone if phone and re.sub(r"\D", "", phone) and re.sub(r"\D", "", phone) in re.sub(r"\D", "", line) else None
    return {**it, "due_time": time_, "location": loc, "phone": phone,
            "medicine": it.get("medicine"), "source_found": hit is not None,
            "source_line": hit[0] if hit else it["source_line"], "source_span": hit[1] if hit else None,
            "due_date": due, "date_ambiguous": res.ambiguous}


async def _set(db, sid, status=None, **extra):
    upd = {**extra}
    if status:
        upd["status"] = status
    await db.discharge_summaries.update_one({"_id": sid}, {"$set": upd})


async def _log(db, sid, step, ok, note="", started=None):
    await db.discharge_summaries.update_one({"_id": sid}, {"$push": {"pipeline_log": {
        "step": step, "started_at": started or now(), "ended_at": now(), "ok": ok, "note": note}}})


async def _extraction_failed(db, s, raw, code, note):
    """Complete extraction failure: a visible Needs Review record, then ask the user for manual entry."""
    item = {"type": "care_instruction", "title": "Discharge summary could not be read",
            "source_line": raw[:300], "confidence": 0.0, "source_found": True}
    flags = [{"field": "item", "reason_code": "EXTRACTION_FAILED", "note": note}]
    task = await planner.insert_task(s["patient_id"], s["_id"], item, flags)
    await planner.create_review(task, flags, "system_failure")
    await _set(db, s["_id"], "needs_manual", error_code=code)


async def run(summary_id) -> None:
    db = get_db()
    s = await db.discharge_summaries.find_one({"_id": summary_id})
    if not s:
        return
    try:
        await _run(db, s)
    except Exception as e:  # visible failure, never silent
        await _log(db, s["_id"], "pipeline", False, type(e).__name__)
        await _set(db, s["_id"], "failed", error_code="PIPELINE_ERROR")


async def _run(db, s):
    sid, raw = s["_id"], dec(s["raw_text"])

    # 2. extraction (AI)
    t0 = now()
    await _set(db, sid, "extracting")
    try:
        out = await extraction_agent.extract(raw)
    except (AgentError, ValueError) as e:
        await _log(db, sid, "extract", False, str(e)[:80], t0)
        return await _extraction_failed(db, s, raw, "EXTRACTION_FAILED", "extraction failed")
    if not out.items and not out.rejected:
        await _log(db, sid, "extract", False, "no items", t0)
        return await _extraction_failed(db, s, raw, "EXTRACTION_FAILED", "nothing found")
    await _log(db, sid, "extract", True, f"{len(out.items)} items", t0)

    # 3+4. evidence and dates (code)
    discharge = dt2d(s.get("discharge_date")) or dates.parse_discharge_date(raw)
    if discharge is None and out.discharge_date_text:
        discharge = dates.parse_absolute(out.discharge_date_text)
    await _set(db, sid, "gating", discharge_date=d2dt(discharge))
    items = [build_gate_item(i.model_dump(), raw, discharge) for i in out.items]
    tpl = template.parse(raw)
    notices = [{"code": n["code"], "line": enc(n["line"])} for n in template.completeness(tpl["header"], items)]
    await _set(db, sid, header=enc_map(tpl["header"]), diagnoses=enc_map(tpl["diagnoses"]), notices=notices)

    # 5. safety gate (fixed rules)
    t0 = now()
    conflicts = safety_gate.conflict_flags(items)
    lines = template.actionable_lines(raw)
    mentions = safety_gate.mention_flags(items, [ln for _, ln in lines])
    gated = [(it, safety_gate.run_gate(it) + conflicts.get(n, []) + mentions.get(n, [])) for n, it in enumerate(items)]
    for line in template.uncovered(lines, [it["source_line"] for it in items]):  # the model skipped this line
        ghost = {"type": "care_instruction", "title": "Not understood automatically", "source_line": line,
                 "confidence": 0.0, "source_found": True}
        hit = find_span(line, raw)
        ghost.update(source_span=hit[1] if hit else None, source_found=hit is not None)
        gated.append((ghost, [{"field": "item", "reason_code": "UNCATEGORISED", "note": "line was not extracted"}]))
    for r in out.rejected:  # schema-invalid items are never trusted
        line = r.get("source_line") if isinstance(r.get("source_line"), str) else ""
        ghost = {"type": "care_instruction", "title": "Unrecognised item", "source_line": line,
                 "confidence": 0.0, "source_found": bool(line and find_span(line, raw))}
        gated.append((ghost, [{"field": "item", "reason_code": "UNCATEGORISED", "note": "schema check failed"}]))
    await _log(db, sid, "gate", True, f"{sum(1 for _, f in gated if f)} flagged", t0)

    if not await db.users.find_one({"_id": s["patient_id"]}):  # account deleted while the pipeline ran
        await db.discharge_summaries.delete_one({"_id": sid})
        return

    # 6. planner
    t0 = now()
    await _set(db, sid, "planning")
    tasks = []
    for it, flags in gated:
        t = await planner.insert_task(s["patient_id"], sid, it, flags)
        if flags:
            await planner.create_review(t, flags, "gate")
        tasks.append(t)
    await _log(db, sid, "plan", True, f"{len(tasks)} tasks", t0)

    # 7+8. simplify clean tasks; provider flag is already on the task (matching happens on demand with location)
    t0 = now()
    await _set(db, sid, "simplifying")
    patient = await db.users.find_one({"_id": s["patient_id"]})
    failures = []
    for t in tasks:
        if t["status"] == "Pending":
            note = await planner.finalize_clean(t, patient["language"])
            if note:
                failures.append(note)
    for t in tasks:  # reminders only for tasks that are still clean
        fresh = await db.tasks.find_one({"_id": t["_id"]})
        if fresh["status"] == "Pending":
            await notify.schedule_reminders(fresh)
    await _log(db, sid, "simplify", not failures, "; ".join(failures)[:200], t0)

    await _set(db, sid, "ready")
