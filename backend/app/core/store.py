"""SQLite document store (Python stdlib `sqlite3`, no server).

Every collection is one SQLite table `c_<name>(id TEXT PRIMARY KEY, doc TEXT)` holding the document as JSON.
The async API is the small subset of Motor the application uses (find, find_one, insert_one, update_one,
find_one_and_update, count_documents, distinct ...), so the business code reads the same as before, but the
data lives in one file on disk (`SQLITE_PATH`, default `backend/data/discharge.db`).

Guarantees:
- Every write runs inside `BEGIN IMMEDIATE ... COMMIT`, so a conditional update ("only if status is Pending")
  is atomic, also across several API processes sharing the same file.
- Unique indexes and the field rules (required fields, enums, number ranges) are enforced on every write.
- Datetimes are stored as UTC and always come back timezone-aware. Bytes are stored base64.
"""
from __future__ import annotations

import base64
import copy
import json
import os
import re
import sqlite3
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.core.ids import ObjectId


class StoreError(Exception):
    pass


class DuplicateKeyError(StoreError):
    pass


class WriteError(StoreError):
    """A document broke a field rule (missing required field, value outside its enum)."""


# ---------------------------------------------------------------- encoding

def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _default(o):
    if isinstance(o, datetime):
        return {"$date": _utc(o).isoformat()}
    if isinstance(o, date):
        return {"$day": o.isoformat()}
    if isinstance(o, (bytes, bytearray, memoryview)):
        return {"$bin": base64.b64encode(bytes(o)).decode()}
    if isinstance(o, (set, tuple)):
        return list(o)
    raise TypeError(f"cannot store {type(o).__name__}")


def _hook(d: dict):
    if len(d) == 1:
        if "$date" in d:
            return datetime.fromisoformat(d["$date"])
        if "$day" in d:
            return date.fromisoformat(d["$day"])
        if "$bin" in d:
            return base64.b64decode(d["$bin"])
    return d


def dumps(doc: dict) -> str:
    return json.dumps(doc, default=_default, ensure_ascii=False, separators=(",", ":"))


def loads(s: str) -> dict:
    return json.loads(s, object_hook=_hook)


def _norm(v):
    """Comparable form of a value (naive datetimes are UTC, tuples are lists)."""
    if isinstance(v, datetime):
        return _utc(v)
    if isinstance(v, tuple):
        return list(v)
    return v


# ---------------------------------------------------------------- matching

_MISSING = object()


def _resolve(doc: Any, path: str) -> list:
    """All values a dotted path reaches. Lists are walked like Mongo does ("ancestors.name", "notices.0")."""
    vals = [doc]
    for part in path.split("."):
        nxt = []
        for v in vals:
            if isinstance(v, dict):
                if part in v:
                    nxt.append(v[part])
            elif isinstance(v, list):
                if part.isdigit():
                    i = int(part)
                    if i < len(v):
                        nxt.append(v[i])
                else:
                    nxt.extend(e[part] for e in v if isinstance(e, dict) and part in e)
        vals = nxt
    return vals


def _candidates(vals: list) -> list:
    out = []
    for v in vals:
        out.append(v)
        if isinstance(v, list):
            out.extend(v)
    return out


def _eq(a, b) -> bool:
    a, b = _norm(a), _norm(b)
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    try:
        return a == b
    except TypeError:
        return False


def _type_rank(v) -> int:
    if v is None:
        return 1
    if isinstance(v, bool):
        return 8
    if isinstance(v, (int, float)):
        return 2
    if isinstance(v, str):
        return 3
    if isinstance(v, dict):
        return 4
    if isinstance(v, list):
        return 5
    if isinstance(v, (bytes, bytearray)):
        return 6
    if isinstance(v, datetime):
        return 9
    if isinstance(v, date):
        return 10
    return 11


def _cmp(a, b, op: str) -> bool:
    a, b = _norm(a), _norm(b)
    if a is None or b is None or _type_rank(a) != _type_rank(b):
        return False
    try:
        return {"$lt": a < b, "$lte": a <= b, "$gt": a > b, "$gte": a >= b}[op]
    except TypeError:
        return False


