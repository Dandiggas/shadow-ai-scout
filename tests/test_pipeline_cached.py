from scout.pipeline import run_cached_scan


def test_cached_scan_produces_clickhouse_ready_evidence_and_report(tmp_path):
    output_dir = tmp_path / "reports"

    result = run_cached_scan(
        tools=["Cursor"],
        company_context="Security-sensitive company handling source code and customer data.",
        output_dir=output_dir,
    )

    assert result.run_id
    assert result.verdicts[0].tool_name == "Cursor"
    assert result.evidence_json.exists()
    assert result.markdown_report.exists()
    assert result.clickhouse_sql.exists()
    data = result.evidence_json.read_text()
    assert "source_url" in data
    assert "evidence_quote" in data
    assert "requirements" in data
