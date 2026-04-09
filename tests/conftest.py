"""Pytest configuration and shared fixtures.

Two layers:
  1. Environment setup and simple mocks (backward compat with existing tests)
  2. Real Postgres fixtures for integration tests (marked with @pytest.mark.integration)

The integration fixtures are only activated when the user has a running Postgres
with the DSN in TEST_POSTGRES_DSN (or POSTGRES_DSN) and the target DB already
migrated via `alembic upgrade head`.
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.fixtures.tenants import make_tenant_row

# ---------------------------------------------------------------------------
# Stub out optional C-extension or uninstalled packages that main.py imports
# at module level. These stubs must be injected BEFORE any test imports
# orchestrator_service.main so the module-level `import socketio` succeeds.
# ---------------------------------------------------------------------------
def _make_socketio_stub() -> ModuleType:
    """Minimal python-socketio stub for test environments without the package.

    We cannot use `MagicMock` as the class value for AsyncServer/ASGIApp because
    Python 3.13's MagicMock interprets the first positional arg as a spec, which
    causes InvalidSpecError when a Mock is passed as that arg. Instead we use
    simple Python classes that behave like no-ops for all socket.io operations.
    """
    mod = ModuleType("socketio")

    class _FakeAsyncServer:
        """Fake socket.io AsyncServer with enough surface to satisfy main.py."""

        def __init__(self, *args, **kwargs):
            pass

        def on(self, event=None, *args, **kwargs):
            """Decorator factory for event handlers."""
            def decorator(f):
                return f
            return decorator

        def event(self, f=None, *args, **kwargs):
            """Alternative event registration decorator."""
            if callable(f):
                return f
            def decorator(fn):
                return fn
            return decorator

        async def emit(self, *args, **kwargs):
            pass

        def attach(self, *args, **kwargs):
            pass

        def __getattr__(self, name):
            # Return no-op callable for any other attribute access
            return MagicMock()

    class _FakeASGIApp:
        """Fake ASGI app wrapping a fake socketio server."""

        def __init__(self, *args, **kwargs):
            pass

        async def __call__(self, scope, receive, send):
            pass

    mod.AsyncServer = _FakeAsyncServer  # type: ignore[attr-defined]
    mod.ASGIApp = _FakeASGIApp  # type: ignore[attr-defined]
    return mod


def _make_jwt_stub() -> ModuleType:
    """Minimal PyJWT stub for test environments without the package."""
    mod = ModuleType("jwt")
    mod.encode = MagicMock(return_value="test_token")  # type: ignore[attr-defined]
    mod.decode = MagicMock(return_value={"sub": "test"})  # type: ignore[attr-defined]
    mod.ExpiredSignatureError = Exception  # type: ignore[attr-defined]
    mod.InvalidTokenError = Exception  # type: ignore[attr-defined]
    mod.PyJWTError = Exception  # type: ignore[attr-defined]
    return mod


def _make_passlib_stubs() -> None:
    """Minimal passlib stubs for test environments without the package."""
    # passlib.context — used by auth_service.py
    ctx_mod = ModuleType("passlib.context")
    ctx_mock = MagicMock()
    ctx_mock.return_value = MagicMock()
    ctx_mod.CryptContext = ctx_mock  # type: ignore[attr-defined]
    sys.modules.setdefault("passlib", ModuleType("passlib"))
    sys.modules["passlib.context"] = ctx_mod
    for sub in ["passlib.handlers", "passlib.handlers.bcrypt", "passlib.handlers.sha2_crypt"]:
        sys.modules.setdefault(sub, ModuleType(sub))


if "socketio" not in sys.modules:
    sys.modules["socketio"] = _make_socketio_stub()

if "jwt" not in sys.modules:
    sys.modules["jwt"] = _make_jwt_stub()

if "passlib" not in sys.modules:
    _make_passlib_stubs()

# --- Load .env file if present (so the real DSN from .env beats hardcoded defaults) ---
try:
    from dotenv import load_dotenv

    _ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=False)
except Exception:
    pass  # dotenv optional — if not installed, fall through to env vars

# --- Default test env vars (only set if not already defined by .env or shell) ---
os.environ.setdefault("YCLOUD_API_KEY", "test_ycloud_key")
os.environ.setdefault("YCLOUD_WEBHOOK_SECRET", "test_webhook_secret")
os.environ.setdefault("INTERNAL_API_TOKEN", "test_internal_token")
os.environ.setdefault("TIENDANUBE_API_KEY", "test_tn_key")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_key")
os.environ.setdefault(
    "POSTGRES_DSN", "postgresql://test:test@localhost:5432/clinicforge_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("ADMIN_TOKEN", "test_admin_token")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret")
os.environ.setdefault("CREDENTIALS_FERNET_KEY", "test_fernet_key_must_be_32_bytes_b")
os.environ.setdefault("FRONTEND_URL", "http://localhost:4173")


# ============================================================================
# Legacy mock fixtures (pre-existing tests use these)
# ============================================================================


@pytest.fixture
def mock_redis():
    mock = MagicMock()
    mock.lock.return_value.acquire.return_value = True
    return mock


@pytest.fixture
def mock_db_pool():
    mock = MagicMock()
    return mock


# ============================================================================
# Canonical tenant fixtures (C1 — REQ-TS-2)
# ============================================================================


@pytest.fixture
def tenant_factory():
    """Return a callable that builds a tenant dict with all NOT NULL columns.

    Usage::

        def test_something(tenant_factory):
            row = tenant_factory(country_code="US", language="en")
            pool.fetchrow.return_value = row
    """
    return make_tenant_row


# ============================================================================
# app_with_mock_pool fixture (C2 — REQ-TS-3)
# ============================================================================


@pytest.fixture
def app_with_mock_pool(monkeypatch):
    """Mount a FastAPI TestClient with db.pool replaced by an AsyncMock.

    Each test can customise individual method return values, e.g.::

        def test_something(app_with_mock_pool):
            client, mock_pool = app_with_mock_pool
            mock_pool.fetchrow.return_value = {"id": 1}
            response = client.get("/admin/something")

    The mock supports: fetchrow, fetch, fetchval, execute, acquire (context mgr).
    """
    from unittest.mock import AsyncMock, MagicMock

    # Build the AsyncMock pool before importing main so the lifespan doesn't
    # connect to a real Postgres.
    mock_pool = MagicMock()
    mock_pool.fetchrow = AsyncMock(return_value=None)
    mock_pool.fetch = AsyncMock(return_value=[])
    mock_pool.fetchval = AsyncMock(return_value=None)
    mock_pool.execute = AsyncMock(return_value=None)

    # acquire() is used as an async context manager: `async with pool.acquire() as conn`
    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.fetchval = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_conn),
        __aexit__=AsyncMock(return_value=False),
    ))

    # Patch db.pool in the orchestrator_service.db module.
    # main.py uses `db.pool.fetchrow(...)` where `db` is the Database() singleton.
    # We patch db.db.pool (the pool attribute on the Database instance).
    import orchestrator_service.db as db_module
    monkeypatch.setattr(db_module.db, "pool", mock_pool)

    # Also patch the top-level `db` module exported as `db` (pythonpath-rooted)
    try:
        import db as db_top
        monkeypatch.setattr(db_top.db, "pool", mock_pool)
    except (ImportError, AttributeError):
        pass

    from fastapi.testclient import TestClient

    # Import app AFTER patching so it doesn't try to connect on startup.
    from unittest.mock import patch
    with patch("redis.from_url"), patch("langchain_openai.ChatOpenAI"):
        from orchestrator_service.main import app
        client = TestClient(app, raise_server_exceptions=False)

    return client, mock_pool


# ============================================================================
# Real Postgres fixtures for integration tests (@pytest.mark.integration)
# ============================================================================

# Resolve the test DSN. Preference order:
#   1. TEST_POSTGRES_DSN (explicit test-only DSN)
#   2. POSTGRES_DSN (fallback — usually same if .env is set up for tests)
_TEST_DSN = os.environ.get("TEST_POSTGRES_DSN") or os.environ.get(
    "POSTGRES_DSN", "postgresql://test:test@localhost:5432/clinicforge_test"
)


@pytest.fixture(scope="session")
def event_loop():
    """Shared event loop across the whole test session.

    Required for session-scoped async fixtures (real_db_pool). Without this,
    pytest-asyncio creates a new loop per test which conflicts with
    asyncpg pools that were created on a different loop.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def real_db_pool():
    """Session-scoped asyncpg pool to the real test Postgres.

    The target DB MUST already exist and be migrated via `alembic upgrade head`.
    Tests that depend on this fixture MUST be marked with @pytest.mark.integration.

    Skips the entire test if asyncpg can't connect (DB not running, wrong DSN,
    or DB not migrated). This keeps CI green on machines without a local DB.
    """
    try:
        import asyncpg
    except ImportError:
        pytest.skip("asyncpg not installed")

    try:
        pool = await asyncpg.create_pool(
            _TEST_DSN, min_size=1, max_size=5, timeout=5.0
        )
    except Exception as exc:
        pytest.skip(f"Cannot connect to test Postgres at {_TEST_DSN}: {exc}")

    # Sanity check: verify the schema is migrated. If `tenants` table doesn't
    # exist, the user forgot to run `alembic upgrade head`.
    try:
        async with pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'tenants' LIMIT 1"
            )
            if not exists:
                pytest.skip(
                    "tenants table not found — run `alembic upgrade head` on "
                    "the test DB before running integration tests"
                )
    except Exception as exc:
        await pool.close()
        pytest.skip(f"Schema check failed: {exc}")

    yield pool

    await pool.close()


