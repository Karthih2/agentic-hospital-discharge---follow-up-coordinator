from fastapi import APIRouter, Depends

from app.core.audit import events as audit_events
from app.core.constants import DISCLAIMER, MEDICINE_LABELS, PROVIDER_LABEL
from app.core.db import get_db
from app.core.security.access import Principal, current_user, require_role
from app.modules.notifications.service import render
from app.core.util import iso, now, sid

router = APIRouter(tags=["misc"])


@router.get("/meta")
async def meta():
    """Fixed texts the interface must show. Public, no data."""
    return {"disclaimer": DISCLAIMER, "provider_label": PROVIDER_LABEL, "medicine_labels": MEDICINE_LABELS}


@router.get("/me/notifications")
async def my_notifications(user: Principal = Depends(current_user)):
    out = []
    async for n in get_db().notifications.find({"recipient_id": user.id, "sent_at": {"$ne": None}}
                                               ).sort("sent_at", -1).limit(100):
        item = {"id": sid(n["_id"]), "type": n["type"], "task_id": sid(n.get("task_id")),
                "text": render(n["template_key"], user.language), "sent_at": iso(n["sent_at"]),
                "read": n.get("read_at") is not None}
        if n.get("callback"):  # the patient sees the HOSPITAL side's masked number only
            cb = n["callback"]
            item["callback"] = {"status": cb["status"], "masked_number": cb.get("provider_mask"),
                                "duration_sec": cb.get("duration_sec")}
        out.append(item)
    return out


@router.post("/me/notifications/{nid}/read")
async def mark_read(nid: str, user: Principal = Depends(current_user)):
    from app.core.util import oid
    await get_db().notifications.update_one({"_id": oid(nid), "recipient_id": user.id}, {"$set": {"read_at": now()}})
    return {"ok": True}


@router.get("/me/audit")
async def my_audit(user: Principal = Depends(require_role("patient"))):
    """My own activity and who viewed my plan. IP addresses are not shown."""
    out = []
    for e in await audit_events({"$or": [{"actor_id": user.id}, {"on_behalf_of": user.id}, {"target_id": user.id}]}):
        out.append({"actor_id": sid(e["actor_id"]) if e["actor_id"] != "system" else "system",
                    "on_behalf_of": sid(e.get("on_behalf_of")), "action": e["action"],
                    "target_type": e.get("target_type"), "target_id": sid(e.get("target_id")),
                    "result": e["result"], "ts": iso(e["ts"])})
    return out
