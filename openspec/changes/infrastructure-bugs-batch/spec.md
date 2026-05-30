# Infrastructure Bugs Batch -- Specification

**Change**: infrastructure-bugs-batch
**Type**: bugfix (5 independent bugs)
**Scope**: Backend only -- orchestrator_service
**Migrations**: NONE required
**Frontend**: NONE required

---

## Bug 1: pgvector FAQ search -- `bytea <=> unknown` type mismatch

### Problem

When numpy is not installed, `embedding_service.search_similar_faqs()` passes a raw Python `list[float]` as the `$1` parameter to asyncpg. asyncpg serializes this as `bytea`, but pgvector's `<=>` cosine distance operator expects type `vector`. PostgreSQL raises a type mismatch error, killing the RAG semantic search for every tenant.

### Root Cause

`orchestrator_service/services/embedding_service.py:220-236`. The `except ImportError` fallback assigns `embedding_param = query_embedding` (a plain list). asyncpg cannot infer the `vector` type from a Python list -- it defaults to `bytea`. The SQL query never casts `$1` to `::vector`.

### Specification

- The SQL query at line 222 MUST cast `$1` explicitly as `$1::vector` in both occurrences within the query (the `<=>` comparison on lines 229, 233, 234).
- When numpy is unavailable, `embedding_param` MUST be converted to a string representation that asyncpg can pass as text (e.g., `"[0.1, 0.2, ...]"` format) so that PostgreSQL's `::vector` cast can parse it.
- When numpy IS available, the existing `np.array(..., dtype=np.float32)` path MUST continue working unchanged (pgvector accepts numpy arrays natively via asyncpg).
- The fallback path MUST NOT import any additional dependencies beyond what is already in requirements.txt.

### Acceptance Criteria

- **AC-1**: Given a tenant with FAQ embeddings and numpy NOT installed, when a patient sends a message triggering RAG search, then the top-K relevant FAQs are returned without errors.
- **AC-2**: Given a tenant with FAQ embeddings and numpy IS installed, when RAG search executes, then behavior is identical to current (no regression).
- **AC-3**: Given a tenant with zero FAQ embeddings, when RAG search executes, then it returns an empty list (existing behavior preserved).

### Regression Guards

- The static FAQ fallback (when pgvector extension is absent) MUST still work.
- `sync_all_tenants_faq_embeddings` startup sync MUST still function.
- FAQ CRUD hooks in `admin_routes.py` that trigger embedding re-generation MUST still work.

---

## Bug 2: Engine router -- `No module named 'database'`

### Problem

`EngineRouter._load_mode_from_db()` imports `from database import AsyncSessionLocal`, a module that does not exist in the project. This causes an `ImportError` every time the engine router tries to load the AI engine mode from the database, breaking the dual-engine toggle for any tenant.

### Root Cause

`orchestrator_service/services/engine_router.py:383`. The import references a non-existent `database` module. The project uses `orchestrator_service/db.py` which exposes an asyncpg connection pool (`db.pool`), not SQLAlchemy async sessions. The method also uses SQLAlchemy `select()` syntax which is inconsistent with the rest of the codebase (raw asyncpg queries).

### Specification

- `_load_mode_from_db()` MUST replace the `from database import AsyncSessionLocal` import with usage of the existing `db.pool` (asyncpg pool from `orchestrator_service/db.py`).
- The query MUST use `db.pool.fetchval()` with a raw SQL query: `SELECT ai_engine_mode FROM tenants WHERE id = $1`, consistent with every other DB access in the project.
- The method MUST return `"solo"` as default when the tenant is not found or the column is NULL.
- The SQLAlchemy `select()` and `session.execute()` patterns MUST be removed from this method.
- No other method in `engine_router.py` is affected (only `_load_mode_from_db`).

### Acceptance Criteria

