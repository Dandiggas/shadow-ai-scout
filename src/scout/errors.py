from __future__ import annotations


class ScoutAPIError(RuntimeError):
    """User-safe API failure with provider-specific remediation."""

    def __init__(self, provider: str, user_message: str, detail: str = ""):
        self.provider = provider
        self.user_message = user_message
        self.detail = detail
        super().__init__(f"{provider}: {user_message}" + (f" ({detail})" if detail else ""))


def provider_key_error(provider: str, status_code: int, detail: str) -> ScoutAPIError:
    if provider == "Tavily":
        msg = (
            "Tavily rejected the API key. Regenerate a valid key at https://app.tavily.com/ "
            "and update TAVILY_API_KEY in .env."
        )
    elif provider == "Gemini":
        msg = (
            "Gemini rejected the API key. Google AI Studio keys usually start with AIza; "
            "regenerate one at https://aistudio.google.com/apikey and update GEMINI_API_KEY in .env."
        )
    else:
        msg = f"{provider} rejected the API request. Check the configured API key."
    return ScoutAPIError(provider, msg, f"HTTP {status_code}: {detail[:300]}")
