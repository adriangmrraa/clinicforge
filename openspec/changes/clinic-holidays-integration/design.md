# Design: Clinic Holidays Integration

**Change**: `clinic-holidays-integration`
**Project**: ClinicForge
**Status**: DESIGN

---

## 1. Investigation Results

### 1.1 Database Schema — COMPLETE

Confirmed via migrations and ORM:

**Migration 010** (`010_add_country_code_and_tenant_holidays.py`): Creates `tenant_holidays` with columns: `id`, `tenant_id`, `date`, `name`, `holiday_type` CHECK IN ('closure','override_open'), `is_recurring`, `created_at`. Adds indexes `idx_tenant_holidays_tenant_date` and `idx_tenant_holidays_recurring`.

**Migration 014** (`014_add_custom_holiday_hours.py`): Adds `custom_hours_start TIME`, `custom_hours_end TIME` (both nullable).

**ORM** (`models.py:1262`): `TenantHoliday` class is complete with all 9 columns.

**Conclusion**: No migration 031 needed. Schema is complete for the target feature set.

### 1.2 Backend Endpoints — COMPLETE

`admin_routes.py:2768–3025`:

| Method | Path | Status |
|--------|------|--------|
| GET | `/admin/holidays` | Complete — returns `{upcoming, custom}` |
| GET | `/admin/holidays/upcoming` | Complete — 30-day shortcut |
| POST | `/admin/holidays` | Complete — creates custom holiday |
| POST | `/admin/holidays/toggle` | Complete — toggles override_open |
| PUT | `/admin/holidays/{id}` | Complete — partial update, auto-nulls hours on type change |
| DELETE | `/admin/holidays/{id}` | Complete — tenant-scoped |

### 1.3 Agent Context Wiring — COMPLETE

**File**: `orchestrator_service/services/buffer_task.py`
**Lines**: 684–719

```
_upcoming_holidays = []                                          # line 685
from services.holiday_service import get_upcoming_holidays       # line 687
_upcoming_holidays = await get_upcoming_holidays(                 # line 689
    db.pool, tenant_id, days_ahead=30
)
...
upcoming_holidays=_upcoming_holidays,                            # line 719 (passed to build_system_prompt)
```

**File**: `orchestrator_service/main.py`
**Lines**: 6334–6347

```python
holidays_section = ""
if upcoming_holidays:
    hol_lines = []
    for h in upcoming_holidays[:7]:
        ch = h.get("custom_hours")
        if ch:
            hol_lines.append(f"• {h['date']}: {h['name']} — HORARIO ESPECIAL {ch['start']}–{ch['end']}")
        else:
            hol_lines.append(f"• {h['date']}: {h['name']} — CERRADO")
    holidays_section = "\n\n## FERIADOS PROXIMOS\n" + "\n".join(hol_lines)
    holidays_section += "\nREGLA: Si feriado CERRADO → informale al paciente y ofrecé el próximo día hábil. ..."
```

The section is injected into the final system prompt string. No code changes needed anywhere in the backend.

### 1.4 Frontend — MISSING

**ClinicsView.tsx**: The modal (lines 853–1091) has no holiday section. It contains (in order): name/phone, address/maps, consultation price, chairs, country_code (already labeled "para feriados"), system_prompt_template, bank section, derivation email, calendar_provider, working_hours. The country_code field is the natural cue that holidays are nearby.

**Existing holiday components**: `AgendaView.tsx` (calendar view with holiday dots), `HolidayDetailModal.tsx` (toggle/hours modal for AgendaView). These are independent and MUST NOT be modified.

---

## 2. Architecture Decisions

### 2.1 No New Migration

Schema is complete. Migration 031 is deferred unless a future field (`notes`) is explicitly required. This avoids a pointless migration that does nothing on already-migrated databases.

### 2.2 No New Component — Inline in ClinicsView

The holiday section will be implemented as a collapsible block directly within `ClinicsView.tsx`, not as a separate imported component. Rationale:
- The section has its own local state (list, add form, edit row index, loading state).
- Extracting it to a component would require passing the tenant's auth context and a refresh callback anyway, adding indirection without benefit.
- Following the existing pattern: working_hours section is also inline in ClinicsView.

If the section grows complex in a future iteration, extraction to `<ClinicHolidaysSection>` is the natural refactor path.

### 2.3 State Design

New state variables added to `ClinicsView.tsx`:

```typescript
// Section toggle
const [holidaysSectionOpen, setHolidaysSectionOpen] = useState(false);

// Fetched data
const [holidayList, setHolidayList] = useState<HolidayItem[]>([]);
const [holidaysLoading, setHolidaysLoading] = useState(false);
const [holidaysFetchError, setHolidaysFetchError] = useState<string | null>(null);

// Add form
const [newHoliday, setNewHoliday] = useState<NewHolidayForm>({
  date: '',
  name: '',
  holiday_type: 'closure',
  custom_hours_start: '',
  custom_hours_end: '',
  is_recurring: false,
});
const [addingSaving, setAddingSaving] = useState(false);
const [addError, setAddError] = useState<string | null>(null);
const [addSuccess, setAddSuccess] = useState(false);

// Inline edit
const [editingHolidayId, setEditingHolidayId] = useState<number | null>(null);
const [editForm, setEditForm] = useState<Partial<NewHolidayForm>>({});

// Delete confirm
const [deletingHolidayId, setDeletingHolidayId] = useState<number | null>(null);
```

