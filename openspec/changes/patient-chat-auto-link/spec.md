# Specs: Auto-link de Pacientes con Conversaciones de Chat

## 1. Overview

Cuando un paciente es creado manualmente desde la UI de **Pacientes** (o desde el modal "Crear paciente" del chat), o cuando llega un mensaje de WhatsApp de un número que ya tiene un paciente registrado, el sistema DEBE vincular automáticamente la conversación de chat (`chat_conversations`) con el registro del paciente (`patients`) mediante `linked_patient_id`.

Esto garantiza que:
- La conversación muestre el badge **"Paciente"** en lugar de **"Lead"**
- El panel derecho muestre el botón **AZUL "Ver ficha"** en lugar de **VERDE "Crear paciente"**
- El contexto clínico (turnos, documentos, etc.) esté disponible en el chat
- El nombre y datos del paciente se muestren correctamente en la conversación

## 2. Functional Requirements

### FR-01: Normalización de teléfono al crear paciente

El endpoint `POST /admin/patients` DEBE normalizar el número de teléfono a formato E.164 antes de guardarlo.

- Criterio: `"5491144445555"` → `"+5491144445555"`
- Criterio: `"+5491144445555"` → `"+5491144445555"` (ya normalizado)
- Criterio: `"115551234"` → `"+549115551234"` (código de país Argentina +549)
- Criterio: `"01144445555"` → `"+5491144445555"`

Si el número no puede normalizarse (vacío, inválido), el endpoint DEBE rechazar la creación con error 422.

### FR-02: Vincular conversaciones al crear paciente

Cuando `POST /admin/patients` crea un paciente exitosamente, el sistema DEBE:

1. Buscar en `chat_conversations` todas las filas que coincidan con el teléfono del paciente, usando múltiples formatos:
   ```sql
   WHERE tenant_id = $1 
     AND channel = 'whatsapp'
     AND (external_user_id = $2 OR external_user_id = $3)
   ```
   Donde `$2 = normalized_phone` (con "+") y `$3 = phone_without_plus` (sin "+").

2. Para cada conversación encontrada donde `linked_patient_id IS NULL`:
   ```sql
   UPDATE chat_conversations 
   SET linked_patient_id = $1, linked_at = NOW() 
   WHERE id = $2
   ```

3. Emitir socket event `PATIENT_CREATED` con:
   ```json
   {
     "patient_id": <int>,
     "phone_number": "<normalized_phone>",
     "tenant_id": <int>,
     "first_name": "<name>",
     "last_name": "<last_name>",
     "status": "active"
   }
   ```

### FR-03: Vincular paciente al crear conversación (YCloud webhook)

Cuando `get_or_create_conversation` crea o actualiza una conversación (`chat_conversations`), el sistema DEBE:

1. Buscar si existe un paciente con el mismo teléfono en `patients`:
   ```sql
   SELECT id FROM patients 
   WHERE tenant_id = $1 
     AND status != 'deleted'
     AND (phone_number = $2 OR phone_number = $3)
   ```
   Donde `$2 = external_user_id` (formato RAW) y `$3 = normalized_phone` (con "+").

2. Si se encuentra un paciente Y `linked_patient_id IS NULL`:
   ```sql
   UPDATE chat_conversations 
   SET linked_patient_id = $1, linked_at = NOW() 
   WHERE id = $2
   ```

3. Si se encuentra un paciente Y `linked_patient_id` ya está seteado al ID correcto → no hacer nada (ya vinculado).

### FR-04: Actualización del frontend sin refresh manual

Cuando se emite `PATIENT_CREATED` desde el backend:

1. El frontend DEBE actualizar la sesión en la lista de chats (`setSessions`) para que muestre "Paciente" (emerald badge) en lugar de "Lead" (amber badge).

2. Si la conversación es la actualmente seleccionada (`selectedSession`), el frontend DEBE:
   - Actualizar `patient_id` en `selectedSession`
   - Refrescar el contexto clínico (`fetchPatientContext`)

3. **Criterio:** No se requiere refresh manual (F5) para ver el cambio.

### FR-05: Botón del contexto clínico actualizado

Cuando la conversación está vinculada a un paciente (`patient_id` presente), el panel derecho DEBE mostrar:

- Badge **AZUL "Paciente"** en lugar de ámbar "Lead"
- Botón **AZUL "Ver ficha del paciente"** (si `status = 'active'`)
- Botón **ÁMBAR "Editar paciente"** (si `status = 'guest'`)

En NINGÚN caso DEBE mostrar el botón **VERDE "Crear paciente"**.

### FR-06: Backfill one-time

Se DEBE proveer un script `scripts/link_existing_patients.py` que:

