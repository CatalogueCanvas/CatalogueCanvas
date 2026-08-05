from __future__ import annotations
import ipaddress
import time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from . import audit
from .auth import ensure_admin, require_session
from .db import ensure_schema, get_connection, get_library, is_public_storage_path
from .routers import auth, collections, items, libraries, portfolios, settings as settings_router, users
from .settings import settings

# How often a single source IP can add a "blocked" entry to the activity log.
# Without this a port scanner would fill the disk one line at a time.
_BLOCK_LOG_INTERVAL_SECONDS = 60
# Upper bound on how many source addresses the rate-limiter remembers at once.
_BLOCK_LOG_MAX_TRACKED = 1024


def _is_private_address(host: str) -> bool:
    """True for loopback, RFC1918/ULA private, and link-local addresses.

    An address that can't be parsed is treated as external: failing closed is
    the whole point of this control.
    """
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


class ExternalRequestMiddleware(BaseHTTPMiddleware):
    """Reject requests from public IPs unless CC_ALLOW_EXTERNAL_REQUESTS is set.

    Guards against the common self-hosting accident: a port forward that quietly
    exposes the whole catalogue to the internet. Applies to every route,
    including public portfolios -- an operator who deliberately publishes one
    opts in explicitly.
    """

    def __init__(self, app):
        super().__init__(app)
        self._last_logged: dict[str, float] = {}

    def _client_host(self, request: Request) -> str:
        peer = request.client.host if request.client else ""
        # X-Forwarded-For is only meaningful when the immediate peer is a proxy
        # we trust. Honouring it unconditionally would let any caller claim to
        # be 127.0.0.1 and walk straight through this check.
        if peer and peer in settings.trusted_proxies:
            forwarded = request.headers.get("x-forwarded-for", "")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return peer

    def _log_blocked(self, host: str, path: str) -> None:
        now = time.monotonic()
        last = self._last_logged.get(host)
        if last is not None and now - last < _BLOCK_LOG_INTERVAL_SECONDS:
            return
        self._last_logged[host] = now
        # Bound the dict so a scanner rotating source addresses can't grow it
        # without limit. Drop expired entries first; if a burst of distinct
        # addresses is still under the interval, evict the oldest by force --
        # the worst case is a duplicate log line for an address we forgot.
        if len(self._last_logged) > _BLOCK_LOG_MAX_TRACKED:
            cutoff = now - _BLOCK_LOG_INTERVAL_SECONDS
            self._last_logged = {k: v for k, v in self._last_logged.items() if v >= cutoff}
            if len(self._last_logged) > _BLOCK_LOG_MAX_TRACKED:
                keep = sorted(self._last_logged.items(), key=lambda kv: kv[1], reverse=True)
                self._last_logged = dict(keep[:_BLOCK_LOG_MAX_TRACKED])
        audit.log_event("request.blocked_external", target=host, path=path)

    async def dispatch(self, request, call_next):
        if not settings.allow_external_requests:
            host = self._client_host(request)
            if not _is_private_address(host):
                self._log_blocked(host or "unknown", request.url.path)
                return JSONResponse(
                    {
                        "detail": (
                            "external requests are disabled. Set CC_ALLOW_EXTERNAL_REQUESTS=true "
                            "to serve public clients, or add your reverse proxy to CC_TRUSTED_PROXIES."
                        )
                    },
                    status_code=403,
                )
        return await call_next(request)


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


_NOT_FOUND_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>404 — Not found</title>
<style>
  :root { color-scheme: light dark; }
  body {
    margin: 0; min-height: 100vh;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 8px; text-align: center;
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    background: #fafaf8; color: #2a2a28;
  }
  @media (prefers-color-scheme: dark) { body { background: #16161a; color: #e8e8e6; } }
  .code { font-size: 56px; font-weight: 700; line-height: 1; color: #d6432a; margin-bottom: 4px; }
  .title { font-size: 18px; font-weight: 600; }
  .sub { font-size: 14px; opacity: 0.7; max-width: 42ch; }
  a { margin-top: 12px; font-size: 14px; color: inherit; }
</style>
</head>
<body>
  <div class="code">404</div>
  <div class="title">Page not found</div>
  <div class="sub">The page you’re looking for doesn’t exist or has been moved.</div>
  <a href="/">Back to catalogue</a>
</body>
</html>"""


def create_app() -> FastAPI:
    settings.ensure_dirs()

    conn = get_connection(settings.db_path)
    ensure_schema(conn)
    ensure_admin(conn)
    conn.close()

    # One-time anonymous install ping (no-op unless CC_INSTALL_TRACKING=1 and not
    # already sent). Never raises.
    from . import telemetry

    telemetry.send_install_ping()

    app = FastAPI(title="CatalogueCanvas")
    app.add_middleware(SecurityHeadersMiddleware)
    # Added last so it wraps outermost (Starlette applies middleware in reverse
    # registration order): a blocked request is rejected before anything else runs.
    app.add_middleware(ExternalRequestMiddleware)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        accepts_html = "text/html" in request.headers.get("accept", "")
        if exc.status_code == 404 and accepts_html:
            return HTMLResponse(_NOT_FOUND_HTML, status_code=404)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    app.include_router(auth.router)
    app.include_router(items.router)
    app.include_router(collections.router)
    app.include_router(portfolios.router)
    app.include_router(libraries.router)
    app.include_router(settings_router.router)
    app.include_router(settings_router.version_router)
    app.include_router(users.router)

    def _resolve_storage_file(library_id: str, rel_path: str) -> Path:
        conn = get_connection(settings.db_path)
        try:
            lib = get_library(conn, library_id)
        finally:
            conn.close()
        if not lib:
            raise HTTPException(status_code=404, detail="library not found")
        lib_root = Path(lib["path"]).resolve()
        # Reject symlinks anywhere along the requested path so a link planted in
        # the library can't redirect a read to another in-root (e.g. admin-only)
        # file. The resolve()+prefix check below already blocks escaping the root.
        unresolved = lib_root / rel_path
        if unresolved.is_symlink() or any(p.is_symlink() for p in unresolved.parents if str(p).startswith(str(lib_root))):
            raise HTTPException(status_code=404, detail="not found")
        target = unresolved.resolve()
        try:
            target.relative_to(lib_root)
        except ValueError:
            raise HTTPException(status_code=404, detail="not found")
        if not target.is_file():
            raise HTTPException(status_code=404, detail="not found")
        return target

    @app.get("/storage/{library_id}/{rel_path:path}")
    def serve_storage_file(library_id: str, rel_path: str, _: str = Depends(require_session)):
        return FileResponse(_resolve_storage_file(library_id, rel_path))

    @app.get("/p-storage/{library_id}/{rel_path:path}")
    def serve_public_storage_file(library_id: str, rel_path: str):
        # Anonymous access, but only for files belonging to items published
        # through a public portfolio. Everything else requires a session.
        conn = get_connection(settings.db_path)
        try:
            allowed = is_public_storage_path(conn, library_id, rel_path)
        finally:
            conn.close()
        if not allowed:
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(_resolve_storage_file(library_id, rel_path))

    if settings.static_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(settings.static_dir / "assets")), name="spa-assets")

        @app.get("/{full_path:path}")
        def spa_fallback(full_path: str):
            index_file = settings.static_dir / "index.html"
            return FileResponse(index_file)

    return app


app = create_app()
