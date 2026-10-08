"""Upgrade older documents to the current schema version.   python -m scripts.migrate

Schema Versioning pattern: every document carries `schema_version`. This script finds documents with an older (or
no) version, applies the matching upgrade, and stamps them. It is idempotent: a second run changes nothing.

v1 -> v2:
  * `family_members` + old `consents` become `family_hubs` (one per patient, the first operator is the manager),
    `hub_members` and the new `consents` (grantee, hub, level); then the old collections are dropped
  * `review_queue` gets a `snapshot` (Extended Reference)
  * `audit_log` flat events are packed into per-actor, per-day buckets
  * every other document is stamped schema_version 2
"""
import asyncio

from app.core.constants import SCHEMA_VERSION
from app.core.db import RULES as VALIDATORS, get_db, init_db
from app.core.util import now


async def _member(db, hub_id, uid, role) -> None:
    await db.hub_members.update_one({"hub_id": hub_id, "user_id": uid, "role": role},
                                    {"$setOnInsert": {"created_at": now(), "schema_version": SCHEMA_VERSION}},
                                    upsert=True)


async def _hubs_from_family() -> int:
    db, n = get_db(), 0
    if "family_members" not in await db.list_collection_names():
        return 0
    by_patient: dict = {}
    async for fm in db.family_members.find({"revoked_at": None}):
        by_patient.setdefault(fm["patient_id"], []).append(fm)
    for pid, fms in by_patient.items():
        if await db.family_hubs.find_one({"legacy_patient_id": pid}):
            continue
        manager = next((f for f in fms if f.get("can_operate")), fms[0])
        hub = {"name": "Family hub", "manager_id": manager["user_id"], "created_at": now(), "legacy_patient_id": pid,
               "schema_version": SCHEMA_VERSION}
        hub["_id"] = (await db.family_hubs.insert_one(hub)).inserted_id
        await _member(db, hub["_id"], pid, "patient")
        await _member(db, hub["_id"], manager["user_id"], "manager")
        for f in fms:
            is_manager = f is manager
            c = await db.consents.find_one({"family_member_id": f["_id"], "revoked_at": None})
            level = "full" if is_manager else (c or {}).get("access_level", "reminders")
            if not is_manager:
                level = "appointments" if level == "full" else level  # a viewer never holds the full plan
                await _member(db, hub["_id"], f["user_id"], "viewer")
            await db.consents.insert_one({"patient_id": pid, "grantee_id": f["user_id"], "hub_id": hub["_id"],
                                          "level": level, "granted_by": pid, "guardian_consent": False,
                                          "granted_at": now(), "revoked_at": None, "schema_version": SCHEMA_VERSION})
            n += 1
    await db.consents.delete_many({"family_member_id": {"$exists": True}})
    for name in ("family_members", "family_requests"):
        await db.drop_collection(name)
    return n


async def _pack_audit() -> int:
    from app.core.audit import audit as write_event
    db = get_db()
    flat = [e async for e in db.audit_log.find({"actor_key": {"$exists": False}}).sort("_id", 1)]
    await db.audit_log.delete_many({"actor_key": {"$exists": False}})
    for e in flat:
        await write_event(e["actor_id"], e["action"], e.get("target_type"), e.get("target_id"), e["result"],
                          e.get("on_behalf_of"), e.get("ip"), e.get("meta"))
    return len(flat)


async def main() -> None:
    db = get_db()
    await init_db()
    changes = {"hub consents": await _hubs_from_family(), "review snapshots": 0}
    async for rv in db.review_queue.find({"snapshot": {"$exists": False}}):
        t = await db.tasks.find_one({"_id": rv["task_id"]}, {"type": 1})
        p = await db.users.find_one({"_id": rv["patient_id"]}, {"patient_code": 1}) or {}
        await db.review_queue.update_one({"_id": rv["_id"]}, {"$set": {"snapshot": {
            "task_type": (t or {}).get("type"), "reasons": rv.get("reasons", []),
            "patient_code": p.get("patient_code"), "created_date": rv["created_at"].date().isoformat()}}})
        changes["review snapshots"] += 1
    changes["audit events packed"] = await _pack_audit()
    stamped = 0
    for name in VALIDATORS:
        r = await db[name].update_many({"schema_version": {"$exists": False}}, {"$set": {"schema_version": SCHEMA_VERSION}})
        stamped += r.modified_count
    changes["documents stamped"] = stamped
    print("migrated:", changes)


if __name__ == "__main__":
    asyncio.run(main())
