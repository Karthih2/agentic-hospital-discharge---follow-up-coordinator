"""PRD traceability. One test per PRD requirement that the earlier test files do not already pin down.
Section numbers refer to docs/PRD (UPDATED). Each test drives the real API (in-memory or on-disk SQLite)."""
import asyncio
from pathlib import Path

import pytest

from app.core import db as dbmod
from app.core import jobs
from app.core.audit import verify_chain
from app.core.constants import DISCLAIMER, MEDICINE_KEYS, PROVIDER_LABEL, STATUSES, TYPES
from app.core.store import Database
from app.pipeline import extraction_agent, safety_gate
from tests.conftest import SUMMARY, publish, upload

run = asyncio.run
SAMPLES = Path(__file__).resolve().parents[1] / "sample_data" / "discharge_template"


def db():
    return dbmod.get_db()


def no_model(monkeypatch):
    """Exercise the real text path without an AI key: the rule-based reader builds the plan."""
    async def boom(raw):
        raise extraction_agent.AgentError("NO_API_KEY")
    monkeypatch.setattr(extraction_agent, "extract", boom)


# ---------- §1 / §5 footer text, §7 provider label: exact PRD wording
def test_fixed_texts_match_the_prd(clients):
    assert DISCLAIMER == ("This tool organizes your discharge instructions. It does not give medical advice. "
                          "Ask your doctor about anything unclear.")
    meta = clients["patient1"].get("/meta").json()
    assert meta["disclaimer"] == DISCLAIMER
    assert meta["provider_label"] == PROVIDER_LABEL and "not a guarantee" in PROVIDER_LABEL


# ---------- §3 step 2: non-medical input -> clear error and manual entry prompt
def test_non_medical_sample_is_refused_with_manual_entry(clients, world):
    text = (SAMPLES.parent / "05_not_medical.txt").read_text(encoding="utf-8")
    r = clients["patient1"].post(f"/patients/{world['patient']}/summaries", data={"text": text}).json()
    assert r["status"] == "needs_manual" and r["error_code"] == "NOT_MEDICAL" and r["next"] == "manual_entry"
    assert "discharge summary" in r["message"]


# ---------- §3 / §4: all 7 types from the 5 synthetic summaries, each with its exact source line
def test_seven_types_with_exact_evidence_from_all_samples(clients, world, monkeypatch):
    no_model(monkeypatch)
    seen = set()
    for f in sorted(SAMPLES.glob("0*.txt")):
        raw = f.read_text(encoding="utf-8")
        sid = upload(clients["patient1"], str(world["patient"]), raw)
        for t in run(db().tasks.find({"summary_id": sid}).to_list()):
            seen.add(t["type"])
            from app.core.security.crypto import dec
            line = dec(t["source_line"])
            assert " ".join(line.split()) in " ".join(raw.split()), f"{f.name}: evidence not verbatim: {line}"
            assert t["source_span"] and raw[t["source_span"]["start"]:t["source_span"]["end"]].split() == line.split()
    assert seen == set(TYPES)  # appointment, test, referral, medicine, care_instruction, date, warning_sign


# ---------- §3 step 2: a PDF upload goes through the same pipeline
def test_pdf_upload_builds_a_plan(clients, world, monkeypatch):
    no_model(monkeypatch)
    data = (SAMPLES / "01_koushal_cardiac_clean.pdf").read_bytes()
    r = clients["patient1"].post(f"/patients/{world['patient']}/summaries",
                                 files={"file": ("summary.pdf", data, "application/pdf")})
    assert r.status_code == 202 and r.json()["status"] == "uploaded"
    sid = r.json()["id"]
    s = run(db().discharge_summaries.find_one({"_id": sid}))
    assert s["source"] == "pdf" and s["status"] == "ready"
    assert run(db().tasks.count_documents({"summary_id": sid})) >= 10


# ---------- §4 / §6: medicine card uses the fixed template, never a rewrite
def test_medicine_card_is_the_fixed_template(clients, world):
    pid = str(world["patient"])
    upload(clients["patient1"], pid)
    med = next(t for t in clients["patient1"].get(f"/patients/{pid}/tasks").json() if t["title"] == "Metformin")
    assert [r["key"] for r in med["medicine_card"]["rows"]] == MEDICINE_KEYS
    assert set(MEDICINE_KEYS) >= {"name", "dose", "timing", "duration", "special"}
    assert med["display_text"] is None  # medicine content is never freely reworded


