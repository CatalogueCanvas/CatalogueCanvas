from __future__ import annotations
import json
import re
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from starlette.background import BackgroundTask
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..auth import require_admin, require_session
from ..db import (
    delete_portfolio,
    get_all_libraries,
    get_all_portfolios,
    get_item,
    get_portfolio,
    get_portfolio_by_slug,
    upsert_portfolio,
)
from ..ids import generate_portfolio_slug
from ..static_export import build_static_site
from .auth import get_db
from .items import _enrich

router = APIRouter(tags=["portfolios"])

PORTFOLIO_STYLES = {"ledger", "kinetic", "brutalist", "riso"}


def _norm_style(value: Any) -> str:
    return value if value in PORTFOLIO_STYLES else "ledger"


def _json_field(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value if value is not None else []


def _enrich_portfolio(p: dict[str, Any]) -> dict[str, Any]:
    p = dict(p)
    p["item_ids"] = _json_field(p.get("item_ids"))
    p["is_public"] = bool(p.get("is_public"))
    p["style"] = _norm_style(p.get("style"))
    p["watermark_enabled"] = bool(p.get("watermark_enabled"))
    p["watermark_text"] = p.get("watermark_text") or ""
    return p


def _visible_to(p: dict[str, Any], role: str) -> bool:
    """Admins see everything; readers only see portfolios marked 'readers'
    (a public portfolio is also reader-visible via this flag)."""
    return role == "admin" or p.get("visibility", "admin") != "admin"


# --- Admin endpoints ---

@router.get("/api/portfolios")
def list_portfolios(conn: sqlite3.Connection = Depends(get_db), role: str = Depends(require_session)):
    return [_enrich_portfolio(p) for p in get_all_portfolios(conn) if _visible_to(p, role)]


@router.get("/api/portfolios/{p_id}")
def get_portfolio_endpoint(p_id: str, conn: sqlite3.Connection = Depends(get_db), role: str = Depends(require_session)):
    p = get_portfolio(conn, p_id)
    if not p or not _visible_to(p, role):
        raise HTTPException(status_code=404, detail="portfolio not found")
    return _enrich_portfolio(p)


class PortfolioCreate(BaseModel):
    title: str
    description: str = ""
    slug: Optional[str] = None
    item_ids: list[str] = []
    is_public: bool = False
    visibility: str = "admin"
    style: str = "ledger"
    watermark_enabled: bool = False
    watermark_text: str = ""


@router.post("/api/portfolios")
def create_portfolio(body: PortfolioCreate, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    if body.slug:
        slug = body.slug
        if get_portfolio_by_slug(conn, slug):
            raise HTTPException(status_code=409, detail="slug already in use")
    else:
        slug = generate_portfolio_slug(lambda s: get_portfolio_by_slug(conn, s) is not None)
    p_id = uuid.uuid4().hex
    upsert_portfolio(conn, {
        "id": p_id,
        "slug": slug,
        "title": body.title,
        "description": body.description,
        "item_ids": body.item_ids,
        "is_public": int(body.is_public),
        "visibility": "readers" if body.visibility == "readers" else "admin",
        "style": _norm_style(body.style),
        "watermark_enabled": int(body.watermark_enabled),
        "watermark_text": body.watermark_text or "",
    })
    return _enrich_portfolio(get_portfolio(conn, p_id))


class PortfolioUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    slug: Optional[str] = None
    item_ids: Optional[list[str]] = None
    is_public: Optional[bool] = None
    visibility: Optional[str] = None
    style: Optional[str] = None
    watermark_enabled: Optional[bool] = None
    watermark_text: Optional[str] = None


@router.patch("/api/portfolios/{p_id}")
def update_portfolio(p_id: str, body: PortfolioUpdate, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    existing = get_portfolio(conn, p_id)
    if not existing:
        raise HTTPException(status_code=404, detail="portfolio not found")

    if body.slug and body.slug != existing["slug"]:
        other = get_portfolio_by_slug(conn, body.slug)
        if other and other["id"] != p_id:
            raise HTTPException(status_code=409, detail="slug already in use")

    updates: dict[str, Any] = {"id": p_id}
    updates["slug"] = body.slug if body.slug is not None else existing["slug"]
    updates["title"] = body.title if body.title is not None else existing["title"]
    updates["description"] = body.description if body.description is not None else existing["description"]
    updates["item_ids"] = body.item_ids if body.item_ids is not None else _json_field(existing["item_ids"])
    updates["is_public"] = int(body.is_public) if body.is_public is not None else existing["is_public"]
    if body.visibility is not None:
        updates["visibility"] = "readers" if body.visibility == "readers" else "admin"
    else:
        updates["visibility"] = existing["visibility"]
    updates["style"] = _norm_style(body.style) if body.style is not None else _norm_style(existing["style"])
    if body.watermark_enabled is not None:
        updates["watermark_enabled"] = int(body.watermark_enabled)
    else:
        updates["watermark_enabled"] = existing["watermark_enabled"]
    if body.watermark_text is not None:
        updates["watermark_text"] = body.watermark_text
    else:
        updates["watermark_text"] = existing["watermark_text"] or ""

    upsert_portfolio(conn, updates)
    return _enrich_portfolio(get_portfolio(conn, p_id))


class PortfolioItemsUpdate(BaseModel):
    item_ids: list[str]
    action: str  # "add" | "remove"


@router.post("/api/portfolios/{p_id}/items")
def update_portfolio_items(p_id: str, body: PortfolioItemsUpdate, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    existing = get_portfolio(conn, p_id)
    if not existing:
        raise HTTPException(status_code=404, detail="portfolio not found")
    if body.action not in ("add", "remove"):
        raise HTTPException(status_code=400, detail="action must be 'add' or 'remove'")

    current = _json_field(existing["item_ids"])
    if body.action == "add":
        new_ids = current + [i for i in body.item_ids if i not in current]
    else:
        new_ids = [i for i in current if i not in body.item_ids]

    upsert_portfolio(conn, {**existing, "item_ids": new_ids})
    return _enrich_portfolio(get_portfolio(conn, p_id))


class ExportOptions(BaseModel):
    quality: int = 85  # webp quality, clamped 40..95
    max_edge: Optional[int] = None  # longest-edge cap in px; None = original


@router.post("/api/portfolios/{p_id}/export")
def export_portfolio_static(p_id: str, body: Optional[ExportOptions] = None, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    """Render the portfolio to a self-contained static site and return it as a zip."""
    p = get_portfolio(conn, p_id)
    if not p:
        raise HTTPException(status_code=404, detail="portfolio not found")
    p = _enrich_portfolio(p)

    opts = body or ExportOptions()
    quality = max(40, min(95, opts.quality))
    max_edge = max(480, min(4000, opts.max_edge)) if opts.max_edge else None

    items = []
    for item_id in p["item_ids"]:
        item = get_item(conn, item_id)
        if item:
            items.append(_enrich(item, public=True))

    library_roots = {
        lib["id"]: Path(lib["path"]).resolve()
        for lib in get_all_libraries(conn)
        if Path(lib["path"]).exists()
    }

    zip_tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    zip_path = Path(zip_tmp.name)
    zip_tmp.close()
    build_static_site(p, items, library_roots, zip_path, quality=quality, max_edge=max_edge)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_slug = re.sub(r"[^a-zA-Z0-9_-]", "-", p["slug"]) or "portfolio"
    filename = f"{safe_slug}-site-{timestamp}.zip"
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=filename,
        background=BackgroundTask(zip_path.unlink, missing_ok=True),
    )


@router.delete("/api/portfolios/{p_id}")
def delete_portfolio_endpoint(p_id: str, conn: sqlite3.Connection = Depends(get_db), _: None = Depends(require_admin)):
    if not get_portfolio(conn, p_id):
        raise HTTPException(status_code=404, detail="portfolio not found")
    delete_portfolio(conn, p_id)
    return {"ok": True}


# --- Public endpoint ---

@router.get("/api/p/{slug}")
def get_public_portfolio(slug: str, conn: sqlite3.Connection = Depends(get_db)):
    p = get_portfolio_by_slug(conn, slug)
    if not p or not p.get("is_public"):
        raise HTTPException(status_code=404, detail="portfolio not found")

    p = _enrich_portfolio(p)
    items = []
    for item_id in p["item_ids"]:
        item = get_item(conn, item_id)
        if item:
            items.append(_enrich(item, public=True))

    return {
        "title": p["title"],
        "description": p["description"],
        "slug": p["slug"],
        "style": p["style"],
        "items": items,
    }
