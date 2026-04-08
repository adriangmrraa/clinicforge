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

    state: AgentState = {
        "tenant_id": ctx.tenant_id,
        "phone_number": ctx.phone_number,
        "thread_id": ctx.thread_id,
        "turn_id": turn_id,
        "user_message": ctx.user_message,
        "patient_profile": profile,
        "chat_history": chat_history,
        "working_state": {},
        "active_agent": "supervisor",
        "hop_count": 0,
        "max_hops": MAX_HOPS,
        "agent_output": "",
        "tools_called": [],
        "handoff_reason": None,
        "start_time": start,
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

    # Best-effort audit log
    model_used = AGENTS[next_agent_name].model if next_agent_name in AGENTS else "unknown"
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
        fake_state: AgentState = {
            "tenant_id": 0,
            "phone_number": "probe",
            "thread_id": "probe",
            "turn_id": "probe",
            "user_message": "hola",
            "patient_profile": {"human_override_until": None, "is_new_lead": True},
            "chat_history": [],
            "working_state": {},
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
