from datetime import date, datetime, timedelta, timezone

from bson import ObjectId
from fastapi import HTTPException

IST = timezone(timedelta(hours=5, minutes=30))


def now() -> datetime:
    return datetime.now(timezone.utc)


def d2dt(d: date | None) -> datetime | None:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc) if d else None


def dt2d(dt: datetime | None) -> date | None:
    return dt.date() if dt else None


def iso(d) -> str | None:
    return d.isoformat() if d else None


def today_ist() -> date:
    return datetime.now(IST).date()


def oid(v) -> ObjectId:
    try:
        return ObjectId(str(v))
    except Exception:
        raise HTTPException(404, "Not found")


def sid(v) -> str | None:
    return str(v) if v is not None else None
