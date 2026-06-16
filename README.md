# CatalogueCanvas

<img src="media/logo_dark.png" align="right" width="150"/>
<p></p>


     

A domain-agnostic catalogue server: ingest ZIP items into a SQLite-backed FastAPI app with a React admin UI, organize them into collections, and share public portfolios.

## Architecture

- **`server/`** — FastAPI backend (`cataloguecanvas` Python package, managed with `uv`). Serves the JSON API, the built React app, and public portfolio pages. Persists data to a SQLite database and stores uploaded item assets on disk.
- **`web/`** — React + TypeScript admin UI (Vite). Built to static assets and served by the FastAPI app.
- **`legacy/`** — deprecated static-site pipeline, unsupported.

### Backend modules (`server/src/cataloguecanvas/`)

- `main.py` — app factory, mounts routers and serves the SPA.
- `routers/` — API endpoints, grouped by resource:
  - `auth` — `/login`, `/logout`, `/me` (session-cookie auth)
  - `items` — `/api/items` CRUD, ZIP upload/ingest, archive download, LLM `describe`
  - `collections` — `/api/collections` CRUD
  - `portfolios` — `/api/portfolios` CRUD, plus public `/api/p/{slug}`
  - `settings` — app settings (incl. LLM config), DB/data export
- `db.py` — SQLite schema (`items`, `collections`, `portfolios`, `admin`, `app_settings`) and connection helpers.
- `ingest.py` — extracts uploaded ZIPs into storage and registers items.
- `convert.py` — image/preview conversion (Pillow, cairosvg).
- `llm.py` — calls an OpenAI-compatible vision LLM to generate item descriptions, using `prompt.template.toml`.
- `auth.py` — password hashing (argon2) and session handling.
- `settings.py` — runtime configuration from environment variables.

### Data flow

1. Admin logs in (`CC_ADMIN_PASSWORD` checked against the `admin` table).
2. Admin uploads a ZIP via the dashboard → `ingest.py` extracts it into `CC_STORAGE_DIR`, creates a row in `items`.
3. Items can be edited (title, tags, notes) and optionally described via an LLM (configured in **Settings**).
4. Items are grouped into `collections`, and selected items can be published as a `portfolio` (slide-deck view at `/p/<slug>`, public if `is_public` is set).

## Requirements

- Docker + Docker Compose (recommended way to run the app)

For local development without Docker:

- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/) for the backend
- Node.js 22+ for the frontend

### Deployment footprint

- Docker image size: ~436 MB
- RAM: ~256 MB sufficient for light use; more if the LLM describe feature or large ZIP ingests are used heavily
- Disk: depends on uploaded item assets — size `CC_DATA_DIR` volume accordingly
- CPU: single core sufficient (image conversion/ingest is the main CPU cost)

## Installation / Running

### With Docker (recommended)

Generate the session secret key once (stored as a Docker Compose secret file, not an env var):

```bash
mkdir -p secrets
openssl rand -hex 32 > secrets/cc_secret_key.txt
```

```bash
CC_ADMIN_PASSWORD=mysecretpassword docker compose up --build
```

Then open `http://localhost:8000` and log in with `CC_ADMIN_PASSWORD`.

All data (the SQLite database and uploaded item assets) is persisted in the `cc-data` Docker volume under `/data`.

### Local development (without Docker)

Backend:

```bash
cd server
uv sync
uv run uvicorn cataloguecanvas.main:app --reload
```

Frontend:

```bash
cd web
npm ci
npm run dev
```

The Vite dev server proxies API requests to the backend; see `web/vite.config.ts` for the proxy target.

## Configuration

Environment variables (set via `docker-compose.yml` or your shell):

| Variable | Default | Description |
|---|---|---|
| `CC_ADMIN_PASSWORD` | _(empty)_ | Admin login password — required to log in |
| `CC_SECRET_KEY` | `dev-secret-change-me` | Session signing key — set a random value in production (local dev only; in Docker use `CC_SECRET_KEY_FILE`) |
| `CC_SECRET_KEY_FILE` | _(unset)_ | Path to a file containing the session signing key — takes precedence over `CC_SECRET_KEY` (used by Docker Compose secrets) |
| `CC_SITE_TITLE` | `My Catalogue` | Title shown in the UI and public portfolios |
| `CC_SITE_AUTHOR` | _(empty)_ | Author/owner name shown on public portfolios |
| `CC_DATA_DIR` | `/data` | Base directory for the database and storage |
| `CC_DB_PATH` | `<CC_DATA_DIR>/catalogue.db` | SQLite database file path |
| `CC_STORAGE_DIR` | `<CC_DATA_DIR>/storage` | Directory for uploaded item assets |
| `CC_STATIC_DIR` | `web/dist` | Directory of built frontend assets to serve |

## Usage

- Upload ZIP items from the dashboard, edit titles/tags/notes, and organize them into collections.
- Generate per-item descriptions with a vision-capable LLM: in **Settings**, set an OpenAI-compatible `api_url` and model (an API key can also be entered per-request — used only for that request and never stored).
  - If the LLM server (e.g. LM Studio, Ollama) runs on your host machine and CatalogueCanvas runs in Docker, use `http://host.docker.internal:1234/v1/chat/completions` (not `localhost`) — `localhost` inside the container refers to the container itself, not your host.
- Create a portfolio, select items, mark it **Public**, and share its `/p/<slug>` link — a slide-deck style presentation viewable without logging in.
- Export the database or full data directory from **Settings**.

## Layout

```
server/                  FastAPI backend (SQLite db, ingestion, LLM descriptions, auth)
web/                     React admin UI + public portfolio pages
```
