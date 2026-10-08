"""Account creation. Keep every account write in this module."""
import random

from fastapi import HTTPException

from app.core.constants import SCHEMA_VERSION
from app.core.db import get_db
from app.core.security.auth import hash_password
from app.core.security.crypto import enc
from app.core.util import now


async def _new_patient_code() -> str:
    db = get_db()
    for digits in (4, 4, 4, 6, 6, 8):  # grow the space if the short one fills up
        code = "PAT-" + "".join(random.choice("0123456789") for _ in range(digits))
        if not await db.users.find_one({"patient_code": code}):
            return code
    raise HTTPException(503, "Could not create the account. Please try again.")


async def create_user(name, login, password, role, language, phone=None, patient_code=None,
                      can_login: bool = True, guardian_id=None, age_label: str | None = None) -> dict:
    db = get_db()
    login = login.strip().lower()
    if await db.users.find_one({"login": login}):
        raise HTTPException(409, "That login is already taken")
    user = {"name": enc(name), "login": login, "password_hash": hash_password(password), "role": role,
            "language": language, "phone": enc(phone), "is_active": True, "can_login": can_login,
            "guardian_id": guardian_id, "age_label": age_label, "failed_logins": 0,
            "locked_until": None, "created_at": now(), "schema_version": SCHEMA_VERSION}
    if role == "patient":
        user["patient_code"] = patient_code or await _new_patient_code()  # fixed codes for demo data
    user["_id"] = (await db.users.insert_one(user)).inserted_id
    return user