- **AC-1**: Given a tenant with `ai_engine_mode = 'multi'`, when the engine router loads its mode, then it returns `"multi"` and the MultiAgentEngine is used.
- **AC-2**: Given a tenant with `ai_engine_mode = 'solo'` (default), when the engine router loads its mode, then it returns `"solo"` and the SoloEngine is used.
- **AC-3**: Given a tenant that does not exist in the DB, when the engine router loads its mode, then it returns `"solo"` (safe fallback) without raising an exception.

### Regression Guards

- The 60-second in-memory cache MUST still work (reads from DB only on cache miss/expiry).
- Redis pubsub cache invalidation (on settings PATCH) MUST still trigger a DB reload.
- The circuit breaker (3 consecutive multi failures -> fallback to solo) MUST be unaffected.

---

## Bug 3: Chat unread counts -- `uuid = integer` type cast error

### Problem

The unread count query in the chats endpoint casts `conversation_id` as `$1::int[]`, but `chat_conversations.id` is `UUID` type. PostgreSQL raises a type mismatch error, breaking the unread message badge/count for all chat sessions in the admin panel.

### Root Cause

`orchestrator_service/admin_routes.py:1590`. The SQL `unnest($1::int[])` should be `unnest($1::uuid[])`. The `chat_conversations.id` column is defined as `UUID(as_uuid=True)` in `models.py:164`.

### Specification

- Line 1590 MUST change the cast from `$1::int[]` to `$1::uuid[]`.
- No other casts in the same CTE query (lines 1591-1592) need changing (`$2::text[]` and `$3::timestamptz[]` are correct).
- The Python list passed as the `$1` parameter MUST contain UUID objects (or UUID-compatible strings). Verify the caller assembles UUID values, not integers.

### Acceptance Criteria

- **AC-1**: Given an admin viewing the Chats panel with 5 active conversations, when the unread counts are fetched, then each conversation shows the correct unread message count without errors.
- **AC-2**: Given an admin with zero conversations, when the endpoint is called, then it returns an empty result without errors.
- **AC-3**: Given conversations with UUID-format IDs (standard for this table), when the batch unread query executes, then the `unnest` correctly unpacks all UUIDs.

### Regression Guards

- The "normal path" (with `conversation_id` and `last_read_at` available) and the "fallback path" (without them) MUST both work.
- The unread count calculation logic (comparing `last_read_at` with message timestamps) MUST be unchanged.
- Real-time Socket.IO unread notifications MUST be unaffected.

---

## Bug 4: Lead recovery -- `timestamp <= interval` type mismatch

### Problem

The lead recovery job reads delay values from `condition_json` (a JSONB config field). JSON parsing can return these as strings (e.g., `"120"` instead of `120`). When passed as `$3` to `INTERVAL '1 minute' * $3`, PostgreSQL cannot multiply an interval by a text value, causing the entire lead recovery job to fail silently for that tenant.

### Root Cause

`orchestrator_service/jobs/lead_recovery.py:80-82`. `config.get("delay_touch1_minutes", 120)` returns the default `120` (int) only when the key is absent. If the key exists in JSON as a string `"120"`, it is passed as-is. Line 140: `INTERVAL '1 minute' * $3` then fails because `$3` is text, not numeric.

### Specification

- Lines 80-82 MUST wrap each `config.get(...)` result with `int()` to coerce the value: `int(config.get("delay_touch1_minutes", 120))`.
- Apply the same `int()` wrap to `delay_t2` and `delay_t3`.
- The `hour_min` and `hour_max` values (line 83-84) MUST also be wrapped with `int()` as they come from the same JSONB source and are used in numeric comparisons.
- MUST NOT change the SQL queries themselves.
- MUST NOT change the default values (120, 480, 480, 8, 20).

### Acceptance Criteria

- **AC-1**: Given a lead recovery rule with `condition_json = {"delay_touch1_minutes": "120"}` (string value), when the job runs, then it correctly identifies candidates whose last message was 120+ minutes ago.
- **AC-2**: Given a lead recovery rule with `condition_json = {"delay_touch1_minutes": 120}` (integer value), when the job runs, then behavior is identical (no regression).
- **AC-3**: Given a lead recovery rule with missing delay keys (uses defaults), when the job runs, then the default integer values (120, 480, 480) are used correctly.

