"""Append-only audit log. Never logs clinical text, tokens, passwords or phone numbers.

Bucket pattern: one document per actor per day holds up to BUCKET_MAX events, then a new bucket opens.
Inside a bucket every event carries the hash of the one before it, so an edited event breaks the chain."""
import hashlib
import json

from pymongo.errors import DuplicateKeyError

from app.core.constants import SCHEMA_VERSION
from app.core.db import get_db
from app.core.util import now

BUCKET_MAX = 200


def _canon(e: dict) -> str:
    ts = e["ts"].replace(tzinfo=None).isoformat()
    body = {k: (str(e.get(k)) if e.get(k) is not None else None)
            for k in ("actor_id", "on_behalf_of", "action", "target_type", "target_id", "result", "ip", "prev_hash")}
    return json.dumps({**body, "meta": e.get("meta"), "ts": ts}, sort_keys=True)


def _hash(e: dict) -> str:
    return hashlib.sha256(_canon(e).encode()).hexdigest()


async def audit(actor_id, action, target_type=None, target_id=None, result="ok", on_behalf_of=None, ip=None, meta=None):
    coll = get_db().audit_log
    ts = now()
    ev = {"actor_id": actor_id, "on_behalf_of": on_behalf_of, "action": action, "target_type": target_type,
          "target_id": target_id, "result": result, "ip": ip, "meta": meta,
          "ts": ts.replace(microsecond=ts.microsecond // 1000 * 1000)}  # Mongo keeps milliseconds
    key, day = str(actor_id), ts.strftime("%Y-%m-%d")
    for _ in range(6):  # optimistic: the push only lands if nobody else appended in between
        b = await coll.find_one({"actor_key": key, "day": day}, sort=[("seq", -1)])
        if b is None or b["count"] >= BUCKET_MAX:
            seq = (b["seq"] + 1) if b else 0
            ev["prev_hash"] = ""
            try:
                await coll.insert_one({"actor_key": key, "actor_id": actor_id, "day": day, "seq": seq, "count": 1,
                                       "events": [ev], "schema_version": SCHEMA_VERSION})
                return
            except DuplicateKeyError:
                continue
        ev["prev_hash"] = _hash(b["events"][-1])
        r = await coll.update_one({"_id": b["_id"], "count": b["count"]},
                                  {"$push": {"events": ev}, "$inc": {"count": 1}})
        if r.modified_count:
            return
    raise RuntimeError("audit write contention")


async def events(match: dict | None = None, limit: int = 200) -> list[dict]:
    """Newest first. `match` filters on event fields without the 'events.' prefix, e.g. {"action": "login"}."""
    pipe = [{"$unwind": "$events"}, {"$replaceRoot": {"newRoot": "$events"}}]
    if match:
        pipe.append({"$match": match})
    pipe += [{"$sort": {"ts": -1}}, {"$limit": limit}]
    return [e async for e in get_db().audit_log.aggregate(pipe)]


async def verify_chain() -> bool:
    async for b in get_db().audit_log.find({}):
        prev = None
        for e in b["events"]:
            if prev is not None and e["prev_hash"] != _hash(prev):
                return False
            prev = e
    return True
