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
