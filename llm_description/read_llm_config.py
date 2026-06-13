"""
read_llm_config.py — print config/config.toml's [llm] section as shell assignments.

Usage: python3 read_llm_config.py <config_toml_path>
Prints KEY=value lines (suitable for `eval`) for: MODEL, API_URL, ITEM_TYPE,
SUMMARY_FOCUS, API_KEY_ENV. Prints nothing if the file or [llm] section is missing.
"""

import sys
import tomllib

config_path = sys.argv[1]

try:
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
except FileNotFoundError:
    sys.exit(0)

llm = data.get("llm", {})

mapping = {
    "model": "MODEL",
    "api_url": "API_URL",
    "item_type": "ITEM_TYPE",
    "summary_focus": "SUMMARY_FOCUS",
    "api_key_env": "API_KEY_ENV",
}

for toml_key, shell_var in mapping.items():
    if toml_key in llm:
        value = str(llm[toml_key]).replace("'", "'\\''")
        print(f"{shell_var}='{value}'")
