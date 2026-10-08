"""Doctor plan review. The system drafts every plan; the matched doctor reviews it here, edits, adds or removes
items, settles every flagged item, and publishes. Only the plan's own doctor can open or change it.
Nothing here is visible to the patient or family until `publish` flips the plan's tasks to `published: True`."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field

from app.core.audit import audit
from app.core.constants import REASON_TEXT, SCHEMA_VERSION
from app.core.db import get_db
from app.core.security.access import Principal, client_ip, require_role
from app.core.security.crypto import dec, dec_map, enc, enc_map
from app.core.util import d2dt, dt2d, iso, now, oid, sid
from app.models.schemas import CorrectedValues, MedicineIn, Strict, TaskType
from app.modules.notifications import service as notify
from app.modules.tasks import stats
from app.pipeline import medicine_template, planner, safety_gate, template

router = APIRouter(prefix="/plans", tags=["plans"])
doctor = require_role("doctor")
OPEN = {"$in": ["open", "in_review"]}
TYPE_ORDER = {"appointment": 0, "referral": 1, "test": 2, "medicine": 3, "date": 4, "care_instruction": 5,
              "warning_sign": 6}


class PlanTaskIn(Strict):
    type: TaskType
    title: str = Field(min_length=1, max_length=200)
    due_date: date | None = None
    due_time: str | None = Field(default=None, max_length=20)
    location: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=30)
    doctor_name: str | None = Field(default=None, max_length=100)
    specialty: str | None = Field(default=None, max_length=60)
    medicine: MedicineIn | None = None
    instruction: str | None = Field(default=None, max_length=500)


class PublishIn(Strict):
    keep_in_review: bool = False  # publish now and keep the still-flagged items with the doctor ("waiting")


# ---------------------------------------------------------------- helpers

async def _mine(summary_id: str, user: Principal, request: Request, draft_only: bool = False) -> dict:
    s = await get_db().discharge_summaries.find_one({"_id": oid(summary_id)})
    if not s or not s.get("plan_status"):
        raise HTTPException(404, "Not found")
    if s.get("plan_doctor_id") != user.id:
        await audit(user.id, "plan_access", "summary", s["_id"], "denied", ip=client_ip(request))
        raise HTTPException(403, "Forbidden")
    if draft_only and s["plan_status"] != "draft":
        raise HTTPException(409, "This plan is not a draft any more" if s["plan_status"] == "published"
                            else "The plan is still being generated")
    return s


async def _task(s: dict, task_id: str) -> dict:
    t = await get_db().tasks.find_one({"_id": oid(task_id), "summary_id": s["_id"]})
    if not t:
        raise HTTPException(404, "Not found")
    return t


def _reasons(flags: list[dict]) -> list[dict]:
    codes = list(dict.fromkeys(f["reason_code"] for f in flags))
    return [{"code": c, "text": REASON_TEXT.get(c, c)} for c in codes]


async def _doctor_view(t: dict) -> dict:
    db = get_db()
    f = dec_map(t.get("fields") or {})
    rv = await db.review_queue.find_one({"task_id": t["_id"], "status": OPEN}, {"_id": 1})
    card = medicine_template.render(dec_map(t["medicine_card"]), "en") if t.get("medicine_card") else None
    return {"id": sid(t["_id"]), "type": t["type"], "title": dec(t["title"]), "status": t["status"],
            "due_date": iso(dt2d(t.get("due_date"))), "due_date_text": t.get("due_date_text"),
            "source_line": dec(t["source_line"]), "source_span": t.get("source_span"),
            "fields": {"doctor_name": f.get("doctor_name"), "specialty": f.get("department"),
                       "instruction": f.get("instruction"), "medicine": f.get("medicine"),
                       "due_time": f.get("due_time"), "location": f.get("location"), "phone": f.get("phone")},
            "flags": t.get("flags", []), "reasons": _reasons(t.get("flags", [])),
            "confidence": t.get("confidence"), "entry_mode": t.get("entry_mode"),
            "doctor_edited": t.get("doctor_edited", False),
            "simple_text": dec(t["simple_text"]) if t.get("simple_text") else None, "medicine_card": card,
            "review_id": sid(rv["_id"]) if rv else None,
            "can_confirm": t["status"] == "Needs Review" and not any(
                fl["reason_code"] in ("EXTRACTION_FAILED",) for fl in t.get("flags", []))}


async def _counts(summary_id) -> dict:
    db = get_db()
    total = await db.tasks.count_documents({"summary_id": summary_id})
    flagged = await db.tasks.count_documents({"summary_id": summary_id, "status": "Needs Review"})
    return {"total": total, "needs_review": flagged, "ready": total - flagged}


async def _close_review(task: dict, user: Principal, outcome: str | None, corrected=None, removed=False) -> None:
    await get_db().review_queue.update_many({"task_id": task["_id"], "status": OPEN}, {"$set": {
        "status": "resolved", "outcome": outcome, "corrected_values": corrected, "resolved_by": user.id,
        "resolved_at": now(), "removed": removed}})


def _gate_item(type_: str, title: str, due, fields: dict, source_line: str) -> dict:
    return {"type": type_, "title": title, "due_date": due, "due_date_text": None, "date_ambiguous": False,
            "doctor_name": fields.get("doctor_name"), "specialty": fields.get("department"),
            "medicine": fields.get("medicine"), "instruction": fields.get("instruction"),
            "source_line": source_line, "confidence": 1.0, "source_found": True}


def _still(item: dict):
    still = safety_gate.run_gate(item, doctor_reviewed=True)
    if still:
        raise HTTPException(422, {"message": "Still incomplete",
                                  "reasons": [{**f, "text": REASON_TEXT.get(f["reason_code"])} for f in still]})


def _wording(type_: str, title: str, fields: dict) -> str | None:
    """What the plain-language rewrite starts from after a doctor edit (the original line no longer fits)."""
    if type_ == "medicine":
        return None
    return ". ".join(x for x in (title, fields.get("instruction")) if x)


async def _refresh_text(task_id, patient_id, wording: str | None) -> None:
    db = get_db()
    task = await db.tasks.find_one({"_id": task_id})
    patient = await db.users.find_one({"_id": patient_id}, {"language": 1})
    await planner.finalize_clean(task, (patient or {}).get("language", "en"), approved=True, text=wording)


# ---------------------------------------------------------------- read

@router.get("")
async def list_plans(status: str = Query("draft", pattern="^(draft|published|all)$"), user: Principal = Depends(doctor)):
    """The doctor's plans. Draft = waiting for this doctor's review."""
    db = get_db()
    q = {"plan_doctor_id": user.id}
    q["plan_status"] = {"$in": ["draft", "published"]} if status == "all" else status
    out = []
    async for s in db.discharge_summaries.find(q, {"raw_text": 0, "pipeline_log": 0}).sort("uploaded_at", -1):
        p = await db.users.find_one({"_id": s["patient_id"]}, {"name": 1, "patient_code": 1, "age_label": 1})
        out.append({"id": sid(s["_id"]), "plan_status": s["plan_status"], "status": s["status"],
                    "patient_id": sid(s["patient_id"]), "patient_name": dec(p["name"]) if p else None,
                    "patient_code": (p or {}).get("patient_code"), "age_label": (p or {}).get("age_label"),
                    "uploaded_at": iso(s["uploaded_at"]), "published_at": iso(s.get("published_at")),
                    "match_reason": (s.get("plan_match") or {}).get("reason"),
                    "extraction_method": s.get("extraction_method"), "counts": await _counts(s["_id"])})
    return out


@router.get("/{summary_id}")
async def get_plan(summary_id: str, request: Request, user: Principal = Depends(doctor)):
    db = get_db()
    s = await _mine(summary_id, user, request)
    p = await db.users.find_one({"_id": s["patient_id"]})
    tasks = [t async for t in db.tasks.find({"summary_id": s["_id"]})]
    tasks.sort(key=lambda t: ((t.get("source_span") or {}).get("start", 10 ** 9), TYPE_ORDER.get(t["type"], 9)))
    await audit(user.id, "view_plan_draft" if s["plan_status"] == "draft" else "view_plan", "summary", s["_id"],
                ip=client_ip(request))
    m = s.get("plan_match") or {}
    colors = {"appointment": "blue", "test": "blue", "referral": "blue", "medicine": "yellow", "warning_sign": "red"}
    views = [await _doctor_view(t) for t in tasks]
    return {
        "id": sid(s["_id"]), "plan_status": s["plan_status"], "status": s["status"],
        "uploaded_at": iso(s["uploaded_at"]), "published_at": iso(s.get("published_at")),
        "extraction_method": s.get("extraction_method"),
        "patient": {"id": sid(s["patient_id"]), "name": dec(p["name"]) if p else None,
                    "patient_code": (p or {}).get("patient_code"), "language": (p or {}).get("language"),
                    "age_label": (p or {}).get("age_label")},
        "match": {"reason": m.get("reason"), "attending": m.get("attending"),
                  "attending_specialty": m.get("attending_specialty")},
        "summary": {"raw_text": dec(s["raw_text"]), "discharge_date": iso(dt2d(s.get("discharge_date"))),
                    "header": dec_map(s.get("header") or {}), "diagnoses": dec_map(s.get("diagnoses") or {}),
                    "notices": [{"code": n["code"], "text": template.NOTICE_TEXT.get(n["code"], n["code"]),
                                 "line": dec(n["line"]) if n.get("line") else None} for n in s.get("notices", [])],
                    "highlights": [{"task_id": v["id"], "type": v["type"], "status": v["status"],
                                    "color": colors.get(v["type"], "gray"), **v["source_span"]}
                                   for v in views if v["source_span"]]},
        "tasks": views, "counts": await _counts(s["_id"])}


# ---------------------------------------------------------------- edit (draft only)

@router.patch("/{summary_id}/tasks/{task_id}")
async def edit_task(summary_id: str, task_id: str, body: CorrectedValues, request: Request,
                    user: Principal = Depends(doctor)):
    """Change any value. The gate re-checks the NEW values; a flagged item becomes Pending once complete."""
    db = get_db()
    s = await _mine(summary_id, user, request, draft_only=True)
    t = await _task(s, task_id)
    cv = body.model_dump(exclude_unset=True)
    fields = dec_map(t.get("fields") or {})
    title = cv.get("title") or dec(t["title"])
    due = cv["due_date"] if "due_date" in cv else dt2d(t.get("due_date"))
    for k_in, k_out in (("doctor_name", "doctor_name"), ("specialty", "department"), ("instruction", "instruction"),
                        ("due_time", "due_time"), ("location", "location"), ("phone", "phone")):
        if k_in in cv:
            fields[k_out] = cv[k_in] or None
    if "medicine" in cv and cv["medicine"] is not None:
        fields["medicine"] = {**(fields.get("medicine") or {}), **cv["medicine"]}
    item = _gate_item(t["type"], title, due, fields, dec(t["source_line"]))
    _still(item)
    needed, spec = planner.provider_info(item)
    await db.task_revisions.insert_one({
        "task_id": t["_id"], "patient_id": t["patient_id"], "revised_by": user.id, "summary_id": s["_id"],
        "previous": {"title": t["title"], "due_date": t.get("due_date"), "fields": t.get("fields"),
                     "status": t["status"]}, "kind": "plan_edit", "created_at": now(),
        "schema_version": SCHEMA_VERSION})
    await db.tasks.update_one({"_id": t["_id"]}, {"$set": {
        "title": enc(title), "due_date": d2dt(due), "due_date_text": None if "due_date" in cv else t.get("due_date_text"),
        "fields": enc_map(fields), "status": "Pending", "flags": [], "confidence": 1.0, "doctor_edited": True,
        "specialty": spec, "provider_needed": needed, "simple_text": None, "translations": {}, "medicine_card": None,
        "updated_at": now()}})
    await _close_review(t, user, "corrected", enc_map({k: (iso(v) if isinstance(v, date) else v) for k, v in cv.items()
                                                         if not isinstance(v, dict)}))
    await _refresh_text(t["_id"], t["patient_id"], _wording(t["type"], title, fields))
    await audit(user.id, "plan_edit_task", "task", t["_id"], ip=client_ip(request))
    return await _doctor_view(await db.tasks.find_one({"_id": t["_id"]}))


@router.post("/{summary_id}/tasks/{task_id}/confirm")
async def confirm_task(summary_id: str, task_id: str, request: Request, user: Principal = Depends(doctor)):
    """Accept a flagged item exactly as written on the summary."""
    db = get_db()
    s = await _mine(summary_id, user, request, draft_only=True)
    t = await _task(s, task_id)
    if t["status"] != "Needs Review":
        raise HTTPException(409, "Only a flagged item can be confirmed")
    if any(f["reason_code"] == "EXTRACTION_FAILED" for f in t.get("flags", [])):
        raise HTTPException(422, "This item has no real content. Edit its values or remove it.")
    r = await db.tasks.update_one({"_id": t["_id"], "status": "Needs Review"}, {"$set": {
        "status": "Pending", "flags": [], "updated_at": now()}})
    if not r.modified_count:
        raise HTTPException(409, "Only a flagged item can be confirmed")
    await _close_review(t, user, "confirmed")
    await _refresh_text(t["_id"], t["patient_id"], None)
    await audit(user.id, "plan_confirm_task", "task", t["_id"], ip=client_ip(request))
    return await _doctor_view(await db.tasks.find_one({"_id": t["_id"]}))


@router.delete("/{summary_id}/tasks/{task_id}")
async def remove_task(summary_id: str, task_id: str, request: Request, user: Principal = Depends(doctor)):
    """Take an item out of the draft (a history line, a duplicate). The previous values are kept in revisions."""
    db = get_db()
    s = await _mine(summary_id, user, request, draft_only=True)
    t = await _task(s, task_id)
    await db.task_revisions.insert_one({
        "task_id": t["_id"], "patient_id": t["patient_id"], "revised_by": user.id, "summary_id": s["_id"],
        "previous": {k: t.get(k) for k in ("type", "title", "due_date", "fields", "status", "source_line")},
        "kind": "plan_remove", "created_at": now(), "schema_version": SCHEMA_VERSION})
    await _close_review(t, user, None, removed=True)
    await db.notifications.delete_many({"task_id": t["_id"]})
    await db.tasks.delete_one({"_id": t["_id"]})
    await audit(user.id, "plan_remove_task", "task", t["_id"], ip=client_ip(request))
    return {"removed": sid(t["_id"]), "counts": await _counts(s["_id"])}


@router.post("/{summary_id}/tasks", status_code=201)
async def add_task(summary_id: str, body: PlanTaskIn, request: Request, user: Principal = Depends(doctor)):
    """An item the summary missed. It must be complete; it is labelled as added by the doctor."""
    db = get_db()
    s = await _mine(summary_id, user, request, draft_only=True)
    med = body.medicine.model_dump() if body.medicine else None
    parts = [body.title, body.doctor_name, body.specialty, body.instruction, iso(body.due_date)]
    parts += [v for v in (med or {}).values() if v]
    item = {"type": body.type, "title": body.title, "due_date": body.due_date, "due_date_text": None,
            "date_ambiguous": False, "doctor_name": body.doctor_name, "specialty": body.specialty,
            "due_time": body.due_time, "location": body.location, "phone": body.phone, "medicine": med,
            "instruction": body.instruction, "confidence": 1.0, "source_found": True,
            "source_line": "Added by your doctor: " + " | ".join(p for p in parts if p), "source_span": None}
    _still(item)
    t = await planner.insert_task(s["patient_id"], s["_id"], item, [], "doctor", published=False)
    await db.tasks.update_one({"_id": t["_id"]}, {"$set": {"doctor_edited": True}})
    await _refresh_text(t["_id"], s["patient_id"], _wording(body.type, body.title, {"instruction": body.instruction}))
    await audit(user.id, "plan_add_task", "task", t["_id"], ip=client_ip(request))
    return await _doctor_view(await db.tasks.find_one({"_id": t["_id"]}))


# ---------------------------------------------------------------- publish

@router.post("/{summary_id}/publish")
async def publish(summary_id: str, body: PublishIn, request: Request, user: Principal = Depends(doctor)):
    """Release the plan to the patient (and family, within their consent). One time, atomic."""
    db = get_db()
    s = await _mine(summary_id, user, request, draft_only=True)
    c = await _counts(s["_id"])
    if c["total"] == 0:
        raise HTTPException(409, {"message": "The plan has no items. Add at least one before publishing.", **c})
    if c["needs_review"] and not body.keep_in_review:
        raise HTTPException(409, {"message": f"{c['needs_review']} item(s) still need your review. Confirm, edit or "
                                             f"remove them, or publish and keep them with you.", **c})
    claimed = await db.discharge_summaries.update_one(
        {"_id": s["_id"], "plan_status": "draft", "plan_doctor_id": user.id},
        {"$set": {"plan_status": "published", "published_at": now(), "published_by": user.id}})
    if not claimed.modified_count:
        raise HTTPException(409, "This plan is not a draft any more")
    await db.tasks.update_many({"summary_id": s["_id"]}, {"$set": {"published": True, "updated_at": now()}})
    task_ids = []
    async for t in db.tasks.find({"summary_id": s["_id"]}):
        task_ids.append(t["_id"])
        if t["status"] == "Pending":
            await notify.schedule_reminders(t)
    kept = await db.review_queue.update_many({"task_id": {"$in": task_ids}, "status": OPEN},
                                             {"$set": {"plan_draft": False}})
    await stats.refresh(s["patient_id"])
    patient = await db.users.find_one({"_id": s["patient_id"]}, {"can_login": 1})
    recipients = ([s["patient_id"]] if patient and patient.get("can_login", True) else [])
    recipients += [g async for g in _grantees(s["patient_id"]) if g not in recipients]
    for r in recipients:
        await notify.add(r, s["patient_id"], "plan_published", "plan_published", sent=True)
    if kept.modified_count:
        await notify.add(s["patient_id"], s["patient_id"], "review_waiting", "review_waiting", sent=True)
    await audit(user.id, "publish_plan", "summary", s["_id"], ip=client_ip(request),
                meta={"tasks": c["total"], "kept_in_review": c["needs_review"]})
    return {"plan_status": "published", "counts": await _counts(s["_id"])}


async def _grantees(patient_id):
    async for x in get_db().consents.find({"patient_id": patient_id, "revoked_at": None}, {"grantee_id": 1}):
        yield x["grantee_id"]
