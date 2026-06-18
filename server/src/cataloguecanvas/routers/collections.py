from __future__ import annotations
import re
import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import require_admin, require_session
from ..db import delete_collection, get_all_collections, get_collection, get_collection_items, upsert_collection
from .auth import get_db
from .items import _enrich

router = APIRouter(prefix="/api/collections", tags=["collections"])

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    return slug or "collection"


@router.get("")
def list_collections(conn: sqlite3.Connection = Depends(get_db), _: str = Depends(require_session)):
    return get_all_collections(conn)


@router.get("/{col_id}")
def get_collection_endpoint(col_id: str, conn: sqlite3.Connection = Depends(get_db), _: str = Depends(require_session)):
    col = get_collection(conn, col_id)
    if not col:
        raise HTTPException(status_code=404, detail="collection not found")
    return col


class CollectionCreate(BaseModel):
    title: str
    description: str = ""
    cover_item_id: Optional[str] = None
    id: Optional[str] = None


@router.post("")
def create_collection(body: CollectionCreate, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    col_id = body.id or _slugify(body.title)
    if get_collection(conn, col_id):
        raise HTTPException(status_code=409, detail="collection id already exists")
    upsert_collection(conn, {
        "id": col_id,
        "title": body.title,
        "description": body.description,
        "cover_item_id": body.cover_item_id,
    })
    return get_collection(conn, col_id)


class CollectionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    cover_item_id: Optional[str] = None


@router.patch("/{col_id}")
def update_collection(col_id: str, body: CollectionUpdate, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    existing = get_collection(conn, col_id)
    if not existing:
        raise HTTPException(status_code=404, detail="collection not found")
    if existing["is_system"]:
        raise HTTPException(status_code=403, detail="system collection cannot be edited")
    merged = {**existing, **{k: v for k, v in body.model_dump().items() if v is not None}}
    upsert_collection(conn, {
        "id": col_id,
        "title": merged["title"],
        "description": merged["description"],
        "cover_item_id": merged["cover_item_id"],
    })
    return get_collection(conn, col_id)


@router.delete("/{col_id}")
def delete_collection_endpoint(col_id: str, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    existing = get_collection(conn, col_id)
    if not existing:
        raise HTTPException(status_code=404, detail="collection not found")
    if existing["is_system"]:
        raise HTTPException(status_code=403, detail="system collection cannot be deleted")
    delete_collection(conn, col_id)
    return {"ok": True}


@router.get("/{col_id}/items")
def list_collection_items(col_id: str, conn: sqlite3.Connection = Depends(get_db), _: str = Depends(require_session)):
    if not get_collection(conn, col_id):
        raise HTTPException(status_code=404, detail="collection not found")
    return [_enrich(i) for i in get_collection_items(conn, col_id)]
