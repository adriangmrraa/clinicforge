# CLAUDE.md — ClinicForge AI Assistant Guide

## Project Overview

ClinicForge is a **multi-tenant SaaS** for clinical practice management with AI-powered patient interactions. It combines appointment scheduling, patient triage, WhatsApp/Instagram/Facebook messaging, and Meta Ads attribution tracking. Built as a microservices architecture with Python/FastAPI backend, React/TypeScript frontend, and an Express BFF proxy.

---

## Architecture

```
Frontend (React 18 + Vite)  →  BFF (Express :3000)  →  Orchestrator (FastAPI :8000)
                                                            ↕
                                                     PostgreSQL + Redis
WhatsApp Service (:8002)  ←→  Orchestrator  ←→  YCloud / Chatwoot
```

### Services

| Service | Path | Tech | Port |
|---------|------|------|------|
| **Orchestrator** | `orchestrator_service/` | FastAPI + LangChain + Socket.IO | 8000 |
| **BFF** | `bff_service/` | Express + Axios reverse proxy | 3000 |
| **Frontend** | `frontend_react/` | React 18 + TypeScript + Vite + Tailwind | 4173 |
| **WhatsApp** | `whatsapp_service/` | FastAPI + YCloud + Whisper | 8002 |

### Infrastructure

- **Database**: PostgreSQL 13 with SQLAlchemy 2.0 ORM (31 model classes in `orchestrator_service/models.py`)
- **Migrations**: Alembic (`orchestrator_service/alembic/`) — auto-runs `alembic upgrade head` on startup via `start.sh`
- **Cache**: Redis (deduplication, message buffers, Meta Ads enrichment cache)
- **Containers**: Docker Compose (`docker-compose.yml`)
- **Deployment**: EasyPanel / Render / AWS ECS

---

## Key Files

### Backend (orchestrator_service/)
- `main.py` — FastAPI app, LangChain agent, AI tools (`DENTAL_TOOLS`), Socket.IO, system prompt
- `admin_routes.py` — All `/admin/*` endpoints (patients, appointments, marketing, staff)
- `public_routes.py` — Public endpoints without auth (`/public/anamnesis/{tenant_id}/{token}`)
- `auth_routes.py` — `/auth/*` endpoints (login, register, clinics, profile)
- `db.py` — Async connection pool (asyncpg)
- `models.py` — SQLAlchemy ORM models (31 classes)
- `gcal_service.py` — Google Calendar hybrid integration
- `analytics_service.py` — Professional metrics and reporting
- `services/meta_ads_service.py` — Meta Graph API client
- `services/marketing_service.py` — ROI & performance intelligence
- `jobs/` — Background jobs: lead recovery, reminders, followups
- `alembic/` — Database migrations (baseline + incremental: 001 baseline → 002 treatment_type_professionals → 003 consultation_price/anamnesis_token → 004 guardian_phone)
- `requirements.txt` — Python dependencies

### Frontend (frontend_react/src/)
- `App.tsx` — Router setup (use `path="/*"` for nested routes)
- `api/axios.ts` — Axios instance with auto-injected `Authorization` + `X-Admin-Token`
- `context/` — AuthContext, LanguageContext
- `locales/` — i18n translations: `es.json`, `en.json`, `fr.json`
- `views/` — Page components (AgendaView, ChatsView, DashboardView, PatientsView, etc.)
- `views/AnamnesisPublicView.tsx` — Public anamnesis form (mobile-optimized checklist, no auth)
- `components/` — Shared UI components

### Config
- `docker-compose.yml` — Full local stack
- `.env.production.example` — Template for environment variables
- `pytest.ini` — Test configuration
- `frontend_react/vite.config.ts` — Vite build config
- `frontend_react/eslint.config.js` — ESLint config
- `frontend_react/tailwind.config.js` — Tailwind CSS config

---

## Critical Rules (Sovereignty Protocol)

### 1. Multi-Tenant Data Isolation (MANDATORY)
Every SQL query **MUST** include `WHERE tenant_id = $x`. The `tenant_id` is resolved from the JWT/database — **never from request parameters**. This is the legal and technical barrier for data isolation.

### 2. Authentication
- Protected routes use `Depends(verify_admin_token)` or `Depends(get_current_user)`
- All `/admin/*` routes require **JWT + X-Admin-Token** header
- Extract `tenant_id` from the authenticated user, never from query params

### 3. Frontend Scroll Isolation
Always use scroll isolation for views with dense content:
- Global: `h-screen`, `overflow-hidden`
- Internal containers: `overflow-y-auto`, `flex-1 min-h-0`

### 4. Internationalization (i18n)
- All visible text must use `useTranslation()` hook with `t('key')` — never hardcode strings
- Add keys to all 3 locale files: `es.json`, `en.json`, `fr.json`
- Default language: Spanish

### 5. Database Changes
- **Always use Alembic migrations** — never run SQL directly
- Create migration: `alembic revision -m "description"` (from `orchestrator_service/`)
- Include both `upgrade()` and `downgrade()` functions
- Update `models.py` ORM classes alongside every migration

