from __future__ import annotations
import os
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_admin
from ..db import (
    create_library,
    delete_library,
    get_all_libraries,
    get_library,
    library_item_count,
    set_default_library,
    update_library,
)
from .auth import get_db

router = APIRouter(prefix="/api/libraries", tags=["libraries"])


def _validate_path(path: str) -> Optional[str]:
    p = Path(path)
    if not p.exists():
        return "path does not exist"
    if not p.is_dir():
        return "path is not a directory"
    if not os.access(p, os.W_OK):
        return "path is not writable"
    return None


@router.get("")
def list_libraries(conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    libs = get_all_libraries(conn)
    for lib in libs:
        lib["item_count"] = library_item_count(conn, lib["id"])
        lib["path_ok"] = _validate_path(lib["path"]) is None
    return libs


class LibraryCreate(BaseModel):
    name: str
    path: str
    is_default: bool = False


@router.post("")
def create_library_endpoint(
    body: LibraryCreate, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)
):
    err = _validate_path(body.path)
    if err:
        raise HTTPException(status_code=400, detail=err)
    if any(lib["path"] == body.path for lib in get_all_libraries(conn)):
        raise HTTPException(status_code=400, detail="a library with this path already exists")
    return create_library(conn, body.name, body.path, body.is_default)


class LibraryUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None


@router.put("/{lib_id}")
def update_library_endpoint(
    lib_id: str, body: LibraryUpdate, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)
):
    lib = get_library(conn, lib_id)
    if not lib:
        raise HTTPException(status_code=404, detail="library not found")
    if body.path is not None and body.path != lib["path"]:
        if library_item_count(conn, lib_id) > 0:
            raise HTTPException(status_code=400, detail="cannot change path of a library that already has items")
        err = _validate_path(body.path)
        if err:
            raise HTTPException(status_code=400, detail=err)
    return update_library(conn, lib_id, body.model_dump(exclude_unset=True))


@router.post("/{lib_id}/default")
def set_default_endpoint(
    lib_id: str, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)
):
    if not get_library(conn, lib_id):
        raise HTTPException(status_code=404, detail="library not found")
    return set_default_library(conn, lib_id)


@router.delete("/{lib_id}")
def delete_library_endpoint(
    lib_id: str, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)
):
    lib = get_library(conn, lib_id)
    if not lib:
        raise HTTPException(status_code=404, detail="library not found")
    if library_item_count(conn, lib_id) > 0:
        raise HTTPException(status_code=400, detail="cannot delete a library that contains items")
    if lib["is_default"]:
        raise HTTPException(status_code=400, detail="cannot delete the default library")
    delete_library(conn, lib_id)
    return {"ok": True}
