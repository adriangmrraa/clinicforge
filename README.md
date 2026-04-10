# 🏥 ClinicForge – Sovereign Clinical SaaS with Marketing Intelligence

**The first AI-driven Operating System for clinical practice management that connects patient care with advertising ROI.** Full-funnel attribution from Meta Ads click to appointment, multi-tenant data sovereignty, AI-powered triage, and true omnichannel (WhatsApp + Instagram + Facebook) — all in one platform.

`Python` `React` `TypeScript` `FastAPI` `LangChain` `pgvector` `Meta Graph API`

---

## 📋 Table of Contents

- [Vision & Value Proposition](#-vision--value-proposition)
- [📈 Meta Ads Analytics — Full-Funnel Traceability](#-meta-ads-analytics--full-funnel-traceability)
- [📱 True Omnichannel (WhatsApp + Chatwoot)](#-true-omnichannel-whatsapp--chatwoot)
- [🧠 Dual-Engine AI Architecture](#-dual-engine-ai-architecture)
- [🎙️ Nova — AI Voice Assistant](#️-nova--ai-voice-assistant)
- [💰 Payment Verification System](#-payment-verification-system)
- [Technology Stack & Architecture](#-technology-stack--architecture)
- [AI Models & Capabilities](#-ai-models--capabilities)
- [Key Features](#-key-features)
- [RAG System — Semantic FAQ Search](#-rag-system--semantic-faq-search)
- [ROI Dashboard — Real Attribution Analytics](#-roi-dashboard--real-attribution-analytics)
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

### 🛡️ Sovereign Data & Security (Nexus v8.0)

ClinicForge implementa un protocolo de **Endurecimiento Proactivo** para proteger la integridad clínica:
- **Aislamiento de Datos**: Cada query está filtrada por `tenant_id`. La identidad se resuelve desde el JWT y la base de datos (nunca desde parámetros del cliente).
- **Security Headers**: Middleware nativo para HSTS, CSP dinámico, X-Frame-Options (Anti-Clickjacking) y X-Content-Type-Options.
- **AI Guardrails**: Capa de protección híbrida que detecta y bloquea intentos de Prompt Injection antes de que lleguen al modelo.
- **Sanitización XSS**: Uso obligatorio de `DOMPurify` en el frontend para renderizar contenido dinámico de forma segura.
- **Auth de Infraestructura**: Las rutas administrativas requieren **JWT + X-Admin-Token** para prevenir accesos no autorizados incluso con tokens comprometidos.
- **Rate Limiting**: Login (5/min), register (3/min), expensive endpoints (10/min) via slowapi.
- **SSRF Protection**: Media proxy blocks private IPs, localhost, and cloud metadata endpoints.
- **File Upload Validation**: Extension whitelist (jpg/png/gif/webp/pdf) + 10MB size limit.
- **Path Traversal Protection**: Document proxy validates resolved paths within allowed directories.
- **PII Protection**: Patient IDs hashed in audit logs. No email/IP in log output.

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
4. **AI Context Injection**: The AI system prompt receives the ad context, enabling **personalized greetings** (e.g., "Vi que te interesa ortodoncia") and **urgency-aware triage** (prioritizing patients from "Urgencia 24h" ads).
5. **Dashboard Aggregation**: `GET /admin/marketing/stats` aggregates leads and appointments per campaign/ad with conversion rates.
6. **Master Ad List Strategy**: To handle Meta Graph API limitations, ClinicForge uses a two-step fetch (Ads + Insights) ensuring **100% ad visibility**, even for ads with 0 spend.

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

### Key Omnichannel Features (v2.0 - Stable)

- **Unified Outgoing API**: A single endpoint `/admin/chat/send` handles everything. It automatically routes to **YCloud** (direct WhatsApp) or **Chatwoot** (IG/FB) based on the conversation provider.
- **Robust Deduplication**: Logic to prevent "echo" messages and double-posting, using `provider_message_id` tracking for both Chatwoot and YCloud.
- **Meta 24h Window Policy**: Continuous tracking of `last_user_message_at`. The system automatically **blocks standard messaging** after 24 hours of inactivity, protecting your Meta account and guiding operators to use HSM templates for re-engagement.
- **Re-engagement Flow**: Visual "Lock" indicators and banners guide operators to **Meta Templates** when the 24h window is closed.
- **Unified inbox**: All channels appear in the same Chats view with platform-specific badges and real-time updates via **Socket.IO**.
- **Same AI brain**: The LangChain agent processes messages identically regardless of source channel, maintaining context across platforms.
- **Human handoff**: `derivhumano` tool works across all channels with 24h silence window per clinic/phone, synchronizing state between DB and UI.
- **Credential isolation**: Chatwoot tokens, YCloud Keys, and OPENAI_API_KEY stored per-tenant (Vault).

---

## 🧠 Dual-Engine AI Architecture

ClinicForge supports **two independent conversational AI engines** per tenant. The CEO selects which one to use from the Settings UI.

### Engines

| Engine | Key | Description |
|--------|-----|-------------|
| **SoloEngine** | `solo` | Monolithic LangChain agent (TORA) with all `DENTAL_TOOLS`. Hardened with state-lock + date validator. **Default for all tenants.** |
| **MultiAgentEngine** | `multi` | Supervisor + 6 specialized agents with shared `PatientContext`. Opt-in per tenant. |

### Multi-Agent Specialists

| Agent | Responsibility | Tools Subset |
|-------|---------------|-------------|
| **Reception** | Greetings, service info, general queries | `list_services`, `list_professionals` |
| **Booking** | Availability, slot confirmation, scheduling | `check_availability`, `confirm_slot`, `book_appointment`, `reschedule_appointment`, `cancel_appointment` |
| **Triage** | Symptom analysis, urgency classification | `triage_urgency` |
| **Billing** | Payment verification, pricing queries | `verify_payment_receipt` |
| **Anamnesis** | Medical history collection | `save_patient_anamnesis`, `get_patient_anamnesis` |
| **Handoff** | Human escalation | `derivhumano` |

### Routing & Safety

- **Engine Router** (`services/engine_router.py`): reads `tenants.ai_engine_mode` (cached 60s, invalidated via Redis pubsub on settings change)
- **Circuit Breaker**: 3 consecutive multi-agent failures within 60s → automatic fallback to solo engine for 5 minutes
- **CEO Toggle**: Settings UI → general tab → only visible to `role === 'ceo'`. Requires passing `GET /admin/ai-engine/health` (probes both engines in parallel) before switching
- **Supervisor**: Deterministic regex rules first (emergency/billing/anamnesis/handoff/booking/greeting), LLM fallback. Max 5 hops per turn, 45s timeout
- **Dynamic Model**: Both engines read from `system_config.OPENAI_MODEL` — never hardcoded. Supports **DeepSeek** models (`deepseek-chat`, `deepseek-reasoner`) with auto API key/base URL switch

---

## 🎙️ Nova — AI Voice Assistant (Jarvis for Clinics)

Nova is the voice-powered AI copilot that runs inside ClinicForge. Available as a floating widget on every page, it uses OpenAI Realtime API for bidirectional audio + function calling.

**50 tools** organized in 11 categories:

| Category | Tools | Examples |
|----------|-------|---------|
| **Patients** | 7 | Search, register, update, clinical history, delete |
| **Appointments** | 9 | View schedule, book, cancel, reschedule, block agenda |
| **Billing** | 3 | Register payments, list treatments, pending invoices |
| **Analytics** | 5 | Weekly summary, professional performance, financial reports |
| **Navigation** | 2 | Navigate to any page, open patient record |
| **Multi-sede CEO** | 4 | Compare locations, switch active clinic, onboarding status |
| **Staff Operations** | 10 | Manage professionals, config, FAQs, send WhatsApp messages |
| **Anamnesis** | 2 | Voice-guided medical history intake |
| **Odontogram** | 2 | View and modify dental chart with surgical safety rules |
| **RAG** | 1 | Search knowledge base semantically |
| **Data Access (CRUD)** | 5 | Natural language queries, generic CRUD on any table |

**Key capabilities:**
- Execute tools first, talk after (Jarvis principle)
- Chain 2-3 tools without asking for confirmation
- All actions emit Socket.IO events for real-time UI sync
- Omnichannel messaging: send WhatsApp, Instagram, Facebook messages by patient name
- Automated daily insights every 12 hours (conversation analysis + recommendations)

---

## 💰 Payment Verification System

Automated payment receipt verification via WhatsApp:

1. Patient sends bank transfer receipt photo
2. AI vision service analyzes the image
3. `verify_payment_receipt` tool verifies:
   - Bank account holder name matches clinic's configuration
   - Amount matches expected seña (50% of professional's consultation price)
   - Accepts overpayment (notes excess), calculates underpayment (shows remaining)
4. On success: appointment auto-confirmed, receipt stored in billing tab
5. On failure: explains what's wrong, asks for corrected receipt

**Features:**
- Partial payment accumulation (multiple receipts sum up)
- Receipt visible in patient's document gallery (green "Comprobante de Pago" badge)
- Receipt visible in appointment's billing tab with verification status
- Real-time Socket.IO events update all connected clients

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
| **BFF Service** | Express + Axios (Node.js) – reverse proxy between Frontend and Orchestrator |
| **Add-ons** | Pydantic, Uvicorn (ASGI) |
| **Microservices** | `orchestrator_service`: main API, agent, calendar, tenants, auth, **relay (buffer)**; `bff_service`: Express proxy (CORS, timeout 60s); `whatsapp_service`: YCloud relay, Whisper transcription |

### 🗄️ Infrastructure & Persistence

| Layer | Technology |
|-------|------------|
| **Database** | PostgreSQL 13+ with **pgvector** extension (clinical records, patients, appointments, tenants, professionals, Meta Ads attribution, FAQ embeddings) |
| **ORM & Migrations** | SQLAlchemy 2.0 (**44 model classes**) + **Alembic** (**43 versioned schema migrations**, auto-run on startup) |
| **Cache / Locks** | Redis (deduplication, context, Meta Ads enrichment cache, lead context accumulator, slot soft-locks) |
| **Containers** | Docker & Docker Compose |
| **Deployment** | EasyPanel, Render, AWS ECS compatible |

### 🤖 Artificial Intelligence Layer

| Layer | Technology |
|-------|------------|
| **Orchestration** | LangChain + custom tools (Solo) / LangGraph Supervisor (Multi-Agent) |
| **Primary model** | Configurable via `system_config` table — default **gpt-4o-mini**; supports **DeepSeek** auto-detection |
| **Audio** | Whisper (symptom transcription) |
| **Tools** | 16 tools: `check_availability`, `confirm_slot`, `book_appointment`, `list_services`, `list_professionals`, `list_my_appointments`, `cancel_appointment`, `reschedule_appointment`, `triage_urgency`, `save_patient_anamnesis`, `get_patient_anamnesis`, `save_patient_email`, `verify_payment_receipt`, `get_treatment_instructions`, `set_no_followup`, `derivhumano` |
| **Hybrid calendar** | Per-tenant: local (BD) or Google Calendar; JIT sync and collision checks |
| **Ad-Aware AI** | System prompt enriched with Meta Ad context; urgency detection cross-referenced with ad intent |
| **RAG (Semantic Search)** | pgvector + OpenAI `text-embedding-3-small` (1536 dims); semantic FAQ retrieval replaces static injection; fallback to first-20 FAQs if pgvector unavailable |
| **Token Tracking** | Per-conversation usage tracking via `dashboard/token_tracker.py`; model selection from `system_config` table in admin UI |

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
| **DeepSeek** | DeepSeek | Alternative: `deepseek-chat` / `deepseek-reasoner` (auto-detected, switches API key + base URL) |
| **Whisper** | OpenAI | Voice message transcription (symptoms) |
| **gpt-4o-realtime** | OpenAI | Nova voice assistant (configurable: mini or premium) |

### Agent Capabilities

- **Conversation:** Greeting, clinic identity, service selection (max 3 options when listing), availability check, slot offering, booking with patient data (name, DNI, insurance).
- **Slot Confirmation:** `confirm_slot` soft-locks a time slot for 30 seconds via Redis before collecting patient data, preventing double-booking.
- **Triage:** Urgency classification from symptoms (text or audio). Ad-intent matching boosts urgency when patient symptoms align with the ad they clicked. **Implant/prosthesis commercial triage** with 6 emoji options flow for specialized positioning.
- **Human handoff:** `derivhumano` + 24h silence window per clinic/phone + comprehensive email notification to clinic & professionals.
- **Multilingual:** Detects message language (es/en/fr) and responds in the same language; clinic name injected from `tenants.clinic_name`.
- **Ad-Aware:** When the patient came from a Meta Ad, the AI mentions the ad topic naturally and prioritizes clinical triage for urgency ads.
- **Differentiated Greeting:** 3-tier based on patient status — new lead ("¿En qué tipo de consulta estás interesado?"), patient without appointment ("¿En qué podemos ayudarte hoy?"), patient with upcoming appointment (personalized mention + sede).

### Third-Party & Minor Booking

The AI supports booking appointments for others:

| Scenario | Flow | Phone Handling |
|----------|------|---------------|
| **For self** | Standard flow, no extra params | Interlocutor's phone |
| **For adult third party** | Agent asks for third party's phone | `patient_phone` param creates separate patient record |
| **For minor (child)** | Agent does NOT ask for phone | Auto-generated as `parent_phone-M{N}` (e.g., `+549111-M1`) |

- `guardian_phone` column links minors to their parent/guardian
- The interlocutor's patient name is **never overwritten** when booking for someone else
- AI context includes all linked minors with anamnesis links and next appointments

### Public Anamnesis Form

Unique mobile-optimized checklist form per patient at `/anamnesis/{tenant_id}/{token}`:
- Token is a UUID in `patients.anamnesis_token`
- Public endpoints `GET/POST /public/anamnesis/{tenant_id}/{token}` (no auth required)
- **Smart send behavior**: AI sends the link automatically after booking ONLY if `anamnesis_completed_at` is null. If already completed, only sends when patient explicitly asks
- Pre-fills existing data so patients can edit without re-entering everything

### Date Parsing System

`parse_date()` uses a 7-layer priority for robust Spanish date interpretation:
1. Exact shortcuts (`hoy`, `mañana`, `pasado mañana`)
2. ASAP/no preference (`lo antes posible`, `cualquier día`)
3. `dateutil` fuzzy parsing (`30 de abril`, `jueves 30 de abril`)
4. Month expressions (`fines de abril`, `mitad de julio`)
5. Weekday only (`jueves`, `lunes`)
6. Relative phrases (`próxima semana`, `mes que viene`)
7. Fallback: `None` (never invents dates)

### Lead Context Accumulator

Redis HSET (`lead_ctx:{tenant_id}:{phone}`) that persists lead data across conversation turns before they become patients. Captures name fragments, service interest, insurance mentions, and preferred schedule — so the AI doesn't re-ask questions the patient already answered in a previous message.

---

## 🚀 Key Features

### 🎯 Agent & Clinical Orchestration

- **Dual-engine architecture** per clinic: SoloEngine (monolithic TORA) or MultiAgentEngine (supervisor + 6 specialists) — CEO selects via UI.
- **16 AI tools** for the WhatsApp/web agent: booking, triage, anamnesis, payment verification, slot soft-lock, human handoff, and more.
- **Canonical tool format** and retry on booking errors ("never give up a reservation").

### 📅 Smart Calendar (Hybrid by Clinic)

- **Per-tenant:** Local (DB only) or **Google Calendar**; `tenants.config.calendar_provider` + `google_calendar_id` per professional.
- **JIT sync:** External blocks mirrored to `google_calendar_blocks`; collision checks before create/update.
- **Real-time UI:** Socket.IO events (`NEW_APPOINTMENT`, `APPOINTMENT_UPDATED`, `APPOINTMENT_DELETED`).

### 🏥 Multi-Sede (Location per Day)

- Each clinic can operate from **different locations depending on the day of the week**, configured in `tenants.working_hours` JSONB with per-day `location`, `address`, and `maps_url`
- Professionals can optionally override location per day in their own `working_hours`
- **Resolution chain**: professional.working_hours[day].location → tenant.working_hours[day].location → tenant.address (fallback)
- AI includes the correct sede + Google Maps link in appointment confirmations
- `check_availability` reads per-day time slots (not env vars) and returns "clinic closed" for disabled days

### 👥 Patients & Clinical Records

- List, search, create, edit patients; optional "first appointment" on create.
- Clinical notes and evolution history; insurance status and context for chat view.
- **Meta Ads badge**: Visual indicator on patient cards showing which patients came from paid ads, with tooltip showing the ad headline.
- **Bulk Import (CSV/XLSX)**: Two-step flow via `POST /admin/patients/import/preview` → `POST /admin/patients/import/execute`. Auto-encoding detection (UTF-8 → latin-1 fallback), column alias mapping (Spanish headers → DB fields), max 1000 rows, duplicate detection by phone with skip/update choice. Frontend drag & drop modal with preview.

### 🩺 Treatment-Professional Assignment

- Many-to-many relationship via `treatment_type_professionals` junction table
- Each treatment can be assigned to specific professionals
- **Backward compatibility**: if a treatment has no professionals assigned, ALL active professionals can perform it
- AI tools (`check_availability`, `book_appointment`, `list_services`) all respect this rule
- Managed via `GET/PUT /admin/treatment-types/{code}/professionals` endpoints
- **Per-professional price override**: `professionals.consultation_price` takes precedence over `tenants.consultation_price`

### 💬 Conversations (Chats)

- **Per clinic:** Sessions and messages filtered by `tenant_id`; CEO can switch clinic.
- **Context:** Last/upcoming appointment, treatment plan, human override and 24h window state.
- **Ad Context Card:** When a patient came from a Meta Ad, a card shows the ad headline and body at the top of the conversation for staff awareness.
- **Actions:** Human intervention, remove silence, unified messaging outlet; click on derivation notification opens the right conversation.
- **Meta Templates View**: Dedicated section for managing re-engagement campaigns and approved platform templates (HSM).

### 🤖 Sistema de Jobs Programados (Modular)

ClinicForge cuenta con un motor de tareas en segundo plano (`orchestrator_service/jobs/`) que gestiona procesos proactivos para maximizar la conversión y retención:

- **Lead Recovery v2 (3-Touch Intelligent)**: Sistema de 3 contactos progresivos — Touch 1 (2h): mensaje contextual basado en interés detectado. Touch 2 (24h): propuesta de turnos reales de la agenda. Touch 3 (72h): último intento con oferta de valor. Análisis IA del historial completo de la conversación para personalizar cada touch.
- **Appointment Reminders**: Envía recordatorios vía WhatsApp HSM **24 horas antes** del turno. Soporta reinicio automático si el paciente reprograma.
- **Post-Treatment Followups**: Seguimiento clínico **45 minutos** o **24 horas** después de tratamientos complejos/cirugías para evaluar síntomas vía Triage IA.
- **Audit Logs**: Registro completo de cada ejecución visible en el panel de **Automatizaciones & HSM**.

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

### 🏢 Multi-Tenant Isolation

- **Isolation:** Patients, appointments, chats, professionals, configuration, and **marketing data** are separated by `tenant_id`. One clinic never sees another's data or ad performance.
- **CEO:** Can switch clinic in Chats and other views; manages approvals, clinics, and configuration per sede.
- **Staff:** Access only to their assigned clinic(s).

### 🌐 Internationalization (i18n) & UX Premium

- **UI Multilingüe**: Interfaz completa en **Español**, **Inglés** y **Francés**, gestionada mediante `LanguageProvider` y traducción dinámica.
- **Diseño Dark Glass**: Estética premium con aislamiento de scroll, componentes de `Lucide React` y layouts adaptativos (Mobile First).
- **WhatsApp agent**: Detecta el idioma del mensaje del paciente (es/en/fr) y responde en consecuencia de forma agnóstica a la configuración de la clínica.

### 🎪 Landing & Public Demo

- **Public page** at `/demo` (no login): value proposition, trial credentials (masked), and three CTAs: **Try app** (auto login to demo account), **Try AI agent** (WhatsApp with preset message), **Sign in**.
- **Demo login:** `/login?demo=1` with prefilled credentials and "Enter demo" button; mobile-first and conversion-oriented.

---

## 🧠 RAG System — Semantic FAQ Search

ClinicForge uses **Retrieval-Augmented Generation (RAG)** to make the AI agent smarter about clinic-specific knowledge:

```
Patient message: "cuánto cuesta una limpieza?"
    ↓
OpenAI Embedding (text-embedding-3-small) → vector [1536 dims]
    ↓
pgvector cosine similarity search → faq_embeddings WHERE tenant_id = $X
    ↓
Top-5 most relevant FAQs injected into system prompt
    ↓
AI responds with accurate, clinic-specific pricing
```

**Key benefits:**
- **Token efficiency**: Only relevant FAQs are injected (5 vs 20), saving ~500 tokens/request
- **Scalability**: Works with 100+ FAQs per tenant (no hard limit of 20)
- **Accuracy**: Semantic matching finds relevant FAQs even with different wording
- **Zero-downtime fallback**: If pgvector isn't available, falls back to static FAQ injection
- **Auto-sync**: Embeddings auto-generate when FAQs are created/updated/deleted
- **Nova integration**: Voice assistant can search the knowledge base on-demand via `buscar_en_base_conocimiento` tool

---

## 📊 ROI Dashboard — Real Attribution Analytics

A dedicated dashboard (`/roi`) that consolidates marketing ROI with real data:

| KPI | Source |
|-----|--------|
| **Total Spend** | Meta Ads API (real) or estimation if no token |
| **Total Revenue** | `appointments.billing_amount` (paid/partial) or `consultation_price × patients` |
| **ROI %** | `((revenue - spend) / spend) × 100` |
| **Leads / Conversions** | `patients WHERE acquisition_source = 'META_ADS'` + appointments |
| **Cost per Lead** | `spend / leads` |
| **Attribution Mix** | First Touch / Last Touch / Conversion / Organic (%) |

**Transparency**: Every response includes `data_source: "meta_api" | "estimated"` so the UI shows a badge indicating whether data is real or estimated.

**8 API endpoints** at `/admin/metrics/*`: executive-summary, campaigns, roi/dashboard, attribution/mix, trend, top/campaigns, comparison/first-vs-last, attribution/report.

---

## 📁 Project Structure

```
ClinicForge/
├── 📂 frontend_react/            # React 18 + Vite SPA (Operations Center)
│   ├── src/
│   │   ├── components/           # Layout, Sidebar, GlassCard, NovaWidget, etc.
│   │   ├── views/                # Dashboard, Agenda, Patients, Chats, ROIDashboard, Config, etc.
│   │   ├── context/              # AuthContext, LanguageContext
│   │   ├── locales/              # es.json, en.json, fr.json
│   │   └── api/                  # axios (JWT + X-Admin-Token)
│   ├── package.json
│   └── vite.config.ts
├── 📂 orchestrator_service/      # FastAPI Core (Orchestrator)
│   ├── main.py                   # App, /chat, /health, Socket.IO, LangChain agent & 16 tools
│   ├── admin_routes.py           # /admin/* (patients, appointments, marketing, health, etc.)
│   ├── public_routes.py          # /public/* (anamnesis form — no auth)
│   ├── auth_routes.py            # /auth/* (clinics, register, login, me, profile)
│   ├── db.py                     # Async connection pool (asyncpg)
│   ├── models.py                 # SQLAlchemy ORM models (44 classes)
│   ├── agents/                   # Multi-Agent Engine
│   │   ├── supervisor.py         # Deterministic routing + LLM fallback
│   │   ├── specialists.py        # 6 specialized agents (Reception, Booking, Triage, etc.)
│   │   ├── graph.py              # LangGraph entry point, run_turn(), probe()
│   │   ├── model_resolver.py     # Dynamic model selection per tenant
│   │   ├── state.py              # AgentState schema
│   │   └── base.py               # BaseAgent class
│   ├── routes/                   # Modular route blueprints
│   │   ├── ai_engine_health.py   # Dual-engine health check
│   │   ├── metrics.py            # /admin/metrics/* (ROI, attribution, trends)
│   │   ├── nova_routes.py        # Nova REST endpoints
│   │   ├── digital_records.py    # Clinical records API
│   │   ├── leads.py              # Lead management
│   │   ├── marketing.py          # Marketing routes
│   │   └── chat_api.py           # Chat API routes
│   ├── services/                 # Business logic layer
│   │   ├── engine_router.py      # Solo/Multi engine routing + circuit breaker
│   │   ├── buffer_task.py        # Message buffer + AI dispatch (hook point)
│   │   ├── patient_context.py    # PatientContext loader (Profile + Working layers)
│   │   ├── lead_context.py       # Lead Context Accumulator (Redis HSET)
│   │   ├── meta_ads_service.py   # Meta Graph API client
│   │   ├── embedding_service.py  # RAG: pgvector embeddings
│   │   ├── metrics_service.py    # Unified attribution metrics
│   │   ├── nova_tools.py         # 50 Nova voice tools
│   │   ├── nova_daily_analysis.py # Automated daily insights
│   │   └── ...                   # 30+ service modules
│   ├── jobs/                     # Modular background jobs system
│   │   ├── lead_recovery.py      # 3-touch intelligent lead recovery
│   │   ├── reminders.py          # Proactive appointment reminders
│   │   └── followups.py          # Clinical post-op followups
│   ├── dashboard/                # Admin dashboard utilities
│   │   ├── config_manager.py     # Dynamic AI model config (system_config table)
│   │   └── token_tracker.py      # Token usage tracking per conversation
│   ├── alembic/                  # Database migrations
│   │   ├── env.py                # DSN normalization (asyncpg → psycopg2)
│   │   └── versions/             # 43 migration scripts (001 baseline → 043 lead_recovery_v2)
│   ├── start.sh                  # Startup: alembic upgrade head → uvicorn
│   └── requirements.txt
├── 📂 bff_service/               # Backend-for-Frontend (Express proxy)
│   ├── src/index.ts              # Reverse proxy: Frontend → Orchestrator
│   ├── package.json
│   └── Dockerfile
├── 📂 whatsapp_service/          # YCloud relay & Whisper
│   ├── main.py
│   ├── ycloud_client.py          # Unified WhatsApp messaging client
│   └── chatwoot_client.py        # Meta/Omnichannel messaging client
├── 📂 shared/                    # Shared Pydantic models
├── 📂 docs/                      # Documentation (30+ files)
├── 📂 db/init/                   # Legacy schema (baseline now in Alembic)
├── docker-compose.yml            # Local stack (orchestrator + bff + whatsapp + postgres + redis)
├── .env.production.example       # Environment variables template
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
cp .env.production.example .env
# Edit .env (see docs/02_environment_variables.md):
# - OPENAI_API_KEY
# - YCloud: YCLOUD_API_KEY, YCLOUD_WEBHOOK_SECRET
# - YCLOUD_WHATSAPP_NUMBER (Mandatory in DB credentials table)
# - POSTGRES_DSN / REDIS_URL
# - CLINIC_NAME, BOT_PHONE_NUMBER
# - META_ADS_TOKEN (for ad enrichment — optional)
# - GOOGLE_CREDENTIALS or connect-sovereign (optional)
# - ADMIN_TOKEN (for X-Admin-Token), JWT_SECRET_KEY
# - FRONTEND_URL (public-facing URL for anamnesis form links)
```

**3. Start services**

```bash
docker-compose up -d --build
```

**4. Access**

| Service | URL | Purpose |
|---------|-----|---------|
| **Orchestrator** | `http://localhost:8000` | Core API & agent |
| **BFF Service** | `http://localhost:3000` | Express proxy (Frontend gateway) |
| **Swagger UI** | `http://localhost:8000/docs` | OpenAPI contract; test with JWT + X-Admin-Token |
| **ReDoc / OpenAPI** | `http://localhost:8000/redoc`, `/openapi.json` | Read-only docs and JSON schema |
| **WhatsApp Service** | `http://localhost:8002` | YCloud relay & Whisper |
| **Operations Center** | `http://localhost:4173` | React UI (ES/EN/FR) via BFF |

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

Development follows the project's SDD workflows (specify → plan → implement) and **AGENTS.md** (sovereignty rules, scroll isolation, auth). For documentation changes, use the **Non-Destructive Fusion** protocol (see [update-docs](.agent/workflows/update-docs.md)). Database changes must go through **Alembic migrations** (`alembic revision -m "..."`) — never run SQL directly. Update `models.py` ORM classes alongside every migration.

---

## 📜 Agent Flow (Summary)

The WhatsApp assistant follows this order: **greeting + clinic name** → **define service** (max 3 if listing) → **(optional) professional preference** → **check_availability** with service duration → **offer time slots** → **confirm_slot** (30s soft-lock) → **patient data** → **book_appointment**. Duration is taken from the database per treatment; availability depends on whether the clinic uses local or Google calendar. Full detail in [04. Agent logic](docs/04_agent_logic_and_persona.md).

When the patient comes from a **Meta Ad**, the assistant adapts: for urgency ads, it prioritizes triage over data capture; for general ads, it personalizes the greeting mentioning the ad topic.

---

## 📜 License

ClinicForge © 2026. All rights reserved.
