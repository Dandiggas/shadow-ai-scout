from scout.agentic import GeminiExtractor


def test_gemini_default_model_is_current_generate_content_model(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    extractor = GeminiExtractor(api_key="fake", client=None)

    assert extractor.model == "gemini-2.0-flash"
