#!/usr/bin/env bash
# Per-file coverage runner (resumable).
#
# Why: `vitest run --coverage` over the whole suite spikes to 4GB+ and OOMs on
# low-RAM machines. This runs coverage one test file at a time in its own
# single-fork process (memory freed between files), writes a per-file Istanbul
# JSON report, then merges them into total line/function/branch/statement %.
#
# Resumable: each completed test file is appended to .coverage-tmp/done.log.
# Re-running skips anything already there, so you can Ctrl-C and continue later.
# Pass --fresh to wipe progress and start over.
#
# Runs up to JOBS files concurrently (default 4) — each vitest process peaks
# well under 1GB, so 4 in parallel stays safe on a 16GB machine while finishing
# ~4x faster than serial. Override with: JOBS=6 bash src/test/coverage-per-file.sh
#
# Usage (from web/):  bash src/test/coverage-per-file.sh [--fresh]
set -uo pipefail

cd "$(dirname "$0")/../.." || exit 1   # -> web/

JOBS="${JOBS:-4}"
# Per-file wall-clock cap. Some tests intentionally leave a pending promise
# (e.g. a "loading state" test with a promise that never resolves), which makes
# vitest hang on teardown when run in isolation. The coverage report is written
# before that hang, so we cap each run and accept the report if it landed.
RUN_TIMEOUT="${RUN_TIMEOUT:-90}"
TMP="src/test/.coverage-tmp"
DONE="$TMP/done.log"
FAILED="$TMP/failed.log"

# Pick a timeout binary if available (coreutils `timeout`/`gtimeout`); else none.
TIMEOUT_BIN=""
for c in timeout gtimeout; do
  if command -v "$c" >/dev/null 2>&1; then TIMEOUT_BIN="$c"; break; fi
done

if [[ "${1:-}" == "--fresh" ]]; then
  rm -rf "$TMP"
fi
mkdir -p "$TMP"
: >"$FAILED"          # reset failure list each run (done.log is preserved)
touch "$DONE"

# Test files excluded from per-file coverage. These run fine in the full suite
# (npm test), but hang on teardown when run in isolation with --coverage because
# they hold a pending promise (a "loading state" test), so v8 never flushes a
# report. The merged totals stay above threshold without them.
EXCLUDE=(
  "src/pages/Settings.test.tsx"
)
is_excluded() {
  for e in "${EXCLUDE[@]}"; do [[ "$1" == "$e" ]] && return 0; done
  return 1
}

# Discover test files (tracked + untracked, excluding deleted).
# Portable to bash 3.2 (macOS default) — no mapfile.
TEST_FILES=()
while IFS= read -r line; do
  [[ -n "$line" ]] || continue
  is_excluded "$line" && { echo "skip (excluded): $line"; continue; }
  TEST_FILES+=("$line")
done < <(git ls-files --cached --others --exclude-standard \
  '*.test.ts' '*.test.tsx' | grep '^src/' | sort -u)

total=${#TEST_FILES[@]}
if [[ "$total" -eq 0 ]]; then
  echo "No test files found." >&2
  exit 1
fi
# Run coverage for one test file (executed as a background worker).
# Appends a single line to done.log / failed.log — one short line is written
# atomically on a local FS, so concurrent workers don't corrupt the logs.
run_one() {
  tf="$1"; idx="$2"
  safe=$(echo "$tf" | tr '/.' '__')
  report="$TMP/$safe/coverage-final.json"
  echo "[$idx/$total] coverage: $tf"
  # Thresholds are disabled per-file: a single file only covers a few percent of
  # the app, which would otherwise trip the global thresholds and mask real test
  # failures. We measure totals from the merged report instead.
  if [[ -n "$TIMEOUT_BIN" ]]; then
    "$TIMEOUT_BIN" -k 5 "$RUN_TIMEOUT" npx vitest run "$tf" \
        --coverage \
        --pool=forks --maxWorkers=1 \
        --coverage.reporter=json \
        --coverage.reportsDirectory="$TMP/$safe" \
        --coverage.thresholds.lines=0 \
        --coverage.thresholds.functions=0 \
        --coverage.thresholds.branches=0 \
        --coverage.thresholds.statements=0 \
        >"$TMP/$safe.log" 2>&1
    rc=$?
  else
    npx vitest run "$tf" \
        --coverage \
        --pool=forks --maxWorkers=1 \
        --coverage.reporter=json \
        --coverage.reportsDirectory="$TMP/$safe" \
        --coverage.thresholds.lines=0 \
        --coverage.thresholds.functions=0 \
        --coverage.thresholds.branches=0 \
        --coverage.thresholds.statements=0 \
        >"$TMP/$safe.log" 2>&1
    rc=$?
  fi
  # Success if vitest exited clean, OR it timed out but still wrote the report
  # before hanging on teardown (rc 124 = coreutils timeout).
  if [[ "$rc" -eq 0 ]] || { [[ "$rc" -eq 124 ]] && [[ -f "$report" ]]; }; then
    [[ "$rc" -eq 124 ]] && echo "[$idx/$total]   (timed out on teardown; report captured): $tf"
    echo "$tf" >>"$DONE"
  else
    echo "[$idx/$total]   FAILED (rc=$rc, see $TMP/$safe.log): $tf"
    echo "$tf" >>"$FAILED"
  fi
}

i=0
for tf in "${TEST_FILES[@]}"; do
  i=$((i + 1))
  if grep -Fxq "$tf" "$DONE"; then
    echo "[$i/$total] skip (done): $tf"
    continue
  fi
  # Throttle: wait until fewer than JOBS workers are running.
  # Polling (not `wait -n`) for bash 3.2 compatibility.
  while [[ "$(jobs -rp | wc -l | tr -d ' ')" -ge "$JOBS" ]]; do
    sleep 0.3
  done
  run_one "$tf" "$i" &
done
wait

echo
exit_code=0
if [[ -s "$FAILED" ]]; then
  echo "Some files failed:"
  cat "$FAILED"
  exit_code=1
fi

# Integration: a single separate process merges every individual report.
# Decoupled — you can run it alone anytime: node src/test/coverage-merge.mjs
echo "Integrating per-file reports..."
node src/test/coverage-merge.mjs "$TMP" || exit_code=1

# Signal failure so CI doesn't report success when tests or the merge failed.
exit "$exit_code"
