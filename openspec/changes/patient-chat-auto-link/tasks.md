# Tasks: Auto-link de Pacientes con Conversaciones de Chat

## Phase 1: Phone normalization y socket helper

- [x] 1.1 `normalize_phone()` ya existe en `admin_routes.py:379` — usada en `create_patient`
- [x] 1.2 Socket event `PATIENT_CREATED` ya se emite en `create_patient` (líneas 4538-4557)
- [x] 1.3 Phone normalizado con `normalize_phone()` antes de INSERT/UPSERT

## Phase 2: Link al crear paciente (create_patient)

- [x] 2.1 En `create_patient`: buscar `chat_conversations` por phone (con y sin +)
- [x] 2.2 En `create_patient`: setear `linked_patient_id` en conversaciones encontradas
- [x] 2.3 En `create_patient`: emitir socket event `PATIENT_CREATED` post-link (ya existía)

## Phase 3: Link al crear conversación (YCloud webhook)

- [x] 3.1 En `db.py:get_or_create_conversation`: buscar paciente por phone (RAW y normalizado)
- [x] 3.2 En `db.py:get_or_create_conversation`: setear `linked_patient_id` si paciente existe

## Phase 4: Auto-backfill en deploy

- [x] 4.1 Crear `scripts/link_existing_patients.py` con lógica de matching por tenant
- [x] 4.2 Integrar auto-link en `start.sh` como inline Python post-migraciones
- [x] 4.3 Crear `orchestrator_service/scripts/link_chat_patients.py` como módulo importable

## Phase 5: Verificación

- [ ] 5.1 Test: crear paciente desde UI con número que tiene conversación → link automático
- [ ] 5.2 Test: mensaje entrante de número con paciente existente → link automático
- [ ] 5.3 Test: backfill linkea pacientes existentes sin duplicar