---

## Development Workflow

### Local Setup
```bash
# Clone and configure
git clone https://github.com/adriangmrraa/clinicforge.git
cd clinicforge
cp .env.production.example .env  # Edit with real values

# Start all services
docker-compose up -d --build

# Or for local dev without Docker
./start_local_dev.sh
```

### Running Tests
```bash
# Run all tests
pytest

# Test paths configured in pytest.ini: tests/
# Async mode: auto (pytest-asyncio)
```

### Building Frontend
```bash
cd frontend_react
npm install
npm run build    # tsc && vite build
npm run dev      # Development with HMR
npm run lint     # ESLint check
```

### Services URLs (Local)
| Service | URL |
|---------|-----|
| Orchestrator API | http://localhost:8000 |
| Swagger/OpenAPI | http://localhost:8000/docs |
| BFF Proxy | http://localhost:3000 |
| Frontend UI | http://localhost:4173 |
| WhatsApp Service | http://localhost:8002 |

---

## Code Conventions

### Python (Backend)
- Framework: FastAPI with async/await
- Database: asyncpg for raw queries, SQLAlchemy for ORM models
- Auth: `Depends(verify_admin_token)` on every admin endpoint
- Socket.IO: Emit events for real-time UI updates (`NEW_APPOINTMENT`, `APPOINTMENT_UPDATED`, `APPOINTMENT_DELETED`)
- AI Tools: Decorated with `@tool`, added to `DENTAL_TOOLS` array in `main.py`
- Context vars: `current_tenant_id.get()`, `current_customer_phone.get()` in tool functions
- Exception handling: Global handler in `main.py` for CORS stability

### TypeScript/React (Frontend)
- Strict TypeScript
- Tailwind CSS for all styling (no CSS modules)
- Icons: `lucide-react`
- API calls: Always use `import api from '../api/axios'` (auto-injects auth headers)
- No `dangerouslySetInnerHTML` — use `<SafeHTML html={...} />` for dynamic content
- Routing: `path="/*"` on routes containing child `Routes`

### Commit Messages
Follow conventional style: `feat:`, `fix:`, `docs:`, `refactor:` with concise descriptions.

---

## Tech Stack Summary

### Backend
- Python 3.11+ / FastAPI / Uvicorn (ASGI)
- LangChain 0.1.0 + OpenAI gpt-4o-mini
- PostgreSQL 13 / asyncpg / SQLAlchemy 2.0 / Alembic
- Redis / Socket.IO / Pydantic
- Google Calendar API / YCloud (WhatsApp) / Meta Graph API

### Frontend
- React 18 / TypeScript / Vite
- Tailwind CSS / Lucide React
- FullCalendar / Recharts / Socket.IO Client
- Axios / React Router DOM v6 / DOMPurify

### Infrastructure
- Docker Compose (local) / EasyPanel (production)
- Nginx (SPA serving)
- Express BFF proxy

---

## AI Agent Tools

The LangChain agent exposes these tools (defined in `orchestrator_service/main.py`):

| Tool | Purpose |
|------|---------|
| `list_professionals` | List active professionals for a clinic |
| `list_services` | List bookable treatment types (shows assigned professionals) |
| `check_availability` | Check real availability for a day (uses tenant `working_hours` per-day slots + sede info) |
| `book_appointment` | Register an appointment (supports self, third-party adult, and minor bookings; includes sede in confirmation) |
| `list_my_appointments` | List patient's upcoming appointments |
| `cancel_appointment` | Cancel a patient's appointment |
| `reschedule_appointment` | Reschedule an appointment |
| `triage_urgency` | Analyze symptom urgency |
| `save_patient_anamnesis` | Save medical history from AI chat conversation |
| `save_patient_email` | Save patient email (supports `patient_phone` for third-party bookings) |
| `get_patient_anamnesis` | Read completed anamnesis form data for verification |
| `derivhumano` | Hand off to human + 24h silence window |

---

## Environment Variables (Key)

| Variable | Service | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | Orchestrator | AI model access |
| `POSTGRES_DSN` | Orchestrator | Database connection |
| `REDIS_URL` | Orchestrator, WhatsApp | Cache and message buffers |
| `ADMIN_TOKEN` | Orchestrator, Frontend | X-Admin-Token header value |
| `JWT_SECRET_KEY` | Orchestrator | JWT signing |
| `YCLOUD_API_KEY` | WhatsApp | WhatsApp Business API |
| `CREDENTIALS_FERNET_KEY` | Orchestrator | Credential encryption |
| `META_ADS_TOKEN` | Orchestrator | Meta Graph API for ad enrichment |
| `VITE_API_URL` | Frontend | BFF proxy URL |
| `FRONTEND_URL` | Orchestrator | Public-facing frontend URL (for anamnesis form links) |

See `.env.production.example` for the complete list.

---

## Project-Specific Patterns

