from __future__ import annotations
import sqlite3
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ..auth import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    create_session_token,
    multi_user_enabled,
    session_role,
    session_username,
    verify_login,
)
from ..db import get_connection
from ..settings import settings

router = APIRouter(prefix="/api", tags=["auth"])

_failed_attempts: dict[str, list[float]] = {}
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
    now = time.monotonic()
    attempts = [t for t in _failed_attempts.get(client_ip, []) if now - t < _LOGIN_WINDOW_SECONDS]

    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="too many login attempts, try again later")

    role = verify_login(conn, body.username, body.password)
    if role is None:
        attempts.append(now)
        _failed_attempts[client_ip] = attempts
        raise HTTPException(status_code=401, detail="invalid credentials")

    _failed_attempts.pop(client_ip, None)

    username = body.username if multi_user_enabled(conn) else settings.admin_username
    token = create_session_token(role, username)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
    )
    return {"ok": True, "role": role, "username": username}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
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