@pytest.fixture
async def test_tenant(real_db_pool):
    """Function-scoped fixture that creates a clean tenant and cleans up after.

    Each test gets its own tenant_id via uuid-based name, ensuring zero
    collision with other tests or with production data in the same DB.

    Cleanup is FK-aware: drops children before parents.
    """
    async with real_db_pool.acquire() as conn:
        tenant_id = await conn.fetchval(
            """
            INSERT INTO tenants (
                clinic_name, bot_phone_number, config,
                accepts_pregnant_patients, accepts_pediatric,
                requires_anamnesis_before_booking
            )
            VALUES ($1, $2, '{}'::jsonb, true, true, false)
            RETURNING id
            """,
            f"test-{uuid.uuid4().hex[:8]}",
            f"+test-{uuid.uuid4().hex[:8]}",
        )

    yield tenant_id

    # Cleanup in FK-safe order. Wrap each in try/except so a failure in one
    # table doesn't leave the fixture in a half-cleaned state.
    async with real_db_pool.acquire() as conn:
        for sql in [
            "DELETE FROM appointments WHERE tenant_id = $1",
            "DELETE FROM professional_derivation_rules WHERE tenant_id = $1",
            "DELETE FROM treatment_type_professionals "
            "WHERE treatment_type_id IN (SELECT id FROM treatment_types WHERE tenant_id = $1)",
            "DELETE FROM treatment_types WHERE tenant_id = $1",
            "DELETE FROM professionals WHERE tenant_id = $1",
            "DELETE FROM tenants WHERE id = $1",
        ]:
            try:
                await conn.execute(sql, tenant_id)
            except Exception:
                pass
