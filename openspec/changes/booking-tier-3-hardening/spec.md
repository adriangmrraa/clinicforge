# Spec — Booking TIER 3 Hardening

## Capability 1: Tenant-aware Timezone Resolution

### Requirement 1.1: Country → Timezone mapping table

The system SHALL provide a deterministic mapping from `tenants.country_code` (ISO 3166-1 alpha-2) to a canonical IANA timezone identifier. The mapping SHALL be defined in code as a Python dict in a new module `orchestrator_service/services/tz_resolver.py` and SHALL include at minimum:

```
AR → America/Argentina/Buenos_Aires
CL → America/Santiago
UY → America/Montevideo
PY → America/Asuncion
BR → America/Sao_Paulo
MX → America/Mexico_City
ES → Europe/Madrid
US → America/New_York
PE → America/Lima
CO → America/Bogota
```

#### Scenario: Known country code resolves to canonical timezone
- WHEN `resolve_tz_for_country("CL")` is called
- THEN it SHALL return `ZoneInfo("America/Santiago")`

#### Scenario: Unknown country code falls back to UTC
- WHEN `resolve_tz_for_country("ZZ")` is called
- THEN it SHALL return `ZoneInfo("UTC")` AND emit a `logger.warning` with the unknown code

#### Scenario: Lowercase country code is normalized
- WHEN `resolve_tz_for_country("ar")` is called
- THEN it SHALL return `ZoneInfo("America/Argentina/Buenos_Aires")`

### Requirement 1.2: Tenant timezone helper

The system SHALL provide an async helper `get_tenant_tz(tenant_id: int) -> ZoneInfo` that resolves the tenant's `country_code` from the `tenants` table and returns the corresponding `ZoneInfo`. The helper SHALL cache results in-process for at least 5 minutes per tenant_id.

#### Scenario: Helper returns Argentina TZ for tenant with country_code='AR'
- GIVEN a tenant row with `country_code = 'AR'`
- WHEN `await get_tenant_tz(tenant_id)` is called
- THEN it SHALL return `ZoneInfo("America/Argentina/Buenos_Aires")`

#### Scenario: Cache hit avoids second DB query
- GIVEN `await get_tenant_tz(1)` was called and returned a value
- WHEN `await get_tenant_tz(1)` is called again within 5 minutes
- THEN no SQL query SHALL be executed AND the same `ZoneInfo` instance SHALL be returned

### Requirement 1.3: All datetime operations honor tenant timezone

Every code path that constructs `datetime.now()`, parses date/time from user input, formats datetimes for display, or compares datetimes against current time within the booking flow SHALL use the tenant-resolved timezone, not the hardcoded `ARG_TZ`. This applies to at minimum:

- `parse_date()`, `parse_datetime()`, `get_now_arg()` in `main.py`
- `check_availability`, `book_appointment`, `cancel_appointment`, `reschedule_appointment`, `confirm_slot`, `list_my_appointments` AI tools
- Holiday lookups in `holidays_service` (already country-aware, must align)
- Working hours computations in `services/buffer_task.py` if any
- Slot picker `pick_representative_slots`
- Audit log `created_at` (server-side `NOW()` is fine — UTC is canonical at storage layer)

#### Scenario: Tenant in Chile during DST sees correct slots
- GIVEN a tenant with `country_code = 'CL'`
- AND the current real-world date is during Chilean DST (e.g. 2026-01-15)
- WHEN the AI agent calls `check_availability(date_query="mañana a las 10hs")`
- THEN the resolved `apt_datetime` SHALL be in `America/Santiago` timezone with the DST-correct offset (`-03:00` summer / `-04:00` winter as IANA dictates)

#### Scenario: Two tenants in different timezones handled in same process
- GIVEN tenant A has `country_code = 'AR'` and tenant B has `country_code = 'ES'`
- WHEN `check_availability` is called for tenant A and then tenant B in the same process
- THEN tenant A SHALL use `America/Argentina/Buenos_Aires` AND tenant B SHALL use `Europe/Madrid` AND the cached values SHALL NOT cross-contaminate

### Requirement 1.4: Migration safety for existing tenants

