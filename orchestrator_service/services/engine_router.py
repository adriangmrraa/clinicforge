"""Engine Router — Dual-engine dispatcher for multi-tenant AI conversation routing.

This module implements the Strategy pattern to dispatch between:
- SoloEngine: TORA monolithic (wraps current get_agent_executable_for_tenant)
- MultiAgentEngine: LangGraph multi-agent system (stub for now)

Key features:
- In-memory cache with 60s TTL for ai_engine_mode
- Circuit breaker: 3 failures in 60s → fallback to solo for 5 min
- Redis pubsub for cross-process cache invalidation
- Thread-safe with asyncio.Lock per tenant

See: openspec/changes/engine-mode-toggle-and-multi-agent/design.md §6
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Tenant

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class TurnContext:
    """Context for a single conversation turn."""

    tenant_id: int
    phone_number: str
    user_message: str
    thread_id: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnResult:
    """Result from processing a turn."""

    output: str
    agent_used: str
    duration_ms: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProbeResult:
    """Result from a health probe."""

    ok: bool
    latency_ms: int
    error: Optional[str] = None
    detail: Optional[str] = None


# =============================================================================
# Engine Protocol
# =============================================================================


class Engine(Protocol):
    """Protocol defining the engine interface."""

    name: str

    async def process_turn(self, ctx: TurnContext) -> TurnResult:
        """Process a single turn and return the result."""
        ...

    async def probe(self) -> ProbeResult:
        """Run a health check probe."""
        ...


# =============================================================================
# Solo Engine (TORA Legacy)
# =============================================================================


class SoloEngine:
    """Wrapper around the current TORA implementation."""

    name: str = "solo"

    async def process_turn(self, ctx: TurnContext) -> TurnResult:
        """Process turn using the existing TORA flow."""
        start = time.perf_counter()

        # Import here to avoid circular imports
        from main import get_agent_executable_for_tenant

        # Build input for the executor
        history = ctx.extra.get("chat_history", [])
        input_data = {
            "input": ctx.user_message,
            "chat_history": history,
        }

        # Create config with session_id for thread continuity
        config = {"configurable": {"session_id": ctx.thread_id}}

        # Get executor and invoke
        executor = await get_agent_executable_for_tenant(ctx.tenant_id)
        result = await executor.ainvoke(input_data, config=config)

        # Extract output
        output = result.get("output", "")

        duration_ms = int((time.perf_counter() - start) * 1000)

        return TurnResult(
            output=output,
            agent_used="solo",
            duration_ms=duration_ms,
            metadata={},
        )

    async def probe(self) -> ProbeResult:
        """Health check for Solo engine.

        Runs a minimal probe without touching patient data.
        """
        start = time.perf_counter()

        try:
            from main import get_agent_executable

            # Get executor without tenant-specific config
            executor = get_agent_executable()

            # Minimal probe with no tools
            result = await executor.ainvoke(
                {"input": "Responde exactamente: pong", "chat_history": []},
                config={"configurable": {"session_id": "healthcheck-probe"}},
            )

            output = result.get("output", "").lower()

            if "pong" in output:
                latency_ms = int((time.perf_counter() - start) * 1000)
                return ProbeResult(
                    ok=True,
                    latency_ms=latency_ms,
                    detail=f"TORA responded with 'pong' in {latency_ms}ms",
                )
            else:
                latency_ms = int((time.perf_counter() - start) * 1000)
                return ProbeResult(
                    ok=False,
                    latency_ms=latency_ms,
                    error="Unexpected response",
                    detail="TORA did not return expected 'pong'",
                )

        except asyncio.TimeoutError:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return ProbeResult(
                ok=False,
                latency_ms=latency_ms,
                error="Timeout",
                detail="TORA probe timed out after 10s",
            )
        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            logger.exception("SoloEngine probe failed")
            return ProbeResult(
                ok=False,
                latency_ms=latency_ms,
                error=str(e),
                detail=f"TORA probe failed: {type(e).__name__}",
            )


# =============================================================================
# Multi-Agent Engine (Stub)
# =============================================================================


class MultiAgentEngine:
    """Multi-agent engine backed by LangGraph-style supervisor + 6 specialists.

    Delegates to `agents.graph.run_turn` which loads PatientContext, routes via
    the Supervisor (deterministic rules + LLM fallback), dispatches to the
    specialized agent, and writes an audit row in `agent_turn_log`.

    The import is lazy inside each method to avoid circular imports with
    `main` (where the DENTAL_TOOLS live).
    """

    name: str = "multi"

    async def process_turn(self, ctx: TurnContext) -> TurnResult:
        """Run the turn through the multi-agent graph.

        Raises are caught upstream by the caller (buffer_task) so the circuit
        breaker can record a failure and fallback to SoloEngine.
        """
        from agents.graph import run_turn as graph_run_turn

        return await graph_run_turn(ctx)

    async def probe(self) -> ProbeResult:
        """Health check for the multi-agent graph.

        Calls `agents.graph.probe()` which runs a minimal supervisor routing
        decision without touching DB or LLM (deterministic path only) to keep
        the probe fast (<5s) and side-effect-free.
        """
        try:
            from agents.graph import probe as graph_probe

            return await graph_probe()
        except Exception as e:
            latency_ms = 0
            logger.exception("MultiAgentEngine probe failed during import/call")
            return ProbeResult(
                ok=False,
                latency_ms=latency_ms,
                error=str(e),
                detail=f"Multi-agent probe failed: {type(e).__name__}",
            )


# =============================================================================
# Circuit Breaker State
# =============================================================================


@dataclass
class CircuitState:
    """Circuit breaker state for a tenant."""

    failures: int = 0
    window_start: float = 0.0
    is_tripped: bool = False
    trip_time: float = 0.0


# =============================================================================
# Engine Router
# =============================================================================


class EngineRouter:
    """Routes requests to the appropriate engine based on tenant config.

    Features:
    - In-memory cache with 60s TTL
    - Circuit breaker (3 failures → 5min fallback to solo)
    - Redis pubsub for cross-process invalidation
    """

    # Cache settings
    CACHE_TTL: int = 60  # seconds
    CACHE_MAX_AGE: float = 60.0

    # Circuit breaker settings
    CIRCUIT_THRESHOLD: int = 3
    CIRCUIT_WINDOW: int = 60  # seconds
    CIRCUIT_RECOVERY: int = 300  # seconds (5 minutes)

    # Redis channel for invalidation
    INVALIDATE_CHANNEL = "engine_router_invalidate"

    _MAX_TENANTS = 500  # hard cap — evict stale entries beyond this

    def __init__(self):
        self._cache: dict[int, tuple[str, float]] = {}  # tenant_id -> (mode, expiry)
        self._circuit_breaker: dict[int, CircuitState] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._pubsub_initialized = False

    def _get_lock(self, tenant_id: int) -> asyncio.Lock:
        """Get or create a lock for a tenant."""
        if tenant_id not in self._locks:
            # Evict expired cache/lock entries if over limit
            if len(self._locks) >= self._MAX_TENANTS:
                self._evict_stale()
            self._locks[tenant_id] = asyncio.Lock()
        return self._locks[tenant_id]

    def _evict_stale(self):
        """Remove stale cache, circuit breaker, and lock entries."""
        import time
        now = time.time()
        expired = [tid for tid, (_, exp) in self._cache.items() if exp < now]
        for tid in expired:
            self._cache.pop(tid, None)
            self._circuit_breaker.pop(tid, None)
            # Only remove lock if not currently held
            lock = self._locks.get(tid)
            if lock and not lock.locked():
                self._locks.pop(tid, None)

    async def _init_pubsub(self):
        """Initialize Redis pubsub for cross-process cache invalidation."""
        if self._pubsub_initialized:
            return

        try:
            from services.relay import get_redis

            redis = get_redis()
            pubsub = redis.pubsub()
            await pubsub.subscribe(self.INVALIDATE_CHANNEL)

            # Create task to listen for invalidation messages
            async def listen():
                async for msg in pubsub.listen():
                    if msg["type"] == "message":
                        try:
                            tenant_id = int(msg["data"])
                            self._cache.pop(tenant_id, None)
                            logger.info(
                                f"Cache invalidated via pubsub for tenant {tenant_id}"
                            )
                        except (ValueError, TypeError):
                            pass

            asyncio.create_task(listen())
            self._pubsub_initialized = True
            logger.info("Engine router pubsub initialized")
        except Exception as e:
            logger.warning(f"Could not initialize pubsub: {e}")
            self._pubsub_initialized = True  # Don't retry

    async def get_engine_for_tenant(self, tenant_id: int) -> Engine:
        """Get the appropriate engine for a tenant.

        Returns SoloEngine or MultiAgentEngine based on tenant config.
        Uses circuit breaker to fallback to solo if multi is failing.
        """
        # Initialize pubsub if needed
        await self._init_pubsub()

        # Check circuit breaker first
        if self._is_tripped(tenant_id):
            logger.info(
                f"Circuit breaker tripped for tenant {tenant_id}, using SoloEngine"
            )
            return SoloEngine()

        # Get mode from cache or DB
        mode = await self._get_mode(tenant_id)

        if mode == "multi":
            return MultiAgentEngine()
        else:
            return SoloEngine()

    async def _get_mode(self, tenant_id: int) -> str:
        """Get engine mode for a tenant, with caching."""
        lock = self._get_lock(tenant_id)

        async with lock:
            # Check cache
            if tenant_id in self._cache:
                mode, expiry = self._cache[tenant_id]
                if time.time() < expiry:
                    return mode

            # Cache miss - load from DB
            mode = await self._load_mode_from_db(tenant_id)

            # Update cache
            self._cache[tenant_id] = (mode, time.time() + self.CACHE_TTL)

            return mode

    async def _load_mode_from_db(self, tenant_id: int) -> str:
        """Load engine mode from database."""
        from database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Tenant.ai_engine_mode).where(Tenant.id == tenant_id)
            )
            mode = result.scalar_one_or_none()

            if mode is None:
                logger.warning(f"Tenant {tenant_id} not found, defaulting to 'solo'")
                return "solo"

            # Validate mode
            if mode not in ("solo", "multi"):
                logger.warning(
                    f"Invalid ai_engine_mode '{mode}' for tenant {tenant_id}, defaulting to 'solo'"
                )
                return "solo"

            return mode

    def _is_tripped(self, tenant_id: int) -> bool:
        """Check if circuit breaker is tripped for a tenant."""
        if tenant_id not in self._circuit_breaker:
            return False

        state = self._circuit_breaker[tenant_id]

        if not state.is_tripped:
            return False

        # Check if recovery time has passed
        if time.time() - state.trip_time >= self.CIRCUIT_RECOVERY:
            # Reset circuit breaker
            self._circuit_breaker[tenant_id] = CircuitState()
            return False

        return True

    def _record_failure(self, tenant_id: int) -> bool:
        """Record a failure and return True if circuit should trip."""
        now = time.time()

        if tenant_id not in self._circuit_breaker:
            self._circuit_breaker[tenant_id] = CircuitState(
                failures=1,
                window_start=now,
                is_tripped=False,
            )
            return False

        state = self._circuit_breaker[tenant_id]

        # Check if we're still within the failure window
        if now - state.window_start > self.CIRCUIT_WINDOW:
            # Reset window
            state.failures = 1
            state.window_start = now
            state.is_tripped = False
            return False

        # Increment failures
        state.failures += 1

        # Check if we should trip
        if state.failures >= self.CIRCUIT_THRESHOLD:
            state.is_tripped = True
            state.trip_time = now
            logger.error(
                f"Circuit breaker TRIPPED for tenant {tenant_id} after {state.failures} failures. "
                f"Falling back to SoloEngine for {self.CIRCUIT_RECOVERY}s."
            )
            return True

        return False

    async def record_failure(self, tenant_id: int, error: Exception):
        """Record a failure for the circuit breaker.

        Called when MultiAgentEngine fails. If circuit trips, the next
        get_engine_for_tenant call will return SoloEngine.
        """
        self._record_failure(tenant_id)
        logger.warning(f"MultiAgentEngine failed for tenant {tenant_id}: {error}")

    def invalidate_cache(self, tenant_id: int):
        """Invalidate cache for a tenant.

        Called after PATCH updates ai_engine_mode.
        """
        self._cache.pop(tenant_id, None)
        logger.info(f"Cache invalidated for tenant {tenant_id}")

    async def publish_invalidation(self, tenant_id: int):
        """Publish cache invalidation to other processes via Redis."""
        try:
            from services.relay import get_redis

            redis = get_redis()
            await redis.publish(self.INVALIDATE_CHANNEL, str(tenant_id))
        except Exception as e:
            logger.warning(f"Could not publish invalidation: {e}")


# =============================================================================
# Singleton instance
# =============================================================================


engine_router = EngineRouter()


# =============================================================================
# Helper functions (for buffer_task.py integration)
# =============================================================================


async def get_engine_for_tenant(tenant_id: int) -> Engine:
    """Convenience function to get engine for a tenant."""
    return await engine_router.get_engine_for_tenant(tenant_id)


def invalidate_cache(tenant_id: int):
    """Convenience function to invalidate cache."""
    engine_router.invalidate_cache(tenant_id)


async def record_engine_failure(tenant_id: int, error: Exception):
    """Record an engine failure for circuit breaker."""
    await engine_router.record_failure(tenant_id, error)
