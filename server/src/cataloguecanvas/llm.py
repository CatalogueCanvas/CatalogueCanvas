from __future__ import annotations
import base64
import ipaddress
import json
import re
import socket
import tomllib
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from PIL import Image

PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent / "prompt.template.toml"

# Cloud metadata endpoints (AWS/GCP/Azure/DigitalOcean) live in the link-local
# range and are never legitimate LLM API targets, unlike localhost/LAN
# addresses which self-hosted setups (Ollama, LM Studio) commonly use.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fd00:ec2::254/128"),
]


class LLMError(Exception):
    pass


def _encode_jpeg_data(image_bytes: bytes) -> str:
    """Transcode arbitrary image bytes to base64 JPEG.

    Previews are stored as WebP, but the request labels the image as
    ``data:image/jpeg`` and LM Studio's endpoint accepts only jpeg/png. Sending
    raw WebP bytes under a jpeg label fails on runtimes that trust the declared
    MIME type, so re-encode to real JPEG to make the bytes match the label.
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        buf = BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=85)
    except (OSError, ValueError) as exc:
        raise LLMError(f"could not decode preview image for LLM request: {exc}") from exc
    return base64.b64encode(buf.getvalue()).decode()


def _snippet(text: str, limit: int = 300) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _normalize_api_url(api_url: str) -> str:
    """Allow users to enter just a host/port and fill in the OpenAI path.

    A bare base URL (``http://host:1234``) or a ``/v1`` root is completed to
    ``/v1/chat/completions``. A URL that already targets the completions
    endpoint, or carries any other deliberate path, is left untouched.
    """
    api_url = (api_url or "").strip().rstrip("/")
    parsed = urlparse(api_url)
    path = parsed.path

    if "/chat/completions" in path:
        return api_url
    if path in ("", "/"):
        suffix = "/v1/chat/completions"
    elif path == "/v1":
        suffix = "/chat/completions"
    else:
        # Some other explicit path — respect it rather than guessing.
        return api_url
    return api_url + suffix


def _validate_api_url(api_url: str) -> None:
    from .settings import settings

    parsed = urlparse(api_url)
    if parsed.scheme not in ("http", "https"):
        raise LLMError("api_url must use http or https")
    if not parsed.hostname:
        raise LLMError("api_url is missing a host")
    if settings.llm_allowed_hosts and parsed.hostname.lower() not in settings.llm_allowed_hosts:
        raise LLMError(
            f"api_url host {parsed.hostname!r} is not in CC_LLM_ALLOWED_HOSTS"
        )
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise LLMError(f"could not resolve api_url host: {exc}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        for net in _BLOCKED_NETWORKS:
            if ip in net:
                raise LLMError("api_url resolves to a blocked address (link-local/metadata range)")


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
    timeout: float = 90.0,
) -> dict[str, Any]:
    """Call an OpenAI-compatible vision chat completions API for a single image.

    The api_key, if provided, is used only for this request's Authorization
    header and is never persisted.
    """
    api_url = _normalize_api_url(api_url)
    _validate_api_url(api_url)

    try:
        prompt = _build_prompt(item_type, summary_focus, bullet_count, bullet_max_words, prompt_template)
    except (tomllib.TOMLDecodeError, KeyError) as exc:
        raise LLMError(f"invalid prompt template: {exc}") from exc
    b64 = _encode_jpeg_data(image_bytes)

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
        resp = httpx.post(api_url, json=payload, headers=headers, timeout=timeout, follow_redirects=False)
    except httpx.HTTPError as exc:
        raise LLMError(f"LLM request failed: could not reach {api_url}: {exc}") from exc

    if resp.status_code >= 400:
        raise LLMError(f"LLM request failed: HTTP {resp.status_code} from {api_url}: {_snippet(resp.text)}")

    try:
        data = resp.json()
    except ValueError as exc:
        raise LLMError(f"LLM request failed: response was not JSON: {_snippet(resp.text)}") from exc

    choices = data.get("choices") if isinstance(data, dict) else None
    if not choices:
        # A 200 with no choices usually means the endpoint returned an error
        # object (model not loaded, bad request) or is the wrong URL/shape.
        api_error = data.get("error") if isinstance(data, dict) else None
        detail = api_error if api_error is not None else data
        raise LLMError(f"LLM request failed: response has no 'choices': {_snippet(json.dumps(detail))}")

    try:
        content = choices[0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise LLMError(f"LLM request failed: unexpected choices shape: {_snippet(json.dumps(choices))}") from exc

    content = _strip_reasoning(content)

    if content.startswith("```"):
        content = "\n".join(line for line in content.splitlines() if not line.startswith("```"))

    inner = _extract_json_object(content)
    if inner is not None and ("descriptions" in inner or "summary" in inner):
        return {
            "descriptions": inner.get("descriptions", []),
            "summary": inner.get("summary", ""),
        }

    return _parse_markdown_response(content)


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_reasoning(content: str) -> str:
    """Remove chain-of-thought emitted by 'thinking' models.

    Handles explicit <think>...</think> blocks, and the common case where a
    model leaves an unterminated <think> with the real answer after it.
    """
    content = _THINK_RE.sub("", content)
    # Unterminated <think> (no closing tag): drop everything up to the last one.
    lower = content.lower()
    if "<think>" in lower:
        content = content[lower.rfind("<think>") + len("<think>"):]
    return content.strip()


def _extract_json_object(content: str) -> dict[str, Any] | None:
    """Return the last decodable top-level JSON object in the text, if any.

    Scans every '{' and keeps the last one that parses, so reasoning prose
    containing stray braces before the real JSON answer doesn't win.
    """
    decoder = json.JSONDecoder()
    found: dict[str, Any] | None = None
    idx = content.find("{")
    while idx != -1:
        try:
            obj, _ = decoder.raw_decode(content, idx)
            if isinstance(obj, dict):
                found = obj
        except json.JSONDecodeError:
            pass
        idx = content.find("{", idx + 1)
    return found


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
