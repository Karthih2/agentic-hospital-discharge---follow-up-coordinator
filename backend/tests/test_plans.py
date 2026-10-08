"""Doctor-reviewed plan workflow: draft -> matched doctor reviews and edits -> publish -> patient sees it."""
import asyncio

from app.core import db as dbmod
from app.pipeline import extraction_agent
from tests.conftest import SUMMARY, upload

run = asyncio.run


def db():
    return dbmod.get_db()


def draft(clients, world, text=SUMMARY):
    pid = str(world["patient"])
    sid = upload(clients["patient1"], pid, text, publish_plan=False)
    return pid, sid


def plan_of(c, sid):
    r = c.get(f"/plans/{sid}")
    assert r.status_code == 200, r.text
    return r.json()


def by_title(plan):
    return {t["title"]: t for t in plan["tasks"]}


# ---------- a draft plan does not exist for the patient or family
def test_draft_is_invisible_to_patient_and_family(clients, world):
    pid, sid = draft(clients, world)
    p, fam = clients["patient1"], clients["daughter1"]
    st = p.get(f"/summaries/{sid}/status").json()
    assert st["status"] == "ready" and st["plan_status"] == "draft" and st["doctor_name"] == "Dr. Meera Iyer"
    assert st["counts"] == {"tasks": 0, "needs_review": 0}
    assert p.get(f"/patients/{pid}/tasks").json() == []
    assert fam.get(f"/patients/{pid}/tasks").json() == []
    tl = p.get(f"/patients/{pid}/timeline").json()
    assert tl["counts"] == {"Pending": 0, "Completed": 0, "Needs Review": 0} and tl["days"] == []
    assert p.get(f"/summaries/{sid}").json()["highlights"] == []
    tid = plan_of(clients["doctor1"], sid)["tasks"][0]["id"]
    for verb, url in (("get", f"/tasks/{tid}"), ("post", f"/tasks/{tid}/complete"), ("post", f"/tasks/{tid}/flag")):
        assert getattr(p, verb)(url, **({"json": {}} if verb == "post" else {})).status_code == 404
    # nothing was scheduled or sent to the patient's side
    assert run(db().notifications.count_documents({"type": "reminder"})) == 0
    assert p.get("/me/notifications").json() == []
    hub = next(h for h in fam.get("/hubs").json() if h["id"] == str(world["hub"]))
    assert hub["patients"][0]["counts"] == {"Pending": 0, "Completed": 0, "Needs Review": 0}
    # the doctor was told a plan is waiting
    assert any(n["type"] == "plan_ready" for n in clients["doctor1"].get("/me/notifications").json())


def test_only_the_matched_doctor_opens_the_plan(clients, world):
    _, sid = draft(clients, world)
    assert clients["doctor2"].get(f"/plans/{sid}").status_code == 403
    for who in ("patient1", "daughter1", "mgmt1"):
        assert clients[who].get(f"/plans/{sid}").status_code == 403
    assert clients["doctor2"].get("/plans").json() == []
    mine = clients["doctor1"].get("/plans").json()
    assert len(mine) == 1 and mine[0]["patient_name"] == "Asha Raman" and mine[0]["counts"]["needs_review"] == 1
    assert mine[0]["match_reason"] == "Already this patient's doctor"
    # draft items are worked in the plan editor, not in the general review queue
    assert clients["doctor1"].get("/review/queue").json() == []


# ---------- doctor matching
def test_attending_physician_on_the_summary_wins(clients, world):
    text = "Attending Physician: Dr. Arun Mathew, General Medicine (attending on the day of discharge)\n" + SUMMARY
    _, sid = draft(clients, world, text)
    s = run(db().discharge_summaries.find_one({"_id": sid}))
    assert s["plan_doctor_id"] == world["doctor2"] and s["plan_match"]["reason"].startswith("Attending physician")
    assert plan_of(clients["doctor2"], sid)["match"]["attending"] == "Dr. Arun Mathew"
    assert clients["doctor1"].get(f"/plans/{sid}").status_code == 403
    # the doctor now looks after this patient
    assert world["patient"] in run(db().doctors.find_one({"user_id": world["doctor2"]}))["assigned_patient_ids"]


