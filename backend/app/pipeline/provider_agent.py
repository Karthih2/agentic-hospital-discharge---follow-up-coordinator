"""Provider matching agent (code, no AI). Specialty + location, ranked by proximity. Coordinates are never stored."""
import math
import re

from app.core.constants import PROVIDER_LABEL
from app.core.db import get_db

SPECIALTY_ALIASES = {
    "cardiologist": "cardiology", "heart": "cardiology", "orthopedic": "orthopedics", "orthopaedics": "orthopedics",
    "orthopaedic": "orthopedics", "orthopedist": "orthopedics", "physiotherapist": "physiotherapy",
    "physio": "physiotherapy", "neurologist": "neurology", "endocrinologist": "endocrinology",
    "diabetologist": "endocrinology", "nephrologist": "nephrology", "urologist": "urology",
    "gastroenterologist": "gastroenterology", "pulmonologist": "pulmonology", "oncologist": "oncology",
    "dermatologist": "dermatology", "general physician": "general medicine", "physician": "general medicine",
    "general surgeon": "general surgery", "surgeon": "general surgery", "ent": "ent",
}


def norm_specialty(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip().casefold())
    return SPECIALTY_ALIASES.get(s, s)


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _public(p: dict, dist: float) -> dict:
    lng, lat = p["location"]["coordinates"]
    return {"id": str(p["_id"]), "name": p["name"], "specialty": p["specialty"], "facility": p.get("facility"),
            "type": p["type"], "pin_color": "blue" if p["type"] == "hospital" else "green",
            "state": p.get("state"), "district": p.get("district"), "area": p.get("area"),
            "lat": lat, "lng": lng, "distance_km": round(dist, 1), "contact": p.get("contact"),
            "languages": [a["v"] for a in p.get("attributes", []) if a["k"] == "language"],
            "facility_type": next((a["v"] for a in p.get("attributes", []) if a["k"] == "facility_type"), None),
            "label": PROVIDER_LABEL}


async def search(specialty: str, lat=None, lng=None, state=None, district=None, area=None, limit: int = 5) -> list:
    """GPS search when lat/lng are given, otherwise the State > District > Area drill-down. Top 3 to 5."""
    db = get_db()
    want = norm_specialty(specialty)
    if lat is not None and lng is not None:
        origin, query = (lat, lng), {}
    else:
        loc = await db.locations.find_one({"kind": "area", "name": area, "$and": [
            {"ancestors.name": state}, {"ancestors.name": district}]})  # Tree pattern: State > District > Area
        if not loc:
            return []
        lng0, lat0 = loc["centre"]["coordinates"]
        # The chosen area is the starting point; providers across the same state are ranked by distance from it, so
        # a small area still yields 3 to 5 suggestions (the nearest, usually inside the area itself, come first).
        origin, query = (lat0, lng0), {"state": state}
    # ponytail: Python haversine over the filtered set. Switch to a $geoNear pipeline (2dsphere index exists) if providers reach thousands.
    found = []
    async for p in db.providers.find({**query, "synthetic": True}):
        if norm_specialty(p["specialty"]) == want:
            lng_p, lat_p = p["location"]["coordinates"]
            found.append((haversine_km(origin[0], origin[1], lat_p, lng_p), p))
    found.sort(key=lambda x: x[0])
    top = found[:max(3, min(limit, 5))]
    return [_public(p, d) for i, (d, p) in enumerate(top) if i < 3 or d <= 100]  # 3 always, extras within 100 km


async def get_public(provider_id) -> dict | None:
    p = await get_db().providers.find_one({"_id": provider_id, "synthetic": True})
    if not p:
        return None
    out = _public(p, 0.0)
    out.pop("distance_km")
    return out
