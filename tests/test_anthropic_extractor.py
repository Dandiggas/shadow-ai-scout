import json

import httpx
import pytest

from scout.agentic import AnthropicExtractor, GeminiExtractor, build_extractor
from scout.errors import ScoutAPIError


def _anthropic_response(payload):
    text = json.dumps(payload)
    body = {"content": [{"type": "text", "text": text}]}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "fake"
        assert request.headers["anthropic-version"] == "2023-06-01"
        return httpx.Response(200, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_anthropic_default_model():
    extractor = AnthropicExtractor(api_key="fake", client=_anthropic_response([]))
    assert extractor.model == "claude-sonnet-4-5-20250929"


def test_anthropic_extract_keeps_only_quoted_claims():
    page_text = "Acme does not train models on customer data."
    payload = [
        {
            "risk_category": "Training on customer data",
            "claim_text": "Acme does not train on customer data.",
            "evidence_quote": "does not train models on customer data",
            "severity": 1,
            "confidence": 0.9,
        },
        {
            "risk_category": "Data retention",
            "claim_text": "Hallucinated claim.",
            "evidence_quote": "this quote is not on the page",
            "severity": 3,
            "confidence": 0.5,
        },
    ]
    extractor = AnthropicExtractor(api_key="fake", client=_anthropic_response(payload))

    claims = extractor.extract("Acme AI", "https://acme.ai/privacy", "privacy", page_text, "Security company")

    assert len(claims) == 1
    assert claims[0].risk_category == "Training on customer data"
    assert claims[0].evidence_quote == "does not train models on customer data"


def test_anthropic_invalid_key_raises_scout_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid x-api-key"}})

    extractor = AnthropicExtractor(api_key="fake", client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(ScoutAPIError) as exc:
        extractor.extract("Acme AI", "https://acme.ai/privacy", "privacy", "page", "ctx")

    assert exc.value.provider == "Anthropic"
    assert "ANTHROPIC_API_KEY" in exc.value.user_message


def test_build_extractor_selects_anthropic(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    assert isinstance(build_extractor(), AnthropicExtractor)


def test_build_extractor_defaults_to_anthropic_when_key_present(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    assert isinstance(build_extractor(), AnthropicExtractor)


def test_build_extractor_falls_back_to_gemini(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    assert isinstance(build_extractor(), GeminiExtractor)
