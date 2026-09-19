# Architecture Decision Records — AI Personal Intelligence Center

> Fase 0 (Discovery). Documento vivo. Última revisión: 2026-09-16.

Formato: cada decisión tiene contexto, decisión, alternativas, consecuencias y
estado (`accepted` | `proposed` | `superseded`).

---

## ADR-001 — Backend en FastAPI + Pydantic
- **Estado**: accepted
- **Contexto**: API asíncrona, contratos tipados, buena integración con Pydantic.
- **Decisión**: FastAPI como framework HTTP; Pydantic para todos los contratos.
- **Alternativas**: Flask (menos async/typing nativo), Django (pesado para este caso).
- **Consecuencias**: async de primera clase; validación estricta de entrada/salida.

## ADR-002 — MySQL + SQLAlchemy + Alembic
- **Estado**: accepted
- **Contexto**: requerido por el proyecto; modelo relacional normalizado.
- **Decisión**: MySQL como store, SQLAlchemy como ORM, Alembic para migraciones.
- **Consecuencias**: migraciones versionadas; esquema explícito.

## ADR-003 — Abstracción LLMProvider
- **Estado**: accepted
- **Contexto**: no acoplar a un único proveedor; costo y disponibilidad varían.
- **Decisión**: interfaz `LLMProvider` con `OpenAIProvider` y `OllamaProvider`;
  selección por config; salida estructurada validada por Pydantic.
- **Consecuencias**: intercambiabilidad de proveedor; tests con LLM fake.

## ADR-004 — Clasificación híbrida (reglas → LLM)
- **Estado**: accepted
- **Contexto**: costo y determinismo (RNF-06).
- **Decisión**: `RuleClassifier` primero; LLM solo bajo umbral/ambigüedad; caché
  por `content_hash`.
- **Consecuencias**: menor costo; mayoría de correos triviales sin LLM.

## ADR-005 — Todo email es UNTRUSTED; defensa anti prompt injection
- **Estado**: accepted
- **Contexto**: emails pueden contener instrucciones maliciosas.
- **Decisión**: separación estricta system/config/email/agent-output; salida
  estructurada; sanitización; sin acciones ejecutables en v1. Ver `security.md`.
- **Consecuencias**: robustez ante inyección; tests adversariales obligatorios.

## ADR-006 — v1 = READ + ANALYZE + NOTIFY
- **Estado**: accepted
- **Contexto**: minimizar riesgo; el supervisor no debe mutar el mundo.
- **Decisión**: no pagos/transferencias/cambios de credenciales/respuestas
  automáticas; solo recomendaciones.
- **Consecuencias**: superficie de daño reducida aunque el LLM sea manipulado.

## ADR-007 — Menor privilegio (email READ-ONLY, telegram SEND)
- **Estado**: accepted
- **Decisión**: scope Gmail `readonly`; bot con permisos de envío; DB con usuario
  de aplicación acotado; N8N vía token de servicio al endpoint.

## ADR-008 — N8N como orquestación, no lógica de negocio
- **Estado**: accepted
- **Decisión**: N8N detecta eventos y llama `POST /emails/process`; la lógica vive
  en Python.
- **Consecuencias**: lógica testeable y versionada en el repo, no en flujos.

## ADR-009 — Secretos fuera de Git; `.env` + `.env.example`
- **Estado**: accepted
- **Decisión**: `.gitignore` excluye secretos; redacción en logs; tokens OAuth
  no en claro en DB (cifrado/gestor; detalle final en Fase 4).

---

# Propuestas pendientes de aprobación (Regla 27)

Estas desviaciones respecto a la estructura del prompt se proponen antes de
implementar. **No se implementan hasta tu confirmación.**

> Estado de las propuestas: PROP-001..004 **aprobadas** por el usuario (2026-09-16).
> Decisión adicional: **Ollama local** es el proveedor LLM por defecto (ADR-016).

## PROP-001 — Paquete `classification/` propio
- **Estado**: accepted
- **Problema**: el motor híbrido (reglas + LLM + caché) es una responsabilidad
  cohesiva; incrustarlo en `services/` o `agents/` mezcla capas.