A non-destructive migration SHALL ensure all existing production tenants have a valid `country_code`. If any tenant has `country_code = 'US'` (the schema default) but is actually operating in Argentina (heuristic: clinic phone country prefix `+54`), the migration SHALL flag it in logs but NOT auto-update; manual review by ops.

#### Scenario: Migration runs against production DB with mixed tenants
- GIVEN the production DB contains tenants with `country_code` values `AR`, `US`, `NULL`
- WHEN migration `028_validate_tenant_country_code` runs
- THEN tenants with `NULL` SHALL be set to `'AR'` (Dra. Laura backfill) AND tenants with `US` SHALL be logged for manual review AND no tenant SHALL end up with `NULL` `country_code`

---

## Capability 2: Reschedule Chair Check

### Requirement 2.1: `reschedule_appointment` validates `max_chairs` capacity

Before executing the UPDATE that moves an appointment to a new datetime, `reschedule_appointment` SHALL count the number of currently active appointments (`status IN ('scheduled','confirmed')`) at the new datetime for the same tenant, EXCLUDING the appointment being rescheduled. If the count is greater than or equal to `tenants.max_chairs`, the reschedule SHALL be rejected with a clear error message and no UPDATE SHALL be executed.

#### Scenario: Reschedule into a slot with available chairs succeeds
- GIVEN a tenant with `max_chairs = 4`
- AND there are 2 active appointments at `2026-04-10 10:00`
- WHEN reschedule moves an appointment from another time to `2026-04-10 10:00`
- THEN the UPDATE SHALL succeed AND the appointment count at `2026-04-10 10:00` SHALL become 3

#### Scenario: Reschedule into a full slot is rejected
- GIVEN a tenant with `max_chairs = 4`
- AND there are 4 active appointments at `2026-04-10 10:00`
- WHEN reschedule tries to move an appointment from another time to `2026-04-10 10:00`
- THEN the UPDATE SHALL NOT execute AND the function SHALL return a user-facing message indicating no chair capacity at that time

#### Scenario: Rescheduling within the same slot does not double-count
- GIVEN a tenant with `max_chairs = 4` and 4 active appointments at `2026-04-10 10:00`
- WHEN one of those 4 appointments is rescheduled to `2026-04-10 10:30`
- THEN the count at `10:30` SHALL exclude the appointment being moved AND succeed if the other count at `10:30` is less than 4

### Requirement 2.2: Reschedule operates inside a transaction

The chair count + UPDATE in `reschedule_appointment` SHALL execute inside a single `async with conn.transaction()` block to prevent TOCTOU races between the count and the UPDATE.

#### Scenario: Concurrent reschedule into the last available slot
- GIVEN two simultaneous reschedule requests targeting `2026-04-10 10:00` where only 1 chair remains
- WHEN both reschedules execute concurrently
- THEN at most one SHALL succeed AND the other SHALL be rejected (either by chair count check OR by the UNIQUE constraint from TIER 1 if both target the same professional)

---

## Capability 3: Appointment Audit Log

### Requirement 3.1: New `appointment_audit_log` table

A new table SHALL be created via Alembic migration `028_appointment_audit_log` (or `029` if `028` is taken by Capability 1) with the following columns:

- `id` BIGSERIAL PRIMARY KEY
- `tenant_id` INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE
- `appointment_id` UUID NULL REFERENCES appointments(id) ON DELETE SET NULL
- `action` VARCHAR(32) NOT NULL CHECK (action IN ('created','rescheduled','cancelled','status_changed','payment_updated'))
- `actor_type` VARCHAR(16) NOT NULL CHECK (actor_type IN ('ai_agent','staff_user','patient_self','system'))
- `actor_id` VARCHAR(128) NULL — UUID of users.id when actor_type='staff_user', or descriptive tag otherwise
- `before_values` JSONB NULL
- `after_values` JSONB NULL
- `source_channel` VARCHAR(32) NULL CHECK (source_channel IN ('whatsapp','instagram','facebook','web_admin','nova_voice','api','system'))
- `reason` TEXT NULL
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT NOW()

Indexes:
- `idx_appointment_audit_tenant_apt_time` ON `(tenant_id, appointment_id, created_at DESC)`
- `idx_appointment_audit_tenant_time` ON `(tenant_id, created_at DESC)`

