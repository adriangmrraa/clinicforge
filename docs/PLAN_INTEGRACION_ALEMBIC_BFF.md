# Implementation Plan: Alembic and BFF Integration

## Current State

All work is **completed**. This document serves as the deployment guide.

| Component | Status | Details |
|-----------|--------|---------|
| `alembic.ini` | DONE | `script_location = %(here)s/alembic`, `prepend_sys_path = .` |
| `alembic/env.py` | DONE | DSN normalization asyncpg→psycopg2, NullPool, `target_metadata = Base.metadata` |
| `alembic/script.py.mako` | DONE | Standard Alembic template |
| `models.py` | DONE | **28 model classes** synced with production schema |
| Baseline migration | DONE | `001_a1b2c3d4e5f6_full_baseline.py` — 28 tables + 1 function + 1 view, raw SQL, idempotent |
| `start.sh` | DONE | `set -e` → `alembic upgrade head` → `exec uvicorn main:socket_app` |
| `requirements.txt` | DONE | `alembic` + `psycopg2-binary` added at end |
| `Dockerfile` | DONE | `WORKDIR /app`, installs curl, `CMD ["./start.sh"]` |
| BFF `src/index.ts` | DONE | Express.js reverse proxy, `/health`, CORS, catch-all proxy |
| BFF `Dockerfile` | DONE | `node:22-alpine`, `npm run build`, exposes port 3000 |
| BFF `package.json` | DONE | Express + Axios + TypeScript, dev/build/start scripts |
| `docker-compose.yml` | DONE | BFF service → orchestrator, frontend → BFF, healthchecks |

## What was excluded from German's branch

| Component | Reason |
|-----------|--------|
| `auth_routes.py` (JWT + HttpOnly cookies) | Conflicts with existing session-based auth in main |
| `security_middleware.py` (HSTS, CSP, X-Frame) | Conflicts with current security setup |
| Old migrations `83ffa6090043`, `820dbf12532d` | Replaced by new complete baseline `a1b2c3d4e5f6` |

## Bugs found and fixed during review

| Bug | Severity | Fix |
|-----|----------|-----|
| `chat_messages` had no `CREATE TABLE` — only `ALTER TABLE` from German's branch. Fresh DB would crash | CRITICAL | Rewrote as full `CREATE TABLE IF NOT EXISTS` with all 11 columns |
| Missing indexes `idx_chat_messages_from_number_created_at` and `idx_chat_messages_conversation_id` | MEDIUM | Added to baseline migration |
| Missing index `idx_chat_conv_last_derivhumano` from `v16` patch | MEDIUM | Added to both `models.py` and baseline migration |
| `patients.preferred_schedule` type mismatch: baseline `VARCHAR(50)`, model `Text` | MEDIUM | Fixed baseline SQL to `TEXT` to match model |
| Documents said "26 tables" but actual count is 28 | LOW | Corrected in all documents |

## Model ↔ Baseline audit (28 tables)

Every column, type, constraint, default, and index has been verified to match between `models.py` and the baseline migration SQL:

| Table | Columns | Indexes | Constraints | Match |
|-------|---------|---------|-------------|-------|
| `tenants` | 12 | — | UNIQUE(bot_phone_number) | model = baseline |
| `credentials` | 8 | 2 | UNIQUE(tenant_id, name) | model = baseline |
| `system_events` | 5 | — | — | model = baseline |
| `inbound_messages` | 10 | 2 | UNIQUE(provider, provider_message_id), CHECK(status) | model = baseline |
| `users` | 9 | 2 | CHECK(role), CHECK(status), UNIQUE(email) | model = baseline |
| `professionals` | 12 | 3 | FK(tenants), FK(users) | model = baseline |
| `patients` | 30 | 10 | UNIQUE(tenant_id, phone), UNIQUE(tenant_id, dni), partial idx handoff | model = baseline |
| `clinical_records` | 11 | 4 | FK(tenants, patients, professionals) | model = baseline |
| `appointments` | 20 | 9 | FK(tenants, patients, professionals) | model = baseline |
| `accounting_transactions` | 14 | 5 | FK(tenants, patients, appointments) | model = baseline |
| `daily_cash_flow` | 10 | 2 | UNIQUE(tenant_id, cash_date) | model = baseline |
| `google_calendar_blocks` | 12 | 4 | UNIQUE(google_event_id), FK(professionals CASCADE) | model = baseline |
| `calendar_sync_log` | 10 | 2 | FK(tenants) | model = baseline |
| `treatment_types` | 16 | 4+1 unique | UNIQUE(tenant_id, code) | model = baseline |
| `treatment_images` | 7 | 1 | Composite FK(tenant_id, treatment_code) | model = baseline |
| `chat_conversations` | 17 | 4 | UNIQUE(tenant_id, channel, external_user_id) | model = baseline |
| `chat_messages` | 11 | 4 | CHECK(role), partial idx(conversation_id IS NOT NULL) | model = baseline |
| `patient_documents` | 8 | 2 | UNIQUE(tenant_id, patient_id, filename) | model = baseline |
| `channel_configs` | 6 | 2 | UNIQUE(tenant_id, provider, channel) | model = baseline |
| `automation_logs` | 8 | 3 | FK(tenants, patients) | model = baseline |
| `meta_form_leads` | 23 | 7 | CHECK(status), partial idx(converted), FK(patients INTEGER) | model = baseline |
| `lead_status_history` | 7 | 3 | FK(meta_form_leads CASCADE) | model = baseline |
| `lead_notes` | 6 | 3 | FK(meta_form_leads CASCADE) | model = baseline |
| `patient_attribution_history` | 15 | 6 | CHECK(attribution_type) | model = baseline |
| `google_oauth_tokens` | 8 | 2 | UNIQUE(tenant_id, platform) | model = baseline |
| `google_ads_accounts` | 8 | 1 | UNIQUE(tenant_id, customer_id) | model = baseline |
| `google_ads_metrics_cache` | 10 | 2 | UNIQUE(tenant_id, customer_id, campaign_id, date) | model = baseline |
| `daily_analytics_metrics` | 5 | 1 | UNIQUE(tenant_id, metric_date, metric_type), tenant_id=UUID | model = baseline |

