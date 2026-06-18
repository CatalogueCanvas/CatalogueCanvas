from __future__ import annotations
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .auth import ensure_admin
from .db import ensure_schema, get_connection, get_library
from .routers import auth, collections, items, libraries, portfolios, settings as settings_router, users
from .settings import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; frame-ancestors 'none'",
        )
        return response


def create_app() -> FastAPI:
    settings.ensure_dirs()

    conn = get_connection(settings.db_path)
    ensure_schema(conn)
    ensure_admin(conn)
    conn.close()

    app = FastAPI(title="CatalogueCanvas")
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(auth.router)
    app.include_router(items.router)
    app.include_router(collections.router)
    app.include_router(portfolios.router)
    app.include_router(libraries.router)
    app.include_router(settings_router.router)
    app.include_router(users.router)

    @app.get("/storage/{library_id}/{rel_path:path}")
    def serve_storage_file(library_id: str, rel_path: str):
        conn = get_connection(settings.db_path)
        try:
            lib = get_library(conn, library_id)
        finally:
            conn.close()
        if not lib:
            raise HTTPException(status_code=404, detail="library not found")
        lib_root = Path(lib["path"]).resolve()
        target = (lib_root / rel_path).resolve()
        if target != lib_root and not str(target).startswith(str(lib_root) + os.sep):
            raise HTTPException(status_code=404, detail="not found")
        if not target.is_file():
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(target)

    if settings.static_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(settings.static_dir / "assets")), name="spa-assets")

        @app.get("/{full_path:path}")
        def spa_fallback(full_path: str):
            index_file = settings.static_dir / "index.html"
            return FileResponse(index_file)

    return app


app = create_app()
