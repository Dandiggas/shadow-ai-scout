from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

import ui
from scout.agentic import run_agentic_scan
from scout.approvals import ApprovalRequest, DecisionStore
from scout.errors import ScoutAPIError
from scout.pipeline import run_cached_scan

st.set_page_config(page_title="Shadow AI Scout", layout="wide", page_icon="🛰️")

# Theme switch lives in the sidebar; pick it before injecting styles so the
# selected palette applies on this same run.
with st.sidebar:
    st.markdown("### Appearance")
    active_theme = ui.theme_toggle()
    st.caption("Switch between dark and light. Your choice is remembered.")

ui.inject_styles(active_theme)
ui.hero()

ui.section("Company policy", "The compliance baseline every requested tool is scored against.")
company_context = st.text_area(
    "Company policy / compliance baseline",
    "Security-sensitive company. Handles proprietary source code, confidential customer data, and sensitive internal meetings. Requires SSO/admin controls, no training on customer data, DPA, deletion/retention controls, and SOC2 or equivalent preferred.",
    height=140,
    label_visibility="collapsed",
)

ui.section("Approval queue", "Capture the request, then run a scan to produce an audit-ready decision packet.")
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
    st.markdown(
        f'<div class="banner" style="text-align:left;">📌 <b>Saved decision found</b> for '
        f'{len(previous_rows)} of the requested tool(s). Prior verdicts shown below.</div>',
        unsafe_allow_html=True,
    )
    st.dataframe(previous_rows, use_container_width=True, hide_index=True)

ui.section("Run a scan")
scan_cols = st.columns([2, 1])
with scan_cols[0]:
    mode = st.radio(
        "Scan mode",
        ["Cached demo", "Live agentic scan"],
        horizontal=True,
        captions=["No API keys · instant", "Live web + Claude · cited evidence"],
    )
with scan_cols[1]:
    st.write("")
    button_label = "Run cached demo scan" if mode == "Cached demo" else "Run live agentic scan"
    run_clicked = st.button(button_label, type="primary", use_container_width=True)

if run_clicked:
    if not requested_tools:
        st.warning("Add at least one tool in **Tools requested** before scanning.")
        st.stop()

    output_dir = Path("reports/demo_run_cached" if mode == "Cached demo" else "reports/live_run")
    _ICONS = {
        "tool": "🔎", "plan": "🧭", "search": "🌐", "read": "📄",
        "extract": "✅", "skip": "⏭️", "done": "🎯", "score": "🧮",
    }
    try:
        if mode == "Cached demo":
            with st.spinner("Running cached demo scan…"):
                result = run_cached_scan(requested_tools, company_context, output_dir)
        else:
            label = f"Scanning {len(requested_tools)} tool(s) live — gathering public evidence with Claude…"
            with st.status(label, expanded=True) as status:
                st.caption(
                    "Live scans search the web, read each vendor's privacy/security/terms pages, "
                    "and ask Claude to extract cited evidence. Expect roughly 20–60s per tool."
                )

                def on_progress(event: str, message: str) -> None:
                    status.write(f"{_ICONS.get(event, '•')} {message}")

                result = run_agentic_scan(
                    requested_tools,
                    company_context,
                    output_dir,
                    max_iterations=2,
                    progress=on_progress,
                )
                status.update(label="Scan complete — audit packet ready", state="complete", expanded=False)
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

    ui.section("Verdicts", "One card per tool, color-coded by risk posture.")
    verdicts = result.verdicts
    if verdicts:
        worst = max(v.risk_score for v in verdicts)
        flagged = sum(1 for v in verdicts if v.verdict in {"needs review", "reject/high risk"})
        m1, m2, m3 = st.columns(3)
        m1.metric("Tools scanned", len(verdicts))
        m2.metric("Flagged for review", flagged)
        m3.metric("Highest risk score", f"{worst}/100")

    card_cols = st.columns(min(len(verdicts), 3) or 1)
    for idx, verdict in enumerate(verdicts):
        with card_cols[idx % len(card_cols)]:
            st.markdown(
                ui.verdict_card(verdict.tool_name, verdict.verdict, verdict.risk_score, verdict.failed_policy),
                unsafe_allow_html=True,
            )

    for verdict in result.verdicts:
        with st.expander(f"Evidence drilldown · {verdict.tool_name}"):
            st.markdown(ui.verdict_badge_html(verdict.verdict), unsafe_allow_html=True)
            if verdict.summary:
                st.caption(verdict.summary)
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
        ui.section("Agent trace", "Plan → search → read → extract → verify → re-plan.")
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        st.dataframe(trace, use_container_width=True, hide_index=True)
        with st.expander("Raw trace JSON"):
            st.json(trace)

    st.success(f"✅ Audit packet written to {result.markdown_report}")

if "last_result" in st.session_state:
    if st.button("Save approval decisions", type="primary"):
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
    ui.section("Saved decisions", "Your approval record, ready for repeat requests and weekly rescans.")
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
        hide_index=True,
    )
