"""Orchestrator. A plain function that runs the steps in order and writes the status after every step.
Any failure sets a visible status. Nothing stops silently.

Plan life cycle: the summary is matched to a doctor first, then the system ALWAYS builds a draft plan (the AI agent,
or the rule-based extractor when the model is missing or fails). Draft tasks are `published: False`: the patient and
family see nothing and no reminder is scheduled until the matched doctor reviews, edits and publishes the plan."""
import re

from app.core.config import settings
from app.core.db import get_db
from app.pipeline import dates, doctor_match, extraction_agent, planner, rule_extractor, safety_gate, template
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
    task = await planner.insert_task(s["patient_id"], s["_id"], item, flags, published=False)
    await planner.create_review(task, flags, "system_failure")
    # the doctor still gets the (empty) draft and can add every item by hand before publishing
    await _set(db, s["_id"], "needs_manual", error_code=code, plan_status="draft")
    await _notify_doctor(db, s["_id"])


async def _notify_doctor(db, sid) -> None:
    s = await db.discharge_summaries.find_one({"_id": sid}, {"plan_doctor_id": 1, "patient_id": 1})
    if s and s.get("plan_doctor_id"):
        await notify.add(s["plan_doctor_id"], s["patient_id"], "plan_ready", "plan_ready", sent=True)


async def _extract(db, sid, raw):
    """AI first; the rule-based extractor when the model is missing, fails, or finds nothing."""
    t0 = now()
    try:
        out = await extraction_agent.extract(raw)
        if out.items or out.rejected:
            await _log(db, sid, "extract", True, f"model: {len(out.items)} items", t0)
            return out, "model"
        note = "model found nothing"
    except (AgentError, ValueError) as e:
        note = f"model unavailable: {str(e)[:60]}"
    out = rule_extractor.extract(raw)
    await _log(db, sid, "extract", bool(out.items), f"{note}; rules: {len(out.items)} items", t0)
    return out, "rules"


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

    # 1b. doctor matching (code): who owns this plan, decided before any task exists
    tpl = template.parse(raw)
    if s.get("plan_doctor_id") is None:
        await doctor_match.assign_plan(s, tpl["header"])

    # 2. extraction (AI, rule-based fallback)
    await _set(db, sid, "extracting")
    out, method = await _extract(db, sid, raw)
    await _set(db, sid, extraction_method=method)
    if not out.items and not out.rejected:
        return await _extraction_failed(db, s, raw, "EXTRACTION_FAILED", "nothing found")

    # 3+4. evidence and dates (code)
    discharge = dt2d(s.get("discharge_date")) or dates.parse_discharge_date(raw)
    if discharge is None and out.discharge_date_text:
        discharge = dates.parse_absolute(out.discharge_date_text)
    await _set(db, sid, "gating", discharge_date=d2dt(discharge))
    items = [build_gate_item(i.model_dump(), raw, discharge) for i in out.items]
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
        t = await planner.insert_task(s["patient_id"], sid, it, flags, published=False)
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
    # no reminders yet: they are scheduled when the doctor publishes the plan
    await _log(db, sid, "simplify", not failures, "; ".join(failures)[:200], t0)

    await _set(db, sid, "ready", plan_status="draft")
    await _notify_doctor(db, sid)
