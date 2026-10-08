"""Seed the whole demo from sample_data/discharge_template/demo_people.json.

    python -m scripts.seed_demo --reset            wipe the database, then build everything
    python -m scripts.seed_demo --reset --no-upload   people, hubs and providers only (no model calls)
    python -m scripts.seed_demo --memory           same, on an in-memory database (when Atlas is not reachable)

Creates the admin, 10 doctors, 4 patients, 3 family members, 2 hubs with consents, synthetic providers, and then
uploads the 5 sample summaries THROUGH THE REAL API (as the patient, or the guardian for a child), so the real
pipeline builds the plans and fills the review queue. Everything is fictional. Password for every login: see JSON."""
import asyncio
import json
import sys
from pathlib import Path

import httpx

from app.core.constants import SCHEMA_VERSION
from app.core.db import get_db, init_db, set_db
from app.core.util import now
from app.main import app
from app.modules.auth import service as accounts
from app.modules.hubs import service as hubs
from scripts.seed import reset, seed_reference

DIR = Path(__file__).resolve().parents[1] / "sample_data" / "discharge_template"
PHONE = "+91-XXXXX-XXXXX"


async def build_people(data: dict) -> dict:
    db, pw = get_db(), data["password"]
    ids: dict = {}
    a = data["admin"]
    ids[a["key"]] = (await accounts.create_user(a["name"], a["login"], pw, "admin", "en", PHONE))["_id"]
    for d in data["doctors"]:
        ids[d["key"]] = (await accounts.create_user(d["name"], d["login"], pw, "doctor", "en", d["phone"]))["_id"]
    for p in sorted(data["patients"], key=lambda x: x["guardian"] is not None):  # guardians first
        ids[p["key"]] = (await accounts.create_user(
            p["name"], p["login"], pw, "patient", p["language"], PHONE, patient_code=p["patient_code"],
            can_login=p["can_login"], guardian_id=ids[p["guardian"]] if p["guardian"] else None,
            age_label=p["age"]))["_id"]
    for f in data["family"]:
        ids[f["key"]] = (await accounts.create_user(f["name"], f["login"], pw, "family", f["language"], PHONE))["_id"]
    patients_of = {d["key"]: [ids[k] for k in d["assigned_patients"]] for d in data["doctors"]}
    await db.doctors.insert_many([
        {"user_id": ids[d["key"]], "specialty": d["specialty"], "clinic": d["clinic"], "area": d["area"],
         "available": d["available"], "unavailable_until": None, "assigned_patient_ids": patients_of[d["key"]],
         "fallback_doctor_id": ids[d["fallback"]], "schema_version": SCHEMA_VERSION} for d in data["doctors"]])
    for h in data["hubs"]:
        hub = {"name": h["name"], "manager_id": ids[h["manager"]], "created_at": now(), "schema_version": SCHEMA_VERSION}
        hub["_id"] = (await db.family_hubs.insert_one(hub)).inserted_id
        for m in h["members"]:
            await hubs.add_member(hub["_id"], ids[m["person"]], m["role"])
        for c in h["consents"]:
            await hubs.grant(ids[c["patient"]], ids[c["grantee"]], hub["_id"], c["level"], ids[c["granted_by"]],
                             guardian=c.get("guardian_consent", False))
    return ids


async def upload_all(data: dict, ids: dict) -> list[dict]:
    """Log in through the API and upload each summary as the patient, or as the guardian for a child."""
    rows = []
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://demo", timeout=300) as c:
        people = {p["key"]: p for p in data["patients"]}
        for fname, who in data["summaries"].items():
            patient = people[who]
            uploader = patient["guardian"] or who  # a child's plan is managed by the guardian
            login = {**{p["key"]: p["login"] for p in data["patients"]}}[uploader]
            r = await c.post("/auth/login", json={"login": login, "password": data["password"]})
            token = c.cookies.get("access_token")
            c.cookies.clear()
            text = (DIR / fname).read_text(encoding="utf-8")
            r = await c.post(f"/patients/{ids[who]}/summaries", data={"text": text},
                             headers={"Authorization": f"Bearer {token}"})
            st = r.json()
            sid = st["id"]
            status = (await c.get(f"/summaries/{sid}/status", headers={"Authorization": f"Bearer {token}"})).json()
            rows.append({"file": fname, "patient": who, "uploaded_by": uploader, "http": r.status_code,
                         "status": status["status"], "counts": status.get("counts")})
            print(f"  {fname:42} {who:12} {status['status']:9} {status.get('counts')}")
    return rows


def login_table(data: dict) -> None:
    pw = data["password"]
    rows = [(data["admin"]["login"], data["admin"]["name"], "Admin (open /admin)")]
    rows += [(d["login"], d["name"], f"Doctor, {d['specialty']}" + ("" if d["available"] else " (UNAVAILABLE)"))
             for d in data["doctors"]]
    for p in data["patients"]:
        rows.append((p["login"] if p["can_login"] else "(no login)", p["name"],
                     f"Patient {p['patient_code']}" + (f", managed by {p['guardian']}" if p["guardian"] else "")))
    hub_roles = {}
    for h in data["hubs"]:
        for m in h["members"]:
            hub_roles.setdefault(m["person"], []).append(f"{m['role']} of {h['name']}")
    rows += [(f["login"], f["name"], "Family: " + "; ".join(hub_roles.get(f["key"], []))) for f in data["family"]]
    print(f"\n{'login':16} {'name':34} role   (password for all: {pw})")
    for lg, nm, role in rows:
        print(f"{lg:16} {nm:34} {role}")


async def main() -> None:
    data = json.loads((DIR / "demo_people.json").read_text(encoding="utf-8"))
    if "--memory" in sys.argv:  # no Atlas: an in-memory database, real model calls. Gone when the script ends.
        from mongomock_motor import AsyncMongoMockClient
        set_db(AsyncMongoMockClient(tz_aware=True)["demo"])
    elif "--reset" in sys.argv:
        print("resetting database ...")
        await reset()
    else:
        await init_db()
    await seed_reference()
    ids = await build_people(data)
    print("people, hubs, consents and providers created")
    if "--no-upload" not in sys.argv:
        print("uploading the 5 summaries through the API (real model, this takes a minute) ...")
        await upload_all(data, ids)
    login_table(data)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
