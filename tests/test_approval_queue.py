from scout.approvals import ApprovalRequest, DecisionStore
from scout.models import ToolVerdict


def test_decision_store_finds_previous_decision_for_same_tool(tmp_path):
    store = DecisionStore(tmp_path / "decisions.json")
    verdict = ToolVerdict(
        tool_name="Cursor",
        risk_score=46,
        verdict="conditional approve",
        failed_policy=["Audit logs preferred"],
        summary="Source-code handling needs review.",
        recommended_policy="Approve only for non-sensitive repos.",
    )
    request = ApprovalRequest(employee="dev@sophos.com", tool_name="Cursor", use_case="coding", data_involved="source code")

    store.save_decision(request, verdict)
    previous = store.find_previous("cursor")

    assert previous is not None
    assert previous.tool_name == "Cursor"
    assert previous.verdict == "conditional approve"
    assert previous.action == "reuse previous decision or review changed use case"
