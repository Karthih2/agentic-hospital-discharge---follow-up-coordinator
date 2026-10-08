"""Family Hub. One hub = one family; the manager organizes, each patient stays a separate channel.
Nothing here returns clinical text: only names, roles, consent levels and counts."""
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.audit import audit
from app.core.constants import SCHEMA_VERSION
from app.core.db import get_db
from app.core.security import ratelimit
from app.core.security.access import Principal, client_ip, require_role
from app.core.security.crypto import dec
from app.core.util import iso, now, oid, sid
from app.models.schemas import AddViewerIn, AnswerInviteIn, ConsentIn, HubIn, InvitePatientIn
from app.modules.hubs import service
from app.modules.notifications import service as notify
from app.modules.tasks import stats

router = APIRouter(tags=["hubs"])
hub_user = require_role("patient", "family")


async def _name(uid) -> str | None:
    u = await get_db().users.find_one({"_id": uid}, {"name": 1})
    return dec(u["name"]) if u else None


async def _hub(hub_id: str, user: Principal, manager_only: bool = False) -> dict:
    db = get_db()
    hub = await db.family_hubs.find_one({"_id": oid(hub_id)})
    if not hub or not await db.hub_members.find_one({"hub_id": hub["_id"], "user_id": user.id}):
        raise HTTPException(404, "Not found")  # a hub you are not in does not exist for you
    if manager_only and hub["manager_id"] != user.id:
        raise HTTPException(403, "Forbidden")
    return hub


async def _patient_card(hub: dict, patient: dict, viewer: Principal) -> dict:
    db = get_db()
    card = {"patient_id": sid(patient["_id"]), "name": dec(patient["name"]), "language": patient["language"],
            "patient_code": patient.get("patient_code") if viewer.id == patient["_id"] else None,
            "is_child": patient.get("guardian_id") is not None, "access": "none", "operate": False,
            "counts": None, "next_due": None}
    if viewer.id == patient["_id"]:
        card.update(access="self", operate=True)
    else:
        c = await db.consents.find_one({"patient_id": patient["_id"], "grantee_id": viewer.id,
                                        "hub_id": hub["_id"], "revoked_at": None})
        if c:
            m = await db.hub_members.find_one({"hub_id": hub["_id"], "user_id": viewer.id,
                                               "role": {"$in": ["manager", "viewer"]}})
            card.update(access=c["level"], operate=bool(m and m["role"] == "manager" and c["level"] == "full"))
    if card["access"] != "none":
        s = await stats.get(patient["_id"])
        if card["access"] == "appointments":
            card["next_due"] = iso(s["next_appointment_due"] and s["next_appointment_due"].date())
        else:
            card["counts"] = {"Pending": s["pending"], "Completed": s["completed"], "Needs Review": s["needs_review"]}
            card["next_due"] = iso(s["next_due"] and s["next_due"].date())
    return card


async def _hub_out(hub: dict, viewer: Principal) -> dict:
    db = get_db()
    members = [m async for m in db.hub_members.find({"hub_id": hub["_id"]})]
    roles: dict = {}
    for m in members:
        roles.setdefault(m["user_id"], []).append(m["role"])
    people, patients = [], []
    for uid, rs in roles.items():
        u = await db.users.find_one({"_id": uid})
        people.append({"user_id": sid(uid), "name": dec(u["name"]), "roles": sorted(rs)})
        if "patient" in rs:
            patients.append(await _patient_card(hub, u, viewer))
    mine = sorted(roles.get(viewer.id, []))
    pending = await db.hub_invites.count_documents({"hub_id": hub["_id"], "status": "pending"}) \
        if hub["manager_id"] == viewer.id else None
    return {"id": sid(hub["_id"]), "name": hub["name"], "manager_id": sid(hub["manager_id"]),
            "manager_name": await _name(hub["manager_id"]), "my_roles": mine,
            "is_manager": hub["manager_id"] == viewer.id, "members": people, "patients": patients,
            "pending_invites": pending}


@router.post("/hubs", status_code=201)
async def create_hub(body: HubIn, request: Request, user: Principal = Depends(hub_user)):
    db = get_db()
    hub = {"name": body.name.strip(), "manager_id": user.id, "created_at": now(), "schema_version": SCHEMA_VERSION}
    hub["_id"] = (await db.family_hubs.insert_one(hub)).inserted_id
    await service.add_member(hub["_id"], user.id, "manager")
    if user.role == "patient":
        await service.add_member(hub["_id"], user.id, "patient")
    await audit(user.id, "hub_create", "hub", hub["_id"], ip=client_ip(request))
    return await _hub_out(hub, user)


