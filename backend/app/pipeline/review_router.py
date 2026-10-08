"""Review routing agent (code). Assigns a doctor, reroutes along the admin-controlled fallback chain.
Everything lives in the database: the assigned doctor on `review_queue`, the chain on `doctors.fallback_doctor_id`."""
from datetime import timedelta

from app.core.audit import audit
from app.core.config import settings
from app.core.db import get_db
from app.core.util import now

_UNSET = object()


def is_available(doc: dict) -> bool:
    if not doc.get("available"):
        return False
    until = doc.get("unavailable_until")
    return until is None or until.replace(tzinfo=None) < now().replace(tzinfo=None)


async def _open_count(doctor_id) -> int:
    return await get_db().review_queue.count_documents(
        {"assigned_doctor_id": doctor_id, "status": {"$in": ["open", "in_review"]}})


async def chain(start_id, exclude: set | None = None) -> list:
    """Doctor user ids after `start_id`, following `fallback_doctor_id`. Stops on a cycle or after 20 hops."""
    db, seen, out, cur = get_db(), {start_id}, [], start_id
    for _ in range(20):
        d = await db.doctors.find_one({"user_id": cur}, {"fallback_doctor_id": 1})
        nxt = (d or {}).get("fallback_doctor_id")
        if not nxt or nxt in seen:
            break
        seen.add(nxt)
        cur = nxt
        if not exclude or nxt not in exclude:
            out.append(nxt)
    return out


async def pick_primary(review: dict, task: dict | None):
    """Doctor already responsible for this patient, else best specialty match, else fewest open items."""
    db = get_db()
    docs = [d async for d in db.doctors.find({})]
    if not docs:
        return None
    spec = ((task or {}).get("specialty") or "").casefold()

    async def key(d):
        return (review["patient_id"] not in d.get("assigned_patient_ids", []),
                d["specialty"].casefold() != spec, await _open_count(d["user_id"]))
    keyed = [(await key(d), d) for d in docs]
    keyed.sort(key=lambda x: x[0])
    return keyed[0][1]


async def assign_to(review: dict, doctor_id, reason: str, actor="system", expect=_UNSET) -> bool:
    """Atomic: the update only lands if the review still has the doctor we saw (`expect`), so two admins or an
    admin and a job can never both move the same review. Returns True when it moved."""
    cur = review.get("assigned_doctor_id") if expect is _UNSET else expect
    entry = {"doctor_id": doctor_id, "assigned_at": now(), "reason": reason}
    chain_ids = await chain(doctor_id) if doctor_id else []
    r = await get_db().review_queue.find_one_and_update(
        {"_id": review["_id"], "assigned_doctor_id": cur, "status": {"$in": ["open", "in_review"]}},
        {"$set": {"assigned_doctor_id": doctor_id, "fallback_doctor_ids": chain_ids},
         "$push": {"assignment_history": entry}})
    if r is None:
        return False
    review["assigned_doctor_id"] = doctor_id
    review.setdefault("assignment_history", []).append(entry)
    await audit(actor, "reroute" if reason != "initial" else "assign_review", "review", review["_id"],
                meta={"reason": reason})
    return True


async def assign(review: dict) -> None:
    db = get_db()
    task = await db.tasks.find_one({"_id": review["task_id"]})
    # The doctor matched to this summary's plan reviews its items first (plan and items never split up).
    summary = await db.discharge_summaries.find_one({"_id": task["summary_id"]}, {"plan_doctor_id": 1}) \
        if task and task.get("summary_id") else None
    pd = (summary or {}).get("plan_doctor_id")
    if pd:
        d = await db.doctors.find_one({"user_id": pd})
        if d and is_available(d):
            await assign_to(review, pd, "plan_doctor")
            return
    primary = await pick_primary(review, task)
    if not primary:
        return  # stays open and unassigned; shows in the admin's "needs assignment" list
    if is_available(primary):
        await assign_to(review, primary["user_id"], "initial")
        return
    for nxt in await chain(primary["user_id"]):
        d = await db.doctors.find_one({"user_id": nxt})
        if d and is_available(d):
            await assign_to(review, d["user_id"], "initial_fallback")
            return


async def reroute(review: dict, reason: str, avoid_history: bool = True) -> bool:
    """Move an open review to the next available reviewer. Returns True if it moved."""
    db = get_db()
    cur = review.get("assigned_doctor_id")
    if cur is None:
        await assign(review)
        return review.get("assigned_doctor_id") is not None
    tried = {h["doctor_id"] for h in review.get("assignment_history", [])} if avoid_history else set()
    for nxt in await chain(cur, tried):
        d = await db.doctors.find_one({"user_id": nxt})
        if d and is_available(d) and await assign_to(review, d["user_id"], reason, expect=cur):
            return True
    return False


async def aging_check() -> int:
    """Open reviews that are too old, or sit with an unavailable doctor, move down the chain."""
    db = get_db()
    cutoff = now() - timedelta(hours=settings.review_aging_hours)
    moved = 0
    # items of a draft plan move with their plan (doctor_match.plan_aging_check), never on their own
    async for rv in db.review_queue.find({"status": {"$in": ["open", "in_review"]}, "plan_draft": {"$ne": True}}):
        hist = rv.get("assignment_history") or []
        since = hist[-1]["assigned_at"] if hist else rv["created_at"]
        doc = await db.doctors.find_one({"user_id": rv.get("assigned_doctor_id")}) if rv.get("assigned_doctor_id") else None
        gone = rv.get("assigned_doctor_id") is None or not doc or not is_available(doc)
        old = rv["status"] == "open" and since.replace(tzinfo=None) < cutoff.replace(tzinfo=None)
        if gone or old:
            moved += await reroute(rv, "unavailable" if gone else "aged")
    return moved
