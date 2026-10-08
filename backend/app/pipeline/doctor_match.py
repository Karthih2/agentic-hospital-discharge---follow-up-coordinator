"""Doctor matching (code, no AI). Runs right after the summary is read, before any task is planned.

Which doctor owns this patient's new plan, in order:
  1. the Attending Physician named on the summary, when that doctor has an account here
  2. the doctor already responsible for this patient (`doctors.assigned_patient_ids`)
  3. a doctor of the attending physician's specialty
  4. the doctor with the fewest open plans and reviews
If the chosen doctor is unavailable, the plan follows that doctor's fallback chain (admin controlled), then any
available doctor. The matched doctor reviews and publishes the plan; the patient sees nothing before that.
"""
import re

from app.core.audit import audit
from app.core.db import get_db
from app.core.security.crypto import dec
from app.core.util import now
from app.pipeline import review_router

_TITLE = re.compile(r"^\s*(dr|doctor|prof)\.?\s+", re.I)


def norm_name(s: str | None) -> str:
    s = _TITLE.sub("", s or "")
    return " ".join(re.sub(r"[^a-z ]", " ", s.casefold()).split())


def parse_attending(value: str | None) -> tuple[str | None, str | None]:
    """'Dr. Sanjay, Endocrinology (attending on the day of discharge)' -> ('Dr. Sanjay', 'Endocrinology')."""
    if not value or not value.strip():
        return None, None
    v = re.sub(r"\(.*?\)", "", value).strip()
    parts = [p.strip() for p in v.split(",") if p.strip()]
    name = parts[0] if parts else None
    spec = parts[1] if len(parts) > 1 else None
    return name, spec


def _same_person(a: str, b: str) -> int:
    """2 = same name, 1 = one name contains the other's words (Dr. Mallu = Dr. Mallu Karthick Balaji Reddy), 0 = no."""
    if not a or not b:
        return 0
    if a == b:
        return 2
    ta, tb = set(a.split()), set(b.split())
    return 1 if ta <= tb or tb <= ta else 0


async def _load(doctor_id) -> int:
    db = get_db()
    plans = await db.discharge_summaries.count_documents({"plan_doctor_id": doctor_id, "plan_status": "draft"})
    reviews = await db.review_queue.count_documents({"assigned_doctor_id": doctor_id,
                                                     "status": {"$in": ["open", "in_review"]}})
    return plans + reviews


async def _doctors() -> list[dict]:
    db = get_db()
    out = []
    async for d in db.doctors.find({}):
        u = await db.users.find_one({"_id": d["user_id"], "is_active": True}, {"name": 1})
        if u:
            out.append({**d, "name": dec(u["name"]) if u.get("name") else ""})
    return out


async def choose(header: dict | None, patient_id) -> dict:
    """Returns {doctor_id, primary_id, reason, attending}. doctor_id is None when no doctor is available at all."""
    docs = await _doctors()
    att_name, att_spec = parse_attending((header or {}).get("attending_physician"))
    base = {"attending": att_name, "attending_specialty": att_spec}
    if not docs:
        return {**base, "doctor_id": None, "primary_id": None, "reason": "No doctor accounts exist yet"}

    primary, reason = None, None
    want = norm_name(att_name)
    if want:
        scored = sorted(((_same_person(want, norm_name(d["name"])), d) for d in docs), key=lambda x: -x[0])
        best = [d for s, d in scored if s and s == scored[0][0]]
        if len(best) == 1:
            primary, reason = best[0], f"Attending physician on the summary ({att_name})"
    if primary is None:
        mine = [d for d in docs if patient_id in d.get("assigned_patient_ids", [])]
        if mine:
            primary, reason = mine[0], "Already this patient's doctor"
    if primary is None and att_spec:
        same = [d for d in docs if d["specialty"].casefold() == att_spec.casefold()]
        if same:
            loads = [(await _load(d["user_id"]), d) for d in same]
            primary = min(loads, key=lambda x: x[0])[1]
            reason = f"Specialty match ({att_spec})"
    if primary is None:
        loads = [(await _load(d["user_id"]), d) for d in docs]
        primary = min(loads, key=lambda x: x[0])[1]
        reason = "Fewest open plans and reviews"

    if review_router.is_available(primary):
        return {**base, "doctor_id": primary["user_id"], "primary_id": primary["user_id"], "reason": reason}
    db = get_db()
    for nxt in await review_router.chain(primary["user_id"]):
        d = await db.doctors.find_one({"user_id": nxt})
        if d and review_router.is_available(d):
            return {**base, "doctor_id": d["user_id"], "primary_id": primary["user_id"],
                    "reason": f"{reason}; that doctor is unavailable, so the plan went to their fallback"}
    free = [d for d in docs if review_router.is_available(d)]
    if free:
        loads = [(await _load(d["user_id"]), d) for d in free]
        d = min(loads, key=lambda x: x[0])[1]
        return {**base, "doctor_id": d["user_id"], "primary_id": primary["user_id"],
                "reason": f"{reason}; that doctor and their fallbacks are unavailable, so the least busy available "
                          f"doctor took it"}
    return {**base, "doctor_id": None, "primary_id": primary["user_id"],
            "reason": f"{reason}; no doctor is available, the admin must assign one"}


