# Exploration: Auto-link de Pacientes con Conversaciones de Chat

## Problema

Cuando un paciente es creado **manualmente desde la UI de Pacientes** (no por la IA/agente), las conversaciones de WhatsApp existentes (de ese mismo número) **no se vinculan automáticamente**. Como resultado:

- La conversación muestra el badge **"Lead"** en lugar de **"Paciente"**
- El panel derecho muestra el botón **VERDE "Crear paciente"** en vez de **AZUL "Ver ficha"**
- El contexto clínico del paciente (turnos, documentos, etc.) no aparece en el chat

## Flujo Actual del Bug

```
1. 📩 Paciente manda WhatsApp → Llega por YCloud
2. 📝 ensure_patient_exists(create_if_missing=False) → NO crea paciente (solo busca)
3. 💾 Mensaje guardado en chat_messages + chat_conversations creada
4. 👤 Admin crea paciente MANUALMENTE desde Pacientes → INSERT en patients
5. ❌ create_patient NO verifica si hay chat_conversations existentes
6. ❌ linked_patient_id nunca se setea en chat_conversations
7. ❌ No se emite socket event para actualizar frontend
8. 🔴 Conversación sigue mostrando "Lead"
```

## Archivos y Líneas Clave

### Modelo `ChatConversation` — `orchestrator_service/models.py:161-204`
- `external_user_id`: teléfono en formato RAW de YCloud (ej: `"5491144445555"`)
- `linked_patient_id`: FK a `patients.id`, nullable, diseñado para este linking pero NUNCA se setea automáticamente

### YCloud extrae teléfono SIN normalizar — `services/channels/ycloud.py:33`
```python
external_user_id = msg.get("from")   # RAW: "5491144445555", sin "+"
```

### `get_or_create_conversation` NO setea `linked_patient_id` — `db.py:151-239`
- Crea/actualiza `chat_conversations` con `external_user_id` RAW
- Nunca busca un paciente existente por ese teléfono
- Nunca setea `linked_patient_id`

### `create_patient` (desde UI) — `admin_routes.py:4513-4582`
- `(p.phone_number or "").strip()` — solo strip(), SIN normalización
- INSERT directo, SIN verificar `chat_conversations` existentes
- SIN emitir socket event `PATIENT_CREATED`

### YCloud Sessions Query — `admin_routes.py:1480-1529`
```sql
FROM patients p
WHERE p.tenant_id = $1
AND EXISTS (SELECT 1 FROM chat_messages WHERE tenant_id = $1 AND from_number = p.phone_number)
```
- Usa igualdad EXACTA de teléfono. Si formatos difieren → no encuentra al paciente.

### `normalize_phone` — `admin_routes.py:379-384`
- Existe pero NO se usa en `create_patient`
- Normaliza a `+5491144445555`

### `normalize_phone_e164` — `ycloud_client.py:20-51`
- Existe pero NO se llama en el webhook principal
- Solo se usa en `ycloud_sync_service.py`

### Frontend `PATIENT_CREATED` handler — `ChatsView.tsx:394-405`
```typescript
socketRef.current.on('PATIENT_CREATED', (data) => {
  setSessions(prev => prev.map(s =>
    s.phone_number === data.phone_number
      ? { ...s, patient_id: data.patient_id, patient_name: fullName }
      : s
  ));
  if (selectedSessionRef.current?.phone_number === data.phone_number) {
    setSelectedSession(prev => prev ? { ...prev, patient_id: data.patient_id, patient_name: fullName } : prev);
    fetchPatientContext(data.phone_number, data.tenant_id);
  }
});
```
- El handler YA existe en frontend. Solo falta que el backend lo emita.

### Frontend `handlePatientCreated` — `ChatsView.tsx:632-647`
- Callback que se pasa al modal de crear paciente desde chat sidebar
- Actualiza sesiones y selectedSession con el nuevo patient_id
- Dispara refetch de patient context

## Diagnóstico

**Causa raíz:** El endpoint `create_patient` y `get_or_create_conversation` no se comunican entre sí. Cada uno opera de forma independiente:

| Operación | Crea en patients | Crea en chat_conversations | Setea linked_patient_id | Socket event |
|-----------|:---:|:---:|:---:|:---:|
| YCloud webhook (mensaje entrante) | Solo si create_if_missing=True | ✅ Sí | ❌ No | ❌ No |
| `create_patient` (UI Pacientes) | ✅ Sí | ❌ No | ❌ No | ❌ No |

**Los formatos de teléfono también son inconsistentes:**
- YCloud RAW: `"5491144445555"`
- UI Pacientes: lo que el admin escriba (`"115551234"`, `"+5491144445555"`, etc.)
- `final_phone`: `"+5491144445555"`
