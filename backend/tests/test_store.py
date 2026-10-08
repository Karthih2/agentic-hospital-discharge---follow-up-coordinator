"""The SQLite store: persistence, rules, atomic conditional writes, Mongo-style queries."""
import asyncio
import threading
from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.db import RULES
from app.core.ids import ObjectId
from app.core.store import Database, DuplicateKeyError, WriteError

run = asyncio.run


def test_file_persists_across_connections(tmp_path):
    path = str(tmp_path / "x.db")
    a = Database(path, RULES)
    ts = datetime(2026, 10, 8, 9, 30, tzinfo=timezone.utc)
    oid = run(a.tasks.insert_one({"patient_id": "p", "type": "test", "status": "Pending", "source_line": "v1:x",
                                  "created_at": ts, "due_date": ts, "blob": b"\x00\x01", "confidence": 0.9})).inserted_id
    a.close()
    b = Database(path, RULES)
    t = run(b.tasks.find_one({"_id": oid}))
    assert t["due_date"] == ts and t["due_date"].tzinfo is not None and t["blob"] == b"\x00\x01"
    assert isinstance(t["_id"], str) and ObjectId.is_valid(t["_id"])


def test_rules_and_unique_keys():
    db = Database(":memory:", RULES)
    with pytest.raises(WriteError):
        run(db.tasks.insert_one({"patient_id": "p", "type": "nope", "status": "Pending", "source_line": "", "created_at": 1}))
    with pytest.raises(WriteError):
        run(db.tasks.insert_one({"patient_id": "p", "type": "test", "status": "Pending", "source_line": "",
                                 "created_at": 1, "confidence": 3}))
    u = {"login": "a", "password_hash": "h", "role": "patient", "language": "en", "created_at": 1}
    run(db.users.insert_one(dict(u)))
    with pytest.raises(DuplicateKeyError):
        run(db.users.insert_one(dict(u)))
    # partial unique index: two users without a patient code are fine
    run(db.users.insert_one({**u, "login": "b", "role": "doctor"}))
    run(db.users.insert_one({**u, "login": "c", "role": "doctor"}))


def test_queries_updates_projection_sort():
    db = Database(":memory:")
    c = db.things
    now = datetime.now(timezone.utc)
    run(c.insert_many([{"n": i, "tags": ["a", "b"] if i % 2 else ["c"], "when": now - timedelta(days=i),
                        "sub": {"k": i}, "items": [{"code": f"x{i}", "v": i}]} for i in range(5)]))
    assert run(c.count_documents({"tags": "a"})) == 2
    assert run(c.count_documents({"n": {"$in": [1, 2, 9]}})) == 2
    assert run(c.count_documents({"when": {"$gte": now - timedelta(days=2, hours=1)}})) == 3
    assert run(c.count_documents({"missing": None})) == 5 and run(c.count_documents({"missing": {"$exists": True}})) == 0
    assert run(c.count_documents({"$or": [{"n": 0}, {"sub.k": 4}]})) == 2
    assert run(c.count_documents({"items.0": {"$exists": True}})) == 5
    docs = run(c.find({}, {"items.code": 1}).sort("n", -1).limit(2).to_list())
    assert [d["items"] for d in docs] == [[{"code": "x4"}], [{"code": "x3"}]]
    r = run(c.update_one({"n": 1, "sub.k": 1}, {"$set": {"sub.k": 10}, "$push": {"tags": "z"}, "$inc": {"n": 100}}))
    assert r.modified_count == 1
    d = run(c.find_one({"n": 101}))
    assert d["sub"]["k"] == 10 and d["tags"] == ["a", "b", "z"]
    assert run(c.update_one({"n": 101, "sub.k": 1}, {"$set": {"x": 1}})).modified_count == 0  # condition no longer true
    before = run(c.find_one_and_update({"n": 0}, {"$set": {"n": -1}}))
    after = run(c.find_one_and_update({"n": -1}, {"$set": {"n": -2}}, return_document=True))
    assert before["n"] == 0 and after["n"] == -2
    r = run(c.update_one({"key": "k1"}, {"$set": {"v": 1}, "$setOnInsert": {"made": True}}, upsert=True))
    assert r.upserted_id and run(c.find_one({"key": "k1"}))["made"] is True
    assert sorted(run(c.distinct("tags"))) == ["a", "b", "c", "z"]
    assert run(c.delete_many({"n": {"$lt": 0}})).deleted_count == 1


def test_conditional_update_is_atomic_across_connections(tmp_path):
    """Two connections race to claim the same task; exactly one wins (BEGIN IMMEDIATE)."""
    path = str(tmp_path / "race.db")
    a, b = Database(path), Database(path)
    tid = run(a.jobs.insert_one({"state": "open"})).inserted_id
    wins = []

    def claim(db, who):
        r = asyncio.run(db.jobs.update_one({"_id": tid, "state": "open"}, {"$set": {"state": who}}))
        wins.append(r.modified_count)
    ts = [threading.Thread(target=claim, args=(d, w)) for d, w in ((a, "a"), (b, "b"), (a, "c"), (b, "d"))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sum(wins) == 1


def test_dates_round_trip():
    db = Database(":memory:")
    run(db.x.insert_one({"d": date(2026, 1, 2), "naive": datetime(2026, 1, 2, 3, 4)}))
    d = run(db.x.find_one({}))
    assert d["d"] == date(2026, 1, 2) and d["naive"] == datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc)
