"""What each viewer may see. Filtering happens HERE, in the API response, not in the interface."""
from app.core.constants import APPT_TYPES, PROVIDER_LABEL, WAITING
from app.pipeline import medicine_template
from app.pipeline.provider_agent import get_public
from app.core.security.access import View
from app.core.security.crypto import dec, dec_map
from app.core.util import iso, sid


def display_text(t: dict, lang: str) -> str | None:
    if lang != "en" and t.get("translations", {}).get(lang):
        return dec(t["translations"][lang])
    return dec(t["simple_text"]) if t.get("simple_text") else None


async def public_task(t: dict, view: View, lang: str) -> dict | None:
    """Returns None when this viewer must not see the task at all."""
    locked = t["status"] == "Needs Review"
    if view.level == "appointments" and t["type"] not in APPT_TYPES:
        return None
    if locked and view.locks_review:
        # Family sees only that the item is waiting. No title, text, date or type.
        return {"id": sid(t["_id"]), "status": "Needs Review", "locked": True, "message": WAITING}

    provider = await get_public(t["provider_id"]) if t.get("provider_id") else None
    title = dec(t["title"])
    f = dec_map(t.get("fields") or {})
    appt = {"time": f.get("due_time"), "location": f.get("location"), "phone": f.get("phone"),
            "doctor_name": f.get("doctor_name")} if t["type"] in APPT_TYPES else None
    if view.level == "reminders":
        return {"id": sid(t["_id"]), "title": title, "due_date": iso(t["due_date"] and t["due_date"].date()),
                "status": t["status"], "appointment": None}
    if view.level == "appointments":
        return {"id": sid(t["_id"]), "type": t["type"], "title": title, "status": t["status"],
                "due_date": iso(t["due_date"] and t["due_date"].date()), "provider": provider,
                "appointment": appt}

    card = None if locked or not t.get("medicine_card") else medicine_template.render(dec_map(t["medicine_card"]), lang)
    return {
        "id": sid(t["_id"]), "type": t["type"], "title": title, "status": t["status"], "locked": locked,
        "message": WAITING if locked else None,
        "reason": next((f["reason_code"] for f in t.get("flags", [])), None) if locked else None,
        "due_date": iso(t["due_date"] and t["due_date"].date()), "due_date_text": t.get("due_date_text"),
        "display_text": None if locked else display_text(t, lang),
        "medicine_card": card, "appointment": appt,
        "source_line": dec(t["source_line"]), "source_span": t.get("source_span"),
        "flags": t.get("flags", []), "confidence": t.get("confidence"),
        "provider_needed": t.get("provider_needed", False), "specialty": t.get("specialty"),
        "provider": provider, "provider_label": PROVIDER_LABEL if provider or t.get("provider_needed") else None,
        "entry_mode": t.get("entry_mode"), "doctor_edited": t.get("doctor_edited", False), "reminder_enabled": t.get("reminder_enabled", True), "completed_at": iso(t.get("completed_at")),
        "callback_completed": t.get("callback_completed_at") is not None,
        "can_listen": not locked and bool(display_text(t, lang) or card),
    }
