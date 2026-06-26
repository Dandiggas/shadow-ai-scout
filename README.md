# Shadow AI Scout

Autonomous due-diligence agent for shadow AI adoption.

It investigates AI tools on the public web, extracts cited security/compliance evidence, scores the tool against a company policy, and emits an auditable approval packet.

## Why it is not “just ChatGPT”

Shadow AI Scout is built as a **plan → act → observe → verify → re-plan** agent:

1. **Plans searches** from the company policy and missing evidence types.
2. **Acts on the web** through Tavily search and source fetching.
3. **Observes coverage gaps** across privacy, security, terms, pricing, docs, and news sources.
4. **Extracts claims with Gemini** into a strict schema.
5. **Verifies claims** by rejecting any claim whose quote is not present in the source text.
6. **Re-plans** follow-up searches when evidence is missing.
7. **Stores an audit trail** in `evidence.json`, `agent_trace.json`, `cited.md`, and ClickHouse-ready SQL.

ChatGPT can give an opinion. Shadow AI Scout gives a repeatable approval record with URLs, quotes, timestamps, scores, and an agent trace.

## Sponsor tool mapping

- **Tavily**: live web evidence discovery.
- **Gemini / DeepMind**: structured extraction and risk reasoning from fetched pages.
- **ClickHouse**: audit/evidence schema via generated insert SQL.

Optional later:

- Twilio: high-risk alert.
- ElevenLabs: voice executive summary.

## Setup

```bash
cd ~/Desktop/Projects/shadow-ai-scout
uv sync --extra dev
cp .env.example .env
```

Add keys to `.env` for live mode:

```env
TAVILY_API_KEY=tvly-...
GEMINI_API_KEY=AIza...
# or GOOGLE_API_KEY=AIza...
```

If live scan says Tavily/Gemini rejected the key, regenerate keys here:

- Tavily: https://app.tavily.com/
- Gemini: https://aistudio.google.com/apikey

## Run cached demo — no keys

```bash
uv run shadow-scout demo
```

## Run live agentic scan — requires keys

```bash
uv run shadow-scout scan \
  --tools "Cursor,Granola,Rewind AI" \
  --company-context "Security-sensitive company handling source code, customer data, and internal meetings. Requires SSO/admin controls, no training on customer data, DPA, deletion/retention controls, and SOC2 or equivalent preferred."
```

Live outputs go to `reports/live_run/`:

- `cited.md` — security adoption brief
- `evidence.json` — sources, claims, verdicts, requirements, trace
- `agent_trace.json` — plan/act/observe loop
- `clickhouse_inserts.sql` — ClickHouse-ready audit inserts

## Streamlit UI

```bash
uv run streamlit run app.py
```

The UI supports:

- approval queue request fields
- cached demo mode
- live agentic scan mode
- evidence drilldown
- agent trace panel
- saved decisions for repeat tool requests

## Tests

```bash
uv run --extra dev pytest -q
```

## Current vertical slice

- Cached evidence for Cursor, Granola, and Rewind AI.
- Live agentic scan path with Tavily + Gemini.
- Deterministic company-policy requirement scoring after extraction.
- Requirement matrix with citations.
- Markdown report generator.
- ClickHouse insert file.
- Agent trace output.
- Streamlit approval queue, trace panel, evidence drilldown, and saved decisions.

## Buyer / money logic

See `docs/value-prop-and-buyer.md`.

Money line:

> **Shadow AI Scout cuts first-pass AI vendor reviews from ~60 minutes to ~5 minutes by automatically collecting evidence, matching it to company policy, and producing an audit-ready decision packet.**

## Hackathon demo line

> “Before your team installs another AI tool, send the scout first.”
