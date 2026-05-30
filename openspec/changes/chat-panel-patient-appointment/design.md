# Technical Design: Chat Panel -- Patient & Appointment Management

**Change:** chat-panel-patient-appointment
**Author:** SDD Design Agent
**Date:** 2026-04-13
**Status:** Draft

---

## 1. Architecture Decisions

### 1.1 Component Hierarchy

```
ChatsView (existing, 1748 lines)
  |-- CreatePatientModal (new)
  |     |-- PatientForm (inline, not extracted)
  |     +-- Insurance provider dropdown (lazy-loaded)
  |
  |-- ScheduleAppointmentModal (new)
  |     |-- Step1: PatientQuickCreate (conditional, only if no patient_id)
  |     |-- Step2: AppointmentWizard
  |     |     |-- ProfessionalSelector
  |     |     |-- TreatmentTypeSelector (filters by professional)
  |     |     |-- DateTimePicker
  |     |     |-- CollisionWarning
  |     |     +-- MultiSessionConfigurator (optional)
  |     +-- SenaDisplay (read-only, from tenant config)
  |
  +-- Side Panel (existing, lines 1516-1717, modified)
        |-- "Crear paciente" button -> opens CreatePatientModal (was: navigate away)
        +-- "Agendar turno" button (new)
```

### 1.2 State Management

**Decision: Modal state lives in ChatsView, data flows down via props.**

Rationale: The modals need access to `selectedSession`, `patientContext`, and `displayPhone`/`displayName` which already live in ChatsView. Lifting modal open/close state into ChatsView keeps it colocated with the data it depends on. No global state or context needed.

```
ChatsView state additions:
  showCreatePatientModal: boolean
  showScheduleModal: boolean

ChatsView passes down:
  CreatePatientModal:  phone, displayName, tenantId, onCreated(patient), onClose
  ScheduleAppointmentModal: patientId (nullable), phone, displayName, tenantId, onScheduled, onClose
```

### 1.3 API Call Strategy

| Data | When to Fetch | Cache? | Why |
|------|---------------|--------|-----|
| Professionals | On ScheduleAppointmentModal mount | Session-level (stale-while-revalidate) | List changes rarely, needed for dropdown |
| Treatment types | On ScheduleAppointmentModal mount | Session-level | Same rationale |
| Insurance providers | On CreatePatientModal mount | Session-level | Dropdown options, stable data |
| Collision check | On datetime change, debounced 500ms | No cache | Real-time accuracy required |
| Consultation price | On tenant load (already in context) | Already cached | Needed for sena display |
| Patient context | After patient creation, after appointment creation | Refresh (invalidate) | Side panel must reflect new data |

**Error handling strategy:** All API calls wrapped in try/catch with toast notification. Modals stay open on error (user can retry). Only close on confirmed success.

---

## 2. Backend Changes

### 2.1 ensure_patient_exists() Modification

**File:** `orchestrator_service/db.py`, line 225

**Current signature:**
```python
async def ensure_patient_exists(
    self,
    phone_number: Optional[str],
    tenant_id: int,
    first_name: str = 'Visitante',
    status: str = 'guest',
    external_id: Optional[dict] = None
)
```

**New signature:**
```python
async def ensure_patient_exists(
    self,
    phone_number: Optional[str],
    tenant_id: int,
    first_name: str = 'Visitante',
    status: str = 'guest',
    external_id: Optional[dict] = None,
    create_if_missing: bool = True,       # <-- NEW
)
```

**Behavior change:** When `create_if_missing=False`, the method returns `None` instead of executing the INSERT block (section 3, lines 261-280). Sections 1 (lookup by external_id) and 2 (lookup by phone_number) remain unchanged.

```python
# Line 261 - wrap existing insert in guard:
if not create_if_missing:
    return None

# 3. Si no existe, crear nuevo (Lead o Paciente segun status)
query_insert = """..."""
```

**Call site changes (4 sites in live files):**

| File | Line | Current Call | Change |
|------|------|-------------|--------|
| `routes/chat_webhooks.py` | 213 | `await db.ensure_patient_exists(phone_number=..., tenant_id=..., first_name=...)` | Add `create_if_missing=False`. Only runs on referral messages (Meta Ads attribution). Patient creation is DEFERRED to admin action or AI booking. |
| `main.py` | 4001 | `await db.ensure_patient_exists(phone, tenant_id, first_name=...)` | Add `create_if_missing=False`. This is in `triage_urgency` tool -- it should NOT auto-create patients. If patient doesn't exist, triage still works (urgency is returned to the AI, just not persisted). |
| `main.py` | 9717 | `await db.ensure_patient_exists(req.final_phone, tenant_id, req.final_name)` | **KEEP `create_if_missing=True` (default)**. This is the WhatsApp message processing in `book_appointment` / AI chat endpoint. AI-initiated booking MUST still create patients. |
| `fix_orphaned_chats.py` | 26 | `await db.ensure_patient_exists(phone)` | One-time script, irrelevant. No change. |

