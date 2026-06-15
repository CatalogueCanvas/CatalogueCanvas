from __future__ import annotations
import base64
import json
import re
import tomllib
from pathlib import Path
from typing import Any

import httpx

PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent / "prompt.template.toml"


class LLMError(Exception):
    pass


def default_prompt_template() -> str:
    return PROMPT_TEMPLATE_PATH.read_text()


def _build_prompt(item_type: str, summary_focus: str, bullet_count: int, bullet_max_words: int, template_text: str | None = None) -> str:
    if template_text:
        template = tomllib.loads(template_text)
    else:
        with open(PROMPT_TEMPLATE_PATH, "rb") as f:
            template = tomllib.load(f)

    schema = template["output_schema"]
    instructions = template["instructions"]

    schema_str = ", ".join(f'"{k}": <{v}>' for k, v in schema.items())
    constraints_str = " ".join(
        f"{i + 1}) {c}" for i, c in enumerate(instructions["constraints"])
    )

    prompt = (
        f"{instructions['task']} "
        f"If responding with JSON, it should look like: {{{schema_str}}}. "
        f"Constraints: {constraints_str}"
    )
    return (
        prompt
        .replace("{item_type}", item_type)
        .replace("{summary_focus}", summary_focus)
        .replace("{bullet_count}", str(bullet_count))
        .replace("{bullet_max_words}", str(bullet_max_words))
    )


def describe(
    image_bytes: bytes,
    api_url: str,
    model: str,
    item_type: str = "image",
    summary_focus: str = "the item's notable characteristics",
    bullet_count: int = 3,
    bullet_max_words: int = 50,
    prompt_template: str | None = None,
    api_key: str | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Call an OpenAI-compatible vision chat completions API for a single image.

    The api_key, if provided, is used only for this request's Authorization
    header and is never persisted.
    """
    try:
        prompt = _build_prompt(item_type, summary_focus, bullet_count, bullet_max_words, prompt_template)
    except (tomllib.TOMLDecodeError, KeyError) as exc:
        raise LLMError(f"invalid prompt template: {exc}") from exc
    b64 = base64.b64encode(image_bytes).decode()

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }
        ],
        "temperature": 0,
        "reasoning": {"exclude_thinking": True},
    }

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = httpx.post(api_url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc

    if content.startswith("```"):
        content = "\n".join(line for line in content.splitlines() if not line.startswith("```"))

    start = content.find("{")
    if start != -1:
        try:
            inner, _ = json.JSONDecoder().raw_decode(content, start)
            return {
                "descriptions": inner.get("descriptions", []),
                "summary": inner.get("summary", ""),
            }
        except json.JSONDecodeError:
            pass

    return _parse_markdown_response(content)


_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.*)")


def _parse_markdown_response(content: str) -> dict[str, Any]:
    """Fall back to plain-text/markdown parsing when the LLM doesn't return JSON.

    Bullet list lines (-, *, or numbered) become `descriptions`; the remaining
    non-empty lines are joined as `summary`.
    """
    descriptions: list[str] = []
    summary_lines: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _BULLET_RE.match(line)
        if match:
            descriptions.append(match.group(1).strip())
        else:
            summary_lines.append(stripped)

    return {
        "descriptions": descriptions,
        "summary": " ".join(summary_lines),
    }