@router.get("/hubs")
async def my_hubs(user: Principal = Depends(hub_user)):
    db, out, seen = get_db(), [], set()
    async for m in db.hub_members.find({"user_id": user.id}):
        if m["hub_id"] in seen:
            continue
        seen.add(m["hub_id"])
        hub = await db.family_hubs.find_one({"_id": m["hub_id"]})
        if hub:
            out.append(await _hub_out(hub, user))
    return out


@router.get("/hubs/{hub_id}")
async def hub_detail(hub_id: str, user: Principal = Depends(hub_user)):
    return await _hub_out(await _hub(hub_id, user), user)


@router.post("/hubs/{hub_id}/invite-patient", status_code=202)
async def invite_patient(hub_id: str, body: InvitePatientIn, request: Request, user: Principal = Depends(hub_user)):
    """The manager enters the patient's code. Nothing is shared until the patient (or guardian) approves,
    except when the manager IS the patient or the patient's guardian."""
    hub = await _hub(hub_id, user, manager_only=True)
    ratelimit.limit("join", user.id, 10, 3600)  # the code is short: slow down guessing
    db = get_db()
    patient = await db.users.find_one({"patient_code": body.patient_code, "role": "patient"})
    if not patient:
        raise HTTPException(404, "No patient found with that code")
    if await db.hub_members.find_one({"hub_id": hub["_id"], "user_id": patient["_id"], "role": "patient"}):
        raise HTTPException(409, "This patient is already in the hub")
    if patient["_id"] == user.id or patient.get("guardian_id") == user.id:
        await service.add_member(hub["_id"], patient["_id"], "patient")
        if patient["_id"] != user.id:
            await service.grant(patient["_id"], user.id, hub["_id"], "full", user.id, guardian=True)
        await audit(user.id, "consent_change", "patient", patient["_id"], ip=client_ip(request),
                    meta={"level": "full", "guardian": patient["_id"] != user.id})
        return {"status": "joined"}
    inv = await db.hub_invites.find_one({"hub_id": hub["_id"], "patient_id": patient["_id"], "status": "pending"})
    if not inv:
        inv = {"hub_id": hub["_id"], "kind": "patient", "patient_id": patient["_id"], "grantee_id": user.id,
               "status": "pending", "created_at": now(), "schema_version": SCHEMA_VERSION}
        inv["_id"] = (await db.hub_invites.insert_one(inv)).inserted_id
        who = patient.get("guardian_id") or patient["_id"]
        await notify.add(who, patient["_id"], "hub_invite", "hub_invite", sent=True)
    await audit(user.id, "hub_invite", "patient", patient["_id"], ip=client_ip(request))
    return {"status": "pending", "id": sid(inv["_id"])}


@router.post("/hubs/{hub_id}/viewers", status_code=201)
async def add_viewer(hub_id: str, body: AddViewerIn, request: Request, user: Principal = Depends(hub_user)):
    """Adds an existing family account to the hub. A viewer sees nothing until a patient grants consent."""
    hub = await _hub(hub_id, user, manager_only=True)
    u = await get_db().users.find_one({"login": body.login.strip().lower(), "role": "family", "is_active": True})
    if not u:
        raise HTTPException(404, "No family account with that login")
    await service.add_member(hub["_id"], u["_id"], "viewer")
    await audit(user.id, "hub_add_viewer", "hub", hub["_id"], ip=client_ip(request))
    return await _hub_out(hub, user)


# ---- invitations: answered by the patient or the guardian only
async def _my_invites(user: Principal) -> list[dict]:
    db = get_db()
    ids = [user.id] + [p["_id"] async for p in db.users.find({"guardian_id": user.id}, {"_id": 1})]
    return [i async for i in db.hub_invites.find({"patient_id": {"$in": ids}, "status": "pending"}).sort("created_at", 1)]


@router.get("/me/invites")
async def my_invites(user: Principal = Depends(hub_user)):
    db, out = get_db(), []
    for i in await _my_invites(user):
        hub = await db.family_hubs.find_one({"_id": i["hub_id"]})
        out.append({"id": sid(i["_id"]), "hub_name": hub["name"] if hub else None,
                    "manager_name": await _name(i["grantee_id"]), "patient_id": sid(i["patient_id"]),
                    "patient_name": await _name(i["patient_id"]), "created_at": iso(i["created_at"])})
    return out