### 2.4 Type Definition

```typescript
interface HolidayItem {
  id?: number;              // undefined for library holidays (no DB row)
  date: string;             // ISO YYYY-MM-DD
  name: string;
  holiday_type: 'closure' | 'override_open';
  source: 'library' | 'custom';
  is_recurring?: boolean;
  custom_hours?: { start: string; end: string } | null;
  custom_hours_start?: string | null;
  custom_hours_end?: string | null;
}

interface NewHolidayForm {
  date: string;
  name: string;
  holiday_type: 'closure' | 'override_open';
  custom_hours_start: string;
  custom_hours_end: string;
  is_recurring: boolean;
}
```

### 2.5 Fetch Strategy

The holiday list is fetched lazily — only when the section is expanded, and only for existing clinics (`editingClinica !== null`). On modal close, `holidaysSectionOpen` resets to `false` and `holidayList` resets to `[]`.

```typescript
useEffect(() => {
  if (!holidaysSectionOpen || !editingClinica) {
    setHolidayList([]);
    return;
  }
  fetchHolidays();
}, [holidaysSectionOpen, editingClinica]);

const fetchHolidays = async () => {
  setHolidaysLoading(true);
  setHolidaysFetchError(null);
  try {
    const res = await api.get('/admin/holidays', { params: { days: 90 } });
    setHolidayList(res.data?.upcoming || []);
  } catch {
    setHolidaysFetchError(t('clinics.holidays.fetch_error'));
  } finally {
    setHolidaysLoading(false);
  }
};
```

### 2.6 Add Form Submission

```typescript
const handleAddHoliday = async (e: React.FormEvent) => {
  e.preventDefault();
  // Validate
  if (!newHoliday.date || !newHoliday.name.trim()) return;
  if (newHoliday.holiday_type === 'override_open') {
    if (!newHoliday.custom_hours_start || !newHoliday.custom_hours_end) {
      setAddError(t('holidays.invalidTimeRange'));
      return;
    }
    if (newHoliday.custom_hours_start >= newHoliday.custom_hours_end) {
      setAddError(t('holidays.invalidTimeRange'));
      return;
    }
  }
  setAddingSaving(true);
  setAddError(null);
  try {
    await api.post('/admin/holidays', {
      date: newHoliday.date,
      name: newHoliday.name.trim(),
      holiday_type: newHoliday.holiday_type,
      is_recurring: newHoliday.is_recurring,
      custom_hours_start: newHoliday.holiday_type === 'override_open' ? newHoliday.custom_hours_start : null,
      custom_hours_end: newHoliday.holiday_type === 'override_open' ? newHoliday.custom_hours_end : null,
    });
    setNewHoliday({ date: '', name: '', holiday_type: 'closure', custom_hours_start: '', custom_hours_end: '', is_recurring: false });
    setAddSuccess(true);
    setTimeout(() => setAddSuccess(false), 2000);
    fetchHolidays();
  } catch (err: any) {
    if (err.response?.status === 409) {
      setAddError(t('clinics.holidays.conflict_error'));
    } else {
      setAddError(t('clinics.holidays.fetch_error'));
    }
  } finally {
    setAddingSaving(false);
  }
};
```

### 2.7 Delete Flow

```typescript
const handleDeleteHoliday = async (id: number) => {
  try {
    await api.delete(`/admin/holidays/${id}`);
    setDeletingHolidayId(null);
    fetchHolidays();
  } catch {
    // inline error (rare)
  }
};
```

### 2.8 Modal Reset on Close

```typescript
// In setIsModalOpen(false) handler, also reset:
setHolidaysSectionOpen(false);
setHolidayList([]);
setEditingHolidayId(null);
setDeletingHolidayId(null);
setAddError(null);
setAddSuccess(false);
```

### 2.9 Icon Choice

Use `CalendarX` from lucide-react for the section header icon (represents closed days). Use `CalendarCheck` for override_open display. Use `ChevronDown`/`ChevronUp` for collapse toggle. No new icon library needed — lucide-react is already a dependency.

If `CalendarX` is not available in the installed lucide-react version, fall back to `CalendarOff` or `Calendar`.

---

## 3. UI Layout Sketch

```
[ CalendarX ] Feriados y Dias Especiales  (3 custom)  [ ChevronDown ]
─────────────────────────────────────────────────────────────────────
  Loading... (spinner)
  ─ or ─
  25/12/2026  Navidad             [Nacional] [Cerrado]
  01/01/2027  Ano Nuevo           [Nacional] [Cerrado]
  07/07/2026  Vacaciones invierno [Custom]   [Cerrado]  [ edit ] [ X ]
  ─────────
  + Agregar feriado o dia especial
  [ Fecha: ____-__-__ ] [ Nombre: ____________ ] [ Tipo: v ]
  [ ] Recurrente (cada año)
  [     Agregar     ]
```

