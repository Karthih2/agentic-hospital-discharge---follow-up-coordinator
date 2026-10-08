"""Authentication dependency, role guard and the ONE shared access check (SECURITY.md 5.3).
Consent lives in MongoDB (`consents` + `hub_members`) and is read on every request, so a revoke is immediate."""
from dataclasses import dataclass

from bson import ObjectId
from fastapi import Depends, HTTPException, Request

from app.core.audit import audit
from app.core.db import get_db
from app.core.security.auth import decode_access, verify_csrf
from app.core.util import oid


@dataclass
class Principal:
    id: ObjectId
    role: str
    language: str


@dataclass
class View:
    level: str            # full | appointments | reminders
    operator: bool        # hub manager with "full" consent: may act for the patient
    actor: ObjectId
    on_behalf_of: ObjectId | None
    family: bool = False  # someone other than the patient
    hub_role: str | None = None

    @property
    def locks_review(self) -> bool:
        """Family never reads an item that is waiting for a doctor, whatever their consent level."""
        return self.family


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def current_user(request: Request) -> Principal:
    token = request.cookies.get("access_token")
    if token:
        verify_csrf(request)
    else:
        auth = request.headers.get("authorization", "")
        token = auth[7:] if auth.lower().startswith("bearer ") else None
    if not token:
        raise HTTPException(401, "Not authenticated")
    p = decode_access(token)
    user = await get_db().users.find_one({"_id": oid(p["sub"]), "is_active": True})
    if not user:
        raise HTTPException(401, "Not authenticated")
    return Principal(user["_id"], user["role"], user["language"])


def require_role(*roles: str):
    async def dep(user: Principal = Depends(current_user)) -> Principal:
        if user.role not in roles:
            await audit(user.id, "role_denied", result="denied")
            raise HTTPException(403, "Forbidden")
        return user
    return dep


# action -> (patient allowed, family rule). Deny by default: unknown action or role => 403.
# family rule: any | full (full level) | operate (hub manager with full level) | None (never)
ACTIONS = {
    "upload": (True, "operate"),
    "manual_entry": (True, "operate"),
    "view_plan": (True, "any"),
    "view_original": (True, "full"),
    "tick": (True, "operate"),
    "flag": (True, "full"),
    "callback": (True, "operate"),      # TECH_STACK 10.3: patient or the manager acting for them
    "listen": (True, "full"),
    "select_provider": (True, "operate"),
    "manage_consent": (True, None),
    "view_audit": (True, None),
}


async def hub_link(user_id, patient_id) -> dict | None:
    """The strongest active consent this person holds for this patient, with their role in that hub."""
    db, best = get_db(), None
    async for c in db.consents.find({"patient_id": patient_id, "grantee_id": user_id, "revoked_at": None}):
        m = await db.hub_members.find_one({"hub_id": c["hub_id"], "user_id": user_id,
                                           "role": {"$in": ["manager", "viewer"]}})
        if not m:
            continue
        cand = {"level": c["level"], "hub_role": m["role"], "hub_id": c["hub_id"],
                "operate": c["level"] == "full" and m["role"] == "manager"}
        if best is None or (cand["operate"], cand["level"] == "full") > (best["operate"], best["level"] == "full"):
            best = cand
    return best


async def check_access(user: Principal, patient_id: ObjectId, action: str, ip: str | None = None) -> View:
    """Called by every endpoint that touches a patient's data. Raises 403 on any failure."""
    patient_ok, fam_rule = ACTIONS.get(action, (False, None))

    async def deny():
        await audit(user.id, action, "patient", patient_id, "denied", ip=ip)
        raise HTTPException(403, "Forbidden")

    if user.role == "patient" and patient_ok and user.id == patient_id:
        return View("full", False, user.id, None)
    if user.role in ("patient", "family") and fam_rule and user.id != patient_id:
        link = await hub_link(user.id, patient_id)
        if link:
            level, operate = link["level"], link["operate"]
            if fam_rule == "any" or (fam_rule == "operate" and operate) or (fam_rule == "full" and level == "full"):
                return View(level, operate, user.id, patient_id, family=True, hub_role=link["hub_role"])
    await deny()
