from __future__ import annotations
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import hash_password, pwd_context, require_admin
from ..db import (
    count_admins,
    create_user,
    delete_user,
    get_connection,
    get_user,
    get_user_by_username,
    list_users,
    update_user,
)
from ..settings import settings

router = APIRouter(prefix="/api/users", tags=["users"])

VALID_ROLES = ("admin", "reader")


def get_db():
    conn = get_connection(settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


class UserCreate(BaseModel):
    username: str
    password: str
    role: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None


def _validate_role(role: str) -> None:
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {VALID_ROLES}")


def _password_collides(conn: sqlite3.Connection, password: str, exclude_id: Optional[int]) -> bool:
    """True if `password` matches any other user's stored password.

    Enforces the "passwords can't be the same" rule across users (notably
    admin vs reader) without ever storing or comparing plaintext.
    """
    for u in list_users(conn):
        if exclude_id is not None and u["id"] == exclude_id:
            continue
        stored = get_user(conn, u["id"])
        if stored and pwd_context.verify(password, stored["password_hash"]):
            return True
    return False


@router.get("")
def list_users_endpoint(conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    return list_users(conn)


@router.post("")
def create_user_endpoint(
    body: UserCreate,
    conn: sqlite3.Connection = Depends(get_db),
    _: None = Depends(require_admin),
):
    _validate_role(body.role)
    if not body.username.strip():
        raise HTTPException(status_code=400, detail="username required")
    if not body.password:
        raise HTTPException(status_code=400, detail="password required")
    if get_user_by_username(conn, body.username):
        raise HTTPException(status_code=409, detail="username already exists")
    if _password_collides(conn, body.password, exclude_id=None):
        raise HTTPException(status_code=400, detail="password must differ from other users")
    user_id = create_user(conn, body.username, hash_password(body.password), body.role)
    created = get_user(conn, user_id)
    return {k: created[k] for k in ("id", "username", "role", "created_at")}


@router.put("/{user_id}")
def update_user_endpoint(
    user_id: int,
    body: UserUpdate,
    conn: sqlite3.Connection = Depends(get_db),
    _: None = Depends(require_admin),
):
    user = get_user(conn, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    new_role = body.role
    if new_role is not None:
        _validate_role(new_role)
        # Prevent demoting the last admin.
        if user["role"] == "admin" and new_role != "admin" and count_admins(conn) <= 1:
            raise HTTPException(status_code=400, detail="cannot demote the last admin")

    if body.username is not None and body.username != user["username"]:
        if get_user_by_username(conn, body.username):
            raise HTTPException(status_code=409, detail="username already exists")

    password_hash = None
    if body.password:
        if _password_collides(conn, body.password, exclude_id=user_id):
            raise HTTPException(status_code=400, detail="password must differ from other users")
        password_hash = hash_password(body.password)

    update_user(
        conn,
        user_id,
        username=body.username,
        password_hash=password_hash,
        role=new_role,
    )
    updated = get_user(conn, user_id)
    return {k: updated[k] for k in ("id", "username", "role", "created_at")}


@router.delete("/{user_id}")
def delete_user_endpoint(
    user_id: int,
    conn: sqlite3.Connection = Depends(get_db),
    _: None = Depends(require_admin),
):
    user = get_user(conn, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    if user["role"] == "admin" and count_admins(conn) <= 1:
        raise HTTPException(status_code=400, detail="cannot delete the last admin")
    delete_user(conn, user_id)
    return {"ok": True}
