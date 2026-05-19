# Tasks: Phone Prefix por País

## Phase 1: Función de normalización centralizada

- [x] 1.1 Agregar `COUNTRY_PHONE_MAP` y `normalize_phone_for_tenant()` en `main.py`
- [x] 1.2 Importar y usar en `admin_routes.py` (create_patient)
- [x] 1.3 Actualizar `update_patient()` para normalizar teléfono (bug fix)

## Phase 2: Normalizar en todos los puntos de entrada

- [x] 2.1 Normalizar en `db.py:ensure_patient_exists`
- [x] 2.2 Normalizar en `nova_tools.py:_registrar_paciente`
- [x] 2.3 Normalizar en `auth_routes.py:register`

## Phase 3: Frontend PhoneInput

- [x] 3.1 Crear `components/PhoneInput.tsx` con prefijo fijo visual
- [x] 3.2 Reemplazar input en `PatientsView.tsx` por PhoneInput

## Phase 4: Backfill

- [x] 4.1 Crear `scripts/normalize_existing_phones.py`
- [ ] 4.2 Agregar a `start.sh` post-migraciones (opcional, ejecutar manual si se desea)

## Phase 5: Verificación

- [ ] 5.1 Verificar normalización en todos los endpoints (post-deploy)
- [ ] 5.2 Verificar PhoneInput en frontend (post-deploy)
