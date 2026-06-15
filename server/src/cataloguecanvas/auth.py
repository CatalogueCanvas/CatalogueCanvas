from __future__ import annotations
import sqlite3

from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from passlib.context import CryptContext

from .db import get_admin_hash, set_admin_hash
from .settings import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

SESSION_COOKIE = "cc_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="cc-session")


def ensure_admin(conn: sqlite3.Connection) -> None:
    """On first boot, derive the admin password hash from CC_ADMIN_PASSWORD if not set."""
    if get_admin_hash(conn) is None and settings.admin_password:
        set_admin_hash(conn, pwd_context.hash(settings.admin_password))


def verify_admin_password(conn: sqlite3.Connection, password: str) -> bool:
    stored = get_admin_hash(conn)
    if not stored:
        return False
    return pwd_context.verify(password, stored)


def create_session_token() -> str:
    return _serializer().dumps({"admin": True})


def is_valid_session(token: str | None) -> bool:
    if not token:
        return False
    try:
        data = _serializer().loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return False
    return bool(data.get("admin"))


def require_admin(request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if not is_valid_session(token):
        raise HTTPException(status_code=401, detail="not authenticated")
