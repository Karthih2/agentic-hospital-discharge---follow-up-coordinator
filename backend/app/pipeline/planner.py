"""Planner (code). Turns gated items into tasks, review records and reminders. Also the single place that
flags a task for review and the single place that simplifies one."""
from app.core.constants import REASON_TEXT, SCHEMA_VERSION
from app.core.db import get_db
from app.pipeline import medicine_template, review_router
from app.pipeline.llm import AgentError
from app.pipeline.simplify_agent import RewriteRejected, simplify
from app.core.security.crypto import dec, enc, enc_map
from app.modules.notifications import service as notify
from app.modules.tasks import stats
from app.core.util import d2dt, now


def reason_text(flags: list[dict]) -> str:
    codes = list(dict.fromkeys(f["reason_code"] for f in flags))
    return "; ".join(REASON_TEXT[c] for c in codes)


def provider_info(item: dict) -> tuple[bool, str | None]:
    spec = (item.get("specialty") or "").strip() or None
    return (item["type"] == "referral" or (item["type"] == "appointment" and spec is not None)), spec


async def insert_task(patient_id, summary_id, item: dict, flags: list[dict], entry_mode: str = "extracted",
                      supersedes=None) -> dict:
    """item is a gate item (see safety_gate). Status comes from the flags: clean -> Pending."""
    needed, spec = provider_info(item)
    ts = now()
    task = {
        "patient_id": patient_id, "summary_id": summary_id, "type": item["type"],
        "title": enc(item.get("title") or ""),
        "due_date": d2dt(item.get("due_date")), "due_date_text": item.get("due_date_text"),
        "status": "Needs Review" if flags else "Pending",
        "source_line": enc(item.get("source_line") or ""), "source_span": item.get("source_span"),
        "confidence": float(item.get("confidence", 1.0)),
        "fields": enc_map({"doctor_name": item.get("doctor_name"), "department": spec,
                           "instruction": item.get("instruction"), "medicine": item.get("medicine"),
                           "due_time": item.get("due_time"), "location": item.get("location"),
                           "phone": item.get("phone")}),
        "flags": flags, "simple_text": None, "translations": {}, "medicine_card": None,
        "provider_id": None, "provider_needed": needed, "specialty": spec, "entry_mode": entry_mode,
        "supersedes": supersedes, "completed_at": None, "completed_by": None, "missed_notified_at": None,
        "callback_completed_at": None, "created_at": ts, "updated_at": ts, "schema_version": SCHEMA_VERSION}
    task["_id"] = (await get_db().tasks.insert_one(task)).inserted_id
    await stats.refresh(patient_id)
    return task


async def create_review(task: dict, flags: list[dict], raised_by: str, user_note: str | None = None) -> dict:
    db = get_db()
    reasons = list(dict.fromkeys(f["reason_code"] for f in flags))
    pat = await db.users.find_one({"_id": task["patient_id"]}, {"patient_code": 1}) or {}
    ts = now()
    rv = {"task_id": task["_id"], "patient_id": task["patient_id"],
          # Extended Reference: just enough to list the queue without joins. No clinical text is copied.
          "snapshot": {"task_type": task["type"], "reasons": reasons, "patient_code": pat.get("patient_code"),
                       "created_date": ts.date().isoformat()},
          "reasons": reasons, "reason_text": reason_text(flags),
          "user_note": enc(user_note) if user_note else None,
          "raised_by": raised_by, "status": "open", "assigned_doctor_id": None, "fallback_doctor_ids": [],
          "assignment_history": [], "outcome": None, "corrected_values": None, "resolved_by": None,
          "resolved_at": None, "created_at": ts, "schema_version": SCHEMA_VERSION}
    rv["_id"] = (await db.review_queue.insert_one(rv)).inserted_id
    await review_router.assign(rv)
    await notify.add(task["patient_id"], task["patient_id"], "review_waiting", "review_waiting",
                     task_id=task["_id"], sent=True)
    return rv


async def flag_task(task: dict, flags: list[dict], raised_by: str, user_note: str | None = None,
                    only_pending: bool = False) -> dict | None:
    """Move a task to Needs Review and open a review record. The only code path that does this.
    The update is conditional: racing flags make one review and a Completed task is never overwritten.
    Returns None when the task had already moved on."""
    cond = {"_id": task["_id"], "status": "Pending" if only_pending else {"$ne": "Needs Review"}}
    r = await get_db().tasks.update_one(cond, {"$set": {
        "status": "Needs Review", "flags": task.get("flags", []) + flags, "updated_at": now()}})
    if not r.modified_count:
        return None
    await stats.refresh(task["patient_id"])
    return await create_review(task, flags, raised_by, user_note)


async def finalize_clean(task: dict, patient_lang: str, approved: bool = False) -> str | None:
    """Make a clean task user-ready: medicine -> fixed card (no AI), others -> plain language + translation.
    Returns a short failure note if the rewrite could not be produced; the task stays usable either way."""
    db = get_db()
    if task["type"] == "medicine":
        med = (task.get("fields") or {}).get("medicine")
        from app.core.security.crypto import dec_map
        card = medicine_template.build_card(dec_map(med) if med else None)
        await db.tasks.update_one({"_id": task["_id"]}, {"$set": {"medicine_card": enc_map(card)}})
        return None
    try:
        simple, tr = await simplify(dec(task["source_line"]), patient_lang)
    except RewriteRejected as e:
        if approved:  # a doctor approved it: keep it Pending, UI shows the source line
            return "rewrite_rejected_after_approval"
        await flag_task(task, [{"field": "simple_text", "reason_code": "UNCATEGORISED",
                                "note": f"rewrite rejected: {e}"}], "gate")
        return "rewrite_rejected"
    except AgentError as e:
        return f"simplify_failed:{e}"
    await db.tasks.update_one({"_id": task["_id"]}, {"$set": {
        "simple_text": enc(simple), "translations": {k: enc(v) for k, v in tr.items()}, "updated_at": now()}})
    return None
