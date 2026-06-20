from __future__ import annotations
import secrets
import sqlite3
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ..auth import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    create_session_token,
    multi_user_enabled,
    session_role,
    session_sid,
    session_username,
    verify_login,
)
from ..db import (
    clear_login_failures,
    count_recent_login_failures,
    delete_session,
    get_connection,
    prune_login_failures,
    record_login_failure,
)
from ..settings import settings

router = APIRouter(prefix="/api", tags=["auth"])

_LOGIN_WINDOW_SECONDS = 300
_LOGIN_MAX_ATTEMPTS = 5


def get_db():
    conn = get_connection(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


class LoginRequest(BaseModel):
    password: str
    username: Optional[str] = None


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    # Throttle on IP + attempted username so one noisy IP can't lock out others
    # and a distributed guess at one account is still bounded.
    scope = f"{client_ip}|{body.username or ''}"
    now = time.time()
    window_start = now - _LOGIN_WINDOW_SECONDS
    prune_login_failures(conn, window_start)

    if count_recent_login_failures(conn, scope, window_start) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="too many login attempts, try again later")

    role = verify_login(conn, body.username, body.password)
    if role is None:
        record_login_failure(conn, scope, now)
        raise HTTPException(status_code=401, detail="invalid credentials")

    clear_login_failures(conn, scope)

    username = body.username if multi_user_enabled(conn) else settings.admin_username
    token = create_session_token(conn, role, username)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
    )
    # Double-submit CSRF token: readable by JS so the client can echo it in a
    # header; SameSite=strict keeps it from leaking cross-site.
    csrf_token = secrets.token_urlsafe(24)
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=SESSION_MAX_AGE,
        httponly=False,
        samesite="strict",
        secure=settings.cookie_secure,
    )
    return {"ok": True, "role": role, "username": username}


@router.post("/logout")
def logout(request: Request, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    sid = session_sid(request.cookies.get(SESSION_COOKIE))
    if sid:
        delete_session(conn, sid)
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(CSRF_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE)
    role = session_role(token)
    return {
        "authenticated": role is not None,
        "role": role,
        "username": session_username(token) if role is not None else None,
        "multi_user": multi_user_enabled(conn),
    }
