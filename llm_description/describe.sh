#!/usr/bin/env bash
# describe.sh — generate LLM descriptions for all catalog items.
#
# Loops over output/items/*/preview.webp, calls an OpenAI-compatible vision
# LLM API (local, e.g. LM Studio, or remote) for each, and merges results
# into llm_descriptions.json. Existing entries are preserved; only new items
# are processed unless --force is passed.
#
# Configuration precedence: environment variables > config/config.toml [llm]
# section > hardcoded defaults for local LM Studio.
#   LLM_MODEL          model name (default: google/gemma-4-12b-qat)
#   LLM_API_URL        OpenAI-compatible chat completions endpoint
#                       (default: http://localhost:1234/v1/chat/completions)
#   LLM_PROMPT_FILE    prompt template path (default: prompt.template.toml)
#   LLM_ITEM_TYPE      substituted into {item_type} in the prompt template
#   LLM_SUMMARY_FOCUS  substituted into {summary_focus} in the prompt template
#   LLM_API_KEY_ENV    name of env var holding an API key, sent as a Bearer token
#
# Usage: bash describe.sh [--force]
#   --force  Re-process items already present in the JSON

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$REPO_ROOT/llm_description"
ITEMS_DIR="$REPO_ROOT/output/items"
OUTPUT_JSON="$SCRIPT_DIR/llm_descriptions.json"
CONFIG_TOML="$REPO_ROOT/config/config.toml"

# Load [llm] section from config/config.toml, if present
eval "$(python3 "$SCRIPT_DIR/read_llm_config.py" "$CONFIG_TOML")"

MODEL="${LLM_MODEL:-${MODEL:-google/gemma-4-12b-qat}}"
API_URL="${LLM_API_URL:-${API_URL:-http://localhost:1234/v1/chat/completions}}"
PROMPT_FILE="${LLM_PROMPT_FILE:-$SCRIPT_DIR/prompt.template.toml}"
ITEM_TYPE="${LLM_ITEM_TYPE:-${ITEM_TYPE:-image}}"
DEFAULT_SUMMARY_FOCUS="the item's notable characteristics"
SUMMARY_FOCUS="${LLM_SUMMARY_FOCUS:-${SUMMARY_FOCUS:-$DEFAULT_SUMMARY_FOCUS}}"
API_KEY_ENV="${LLM_API_KEY_ENV:-${API_KEY_ENV:-}}"

# Load the prompt template (TOML) and substitute placeholders
PROMPT=$(python3 "$SCRIPT_DIR/build_prompt.py" "$PROMPT_FILE" "$ITEM_TYPE" "$SUMMARY_FOCUS")

# Parse flags
FORCE=0
for arg in "$@"; do [ "$arg" = "--force" ] && FORCE=1; done

# Ensure the output file exists so merge_entry.py always finds it
[ -f "$OUTPUT_JSON" ] || echo "{}" > "$OUTPUT_JSON"

processed=0; skipped=0; failed=0

for item_dir in "$ITEMS_DIR"/*/; do
    item_id=$(basename "$item_dir")
    preview_path="$item_dir/preview.webp"

    # Skip items with no preview image
    [ ! -f "$preview_path" ] && continue

    # Skip items already described unless --force
    if [ $FORCE -eq 0 ]; then
        already=$(python3 -c "import json; d=json.load(open('$OUTPUT_JSON')); print('yes' if '$item_id' in d else 'no')")
        [ "$already" = "yes" ] && { skipped=$((skipped+1)); continue; }
    fi

    echo -n "→ $item_id ... "

    # Rescale to 512px wide before sending to the LLM to keep payload small
    tmp_preview="$(mktemp /tmp/describe_XXXXXX).webp"
    if ! magick "$preview_path" -resize 512x512\> "$tmp_preview" 2>/dev/null; then
        echo "WARN: failed to resize $preview_path (corrupt or empty?)"
        failed=$((failed+1))
        rm -f "$tmp_preview"
        continue
    fi

    # Call the API; on success pipe the entry into the merge script
    if entry=$(python3 "$SCRIPT_DIR/describe_one.py" "$tmp_preview" "$item_id" "$MODEL" "$API_URL" "$PROMPT" "$API_KEY_ENV" 2>&1); then
        echo "$entry" | python3 "$SCRIPT_DIR/merge_entry.py" "$OUTPUT_JSON" "$item_id"
        echo "done"
        processed=$((processed+1))
    else
        echo "WARN: $entry"
        failed=$((failed+1))
    fi
    rm -f "$tmp_preview"
done

echo ""
echo "Done — $processed processed, $skipped skipped (already described), $failed failed"
echo "Output: $OUTPUT_JSON"