_TYPES = {"string": str, "int": int, "long": int, "double": float, "bool": bool, "object": dict, "array": list,
          "null": type(None), "date": datetime}


def _match_field(doc, path: str, cond) -> bool:
    vals = _resolve(doc, path)
    cands = _candidates(vals)
    exists = bool(vals)
    if isinstance(cond, dict) and cond and all(k.startswith("$") for k in cond):
        for op, arg in cond.items():
            if op == "$eq":
                ok = _match_field(doc, path, arg)
            elif op == "$ne":
                ok = not _match_field(doc, path, arg)
            elif op == "$in":
                ok = any(_match_field(doc, path, a) for a in arg)
            elif op == "$nin":
                ok = not any(_match_field(doc, path, a) for a in arg)
            elif op in ("$lt", "$lte", "$gt", "$gte"):
                ok = any(_cmp(c, arg, op) for c in cands)
            elif op == "$exists":
                ok = exists == bool(arg)
            elif op == "$type":
                want = arg if isinstance(arg, list) else [arg]
                ok = any(isinstance(c, _TYPES.get(t, object)) and not (t in ("int", "long") and isinstance(c, bool))
                         for c in cands for t in want)
            elif op == "$size":
                ok = any(isinstance(v, list) and len(v) == arg for v in vals)
            elif op == "$all":
                ok = all(_match_field(doc, path, a) for a in arg)
            elif op == "$regex":
                rx = re.compile(arg, re.I if "i" in cond.get("$options", "") else 0)
                ok = any(isinstance(c, str) and rx.search(c) for c in cands)
            elif op == "$options":
                ok = True
            elif op == "$not":
                ok = not _match_field(doc, path, arg)
            elif op == "$elemMatch":
                ok = any(isinstance(v, list) and any(matches(e, arg) for e in v if isinstance(e, dict)) for v in vals)
            else:
                raise StoreError(f"unsupported query operator {op}")
            if not ok:
                return False
        return True
    if cond is None:
        return not exists or any(c is None for c in cands)
    return any(_eq(c, cond) for c in cands)


def matches(doc: dict, flt: dict | None) -> bool:
    """True when `doc` satisfies the Mongo-style filter `flt`."""
    for k, cond in (flt or {}).items():
        if k == "$and":
            if not all(matches(doc, f) for f in cond):
                return False
        elif k == "$or":
            if not any(matches(doc, f) for f in cond):
                return False
        elif k == "$nor":
            if any(matches(doc, f) for f in cond):
                return False
        elif not _match_field(doc, k, cond):
            return False
    return True


# ---------------------------------------------------------------- updates

def _set_path(doc: dict, path: str, value) -> None:
    parts = path.split(".")
    cur = doc
    for p in parts[:-1]:
        if isinstance(cur, list) and p.isdigit():
            cur = cur[int(p)]
            continue
        if not isinstance(cur.get(p), (dict, list)):
            cur[p] = {}
        cur = cur[p]
    last = parts[-1]
    if isinstance(cur, list) and last.isdigit():
        cur[int(last)] = value
    else:
        cur[last] = value


def _get_path(doc: dict, path: str, default=_MISSING):
    cur = doc
    for p in path.split("."):
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        elif isinstance(cur, list) and p.isdigit() and int(p) < len(cur):
            cur = cur[int(p)]
        else:
            return default
    return cur


