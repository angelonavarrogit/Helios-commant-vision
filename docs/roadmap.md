# ☀️ HELIOS — Product Roadmap (vision-level)

> Companion to `docs/vision.md`. This file captures the **product ideas** and the
> staged evolution (V1 → V4). It is a roadmap, **not** a commitment to build: each
> item becomes real only through the phased process in the improvement roadmap
> (ANALYZE → IMPLEMENT → TEST → DOCUMENT → REPORT → STOP) and, where it affects
> security/data/architecture/cost, an ADR in `decisions.md`.

All items preserve the core discipline:

```
OBSERVE → UNDERSTAND → PRIORITIZE → ALERT → REMEMBER
READ → ANALYZE → NOTIFY   (before any  WRITE → SEND → DELETE → TRANSACT)
```

No feature here may move money, send/delete mail, change credentials, or take
irreversible action without an explicit human-in-the-loop gate and a dedicated
ADR (scope guard, `docs/security.md` §4).

---

## Staged evolution

### V1 — FOUNDATION (largely in place today)
HELIOS COMMAND · Authentication · Connections · Gmail · OpenAI/Ollama · Telegram ·
Agents · Supervisor · Audit · Security. See `docs/project-baseline.md` for the
confirmed vs partial status.

### V1.5 — INTELLIGENCE
HELIOS WATCH · HELIOS DAILY · Search · Activity · Explain · Rules · Feedback.

### V2 — PERSONAL KNOWLEDGE
Memory · Documents · Calendar · Tasks · Reports · Finance · Insurance.

### V3 — PROACTIVE
Cross-source intelligence · Context engine · Predictive reminders · Proactive
alerts · Advanced orchestration.

### V4 — PLATFORM
Plugin system · Public API · Webhooks · Multiple users · Mobile · Advanced
integrations.

---

## Suggested build order (top 7, by technical dependency)

Not a ranking of value — an order that respects dependencies:

1. **HELIOS WATCH** — a layer that supervises the system itself.
2. **HELIOS DAILY** — turns analysis into a useful daily experience.
3. **HELIOS EXPLAIN** — know *why* HELIOS made a decision (traceability).
4. **HELIOS SEARCH** — makes accumulated information queryable.
5. **HELIOS MEMORY** — keeps context across events.
6. **HELIOS FEEDBACK + RULE ENGINE** — learns preferences via explicit signals.
7. **HELIOS PROACTIVE INTELLIGENCE** — connects everything into insights.

---

## Feature catalog (21 ideas)

Content adapted and summarized from the owner's product notes.

### 1. HELIOS DAILY — personal morning briefing
A proactive morning message (Telegram) with: what needs attention today
(prioritized), email volume (new/analyzed/important), finance events, security
status, and relevant events for the day. Turns HELIOS from "open the dashboard"
into "HELIOS tells you". *(Builds on the existing report/summary logic.)*

### 2. HELIOS WATCH — system watch layer
Monitors Gmail/Outlook, OpenAI/Ollama, Docker, database, OAuth, backups, disk,
system. Detects: OAuth expired, provider disconnected, DB/LLM/Telegram
unavailable, backup failed, unusual email volume, agent failure. Flows
Watch → event → supervisor → (important?) → Telegram. See `docs/helios-watch.md`
(to be authored in its phase).

### 3. HELIOS ALERT ENGINE — severity + confidence
Not every event is an alert. Model **severity** (info/low/medium/high/critical)
and **confidence** (low/medium/high). Alerts carry source, reason and a
*recommended action*. Language stays calibrated: "possible anomaly / requires
review", never an automatic "fraud" claim (consistent with the current agents).

### 4. HELIOS MEMORY — layered memory
Remember preferences, financial patterns, institutions, recurring bills,
policies, contacts, work context, documents, past alerts. Distinguish
short-term / long-term / episodic / semantic memory, each fact carrying source,
confidence, created, last-verified and expiration — so stale info is not treated
as permanent truth.

### 5. HELIOS EXPLAIN — decision traceability
For any flagged item, open a "Why?" view: source, agent, signals detected,
supervisor decision, confidence. HELIOS should say "here's what I found and why
I classified it this way", never "just trust me". *(The data already exists in
agent results + supervisor decision.)*

### 6. HELIOS SEARCH — global search
One search across emails, documents, alerts, financial events, memory, reports.
Natural questions like "when does my insurance expire?" resolve across sources
and return a synthesized answer with its source. *(Extends the current keyword
search.)*

