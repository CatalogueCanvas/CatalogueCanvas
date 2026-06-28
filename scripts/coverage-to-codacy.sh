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
#   ./scripts/coverage-to-codacy.sh
#
set -euo pipefail

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
      sub(/^[^=]*=[[:space:]]*/, ""); gsub(/"/, ""); gsub(/[[:space:]]/, "");
      print; exit
    }
  ' "$SECRET_FILE"
)"

if [[ -z "$CODACY_PROJECT_TOKEN" ]]; then
  echo "ERROR: [codacy_project_token].token not found in $SECRET_FILE." >&2
  exit 1
fi
export CODACY_PROJECT_TOKEN

# Ask whether to regenerate coverage, or reuse the reports already on disk.
read -r -p "Regenerate coverage reports before uploading? [y/N] " ans
if [[ "$ans" =~ ^[Yy]$ ]]; then
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

echo "==> Uploading both reports to Codacy"
cd "$REPO_ROOT"
bash <(curl -Ls https://coverage.codacy.com/get.sh) report \
  --force-coverage-parser cobertura -r server/coverage.xml \
  --force-coverage-parser lcov   -r web/coverage/lcov.info

echo "==> Done."
