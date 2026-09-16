# HELIOS COMMAND — Architecture Review

> Fase de diseño (no implementación). Última revisión: 2026-09-16.
> Estado: **aprobado como fase futura** (ver ADR-024). Se implementará **después
> de la Fase 6**, con autenticación de HELIOS como prerrequisito.

HELIOS COMMAND es el frontend / centro de control de HELIOS: permite al usuario
conectar, ver y desconectar servicios (empezando por Gmail/Outlook) desde una
interfaz gráfica, sin editar `.env`. Este documento es la revisión de
arquitectura previa a implementar.

## 1. Current State

- Backend Python (FastAPI) con fases 0-5 completas: health, DB (18 tablas),
  Telegram bot, `EmailProvider`/`ProviderRegistry`/`GmailProvider`/`FakeEmailProvider`,
  cifrado (`security/encryption.py`), pipeline con `audit_logs`.
- `email_accounts` existe con: `user_id`, `provider`, `email_address`,
  `oauth_ref`, `scopes`, `status` (texto libre), timestamps.
- **No hay frontend** ni **autenticación de usuario** todavía. La app es
  mono-usuario self-hosted en la práctica.
- Config OAuth (`GOOGLE_CLIENT_ID/SECRET`) vive en `.env`; el client-secret JSON
  en `secrets/` (git-ignored).

## 2. Existing Components Reused

- `ProviderRegistry` → base del Connection Manager (no se reemplaza).
- `EmailProvider` contract → capacidades y estados se derivan de aquí.
- `security/encryption.py` (Fernet) → cifrado de refresh tokens.
- `audit_logs` → eventos de conexión.
- `users` / `email_accounts` → identidad y cuentas (con migración, ver §8).

## 3. Architecture Proposal

```text
USER → HELIOS COMMAND (frontend) → HELIOS CORE/API (FastAPI)
     → ConnectionManager → ProviderRegistry → Gmail/Outlook/… → External APIs
```

El frontend consume **solo** APIs del backend. Nunca habla con Google/Microsoft/
MySQL/Ollama directamente. El Connection Manager es una capa de servicio nueva
sobre el registry existente.

## 4. Connection Manager (backend, nuevo — `services/connections.py`)

Responsabilidades: iniciar OAuth, manejar callback, validar `state` (anti-CSRF),
identificar al usuario HELIOS, asociar la cuenta externa al usuario correcto,
cifrar/guardar tokens, refrescar, detectar expiración, desconectar, revocar,
consultar estado y permisos, auditar, evitar duplicados, normalizar errores.
Sin lógica específica de proveedor: delega en el registry.

## 5. OAuth Architecture

```text
Frontend "Connect Gmail" → POST /connections/gmail/connect
  → backend genera authorization_url + state (CSRF), guarda state
  → redirect a Google → usuario consiente (scope readonly)
  → GET /connections/gmail/callback?code&state
  → backend valida state, intercambia code→tokens, cifra refresh token,
    guarda en email_accounts, audita → "Connected"
```

Reglas: el frontend nunca ve client_secret ni tokens; tokens nunca en URL ni
logs; scopes mínimos (`gmail.readonly`, Graph `Mail.Read`+`User.Read`).

## 6. Frontend Architecture

- **React + TypeScript + Vite + Tailwind**, en un paquete **aislado `frontend/`**
  con su propio Dockerfile, servido detrás del backend/reverse-proxy. No se
  acopla al backend Python.
- Empezar con un **minimal shell**: Dashboard + Connections. El resto de
  secciones (Emails, Intelligence, Alerts, …) llegan en fases posteriores.
- Provider-agnóstico: la UI se dibuja desde metadata del backend (nada de
  `if provider == "gmail"`).

## 7. API Proposal (v1, con auth)

```text
GET  /api/v1/connections/providers        # metadata de proveedores disponibles
GET  /api/v1/connections                   # cuentas del usuario autenticado
POST /api/v1/connections/{provider}/connect
GET  /api/v1/connections/{provider}/callback
POST /api/v1/connections/{id}/disconnect
POST /api/v1/connections/{id}/refresh
GET  /api/v1/connections/{id}
```

Todos requieren autenticación de HELIOS y filtran por `user_id` (evita IDOR).

## 8. Database Impact (migración estructural — requiere ADR)

`email_accounts` necesita, para soportar el ciclo de vida y multi-cuenta:
- `external_account_id` (id estable del proveedor; el email puede cambiar).
- `status` normalizado (enum aplicado en app): CONNECTED, CONNECTING, EXPIRED,
  ERROR, DISCONNECTED, REVOKED, REAUTH_REQUIRED.
