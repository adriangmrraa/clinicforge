# Specs: Phone Prefix por País

## 1. Overview

Sistema para normalizar números de teléfono usando el `country_code` de la clínica. Todos los números se almacenan con el prefijo internacional correcto (ej: `+549` para Argentina). Esto elimina el mismatch entre pacientes cargados manualmente (sin código de país) y los números que llegan de YCloud/WhatsApp (con `+549`).

## 2. Functional Requirements

### FR-01: Mapa de prefijos por país

El sistema DEBE tener un mapa de códigos de país a prefijos telefónicos:

```python
COUNTRY_PHONE_MAP = {
    "AR": {"prefix": "+549", "code": "54", "has_mobile_9": True},
    "US": {"prefix": "+1", "code": "1", "has_mobile_9": False},
    "ES": {"prefix": "+34", "code": "34", "has_mobile_9": False},
    "MX": {"prefix": "+52", "code": "52", "has_mobile_9": False},
    "CO": {"prefix": "+57", "code": "57", "has_mobile_9": False},
    "CL": {"prefix": "+56", "code": "56", "has_mobile_9": False},
}
```

Criterio: Para países con `has_mobile_9 = True`, se DEBE insertar un `9` después del código de país cuando el número original no lo tiene (Argentina).

### FR-02: Función `normalize_phone_for_tenant`

Se DEBE crear la función:

```python
def normalize_phone_for_tenant(phone: str, country_code: str = "AR") -> str:
```

Comportamiento:
- Si `phone` está vacío → retorna `""`
- Si `phone` ya empieza con el prefijo correcto (ej: `+549...`) → retorna sin cambios
- Si `phone` empieza con `+` + código de país pero sin `9` (ej: `+542996114843`) → inserta 9 (`+5492996114843`)
- Si `phone` empieza con código de país sin `+` (ej: `542996114843`) → agrega `+` y 9 si corresponde (`+5492996114843`)
- Si `phone` NO tiene código de país (ej: `3704868421`) → antepone el prefijo completo (`+5493704868421`)
- Si `phone` es solo dígitos y corto (< 8 dígitos) → se deja como está (número interno)

### FR-03: Frontend PhoneInput component

Se DEBE crear `frontend_react/src/components/PhoneInput.tsx`:

- Props: `value`, `onChange`, `prefix` (ej: `"+549"`), `placeholder`, `disabled`
- Muestra el prefijo en un badge fijo a la izquierda del input
- El usuario solo escribe los dígitos restantes
- El `onChange` devuelve la concatenación `prefix + digits`
- El prefijo NO es editable

### FR-04: Actualizar inputs de teléfono en frontend

`PatientsView.tsx`:
- Reemplazar `<input type="tel">` por `<PhoneInput prefix="+549">`
- Obtener el `country_code` del tenant desde el contexto de la clínica

### FR-05: Normalizar en create_patient

`POST /admin/patients`:
- Usar `normalize_phone_for_tenant(raw_phone, country_code)` en lugar de `normalize_phone(raw_phone)`
- Obtener `country_code` del tenant autenticado

### FR-06: Normalizar en update_patient

`PUT /admin/patients/{id}`:
- **BUG FIX**: Normalizar `phone_number` con `normalize_phone_for_tenant`
- Actual: guarda el número sin normalizar

### FR-07: Normalizar en Nova

`_registrar_paciente()` en `nova_tools.py`:
- Normalizar `phone` con `normalize_phone_for_tenant` antes de guardar
- Obtener `country_code` del tenant correspondiente

### FR-08: Normalizar en ensure_patient_exists

`db.py`:
- Normalizar `phone_number` con `normalize_phone_for_tenant` antes de INSERT/UPDATE
- Obtener `country_code` del tenant

### FR-09: Normalizar en auth register

`POST /auth/register`:
- Normalizar `phone_number` con `normalize_phone_for_tenant`

### FR-10: Backfill de pacientes existentes

Script `scripts/normalize_existing_phones.py`:
- Para cada tenant, obtener su `country_code`
- Para cada paciente del tenant:
  - Normalizar `phone_number` con `normalize_phone_for_tenant`
  - Si cambió: UPDATE en patients
  - Re-linkear `chat_conversations` si el número cambió
- Loggear resultados

## 3. Scenarios

### Scenario 1: Crear paciente desde UI con número local

**Given**: Clínica en Argentina (country_code = "AR")
**When**: Admin crea paciente con teléfono `"3704868421"`
**Then**: `normalize_phone_for_tenant("3704868421", "AR")` → `"+5493704868421"`
**Then**: Se guarda en DB como `"+5493704868421"`
**Then**: La conversación YCloud con `external_user_id = "+5493704868421"` matchea automáticamente

### Scenario 2: Update paciente con +54 (sin 9)

**Given**: Paciente tiene `"+542996114843"` (sin 9)
**When**: Admin edita y guarda (incluso sin cambiar el número)
**Then**: `normalize_phone_for_tenant("+542996114843", "AR")` → `"+5492996114843"`
**Then**: Se actualiza en DB con el 9
**Then**: Matchea con la conversación YCloud

### Scenario 3: Nova registra paciente

**Given**: Agente Nova recibe `"registrá a Juan con teléfono 1144445555"`
**When**: `_registrar_paciente()` ejecuta
**Then**: `normalize_phone_for_tenant("1144445555", "AR")` → `"+5491144445555"`
**Then**: Se guarda correctamente

### Scenario 4: Frontend PhoneInput

**Given**: Usuario en página de Pacientes, clínica Argentina
**When**: Input de teléfono muestra `[+549][          ]`
**When**: Usuario escribe `"3704868421"`
**Then**: `onChange` envía `"+5493704868421"`

### Scenario 5: Backfill

**Given**: Paciente existente con `phone_number = "+543704868421"` (sin 9)
**When**: Script `normalize_existing_phones.py` corre
**Then**: Actualiza a `"+5493704868421"`
**Then**: Re-linkea `chat_conversations` si el external_user_id ahora matchea

### Scenario 6: Teléfono ya normalizado

**Given**: Paciente con `phone_number = "+5493704868421"`
**When**: `normalize_phone_for_tenant("+5493704868421", "AR")`
**Then**: Retorna `"+5493704868421"` sin cambios (idempotente)

## 4. Files to Modify

| File | Action | Change |
|------|--------|--------|
| `orchestrator_service/main.py` | Modify | Agregar `COUNTRY_PHONE_MAP` y `normalize_phone_for_tenant` |
| `orchestrator_service/admin_routes.py` | Modify | `create_patient` y `update_patient` usan nueva normalización |
| `orchestrator_service/db.py` | Modify | `ensure_patient_exists` normaliza con prefijo |
| `orchestrator_service/services/nova_tools.py` | Modify | `_registrar_paciente` normaliza teléfono |
| `orchestrator_service/auth_routes.py` | Modify | Register normaliza teléfono |
| `frontend_react/src/components/PhoneInput.tsx` | Create | Nuevo componente con prefijo fijo |
| `frontend_react/src/views/PatientsView.tsx` | Modify | Usar PhoneInput |
| `scripts/normalize_existing_phones.py` | Create | Backfill script |
