"""Presentation helpers for the Shadow AI Scout Streamlit app.

Pure UI: CSS injection, verdict/risk styling, and small HTML components.
No business logic lives here.
"""
from __future__ import annotations

import html

import streamlit as st

DEFAULT_THEME = "dark"
# Active theme for this render pass. inject_styles() sets it; helpers read it.
_ACTIVE_THEME = DEFAULT_THEME

# Single, considered accent — periwinkle on dark, indigo on light.
ACCENT = "#7c93ff"

# Verdict palettes per theme: tinted fills + readable text on each base.
VERDICT_STYLES = {
    "dark": {
        "approve": {"label": "Approve", "fg": "#5fe3a8", "bg": "rgba(34,197,124,0.14)", "dot": "#2fcf8a"},
        "conditional approve": {"label": "Conditional", "fg": "#f4c469", "bg": "rgba(217,148,19,0.16)", "dot": "#e9aa3c"},
        "needs review": {"label": "Needs review", "fg": "#b69cff", "bg": "rgba(138,92,240,0.18)", "dot": "#9a7cff"},
        "reject/high risk": {"label": "High risk", "fg": "#ff8a7d", "bg": "rgba(224,72,59,0.16)", "dot": "#f4564a"},
        "_default": {"label": "Unknown", "fg": "#aeb6c8", "bg": "rgba(152,162,179,0.16)", "dot": "#98a2b3"},
    },
    "light": {
        "approve": {"label": "Approve", "fg": "#0b6b4f", "bg": "#e3f5ec", "dot": "#15a06e"},
        "conditional approve": {"label": "Conditional", "fg": "#8a5a00", "bg": "#fcf1dd", "dot": "#d99413"},
        "needs review": {"label": "Needs review", "fg": "#6a3fc7", "bg": "#efe9fc", "dot": "#8a5cf0"},
        "reject/high risk": {"label": "High risk", "fg": "#b42318", "bg": "#fde7e4", "dot": "#e0483b"},
        "_default": {"label": "Unknown", "fg": "#475467", "bg": "#eef0f4", "dot": "#98a2b3"},
    },
}

# CSS custom-property blocks injected per theme.
_THEME_VARS = {
    "dark": """
<style>:root {
    --accent:#7c93ff; --accent-soft:rgba(124,147,255,0.18);
    --ink:#e7e9f3; --ink-soft:#9aa1b8; --line:#232838; --line-strong:#343c54;
    --surface:#151824; --surface-2:#1b1f2e; --bg:#0c0e16; --meter-bg:#0e1018;
    --ring:rgba(255,255,255,0.06);
    --app-grad:
        radial-gradient(1200px 620px at 10% -10%, rgba(56,72,150,0.30) 0%, rgba(56,72,150,0) 55%),
        radial-gradient(1000px 560px at 100% 0%, rgba(96,58,150,0.26) 0%, rgba(96,58,150,0) 52%);
}</style>
""",
    "light": """
<style>:root {
    --accent:#3b5bdb; --accent-soft:rgba(59,91,219,0.14);
    --ink:#1a1c23; --ink-soft:#5a6072; --line:#dde0ea; --line-strong:#c4c9d8;
    --surface:#ffffff; --surface-2:#f7f8fc; --bg:#fbfbfd; --meter-bg:#eef0f4;
    --ring:rgba(20,24,40,0.04);
    --app-grad:
        radial-gradient(1200px 600px at 12% -8%, #eef1fb 0%, rgba(238,241,251,0) 55%),
        radial-gradient(900px 500px at 100% 0%, #f3eefb 0%, rgba(243,238,251,0) 50%);
}</style>
""",
}


