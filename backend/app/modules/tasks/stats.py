"""Computed pattern: per-patient counts and next due date, recomputed on every task status change.
Hub cards and the admin overview read this one small document instead of scanning tasks."""
from app.core.constants import APPT_TYPES, PUBLISHED, SCHEMA_VERSION
from app.core.db import get_db
from app.core.util import now, today_ist, d2dt


async def refresh(patient_id) -> dict:
    db = get_db()
    counts = {"pending": 0, "completed": 0, "needs_review": 0}
    key = {"Pending": "pending", "Completed": "completed", "Needs Review": "needs_review"}
    async for t in db.tasks.find({"patient_id": patient_id, **PUBLISHED}, {"status": 1}):
        counts[key[t["status"]]] += 1
    today = d2dt(today_ist())
    nxt = await db.tasks.find_one({"patient_id": patient_id, "status": "Pending", "due_date": {"$gte": today},
                                   **PUBLISHED}, {"due_date": 1}, sort=[("due_date", 1)])
    nxt_appt = await db.tasks.find_one({"patient_id": patient_id, "status": "Pending", "due_date": {"$gte": today},
                                        "type": {"$in": list(APPT_TYPES)}, **PUBLISHED}, {"due_date": 1}, sort=[("due_date", 1)])
    doc = {**counts, "next_due": nxt["due_date"] if nxt else None,
           "next_appointment_due": nxt_appt["due_date"] if nxt_appt else None,
           "updated_at": now(), "schema_version": SCHEMA_VERSION}
    await db.patient_stats.replace_one({"_id": patient_id}, doc, upsert=True)
    return doc


async def get(patient_id) -> dict:
    s = await get_db().patient_stats.find_one({"_id": patient_id})
    return s or await refresh(patient_id)
