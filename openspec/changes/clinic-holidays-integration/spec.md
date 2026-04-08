# SPEC: Clinic Holidays Integration

**Change**: `clinic-holidays-integration`
**Project**: ClinicForge
**Scope**: Frontend ClinicsView modal + backend test verification
**Out of scope**: AgendaView, HolidayDetailModal, holiday_service, buffer_task, build_system_prompt (all already complete)

---

## RFC Keywords

Throughout this document: MUST = mandatory, SHALL = equivalent to MUST, SHOULD = recommended, MAY = optional.

---

## REQ-1 — Schema State Verification

### REQ-1.1 — Audit Before Migrate

Before running any migration, the implementation MUST perform a schema audit to verify the current state of `tenant_holidays`.

Expected columns (from migrations 010 + 014):
- `id` INTEGER PRIMARY KEY
- `tenant_id` INTEGER FK tenants.id CASCADE
- `date` DATE NOT NULL
- `name` TEXT NOT NULL
- `holiday_type` VARCHAR(20) CHECK IN ('closure', 'override_open')
- `is_recurring` BOOLEAN DEFAULT false
- `custom_hours_start` TIME nullable
- `custom_hours_end` TIME nullable
- `created_at` TIMESTAMPTZ DEFAULT now()

### REQ-1.2 — Migration 031 (conditional)

Migration 031 MUST be created IF AND ONLY IF any column from REQ-1.1 is absent from the live schema.

If all columns are present, migration 031 MUST NOT be created (no empty migration).

Migration file, if created: `orchestrator_service/alembic/versions/031_clinic_holidays_missing_fields.py`

Migration MUST be idempotent (use `_column_exists()` guard pattern consistent with migrations 010–014 before adding any column).

Migration MUST include both `upgrade()` and `downgrade()`.

---

## REQ-2 — Backend Endpoint Contract

The following endpoints MUST exist and behave as specified. They ALREADY exist in `admin_routes.py`. This REQ documents the contract for test verification.

### REQ-2.1 — GET /admin/holidays

**Auth**: MUST require `verify_admin_token`. `tenant_id` MUST be derived from JWT, never from query params.

**Query param**: `days` (int, default 90, range 1–365).

**Response 200**:
```json
{
  "upcoming": [
    {
      "id": 1,
      "date": "2026-12-25",
      "name": "Navidad",
      "holiday_type": "closure",
      "source": "library",
      "is_recurring": false,
      "custom_hours": null
    }
  ],
  "custom": [
    {
      "id": 1,
      "date": "2026-12-25",
      "name": "Navidad",
      "holiday_type": "closure",
      "is_recurring": false,
      "custom_hours_start": null,
      "custom_hours_end": null,
      "created_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

`upcoming` items include national holidays from the `holidays` Python library; `custom` items are only rows in `tenant_holidays`.

### REQ-2.2 — POST /admin/holidays

**Auth**: MUST require `verify_admin_token`.

**Body**:
```json
{
  "date": "YYYY-MM-DD",
  "name": "string (non-empty)",
  "holiday_type": "closure | override_open",
  "is_recurring": false,
  "custom_hours_start": "HH:MM (nullable, only meaningful if holiday_type=override_open)",
  "custom_hours_end": "HH:MM (nullable)"
}
```

**Response 200**: `{"id": <new_id>, ...record fields}`

**Error 422**: if `holiday_type` not in ('closure', 'override_open').

**Error 409**: if unique constraint `(tenant_id, date, holiday_type)` violated — MUST return `{"detail": "Ya existe un feriado con ese tipo para esa fecha"}`.

### REQ-2.3 — PUT /admin/holidays/{id}

**Auth**: MUST require `verify_admin_token`.

MUST verify `tenant_id` ownership before updating (404 if not found or wrong tenant).

Accepts partial update: any subset of `name`, `date`, `holiday_type`, `is_recurring`, `custom_hours_start`, `custom_hours_end`.

If `holiday_type` changes to `'closure'`, `custom_hours_start` and `custom_hours_end` MUST be NULLed (enforced by admin_routes.py:2960).

**Response 200**: `{"ok": true}`.

### REQ-2.4 — DELETE /admin/holidays/{id}

**Auth**: MUST require `verify_admin_token`.

MUST verify tenant ownership (404 if not found or wrong tenant).

MUST only delete custom records (source='custom'). National library holidays cannot be deleted (they have no `id` in the DB — they are synthesized at query time; attempting to DELETE a non-existent id returns 404 naturally).

**Response 200**: `{"ok": true}`.

### REQ-2.5 — POST /admin/holidays/toggle

Toggles a date between closed and override_open. Used by HolidayDetailModal (existing). MAY be used by the new ClinicsView section for national holidays.

---

## REQ-3 — Agent Context Wiring Verification

### REQ-3.1 — buffer_task.py Calls get_upcoming_holidays

The call at `buffer_task.py:685–693` MUST:
- Call `get_upcoming_holidays(db.pool, tenant_id, days_ahead=30)`.
- Catch and log any exception as non-fatal (current code uses `logger.debug`).
- Pass the result as `upcoming_holidays=_upcoming_holidays` to `build_system_prompt()` at line 719.

This MUST be verified by a test: mock `get_upcoming_holidays` to return a known holiday list, call the system prompt builder, assert `## FERIADOS PROXIMOS` section appears in the output.

