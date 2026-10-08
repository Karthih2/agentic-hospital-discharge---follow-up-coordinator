"""Role matrix (every cell, allowed and denied), hub isolation, guardians, and the new jobs and routing rules.

Cast (conftest.seed): patient1 = the patient; daughter1 = hub manager with "full"; son1 = viewer with "reminders";
brother1 = viewer with "appointments"; doctor1 is assigned to the patient, doctor2 is not; mgmt1 = admin."""
import asyncio
from datetime import timedelta

import pytest

from app.core import db as dbmod
from app.core import jobs
from app.core.util import now
from app.modules.auth import service as accounts
from app.modules.hubs import service as hubs
from app.pipeline import extraction_agent
from app.pipeline.extraction_agent import MedicineFields, Outcome
from tests.conftest import PW, SUMMARY, item, login, new_client, upload

run = asyncio.run


def db():
    return dbmod.get_db()


@pytest.fixture
def plan(clients, world):
    pid = str(world["patient"])
    upload(clients["patient1"], pid)
    tasks = clients["patient1"].get(f"/patients/{pid}/tasks").json()
    by = {t["title"]: t for t in tasks}
    return pid, by


def codes(c, method, url, **kw):
    if method == "delete":
        kw.pop("json", None)
    return getattr(c, method)(url, **kw).status_code


ROLES = ["mgmt1", "doctor1", "doctor2", "daughter1", "patient1", "son1", "brother1"]


# ---- row 1: see a patient's full plan
def test_matrix_see_full_plan(clients, world, plan):
    pid, by = plan
    sid = run(db().discharge_summaries.find_one({}))["_id"]
    got = {r: codes(clients[r], "get", f"/patients/{pid}/tasks") for r in ROLES}
    assert got == {"mgmt1": 403, "doctor1": 403, "doctor2": 403, "daughter1": 200, "patient1": 200, "son1": 200,
                   "brother1": 200}
    # the full plan (source line, flags) reaches only the patient and a manager with "full" consent
    for who, expect in (("patient1", True), ("daughter1", True), ("son1", False), ("brother1", False)):
        rows = clients[who].get(f"/patients/{pid}/tasks").json()
        assert any("source_line" in t for t in rows) is expect, who
    # original summary text
    assert {r: codes(clients[r], "get", f"/summaries/{sid}") for r in ROLES} == {
        "mgmt1": 403, "doctor1": 403, "doctor2": 403, "daughter1": 200, "patient1": 200, "son1": 403, "brother1": 403}


# ---- rows 2 and 3: appointment titles and dates; reminders
def test_matrix_appointments_and_reminders(clients, world, plan):
    pid, by = plan
    appt = clients["brother1"].get(f"/patients/{pid}/tasks").json()  # "appointments" consent
    assert appt and {t.get("type") for t in appt if t.get("type")} <= {"appointment", "test", "referral"}
    assert all("title" in t and "due_date" in t for t in appt if not t.get("locked"))
    rem = clients["son1"].get(f"/patients/{pid}/tasks").json()  # "reminders" consent: title, date, status only
    assert {k for t in rem for k in t} <= {"id", "title", "due_date", "status", "locked", "message", "appointment"}
    assert any(t.get("title") == "Cardiology follow-up" for t in rem)
    # the assigned doctor sees appointment titles and dates read-only; an unassigned doctor sees none
    mine = clients["doctor1"].get("/review/patients").json()
    assert mine and any(a["title"] == "Cardiology follow-up" for a in mine[0]["appointments"])
    assert clients["doctor2"].get("/review/patients").json() == []
    for who in ("mgmt1", "patient1", "daughter1", "son1"):
        assert codes(clients[who], "get", "/review/patients") == 403


# ---- row 4: upload
def test_matrix_upload(clients, world):
    pid = str(world["patient"])
    res = {r: codes(clients[r], "post", f"/patients/{pid}/summaries", data={"text": SUMMARY}) for r in ROLES}
    assert res == {"mgmt1": 403, "doctor1": 403, "doctor2": 403, "daughter1": 202, "patient1": 202, "son1": 403,
                   "brother1": 403}


# ---- row 5: mark done, undo, reminder
def test_matrix_tick_and_reminder(clients, world, plan):
    pid, by = plan
    tid = by["Wound dressing"]["id"]
    for who in ("mgmt1", "doctor1", "doctor2", "son1", "brother1"):
        assert codes(clients[who], "post", f"/tasks/{tid}/complete") == 403, who
        assert codes(clients[who], "post", f"/tasks/{tid}/reminder", json={"enabled": False}) == 403, who
    assert codes(clients["daughter1"], "post", f"/tasks/{tid}/complete") == 200
    assert codes(clients["daughter1"], "post", f"/tasks/{tid}/undo") == 200
    assert codes(clients["patient1"], "post", f"/tasks/{tid}/complete") == 200
    assert codes(clients["patient1"], "post", f"/tasks/{tid}/reminder", json={"enabled": False}) == 200


