"""Passwords (Argon2id), JWT access tokens (15 min), rotating refresh tokens (7 days), httpOnly cookies, CSRF."""
import hashlib
import secrets
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, Request, Response

from app.core.config import settings
from app.core.db import get_db
from app.core.util import now

_ph = PasswordHasher()  # Argon2id by default
DUMMY_HASH = _ph.hash("not-a-real-password")
MAX_FAILS = 5
LOCK_MIN = 15


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(hashed: str, pw: str) -> bool:
    try:
        return _ph.verify(hashed, pw)
    except (VerifyMismatchError, Exception):
        return False


def make_access(user_id: str, role: str) -> str:
    # user id and role only. No clinical data, names or phone numbers.
    exp = now() + timedelta(minutes=settings.access_ttl_min)
    return jwt.encode({"sub": user_id, "role": role, "typ": "access", "exp": exp}, settings.jwt_secret, "HS256")


def decode_access(token: str) -> dict:
    try:
        p = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Not authenticated")
    if p.get("typ") != "access":
        raise HTTPException(401, "Not authenticated")
    return p


def _h(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


async def new_refresh(user_id) -> str:
    tok = secrets.token_urlsafe(48)
    await get_db().refresh_tokens.insert_one(
        {"user_id": user_id, "token_hash": _h(tok), "revoked": False,
         "expires_at": now() + timedelta(days=settings.refresh_ttl_days)})
    return tok


async def rotate_refresh(tok: str):
    """Returns user_id and a new token. A reused (already revoked) token revokes every token of that user."""
    db = get_db()
    # atomic claim: of two concurrent refreshes with one token only one wins
    rec = await db.refresh_tokens.find_one_and_update({"token_hash": _h(tok), "revoked": False},
                                                      {"$set": {"revoked": True}})
    if not rec:
        seen = await db.refresh_tokens.find_one({"token_hash": _h(tok)})
        if seen:  # reuse of a spent token: assume theft, revoke every token of that user
            await db.refresh_tokens.update_many({"user_id": seen["user_id"]}, {"$set": {"revoked": True}})
        raise HTTPException(401, "Not authenticated")
    if rec["expires_at"].replace(tzinfo=None) < now().replace(tzinfo=None):
        raise HTTPException(401, "Not authenticated")
    return rec["user_id"], await new_refresh(rec["user_id"])


async def revoke_refresh(tok: str) -> None:
    await get_db().refresh_tokens.update_one({"token_hash": _h(tok)}, {"$set": {"revoked": True}})


def set_cookies(resp: Response, access: str, refresh: str) -> str:
    csrf = secrets.token_urlsafe(24)
    kw = {"secure": settings.cookie_secure, "samesite": "strict"}
    resp.set_cookie("access_token", access, httponly=True, max_age=settings.access_ttl_min * 60, path="/", **kw)
    resp.set_cookie("refresh_token", refresh, httponly=True, max_age=settings.refresh_ttl_days * 86400,
                    path="/auth", **kw)
    resp.set_cookie("csrf_token", csrf, httponly=False, max_age=settings.refresh_ttl_days * 86400, path="/", **kw)
    return csrf


def clear_cookies(resp: Response) -> None:
    for name, path in (("access_token", "/"), ("refresh_token", "/auth"), ("csrf_token", "/")):
        resp.delete_cookie(name, path=path)


def verify_csrf(request: Request) -> None:
    """Double submit cookie. Only needed for cookie sessions on state-changing methods."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    c, h = request.cookies.get("csrf_token"), request.headers.get("x-csrf-token")
    if not c or not h or not secrets.compare_digest(c, h):
        raise HTTPException(403, "CSRF check failed")
