import httpx
import pytest

from scout.agentic import GeminiExtractor, TavilySearcher
from scout.errors import ScoutAPIError


class FakeClient:
    def __init__(self, response):
        self.response = response

    def post(self, *args, **kwargs):
        return self.response


def test_tavily_401_becomes_clean_key_error():
    request = httpx.Request("POST", "https://api.tavily.com/search")
    response = httpx.Response(401, request=request, text="Unauthorized")
    searcher = TavilySearcher(api_key="bad-key", client=FakeClient(response))

    with pytest.raises(ScoutAPIError) as exc:
        searcher.search("Cursor privacy")

    assert exc.value.provider == "Tavily"
    assert "regenerate" in exc.value.user_message.lower()
    assert "api.tavily.com" in exc.value.detail


def test_gemini_bad_key_becomes_clean_key_error():
    request = httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent")
    response = httpx.Response(400, request=request, text="API key not valid")
    extractor = GeminiExtractor(api_key="AQ-bad", client=FakeClient(response))

    with pytest.raises(ScoutAPIError) as exc:
        extractor.extract("Cursor", "https://cursor.com/privacy", "privacy", "Some source text", "Company policy")

    assert exc.value.provider == "Gemini"
    assert "AIza" in exc.value.user_message
