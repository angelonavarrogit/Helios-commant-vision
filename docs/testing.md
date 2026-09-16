# Testing Strategy — AI Personal Intelligence Center

> Fase 0 (Discovery). Documento vivo. Última revisión: 2026-09-16.

## 1. Objetivos

- Cada módulo tiene tests (unit) y los flujos clave tienen integración.
- Tests deterministas: el LLM se **mockea** en unit tests; contratos de salida
  validados por Pydantic.
- Tests adversariales de seguridad son obligatorios y bloquean la fase si fallan.

## 2. Pirámide de pruebas

- **Unit**: parser, normalizer, rule classifier, cada agente, supervisor,
  reglas de notificación, sanitización, masking.
- **Integración**: pipeline `process` end-to-end con proveedor de email fake,
  LLM fake y DB de test; comandos de Telegram con bot mockeado.
- **Contrato**: esquemas Pydantic de `Classification`, `AgentResult`,
  `SupervisorDecision`.

## 3. Suites por módulo (referencia)

```text
test_email_parser
test_email_normalizer
test_email_classifier
test_finance_agent
test_insurance_agent
test_work_agent
test_security_agent
test_supervisor
test_notifications        # reglas de prioridad + dedupe/agrupación
test_telegram             # autorización + comandos
test_security_sanitization
```

## 4. Casos adversariales / de borde (obligatorios)

| Caso | Expectativa |
|------|-------------|
| email normal | clasificación y flujo correctos |
| email vacío | manejo con gracia, sin excepción no controlada |
| email solo HTML | normaliza a texto plano usable |
| email malicioso (prompt injection) | NO altera instrucciones ni decisión; no expone prompt/datos |
| "Ignore previous instructions..." | tratado como dato; decisión no cambia hacia lo pedido |
| archivo/adjunto corrupto | error controlado, email procesa el resto |
| correo duplicado (mismo message-id/hash) | idempotente: no re-notifica |
| correo gigante | truncado defensivo; sin agotar recursos/costo |
| remitente desconocido | clasifica sin fallar; prioridad prudente |
| OTP/código en cuerpo (SecurityAgent) | nunca se muestra completo en Telegram |
| finanzas ambiguas | lenguaje calibrado ("requiere revisión"), no "fraude" |

## 5. Datos de prueba

- Fixtures de correos sintéticos por categoría (finance, insurance, work,
  security, ...), sin datos personales reales.
- PII solo con placeholders; números de cuenta/tarjeta ficticios y enmascarados.

## 6. Calidad y CI (se cablea en fases correspondientes)

- Ruff + Black + mypy (donde aporte) en pre-commit / CI.
- pytest con cobertura; umbral mínimo a definir en Fase 17 (Hardening).
- Los tests adversariales de prompt injection forman parte del gate de release.

## 7. Regla de validación por fase

Al cerrar cada fase se reporta:

```text
FASE X COMPLETADA
Implementado: ✓ ...
Tests: ✓ N passed / ✗ M failed
Estado: READY / NOT READY
Problemas: ...
Siguiente fase: ...
```

No se avanza con errores críticos.