# ---- row 6: edit medicines or instructions
def test_matrix_nobody_edits_a_medicine(clients, world, plan):
    pid, by = plan
    tid = by["Metformin"]["id"]
    for who in ROLES:
        for method in ("patch", "put", "delete"):
            assert codes(clients[who], method, f"/tasks/{tid}", json={"title": "x"}) in (404, 405), (who, method)
    # a hand-typed medicine is never trusted: it waits for a doctor, whoever typed it
    r = clients["patient1"].post(f"/patients/{pid}/tasks", json={"type": "medicine", "title": "X", "medicine": {
        "name": "X", "dose": "5 mg", "timing": "daily", "duration": "5 days"}})
    assert r.json()["status"] == "Needs Review"
    assert codes(clients["daughter1"], "post", f"/patients/{pid}/tasks",
                 json={"type": "medicine", "title": "Y", "medicine": {"name": "Y"}}) == 201
    assert codes(clients["son1"], "post", f"/patients/{pid}/tasks",
                 json={"type": "care_instruction", "title": "Z", "instruction": "z"}) == 403
    # only a doctor changes values, only by resolving a review, and the gate re-checks
    rid = clients["doctor1"].get("/review/queue").json()[0]["id"]
    bad = clients["doctor1"].post(f"/review/{rid}/resolve", json={"outcome": "corrected", "corrected_values": {
        "medicine": {"dose": "75 mg"}}})
    assert bad.status_code == 422
    assert run(db().task_revisions.count_documents({})) == 0  # nothing was changed, so nothing was versioned


# ---- row 7: resolve a review
def test_matrix_resolve_review(clients, world, plan):
    rid = clients["doctor1"].get("/review/queue").json()[0]["id"]
    for who in ("mgmt1", "doctor2", "daughter1", "patient1", "son1", "brother1"):
        assert codes(clients[who], "post", f"/review/{rid}/resolve", json={"outcome": "confirmed"}) == 403, who
    good = {"outcome": "corrected", "corrected_values": {"medicine": {"dose": "75 mg", "duration": "30 days"}}}
    assert codes(clients["doctor1"], "post", f"/review/{rid}/resolve", json=good) == 200
    assert run(db().task_revisions.count_documents({})) == 1  # Document Versioning: the old values were kept


# ---- row 8: consent
def test_matrix_consent(clients, world):
    pid, hub, son = str(world["patient"]), str(world["hub"]), str(world["son"])
    url = f"/hubs/{hub}/patients/{pid}/consents/{son}"
    for who in ("mgmt1", "doctor1", "daughter1", "son1", "brother1"):
        assert codes(clients[who], "put", url, json={"level": "appointments"}) == 403, who
        assert codes(clients[who], "delete", url) == 403, who
    assert codes(clients["patient1"], "put", url, json={"level": "appointments"}) == 200
    assert codes(clients["patient1"], "delete", url) == 200


def test_guardian_consents_for_a_child_and_only_the_guardian(clients, world):
    async def make():
        child = await accounts.create_user("Little Giri", "giri1", PW, "patient", "ta", None, can_login=False,
                                           guardian_id=world["daughter"])
        await hubs.add_member(world["hub"], child["_id"], "patient")
        await hubs.grant(child["_id"], world["daughter"], world["hub"], "full", world["daughter"], guardian=True)
        return child["_id"]
    cid = str(run(make()))
    url = f"/hubs/{world['hub']}/patients/{cid}/consents/{world['son']}"
    assert codes(clients["daughter1"], "put", url, json={"level": "reminders"}) == 200  # the guardian
    assert run(db().consents.find_one({"patient_id": run(make_oid(cid)), "grantee_id": world["son"],
                                       "revoked_at": None}))["guardian_consent"] is True
    assert codes(clients["son1"], "put", url, json={"level": "reminders"}) == 403
    assert codes(clients["patient1"], "put", url, json={"level": "reminders"}) == 403
    assert codes(new_client(), "post", "/auth/login", json={"login": "giri1", "password": PW}) == 401  # no login
    # the guardian can upload for the child
    assert codes(clients["daughter1"], "post", f"/patients/{cid}/summaries", data={"text": SUMMARY}) == 202


async def make_oid(s):
    from bson import ObjectId
    return ObjectId(s)


