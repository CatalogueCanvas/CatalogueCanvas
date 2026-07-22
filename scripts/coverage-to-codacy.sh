#!/usr/bin/env bash
#
# Regenerate coverage for both the Python server and the web frontend, then push
# the reports to Codacy. Mirrors what .github/workflows/coverage.yml does in CI,
# but runs locally end-to-end.
#
# Requirements:
#   - uv          (Python deps + pytest)
#   - npm / node  (web deps + vitest)
#   - secret.toml (repo root, gitignored) with the project token:
#         [codacy_project_token]
#         token="xxxx"
#
# Usage:
#   ./scripts/coverage-to-codacy.sh [--auto|--yes|--skip-regenerate]
#
#   --auto, --yes       regenerate coverage without prompting
#   --skip-regenerate   upload the reports already on disk
#   (no argument)       prompt interactively
#
set -euo pipefail

# Pinned so the uploaded binary is immutable and checksum-verifiable. Codacy's
# rolling get.sh installer publishes no checksum, so we fetch the release asset.
CODACY_REPORTER_VERSION="14.1.3"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SECRET_FILE="$REPO_ROOT/secret.toml"

if [[ ! -f "$SECRET_FILE" ]]; then
  echo "ERROR: $SECRET_FILE not found." >&2
  exit 1
fi

# Read token= from the [codacy_project_token] section of the TOML file.
CODACY_PROJECT_TOKEN="$(
  awk '
    /^\[/                  { in_section = ($0 ~ /\[codacy_project_token\]/) }
    in_section && /token[[:space:]]*=/ {
      # Trim only the edges: a token may legitimately contain spaces.
      sub(/^[^=]*=[[:space:]]*/, "");
      sub(/^[[:space:]]*"/, ""); sub(/"[[:space:]]*$/, "");
      sub(/^[[:space:]]+/, "");  sub(/[[:space:]]+$/, "");
      print; exit
    }
  ' "$SECRET_FILE"
)"

if [[ -z "$CODACY_PROJECT_TOKEN" ]]; then
  echo "ERROR: [codacy_project_token].token not found in $SECRET_FILE." >&2
  exit 1
fi
export CODACY_PROJECT_TOKEN

REGENERATE=""
case "${1:-}" in
  --auto|--yes)       REGENERATE="true" ;;
  --skip-regenerate)  REGENERATE="false" ;;
  -h|--help)
    echo "Usage: ./scripts/coverage-to-codacy.sh [--auto|--yes|--skip-regenerate]"
    exit 0
    ;;
  "") ;;
  *)
    echo "ERROR: Unknown argument: $1" >&2
    echo "Usage: ./scripts/coverage-to-codacy.sh [--auto|--yes|--skip-regenerate]" >&2
    exit 1
    ;;
esac

# Ask whether to regenerate coverage, or reuse the reports already on disk.
# In non-interactive contexts pass --auto/--yes or --skip-regenerate.
if [[ -z "$REGENERATE" ]]; then
  read -r -p "Regenerate coverage reports before uploading? [y/N] " ans
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    REGENERATE="true"
  else
    REGENERATE="false"
  fi
fi

if [[ "$REGENERATE" == "true" ]]; then
  echo "==> Server coverage (pytest)"
  cd "$REPO_ROOT/server"
  uv sync --group dev
  uv run pytest --cov --cov-report=xml:coverage.xml

  echo "==> Web coverage (vitest, per-file to avoid OOM)"
  cd "$REPO_ROOT/web"
  npm ci
  bash src/test/coverage-per-file.sh --fresh
else
  echo "==> Skipping regeneration; using existing reports."
fi

echo "==> Fetching Codacy coverage reporter $CODACY_REPORTER_VERSION"
case "$(uname -s)" in
  Darwin) CODACY_ASSET="codacy-coverage-reporter-darwin" ;;
  Linux)  CODACY_ASSET="codacy-coverage-reporter-linux" ;;
  *)
    echo "ERROR: Unsupported platform: $(uname -s)" >&2
    exit 1
    ;;
esac

CODACY_TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$CODACY_TMP_DIR"' EXIT
CODACY_BASE_URL="https://github.com/codacy/codacy-coverage-reporter/releases/download/$CODACY_REPORTER_VERSION"

curl --fail --show-error --location --silent \
  "$CODACY_BASE_URL/$CODACY_ASSET" -o "$CODACY_TMP_DIR/$CODACY_ASSET"
curl --fail --show-error --location --silent \
  "$CODACY_BASE_URL/$CODACY_ASSET.SHA512SUM" -o "$CODACY_TMP_DIR/$CODACY_ASSET.SHA512SUM"

# The checksum file names the asset without a path, so verify from inside the dir.
(cd "$CODACY_TMP_DIR" && shasum -a 512 -c "$CODACY_ASSET.SHA512SUM")
chmod +x "$CODACY_TMP_DIR/$CODACY_ASSET"

echo "==> Uploading both reports to Codacy"
cd "$REPO_ROOT"
"$CODACY_TMP_DIR/$CODACY_ASSET" report \
  --force-coverage-parser cobertura -r server/coverage.xml \
  --force-coverage-parser lcov   -r web/coverage/lcov.info

echo "==> Done."
