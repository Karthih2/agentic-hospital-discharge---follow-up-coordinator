"""SQLite connection (one file, no server), field rules and unique keys.
Which data pattern each collection uses is written down in docs/DATA_MODEL.md."""
from app.core.config import settings
from app.core.constants import ACCESS_LEVELS, HUB_ROLES, PLAN_STATUSES, ROLES, STATUSES, TYPES
from app.core.store import Database, DuplicateKeyError, Rules, StoreError, WriteError, open_database  # noqa: F401

_db: Database | None = None

LANG_CODES = ("en", "ta", "hi", "te", "kn", "ml")

# Field rules: required fields and allowed values, checked on every write (the enums are enforced in the DB layer
# too, not only in the API). The same rules the MongoDB $jsonSchema validators held.
RULES = {
    "users": Rules(["login", "password_hash", "role", "language", "created_at"],
                   {"role": ROLES, "language": LANG_CODES},
                   uniques=[(("login",), None),
                            (("patient_code",), {"patient_code": {"$type": "string"}})]),
    "family_hubs": Rules(["name", "manager_id", "created_at"]),
    "hub_members": Rules(["hub_id", "user_id", "role", "created_at"], {"role": HUB_ROLES},
                         uniques=[(("hub_id", "user_id", "role"), None)]),
    "hub_invites": Rules(["hub_id", "kind", "status", "created_at"],
                         {"kind": ("patient", "viewer"), "status": ("pending", "approved", "denied")}),
    "consents": Rules(["patient_id", "grantee_id", "hub_id", "level", "granted_by", "granted_at"],
                      {"level": ACCESS_LEVELS}),
    "patient_stats": Rules(["pending", "completed", "needs_review", "updated_at"]),
    "discharge_summaries": Rules(["patient_id", "source", "status", "uploaded_at"],
                                 {"source": ("pdf", "text", "manual"),
                                  "status": ("uploaded", "extracting", "gating", "planning", "simplifying",
                                             "ready", "needs_manual", "failed"),
                                  "plan_status": PLAN_STATUSES}),
    "tasks": Rules(["patient_id", "type", "status", "source_line", "created_at"],
                   {"status": STATUSES, "type": TYPES}, {"confidence": (0, 1)}),
    "task_revisions": Rules(["task_id", "patient_id", "revised_by", "previous", "created_at"]),
    "review_queue": Rules(["task_id", "patient_id", "status", "snapshot", "created_at"],
                          {"status": ("open", "in_review", "resolved"), "outcome": ("confirmed", "corrected", None)}),
    "doctors": Rules(["user_id", "specialty", "available"], uniques=[(("user_id",), None)]),
    "providers": Rules(["name", "specialty", "type", "location", "synthetic", "attributes"],
                       {"type": ("hospital", "clinic"), "synthetic": (True,)}),
    "locations": Rules(["kind", "name", "ancestors"], {"kind": ("state", "district", "area")},
                       uniques=[(("kind", "name", "ancestors"), None)]),
    "notifications": Rules(["recipient_id", "type", "scheduled_at", "template_key"],
                           {"type": ("reminder", "missed_task", "review_waiting", "callback", "hub_invite",
                                     "plan_ready", "plan_published")}),
    "audit_log": Rules(["actor_key", "day", "seq", "count", "events"],
                       uniques=[(("actor_key", "day", "seq"), None)]),
    "job_locks": Rules(["locked_until"]),
    "refresh_tokens": Rules(uniques=[(("token_hash",), None)]),
    "audio_cache": Rules(uniques=[(("task_id", "lang"), None)]),
}


def get_db() -> Database:
    global _db
    if _db is None:
        _db = open_database(settings.sqlite_path, RULES)
    return _db


def set_db(db: Database) -> None:
    """Tests and the demo server inject their own (usually in-memory) database."""
    global _db
    _db = db


def memory_db() -> Database:
    """A fresh in-memory database with the same rules. Used by the tests and the offline demo server."""
    return Database(":memory:", RULES)


async def init_db() -> None:
    """Create every table. Safe to run on every start."""
    db = get_db()
    db.rules = RULES
    for name in RULES:
        await db.create_collection(name)
