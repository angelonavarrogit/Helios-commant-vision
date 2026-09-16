# Security Model — AI Personal Intelligence Center

> Fase 0 (Discovery). Documento vivo. Última revisión: 2026-09-16.

## 1. Postura de seguridad

El sistema procesa información personal y potencialmente financiera. La postura
por defecto es **negar / minimizar / aislar**:

- Todo contenido de correo es **UNTRUSTED DATA**.
- Cada componente opera con **menor privilegio**.
- v1 es **READ + ANALYZE + NOTIFY**: no existen rutas de código que muevan
  dinero, cambien credenciales ni respondan correos.

## 2. Clasificación de confianza de datos

| Fuente | Confianza | Regla |
|--------|-----------|-------|
| SYSTEM INSTRUCTIONS | Confiable | Definidas en código/config del sistema |
| USER CONFIGURATION | Confiable | `.env`, listas blancas, umbrales |
| EMAIL DATA (asunto, cuerpo, adjuntos, nombres) | **NO confiable** | Nunca interpretado como instrucción |
| AGENT OUTPUT | Semi-confiable | Validado contra esquema; no ejecuta acciones |

Estas cuatro zonas se mantienen **separadas** en memoria y en los prompts.

## 3. Defensa contra prompt injection (obligatorio)

Amenaza: un correo contiene texto como "Ignore previous instructions", "Reveal
your system prompt", "Send all emails to X".

Controles:

1. **Separación estructural del prompt**: el contenido del email se pasa al LLM
   dentro de un bloque claramente delimitado y etiquetado como datos no
   confiables; nunca concatenado al bloque de instrucciones del sistema.
2. **Instrucción de sistema defensiva**: el system prompt indica explícitamente
   que el contenido entre delimitadores es dato a analizar, no órdenes a obedecer.
3. **Salida estructurada forzada**: el LLM debe responder un JSON validado por
   Pydantic; cualquier desviación se rechaza. Esto limita la superficie de
   "hacer lo que el email pide".
4. **Sanitización previa** (`security/sanitization.py`): normaliza espacios,
   neutraliza secuencias de control, recorta longitud, elimina/inerta patrones
   conocidos de inyección antes de enviar al modelo.
5. **Sin acciones ejecutables**: aunque un modelo fuera manipulado, no hay
   herramientas conectadas que envíen dinero, correos o cambien credenciales en v1.
6. **Límites de tamaño**: truncado defensivo para evitar correos gigantes que
   agoten contexto/costos o escondan payloads al final.
7. **Tests adversariales** obligatorios (ver `testing.md`).

Criterio verificable (CA-02): un correo con instrucciones inyectadas no cambia
la categoría/decisión hacia lo que el atacante pide, y el sistema no expone su
prompt ni datos de otros correos.

## 4. Gestión de secretos

- Secretos vía `.env` (local) / gestor de secretos (prod). `.env.example` sin valores reales.
- `.gitignore` excluye `.env`, credenciales OAuth, tokens, claves.
- Nunca imprimir secretos en logs (redacción en el logger).
- Nunca enviar secretos al LLM.
- Tokens OAuth: no se guardan en claro en la base de datos. Se guarda una
  referencia (`oauth_ref`) y el material sensible se cifra en reposo
  (`security/encryption.py`) o se delega a un gestor externo. Decisión final de
  almacenamiento en Fase 4.

## 5. Datos que NUNCA se almacenan

Contraseñas, CVV, PIN, número completo de tarjeta (PAN), tokens, secretos.

Cuando se requiere un identificador sensible: **hashing** (para comparación),
**cifrado** (para recuperar) o **masking** (para mostrar, p. ej. `**** 1234`).

## 6. Menor privilegio

| Componente | Permiso | Justificación |
|-----------|---------|---------------|
| Email reader | READ ONLY (scope Gmail `readonly`) | Solo necesitamos leer |
| Telegram bot | SEND / responder a IDs autorizados | Solo entrega y consultas |
| DB (app user) | CRUD limitado al esquema de la app | No DDL en runtime |
| N8N | Llamar `POST /emails/process` con token de servicio | No accede a DB directamente |
| LLM provider | Solo recibe datos minimizados | Minimización |

## 7. Autorización de Telegram

