# CatalogueCanvas

[![Codacy Badge](https://app.codacy.com/project/badge/Grade/e2b7642211994b0a8cba75e9d1d1a14f)](https://app.codacy.com/gh/CatalogueCanvas/CatalogueCanvas/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![Codacy Badge](https://app.codacy.com/project/badge/Coverage/e2b7642211994b0a8cba75e9d1d1a14f)](https://app.codacy.com/gh/CatalogueCanvas/CatalogueCanvas/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_coverage)
[![Coverage CI](https://github.com/CatalogueCanvas/CatalogueCanvas/actions/workflows/coverage.yml/badge.svg)](https://github.com/CatalogueCanvas/CatalogueCanvas/actions/workflows/coverage.yml)
[![Security audit](https://github.com/CatalogueCanvas/CatalogueCanvas/actions/workflows/security.yml/badge.svg)](https://github.com/CatalogueCanvas/CatalogueCanvas/actions/workflows/security.yml)
[![CodeQL](https://github.com/CatalogueCanvas/CatalogueCanvas/actions/workflows/codeql.yml/badge.svg)](https://github.com/CatalogueCanvas/CatalogueCanvas/actions/workflows/codeql.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-blue?logo=docker)](https://github.com/CatalogueCanvas/CatalogueCanvas/blob/main/Dockerfile)

<img src="media/logo_dark.png" align="right" width="150"/>
<p></p>


     

**Your catalogue, your disks, your data.**

CatalogueCanvas is a self-hosted home for your digital work. Drop in a ZIP and it becomes a catalogue item. From there you sort items into collections, tag them, add notes (or let a local vision model write the descriptions for you), and pull your best pieces into a portfolio you can hand to anyone with a link.

Collect whatever you like. Generative art, illustrations, code sketches, design assets, photos, or a messy pile of all of it. The whole thing runs in one Docker container on hardware you own, with no account to sign up for and nobody else holding your files.

It is built for people who work in files. If you make art, you can show a body of work without first building a website. If you write generative code, the rendered image and the source that produced it live in the same item. And if you would rather run your own catalogue than pay for another seat somewhere, this is for you.

Designed to fit in a self-hosting environment, will run anywhere that a docker container can run, even a old android phone [Article](https://medium.com/@adam.frydrych_29025/running-a-server-from-an-old-android-phone-4f1a3973f7cb) [Guide](https://gist.github.com/FreddieOliveira/efe850df7ff3951cb62d74bd770dce27)

![Main Layout Catalogue Canvas](media/Items_CC.png "Main Layout")

## Requirements

- Docker + Docker Compose (recommended way to run the app)

For local development without Docker:

- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/) for the backend
- Node.js 22+ for the frontend

### Deployment footprint 

- Docker image size: ~436 MB
- RAM: ~256 MB sufficient for light use; more if large ZIP ingests are used heavily
- Disk: depends on uploaded item assets — size `CC_DATA_DIR` volume accordingly
- CPU: single core sufficient (image conversion/ingest is the main CPU cost)

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

## Installation / Running

### With Docker (recommended)

Create a `.env` file in the project root (alongside `docker-compose.yml`) with at least the admin password:

```dotenv
# Required: admin login password (app fails closed until this is set)
CC_ADMIN_PASSWORD=changeme

# Optional
CC_PORT=8000
CC_SITE_TITLE=CatalogueCanvas
CC_SITE_AUTHOR=
CC_COOKIE_SECURE=true

# Optional SSRF guard for the LLM describe feature. When set, the LLM api_url
# host must match one of these (comma-separated). Add internal hosts explicitly,
# e.g. CC_LLM_ALLOWED_HOSTS=ollama.lan,192.168.1.50. Unset = no host restriction.
CC_LLM_ALLOWED_HOSTS=
```

Docker Compose reads `.env` automatically. Then run:

```bash
docker compose up -d --build
```

The `.env` file is gitignored — keep your real secrets out of version control. Alternatively, pass variables inline:

```bash
CC_ADMIN_PASSWORD=mysecretpassword docker compose up --build
```

Then open `http://localhost:8000` and log in with `CC_ADMIN_PASSWORD`.

To serve on a different host port, set `CC_PORT` (the container always listens on 8000 internally):

```bash
CC_ADMIN_PASSWORD=mysecretpassword CC_PORT=8081 docker compose up --build
```

This maps host port 8081 to the container, so the app is reachable at `http://localhost:8081`.

On first boot the container generates a random session signing key at `/data/cc_secret_key.txt` and reuses it on subsequent starts — no manual setup needed. All data (the SQLite database, uploaded item assets, and the session key) is persisted in the `./data` directory mounted into the container at `/data`.

### Bare Metal Install 

This is more advanced since will let you use the full OS to run it. This have been tested in windows 11, OSX arm and Debian. Details and guides for install each system in documentation.

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
| `CC_PORT` | `8000` | Host port mapped to the container in `docker-compose.yml` (container always listens on 8000) |
| `CC_SECRET_KEY` | `dev-secret-change-me` | Session signing key — set a random value for local dev. In Docker, the key is auto-generated and persisted at `<CC_DATA_DIR>/cc_secret_key.txt`, so this is not needed. |
| `CC_SECRET_KEY_FILE` | _(unset)_ | Path to a file containing the session signing key — takes precedence over `CC_SECRET_KEY`. The Docker entrypoint sets this automatically. |
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
- Export the database or full data directory from **Settings**. Exports are admin-only and **unencrypted** — store and transfer the downloaded files over a trusted channel.

## Layout

```
server/                  FastAPI backend (SQLite db, ingestion, LLM descriptions, auth)
web/                     React admin UI + public portfolio pages
```
