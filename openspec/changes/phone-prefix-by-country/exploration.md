# Exploration: Phone Prefix por País

## Contexto

Las clínicas en ClinicForge tienen un `country_code` (ISO 3166-1 alpha-2, ej: `"AR"` para Argentina) pero este campo **no se usa para normalización de teléfonos**. Existen múltiples funciones de normalización inconsistentes y ninguna toma en cuenta el país de la clínica.

## Hallazgos Clave

### `tenants.country_code` existe pero está aislado

- `models.py:243` — `country_code = Column(String(2), nullable=False, default="US")`
- Baseline migration tiene `NOT NULL DEFAULT 'AR'`
- **NO se usa para teléfonos** — solo para feriados (holiday_service.py)
- No existe un campo `phone_prefix` separado

### Funciones de normalización actuales (ninguna usa country_code)

| Función | Archivo | Línea | Comportamiento |
|---------|---------|-------|----------------|
| `normalize_phone()` | admin_routes.py | 379 | Solo agrega `+`, no deduce país |
| `normalize_phone_e164()` | ycloud_client.py | 20 | Hardcodeada para Argentina |
| `normalize_phone_digits()` | main.py | 250 | Solo dígitos sin `+` |
| `generate_phone_variants()` | admin_routes.py | 387 | Hardcodeada para Argentina |

### Puntos de entrada de teléfonos SIN normalización de país

| Endpoint/Flujo | Normaliza? | Problema |
|----------------|:----------:|----------|
| `POST /admin/patients` (create_patient) | ✅ `normalize_phone()` | No agrega código de país |
| `PUT /admin/patients/{id}` (update_patient) | ❌ No normaliza | BUG: guarda raw |
| `POST /auth/register` | ❌ No normaliza | Guarda raw |
| Nova `_registrar_paciente()` | ❌ No normaliza | Guarda raw |
| `ensure_patient_exists()` | ❌ No normaliza | Guarda raw de YCloud |

### Frontend: inputs de teléfono

| Componente | Comportamiento |
|------------|----------------|
| `CreatePatientModal.tsx:186` | Readonly (viene del chat, ya normalizado) |
| `PatientsView.tsx:918-930` | **Input libre** — usuario escribe cualquier formato |
| `ClinicsView.tsx:731` | Bot phone number |
| `LoginView.tsx:370` | Registro de profesional |

### Inconsistencias existentes

- `update_patient()` no normaliza el teléfono (vs `create_patient()` que sí)
- Nova guarda teléfonos tal cual los pasa el LLM
- `ensure_patient_exists()` guarda RAW de YCloud (con o sin `+`)
- El UNIQUE constraint `(tenant_id, phone_number)` en `patients` hace que formatos diferentes creen duplicados

### Formato actual YCloud para Argentina

WhatsApp/YCloud envía números en E.164 **con 9**: `+5492996114843`  
Los pacientes pueden cargarse manualmente como: `3704868421`, `+543704868421`, etc.  
→ El `9` entre `54` y el código de área es específico de Argentina para celulares.