def _unset_path(doc: dict, path: str) -> None:
    parts = path.split(".")
    cur = doc
    for p in parts[:-1]:
        cur = cur.get(p) if isinstance(cur, dict) else None
        if cur is None:
            return
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def apply_update(doc: dict, update: dict, inserting: bool = False) -> dict:
    """Returns a new document with the update operators applied. A plain dict (no operators) replaces."""
    if not any(k.startswith("$") for k in update):
        new = copy.deepcopy(update)
        if "_id" in doc:
            new["_id"] = doc["_id"]
        return new
    new = copy.deepcopy(doc)
    for op, fields in update.items():
        if op == "$setOnInsert":
            if not inserting:
                continue
            op = "$set"
        for path, val in fields.items():
            if op == "$set":
                _set_path(new, path, copy.deepcopy(val))
            elif op == "$unset":
                _unset_path(new, path)
            elif op == "$inc":
                cur = _get_path(new, path, 0)
                _set_path(new, path, (cur or 0) + val)
            elif op in ("$push", "$addToSet"):
                cur = _get_path(new, path, None)
                arr = list(cur) if isinstance(cur, list) else []
                items = val["$each"] if isinstance(val, dict) and "$each" in val else [val]
                for it in items:
                    if op == "$push" or not any(_eq(it, x) for x in arr):
                        arr.append(copy.deepcopy(it))
                if isinstance(val, dict) and "$slice" in val:
                    s = val["$slice"]
                    arr = arr[s:] if s < 0 else arr[:s]
                _set_path(new, path, arr)
            elif op == "$pull":
                cur = _get_path(new, path, None)
                if isinstance(cur, list):
                    keep = [x for x in cur if not (matches(x, val) if isinstance(val, dict) and isinstance(x, dict)
                                                   else _eq(x, val))]
                    _set_path(new, path, keep)
            elif op == "$min":
                cur = _get_path(new, path, _MISSING)
                if cur is _MISSING or _cmp(val, cur, "$lt"):
                    _set_path(new, path, val)
            elif op == "$max":
                cur = _get_path(new, path, _MISSING)
                if cur is _MISSING or _cmp(val, cur, "$gt"):
                    _set_path(new, path, val)
            else:
                raise StoreError(f"unsupported update operator {op}")
    return new


def _seed_from_filter(flt: dict) -> dict:
    """Equality fields of a filter become the starting document of an upsert."""
    doc = {}
    for k, v in (flt or {}).items():
        if k.startswith("$") or (isinstance(v, dict) and any(x.startswith("$") for x in v)):
            continue
        _set_path(doc, k, copy.deepcopy(v))
    return doc


# ---------------------------------------------------------------- projection and sort

def _pick(v, parts: list[str]):
    """The part of `v` a dotted inclusion path keeps. Lists are mapped element by element, like Mongo."""
    if not parts:
        return copy.deepcopy(v)
    if isinstance(v, list):
        return [x for x in (_pick(e, parts) for e in v if isinstance(e, dict)) if x is not _MISSING]
    if isinstance(v, dict) and parts[0] in v:
        sub = _pick(v[parts[0]], parts[1:])
        return _MISSING if sub is _MISSING else {parts[0]: sub}
    return _MISSING


def _merge(into: dict, part) -> None:
    if not isinstance(part, dict):
        return
    for k, v in part.items():
        if isinstance(v, dict) and isinstance(into.get(k), dict):
            _merge(into[k], v)
        elif isinstance(v, list) and isinstance(into.get(k), list) and len(v) == len(into[k]):
            for a, b in zip(into[k], v):
                if isinstance(a, dict):
                    _merge(a, b)
        else:
            into[k] = v


def _project(doc: dict, projection) -> dict:
    if not projection:
        return doc
    if isinstance(projection, (list, tuple)):
        projection = {k: 1 for k in projection}
    include = {k for k, v in projection.items() if v and k != "_id"}
    if include:
        out = {}
        if projection.get("_id", 1):
            out["_id"] = doc.get("_id")
        for k in include:
            _merge(out, _pick(doc, k.split(".")))
        return out
    out = copy.deepcopy(doc)
    for k, v in projection.items():
        if not v:
            _unset_path(out, k)
    return out


def _sort_key(v):
    v = _norm(v)
    if v is _MISSING:
        v = None
    rank = _type_rank(v)
    if isinstance(v, (dict, list)):
        v = dumps(v) if isinstance(v, dict) else dumps({"a": v})
    return rank, v if v is not None else 0


def sort_docs(docs: list[dict], spec) -> list[dict]:
    if not spec:
        return docs
    if isinstance(spec, str):
        spec = [(spec, 1)]
    for key, direction in reversed(list(spec)):
        docs.sort(key=lambda d: _sort_key(_get_path(d, key, None)), reverse=direction < 0)
    return docs


# ---------------------------------------------------------------- results

class InsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id
        self.acknowledged = True


