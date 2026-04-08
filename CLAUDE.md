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

- **Database**: PostgreSQL 13 with SQLAlchemy 2.0 ORM (31 model classes in `orchestrator_service/models.py`) + pgvector extension for RAG embeddings
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
- `services/embedding_service.py` — RAG system: pgvector embeddings, semantic FAQ search
- `services/metrics_service.py` — Unified attribution metrics (first/last touch, ROI dashboard)
- `routes/metrics.py` — `/admin/metrics/*` endpoints (campaigns, attribution, ROI, trends)
- `jobs/` — Background jobs: lead recovery, reminders, followups
- `alembic/` — Database migrations. **Current head: `032_multi_agent_tables.py`**. Chain: 001 baseline → 002 treatment_type_professionals → 003 consultation_price/anamnesis_token → 004 guardian_phone → 005 meta_native_connection → 006 billing_bank_derivation → 007 tenant_logo_url → 008 max_chairs → 009 pgvector_faq_embeddings → 010 country_code+tenant_holidays → 011 priority_fields → 012 clinical_rules_engine → 013 patient_digital_records → 014 custom_holiday_hours → 015 keyword_lists → 016 clinical_record_summaries → 017 odontogram_v3 → 018 treatment_plan_billing → 019 treatment_plan_billing_fixes → 020 financial_command_center → 021 telegram_authorized_users → 022 patient_display_name → 023 nova_memories → 024 assigned_professional → 025 fix_faq_embeddings_vector_type → 026 fix_duplicated_professional_names → 027 appointment_unique_constraint → 028 appointment_audit_log → 029 validate_tenant_country_code → 030 chat_messages_provider_msg_unique → 031 ai_engine_mode_column (dual-engine) → 032 multi_agent_tables (dual-engine). **Rule**: before writing a new migration, run `ls orchestrator_service/alembic/versions/` to confirm the real head — never trust stale notes.
- `email_service.py` — Handoff email service (multi-channel, multi-recipient)
- `dashboard/config_manager.py` — Dynamic AI model configuration (system_config table)
- `dashboard/token_tracker.py` — Token usage tracking per conversation
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
- PostgreSQL 13 / asyncpg / SQLAlchemy 2.0 / Alembic / pgvector (RAG)
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
| `check_availability` | Check real availability (multi-day search up to 7 days, returns 2-3 concrete slots + sede info) |
| `confirm_slot` | **(NEW)** Soft-lock a slot for 30s via Redis before collecting patient data |
| `book_appointment` | Register an appointment (supports self, third-party adult, and minor bookings; includes sede in confirmation) |
| `list_my_appointments` | List patient's upcoming appointments |
| `cancel_appointment` | Cancel a patient's appointment |
| `reschedule_appointment` | Reschedule an appointment |
| `triage_urgency` | Analyze symptom urgency (expanded: tooth loss, multi-condition detection) |
| `save_patient_anamnesis` | Save medical history from AI chat conversation |
| `save_patient_email` | Save patient email (supports `patient_phone` for third-party bookings) |
| `get_patient_anamnesis` | Read completed anamnesis form data for verification |
| `verify_payment_receipt` | Verify bank transfer receipt via vision (matches holder name + amount, handles partial payments) |
| `derivhumano` | Hand off to human + 24h silence window + comprehensive email to clinic & professionals |

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

### Consultation Price & Billing
Stored in `tenants.consultation_price` (DECIMAL). Configurable from the UI in clinic settings. The AI uses this value dynamically when patients ask about pricing. If NULL, the AI tells the patient to contact the clinic directly. **Per-professional override**: `professionals.consultation_price` takes precedence over tenant price. **Billing fields** on appointments: `billing_amount`, `billing_installments`, `billing_notes`, `payment_status` (pending/partial/paid), `payment_receipt_data` (JSONB). **Bank config** on tenants: `bank_cbu`, `bank_alias`, `bank_holder_name` for payment verification via vision.

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

### RAG System (Retrieval-Augmented Generation)
Semantic FAQ search powered by pgvector. Instead of injecting all 20 FAQs into the AI prompt, the system embeds each FAQ as a 1536-dim vector (OpenAI `text-embedding-3-small`) and retrieves only the top-5 most relevant FAQs based on the patient's message.

**Architecture:** `patient message → embedding → pgvector cosine similarity → top-K FAQs → inject into prompt`

