"""Hospital management center. Metadata only: counts, ids, names of staff and hub members, consent levels.
NEVER clinical text: no source lines, no medicines, no diagnoses, no summary text."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core import audit as audit_mod
from app.core import db as dbmod
from app.core.audit import audit
from app.core.constants import SCHEMA_VERSION
from app.core.db import get_db
from app.core.security.access import Principal, client_ip, require_role
from app.core.security.crypto import dec
from app.core.util import iso, now, oid, sid
from app.models.schemas import AssignIn, AvailabilityIn, FallbackIn
from app.modules.admin import callbacks
from app.pipeline import review_router
from app.pipeline.template import NOTICE_TEXT

router = APIRouter(prefix="/admin-api", tags=["admin"])
admin = require_role("admin")
OPEN = {"$in": ["open", "in_review"]}


def _age_h(ts) -> float:
    return round((now().replace(tzinfo=None) - ts.replace(tzinfo=None)).total_seconds() / 3600, 1)


async def _names(ids) -> dict:
    return {u["_id"]: dec(u["name"]) async for u in get_db().users.find({"_id": {"$in": list(ids)}}, {"name": 1})}


@router.get("/overview")
async def overview(user: Principal = Depends(admin)):
    db = get_db()
    ages = {"under_24h": 0, "one_to_three_days": 0, "over_three_days": 0}
    unassigned = 0
    async for rv in db.review_queue.find({"status": OPEN}, {"created_at": 1, "assigned_doctor_id": 1}):
        h = _age_h(rv["created_at"])
        ages["under_24h" if h < 24 else "one_to_three_days" if h < 72 else "over_three_days"] += 1
        unassigned += rv.get("assigned_doctor_id") is None
    docs = [d async for d in db.doctors.find({})]
    start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    totals = {"Pending": 0, "Completed": 0, "Needs Review": 0}
    async for s in db.patient_stats.find({}):  # Computed pattern: no scan of tasks
        totals["Pending"] += s["pending"]
        totals["Completed"] += s["completed"]
        totals["Needs Review"] += s["needs_review"]
    return {"open_reviews": ages, "open_total": sum(ages.values()), "unassigned_reviews": unassigned,
            "doctors_available": sum(review_router.is_available(d) for d in docs), "doctors_total": len(docs),
            "summaries_today": await db.discharge_summaries.count_documents({"uploaded_at": {"$gte": start}}),
            "failures_today": await db.discharge_summaries.count_documents(
                {"uploaded_at": {"$gte": start}, "status": {"$in": ["failed", "needs_manual"]}}),
            "tasks": totals}


@router.get("/doctors")
async def doctors(user: Principal = Depends(admin)):
    db = get_db()
    docs = [d async for d in db.doctors.find({})]
    names = await _names({d["user_id"] for d in docs})
    out = []
    for d in docs:
        out.append({"doctor_id": sid(d["user_id"]), "name": names.get(d["user_id"]), "specialty": d["specialty"],
                    "clinic": d.get("clinic"), "area": d.get("area"),
                    "available": review_router.is_available(d), "switch_on": d["available"],
                    "unavailable_until": iso(d.get("unavailable_until")),
                    "fallback_doctor_id": sid(d.get("fallback_doctor_id")),
                    "fallback_name": names.get(d.get("fallback_doctor_id")),
                    "open_reviews": await db.review_queue.count_documents(
                        {"assigned_doctor_id": d["user_id"], "status": OPEN})})
    return sorted(out, key=lambda x: x["name"] or "")


async def _doctor(doctor_id: str) -> dict:
    d = await get_db().doctors.find_one({"user_id": oid(doctor_id)})
    if not d:
        raise HTTPException(404, "Not found")
    return d


@router.put("/doctors/{doctor_id}/availability")
async def availability(doctor_id: str, body: AvailabilityIn, request: Request, user: Principal = Depends(admin)):
    db = get_db()
    d = await _doctor(doctor_id)
    until = None
    if body.unavailable_until:
        try:
            until = datetime.fromisoformat(body.unavailable_until)
        except ValueError:
            raise HTTPException(422, "unavailable_until must be an ISO datetime")
    await db.doctors.update_one({"_id": d["_id"]}, {"$set": {"available": body.available, "unavailable_until": until}})
    moved = 0
    if not body.available or until:  # their open items move along the fallback chain now
        async for rv in db.review_queue.find({"assigned_doctor_id": d["user_id"], "status": OPEN}):
            moved += await review_router.reroute(rv, "unavailable", avoid_history=False)
    await audit(user.id, "doctor_availability", "doctor", d["user_id"], ip=client_ip(request),
                meta={"available": body.available, "rerouted": moved})
    return {"available": body.available, "rerouted": moved}


@router.put("/doctors/{doctor_id}/fallback")
async def fallback(doctor_id: str, body: FallbackIn, request: Request, user: Principal = Depends(admin)):
    db = get_db()
    d = await _doctor(doctor_id)
    nxt = None
    if body.next_doctor_id:
        nxt = (await _doctor(body.next_doctor_id))["user_id"]
        if nxt == d["user_id"]:
            raise HTTPException(422, "A doctor cannot be their own fallback")
    await db.doctors.update_one({"_id": d["_id"]}, {"$set": {"fallback_doctor_id": nxt}})
    await audit(user.id, "fallback_change", "doctor", d["user_id"], ip=client_ip(request))
    return {"fallback_doctor_id": sid(nxt)}


@router.get("/reviews")
async def reviews(status: str = Query("open", pattern="^(open|resolved|all)$"), user: Principal = Depends(admin)):
    """Routing list built from each review's own snapshot. No task is read, so no clinical text can leak."""
    db = get_db()
    q = {} if status == "all" else {"status": OPEN} if status == "open" else {"status": "resolved"}
    rows = [rv async for rv in db.review_queue.find(q).sort("created_at", 1).limit(500)]
    names = await _names({r["assigned_doctor_id"] for r in rows if r.get("assigned_doctor_id")})
    return [{"id": sid(rv["_id"]), "status": rv["status"], "reasons": rv["reasons"], "reason_text": rv["reason_text"],
             "task_type": rv["snapshot"]["task_type"], "patient_code": rv["snapshot"].get("patient_code"),
             "assigned_doctor_id": sid(rv.get("assigned_doctor_id")),
             "assigned_name": names.get(rv.get("assigned_doctor_id")), "age_hours": _age_h(rv["created_at"]),
             "needs_assignment": rv.get("assigned_doctor_id") is None and rv["status"] != "resolved",
             "moves": max(0, len(rv.get("assignment_history", [])) - 1)} for rv in rows]