- **Alternativa**: paquete `app/classification/` con `engine.py`, `rules.py`,
  `llm_classifier.py`.
- **Ventajas**: cohesión, testabilidad aislada, límites claros.
- **Desventajas**: un paquete más que mantener.
- **Impacto**: bajo; solo organización de carpetas.

## PROP-002 — Paquete `observability/`
- **Estado**: accepted
- **Problema**: logging estructurado + contexto de request (request_id) es
  transversal; disperso genera inconsistencia y riesgo de fugas en logs.
- **Alternativa**: `app/observability/` con logger estructurado y middleware de
  contexto/redacción.
- **Ventajas**: logs consistentes, redacción de secretos centralizada (RNF-04).
- **Desventajas**: pequeña capa adicional.
- **Impacto**: bajo; refuerza seguridad y auditoría.

## PROP-003 — Ubicación del bot de Telegram (proceso vs worker)
- **Estado**: accepted (dirección aprobada; alternativa concreta se fija en Fase 3)
- **Problema**: el bot con long-polling y FastAPI en el mismo proceso pueden
  competir por el loop.
- **Alternativas**: (a) worker/proceso separado para el bot; (b) webhook de
  Telegram servido por FastAPI.
- **Ventajas/Desventajas**: (a) aísla fallos pero añade un servicio; (b) menos
  procesos pero requiere URL pública/HTTPS.
- **Impacto**: medio; afecta docker-compose. Se resolverá con datos en Fase 3.

## PROP-004 — Alembic dentro de `backend/alembic/`
- **Estado**: accepted
- **Problema**: el prompt no fija la ubicación de Alembic.
- **Alternativa**: mantener migraciones en `backend/alembic/` junto al código del
  backend para cohesión y build de imagen.
- **Impacto**: bajo.

---

# ADRs adicionales (seguridad y fiabilidad)

## ADR-010 — Cifrado en reposo para material OAuth y datos sensibles
- **Estado**: accepted
- **Contexto**: los tokens OAuth y ciertos datos son sensibles (A2, A3).
- **Decisión**: cifrado autenticado (AES-GCM o equivalente) con clave gestionada
  fuera del repositorio; masking para lo que solo se muestra.
- **Consecuencias**: fuga de DB no expone tokens en claro. Ver `data-governance.md`.

## ADR-011 — Idempotencia y dead-letter en el pipeline
- **Estado**: accepted
- **Decisión**: dedupe por `provider_message_id` + `content_hash`; reintentos con
  backoff acotado; emails que fallan repetidamente van a dead-letter sin bloquear.
- **Consecuencias**: robustez y no re-notificación. Ver `operations.md §4`.

## ADR-012 — Rate limiting y presupuesto de LLM
- **Estado**: accepted
- **Decisión**: rate limit en `POST /emails/process`; presupuesto de coste/llamadas
  LLM por ventana; degradación a solo reglas al superarlo.
- **Consecuencias**: protección ante DoS (T-D2) y coste (R-06). Ver `operations.md §5`.

## ADR-013 — Backups cifrados con restauración probada
- **Estado**: accepted
- **Decisión**: backup periódico y cifrado de MySQL; la clave de cifrado se
  respalda por separado; se documenta y prueba la restauración.
- **Consecuencias**: recuperación ante desastre (R-10). Ver `operations.md §7`.

## ADR-014 — Modelo de amenazas STRIDE como artefacto vivo
- **Estado**: accepted
- **Decisión**: mantener `docs/threat-model.md`; cada control P1 tiene test en el
  gate de release (F17).
- **Consecuencias**: seguridad verificable, no solo declarativa.

## ADR-015 — SQL siempre parametrizado; errores externos genéricos
- **Estado**: accepted
- **Decisión**: acceso a datos exclusivamente vía ORM con parámetros; respuestas
  de error al exterior sin detalle interno.
- **Consecuencias**: mitiga SQLi (R-12) y fuga por errores (R-13).

## ADR-016 — Ollama local como proveedor LLM por defecto
- **Estado**: accepted
- **Contexto**: el usuario prioriza privacidad; el contenido de correo es sensible.
- **Decisión**: `OllamaProvider` es el proveedor por defecto (`LLM_PROVIDER=ollama`);
  el contenido se analiza localmente. `OpenAIProvider` queda disponible pero opt-in.