def test_specialty_match_and_unavailable_fallback(clients, world):
    run(db().doctors.update_one({"user_id": world["doctor1"]}, {"$set": {"assigned_patient_ids": []}}))
    text = "Attending Physician: Dr. Someone Else, General Medicine\n" + SUMMARY
    _, sid = draft(clients, world, text)
    s = run(db().discharge_summaries.find_one({"_id": sid}))
    assert s["plan_doctor_id"] == world["doctor2"] and "Specialty match" in s["plan_match"]["reason"]
    run(db().doctors.update_one({"user_id": world["doctor2"]}, {"$set": {"available": False}}))
    run(db().doctors.update_one({"user_id": world["doctor2"]}, {"$set": {"fallback_doctor_id": world["doctor1"]}}))
    _, sid2 = draft(clients, world, text.replace("Someone Else", "Another One"))
    s2 = run(db().discharge_summaries.find_one({"_id": sid2}))
    assert s2["plan_doctor_id"] == world["doctor1"] and "fallback" in s2["plan_match"]["reason"]
    # the plan's flagged items go to the same doctor as the plan
    task_ids = [t["_id"] for t in run(db().tasks.find({"summary_id": sid2}).to_list())]
    for rv in run(db().review_queue.find({"task_id": {"$in": task_ids}}).to_list()):
        assert rv["assigned_doctor_id"] == world["doctor1"]


# ---------- review, edit, publish
def test_doctor_edits_then_publishes(clients, world):
    pid, sid = draft(clients, world)
    d = clients["doctor1"]
    plan = plan_of(d, sid)
    assert plan["patient"]["name"] == "Asha Raman" and plan["counts"] == {"total": 6, "needs_review": 1, "ready": 5}
    asp = by_title(plan)["Aspirin"]
    assert asp["status"] == "Needs Review" and {r["code"] for r in asp["reasons"]} >= {"MISSING_DOSE"}
    assert plan["summary"]["raw_text"].startswith("Discharge date") and plan["summary"]["highlights"]

    r = d.post(f"/plans/{sid}/publish", json={})
    assert r.status_code == 409 and r.json()["detail"]["needs_review"] == 1  # flagged items block publishing
    r = d.patch(f"/plans/{sid}/tasks/{asp['id']}", json={"medicine": {"dose": "75 mg"}})
    assert r.status_code == 422 and "MISSING_DURATION" in str(r.json())  # the gate re-checks the new values
    r = d.patch(f"/plans/{sid}/tasks/{asp['id']}", json={"medicine": {"dose": "75 mg", "duration": "30 days"}})
    assert r.status_code == 200 and r.json()["status"] == "Pending" and r.json()["doctor_edited"]
    assert r.json()["source_line"] == "Tab. Aspirin once daily. Continue as advised."  # evidence never rewritten
    rv = run(db().review_queue.find_one({}))
    assert rv["status"] == "resolved" and rv["outcome"] == "corrected"
    assert run(db().task_revisions.count_documents({"kind": "plan_edit"})) == 1

    wound = by_title(plan)["Wound dressing"]
    r = d.patch(f"/plans/{sid}/tasks/{wound['id']}", json={"instruction": "Change the dressing every 2 days"})
    assert r.status_code == 200 and r.json()["simple_text"].startswith("Wound dressing")

    r = d.post(f"/plans/{sid}/publish", json={})
    assert r.status_code == 200 and r.json()["counts"] == {"total": 6, "needs_review": 0, "ready": 6}

    p = clients["patient1"]
    tasks = {t["title"]: t for t in p.get(f"/patients/{pid}/tasks").json()}
    assert len(tasks) == 6 and all(t["status"] == "Pending" for t in tasks.values())
    assert {r["key"]: r["value"] for r in tasks["Aspirin"]["medicine_card"]["rows"]}["dose"] == "75 mg"
    assert tasks["Aspirin"]["doctor_edited"] and not tasks["Metformin"]["doctor_edited"]
    assert p.get(f"/summaries/{sid}/status").json()["plan_status"] == "published"
    assert any(n["type"] == "plan_published" for n in p.get("/me/notifications").json())
    assert any(n["type"] == "plan_published" for n in clients["daughter1"].get("/me/notifications").json())
    assert run(db().notifications.count_documents({"type": "reminder"})) > 0  # scheduled only now

    # a published plan is locked for plan edits; later changes go through the normal flag -> review path
    assert d.patch(f"/plans/{sid}/tasks/{asp['id']}", json={"title": "x"}).status_code == 409
    assert d.post(f"/plans/{sid}/publish", json={}).status_code == 409
    assert p.post(f"/tasks/{tasks['Metformin']['id']}/flag", json={"note": "?"}).status_code == 200
    q = d.get("/review/queue").json()
    assert len(q) == 1 and q[0]["reasons"] == ["USER_FLAGGED"]