@router.get("/reviews/{review_id}/history")
async def review_history(review_id: str, user: Principal = Depends(admin)):
    rv = await get_db().review_queue.find_one({"_id": oid(review_id)})
    if not rv:
        raise HTTPException(404, "Not found")
    names = await _names({h["doctor_id"] for h in rv.get("assignment_history", []) if h.get("doctor_id")})
    return [{"doctor_id": sid(h["doctor_id"]), "name": names.get(h["doctor_id"]), "reason": h["reason"],
             "assigned_at": iso(h["assigned_at"])} for h in rv.get("assignment_history", [])]


@router.post("/reviews/{review_id}/assign")
async def assign(review_id: str, body: AssignIn, request: Request, user: Principal = Depends(admin)):
    """One review at a time, by design: there is no bulk reassign."""
    rv = await get_db().review_queue.find_one({"_id": oid(review_id)})
    if not rv or rv["status"] == "resolved":
        raise HTTPException(404, "Not found")
    d = await _doctor(body.doctor_id)
    if not await review_router.assign_to(rv, d["user_id"], "admin", actor=user.id):
        raise HTTPException(409, "This review changed while you were assigning it. Reload and try again.")
    return {"assigned_doctor_id": sid(d["user_id"])}


@router.get("/hubs")
async def hubs(user: Principal = Depends(admin)):
    db, out = get_db(), []
    async for h in db.family_hubs.find({}):
        members = [m async for m in db.hub_members.find({"hub_id": h["_id"]})]
        consents = [c async for c in db.consents.find({"hub_id": h["_id"], "revoked_at": None})]
        names = await _names({m["user_id"] for m in members})
        out.append({"id": sid(h["_id"]), "name": h["name"], "manager": names.get(h["manager_id"]),
                    "members": [{"name": names.get(m["user_id"]), "role": m["role"]} for m in members],
                    "consents": [{"patient": names.get(c["patient_id"]), "grantee": names.get(c["grantee_id"]),
                                  "level": c["level"], "guardian": bool(c.get("guardian_consent"))}
                                 for c in consents]})
    return out


