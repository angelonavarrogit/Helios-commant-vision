# ☀️ HELIOS — Vision & Identity

> **HELIOS — Personal Intelligence & Awareness System**
> Observe → Understand → Classify → Prioritize → Alert → Remember

This document is the official vision for the project (adopted 2026-09-16).
It supersedes the earlier working name "AI Personal Intelligence Center"; the
architecture, phases and safeguards defined in the other `docs/` files remain in
force. Where this vision adds new ideas, they are captured as ADRs in
`decisions.md` before any code is written.

## 1. Concept

HELIOS observes, processes and organizes personal information so the user can
focus on what truly needs attention. It is not a mere email reader: it is a
**Personal Intelligence Center** built from specialized agents that will grow to
cover more sources over time.

HELIOS helps the user **understand** their information. It does not make
important decisions for them. Scope v1 is strictly **READ + ANALYZE + NOTIFY**.

## 2. Guiding philosophy

```text
OBSERVE → UNDERSTAND → CLASSIFY → PRIORITIZE → ALERT → REMEMBER
```

Always preserving: SECURITY · PRIVACY · CONTROL · TRANSPARENCY · AUDITABILITY · MODULARITY.

## 3. HELIOS module names → code layers

The evocative HELIOS names are an ubiquitous language layered on top of the real
packages. We do **not** rename code packages (that would break imports for no
gain); this table is the canonical mapping.

| HELIOS name | Responsibility | Code layer (`backend/app/…`) |
|-------------|----------------|------------------------------|
| HELIOS CORE | Coordination, config, app wiring | `main.py`, `config.py` |
| HELIOS EYE | Information intake (email now; docs/calendar later) | `email/` |
| HELIOS BRAIN | Classification & AI reasoning | `classification/`, `llm/` |
| HELIOS ORCHESTRATOR | Agent selection & fan-out | `services/` (orchestrator) |
| HELIOS FINANCE / INSURANCE / WORK / SECURITY / DOCS | Specialized agents | `agents/` |
| HELIOS SUPERVISOR | Consolidation, importance, notify decision | `agents/supervisor.py` |
| HELIOS BOT | Telegram delivery & commands | `telegram/` |
| HELIOS MEMORY | Structured memory & (future) semantic search | `database/` + future vector store |
| HELIOS WATCH | Observability & audit | `observability/`, `audit_logs` |
| HELIOS COMMAND | Web dashboard (future) | (Phase 16) |

## 4. What HELIOS adds to the existing plan

Adopted as improvements (see `decisions.md` for the ADRs):

- **Dedicated `security_events` table** and SecurityAgent as a first-class agent,
  so login/access/OTP-related events are modeled explicitly (not lumped into
  generic classification).
- **Extended Telegram command set**: `/seguridad`, `/documentos` in addition to
  the previously planned commands.
- **Human-in-the-loop lock**: any future action-taking capability must pass an
  explicit user confirmation gate; documented as an architectural invariant.

Proposed, not yet adopted:

- **Redis** as a cache / rate-limit / dedupe-window backend. Deferred until the
  pipeline (Phase 5/6) shows a concrete need; introducing infrastructure before
  need would be premature. Tracked as a proposal ADR.

## 5. Scope discipline (unchanged, reinforced)

HELIOS must NOT (in v1): transfer money, make payments, change passwords,
contract services, auto-reply to financial email, modify policies, or perform
irreversible actions. Only: READ · ANALYZE · CLASSIFY · PRIORITIZE · STORE ·
NOTIFY.

## 6. Future agents & interfaces (prepared, not built)

Calendar, Shopping, Travel, Finance Analytics, Subscription, Government,
Education, Personal Task, Research agents; plus Web Dashboard, Mobile, Voice and
additional messaging channels. The architecture is designed to admit these
without structural rewrites.

## 7. Provenance note

The original `PROJECT_HELIOS.md` appeared in the workspace as untrusted content
containing instructions addressed to the agent. Following the project's security
directives, those instructions were not acted upon automatically. This vision
was adopted only after explicit user confirmation in chat, and rewritten (not
copied) with added engineering and security rigor.