class InsertManyResult:
    def __init__(self, ids):
        self.inserted_ids = ids
        self.acknowledged = True


class UpdateResult:
    def __init__(self, matched: int, modified: int, upserted_id=None):
        self.matched_count = matched
        self.modified_count = modified
        self.upserted_id = upserted_id
        self.acknowledged = True


class DeleteResult:
    def __init__(self, n: int):
        self.deleted_count = n
        self.acknowledged = True


# ---------------------------------------------------------------- rules (validators + unique indexes)

class Rules:
    """Field rules and unique indexes for one collection."""

    def __init__(self, required=(), enums=None, numbers=None, uniques=()):
        self.required = list(required)
        self.enums = enums or {}        # field -> allowed values
        self.numbers = numbers or {}    # field -> (min, max)  values must be numbers
        self.uniques = list(uniques)    # [(fields tuple, partial filter or None)]

    def check(self, doc: dict, name: str) -> None:
        for f in self.required:
            if f not in doc:
                raise WriteError(f"{name}: missing required field {f}")
        for f, allowed in self.enums.items():
            if f in doc and not any(_eq(doc[f], a) for a in allowed):
                raise WriteError(f"{name}: {f}={doc[f]!r} is not allowed")
        for f, (lo, hi) in self.numbers.items():
            if f in doc and doc[f] is not None:
                v = doc[f]
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise WriteError(f"{name}: {f} must be a number")
                if (lo is not None and v < lo) or (hi is not None and v > hi):
                    raise WriteError(f"{name}: {f} out of range")


# ---------------------------------------------------------------- database

