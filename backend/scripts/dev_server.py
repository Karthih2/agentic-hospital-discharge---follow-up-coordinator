"""Run the API on an in-memory MongoDB with the whole demo loaded, no Atlas and no model calls.
    python -m scripts.dev_server           http://127.0.0.1:8000  (password for every demo login: Demo@12345)
    python -m scripts.dev_server --live-model   same, but the real model (Groq) reads the 5 summaries (a few minutes)

The 5 sample summaries are planned from the reference extraction in expected.json (the real safety gate, dates and
planner still run), and plain-language rewrites are canned text. For the real model use  scripts.seed_demo."""
import asyncio
import json
import os
import re
import sys

os.environ.setdefault("SKIP_INIT", "1")

import uvicorn  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

from app.core import db as dbmod  # noqa: E402
from app.main import app  # noqa: E402
from app.pipeline import extraction_agent, planner  # noqa: E402
from app.pipeline.extraction_agent import ExtractedItem, Outcome  # noqa: E402
from scripts import seed_demo  # noqa: E402

CANNED = {"ta": "மருத்துவர் சொன்னபடி இந்த வேலையை குறிப்பிட்ட நாளுக்குள் செய்து முடிக்கவும்: ",
          "hi": "डॉक्टर के बताए अनुसार इस कार्य को निर्धारित तिथि तक पूरा कीजिए: ",
          "te": "వైద్యుడు చెప్పినట్లు ఈ పనిని నిర్ణీత తేదీలోగా పూర్తి చేయండి: ",
          "kn": "ವೈದ್ಯರು ಹೇಳಿದಂತೆ ಈ ಕೆಲಸವನ್ನು ನಿಗದಿತ ದಿನಾಂಕದೊಳಗೆ ಪೂರ್ಣಗೊಳಿಸಿ: ",
          "ml": "ഡോക്ടർ പറഞ്ഞതുപോലെ ഈ ജോലി നിശ്ചിത തീയതിക്കുള്ളിൽ പൂർത്തിയാക്കുക: "}


async def fake_simplify(source_line, lang):
    s = re.sub(r"^\d+\.\s*", "", source_line).rstrip(".")
    return s, {k: v + s for k, v in CANNED.items()}


async def reference_extract(raw):
    cases = json.loads((seed_demo.DIR / "expected.json").read_text(encoding="utf-8"))
    for case in cases:
        if all(e["source_line"] in raw for e in case["items"][:3]):
            return Outcome(discharge_date_text=case["discharge_date"], items=[
                ExtractedItem(type=e["type"], source_line=e["source_line"], **e["reference_extraction"])
                for e in case["items"]])
    return Outcome()


async def main():
    dbmod.set_db(AsyncMongoMockClient(tz_aware=True)["dev"])
    if "--live-model" not in sys.argv:  # default: offline reference data; with the flag, the real model builds the plans
        planner.simplify = fake_simplify
        extraction_agent.extract = reference_extract
    data = json.loads((seed_demo.DIR / "demo_people.json").read_text(encoding="utf-8"))
    await seed_demo.seed_reference()
    ids = await seed_demo.build_people(data)
    await seed_demo.upload_all(data, ids)
    seed_demo.login_table(data)
    cfg = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
    await uvicorn.Server(cfg).serve()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
