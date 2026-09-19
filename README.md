# ☀️ HELIOS — Personal Intelligence & Awareness System

> Observe → Understand → Classify → Prioritize → Alert → Remember

Sistema personal de agentes de IA que ingiere correo electrónico vía APIs
oficiales (OAuth de solo lectura), lo clasifica, lo analiza con agentes
especializados, decide prioridad/riesgo/acción con un agente supervisor,
persiste eventos importantes y notifica por Telegram.

Visión completa e identidad de módulos en [`docs/vision.md`](docs/vision.md).

> **v1 = READ + ANALYZE + NOTIFY.** El sistema no mueve dinero, no cambia
> credenciales y no responde correos. Todo contenido de correo se trata como
> **UNTRUSTED DATA**.

## Estado

En construcción por fases. Fase actual: **Fase 6 — Classification Engine**.

| Fase | Contenido | Estado |
|------|-----------|--------|
| 0 | Discovery & Architecture (docs) | Completada |
| 1 | Bootstrap (FastAPI, MySQL, Docker, health) | Completada |
| 2 | Database (SQLAlchemy + Alembic) | Completada |
| 3 | Telegram bot (/start, /help, allow-list) | Completada |
| 4 | Email Provider (EmailProvider, Gmail read-only, registry) | Completada |
| 5 | Email Pipeline (fetch→parse→normalize→store→classify) | Completada |
| 6 | Classification Engine (híbrido reglas + LLM Ollama) | En curso |
| 7-11 | Agentes (Finance/Insurance/Work/Security) + Supervisor | Pendiente |
| 5.7 | HELIOS COMMAND (frontend + connections) tras Fase 6 | Diseñada ([docs](docs/helios-command.md)) |
| 12-17 | Telegram intelligence, reports, documents, memory, hardening | Pendiente |

## Arquitectura (resumen)

```text
Gmail/Outlook ─OAuth(ro)→ Ingestor → Normalizer → Classifier (reglas→LLM)
   → Orchestrator (Finance/Insurance/Work/Security) → Supervisor
   → MySQL + Notification (reglas+dedupe) → Telegram
```

LLM por defecto: **Ollama local** (privacidad; ver `docs/decisions.md` ADR-016).
Detalle completo en [`docs/architecture.md`](docs/architecture.md).

## Stack

- Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic
- MySQL, Docker, Docker Compose
- Ollama (LLM local por defecto) / OpenAI (opt-in)
- N8N (orquestación), python-telegram-bot
- Calidad: Ruff, Black, mypy, pytest

## Requisitos previos

- Docker y Docker Compose
- (Opcional para desarrollo local sin Docker) Python 3.12+

## Configuración

```bash
cp .env.example .env
# Edita .env con tus valores. NUNCA subas .env a git.
```

Variables clave en [`.env.example`](.env.example). Ningún secreto se guarda en
código ni en el repositorio.

## Ejecución (Docker)

```bash
docker compose up -d --build
```

Servicios: `backend` (API), `frontend` (HELIOS COMMAND UI, puerto 5173), `mysql`, `n8n`, `ollama`.

## HELIOS COMMAND (frontend)

Interfaz web para conectar cuentas (Gmail, etc.) sin editar `.env`. Requiere un
usuario propietario configurado:

```bash
# Genera el hash de la contraseña del propietario y ponlo en .env (OWNER_PASSWORD_HASH)
python backend/scripts/hash_password.py
```

Luego abre `http://localhost:5173`, inicia sesión y ve a Connections.
Detalle en [`docs/frontend-architecture.md`](docs/frontend-architecture.md) y
[`docs/helios-command.md`](docs/helios-command.md).

## Health check

```bash
curl http://localhost:8000/health
# {"status":"ok","app":"ai-personal-intelligence","env":"local"}
```

## Desarrollo local (sin Docker)

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload
```

## Testing

```bash
pip install -r backend/requirements.txt
pytest backend/tests -q
```

## Calidad

```bash
ruff check backend
black --check backend
mypy backend/app
```

## Seguridad

- Todo email es UNTRUSTED; defensa anti prompt injection por diseño.
- Sin contraseñas/CVV/PIN/PAN completo/tokens/secretos en la base de datos.
- Menor privilegio: correo READ-ONLY, Telegram SEND.
- Detalle en [`docs/security.md`](docs/security.md),
  [`docs/threat-model.md`](docs/threat-model.md) y
  [`docs/data-governance.md`](docs/data-governance.md).

## Documentación

- [`docs/vision.md`](docs/vision.md)
- [`docs/requirements.md`](docs/requirements.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/security.md`](docs/security.md)
- [`docs/threat-model.md`](docs/threat-model.md)
- [`docs/data-governance.md`](docs/data-governance.md)
- [`docs/operations.md`](docs/operations.md)
- [`docs/agents.md`](docs/agents.md)
- [`docs/testing.md`](docs/testing.md)
- [`docs/decisions.md`](docs/decisions.md)

## Troubleshooting

- **`/health` no responde**: revisa `docker compose logs backend` y que el puerto
  `API_PORT` no esté ocupado.
- **Backend no conecta a MySQL**: espera al healthcheck de `mysql`; verifica
  `DATABASE_URL` y credenciales en `.env`.
- **Ollama sin modelo**: descarga el modelo con `docker exec -it <ollama> ollama pull llama3.1`.

## Licencia

MIT. Ver [`LICENSE`](LICENSE).
