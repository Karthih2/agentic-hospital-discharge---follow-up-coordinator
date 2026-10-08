"""ElevenLabs text-to-speech. Reads APPROVED, stored text only. Never writes new wording."""
import hashlib

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.core.db import get_db
from app.pipeline import medicine_template
from app.core.security.crypto import dec, dec_bytes, dec_map, enc_bytes
from app.modules.tasks.view import display_text
from app.core.util import now


def _voice(lang: str) -> str | None:
    ids = dict(p.split(":", 1) for p in settings.elevenlabs_voice_ids.split(",") if ":" in p)
    return ids.get(lang) or ids.get("en")


def approved_text(task: dict, lang: str) -> str:
    if task["status"] == "Needs Review":
        raise HTTPException(409, "This item is waiting for doctor review")
    if task.get("medicine_card"):
        txt = medicine_template.spoken(dec_map(task["medicine_card"]), lang)
    else:
        txt = display_text(task, lang)
    if not txt:
        raise HTTPException(404, "No approved text to read yet")
    return txt


async def audio_for(task: dict, lang: str) -> bytes:
    text = approved_text(task, lang)
    h = hashlib.sha256(text.encode()).hexdigest()
    db = get_db()
    hit = await db.audio_cache.find_one({"task_id": task["_id"], "lang": lang})
    if hit and hit["text_hash"] == h:
        return dec_bytes(bytes(hit["audio"]))  # repeat listens cost nothing
    voice = _voice(lang)
    if not settings.elevenlabs_api_key or not voice:
        raise HTTPException(503, "Voice is not configured")
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                         headers={"xi-api-key": settings.elevenlabs_api_key},
                         json={"text": text, "model_id": "eleven_multilingual_v2"})
    if r.status_code != 200:
        raise HTTPException(502, "Voice service failed")
    await db.audio_cache.update_one({"task_id": task["_id"], "lang": lang}, {"$set": {
        "text_hash": h, "audio": enc_bytes(r.content), "created_at": now()}}, upsert=True)
    return r.content