@router.get("/audit")
async def audit_log(actor: str | None = None, date_from: str | None = None, date_to: str | None = None,
                    limit: int = Query(200, ge=1, le=500), user: Principal = Depends(admin)):
    """Who did what and when. Metadata only; the log never holds clinical text."""
    match: dict = {}
    if actor:
        match["actor_id"] = oid(actor)
    try:
        if date_from:
            match.setdefault("ts", {})["$gte"] = datetime.fromisoformat(date_from).replace(tzinfo=now().tzinfo)
        if date_to:
            match.setdefault("ts", {})["$lt"] = datetime.fromisoformat(date_to).replace(tzinfo=now().tzinfo) + timedelta(days=1)
    except ValueError:
        raise HTTPException(422, "Dates must look like 2026-10-08")
    evs = await audit_mod.events(match, limit)
    names = await _names({e["actor_id"] for e in evs if not isinstance(e["actor_id"], str)})
    return [{"ts": iso(e["ts"]), "actor_id": sid(e["actor_id"]),
             "actor": names.get(e["actor_id"]) or (e["actor_id"] if isinstance(e["actor_id"], str) else None),
             "action": e["action"], "target_type": e.get("target_type"), "target_id": sid(e.get("target_id")),
             "result": e["result"]} for e in evs]


@router.get("/people")
async def people(user: Principal = Depends(admin)):
    """Accounts for the audit filter. Names and roles only."""
    return [{"id": sid(u["_id"]), "name": dec(u["name"]), "role": u["role"]}
            async for u in get_db().users.find({}, {"name": 1, "role": 1}).sort("role", 1)]


@router.get("/summary-notices")
async def summary_notices(user: Principal = Depends(admin)):
    """Template completeness notices per summary: the notice kind only, never the summary line."""
    out = []
    async for s in get_db().discharge_summaries.find({"notices.0": {"$exists": True}},
                                                     {"notices.code": 1, "uploaded_at": 1, "patient_id": 1}):
        p = await get_db().users.find_one({"_id": s["patient_id"]}, {"patient_code": 1})
        out.append({"summary_id": sid(s["_id"]), "patient_code": (p or {}).get("patient_code"),
                    "uploaded_at": iso(s["uploaded_at"]),
                    "notices": [{"code": n["code"], "text": NOTICE_TEXT.get(n["code"], n["code"])} for n in s["notices"]]})
    return out


@router.get("/system")
async def system(user: Principal = Depends(admin)):
    db = get_db()
    try:
        await db.command("ping")
        status = "ok"
    except Exception:
        status = "down"
    cols = []
    for name in sorted(dbmod.VALIDATORS):
        old = await db[name].count_documents({"schema_version": {"$lt": SCHEMA_VERSION}})
        missing = await db[name].count_documents({"schema_version": {"$exists": False}})
        cols.append({"name": name, "count": await db[name].count_documents({}), "older_schema": old + missing})
    jobs = [{"name": j["_id"], "last_run": iso(j.get("last_run")), "last_error": j.get("last_error")}
            async for j in db.job_locks.find({})]
    return {"db": status, "schema_version": SCHEMA_VERSION, "collections": cols, "jobs": jobs}


@router.get("/callbacks")
async def list_callbacks(user: Principal = Depends(admin)):
    """Request + masked numbers only. Never a real number."""
    out = []
    async for n in get_db().notifications.find({"type": "callback", "callback": {"$ne": None}}).sort("scheduled_at", 1):
        cb = n["callback"]
        out.append({"id": sid(n["_id"]), "task_id": sid(n.get("task_id")), "status": cb["status"],
                    "requested_at": iso(n["scheduled_at"]), "patient_mask": cb.get("patient_mask"),
                    "duration_sec": cb.get("duration_sec")})
    return out


@router.post("/callbacks/{cb_id}/start")
async def start_callback(cb_id: str, request: Request, user: Principal = Depends(admin)):
    return await callbacks.start(oid(cb_id), user.id, client_ip(request))


@router.post("/callbacks/{cb_id}/complete")
async def complete_callback(cb_id: str, request: Request, user: Principal = Depends(admin)):
    return await callbacks.complete(oid(cb_id), user.id, client_ip(request))