- **Consecuencias**: máxima privacidad (nada de contenido sale del entorno);
  requiere hardware local para Ollama. La abstracción `LLMProvider` (ADR-003) se
  mantiene intacta.

## ADR-017 — Rebranding a HELIOS
- **Estado**: accepted
- **Contexto**: el usuario aprobó adoptar "HELIOS — Personal Intelligence &
  Awareness System" como nombre e identidad del proyecto.
- **Decisión**: HELIOS es el nombre oficial (docs, README, `APP_NAME`). Se
  introduce un "ubiquitous language" (HELIOS EYE/BRAIN/ORCHESTRATOR/SUPERVISOR/
  BOT/WATCH/…) mapeado a las capas de código en `docs/vision.md`. **No** se
  renombran paquetes de código para no romper imports sin beneficio.
- **Consecuencias**: identidad coherente; el código sigue estable.

## ADR-018 — `security_events` como tabla dedicada
- **Estado**: accepted
- **Contexto**: los eventos de seguridad (inicios de sesión, accesos, cambios de
  contraseña, OTP, actividad sospechosa) merecen modelado propio, igual que
  finance/insurance/work.
- **Decisión**: añadir tabla `security_events` en la Fase 4/5 (cuando el pipeline
  la consuma), con masking obligatorio y prohibición de persistir OTP/códigos.
- **Consecuencias**: memoria de seguridad consultable; alineado con SecurityAgent.

## ADR-019 — Comandos Telegram ampliados
- **Estado**: accepted
- **Decisión**: incluir `/seguridad` y `/documentos` además de los comandos ya
  planificados. `/start` y `/help` se implementan en la Fase 3; el resto en F12.

## ADR-020 — Human-in-the-loop lock para acciones futuras
- **Estado**: accepted
- **Contexto**: reforzar el candado de "no ejecutar acciones" más allá de v1.
- **Decisión**: cualquier capacidad futura de ejecutar acciones (responder,
  pagar, cambiar config) requiere un paso explícito de confirmación humana y su
  propio ADR. No debe existir ninguna ruta de código que actúe sobre el mundo
  sin ese gate. Registrado también en la steering `.kiro/steering/security.md`.
- **Consecuencias**: invariante arquitectónica de seguridad verificable.

## ADR-021 — Directivas de seguridad como steering permanente
- **Estado**: accepted
- **Decisión**: las directivas de seguridad/ingeniería viven en
  `.kiro/steering/security.md` (always on), de modo que apliquen a todo cambio
  del repositorio.
- **Consecuencias**: la postura de seguridad no depende de recordarla en cada tarea.

## PROP-005 — Redis para caché / rate-limiting / ventana de dedupe
- **Estado**: proposed (diferido)
- **Problema**: HELIOS sugiere Redis en el stack. Hoy no hay necesidad concreta:
  la caché de clasificación se resuelve por `content_hash` en DB y el rate
  limiting aún no existe.
- **Alternativa**: introducir Redis cuando la Fase 5/6 muestre necesidad real
  (throughput, ventanas de dedupe en memoria, rate limit distribuido).
- **Ventajas**: rendimiento y TTL naturales. **Desventajas**: un servicio más que
  operar y asegurar. **Impacto**: medio (docker-compose + config).
- **Decisión**: NO adoptar todavía; evitar sobre-ingeniería. Reabrir en Fase 5/6.

## ADR-022 — Email provider abstraction + registry (multi-provider)
- **Estado**: accepted
- **Contexto**: HELIOS debe ingerir de varias cuentas y varios tipos de proveedor
  (Gmail ahora; Outlook/IMAP/otros después) sin acoplar el pipeline.
- **Decisión**: interfaz `EmailProvider` (Protocol, solo lectura) con objetos de
  datos neutrales (`RawEmail`/`ProviderMessageRef`/`RawAttachment`) y un
  `ProviderRegistry` de factorías por nombre. Los proveedores se auto-registran
  al importarse. Guía completa en `docs/email-providers.md`.
