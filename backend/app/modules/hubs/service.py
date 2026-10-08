"""Family Hub rules. A hub is a shared home for one family; each patient in it stays a separate channel.
Consent is per person, per patient, and a revoke closes the record at once (history is kept)."""
from fastapi import HTTPException

from app.core.constants import SCHEMA_VERSION
from app.core.db import get_db
from app.core.security.access import Principal
from app.core.util import now


async def can_consent_for(user: Principal, patient: dict) -> bool:
    """The patient, or the guardian of a child or of a person who cannot consent."""
    return user.id == patient["_id"] or patient.get("guardian_id") == user.id


async def require_consenter(user: Principal, patient_id) -> dict:
    p = await get_db().users.find_one({"_id": patient_id, "role": "patient"})
    if not p or not await can_consent_for(user, p):
        raise HTTPException(403, "Forbidden")
    return p


async def add_member(hub_id, user_id, role: str) -> None:
    await get_db().hub_members.update_one(
        {"hub_id": hub_id, "user_id": user_id, "role": role},
        {"$setOnInsert": {"created_at": now(), "schema_version": SCHEMA_VERSION}}, upsert=True)


async def grant(patient_id, grantee_id, hub_id, level: str, granted_by, guardian: bool = False) -> dict:
    """Close the old consent (kept as history) and open a new one."""
    db = get_db()
    member = await db.hub_members.find_one({"hub_id": hub_id, "user_id": grantee_id,
                                            "role": {"$in": ["manager", "viewer"]}})
    if not member:
        raise HTTPException(404, "Not found")
    if member["role"] == "viewer" and level == "full":
        raise HTTPException(422, "A viewer can have appointments or reminders access, not the full plan")
    await db.consents.update_many({"patient_id": patient_id, "grantee_id": grantee_id, "hub_id": hub_id,
                                   "revoked_at": None}, {"$set": {"revoked_at": now()}})
    doc = {"patient_id": patient_id, "grantee_id": grantee_id, "hub_id": hub_id, "level": level,
           "granted_by": granted_by, "guardian_consent": guardian, "granted_at": now(), "revoked_at": None,
           "schema_version": SCHEMA_VERSION}
    doc["_id"] = (await db.consents.insert_one(doc)).inserted_id
    return doc


async def revoke(patient_id, grantee_id, hub_id) -> int:
    r = await get_db().consents.update_many({"patient_id": patient_id, "grantee_id": grantee_id, "hub_id": hub_id,
                                             "revoked_at": None}, {"$set": {"revoked_at": now()}})
    return r.modified_count