**Tables:** `faq_embeddings` (per-FAQ vectors), `document_embeddings` (future: clinical docs).

**Fallback:** If pgvector is not available (hosting limitation), the system automatically falls back to the original static FAQ injection (first 20 FAQs). No breakage.

**Sync:** Embeddings auto-generate on FAQ create/update/delete via hooks in `admin_routes.py`. Bulk sync runs at startup for all tenants (`embedding_service.sync_all_tenants_faq_embeddings`).

### ROI Dashboard
Dedicated analytics view (`/roi`) with real spend data from Meta API and billing revenue from appointments. Executive summary endpoint consolidates: total spend, revenue, ROI %, leads, conversions, cost per lead, top campaign. Attribution mix shows First Touch vs Last Touch vs Organic distribution. All metrics scoped by `tenant_id`.

---

## Dual-Engine Architecture (TORA Solo + Multi-Agent)

ClinicForge supports **two independent conversational AI engines** per tenant. The CEO selects which one to use from the Settings UI. This was built to coexist with (not replace) the original monolithic TORA and allow experimental migration to a multi-agent architecture.

### The two engines

| Engine | Module | Description |
|--------|--------|-------------|
| **SoloEngine** (`solo`) | `orchestrator_service/main.py` | The original monolithic LangChain agent TORA with `DENTAL_TOOLS`. Hardened by changes C1 (quick wins) and C2 (state lock + date validator). Default for all tenants. |
| **MultiAgentEngine** (`multi`) | `orchestrator_service/agents/` | Supervisor + 6 specialized agents (Reception, Booking, Triage, Billing, Anamnesis, Handoff) with shared `PatientContext`. Opt-in per tenant. |

### How routing works

1. WhatsApp/web message arrives → `services/buffer_task.py:998`
2. `services/engine_router.py` → `get_engine_for_tenant(tenant_id)` reads `tenants.ai_engine_mode` (cached 60s in-memory, invalidated via Redis pubsub on settings PATCH)
3. Returns `SoloEngine` or `MultiAgentEngine` based on the value
4. Circuit breaker: 3 consecutive multi failures within 60s → automatic fallback to solo for 5 minutes for that tenant

### Toggle UI

- **Page:** `frontend_react/src/views/ConfigView.tsx` → general tab
- **Gate:** `user?.role === 'ceo'` (only the CEO of the tenant sees the selector)
- **Flow:** select target → `GET /admin/ai-engine/health` runs sanity probes on both engines in parallel → modal shows result → confirm button enabled only if target reports OK → `PATCH /admin/settings/clinic` with `ai_engine_mode` (extends the existing endpoint, re-runs target probe inline, refuses with 422 if it fails)

### Migrations

- `031_ai_engine_mode_column.py` — adds `tenants.ai_engine_mode TEXT NOT NULL DEFAULT 'solo' CHECK (IN ('solo','multi'))`
- `032_multi_agent_tables.py` — adds `patient_context_snapshots` (LangGraph-style checkpointer keyed by `(tenant_id, phone_number, thread_id)`) and `agent_turn_log` (per-turn audit with `agent_name`, `tools_called JSONB`, `duration_ms`, `model`)

### Model selection (CRITICAL)

**Both engines use the SAME source of truth for model selection:** the `system_config.OPENAI_MODEL` row configured via the **Tokens & Metrics** admin page.

- **SoloEngine**: reads the model in `main.get_agent_executable_for_tenant` (around line 7327).
- **MultiAgentEngine**: reads the model in `agents/model_resolver.py` → `resolve_tenant_model(tenant_id)` which mirrors the solo logic exactly. Called once per turn in `agents/graph.py:run_turn` and propagated via `AgentState["model_config"]`. Every agent reads the model from the state, never from a class attribute.

**NEVER hardcode a model name in agent code.** Always call the resolver or read from `state["model_config"]`. The default fallback model is `DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"` defined in `main.py` and mirrored in `agents/model_resolver.py`. Both engines also auto-detect DeepSeek models (`deepseek-chat`, `deepseek-reasoner`) and switch API key + base URL accordingly.

### Multi-agent system internals