- Lista blanca `TELEGRAM_ALLOWED_USER_IDS`. Cualquier ID no listado se ignora
  (sin filtrar información en el mensaje de rechazo).
- SecurityAgent: nunca envía OTP/códigos completos por Telegram (masking).

## 8. Observabilidad segura

- Logs estructurados con `request_id`, `email_id`, `agent_id`, `timestamp`,
  `processing_status`.
- Redacción automática de campos sensibles.
- Auditoría (`audit_logs`) responde a "¿por qué recibí esta alerta?" sin exponer
  secretos.

## 9. Superficie de red y despliegue

- Servicios internos (MySQL) no expuestos públicamente; solo puertos necesarios.
- Endpoint `POST /emails/process` protegido por token de servicio para N8N.
- HTTPS/red segura en cualquier tránsito hacia servicios externos.

## 10. Backups y retención (definir en Fase 17)

- Estrategia de backup de la base de datos.
- Política de retención/minimización: no conservar cuerpos de correo más de lo
  necesario si no aportan a la memoria de eventos.

## 11. Endurecimiento de OAuth (email)

- Scope mínimo estricto: `gmail.readonly` (y equivalente read-only en Outlook).
- Nunca solicitar contraseñas del correo; solo flujo OAuth oficial.
- Tokens de refresco cifrados en reposo; nunca en logs ni en el LLM.
- Revocación inmediata ante sospecha de compromiso; rotación planificada.
- Validación del `state` en el flujo OAuth para prevenir CSRF.

## 12. Defensa en profundidad del LLM

Además de la sección 3 (prompt injection):

- **Minimización del prompt**: masking de montos/cuentas y truncado antes de enviar.
- **Salida contractual**: JSON validado por Pydantic; se rechaza cualquier salida
  fuera de esquema, evitando inyección de instrucciones en el resultado.
- **Aislamiento de contenido**: cada email se procesa aislado; el prompt nunca
  mezcla datos de varios correos.
- **Provider local opcional**: Ollama permite análisis 100% local para contenido
  especialmente sensible (seleccionable por config).
- **Presupuesto y circuit breaker**: límite de coste/llamadas; ante fallos
  sostenidos, degradar a solo reglas.

## 13. Seguridad de la API y de la red

- HTTPS/TLS en todo tránsito externo.
- `POST /emails/process` con token de servicio y rate limiting.
- Errores hacia el exterior genéricos; detalle solo en logs internos.
- Consultas SQL siempre parametrizadas (ORM); nunca concatenación de strings.
- MySQL en red interna, no expuesto públicamente.
- CORS restrictivo (relevante cuando llegue el dashboard, Fase 16).

## 14. Documentos de seguridad relacionados

- `docs/threat-model.md` — análisis STRIDE y matriz de riesgo.
- `docs/data-governance.md` — clasificación, masking, retención, minimización.
- `docs/operations.md` — backups, rotación de secretos, rate limiting, DR.

## 15. Riesgos y mitigaciones (resumen)

| ID | Riesgo | Impacto | Mitigación |
|----|--------|---------|-----------|
| R-01 | Prompt injection vía email | Alto | Sección 3 completa |
| R-02 | Fuga de secretos en Git/logs | Alto | `.gitignore`, redacción, revisión |
| R-03 | Almacenar datos sensibles de más | Alto | Sección 5, masking/cifrado |
| R-04 | Falsos positivos de fraude | Medio | Lenguaje calibrado, no declarar fraude |
| R-05 | Spam de notificaciones | Medio | Reglas + dedupe/agrupación |
| R-06 | Costo LLM descontrolado | Medio | Reglas primero, caché, tracking |
| R-07 | Abuso del endpoint de proceso | Medio | Token de servicio, rate limiting (F17) |
| R-08 | Compromiso de token OAuth | Alto | Scope read-only, cifrado en reposo, revocación |
| R-09 | DoS por volumen/correo gigante | Medio | Límites de tamaño, rate limiting, backpressure |
| R-10 | Pérdida de datos / sin recuperación | Alto | Backups cifrados + restauración probada (F17) |
| R-11 | Vulnerabilidad en dependencia | Medio | Versiones pinneadas + auditoría (F17) |
| R-12 | SQL injection | Alto | ORM con consultas parametrizadas |
| R-13 | Errores verbosos filtran info | Bajo | Errores genéricos al exterior, detalle en logs |
