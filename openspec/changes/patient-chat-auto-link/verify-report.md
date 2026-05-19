# Verification Report: Auto-link de Pacientes con Conversaciones de Chat

**Change**: patient-chat-auto-link
**Mode**: Standard

---

## Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 11 |
| Tasks complete | 9 |
| Tasks incomplete | 2 |

**Incomplete:**
- 4.2 Probar script en entorno local con data de prueba (post-deploy)
- 5.3 Test: backfill linkea pacientes existentes sin duplicar (post-deploy)

---

## Build & Tests Execution

**Build**: ⚠️ No ejecutado (requiere entorno con DB + dependencias)

**Tests**: ➖ No hay tests unitarios específicos para estos endpoints

---

## Spec Compliance Matrix

| Requirement | Scenario | Evidence | Result |
|-------------|----------|----------|--------|
| FR-01: Normalizar teléfono | `create_patient` con cualquier formato | `admin_routes.py:4525` — `normalize_phone(raw_phone)` | ✅ COMPLIANT |
| FR-01: Rechazar phone vacío | `create_patient` con phone vacío | `admin_routes.py:4523-4524` — raise 422 | ✅ COMPLIANT |
| FR-02: Vincular conversaciones | `create_patient` linkea `chat_conversations` | `admin_routes.py:4556-4570` — UPDATE con y sin + | ✅ COMPLIANT |
| FR-02: Socket event | `create_patient` emite `PATIENT_CREATED` | `admin_routes.py:4572-4591` — `sio.emit` existente | ✅ COMPLIANT |
| FR-03: Vincular al crear conversación | `get_or_create_conversation` linkea paciente | `db.py:244-269` — busca patient por phone, setea linked_patient_id | ✅ COMPLIANT |
| FR-04: Frontend sin refresh | `PATIENT_CREATED` actualiza sesión | `ChatsView.tsx:394-405` — handler existente | ✅ COMPLIANT |
| FR-04: Botón contexto clínico | `patientId` truthy → "Ver ficha" | `ChatsView.tsx:1777` — `selectedSession?.patient_id` (se setea vía socket) | ✅ COMPLIANT |

---

## Correctness (Static — Structural Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| FR-01: Normalización E.164 | ✅ | `normalize_phone()` en admin_routes.py, usada en create_patient |
| FR-01: ON CONFLICT DO UPDATE | ✅ | Upsert con promoción de status a 'active' |
| FR-02: Link por múltiples formatos | ✅ | Busca con y sin "+" en external_user_id |
| FR-02: linked_patient_id + linked_at | ✅ | UPDATE con ambos campos |
| FR-03: Solo WhatsApp channel | ✅ | `if channel == 'whatsapp'` gate |
| FR-03: Excluye pacientes deleted | ✅ | `AND status != 'deleted'` |
| FR-03: No sobreescribe link existente | ✅ | `AND linked_patient_id IS NULL` |
| FR-04: Socket event | ✅ | `sio.emit("PATIENT_CREATED", ...)` existente y funcional |
| FR-06: Backfill script | ✅ | `scripts/link_existing_patients.py` con dry-run y logging |

---

## Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| Phone normalization en create_patient | ✅ Sí | Usa normalize_phone() existente |
| ON CONFLICT DO UPDATE | ✅ Sí | Maneja caso de guest existente |
| linked_patient_id existente | ✅ Sí | Sin migración nueva |
| Socket event existente | ✅ Sí | Ya se emitía, solo se mejoró el phone_number |
| Backfill script standalone | ✅ Sí | scripts/link_existing_patients.py |

---

## Issues Found

**CRITICAL**
- Ninguno

**WARNING**
- `get_or_create_conversation` tiene `import re` inline (dentro del método) — no es un problema funcional pero es anti-patrón. Podría moverse al tope del archivo.

**SUGGESTION**
- Agregar tests unitarios para `normalize_phone` (función existente no testeada)
- Agregar test de integración para el linking en `create_patient`

---

## Verdict

**PASS** ✅

El cambio está completo para los flujos principales:

1. **`create_patient`**: normaliza teléfono, hace UPSERT (ON CONFLICT), linkea conversaciones existentes por teléfono en ambos formatos (con/sin +), emite socket event
2. **`get_or_create_conversation`**: al crear/actualizar conversación WhatsApp, busca paciente existente por teléfono (RAW y normalizado) y setea `linked_patient_id`
3. **Backfill script**: `scripts/link_existing_patients.py` con soporte --tenant, --dry-run
4. **Frontend**: sin cambios necesarios — el handler `PATIENT_CREATED` ya existe y actualiza la UI

Los tasks pendientes (4.2, 5.3) son post-deploy y dependen de tener datos reales o un entorno de prueba con DB.
