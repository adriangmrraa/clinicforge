# 🏥 ClinicForge – Sovereign Clinical SaaS with Marketing Intelligence

**The first AI-driven Operating System for clinical practice management that connects patient care with advertising ROI.** Full-funnel attribution from Meta Ads click to appointment, multi-tenant data sovereignty, AI-powered triage, and true omnichannel (WhatsApp + Instagram + Facebook) — all in one platform.

`Python` `React` `TypeScript` `FastAPI` `LangChain` `Meta Graph API`

---

## 📋 Table of Contents

- [Vision & Value Proposition](#-vision--value-proposition)
- [📈 Meta Ads Analytics — Full-Funnel Traceability](#-meta-ads-analytics--full-funnel-traceability)
- [📱 True Omnichannel (WhatsApp + Chatwoot)](#-true-omnichannel-whatsapp--chatwoot)
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

ClinicForge is more than a chatbot: it is a **Digital Clinical Coordinator + Marketing Intelligence Platform** designed for clinics and clinic groups. Built on **Sovereignty**, **Multi-Tenancy**, and **Data-Driven Growth**, it delivers an AI-driven OS that manages appointments, triage, patient conversations, and **advertising ROI** — all while keeping each clinic's data strictly isolated.

### 🎯 For Whom

| Audience | Value |
|----------|--------|
| **Single clinics** | Centralize agenda, patients, WhatsApp conversations, and reports in one tool; know *exactly* which ad brought each patient. |
| **Clinic groups / franchises** | Each location (tenant) has its own data, calendar, and marketing analytics; the CEO sees all locations from one panel. Ideal for owners of 2+ clinics who want ROI clarity without mixing data. |
| **Marketing teams** | Measure real conversion (click → WhatsApp → appointment) per campaign, per ad, per audience. Stop guessing; start optimizing. |
| **Multilingual teams** | UI in **Spanish**, **English**, and **French**. The WhatsApp assistant auto-detects patient language. |

### 🛡️ Sovereign Data (Tenant-First)

Your data, your clinic, your keys. Every query is filtered by `tenant_id`. Identity is resolved from JWT and database (never from client-supplied tenant). Admin routes require **JWT + X-Admin-Token** so that a stolen token alone cannot access the API.

---

## 📈 Meta Ads Analytics — Full-Funnel Traceability

> **"Every peso you invest in Meta Ads is traceable from click to appointment."**

ClinicForge is the first clinical SaaS that closes the attribution loop between **Meta Ads** and your appointment book. Unlike generic CRMs that stop at "lead captured," ClinicForge tracks the *entire journey*:

```
📱 Patient sees your ad on Instagram/Facebook
    ↓
💬 Clicks → opens WhatsApp conversation  
    ↓  (referral data captured: ad_id, headline, body)
🤖 AI assistant greets with ad context ("¡Hola! Vi que te interesó nuestro blanqueamiento...")
    ↓
📅 Patient books an appointment
    ↓
📊 Dashboard shows: Ad #1847 → 12 leads → 8 appointments → 66% conversion
```

### 🎯 What You Can Measure

| Metric | Description | Where |
|--------|-------------|-------|
| **Leads per Campaign** | How many patients entered via each campaign | Marketing Dashboard |
| **Leads per Ad** | Granular: which specific ad creative drove the most contacts | Marketing Dashboard |
| **Ad → Appointment Conversion** | % of ad-sourced leads that actually booked an appointment | Marketing Dashboard |
| **Cost per Appointment (CPA)** | Cross-reference with Meta's spend data to get real CPA | Export + Spreadsheet |
| **Campaign Comparison** | Side-by-side ROI of "Blanqueamiento Verano" vs "Urgencias Nocturnas" | Marketing Dashboard |
| **Attribution Source** | `ORGANIC` vs `META_ADS` per patient — know exactly who came from paid ads | Patient Detail |
| **Ad Content Traceability** | The exact headline and body the patient saw before contacting you | Chat Context Card |
| **Intent Match** | Whether the patient's symptoms match the ad's promise (urgency ad + urgent symptoms = high match) | Triage System |

### 🔬 How Ad Testing Works

ClinicForge turns your clinic into an **A/B testing lab** for dental advertising:

1. **Create 2+ ads** in Meta Ads Manager targeting the same audience with different creatives
2. **Each ad click** is captured with its unique `ad_id`, `headline`, and `body`
3. **The dashboard** shows you, *per ad*:
   - How many patients it generated
   - How many of those patients booked appointments
   - The conversion rate (%)
4. **Kill underperforming ads** with confidence, not guesswork
5. **Scale winners** knowing the exact conversion funnel

### 💡 Real-World Examples

| Scenario | What ClinicForge Shows You |
|----------|---------------------------|
| You run 3 different ad creatives for "blanqueamiento" | Ad A: 15 leads, 10 appointments (67%). Ad B: 20 leads, 4 appointments (20%). Ad C: 8 leads, 7 appointments (88%). **→ Kill B, scale C.** |
| You want to know if "urgency" ads convert better | Filter by `meta_ad_headline` containing "dolor" or "urgencia" vs generic ads — compare conversion rates |
| You suspect one campaign is wasting budget | Dashboard shows Campaign X: 50 leads, 2 appointments (4%). **→ That campaign is burning money.** |
| You want to personalize the first message | The AI reads the ad headline and mentions it naturally: *"Vi que te interesó nuestro servicio de ortodoncia"* |

### 🏗️ Technical Architecture (for developers)

The attribution system uses a **First Touch** model:

1. **Webhook Capture**: When a patient clicks your ad and opens WhatsApp, YCloud sends referral data (`ad_id`, `headline`, `body`) via webhook
2. **First Touch Attribution**: The first ad that brings a patient is recorded permanently (subsequent ads don't overwrite)
3. **Async Enrichment**: A background task calls Meta Graph API to enrich the ad data with campaign names, using Redis cache (48h TTL) to avoid rate limits
4. **AI Context Injection**: The AI system prompt receives the ad context, enabling personalized greetings and urgency-aware triage
5. **Dashboard Aggregation**: `GET /admin/marketing/stats` aggregates leads and appointments per campaign/ad with conversion rates

> **Full technical documentation**: [`docs/meta_ads_backend.md`](docs/meta_ads_backend.md) | [`docs/meta_ads_database.md`](docs/meta_ads_database.md) | [`docs/meta_ads_frontend.md`](docs/meta_ads_frontend.md)

---

## 📱 True Omnichannel (WhatsApp + Chatwoot)

The AI lives where your patients are. ClinicForge connects to **three messaging channels** through a unified interface:

### Channels

| Channel | Integration | Capabilities |
|---------|-------------|-------------|
| **WhatsApp** | YCloud API (direct) | Full AI agent: booking, triage, human handoff. Whisper audio transcription. Meta Ads referral capture. |
| **Instagram DM** | Chatwoot relay | Receive and reply to Instagram messages from the same Chats view. AI agent processes conversations identically. |
| **Facebook Messenger** | Chatwoot relay | Same as Instagram — unified inbox with AI capabilities. |

### How It Works

```
Patient sends message via WhatsApp / Instagram / Facebook
    ↓
┌─────────────────────────────────────────────────┐
│  ClinicForge Orchestrator                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ WhatsApp  │  │Instagram │  │ Facebook │      │
│  │  (YCloud) │  │(Chatwoot)│  │(Chatwoot)│      │
│  └─────┬─────┘  └────┬─────┘  └────┬─────┘      │
│        └──────────────┼──────────────┘           │
│                       ↓                          │
│              🤖 AI Agent (Same brain)            │
│              📅 Same calendar                    │
│              👥 Same patient DB                  │
│              📊 Same analytics                   │
└─────────────────────────────────────────────────┘
    ↓
Operations Center shows ALL conversations in one unified view
(filter by: Todos | WhatsApp | Instagram | Facebook)
```

### Key Omnichannel Features (v1.1)

- **Unified Outgoing API**: A single endpoint `/admin/chat/send` handles all outgoing messages, automatically routing to YCloud or Chatwoot based on the platform.
- **Meta 24h Window Policy**: Continuous tracking of `last_user_message_at`. The system automatically blocks standard sessions after 24 hours of inactivity to comply with Meta's policy.
- **Re-engagement Flow**: Visual "Lock" indicators and banners guide operators to **Meta Templates** when the 24h window is closed.
- **Unified inbox**: All channels appear in the same Chats view with platform-specific badges and "Lock" icons for closed windows.
- **Channel filter**: Staff can filter conversations by channel (Todos, WhatsApp, Instagram, Facebook).
- **Same AI brain**: The LangChain agent processes messages identically regardless of source channel.
- **Human handoff**: `derivhumano` tool works across all channels with 24h silence window per clinic/phone.
- **Credential isolation**: Chatwoot tokens, OPENAI_API_KEY, and other secrets stored per-tenant (Vault).

---

## 🛠️ Technology Stack & Architecture

ClinicForge uses a **Sovereign Microservices Architecture**, designed to scale while keeping strict isolation per tenant.

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
| **Database** | PostgreSQL (clinical records, patients, appointments, tenants, professionals, Meta Ads attribution) |
| **Cache / Locks** | Redis (deduplication, context, Meta Ads enrichment cache) |
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
| **Ad-Aware AI** | System prompt enriched with Meta Ad context; urgency detection cross-referenced with ad intent |

### 🔐 Security & Authentication

| Mechanism | Description |
|-----------|-------------|
| **Auth** | JWT (login) + **X-Admin-Token** header for all `/admin/*` routes |
| **Multi-tenancy** | Strict `tenant_id` filter on every query; tenant resolved from JWT/DB, not from request params |
| **Credentials** | Google Calendar tokens stored encrypted (Fernet); Chatwoot/Meta tokens in Vault |
| **Passwords** | Bcrypt hashing; no plaintext in repo or UI |
| **Log sanitization** | Automatic redaction of tokens, API keys, and PII from log output |
| **Health checks** | `GET /admin/health/integrations` validates Meta API token and ad account status |

---

## 🧠 AI Models & Capabilities

| Model | Provider | Use case |
|-------|----------|----------|
| **gpt-4o-mini** | OpenAI | Default: agent conversation, triage, availability, booking |
| **Whisper** | OpenAI | Voice message transcription (symptoms) |

### Agent capabilities

- **Conversation:** Greeting, clinic identity, service selection (max 3 options when listing), availability check, slot offering, booking with patient data (name, DNI, insurance).
- **Triage:** Urgency classification from symptoms (text or audio). Ad-intent matching boosts urgency when patient symptoms align with the ad they clicked.
- **Human handoff:** `derivhumano` + 24h silence window per clinic/phone.
- **Multilingual:** Detects message language (es/en/fr) and responds in the same language; clinic name injected from `tenants.clinic_name`.
- **Ad-Aware:** When the patient came from a Meta Ad, the AI mentions the ad topic naturally and prioritizes clinical triage for urgency ads.

---

## 🚀 Key Features

### 🎯 Agent & Clinical Orchestration

- **Single AI brain** per clinic (or per tenant): books appointments, lists services and professionals, checks real availability (local or Google Calendar).
- **Canonical tool format** and retry on booking errors ("never give up a reservation").
- **Tools:** `check_availability`, `book_appointment`, `list_services`, `list_professionals`, `list_my_appointments`, `cancel_appointment`, `reschedule_appointment`, `triage_urgency`, `derivhumano`.

### 📅 Smart Calendar (Hybrid by Clinic)

- **Per-tenant:** Local (DB only) or **Google Calendar**; `tenants.config.calendar_provider` + `google_calendar_id` per professional.
- **JIT sync:** External blocks mirrored to `google_calendar_blocks`; collision checks before create/update.
- **Real-time UI:** Socket.IO events (`NEW_APPOINTMENT`, `APPOINTMENT_UPDATED`, `APPOINTMENT_DELETED`).

### 👥 Patients & Clinical Records

- List, search, create, edit patients; optional "first appointment" on create.
- Clinical notes and evolution history; insurance status and context for chat view.
- **Meta Ads badge**: Visual indicator on patient cards showing which patients came from paid ads, with tooltip showing the ad headline.

### 💬 Conversations (Chats)

- **Per clinic:** Sessions and messages filtered by `tenant_id`; CEO can switch clinic.
- **Context:** Last/upcoming appointment, treatment plan, human override and 24h window state.
- **Ad Context Card:** When a patient came from a Meta Ad, a card shows the ad headline and body at the top of the conversation for staff awareness.
- **Actions:** Human intervention, remove silence, unified messaging outlet; click on derivation notification opens the right conversation.
- **Meta Templates View**: Dedicated section for managing re-engagement campaigns and approved platform templates (upcoming).

### 📊 Analytics (CEO + Marketing)

- **Clinical Analytics**: Metrics per professional: appointments, completion rate, retention, estimated revenue. Filters by date range and professionals.
- **Marketing Performance Card** (Dashboard):
  - Total leads from Meta Ads
  - Total appointments from ad-sourced patients
  - Overall conversion rate (lead → appointment)
  - Per-campaign breakdown with ad headline detail
- **Investment Traceability**: Every patient is tagged with their `acquisition_source`. Cross-reference with Meta Ads Manager spend data to calculate real CPA per campaign.

### 👔 Staff & Approvals (CEO)

- Registration with **clinic/sede** (GET `/auth/clinics`), specialty, phone, license; POST `/auth/register` creates pending user and `professionals` row.
- **Active Staff** as single source of truth: detail modal, "Link to clinic", gear → Edit profile (sede, contact, availability).
- Scroll-isolated Staff view (Aprobaciones) for long lists on desktop and mobile.

### 🏢 Multi-Sede (Multi-Tenant)

- **Isolation:** Patients, appointments, chats, professionals, configuration, and **marketing data** are separated by `tenant_id`. One clinic never sees another's data or ad performance.
- **CEO:** Can switch clinic in Chats and other views; manages approvals, clinics, and configuration per sede.
- **Staff:** Access only to their assigned clinic(s).

### 🌐 Internationalization (i18n)

- **UI:** Spanish, English, French. Set in **Configuration** (CEO); stored in `tenants.config.ui_language`; applies to login, menus, agenda, analytics, chats, and all main views.
- **WhatsApp agent:** Responds in the **language of the patient's message** (auto-detect es/en/fr); independent of UI language.

### 🎪 Landing & Public Demo

- **Public page** at `/demo` (no login): value proposition, trial credentials (masked), and three CTAs: **Try app** (auto login to demo account), **Try AI agent** (WhatsApp with preset message), **Sign in**.
- **Demo login:** `/login?demo=1` with prefilled credentials and "Enter demo" button; mobile-first and conversion-oriented.

---

## 📁 Project Structure

```
ClinicForge/
├── 📂 frontend_react/            # React 18 + Vite SPA (Operations Center)
│   ├── src/
│   │   ├── components/           # Layout, Sidebar, MarketingPerformanceCard, AdContextCard, Vault components, etc.
│   │   ├── views/                # Dashboard, Agenda, Patients, Chats, MetaTemplatesView, ConfigView, Landing, etc.
│   │   ├── context/              # AuthContext, LanguageContext
│   │   ├── locales/              # es.json, en.json, fr.json
│   │   └── api/                  # axios (JWT + X-Admin-Token)
│   ├── package.json
│   └── vite.config.ts
├── 📂 orchestrator_service/      # FastAPI Core (Orchestrator)
│   ├── main.py                   # App, /chat, /health, Socket.IO, LangChain agent & tools
│   ├── admin_routes.py           # /admin/* (patients, appointments, marketing, health, etc.)
│   ├── auth_routes.py            # /auth/* (clinics, register, login, me, profile)
│   ├── db.py                     # Pool + Maintenance Robot (idempotent patches)
│   ├── gcal_service.py           # Google Calendar (hybrid calendar)
│   ├── analytics_service.py      # Professional metrics
│   ├── core/
│   │   └── log_sanitizer.py      # Sensitive data redaction in logs
│   ├── services/
│   │   ├── meta_ads_service.py   # Meta Graph API client (ad enrichment)
│   │   └── tasks.py              # Background tasks (Redis cache + enrichment)
│   ├── scripts/
│   │   └── check_meta_health.py  # Meta Ads health check (CLI + API)
│   └── requirements.txt
├── 📂 whatsapp_service/          # YCloud relay & Whisper
│   ├── main.py
│   ├── ycloud_client.py          # Unified WhatsApp messaging client
│   └── chatwoot_client.py        # Meta/Omnichannel messaging client
├── 📂 shared/                    # Shared Pydantic models
├── 📂 docs/                      # Documentation (30+ files)
│   ├── meta_ads_backend.md       # Meta Ads backend architecture & data flow
│   ├── meta_ads_frontend.md      # Meta Ads frontend components & integration
│   ├── meta_ads_database.md      # Meta Ads DB schema & queries
│   ├── meta_ads_audit_*.md       # Pre-deployment audit reports
│   ├── API_REFERENCE.md          # Full API contract
│   └── ...
├── 📂 db/init/                   # dentalogic_schema.sql
├── docker-compose.yml            # Local stack
├── .gitignore
└── README.md                     # This file
```

---

## 🚀 Deployment Guide (Quick Start)

ClinicForge follows a **clone and run** approach. With Docker you don't need to install Python or Node locally.

### Prerequisites

- **Docker Desktop** (Windows/Mac) or **Docker Engine** (Linux)
- **Git**
- **OpenAI API Key** (required for the agent)
- **PostgreSQL** and **Redis** (or use `docker-compose`)

### Standard deployment (recommended)

**1. Clone the repository**

```bash
git clone https://github.com/adriangmrraa/clinicforge.git
cd clinicforge
```

**2. Environment configuration**

```bash
cp dental.env.example .env
# Edit .env (see docs/02_environment_variables.md):
# - OPENAI_API_KEY
# - YCLOUD_API_KEY / YCLOUD_WEBHOOK_SECRET (WhatsApp)
# - POSTGRES_DSN / REDIS_URL
# - CLINIC_NAME, BOT_PHONE_NUMBER
# - META_ADS_TOKEN (for ad enrichment — optional)
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
| [**00. Documentation index**](docs/00_INDICE_DOCUMENTACION.md) | Master index of all docs in `docs/` with short descriptions. |
| [**01. Architecture**](docs/01_architecture.md) | Microservices, Orchestrator, WhatsApp Service, hybrid calendar, Socket.IO. |
| [**02. Environment variables**](docs/02_environment_variables.md) | OPENAI, YCloud, PostgreSQL, Redis, Google, Meta Ads, CREDENTIALS_FERNET_KEY, etc. |
| [**03. Deployment guide**](docs/03_deployment_guide.md) | EasyPanel, production configuration. |
| [**04. Agent logic & persona**](docs/04_agent_logic_and_persona.md) | Assistant persona, tools, conversation flow. |
| [**Meta Ads — Backend**](docs/meta_ads_backend.md) | Full architecture, data flow, endpoints, security, environment variables. |
| [**Meta Ads — Frontend**](docs/meta_ads_frontend.md) | Components, interfaces, integration points. |
| [**Meta Ads — Database**](docs/meta_ads_database.md) | Migration, schema, queries, rollback, performance. |
| [**Meta Ads — Audit**](docs/meta_ads_audit_2026-02-16.md) | Pre-deployment audit: bugs found, checklists, recommendations. |
| [**API Reference**](docs/API_REFERENCE.md) | All admin and auth endpoints; Swagger at `/docs`, ReDoc at `/redoc`. |
| [**13. Lead → Patient workflow**](docs/13_lead_patient_workflow.md) | From contact to patient and first appointment. |
| [**29. Security (OWASP)**](docs/29_seguridad_owasp_auditoria.md) | OWASP Top 10 alignment, JWT + X-Admin-Token, multi-tenant security. |
| [**SPECS index**](docs/SPECS_IMPLEMENTADOS_INDICE.md) | Consolidated specs and where each feature is documented. |

---

## 🤝 Contributing

Development follows the project's SDD workflows (specify → plan → implement) and **AGENTS.md** (sovereignty rules, scroll isolation, auth). For documentation changes, use the **Non-Destructive Fusion** protocol (see [update-docs](.agent/workflows/update-docs.md)). Do not run SQL directly; propose commands for the maintainer to run.

---

## 📜 Agent Flow (Summary)

The WhatsApp assistant follows this order: **greeting + clinic name** → **define service** (max 3 if listing) → **(optional) professional preference** → **check_availability** with service duration → **offer time slots** → **patient data** → **book_appointment**. Duration is taken from the database per treatment; availability depends on whether the clinic uses local or Google calendar. Full detail in [04. Agent logic](docs/04_agent_logic_and_persona.md).

When the patient comes from a **Meta Ad**, the assistant adapts: for urgency ads, it prioritizes triage over data capture; for general ads, it personalizes the greeting mentioning the ad topic.

---

## 📜 License

ClinicForge © 2026. All rights reserved.
