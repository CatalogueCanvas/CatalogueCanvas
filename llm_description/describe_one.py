"""
describe_one.py — call an OpenAI-compatible vision LLM API (local or remote) for a single item.

Usage: python3 describe_one.py <preview_path> <item_id> <model> <api_url> <prompt> [api_key_env]
Prints a JSON entry to stdout: {image_path, descriptions, summary}
"""

import base64
import json
import os
import sys

import urllib.request

args = sys.argv[1:]
preview_path, item_id, model, api_url, prompt = args[:5]
api_key_env = args[5] if len(args) > 5 else ""

# Encode the preview image as base64; OpenAI-compatible APIs expect data:image/jpeg;base64,<data>
b64 = base64.b64encode(open(preview_path, "rb").read()).decode()

# Build the OpenAI-compatible chat completion request with vision content
req = {
    "model": model,
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64," + b64},
                },
            ],
        }
    ],
    "temperature": 0,
    # Suppress chain-of-thought from appearing in the response content
    "reasoning": {"exclude_thinking": True},
}

headers = {"Content-Type": "application/json"}
if api_key_env:
    api_key = os.environ.get(api_key_env)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

r = urllib.request.urlopen(
    urllib.request.Request(
        api_url,
        data=json.dumps(req).encode(),
        headers=headers,
    )
)
d = json.loads(r.read())
content = d["choices"][0]["message"]["content"].strip()

# Some models wrap output in ```json ... ``` fences despite being asked not to
if content.startswith("```"):
    content = "\n".join(l for l in content.splitlines() if not l.startswith("```"))

inner = json.loads(content)

# Wrap with image_path so the JSON file stays self-contained
entry = {
    "image_path": f"output/items/{item_id}/preview.webp",
    "descriptions": inner.get("descriptions", []),
    "summary": inner.get("summary", ""),
}
print(json.dumps(entry))
