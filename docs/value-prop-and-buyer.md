# Shadow AI Scout — Buyer / Money Logic

## Core paid value

Shadow AI Scout is **not** “ask ChatGPT if a tool is safe”.

The paid product is:

> **First-pass AI vendor review automation for security, IT, compliance, and founders.**

It saves time by turning messy public vendor pages into an audit-ready approval packet.

---

## Money line

> **Shadow AI Scout cuts first-pass AI vendor reviews from ~60 minutes to ~5 minutes by automatically collecting evidence, matching it to company policy, and producing an audit-ready decision packet.**

---

## Who pays?

### 1. Security / GRC teams

They are drowning in AI tool requests:

- “Can I use Granola for customer calls?”
- “Can I use Cursor on private repos?”
- “Can I install Rewind on my work laptop?”
- “Can marketing use this AI video tool?”

They need a repeatable approval record, not a one-off AI opinion.

### 2. IT / procurement teams

They need to know:

- is this vendor safe enough?
- does it have SSO?
- does it have SOC2 / ISO27001?
- does it offer a DPA?
- what data is collected?
- is customer/source/meeting data retained?
- can users delete/export data?

They also need the decision saved so the next employee gets the same answer.

### 3. Small security-conscious startups

They have enough risk to care, but not enough headcount to do full vendor reviews manually.

Founder/CTO buyer question:

> “What AI tools can my team safely use without creating a data/security mess?”

---

## Current manual workflow

For every new AI tool request, a security/GRC person may need to:

1. Open vendor website.
2. Find privacy policy.
3. Find terms.
4. Find security/trust page.
5. Check pricing/enterprise controls.
6. Check SOC2 / ISO27001 / GDPR / DPA claims.
7. Check SSO/SAML/admin controls.
8. Check data retention/deletion.
9. Check if customer data is used for training.
10. Search for breach/news/security history.
11. Write notes.
12. Make a recommendation.
13. Save evidence for audit/procurement.

Estimated time: **30–90 minutes per tool**.

Shadow AI Scout target: **5 minutes to review the generated packet**.

---

## Why ChatGPT/Claude/Hermes alone do not replace it

General chat tools can give advice, but they do not provide the product workflow:

| Need | ChatGPT/Claude alone | Shadow AI Scout |
|---|---|---|
| Company-specific policy scoring | Weak / manual | Built in |
| Repeatable evidence collection | Inconsistent | Built in |
| Exact source quotes | Often unreliable | Required + verified |
| Stored approval history | No | Yes |
| Change monitoring | No | Yes |
| Audit trail | No | Yes |
| Team approval queue | No | Product workflow |
| Same answer for all employees | No | Yes |
| ClickHouse evidence DB | No | Yes |

The paid value is **workflow + audit + repeatability**, not raw LLM intelligence.

---

## Product framing

Bad framing:

> “AI that reviews AI tools.”

Better framing:

> **“A security approval queue for shadow AI adoption.”**

Best framing:

> **“Before your team installs another AI tool, send the scout first.”**

---

## Paid SaaS workflow

1. Employee submits a tool request.

```txt
Can I use Granola for customer calls?
```

2. Shadow AI Scout investigates:

- privacy policy
- security page
- terms
- pricing
- docs
- subprocessors
- breach/news history

3. It scores against company policy:

- SOC2 required
- SSO required
- no customer data training
- deletion controls required
- DPA required
- audit logs preferred

4. It outputs:

```txt
Decision: Needs Review
Reason: meeting transcript data + retention/admin controls unclear
Evidence: privacy/security/pricing pages
Suggested employee response: not approved for customer calls until DPA and retention are confirmed
```

5. Security chooses:

- approve
- approve with restrictions
- reject
- ask vendor questions

6. Decision is saved.

Next time another employee asks for the same tool:

```txt
Already reviewed.
Granola approved only for internal meetings.
Customer calls not allowed.
Last checked: 3 days ago.
```

---

## Pricing hypothesis

| Buyer | Pain | Possible price |
|---|---|---:|
| 10–50 person startup | Founder/CTO reviewing random AI tools | £49–£199/mo |
| 50–500 person company | IT/security drowning in AI requests | £499–£2k/mo |
| Security/compliance team | Needs vendor evidence trail | £2k–£10k/mo |
| MSP/security consultant | Reviews AI tools for clients | per-client / per-report |

Best first wedge:

> **Small security-conscious startups and AI-heavy teams without mature GRC headcount.**

---

## Hackathon demo implication

The demo must show saved labour, not just a report.

Demo this workflow:

1. Employee request appears.
2. Agent investigates live web.
3. Agent shows trace: plan → search → read → extract → verify → re-plan.
4. Agent fills approval queue.
5. Agent produces audit packet.
6. Security clicks decision.
7. Next request for same tool reuses saved decision.

This makes the payment factor obvious:

> **It replaces the first hour of manual AI vendor review and leaves an audit trail.**
