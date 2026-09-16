# Operations & Reliability — AI Personal Intelligence Center

> Fase 0 (Discovery). Documento vivo. Última revisión: 2026-09-16.

## 1. Entornos

- `local` (desarrollo), `prod` (self-hosted). Seleccionado por `APP_ENV`.
- Config exclusivamente por variables de entorno; sin secretos en imagen.

## 2. Topología de despliegue (Docker Compose)

| Servicio | Rol | Exposición |
|----------|-----|-----------|
| `backend` | FastAPI + pipeline | Puerto API interno; expuesto solo lo necesario |
| `mysql` | Persistencia | Red interna, no público |
| `n8n` | Orquestación | UI protegida; llama al backend con token |
| `bot` (o parte de backend) | Telegram | Salida a Telegram API |

Redes segmentadas: los servicios se comunican por red interna de Docker; MySQL
nunca se publica al host salvo para depuración explícita.

## 3. Health checks y readiness

- `GET /health`: liveness (proceso vivo).
- `GET /ready` (propuesto): readiness (DB alcanzable, config válida, proveedor LLM configurado).
- Healthchecks de Compose para orden de arranque (DB lista antes que backend).

## 4. Manejo de errores y resiliencia

- **Idempotencia**: `provider_message_id` + `content_hash` evitan reprocesar/re-notificar.
- **Reintentos**: backoff exponencial acotado en llamadas a proveedores (email, LLM, Telegram).
- **Dead-letter**: emails que fallan repetidamente se marcan y se aíslan, sin bloquear el pipeline.
- **Degradación con gracia**: si el LLM no está disponible, las reglas siguen clasificando; si Telegram falla, la alerta queda persistida y se reintenta.
- **Timeouts** explícitos en toda llamada externa.
- **Circuit breaker** (propuesto) para el proveedor LLM ante fallos sostenidos.

## 5. Rate limiting y control de coste

- Rate limit en `POST /emails/process` (protege de ráfagas y abuso — T-D2).
- Presupuesto de LLM: límite de llamadas/coste por ventana; si se supera, degradar a solo reglas y avisar.
- Caché por `content_hash` para no reanalizar contenido idéntico.

## 6. Observabilidad

- Logs estructurados (JSON) con `request_id`, `email_id`, `agent_id`, `timestamp`, `processing_status`.
- Redacción automática de secretos/PII en el logger.
- Métricas propuestas: correos procesados, % resuelto por reglas vs LLM, alertas enviadas, errores, latencia de pipeline, coste LLM.
- Trazabilidad extremo a extremo por `request_id`.

## 7. Backups y recuperación (DR)

- Backup periódico de MySQL (dump cifrado, retención definida en Fase 17).
- Backup separado y cifrado de la clave de cifrado / material OAuth (no junto a la DB).
- Prueba de restauración documentada (un backup no probado no es un backup).
- RPO/RTO objetivo a definir según criticidad en Fase 17.

## 8. Gestión de secretos y rotación

- Secretos vía `.env` (local) o gestor externo (prod).
- Rotación planificada de: token del bot, API keys LLM, credenciales DB, clave de cifrado.
- Revocación inmediata de tokens OAuth ante sospecha de compromiso.

## 9. Dependencias y cadena de suministro

- Versiones fijadas/pinneadas en `requirements.txt`.
- Auditoría de dependencias (F17): escaneo de vulnerabilidades y de secretos.
- Preferir paquetes mantenidos; verificar nombres para evitar typosquatting.

## 10. Runbook mínimo (se ampliará)

- "No llegan alertas": revisar bot, lista blanca, cola de alertas, logs por `request_id`.
- "Coste LLM alto": revisar % LLM vs reglas, caché, presupuesto.
- "Pipeline atascado": revisar dead-letter, reintentos, salud de DB/LLM.
- "Sospecha de fuga": rotar secretos, revocar OAuth, revisar `audit_logs`.
