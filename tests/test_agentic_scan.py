from __future__ import annotations

from scout.agentic import AgenticScanner, SearchResult


class FakeSearcher:
    def search(self, query: str, max_results: int = 5):
        if "security" in query.lower() or "trust" in query.lower():
            return [SearchResult("Acme Security", "https://acme.ai/security", "SSO and SOC 2 details")]
        if "pricing" in query.lower():
            return [SearchResult("Acme Pricing", "https://acme.ai/pricing", "Enterprise plan")]
        return [SearchResult("Acme Privacy", "https://acme.ai/privacy", "Privacy and training details")]


class FakeFetcher:
    def fetch_text(self, url: str) -> str:
        if "security" in url:
            return "Acme supports SSO, SAML, admin controls, audit logs, and SOC 2 Type II for enterprise customers."
        if "pricing" in url:
            return "Enterprise pricing includes SSO, admin controls, and audit logs."
        return "Acme does not train models on customer data. Customers can request deletion of account data."


class FakeExtractor:
    def extract(self, tool_name: str, source_url: str, source_type: str, page_text: str, company_context: str):
        from scout.models import EvidenceClaim

        claims = []
        if "does not train" in page_text:
            claims.append(EvidenceClaim(tool_name=tool_name, source_url=source_url, source_type=source_type, risk_category="Training on customer data", claim_text="Acme says it does not train on customer data.", evidence_quote="does not train models on customer data", severity=1, confidence=0.9))
        if "SSO" in page_text:
            claims.append(EvidenceClaim(tool_name=tool_name, source_url=source_url, source_type=source_type, risk_category="SSO/SAML", claim_text="Acme supports SSO/SAML.", evidence_quote="SSO, SAML", severity=1, confidence=0.9))
        if "SOC 2" in page_text:
            claims.append(EvidenceClaim(tool_name=tool_name, source_url=source_url, source_type=source_type, risk_category="SOC2 / ISO27001", claim_text="Acme has SOC 2 Type II.", evidence_quote="SOC 2 Type II", severity=1, confidence=0.85))
        if "deletion" in page_text:
            claims.append(EvidenceClaim(tool_name=tool_name, source_url=source_url, source_type=source_type, risk_category="Deletion/export controls", claim_text="Acme supports deletion requests.", evidence_quote="request deletion of account data", severity=1, confidence=0.8))
        return claims


def test_agentic_scan_has_plan_act_observe_trace_and_outputs(tmp_path):
    scanner = AgenticScanner(searcher=FakeSearcher(), fetcher=FakeFetcher(), extractor=FakeExtractor())

    result = scanner.scan(["Acme AI"], "Security company requiring SSO and no training.", tmp_path, max_iterations=2)

    assert result.evidence_json.exists()
    assert (tmp_path / "agent_trace.json").exists()
    assert result.sources
    assert result.claims
    trace = (tmp_path / "agent_trace.json").read_text()
    assert "plan_queries" in trace
    assert "tavily_search" in trace
    assert "extract_and_verify" in trace
    assert result.verdicts[0].tool_name == "Acme AI"
