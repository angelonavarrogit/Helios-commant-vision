# Architecture — AI Personal Intelligence Center

> Fase 0 (Discovery). Documento vivo. Última revisión: 2026-09-16.

## 1. Principios rectores

1. **Modular y desacoplado**: cada capa tiene un contrato claro y dependencias explícitas.
2. **Reglas antes que LLM**: el LLM es un recurso caro y no determinista; se usa solo cuando las reglas no bastan.
3. **UNTRUSTED por defecto**: todo lo que entra por correo es dato no confiable.
4. **READ + ANALYZE + NOTIFY**: v1 no muta el mundo exterior.
5. **Idempotencia**: reprocesar el mismo correo no genera efectos duplicados.
6. **Observabilidad y auditoría de primera clase**: cada decisión es rastreable.

## 2. Vista de componentes

```text
EMAIL SOURCES (Gmail/Outlook)
        │  OAuth (read-only)
        ▼
EMAIL INGESTOR ── EmailProvider (interfaz) → GmailProvider / OutlookProvider
        ▼
NORMALIZATION LAYER (parser + normalizer → NormalizedEmail)
        ▼
CLASSIFICATION ENGINE (RuleClassifier → LLMClassifier fallback)
        ▼
AGENT ORCHESTRATOR (selección de agentes según categoría)
        │
   ┌────┼───────────────┬───────────────┐
   ▼    ▼               ▼               ▼
FINANCE INSURANCE      WORK          SECURITY   (BaseAgent)
   └────┴───────────────┴───────────────┘
        ▼
SUPERVISOR AGENT (importance, notify_now, summary, action)
        │
   ┌────┴─────┐
   ▼          ▼
DATABASE   NOTIFICATION SERVICE → TELEGRAM BOT
(MySQL)    (reglas + dedupe/agrupación)
```

## 3. Flujo de datos (pipeline)

```text
N8N detecta nuevo email
   → POST /emails/process { account_id, message_id }
      → FastAPI: EmailService
         → EmailProvider.fetch(message_id)        [READ ONLY]
         → parser.parse() → normalizer.normalize() → NormalizedEmail
         → dedupe: ¿message_id + content_hash ya procesado? → si sí, short-circuit
         → persist Email (untrusted)
         → ClassificationEngine.classify()        [rules → LLM si necesario]
         → Orchestrator.run(agents por categoría)  [async gather]
         → Supervisor.consolidate(agent_results)
         → persist agent_runs / agent_results / supervisor decision
         → NotificationService.evaluate()          [reglas + dedupe]
             → TelegramNotifier.send() (si notify_now)
         → audit_log
```

Cada paso emite logs estructurados con `request_id` y `email_id`.

## 4. Capas y responsabilidades

| Capa | Responsabilidad | No hace |
|------|-----------------|---------|
| `email/` | Fetch, parse, normalize | Clasificar, decidir |
| `llm/` | Abstracción de proveedores LLM | Lógica de negocio |
| `agents/` | Análisis especializado por dominio | Enviar notificaciones, escribir DB directamente |
| `agents/supervisor` | Consolidar y decidir importancia/acción recomendada | Ejecutar acciones |
| `services/` | Orquestación de casos de uso | Detalles de proveedor |
| `database/` | Persistencia y repositorios | Lógica de dominio |
| `telegram/` | Entrega y comandos | Análisis |
| `security/` | Cifrado, secretos, sanitización | Nada de negocio |
| `api/` | Contratos HTTP (FastAPI) | Lógica pesada (delega a services) |

## 5. Abstracción LLM

```python
class LLMProvider(Protocol):
    async def complete(self, *, system: str, user: str, schema: type[BaseModel]) -> BaseModel: ...
```
Implementaciones: `OpenAIProvider`, `OllamaProvider`. Selección por config
(`LLM_PROVIDER`). Contrato con salida estructurada (JSON validado por Pydantic)
para evitar parsing frágil.

## 6. Estructura de carpetas (propuesta)