### 7. HELIOS DOCS — document analysis
Analyze PDF/DOCX/XLSX/CSV/images → OCR/parse → extract (invoice, contract,
policy, statement, receipt, warranty, employment doc) → classify → agent →
memory. *(A DocumentAgent already exists for text-based PDF/Excel/Word; OCR for
images is future.)*

### 8. HELIOS FINANCE — finance module
Beyond detecting bank emails: transactions, bills, subscriptions, loans, credit
cards, income, financial alerts. Detect recurring payments, upcoming due dates,
possible unusual transactions (flagged as "requires review"), and subscriptions.

### 9. HELIOS SECURITY CENTER
A status view per category (OAuth connections, active sessions, MFA, backups,
secrets, HTTPS) — status by category rather than a single numeric score. Plus
security events: new login, connection changed, OAuth token expired, unusual
auth activity.

### 10. HELIOS CALENDAR
With Google/Outlook Calendar connected, combine email + calendar + tasks +
documents + alerts for contextual intelligence ("tomorrow's 9am meeting relates
to a project with three pending emails").

### 11. HELIOS TASKS
Turn information into tasks ("send the report before Friday" → task with due date,
source, priority). Initially **does not execute** anything — surfacing only.

### 12. HELIOS AGENT ORCHESTRATOR (evolution)
Let one event activate several relevant agents (e.g. PDF + email + payment →
Document + Finance + Security agents), consolidated by the supervisor. *(The
orchestrator + supervisor already exist; this extends fan-out.)*

### 13. HELIOS SIMULATION MODE
Load a sample event, run it through EYE → BRAIN → agent → SUPERVISOR with an
expected outcome; plus a replay engine to re-run a stored event against agent
versions. Excellent for safely testing agent changes. *(Aligns with the
FakeEmailProvider/FakeLLM already used in tests.)*

### 14. HELIOS ANALYTICS
Emails analyzed, alerts generated/dismissed, agent accuracy, false positives,
provider failures, LLM usage/cost, processing time — to improve HELIOS from real
data.

### 15. HELIOS FEEDBACK LOOP
On each alert: 👍 correct / 👎 incorrect / ignore / always important / never
important. Feedback flows into memory/rules and future classification, adapting
to the user without training a model from scratch.

### 16. PERSONAL RULE ENGINE
Explicit deterministic rules alongside AI (e.g. IF sender contains "Banco
General" AND body contains "transferencia" THEN priority = HIGH; IF insurance
renewal < 30 days THEN alert). Rules + AI + history + context → supervisor. More
reliable than asking the LLM for everything. *(The classifier already runs rules
before the LLM; this exposes user-defined rules.)*

### 17. HELIOS PLUGIN SYSTEM
Providers as declarative plugins (name, version, capabilities) — Gmail, Outlook,
Telegram, Drive, Slack, Calendar, Finance, Weather, Home Assistant, etc. *(The
provider registry is already the seed of this.)*

### 18. HELIOS API
When stable, expose `/api/v1` for other systems (POST /events, GET
/alerts|/connections|/tasks|/reports), later with API keys, webhooks, OAuth.

### 19. Multi-channel notifications
Beyond Telegram: email, push, web, Discord, Slack, with routing by severity
(critical → Telegram + push; high → Telegram; medium → dashboard; low → daily
report).

### 20. HELIOS CHAT
Conversational interface: "what needs my attention?", "how much did I spend this
month?", "what insurance do I have?", "which emails should I read first?",
"what documents expire soon?" — with [Explain]/[Open] actions.

### 21. HELIOS PROACTIVE INTELLIGENCE
The most differentiating step: HELIOS acts without being asked. E.g. insurance
expires in 27 days → search email/documents/calendar/previous policy →
supervisor → alert: "Your policy expires in 27 days. I found the previous policy
and a renewal email; I have not detected a new policy yet." Connects email +
document + calendar + memory + finance + insurance + work → context → supervisor
→ insight → alert.

---

## Relationship to the stabilization roadmap

The owner's stabilization roadmap (baseline → configuration → auth → OAuth →
connection center → settings → secrets → LLM → data governance → audit → watch →
command center → navigation → backup → production hardening → quality gate →
documentation → Outlook → internet readiness → final review) is the **hardening
track**. This product roadmap is the **capability track**. Hardening comes first;
capabilities are layered on a stable, secure foundation. Both are driven phase by
phase with explicit approval between phases.
