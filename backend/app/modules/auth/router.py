from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.core.db import get_db
from app.models.schemas import LanguageIn, LoginIn, RegisterIn
from app.core.security import auth, ratelimit
from app.core.security.access import Principal, client_ip, current_user, require_role
from app.core.security.crypto import dec
from app.modules.auth import service as accounts
from app.core.audit import audit
from app.core.util import now, sid

router = APIRouter(tags=["auth"])


@router.post("/auth/register", status_code=201)
async def register(body: RegisterIn, request: Request, response: Response):
    """Self sign-up creates a PATIENT account. Family accounts are added by the patient; doctor and
    management accounts are provisioned by an administrator (seed script)."""
    ratelimit.limit("register", client_ip(request), 10, 3600)
    u = await accounts.create_user(body.name, body.login, body.password, body.role, body.language)
    await audit(u["_id"], "register", "user", u["_id"], ip=client_ip(request))
    csrf = auth.set_cookies(response, auth.make_access(str(u["_id"]), body.role), await auth.new_refresh(u["_id"]))
    return {"id": sid(u["_id"]), "role": body.role, "language": u["language"], "csrf_token": csrf}


@router.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response):
    ip = client_ip(request)
    ratelimit.limit("login_ip", ip, 20, 900)
    db = get_db()
    user = await db.users.find_one({"login": body.login.strip().lower()})
    if user and user.get("locked_until") and user["locked_until"].replace(tzinfo=None) > now().replace(tzinfo=None):
        await audit(user["_id"], "login", "user", user["_id"], "denied", ip=ip)
        raise HTTPException(429, "Too many attempts. Please try again later.")
    if not user:
        auth.verify_password(auth.DUMMY_HASH, body.password)  # same work for unknown logins
    if not user or not user.get("is_active") or not user.get("can_login", True)             or not auth.verify_password(user["password_hash"], body.password):
        if user:
            after = await db.users.find_one_and_update({"_id": user["_id"]}, {"$inc": {"failed_logins": 1}},
                                                       return_document=True)  # atomic: parallel guesses all count
            if after["failed_logins"] >= auth.MAX_FAILS:
                await db.users.update_one({"_id": user["_id"]}, {"$set": {
                    "locked_until": now() + timedelta(minutes=auth.LOCK_MIN), "failed_logins": 0}})
        await audit(user["_id"] if user else "unknown", "login", "user", user["_id"] if user else None,
                    "denied", ip=ip)
        raise HTTPException(401, "Invalid login or password")
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"failed_logins": 0, "locked_until": None}})
    await audit(user["_id"], "login", "user", user["_id"], ip=ip)
    csrf = auth.set_cookies(response, auth.make_access(str(user["_id"]), user["role"]),
                            await auth.new_refresh(user["_id"]))
    return {"id": sid(user["_id"]), "role": user["role"], "language": user["language"], "csrf_token": csrf}


@router.post("/auth/refresh")
async def refresh(request: Request, response: Response):
    tok = request.cookies.get("refresh_token")
    if not tok:
        raise HTTPException(401, "Not authenticated")
    auth.verify_csrf(request)
    uid, new_tok = await auth.rotate_refresh(tok)
    user = await get_db().users.find_one({"_id": uid, "is_active": True})
    if not user:
        raise HTTPException(401, "Not authenticated")
    csrf = auth.set_cookies(response, auth.make_access(str(uid), user["role"]), new_tok)
    return {"csrf_token": csrf}


@router.post("/auth/logout")
async def logout(request: Request, response: Response):
    """Needs only the refresh cookie, so it still works after the 15-minute access token expired."""
    if tok := request.cookies.get("refresh_token"):
        await auth.revoke_refresh(tok)
    auth.clear_cookies(response)
    return {"ok": True}


@router.get("/me")
async def me(user: Principal = Depends(current_user)):
    db = get_db()
    u = await db.users.find_one({"_id": user.id})
    out = {"id": sid(user.id), "name": dec(u["name"]), "role": user.role, "language": user.language}
    if user.role == "patient":
        out["patient_code"] = u.get("patient_code")
    if user.role in ("patient", "family"):
        out["hubs"] = [sid(m["hub_id"]) async for m in db.hub_members.find({"user_id": user.id})]
    return out


@router.put("/me/language")
async def set_language(body: LanguageIn, user: Principal = Depends(current_user)):
    await get_db().users.update_one({"_id": user.id}, {"$set": {"language": body.language}})
    return {"language": body.language}


@router.delete("/me")
async def delete_account(request: Request, response: Response, user: Principal = Depends(require_role("patient"))):
    """Patient right: delete my account and my data. The audit trail is append-only, so it stays."""
    db = get_db()
    task_ids = [t["_id"] async for t in db.tasks.find({"patient_id": user.id}, {"_id": 1})]
    await db.audio_cache.delete_many({"task_id": {"$in": task_ids}})
    await db.task_revisions.delete_many({"patient_id": user.id})
    for coll in ("tasks", "review_queue", "discharge_summaries", "notifications", "hub_invites"):
        await db[coll].delete_many({"patient_id": user.id})
    await db.patient_stats.delete_one({"_id": user.id})
    await db.consents.delete_many({"$or": [{"patient_id": user.id}, {"grantee_id": user.id}]})
    await db.hub_members.delete_many({"user_id": user.id})
    await db.refresh_tokens.delete_many({"user_id": user.id})
    await db.users.delete_one({"_id": user.id})
    auth.clear_cookies(response)
    await audit(user.id, "delete_account", "user", user.id, ip=client_ip(request))
    return {"ok": True}
