from __future__ import annotations

import json
from io import BytesIO

import httpx
import pytest
import respx
from PIL import Image

from cataloguecanvas import llm


def _webp_bytes() -> bytes:
    """A minimal but real WebP image, mirroring how previews are stored."""
    buf = BytesIO()
    Image.new("RGB", (4, 4), (200, 100, 50)).save(buf, format="WEBP")
    return buf.getvalue()


# --- _normalize_api_url ---

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("http://host:1234", "http://host:1234/v1/chat/completions"),
        ("http://host:1234/", "http://host:1234/v1/chat/completions"),
        ("http://host:1234/v1", "http://host:1234/v1/chat/completions"),
        ("http://host/v1/chat/completions", "http://host/v1/chat/completions"),
        ("http://host/custom/path", "http://host/custom/path"),
        ("  http://host/v1/  ", "http://host/v1/chat/completions"),
    ],
)
def test_normalize_api_url(raw, expected):
    assert llm._normalize_api_url(raw) == expected


# --- _validate_api_url ---

def test_validate_api_url_rejects_bad_scheme():
    with pytest.raises(llm.LLMError, match="http or https"):
        llm._validate_api_url("ftp://host/x")


def test_validate_api_url_requires_host():
    with pytest.raises(llm.LLMError, match="missing a host"):
        llm._validate_api_url("http:///path")


def test_validate_api_url_blocks_link_local(monkeypatch):
    monkeypatch.setattr(
        llm.socket, "getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("169.254.169.254", 0))],
    )
    with pytest.raises(llm.LLMError, match="blocked address"):
        llm._validate_api_url("http://metadata.example/v1/chat/completions")


def test_validate_api_url_allows_normal_host(monkeypatch):
    monkeypatch.setattr(
        llm.socket, "getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )
    llm._validate_api_url("http://example.com/v1/chat/completions")


def test_validate_api_url_resolution_failure(monkeypatch):
    def boom(*a, **k):
        raise llm.socket.gaierror("nope")
    monkeypatch.setattr(llm.socket, "getaddrinfo", boom)
    with pytest.raises(llm.LLMError, match="could not resolve"):
        llm._validate_api_url("http://nope.invalid/v1/chat/completions")


def test_validate_api_url_allowed_hosts(monkeypatch):
    monkeypatch.setattr(llm.socket, "getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", ("10.0.0.5", 0))])
    from cataloguecanvas.settings import settings
    monkeypatch.setattr(settings, "llm_allowed_hosts", {"ollama.lan"})
    with pytest.raises(llm.LLMError, match="not in CC_LLM_ALLOWED_HOSTS"):
        llm._validate_api_url("http://other.lan/v1/chat/completions")


# --- _strip_reasoning ---

def test_strip_reasoning_paired_block():
    assert llm._strip_reasoning("<think>hidden</think>answer") == "answer"


def test_strip_reasoning_unterminated_block():
    assert llm._strip_reasoning("prefix <think> the real answer") == "the real answer"


# --- _extract_json_object ---

def test_extract_json_object_last_wins():
    text = 'noise {"a": 1} more {"descriptions": [], "summary": "ok"}'
    assert llm._extract_json_object(text) == {"descriptions": [], "summary": "ok"}


def test_extract_json_object_none():
    assert llm._extract_json_object("no json here") is None


# --- _parse_markdown_response ---

def test_parse_markdown_response_bullets_and_summary():
    content = "- one\n* two\n1. three\nA summary line\nAnother line"
    result = llm._parse_markdown_response(content)
    assert result["descriptions"] == ["one", "two", "three"]
    assert result["summary"] == "A summary line Another line"


# --- _build_prompt / default_prompt_template ---

def test_default_prompt_template_loads():
    assert isinstance(llm.default_prompt_template(), str)
    assert llm.default_prompt_template().strip()


def test_build_prompt_substitutes_placeholders():
    prompt = llm._build_prompt("painting", "the brushwork", 4, 20)
    assert "painting" in prompt
    assert "the brushwork" in prompt
    assert "4" in prompt
    assert "20" in prompt


