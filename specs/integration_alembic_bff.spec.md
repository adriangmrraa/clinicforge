# Specification: Integration of Alembic and BFF Service

## Overview
This specification outlines the integration of the Alembic migration framework and the BFF (Backend-for-Frontend) service into the `main` branch of ClinicForge. Both components originate from `Rama-German` and have been adapted to work with main's current schema and architecture.

## Requirements
- **Alembic**: Adopt the migration infrastructure from `Rama-German`. The `models.py` must be fully synced with the current production schema (28 tables + 1 function + 1 view).
- **BFF Service**: Integrate the TypeScript-based reverse proxy as a gateway between the frontend and the orchestrator.
- **Security**: DO NOT integrate `auth_routes.py` (JWT authentication) or `security_middleware.py` from German's branch. They conflict with the existing session-based authentication in main.

## Architecture

### Alembic Integration

#### Infrastructure files
| File | Purpose | Status |
|------|---------|--------|
| `orchestrator_service/alembic.ini` | Alembic config, `script_location = %(here)s/alembic`, `prepend_sys_path = .` | Done |
| `orchestrator_service/alembic/env.py` | Runtime env — DSN normalization asyncpg→psycopg2, NullPool, autogenerate via `Base.metadata` | Done |
| `orchestrator_service/alembic/script.py.mako` | Migration file template | Done |
| `orchestrator_service/models.py` | 28 SQLAlchemy model classes matching production schema | Done |
| `orchestrator_service/start.sh` | `set -e` + `alembic upgrade head` + `exec uvicorn main:socket_app` | Done |
| `orchestrator_service/requirements.txt` | `alembic` + `psycopg2-binary` added | Done |
| `orchestrator_service/Dockerfile` | `WORKDIR /app`, `CMD ["./start.sh"]` | Done |

#### DSN Normalization
`env.py` converts `postgresql+asyncpg://` (FastAPI runtime) to `postgresql://` (Alembic/SQLAlchemy sync):
```python
dsn.replace("postgresql+asyncpg://", "postgresql://")
```
This is critical because Alembic uses synchronous SQLAlchemy, but the app uses asyncpg.

#### Baseline Migration
File: `alembic/versions/001_a1b2c3d4e5f6_full_baseline.py`
Revision ID: `a1b2c3d4e5f6`

Uses raw SQL (`op.execute`) with `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` for idempotency. This approach was chosen because:
1. The production database already has all tables — the baseline must be safe to run against it.
2. `IF NOT EXISTS` makes it idempotent for both fresh and existing databases.
3. Raw SQL gives exact control over PostgreSQL-specific syntax (CHECK constraints, partial indexes, functions, views).

#### Complete table inventory (28 tables)