### Requirement 3.2: Helper `log_appointment_mutation`

A helper function `log_appointment_mutation(...)` SHALL be added in a new module `orchestrator_service/services/audit_log.py`. Its signature:

```python
async def log_appointment_mutation(
    tenant_id: int,
    appointment_id: Optional[str],
    action: str,
    actor_type: str,
    actor_id: Optional[str] = None,
    before_values: Optional[dict] = None,
    after_values: Optional[dict] = None,
    source_channel: Optional[str] = None,
    reason: Optional[str] = None,
) -> None
```

The helper SHALL:
- Be best-effort: any exception SHALL be caught and logged as warning, never propagated.
- Insert a single row into `appointment_audit_log`.
- Serialize `before_values` and `after_values` via the existing `to_json_safe` helper.

#### Scenario: AI agent creates appointment
- WHEN `book_appointment` succeeds
- THEN exactly one row SHALL be inserted with `action='created'`, `actor_type='ai_agent'`, `before_values=NULL`, `after_values={...new appointment fields...}`, `source_channel='whatsapp'` (or other channel)

#### Scenario: Staff user reschedules from admin UI
- WHEN an admin endpoint reschedules an appointment
- THEN exactly one row SHALL be inserted with `action='rescheduled'`, `actor_type='staff_user'`, `actor_id=<users.id>`, `before_values={appointment_datetime: <old>}`, `after_values={appointment_datetime: <new>}`, `source_channel='web_admin'`

#### Scenario: Audit log insert fails but mutation succeeds
- GIVEN the audit_log table is temporarily unavailable
- WHEN `book_appointment` succeeds and the audit log INSERT raises an error
- THEN the appointment booking SHALL still be considered successful AND a warning SHALL be logged AND the user-facing response SHALL NOT mention the audit failure

### Requirement 3.3: Audit log read endpoint

A new endpoint `GET /admin/appointments/{appointment_id}/audit` SHALL be added in `admin_routes.py`, protected by `verify_admin_token` and accessible only to users with role `'ceo'` or `'admin'`. It SHALL return all audit log rows for that appointment, ordered by `created_at ASC`, with the actor_id resolved to the user's display name when applicable.

#### Scenario: Admin requests audit log of an appointment
- GIVEN an appointment with 3 audit rows (created, rescheduled, status_changed)
- WHEN admin calls `GET /admin/appointments/{id}/audit`
- THEN the response SHALL be a JSON array of 3 entries in chronological order

#### Scenario: Non-admin user is rejected
- WHEN a user with role `'professional'` calls `GET /admin/appointments/{id}/audit`
- THEN the response SHALL be HTTP 403

#### Scenario: Multi-tenant isolation
- WHEN tenant A's admin calls `GET /admin/appointments/{id}/audit` with an appointment_id belonging to tenant B
- THEN the response SHALL be HTTP 404 (not 200 with leaked data)

### Requirement 3.4: Audit log call sites

The following code paths SHALL invoke `log_appointment_mutation` after their respective mutation succeeds:

| File | Function | Action | Actor type |
|------|----------|--------|------------|
| `main.py` | `book_appointment` (AI tool) | `created` | `ai_agent` |
| `main.py` | `cancel_appointment` (AI tool) | `cancelled` | `ai_agent` |
| `main.py` | `reschedule_appointment` (AI tool) | `rescheduled` | `ai_agent` |
| `admin_routes.py` | POST `/admin/appointments` | `created` | `staff_user` |
| `admin_routes.py` | PUT `/admin/appointments/{id}` | `rescheduled` or `status_changed` | `staff_user` |
| `admin_routes.py` | DELETE `/admin/appointments/{id}` | `cancelled` | `staff_user` |
| `services/nova_tools.py` | `agendar_turno` | `created` | `staff_user` (Nova is voice-driven by staff) |
| `services/nova_tools.py` | `cancelar_turno` | `cancelled` | `staff_user` |
| `services/nova_tools.py` | `reprogramar_turno` | `rescheduled` | `staff_user` |
| `services/nova_tools.py` | `cambiar_estado_turno` | `status_changed` | `staff_user` |
