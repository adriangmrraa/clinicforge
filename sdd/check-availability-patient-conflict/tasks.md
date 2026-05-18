# Tasks: Patient self-conflict guard in check_availability

## Phase 1: Preservar patient_id

- [ ] 1.1 En `check_availability` (~L1708): guardar `_ca_patient_id = patient_row["id"]` después del patient lookup exitoso

## Phase 2: Agregar patient conflict guard

- [ ] 2.1 Entre L2388 (global_busy update) y L2425 (chair constraint): insertar bloque que fetchea appointments del paciente y marca esos slots en TODOS los profesionales del busy_map

## Phase 3: Verificación

- [ ] 3.1 Verificar que `_ca_patient_id` existe después del patient lookup
- [ ] 3.2 Verificar que el bloque de conflict guard usa `if _ca_patient_id:` como guard
- [ ] 3.3 Verificar que el bloque está ANTES de chair constraint (L2425) y DESPUÉS de global_busy (L2388)
