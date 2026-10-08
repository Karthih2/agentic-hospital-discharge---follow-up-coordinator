import hashlib
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile

from app.core.config import settings
from app.core.constants import SCHEMA_VERSION, WAITING
from app.core.db import get_db
from app.pipeline import orchestrator
from app.pipeline.reader import MESSAGES, InputError, check_text, read_upload
from app.core.security import ratelimit
from app.core.security.access import Principal, check_access, client_ip, current_user
from app.core.security.crypto import dec, dec_map, enc
from app.core.audit import audit
from app.core.util import d2dt, now, oid, sid

router = APIRouter(tags=["summaries"])


@router.post("/patients/{pid}/summaries", status_code=202)
async def upload(pid: str, request: Request, background: BackgroundTasks,
                 file: UploadFile | None = File(None), text: str | None = Form(None),
                 discharge_date: date | None = Form(None), user: Principal = Depends(current_user)):
    ip, patient_id = client_ip(request), oid(pid)
    view = await check_access(user, patient_id, "upload", ip)
    ratelimit.limit("upload", user.id, 20, 3600)
    db = get_db()
    source, raw, error = "text", "", None
    try:
        if file is not None:
            data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
            raw, source = read_upload(data)
        elif text is not None:
            raw = text
            if len(raw.encode()) > settings.max_upload_mb * 1024 * 1024:
                raise InputError("FILE_TOO_LARGE")
        raw = check_text(raw)
    except InputError as e:
        error = e.code
    rec = {"patient_id": patient_id, "uploaded_by": user.id, "source": source,
           "raw_text": enc(raw), "text_hash": hashlib.sha256(raw.encode()).hexdigest() if raw else None,
           "discharge_date": d2dt(discharge_date), "status": "needs_manual" if error else "uploaded",
           "error_code": error, "pipeline_log": [], "uploaded_at": now(), "schema_version": SCHEMA_VERSION}
    if not error:
        dup = await db.discharge_summaries.find_one(
            {"patient_id": patient_id, "text_hash": rec["text_hash"], "status": "ready"})
        if dup:
            return {"id": sid(dup["_id"]), "status": "ready", "duplicate": True}
    rec["_id"] = (await db.discharge_summaries.insert_one(rec)).inserted_id
    await audit(view.actor, "upload_summary", "summary", rec["_id"], result="error" if error else "ok",
                on_behalf_of=view.on_behalf_of, ip=ip)
    if error:
        return {"id": sid(rec["_id"]), "status": "needs_manual", "error_code": error, "message": MESSAGES[error],
                "next": "manual_entry"}
    background.add_task(orchestrator.run, rec["_id"])
    return {"id": sid(rec["_id"]), "status": "uploaded"}


@router.get("/patients/{pid}/summaries")
async def list_summaries(pid: str, request: Request, user: Principal = Depends(current_user)):
    patient_id = oid(pid)
    view = await check_access(user, patient_id, "upload", client_ip(request))
    db, out = get_db(), []
    # Subset pattern: list screens read only the header fields, never raw_text or the pipeline log
    proj = {"raw_text": 0, "pipeline_log": 0, "header": 0, "diagnoses": 0, "notices": 0}
    async for s in db.discharge_summaries.find({"patient_id": patient_id}, proj).sort("uploaded_at", -1).limit(50):
        counts = {"Pending": 0, "Completed": 0, "Needs Review": 0}
        async for t in db.tasks.find({"summary_id": s["_id"]}, {"status": 1}):
            counts[t["status"]] += 1
        out.append({"id": sid(s["_id"]), "uploaded_at": s["uploaded_at"].isoformat(), "status": s["status"],
                    "error_code": s.get("error_code"), "counts": counts})
    await audit(view.actor, "list_summaries", "patient", patient_id, on_behalf_of=view.on_behalf_of, ip=client_ip(request))
    return out


async def _summary(sid_: str, user, action: str, request):
    s = await get_db().discharge_summaries.find_one({"_id": oid(sid_)})
    if not s:
        raise HTTPException(404, "Not found")
    view = await check_access(user, s["patient_id"], action, client_ip(request))
    return s, view


@router.get("/summaries/{summary_id}/status")
async def status(summary_id: str, request: Request, user: Principal = Depends(current_user)):
    s, _ = await _summary(summary_id, user, "upload", request)
    db = get_db()
    counts = {}
    if s["status"] in ("ready", "needs_manual"):
        counts = {"tasks": await db.tasks.count_documents({"summary_id": s["_id"]}),
                  "needs_review": await db.tasks.count_documents({"summary_id": s["_id"], "status": "Needs Review"})}
    return {"id": sid(s["_id"]), "status": s["status"], "error_code": s.get("error_code"),
            "message": MESSAGES.get(s.get("error_code")), "counts": counts,
            "steps": [{"step": p["step"], "ok": p["ok"]} for p in s.get("pipeline_log", [])]}


def _redact(raw: str, spans: list[dict], locked: list[tuple[int, int]]):
    """Family without operate rights must not read flagged text. Replace it and shift the other highlights."""
    merged = []
    for a, b in sorted(locked):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    out, pos, shift_at = [], 0, []
    for a, b in merged:
        out += [raw[pos:a], f"[{WAITING}]"]
        shift_at.append((a, b, len(WAITING) + 2 - (b - a)))
        pos = b
    out.append(raw[pos:])

    def move(p):
        d = 0
        for a, b, delta in shift_at:
            if p >= b:
                d += delta
            elif p > a:
                return None
        return p + d
    kept = []
    for sp in spans:
        s0, e0 = move(sp["start"]), move(sp["end"])
        if s0 is not None and e0 is not None:
            kept.append({**sp, "start": s0, "end": e0})
    return "".join(out), kept


@router.get("/summaries/{summary_id}")
async def get_summary(summary_id: str, request: Request, user: Principal = Depends(current_user)):
    s, view = await _summary(summary_id, user, "view_original", request)
    raw, spans, locked = dec(s["raw_text"]), [], []
    async for t in get_db().tasks.find({"summary_id": s["_id"]}):
        sp = t.get("source_span")
        if not sp:
            continue
        if t["status"] == "Needs Review" and view.locks_review:
            locked.append((sp["start"], sp["end"]))
        else:
            spans.append({"task_id": sid(t["_id"]), "type": t["type"], "status": t["status"],
                          "start": sp["start"], "end": sp["end"]})
    if locked:
        raw, spans = _redact(raw, spans, locked)
    await audit(view.actor, "view_original", "summary", s["_id"], on_behalf_of=view.on_behalf_of,
                ip=client_ip(request))
    colors = {"appointment": "blue", "test": "blue", "referral": "blue", "medicine": "yellow",
              "warning_sign": "red"}
    # "From your summary": shown verbatim, never explained. Diagnoses go to the patient (and the doctor) only.
    return {"id": sid(s["_id"]), "raw_text": raw, "discharge_date": s["discharge_date"].date().isoformat()
            if s.get("discharge_date") else None,
            "header": dec_map(s.get("header") or {}),
            "diagnoses": None if view.family else dec_map(s.get("diagnoses") or {}),
            "highlights": [{**h, "color": colors.get(h["type"], "gray")} for h in spans]}