- `last_sync_at`, `last_error`, `connected_at`, `token_expires_at`.
- Cambiar la unicidad de `(provider, email_address)` a
  `(user_id, provider, external_account_id)`.

Se documenta ahora; se aplica con migración Alembic **tras aprobación** (ADR-027).

## 9. Security Impact

- Introduce **autenticación de HELIOS** (prerrequisito, ADR-025): sin ella hay
  riesgo de IDOR (asociar/leer cuentas de otros).
- `state` OAuth firmado/aleatorio con expiración (anti-CSRF).
- Tokens cifrados en reposo (reusa Fernet); nunca en frontend/localStorage/logs/URL.
- Errores OAuth traducidos a mensajes amigables; detalle solo en `audit_logs`.
- Tests de seguridad: CSRF, state tampering, IDOR, XSS, token leakage.

## 10. Multiple Account Strategy

Varias cuentas por proveedor y por usuario. La clave es
`(user_id, provider, external_account_id)`. La UI ofrece "Add connection" y
lista cada cuenta con su estado.

## 11. Provider Extensibility

Nuevos proveedores (Outlook, IMAP, Yahoo, Drive, OneDrive, Slack, Telegram…) se
añaden implementando el contrato y registrándose. El frontend no cambia: lee
metadata + capabilities del backend.

## 12. UX Proposal

Estética de "centro de control" (tecnológica, limpia, modo oscuro opcional),
priorizando claridad, jerarquía, accesibilidad y estado de conexiones. Connections
muestra tarjetas por proveedor con estado, permisos, última sync y acciones.

## 13. Testing Strategy

- Backend: connection manager, state validation, encryption, token lifecycle,
  múltiples/duplicadas cuentas, callbacks inválidos, credenciales expiradas/revocadas.
- Frontend: provider cards, estados, connect/disconnect, errores, loading, multi-cuenta.
- Seguridad: CSRF, state tampering, token leakage, IDOR, XSS, respuestas maliciosas.

## 14. Documentation Changes

Este archivo + `docs/connections.md`, `docs/oauth-architecture.md`,
`docs/frontend-architecture.md` (a crear en su fase). Actualizar `architecture.md`
y `security.md` cuando se implemente.

## 15. Roadmap Integration

**Recomendación (mi criterio):** HELIOS COMMAND va como **Fase 5.7**, **después
de la Fase 6** (que el cerebro funcione end-to-end primero) y **antes** del resto
de fases de inteligencia de Telegram. Orden interno por dependencias:
1. Auth de HELIOS (mínima real) → 2. Migración `email_accounts` → 3. Connection
Manager + endpoints → 4. OAuth initiation + callback → 5. Frontend shell.

## 16. Risks

- **Desvío de foco**: es una vertical grande; se mitiga haciéndola tras la Fase 6.
- **IDOR/seguridad** si se salta la auth: mitigado haciéndola prerrequisito.
- **Segunda toolchain (Node)**: aislada en `frontend/` para no contaminar el backend.
- **Migración de datos**: `email_accounts` cambia; ADR + migración reversible.

## 17. Recommended Implementation Phases

- **Fase 6** (siguiente, YA): Classification Engine con LLM.
- **Fase 5.7 — HELIOS COMMAND FOUNDATION** (después): auth + connection manager +
  OAuth + frontend shell (Dashboard + Connections).
- Fases 7-13 de agentes/supervisor/telegram continúan según roadmap.

## 18. Files That Would Be Created/Modified (cuando se implemente)

Backend: `services/connections.py`, `api/connections.py`, `api/auth.py`,
`security/oauth_state.py`, migración de `email_accounts`. Frontend: paquete
`frontend/` (React+TS+Vite+Tailwind) con Dashboard y Connections. Docs listados en §14.

## 19. Decisions Requiring Approval

- ADR-024 HELIOS COMMAND como fase (aceptado).
- ADR-025 Autenticación mínima real de HELIOS (aceptado, prerrequisito).
- ADR-026 Frontend aislado React+TS+Vite+Tailwind (aceptado).
- ADR-027 Migración de `email_accounts` (aceptado el enfoque; el SQL exacto se
  revisa al implementar la fase).

## 20. Final Recommendation

Aprobar HELIOS COMMAND como **Fase 5.7**, ejecutarla **después de la Fase 6**,
con auth como primer paso. Mantener el frontend aislado y el principio
READ + ANALYZE + NOTIFY (sin write/send/delete). Proceder ahora con la Fase 6.
