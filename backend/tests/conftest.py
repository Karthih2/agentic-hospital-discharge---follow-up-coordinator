import base64
import os

# Must be set before the app is imported. Environment beats .env, so tests never touch real databases.
os.environ.update({
    "SKIP_INIT": "1", "JWT_SECRET": "t" * 48, "CLAUDE_API_KEY": "",
    "FIELD_ENC_KEY": base64.b64encode(b"k" * 32).decode(), "SQLITE_PATH": ":memory:"})

import asyncio  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core import db as dbmod  # noqa: E402
from app.main import app  # noqa: E402
from app.pipeline import extraction_agent, planner  # noqa: E402
from app.pipeline.extraction_agent import ExtractedItem, MedicineFields, Outcome  # noqa: E402
from app.core.security import ratelimit  # noqa: E402
from scripts.seed import seed  # noqa: E402

PW = "Test@12345"

SUMMARY = """Discharge date: 02 Nov 2026
1. Follow up with cardiologist in 2 weeks.
2. Tab. Metformin 500 mg twice daily for 30 days after food.
3. Fasting blood sugar test on Day 7.
4. Change wound dressing every 48 hours.
5. Seek immediate care if chest pain or breathlessness occurs.
6. Tab. Aspirin once daily. Continue as advised.
"""


def item(type_, line, conf=0.95, **kw):
    return ExtractedItem(type=type_, title=kw.pop("title", line[:40]), source_line=line, confidence=conf, **kw)


def sample_outcome() -> Outcome:
    L = [s for s in SUMMARY.splitlines()]
    return Outcome(discharge_date_text="02 Nov 2026", items=[
        item("appointment", L[1][3:], title="Cardiology follow-up", due_date_text="in 2 weeks", specialty="Cardiology"),
        item("medicine", L[2][3:], title="Metformin",
             medicine=MedicineFields(name="Metformin", dose="500 mg", timing="twice daily", duration="30 days",
                                     special="after food")),
        item("test", L[3][3:], title="Fasting blood sugar test", due_date_text="Day 7"),
        item("care_instruction", L[4][3:], title="Wound dressing", instruction="Change wound dressing every 48 hours"),
        item("warning_sign", L[5][3:], title="Warning signs", instruction="Seek immediate care if chest pain"),
        item("medicine", L[6][3:], title="Aspirin",
             medicine=MedicineFields(name="Aspirin", timing="once daily"))])


@pytest.fixture(autouse=True)
def env(monkeypatch):
    dbmod.set_db(dbmod.memory_db())  # fresh in-memory SQLite per test
    ratelimit.clear()

    async def fake_simplify(source_line, lang):
        s = source_line.rstrip(".")
        return s, {c: c.upper() + " " + s for c in ("ta", "hi", "te", "kn", "ml")}
    monkeypatch.setattr(planner, "simplify", fake_simplify)

    async def fake_extract(raw):
        return sample_outcome()
    monkeypatch.setattr(extraction_agent, "extract", fake_extract)
    yield


@pytest.fixture
def world():
    return asyncio.run(seed(PW))


def new_client() -> TestClient:
    return TestClient(app)


def login(c: TestClient, login_name: str, pw: str = PW):
    r = c.post("/auth/login", json={"login": login_name, "password": pw})
    assert r.status_code == 200, r.text
    c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    return r.json()


@pytest.fixture
def clients(world):
    out = {}
    for name in ("patient1", "daughter1", "son1", "brother1", "doctor1", "doctor2", "mgmt1"):
        c = new_client()
        login(c, name)
        out[name] = c
    return out


def doctor_client(summary_id) -> TestClient:
    """A client logged in as the doctor the pipeline matched to this summary's plan."""
    s = asyncio.run(dbmod.get_db().discharge_summaries.find_one({"_id": summary_id}))
    assert s and s.get("plan_doctor_id"), "no doctor was matched to this plan"
    u = asyncio.run(dbmod.get_db().users.find_one({"_id": s["plan_doctor_id"]}))
    c = new_client()
    login(c, u["login"])
    return c


def publish(summary_id, keep_in_review: bool = True):
    """The matched doctor publishes the draft plan. keep_in_review=True keeps still-flagged items with the doctor,
    so they show to the patient as 'Waiting for doctor review' (what most older tests exercise)."""
    r = doctor_client(summary_id).post(f"/plans/{summary_id}/publish", json={"keep_in_review": keep_in_review})
    assert r.status_code == 200, r.text
    return r.json()


def upload(c, pid, text=SUMMARY, publish_plan: bool = True):
    r = c.post(f"/patients/{pid}/summaries", data={"text": text})
    assert r.status_code == 202, r.text
    sid = r.json()["id"]
    if publish_plan and r.json().get("status") == "uploaded":
        st = c.get(f"/summaries/{sid}/status").json()
        if st.get("plan_status") == "draft":
            publish(sid)
    return sid
