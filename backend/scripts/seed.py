"""Reference data and the small test world.

    python -m scripts.seed --reset --yes     wipe the database and load reference data only (locations, providers)
    (the demo people and their summaries come from  python -m scripts.seed_demo --reset)

Everything here is synthetic. Provider names, facilities and phone numbers are invented."""
import asyncio
import sys

from app.core.constants import SCHEMA_VERSION
from app.core.db import get_db, init_db
from app.modules.auth import service as accounts
from app.modules.hubs import service as hubs

PHONE = "+91-XXXXX-XXXXX"

LOCATIONS = [  # state, district, area, lat, lng
    ("Tamil Nadu", "Chennai", "Perambur", 13.1067, 80.2206), ("Tamil Nadu", "Chennai", "Adyar", 13.0012, 80.2565),
    ("Tamil Nadu", "Chennai", "T Nagar", 13.0418, 80.2341), ("Tamil Nadu", "Coimbatore", "RS Puram", 11.0067, 76.9496),
    ("Maharashtra", "Mumbai", "Andheri", 19.1197, 72.8464), ("Delhi", "New Delhi", "Dwarka", 28.5921, 77.0460),
    ("Tamil Nadu", "Chennai", "Anna Nagar", 13.0850, 80.2101), ("Tamil Nadu", "Chennai", "Kilpauk", 13.0836, 80.2417),
    ("Tamil Nadu", "Chennai", "Egmore", 13.0732, 80.2609),
]
AREA = {a: i for i, (_, _, a, _, _) in enumerate(LOCATIONS)}
PROVIDERS = [  # name, specialty, facility, type, area, lat offset, lng offset
    ("Dr. Ramesh Kumar", "Orthopedics", "Sunrise Bone and Joint Hospital", "hospital", "Perambur", 0.010, 0.008),
    ("Dr. Latha Venkat", "Orthopedics", "Perambur Family Clinic", "clinic", "Perambur", -0.006, 0.004),
    ("Dr. Anil Shah", "Orthopedics", "Marina Care Hospital", "hospital", "Adyar", 0.003, -0.002),
    ("Dr. Meera Iyer", "Cardiology", "Sunrise Heart Institute", "hospital", "Perambur", 0.004, -0.005),
    ("Dr. Suresh Babu", "Cardiology", "Heartline Clinic", "clinic", "Perambur", -0.012, 0.010),
    ("Dr. Kavitha Rao", "Cardiology", "Adyar Cardiac Centre", "hospital", "Adyar", 0.005, 0.003),
    ("Dr. Prakash Nair", "Cardiology", "T Nagar Heart Clinic", "clinic", "T Nagar", 0.001, 0.002),
    ("Dr. Divya Menon", "Physiotherapy", "Active Life Physio", "clinic", "Perambur", 0.002, 0.009),
    ("Dr. Karthik S", "Physiotherapy", "Perambur Rehab Centre", "clinic", "Perambur", -0.004, -0.006),
    ("Dr. Farah Khan", "Physiotherapy", "Adyar Movement Clinic", "clinic", "Adyar", 0.001, 0.001),
    ("Dr. Nalini Devi", "Endocrinology", "Sugar and Thyroid Clinic", "clinic", "Perambur", 0.007, 0.002),
    ("Dr. Rohan Das", "Endocrinology", "Metro Diabetes Hospital", "hospital", "T Nagar", 0.006, -0.004),
    ("Dr. Geetha Pillai", "General Medicine", "Perambur Family Clinic", "clinic", "Perambur", 0.003, 0.003),
    ("Dr. Arun Mathew", "General Medicine", "Sunrise General Hospital", "hospital", "Perambur", -0.009, 0.007),
    ("Dr. Sunita Joshi", "Cardiology", "Coastal Heart Hospital", "hospital", "Andheri", 0.004, 0.004),
    ("Dr. Imran Ali", "Orthopedics", "Capital Ortho Clinic", "clinic", "Dwarka", 0.002, 0.002),
    ("Dr. Revathi K", "Cardiology", "Kovai Heart Centre", "hospital", "RS Puram", 0.003, 0.001),
]
# At least 3 per demo specialty, spread over Anna Nagar, Perambur, Kilpauk and Egmore (all invented).
_DEMO_SPECIALTIES = ["Cardiology", "Orthopedics", "Endocrinology", "Pediatrics", "Pediatric Pulmonology",
                     "General Medicine", "General Surgery", "Physiotherapy", "Nephrology"]
_DEMO_AREAS = ["Anna Nagar", "Perambur", "Kilpauk", "Egmore"]
_FIRST = ["Aarthi", "Bala", "Chitra", "Dinesh", "Elango", "Fathima", "Gopal", "Hema", "Ilango", "Janaki", "Kumar",
          "Lavanya", "Murali", "Nithya", "Omar", "Priya", "Qadir", "Revathi", "Sathish", "Thenmozhi"]
_LAST = ["Narayanan", "Subramani", "Pillai", "Rajan", "Iyer", "Naidu", "Sekar", "Menon", "Varadhan", "Krishnan"]
_FACILITY = {"Cardiology": "Heart Care", "Orthopedics": "Bone and Joint", "Endocrinology": "Diabetes Centre",
             "Pediatrics": "Children's Clinic", "Pediatric Pulmonology": "Child Lung Clinic",
             "General Medicine": "Family Clinic", "General Surgery": "Surgical Clinic",
             "Physiotherapy": "Rehab Centre", "Nephrology": "Kidney Care"}


