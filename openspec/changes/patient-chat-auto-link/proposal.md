# Proposal: Auto-link de Pacientes con Conversaciones de Chat

## Intent

Resolver el problema donde pacientes creados manualmente desde la UI de Pacientes no se vinculan automáticamente con sus conversaciones de WhatsApp existentes, causando que el chat muestre "Lead" en lugar de "Paciente" y el botón "Crear paciente" en vez de "Ver ficha".

## Scope

### In Scope
1. **Backend: `create_patient` endpoint** — al crear paciente desde UI, buscar `chat_conversations` existentes por teléfono y setear `linked_patient_id`, emitir socket event
2. **Backend: `get_or_create_conversation`** — al crear/actualizar conversación (YCloud webhook), buscar paciente existente por teléfono y setear `linked_patient_id`
3. **Backend: Emisión de socket event `PATIENT_CREATED`** desde `create_patient`
4. **Backend: Phone normalization** — normalizar teléfono a E.164 consistentemente en `create_patient`
5. **Frontend: Manejo de `PATIENT_CREATED`** — verificar que el handler existente funcione correctamente cuando el paciente se crea desde Pacientes (no solo desde chat)
6. **One-time backfill: Script** para vincular pacientes existentes no linkeados con sus conversaciones

### Out of Scope
- ✅ Chatwoot (Instagram/Facebook) — el usuario confirmó que solo usa YCloud para WhatsApp
- Refactor completo del sistema de normalización de teléfonos
- Migraciones de base de datos (linked_patient_id ya existe)

## Approach

### Part A: Fix `create_patient` endpoint (`admin_routes.py:4513-4582`)

```
Algoritmo:
1. Normalizar phone a E.164 (agregar "+" si no tiene)
2. INSERT paciente (con upsert si ya existe el normalized phone)
3. Buscar en chat_conversations WHERE tenant_id = $1 AND channel = 'whatsapp'
   AND (external_user_id = $2 OR external_user_id = $3)  ← múltiples formatos
4. Para cada conversación encontrada:
   - UPDATE SET linked_patient_id = nuevo_patient_id, linked_at = NOW()
5. Emitir socket event 'PATIENT_CREATED' con { patient_id, phone_number, tenant_id, first_name, last_name, status }
```

### Part B: Fix `get_or_create_conversation` (`db.py:151-239`)

```
Algoritmo:
1. Crear/actualizar conversación (lógica existente)
2. Buscar paciente por teléfono: SELECT id FROM patients WHERE tenant_id = $1 
   AND (phone_number = $2 OR phone_number = $3)  ← múltiples formatos
3. Si se encuentra paciente Y linked_patient_id IS NULL:
   - UPDATE chat_conversations SET linked_patient_id = patient_id, linked_at = NOW()
```

### Part C: Phone normalization utility

Crear función `normalize_phone_e164(phone: str) -> str` reusable:
- Eliminar todos los non-digits
- Si no empieza con "+", agregar "+"
- Para Argentina: asegurar formato "+549..." si es necesario

Usar esta función en:
- `create_patient` (al guardar phone en patients)
- `get_or_create_conversation` (al buscar paciente por phone)
- `get_chat_sessions` (al matchear patients con chat_messages) — ya usa EXACT match, mejorar con normalized match

### Part D: Socket event emission

En `create_patient`, después de insertar y linkear:
```python
await emit_socket_event(tenant_id, {
    "event": "PATIENT_CREATED",
    "data": {
        "patient_id": new_id,
        "phone_number": normalized_phone,
        "tenant_id": tenant_id,
        "first_name": first_name,
        "last_name": last_name,
        "status": status,
    }
})
```

### Part E: One-time backfill script (`scripts/link_existing_patients.py`)

```
Para cada paciente en patients de cada tenant:
  1. Normalizar phone a E.164
  2. Buscar chat_conversations por phone (múltiples formatos)
  3. Si linked_patient_id IS NULL → UPDATE
  4. Loggear resultados
```

## Impact Analysis

### Frontend Impact
- **Ningún cambio necesario** en componentes React
- El handler `PATIENT_CREATED` (ChatsView.tsx:394-405) ya maneja la actualización de sesiones y refresco de contexto clínico
- El callback `handlePatientCreated` (ChatsView.tsx:632-647) ya actualiza selectedSession
- Solo se necesita verificar que el handler recibe el event cuando se emite desde Pacientes (no solo desde chat sidebar)

### Backend Impact
- **Archivos a modificar:**
  - `admin_routes.py` — `create_patient` endpoint
  - `db.py` — `get_or_create_conversation`
  - (posible) `routes/chat_webhooks.py` — flujo YCloud
  - (nuevo) `scripts/link_existing_patients.py` — backfill

### Database Impact
- **Sin migraciones nuevas** — `linked_patient_id` ya existe en `chat_conversations`

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Phone format mismatch entre patients y conversations | Buscar con múltiples formatos (con y sin "+") |
| Duplicación de pacientes por distintos formatos de phone | Usar ON CONFLICT DO UPDATE en create_patient |
| Socket event emitido pero frontend no lo capta | Verificar que el event name coincide exactamente: `PATIENT_CREATED` |
| Backfill script corre demasiado tiempo | Procesar por tenant, con límite de rows por batch |

## Verification

1. **Test case 1:** Crear paciente desde UI Pacientes con número que YA tiene conversación de WhatsApp
   - Esperado: conversación cambia a "Paciente" automáticamente sin refresh manual
2. **Test case 2:** Paciente existente sin linked_patient_id envía nuevo WhatsApp
   - Esperado: `get_or_create_conversation` linkea automáticamente
3. **Test case 3:** Backfill script corre sobre datos existentes
   - Esperado: todas las conversaciones con paciente existente quedan linkeadas
4. **Test case 4:** Crear paciente desde chat sidebar ("Crear paciente" verde)
   - Esperado: sigue funcionando como antes (sin regression)
