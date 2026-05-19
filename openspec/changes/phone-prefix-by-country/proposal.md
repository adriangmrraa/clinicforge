# Proposal: Phone Prefix por País

## Intent

Centralizar la normalización de teléfonos usando el `country_code` de la clínica, para que todos los números se guarden con el prefijo internacional correcto (+549 para Argentina). Esto elimina el mismatch de formatos entre pacientes cargados manualmente y conversaciones de YCloud.

## Scope

### In Scope

1. **Función unificada de normalización** que use `country_code` para determinar el prefijo
2. **PhoneInput component** en frontend con prefijo fijo visual (+549)
3. **Actualizar `update_patient`** para normalizar teléfono (bug fix)
4. **Actualizar Nova** (`_registrar_paciente`) para normalizar teléfono
5. **Actualizar `ensure_patient_exists`** para normalizar con prefijo
6. **Backfill** de pacientes existentes a formato +549

### Out of Scope

- Cambiar `generate_phone_variants()` (ya funciona con múltiples formatos)
- Modificar la query de YCloud sessions (ya usa regexp_replace)
- Agregar selector de país en el registro de clínica (ya existe)
- Internacionalización completa (solo AR para empezar)

## Approach

### Part A: Backend — Función `normalize_phone_for_tenant`

```python
COUNTRY_PREFIXES = {
    "AR": {
        "prefix": "+549",
        "code": "54",
        "has_mobile_9": True,
    },
    "US": {"prefix": "+1", "code": "1", "has_mobile_9": False},
    "ES": {"prefix": "+34", "code": "34", "has_mobile_9": False},
    # ...
}
```

La función:
1. Recibe `phone` y `country_code`
2. Saca todos los no-dígitos
3. Si ya empieza con el prefijo correcto → devuelve como está
4. Si empieza con `+` y el código de país (ej: +54) pero sin 9 → agrega el 9 (si has_mobile_9)
5. Si empieza con el código de país (ej: 54) sin + → agrega + y 9 si corresponde
6. Si NO tiene código de país → antepone el prefijo completo

### Part B: Frontend — PhoneInput componente

Crear `frontend_react/src/components/PhoneInput.tsx`:
- Muestra el prefijo fijo (ej: `+549`) en un badge a la izquierda del input
- El usuario escribe solo los dígitos restantes
- El valor enviado al form es la concatenación: `prefijo + dígitos`

### Part C: Reemplazar inputs de teléfono

| Componente | Input actual | Reemplazar con |
|------------|-------------|----------------|
| `PatientsView.tsx` | `<input type="tel">` | `<PhoneInput>` |
| `CreatePatientModal.tsx` | readonly input | ya viene del chat |

### Part D: Backend — Normalizar en todos los puntos de entrada

| Endpoint | Cambio |
|----------|--------|
| `POST /admin/patients` (create_patient) | Usar `normalize_phone_for_tenant` |
| `PUT /admin/patients/{id}` (update_patient) | **NUEVO**: normalizar teléfono |
| Nova `_registrar_paciente` | Normalizar con prefijo |
| `ensure_patient_exists` | Normalizar con prefijo |
| `POST /auth/register` | Normalizar teléfono |

### Part E: Backfill de pacientes existentes

En `start.sh` o script aparte:
1. Obtener todos los pacientes por tenant
2. Normalizar cada `phone_number` con el `country_code` del tenant
3. UPDATE en patients
4. Re-linkear `chat_conversations` si es necesario

## Impact Analysis

### Frontend
- **Nuevo componente**: `PhoneInput` (reusable)
- **Modificar**: `PatientsView.tsx` — usar PhoneInput
- **Sin cambios**: `CreatePatientModal.tsx` (readonly)

### Backend
- **Modificar**: `admin_routes.py`, `db.py`, `nova_tools.py`, `auth_routes.py`
- **Nuevo helper**: `normalize_phone_for_tenant`
- **Bug fix**: `update_patient` ahora normaliza

### Database
- Sin migraciones nuevas (usa `country_code` existente)

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Cambiar formato de teléfono existente rompe matching en queries | Ya usamos `replace(regexp_replace(...))` en YCloud sessions |
| Pacientes duplicados por normalización | ON CONFLICT DO UPDATE en create_patient |
| Números de otros países se rompen | Backfill y normalización solo modifican si el formato es inconsistente |

## Verification

1. Crear paciente con `3704868421` → se guarda `+5493704868421`
2. Update paciente con `+542996114843` → se normaliza a `+5492996114843`
3. Nova registra `1144445555` → se normaliza a `+5491144445555`
4. Backfill: pacientes con `+543704868421` → se actualizan a `+5493704868421`
5. Input en frontend muestra `+549` como prefijo fijo