def test_build_prompt_custom_template():
    tmpl = (
        '[output_schema]\n'
        'descriptions = "list"\n'
        'summary = "string"\n'
        '[instructions]\n'
        'task = "Describe the {item_type}."\n'
        'constraints = ["max {bullet_count}", "under {bullet_max_words} words"]\n'
    )
    prompt = llm._build_prompt("widget", "x", 2, 10, tmpl)
    assert "Describe the widget." in prompt
    assert "max 2" in prompt


# --- describe (mocked HTTP) ---

_URL = "http://example.com/v1/chat/completions"


@pytest.fixture()
def _allow_dns(monkeypatch):
    monkeypatch.setattr(llm.socket, "getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])


def _chat_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


@respx.mock
def test_describe_parses_json_content(_allow_dns):
    payload = json.dumps({"descriptions": ["a", "b"], "summary": "s"})
    respx.post(_URL).mock(return_value=httpx.Response(200, json=_chat_response(payload)))
    out = llm.describe(_webp_bytes(), "http://example.com", "model")
    assert out == {"descriptions": ["a", "b"], "summary": "s"}


@respx.mock
def test_describe_falls_back_to_markdown(_allow_dns):
    respx.post(_URL).mock(
        return_value=httpx.Response(200, json=_chat_response("- bullet one\nA summary")))
    out = llm.describe(_webp_bytes(), "http://example.com", "model")
    assert out["descriptions"] == ["bullet one"]
    assert out["summary"] == "A summary"


@respx.mock
def test_describe_http_error(_allow_dns):
    respx.post(_URL).mock(return_value=httpx.Response(500, text="boom"))
    with pytest.raises(llm.LLMError, match="HTTP 500"):
        llm.describe(_webp_bytes(), "http://example.com", "model")


@respx.mock
def test_describe_no_choices(_allow_dns):
    respx.post(_URL).mock(return_value=httpx.Response(200, json={"error": "model not loaded"}))
    with pytest.raises(llm.LLMError, match="no 'choices'"):
        llm.describe(_webp_bytes(), "http://example.com", "model")


@respx.mock
def test_describe_strips_code_fence(_allow_dns):
    fenced = "```json\n" + json.dumps({"summary": "ok", "descriptions": []}) + "\n```"
    respx.post(_URL).mock(return_value=httpx.Response(200, json=_chat_response(fenced)))
    out = llm.describe(_webp_bytes(), "http://example.com", "model")
    assert out["summary"] == "ok"


@respx.mock
def test_describe_connection_failure(_allow_dns):
    respx.post(_URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(llm.LLMError, match="could not reach"):
        llm.describe(_webp_bytes(), "http://example.com", "model")


def test_describe_invalid_template(_allow_dns):
    with pytest.raises(llm.LLMError, match="invalid prompt template"):
        llm.describe(b"img", "http://example.com", "model", prompt_template="not = [valid")


@respx.mock
def test_describe_transcodes_webp_to_jpeg(_allow_dns):
    """WebP preview bytes must be sent as real JPEG under the image/jpeg label."""
    import base64

    captured: dict = {}

    def _capture(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_chat_response(json.dumps({"summary": "ok", "descriptions": []})))

    respx.post(_URL).mock(side_effect=_capture)
    llm.describe(_webp_bytes(), "http://example.com", "model")

    url = captured["body"]["messages"][0]["content"][1]["image_url"]["url"]
    prefix = "data:image/jpeg;base64,"
    assert url.startswith(prefix)
    # Bytes under the jpeg label must actually be JPEG (start with the SOI marker).
    assert base64.b64decode(url[len(prefix):])[:2] == b"\xff\xd8"


def test_encode_jpeg_data_rejects_non_image():
    with pytest.raises(llm.LLMError, match="could not decode preview image"):
        llm._encode_jpeg_data(b"not an image")
