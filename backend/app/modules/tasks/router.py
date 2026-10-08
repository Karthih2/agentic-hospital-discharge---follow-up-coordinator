from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.core.constants import LANGS, PUBLISHED
from app.core.db import get_db
from app.models.schemas import FlagIn, ManualTaskIn, ProviderSelectIn, ReminderIn
from app.pipeline import planner, safety_gate
from app.core.security import ratelimit
from app.core.security.access import Principal, check_access, client_ip, current_user
from app.modules.admin import callbacks
from app.modules.notifications import service as notify
from app.modules.tasks import stats
from app.modules.tasks import voice
from app.core.audit import audit
from app.modules.tasks.view import public_task
from app.core.util import iso, now, oid

router = APIRouter(tags=["tasks"])


async def load_task(task_id: str, user: Principal, action: str, request: Request):
    t = await get_db().tasks.find_one({"_id": oid(task_id)})
    if not t or t.get("published") is False:  # a draft plan does not exist for the patient until it is published
        raise HTTPException(404, "Not found")
    return t, await check_access(user, t["patient_id"], action, client_ip(request))


async def _views(patient_id, view, lang, extra: dict | None = None) -> list[dict]:
    out = []
    async for t in get_db().tasks.find({"patient_id": patient_id, **PUBLISHED, **(extra or {})}).sort("due_date", 1):
        p = await public_task(t, view, lang)
        if p:
            out.append(p)
    return out


@router.get("/patients/{pid}/tasks")
async def list_tasks(pid: str, request: Request, user: Principal = Depends(current_user)):
    patient_id = oid(pid)
    view = await check_access(user, patient_id, "view_plan", client_ip(request))
    await audit(view.actor, "view_plan", "patient", patient_id, on_behalf_of=view.on_behalf_of, ip=client_ip(request))
    return await _views(patient_id, view, user.language)


@router.get("/patients/{pid}/timeline")
async def timeline(pid: str, request: Request, user: Principal = Depends(current_user)):
    patient_id = oid(pid)
    view = await check_access(user, patient_id, "view_plan", client_ip(request))
    await audit(view.actor, "view_timeline", "patient", patient_id, on_behalf_of=view.on_behalf_of,
                ip=client_ip(request))
    tasks = await _views(patient_id, view, user.language)
    groups, no_date = OrderedDict(), []
    for t in tasks:
        if t.get("due_date"):
            groups.setdefault(t["due_date"], []).append(t)
        else:
            no_date.append(t)
    counts = {s: sum(1 for t in tasks if t["status"] == s) for s in ("Pending", "Completed", "Needs Review")}
    return {"counts": counts, "days": [{"date": d, "tasks": ts} for d, ts in sorted(groups.items())],
            "no_date": no_date}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, request: Request, user: Principal = Depends(current_user)):
    t, view = await load_task(task_id, user, "view_plan", request)
    await audit(view.actor, "view_task", "task", t["_id"], on_behalf_of=view.on_behalf_of, ip=client_ip(request))
    p = await public_task(t, view, user.language)
    if p is None:
        raise HTTPException(403, "Forbidden")
    return p


@router.post("/tasks/{task_id}/complete")
async def complete(task_id: str, request: Request, user: Principal = Depends(current_user)):
    t, view = await load_task(task_id, user, "tick", request)
    r = await get_db().tasks.update_one({"_id": t["_id"], "status": "Pending"}, {"$set": {
        "status": "Completed", "completed_at": now(), "completed_by": view.actor, "updated_at": now()}})
    if not r.modified_count:  # Needs Review -> Completed is never allowed directly
        raise HTTPException(409, "Only a Pending task can be completed")
    await stats.refresh(t["patient_id"])
    await audit(view.actor, "task_complete", "task", t["_id"], on_behalf_of=view.on_behalf_of, ip=client_ip(request))
    return {"status": "Completed"}


@router.post("/tasks/{task_id}/undo")
async def undo(task_id: str, request: Request, user: Principal = Depends(current_user)):
    t, view = await load_task(task_id, user, "tick", request)
    r = await get_db().tasks.update_one({"_id": t["_id"], "status": "Completed"}, {"$set": {
        "status": "Pending", "completed_at": None, "completed_by": None, "updated_at": now()}})
    if not r.modified_count:
        raise HTTPException(409, "Only a Completed task can be undone")
    await stats.refresh(t["patient_id"])
    await audit(view.actor, "task_undo", "task", t["_id"], on_behalf_of=view.on_behalf_of, ip=client_ip(request))
    return {"status": "Pending"}


@router.post("/tasks/{task_id}/flag")
async def flag(task_id: str, body: FlagIn, request: Request, user: Principal = Depends(current_user)):
    t, view = await load_task(task_id, user, "flag", request)
    ratelimit.limit("flag", user.id, 20, 3600)  # a flooded doctor queue helps nobody
    if t["status"] != "Pending":
        raise HTTPException(409, "Only a Pending task can be flagged")
    flags = [{"field": "item", "reason_code": "USER_FLAGGED", "note": ""}]
    if not await planner.flag_task(t, flags, "family" if view.family else "patient",
                                   body.note, only_pending=True):
        raise HTTPException(409, "Only a Pending task can be flagged")
    await audit(view.actor, "flag", "task", t["_id"], on_behalf_of=view.on_behalf_of, ip=client_ip(request))
    return {"status": "Needs Review"}


