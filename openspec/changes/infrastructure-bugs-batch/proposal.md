# Proposal: infrastructure-bugs-batch

**Change**: `infrastructure-bugs-batch`
**Status**: PROPOSAL
**Date**: 2026-04-25
**Priority**: CRITICAL (Bug 2 blocks multi-agent engine activation)

---

## 1. Intent

Five independent infrastructure bugs are silently degrading ClinicForge in production. They span the AI engine router, RAG search, chat UI, background jobs, and Redis state serialization. None of them raise user-visible errors in the frontend -- they fail silently or spam server logs, making them hard to detect but high-impact.

**Why now:**
- **Bug 2 (engine router)** is a hard blocker: the user just activated the multi-agent engine from the UI, but the router crashes on import (`No module named 'database'`). Multi-agent is completely non-functional until this is fixed.
- **Bug 4 (lead recovery)** fires every 15 minutes across 3 tiers and fails every time. This pollutes logs with `TypeError: can't multiply sequence by non-int of type 'timedelta'`, burying real errors and preventing all automated lead follow-up.
- **Bug 1 (pgvector)** degrades RAG quality: when numpy is absent (common in slim Docker images), the semantic FAQ search silently breaks, falling back to static injection or returning no results.
- **Bug 5 (date serialization)** causes `check_availability` to fail when writing slot options to Redis state via `json.dumps()`, breaking the booking flow intermittently.
- **Bug 3 (unread counts)** prevents the chat badge from updating -- a cosmetic but trust-eroding issue for clinic staff.

**Cost of not fixing:** Multi-agent engine is dead on arrival. Lead recovery is 100% broken. RAG search is degraded. Booking flow has intermittent failures. Chat badges are wrong.

---

## 2. Scope

### In scope
5 bugs across 5 files. All are type-mismatch or import errors -- no architectural changes, no new features, no schema changes, no migrations.

| Bug | File | Type |
|-----|------|------|
| Bug 1: pgvector `bytea <=> unknown` | `orchestrator_service/services/embedding_service.py` | SQL parameter cast |
| Bug 2: `No module named 'database'` | `orchestrator_service/services/engine_router.py` | Import fix |
| Bug 3: `uuid = integer` | `orchestrator_service/admin_routes.py` | SQL cast fix |
| Bug 4: `timestamp <= interval` | `orchestrator_service/jobs/lead_recovery.py` | Type coercion |
| Bug 5: `date not JSON serializable` | `orchestrator_service/main.py` | Serialization fix |

### Out of scope
- No new tests (these are one-liner fixes in existing code paths; tests can follow in a dedicated test-suite change).
- No migration files.
- No frontend changes.
- No dependency additions.
- No changes to the multi-agent engine logic itself -- only fixing the import that prevents it from loading.

---

## 3. Approach

### Bug 2: Engine router import crash (CRITICAL -- P0)

- **File**: `orchestrator_service/services/engine_router.py:383`
- **Current**: `from database import AsyncSessionLocal` -- module does not exist.
- **Change**: Replace the SQLAlchemy session import with `from orchestrator_service.db import pool` (the existing asyncpg pool). Rewrite the `_read_engine_mode` method to use a raw asyncpg query (`SELECT ai_engine_mode FROM tenants WHERE id = $1`) instead of an ORM session. This avoids circular imports entirely since `db.py` has no dependency on `main.py`.
- **Type**: Structural (method rewrite, ~10 lines). Not a one-liner because the calling code assumes a SQLAlchemy session context manager.

### Bug 4: Lead recovery type mismatch (P1)

- **File**: `orchestrator_service/jobs/lead_recovery.py:80-82`
- **Current**: `delay_t1 = config.get("delay_touch1_minutes", 120)` -- config values may arrive as strings from the DB, and downstream code does `INTERVAL '1 minute' * $1` which requires an integer.
- **Change**: Wrap each delay extraction in `int()`: `delay_t1 = int(config.get("delay_touch1_minutes", 120))`. Same for `delay_t2` and `delay_t3`.
- **Type**: One-liner x3. Pure type coercion.

### Bug 1: pgvector embedding parameter (P2)

