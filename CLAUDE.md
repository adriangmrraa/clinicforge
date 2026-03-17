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

- **Database**: PostgreSQL 13 with SQLAlchemy 2.0 ORM (30 model classes in `orchestrator_service/models.py`)
- **Migrations**: Alembic (`orchestrator_service/alembic/`) — auto-runs `alembic upgrade head` on startup via `start.sh`
- **Cache**: Redis (deduplication, message buffers, Meta Ads enrichment cache)
- **Containers**: Docker Compose (`docker-compose.yml`)
- **Deployment**: EasyPanel / Render / AWS ECS

---

## Key Files

### Backend (orchestrator_service/)
- `main.py` — FastAPI app, LangChain agent, AI tools (`DENTAL_TOOLS`), Socket.IO, system prompt
- `admin_routes.py` — All `/admin/*` endpoints (patients, appointments, marketing, staff)
- `auth_routes.py` — `/auth/*` endpoints (login, register, clinics, profile)
- `db.py` — Async connection pool (asyncpg)
- `models.py` — SQLAlchemy ORM models (30 classes)
- `gcal_service.py` — Google Calendar hybrid integration
- `analytics_service.py` — Professional metrics and reporting
- `services/meta_ads_service.py` — Meta Graph API client
- `services/marketing_service.py` — ROI & performance intelligence
- `jobs/` — Background jobs: lead recovery, reminders, followups
- `alembic/` — Database migrations (baseline + incremental)
- `requirements.txt` — Python dependencies

### Frontend (frontend_react/src/)
- `App.tsx` — Router setup (use `path="/*"` for nested routes)
- `api/axios.ts` — Axios instance with auto-injected `Authorization` + `X-Admin-Token`
- `context/` — AuthContext, LanguageContext
- `locales/` — i18n translations: `es.json`, `en.json`, `fr.json`
- `views/` — Page components (AgendaView, ChatsView, DashboardView, PatientsView, etc.)
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
| `list_services` | List bookable treatment types |
| `check_availability` | Check real availability for a day (supports `time_preference`) |
| `book_appointment` | Register an appointment |
| `list_my_appointments` | List patient's upcoming appointments |
| `cancel_appointment` | Cancel a patient's appointment |
| `reschedule_appointment` | Reschedule an appointment |
| `triage_urgency` | Analyze symptom urgency |
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

See `.env.production.example` for the complete list.

---

## Project-Specific Patterns

### Hybrid Calendar
Each tenant can use `'local'` (DB-only) or `'google'` calendar. Controlled by `tenants.config.calendar_provider`. All calendar operations check this field and route to the appropriate implementation.

### Human Override
When a human agent intervenes in a WhatsApp chat, the AI is silenced for 24 hours per `(tenant_id, phone_number)`. Stored in `patients.human_override_until`.

### Meta Ads Attribution
First-touch model: the first ad that brings a patient is recorded permanently. Background tasks enrich ad data via Meta Graph API with Redis cache (48h TTL).

### BFF Proxy Pattern
Frontend (port 4173) never calls the orchestrator directly. All API calls go through the BFF Express proxy (port 3000), which handles CORS and 60s timeouts.
