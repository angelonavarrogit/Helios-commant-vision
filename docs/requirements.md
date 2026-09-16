# Requirements — AI Personal Intelligence Center

> Fase 0 (Discovery). Documento vivo. Última revisión: 2026-09-16.

## 1. Visión

Sistema personal de agentes de IA que ingiere correo electrónico vía APIs
oficiales (OAuth), lo clasifica, lo analiza con agentes especializados, decide
prioridad/riesgo/acción mediante un agente supervisor, persiste eventos
importantes y notifica al usuario por Telegram. En su primera versión el sistema
es estrictamente **READ + ANALYZE + NOTIFY** (sin acciones que muten el mundo).

## 2. Requisitos funcionales (RF)

### 2.1 Ingesta de correo
- RF-01: Conectarse a cuentas de correo vía API oficial + OAuth (Gmail primero).
- RF-02: Leer correos nuevos (sin marcar como leído; scope de solo lectura).
- RF-03: Extraer remitente, destinatario, asunto, fecha, cuerpo, etiquetas, adjuntos (metadatos).
- RF-04: Detección de duplicados / correos ya procesados (idempotencia por message-id + hash de contenido).

### 2.2 Normalización
- RF-05: Convertir cada correo a un `NormalizedEmail` canónico (texto plano derivado de HTML, metadatos saneados).
- RF-06: Marcar todo el contenido del correo como **UNTRUSTED DATA**.

### 2.3 Clasificación
- RF-07: Clasificación híbrida: reglas primero, LLM solo cuando sea necesario.
- RF-08: Producir estructura `{category, subcategory, priority, risk_level, requires_action, deadline, confidence}`.
- RF-09: Categorías: finance, insurance, work, security, documents, shopping, subscriptions, travel, education, personal, government, other.
- RF-10: Prioridades: critical, high, medium, low, informational.

### 2.4 Agentes especializados
- RF-11: Interfaz `BaseAgent` común con `analyze(input) -> AgentResult`.
- RF-12: FinanceAgent, InsuranceAgent, WorkAgent, SecurityAgent (DocumentAgent en fase posterior).
- RF-13: FinanceAgent no declara fraude; usa lenguaje calibrado ("requiere revisión", "posible anomalía", "operación no reconocida").
- RF-14: SecurityAgent nunca muestra códigos/OTP completos.

### 2.5 Supervisor
- RF-15: Agente supervisor consolida resultados y produce `{importance, notify_now, summary, reason, recommended_action, confidence}`.
- RF-16: El supervisor NO ejecuta acciones (no paga, no transfiere, no cambia contraseñas, no responde correos, no contrata servicios).

### 2.6 Persistencia y memoria
- RF-17: Persistir emails, resultados de agentes, decisiones del supervisor, alertas y auditoría.
- RF-18: Mantener memoria estructurada de eventos importantes (finance/insurance/work events).
- RF-19: Búsqueda semántica (fase 15, no ahora).

### 2.7 Telegram
- RF-20: Bot con `/start`, `/help` (fase 3); `/resumen`, `/urgentes`, `/finanzas`, `/seguros`, `/trabajo`, `/pendientes`, `/hoy`, `/semana` (fase 12).
- RF-21: Autorización por lista blanca de user IDs.
- RF-22: Consultas en lenguaje natural (fase posterior).

### 2.8 Notificaciones
- RF-23: Reglas por prioridad (critical → inmediato; medium → resumen; low/informational → guardar).
- RF-24: Deduplicación y agrupación de eventos relacionados (no spam).

### 2.9 Informes
- RF-25: Informe diario consolidado (fase 13).

### 2.10 Orquestación
- RF-26: N8N como capa de orquestación/automatización; lógica de negocio en Python.
- RF-27: Endpoint `POST /emails/process` para disparar el pipeline.

### 2.11 Documentos (futuro)
- RF-28: Procesar PDF, Excel, Word, imágenes, facturas, contratos, estados de cuenta (fase 14).

### 2.12 Dashboard (futuro)
- RF-29: Dashboard web (fase 16).

## 3. Requisitos no funcionales (RNF)

- RNF-01 Seguridad: no almacenar contraseñas/CVV/PIN/PAN completo/tokens/secretos; cifrado/hashing/masking donde aplique.
- RNF-02 Privacidad: minimización de datos; enviar al LLM solo lo estrictamente necesario.
- RNF-03 Resistencia a prompt injection: separación estricta system / config / email data / agent output.
- RNF-04 Observabilidad: logs estructurados con request_id, email_id, agent_id, timestamp, processing_status; nunca secretos.
- RNF-05 Auditabilidad: rastrear por qué se envió cada alerta.
- RNF-06 Costo: minimizar llamadas al LLM (reglas primero, caché/hashing de contenido procesado).
- RNF-07 Modularidad/Extensibilidad: agregar nuevos agentes sin refactor mayor.
- RNF-08 Portabilidad: Docker + Docker Compose; config vía `.env`.
- RNF-09 Menor privilegio: cada componente con permisos mínimos (email READ-ONLY, telegram SEND).
- RNF-10 Calidad: Ruff, Black, mypy (donde aporte), pytest con unit + integración.
- RNF-11 Mantenibilidad: código limpio, tipado, contratos Pydantic explícitos.
- RNF-12 Fiabilidad: idempotencia, reintentos controlados, manejo de errores explícito.
- RNF-13 Escalabilidad: pipeline desacoplado que permita crecer a colas/workers.

## 4. Fuera de alcance (v1)

- Acciones que muten el mundo (pagos, transferencias, respuestas automáticas, cambios de credenciales).
- Document intelligence, memoria semántica, dashboard, interfaces voz/WhatsApp/Discord/móvil.
- Multi-tenant real (se diseña `users` para permitirlo, pero el foco es un solo usuario).

## 5. Actores

- **Usuario propietario**: único humano autorizado; recibe alertas y consulta por Telegram.
- **Proveedores de correo**: Gmail (v1), Outlook (posterior).
- **Proveedores LLM**: OpenAI / Ollama vía abstracción.
- **N8N**: orquestador de eventos.

## 6. Criterios de aceptación globales

- CA-01: Ningún secreto en el repositorio (verificado por revisión + `.gitignore`).
- CA-02: Contenido de email jamás altera instrucciones del sistema (test adversarial).
- CA-03: Cada fase entrega tests que pasan y un reporte de validación.
- CA-04: Endpoints y agentes con contratos Pydantic tipados.
