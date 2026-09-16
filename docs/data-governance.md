# Data Governance — AI Personal Intelligence Center

> Fase 0 (Discovery). Documento vivo. Última revisión: 2026-09-16.

## 1. Principios

- **Minimización**: se almacena y procesa solo lo necesario para notificar y recordar.
- **Propósito limitado**: los datos se usan para clasificación, análisis y alertas; nada más.
- **Confidencialidad por diseño**: masking/cifrado por defecto para lo sensible.

## 2. Clasificación de datos

| Nivel | Ejemplos | Tratamiento |
|-------|----------|-------------|
| **Secreto** | API keys, token del bot, tokens OAuth, clave de cifrado, credenciales DB | Nunca en DB en claro ni en Git; cifrado/gestor de secretos; jamás al LLM ni a logs |
| **Sensible** | Cuerpo de correo, montos, nombres de instituciones, identificadores de cuenta/póliza | Cifrado o masking según uso; minimizado antes del LLM; retención acotada |
| **Interno** | Clasificaciones, decisiones del supervisor, metadatos | DB con acceso de app; auditable |
| **Público/operacional** | Métricas agregadas, conteos, logs redactados | Sin PII; libre uso interno |

## 3. Reglas de masking / cifrado / hashing

| Dato | Técnica | Detalle |
|------|---------|---------|
| Número de cuenta / tarjeta | Masking | Solo últimos 4 dígitos; nunca PAN completo |
| Póliza / referencia | Masking | Ofuscación parcial para mostrar |
| Token OAuth | Cifrado en reposo | AES-GCM u equivalente; clave fuera del repo |
| `content_hash` de email | Hashing | SHA-256 para dedupe/caché, no reversible |
| OTP / códigos de seguridad | No persistir | Se detectan y se enmascaran; no se guardan |

## 4. Retención y ciclo de vida

| Dato | Retención propuesta | Acción al expirar |
|------|---------------------|-------------------|
| Cuerpo de correo (`emails.body_text`) | Configurable (p. ej. 30-90 días) | Purga o reducción a solo metadatos/resumen |
| Eventos (finance/insurance/work) | Larga (memoria útil) | Conservar; son el valor del sistema |
| `llm_requests` (sin contenido) | Media | Purga por antigüedad |
| `audit_logs` | Larga | Conservar para trazabilidad |
| Adjuntos | Solo referencia + hash | Binario no se guarda salvo necesidad explícita |

Los periodos concretos se parametrizan por `.env` y se fijan en Fase 17.

## 5. Flujo de datos hacia el LLM (minimización)

Antes de construir un prompt:
1. Aplicar masking a montos/cuentas cuando no aportan al análisis.
2. Truncar a un límite de tamaño defensivo.
3. Excluir cabeceras/técnicos irrelevantes.
4. Nunca incluir secretos ni datos de otros correos.
5. Registrar en `llm_requests` solo metadatos (proveedor, modelo, tokens, coste, hash del prompt), nunca el contenido.

## 6. PII / DLP

- Placeholders para PII en ejemplos, fixtures y documentación.
- Detección básica de patrones sensibles (tarjetas, OTP) para masking automático.
- Salida hacia Telegram revisada: resúmenes sin exponer datos sensibles innecesarios.

## 7. Derechos del usuario / borrado

- El usuario es el propietario de sus datos; debe existir una vía para purgar
  correos/eventos (comando administrativo o script) — se especifica en Fase 17.
- Borrado en cascada coherente con las FKs del modelo de datos.

## 8. Ubicación y soberanía

- Por defecto, todo el almacenamiento es local/self-hosted (MySQL en Docker).
- Si se usa OpenAI, el contenido minimizado sale del entorno; Ollama permite
  operación totalmente local para casos sensibles (seleccionable por config).