# ---- row 9: admin only
def test_matrix_admin_only(clients, world, plan):
    did = str(world["doctor1"])
    for who in ROLES:
        ok = who == "mgmt1"
        assert (codes(clients[who], "get", "/admin-api/overview") == 200) is ok, who
        assert (codes(clients[who], "put", f"/admin-api/doctors/{did}/availability", json={"available": True}) == 200) is ok
        assert (codes(clients[who], "get", "/admin-api/system") == 200) is ok
    rid = clients["mgmt1"].get("/admin-api/reviews").json()[0]["id"]
    for who in ROLES[1:]:
        assert codes(clients[who], "post", f"/admin-api/reviews/{rid}/assign", json={"doctor_id": did}) == 403, who
    assert codes(clients["mgmt1"], "post", f"/admin-api/reviews/{rid}/assign", json={"doctor_id": did}) == 200
    assert not any(p.endswith("/bulk") or "bulk" in p for p in [r.path for r in __import__("app.main", fromlist=["app"]).app.routes])


# ---- row 10: clinical text
def test_matrix_admin_never_sees_clinical_text(clients, world, plan):
    pid, by = plan
    blob = ""
    for url in ("/admin-api/overview", "/admin-api/doctors", "/admin-api/reviews", "/admin-api/hubs", "/admin-api/audit",
                "/admin-api/summary-notices", "/admin-api/system", "/admin-api/people"):
        blob += clients["mgmt1"].get(url).text
    for secret in ("Metformin", "Aspirin", "cardiologist", "Wound", "500 mg", "source_line", "raw_text"):
        assert secret not in blob, secret


# ---- row 11: audit log
def test_matrix_audit(clients, world, plan):
    assert codes(clients["mgmt1"], "get", "/admin-api/audit") == 200
    for who in ("doctor1", "doctor2", "daughter1", "patient1", "son1", "brother1"):
        assert codes(clients[who], "get", "/admin-api/audit") == 403, who
    assert codes(clients["patient1"], "get", "/me/audit") == 200
    for who in ("mgmt1", "doctor1", "daughter1", "son1", "brother1"):
        assert codes(clients[who], "get", "/me/audit") == 403, who
    rows = clients["mgmt1"].get("/admin-api/audit").json()
    assert rows and set(rows[0]) == {"ts", "actor_id", "actor", "action", "target_type", "target_id", "result"}
    only = clients["mgmt1"].get("/admin-api/audit", params={"actor": str(world["daughter"])}).json()
    assert all(r["actor_id"] == str(world["daughter"]) for r in only)
    assert clients["mgmt1"].get("/admin-api/audit", params={"date_from": "2999-01-01"}).json() == []


# ---- the hub: nothing mixes between patients
def test_two_patients_in_one_hub_never_mix(clients, world, monkeypatch):
    async def by_text(raw):
        if "Ramipril" in raw:
            return Outcome(discharge_date_text="02 Nov 2026", items=[
                item("medicine", "Tab. Ramipril 5 mg once daily for 30 days after food.", title="Ramipril",
                     medicine=MedicineFields(name="Ramipril", dose="5 mg", timing="once daily", duration="30 days")),
                item("appointment", "Follow up with orthopedic surgeon in 3 weeks.", title="Ortho follow-up",
                     due_date_text="in 3 weeks", specialty="Orthopedics")])
        from tests.conftest import sample_outcome
        return sample_outcome()
    monkeypatch.setattr(extraction_agent, "extract", by_text)

    kabel = new_client()
    r = kabel.post("/auth/register", json={"name": "Kabel", "login": "kabel1", "password": PW, "role": "patient"})
    kabel.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    kid, kcode = r.json()["id"], kabel.get("/me").json()["patient_code"]
    hub = str(world["hub"])
    assert clients["daughter1"].post(f"/hubs/{hub}/invite-patient", json={"patient_code": kcode}).status_code == 202
    inv = kabel.get("/me/invites").json()[0]["id"]
    assert kabel.post(f"/invites/{inv}/approve", json={"level": "full"}).status_code == 200

    pid = str(world["patient"])
    upload(clients["patient1"], pid)
    r = kabel.post(f"/patients/{kid}/summaries", data={"text": SUMMARY + "\nTab. Ramipril 5 mg once daily for 30 days after food.\nFollow up with orthopedic surgeon in 3 weeks.\n"})
    assert r.status_code == 202

    d = clients["daughter1"]
    asha = str(d.get(f"/patients/{pid}/tasks").json())
    kab = str(d.get(f"/patients/{kid}/tasks").json())
    assert "Metformin" in asha and "Ramipril" not in asha
    assert "Ramipril" in kab and "Metformin" not in kab
    assert not d.get(f"/patients/{kid}/summaries").json()[0]["counts"] == d.get(f"/patients/{pid}/summaries").json()[0]["counts"]

    home = next(h for h in d.get("/hubs").json() if h["id"] == hub)
    cards = {c["name"]: c for c in home["patients"]}
    assert set(cards) == {"Asha Raman", "Kabel"} and cards["Kabel"]["counts"]["Pending"] == 2
    assert cards["Asha Raman"]["counts"] == {"Pending": 5, "Completed": 0, "Needs Review": 1}
    # a viewer who has consent for Asha only sees nothing of Kabel
    assert codes(clients["son1"], "get", f"/patients/{kid}/tasks") == 403
    son_home = next(h for h in clients["son1"].get("/hubs").json() if h["id"] == hub)
    assert {c["name"]: c["access"] for c in son_home["patients"]} == {"Asha Raman": "reminders", "Kabel": "none"}
    assert all(c["counts"] is None for c in son_home["patients"] if c["access"] == "none")
    # Kabel cannot see Asha, and a patient's reminders go only to people subscribed to that channel
    assert codes(kabel, "get", f"/patients/{pid}/tasks") == 403
    kt = run(db().tasks.find_one({"patient_id": __import__("bson").ObjectId(kid), "type": "appointment"}))
    from app.modules.notifications import service as notify
    subs = run(notify.subscribers(kt["patient_id"], "appointment"))
    assert world["daughter"] in subs and world["son"] not in subs  # son1 has consent for Asha, not Kabel


