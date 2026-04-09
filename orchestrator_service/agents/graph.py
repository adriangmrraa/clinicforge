"""Multi-agent graph wiring + `run_turn` entry point for MultiAgentEngine (C3 F3).

Minimal implementation without a hard dependency on the `langgraph` package:
- Supervisor decides which specialized agent handles the turn.
- Selected agent runs, sets `agent_output`, and terminates.
- Audit row written to `agent_turn_log` (best-effort).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import text

from .specialists import AGENTS
from .state import AgentState
from .supervisor import SupervisorAgent

if TYPE_CHECKING:
    from services.engine_router import ProbeResult, TurnContext, TurnResult

logger = logging.getLogger(__name__)

MAX_HOPS = 5
TURN_TIMEOUT_S = 45

_supervisor = SupervisorAgent()


async def _load_patient_context(tenant_id: int, phone_number: str) -> tuple[dict, list[dict]]:
    """Load minimal patient profile and chat history for the turn."""
    from services.patient_context import PatientContext
    ctx = await PatientContext.load(tenant_id, phone_number)
    p = ctx.profile
    profile_dict = {
        "name": p.name,
        "dni": p.dni,
        "email": p.email,
        "is_new_lead": p.is_new_lead,
        "human_override_until": p.human_override_until.isoformat() if p.human_override_until else None,
        "medical_history": p.medical_history,
        "future_appointments": p.future_appointments,
    }
    return profile_dict, p.recent_turns


async def _log_turn(state: AgentState, agent_name: str, duration_ms: int, model: str, handoff_to: str = None) -> None:
    """Insert a row in agent_turn_log. Best-effort — failure is logged and swallowed."""
    try:
        from main import AsyncSessionLocal  # type: ignore
    except Exception as e:
        logger.debug(f"_log_turn: AsyncSessionLocal unavailable: {e}")
        return

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    INSERT INTO agent_turn_log
                        (tenant_id, phone_number, turn_id, agent_name,
                         tools_called, handoff_to, duration_ms, model)
                    VALUES
                        (:tenant_id, :phone, :turn_id, :agent,
                         CAST(:tools AS JSONB), :handoff, :dur, :model)
                """),
                {
                    "tenant_id": state["tenant_id"],
                    "phone": state["phone_number"],
                    "turn_id": state["turn_id"],
                    "agent": agent_name,
                    "tools": json.dumps(state.get("tools_called", []), default=str),
                    "handoff": handoff_to,
                    "dur": duration_ms,
                    "model": model,
                },
            )
            await session.commit()
    except Exception as e:
        logger.warning(f"Failed to write agent_turn_log: {e}")