### Hybrid Calendar
Each tenant can use `'local'` (DB-only) or `'google'` calendar. Controlled by `tenants.config.calendar_provider`. All calendar operations check this field and route to the appropriate implementation.

### Human Override
When a human agent intervenes in a WhatsApp chat, the AI is silenced for 24 hours per `(tenant_id, phone_number)`. Stored in `patients.human_override_until`.

### Meta Ads Attribution
First-touch model: the first ad that brings a patient is recorded permanently. Background tasks enrich ad data via Meta Graph API with Redis cache (48h TTL).

### Treatment-Professional Assignment
Many-to-many relationship via `treatment_type_professionals` junction table. Each treatment can be assigned to specific professionals. **Backward compatibility rule**: if a treatment has no professionals assigned, ALL active professionals can perform it. The AI tools (`check_availability`, `book_appointment`, `list_services`, `get_service_details`) all respect this rule. Managed via `GET/PUT /admin/treatment-types/{code}/professionals` endpoints.

### Multi-Sede (Location per Day)
The clinic can operate from different locations depending on the day of the week. This is configured in `tenants.working_hours` JSONB with per-day `location`, `address`, and `maps_url` fields. Professionals can optionally override location per day in their own `working_hours`. **Resolution chain**: professional.working_hours[day].location → tenant.working_hours[day].location → tenant.address (fallback). The AI agent includes the correct sede in appointment confirmations.

**AI Tools integration**: `check_availability` reads `tenants.working_hours` to determine per-day time slots (instead of env vars `CLINIC_HOURS_START/END`). If a day is disabled, it returns "clinic closed". The response includes the sede/address/Maps link for the queried day. `book_appointment` also resolves and includes the sede in the confirmation message.

**JSONB handling**: asyncpg may return JSONB columns as strings. The `GET /admin/tenants` endpoint applies `json.loads` defensively, and the frontend's `parseWorkingHours()` also handles string input via `JSON.parse`.

### Differentiated AI Greeting
The AI agent uses different greetings based on patient status:
- **New lead** (not in patients table): "En qué tipo de consulta estás interesado?"
- **Patient without future appointment**: "En qué podemos ayudarte hoy?"
- **Patient with future appointment**: Personalized comment about their upcoming appointment + sede

### Implant/Prosthesis Commercial Triage
When a patient mentions implants or prosthetics, the AI activates a commercial triage flow with 6 emoji options (mandatory visible), followed by profundization and positioning messages about the doctor's specialties.

### Consultation Price
Stored in `tenants.consultation_price` (DECIMAL). Configurable from the UI in clinic settings. The AI uses this value dynamically when patients ask about pricing. If NULL, the AI tells the patient to contact the clinic directly.

### Third-Party & Minor Booking
The AI agent supports booking appointments for third parties (friends, family) and minors (children). Three scenarios:
- **For self**: standard flow, no extra params.
- **For adult third party**: agent asks for the third party's phone number. `book_appointment(patient_phone=..., is_minor=false)`. Creates a separate patient record.
- **For minor (child)**: agent does NOT ask for phone. `book_appointment(is_minor=true)`. Phone is auto-generated as `parent_phone-M{N}` (e.g., `+549111-M1`). The `guardian_phone` column links the minor to the parent. The agent's context (via `buffer_task.py`) includes all linked minors with their anamnesis links and next appointments. **Name protection**: the interlocutor's patient name is NEVER overwritten when booking for someone else. `save_patient_email` accepts optional `patient_phone` to target the correct patient record.

### Bulk Patient Import (CSV/XLSX)
Two-step flow via `POST /admin/patients/import/preview` and `POST /admin/patients/import/execute`. Supports CSV and XLSX with auto-encoding detection (UTF-8 → latin-1 fallback). Column aliases map Spanish headers to DB fields (e.g., `nombre` → `first_name`, `telefono` → `phone_number`). Max 1000 rows. Missing phone/DNI generates placeholders (`SIN-TEL-XXX`, `SIN-DNI-XXX`). Duplicate detection by phone with user choice: skip or update (COALESCE — only fills empty DB fields). Frontend modal in PatientsView with drag & drop upload → preview → result flow.

### Public Anamnesis Form
Unique link to a mobile-optimized anamnesis checklist form (`/anamnesis/{tenant_id}/{token}`). Token is a UUID in `patients.anamnesis_token`. The form page is NOT in the sidebar — only accessible via AI-generated link. Public endpoints: `GET/POST /public/anamnesis/{tenant_id}/{token}` (no auth). **Smart send behavior**: the AI sends the link automatically after booking ONLY if the patient has no completed anamnesis (`medical_history.anamnesis_completed_at` is null). If already completed, the AI only sends the link when the patient explicitly asks to update their data. The form always pre-fills existing data so patients can edit without re-entering everything.

### BFF Proxy Pattern
Frontend (port 4173) never calls the orchestrator directly. All API calls go through the BFF Express proxy (port 3000), which handles CORS and 60s timeouts.