### REQ-3.2 — build_system_prompt() Produces Correct Holidays Section

Given `upcoming_holidays = [{"date": "2026-12-25", "name": "Navidad", "source": "library", "custom_hours": None}]`:

The result of `build_system_prompt(...)` MUST contain:
- The substring `## FERIADOS PROXIMOS`
- The substring `2026-12-25: Navidad`
- The substring `CERRADO`
- The substring `REGLA:`

Given `upcoming_holidays = [{"date": "2026-12-25", "name": "Navidad", "source": "library", "custom_hours": {"start": "09:00", "end": "13:00"}}]`:

The result MUST contain `HORARIO ESPECIAL 09:00–13:00`.

### REQ-3.3 — Empty List Does Not Inject Section

Given `upcoming_holidays = []` or `upcoming_holidays = None`:

The result MUST NOT contain `## FERIADOS PROXIMOS`.

---

## REQ-4 — Agent Answer Scenarios

### REQ-4.1 — Closed Holiday

**Given**: Tenant has `upcoming_holidays = [{"date": "2026-12-25", "name": "Navidad", "custom_hours": None}]` in the prompt.

**When**: Patient asks "¿Atienden el 25 de diciembre?"

**Then**: The agent MUST:
- Mention that the clinic is closed on that date.
- Offer an alternative date (the next business day).
- NOT attempt to call `check_availability` for December 25.

This scenario is verified by providing the system prompt to the LLM with a mocked conversation. The test asserts the response does not contain a time slot for December 25.

### REQ-4.2 — Special Hours Holiday

**Given**: Tenant has `upcoming_holidays = [{"date": "2026-05-01", "name": "Dia del Trabajador", "custom_hours": {"start": "09:00", "end": "13:00"}}]` in the prompt.

**When**: Patient asks "¿Qué horario tienen el 1 de mayo?"

**Then**: The agent MUST:
- Inform the patient that the clinic operates with special hours: 09:00–13:00.
- Offer to check availability within that range.

---

## REQ-5 — Frontend: ClinicsView Modal Section

### REQ-5.1 — Section Location and Behavior

The section MUST appear inside the Edit Clinic form (`ClinicsView.tsx`) between the "Horarios por dia" section and the submit buttons.

The section MUST be collapsed by default.

The section MUST only be visible when editing an existing clinic (`editingClinica !== null`). When creating a new clinic, the section MUST NOT render (no tenant_id yet to fetch holidays for).

### REQ-5.2 — Section Header

The header MUST display:
- An icon (CalendarX from lucide-react or equivalent)
- The label `t('clinics.holidays.section_title')` ("Feriados y Dias Especiales")
- A chevron icon that rotates on open/close
- A badge showing count of custom holidays for the tenant (fetched alongside the list)

### REQ-5.3 — Holiday List

On expand, the section MUST call `GET /admin/holidays?days=90` using the tenant's auth context (no extra clinic_id parameter — tenant_id is already in JWT).

The list MUST display:
- For each item: date formatted as `dd/MM/yyyy`, name, type badge (red "Cerrado" for closure, amber "Horario especial" for override_open), source badge (gray "Nacional" for source='library', blue "Custom" for source='custom').
- Delete button (X icon) for `source='custom'` items only. National holidays MUST NOT have a delete button.
- Edit button (pencil icon) for `source='custom'` items only.

If the list is empty: display `t('clinics.holidays.empty_message')`.

Loading state: show spinner while fetching.

Error state: show `t('clinics.holidays.fetch_error')` inline (not a toast, inline in the section).

### REQ-5.4 — Inline Add Form

Below the list, the section MUST render an inline "add" form with:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| date | `<input type="date">` | YES | HTML date picker, min = today |
| name | `<input type="text">` | YES | Placeholder: "Ej: Vacaciones de invierno" |
| holiday_type | `<select>` | YES | Options: "closure" (Cerrado) / "override_open" (Con horario especial) |
| custom_hours_start | `<input type="time">` | NO | Only visible when holiday_type = 'override_open' |
| custom_hours_end | `<input type="time">` | NO | Only visible when holiday_type = 'override_open' |
| is_recurring | `<input type="checkbox">` | NO | Default unchecked |

Submit button: `t('clinics.holidays.add_button')`. MUST be disabled while saving.

