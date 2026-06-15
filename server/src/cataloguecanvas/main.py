from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth import ensure_admin
from .db import ensure_schema, get_connection
from .routers import auth, collections, items, portfolios, settings as settings_router
from .settings import settings


def create_app() -> FastAPI:
    settings.ensure_dirs()

    conn = get_connection(settings.db_path)
    ensure_schema(conn)
    ensure_admin(conn)
    conn.close()

    app = FastAPI(title="CatalogueCanvas")

    app.include_router(auth.router)
    app.include_router(items.router)
    app.include_router(collections.router)
    app.include_router(portfolios.router)
    app.include_router(settings_router.router)

    if settings.storage_dir.exists():
        app.mount("/storage", StaticFiles(directory=str(settings.storage_dir)), name="storage")

    if settings.static_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(settings.static_dir / "assets")), name="spa-assets")

        @app.get("/{full_path:path}")
        def spa_fallback(full_path: str):
            index_file = settings.static_dir / "index.html"
            return FileResponse(index_file)

    return app


app = create_app()
