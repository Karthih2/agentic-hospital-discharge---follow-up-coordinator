"""Masked call flow. SIMULATED: synthetic proxy numbers, no telephony.
In production only this module changes (swap in a Twilio adapter, recording off by default)."""
import random

from fastapi import HTTPException

from app.core.db import get_db
from app.modules.notifications import service as notify
from app.core.audit import audit
from app.core.util import now

MAX_PER_DAY = 5


def _mask() -> str:
    return f"+91-9{random.randint(0, 9999):04d}-{random.randint(0, 99999):05d}"


async def request(task: dict, user_id, view_on_behalf, ip) -> dict:
    db = get_db()
    since = now().replace(hour=0, minute=0, second=0, microsecond=0)
    n = await db.notifications.count_documents(
        {"type": "callback", "template_key": "callback_requested", "patient_id": task["patient_id"], "scheduled_at": {"$gte": since}})
    if n >= MAX_PER_DAY:
        raise HTTPException(429, "Too many callback requests today")
    cb = {"status": "requested", "requested_by": user_id, "handled_by": None, "patient_mask": None,
          "provider_mask": None, "started_at": None, "ended_at": None, "duration_sec": None}
    await notify.add(task["patient_id"], task["patient_id"], "callback", "callback_requested",
                     task_id=task["_id"], sent=True, callback=cb)
    await audit(user_id, "callback_requested", "task", task["_id"], on_behalf_of=view_on_behalf, ip=ip)
    return {"status": "requested"}


async def start(cb_id, mgmt_id, ip) -> dict:
    db = get_db()
    n = await db.notifications.find_one({"_id": cb_id, "type": "callback"})
    if not n:
        raise HTTPException(404, "Not found")
    if n["callback"]["status"] not in ("requested", "queued"):
        raise HTTPException(409, "Callback already started")
    upd = {"callback.status": "connecting", "callback.handled_by": mgmt_id, "callback.started_at": now(),
           "callback.patient_mask": _mask(), "callback.provider_mask": _mask()}
    await db.notifications.update_one({"_id": cb_id}, {"$set": upd})
    await audit(mgmt_id, "callback_started", "task", n["task_id"], ip=ip)
    return {"status": "connecting"}


async def complete(cb_id, mgmt_id, ip) -> dict:
    db = get_db()
    n = await db.notifications.find_one({"_id": cb_id, "type": "callback"})
    if not n:
        raise HTTPException(404, "Not found")
    if n["callback"]["status"] != "connecting":
        raise HTTPException(409, "Callback is not in progress")
    end = now()
    dur = max(0, int((end - n["callback"]["started_at"]).total_seconds()))
    await db.notifications.update_one({"_id": cb_id}, {"$set": {
        "callback.status": "completed", "callback.ended_at": end, "callback.duration_sec": dur}})
    if n.get("task_id"):
        await db.tasks.update_one({"_id": n["task_id"]}, {"$set": {"callback_completed_at": end}})
    await notify.add(n["patient_id"], n["patient_id"], "callback", "callback_completed",
                     task_id=n.get("task_id"), sent=True)
    await audit(mgmt_id, "callback_completed", "task", n["task_id"], ip=ip, meta={"duration_sec": dur})  # who, when, duration. Never content
    return {"status": "completed", "duration_sec": dur}
