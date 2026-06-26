import pytest

from scout.agentic import AgenticScanner, SearchResult
from scout.errors import ScoutAPIError


class OneResultSearcher:
    def search(self, query: str, max_results: int = 5):
        return [SearchResult("Cursor Privacy", "https://cursor.com/privacy", "privacy")]


class TextFetcher:
    def fetch_text(self, url: str) -> str:
        return "Cursor privacy page text"


class QuotaExtractor:
    def extract(self, tool_name: str, source_url: str, source_type: str, page_text: str, company_context: str):
        raise ScoutAPIError("Gemini", "Gemini quota exhausted. Check billing/quota or use another key.", "HTTP 429")


def test_agentic_scan_propagates_provider_errors_instead_of_fake_verdict(tmp_path):
    scanner = AgenticScanner(searcher=OneResultSearcher(), fetcher=TextFetcher(), extractor=QuotaExtractor())

    with pytest.raises(ScoutAPIError) as exc:
        scanner.scan(["Cursor"], "Company policy", tmp_path, max_iterations=1)

    assert exc.value.provider == "Gemini"
    assert "quota" in exc.value.user_message.lower()