def test_confirm_remove_and_add(clients, world):
    pid, sid = draft(clients, world)
    d = clients["doctor1"]
    plan = by_title(plan_of(d, sid))
    assert d.post(f"/plans/{sid}/tasks/{plan['Metformin']['id']}/confirm").status_code == 409  # not flagged
    assert d.post(f"/plans/{sid}/tasks/{plan['Aspirin']['id']}/confirm").json()["status"] == "Pending"
    r = d.delete(f"/plans/{sid}/tasks/{plan['Warning signs']['id']}")
    assert r.status_code == 200 and r.json()["counts"]["total"] == 5
    assert run(db().task_revisions.count_documents({"kind": "plan_remove"})) == 1
    r = d.post(f"/plans/{sid}/tasks", json={"type": "appointment", "title": "Eye check-up"})
    assert r.status_code == 422  # incomplete: no date and no doctor or specialty
    r = d.post(f"/plans/{sid}/tasks", json={"type": "appointment", "title": "Eye check-up", "due_date": "2026-12-01",
                                            "specialty": "Ophthalmology", "due_time": "10:00 AM"})
    assert r.status_code == 201 and r.json()["source_line"].startswith("Added by your doctor")
    assert d.post(f"/plans/{sid}/publish", json={}).status_code == 200
    tasks = {t["title"]: t for t in clients["patient1"].get(f"/patients/{pid}/tasks").json()}
    assert "Warning signs" not in tasks and tasks["Eye check-up"]["due_date"] == "2026-12-01"
    assert tasks["Eye check-up"]["provider_needed"]


def test_publish_keeping_items_in_review(clients, world):
    pid, sid = draft(clients, world)
    r = clients["doctor1"].post(f"/plans/{sid}/publish", json={"keep_in_review": True})
    assert r.status_code == 200
    asp = next(t for t in clients["patient1"].get(f"/patients/{pid}/tasks").json() if t["status"] == "Needs Review")
    assert asp["locked"] and asp["display_text"] is None
    assert len(clients["doctor1"].get("/review/queue").json()) == 1  # now in the normal queue
    fam = clients["daughter1"].get(f"/patients/{pid}/tasks").json()
    assert any(t.get("message") == "Waiting for doctor review" and "title" not in t for t in fam)


# ---------- admin routing of plans (no clinical text)
def test_admin_sees_and_reassigns_plans_without_clinical_text(clients, world):
    _, sid = draft(clients, world)
    m = clients["mgmt1"]
    rows = m.get("/admin-api/plans").json()
    assert len(rows) == 1 and rows[0]["doctor"] == "Dr. Meera Iyer" and rows[0]["flagged"] == 1
    assert "Aspirin" not in str(rows) and "Metformin" not in str(rows)
    assert m.get("/admin-api/overview").json()["plans_waiting_for_doctor"] == 1
    r = m.post(f"/admin-api/plans/{sid}/assign", json={"doctor_id": str(world["doctor2"])})
    assert r.status_code == 200
    assert clients["doctor1"].get(f"/plans/{sid}").status_code == 403
    assert clients["doctor2"].get(f"/plans/{sid}").status_code == 200
    rv = run(db().review_queue.find_one({}))
    assert rv["assigned_doctor_id"] == world["doctor2"]  # the flagged item moved with its plan
    assert clients["doctor1"].get("/admin-api/plans").status_code == 403


def test_doctor_going_unavailable_moves_the_draft_with_its_items(clients, world):
    _, sid = draft(clients, world)
    r = clients["mgmt1"].put(f"/admin-api/doctors/{world['doctor1']}/availability", json={"available": False})
    assert r.json()["plans_moved"] == 1
    assert clients["doctor2"].get(f"/plans/{sid}").status_code == 200
    rv = run(db().review_queue.find_one({}))
    assert rv["assigned_doctor_id"] == world["doctor2"]


# ---------- a plan is always generated
def test_rule_based_fallback_builds_the_draft_when_the_model_fails(clients, world, monkeypatch):
    async def boom(raw):
        raise extraction_agent.AgentError("NO_API_KEY")
    monkeypatch.setattr(extraction_agent, "extract", boom)
    _, sid = draft(clients, world)
    s = run(db().discharge_summaries.find_one({"_id": sid}))
    assert s["status"] == "ready" and s["plan_status"] == "draft" and s["extraction_method"] == "rules"
    plan = plan_of(clients["doctor1"], sid)
    assert plan["counts"]["total"] == 6  # every numbered line became an item
    types = sorted(t["type"] for t in plan["tasks"])
    assert types == sorted(["appointment", "medicine", "test", "care_instruction", "warning_sign", "medicine"])
    # free-text lines get a low confidence on purpose: the doctor looks at every one
    assert all(t["status"] == "Needs Review" for t in plan["tasks"])