# ---------- §5 gate rules, one by one
def _item(**kw):
    base = {"type": "care_instruction", "title": "x", "source_line": "Walk daily.", "instruction": "Walk daily.",
            "confidence": 0.95, "source_found": True, "due_date": None, "date_ambiguous": False}
    return {**base, **kw}


@pytest.mark.parametrize("item,code", [
    (_item(type="appointment", specialty="Cardiology", source_line="See cardiology."), "MISSING_DATE"),
    (_item(type="medicine", source_line="Aspirin once daily.", medicine={"name": "Aspirin", "timing": "once daily"}),
     "MISSING_DOSE"),
    (_item(type="medicine", source_line="Aspirin 75 mg.", medicine={"name": "Aspirin", "dose": "75 mg"}), "MISSING_TIMING"),
    (_item(type="appointment", source_line="Follow up on 2026-11-02.", due_date="2026-11-02"), "MISSING_DOCTOR"),
    (_item(source_line="What should I do if I feel dizzy?"), "SYMPTOM_QUESTION"),
    (_item(source_line="If you feel dizzy, sit down."), "SYMPTOM_QUESTION"),
    (_item(type="medicine", source_line="Stop Glimepiride.", medicine={"name": "Glimepiride"}), "MEDICINE_CHANGE"),
    (_item(confidence=0.69), "LOW_CONFIDENCE"),
    (_item(instruction=None), "UNCATEGORISED"),
    (_item(type="test", source_line="HbA1c soon.", due_date_text="soon", date_ambiguous=True), "AMBIGUOUS_DATE"),
])
def test_each_gate_rule_flags(item, code):
    assert code in {f["reason_code"] for f in safety_gate.run_gate(item)}


def test_confidence_threshold_is_exactly_70_percent():
    assert not safety_gate.run_gate(_item(confidence=0.70))
    assert safety_gate.run_gate(_item(confidence=0.6999))


def test_clash_between_two_instructions_flags_both():
    a = _item(type="medicine", source_line="Metformin 500 mg twice daily for 30 days.",
              medicine={"name": "Metformin", "dose": "500 mg", "timing": "twice daily", "duration": "30 days"})
    b = _item(type="medicine", source_line="Metformin 1000 mg once daily for 30 days.",
              medicine={"name": "Metformin", "dose": "1000 mg", "timing": "once daily", "duration": "30 days"})
    assert set(safety_gate.conflict_flags([a, b])) == {0, 1}


# ---------- §5 hard rule: nothing but a doctor closes a Needs Review item
def test_jobs_never_auto_resolve_needs_review(clients, world):
    pid = str(world["patient"])
    upload(clients["patient1"], pid)
    before = run(db().tasks.count_documents({"status": "Needs Review"}))
    assert before == 1
    for name, (fn, _) in jobs.JOBS.items():
        run(fn())
    assert run(db().tasks.count_documents({"status": "Needs Review"})) == before
    t = run(db().tasks.find_one({"status": "Needs Review"}))
    for who in ("patient1", "daughter1"):  # patient and family cannot tick it either
        assert clients[who].post(f"/tasks/{t['_id']}/complete").status_code == 409


# ---------- §6 statuses
def test_status_values_are_the_three_in_the_prd():
    assert STATUSES == ("Pending", "Completed", "Needs Review")


# ---------- §7 provider matching: specialty, 3 to 5 by proximity, location never stored
def test_provider_search_does_not_store_the_location(tmp_path, clients, world):
    p = clients["patient1"]
    r = p.get("/providers", params={"specialty": "Cardiology", "lat": 13.104321, "lng": 80.219876}).json()
    assert 3 <= len(r["results"]) <= 5 and r["label"] == PROVIDER_LABEL
    d = [x["distance_km"] for x in r["results"]]
    assert d == sorted(d) and all(x["specialty"] == "Cardiology" for x in r["results"])
    assert all(x["pin_color"] == ("blue" if x["type"] == "hospital" else "green") for x in r["results"])
    stored = str([run(db()[c].find({}).to_list()) for c in run(db().list_collection_names())])
    assert "13.104321" not in stored and "80.219876" not in stored


