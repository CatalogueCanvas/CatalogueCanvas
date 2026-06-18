from __future__ import annotations
import sqlite3
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from passlib.context import CryptContext

from .db import get_admin_hash, get_settings, get_user_by_username, set_admin_hash
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


def multi_user_enabled(conn: sqlite3.Connection) -> bool:
    return get_settings(conn).get("multi_user_enabled") == "true"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_admin_password(conn: sqlite3.Connection, password: str) -> bool:
    stored = get_admin_hash(conn)
    if not stored:
        return False
    return pwd_context.verify(password, stored)


def verify_login(conn: sqlite3.Connection, username: Optional[str], password: str) -> Optional[str]:
    """Validate credentials and return the resolved role, or None on failure.

    When multi-user mode is off, only the admin path is accepted (username is
    ignored) so the legacy password-only login keeps working unchanged. When on,
    credentials are checked against the users table.
    """
    if multi_user_enabled(conn):
        if not username:
            return None
        user = get_user_by_username(conn, username)
        if not user or not pwd_context.verify(password, user["password_hash"]):
            return None
        return user["role"]

    return "admin" if verify_admin_password(conn, password) else None


def create_session_token(role: str = "admin") -> str:
    return _serializer().dumps({"role": role})


def session_role(token: str | None) -> Optional[str]:
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None
    # Backwards-compat with legacy {"admin": True} tokens.
    if data.get("admin") is True and "role" not in data:
        return "admin"
    role = data.get("role")
    return role if role in ("admin", "reader") else None


def is_valid_session(token: str | None) -> bool:
    return session_role(token) is not None


def _check_cross_origin(request: Request) -> None:
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("origin") or request.headers.get("referer")
        if origin:
            origin_host = urlparse(origin).netloc
            if origin_host and origin_host != request.url.netloc:
                raise HTTPException(status_code=403, detail="cross-origin request rejected")


def require_session(request: Request) -> str:
    """Require any authenticated user (admin or reader). Returns the role."""
    role = session_role(request.cookies.get(SESSION_COOKIE))
    if role is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    _check_cross_origin(request)
    return role


def require_admin(request: Request) -> None:
    role = session_role(request.cookies.get(SESSION_COOKIE))
    if role is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    if role != "admin":
        raise HTTPException(status_code=403, detail="admin privileges required")
    _check_cross_origin(request)
