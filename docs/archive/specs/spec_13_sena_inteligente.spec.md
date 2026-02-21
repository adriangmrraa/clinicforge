# Spec 13: Sistema de Seña Inteligente (Lead Closing)

## 1. Contexto y Objetivos
**Objetivo:** Automatizar la validación del compromiso económico del lead proveniente de Meta Ads.
**Problema:** Leads de Meta suelen tener alto ausentismo si no se concreta una seña monetaria rápida. La verificación manual es lenta.

## 2. Requerimientos Técnicos

### Backend (Orchestrator Logic)
- **Módulo:** `orchestrator_service/features/payments.py` (o similar).
- **Lógica:**
  - Detectar intención de pago o comprobante enviado.
  - Validar monto contra el valor requerido del tratamiento (`treatment_deposit_value`).
  - Comparar monto recibido vs esperado.
  - Si `monto_recibido < monto_esperado`:
    - Generar respuesta automática: "Detectamos una diferencia de $X. Por favor abona el resto."
    - Alertar a humano (Flag `payment_discrepancy`).
  - Si `monto_recibido >= monto_esperado`:
    - Confirmar turno automáticamente.
    - Cambiar estado de lead a `PATIENT_CONFIRMED`.

## 3. Criterios de Aceptación (Gherkin)

```gherkin
Scenario: Pago parcial detectado
  Given un tratamiento con seña de $5000
  When el paciente envía comprobante válido por $3000
  Then el sistema responde alertando sobre la diferencia de $2000
  And no confirma el turno automáticamente

Scenario: Pago total correcto
  Given seña de $5000
  When paciente envía $5000
  Then el sistema confirma el turno
  And envía mensaje de éxito
```

## 4. Esquema de Datos
- Tabla `payments` o `transactions` (existente o nueva).
- Columna `payment_status` en `appointments`.

## 5. Riesgos y Mitigación
- **Riesgo:** Falsos positivos en lectura de comprobantes (OCR).
- **Mitigación:** Si la confianza del OCR es baja, derivar a humano siempre.

## 6. Compliance SDD v2.0
- **Sovereign:** Datos de pagos aislados por tenant.
