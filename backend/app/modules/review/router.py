"""Doctor review. Doctors reach clinical content ONLY here, and only for items assigned to them."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.audit import audit
from app.core.constants import APPT_TYPES, REASON_TEXT
from app.core.db import get_db
from app.core.security.access import Principal, client_ip, require_role
from app.core.security.crypto import dec, dec_map, enc, enc_map
from app.core.util import d2dt, dt2d, iso, now, oid, sid
from app.models.schemas import ResolveIn
from app.modules.notifications import service as notify
from app.modules.tasks import stats
from app.pipeline import planner, safety_gate, template

router = APIRouter(prefix="/review", tags=["review"])
doctor = require_role("doctor")


async def _mine(review_id: str, user: Principal, request: Request) -> dict:
    rv = await get_db().review_queue.find_one({"_id": oid(review_id)})
    if not rv:
        raise HTTPException(404, "Not found")
    if rv.get("assigned_doctor_id") != user.id:  # also blocks self-assignment: only the admin assigns
        await audit(user.id, "review_access", "review", rv["_id"], "denied", ip=client_ip(request))
        raise HTTPException(403, "Forbidden")
    return rv


def _reasons(codes: list[str]) -> list[dict]:
    return [{"code": c, "text": REASON_TEXT.get(c, c)} for c in codes]


@router.get("/queue")
async def queue(type: str | None = Query(None, max_length=30), sort: str = Query("flagged", pattern="^(flagged|age)$"),
                user: Principal = Depends(doctor)):
    """Sort 'flagged' = newest first (date flagged); 'age' = oldest first. Built from the review's own snapshot."""
    db = get_db()
    # items of a draft plan are worked on in the plan editor (/plans); this queue holds published-plan items
    q = {"assigned_doctor_id": user.id, "status": {"$in": ["open", "in_review"]}, "plan_draft": {"$ne": True}}
    if type:
        q["snapshot.task_type"] = type
    rows = [rv async for rv in db.review_queue.find(q).sort("created_at", 1 if sort == "age" else -1)]
    names = {u["_id"]: dec(u["name"]) async for u in db.users.find(
        {"_id": {"$in": list({r["patient_id"] for r in rows})}}, {"name": 1})}
    t = now().replace(tzinfo=None)
    return [{"id": sid(rv["_id"]), "status": rv["status"], "reasons": rv["reasons"], "reason_text": rv["reason_text"],
             "patient_name": names.get(rv["patient_id"]), "patient_code": rv["snapshot"].get("patient_code"),
             "task_type": rv["snapshot"]["task_type"], "raised_by": rv["raised_by"], "created_at": iso(rv["created_at"]),
             "age_hours": round((t - rv["created_at"].replace(tzinfo=None)).total_seconds() / 3600, 1)}
            for rv in rows]


@router.get("/patients")
async def my_patients(user: Principal = Depends(doctor)):
    """Read-only list of the doctor's patients: counts and appointment titles and dates. No plan editing here."""
    db = get_db()
    me = await db.doctors.find_one({"user_id": user.id}) or {}
    ids = set(me.get("assigned_patient_ids", []))
    async for rv in db.review_queue.find({"assigned_doctor_id": user.id, "status": {"$in": ["open", "in_review"]}},
                                         {"patient_id": 1}):
        ids.add(rv["patient_id"])
    out = []
    for pid in ids:
        p = await db.users.find_one({"_id": pid})
        if not p:
            continue
        s = await stats.get(pid)
        appts = [{"title": dec(t["title"]), "due_date": iso(dt2d(t.get("due_date"))), "status": t["status"]}
                 async for t in db.tasks.find({"patient_id": pid, "type": {"$in": list(APPT_TYPES)},
                                               "status": {"$ne": "Needs Review"}}).sort("due_date", 1)]
        out.append({"patient_id": sid(pid), "name": dec(p["name"]), "patient_code": p.get("patient_code"),
                    "counts": {"Pending": s["pending"], "Completed": s["completed"], "Needs Review": s["needs_review"]},
                    "appointments": appts})
    return sorted(out, key=lambda x: x["name"])


@router.get("/{review_id}")
async def detail(review_id: str, request: Request, user: Principal = Depends(doctor)):
    db = get_db()
    rv = await _mine(review_id, user, request)
    t = await db.tasks.find_one({"_id": rv["task_id"]})
    if rv["status"] == "open":
        await db.review_queue.update_one({"_id": rv["_id"]}, {"$set": {"status": "in_review"}})
    await audit(user.id, "view_review", "review", rv["_id"], ip=client_ip(request))
    p = await db.users.find_one({"_id": rv["patient_id"]}, {"name": 1, "language": 1, "patient_code": 1})
    summary = await db.discharge_summaries.find_one({"_id": t.get("summary_id")}) if t.get("summary_id") else None
    fields = dec_map(t["fields"])
    return {"id": sid(rv["_id"]), "status": "in_review" if rv["status"] == "open" else rv["status"],
            "patient_name": dec(p["name"]) if p else None, "patient_code": (p or {}).get("patient_code"),
            "reasons": rv["reasons"], "reason_text": rv["reason_text"], "reason_list": _reasons(rv["reasons"]),
            "user_note": dec(rv["user_note"]) if rv.get("user_note") else None,
            "summary": None if not summary else {
                "id": sid(summary["_id"]), "raw_text": dec(summary["raw_text"]), "source_span": t.get("source_span"),
                "header": dec_map(summary.get("header") or {}), "diagnoses": dec_map(summary.get("diagnoses") or {}),
                "notices": [{"code": n["code"], "text": template.NOTICE_TEXT.get(n["code"], n["code"]),
                             "line": dec(n["line"]) if n.get("line") else None}
                            for n in summary.get("notices", [])]},
            "task": {"id": sid(t["_id"]), "type": t["type"], "title": dec(t["title"]),
                     "source_line": dec(t["source_line"]), "due_date": iso(dt2d(t.get("due_date"))),
                     "due_date_text": t.get("due_date_text"), "fields": fields,
                     "simple_text": dec(t["simple_text"]) if t.get("simple_text") else None,
                     "flags": t["flags"]}}


