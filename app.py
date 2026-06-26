from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from scout.agentic import run_agentic_scan
from scout.approvals import ApprovalRequest, DecisionStore
from scout.errors import ScoutAPIError
from scout.pipeline import run_cached_scan

st.set_page_config(page_title="Shadow AI Scout", layout="wide")
st.title("Shadow AI Scout")
st.caption("AI tool approval infrastructure: policy + public evidence + audit packet")

company_context = st.text_area(
    "Company policy / compliance baseline",
    "Security-sensitive company. Handles proprietary source code, confidential customer data, and sensitive internal meetings. Requires SSO/admin controls, no training on customer data, DPA, deletion/retention controls, and SOC2 or equivalent preferred.",
    height=140,
)

st.subheader("Approval queue")
queue_cols = st.columns(4)
with queue_cols[0]:
    employee = st.text_input("Employee", "employee@company.com")
with queue_cols[1]:
    tool_text = st.text_input("Tools requested", "Cursor, Granola, Rewind AI")
with queue_cols[2]:
    use_case = st.text_input("Use case", "coding, meetings, research")
with queue_cols[3]:
    data_involved = st.text_input("Data involved", "source code, customer data, meeting notes")

store = DecisionStore(Path("reports/decisions.json"))
requested_tools = [t.strip() for t in tool_text.split(",") if t.strip()]
previous_rows = []
for tool_name in requested_tools:
    previous = store.find_previous(tool_name)
    if previous:
        previous_rows.append(
            {
                "Tool": previous.tool_name,
                "Previous verdict": previous.verdict,
                "Score": previous.risk_score,
                "Action": previous.action,
                "Last use case": previous.use_case,
            }
        )
if previous_rows:
    st.info("Saved decision found for one or more requested tools.")
    st.dataframe(previous_rows, use_container_width=True)

mode = st.radio("Scan mode", ["Cached demo", "Live agentic scan"], horizontal=True)
button_label = "Run cached demo scan" if mode == "Cached demo" else "Run live agentic scan"

if st.button(button_label):
    output_dir = Path("reports/demo_run_cached" if mode == "Cached demo" else "reports/live_run")
    try:
        if mode == "Cached demo":
            result = run_cached_scan(requested_tools, company_context, output_dir)
        else:
            result = run_agentic_scan(requested_tools, company_context, output_dir)
    except ScoutAPIError as exc:
        st.error(f"{exc.provider} setup error: {exc.user_message}")
        if exc.detail:
            st.caption(exc.detail)
        st.stop()

    st.session_state["last_result"] = result
    st.session_state["last_request"] = ApprovalRequest(
        employee=employee,
        tool_name=requested_tools[0] if requested_tools else "",
        use_case=use_case,
        data_involved=data_involved,
    ).model_dump()
    st.session_state["last_output_dir"] = str(output_dir)

    rows = [
        {
            "Tool": v.tool_name,
            "Verdict": v.verdict,
            "Score": v.risk_score,
            "Failed policy": ", ".join(v.failed_policy) or "None",
        }
        for v in result.verdicts
    ]
    st.subheader("Verdict table")
    st.dataframe(rows, use_container_width=True)

    for verdict in result.verdicts:
        with st.expander(f"Evidence drilldown: {verdict.tool_name}"):
            st.markdown("#### Why this score?")
            st.dataframe(
                [
                    {
                        "Reason": reason.label,
                        "Score impact": reason.score_delta,
                        "Evidence": reason.evidence_quote,
                        "Source": reason.source_url,
                    }
                    for reason in verdict.score_reasons
                ],
                use_container_width=True,
            )

            st.markdown("#### Compliance roadmap")
            st.dataframe(
                [
                    {
                        "Action": step.action,
                        "Why": step.rationale,
                        "Source": step.source_url,
                    }
                    for step in verdict.remediation_steps
                ],
                use_container_width=True,
            )

            st.markdown("#### Requirement evidence")
            for req in verdict.requirements:
                st.markdown(f"**{req.label}**: `{req.status}`")
                st.write(req.evidence_quote or "No public evidence found")
                if req.source_url:
                    st.caption(req.source_url)
                st.divider()

    trace_path = output_dir / "agent_trace.json"
    if trace_path.exists():
        st.subheader("Agent trace")
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        st.dataframe(trace, use_container_width=True)
        with st.expander("Raw trace JSON"):
            st.json(trace)

    st.success(f"Report written to {result.markdown_report}")

if "last_result" in st.session_state:
    if st.button("Save approval decisions"):
        request_payload = st.session_state.get("last_request", {})
        result = st.session_state["last_result"]
        saved = []
        for verdict in result.verdicts:
            request = ApprovalRequest(
                employee=request_payload.get("employee", employee),
                tool_name=verdict.tool_name,
                use_case=request_payload.get("use_case", use_case),
                data_involved=request_payload.get("data_involved", data_involved),
            )
            saved.append(store.save_decision(request, verdict))
        st.success(f"Saved {len(saved)} decision(s) to reports/decisions.json")

saved_decisions = store.list_decisions()
if saved_decisions:
    st.subheader("Saved decisions")
    st.dataframe(
        [
            {
                "Tool": d.tool_name,
                "Verdict": d.verdict,
                "Score": d.risk_score,
                "Use case": d.use_case,
                "Data involved": d.data_involved,
                "Action": d.action,
            }
            for d in saved_decisions
        ],
        use_container_width=True,
    )