- **Supervisor** (`agents/supervisor.py`): deterministic regex rules first (emergency/billing/anamnesis/handoff/booking/greeting), LLM fallback using tenant's configured model. Honors `human_override_until` (silent) and `hop_count >= max_hops` (→ handoff).
- **6 specialists** (`agents/specialists.py`): each wraps a bounded `AgentExecutor` (`max_iterations=4`) with ONLY its subset of `DENTAL_TOOLS` (lazy imported from `main`). All read `state["model_config"]`, all respond in Spanish rioplatense (voseo).
- **PatientContext** (`services/patient_context.py`): tenant-scoped loader with 2 layers — Profile (PG: patients + medical_history + future_appointments + last 20 chat_messages) and Working (Redis hash `patient_ctx_working:{tenant_id}:{phone}` TTL 30min). Fail-safe: empty profile on error.
- **Graph entry point** (`agents/graph.py`): `run_turn(ctx)` resolves model, loads context, routes via supervisor, dispatches, writes `agent_turn_log` best-effort, wraps in 45s `asyncio.timeout`. `probe()` runs supervisor routing on a minimal fake state for the health check.
- **Max hops:** 5. **Turn timeout:** 45s.

### Health check endpoint

`GET /admin/ai-engine/health` (defined in `orchestrator_service/routes/ai_engine_health.py`) runs both probes in parallel and returns:
```json
{"solo": {"ok": true, "latency_ms": 123, "detail": "..."},
 "multi": {"ok": true, "latency_ms": 456, "detail": "..."}}
```

### Rules

1. Hook point for the router is `services/buffer_task.py:998` — do NOT dispatch to the engine from anywhere else.
2. Every query in `PatientContext` MUST filter by `tenant_id` (Sovereignty Protocol §1).
3. Never hardcode a model. Always resolve via `model_resolver.resolve_tenant_model(tenant_id)` or read from `state["model_config"]`.
4. When adding a new specialized agent: inherit `BaseAgent`, read model from state, register in the `AGENTS` dict, add the routing rule to `SupervisorAgent`.
5. `ai_engine_mode` default stays `'solo'`. Switching to `'multi'` requires the CEO to pass the health check in the UI.

---

## Nova — AI Voice Assistant (Jarvis for Dental Clinics)

### Overview
Nova is the voice-powered AI copilot that runs inside ClinicForge. Available as a floating widget on every page. Uses OpenAI Realtime API for bidirectional audio + function calling.

### Architecture
```
NovaWidget (React)  →  WebSocket  →  Nova Handler (main.py)  →  OpenAI Realtime API
                                          ↕
                                    Nova Tools (50 tools)  →  PostgreSQL
```

### Files
| File | Purpose |
|------|---------|
| `frontend_react/src/components/NovaWidget.tsx` | Voice widget UI, WebSocket client, audio playback |
| `orchestrator_service/services/nova_tools.py` | 49 tool definitions + implementations |
| `orchestrator_service/main.py` (~line 4713) | WebSocket handler, Realtime API bridge, system prompt |
| `orchestrator_service/services/nova_daily_analysis.py` | Automated daily insights (every 12h) |
| `orchestrator_service/routes/nova_routes.py` | REST endpoints (context, health, sessions) |

### Tools (50 total)
Organized in categories:

| Category | Tools | Count |
|----------|-------|-------|
| **A. Pacientes** | buscar_paciente, ver_paciente, registrar_paciente, actualizar_paciente, historial_clinico, registrar_nota_clinica, eliminar_paciente | 7 |
| **B. Turnos** | ver_agenda, proximo_paciente, verificar_disponibilidad, agendar_turno, cancelar_turno, confirmar_turnos, reprogramar_turno, cambiar_estado_turno, bloquear_agenda | 9 |
| **C. Facturación** | listar_tratamientos, registrar_pago, facturacion_pendiente | 3 |
| **D. Analytics** | resumen_semana, rendimiento_profesional, ver_estadisticas, resumen_marketing, resumen_financiero | 5 |
| **E. Navegación** | ir_a_pagina, ir_a_paciente | 2 |
| **F. Multi-sede** | resumen_sedes, comparar_sedes, switch_sede, onboarding_status | 4 |
| **G. Staff** | listar_profesionales, ver_configuracion, actualizar_configuracion, crear_tratamiento, editar_tratamiento, ver_chats_recientes, enviar_mensaje, ver_faqs, eliminar_faq, actualizar_faq | 10 |
| **H. Anamnesis** | guardar_anamnesis, ver_anamnesis | 2 |
| **H2. Odontograma** | ver_odontograma, modificar_odontograma | 2 |
| **I. Datos** | consultar_datos | 1 |
| **K. RAG** | buscar_en_base_conocimiento | 1 |
| **J. CRUD** | obtener_registros, actualizar_registro, crear_registro, contar_registros | 4 |

