from pathlib import Path

import streamlit as st

from scout.pipeline import run_cached_scan
from scout.agentic import run_agentic_scan

st.set_page_config(page_title="Shadow AI Scout", layout="wide")
st.title("Shadow AI Scout")
st.caption("AI tool approval infrastructure: policy + public evidence + audit packet")

company_context = st.text_area(
    "Company policy / compliance baseline",
    "Security-sensitive company. Handles proprietary source code, confidential customer data, and sensitive internal meetings. Requires SSO/admin controls, no training on customer data, DPA, deletion/retention controls, and SOC2 or equivalent preferred.",
    height=140,
)
tool_text = st.text_input("Tools to scan", "Cursor, Granola, Rewind AI")

mode = st.radio("Scan mode", ["Cached demo", "Live agentic scan"], horizontal=True)
button_label = "Run cached demo scan" if mode == "Cached demo" else "Run live agentic scan"

if st.button(button_label):
    tools = [t.strip() for t in tool_text.split(",") if t.strip()]
    if mode == "Cached demo":
        result = run_cached_scan(tools, company_context, Path("reports/demo_run_cached"))
    else:
        result = run_agentic_scan(tools, company_context, Path("reports/live_run"))
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
            for req in verdict.requirements:
                st.markdown(f"**{req.label}**: `{req.status}`")
                st.write(req.evidence_quote or "No public evidence found")
                if req.source_url:
                    st.caption(req.source_url)
                st.divider()
    st.success(f"Report written to {result.markdown_report}")
