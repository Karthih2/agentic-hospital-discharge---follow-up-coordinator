"""List Groq models this key can use, probe each with a real extraction-style task, pick the best, save GROQ_MODEL.
   python -m scripts.pick_groq_model            (probe + write .env)
Probe = what the pipeline needs: JSON only, exact source_line copy, no invented values."""
import json
import re
import sys
import time
from pathlib import Path

import httpx

from app.core.config import settings

ENV = Path(__file__).resolve().parents[1] / ".env"
BASE = "https://api.groq.com/openai/v1"
SKIP = re.compile(r"whisper|tts|guard|embed|orpheus|playai|distil.*whisper|compound|safeguard", re.I)
TEXT = "Tab. Metformin 500 mg twice daily for 30 days after food. Follow up with cardiologist in 2 weeks."
PROMPT = ('Return ONLY JSON: {"items":[{"type":"medicine|appointment","source_line":"<copied exactly>",'
          '"dose":string|null,"due_date_text":string|null}]}. Never guess; use null. Data:\n<d>' + TEXT + "</d>")


def probe(client, key, model):
    t = time.time()
    r = client.post(f"{BASE}/chat/completions", headers={"Authorization": f"Bearer {key}"}, timeout=60,
                    json={"model": model, "temperature": 0, "max_tokens": 400,
                          "messages": [{"role": "user", "content": PROMPT}]})
    dt = time.time() - t
    if r.status_code != 200:
        return {"model": model, "ok": False, "why": f"{r.status_code} {r.text[:90]}"}
    txt = r.json()["choices"][0]["message"]["content"]
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S)
    try:
        items = json.loads(txt[txt.find("{"):txt.rfind("}") + 1])["items"]
    except Exception:
        return {"model": model, "ok": False, "why": "bad JSON"}
    exact = sum(1 for i in items if isinstance(i.get("source_line"), str) and i["source_line"].strip(" .") in TEXT)
    dose = any(i.get("dose") and "500" in i["dose"] for i in items)
    score = exact * 2 + dose + (len(items) == 2)
    return {"model": model, "ok": True, "score": score, "sec": round(dt, 2), "items": len(items)}


def main():
    key = settings.groq_api_key
    if not key:
        sys.exit("groq_api_key missing in .env")
    with httpx.Client() as c:
        r = c.get(f"{BASE}/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
        if r.status_code != 200:
            sys.exit(f"models list failed: {r.status_code} {r.text[:120]}")
        models = sorted(m["id"] for m in r.json()["data"] if not SKIP.search(m["id"]))
        print(f"{len(models)} chat candidates:", ", ".join(models))
        results = []
        for m in models:
            res = probe(c, key, m)
            print(res)
            results.append(res)
            time.sleep(1)  # stay under free-tier rate limits
    good = [x for x in results if x["ok"]]
    if not good:
        sys.exit("no model passed the probe")
    best = sorted(good, key=lambda x: (-x["score"], x["sec"]))[0]
    print("PICK:", best)
    lines = ENV.read_text(encoding="utf-8").splitlines()
    lines = [l for l in lines if not l.upper().startswith("GROQ_MODEL=")] + [f"GROQ_MODEL={best['model']}"]
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