### Regression Guards

- All 3 touch levels (T1, T2, T3) MUST continue to process candidates correctly.
- Business hours gating (hour_min/hour_max) MUST still work.
- High-ticket lead prioritization MUST be unaffected.
- The automation_logs deduplication check MUST be unaffected.

---

## Bug 5: Date JSON serialization in slot offers

### Problem

`pick_representative_slots()` returns option dicts with `"date": target_date` where `target_date` is a Python `datetime.date` object. When `check_availability` stores these options in Redis via `json.dumps()` (line 2687-2688), it raises `TypeError: Object of type date is not JSON serializable`, preventing slot offer persistence in Redis. This breaks the slot confirmation flow that reads cached offers.

### Root Cause

`orchestrator_service/main.py` -- 3 `options.append()` sites inside `pick_representative_slots` (lines 1389-1394, 1478-1483, 1531-1536) all set `"date": target_date` / `"date": d` / `"date": extra_date` as raw `date` objects. Line 2687-2688 in `check_availability` calls `json.dumps([{"date": opt.get("date"), ...}])` on these objects, which fails.

### Specification

- All 3 `options.append()` sites in `pick_representative_slots` MUST convert the date value to ISO format string using `.isoformat()`:
  - Line 1392: `"date": target_date.isoformat()`
  - Line 1481: `"date": d.isoformat()`
  - Line 1534: `"date": extra_date.isoformat()`
- The `json.dumps` call at line 2687-2688 MUST NOT need modification (it will work once the values are strings).
- Any downstream consumer of `opt["date"]` that expects a `date` object MUST be checked. The display formatting uses `opt["date_display"]` (a pre-formatted string), so the `"date"` field is only consumed by: (a) the Redis slot offer cache and (b) any downstream parsing that should handle ISO strings.
- MUST NOT change the `"date_display"` field format (used for WhatsApp message rendering).

### Acceptance Criteria

- **AC-1**: Given a patient asking for availability and 2 options are found, when `check_availability` stores the slot offer in Redis, then `json.dumps` succeeds and the offer is cached with 300s TTL.
- **AC-2**: Given a cached slot offer in Redis, when `confirm_slot` reads it back, then the date strings parse correctly for slot confirmation.
- **AC-3**: Given a multi-day search (search_range_days > 1) producing options across different dates, when all options are serialized, then each date is a valid ISO format string (YYYY-MM-DD).

### Regression Guards

- The WhatsApp message formatting (`opt["date_display"]`) MUST be unchanged.
- The `confirm_slot` tool that reads from `slot_offer:{tenant_id}:{phone}` Redis key MUST still work.
- Multi-sede display logic that reads `opt["sede"]` MUST be unaffected.
- The `lead_context.merge` call downstream MUST be unaffected.

---

## Cross-Cutting Concerns

1. **No new migrations** -- All 5 bugs are runtime code fixes. No schema changes needed.
2. **No frontend changes** -- All bugs are in the Python backend (orchestrator_service).
3. **Agent response flow must not break** -- The AI conversational flow (TORA Solo and Multi-Agent) must continue to work. Bug fixes are in supporting infrastructure (RAG, routing, chat, jobs, serialization), not in the agent prompt or tool definitions.
4. **All fixes are backward compatible** -- Each fix handles both the current (broken) input types AND the expected (correct) input types. No API contracts change.
5. **No new dependencies** -- All fixes use existing stdlib or project dependencies.
6. **Tenant isolation** -- No fix introduces any cross-tenant data leak risk. All queries retain their `tenant_id` filters.
7. **Testing** -- Each bug should have at minimum one unit test covering the fixed path. Since these are type-level bugs (wrong casts, missing conversions), tests should verify the correct types are produced/accepted.
