"""Background jobs: plain async functions plus one asyncio loop started in the FastAPI lifespan.

Every job takes a lease first (`job_locks`, one document per job) so that two server processes never run the
same job in the same interval. Every job is idempotent: running it twice changes nothing the second time."""
import asyncio
import logging
import os
import socket
from datetime import timedelta

from pymongo.errors import DuplicateKeyError

from app.core.audit import audit
from app.core.db import get_db
from app.core.util import d2dt, now, today_ist
from app.modules.notifications import service as notify
from app.pipeline import review_router

log = logging.getLogger("jobs")
HOLDER = f"{socket.gethostname()}:{os.getpid()}"
TICK_SECONDS = 60


async def send_due_notifications() -> int:
    """Notifications whose time has come become visible to the recipient."""
    db, n = get_db(), 0
    async for x in db.notifications.find({"sent_at": None, "scheduled_at": {"$lte": now()}}):
        if x["type"] == "reminder":  # drop reminders for tasks completed, flagged or removed since scheduling
            t = await db.tasks.find_one({"_id": x["task_id"]}, {"status": 1})
            if not t or t["status"] != "Pending":
                await db.notifications.delete_one({"_id": x["_id"]})
                continue
        claimed = await db.notifications.update_one({"_id": x["_id"], "sent_at": None}, {"$set": {"sent_at": now()}})
        n += claimed.modified_count
    return n


async def missed_task_check() -> int:
    """Pending tasks past their due date alert the hub manager once (only if their consent allows it)."""
    db, n = get_db(), 0
    async for t in db.tasks.find({"status": "Pending", "due_date": {"$lt": d2dt(today_ist())},
                                  "missed_notified_at": None}):
        claim = await db.tasks.update_one({"_id": t["_id"], "missed_notified_at": None},
                                          {"$set": {"missed_notified_at": now()}})
        if not claim.modified_count:
            continue  # another process got it
        for uid in await notify.subscribers(t["patient_id"], t["type"], only_missed=True):
            await notify.add(uid, t["patient_id"], "missed_task", "missed_task", task_id=t["_id"], sent=True)
            n += 1
    return n


async def review_aging_check() -> int:
    return await review_router.aging_check()


async def cleanup() -> int:
    r = await get_db().refresh_tokens.delete_many({"expires_at": {"$lt": now()}})
    return r.deleted_count


async def suspicious_activity_check() -> int:
    """Raise an alert entry when one actor is denied 10+ times in 15 minutes (once per actor per window)."""
    from app.core import audit as audit_mod
    since = now() - timedelta(minutes=15)
    denied: dict = {}
    for e in await audit_mod.events({"result": "denied", "ts": {"$gte": since}}, limit=1000):
        denied[e["actor_id"]] = denied.get(e["actor_id"], 0) + 1
    hits = {a: c for a, c in denied.items() if c >= 10}
    for actor, c in hits.items():
        recent = await audit_mod.events({"action": "alert_suspicious", "target_id": actor,
                                         "ts": {"$gte": since}}, limit=1)
        if not recent:
            await audit("system", "alert_suspicious", "user", actor if not isinstance(actor, str) else None,
                        result="error", meta={"denied_in_15min": c})
    return len(hits)


JOBS = {  # name: (function, minimum seconds between runs)
    "send_due_notifications": (send_due_notifications, 60),
    "missed_task_check": (missed_task_check, 60),
    "review_aging_check": (review_aging_check, 300),
    "suspicious_activity_check": (suspicious_activity_check, 300),
    "cleanup": (cleanup, 3600),
}


async def lease(name: str, seconds: int) -> bool:
    """True if this process now holds the job. The lease is the 'locked_until' of the job's one document."""
    coll, t = get_db().job_locks, now()
    until = t + timedelta(seconds=seconds)
    if await coll.find_one_and_update({"_id": name, "locked_until": {"$lt": t}},
                                      {"$set": {"locked_until": until, "holder": HOLDER}}):
        return True
    try:
        await coll.insert_one({"_id": name, "locked_until": until, "holder": HOLDER})
        return True
    except DuplicateKeyError:
        return False


async def run_due_jobs() -> dict:
    """One tick: run each job whose lease we can take. Returns what ran. A failing job is logged and recorded."""
    ran = {}
    for name, (fn, every) in JOBS.items():
        if not await lease(name, every - 5):
            continue
        try:
            ran[name] = await fn()
            await get_db().job_locks.update_one({"_id": name}, {"$set": {"last_run": now(), "last_result": ran[name],
                                                                          "last_error": None}})
        except Exception as e:  # visible, never silent
            log.error("job %s failed: %s", name, type(e).__name__)
            await get_db().job_locks.update_one({"_id": name}, {"$set": {"last_run": now(),
                                                                          "last_error": type(e).__name__}})
    return ran


async def run_loop() -> None:
    while True:
        try:
            await run_due_jobs()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error("job tick failed: %s", type(e).__name__)
        await asyncio.sleep(TICK_SECONDS)
