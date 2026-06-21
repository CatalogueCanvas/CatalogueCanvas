# Changelog

All notable changes to CatalogueCanvas are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project has not yet tagged a release; entries are grouped by date.

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
