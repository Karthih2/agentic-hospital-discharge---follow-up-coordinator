"""Single place that talks to the model. No tools, no database access.
Groq is used when GROQ_API_KEY and GROQ_MODEL are set (see scripts/pick_groq_model.py), otherwise Claude."""
import asyncio
import json
import re

import httpx

from app.core.config import settings


class AgentError(Exception):
    pass


def _json_from(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b < a:
        raise AgentError("NO_JSON")
    try:
        return json.loads(text[a:b + 1])  # free text outside the JSON object is discarded
    except json.JSONDecodeError:
        raise AgentError("BAD_JSON")


async def _groq(system: str, user: str, max_tokens: int) -> str:
    body = {"model": settings.groq_model, "temperature": 0, "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    for attempt in range(6):  # free tier returns 429 on bursts: wait as told, then retry
        try:
            async with httpx.AsyncClient(timeout=90) as c:
                r = await c.post("https://api.groq.com/openai/v1/chat/completions",
                                 headers={"Authorization": f"Bearer {settings.groq_api_key}"}, json=body)
        except httpx.HTTPError as e:
            raise AgentError(f"MODEL_CALL_FAILED:{type(e).__name__}")
        if r.status_code == 429 and attempt < 5:
            await asyncio.sleep(min(float(r.headers.get("retry-after", 5 * (attempt + 1))), 60))
            continue
        break
    if r.status_code != 200:
        raise AgentError(f"MODEL_CALL_FAILED:{r.status_code}")
    return r.json()["choices"][0]["message"]["content"] or ""


async def _claude(system: str, user: str, max_tokens: int) -> str:
    from anthropic import AsyncAnthropic
    try:
        msg = await AsyncAnthropic(api_key=settings.claude_api_key).messages.create(
            model=settings.claude_model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}])
    except Exception as e:
        raise AgentError(f"MODEL_CALL_FAILED:{type(e).__name__}")
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


async def ask_json(system: str, user: str, max_tokens: int = 4096) -> dict:
    if settings.groq_api_key and settings.groq_model:
        return _json_from(await _groq(system, user, max_tokens))
    if settings.claude_api_key:
        return _json_from(await _claude(system, user, max_tokens))
    raise AgentError("NO_API_KEY")
