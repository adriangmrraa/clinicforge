# Design: Auto-link de Pacientes con Conversaciones de Chat

## Technical Approach

Implementar linking bidireccional entre `patients` y `chat_conversations` en ambos sentidos: (1) al crear paciente desde UI, buscar y linkear conversaciones existentes; (2) al crear/actualizar conversación (webhook YCloud), buscar paciente existente. Acompañado de normalización telefónica E.164 consistente y backfill one-time.

## Architecture Decisions

### Decision: Phone normalization

**Choice**: Normalizar a `+549XXXXXXXXX` (E.164 con +) en `create_patient` y buscar conversaciones en ambos formatos (con y sin +).
**Alternatives**: Usar solo RAW de YCloud, normalizar en todos lados.
**Rationale**: Los usuarios pueden ingresar el teléfono en cualquier formato desde la UI. Buscar en ambos formatos maximiza matches sin refactor masivo.

### Decision: Sin nueva migración DB

**Choice**: Usar `linked_patient_id` existente en `chat_conversations`.
**Rationale**: La columna ya existe desde migración 054. No requiere schema change.

### Decision: Socket event en create_patient

**Choice**: Emitir `PATIENT_CREATED` desde el endpoint REST.
**Rationale**: El frontend ya tiene el handler (ChatsView.tsx:394). Solo falta que el backend lo emita cuando se crea desde Pacientes.

### Decision: Backfill como script standalone

**Choice**: Script Python independiente (`scripts/link_existing_patients.py`).
**Rationale**: One-time operation. No necesita integrarse al ciclo de vida de la app.

## Data Flow

### Flow 1: Crear paciente desde UI → linkear conversaciones

```
POST /admin/patients { phone: "115551234", ... }
  │
  ├─ normalize_phone("115551234") → "+549115551234"
  ├─ INSERT INTO patients (...)
  ├─ SELECT FROM chat_conversations WHERE tenant_id=$1 AND channel='whatsapp'
  │    AND (external_user_id = '+549115551234' OR external_user_id = '549115551234')
  ├─ UPDATE chat_conversations SET linked_patient_id=$1, linked_at=NOW() WHERE id IN (...)
  ├─ Emitir socket 'PATIENT_CREATED' → Frontend actualiza sesión
  └─ Return paciente
```

### Flow 2: Llega mensaje YCloud → linkear paciente existente

```
YCloud webhook → get_or_create_conversation(tenant_id, 'whatsapp', '5491144445555')
  │
  ├─ INSERT/UPDATE chat_conversations (existing logic)
  ├─ SELECT id FROM patients WHERE tenant_id=$1
  │    AND (phone_number = '5491144445555' OR phone_number = '+5491144445555')
  ├─ IF found AND linked_patient_id IS NULL:
  │    UPDATE chat_conversations SET linked_patient_id=$1, linked_at=NOW()
  └─ Return conv_id
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/admin_routes.py` | Modify | `create_patient`: normalizar phone, linkear conversations, emitir socket |
| `orchestrator_service/db.py` | Modify | `get_or_create_conversation`: buscar paciente y setear linked_patient_id |
| `orchestrator_service/main.py` | Modify | Agregar helper `emit_socket_event_to_tenant` (si no existe) |
| `scripts/link_existing_patients.py` | Create | Backfill script one-time |

## Interfaces / Contracts

### Función helper: `normalize_phone_e164`

```python
def normalize_phone_e164(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    return f"+{digits}"
```

### Socket event: `PATIENT_CREATED`

```python
{
    "patient_id": int,
    "phone_number": str,      # normalized E.164
    "tenant_id": int,
    "first_name": str,
    "last_name": str,
    "status": str,            # "active" | "guest"
}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `normalize_phone_e164` | Test múltiples formatos de entrada |
| Integration | `create_patient` con link | Mock DB, verificar socket emitido, linked_patient_id seteado |
| Integration | `get_or_create_conversation` con link | Mock DB, verificar linked_patient_id seteado cuando paciente existe |
| E2E | Backfill script | Ejecutar sobre data de test, verificar resultados |

## Migration / Rollout

**No migration required.** Ejecutar backfill post-deploy para linkear pacientes existentes.

## Open Questions

- [x] Ninguna — todos los detalles fueron resueltos en exploration y proposal.