| # | Table | Model Class | PK Type | tenant_id | Origin |
|---|-------|------------|---------|-----------|--------|
| 1 | `tenants` | `Tenant` | SERIAL | N/A (is tenant) | `dentalogic_schema.sql` |
| 2 | `credentials` | `Credential` | SERIAL | FK INTEGER | `dentalogic_schema.sql` |
| 3 | `system_events` | `SystemEvent` | BIGSERIAL | — | `dentalogic_schema.sql` |
| 4 | `inbound_messages` | `InboundMessage` | BIGSERIAL | — | `dentalogic_schema.sql` |
| 5 | `users` | `User` | UUID | — (global) | `dentalogic_schema.sql` |
| 6 | `professionals` | `Professional` | SERIAL | FK INTEGER | `dentalogic_schema.sql` |
| 7 | `patients` | `Patient` | SERIAL | FK INTEGER | `dentalogic_schema.sql` + patches 017,020,022 |
| 8 | `clinical_records` | `ClinicalRecord` | UUID | FK INTEGER | `dentalogic_schema.sql` |
| 9 | `appointments` | `Appointment` | UUID | FK INTEGER | `dentalogic_schema.sql` |
| 10 | `accounting_transactions` | `AccountingTransaction` | UUID | FK INTEGER | `dentalogic_schema.sql` |
| 11 | `daily_cash_flow` | `DailyCashFlow` | SERIAL | FK INTEGER | `dentalogic_schema.sql` |
| 12 | `google_calendar_blocks` | `GoogleCalendarBlock` | UUID | FK INTEGER | `dentalogic_schema.sql` |
| 13 | `calendar_sync_log` | `CalendarSyncLog` | SERIAL | FK INTEGER | `dentalogic_schema.sql` |
| 14 | `treatment_types` | `TreatmentType` | SERIAL | FK INTEGER | `dentalogic_schema.sql` |
| 15 | `treatment_images` | `TreatmentImage` | UUID | FK composite | code evolution |
| 16 | `chat_conversations` | `ChatConversation` | UUID | FK INTEGER | code evolution + v15, v16 |
| 17 | `chat_messages` | `ChatMessage` | BIGSERIAL | FK INTEGER (default=1) | `dentalogic_schema.sql` + evolution |
| 18 | `patient_documents` | `PatientDocument` | SERIAL | FK INTEGER | code evolution |
| 19 | `channel_configs` | `ChannelConfig` | SERIAL | FK INTEGER | code evolution |
| 20 | `automation_logs` | `AutomationLog` | SERIAL | FK INTEGER | code evolution |
| 21 | `meta_form_leads` | `MetaFormLead` | UUID | FK INTEGER | `patch_019` |
| 22 | `lead_status_history` | `LeadStatusHistory` | UUID | FK INTEGER | `patch_019` |
| 23 | `lead_notes` | `LeadNote` | UUID | FK INTEGER | `patch_019` |
| 24 | `patient_attribution_history` | `PatientAttributionHistory` | UUID | FK INTEGER | `patch_020` |
| 25 | `google_oauth_tokens` | `GoogleOAuthToken` | SERIAL | FK INTEGER | `patch_021` |
| 26 | `google_ads_accounts` | `GoogleAdsAccount` | SERIAL | FK INTEGER | `patch_021` |
| 27 | `google_ads_metrics_cache` | `GoogleAdsMetricsCache` | SERIAL | FK INTEGER | `patch_021` |
| 28 | `daily_analytics_metrics` | `DailyAnalyticsMetric` | SERIAL | **UUID** (not FK) | `007_analytics_metrics.sql` |

Plus:
- **1 function**: `get_treatment_duration(VARCHAR, INTEGER, VARCHAR)` — returns treatment duration based on urgency
- **1 view**: `patient_attribution_complete` — unified first/last-touch + conversion attribution
- **Seed data**: 1 default tenant + 8 default treatment types

#### Schema notes

1. **`daily_analytics_metrics.tenant_id` is UUID**, not INTEGER like all other tenant_ids. This is intentional — the Dashboard Analytics Sovereign module uses a different tenant identification pattern. Model and baseline SQL are consistent.

2. **`chat_messages` has `tenant_id DEFAULT 1`** — not `NOT NULL`. This preserves backward compatibility with messages created before multi-tenancy was added.

3. **`inbound_messages` and `system_events` have no `tenant_id`** — these are global system tables, not tenant-scoped.

4. **`users` has no `tenant_id`** — users are global (a CEO could manage multiple tenants). The link is through `professionals.user_id`.

5. **`treatment_images` uses a composite FK** — `(tenant_id, treatment_code) REFERENCES treatment_types(tenant_id, code)` for data isolation.

#### Expected drift after `alembic stamp` on production

After stamping production (marking the DB as at revision `a1b2c3d4e5f6`), running `alembic check` may detect minor differences between the model and the actual DB. This is expected because:

- The production DB was built incrementally from `dentalogic_schema.sql` + patches + code-level ALTERs
- Some column types evolved (e.g., `credentials.name` was `TEXT` in original schema, now `VARCHAR(255)` in model)
- Some columns were added via code, not SQL patches (e.g., `tenants.config`, `tenants.timezone`, `users.first_name/last_name`, `professionals.google_calendar_id/working_hours`, `clinical_records.odontogram_data`, `appointments.feedback_sent/followup_sent`)
- `patients.preferred_schedule` was `VARCHAR(50)` in original schema, model uses `Text` (intentional improvement)

