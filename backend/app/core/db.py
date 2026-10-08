"""MongoDB connection, $jsonSchema validators (enums are enforced in the database too) and indexes.
Which schema pattern each collection uses is written down in docs/DATA_MODEL.md."""
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, GEOSPHERE, IndexModel
from pymongo.errors import CollectionInvalid

from app.core.config import settings
from app.core.constants import ACCESS_LEVELS, HUB_ROLES, ROLES, STATUSES, TYPES

_client = None
_db = None


def get_db():
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(settings.mongo_uri, tz_aware=True, serverSelectionTimeoutMS=8000)
        _db = _client[settings.mongo_db]
    return _db


def set_db(db) -> None:
    """Tests inject an in-memory db."""
    global _db
    _db = db


def _v(required: list[str], **props) -> dict:
    props.setdefault("schema_version", {"bsonType": ["int", "long"]})
    return {"$jsonSchema": {"bsonType": "object", "required": required, "properties": props}}


_ENUM = lambda *vals: {"enum": list(vals)}  # noqa: E731

VALIDATORS = {
    "users": _v(["login", "password_hash", "role", "language", "created_at"],
                role=_ENUM(*ROLES), language=_ENUM("en", "ta", "hi", "te", "kn", "ml")),
    "family_hubs": _v(["name", "manager_id", "created_at"]),
    "hub_members": _v(["hub_id", "user_id", "role", "created_at"], role=_ENUM(*HUB_ROLES)),
    "hub_invites": _v(["hub_id", "kind", "status", "created_at"],
                      kind=_ENUM("patient", "viewer"), status=_ENUM("pending", "approved", "denied")),
    "consents": _v(["patient_id", "grantee_id", "hub_id", "level", "granted_by", "granted_at"],
                   level=_ENUM(*ACCESS_LEVELS)),
    "patient_stats": _v(["pending", "completed", "needs_review", "updated_at"]),
    "discharge_summaries": _v(["patient_id", "source", "status", "uploaded_at"],
                              source=_ENUM("pdf", "text", "manual"),
                              status=_ENUM("uploaded", "extracting", "gating", "planning", "simplifying",
                                           "ready", "needs_manual", "failed")),
    "tasks": _v(["patient_id", "type", "status", "source_line", "created_at"],
                status=_ENUM(*STATUSES), type=_ENUM(*TYPES),
                confidence={"bsonType": ["double", "int"], "minimum": 0, "maximum": 1}),
    "task_revisions": _v(["task_id", "patient_id", "revised_by", "previous", "created_at"]),
    "review_queue": _v(["task_id", "patient_id", "status", "snapshot", "created_at"],
                       status=_ENUM("open", "in_review", "resolved"),
                       outcome={"enum": ["confirmed", "corrected", None]}),
    "doctors": _v(["user_id", "specialty", "available"]),
    "providers": _v(["name", "specialty", "type", "location", "synthetic", "attributes"],
                    type=_ENUM("hospital", "clinic"), synthetic={"enum": [True]}),
    "locations": _v(["kind", "name", "ancestors"], kind=_ENUM("state", "district", "area")),
    "notifications": _v(["recipient_id", "type", "scheduled_at", "template_key"],
                        type=_ENUM("reminder", "missed_task", "review_waiting", "callback", "hub_invite")),
    "audit_log": _v(["actor_key", "day", "seq", "count", "events"]),
    "job_locks": _v(["locked_until"]),
}

INDEXES = {
    "users": [IndexModel([("login", ASCENDING)], unique=True), IndexModel([("role", ASCENDING)]),
              IndexModel([("patient_code", ASCENDING)], unique=True,
                         partialFilterExpression={"patient_code": {"$type": "string"}})],
    "family_hubs": [IndexModel([("manager_id", ASCENDING)])],
    "hub_members": [IndexModel([("hub_id", ASCENDING), ("user_id", ASCENDING), ("role", ASCENDING)], unique=True),
                    IndexModel([("user_id", ASCENDING)])],
    "hub_invites": [IndexModel([("patient_id", ASCENDING), ("status", ASCENDING)]),
                    IndexModel([("grantee_id", ASCENDING), ("status", ASCENDING)])],
    "consents": [IndexModel([("patient_id", ASCENDING), ("grantee_id", ASCENDING), ("revoked_at", ASCENDING)]),
                 IndexModel([("grantee_id", ASCENDING), ("revoked_at", ASCENDING)]),
                 IndexModel([("hub_id", ASCENDING)])],
    "discharge_summaries": [IndexModel([("patient_id", ASCENDING), ("uploaded_at", DESCENDING)]),
                            IndexModel([("text_hash", ASCENDING)])],
    "tasks": [IndexModel([("patient_id", ASCENDING), ("status", ASCENDING), ("due_date", ASCENDING)]),
              IndexModel([("patient_id", ASCENDING), ("type", ASCENDING)]),
              IndexModel([("summary_id", ASCENDING)]),
              IndexModel([("status", ASCENDING), ("due_date", ASCENDING)],
                         partialFilterExpression={"status": "Pending"}, name="pending_due")],
    "task_revisions": [IndexModel([("task_id", ASCENDING), ("created_at", DESCENDING)])],
    "review_queue": [IndexModel([("assigned_doctor_id", ASCENDING), ("status", ASCENDING)]),
                     IndexModel([("status", ASCENDING), ("created_at", ASCENDING)]),
                     IndexModel([("task_id", ASCENDING)])],
    "doctors": [IndexModel([("user_id", ASCENDING)], unique=True), IndexModel([("available", ASCENDING)])],
    "providers": [IndexModel([("location", GEOSPHERE)]),
                  IndexModel([("specialty", ASCENDING), ("state", ASCENDING),
                              ("district", ASCENDING), ("area", ASCENDING)]),
                  IndexModel([("attributes.k", ASCENDING), ("attributes.v", ASCENDING)])],
    "locations": [IndexModel([("kind", ASCENDING), ("name", ASCENDING), ("ancestors.name", ASCENDING)], unique=True),
                  IndexModel([("ancestors.name", ASCENDING)])],
    "notifications": [IndexModel([("sent_at", ASCENDING), ("scheduled_at", ASCENDING)],
                                 partialFilterExpression={"sent_at": None}, name="unsent"),
                      IndexModel([("recipient_id", ASCENDING), ("read_at", ASCENDING)]),
                      IndexModel([("type", ASCENDING), ("callback.status", ASCENDING)])],
    "audit_log": [IndexModel([("actor_key", ASCENDING), ("day", ASCENDING), ("seq", ASCENDING)], unique=True),
                  IndexModel([("events.target_id", ASCENDING)]),
                  IndexModel([("events.on_behalf_of", ASCENDING)])],
    "refresh_tokens": [IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0),
                       IndexModel([("token_hash", ASCENDING)], unique=True)],
    "audio_cache": [IndexModel([("task_id", ASCENDING), ("lang", ASCENDING)], unique=True)],
}


async def init_db() -> None:
    """Create collections with validators (enums checked in the DB too), then indexes."""
    db = get_db()
    for name, validator in VALIDATORS.items():
        try:
            await db.create_collection(name, validator=validator, validationLevel="strict", validationAction="error")
        except CollectionInvalid:
            await db.command("collMod", name, validator=validator, validationLevel="strict", validationAction="error")
    for name, idx in INDEXES.items():
        await db[name].create_indexes(idx)