async def assign_plan(summary: dict, header: dict | None) -> dict:
    """Match a doctor to this summary's plan and record it. Returns the match record."""
    db = get_db()
    m = await choose(header, summary["patient_id"])
    rec = {"reason": m["reason"], "primary_doctor_id": m["primary_id"], "attending": m["attending"],
           "attending_specialty": m["attending_specialty"], "matched_at": now(),
           "history": [{"doctor_id": m["doctor_id"], "at": now(), "reason": "initial"}]}
    await db.discharge_summaries.update_one({"_id": summary["_id"]}, {"$set": {
        "plan_doctor_id": m["doctor_id"], "plan_match": rec}})
    if m["doctor_id"] is not None:
        await db.doctors.update_one({"user_id": m["doctor_id"]},
                                    {"$addToSet": {"assigned_patient_ids": summary["patient_id"]}})
    await audit("system", "match_doctor", "summary", summary["_id"], meta={"reason": m["reason"]})
    return {**rec, "doctor_id": m["doctor_id"]}


async def move_plan(summary: dict, doctor_id, reason: str, actor="system") -> bool:
    """Hand a draft plan (and its open review items) to another doctor. Atomic on the current owner."""
    db = get_db()
    cur = summary.get("plan_doctor_id")
    r = await db.discharge_summaries.update_one(
        {"_id": summary["_id"], "plan_status": {"$in": ["generating", "draft"]}, "plan_doctor_id": cur},
        {"$set": {"plan_doctor_id": doctor_id},
         "$push": {"plan_match.history": {"doctor_id": doctor_id, "at": now(), "reason": reason}}})
    if not r.modified_count:
        return False
    if doctor_id is not None:
        await db.doctors.update_one({"user_id": doctor_id}, {"$addToSet": {"assigned_patient_ids": summary["patient_id"]}})
    task_ids = [t["_id"] async for t in db.tasks.find({"summary_id": summary["_id"]}, {"_id": 1})]
    async for rv in db.review_queue.find({"task_id": {"$in": task_ids}, "status": {"$in": ["open", "in_review"]}}):
        await review_router.assign_to(rv, doctor_id, reason, actor=actor)
    await audit(actor, "reassign_plan", "summary", summary["_id"], meta={"reason": reason})
    return True


async def plan_aging_check() -> int:
    """Draft plans whose doctor became unavailable (or that never got one) move down the fallback chain."""
    db = get_db()
    moved = 0
    async for s in db.discharge_summaries.find({"plan_status": "draft"}):
        cur = s.get("plan_doctor_id")
        doc = await db.doctors.find_one({"user_id": cur}) if cur else None
        if doc and review_router.is_available(doc):
            continue
        start = cur or (s.get("plan_match") or {}).get("primary_doctor_id")
        target = None
        if start:
            for nxt in await review_router.chain(start):
                d = await db.doctors.find_one({"user_id": nxt})
                if d and review_router.is_available(d):
                    target = d["user_id"]
                    break
        if target is None:
            free = [d async for d in db.doctors.find({}) if review_router.is_available(d)]
            if free:
                target = min([(await _load(d["user_id"]), d) for d in free], key=lambda x: x[0])[1]["user_id"]
        if target is not None and target != cur and await move_plan(s, target, "unavailable"):
            moved += 1
    return moved