- **Consecuencias**: añadir un proveedor no cambia el pipeline; credenciales por
  cuenta (no globales); errores uniformes vía `EmailProviderError`.

## ADR-023 — Gmail read-only + refresh token cifrado
- **Estado**: accepted
- **Decisión**: `GmailProvider` usa exclusivamente el scope `gmail.readonly`;
  la identidad OAuth (client_id/secret) viene del entorno y el refresh token por
  cuenta se guarda cifrado (Fernet, ADR-010) y solo se descifra en memoria. El
  SDK síncrono se ejecuta en hilos (`asyncio.to_thread`) para no bloquear el loop.
  El client-secret JSON vive en `secrets/` (git-ignored), nunca en el repo.
- **Consecuencias**: mínimo privilegio real sobre el correo; sin secretos en git.

## ADR-024 — HELIOS COMMAND como fase (Fase 5.7, tras la Fase 6)
- **Estado**: accepted
- **Contexto**: el usuario quiere conectar cuentas desde una UI, sin editar `.env`.
- **Decisión**: HELIOS COMMAND (frontend + Connection Manager) se implementa como
  **Fase 5.7, después de la Fase 6** (que el cerebro funcione primero end-to-end).
  El frontend consume solo APIs del backend. Diseño en `docs/helios-command.md`.
- **Consecuencias**: la inteligencia madura antes de exponer la conexión real de
  cuentas; se evita desviar el foco a una vertical grande demasiado pronto.

## ADR-025 — Autenticación mínima real de HELIOS (prerrequisito de Connections)
- **Estado**: accepted
- **Contexto**: exponer OAuth de cuentas sin identificar al usuario HELIOS crea
  riesgo de IDOR (acceder/asociar cuentas ajenas).
- **Decisión**: introducir autenticación de HELIOS (sesión + usuario propietario,
  o JWT local) **antes** de los endpoints de conexión. Separar siempre identidad
  interna HELIOS de identidad del proveedor externo.
- **Consecuencias**: todos los endpoints de conexión filtran por `user_id`; sin
  auth no hay connections.

## ADR-026 — Frontend aislado (React + TypeScript + Vite + Tailwind)
- **Estado**: accepted
- **Decisión**: el frontend vive en un paquete `frontend/` separado, con su propio
  Dockerfile, servido detrás del backend/reverse-proxy. No se acopla al backend
  Python. Empieza como "minimal shell" (Dashboard + Connections).
- **Consecuencias**: la toolchain de Node queda aislada; el backend sigue siendo
  Python puro y desplegable por sí mismo.

## ADR-027 — Migración estructural de `email_accounts` (para el ciclo de vida de conexión)
- **Estado**: accepted (enfoque; SQL exacto se revisa al implementar la Fase 5.7)
- **Decisión**: añadir `external_account_id`, `status` normalizado
  (CONNECTED/CONNECTING/EXPIRED/ERROR/DISCONNECTED/REVOKED/REAUTH_REQUIRED),
  `last_sync_at`, `last_error`, `connected_at`, `token_expires_at`; cambiar la
  unicidad a `(user_id, provider, external_account_id)`. Migración Alembic
  reversible cuando se implemente la fase.
- **Consecuencias**: soporte real de multi-cuenta/multi-usuario y estados de
  conexión; requiere migración de datos.

## ADR-028 — Memory: structured search now, semantic search deferred
- **Estado**: accepted
- **Contexto**: la Fase 15 pide memoria consultable. La búsqueda semántica
  (embeddings + vector DB) aporta valor pero añade infraestructura y un pipeline
  de embeddings.
- **Decisión**: implementar primero **búsqueda estructurada por palabra clave**
  (`MemoryService` + `search_emails` con LIKE parametrizado y wildcards
  escapados). La **búsqueda semántica** queda propuesta: Ollama puede generar
  embeddings localmente (coherente con ADR-016) y se evaluaría un vector store
  (o pgvector/Redis) cuando el volumen lo justifique. Reabrir junto a PROP-005.
- **Consecuencias**: memoria útil hoy sin infraestructura nueva; camino claro a
  semántica sin rediseño (el `MemoryService` es el punto de extensión).