- **File**: `orchestrator_service/services/embedding_service.py:222-236`
- **Current**: When numpy is not installed, `embedding_param` is a raw `list[float]`. asyncpg encodes Python lists as PostgreSQL arrays, but the `<=>` cosine distance operator expects a `vector` type, not `float[]` or `bytea`.
- **Change**: Convert the embedding to a string representation (`"[0.1, 0.2, ...]"`) and use an explicit `$1::vector` cast in the SQL query. This works identically whether numpy is installed or not.
- **Type**: Small structural (~3 lines changed in the query + parameter preparation).

### Bug 5: Date JSON serialization (P3)

- **File**: `orchestrator_service/main.py` -- inside `pick_representative_slots` (5 append sites)
- **Current**: `"date": target_date` stores a `datetime.date` object. When `set_state()` later calls `json.dumps()`, it raises `TypeError: Object of type date is not JSON serializable`.
- **Change**: Replace `target_date` with `target_date.isoformat()` at each of the 5 append sites.
- **Type**: One-liner x5. Pure serialization fix.

### Bug 3: Chat unread UUID cast (P4)

- **File**: `orchestrator_service/admin_routes.py:1590`
- **Current**: `$1::int[]` cast on `chat_conversations.id`, which is a UUID column.
- **Change**: Replace `$1::int[]` with `$1::uuid[]`.
- **Type**: One-liner. Pure SQL cast fix.

---

## 4. Priority Order

Ordered by production impact (descending):

| Priority | Bug | Impact | Severity |
|----------|-----|--------|----------|
| P0 | Bug 2: Engine router import | Multi-agent engine completely non-functional | CRITICAL |
| P1 | Bug 4: Lead recovery types | Log spam every 15min, all lead follow-up broken | HIGH |
| P2 | Bug 1: pgvector cast | RAG search degraded when numpy absent | MEDIUM |
| P3 | Bug 5: Date serialization | Booking flow intermittent failures | MEDIUM |
| P4 | Bug 3: Unread count cast | Chat badges show wrong counts | LOW |

Implementation order follows this priority. Bug 2 should be deployed first if hotfix cadence allows.

---

## 5. Risks & Mitigations

| Bug | Risk | Mitigation |
|-----|------|------------|
| Bug 2 | Circular import if we import from `main.py` | Use `db.pool` (asyncpg) instead of any SQLAlchemy import. `db.py` has zero internal dependencies. Verified in exploration. |
| Bug 2 | asyncpg pool not yet initialized when router is first called | The router is only called from `buffer_task.py:998` during message processing, which happens well after startup. Pool is guaranteed initialized. |
| Bug 1 | String-format embedding may have precision loss | IEEE 754 float string representation preserves full precision for 64-bit floats. Cosine similarity tolerance is well within this range. |
| Bug 1 | `::vector` cast may fail if pgvector extension not loaded | Existing fallback already handles this case (static FAQ injection). No regression. |
| Bug 4 | `int()` on a non-numeric config value raises ValueError | The `config.get()` calls have sensible integer defaults (120, 720, 4320). If the DB contains garbage, it will raise early and visibly instead of failing silently downstream. This is the correct behavior. |
| Bug 5 | Missing an append site (5 locations) | Exploration identified all 5 via grep. Will verify during apply phase with a targeted search for `"date": target_date` and `"date": `. |
| Bug 3 | Passing Python UUIDs vs strings to asyncpg | asyncpg natively handles Python `uuid.UUID` objects in `uuid[]` arrays. No conversion needed on the caller side. |

**General risk**: All 5 fixes are in the hot path of their respective features. A typo could crash the feature entirely. Mitigation: each fix is small and isolated. The verify phase will confirm each fix with targeted code review.

---

## 6. Estimated Impact

| Metric | Value |
|--------|-------|
| Files touched | 5 |
| Lines changed (estimated) | ~25-30 |
| Migrations | 0 |
| New dependencies | 0 |
| Frontend changes | 0 |
| Breaking changes | 0 |
| Deployment requirements | Backend restart only |

### Files changed

| File | Lines changed (est.) |
|------|---------------------|
| `orchestrator_service/services/engine_router.py` | ~10 (method rewrite) |
| `orchestrator_service/jobs/lead_recovery.py` | 3 (int wraps) |
| `orchestrator_service/services/embedding_service.py` | ~5 (query + param) |
| `orchestrator_service/main.py` | 5 (isoformat calls) |
| `orchestrator_service/admin_routes.py` | 1 (cast change) |

---

## Decision

These are all type-level bugs with deterministic fixes. No design ambiguity. Recommend proceeding directly to **tasks** (skip specs and design phases -- the exploration already identified exact lines and fixes).