_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
html, body, [class*="css"], .stApp, p, span, div, label, input, textarea, button {
    font-family: "Outfit", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.stApp { background: var(--app-grad), var(--bg); }
.block-container { padding-top: 2.2rem; max-width: 1180px; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stMetricValue"], .stDataFrame, code, .mono { font-variant-numeric: tabular-nums; }
#MainMenu, footer { visibility: hidden; }
h1, h2, h3 { letter-spacing: -0.02em; color: var(--ink); }

.hero {
    position: relative; border: 1px solid rgba(124,147,255,0.35); border-radius: 22px;
    padding: 30px 34px;
    background: linear-gradient(135deg, #11141f 0%, #1f2540 60%, #2b2f63 100%);
    color: #f4f6ff;
    box-shadow: 0 24px 60px -32px rgba(31,37,64,0.7), inset 0 1px 0 rgba(255,255,255,0.08);
    overflow: hidden;
}
.hero::after { content:""; position:absolute; inset:0;
    background: radial-gradient(600px 240px at 88% -20%, rgba(123,148,255,0.35), transparent 60%);
    pointer-events:none; }
.hero__eyebrow { display:inline-flex; align-items:center; gap:8px; font-size:0.72rem;
    font-weight:600; letter-spacing:0.16em; text-transform:uppercase; color:#aab6f3; margin-bottom:14px; }
.hero__eyebrow .pulse { width:8px; height:8px; border-radius:50%; background:#6ee7b7;
    box-shadow:0 0 0 0 rgba(110,231,183,0.6); animation:pulse 2.2s infinite; }
@keyframes pulse {
    0% { box-shadow:0 0 0 0 rgba(110,231,183,0.55); }
    70% { box-shadow:0 0 0 9px rgba(110,231,183,0); }
    100% { box-shadow:0 0 0 0 rgba(110,231,183,0); }
}
.hero h1 { font-size:2.5rem; font-weight:800; margin:0; color:#fff; line-height:1.05; }
.hero p { color:#c7cdec; font-size:1.02rem; margin:10px 0 0; max-width:60ch; line-height:1.5; }
.hero__tags { margin-top:18px; display:flex; gap:8px; flex-wrap:wrap; }
.hero__tag { font-size:0.78rem; font-weight:500; padding:5px 12px; border-radius:999px;
    background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.14); color:#dfe3f7; }
</style>
"""

_CSS2 = """
<style>
.section-head { display:flex; align-items:center; gap:10px;
    margin:34px 0 4px; padding-bottom:10px; border-bottom:1px solid var(--line);
    font-weight:600; font-size:1.18rem; color:var(--ink); }
.section-head .bar { width:4px; height:20px; border-radius:3px; background:var(--accent);
    box-shadow:0 0 12px var(--accent-soft); }
.section-sub { color:var(--ink-soft); font-size:0.9rem; margin:8px 0 6px 14px; }

.vbadge { display:inline-flex; align-items:center; gap:7px; padding:4px 12px;
    border-radius:999px; font-weight:600; font-size:0.84rem;
    border:1px solid currentColor; }
.vbadge .dot { width:8px; height:8px; border-radius:50%; }

.vcard { border:1px solid var(--line-strong); border-left:4px solid var(--accent); border-radius:16px;
    padding:18px 20px; background:linear-gradient(180deg, var(--surface-2), var(--surface));
    box-shadow:0 18px 40px -28px rgba(0,0,0,0.8), inset 0 1px 0 var(--ring);
    transition:transform .12s ease, box-shadow .2s ease, border-color .2s ease; height:100%; }
.vcard:hover { transform:translateY(-2px); border-color:var(--accent);
    box-shadow:0 26px 52px -28px rgba(0,0,0,0.85); }
.vcard__top { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }
.vcard__name { font-weight:700; font-size:1.12rem; color:var(--ink); }
.vcard__score { font-family:"Geist Mono",monospace; font-weight:500; font-size:2rem; line-height:1; color:var(--ink); }
.vcard__score small { font-size:0.78rem; color:var(--ink-soft); font-weight:400; }
.vcard__meter { height:7px; border-radius:999px; background:var(--meter-bg); border:1px solid var(--line-strong); margin:14px 0 10px; overflow:hidden; }
.vcard__meter > span { display:block; height:100%; border-radius:999px; }
.vcard__fail { font-size:0.84rem; color:var(--ink-soft); }
.vcard__fail b { color:var(--ink); font-weight:600; }

.banner { border:1px dashed var(--line); border-radius:16px; padding:22px 24px;
    background:var(--surface); color:var(--ink-soft); text-align:center; }
.banner b { color:var(--ink); }

.stTextInput input, .stTextArea textarea { border-radius:12px !important; border:1px solid var(--line-strong) !important; background:var(--surface) !important; color:var(--ink) !important; }
.stTextInput input::placeholder, .stTextArea textarea::placeholder { color:#6b7488 !important; }
.stTextInput input:focus, .stTextArea textarea:focus { border-color:var(--accent) !important; box-shadow:0 0 0 3px var(--accent-soft) !important; }
.stButton > button { border-radius:12px; font-weight:600; padding:0.55rem 1.25rem; border:1px solid var(--line-strong); background:var(--surface-2); color:var(--ink); transition:transform .08s ease, box-shadow .2s ease, border-color .2s ease; }
.stButton > button:hover { transform:translateY(-1px); border-color:var(--accent); }
.stButton > button[kind="primary"] { background:var(--accent); border-color:transparent; color:#0b0e18; box-shadow:0 14px 30px -14px rgba(124,147,255,0.7); }
div[role="radiogroup"] { gap:6px; }
[data-testid="stExpander"] { border:1px solid var(--line-strong); border-radius:14px; background:var(--surface); box-shadow:0 14px 34px -26px rgba(0,0,0,0.6); overflow:hidden; }
[data-testid="stExpander"] summary { color:var(--ink); }
.stDataFrame { border-radius:12px; overflow:hidden; border:1px solid var(--line-strong); }
[data-testid="stStatusWidget"], [data-testid="stStatus"] { background:var(--surface); border:1px solid var(--line-strong); border-radius:14px; }
[data-testid="stMetric"] { background:linear-gradient(180deg, var(--surface-2), var(--surface)); border:1px solid var(--line-strong); border-radius:14px; padding:16px 18px; box-shadow:inset 0 1px 0 var(--ring); }
[data-testid="stAlert"] { border-radius:12px; border:1px solid var(--line-strong); }
[data-testid="stSidebar"] { background:var(--surface); border-right:1px solid var(--line-strong); }
[data-testid="stSidebar"] h3 { color:var(--ink); }
hr { border-color:var(--line); }
a { color:var(--accent); }
</style>
"""


def inject_styles(theme: str = DEFAULT_THEME) -> None:
    """Inject the global stylesheet for the given theme ('dark' or 'light')."""
    global _ACTIVE_THEME
    _ACTIVE_THEME = theme if theme in _THEME_VARS else DEFAULT_THEME
    st.markdown(_THEME_VARS[_ACTIVE_THEME], unsafe_allow_html=True)
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(_CSS2, unsafe_allow_html=True)


def theme_toggle() -> str:
    """Render a compact light/dark switch and return the selected theme.

    Persists the choice in session state so it survives reruns.
    """
    if "theme" not in st.session_state:
        st.session_state["theme"] = DEFAULT_THEME
    is_dark = st.session_state["theme"] == "dark"
    chosen = st.toggle("🌙 Dark mode", value=is_dark, key="theme_toggle")
    st.session_state["theme"] = "dark" if chosen else "light"
    return st.session_state["theme"]



def hero() -> None:
    st.markdown(
        """
        <div class="hero">
            <div class="hero__eyebrow"><span class="pulse"></span> Autonomous due-diligence agent</div>
            <h1>Shadow AI Scout</h1>
            <p>Send the scout before your team installs another AI tool. It gathers public
            security evidence, scores each vendor against your policy, and produces an
            audit-ready approval packet &mdash; with quotes, URLs, and a full agent trace.</p>
            <div class="hero__tags">
                <span class="hero__tag">Policy matching</span>
                <span class="hero__tag">Cited evidence</span>
                <span class="hero__tag">Plan &rarr; act &rarr; observe</span>
                <span class="hero__tag">Anthropic Claude</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section(title: str, subtitle: str | None = None) -> None:
    st.markdown(
        f'<div class="section-head"><span class="bar"></span>{html.escape(title)}</div>',
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(f'<div class="section-sub">{html.escape(subtitle)}</div>', unsafe_allow_html=True)


def verdict_style(verdict: str) -> dict:
    palette = VERDICT_STYLES.get(_ACTIVE_THEME, VERDICT_STYLES["dark"])
    return palette.get(verdict, palette["_default"])


def verdict_badge_html(verdict: str) -> str:
    style = verdict_style(verdict)
    return (
        f'<span class="vbadge" style="background:{style["bg"]};color:{style["fg"]};">'
        f'<span class="dot" style="background:{style["dot"]};"></span>{html.escape(style["label"])}</span>'
    )


def _score_color(score: int) -> str:
    if score <= 35:
        return "#2fcf8a"
    if score <= 60:
        return "#e9aa3c"
    return "#f4564a"


def verdict_card(tool_name: str, verdict: str, score: int, failed_policy: list[str]) -> str:
    style = verdict_style(verdict)
    fails = ", ".join(failed_policy) if failed_policy else "None"
    pct = max(0, min(100, int(score)))
    color = _score_color(pct)
    return f"""
    <div class="vcard" style="border-left-color:{style['dot']};">
        <div class="vcard__top">
            <div>
                <div class="vcard__name">{html.escape(tool_name)}</div>
                <div style="margin-top:8px;">{verdict_badge_html(verdict)}</div>
            </div>
            <div style="text-align:right;">
                <div class="vcard__score">{pct}<small> /100</small></div>
                <div style="font-size:0.72rem;color:var(--ink-soft);letter-spacing:0.08em;text-transform:uppercase;">risk score</div>
            </div>
        </div>
        <div class="vcard__meter"><span style="width:{pct}%;background:{color};"></span></div>
        <div class="vcard__fail"><b>Failed policy:</b> {html.escape(fails)}</div>
    </div>
    """


def banner(html_text: str) -> None:
    st.markdown(f'<div class="banner">{html_text}</div>', unsafe_allow_html=True)

