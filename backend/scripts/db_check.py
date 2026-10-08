"""Check the SQLite database and what is stored.   python -m scripts.db_check  [--memory]

Opens the database file, lists every table with its document count and field rules, writes one encrypted test
document, reads it back, decrypts it, deletes it, checks that a duplicate login is refused, and prints PASS or FAIL.
Secrets are never printed."""
import asyncio
import sys

from app.core.config import settings
from app.core.db import RULES, DuplicateKeyError, get_db, init_db, memory_db, set_db
from app.core.security.crypto import dec, enc

SECRET = "db-check-secret-value"


async def main() -> int:
    ok = True
    if "--memory" in sys.argv:  # offline self-test of this script
        set_db(memory_db())
    await init_db()
    db = get_db()
    try:
        await db.command("ping")
    except Exception as e:
        print(f"FAIL cannot open the database: {type(e).__name__}")
        return 1
    print(f"SQLite database: {db.path}  (SQLITE_PATH={settings.sqlite_path})")
    names = await db.list_collection_names()
    print(f"\n{'table':22} {'docs':>6}  rules")
    for n in names:
        r = RULES.get(n)
        rule = "" if not r else ", ".join(filter(None, [
            f"{len(r.required)} required" if r.required else "", f"{len(r.enums)} enums" if r.enums else "",
            f"{len(r.uniques)} unique" if r.uniques else ""]))
        print(f"{n:22} {await db[n].count_documents({}):>6}  {rule}")
    missing = [n for n in RULES if n not in names]
    if missing:
        print(f"\nFAIL tables missing: {', '.join(missing)}")
        ok = False
    coll = db["_db_check"]
    try:
        doc_id = (await coll.insert_one({"secret": enc(SECRET)})).inserted_id
        stored = (await coll.find_one({"_id": doc_id}))["secret"]
        plain = dec(stored)
        await coll.delete_one({"_id": doc_id})
        left = await coll.count_documents({})
        await coll.drop()
        good = stored.startswith("v1:") and SECRET not in stored and plain == SECRET and left == 0
        print(f"\nencrypted round trip: stored as '{stored[:14]}...', decrypts to the original, deleted -> "
              f"{'ok' if good else 'WRONG'}")
        ok = ok and good
    except Exception as e:
        print(f"\nFAIL encrypted round trip: {type(e).__name__}")
        ok = False
    probe = "__db_check_unique__"
    try:
        u = {"login": probe, "password_hash": "x", "role": "patient", "language": "en", "created_at": 0}
        await db.users.insert_one(dict(u))
        try:
            await db.users.insert_one(dict(u))
            print("unique login: a duplicate was accepted -> WRONG")
            ok = False
        except DuplicateKeyError:
            print("unique login: duplicate refused -> ok")
    finally:
        await db.users.delete_many({"login": probe})
    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
