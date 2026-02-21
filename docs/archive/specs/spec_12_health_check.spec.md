# Spec 12: Health Check y Monitoreo

## 1. Contexto y Objetivos
**Objetivo:** Detectar proactivamente si la integración con Meta se ha roto.
**Problema:** Token revocado o cuenta bloqueada sin aviso.

## 2. Requerimientos Técnicos

### Backend (Scripting)
- **Archivo:** `scripts/check_meta_health.py`
- **Lógica:**
  - Request a `/me/adaccounts`.
  - Verificar status 200 y `account_status=1` (Active).

## 3. Criterios de Aceptación (Gherkin)

```gherkin
Scenario: Token válido
  Given credenciales correctas
  When ejecuta health check
  Then retorna OK

Scenario: Token inválido
  Given token expirado
  When ejecuta health check
  Then retorna Error Auth
```

## 4. Esquema de Datos
N/A.

## 5. Riesgos y Mitigación
- **Riesgo:** Falsos positivos por downtime de Meta.
- **Mitigación:** Retry antes de alertar.

## 6. Compliance SDD v2.0
- **DevOps:** Script ejecutable manualmente.