def test_viewer_sees_hub_but_filtered_counts(clients, world, plan):
    hub = str(world["hub"])
    card = lambda who: next(h for h in clients[who].get("/hubs").json() if h["id"] == hub)["patients"][0]  # noqa: E731
    assert card("brother1")["counts"] is None and card("brother1")["access"] == "appointments"
    assert card("son1")["counts"]["Needs Review"] == 1
    assert card("patient1")["access"] == "self"
    assert codes(clients["mgmt1"], "get", "/hubs") == 403 and codes(clients["doctor1"], "get", "/hubs") == 403


# ---- family sees only "waiting"
def test_family_sees_waiting_never_the_item(clients, world, plan):
    pid, by = plan
    for who in ("daughter1", "son1"):
        locked = [t for t in clients[who].get(f"/patients/{pid}/tasks").json() if t.get("locked")]
        assert locked and all(set(t) == {"id", "status", "locked", "message"} for t in locked)
        assert locked[0]["message"] == "Waiting for doctor review"
    tid = by["Aspirin"]["id"]
    assert clients["daughter1"].get(f"/tasks/{tid}").json()["locked"] is True
    assert "Aspirin" not in clients["daughter1"].get(f"/tasks/{tid}").text


# ---- routing and jobs
def test_unavailable_doctor_review_routes_to_fallback_at_creation(clients, world):
    async def off():
        await db().doctors.update_one({"user_id": world["doctor1"]}, {"$set": {"available": False}})
    run(off())
    upload(clients["patient1"], str(world["patient"]))
    rv = run(db().review_queue.find_one({}))
    assert rv["assigned_doctor_id"] == world["doctor2"]  # Dr. Jason's case: primary is out, the fallback takes it
    assert rv["assignment_history"][0]["reason"] == "initial_fallback"


def test_assignment_is_atomic_and_chain_cycles_are_safe(clients, world, plan):
    from app.pipeline import review_router
    rv = run(db().review_queue.find_one({}))

    async def cycle():
        await db().doctors.update_one({"user_id": world["doctor2"]}, {"$set": {"fallback_doctor_id": world["doctor1"]}})
        chain = await review_router.chain(world["doctor1"])
        stale = dict(rv)
        first = await review_router.assign_to(rv, world["doctor2"], "admin")
        second = await review_router.assign_to(stale, world["doctor2"], "admin")  # stale view of who had it
        return chain, first, second
    chain, first, second = run(cycle())
    assert chain == [world["doctor2"]]  # doctor1 -> doctor2 -> doctor1 stops instead of looping
    assert first is True and second is False  # the second, stale update loses


def test_jobs_take_a_lease_and_are_idempotent(clients, world, plan):
    assert run(jobs.lease("send_due_notifications", 30)) is True
    assert run(jobs.lease("send_due_notifications", 30)) is False  # a second process cannot take it
    ran = run(jobs.run_due_jobs())
    assert "send_due_notifications" not in ran and "missed_task_check" in ran
    run(db().job_locks.update_many({}, {"$set": {"locked_until": now() - timedelta(seconds=1)}}))
    assert "cleanup" in run(jobs.run_due_jobs())
    assert run(db().job_locks.find_one({"_id": "cleanup"}))["last_error"] is None
    # idempotent: a second pass finds nothing new
    assert run(jobs.missed_task_check()) == 0 and run(jobs.send_due_notifications()) == 0


def test_health_and_stats(world):
    c = new_client()
    r = c.get("/health")
    assert r.status_code == 200 and r.json() == {"db": "ok"}
    login(c, "patient1")
    pid = str(world["patient"])
    assert c.get(f"/patients/{pid}/tasks").json() == []
