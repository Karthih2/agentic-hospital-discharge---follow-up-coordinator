"""Check the MongoDB connection and what is stored.   python -m scripts.db_check

Connects, lists every collection with its validator and indexes, prints document counts, writes one encrypted
test document, reads it back, decrypts it, deletes it, and prints PASS or FAIL. Secrets are never printed."""
import asyncio
import sys

from app.core.config import settings
from app.core.db import VALIDATORS, get_db, set_db
from app.core.security.crypto import dec, enc

SECRET = "db-check-secret-value"


async def main() -> int:
    ok = True
    if "--memory" in sys.argv:  # offline self-test of this script; validators are not enforced by the mock
        from mongomock_motor import AsyncMongoMockClient
        set_db(AsyncMongoMockClient(tz_aware=True)["check"])
        for n in VALIDATORS:
            await get_db()[n].insert_one({"_check": True})
            await get_db()[n].delete_many({})
    db = get_db()
    try:
        await db.command("ping")
    except Exception as e:
        print(f"FAIL cannot connect: {type(e).__name__}")
        return 1
    print(f"connected to database '{settings.mongo_db}'")
    names = sorted(await db.list_collection_names())
    print(f"\n{'collection':22} {'docs':>6}  validator  indexes")
    for n in names:
        try:
            info = (await db.list_collections(filter={"name": n}).to_list(1))[0]
            has_v = bool(info.get("options", {}).get("validator"))
            idx = [i["name"] for i in await db[n].list_indexes().to_list(50)]
        except Exception:
            has_v, idx = False, []
        print(f"{n:22} {await db[n].count_documents({}):>6}  {'yes' if has_v else 'no ':9}  {', '.join(idx)}")
    missing = [n for n in VALIDATORS if n not in names]
    if missing and "--memory" not in sys.argv:
        print(f"\nFAIL collections missing (run  python -m scripts.seed --reset --yes): {', '.join(missing)}")
        ok = False
    # encrypted write -> read -> decrypt -> delete
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
    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