Collapsed (default):
```
[ CalendarX ] Feriados y Dias Especiales  (3 custom)  [ ChevronDown ]
```

---

## 4. Styling

Follows the existing ClinicsView modal dark theme:
- Section wrapper: `border-t border-white/[0.06] pt-4 mt-4`
- Header: `flex items-center justify-between cursor-pointer py-2 hover:bg-white/[0.02] rounded-lg px-1`
- Holiday row: `flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-white/[0.02]`
- Date: `text-sm font-mono text-white/60 w-24 shrink-0`
- Name: `text-sm text-white flex-1`
- Type badge (closure): `px-1.5 py-0.5 rounded text-[10px] font-semibold bg-red-500/10 text-red-400`
- Type badge (override_open): `px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-400`
- Source badge (library): `px-1.5 py-0.5 rounded text-[10px] font-semibold bg-white/[0.06] text-white/40`
- Source badge (custom): `px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-500/10 text-blue-400`
- Add form: `bg-white/[0.02] p-3 rounded-xl border border-white/[0.06] space-y-3 mt-3`
- Add form inputs: same as modal inputs (`bg-white/[0.04] border border-white/[0.08] rounded-lg text-white`)

---

## 5. Test Architecture

### 5.1 File

`tests/test_clinic_holidays_integration.py`

### 5.2 Test Classes

```
TestHolidayEndpointContract
  test_get_holidays_requires_auth
  test_get_holidays_returns_correct_structure
  test_post_holiday_creates_closure
  test_post_holiday_creates_override_open
  test_post_holiday_409_on_duplicate
  test_put_holiday_updates_name
  test_put_holiday_clears_hours_on_type_change_to_closure
  test_delete_holiday_removes_record
  test_delete_holiday_404_wrong_tenant

TestAgentPromptInjection
  test_build_system_prompt_includes_holidays_section
  test_build_system_prompt_custom_hours_format
  test_build_system_prompt_empty_list_no_section
  test_build_system_prompt_limits_to_7_holidays

TestBufferTaskHolidayWiring
  test_buffer_task_calls_get_upcoming_holidays
  test_buffer_task_passes_holidays_to_build_system_prompt
  test_buffer_task_handles_holiday_service_exception_gracefully
```

### 5.3 Fixtures

```python
@pytest.fixture
def mock_tenant():
    return {"id": 1, "tenant_id": 1, "email": "test@test.com"}

@pytest.fixture
def sample_holidays():
    return [
        {"date": "2026-12-25", "name": "Navidad", "source": "library",
         "holiday_type": "closure", "custom_hours": None},
        {"date": "2026-01-01", "name": "Año Nuevo", "source": "library",
         "holiday_type": "closure", "custom_hours": None},
    ]

@pytest.fixture
def sample_holidays_with_custom_hours():
    return [
        {"date": "2026-05-01", "name": "Día del Trabajador", "source": "library",
         "holiday_type": "override_open",
         "custom_hours": {"start": "09:00", "end": "13:00"}},
    ]
```

### 5.4 Key Assertion Pattern for Prompt Tests

```python
def test_build_system_prompt_includes_holidays_section(sample_holidays):
    result = build_system_prompt(
        clinic_name="Test",
        current_time="Monday 10:00",
        upcoming_holidays=sample_holidays,
        # ... other required params with defaults
    )
    assert "## FERIADOS PROXIMOS" in result
    assert "2026-12-25: Navidad" in result
    assert "CERRADO" in result
    assert "REGLA:" in result
```

---

## 6. Security Design

### 6.1 Tenant Isolation

Frontend never passes tenant_id or clinic_id to holiday endpoints. The `verify_admin_token` dependency in admin_routes.py extracts tenant_id from the JWT. Since the modal only opens for clinics belonging to the authenticated user's tenant, the holiday list will always be scoped to the correct tenant.

### 6.2 No New Auth Surface

No new endpoints. No new auth dependencies. The existing `verify_admin_token` is reused on all holiday endpoints.

---

## 7. Performance

- Holiday list fetch: single query to `tenant_holidays` + Python `holidays` library lookup for 90 days. Expected latency < 100ms.
- Fetch is lazy (only on section expand). The modal form submit (`handleSubmit`) does NOT await holiday loading — holidays are loaded independently.
- List is capped at 90 days / ~15 entries in the UI display. No pagination needed.

---

## 8. i18n Integration

New keys go into the `clinics.holidays` namespace (not the top-level `holidays` namespace already used by `HolidayDetailModal`). This avoids any conflict with existing keys.

Existing keys at `holidays.*` (top-level) MUST remain untouched.

New keys at `clinics.holidays.*` follow the convention of other `clinics.*` keys in the same locale files.