```text
ai-personal-intelligence/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/                # routers FastAPI (health, emails, ...)
│   │   ├── agents/             # base, supervisor, finance, insurance, work, security, documents
│   │   ├── email/              # base, gmail, outlook, parser, normalizer
│   │   ├── telegram/           # bot, handlers, notifications
│   │   ├── llm/                # base, openai, ollama
│   │   ├── classification/     # engine, rules, llm_classifier   [añadido vs. propuesta original]
│   │   ├── database/           # models, database, repositories/
│   │   ├── security/           # encryption, secrets, sanitization
│   │   ├── observability/      # logging estructurado, request context  [añadido]
│   │   └── services/           # casos de uso / orquestación
│   ├── tests/                  # unit + integration + adversarial
│   ├── alembic/                # migraciones
│   ├── requirements.txt
│   └── Dockerfile
├── n8n/workflows/
├── database/                   # init scripts, seeds
├── docs/                       # requirements, architecture, security, agents, testing, setup, api, decisions
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

Cambios respecto a la propuesta original (documentados en `decisions.md`):
- Se añade `classification/` como paquete propio (motor híbrido reglas+LLM merece cohesión).
- Se añade `observability/` para logging estructurado y contexto de request.

## 7. Modelo de datos (propuesto, normalizado)

Tablas y campos clave (tipos finales se definen en Fase 2 con SQLAlchemy):

- **users**(id, external_ref, created_at) — soporte multi-usuario futuro.
- **email_accounts**(id, user_id FK, provider, email_address, oauth_ref, scopes, status) — sin tokens en claro; `oauth_ref` apunta a secreto cifrado externo.
- **emails**(id, account_id FK, provider_message_id UNIQUE, thread_id, sender, recipient, subject, sent_at, received_at, body_text, snippet, content_hash, is_processed, created_at) — cuerpo tratado como untrusted.
- **email_attachments**(id, email_id FK, filename, mime_type, size_bytes, storage_ref, sha256) — no se guarda binario sensible innecesario.
- **email_labels**(id, email_id FK, label) — etiquetas del proveedor.
- **institutions**(id, name, type, domain) — bancos/aseguradoras/etc. normalizados.
- **classifications**(id, email_id FK, category, subcategory, priority, risk_level, requires_action, deadline, confidence, method[rules|llm], created_at).
- **financial_events**(id, email_id FK, institution_id FK, event_type, amount, currency, masked_account, occurred_at, needs_review) — masking obligatorio.
- **insurance_events**(id, email_id FK, institution_id FK, policy_ref_masked, event_type, due_date, coverage_change).
- **work_events**(id, email_id FK, event_type, requires_reply, deadline, meeting_at).
- **documents**(id, email_id FK, doc_type, storage_ref, sha256, status) — fase 14.
- **tasks**(id, source_email_id FK, title, due_date, status).
- **alerts**(id, email_id FK, channel, priority, dedupe_key, group_id, sent_at, status).
- **agent_runs**(id, email_id FK, request_id, started_at, finished_at, status).
- **agent_results**(id, agent_run_id FK, agent_name, output_json, confidence).
- **supervisor_decisions**(id, agent_run_id FK, importance, notify_now, summary, reason, recommended_action, confidence).
- **llm_requests**(id, request_id, provider, model, tokens_prompt, tokens_completion, cost_estimate, created_at) — sin contenido sensible; hash del prompt.
- **audit_logs**(id, request_id, email_id, actor, action, detail_json, created_at).

Reglas de datos:
- Nunca: contraseñas, CVV, PIN, PAN completo, tokens, secretos.
- `masked_account` guarda solo últimos 4 dígitos u ofuscación.
- Deduplicación por `emails.provider_message_id` + `emails.content_hash`.
- `alerts.dedupe_key` / `group_id` para agrupar eventos relacionados.

## 8. Flujo de agentes

1. **Orchestrator** recibe `NormalizedEmail` + `Classification`.
2. Selecciona agentes según `category` (p.ej. finance → FinanceAgent; security → SecurityAgent). Un email puede activar más de uno.
3. Ejecuta agentes en paralelo (`asyncio.gather`), cada uno devuelve `AgentResult` tipado.
4. **Supervisor** recibe la lista de `AgentResult` + clasificación y produce `SupervisorDecision`.
5. La decisión alimenta `NotificationService`, que aplica reglas de prioridad y dedupe antes de entregar por Telegram.

El supervisor es el único punto que decide **notify_now**; los agentes no notifican.

## 9. Decisiones de despliegue

- Contenedores: `backend` (FastAPI), `mysql`, `n8n`. Telegram bot como proceso del backend o worker separado (se decide en Fase 3).
- Config por `.env` + `.env.example`; secretos nunca en imagen ni en Git.
- Migraciones con Alembic aplicadas en arranque controlado (no auto en prod sin revisión).

## 10. Estrategia anti-costos

- Reglas deterministas resuelven la mayoría de correos triviales (newsletters, recibos conocidos por dominio).
- LLM solo cuando confianza de reglas < umbral o categoría ambigua.
- Caché por `content_hash` para no reanalizar contenido idéntico.
- Registro de `llm_requests` con estimación de costo para monitoreo.
