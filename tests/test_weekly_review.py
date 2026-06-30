from pathlib import Path

from scout.approvals import ApprovalRequest, DecisionStore
from scout.models import ScanResult, ToolVerdict
from scout.review import approved_tools_from_decisions, review_approved_products


def _verdict(tool_name: str, verdict: str) -> ToolVerdict:
    return ToolVerdict(
        tool_name=tool_name,
        risk_score=20 if verdict == "approve" else 100,
        verdict=verdict,
        failed_policy=[] if verdict == "approve" else ["DPA available"],
        summary="summary",
        recommended_policy="policy",
    )


def test_approved_tools_excludes_rejected_decisions(tmp_path):
    store = DecisionStore(tmp_path / "decisions.json")
    store.save_decision(ApprovalRequest(employee="dev@example.com", tool_name="Cursor", use_case="coding", data_involved="source code"), _verdict("Cursor", "approve"))
    store.save_decision(ApprovalRequest(employee="dev@example.com", tool_name="Granola", use_case="meetings", data_involved="meeting notes"), _verdict("Granola", "reject/high risk"))

    assert approved_tools_from_decisions(store) == ["Cursor"]


def test_decisions_are_scoped_by_use_case_and_data_class(tmp_path):
    store = DecisionStore(tmp_path / "decisions.json")
    store.save_decision(ApprovalRequest(employee="dev@example.com", tool_name="Cursor", use_case="public docs", data_involved="public data"), _verdict("Cursor", "approve"))
    store.save_decision(ApprovalRequest(employee="dev@example.com", tool_name="Cursor", use_case="customer support", data_involved="customer data"), _verdict("Cursor", "reject/high risk"))

    decisions = store.list_decisions()

    assert len(decisions) == 2
    assert {decision.data_involved for decision in decisions} == {"public data", "customer data"}
    assert store.find_previous("Cursor", use_case="public docs", data_involved="public data").verdict == "approve"


def test_review_approved_products_runs_scan_for_only_approved_tools(tmp_path):
    store = DecisionStore(tmp_path / "decisions.json")
    store.save_decision(ApprovalRequest(employee="dev@example.com", tool_name="Cursor", use_case="coding", data_involved="source code"), _verdict("Cursor", "conditional approve"))
    store.save_decision(ApprovalRequest(employee="dev@example.com", tool_name="Rewind AI", use_case="memory", data_involved="screen audio"), _verdict("Rewind AI", "reject/high risk"))
    called = {}

    def fake_scan(tools: list[str], company_context: str, output_dir: Path) -> ScanResult:
        called["tools"] = tools
        output_dir.mkdir(parents=True, exist_ok=True)
        report = output_dir / "cited.md"
        evidence = output_dir / "evidence.json"
        sql = output_dir / "clickhouse_inserts.sql"
        report.write_text("# report", encoding="utf-8")
        evidence.write_text("{}", encoding="utf-8")
        sql.write_text("-- sql", encoding="utf-8")
        return ScanResult(run_id="run-1", verdicts=[_verdict("Cursor", "approve")], claims=[], sources=[], evidence_json=evidence, markdown_report=report, clickhouse_sql=sql)

    result = review_approved_products(store, "Company policy", tmp_path / "weekly", scan_func=fake_scan)

    assert called["tools"] == ["Cursor"]
    assert result.markdown_report == tmp_path / "weekly" / "cited.md"
    assert (tmp_path / "weekly" / "weekly_review_summary.md").read_text(encoding="utf-8").startswith("# Weekly compliance review")


def test_weekly_summary_shows_drift_from_saved_decision(tmp_path):
    store = DecisionStore(tmp_path / "decisions.json")
    store.save_decision(ApprovalRequest(employee="dev@example.com", tool_name="Cursor", use_case="coding", data_involved="source code"), _verdict("Cursor", "approve"))

    def fake_scan(tools: list[str], company_context: str, output_dir: Path) -> ScanResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        report = output_dir / "cited.md"
        evidence = output_dir / "evidence.json"
        sql = output_dir / "clickhouse_inserts.sql"
        report.write_text("# report", encoding="utf-8")
        evidence.write_text("{}", encoding="utf-8")
        sql.write_text("-- sql", encoding="utf-8")
        worse = _verdict("Cursor", "needs review")
        worse.risk_score = 75
        return ScanResult(run_id="run-1", verdicts=[worse], claims=[], sources=[], evidence_json=evidence, markdown_report=report, clickhouse_sql=sql)

    review_approved_products(store, "Company policy", tmp_path / "weekly", scan_func=fake_scan)

    summary = (tmp_path / "weekly" / "weekly_review_summary.md").read_text(encoding="utf-8")
    assert "Previous verdict" in summary
    assert "approve" in summary
    assert "Current verdict" in summary
    assert "needs review" in summary
    assert "+55" in summary