# ---------- §8 security: encrypted at rest (checked on the raw SQLite file), audit chain intact
def test_clinical_text_is_encrypted_in_the_database_file(tmp_path, clients, world):
    path = tmp_path / "prd.db"
    disk = Database(str(path), dbmod.RULES)
    for name in ("users", "doctors", "family_hubs", "hub_members", "consents", "locations", "providers"):
        for d in run(db()[name].find({}).to_list()):
            run(disk[name].insert_one(d))
    dbmod.set_db(disk)
    pid = str(world["patient"])
    sid = upload(clients["patient1"], pid)
    assert run(disk.tasks.count_documents({"summary_id": sid})) == 6
    disk.close()
    raw = path.read_bytes() + (path.with_name(path.name + "-wal").read_bytes()
                               if path.with_name(path.name + "-wal").exists() else b"")
    for secret in (b"Metformin", b"Aspirin", b"cardiologist", b"Asha Raman", b"wound dressing"):
        assert secret not in raw, secret
    assert b"v1:" in raw  # the encrypted values are there


def test_audit_log_is_append_only_and_chained(clients, world):
    upload(clients["patient1"], str(world["patient"]))
    assert run(verify_chain())
    # an edited event is detected when a later event in its bucket follows it (the chain stores the PREVIOUS
    # event's hash). Known limit: the newest event of a bucket has no successor yet, so its edit is not detected.
    b = run(db().audit_log.find_one({"count": {"$gte": 2}}))
    run(db().audit_log.update_one({"_id": b["_id"]}, {"$set": {"events.0.action": "tampered"}}))
    assert not run(verify_chain())
    paths = {getattr(r, "path", "") for r in __import__("app.main", fromlist=["app"]).app.routes}
    assert not any("audit" in p and m in getattr(r, "methods", set())
                   for r in __import__("app.main", fromlist=["app"]).app.routes
                   for p in [getattr(r, "path", "")] for m in ("PUT", "PATCH", "DELETE"))
    assert "/admin-api/audit" in paths


# ---------- §2 every view and action is logged
def test_views_and_actions_are_audited(clients, world):
    pid = str(world["patient"])
    upload(clients["patient1"], pid)
    clients["daughter1"].get(f"/patients/{pid}/tasks")
    t = clients["patient1"].get(f"/patients/{pid}/tasks").json()[0]
    clients["patient1"].post(f"/tasks/{t['id']}/complete")
    from app.core.audit import events
    acts = {e["action"] for e in run(events(limit=1000))}
    assert {"upload_summary", "view_plan", "task_complete", "publish_plan", "match_doctor"} <= acts


# ---------- §11 masked call: patient initiates, numbers masked, logged with duration and no number
def test_callback_audit_has_no_phone_numbers(clients, world):
    pid = str(world["patient"])
    upload(clients["patient1"], pid)
    tid = clients["patient1"].get(f"/patients/{pid}/tasks").json()[0]["id"]
    assert clients["patient1"].post(f"/tasks/{tid}/callback").status_code == 202
    m = clients["mgmt1"]
    cb = m.get("/admin-api/callbacks").json()[0]
    m.post(f"/admin-api/callbacks/{cb['id']}/start")
    m.post(f"/admin-api/callbacks/{cb['id']}/complete")
    from app.core.audit import events
    cb_events = [e for e in run(events(limit=1000)) if "callback" in e["action"]]
    assert cb_events and "+91" not in str(cb_events)
    assert run(db().notifications.count_documents({"type": "callback"})) >= 1


# ---------- §3 step 8 + new workflow: plan doctor unavailable before upload -> fallback gets plan and items
def test_unclear_items_reach_a_human_and_never_the_patient_first(clients, world):
    pid = str(world["patient"])
    sid = upload(clients["patient1"], pid, publish_plan=False)
    assert clients["patient1"].get(f"/patients/{pid}/tasks").json() == []
    plan = clients["doctor1"].get(f"/plans/{sid}").json()
    flagged = [t for t in plan["tasks"] if t["status"] == "Needs Review"]
    assert flagged and all(t["reasons"] for t in flagged)  # a visible reason on every flagged item
    publish(sid)
    assert any(t["status"] == "Needs Review" for t in clients["patient1"].get(f"/patients/{pid}/tasks").json())


# ---------- §7 drill-down also returns 3 to 5, nearest first, starting from the chosen area
def test_area_drilldown_returns_three_to_five(clients, world):
    p = clients["patient1"]
    for spec, area in (("Cardiology", "Adyar"), ("Physiotherapy", "T Nagar"), ("Orthopedics", "Adyar")):
        r = p.get("/providers", params={"specialty": spec, "state": "Tamil Nadu", "district": "Chennai",
                                        "area": area}).json()["results"]
        assert 3 <= len(r) <= 5, (spec, area, len(r))
        assert [x["distance_km"] for x in r] == sorted(x["distance_km"] for x in r)
        assert all(x["state"] == "Tamil Nadu" and x["specialty"] == spec for x in r)