**NULL patient_id cascade analysis:**

When `create_if_missing=False` returns `None`, the following queries that currently assume `patient_id` exists need adjustment:

1. **`chat_webhooks.py` line 213 context** -- The `patient_row` is used for Meta Ads attribution (lines 219-260). If `patient_row is None`, skip the attribution block entirely (it's already inside a try/except). The conversation is still created (line 196-208) regardless -- `create_or_get_conversation()` does NOT depend on patients table.

2. **`main.py` line 4001 context** -- `patient_row` is used to persist urgency_level. If None, skip the `UPDATE patients SET urgency_level` query. The triage tool still returns the urgency assessment to the AI -- it just doesn't persist it to a patient record. When the patient IS created later (via modal or AI booking), the next triage call will persist it.

3. **Chat summary endpoint (`routes/chat_api.py` line 59)** -- Currently does NOT join patients table. No change needed. Sessions are built from `chat_conversations` only.

4. **Patient context endpoint (`admin_routes.py` line 465)** -- Already handles `patient=None` case (lines 586-592), returns `{"patient": None, "is_guest": True}`. No change needed.

### 2.2 POST /admin/patients Enhancement

**File:** `orchestrator_service/admin_routes.py`, line 4248

Three additions to the existing `create_patient` endpoint:

#### 2.2.1 PATIENT_CREATED Socket Emit

After the successful INSERT (line 4276), emit a new socket event:

```python
# After: return {"id": row["id"]}
# Replace with:
patient_id = row["id"]

# Emit PATIENT_CREATED for real-time UI updates
try:
    if hasattr(request.app.state, "emit_appointment_event"):
        await request.app.state.emit_appointment_event("PATIENT_CREATED", {
            "patient_id": patient_id,
            "tenant_id": tenant_id,
            "phone_number": (p.phone_number or "").strip(),
            "first_name": (p.first_name or "").strip(),
            "last_name": (p.last_name or "").strip(),
        })
except Exception as emit_err:
    logger.warning(f"Socket emit PATIENT_CREATED failed: {emit_err}")

return {"id": patient_id}
```

**Requires:** Add `request: Request` parameter to the endpoint signature (currently missing -- needed for `request.app.state`).

#### 2.2.2 chat_conversations.patient_id Backfill

**Problem:** `chat_conversations` table has NO `patient_id` column (confirmed in `models.py` lines 161-194). The proposal mentions backfilling it, but the column doesn't exist.

**Decision: Do NOT add patient_id to chat_conversations.**

Rationale:
- The chat summary endpoint resolves patient identity by `external_user_id` (phone/platform ID) matched against `patients.phone_number` or `patients.external_ids`.
- Adding a FK would require a migration, backfill script, and maintaining sync on every patient merge/delete.
- The existing phone-based lookup in `get_patient_clinical_context` (line 465) already works for both leads (returns null) and patients (returns full context).

**Instead:** After patient creation, update the `sessions` list in ChatsView by matching phone number. The `PATIENT_CREATED` socket event carries `phone_number`, and the frontend handler sets `patient_id` on the matching session.

#### 2.2.3 Response Enhancement

Return the full patient object (not just `{id}`) so the modal can update parent state without a second fetch:

```python
return {
    "id": patient_id,
    "first_name": (p.first_name or "").strip(),
    "last_name": (p.last_name or "").strip(),
    "phone_number": (p.phone_number or "").strip(),
    "status": "active",
}
```

### 2.3 New/Modified Endpoints

#### 2.3.1 GET /admin/insurance-providers -- Already Exists

**File:** `orchestrator_service/admin_routes.py`, line 8426
**Endpoint:** `GET /admin/insurance-providers`
**Auth:** `Depends(verify_admin_token)`
**Returns:** Full list with `id`, `provider_name`, `is_active`, `sort_order`, etc.

**No changes needed.** Frontend will call this directly. Filter `is_active=true` client-side for the dropdown.

#### 2.3.2 GET /admin/patients/phone/{phone}/context -- Modification

**File:** `orchestrator_service/admin_routes.py`, line 465

**Current behavior when patient=None (line 586):**
```python
return {
    "patient": None,
    "last_appointment": None,
    "upcoming_appointment": None,
    "treatment_plan": None,
    "is_guest": True,
}
```

**Enhancement:** Add `is_lead: True` flag to distinguish "no patient record at all" from "guest patient record exists":

```python
return {
    "patient": None,
    "last_appointment": None,
    "upcoming_appointment": None,
    "treatment_plan": None,
    "is_guest": True,
    "is_lead": True,  # <-- NEW: no patient record exists
}
```

And in the patient-found branch (line 574):
```python
return {
    "patient": dict(patient),
    "last_appointment": dict(last_apt) if last_apt else None,
    "upcoming_appointment": dict(upcoming_apt) if upcoming_apt else None,
    "treatment_plan": ...,
    "diagnosis": ...,
    "is_guest": patient["status"] == "guest",
    "is_lead": False,  # <-- NEW
}
```

This lets the frontend decide: `is_lead=True` -> show "Crear paciente" button. `is_guest=True, is_lead=False` -> show "Completar ficha" (edit mode). `is_guest=False` -> show "Ver ficha".

#### 2.3.3 GET /admin/tenants/current -- No New Endpoint Needed

The `consultation_price` (for sena calculation) is already available from the tenant config. The frontend can fetch it via `GET /admin/settings/clinic` or from the existing auth context. No new endpoint.

#### 2.3.4 Treatment Types with Duration -- Already Exists

`GET /admin/treatment-types` (line 9409) already returns `default_duration`, `professional_ids`, `price`. No changes needed.

---

## 3. Frontend Architecture

### 3.1 CreatePatientModal Component

**File:** `frontend_react/src/components/modals/CreatePatientModal.tsx` (new)

#### Props Interface

```typescript
interface CreatePatientModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (patient: CreatedPatient) => void;
  // Pre-fill data from chat session
  prefillPhone: string;
  prefillName: string;  // from WhatsApp display_name
  tenantId: number;
  // Edit mode: existing guest patient
  editPatientId?: number;
  editPatientData?: Partial<PatientFormData>;
}

interface CreatedPatient {
  id: number;
  first_name: string;
  last_name: string;
  phone_number: string;
  status: string;
}

interface PatientFormData {
  first_name: string;
  last_name: string;
  phone_number: string;
  email: string;
  dni: string;
  insurance: string;    // free text or selected from dropdown
  city: string;
  birth_date: string;   // ISO date string
}
```

#### Internal State

```typescript
const [form, setForm] = useState<PatientFormData>(initialFromProps);
const [insuranceProviders, setInsuranceProviders] = useState<InsuranceProvider[]>([]);
const [isSubmitting, setIsSubmitting] = useState(false);
const [errors, setErrors] = useState<Partial<Record<keyof PatientFormData, string>>>({});
```

#### API Calls

1. **On mount:** `GET /admin/insurance-providers` -> populate dropdown (filter `is_active=true`).
2. **On submit (create mode):** `POST /admin/patients` with `PatientFormData`.
3. **On submit (edit mode):** `PUT /admin/patients/${editPatientId}` with changed fields only.

#### Name Split Logic

`prefillName` from WhatsApp is a single string (e.g., "Maria Garcia"). Split heuristic:

```typescript
function splitDisplayName(displayName: string): { first: string; last: string } {
  const parts = displayName.trim().split(/\s+/);
  if (parts.length === 0) return { first: '', last: '' };
  if (parts.length === 1) return { first: parts[0], last: '' };
  return { first: parts[0], last: parts.slice(1).join(' ') };
}
```

User can edit both fields -- this is just a convenience pre-fill.

#### Validation

- `first_name`: required, min 2 chars
- `phone_number`: required, must match `/^\+?\d{7,15}$/`
- `email`: optional, basic format check
- `dni`: optional, no format enforced (varies by country)
- `birth_date`: optional, must be in the past

#### Event Flow

```
User clicks "Crear paciente" in side panel
  -> setShowCreatePatientModal(true)
  -> Modal opens with prefilled phone + split name
  -> User fills/edits fields, submits
  -> POST /admin/patients
  -> On 201:
     1. onCreated(patient) called
     2. ChatsView updates patientContext (refetch via fetchPatientContext)
     3. ChatsView updates sessions list (set patient_id on matching session)
     4. Modal closes
  -> On 409 (duplicate phone):
     Show error inline: "Ya existe un paciente con ese telefono"
     Offer "Ver paciente existente" link
  -> On network error:
     Show toast, modal stays open
```

### 3.2 ScheduleAppointmentModal Component

**File:** `frontend_react/src/components/modals/ScheduleAppointmentModal.tsx` (new)

#### Props Interface

```typescript
interface ScheduleAppointmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onScheduled: (appointment: CreatedAppointment) => void;
  // Patient context (nullable for leads)
  patientId: number | null;
  patientName: string;
  phone: string;
  tenantId: number;
  consultationPrice: number | null;  // from tenant config, for sena display
}

interface CreatedAppointment {
  id: string;
  patient_id: number;
  professional_id: number;
  appointment_datetime: string;
  appointment_type: string;
  duration_minutes: number;
}
```

#### 2-Step Wizard State Machine

```typescript
type WizardStep = 'patient' | 'appointment';

const [step, setStep] = useState<WizardStep>(
  patientId ? 'appointment' : 'patient'  // skip step 1 if patient exists
);
const [resolvedPatientId, setResolvedPatientId] = useState<number | null>(patientId);
```

**Step transitions:**

```
                      patientId !== null
Modal opens ──────────────────────────────────> Step 2 (appointment)
     |
     | patientId === null
     v
Step 1 (patient)
     |
     | POST /admin/patients -> success
     v
Step 2 (appointment)
     |
     | POST /admin/appointments -> success
     v
Close modal, call onScheduled()
```

Step 1 embeds a SIMPLIFIED patient form (just first_name, last_name, phone -- not the full CreatePatientModal). The idea: we need a patient_id to book, so create one quickly.

#### Step 2: Appointment Form State

```typescript
interface AppointmentFormState {
  professional_id: number | null;
  treatment_type_code: string;
  appointment_datetime: string;  // ISO string
  duration_minutes: number;
  notes: string;
  // Multi-session
  multiSessionEnabled: boolean;
  multiSessionCount: number;       // 2-12
  multiSessionIntervalDays: number; // 7, 14, 21, 28
}

const [professionals, setProfessionals] = useState<Professional[]>([]);
const [treatmentTypes, setTreatmentTypes] = useState<TreatmentType[]>([]);
const [collision, setCollision] = useState<CollisionResult | null>(null);
const [isCheckingCollision, setIsCheckingCollision] = useState(false);
```

#### Collision Check Debounce Strategy

```typescript
const checkCollisionDebounced = useMemo(
  () => debounce(async (professionalId: number, datetime: string, duration: number) => {
    if (!professionalId || !datetime) return;
    setIsCheckingCollision(true);
    try {
      const res = await api.get('/admin/appointments/check-collisions', {
        params: {
          professional_id: professionalId,
          datetime_str: datetime,
          duration_minutes: duration,
        },
      });
      setCollision(res.data);
    } catch {
      setCollision(null); // fail open -- let the server reject on submit
    } finally {
      setIsCheckingCollision(false);
    }
  }, 500),
  []
);
```

Trigger: whenever `professional_id`, `appointment_datetime`, or `duration_minutes` changes.

#### Treatment Type -> Professional Filtering

When user selects a treatment type that has `professional_ids` assigned (non-empty array), filter the professional dropdown to only show those professionals. If `professional_ids` is empty, show all active professionals (backward compat rule from CLAUDE.md).

```typescript
const filteredProfessionals = useMemo(() => {
  if (!selectedTreatmentType?.professional_ids?.length) return professionals;
  return professionals.filter(p => selectedTreatmentType.professional_ids.includes(p.id));
}, [selectedTreatmentType, professionals]);
```

When user selects professional FIRST, filter treatment types to those the professional can perform:
```typescript
const filteredTreatments = useMemo(() => {
  if (!form.professional_id) return treatmentTypes;
  return treatmentTypes.filter(t =>
    !t.professional_ids?.length || t.professional_ids.includes(form.professional_id!)
  );
}, [form.professional_id, treatmentTypes]);
```

#### Multi-Session Flow

When `multiSessionEnabled=true`:

1. User configures: count (2-12) and interval (weekly/biweekly/triweekly/monthly).
2. Preview shows all N dates with collision status for each.
3. On submit: sequential POST `/admin/appointments` for each session. If any fails (collision), report which ones succeeded and which failed. Do NOT rollback successful ones.

```typescript
interface MultiSessionResult {
  scheduled: CreatedAppointment[];
  failed: { index: number; datetime: string; reason: string }[];
}
```

UI shows a summary after all attempts complete.

#### Sena Display Logic

Read-only display below the form:

```typescript
// consultation_price comes from props (tenant config)
// sena = 50% of consultation_price (clinic convention)
const senaAmount = consultationPrice ? consultationPrice * 0.5 : null;

{senaAmount && (
  <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
    <p className="text-xs text-amber-400">
      Sena requerida: ${senaAmount.toLocaleString('es-AR')}
      <span className="text-white/40 ml-1">(50% de ${consultationPrice})</span>
    </p>
  </div>
)}
```

### 3.3 ChatsView Integration

**File:** `frontend_react/src/views/ChatsView.tsx`

#### New State Variables

```typescript
// After existing state declarations (~line 110)
const [showCreatePatientModal, setShowCreatePatientModal] = useState(false);
const [showScheduleModal, setShowScheduleModal] = useState(false);
```

#### Button Conditions in Side Panel

Replace the existing "Crear paciente" navigate button (lines 1616-1625) with conditional rendering:

```typescript
{/* Three states based on patientContext */}
{patientContext?.is_lead ? (
  // State A: Pure lead (no patient record)
  <div className="flex gap-2">
    <button onClick={() => setShowCreatePatientModal(true)}
      className="flex-1 py-2 px-3 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1.5">
      <User size={12} /> Crear paciente
    </button>
    <button onClick={() => setShowScheduleModal(true)}
      className="flex-1 py-2 px-3 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/20 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1.5"
      title="Agendar turno (creara paciente automaticamente)">
      <Calendar size={12} /> Agendar turno
    </button>
  </div>
) : patientContext?.is_guest ? (
  // State B: Guest patient (auto-created, incomplete data)
  <div className="flex gap-2">
    <button onClick={() => setShowCreatePatientModal(true)}
      className="flex-1 py-2 px-3 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/20 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1.5">
      <User size={12} /> Completar ficha
    </button>
    <button onClick={() => setShowScheduleModal(true)}
      className="flex-1 py-2 px-3 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/20 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1.5">
      <Calendar size={12} /> Agendar turno
    </button>
  </div>
) : (
  // State C: Full patient (active status)
  <div className="flex gap-2">
    <button onClick={() => navigate(`/pacientes/${patientContext?.patient?.id || selectedSession?.patient_id}`)}
      className="flex-1 py-2 px-3 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/20 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1.5">
      <User size={12} /> Ver ficha
    </button>
    <button onClick={() => setShowScheduleModal(true)}
      className="flex-1 py-2 px-3 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/20 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1.5">
      <Calendar size={12} /> Agendar turno
    </button>
  </div>
)}
```

#### Socket Event Handlers

Add to existing socket setup block (~line 328):

```typescript
// NEW: Patient created (from any admin user in the same tenant)
socketRef.current.on('PATIENT_CREATED', (data: {
  patient_id: number;
  tenant_id: number;
  phone_number: string;
  first_name: string;
  last_name: string;
}) => {
  // Update sessions list: mark matching session with patient_id
  setSessions(prev => prev.map(s =>
    s.phone_number === data.phone_number ||
    s.phone_number?.replace(/\D/g, '') === data.phone_number?.replace(/\D/g, '')
      ? { ...s, patient_id: data.patient_id, patient_name: `${data.first_name} ${data.last_name}`.trim() }
      : s
  ));

  // Refresh context if currently viewing this patient's chat
  const currentPhone = selectedSessionRef.current?.phone_number ||
    selectedChatwootRef.current?.external_user_id;
  if (currentPhone?.replace(/\D/g, '') === data.phone_number?.replace(/\D/g, '')) {
    fetchPatientContext(data.phone_number, data.tenant_id);
  }
});
```

#### Callback Handlers for Modals

```typescript
const handlePatientCreated = useCallback((patient: CreatedPatient) => {
  setShowCreatePatientModal(false);
  // Refresh side panel context
  const phone = selectedSession?.phone_number || selectedChatwoot?.external_user_id;
  if (phone) fetchPatientContext(phone);
  // Toast
  setShowToast({
    id: Date.now().toString(),
    type: 'success',
    title: 'Paciente creado',
    message: `${patient.first_name} ${patient.last_name} registrado correctamente`,
  });
}, [selectedSession, selectedChatwoot]);

const handleAppointmentScheduled = useCallback((appointment: CreatedAppointment) => {
  setShowScheduleModal(false);
  // Context refresh happens via NEW_APPOINTMENT socket event (already wired, line 355)
  // Just show toast
  setShowToast({
    id: Date.now().toString(),
    type: 'success',
    title: 'Turno agendado',
    message: `Turno confirmado para ${new Date(appointment.appointment_datetime).toLocaleString('es-AR')}`,
  });
}, []);
```

#### Modal Rendering (at end of JSX, before closing fragment)

```tsx
{/* Patient & Appointment Modals */}
<CreatePatientModal
  isOpen={showCreatePatientModal}
  onClose={() => setShowCreatePatientModal(false)}
  onCreated={handlePatientCreated}
  prefillPhone={displayPhone}
  prefillName={displayName !== displayPhone ? displayName : ''}
  tenantId={selectedSession?.tenant_id || selectedChatwoot?.tenant_id || 0}
  editPatientId={patientContext?.is_guest && !patientContext?.is_lead
    ? patientContext?.patient?.id
    : undefined}
  editPatientData={patientContext?.is_guest && !patientContext?.is_lead
    ? {
        first_name: patientContext.patient?.first_name || '',
        last_name: patientContext.patient?.last_name || '',
        phone_number: displayPhone,
      }
    : undefined}
/>

<ScheduleAppointmentModal
  isOpen={showScheduleModal}
  onClose={() => setShowScheduleModal(false)}
  onScheduled={handleAppointmentScheduled}
  patientId={patientContext?.patient?.id || null}
  patientName={displayName}
  phone={displayPhone}
  tenantId={selectedSession?.tenant_id || selectedChatwoot?.tenant_id || 0}
  consultationPrice={null}  // TODO: wire from tenant settings
/>
```

---

## 4. Data Flow Diagrams

### 4.1 Lead -> Patient Conversion Flow

```
WhatsApp message arrives
    |
    v
chat_webhooks.py: create_or_get_conversation()
    |
    | create_if_missing=False (NEW)
    v
db.ensure_patient_exists() returns None
    |
    v
chat_conversations row created (no patient_id column, external_user_id = phone)
    |
    v
Frontend: ChatsView loads sessions via GET /admin/chats/summary
    |
    v
User selects conversation, side panel calls GET /admin/patients/phone/{phone}/context
    |
    v
Context returns { patient: null, is_lead: true }
    |
    v
Side panel shows "Crear paciente" button
    |
    v
User clicks -> CreatePatientModal opens (prefilled phone + WhatsApp name)
    |
    v
User fills form -> POST /admin/patients
    |
    v
Backend: INSERT into patients, emit PATIENT_CREATED via Socket.IO
    |
    v
Frontend: PATIENT_CREATED handler updates sessions list + refreshes context
    |
    v
Side panel now shows patient info + "Agendar turno" button
```

### 4.2 Appointment Scheduling Flow

```
User clicks "Agendar turno" in side panel
    |
    +--[patientId exists]--> Step 2 directly
    |
    +--[patientId null]----> Step 1: quick patient create
    |                            |
    |                            v
    |                        POST /admin/patients
    |                            |
    |                            v
    |                        resolvedPatientId set
    |                            |
    +<---------------------------+
    |
    v
Step 2: Appointment wizard
    |
    | Parallel fetches on mount:
    |   GET /admin/professionals
    |   GET /admin/treatment-types
    |
    v
User selects professional + treatment + datetime
    |
    | onChange debounced 500ms:
    v
GET /admin/appointments/check-collisions
    |
    +--[has_collisions=true]--> Show warning, disable submit
    |
    +--[has_collisions=false]--> Enable submit
    |
    v
User clicks "Confirmar turno"
    |
    v
POST /admin/appointments { patient_id, professional_id, datetime, ... }
    |
    v
Backend: INSERT appointment, emit NEW_APPOINTMENT via Socket.IO
    |
    v
Frontend: NEW_APPOINTMENT handler (already exists, line 355) refreshes context
    |
    v
Modal closes, toast shown
```

### 4.3 Multi-Session Scheduling Flow

```
User enables "Sesiones multiples" toggle in Step 2
    |
    v
Configurator appears: count (2-12) + interval dropdown
    |
    v
Preview panel shows N date slots with individual collision checks
    | (batch: N parallel GET /admin/appointments/check-collisions)
    |
    v
User clicks "Confirmar N turnos"
    |
    v
Sequential POST /admin/appointments for each slot
    |
    +--[slot i success]--> add to scheduled[]
    |
    +--[slot i 409 collision]--> add to failed[] with reason, continue
    |
    v
Summary dialog: "X de N turnos agendados. Y fallaron por colision."
    |
    +--[all succeeded]--> Close modal, single toast
    |
    +--[some failed]--> Keep summary visible, user can dismiss
```

---

## 5. Error Handling

### 5.1 Network Failures During Patient Creation

```
POST /admin/patients fails (timeout, 500, network error)
    |
    v
Modal stays open. Form data preserved.
Show inline error: "Error de conexion. Intenta nuevamente."
Submit button re-enabled after 2s cooldown.
```

No retry logic -- user clicks again manually. Idempotency is guaranteed by the unique constraint on `(tenant_id, phone_number)`.

### 5.2 Collision Detected During Scheduling

```
GET /admin/appointments/check-collisions returns has_collisions=true
    |
    v
Show inline warning with collision details:
  "Hay un turno existente: [datetime] con [professional]"
  "Bloqueo de Google Calendar: [title] ([datetime])"
    |
    v
Submit button disabled (cannot force through collision from chat panel).
User must pick a different time/professional.
```

The existing `POST /admin/appointments` endpoint also checks collisions server-side (lines 6499-6520) as a safety net, returning 409.

### 5.3 Concurrent Creation (Race Conditions)

**Scenario:** Two admins try to create the same patient simultaneously.

```
Admin A: POST /admin/patients (phone=+549111)
Admin B: POST /admin/patients (phone=+549111) -- arrives 50ms later
    |
    v
PostgreSQL UNIQUE constraint on (tenant_id, phone_number)
    |
    +--[Admin A wins]--> 201, patient created
    +--[Admin B loses]--> 409, "Ya existe un paciente con ese numero"
    |
    v
Admin B's modal shows error with option to load existing patient
```

**Scenario:** Two admins book the same slot simultaneously.

```
Admin A: check-collisions -> no collision -> POST /admin/appointments
Admin B: check-collisions -> no collision -> POST /admin/appointments (same slot)
    |
    v
Server-side collision check in POST handler (line 6499) catches this:
    +--[Admin A wins]--> 201, appointment created
    +--[Admin B loses]--> 409, "Hay colisiones de horario"
    |
    v
Admin B sees collision error, must pick new time
```

Both race conditions are handled by existing server-side constraints. The frontend just needs to display the 409 error gracefully.

### 5.4 Socket Disconnection

```
Socket disconnects during patient creation
    |
    v
POST /admin/patients still succeeds (HTTP, not socket)
PATIENT_CREATED event lost (no socket to receive it)
    |
    v
Modal closes normally via HTTP response callback
patientContext refresh happens via fetchPatientContext (HTTP)
    |
    v
When socket reconnects, no automatic reconciliation needed.
Next user action that triggers a context fetch will pick up the new state.
```

The modals do NOT depend on socket events for their own flow. Socket events only update OTHER open browser tabs/users.

---

## 6. Performance Considerations

### 6.1 Prefetch vs Lazy Load

| Data | Strategy | Rationale |
|------|----------|-----------|
| Professionals list | **Lazy load** on modal mount | Only ~5-15 records, fast query. Not needed until modal opens. |
| Treatment types | **Lazy load** on modal mount | Same. Fetch in parallel with professionals. |
| Insurance providers | **Lazy load** on CreatePatientModal mount | Only needed when creating/editing patient. |
| Collision check | **Lazy load** on user input | Real-time, cannot prefetch. |
| Patient context | **Already loaded** in side panel | No additional fetch. Passed via props. |
| Consultation price | **Lazy load** via tenant settings | One fetch, cache for session. Can also piggyback on existing tenant config fetch if available in AuthContext. |

**Parallel fetches on ScheduleAppointmentModal mount:**
```typescript
useEffect(() => {
  if (!isOpen) return;
  const controller = new AbortController();
  Promise.all([
    api.get('/admin/professionals', { signal: controller.signal }),
    api.get('/admin/treatment-types', { signal: controller.signal }),
  ]).then(([profRes, ttRes]) => {
    setProfessionals(profRes.data.filter((p: any) => p.is_active));
    setTreatmentTypes(ttRes.data);
  });
  return () => controller.abort();
}, [isOpen]);
```

### 6.2 Debounce Strategies

| Action | Debounce | Rationale |
|--------|----------|-----------|
| Collision check | 500ms | User is typing/selecting datetime. Don't fire on every keystroke. |
| Phone number validation | 300ms | Format check while typing. |
| Multi-session preview recalc | 200ms | Slider/input for count/interval. Pure client-side calculation, no API call. |

### 6.3 Optimistic Updates vs Wait-for-Server

**Decision: Wait-for-server on ALL mutations. No optimistic updates.**

Rationale:
- Patient creation has a unique constraint that can fail. Optimistic would show a patient that doesn't exist.
- Appointment creation has collision checks. Optimistic would show an appointment that might be rejected.
- The operations are fast (~100-300ms). The UX cost of waiting is low.
- Reverting optimistic updates on failure is complex and error-prone in a multi-modal context.
- Socket events handle cross-tab consistency -- optimistic updates would conflict with socket-driven state.

The only "optimistic" behavior: disable the submit button immediately on click and show a spinner. Re-enable on error.

---

## 7. i18n Keys Required

All visible text must go through `t()`. New keys for `es.json`, `en.json`, `fr.json`:

```json
{
  "modals.create_patient.title": "Crear paciente",
  "modals.create_patient.title_edit": "Completar ficha del paciente",
  "modals.create_patient.first_name": "Nombre",
  "modals.create_patient.last_name": "Apellido",
  "modals.create_patient.phone": "Telefono",
  "modals.create_patient.email": "Email",
  "modals.create_patient.dni": "DNI / Documento",
  "modals.create_patient.insurance": "Obra social",
  "modals.create_patient.city": "Ciudad",
  "modals.create_patient.birth_date": "Fecha de nacimiento",
  "modals.create_patient.submit": "Crear paciente",
  "modals.create_patient.submit_edit": "Guardar cambios",
  "modals.create_patient.duplicate_error": "Ya existe un paciente con ese numero de telefono",
  "modals.create_patient.success": "Paciente creado correctamente",

  "modals.schedule.title": "Agendar turno",
  "modals.schedule.step_patient": "Datos del paciente",
  "modals.schedule.step_appointment": "Datos del turno",
  "modals.schedule.professional": "Profesional",
  "modals.schedule.treatment_type": "Tipo de tratamiento",
  "modals.schedule.datetime": "Fecha y hora",
  "modals.schedule.duration": "Duracion (minutos)",
  "modals.schedule.notes": "Notas",
  "modals.schedule.collision_warning": "Hay colisiones de horario",
  "modals.schedule.no_collision": "Horario disponible",
  "modals.schedule.checking": "Verificando disponibilidad...",
  "modals.schedule.submit": "Confirmar turno",
  "modals.schedule.sena_label": "Sena requerida",
  "modals.schedule.multi_session": "Sesiones multiples",
  "modals.schedule.multi_count": "Cantidad de sesiones",
  "modals.schedule.multi_interval": "Intervalo entre sesiones",
  "modals.schedule.multi_preview": "Vista previa de fechas",
  "modals.schedule.multi_submit": "Confirmar {count} turnos",
  "modals.schedule.multi_result": "{success} de {total} turnos agendados",
  "modals.schedule.success": "Turno agendado correctamente",

  "chats.create_patient_btn": "Crear paciente",
  "chats.complete_profile_btn": "Completar ficha",
  "chats.view_profile_btn": "Ver ficha",
  "chats.schedule_btn": "Agendar turno"
}
```

---

## 8. File Inventory

### New Files
| File | Purpose |
|------|---------|
| `frontend_react/src/components/modals/CreatePatientModal.tsx` | Patient creation/edit modal |
| `frontend_react/src/components/modals/ScheduleAppointmentModal.tsx` | 2-step appointment wizard |

### Modified Files
| File | Change |
|------|--------|
| `orchestrator_service/db.py` | Add `create_if_missing` param to `ensure_patient_exists()` |
| `orchestrator_service/routes/chat_webhooks.py` | Pass `create_if_missing=False` |
| `orchestrator_service/main.py` (~line 4001) | Pass `create_if_missing=False` to triage call |
| `orchestrator_service/admin_routes.py` (~line 4248) | Add `request` param, PATIENT_CREATED emit, enhanced response |
| `orchestrator_service/admin_routes.py` (~line 465) | Add `is_lead` field to context response |
| `frontend_react/src/views/ChatsView.tsx` | Modal state, button conditions, socket handler, modal rendering |
| `frontend_react/src/locales/es.json` | i18n keys |
| `frontend_react/src/locales/en.json` | i18n keys |
| `frontend_react/src/locales/fr.json` | i18n keys |

### NOT Modified (decided against)
| File | Reason |
|------|--------|
| `orchestrator_service/models.py` | No new columns on `chat_conversations` (decided against `patient_id` FK) |
| No new Alembic migration | No schema changes needed. `ensure_patient_exists` is purely behavioral. |

---

## 9. Testing Strategy

### Backend Unit Tests

```python
# tests/test_ensure_patient_create_if_missing.py

async def test_ensure_patient_exists_create_if_missing_false_returns_none():
    """When create_if_missing=False and patient doesn't exist, return None."""
    result = await db.ensure_patient_exists(
        phone_number="+5491199990000",
        tenant_id=1,
        create_if_missing=False,
    )
    assert result is None

async def test_ensure_patient_exists_create_if_missing_false_finds_existing():
    """When create_if_missing=False and patient exists, return the patient."""
    # Pre-create patient
    await db.pool.execute(
        "INSERT INTO patients (tenant_id, phone_number, first_name, status) VALUES (1, '+5491199990000', 'Test', 'active')"
    )
    result = await db.ensure_patient_exists(
        phone_number="+5491199990000",
        tenant_id=1,
        create_if_missing=False,
    )
    assert result is not None
    assert result["status"] == "active"

async def test_ensure_patient_exists_default_still_creates():
    """Default behavior (create_if_missing=True) unchanged."""
    result = await db.ensure_patient_exists(
        phone_number="+5491199991111",
        tenant_id=1,
    )
    assert result is not None
    assert result["id"] is not None
```

### Frontend Component Tests

```typescript
// CreatePatientModal: renders with prefilled data
// CreatePatientModal: validates required fields
// CreatePatientModal: handles 409 duplicate gracefully
// ScheduleAppointmentModal: skips step 1 when patientId provided
// ScheduleAppointmentModal: shows step 1 when patientId null
// ScheduleAppointmentModal: collision warning disables submit
// ScheduleAppointmentModal: multi-session preview calculates dates correctly
```

---

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `create_if_missing=False` breaks Meta Ads attribution on first message | Lost first-touch attribution for new leads from ads | The attribution block in `chat_webhooks.py` (lines 219-260) already checks `if patient_row:` -- skipping when None is safe. Attribution will happen when the patient IS created (manually or via AI). We add a TODO to backfill attribution on patient creation. |
| Triage urgency not persisted for leads | Urgency level not saved until patient record exists | Acceptable tradeoff. The AI still receives the urgency assessment in the tool response. When patient is created later, next interaction persists it. |
| Multi-session sequential POSTs are slow for 12 sessions | ~3-4 seconds of waiting | Show progress indicator ("Agendando turno 3 de 12..."). Each success updates the preview in real-time. User sees incremental progress. |
| ChatsView is already 1748 lines | Adding modals increases complexity | Modals are separate files. ChatsView only gains ~40 lines (state, handlers, JSX render). The modals encapsulate all their logic. |