### Tool Schema Format (CRITICAL)
OpenAI Realtime API requires **flat** tool schema format:
```json
{"type": "function", "name": "tool_name", "description": "...", "parameters": {...}}
```
**NOT** the Chat Completions wrapper format:
```json
{"type": "function", "function": {"name": "tool_name", ...}}  // WRONG for Realtime
```

### Payment Verification Flow
The AI agent automatically detects payment receipts when a patient with pending seña sends an image:
- `buffer_task.py` checks if patient has pending payment before processing image
- If yes, injects "PROBABLE COMPROBANTE DE PAGO" context
- Agent calls `verify_payment_receipt` instead of saving as medical document
- Verification checks holder name (fuzzy match + CBU/alias) and amount (accepts overpayment)
- Success: appointment status → confirmed, payment_status → paid
- Failure: explains issue, asks for corrected receipt

### Date Parsing System
`parse_date()` uses 7-layer priority for robust date interpretation:
1. Exact shortcuts (hoy, mañana, pasado mañana)
2. ASAP/no preference (lo antes posible, cualquier día)
3. dateutil fuzzy parsing (30 de abril, jueves 30 de abril)
4. Month expressions (fines de abril, mitad de julio)
5. Weekday only (jueves, lunes)
6. Relative phrases (próxima semana, mes que viene)
7. Fallback: None (never invents dates)

`check_availability` uses `interpreted_date` (YYYY-MM-DD from LLM reasoning) + `search_mode` (exact/week/month/open) for accurate date resolution. Auto-advances to next valid day if clinic/professional is closed.

### CRUD Tools
Generic tools that give Nova access to ALL database tables:
- `obtener_registros(tabla, filtros, campos, limite, orden)` — GET with filters (max 15 results)
- `actualizar_registro(tabla, registro_id, campos)` — UPDATE by ID
- `crear_registro(tabla, datos)` — INSERT new record
- `contar_registros(tabla, filtros)` — COUNT with filters

Allowed tables: patients, appointments, professionals, treatment_types, tenants, chat_messages, chat_conversations, patient_documents, clinical_records, automation_logs, patient_memories, clinic_faqs, google_calendar_blocks, meta_ad_insights, treatment_type_professionals, users.

### Date Handling
All tool args come as strings from OpenAI. Use `_parse_date_str()` and `_parse_datetime_str()` helpers to convert before passing to asyncpg.

### Voice Model Configuration
- Stored in `system_config` table, key `MODEL_NOVA_VOICE`
- Options: `gpt-4o-mini-realtime-preview` (economic) or `gpt-4o-realtime-preview` (premium)
- Selected from Tokens & Metrics page in the admin UI

### System Prompt Design
Nova's prompt follows the "Jarvis" principle:
- Execute tools FIRST, talk AFTER
- Chain 2-3 tools without asking for confirmation
- If missing a data point, infer or ask ONCE
- When on anamnesis page, switch to patient-facing mode
- NEVER say "no puedo" if a tool can solve it

### MCP Server (Planned)
A Model Context Protocol server is planned to replace the 49 individual tools with a more fluid resource-based architecture. See `MCP_SERVER_SPEC.md` for the complete specification.

---

## UI Design System

### Dark Mode (Mandatory)
The entire platform uses dark mode. No light mode exists.

| Element | Class |
|---------|-------|
| Root background | `bg-[#06060e]` |
| Cards | `GlassCard` component with hover images |
| Modals | `bg-[#0d1117]` |
| Text primary | `text-white` |
| Text secondary | `text-white/50` |
| Text muted | `text-white/30` |
| Borders | `border-white/[0.06]` |
| Inputs | `bg-white/[0.04] border-white/[0.08] text-white` |
| Primary buttons | `bg-white text-[#0a0e1a]` (white accent) |
| Badges | `bg-{color}-500/10 text-{color}-400` |

### GlassCard Component
Reusable card with background image that fades in on hover/touch:
- `blur(2px)` filter on background image
- Ken Burns slow zoom animation (8s)
- Scale-up 1.015x with cubic-bezier bounce
- Blue gradient glow on bottom edge
- Pre-defined `CARD_IMAGES` for each context

### Sidebar
Uses Lucide icons (no emojis). Each item has a themed background image on hover with scale animation.
