# Design: Phone Prefix por País

## Technical Approach

Crear función unificada `normalize_phone_for_tenant()` que use `country_code` del tenant para determinar el prefijo (+549, +1, etc.). La función se aplica en todos los puntos de entrada de teléfonos. Componente frontend `PhoneInput` con prefijo fijo visual.

## Architecture Decisions

### Decision: Ubicación de COUNTRY_PHONE_MAP

**Choice**: En `orchestrator_service/main.py` como módulo importable.
**Rationale**: Accesible desde admin_routes.py, db.py, nova_tools.py sin imports circulares.

### Decision: Frontend PhoneInput

**Choice**: Componente nuevo en `frontend_react/src/components/PhoneInput.tsx`.
**Rationale**: Reutilizable en PatientsView y futuros formularios. Muestra prefijo como badge no editable.

### Decision: Backfill en start.sh

**Choice**: Script separado `scripts/normalize_existing_phones.py` + llamado desde `start.sh`.
**Rationale**: Sigue el patrón existente de start.sh con inline Python.

## Data Flow

```
Frontend PhoneInput → "3704868421" + prefijo "+549"
  → POST /admin/patients { phone: "+5493704868421" }
  → normalize_phone_for_tenant("+5493704868421", "AR")
  → "+5493704868421" (normalized + idempotent check)
  → INSERT INTO patients (phone_number = "+5493704868421")
  → MATCH con chat_conversations.external_user_id = "+5493704868421" ✅
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` | Modify | Agregar `COUNTRY_PHONE_MAP` y `normalize_phone_for_tenant()` |
| `orchestrator_service/admin_routes.py` | Modify | `create_patient` y `update_patient` usan nueva función |
| `orchestrator_service/db.py` | Modify | `ensure_patient_exists` normaliza con prefijo |
| `orchestrator_service/services/nova_tools.py` | Modify | `_registrar_paciente` normaliza teléfono |
| `orchestrator_service/auth_routes.py` | Modify | Register normaliza teléfono |
| `frontend_react/src/components/PhoneInput.tsx` | Create | Componente con prefijo fijo |
| `frontend_react/src/views/PatientsView.tsx` | Modify | Usar PhoneInput |
| `scripts/normalize_existing_phones.py` | Create | Backfill script |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `normalize_phone_for_tenant` | Test múltiples formatos (AR, US, ES) |
| Integration | `create_patient` con número local | Verificar guardado como +549... |
| Integration | `update_patient` | Verificar normalización (bug fix) |
| E2E | Backfill script | Ejecutar sobre data de test |

## Migration / Rollout

**Sin migración nueva.** Backfill post-deploy en start.sh.