1. Itera por todos los tenants
2. Para cada paciente en `patients`:
   - Normaliza el teléfono
   - Busca `chat_conversations` coincidentes
   - Si `linked_patient_id IS NULL` → actualiza
3. Loggea:
   - `[OK] Tenant {id}: linked patient {patient_id} → conversation {conv_id}`
   - `[SKIP] Tenant {id}: patient {patient_id} no tiene conversación`
   - `[ALREADY] Tenant {id}: patient {patient_id} ya linkeado a conv {conv_id}`
4. Reporta resumen al final: `Linkeados: X | Saltados: Y | Ya linkeados: Z`

## 3. Non-Functional Requirements

### NFR-01: Sin regression en flujo existente

El flujo actual de creación de paciente desde el chat sidebar (modal "Crear paciente") NO DEBE romperse.

### NFR-02: Idempotencia

Si `create_patient` se llama dos veces con el mismo teléfono, el sistema DEBE:
- Encontrar al paciente existente (por `phone_number` único)
- Actualizar datos si es necesario (UPSERT)
- No crear duplicados en `chat_conversations`

### NFR-03: Performance

La búsqueda de `chat_conversations` al crear paciente DEBE usar índices existentes:
- `idx_chat_conv_tenant_channel_user` sobre `(tenant_id, channel, external_user_id)`
- No DEBE agregar queries O(N) por paciente creado

### NFR-04: Compatibilidad hacia atrás

Pacientes existentes sin `linked_patient_id` seteados NO DEBEN romperse. El sistema DEBE seguir funcionando mientras el backfill no se haya ejecutado.

## 4. Scenarios

### Scenario 1: Paciente creado desde UI con conversación existente

**Given:**
- Existe una conversación en `chat_conversations` con `external_user_id = "5491144445555"`
- Existen mensajes en `chat_messages` desde ese número
- NO existe paciente en `patients` con ese teléfono

**When:**
- Admin crea paciente desde Pacientes con teléfono `"115551234"`

**Then:**
- Sistema normaliza a `"+549115551234"`
- Sistema busca conversaciones con `external_user_id IN ("+549115551234", "549115551234")`
- Si encuentra match → setea `linked_patient_id`
- Emite socket event `PATIENT_CREATED`
- Frontend actualiza la sesión a "Paciente" automáticamente

### Scenario 2: Mensaje entrante con paciente existente

**Given:**
- Existe paciente en `patients` con `phone_number = "+5491144445555", status = "active"`
- NO existe conversación en `chat_conversations` para ese número
- NO hay `linked_patient_id` seteado

**When:**
- Paciente envía mensaje de WhatsApp
- YCloud webhook recibe el mensaje
- `get_or_create_conversation` crea nueva conversación

**Then:**
- Sistema crea `chat_conversations` con `external_user_id = "5491144445555"` (RAW de YCloud)
- Sistema busca paciente con `phone_number IN ("5491144445555", "+5491144445555")`
- Encuentra el paciente → setea `linked_patient_id`

### Scenario 3: Backfill sobre datos existentes

**Given:**
- Varios pacientes creados manualmente sin `linked_patient_id`
- Conversaciones existentes en `chat_conversations`

**When:**
- Se ejecuta `python scripts/link_existing_patients.py`

**Then:**
- Todos los pacientes con conversaciones coincidentes quedan linkeados
- Log muestra el resumen de operaciones

### Scenario 4: Sin conversación existente

**Given:**
- NO existe conversación para el teléfono del paciente

**When:**
- Admin crea paciente desde Pacientes

**Then:**
- Sistema crea el paciente normalmente
- No encuentra conversaciones para linkear
- No emite `PATIENT_CREATED` (no hay sesión que actualizar)
- Flujo normal continúa

### Scenario 5: Teléfono ya existe (duplicado)

**Given:**
- Existe paciente en `patients` con `phone_number = "+5491144445555"`

**When:**
- Admin intenta crear otro paciente con `phone_number = "5491144445555"`

**Then:**
- Sistema normaliza el phone a `"+5491144445555"`
- Detecta conflicto con UNIQUE constraint `(tenant_id, phone_number)`
- Hace UPSERT: ON CONFLICT DO UPDATE (actualiza datos, no crea duplicado)
- Si hay conversaciones sin linked_patient_id → las linkea

## 5. Files to Modify

| File | Change |
|------|--------|
| `orchestrator_service/admin_routes.py` | `create_patient`: normalizar phone, buscar conversaciones, linkear, emitir socket |
| `orchestrator_service/db.py` | `get_or_create_conversation`: buscar paciente y setear `linked_patient_id` |
| `orchestrator_service/main.py` | (posible) función helper para emitir socket event |
| `scripts/link_existing_patients.py` | (nuevo) one-time backfill script |
