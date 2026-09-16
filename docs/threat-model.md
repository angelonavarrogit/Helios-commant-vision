# Threat Model — AI Personal Intelligence Center

> Fase 0 (Discovery). Documento vivo. Última revisión: 2026-09-16.
> Metodología: STRIDE sobre los límites de confianza del sistema.

## 1. Alcance y activos a proteger

Activos primarios:
- **A1** Contenido de correo del usuario (personal, financiero, laboral).
- **A2** Tokens OAuth de las cuentas de correo.
- **A3** Secretos del sistema (API keys LLM, token del bot, credenciales DB, clave de cifrado).
- **A4** Base de datos (eventos, auditoría, memoria).
- **A5** Canal de Telegram con el usuario (integridad de las alertas).
- **A6** Disponibilidad del pipeline de procesamiento.

## 2. Límites de confianza (trust boundaries)

```text
[Internet] ── Gmail/Outlook API ──▶ (TB1) ──▶ Backend
[Internet] ── Telegram API ───────▶ (TB2) ──▶ Bot
[N8N] ── POST /emails/process ────▶ (TB3) ──▶ FastAPI
[Backend] ── prompt ──────────────▶ (TB4) ──▶ LLM (OpenAI/Ollama)
[Backend] ── SQL ─────────────────▶ (TB5) ──▶ MySQL
Email body (UNTRUSTED) ───────────▶ (TB6) ──▶ Clasificador/Agentes/LLM
```

`TB6` es el límite más crítico: datos no confiables que atraviesan clasificador,
agentes y LLM.

## 3. Análisis STRIDE

### Spoofing (suplantación)
- **T-S1**: Remitente falsificado (spoofing de "banco"). → Los agentes no confían
  en el remitente como verdad; correlación por dominio verificado
  (SPF/DKIM/DMARC cuando el proveedor lo expone) y lenguaje calibrado.
- **T-S2**: Usuario no autorizado en Telegram. → Lista blanca de user IDs;
  mensajes de rechazo neutros.
- **T-S3**: Llamadas falsas a `POST /emails/process`. → Token de servicio +
  validación de origen; rate limiting.

### Tampering (manipulación)
- **T-T1**: Manipulación de payload en tránsito. → HTTPS/TLS en todos los saltos externos.
- **T-T2**: Manipulación de la decisión vía prompt injection. → Ver `security.md §3`;
  salida estructurada validada; sin acciones ejecutables.
- **T-T3**: Manipulación de la DB. → Usuario de DB acotado, sin DDL en runtime;
  consultas parametrizadas (nunca SQL por concatenación).

### Repudiation (repudio)
- **T-R1**: "No sé por qué recibí esta alerta". → `audit_logs` con la cadena
  completa: email → clasificación → agentes → decisión → notificación.

### Information Disclosure (divulgación)
- **T-I1**: Fuga de secretos en logs. → Redacción centralizada en el logger.
- **T-I2**: Fuga de datos sensibles al LLM. → Minimización + masking antes del prompt.
- **T-I3**: OTP/códigos en Telegram. → SecurityAgent nunca envía códigos completos.
- **T-I4**: Secretos en Git. → `.gitignore`, escaneo de secretos en CI (F17).
- **T-I5**: Mensajes de error verbosos. → Errores genéricos al exterior; detalle solo en logs internos.

### Denial of Service (denegación)
- **T-D1**: Correo gigante agota memoria/coste. → Límites de tamaño y truncado defensivo.
- **T-D2**: Ráfaga de eventos a `/emails/process`. → Rate limiting + cola/backpressure.
- **T-D3**: Bucle de reintentos. → Reintentos acotados con backoff y dead-letter.

### Elevation of Privilege (elevación)
- **T-E1**: LLM manipulado intenta acciones. → No hay herramientas de acción en v1
  (READ+ANALYZE+NOTIFY). Cualquier acción futura pasará por confirmación humana.
- **T-E2**: Token de correo con scope excesivo. → Scope `readonly` estricto.
- **T-E3**: Contenedor comprometido accede a otros servicios. → Redes Docker
  segmentadas; MySQL no expuesto; menor privilegio por servicio.

## 4. Matriz de riesgo (resumen)

| ID | Amenaza | Prob. | Impacto | Prioridad | Estado control |
|----|---------|-------|---------|-----------|----------------|
| T-T2 | Prompt injection cambia decisión | Media | Alto | P1 | Diseñado |
| T-I2 | Datos sensibles al LLM | Media | Alto | P1 | Diseñado |
| T-S1 | Remitente falsificado | Media | Medio | P2 | Diseñado |
| T-S3 | Endpoint sin auth | Baja | Alto | P1 | Diseñado |
| T-I1/T-I4 | Fuga de secretos | Baja | Alto | P1 | Diseñado |
| T-D1/T-D2 | DoS por volumen | Media | Medio | P2 | Diseñado |
| T-E2 | Scope OAuth excesivo | Baja | Alto | P1 | Diseñado |

## 5. Supuestos y dependencias

- Se confía en la seguridad de los proveedores (Google, Microsoft, Telegram, OpenAI).
- El host/red donde corre el stack está bajo control del usuario.
- La clave de cifrado en reposo se gestiona fuera del repositorio.

## 6. Verificación

Cada control P1 tiene un test asociado (unit o adversarial) que forma parte del
gate de release en Fase 17. Ver `testing.md`.