async def _invite(invite_id: str, user: Principal) -> dict:
    mine = {str(i["_id"]): i for i in await _my_invites(user)}
    if invite_id not in mine:
        raise HTTPException(404, "Not found")
    return mine[invite_id]


@router.post("/invites/{invite_id}/approve")
async def approve_invite(invite_id: str, body: AnswerInviteIn, request: Request,
                         user: Principal = Depends(hub_user)):
    db = get_db()
    inv = await _invite(invite_id, user)
    await service.add_member(inv["hub_id"], inv["patient_id"], "patient")
    await service.grant(inv["patient_id"], inv["grantee_id"], inv["hub_id"], body.level, user.id,
                        guardian=user.id != inv["patient_id"])
    await db.hub_invites.update_one({"_id": inv["_id"]}, {"$set": {"status": "approved", "decided_at": now()}})
    await audit(user.id, "consent_change", "patient", inv["patient_id"], ip=client_ip(request),
                meta={"level": body.level})
    return {"status": "approved", "level": body.level}


@router.post("/invites/{invite_id}/deny")
async def deny_invite(invite_id: str, request: Request, user: Principal = Depends(hub_user)):
    inv = await _invite(invite_id, user)
    await get_db().hub_invites.update_one({"_id": inv["_id"]}, {"$set": {"status": "denied", "decided_at": now()}})
    await audit(user.id, "join_denied", "patient", inv["patient_id"], ip=client_ip(request))
    return {"status": "denied"}


# ---- consent: given and revoked by the patient (or guardian) only
@router.get("/patients/{pid}/consents")
async def list_consents(pid: str, user: Principal = Depends(hub_user)):
    db, patient_id = get_db(), oid(pid)
    await service.require_consenter(user, patient_id)
    out = []
    async for m in db.hub_members.find({"role": {"$in": ["manager", "viewer"]}}):
        if not await db.hub_members.find_one({"hub_id": m["hub_id"], "user_id": patient_id, "role": "patient"}):
            continue
        c = await db.consents.find_one({"patient_id": patient_id, "grantee_id": m["user_id"], "hub_id": m["hub_id"],
                                        "revoked_at": None})
        hub = await db.family_hubs.find_one({"_id": m["hub_id"]})
        if m["user_id"] != patient_id:
            out.append({"hub_id": sid(m["hub_id"]), "hub_name": hub["name"], "grantee_id": sid(m["user_id"]),
                        "name": await _name(m["user_id"]), "hub_role": m["role"],
                        "level": c["level"] if c else None,
                        "guardian_consent": bool(c and c.get("guardian_consent"))})
    return out


@router.put("/hubs/{hub_id}/patients/{pid}/consents/{grantee_id}")
async def set_consent(hub_id: str, pid: str, grantee_id: str, body: ConsentIn, request: Request,
                      user: Principal = Depends(hub_user)):
    db, patient_id = get_db(), oid(pid)
    patient = await service.require_consenter(user, patient_id)
    hub = await db.family_hubs.find_one({"_id": oid(hub_id)})
    if not hub or not await db.hub_members.find_one({"hub_id": hub["_id"], "user_id": patient_id, "role": "patient"}):
        raise HTTPException(404, "Not found")
    c = await service.grant(patient_id, oid(grantee_id), hub["_id"], body.level, user.id,
                            guardian=user.id != patient["_id"])
    await audit(user.id, "consent_change", "patient", patient_id, ip=client_ip(request),
                meta={"level": body.level, "guardian": user.id != patient["_id"]})
    return {"level": c["level"]}


@router.delete("/hubs/{hub_id}/patients/{pid}/consents/{grantee_id}")
async def revoke_consent(hub_id: str, pid: str, grantee_id: str, request: Request,
                         user: Principal = Depends(hub_user)):
    """Takes effect at once: every request reads the consent record, so open sessions lose access immediately."""
    patient_id = oid(pid)
    await service.require_consenter(user, patient_id)
    n = await service.revoke(patient_id, oid(grantee_id), oid(hub_id))
    if not n:
        raise HTTPException(404, "Not found")
    await audit(user.id, "consent_change", "patient", patient_id, ip=client_ip(request), meta={"revoked": True})
    return {"ok": True}