**Procedure**: After stamp, run `alembic revision --autogenerate -m "sync_production_drift"`, review the generated migration carefully, then apply or discard as appropriate.

#### Deployment procedure
- **Existing production DB**: `alembic stamp a1b2c3d4e5f6` to mark current state without running SQL.
- **Fresh database**: `alembic upgrade head` creates all 28 tables, function, view, and seed data.
- **Future migrations**: `alembic revision --autogenerate -m "description"` generates diffs against `models.py`.

### BFF Service

#### Architecture
- **Type**: Reverse proxy using Express.js + Axios
- **Port**: 3000 (configurable via `PORT` env var)
- **Role**: Forward all requests from frontend to `orchestrator_service:8000`
- **Source**: `bff_service/src/index.ts` (TypeScript, compiled via `tsc`)
- **Docker base**: `node:22-alpine`

#### Features
- `/` root endpoint returning `'BFF Service is Running'`
- `/health` endpoint returning `{ status: 'ok', service: 'bff-interface', mode: 'proxy' }`
- Catch-all proxy middleware forwarding to `ORCHESTRATOR_URL` (falls back to `ORCHESTRATOR_SERVICE_URL` or `http://localhost:8000`)
- Filters problematic headers: `Host`, `Content-Length`, `Connection`
- `validateStatus: () => true` — transparently forwards ALL HTTP status codes including 4xx/5xx
- 502 error response with details when orchestrator is unreachable
- CORS configured with `origin: true, credentials: true`, allows methods `GET/POST/PUT/DELETE/OPTIONS/PATCH`
- Allowed headers: `Content-Type, Authorization, x-admin-token, x-tenant-id, x-signature`

#### Docker configuration
```yaml
bff_service:
  build: ./bff_service
  ports:
    - "3000:3000"
  environment:
    - PORT=3000
    - ORCHESTRATOR_URL=http://orchestrator_service:8000
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
  depends_on:
    - orchestrator_service
```

Frontend's `VITE_API_URL` must point to the BFF service URL (not directly to orchestrator).

#### Request flow
```
Browser → Frontend (port 4173/80) → BFF (port 3000) → Orchestrator (port 8000) → PostgreSQL
```

## Constraints
- **Multi-tenancy**: All patient/clinical models enforce `tenant_id` isolation via ForeignKey to `tenants`. Exception: `inbound_messages`, `system_events`, `users`, and `daily_analytics_metrics` are global/use different patterns.
- **Security isolation**: Keep existing session-based auth. Do NOT import `auth_routes.py` or `security_middleware.py` from German's branch.
- **Idempotency**: Baseline migration uses `CREATE TABLE/INDEX IF NOT EXISTS` throughout. Safe to run multiple times.
- **No data loss**: Migrations must never drop existing data. Downgrade drops tables with `CASCADE` — only for development/testing.
- **Driver compatibility**: Production uses `asyncpg` (async). Alembic uses `psycopg2-binary` (sync). Both drivers must remain in `requirements.txt`.

## Verification

### Alembic
```bash
cd orchestrator_service
alembic current          # Expected: a1b2c3d4e5f6 (head)
alembic history          # Expected: single baseline revision
alembic check            # Expected: no pending changes (models.py == DB)
```

### BFF
```bash
curl http://localhost:3000/health
# Expected: {"status":"ok","service":"bff-interface","mode":"proxy"}

curl http://localhost:3000/health -H "Origin: http://localhost:4173" -v
# Should include Access-Control-Allow-Origin header

curl http://localhost:3000/api/v1/tenants
# Should proxy to orchestrator and return same response
```

### End-to-end
- Frontend (port 4173) → BFF (port 3000) → Orchestrator (port 8000)
- Verify all existing frontend pages load and function correctly through the BFF
- Verify WebSocket/Socket.IO connections pass through correctly (if applicable)
