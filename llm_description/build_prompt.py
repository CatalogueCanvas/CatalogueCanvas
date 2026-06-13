"""
build_prompt.py — render prompt.template.toml into a flat prompt string.

Usage: python3 build_prompt.py <prompt_template.toml> <item_type> <summary_focus>
Prints the rendered prompt to stdout.
"""

import sys
import tomllib

template_path, item_type, summary_focus = sys.argv[1:]

with open(template_path, "rb") as f:
    template = tomllib.load(f)

schema = template["output_schema"]
instructions = template["instructions"]

schema_str = ", ".join(f'"{k}": <{v}>' for k, v in schema.items())
constraints_str = " ".join(
    f"{i + 1}) {c}" for i, c in enumerate(instructions["constraints"])
)

prompt = (
    f"{instructions['task']} "
    f"The JSON object should look like: {{{schema_str}}}. "
    f"Constraints: {constraints_str}"
)

prompt = prompt.replace("{item_type}", item_type).replace("{summary_focus}", summary_focus)
print(prompt)
