# Changelog

All notable changes to CatalogueCanvas are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Released versions are tagged (see `v*` tags and the published `ghcr.io` image); earlier pre-release entries are grouped by date.

## [0.1.4] - 2026-07-15

### Added
- Item images open at full size. Clicking the preview on an item page opens a lightbox that fits the image to the screen, toggles to 1:1 on click, and pans by dragging. Previews were already stored at full resolution, so no new assets are generated. Arrow-key item navigation is suspended while the lightbox is open.
- Portfolio layout option, chosen per portfolio and independent of the theme: `slide` (the existing full-height deck, printable to PDF at 1920×1080) or `scroll` (a continuous one-page site with no page breaks and no print button). Any of the four themes can be published either way. Applies to the live portfolio and the static zip export. Existing portfolios default to `slide`.

### Fixed
- The lightbox now fits the image to the screen at all times. Clicking to zoom to 1:1 opened large images past the edge of the viewport, so the zoom and drag-to-pan behaviour is gone.
- "Preview deck" and the portfolio list's "View" button now carry the share token. Both linked to the untokenized URL, which returns 404 for a gated portfolio.

## [0.1.3] - 2026-07-11

### Added
- Opt-in update check. An admin-only `/api/version` endpoint queries GitHub for the latest release (weekly throttle, no network unless enabled) and the footer surfaces when a newer version is available. Configurable from Settings.

### Fixed
- LLM descriptions are now stored identically whether generated for a single item or in batch. Both paths use a shared `describeResultToNote` helper, so the full summary and bullet list are saved to the note instead of only the summary in the batch flow.

## [0.1.2] - 2026-07-10

### Fixed
- LLM description pipeline: preview images (stored as WebP) were sent to the vision endpoint under a hardcoded `data:image/jpeg` label, so the bytes never matched the declared MIME type. This worked only on lenient runtimes and failed with `HTTP 400 Failed to load image or audio file` on LM Studio versions that trust the declared type (which accepts only jpeg/png). Previews are now transcoded to real JPEG before the request, and undecodable images raise a clear error.
- Footer now displays the correct app version. `web/package.json` version was left at the default `0.0.0`, which Vite injects as `__APP_VERSION__` and the footer renders; bumped it to `0.1.1` to match the release.

## [0.1.1] - 2026-07-08

### Security
- Bumped dependencies via Dependabot (consolidated): raised Python floors (fastapi 0.139.0, uvicorn 0.51.0, markdown 3.10.2, coverage 7.15.0, respx 0.23.1), web devDependencies (@types/node 26.1.1, @vitest/coverage-v8 4.1.10, typescript-eslint 8.63.0, vite 8.1.3, vitest 4.1.10), and pinned GitHub Actions (docker setup-buildx 4.2.0, docker login 4.4.0, docker build-push 7.3.0, codeql-action 4.37.0, astral-sh/setup-uv 8.3.2).
- Earlier Dependabot batch: pinned GitHub Actions (checkout, upload-artifact, docker login/setup-buildx/metadata) and raised Python (fastapi, uvicorn, cairosvg, passlib, python-multipart) and web npm floors.

## [0.1.0] - 2026-06-30

### Added
- Token-secured shared portfolio links: opt-in per-portfolio share token gates the public deck so a link without the token returns a 404; a valid token sets a cookie so the recipient can revisit without re-pasting it. Admins can require, regenerate, disable, and copy the link from the portfolio editor. Live server only — static exports remain unlisted.

## 2026-06-20

### Added
- CSV batch metadata editing: export catalogue metadata to CSV, re-import edits with a preview of pending changes, and per-import lz4 backups.

### Changed
- Updated repository links and footer.

### Security
- Hardened Docker secret defaults.
- Hardened request throttling, archive downloads, and exports.
- Added revocable sessions and CSRF protection.
- Hardened the secret key handling and gated storage access.

## 2026-06-19

### Added
- Floating activity tray that tracks long-running background work (uploads, batch and single-item LLM descriptions) across page navigation.

### Changed
- Cookies default to insecure over plain HTTP for LAN/local testing.
- Updated README.

## 2026-06-18

### Added
- Multi-user mode with admin and read-only reader roles.
- Username-based login, reader downloads, an HTML 404 page, and a diagnostics endpoint/report.
- Full-text metadata search across title, notes, tags, and flattened item metadata.
- Per-item JSON-LD export (schema.org / Dublin Core) with the persistent item ID embedded for FAIR-style harvesting.
- Batch LLM description button with per-batch API key prompt.

### Changed
- Session signing key is now generated at the Docker entrypoint; LLM API URL is parsed and completed as needed.
- Raised the LLM request timeout to 90 seconds.
- Strip LLM reasoning from generated descriptions.

### Fixed
- lz4 raw file download served correctly.

## 2026-06-16

### Added
- Media folder support.

## 2026-06-15

### Added
- Bulk item actions and a printable slide deck.
- Slug generation, LLM Markdown fallback, item navigation, and an appearance API.
- Icon mark, login logo, and collapsible item filters.
- Multi-library storage support for keeping assets on different disks or paths.
- Secrets implementation, footer, and license.

### Security
- Initial security hardening from an audit.

## 2026-06-14

### Added
- Web server backend with database, Docker support, and a settings page.
- Upload queue, LLM toggle, Markdown deck, and bind-mount support.
- Grid redesign and theming.

### Changed
- Moved the legacy static-site pipeline to `legacy/`.

### Fixed
- Thumbnail cropping for all aspect ratios.

## 2026-06-13

### Added
- Initial repository scaffold with configuration examples.
- ZIP ingestion with generated item IDs and a multi-image preview notice.
- LLM item description generator.
- `catalogcanvas` CLI with an init wizard.
- Static site build command.
- Project README and usage docs.