def _table(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise StoreError(f"bad collection name {name!r}")
    return f'"c_{name}"'


class Database:
    """One SQLite file (or ':memory:'). Thread-safe; writes are serialized with BEGIN IMMEDIATE."""

    def __init__(self, path: str = ":memory:", rules: dict[str, Rules] | None = None):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=30)
        self._conn.execute("PRAGMA journal_mode=WAL" if path != ":memory:" else "PRAGMA journal_mode=MEMORY")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=30000")
        self._lock = threading.RLock()
        self.rules: dict[str, Rules] = rules or {}
        self._known: set[str] = set()

    # -- plumbing
    def _ensure(self, name: str) -> None:
        if name not in self._known:
            self._conn.execute(f"CREATE TABLE IF NOT EXISTS {_table(name)} (id TEXT PRIMARY KEY, doc TEXT NOT NULL)")
            self._known.add(name)

    def _all(self, name: str) -> list[dict]:
        self._ensure(name)
        return [loads(r[0]) for r in self._conn.execute(f"SELECT doc FROM {_table(name)} ORDER BY rowid")]

    def _candidates(self, name: str, flt: dict | None) -> list[dict]:
        """Rows that may match. `_id` equality is a primary key lookup, everything else a scan."""
        self._ensure(name)
        idv = (flt or {}).get("_id", _MISSING)
        if idv is not _MISSING and not isinstance(idv, dict) and idv is not None:
            row = self._conn.execute(f"SELECT doc FROM {_table(name)} WHERE id=?", (str(idv),)).fetchone()
            docs = [loads(row[0])] if row else []
        else:
            docs = self._all(name)
        return [d for d in docs if matches(d, flt)]

    def _check_unique(self, name: str, doc: dict, others: Iterable[dict]) -> None:
        r = self.rules.get(name)
        if not r:
            return
        for fields, partial in r.uniques:
            if partial and not matches(doc, partial):
                continue
            key = [_norm(_get_path(doc, f, None)) for f in fields]
            for o in others:
                if o.get("_id") == doc.get("_id"):
                    continue
                if partial and not matches(o, partial):
                    continue
                if [_norm(_get_path(o, f, None)) for f in fields] == key:
                    raise DuplicateKeyError(f"{name}: duplicate key {dict(zip(fields, key))}")

    def _validate(self, name: str, doc: dict, siblings: list[dict] | None = None) -> None:
        r = self.rules.get(name)
        if r:
            r.check(doc, name)
            if r.uniques:
                self._check_unique(name, doc, siblings if siblings is not None else self._all(name))

    def _write(self, fn):
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                out = fn()
            except BaseException:
                self._conn.execute("ROLLBACK")
                self._known.clear()  # a CREATE TABLE inside the rolled-back transaction is gone too
                raise
            self._conn.execute("COMMIT")
            return out

    def _read(self, fn):
        with self._lock:
            return fn()

    def _put(self, name: str, doc: dict) -> None:
        self._conn.execute(f"INSERT OR REPLACE INTO {_table(name)} (id, doc) VALUES (?, ?)", (str(doc["_id"]), dumps(doc)))

    # -- public, Motor-like
    def __getattr__(self, name: str) -> "Collection":
        if name.startswith("_"):
            raise AttributeError(name)
        return Collection(self, name)

    def __getitem__(self, name: str) -> "Collection":
        return Collection(self, name)

    async def command(self, cmd, *args, **kw) -> dict:
        if cmd == "ping":
            self._read(lambda: self._conn.execute("SELECT 1").fetchone())
        return {"ok": 1}

    async def list_collection_names(self) -> list[str]:
        rows = self._read(lambda: self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'c\\_%' ESCAPE '\\'").fetchall())
        return sorted(r[0][2:] for r in rows)

    async def drop_collection(self, name: str) -> None:
        def run():
            self._conn.execute(f"DROP TABLE IF EXISTS {_table(name)}")
            self._known.discard(name)
        self._write(run)

    async def create_collection(self, name: str, **kw) -> "Collection":
        self._write(lambda: self._ensure(name))
        return Collection(self, name)

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class Cursor:
    def __init__(self, coll: "Collection", flt, projection):
        self._c, self._flt, self._proj = coll, flt, projection
        self._sort, self._limit, self._skip = None, 0, 0

    def sort(self, key, direction: int = 1):
        self._sort = key if isinstance(key, list) else [(key, direction)]
        return self

    def limit(self, n: int):
        self._limit = n
        return self

    def skip(self, n: int):
        self._skip = n
        return self

    def _run(self) -> list[dict]:
        db, name = self._c._db, self._c.name
        docs = db._read(lambda: db._candidates(name, self._flt))
        docs = sort_docs(docs, self._sort)
        if self._skip:
            docs = docs[self._skip:]
        if self._limit:
            docs = docs[:self._limit]
        return [_project(d, self._proj) for d in docs]

    def __aiter__(self):
        self._it = iter(self._run())
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration

    async def to_list(self, length: int | None = None) -> list[dict]:
        docs = self._run()
        return docs[:length] if length else docs


class Collection:
    def __init__(self, db: Database, name: str):
        self._db, self.name = db, name

    # reads
    def find(self, filter: dict | None = None, projection=None, sort=None, limit: int = 0) -> Cursor:
        cur = Cursor(self, filter or {}, projection)
        if sort:
            cur.sort(sort)
        if limit:
            cur.limit(limit)
        return cur

    async def find_one(self, filter: dict | None = None, projection=None, sort=None):
        docs = await self.find(filter, projection, sort=sort, limit=1).to_list(1)
        return docs[0] if docs else None

    async def count_documents(self, filter: dict | None = None) -> int:
        return len(self._db._read(lambda: self._db._candidates(self.name, filter or {})))

    async def distinct(self, key: str, filter: dict | None = None) -> list:
        out = []
        for d in self._db._read(lambda: self._db._candidates(self.name, filter or {})):
            for v in _candidates(_resolve(d, key)):
                if not isinstance(v, list) and not any(_eq(v, o) for o in out):
                    out.append(v)
        return out

    # writes
    async def insert_one(self, doc: dict) -> InsertOneResult:
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        new = copy.deepcopy(doc)

        def run():
            self._db._ensure(self.name)
            if self._db._conn.execute(f"SELECT 1 FROM {_table(self.name)} WHERE id=?", (str(new["_id"]),)).fetchone():
                raise DuplicateKeyError(f"{self.name}: duplicate _id")
            self._db._validate(self.name, new)
            self._db._put(self.name, new)
        self._db._write(run)
        return InsertOneResult(doc["_id"])

    async def insert_many(self, docs: list[dict]) -> InsertManyResult:
        for d in docs:
            d.setdefault("_id", ObjectId())
        news = [copy.deepcopy(d) for d in docs]

        def run():
            self._db._ensure(self.name)
            existing = self._db._all(self.name)
            ids = {str(e["_id"]) for e in existing}
            for n in news:
                if str(n["_id"]) in ids:
                    raise DuplicateKeyError(f"{self.name}: duplicate _id")
                self._db._validate(self.name, n, existing)
                self._db._put(self.name, n)
                existing.append(n)
                ids.add(str(n["_id"]))
        self._db._write(run)
        return InsertManyResult([d["_id"] for d in docs])

    def _update(self, flt, update, many: bool, upsert: bool, sort=None):
        """Returns (matched, modified, upserted_id, before, after) for the first document."""
        def run():
            docs = sort_docs(self._db._candidates(self.name, flt), sort)
            if not docs:
                if not upsert:
                    return 0, 0, None, None, None
                base = _seed_from_filter(flt)
                new = apply_update(base, update, inserting=True)
                if not any(k.startswith("$") for k in update):  # replace_one upsert keeps the filter's _id
                    new = {**{k: v for k, v in base.items() if k == "_id"}, **new}
                new.setdefault("_id", ObjectId())
                self._db._validate(self.name, new)
                self._db._put(self.name, new)
                return 0, 0, new["_id"], None, new
            modified, first = 0, None
            siblings = self._db._all(self.name) if (self._db.rules.get(self.name) or Rules()).uniques else None
            for d in (docs if many else docs[:1]):
                new = apply_update(d, update)
                if dumps(new) != dumps(d):
                    self._db._validate(self.name, new, siblings)
                    self._db._put(self.name, new)
                    modified += 1
                    if siblings is not None:
                        siblings = [new if s.get("_id") == new["_id"] else s for s in siblings]
                if first is None:
                    first = (d, new)
            return len(docs) if many else 1, modified, None, first[0], first[1]
        return self._db._write(run)

    async def update_one(self, filter: dict, update: dict, upsert: bool = False) -> UpdateResult:
        m, n, up, _, _ = self._update(filter, update, False, upsert)
        return UpdateResult(m, n, up)

    async def update_many(self, filter: dict, update: dict, upsert: bool = False) -> UpdateResult:
        m, n, up, _, _ = self._update(filter, update, True, upsert)
        return UpdateResult(m, n, up)

    async def replace_one(self, filter: dict, replacement: dict, upsert: bool = False) -> UpdateResult:
        if any(k.startswith("$") for k in replacement):
            raise StoreError("replacement must not contain operators")
        m, n, up, _, _ = self._update(filter, replacement, False, upsert)
        return UpdateResult(m, n, up)

    async def find_one_and_update(self, filter: dict, update: dict, projection=None, sort=None,
                                  upsert: bool = False, return_document: bool = False):
        """return_document=True gives the document after the update (pymongo's ReturnDocument.AFTER)."""
        _, _, _, before, after = self._update(filter, update, False, upsert, sort)
        doc = after if return_document else before
        return _project(doc, projection) if doc is not None else None

    async def delete_one(self, filter: dict) -> DeleteResult:
        return self._delete(filter, False)

    async def delete_many(self, filter: dict | None = None) -> DeleteResult:
        return self._delete(filter or {}, True)

    def _delete(self, flt, many: bool) -> DeleteResult:
        def run():
            docs = self._db._candidates(self.name, flt)
            docs = docs if many else docs[:1]
            for d in docs:
                self._db._conn.execute(f"DELETE FROM {_table(self.name)} WHERE id=?", (str(d["_id"]),))
            return len(docs)
        return DeleteResult(self._db._write(run))

    async def create_indexes(self, *a, **k) -> list:
        return []

    async def drop(self) -> None:
        await self._db.drop_collection(self.name)


def open_database(path: str, rules: dict[str, Rules] | None = None) -> Database:
    if path != ":memory:" and not os.path.isabs(path):
        path = str(Path(__file__).resolve().parents[2] / path)
    return Database(path, rules)