@router.post("/patients/{pid}/tasks", status_code=201)
async def manual_entry(pid: str, body: ManualTaskIn, request: Request, user: Principal = Depends(current_user)):
    """Structured form for missing or wrong items. Goes through the same safety gate as extracted items.
    A correction never edits extracted text: it adds a new task and flags the old one."""
    patient_id = oid(pid)
    view = await check_access(user, patient_id, "manual_entry", client_ip(request))
    db = get_db()
    med = body.medicine.model_dump() if body.medicine else None
    parts = [body.title, body.doctor_name, body.specialty, body.instruction, iso(body.due_date)]
    parts += list((med or {}).values())
    item = {"type": body.type, "title": body.title, "due_date": body.due_date, "due_date_text": None,
            "date_ambiguous": False, "doctor_name": body.doctor_name, "specialty": body.specialty,
            "due_time": body.due_time, "location": body.location, "phone": body.phone, "medicine": med, "instruction": body.instruction, "confidence": 1.0, "source_found": True,
            "source_line": "Manual entry: " + " | ".join(p for p in parts if p), "source_span": None}
    old = None
    if body.supersedes:
        old = await db.tasks.find_one({"_id": oid(body.supersedes), "patient_id": patient_id, **PUBLISHED})
        if not old:
            raise HTTPException(404, "Not found")
    flags = safety_gate.run_gate(item)
    if body.type == "medicine" and not any(f["reason_code"] == "MANUAL_ENTRY" for f in flags):
        # Nobody but a doctor puts a medicine into a plan: a hand-typed medicine always goes to review.
        flags.append({"field": "item", "reason_code": "MANUAL_ENTRY", "note": ""})
    task = await planner.insert_task(patient_id, None, item, flags, "manual", old["_id"] if old else None)
    if flags:
        await planner.create_review(task, flags, "gate")
    else:
        patient = await db.users.find_one({"_id": patient_id})
        await planner.finalize_clean(task, patient["language"])
        fresh = await db.tasks.find_one({"_id": task["_id"]})
        if fresh["status"] == "Pending":
            await notify.schedule_reminders(fresh)
    if old and old["status"] == "Pending":
        await planner.flag_task(old, [{"field": "item", "reason_code": "USER_FLAGGED",
                                       "note": "replaced by a manual correction"}],
                                "family" if view.family else "patient")
    await audit(view.actor, "manual_entry", "task", task["_id"], on_behalf_of=view.on_behalf_of, ip=client_ip(request))
    return await public_task(await db.tasks.find_one({"_id": task["_id"]}), view, user.language)


@router.get("/tasks/{task_id}/audio")
async def audio(task_id: str, request: Request, lang: str | None = Query(None), user: Principal = Depends(current_user)):
    t, view = await load_task(task_id, user, "listen", request)
    lang = lang or user.language
    if lang not in LANGS:
        raise HTTPException(422, "Unsupported language")
    data = await voice.audio_for(t, lang)
    await audit(view.actor, "listen", "task", t["_id"], on_behalf_of=view.on_behalf_of, ip=client_ip(request))
    return Response(data, media_type="audio/mpeg")


@router.post("/tasks/{task_id}/callback", status_code=202)
async def request_callback(task_id: str, request: Request, user: Principal = Depends(current_user)):
    t, view = await load_task(task_id, user, "callback", request)
    return await callbacks.request(t, view.actor, view.on_behalf_of, client_ip(request))


@router.post("/tasks/{task_id}/provider")
async def select_provider(task_id: str, body: ProviderSelectIn, request: Request,
                          user: Principal = Depends(current_user)):
    t, view = await load_task(task_id, user, "select_provider", request)
    db = get_db()
    if not t.get("provider_needed") or t["status"] == "Needs Review":
        raise HTTPException(409, "A provider cannot be chosen for this task")
    prov = await db.providers.find_one({"_id": oid(body.provider_id), "synthetic": True})
    if not prov:
        raise HTTPException(404, "Not found")
    await db.tasks.update_one({"_id": t["_id"]}, {"$set": {"provider_id": prov["_id"], "updated_at": now()}})
    await audit(view.actor, "select_provider", "task", t["_id"], on_behalf_of=view.on_behalf_of, ip=client_ip(request))
    return await public_task(await db.tasks.find_one({"_id": t["_id"]}), view, user.language)


@router.post("/tasks/{task_id}/reminder")
async def set_reminder(task_id: str, body: ReminderIn, request: Request, user: Principal = Depends(current_user)):
    """The Set reminder toggle on a task card."""
    t, view = await load_task(task_id, user, "tick", request)
    db = get_db()
    await db.tasks.update_one({"_id": t["_id"]}, {"$set": {"reminder_enabled": body.enabled, "updated_at": now()}})
    fresh = await db.tasks.find_one({"_id": t["_id"]})
    if body.enabled and fresh["status"] == "Pending":
        await notify.schedule_reminders(fresh)
    elif not body.enabled:
        await db.notifications.delete_many({"task_id": t["_id"], "type": "reminder", "sent_at": None})
    await audit(view.actor, "reminder_toggle", "task", t["_id"], on_behalf_of=view.on_behalf_of, ip=client_ip(request))
    return {"reminder_enabled": body.enabled}
