from __future__ import annotations
import secrets
import sqlite3
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from passlib.context import CryptContext

from .db import (
    get_admin_hash,
    get_connection,
    get_settings,
    get_user_by_username,
    session_exists,
    set_admin_hash,
)
from .settings import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

SESSION_COOKIE = "cc_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
CSRF_COOKIE = "cc_csrf"
CSRF_HEADER = "x-csrf-token"


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


def create_session_token(conn: sqlite3.Connection, role: str = "admin", username: Optional[str] = None) -> str:
    """Mint a signed token bound to a server-side session row so logout (which
    deletes the row) revokes the token, not just the cookie."""
    from .db import create_session

    sid = secrets.token_urlsafe(24)
    create_session(conn, sid, role, username)
    return _serializer().dumps({"sid": sid, "role": role, "username": username})


def _session_data(token: str | None) -> Optional[dict]:
    if not token:
        return None
    try:
        return _serializer().loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None


def session_sid(token: str | None) -> Optional[str]:
    data = _session_data(token)
    return data.get("sid") if data else None


def _sid_is_active(sid: Optional[str]) -> bool:
    """A valid token must be bound to a live server-side session row. Tokens
    without a sid (legacy stateless tokens) can't be revoked, so they are
    rejected outright rather than trusted for backwards-compat."""
    if sid is None:
        return False
    conn = get_connection(settings.db_path)
    try:
        return session_exists(conn, sid)
    finally:
        conn.close()


def session_role(token: str | None) -> Optional[str]:
    data = _session_data(token)
    if data is None:
        return None
    if not _sid_is_active(data.get("sid")):
        return None
    role = data.get("role")
    return role if role in ("admin", "reader") else None


def session_username(token: str | None) -> Optional[str]:
    data = _session_data(token)
    if data is None:
        return None
    return data.get("username")


def is_valid_session(token: str | None) -> bool:
    return session_role(token) is not None


_UNSAFE_METHODS = ("POST", "PUT", "PATCH", "DELETE")


def _check_cross_origin(request: Request) -> None:
    if request.method in _UNSAFE_METHODS:
        origin = request.headers.get("origin") or request.headers.get("referer")
        if origin:
            origin_host = urlparse(origin).netloc
            if origin_host and origin_host != request.url.netloc:
                raise HTTPException(status_code=403, detail="cross-origin request rejected")


def _check_csrf(request: Request) -> None:
    """Double-submit check: the cc_csrf cookie must match the X-CSRF-Token header
    on state-changing requests. Defense-in-depth on top of SameSite=strict."""
    if request.method not in _UNSAFE_METHODS:
        return
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise HTTPException(status_code=403, detail="invalid or missing CSRF token")


def require_session(request: Request) -> str:
    """Require any authenticated user (admin or reader). Returns the role."""
    role = session_role(request.cookies.get(SESSION_COOKIE))
    if role is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    _check_cross_origin(request)
    _check_csrf(request)
    return role


def require_admin(request: Request) -> None:
    role = session_role(request.cookies.get(SESSION_COOKIE))
    if role is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    if role != "admin":
        raise HTTPException(status_code=403, detail="admin privileges required")
    _check_cross_origin(request)
    _check_csrf(request)