def _gate_item(task: dict, fields: dict, due) -> dict:
    return {"type": task["type"], "title": dec(task["title"]), "due_date": due, "due_date_text": None,
            "date_ambiguous": False, "doctor_name": fields.get("doctor_name"), "specialty": fields.get("department"),
            "medicine": fields.get("medicine"), "instruction": fields.get("instruction"),
            "source_line": dec(task["source_line"]), "confidence": 1.0, "source_found": True}


@router.post("/{review_id}/resolve")
async def resolve(review_id: str, body: ResolveIn, request: Request, user: Principal = Depends(doctor)):
    db = get_db()
    rv = await _mine(review_id, user, request)
    if rv["status"] == "resolved":
        raise HTTPException(409, "Already resolved")
    if body.outcome == "confirmed" and "EXTRACTION_FAILED" in rv["reasons"]:
        raise HTTPException(422, "This item has no real content. Enter the values with outcome corrected.")
    task = await db.tasks.find_one({"_id": rv["task_id"]})
    set_ = {"status": "Pending", "flags": [], "updated_at": now()}
    corrected = None

    if body.outcome == "corrected":
        if not body.corrected_values:
            raise HTTPException(422, "corrected_values required")
        cv = body.corrected_values.model_dump(exclude_none=True)
        fields = dec_map(task["fields"])
        due = dt2d(task.get("due_date"))
        title = dec(task["title"])
        if "title" in cv:
            title = cv["title"]
        if "due_date" in cv:
            due = cv["due_date"]
        for k_in, k_out in (("doctor_name", "doctor_name"), ("specialty", "department"), ("instruction", "instruction"),
                            ("due_time", "due_time"), ("location", "location"), ("phone", "phone")):
            if k_in in cv:
                fields[k_out] = cv[k_in]
        if "medicine" in cv:
            fields["medicine"] = {**(fields.get("medicine") or {}), **cv["medicine"]}
        item = _gate_item({**task, "title": enc(title)}, fields, due)
        still = safety_gate.run_gate(item, doctor_reviewed=True)  # the gate re-checks the NEW values
        if still:
            raise HTTPException(422, {"message": "Still incomplete",
                                      "reasons": [{**f, "text": REASON_TEXT.get(f["reason_code"])} for f in still]})
        needed, spec = planner.provider_info(item)
        # Document Versioning: the values being replaced are kept, linked to the task
        await db.task_revisions.insert_one({
            "task_id": task["_id"], "patient_id": task["patient_id"], "revised_by": user.id, "review_id": rv["_id"],
            "previous": {"title": task["title"], "due_date": task.get("due_date"), "fields": task["fields"]},
            "created_at": now(), "schema_version": 2})
        set_.update(title=enc(title), due_date=d2dt(due), fields=enc_map(fields), due_date_text=None,
                    specialty=spec, provider_needed=needed, confidence=1.0)
        corrected = enc_map(cv | {"due_date": iso(cv.get("due_date"))} if "due_date" in cv else cv)

    await db.review_queue.update_one({"_id": rv["_id"]}, {"$set": {
        "status": "resolved", "outcome": body.outcome, "corrected_values": corrected,
        "resolved_by": user.id, "resolved_at": now()}})
    await db.tasks.update_one({"_id": task["_id"]}, {"$set": set_})

    task = await db.tasks.find_one({"_id": task["_id"]})  # now approved: build medicine card / plain language
    patient = await db.users.find_one({"_id": task["patient_id"]})
    await planner.finalize_clean(task, patient["language"], approved=True)
    fresh = await db.tasks.find_one({"_id": task["_id"]})
    published = fresh.get("published", True)
    if fresh["status"] == "Pending" and published:  # a draft plan schedules nothing until it is published
        await notify.schedule_reminders(fresh)
    await stats.refresh(task["patient_id"])
    if published:
        await notify.add(task["patient_id"], task["patient_id"], "review_waiting", "review_resolved",
                         task_id=task["_id"], sent=True)
    await audit(user.id, "resolve_review", "review", rv["_id"], ip=client_ip(request),
                meta={"outcome": body.outcome})
    return {"status": "resolved", "task_status": fresh["status"]}