## Deployment steps

### Step 1: Confirm old migration files are deleted

```
orchestrator_service/alembic/versions/83ffa6090043_initial_baseline.py       (deleted)
orchestrator_service/alembic/versions/820dbf12532d_sync_point_with_patients_and_treatments.py  (deleted)
```

Only `001_a1b2c3d4e5f6_full_baseline.py` should remain in `alembic/versions/`.

### Step 2: Deploy code

Deploy the updated code to production (includes all Alembic infrastructure + BFF service).

> [!IMPORTANT]
> On first deploy, `start.sh` will run `alembic upgrade head`. For an **EXISTING production database**, you must run `alembic stamp` BEFORE the first deploy to prevent the baseline from trying to recreate existing tables.

**Option A — Stamp before deploy (recommended for existing DB):**
```bash
# SSH into production container or run one-off:
cd /app  # or orchestrator_service directory
export POSTGRES_DSN="postgresql://..."  # your production DSN
alembic stamp a1b2c3d4e5f6
```
Then deploy. `start.sh` will run `alembic upgrade head`, see the DB is already at head, and do nothing.

**Option B — Fresh database:**
Just deploy. `start.sh` runs `alembic upgrade head` which creates all 28 tables, the function, the view, and seed data from scratch.

### Step 3: Verify Alembic state

```bash
cd orchestrator_service
alembic current
# Expected: a1b2c3d4e5f6 (head)

alembic history
# Expected:
# a1b2c3d4e5f6 -> (head), Full baseline - complete ClinicForge schema
```

### Step 4: Check for production drift (existing DB only)

```bash
# Generate a diff between models.py and actual DB
alembic revision --autogenerate -m "sync_production_drift"
```

Review the generated migration file. Expected drift items for a production DB built from original `dentalogic_schema.sql`:

| What | Original Schema | Current Model | Action |
|------|----------------|---------------|--------|
| `credentials.name` | `TEXT` | `VARCHAR(255)` | Review — may want to keep TEXT |
| `tenants.config` | not present | `JSONB DEFAULT '{}'` | Should already exist (added via code) |
| `tenants.timezone` | not present | `VARCHAR(100)` | Should already exist (added via code) |
| `users.first_name/last_name` | not present | `VARCHAR(100)` | Should already exist (added via code) |
| `professionals.google_calendar_id` | not present | `VARCHAR(255)` | Should already exist (added via code) |
| `professionals.working_hours` | not present | `JSONB DEFAULT '{}'` | Should already exist (added via code) |
| `clinical_records.odontogram_data` | not present | `JSONB DEFAULT '{}'` | Should already exist (added via code) |
| `appointments.feedback_sent` | not present | `BOOLEAN DEFAULT FALSE` | Should already exist (added via code) |
| `patients.preferred_schedule` | `VARCHAR(50)` | `TEXT` | Intentional upgrade |

If the diff is empty or trivial, delete the generated file. If it has real changes, review and apply:
```bash
alembic upgrade head
```

### Step 5: Verify BFF connectivity

```bash
# Health check
curl http://localhost:3000/health
# Expected: {"status":"ok","service":"bff-interface","mode":"proxy"}

# Proxy test — should return same as direct orchestrator call
curl http://localhost:3000/api/v1/tenants
curl http://localhost:8000/api/v1/tenants
# Both should return identical responses
```

### Step 6: Frontend verification

1. Verify `VITE_API_URL` points to BFF:
   - Docker: `http://bff_service:3000`
   - Easypanel/production: the public BFF URL
2. Test ALL frontend pages load correctly through the BFF proxy
3. Test WebSocket/Socket.IO connections if used

## Rollback plan

### Alembic rollback
- **Production (after stamp)**: Nothing to rollback — `stamp` doesn't modify the DB
- **Fresh DB (after upgrade)**: `alembic downgrade base` drops all tables (dev/staging only)

### BFF rollback
1. Change `VITE_API_URL` to point directly to orchestrator URL
2. Stop/remove `bff_service` container
3. Frontend connects directly to orchestrator — no functionality lost

### Orchestrator rollback
If `start.sh` fails on `alembic upgrade head`:
1. `set -e` prevents uvicorn from starting (fail-fast, no corrupted state)
2. Fix the migration issue, or...
3. Temporarily change Dockerfile CMD to: `["uvicorn", "main:socket_app", "--host", "0.0.0.0", "--port", "8000"]`

## Future workflow

All schema changes now follow this process:

```bash
# 1. Edit models.py — add/modify table or column
# 2. Generate migration
cd orchestrator_service
alembic revision --autogenerate -m "add_feature_x"

# 3. Review generated migration file (ALWAYS review autogenerate output)
# 4. Test locally:
alembic upgrade head     # apply
alembic downgrade -1     # rollback
alembic upgrade head     # re-apply

# 5. Commit BOTH migration file + models.py changes together
# 6. On deploy, start.sh automatically runs alembic upgrade head
```

The old approach of writing raw SQL patches (`patch_*.sql`, `v*.sql`) is **replaced** by Alembic autogenerate. Existing SQL patch files in `orchestrator_service/migrations/` and `db_patches/` are kept as historical reference but are **no longer executed**.
