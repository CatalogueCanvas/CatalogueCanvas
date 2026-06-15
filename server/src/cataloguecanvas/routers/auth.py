from __future__ import annotations
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ..auth import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    create_session_token,
    is_valid_session,
    verify_admin_password,
)
from ..db import get_connection
from ..settings import settings

router = APIRouter(prefix="/api", tags=["auth"])


def get_db():
    conn = get_connection(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginRequest, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    if not verify_admin_password(conn, body.password):
        raise HTTPException(status_code=401, detail="invalid password")

    token = create_session_token()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    return {"authenticated": is_valid_session(token)}
