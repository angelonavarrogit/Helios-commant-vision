# Agents & Classification — AI Personal Intelligence Center

> Fase 0 (Discovery). Documento vivo. Última revisión: 2026-09-16.

## 1. Modelo de clasificación

Cada email se convierte en una `Classification`:

```json
{
  "category": "finance",
  "subcategory": "transaction",
  "priority": "high",
  "risk_level": "medium",
  "requires_action": true,
  "deadline": null,
  "confidence": 0.96
}
```

- **category**: finance, insurance, work, security, documents, shopping,
  subscriptions, travel, education, personal, government, other.
- **priority**: critical, high, medium, low, informational.
- **risk_level**: low, medium, high.
- **method**: `rules` | `llm` (para auditoría/costo).

### 1.1 Clasificación híbrida

```text
RuleClassifier (dominios conocidos, patrones, remitentes)
   │  confianza >= umbral → resultado directo
   ▼  confianza <  umbral / categoría ambigua
LLMClassifier (salida estructurada validada)
```

Objetivo: minimizar llamadas al LLM (RNF-06). Contenido idéntico
(`content_hash`) reutiliza clasificación previa.

## 2. Contrato de agente

```python
class AgentResult(BaseModel):
    agent_name: str
    findings: list[Finding]        # hallazgos tipados por dominio
    requires_action: bool
    confidence: float

class BaseAgent(Protocol):
    name: str
    async def analyze(self, email: NormalizedEmail, ctx: AnalysisContext) -> AgentResult: ...
```

Reglas comunes:
- Reciben `NormalizedEmail` (UNTRUSTED) + contexto; devuelven salida tipada.
- No escriben en DB ni envían notificaciones (eso es del pipeline/supervisor).
- Deben degradar con gracia ante entradas vacías/corruptas.

## 3. Agentes v1

### FinanceAgent
Detecta: compras, transferencias, depósitos, retiros, pagos, estados de cuenta,
tarjetas, préstamos, intereses, comisiones, cargos desconocidos, cambios
importantes.

Restricciones:
- **No declara fraude.** Usa: "requiere revisión", "posible anomalía",
  "operación no reconocida".
- Solo extrae datos mínimos; cuentas/tarjetas siempre enmascaradas.

### InsuranceAgent
Detecta: pólizas, renovaciones, pagos, vencimientos, reclamos, cambios de
cobertura, documentos pendientes. Extrae `due_date` cuando existe.

### WorkAgent
Detecta: solicitudes, reuniones, tareas, deadlines, correos que requieren
respuesta, comunicaciones importantes. Marca `requires_reply` y `deadline`.

### SecurityAgent
Detecta: nuevos inicios de sesión, intentos de acceso, cambios de contraseña,
alertas de seguridad, códigos de autenticación, actividad sospechosa.

Restricción crítica: **nunca** muestra códigos/OTP completos (masking).

### DocumentAgent (fase 14)
PDF, Excel, Word, imágenes, facturas, contratos, estados de cuenta. No se
implementa en v1; la interfaz queda preparada.

## 4. Supervisor

Recibe todos los `AgentResult` + `Classification` y produce:

```json
{
  "importance": "high",
  "notify_now": true,
  "summary": "...",
  "reason": "...",
  "recommended_action": "...",
  "confidence": 0.94
}
```

Restricciones (v1 = READ + ANALYZE + NOTIFY):
- No transfiere dinero, no paga, no cambia contraseñas, no responde correos
  sensibles, no contrata servicios.
- Solo **recomienda** acciones al usuario; nunca las ejecuta.
- `summary` y `reason` alimentan la auditoría ("¿por qué recibí esta alerta?").

## 5. Orquestación

1. Orchestrator selecciona agentes según `category` (puede activar varios).
2. Ejecuta en paralelo (`asyncio.gather`).
3. Consolida en Supervisor.
4. Persiste `agent_runs`, `agent_results`, `supervisor_decisions`.
5. Entrega a `NotificationService`.

## 6. Reglas de notificación

```text
CRITICAL       → Telegram inmediato
HIGH           → inmediato o resumen según contexto (notify_now del supervisor)
MEDIUM         → resumen
LOW            → guardar
INFORMATIONAL  → guardar
```

Deduplicación/agrupación:
- `dedupe_key` por evento lógico; correos del mismo evento se agrupan en un
  `group_id` y generan una sola alerta agrupada.
- Umbral temporal para consolidar ráfagas de correos relacionados.

## 7. Informe diario (fase 13)

Resumen consolidado con conteos por prioridad y por dominio (finanzas, seguros,
trabajo, agenda) y una sección "requiere atención" priorizada. Formato de
referencia en el prompt del proyecto (sección 12).

## 8. Extensibilidad

Nuevos agentes (Calendar, Shopping, Travel, Subscription, Government, Education,
Personal Task, Finance Analytics) se añaden implementando `BaseAgent` y
registrándose en el Orchestrator, sin cambiar el contrato del supervisor.