async def run_turn(ctx: "TurnContext") -> "TurnResult":
    """Entry point invoked by MultiAgentEngine.process_turn.

    1. Load patient context (profile + history)
    2. Build initial AgentState
    3. Supervisor routes
    4. Specialized agent runs
    5. Audit log + return TurnResult
    """
    from services.engine_router import TurnResult  # lazy — avoid circular
    start = time.perf_counter()
    turn_id = str(uuid.uuid4())

    try:
        profile, chat_history = await _load_patient_context(ctx.tenant_id, ctx.phone_number)
    except Exception:
        logger.exception("Failed to load patient context")
        profile = {
            "name": None, "dni": None, "email": None, "is_new_lead": True,
            "human_override_until": None, "medical_history": {}, "future_appointments": [],
        }
        chat_history = []

    # Resolve the tenant's configured model ONCE per turn from system_config.OPENAI_MODEL
    # (single source of truth — same as SoloEngine / TORA legacy). NEVER hardcoded.
    try:
        from .model_resolver import resolve_tenant_model
        model_config = await resolve_tenant_model(ctx.tenant_id)
    except Exception:
        logger.exception("Failed to resolve tenant model, using default")
        from .model_resolver import get_default_model_config
        model_config = get_default_model_config()

    # Build tenant-configured context blocks ONCE per turn (multi-agent parity
    # with TORA solo — spec: multi-agent-tenant-context-parity REQ-3).
    # All specialists in this turn read from the same dict via
    # select_blocks_for_specialist(). Failure is non-fatal: empty dict falls
    # through to bare prompts so the multi-agent still runs.
    tenant_context: dict = {}
    try:
        from db import db  # lazy — avoid circular
        from .tenant_context import build_tenant_context_blocks

        # Defensive intent classification (REQ-3.1) — safe default on failure.
        try:
            from services.buffer_task import classify_intent  # type: ignore
            intent_tags = classify_intent([{"role": "user", "content": ctx.user_message}])
        except Exception:
            intent_tags = set()

        tenant_context = await build_tenant_context_blocks(
            db.pool,
            ctx.tenant_id,
            user_message_text=ctx.user_message or "",
            intent_tags=intent_tags,
        )
    except Exception:
        logger.exception("build_tenant_context_blocks failed — continuing with empty context")
        tenant_context = {}

    state: AgentState = {
        "tenant_id": ctx.tenant_id,
        "phone_number": ctx.phone_number,
        "thread_id": ctx.thread_id,
        "turn_id": turn_id,
        "user_message": ctx.user_message,
        "patient_profile": profile,
        "chat_history": chat_history,
        "working_state": {},
        "model_config": model_config,
        "tenant_context": tenant_context,
        "active_agent": "supervisor",
        "hop_count": 0,
        "max_hops": MAX_HOPS,
        "agent_output": "",
        "tools_called": [],
        "handoff_reason": None,
        "start_time": start,
        # Social channel context (Instagram/Facebook agent — phase 5).
        # Populated from ctx.extra which is set by buffer_task.compute_social_context.
        # Safe defaults ensure backward compat with callers that don't set extra.
        "channel": ctx.extra.get("channel", "whatsapp"),
        "is_social_channel": ctx.extra.get("is_social_channel", False),
        "social_landings": ctx.extra.get("social_landings"),
        "instagram_handle": ctx.extra.get("instagram_handle"),
        "facebook_page_id": ctx.extra.get("facebook_page_id"),
        "whatsapp_link": ctx.extra.get("whatsapp_link"),
    }

    # Human override silence window → empty output, agent_used=handoff
    if state["patient_profile"].get("human_override_until"):
        duration_ms = int((time.perf_counter() - start) * 1000)
        return TurnResult(
            output="",
            agent_used="handoff",
            duration_ms=duration_ms,
            metadata={"reason": "human_override_silence", "turn_id": turn_id},
        )

    next_agent_name = "reception"
    try:
        async with asyncio.timeout(TURN_TIMEOUT_S):
            next_agent_name = await _supervisor.route(state)
            state["active_agent"] = next_agent_name
            state["hop_count"] = state.get("hop_count", 0) + 1

            agent = AGENTS.get(next_agent_name)
            if agent is None:
                next_agent_name = "reception"
                agent = AGENTS["reception"]
            state = await agent.run(state)
    except asyncio.TimeoutError:
        logger.error(f"Multi-agent turn timed out after {TURN_TIMEOUT_S}s")
        state["agent_output"] = "Disculpá, estoy tardando más de lo esperado. ¿Podés reformular tu mensaje?"
        next_agent_name = "timeout"
    except Exception:
        logger.exception("Multi-agent graph failed")
        state["agent_output"] = "Tuve un problema procesando tu mensaje. Te conecto con el equipo."
        next_agent_name = "error"

    duration_ms = int((time.perf_counter() - start) * 1000)

    # Best-effort audit log — use the REAL model that was configured for the tenant
    # (from state["model_config"]), not a hardcoded per-agent default
    model_used = (state.get("model_config") or {}).get("model") or "unknown"
    await _log_turn(state, next_agent_name, duration_ms, model_used)

    return TurnResult(
        output=state.get("agent_output", "") or "",
        agent_used=next_agent_name,
        duration_ms=duration_ms,
        metadata={
            "turn_id": turn_id,
            "hop_count": state.get("hop_count", 0),
            "tools_called": [t.get("tool") for t in state.get("tools_called", [])],
        },
    )


async def probe() -> "ProbeResult":
    """Health probe for the multi-agent graph.

    Runs supervisor routing on a fake minimal state with no LLM call
    (deterministic rules cover the greeting path). Pure code-path validation.
    """
    from services.engine_router import ProbeResult  # lazy — avoid circular
    start = time.perf_counter()

    try:
        from .model_resolver import get_default_model_config
        fake_state: AgentState = {
            "tenant_id": 0,
            "phone_number": "probe",
            "thread_id": "probe",
            "turn_id": "probe",
            "user_message": "hola",
            "patient_profile": {"human_override_until": None, "is_new_lead": True},
            "chat_history": [],
            "working_state": {},
            "model_config": get_default_model_config(),
            "active_agent": "supervisor",
            "hop_count": 0,
            "max_hops": MAX_HOPS,
            "agent_output": "",
            "tools_called": [],
            "handoff_reason": None,
            "start_time": start,
        }

        next_agent = await asyncio.wait_for(_supervisor.route(fake_state), timeout=5.0)
        latency_ms = int((time.perf_counter() - start) * 1000)

        if next_agent in AGENTS:
            return ProbeResult(
                ok=True,
                latency_ms=latency_ms,
                detail=f"Multi-agent graph healthy. Supervisor routed probe to '{next_agent}' in {latency_ms}ms.",
            )
        return ProbeResult(
            ok=False,
            latency_ms=latency_ms,
            error="Invalid routing",
            detail=f"Supervisor returned unknown agent '{next_agent}'",
        )
    except asyncio.TimeoutError:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return ProbeResult(ok=False, latency_ms=latency_ms, error="Timeout", detail="Supervisor probe timed out after 5s")
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.exception("Multi-agent probe failed")
        return ProbeResult(ok=False, latency_ms=latency_ms, error=str(e), detail=f"Probe failed: {type(e).__name__}")
