# CatalogCanvas

A domain-agnostic ingestion and static-site-generator pipeline. Drop any files into an ingestion folder, curate metadata via TOML overrides, and generate a static catalog site.

## Layout

```
config/                  example config files (copy to config.toml / catalog.toml)
ingestion/                drop input items here (configurable via [paths] ingestion_dir)
output/                   generated site + per-item assets (configurable via [paths] output_dir)
templates/                Jinja2 templates for the static site
llm_description/          LLM-based per-item description generator (see below)
pipeline/                 uv project: catalogcanvas CLI (catalog init, ...)
```

## Setup

From `pipeline/`, run the interactive configuration wizard:

```bash
cd pipeline
uv sync
uv run catalog init
```

This asks for the catalog title, input/output folders, database path, optional backup folder, build settings, and LLM provider/model/prompt preferences, then writes `config/config.toml`. Re-run `catalog init` any time to update the configuration (it will ask before overwriting).

## LLM item descriptions

`llm_description/` generates per-item descriptions using a vision-capable LLM (local, e.g. LM Studio or Ollama, or any remote OpenAI-compatible API such as OpenAI, Anthropic, or Gemini).

```bash
bash llm_description/describe.sh [--force]
```

Configuration precedence: environment variables > `config/config.toml` `[llm]` section (written by `catalog init`) > hardcoded defaults for local LM Studio.

| Variable | `[llm]` key | Default | Purpose |
|---|---|---|---|
| `LLM_MODEL` | `model` | `google/gemma-4-12b-qat` | model name passed to the API |
| `LLM_API_URL` | `api_url` | `http://localhost:1234/v1/chat/completions` | OpenAI-compatible chat completions endpoint |
| `LLM_ITEM_TYPE` | `item_type` | `image` | substituted into `{item_type}` in the prompt |
| `LLM_SUMMARY_FOCUS` | `summary_focus` | `the item's notable characteristics` | substituted into `{summary_focus}` in the prompt |
| `LLM_API_KEY_ENV` | `api_key_env` | _(none)_ | name of an env var holding an API key, sent as `Authorization: Bearer <key>` |
| `LLM_PROMPT_FILE` | _(none)_ | `llm_description/prompt.template.toml` | prompt template (TOML) |

The script loops over `output/items/*/preview.webp`, calls the LLM for each, and merges results into `llm_description/llm_descriptions.json`. Items already present in that file are skipped unless `--force` is passed.

Example for a remote OpenAI-compatible endpoint with custom focus, overriding `config/config.toml` for one run:

```bash
LLM_API_URL="https://api.example.com/v1/chat/completions" \
LLM_MODEL="gpt-4o-mini" \
LLM_ITEM_TYPE="product photo" \
LLM_SUMMARY_FOCUS="the product's condition and notable features" \
LLM_API_KEY_ENV="OPENAI_API_KEY" \
bash llm_description/describe.sh
```

To customize the prompt structure itself, edit `llm_description/prompt.template.toml`.