def _demo_providers() -> list[tuple]:
    out, n = [], 0
    for si, spec in enumerate(_DEMO_SPECIALTIES):
        for k in range(3):
            area = _DEMO_AREAS[(si + k) % 4]
            name = f"Dr. {_FIRST[(n * 3) % 20]} {_LAST[(n * 7) % 10]}"
            out.append((name, spec, f"{area} {_FACILITY[spec]}", "clinic" if k else "hospital", area,
                        (k - 1) * 0.004, (si % 3 - 1) * 0.003))
            n += 1
    return out


def _point(lat, lng):
    return {"type": "Point", "coordinates": [lng, lat]}


async def seed_reference() -> None:
    """Locations as a tree (state > district > area, with ancestors) and providers with attributes."""
    db = get_db()
    docs, seen = [], set()
    for s, d, a, la, ln in LOCATIONS:
        for kind, name, anc in (("state", s, []), ("district", d, [("state", s)]),
                                ("area", a, [("state", s), ("district", d)])):
            key = (kind, name, tuple(x[1] for x in anc))
            if key in seen:
                continue
            seen.add(key)
            docs.append({"kind": kind, "name": name, "ancestors": [{"kind": k, "name": n} for k, n in anc],
                         "centre": _point(la, ln), "schema_version": SCHEMA_VERSION})
    await db.locations.insert_many(docs)
    provs = []
    for i, (name, spec, fac, typ, area, dla, dln) in enumerate(PROVIDERS + _demo_providers()):
        s, d, a, la, ln = LOCATIONS[AREA[area]]
        provs.append({"name": name, "specialty": spec, "facility": fac, "type": typ, "state": s, "district": d,
                      "area": a, "location": _point(la + dla, ln + dln), "contact": f"+91-90000-{10000 + i:05d}",
                      "attributes": [{"k": "facility_type", "v": typ},
                                     {"k": "language", "v": "English"}, {"k": "language", "v": "Tamil"}]
                      + ([{"k": "language", "v": "Hindi"}] if i % 3 == 0 else []),
                      "synthetic": True, "schema_version": SCHEMA_VERSION})
    await db.providers.insert_many(provs)


async def seed(password: str) -> dict:
    """Small world for the tests: one patient with a hub (manager with full access, two viewers), two doctors, admin."""
    db = get_db()
    mk = accounts.create_user
    patient = await mk("Asha Raman", "patient1", password, "patient", "en", PHONE, patient_code="PAT-2845")
    daughter = await mk("Divya Raman", "daughter1", password, "family", "en", PHONE)
    son = await mk("Vikram Raman", "son1", password, "family", "en", PHONE)
    brother = await mk("Mohan Raman", "brother1", password, "family", "en", PHONE)
    d1 = await mk("Dr. Meera Iyer", "doctor1", password, "doctor", "en", PHONE)
    d2 = await mk("Dr. Arun Mathew", "doctor2", password, "doctor", "en", PHONE)
    adm = await mk("Hospital Desk", "mgmt1", password, "admin", "en", PHONE)

    hub = {"name": "Raman family hub", "manager_id": daughter["_id"], "created_at": patient["created_at"],
           "schema_version": SCHEMA_VERSION}
    hub["_id"] = (await db.family_hubs.insert_one(hub)).inserted_id
    for uid, role in ((daughter["_id"], "manager"), (patient["_id"], "patient"), (son["_id"], "viewer"),
                      (brother["_id"], "viewer")):
        await hubs.add_member(hub["_id"], uid, role)
    await hubs.grant(patient["_id"], daughter["_id"], hub["_id"], "full", patient["_id"])
    await hubs.grant(patient["_id"], son["_id"], hub["_id"], "reminders", patient["_id"])
    await hubs.grant(patient["_id"], brother["_id"], hub["_id"], "appointments", patient["_id"])

    await db.doctors.insert_many([
        {"user_id": d1["_id"], "specialty": "Cardiology", "available": True, "unavailable_until": None,
         "assigned_patient_ids": [patient["_id"]], "fallback_doctor_id": d2["_id"], "schema_version": SCHEMA_VERSION},
        {"user_id": d2["_id"], "specialty": "General Medicine", "available": True, "unavailable_until": None,
         "assigned_patient_ids": [], "fallback_doctor_id": None, "schema_version": SCHEMA_VERSION}])
    await seed_reference()
    return {"password": password, "patient": patient["_id"], "daughter": daughter["_id"], "son": son["_id"],
            "brother": brother["_id"], "doctor1": d1["_id"], "doctor2": d2["_id"], "admin": adm["_id"],
            "hub": hub["_id"]}


async def reset() -> None:
    """Drop every collection (validators and indexes too), then rebuild them empty."""
    db = get_db()
    for name in await db.list_collection_names():
        await db.drop_collection(name)
    await init_db()


async def main():
    if "--reset" not in sys.argv or "--yes" not in sys.argv:
        sys.exit("This wipes ALL data in the database. Re-run with --reset --yes")
    await reset()
    await seed_reference()
    print("reset done; locations and providers loaded")


if __name__ == "__main__":
    asyncio.run(main())
