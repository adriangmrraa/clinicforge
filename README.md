# 🦷 Dentalogic – Sovereign Clinical SaaS

**The Ultimate AI-Driven Operating System for Dental Practice Excellence.** Multi-tenant orchestration, sovereign data isolation, and real-time clinical coordination via WhatsApp.

`Python` `React` `TypeScript` `FastAPI` `LangChain`

---

## 📋 Table of Contents

- [Vision & Value Proposition](#-vision--value-proposition)
- [Technology Stack & Architecture](#-technology-stack--architecture)
- [AI Models & Capabilities](#-ai-models--capabilities)
- [Key Features](#-key-features)
- [Project Structure](#-project-structure)
- [Deployment Guide (Quick Start)](#-deployment-guide-quick-start)
- [Documentation Hub](#-documentation-hub)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌟 Vision & Value Proposition

Dentalogic is more than a chatbot: it is a **Digital Clinical Coordinator** designed for dental practices and clinic groups. Built on **Sovereignty**, **Multi-Tenancy**, and **Value**, it delivers the first AI-driven OS that manages appointments, triage, and patient conversations while keeping each clinic’s data strictly isolated.

### 🎯 For Whom

| Audience | Value |
|----------|--------|
| **Single clinics** | Centralize agenda, patients, WhatsApp conversations, and reports in one tool; fewer spreadsheets and missed calls. |
| **Clinic groups / franchises** | Each location (tenant) has its own data and calendar; the CEO sees all locations, staff approvals, and analytics from one panel. Ideal for owners of 2+ clinics who want control without mixing data between sites. |
| **Multilingual teams** | UI in **Spanish**, **English**, and **French**. Language is set in Configuration and applies to the entire platform. The WhatsApp assistant detects the patient’s language and replies in the same language. |

### 🛡️ Sovereign Data (Tenant-First)

Your data, your clinic, your keys. Every query is filtered by `tenant_id`. Identity is resolved from JWT and database (never from client-supplied tenant). Admin routes require **JWT + X-Admin-Token** so that a stolen token alone cannot access the API.

### 📱 True Omnichannel (WhatsApp + Chatwoot)

The AI lives where your patients are:

- **WhatsApp** (YCloud integration): Booking, triage, and human handoff.
- **Chatwoot** (optional): Receive and reply to conversations from **WhatsApp, Instagram, and Facebook** in the same Chats view. Configure the webhook URL in **Configuration**; filter by channel (Todos, WhatsApp, Instagram, Facebook); human override 24h and same UX as YCloud chats. Credentials (e.g. OPENAI_API_KEY, Chatwoot token) are stored per tenant (Vault).
- **Operations Center** (React SPA): Dashboard, agenda, patients, chats (unified YCloud + Chatwoot), analytics, staff approval, and configuration—all in one place, with real-time updates via Socket.IO.

---

## 🛠️ Technology Stack & Architecture

Dentalogic uses a **Sovereign Microservices Architecture**, designed to scale while keeping strict isolation per tenant.

### 🎨 Frontend (Operations Center)

| Layer | Technology |
|-------|------------|
| **Framework** | React 18 + TypeScript |
| **Build** | Vite (fast HMR & build) |
| **Styling** | Tailwind CSS |
| **Icons** | Lucide React |
| **Routing** | React Router DOM v6 (`path="/*"` for nested routes) |
| **State** | Context API (Auth, Language) + Axios (API with JWT + X-Admin-Token) |
| **i18n** | LanguageProvider + `useTranslation()` + `es.json` / `en.json` / `fr.json` |
| **Deployment** | Docker + Nginx (SPA mode) |

### ⚙️ Backend (The Core)

| Component | Technology |
|------------|------------|
| **Orchestrator** | FastAPI (Python 3.11+) – central brain, LangChain agent, Socket.IO server |
| **Add-ons** | Pydantic, Uvicorn (ASGI) |
| **Microservices** | `orchestrator_service`: main API, agent, calendar, tenants, auth; `whatsapp_service`: YCloud relay, Whisper transcription |

### 🗄️ Infrastructure & Persistence

| Layer | Technology |
|-------|------------|
| **Database** | PostgreSQL (clinical records, patients, appointments, tenants, professionals) |
| **Cache / Locks** | Redis (deduplication, context) |
| **Containers** | Docker & Docker Compose |
| **Deployment** | EasyPanel, Render, AWS ECS compatible |

### 🤖 Artificial Intelligence Layer

| Layer | Technology |
|-------|------------|
| **Orchestration** | LangChain + custom tools |
| **Primary model** | OpenAI **gpt-4o-mini** (default for agent and triage) |
| **Audio** | Whisper (symptom transcription) |
| **Tools** | `check_availability`, `book_appointment`, `list_services`, `list_professionals`, `list_my_appointments`, `cancel_appointment`, `reschedule_appointment`, `triage_urgency`, `derivhumano` |
| **Hybrid calendar** | Per-tenant: local (BD) or Google Calendar; JIT sync and collision checks |

### 🔐 Security & Authentication

| Mechanism | Description |
|-----------|-------------|
| **Auth** | JWT (login) + **X-Admin-Token** header for all `/admin/*` routes |
| **Multi-tenancy** | Strict `tenant_id` filter on every query; tenant resolved from JWT/DB, not from request params |
| **Credentials** | Google Calendar tokens stored encrypted (Fernet) when using connect-sovereign |
| **Passwords** | Bcrypt hashing; no plaintext in repo or UI (demo credentials shown as [REDACTED] on public pages) |

---

## 🧠 AI Models & Capabilities

| Model | Provider | Use case |
|-------|----------|----------|
| **gpt-4o-mini** | OpenAI | Default: agent conversation, triage, availability, booking |
| **Whisper** | OpenAI | Voice message transcription (symptoms) |

### Agent capabilities

- **Conversation:** Greeting, clinic identity, service selection (max 3 options when listing), availability check, slot offering, booking with patient data (name, DNI, insurance).
- **Triaje:** Urgency classification from symptoms (text or audio).
- **Human handoff:** `derivhumano` + 24h silence window per clinic/phone.
- **Multilingual:** Detects message language (es/en/fr) and responds in the same language; clinic name injected from `tenants.clinic_name`.

---

## 🚀 Key Features

### 🎯 Agent & Clinical Orchestration

- **Single AI brain** per clinic (or per tenant): books appointments, lists services and professionals, checks real availability (local or Google Calendar).
- **Canonical tool format** and retry on booking errors (“never give up a reservation”).
- **Tools:** `check_availability`, `book_appointment`, `list_services`, `list_professionals`, `list_my_appointments`, `cancel_appointment`, `reschedule_appointment`, `triage_urgency`, `derivhumano`.

### 📅 Smart Calendar (Hybrid by Clinic)

- **Per-tenant:** Local (DB only) or **Google Calendar**; `tenants.config.calendar_provider` + `google_calendar_id` per professional.
- **JIT sync:** External blocks mirrored to `google_calendar_blocks`; collision checks before create/update.
- **Real-time UI:** Socket.IO events (`NEW_APPOINTMENT`, `APPOINTMENT_UPDATED`, `APPOINTMENT_DELETED`).

### 👥 Patients & Clinical Records

- List, search, create, edit patients; optional “first appointment” on create.
- Clinical notes and evolution history; insurance status and context for chat view.

### 💬 Conversations (Chats)

- **Per clinic:** Sessions and messages filtered by `tenant_id`; CEO can switch clinic.
- **Context:** Last/upcoming appointment, treatment plan, human override and 24h window.
- **Actions:** Human intervention, remove silence, send message; click on derivation notification opens the right conversation.

### 📊 Analytics (CEO)

- Metrics per professional: appointments, completion rate, retention, estimated revenue.
- Filters by date range and professionals; dashboard and dedicated analytics view.

### 👔 Staff & Approvals (CEO)

- Registration with **clinic/sede** (GET `/auth/clinics`), specialty, phone, license; POST `/auth/register` creates pending user and `professionals` row.
- **Active Staff** as single source of truth: detail modal, “Link to clinic”, gear → Edit profile (sede, contact, availability).
- Scroll-isolated Staff view (Aprobaciones) for long lists on desktop and mobile.

### 🏢 Multi-Sede (Multi-Tenant)

- **Isolation:** Patients, appointments, chats, professionals, and configuration are separated by `tenant_id`. One clinic never sees another’s data.
- **CEO:** Can switch clinic in Chats and other views; manages approvals, clinics, and configuration per sede.
- **Staff:** Access only to their assigned clinic(s).

### 🌐 Internationalization (i18n)

- **UI:** Spanish, English, French. Set in **Configuration** (CEO); stored in `tenants.config.ui_language`; applies to login, menus, agenda, analytics, chats, and all main views.
- **WhatsApp agent:** Responds in the **language of the patient’s message** (auto-detect es/en/fr); independent of UI language.

### 🎪 Landing & Public Demo

- **Public page** at `/demo` (no login): value proposition, trial credentials (masked), and three CTAs: **Try app** (auto login to demo account), **Try AI agent** (WhatsApp with preset message), **Sign in**.
- **Demo login:** `/login?demo=1` with prefilled credentials and “Enter demo” button; mobile-first and conversion-oriented.

---

## 📁 Project Structure

```
Clinica Dental/
├── 📂 .agent/                    # Agent configuration & skills
│   ├── workflows/                # Autonomy, specify, plan, audit, update-docs, etc.
│   └── skills/                   # Backend, Frontend, DB, Prompt, Doc_Keeper, etc.
├── 📂 frontend_react/            # React 18 + Vite SPA (Operations Center)
│   ├── src/
│   │   ├── components/           # Layout, Sidebar, AppointmentForm, Modal, etc.
│   │   ├── views/                # Dashboard, Agenda, Patients, Chats, Landing, etc.
│   │   ├── context/              # AuthContext, LanguageContext
│   │   ├── locales/              # es.json, en.json, fr.json
│   │   └── api/                  # axios (JWT + X-Admin-Token)
│   ├── package.json
│   └── vite.config.ts
├── 📂 orchestrator_service/      # FastAPI Core (Orchestrator)
│   ├── main.py                   # App, /chat, /health, Socket.IO, LangChain agent & tools
│   ├── admin_routes.py           # /admin/* (patients, appointments, professionals, chat, tenants, etc.)
│   ├── auth_routes.py            # /auth/* (clinics, register, login, me, profile)
│   ├── db.py                     # Pool + Maintenance Robot (idempotent patches)
│   ├── gcal_service.py           # Google Calendar (hybrid calendar)
│   ├── analytics_service.py      # Professional metrics
│   └── requirements.txt
├── 📂 whatsapp_service/          # YCloud relay & Whisper
│   ├── main.py
│   └── ycloud_client.py
├── 📂 docs/                      # Documentation
│   ├── 01_architecture.md
│   ├── 02_environment_variables.md
│   ├── 03_deployment_guide.md
│   ├── 04_agent_logic_and_persona.md
│   ├── API_REFERENCE.md
│   ├── SPECS_IMPLEMENTADOS_INDICE.md
│   ├── 29_seguridad_owasp_auditoria.md
│   └── ...
├── 📂 db/init/                   # dentalogic_schema.sql
├── docker-compose.yml            # Local stack
└── README.md                     # This file
```

---

## 🚀 Deployment Guide (Quick Start)

Dentalogic follows a **clone and run** approach. With Docker you don’t need to install Python or Node locally.

### Prerequisites

- **Docker Desktop** (Windows/Mac) or **Docker Engine** (Linux)
- **Git**
- **OpenAI API Key** (required for the agent)
- **PostgreSQL** and **Redis** (or use `docker-compose`)

### Standard deployment (recommended)

**1. Clone the repository**

```bash
git clone <repository-url>
cd "Clinica Dental"
```

**2. Environment configuration**

```bash
cp dental.env.example .env
# Edit .env (see docs/02_environment_variables.md):
# - OPENAI_API_KEY
# - YCLOUD_API_KEY / YCLOUD_WEBHOOK_SECRET (WhatsApp)
# - POSTGRES_DSN / REDIS_URL
# - CLINIC_NAME, BOT_PHONE_NUMBER
# - GOOGLE_CREDENTIALS or connect-sovereign (optional)
# - ADMIN_TOKEN (for X-Admin-Token), JWT_SECRET_KEY
```

**3. Start services**

```bash
docker-compose up -d --build
```

**4. Access**

| Service | URL | Purpose |
|---------|-----|---------|
| **Orchestrator** | `http://localhost:8000` | Core API & agent |
| **Swagger UI** | `http://localhost:8000/docs` | OpenAPI contract; test with JWT + X-Admin-Token |
| **ReDoc / OpenAPI** | `http://localhost:8000/redoc`, `/openapi.json` | Read-only docs and JSON schema |
| **WhatsApp Service** | `http://localhost:8002` | YCloud relay & Whisper |
| **Operations Center** | `http://localhost:5173` | React UI (ES/EN/FR) |

---

## 📚 Documentation Hub

| Document | Description |
|----------|-------------|
| [**00. Documentation index**](docs/00_INDICE_DOCUMENTACION.md) | Master index of all 28 docs in `docs/` with short descriptions. |
| [**01. Architecture**](docs/01_architecture.md) | Microservices, Orchestrator, WhatsApp Service, hybrid calendar, Socket.IO. |
| [**02. Environment variables**](docs/02_environment_variables.md) | OPENAI, YCloud, PostgreSQL, Redis, Google, CREDENTIALS_FERNET_KEY, etc. |
| [**03. Deployment guide**](docs/03_deployment_guide.md) | EasyPanel, production configuration. |
| [**04. Agent logic & persona**](docs/04_agent_logic_and_persona.md) | Assistant persona, tools, conversation flow. |
| [**API Reference**](docs/API_REFERENCE.md) | All admin and auth endpoints; Swagger at `/docs`, ReDoc at `/redoc`. |
| [**13. Lead → Patient workflow**](docs/13_lead_patient_workflow.md) | From contact to patient and first appointment. |
| [**08. Troubleshooting**](docs/08_troubleshooting_history.md) | Common issues; “IA can’t see availability” (calendar). |
| [**29. Security (OWASP)**](docs/29_seguridad_owasp_auditoria.md) | OWASP Top 10 alignment, JWT + X-Admin-Token, multi-tenant security. |
| [**SPECS index**](docs/SPECS_IMPLEMENTADOS_INDICE.md) | Consolidated specs and where each feature is documented. |
| [**Context for AI agents**](docs/CONTEXTO_AGENTE_IA.md) | Entry point for another IA: stack, rules, API, DB, i18n. |
| [**Prompt for IA**](docs/PROMPT_CONTEXTO_IA_COMPLETO.md) | Copy-paste block for full project context in a new chat. |

---

## 🤝 Contributing

Development follows the project’s SDD workflows (specify → plan → implement) and **AGENTS.md** (sovereignty rules, scroll isolation, auth). For documentation changes, use the **Non-Destructive Fusion** protocol (see [update-docs](.agent/workflows/update-docs.md)). Do not run SQL directly; propose commands for the maintainer to run.

---

## 📜 Flujo del agente (resumen)

El asistente por WhatsApp sigue este orden: **saludo y nombre de la clínica** → **definir servicio** (máx. 3 si lista) → **(opcional) preferencia de profesional** → **check_availability** con duración del servicio → **ofrecer horarios** → **datos del paciente** → **book_appointment**. La duración se toma de la base de datos según el tratamiento; la disponibilidad depende de si la sede usa calendario local o Google. Detalle completo en [04. Agent logic](docs/04_agent_logic_and_persona.md) y en la sección “Flujo del agente” de la documentación.

---

## 📜 License

Sistema Dentalogic © 2026.
