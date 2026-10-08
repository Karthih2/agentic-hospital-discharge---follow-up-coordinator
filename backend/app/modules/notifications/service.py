"""Notifications are built from templates only. They never contain clinical text."""
from datetime import datetime, timedelta

from app.core.constants import APPT_TYPES, SCHEMA_VERSION, TEMPLATES
from app.core.db import get_db
from app.core.security.crypto import dec
from app.pipeline import dates
from app.core.util import IST, now


def render(template_key: str, lang: str) -> str:
    t = TEMPLATES[template_key]
    return t.get(lang) or t["en"]


def consent_allows(level: str, task_type: str) -> bool:
    return level in ("full", "reminders") or (level == "appointments" and task_type in APPT_TYPES)


async def add(recipient_id, patient_id, ntype, template_key, task_id=None, when=None, sent=False, callback=None):
    ts = when or now()
    await get_db().notifications.insert_one({
        "recipient_id": recipient_id, "patient_id": patient_id, "task_id": task_id, "type": ntype,
        "scheduled_at": ts, "sent_at": ts if sent else None, "read_at": None,
        "template_key": template_key, "callback": callback, "schema_version": SCHEMA_VERSION})


async def subscribers(patient_id, task_type: str, only_missed: bool = False) -> list:
    """Pub-sub: each patient is a channel. A person is subscribed only while an active consent allows this kind
    of task. Missed-task alerts go to the hub manager only. The patient is always on their own channel."""
    db = get_db()
    out, seen = [], set()
    async for c in db.consents.find({"patient_id": patient_id, "revoked_at": None}):
        if c["grantee_id"] in seen or not consent_allows(c["level"], task_type):
            continue
        if only_missed and not await db.hub_members.find_one({"hub_id": c["hub_id"], "user_id": c["grantee_id"],
                                                              "role": "manager"}):
            continue
        seen.add(c["grantee_id"])
        out.append(c["grantee_id"])
    return out


async def schedule_reminders(task: dict) -> None:
    """Day before at 09:00 IST, and the day of: 2 hours before the appointment time when the summary gave one,
    else 09:00. Goes to the patient and every subscriber. Past times are skipped. Text is template-only."""
    if not task.get("due_date") or task.get("reminder_enabled") is False:
        return
    db = get_db()
    await db.notifications.delete_many({"task_id": task["_id"], "type": "reminder", "sent_at": None})
    due = task["due_date"].date()
    patient = await db.users.find_one({"_id": task["patient_id"]}, {"can_login": 1})
    recipients = ([task["patient_id"]] if patient and patient.get("can_login", True) else [])         + await subscribers(task["patient_id"], task["type"])
    at = dates.parse_time(dec((task.get("fields") or {}).get("due_time")))
    day_of = datetime(due.year, due.month, due.day, at[0], at[1], tzinfo=IST) - timedelta(hours=2) if at         else datetime(due.year, due.month, due.day, 9, tzinfo=IST)
    for key, when in (("reminder_due_tomorrow", datetime(due.year, due.month, due.day, 9, tzinfo=IST) - timedelta(days=1)),
                      ("reminder_due_today", day_of)):
        if when <= now():
            continue
        for r in recipients:
            await add(r, task["patient_id"], "reminder", key, task_id=task["_id"], when=when)