On success: clear form, reload holiday list, show inline success message for 2 seconds.

On 409 conflict: show `t('clinics.holidays.conflict_error')` inline.

### REQ-5.5 — Inline Edit

Clicking the edit icon on a custom holiday row MUST transform that row into an editable inline form (same fields as add, pre-filled). Canceling restores the row to read-only display. Saving calls `PUT /admin/holidays/{id}` and refreshes the list.

### REQ-5.6 — Delete Confirmation

Clicking delete on a custom holiday row MUST show a single inline confirmation prompt ("¿Eliminár este feriado?") with Confirmar / Cancelar buttons. On confirm: call `DELETE /admin/holidays/{id}` and refresh list.

### REQ-5.7 — Form Validation

- `date` MUST be a valid ISO date string (YYYY-MM-DD).
- `name` MUST NOT be empty (trimmed).
- If `holiday_type = 'override_open'`: both `custom_hours_start` and `custom_hours_end` MUST be set, and `start < end`. Show `t('holidays.invalidTimeRange')` if violated.
- Frontend validation MUST run before any API call.

---

## REQ-6 — Internationalization

All new string keys MUST be added to `es.json`, `en.json`, and `fr.json` before the component is implemented.

New keys (namespace `clinics.holidays.*`):

| Key | es | en | fr |
|-----|----|----|-----|
| `clinics.holidays.section_title` | "Feriados y Dias Especiales" | "Holidays & Special Days" | "Jours feries et jours speciaux" |
| `clinics.holidays.section_subtitle` | "El agente de IA no agenda turnos en dias cerrados" | "The AI agent won't schedule on closed days" | "L'agent IA ne planifie pas les jours fermes" |
| `clinics.holidays.empty_message` | "No hay feriados configurados para los proximos 90 dias" | "No holidays configured for the next 90 days" | "Aucun jour ferie configure pour les 90 prochains jours" |
| `clinics.holidays.fetch_error` | "Error al cargar feriados" | "Error loading holidays" | "Erreur lors du chargement des jours feries" |
| `clinics.holidays.add_button` | "Agregar" | "Add" | "Ajouter" |
| `clinics.holidays.add_form_title` | "Agregar feriado o dia especial" | "Add holiday or special day" | "Ajouter un jour ferie ou special" |
| `clinics.holidays.date_label` | "Fecha" | "Date" | "Date" |
| `clinics.holidays.name_label` | "Nombre" | "Name" | "Nom" |
| `clinics.holidays.type_label` | "Tipo" | "Type" | "Type" |
| `clinics.holidays.type_closure` | "Cerrado" | "Closed" | "Ferme" |
| `clinics.holidays.type_override_open` | "Con horario especial" | "Special hours" | "Heures speciales" |
| `clinics.holidays.is_recurring_label` | "Recurrente (cada ano)" | "Recurring (every year)" | "Recurrent (chaque annee)" |
| `clinics.holidays.conflict_error` | "Ya existe un feriado de ese tipo para esa fecha" | "A holiday of that type already exists for that date" | "Un jour ferie de ce type existe deja pour cette date" |
| `clinics.holidays.delete_confirm` | "Eliminar feriado?" | "Delete holiday?" | "Supprimer ce jour ferie?" |
| `clinics.holidays.source_national` | "Nacional" | "National" | "National" |
| `clinics.holidays.source_custom` | "Custom" | "Custom" | "Personnalise" |
| `clinics.holidays.custom_hours_label` | "Horario especial" | "Special hours" | "Heures speciales" |
| `clinics.holidays.add_success` | "Feriado agregado" | "Holiday added" | "Jour ferie ajoute" |
| `clinics.holidays.delete_success` | "Feriado eliminado" | "Holiday removed" | "Jour ferie supprime" |

---

## REQ-7 — Security and Tenant Isolation

### REQ-7.1

The frontend MUST NOT pass `clinic_id` or `tenant_id` as a query param to holiday endpoints. The backend derives `tenant_id` from the JWT token. This is already enforced by `verify_admin_token` in `admin_routes.py`.

### REQ-7.2

The frontend section MUST only render inside the Edit Clinic modal when `editingClinica` is non-null. It MUST NOT display holiday data from a previous editing session when the modal opens for a different clinic.

### REQ-7.3

On modal close, the holiday list state MUST be reset to empty (re-fetched on next open).

---

## REQ-8 — No Regressions

### REQ-8.1

`AgendaView.tsx`, `HolidayDetailModal.tsx`, `MobileAgenda.tsx` MUST NOT be modified.

### REQ-8.2

`holiday_service.py`, `buffer_task.py`, `admin_routes.py`, `models.py`, `main.py` MUST NOT be modified (they are already correct).

### REQ-8.3

Existing `holidays.*` i18n keys MUST NOT be removed or renamed (HolidayDetailModal depends on them).
