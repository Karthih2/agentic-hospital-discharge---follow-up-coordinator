from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.constants import PROVIDER_LABEL
from app.core.db import get_db
from app.pipeline import provider_agent
from app.core.security import ratelimit
from app.core.security.access import Principal, require_role

router = APIRouter(tags=["providers"])
patient_or_family = require_role("patient", "family")


@router.get("/locations/states")
async def states(user: Principal = Depends(patient_or_family)):
    return sorted(await get_db().locations.distinct("name", {"kind": "state"}))


@router.get("/locations/districts")
async def districts(state: str, user: Principal = Depends(patient_or_family)):
    return sorted(await get_db().locations.distinct("name", {"kind": "district", "ancestors.name": state}))


@router.get("/locations/areas")
async def areas(state: str, district: str, user: Principal = Depends(patient_or_family)):
    return sorted(await get_db().locations.distinct(
        "name", {"kind": "area", "$and": [{"ancestors.name": state}, {"ancestors.name": district}]}))


@router.get("/providers")
async def providers(specialty: str = Query(min_length=2, max_length=60),
                    lat: float | None = Query(None, ge=-90, le=90), lng: float | None = Query(None, ge=-180, le=180),
                    state: str | None = None, district: str | None = None, area: str | None = None,
                    user: Principal = Depends(patient_or_family)):
    """GPS search (lat+lng) or the State > District > Area fallback. Coordinates are used for this query only
    and are never stored or logged."""
    ratelimit.limit("providers", user.id, 60, 3600)
    gps = lat is not None and lng is not None
    if not gps and not (state and district and area):
        raise HTTPException(422, "Give lat and lng, or state, district and area")
    results = await provider_agent.search(specialty, lat, lng, state, district, area)
    return {"label": PROVIDER_LABEL, "results": results}
